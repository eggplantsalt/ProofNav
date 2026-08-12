"""Deterministic M2 positive and refutation-cover certificate constructors."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256


def _group(snapshot):
    obligations = {}
    by_hypothesis = {key: [] for key in snapshot["hypothesis_ids"]}
    for obligation in snapshot["obligations"]:
        obligations[obligation["obligation_id"]] = obligation
        by_hypothesis[obligation["hypothesis_id"]].append(obligation)
    for values in by_hypothesis.values():
        values.sort(key=lambda item: item["obligation_id"])
    evidence = {
        item["evidence_id"]: item for item in snapshot["active_evidence"]
    }
    return obligations, by_hypothesis, evidence


def _feedback(snapshot, reason_codes, missing=None, uncovered=None):
    return {
        "reason_codes": sorted(set(reason_codes)),
        "missing_obligation_ids": sorted(set(missing or [])),
        "uncovered_hypothesis_ids": sorted(set(uncovered or [])),
        "frontier_witnesses": copy.deepcopy(snapshot["frontier_witnesses"]),
        "recommended_action": "CONTINUE_EVIDENCE_COLLECTION",
    }


def _outcome(snapshot, certificate=None, reason_codes=None, missing=None, uncovered=None):
    return {
        "status": "CERTIFICATE" if certificate is not None else "UNRESOLVED",
        "certificate": certificate,
        "proof_state_digest": snapshot["proof_state_digest"],
        "feedback": _feedback(snapshot, reason_codes or [], missing, uncovered),
    }


def _finalize(snapshot, certificate_type, requested_verdict, evidence_ids,
              obligation_ids, payload):
    evidence_by_id = {
        item["evidence_id"]: item for item in snapshot["active_evidence"]
    }
    selected = [evidence_by_id[key] for key in sorted(evidence_ids)]
    risk_claim = copy.deepcopy(snapshot["risk_claims"][requested_verdict])
    certificate = {
        "schema_version": SCHEMA_VERSIONS["m2_certificate"],
        "certificate_type": certificate_type,
        "requested_verdict": requested_verdict,
        "episode_id": snapshot["episode_id"],
        "scope_contract_id": snapshot["scope_contract_id"],
        "scope_version": snapshot["scope_version"],
        "scope_digest": snapshot["scope_digest"],
        "proof_state_version": snapshot["state_version"],
        "proof_state_digest": snapshot["proof_state_digest"],
        "ledger_digest": snapshot["ledger_digest"],
        "budget_snapshot": copy.deepcopy(snapshot["budget_status"]),
        "cost_snapshot": copy.deepcopy(snapshot["cost_ledger"]),
        "risk_claim": risk_claim,
        "evidence_ids": sorted(evidence_ids),
        "obligation_ids": sorted(obligation_ids),
        "payload": copy.deepcopy(payload),
        "provenance": {
            "builder_version": "proofnav.certificate-builder.v1",
            "observation_event_ids": sorted({
                item["source_event_id"] for item in selected
            }),
            "evidence_adapter_versions": sorted({
                item["adapter_version"] for item in selected
            }),
            "ledger_event_count": snapshot["ledger_event_count"],
        },
    }
    certificate["certificate_digest"] = canonical_sha256(certificate)
    certificate["certificate_id"] = "cert-" + certificate["certificate_digest"][:20]
    return certificate


class CertificateBuilder(object):
    """Pure constructor: it never closes an incomplete or conflicted proof."""

    def build(self, state, requested_verdict):
        snapshot = state.snapshot()
        if requested_verdict == "FOUND":
            return self._positive(snapshot)
        if requested_verdict == "NOT_FOUND":
            return self._refutation(snapshot)
        return _outcome(snapshot, reason_codes=["VERDICT_TYPE_INVALID"])

    def _preconditions(self, snapshot, verdict):
        reasons = []
        if not snapshot["budget_status"]["within_budget"]:
            reasons.append("BUDGET_EXHAUSTED")
        if verdict not in snapshot["risk_claims"]:
            reasons.append("RISK_CLAIM_MISSING")
        else:
            claim = snapshot["risk_claims"][verdict]
            if claim["upper_bound"] > claim["budget"]:
                reasons.append("RISK_BUDGET_EXCEEDED")
        if any(item["status"] == "CONFLICTED" for item in snapshot["obligations"]):
            reasons.append("CONFLICTED_EVIDENCE")
        return reasons

    def _positive(self, snapshot):
        reasons = self._preconditions(snapshot, "FOUND")
        _, by_hypothesis, evidence = _group(snapshot)
        candidates = []
        missing = []
        for hypothesis_id in snapshot["hypothesis_ids"]:
            necessary = [item for item in by_hypothesis[hypothesis_id] if item["necessary"]]
            open_ids = [
                item["obligation_id"] for item in necessary
                if item["status"] != "SATISFIED"
            ]
            if open_ids:
                missing.extend(open_ids)
            else:
                candidates.append((hypothesis_id, necessary))
        if not candidates:
            reasons.append("POSITIVE_PATH_INCOMPLETE")
        if reasons:
            return _outcome(snapshot, reason_codes=reasons, missing=missing)
        hypothesis_id, necessary = candidates[0]
        true_path = []
        all_evidence_ids = []
        for obligation in necessary:
            evidence_ids = obligation["support_evidence_ids"]
            all_evidence_ids.extend(evidence_ids)
            true_path.append({
                "obligation_id": obligation["obligation_id"],
                "predicate_id": obligation["predicate_id"],
                "evidence_ids": sorted(evidence_ids),
            })
        binding_evidence = evidence[sorted(all_evidence_ids)[0]]
        payload = {
            "hypothesis_id": hypothesis_id,
            "entity_binding": {
                "unit_id": binding_evidence["unit_id"],
                "binding_event_id": binding_evidence["source_event_id"],
            },
            "true_path": true_path,
            "unresolved_obligation_ids": [],
        }
        certificate = _finalize(
            snapshot, "positive", "FOUND", all_evidence_ids,
            [item["obligation_id"] for item in necessary], payload,
        )
        return _outcome(snapshot, certificate=certificate)

    def _refutation(self, snapshot):
        reasons = self._preconditions(snapshot, "NOT_FOUND")
        _, by_hypothesis, _ = _group(snapshot)
        if not snapshot["scope_closed"]:
            reasons.append("SCOPE_NOT_CLOSED")
        if snapshot["frontier_witnesses"]:
            reasons.append("FRONTIER_OPEN")
        uncovered = []
        cover = []
        all_evidence_ids = []
        all_obligation_ids = []
        for hypothesis_id in snapshot["hypothesis_ids"]:
            refuted = [
                item for item in by_hypothesis[hypothesis_id]
                if item["necessary"] and item["status"] == "REFUTED"
            ]
            if not refuted:
                uncovered.append(hypothesis_id)
                continue
            selected = refuted[0]
            evidence_ids = selected["refutation_evidence_ids"]
            all_evidence_ids.extend(evidence_ids)
            all_obligation_ids.append(selected["obligation_id"])
            cover.append({
                "hypothesis_id": hypothesis_id,
                "obligation_id": selected["obligation_id"],
                "predicate_id": selected["predicate_id"],
                "evidence_ids": sorted(evidence_ids),
            })
        if uncovered:
            reasons.append("REFUTATION_COVER_INCOMPLETE")
        if reasons:
            return _outcome(snapshot, reason_codes=reasons, uncovered=uncovered)
        payload = {
            "hypothesis_index": sorted(snapshot["hypothesis_ids"]),
            "refutation_cover": cover,
            "uncovered_hypothesis_ids": [],
            "frontier_unresolved": [],
        }
        certificate = _finalize(
            snapshot, "refutation_cover", "NOT_FOUND", all_evidence_ids,
            all_obligation_ids, payload,
        )
        return _outcome(snapshot, certificate=certificate)
