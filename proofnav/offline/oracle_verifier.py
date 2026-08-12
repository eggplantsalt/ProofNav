"""Independent hidden-truth verifier; its output never enters runtime control."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS
from proofnav.offline.oracle_evidence import validate_controlled_truth


class OracleOfflineVerifier(object):
    """Audit terminal output against hidden truth without calling online logic."""

    def verify(self, truth, terminal_decision, certificate):
        truth = copy.deepcopy(truth)
        validate_controlled_truth(truth)
        terminal = copy.deepcopy(terminal_decision)
        cert = copy.deepcopy(certificate)
        runtime_verdict = terminal.get("semantic_verdict")
        online = terminal.get("online_verification", {})
        online_status = online.get("status")
        reasons = []
        outcome = "UNRESOLVED"

        wrong_scope = bool(cert) and (
            cert.get("scope_contract_id") != truth["scope_contract_id"]
            or cert.get("scope_version") != truth["scope_version"]
            or cert.get("scope_digest") != truth["scope_digest"]
        )
        if wrong_scope:
            outcome = "WRONG_SCOPE"
            reasons.append("OFFLINE_SCOPE_MISMATCH")
        elif terminal.get("certificate_accepted"):
            factually_correct = runtime_verdict == truth["semantic_truth"]
            if factually_correct and runtime_verdict == "FOUND":
                payload = cert.get("payload", {}) if isinstance(cert, dict) else {}
                factually_correct = (
                    payload.get("hypothesis_id") in truth["supported_hypothesis_ids"]
                )
            if factually_correct and runtime_verdict == "NOT_FOUND":
                payload = cert.get("payload", {}) if isinstance(cert, dict) else {}
                covered = {
                    item.get("hypothesis_id")
                    for item in payload.get("refutation_cover", [])
                    if isinstance(item, dict)
                }
                factually_correct = covered == set(truth["refuted_hypothesis_ids"])
            if factually_correct:
                outcome = "TRUE_ACCEPT"
            else:
                outcome = "FALSE_ACCEPT"
                reasons.append("OFFLINE_FACTUAL_MISMATCH")
        elif online_status == "REJECT" and isinstance(cert, dict):
            claim_matches = cert.get("requested_verdict") == truth["semantic_truth"]
            if claim_matches and cert.get("requested_verdict") == "FOUND":
                claim_matches = cert.get("payload", {}).get("hypothesis_id") in truth["supported_hypothesis_ids"]
            if claim_matches:
                outcome = "FALSE_REJECT"
                reasons.append("OFFLINE_REJECTED_TRUE_CLAIM")
        conflict = outcome in ("FALSE_ACCEPT", "FALSE_REJECT", "WRONG_SCOPE")
        return {
            "schema_version": SCHEMA_VERSIONS["offline_verification"],
            "outcome": outcome,
            "online_offline_conflict": conflict,
            "audit_disposition": "UNRESOLVED" if conflict else runtime_verdict,
            "certificate_accepted_for_audit": outcome == "TRUE_ACCEPT",
            "truth_verdict": truth["semantic_truth"],
            "runtime_verdict": runtime_verdict,
            "scope_contract_id": truth["scope_contract_id"],
            "reason_codes": reasons,
            "feedback_to_runtime": None,
        }
