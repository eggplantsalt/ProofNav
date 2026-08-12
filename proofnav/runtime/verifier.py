"""Independent online semantic verifier for M2 certificates."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256


_CERTIFICATE_FIELDS = {
    "schema_version", "certificate_id", "certificate_digest",
    "certificate_type", "requested_verdict", "episode_id",
    "scope_contract_id", "scope_version", "scope_digest",
    "proof_state_version", "proof_state_digest", "ledger_digest",
    "budget_snapshot", "cost_snapshot", "risk_claim", "evidence_ids", "obligation_ids",
    "payload", "provenance",
}
_CONTROLLED_TOKENS = (
    "oracle", "fixture", "ground_truth", "evaluator", "controlled_truth",
)


def _duplicates(values):
    return len(values) != len(set(values))


def _safe_list(value):
    return value if isinstance(value, list) else []


def _report(snapshot, status, requested_verdict, reasons, missing=None,
            uncovered=None, certificate_digest=None):
    reasons = sorted(set(reasons))
    missing = sorted(set(missing or []))
    uncovered = sorted(set(uncovered or []))
    return {
        "schema_version": SCHEMA_VERSIONS["online_verification"],
        "status": status,
        "accepted": status == "ACCEPT",
        "requested_verdict": requested_verdict,
        "reason_codes": reasons,
        "missing_obligation_ids": missing,
        "uncovered_hypothesis_ids": uncovered,
        "frontier_witnesses": copy.deepcopy(snapshot["frontier_witnesses"]),
        "scope_digest": snapshot["scope_digest"],
        "proof_state_digest": snapshot["proof_state_digest"],
        "certificate_digest": certificate_digest,
        "structured_feedback": {
            "recommended_action": (
                "FINALIZE" if status == "ACCEPT"
                else "CONTINUE_EVIDENCE_COLLECTION"
            ),
            "reason_codes": reasons,
            "missing_obligation_ids": missing,
            "uncovered_hypothesis_ids": uncovered,
            "frontier_witness_ids": [
                item["frontier_id"] for item in snapshot["frontier_witnesses"]
            ],
        },
    }


def _group(snapshot):
    obligations = {
        item["obligation_id"]: item for item in snapshot["obligations"]
    }
    by_hypothesis = {key: [] for key in snapshot["hypothesis_ids"]}
    for item in snapshot["obligations"]:
        by_hypothesis[item["hypothesis_id"]].append(item)
    for values in by_hypothesis.values():
        values.sort(key=lambda item: item["obligation_id"])
    evidence = {
        item["evidence_id"]: item for item in snapshot["active_evidence"]
    }
    return obligations, by_hypothesis, evidence


class _OnlineVerifierCore(object):
    """Shared verifier semantics; replay opt-in is only instantiated offline."""

    def __init__(self, allow_controlled=False):
        self._allow_controlled = bool(allow_controlled)

    def verify(self, state, certificate):
        snapshot = state.snapshot()
        try:
            return self._verify_impl(state, certificate, snapshot)
        except (KeyError, TypeError, ValueError, IndexError):
            # A verifier is a trust boundary.  Malformed external certificates
            # must become a stable rejection, never an exception that lets a
            # caller skip the gate.
            return _report(
                snapshot, "REJECT", None, ["CERTIFICATE_SCHEMA_INVALID"],
            )

    def _verify_impl(self, state, certificate, snapshot):
        if certificate is None:
            missing = [
                item["obligation_id"] for item in snapshot["obligations"]
                if item["necessary"] and item["status"] != "SATISFIED"
            ]
            return _report(
                snapshot, "DEFER", None, ["CERTIFICATE_ABSENT"], missing,
                snapshot["hypothesis_ids"],
            )
        if not isinstance(certificate, dict):
            return _report(snapshot, "REJECT", None, ["CERTIFICATE_TYPE_INVALID"])
        requested = certificate.get("requested_verdict")
        reasons = []
        missing = []
        uncovered = []
        if set(certificate) != _CERTIFICATE_FIELDS:
            reasons.append("CERTIFICATE_SCHEMA_INVALID")
        if certificate.get("schema_version") != SCHEMA_VERSIONS["m2_certificate"]:
            reasons.append("CERTIFICATE_VERSION_INVALID")
        if requested not in ("FOUND", "NOT_FOUND"):
            reasons.append("VERDICT_TYPE_INVALID")
        expected_type = {
            "FOUND": "positive", "NOT_FOUND": "refutation_cover",
        }.get(requested)
        if certificate.get("certificate_type") != expected_type:
            reasons.append("CERTIFICATE_VERDICT_MISMATCH")
        digest_payload = copy.deepcopy(certificate)
        digest_payload.pop("certificate_id", None)
        claimed_digest = digest_payload.pop("certificate_digest", None)
        calculated_digest = canonical_sha256(digest_payload)
        if claimed_digest != calculated_digest:
            reasons.append("CERTIFICATE_DIGEST_INVALID")
        if certificate.get("certificate_id") != "cert-" + calculated_digest[:20]:
            reasons.append("CERTIFICATE_ID_INVALID")
        identity_checks = {
            "episode_id": snapshot["episode_id"],
            "scope_contract_id": snapshot["scope_contract_id"],
            "scope_version": snapshot["scope_version"],
            "scope_digest": snapshot["scope_digest"],
        }
        for key, expected in identity_checks.items():
            if certificate.get(key) != expected:
                reasons.append("SCOPE_%s_MISMATCH" % key.upper())
        state_checks = {
            "proof_state_version": snapshot["state_version"],
            "proof_state_digest": snapshot["proof_state_digest"],
            "ledger_digest": snapshot["ledger_digest"],
        }
        for key, expected in state_checks.items():
            if certificate.get(key) != expected:
                reasons.append("STALE_%s" % key.upper())
        if certificate.get("budget_snapshot") != snapshot["budget_status"]:
            reasons.append("BUDGET_SNAPSHOT_MISMATCH")
        if certificate.get("cost_snapshot") != snapshot["cost_ledger"]:
            reasons.append("COST_SNAPSHOT_MISMATCH")
        if not snapshot["budget_status"]["within_budget"]:
            reasons.append("BUDGET_EXHAUSTED")
        if any(item["status"] == "CONFLICTED" for item in snapshot["obligations"]):
            reasons.append("CONFLICTED_EVIDENCE")

        obligations, by_hypothesis, evidence = _group(snapshot)
        evidence_ids = certificate.get("evidence_ids")
        obligation_ids = certificate.get("obligation_ids")
        if not isinstance(evidence_ids, list) or any(not isinstance(x, str) for x in _safe_list(evidence_ids)):
            reasons.append("CERTIFICATE_EVIDENCE_IDS_INVALID")
            evidence_ids = []
        if not isinstance(obligation_ids, list) or any(not isinstance(x, str) for x in _safe_list(obligation_ids)):
            reasons.append("CERTIFICATE_OBLIGATION_IDS_INVALID")
            obligation_ids = []
        if _duplicates(evidence_ids):
            reasons.append("DUPLICATE_EVIDENCE_COVERAGE")
        if _duplicates(obligation_ids):
            reasons.append("DUPLICATE_OBLIGATION_COVERAGE")
        selected_evidence = []
        for evidence_id in evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                reasons.append("EVIDENCE_MISSING_OR_REVOKED")
            else:
                selected_evidence.append(item)
                if item["source_event_id"] not in snapshot["observation_event_ids"]:
                    reasons.append("EVIDENCE_PROVENANCE_INVALID")
        for obligation_id in obligation_ids:
            if obligation_id not in obligations:
                reasons.append("OBLIGATION_UNKNOWN")

        if not self._allow_controlled:
            for item in selected_evidence:
                source_text = " ".join((
                    item["adapter_version"], item["dependency_group"],
                    item["audit_trail"]["producer"],
                    item["audit_trail"]["source_field"],
                )).lower()
                if any(token in source_text for token in _CONTROLLED_TOKENS):
                    reasons.append("CONTROLLED_SOURCE_FORBIDDEN")
                reasons.append("EVIDENCE_ADAPTER_NOT_REGISTERED")

        provenance = certificate.get("provenance")
        provenance_fields = {
            "builder_version", "observation_event_ids",
            "evidence_adapter_versions", "ledger_event_count",
        }
        if not isinstance(provenance, dict) or set(provenance) != provenance_fields:
            reasons.append("CERTIFICATE_PROVENANCE_INVALID")
        else:
            expected_events = sorted({item["source_event_id"] for item in selected_evidence})
            expected_adapters = sorted({item["adapter_version"] for item in selected_evidence})
            if provenance["builder_version"] != "proofnav.certificate-builder.v1":
                reasons.append("CERTIFICATE_BUILDER_INVALID")
            if provenance["observation_event_ids"] != expected_events:
                reasons.append("CERTIFICATE_PROVENANCE_EVENT_MISMATCH")
            if provenance["evidence_adapter_versions"] != expected_adapters:
                reasons.append("CERTIFICATE_PROVENANCE_ADAPTER_MISMATCH")
            if provenance["ledger_event_count"] != snapshot["ledger_event_count"]:
                reasons.append("STALE_LEDGER_EVENT_COUNT")

        risk = certificate.get("risk_claim")
        expected_risk = snapshot["risk_claims"].get(requested)
        if risk != expected_risk:
            reasons.append("RISK_CLAIM_MISMATCH")
        elif risk is not None and risk["upper_bound"] > risk["budget"]:
            reasons.append("RISK_BUDGET_EXCEEDED")

        payload = certificate.get("payload")
        if requested == "FOUND":
            semantic = self._verify_positive(
                snapshot, payload, evidence_ids, obligation_ids,
                by_hypothesis, evidence,
            )
        elif requested == "NOT_FOUND":
            semantic = self._verify_refutation(
                snapshot, payload, evidence_ids, obligation_ids,
                by_hypothesis, evidence,
            )
        else:
            semantic = ([], [], [])
        reasons.extend(semantic[0])
        missing.extend(semantic[1])
        uncovered.extend(semantic[2])
        return _report(
            snapshot, "ACCEPT" if not reasons else "REJECT", requested,
            reasons, missing, uncovered, certificate.get("certificate_digest"),
        )

    def _verify_positive(self, snapshot, payload, certificate_evidence_ids,
                         certificate_obligation_ids, by_hypothesis, evidence):
        reasons, missing = [], []
        fields = {
            "hypothesis_id", "entity_binding", "true_path",
            "unresolved_obligation_ids",
        }
        if not isinstance(payload, dict) or set(payload) != fields:
            return ["POSITIVE_PAYLOAD_INVALID"], [], []
        hypothesis_id = payload["hypothesis_id"]
        if hypothesis_id not in by_hypothesis:
            return ["POSITIVE_HYPOTHESIS_OUT_OF_SCOPE"], [], []
        necessary = [item for item in by_hypothesis[hypothesis_id] if item["necessary"]]
        expected_ids = sorted(item["obligation_id"] for item in necessary)
        if sorted(certificate_obligation_ids) != expected_ids:
            reasons.append("POSITIVE_OBLIGATION_COVERAGE_INVALID")
        path = payload["true_path"]
        if not isinstance(path, list):
            return reasons + ["TRUE_PATH_INVALID"], [], []
        path_by_obligation = {}
        used_evidence = []
        for index, item in enumerate(path):
            if not isinstance(item, dict) or set(item) != {"obligation_id", "predicate_id", "evidence_ids"}:
                reasons.append("TRUE_PATH_ITEM_INVALID")
                continue
            obligation_id = item["obligation_id"]
            if obligation_id in path_by_obligation:
                reasons.append("DUPLICATE_OBLIGATION_COVERAGE")
            path_by_obligation[obligation_id] = item
            resolution = next((x for x in necessary if x["obligation_id"] == obligation_id), None)
            if resolution is None:
                reasons.append("TRUE_PATH_OBLIGATION_INVALID")
                continue
            if item["predicate_id"] != resolution["predicate_id"]:
                reasons.append("TRUE_PATH_PREDICATE_MISMATCH")
            if resolution["status"] != "SATISFIED":
                reasons.append("POSITIVE_OBLIGATION_NOT_SATISFIED")
                missing.append(obligation_id)
            if sorted(item["evidence_ids"]) != resolution["support_evidence_ids"]:
                reasons.append("TRUE_PATH_EVIDENCE_MISMATCH")
            used_evidence.extend(item["evidence_ids"])
            for evidence_id in item["evidence_ids"]:
                if evidence_id in evidence and evidence[evidence_id]["claim"] != "SUPPORTS":
                    reasons.append("TRUE_PATH_POLARITY_INVALID")
        if sorted(path_by_obligation) != expected_ids:
            reasons.append("TRUE_PATH_INCOMPLETE")
            missing.extend(set(expected_ids) - set(path_by_obligation))
        if sorted(used_evidence) != sorted(certificate_evidence_ids):
            reasons.append("CERTIFICATE_EVIDENCE_COVERAGE_INVALID")
        if payload["unresolved_obligation_ids"]:
            reasons.append("POSITIVE_UNRESOLVED_NONEMPTY")
        binding = payload["entity_binding"]
        if not isinstance(binding, dict) or set(binding) != {"unit_id", "binding_event_id"}:
            reasons.append("ENTITY_BINDING_INVALID")
        elif not any(
                item.get("unit_id") == binding["unit_id"]
                and item.get("source_event_id") == binding["binding_event_id"]
                for item in (evidence.get(key, {}) for key in certificate_evidence_ids)):
            reasons.append("ENTITY_BINDING_UNPROVEN")
        return reasons, missing, []

    def _verify_refutation(self, snapshot, payload, certificate_evidence_ids,
                           certificate_obligation_ids, by_hypothesis, evidence):
        reasons, uncovered = [], []
        fields = {
            "hypothesis_index", "refutation_cover",
            "uncovered_hypothesis_ids", "frontier_unresolved",
        }
        if not isinstance(payload, dict) or set(payload) != fields:
            return ["REFUTATION_PAYLOAD_INVALID"], [], []
        if payload["hypothesis_index"] != sorted(snapshot["hypothesis_ids"]):
            reasons.append("HYPOTHESIS_INDEX_MISMATCH")
        if not snapshot["scope_closed"]:
            reasons.append("SCOPE_NOT_CLOSED")
        if snapshot["frontier_witnesses"] or payload["frontier_unresolved"]:
            reasons.append("FRONTIER_OPEN")
        if payload["uncovered_hypothesis_ids"]:
            reasons.append("UNCOVERED_HYPOTHESES_NONEMPTY")
        cover = payload["refutation_cover"]
        if not isinstance(cover, list):
            return reasons + ["REFUTATION_COVER_INVALID"], [], snapshot["hypothesis_ids"]
        cover_by_hypothesis = {}
        used_evidence = []
        used_obligations = []
        for item in cover:
            if not isinstance(item, dict) or set(item) != {
                    "hypothesis_id", "obligation_id", "predicate_id", "evidence_ids"}:
                reasons.append("REFUTATION_COVER_ITEM_INVALID")
                continue
            hypothesis_id = item["hypothesis_id"]
            if hypothesis_id in cover_by_hypothesis:
                reasons.append("DUPLICATE_HYPOTHESIS_COVERAGE")
            cover_by_hypothesis[hypothesis_id] = item
            candidates = by_hypothesis.get(hypothesis_id, [])
            resolution = next(
                (x for x in candidates if x["obligation_id"] == item["obligation_id"]),
                None,
            )
            if resolution is None or not resolution["necessary"]:
                reasons.append("REFUTATION_OBLIGATION_INVALID")
                continue
            if item["predicate_id"] != resolution["predicate_id"]:
                reasons.append("REFUTATION_PREDICATE_MISMATCH")
            if resolution["status"] != "REFUTED":
                reasons.append("REFUTATION_OBLIGATION_NOT_REFUTED")
            if sorted(item["evidence_ids"]) != resolution["refutation_evidence_ids"]:
                reasons.append("REFUTATION_EVIDENCE_MISMATCH")
            used_evidence.extend(item["evidence_ids"])
            used_obligations.append(item["obligation_id"])
            for evidence_id in item["evidence_ids"]:
                if evidence_id in evidence and evidence[evidence_id]["claim"] != "REFUTES":
                    reasons.append("REFUTATION_POLARITY_INVALID")
        expected_hypotheses = set(snapshot["hypothesis_ids"])
        uncovered.extend(expected_hypotheses - set(cover_by_hypothesis))
        if uncovered or set(cover_by_hypothesis) != expected_hypotheses:
            reasons.append("REFUTATION_COVER_INCOMPLETE")
        if sorted(used_evidence) != sorted(certificate_evidence_ids):
            reasons.append("CERTIFICATE_EVIDENCE_COVERAGE_INVALID")
        if sorted(used_obligations) != sorted(certificate_obligation_ids):
            reasons.append("CERTIFICATE_OBLIGATION_COVERAGE_INVALID")
        return reasons, [], uncovered


class OnlineVerifier(_OnlineVerifierCore):
    """Production verifier: controlled/oracle sources are always rejected."""

    def __init__(self):
        super().__init__(allow_controlled=False)
