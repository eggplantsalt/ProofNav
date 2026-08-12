"""Independent hidden-truth and structural audit for M2.1.

This module never imports or calls the online verifier.  It reconstructs proof
state from raw transitions through the separate offline implementation and
uses hidden truth only after the runtime decision is immutable.  The returned
record is publication/audit metadata and contains no runtime feedback.
"""

import copy

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS
from proofnav.offline.oracle_evidence import validate_controlled_truth
from proofnav.offline.structural_audit import (
    audit_certificate,
    audit_terminal,
    structural_result,
)


def _truth_claims(truth):
    return {
        item["obligation_id"]: item for item in truth["claims"]
    }


def _truth_identity_matches_state(truth, state):
    identity = {
        "episode_id": state["episode_id"],
        "scope_contract_id": state["scope_contract_id"],
        "scope_version": state["scope_version"],
        "scope_digest": state["scope_digest"],
        "template_id": state["template_id"],
        "template_digest": state["template_digest"],
        "universe_digest": state["universe_digest"],
    }
    return all(truth.get(key) == expected for key, expected in identity.items())


def _claim_matches_truth(truth, certificate):
    """Check verdict, dynamic universe, typed binding, and claim polarity."""

    if not isinstance(certificate, dict):
        return False
    requested = certificate.get("requested_verdict")
    if requested != truth["semantic_truth"]:
        return False
    payload = certificate.get("payload")
    if not isinstance(payload, dict):
        return False
    hypotheses = {
        item["hypothesis_id"]: item for item in truth["hypotheses"]
    }
    obligations = {
        item["obligation_id"]: item for item in truth["obligations"]
    }
    claims = _truth_claims(truth)
    if requested == "FOUND":
        hypothesis = payload.get("hypothesis")
        if not isinstance(hypothesis, dict):
            return False
        hypothesis_id = hypothesis.get("hypothesis_id")
        if (hypothesis_id not in truth["supported_hypothesis_ids"]
                or hypothesis != hypotheses.get(hypothesis_id)
                or payload.get("binding") != hypothesis.get("binding")):
            return False
        necessary = {
            item["obligation_id"]: item for item in obligations.values()
            if item["hypothesis_id"] == hypothesis_id and item["necessary"]
        }
        path = payload.get("true_path")
        if not isinstance(path, list) or {
                item.get("obligation_id") for item in path
                if isinstance(item, dict)} != set(necessary):
            return False
        for item in path:
            if not isinstance(item, dict):
                return False
            obligation_id = item.get("obligation_id")
            obligation = necessary.get(obligation_id)
            claim = claims.get(obligation_id)
            if obligation is None or claim is None:
                return False
            if not (
                    item.get("hypothesis_id") == hypothesis_id
                    and item.get("hypothesis_kind") == hypothesis["hypothesis_kind"]
                    and item.get("binding") == hypothesis["binding"]
                    and item.get("predicate_id") == obligation["predicate_id"]
                    and item.get("predicate_kind") == obligation["predicate_kind"]
                    and claim["hypothesis_id"] == hypothesis_id
                    and claim["predicate_id"] == obligation["predicate_id"]
                    and claim["predicate_kind"] == obligation["predicate_kind"]
                    and claim["binding"] == hypothesis["binding"]
                    and claim["claim"] == "SUPPORTS"):
                return False
        return True
    if requested == "NOT_FOUND":
        expected_ids = set(hypotheses)
        if set(certificate.get("hypothesis_ids", [])) != expected_ids:
            return False
        index = payload.get("hypothesis_index")
        if (not isinstance(index, list)
                or {item.get("hypothesis_id") for item in index if isinstance(item, dict)} != expected_ids
                or any(item != hypotheses.get(item.get("hypothesis_id")) for item in index if isinstance(item, dict))):
            return False
        cover = payload.get("refutation_cover")
        if not isinstance(cover, list):
            return False
        covered = set()
        for item in cover:
            if not isinstance(item, dict):
                return False
            hypothesis_id = item.get("hypothesis_id")
            obligation_id = item.get("obligation_id")
            hypothesis = hypotheses.get(hypothesis_id)
            obligation = obligations.get(obligation_id)
            claim = claims.get(obligation_id)
            if hypothesis is None or obligation is None or claim is None:
                return False
            if not (
                    obligation["hypothesis_id"] == hypothesis_id
                    and obligation["necessary"]
                    and item.get("hypothesis_kind") == hypothesis["hypothesis_kind"]
                    and item.get("binding") == hypothesis["binding"]
                    and item.get("predicate_id") == obligation["predicate_id"]
                    and item.get("predicate_kind") == obligation["predicate_kind"]
                    and claim["hypothesis_id"] == hypothesis_id
                    and claim["predicate_id"] == obligation["predicate_id"]
                    and claim["predicate_kind"] == obligation["predicate_kind"]
                    and claim["binding"] == hypothesis["binding"]
                    and claim["claim"] == "REFUTES"):
                return False
            covered.add(hypothesis_id)
        return covered == expected_ids == set(truth["refuted_hypothesis_ids"])
    return False


def _report(outcome, truth, terminal, reasons, structure, certificate_audit,
            terminal_audit, claim_matches):
    runtime_verdict = (
        terminal.get("semantic_verdict") if isinstance(terminal, dict) else None
    )
    conflict = outcome in ("FALSE_ACCEPT", "FALSE_REJECT", "WRONG_SCOPE")
    return {
        "schema_version": SCHEMA_VERSIONS["offline_verification"],
        "outcome": outcome,
        "online_offline_conflict": conflict,
        "audit_disposition": (
            runtime_verdict if outcome == "TRUE_ACCEPT" else "UNRESOLVED"
        ),
        "certificate_accepted_for_audit": outcome == "TRUE_ACCEPT",
        "truth_verdict": truth["semantic_truth"],
        "runtime_verdict": runtime_verdict,
        "scope_contract_id": truth["scope_contract_id"],
        "structural_valid": structure["valid"],
        "certificate_structural_valid": certificate_audit["valid"],
        "terminal_structural_valid": terminal_audit["valid"],
        "claim_matches_truth": bool(claim_matches),
        "reason_codes": sorted(set(reasons)),
        "feedback_to_runtime": None,
    }


class OracleOfflineVerifier(object):
    """Classify immutable online outcomes against hidden controlled truth."""

    def verify(self, truth, audit_bundle, terminal_decision, certificate):
        truth = copy.deepcopy(truth)
        validate_controlled_truth(truth)
        bundle = copy.deepcopy(audit_bundle)
        terminal = copy.deepcopy(terminal_decision)
        cert = copy.deepcopy(certificate)

        structure = structural_result(bundle)
        state = structure["state"]
        if state is None:
            certificate_audit = {
                "valid": False,
                "reason_codes": ["OFFLINE_AUDIT_BUNDLE_INVALID"],
                "requested_verdict": (
                    cert.get("requested_verdict") if isinstance(cert, dict) else None
                ),
            }
            terminal_audit = {
                "valid": False,
                "reason_codes": ["OFFLINE_AUDIT_BUNDLE_INVALID"],
                "online_status": (
                    terminal.get("online_verification", {}).get("status")
                    if isinstance(terminal, dict) else None
                ),
                "online_accepted": (
                    bool(terminal.get("certificate_accepted"))
                    if isinstance(terminal, dict) else False
                ),
                "preflight_firewall": False,
            }
            truth_identity = False
        else:
            certificate_audit = audit_certificate(bundle, cert, state=state)
            terminal_audit = audit_terminal(state, terminal, cert)
            truth_identity = _truth_identity_matches_state(truth, state)
        claim_matches = (
            truth_identity and certificate_audit["valid"]
            and _claim_matches_truth(truth, cert)
        )
        reasons = (
            list(structure["reason_codes"])
            + list(certificate_audit["reason_codes"])
            + list(terminal_audit["reason_codes"])
        )
        online_status = terminal_audit.get("online_status")
        online_accepted = terminal_audit.get("online_accepted", False)

        # WRONG_SCOPE is reserved for an internally valid artifact from a
        # genuinely different scope.  Tampering a scope field breaks the cert
        # digest/identity and is therefore a correct rejection instead.
        wrong_scope = (
            structure["valid"] and certificate_audit["valid"]
            and terminal_audit["valid"] and not truth_identity
        )
        if wrong_scope:
            reasons.append("OFFLINE_SCOPE_MISMATCH")
            return _report(
                "WRONG_SCOPE", truth, terminal, reasons, structure,
                certificate_audit, terminal_audit, claim_matches,
            )

        if online_accepted or (
                isinstance(terminal, dict)
                and terminal.get("certificate_accepted") is True):
            if (structure["valid"] and certificate_audit["valid"]
                    and terminal_audit["valid"] and claim_matches):
                outcome = "TRUE_ACCEPT"
            else:
                outcome = "FALSE_ACCEPT"
                reasons.append("OFFLINE_ACCEPTED_INVALID_OR_FALSE_CERTIFICATE")
            return _report(
                outcome, truth, terminal, reasons, structure,
                certificate_audit, terminal_audit, claim_matches,
            )

        if online_status == "REJECT":
            # Do not trust a rejecting verifier's self-reported reason code as
            # proof that the rejection was correct.  Most policy violations
            # (bad proposal identity, malformed execution/certificate, stale
            # provenance) are already established independently by the three
            # structural audits above.  The sole valid-certificate exception
            # in M2.1 is the production verifier's fail-closed preflight over
            # an otherwise valid controlled-replay bundle; audit_terminal
            # recognizes that exact state-less boundary record.
            policy_reject = terminal_audit.get("preflight_firewall", False)
            if (structure["valid"] and certificate_audit["valid"]
                    and terminal_audit["valid"] and claim_matches
                    and not policy_reject):
                outcome = "FALSE_REJECT"
                reasons.append("OFFLINE_REJECTED_VALID_TRUE_CERTIFICATE")
            else:
                outcome = "CORRECT_REJECT"
                reasons.append("OFFLINE_REJECTED_INVALID_OR_POLICY_FORBIDDEN_CERTIFICATE")
            return _report(
                outcome, truth, terminal, reasons, structure,
                certificate_audit, terminal_audit, claim_matches,
            )

        return _report(
            "UNRESOLVED", truth, terminal, reasons, structure,
            certificate_audit, terminal_audit, claim_matches,
        )


__all__ = ["OracleOfflineVerifier"]
