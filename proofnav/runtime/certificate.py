"""Deterministic M2.1 certificates over a causal, recomputable proof state.

The builder is not a trust boundary (the online verifier is), but it consumes
the same decision-audit bundle and refuses to construct a certificate from a
caller-supplied closure flag, frontier array, or static hypothesis list.
"""

import copy

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.runtime.semantics import (
    RESIDUAL_HYPOTHESIS_KINDS, recompute_view, registered_admission_profile,
)


_CERTIFICATE_FIELDS = {
    "schema_version", "certificate_id", "certificate_digest",
    "certificate_type", "requested_verdict", "episode_id",
    "scope_contract_id", "scope_version", "scope_digest", "template_id",
    "template_digest", "proof_state_version", "decision_cut",
    "transition_tip", "proof_state_digest", "audit_bundle_digest",
    "universe_digest", "binding_digest", "closure_witness",
    "ledger_digest", "budget_snapshot", "cost_snapshot", "risk_claim",
    "hypothesis_ids", "obligation_ids", "evidence_ids", "payload",
    "provenance",
}


def _copy(value):
    return copy.deepcopy(value)


def _frontier(snapshot):
    return list(snapshot.get("topology", {}).get("frontier_viewpoint_ids", []))


def _feedback(snapshot, reason_codes, missing=None, uncovered=None):
    return {
        "reason_codes": sorted(set(reason_codes)),
        "missing_obligation_ids": sorted(set(missing or [])),
        "uncovered_hypothesis_ids": sorted(set(uncovered or [])),
        "frontier_viewpoint_ids": sorted(_frontier(snapshot)),
        "recommended_action": "CONTINUE_EVIDENCE_COLLECTION",
    }


def _outcome(snapshot, certificate=None, reason_codes=None, missing=None,
             uncovered=None):
    return {
        "status": "CERTIFICATE" if certificate is not None else "UNRESOLVED",
        "certificate": certificate,
        "decision_cut": _copy(snapshot.get("decision_cut")),
        "proof_state_digest": snapshot.get("proof_state_digest"),
        "feedback": _feedback(
            snapshot, reason_codes or [], missing=missing, uncovered=uncovered,
        ),
    }


def _canonical_bundle(source):
    """Return ``(audit_bundle, recomputed_view)`` without trusting its state."""

    if hasattr(source, "audit_bundle") and callable(source.audit_bundle):
        bundle = source.audit_bundle()
    elif isinstance(source, dict):
        bundle = _copy(source)
    else:
        raise ContractViolation(
            "AUDIT_BUNDLE_REQUIRED", "$", "certificate construction needs raw transitions",
        )
    if not isinstance(bundle, dict) or set(bundle) != {
            "schema_version", "scope", "template", "admission_profile",
            "risk_claims", "transitions", "state", "bundle_digest"}:
        raise ContractViolation(
            "AUDIT_BUNDLE_SCHEMA", "$", "expected the exact M2.1 decision bundle",
        )
    if bundle["schema_version"] != SCHEMA_VERSIONS["audit_bundle"]:
        raise ContractViolation(
            "AUDIT_BUNDLE_VERSION", "$.schema_version", "unsupported decision bundle",
        )
    digest_body = _copy(bundle)
    claimed_digest = digest_body.pop("bundle_digest")
    if claimed_digest != canonical_sha256(digest_body):
        raise ContractViolation(
            "AUDIT_BUNDLE_DIGEST", "$.bundle_digest", "bundle was modified",
        )
    base = {key: _copy(bundle[key]) for key in (
        "schema_version", "scope", "template", "admission_profile",
        "risk_claims", "transitions",
    )}
    # Replay construction is offline-only, but this pure builder must still
    # demand the exact code-owned profile that the transition fold validates.
    allow_controlled = (
        base["admission_profile"] == registered_admission_profile(True)
    )
    expected_profile = registered_admission_profile(allow_controlled)
    if base["admission_profile"] != expected_profile:
        raise ContractViolation(
            "ADMISSION_PROFILE_NOT_CODE_OWNED", "$.admission_profile",
            "registered M2.1 profile required",
        )
    snapshot = recompute_view(base, allow_controlled=allow_controlled)
    if bundle["state"] != snapshot:
        raise ContractViolation(
            "AUDIT_STATE_MISMATCH", "$.state", "cached state differs from transition fold",
        )
    return bundle, snapshot


def _indexes(snapshot):
    hypotheses = {
        item["hypothesis_id"]: item for item in snapshot["hypotheses"]
    }
    obligations = {
        item["obligation_id"]: item for item in snapshot["obligations"]
    }
    by_hypothesis = {key: [] for key in hypotheses}
    for obligation in snapshot["obligations"]:
        by_hypothesis[obligation["hypothesis_id"]].append(obligation)
    for values in by_hypothesis.values():
        values.sort(key=lambda item: item["obligation_id"])
    evidence = {
        item["evidence"]["evidence_id"]: item
        for item in snapshot["active_bound_evidence"]
    }
    return hypotheses, obligations, by_hypothesis, evidence


def _coverage_item(hypothesis, obligation, evidence_ids):
    return {
        "hypothesis_id": hypothesis["hypothesis_id"],
        "hypothesis_kind": hypothesis["hypothesis_kind"],
        "binding": _copy(hypothesis["binding"]),
        "obligation_id": obligation["obligation_id"],
        "predicate_id": obligation["predicate_id"],
        "predicate_kind": obligation["predicate_kind"],
        "evidence_ids": sorted(evidence_ids),
    }


def _bound_evidence_matches(wrapper, hypothesis, obligation, polarity):
    """Check the complete typed substitution, not merely an obligation ID."""

    evidence = wrapper.get("evidence", {})
    return (
        wrapper.get("hypothesis_id") == hypothesis["hypothesis_id"]
        and wrapper.get("obligation_id") == obligation["obligation_id"]
        and wrapper.get("predicate_id") == obligation["predicate_id"]
        and wrapper.get("predicate_kind") == obligation["predicate_kind"]
        and wrapper.get("binding") == hypothesis["binding"]
        and obligation.get("binding_requirement") == hypothesis["binding"]
        and evidence.get("obligation_id") == obligation["obligation_id"]
        and evidence.get("predicate_id") == obligation["predicate_id"]
        and evidence.get("claim") == polarity
    )


def _selected_evidence_valid(ids, evidence, hypothesis, obligation, polarity):
    return bool(ids) and all(
        evidence_id in evidence
        and _bound_evidence_matches(
            evidence[evidence_id], hypothesis, obligation, polarity,
        )
        for evidence_id in ids
    )


def _finalize(bundle, snapshot, certificate_type, requested_verdict,
              hypothesis_ids, obligation_ids, evidence_ids, payload):
    evidence = {
        item["evidence"]["evidence_id"]: item
        for item in snapshot["active_bound_evidence"]
    }
    selected = [evidence[key] for key in sorted(evidence_ids)]
    certificate = {
        "schema_version": SCHEMA_VERSIONS["m2_certificate"],
        "certificate_type": certificate_type,
        "requested_verdict": requested_verdict,
        "episode_id": snapshot["episode_id"],
        "scope_contract_id": snapshot["scope_contract_id"],
        "scope_version": snapshot["scope_version"],
        "scope_digest": snapshot["scope_digest"],
        "template_id": snapshot["template_id"],
        "template_digest": snapshot["template_digest"],
        "proof_state_version": snapshot["state_version"],
        "decision_cut": _copy(snapshot["decision_cut"]),
        "transition_tip": snapshot["transition_tip"],
        "proof_state_digest": snapshot["proof_state_digest"],
        "audit_bundle_digest": bundle["bundle_digest"],
        "universe_digest": snapshot["universe_digest"],
        "binding_digest": snapshot["binding_digest"],
        "closure_witness": _copy(snapshot["closure_witness"]),
        "ledger_digest": snapshot["ledger_digest"],
        "budget_snapshot": _copy(snapshot["budget_status"]),
        "cost_snapshot": _copy(snapshot["cost_ledger"]),
        "risk_claim": _copy(snapshot["risk_claims"][requested_verdict]),
        "hypothesis_ids": sorted(hypothesis_ids),
        "obligation_ids": sorted(obligation_ids),
        "evidence_ids": sorted(evidence_ids),
        "payload": _copy(payload),
        "provenance": {
            "builder_version": "proofnav.certificate-builder.v2",
            "admission_profile_id": snapshot["audit_trail"]["admission_profile_id"],
            "observation_event_ids": sorted({
                item["evidence"]["source_event_id"] for item in selected
            }),
            "evidence_adapter_versions": sorted({
                item["evidence"]["adapter_version"] for item in selected
            }),
            "ledger_event_count": snapshot["ledger_event_count"],
        },
    }
    certificate["certificate_digest"] = canonical_sha256(certificate)
    certificate["certificate_id"] = "cert-" + certificate["certificate_digest"][:20]
    if set(certificate) != _CERTIFICATE_FIELDS:
        raise AssertionError("internal M2.1 certificate field drift")
    return certificate


class CertificateBuilder(object):
    """Construct positive or refutation-cover certificates at one exact cut."""

    def build(self, state_or_bundle, requested_verdict):
        try:
            bundle, snapshot = _canonical_bundle(state_or_bundle)
        except ContractViolation as error:
            return _outcome({}, reason_codes=[error.code])
        if requested_verdict == "FOUND":
            return self._positive(bundle, snapshot)
        if requested_verdict == "NOT_FOUND":
            return self._refutation(bundle, snapshot)
        return _outcome(snapshot, reason_codes=["VERDICT_TYPE_INVALID"])

    @staticmethod
    def _preconditions(snapshot, verdict):
        reasons = []
        if not snapshot["budget_status"]["within_budget"]:
            reasons.append("BUDGET_EXHAUSTED")
        claim = snapshot["risk_claims"].get(verdict)
        if claim is None:
            reasons.append("RISK_CLAIM_MISSING")
        elif claim["upper_bound"] > claim["budget"]:
            reasons.append("RISK_BUDGET_EXCEEDED")
        return reasons

    def _positive(self, bundle, snapshot):
        reasons = self._preconditions(snapshot, "FOUND")
        hypotheses, _, by_hypothesis, evidence = _indexes(snapshot)
        candidates = []
        missing = []
        binding_failures = []
        for hypothesis_id in sorted(hypotheses):
            hypothesis = hypotheses[hypothesis_id]
            if hypothesis["hypothesis_kind"] in RESIDUAL_HYPOTHESIS_KINDS:
                continue
            necessary = [
                item for item in by_hypothesis[hypothesis_id] if item["necessary"]
            ]
            incomplete = [
                item["obligation_id"] for item in necessary
                if item["status"] != "SATISFIED"
            ]
            if incomplete:
                missing.extend(incomplete)
                continue
            coherent = all(
                _selected_evidence_valid(
                    item["support_evidence_ids"], evidence,
                    hypothesis, item, "SUPPORTS",
                )
                for item in necessary
            )
            if not coherent:
                binding_failures.extend(item["obligation_id"] for item in necessary)
                continue
            candidates.append((hypothesis, necessary))
        if binding_failures:
            reasons.append("POSITIVE_BINDING_INCOHERENT")
            missing.extend(binding_failures)
        if not candidates:
            reasons.append("POSITIVE_PATH_INCOMPLETE")
        if reasons:
            return _outcome(snapshot, reason_codes=reasons, missing=missing)
        hypothesis, necessary = candidates[0]
        true_path = []
        evidence_ids = []
        for obligation in necessary:
            ids = obligation["support_evidence_ids"]
            evidence_ids.extend(ids)
            true_path.append(_coverage_item(hypothesis, obligation, ids))
        payload = {
            "hypothesis": _copy(hypothesis),
            "binding": _copy(hypothesis["binding"]),
            "true_path": true_path,
            "unresolved_obligation_ids": [],
        }
        certificate = _finalize(
            bundle, snapshot, "positive", "FOUND",
            [hypothesis["hypothesis_id"]],
            [item["obligation_id"] for item in necessary],
            evidence_ids, payload,
        )
        return _outcome(snapshot, certificate=certificate)

    def _refutation(self, bundle, snapshot):
        reasons = self._preconditions(snapshot, "NOT_FOUND")
        hypotheses, _, by_hypothesis, evidence = _indexes(snapshot)
        if snapshot["closure_witness"] is None:
            reasons.append("SCOPE_NOT_CLOSED")
        if _frontier(snapshot):
            reasons.append("FRONTIER_OPEN")
        cover = []
        uncovered = []
        evidence_ids = []
        obligation_ids = []
        for hypothesis_id in sorted(hypotheses):
            hypothesis = hypotheses[hypothesis_id]
            necessary = [
                item for item in by_hypothesis[hypothesis_id] if item["necessary"]
            ]
            if hypothesis["hypothesis_kind"] in RESIDUAL_HYPOTHESIS_KINDS:
                selected = necessary
                valid = bool(selected) and all(
                    item["status"] == "REFUTED"
                    and item["predicate_kind"] == "coverage"
                    and _selected_evidence_valid(
                        item["refutation_evidence_ids"], evidence,
                        hypothesis, item, "REFUTES",
                    )
                    for item in selected
                )
            else:
                selected = [
                    item for item in necessary
                    if item["status"] == "REFUTED"
                    and _selected_evidence_valid(
                        item["refutation_evidence_ids"], evidence,
                        hypothesis, item, "REFUTES",
                    )
                ][:1]
                valid = bool(selected)
            if not valid:
                uncovered.append(hypothesis_id)
                continue
            for obligation in selected:
                ids = obligation["refutation_evidence_ids"]
                cover.append(_coverage_item(hypothesis, obligation, ids))
                obligation_ids.append(obligation["obligation_id"])
                evidence_ids.extend(ids)
        if uncovered:
            reasons.append("REFUTATION_COVER_INCOMPLETE")
        if reasons:
            return _outcome(snapshot, reason_codes=reasons, uncovered=uncovered)
        payload = {
            "hypothesis_index": [
                _copy(hypotheses[key]) for key in sorted(hypotheses)
            ],
            "refutation_cover": cover,
            "uncovered_hypothesis_ids": [],
            "frontier_unresolved": [],
        }
        certificate = _finalize(
            bundle, snapshot, "refutation_cover", "NOT_FOUND",
            sorted(hypotheses), obligation_ids, evidence_ids, payload,
        )
        return _outcome(snapshot, certificate=certificate)


__all__ = ["CertificateBuilder"]
