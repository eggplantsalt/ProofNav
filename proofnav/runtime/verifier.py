"""M2.1 online verifier over raw, causal transition bundles.

The verifier never accepts a caller's cached proof snapshot as authority.  It
validates the bundle hash, folds every raw transition through
``semantics.recompute_view``, and then checks the certificate against that
independently derived view.
"""

import copy

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.runtime.semantics import (
    RESIDUAL_HYPOTHESIS_KINDS, recompute_view, registered_admission_profile,
)


_BUNDLE_FIELDS = {
    "schema_version", "scope", "template", "admission_profile", "risk_claims",
    "transitions", "state", "bundle_digest",
}
_BASE_BUNDLE_FIELDS = (
    "schema_version", "scope", "template", "admission_profile", "risk_claims",
    "transitions",
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
_PROVENANCE_FIELDS = {
    "builder_version", "admission_profile_id", "observation_event_ids",
    "evidence_adapter_versions", "ledger_event_count",
}
_COVERAGE_FIELDS = {
    "hypothesis_id", "hypothesis_kind", "binding", "obligation_id",
    "predicate_id", "predicate_kind", "evidence_ids",
}


def _copy(value):
    return copy.deepcopy(value)


def _duplicates(values):
    return len(values) != len(set(values))


def _string_list(value):
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and item for item in value)
        and not _duplicates(value)
    )


def _certificate_identity(certificate):
    claimed_id = certificate.get("certificate_id") if isinstance(certificate, dict) else None
    claimed_digest = certificate.get("certificate_digest") if isinstance(certificate, dict) else None
    calculated = None
    if isinstance(certificate, dict):
        try:
            body = _copy(certificate)
            body.pop("certificate_id", None)
            body.pop("certificate_digest", None)
            calculated = canonical_sha256(body)
        except (TypeError, ValueError):
            calculated = None
    return claimed_id, claimed_digest, calculated


def _empty_view():
    return {
        "scope_digest": None,
        "template_digest": None,
        "universe_digest": None,
        "binding_digest": None,
        "decision_cut": None,
        "transition_tip": None,
        "proof_state_digest": None,
        "topology": {"frontier_viewpoint_ids": []},
    }


def _report(snapshot, status, requested_verdict, reasons, missing=None,
            uncovered=None, certificate=None):
    reasons = sorted(set(reasons))
    missing = sorted(set(missing or []))
    uncovered = sorted(set(uncovered or []))
    claimed_id, claimed_digest, calculated_digest = _certificate_identity(certificate)
    frontier = sorted(snapshot.get("topology", {}).get("frontier_viewpoint_ids", []))
    return {
        "schema_version": SCHEMA_VERSIONS["online_verification"],
        "status": status,
        "accepted": status == "ACCEPT",
        "requested_verdict": requested_verdict,
        "reason_codes": reasons,
        "missing_obligation_ids": missing,
        "uncovered_hypothesis_ids": uncovered,
        "frontier_viewpoint_ids": frontier,
        "scope_digest": snapshot.get("scope_digest"),
        "template_digest": snapshot.get("template_digest"),
        "universe_digest": snapshot.get("universe_digest"),
        "binding_digest": snapshot.get("binding_digest"),
        "decision_cut": _copy(snapshot.get("decision_cut")),
        "transition_tip": snapshot.get("transition_tip"),
        "proof_state_digest": snapshot.get("proof_state_digest"),
        "certificate_id": claimed_id,
        "certificate_digest": claimed_digest,
        "calculated_certificate_digest": calculated_digest,
        "structured_feedback": {
            "recommended_action": (
                "FINALIZE" if status == "ACCEPT"
                else "CONTINUE_EVIDENCE_COLLECTION"
            ),
            "reason_codes": reasons,
            "missing_obligation_ids": missing,
            "uncovered_hypothesis_ids": uncovered,
            "frontier_viewpoint_ids": frontier,
        },
    }


def _source_bundle(source):
    if hasattr(source, "audit_bundle") and callable(source.audit_bundle):
        return source.audit_bundle()
    if isinstance(source, dict):
        return _copy(source)
    raise ContractViolation(
        "AUDIT_BUNDLE_REQUIRED", "$", "online verification needs raw transitions",
    )


def _canonical_view(source, allow_controlled=False, allow_m3=False):
    """Validate and fold an audit bundle; return bundle, view, soft reasons."""

    bundle = _source_bundle(source)
    if not isinstance(bundle, dict) or set(bundle) != _BUNDLE_FIELDS:
        raise ContractViolation(
            "AUDIT_BUNDLE_SCHEMA", "$", "expected exact decision-audit-bundle fields",
        )
    if bundle["schema_version"] != SCHEMA_VERSIONS["audit_bundle"]:
        raise ContractViolation(
            "AUDIT_BUNDLE_VERSION", "$.schema_version", "unsupported audit bundle",
        )
    reasons = []
    digest_body = _copy(bundle)
    claimed_digest = digest_body.pop("bundle_digest")
    calculated_digest = canonical_sha256(digest_body)
    if claimed_digest != calculated_digest:
        reasons.append("AUDIT_BUNDLE_DIGEST_INVALID")
    base = {key: _copy(bundle[key]) for key in _BASE_BUNDLE_FIELDS}
    profile = base.get("admission_profile")
    scope = base.get("scope")
    if not isinstance(profile, dict) or not isinstance(scope, dict):
        raise ContractViolation(
            "ADMISSION_PROFILE_NOT_CODE_OWNED", "$.admission_profile",
            "registered M2.1 profile required",
        )
    if allow_controlled and allow_m3:
        raise ContractViolation(
            "ADMISSION_PROFILE_MODE", "$.admission_profile",
            "one verifier cannot authorize two non-default profiles",
        )
    if (not allow_controlled
            and profile == registered_admission_profile(True)):
        raise ContractViolation(
            "CONTROLLED_SOURCE_FORBIDDEN", "$.admission_profile",
            "controlled replay cannot enter production verification",
        )
    if (not allow_m3
            and profile == registered_admission_profile(m3=True)):
        raise ContractViolation(
            "M3_SOURCE_FORBIDDEN", "$.admission_profile",
            "the explicit M3 verifier is required",
        )
    expected_profile = registered_admission_profile(
        controlled=allow_controlled, m3=allow_m3,
    )
    if profile != expected_profile:
        raise ContractViolation(
            "ADMISSION_PROFILE_NOT_CODE_OWNED", "$.admission_profile",
            "profile must exactly match the verifier class",
        )
    snapshot = recompute_view(
        base, allow_controlled=allow_controlled, allow_m3=allow_m3,
    )
    if allow_m3:
        from proofnav.calibration.registry import (  # pylint: disable=import-outside-toplevel
            is_registered_observation_digest,
        )
        prefix = "proofnav.calibration-artifact.v1:"
        version = scope.get("calibration_version", "")
        artifact_digest = version[len(prefix):] if version.startswith(prefix) else ""
        if (not artifact_digest or any(
                transition["event_type"] == "OBSERVATION"
                and not is_registered_observation_digest(
                    artifact_digest, canonical_sha256(transition["payload"]),
                )
                for transition in base["transitions"])):
            reasons.append("M3_OBSERVATION_PREFIX_NOT_REGISTERED")
    if bundle["state"] != snapshot:
        reasons.append("AUDIT_STATE_MISMATCH")
    return bundle, snapshot, reasons


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


def _m3_profile(snapshot):
    return (
        snapshot.get("audit_trail", {}).get("admission_profile_id")
        == "proofnav.admission.m3-entity-support.v1"
    )


def _wrapper_matches(wrapper, hypothesis, obligation, polarity, snapshot):
    evidence = wrapper.get("evidence", {})
    cut = snapshot["decision_cut"]
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
        and isinstance(evidence.get("event_seq"), int)
        and evidence["event_seq"] <= cut["max_observation_event_seq"]
        and isinstance(evidence.get("step"), int)
        and evidence["step"] <= cut["max_step"]
        and evidence.get("source_event_id")
        in snapshot["topology"]["observation_event_ids"]
    )


def _coverage_matches(item, hypothesis, obligation):
    return (
        isinstance(item, dict)
        and set(item) == _COVERAGE_FIELDS
        and item.get("hypothesis_id") == hypothesis["hypothesis_id"]
        and item.get("hypothesis_kind") == hypothesis["hypothesis_kind"]
        and item.get("binding") == hypothesis["binding"]
        and item.get("obligation_id") == obligation["obligation_id"]
        and item.get("predicate_id") == obligation["predicate_id"]
        and item.get("predicate_kind") == obligation["predicate_kind"]
        and _string_list(item.get("evidence_ids"))
    )


class _OnlineVerifierCore(object):
    """Raw-transition verifier; controlled replay is an offline-only subclass."""

    def __init__(self, allow_controlled=False, allow_m3=False):
        self._allow_controlled = bool(allow_controlled)
        self._allow_m3 = bool(allow_m3)
        if self._allow_controlled and self._allow_m3:
            raise ValueError("controlled and M3 verifier modes are disjoint")

    def verify(self, state_or_bundle, certificate):
        try:
            bundle, snapshot, bundle_reasons = _canonical_view(
                state_or_bundle, self._allow_controlled, self._allow_m3,
            )
        except ContractViolation as error:
            return _report(
                _empty_view(), "REJECT", (
                    certificate.get("requested_verdict")
                    if isinstance(certificate, dict) else None
                ), [error.code], certificate=certificate,
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return _report(
                _empty_view(), "REJECT", None, ["AUDIT_BUNDLE_INVALID"],
                certificate=certificate,
            )
        if certificate is None:
            missing = [
                item["obligation_id"] for item in snapshot["obligations"]
                if item["necessary"] and item["status"] == "OPEN"
            ]
            reasons = bundle_reasons + ["CERTIFICATE_ABSENT"]
            return _report(
                snapshot, "REJECT" if bundle_reasons else "DEFER", None,
                reasons, missing=missing,
                uncovered=snapshot["hypothesis_ids"], certificate=None,
            )
        try:
            return self._verify_impl(bundle, snapshot, certificate, bundle_reasons)
        except ContractViolation as error:
            return _report(
                snapshot, "REJECT", (
                    certificate.get("requested_verdict")
                    if isinstance(certificate, dict) else None
                ), bundle_reasons + [error.code], certificate=certificate,
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return _report(
                snapshot, "REJECT", (
                    certificate.get("requested_verdict")
                    if isinstance(certificate, dict) else None
                ), bundle_reasons + ["CERTIFICATE_SCHEMA_INVALID"],
                certificate=certificate,
            )

    def _verify_impl(self, bundle, snapshot, certificate, initial_reasons):
        if not isinstance(certificate, dict):
            return _report(
                snapshot, "REJECT", None,
                initial_reasons + ["CERTIFICATE_TYPE_INVALID"],
                certificate=certificate,
            )
        requested = certificate.get("requested_verdict")
        reasons = list(initial_reasons)
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
        claimed_id, claimed_digest, calculated_digest = _certificate_identity(certificate)
        if calculated_digest is None or claimed_digest != calculated_digest:
            reasons.append("CERTIFICATE_DIGEST_INVALID")
        if calculated_digest is None or claimed_id != "cert-" + calculated_digest[:20]:
            reasons.append("CERTIFICATE_ID_INVALID")

        identity = {
            "episode_id": snapshot["episode_id"],
            "scope_contract_id": snapshot["scope_contract_id"],
            "scope_version": snapshot["scope_version"],
            "scope_digest": snapshot["scope_digest"],
            "template_id": snapshot["template_id"],
            "template_digest": snapshot["template_digest"],
            "proof_state_version": snapshot["state_version"],
            "decision_cut": snapshot["decision_cut"],
            "transition_tip": snapshot["transition_tip"],
            "proof_state_digest": snapshot["proof_state_digest"],
            "audit_bundle_digest": bundle["bundle_digest"],
            "universe_digest": snapshot["universe_digest"],
            "binding_digest": snapshot["binding_digest"],
            "closure_witness": snapshot["closure_witness"],
            "ledger_digest": snapshot["ledger_digest"],
        }
        reason_names = {
            "proof_state_version": "STALE_PROOF_STATE_VERSION",
            "decision_cut": "STALE_DECISION_CUT",
            "transition_tip": "STALE_TRANSITION_TIP",
            "proof_state_digest": "STALE_PROOF_STATE_DIGEST",
            "audit_bundle_digest": "STALE_AUDIT_BUNDLE_DIGEST",
            "universe_digest": "STALE_UNIVERSE_DIGEST",
            "binding_digest": "STALE_BINDING_DIGEST",
            "closure_witness": "CLOSURE_WITNESS_MISMATCH",
            "ledger_digest": "STALE_LEDGER_DIGEST",
        }
        for key, expected in identity.items():
            if certificate.get(key) != expected:
                reasons.append(reason_names.get(key, "%s_MISMATCH" % key.upper()))
        if certificate.get("budget_snapshot") != snapshot["budget_status"]:
            reasons.append("BUDGET_SNAPSHOT_MISMATCH")
        if certificate.get("cost_snapshot") != snapshot["cost_ledger"]:
            reasons.append("COST_SNAPSHOT_MISMATCH")
        if not snapshot["budget_status"]["within_budget"]:
            reasons.append("BUDGET_EXHAUSTED")
        if not _m3_profile(snapshot):
            expected_risk = snapshot["risk_claims"].get(requested)
            if certificate.get("risk_claim") != expected_risk:
                reasons.append("RISK_CLAIM_MISMATCH")
            elif (expected_risk is not None
                  and expected_risk["upper_bound"] > expected_risk["budget"]):
                reasons.append("RISK_BUDGET_EXCEEDED")

        hypotheses, obligations, by_hypothesis, evidence = _indexes(snapshot)
        lists = {}
        for field in ("hypothesis_ids", "obligation_ids", "evidence_ids"):
            value = certificate.get(field)
            if not _string_list(value):
                reasons.append("CERTIFICATE_%s_INVALID" % field.upper())
                value = []
            lists[field] = value
        selected = []
        for evidence_id in lists["evidence_ids"]:
            wrapper = evidence.get(evidence_id)
            if wrapper is None:
                reasons.append("EVIDENCE_MISSING_OR_REVOKED")
            else:
                selected.append(wrapper)
                raw = wrapper["evidence"]
                if (raw["event_seq"] > snapshot["decision_cut"]["max_observation_event_seq"]
                        or raw["step"] > snapshot["decision_cut"]["max_step"]):
                    reasons.append("FUTURE_EVIDENCE")
        if _m3_profile(snapshot):
            if requested != "FOUND":
                reasons.append("M3_NOT_FOUND_SEALED")
            else:
                try:
                    from proofnav.calibration.risk import (  # pylint: disable=import-outside-toplevel
                        compose_certificate_risk,
                    )
                    expected_risk = compose_certificate_risk(
                        selected, "FOUND", bundle["scope"],
                    )
                    if certificate.get("risk_claim") != expected_risk:
                        reasons.append("RISK_CLAIM_MISMATCH")
                    elif expected_risk["upper_bound"] > expected_risk["budget"]:
                        reasons.append("RISK_BUDGET_EXCEEDED")
                except ContractViolation as error:
                    reasons.append(error.code)
        for hypothesis_id in lists["hypothesis_ids"]:
            if hypothesis_id not in hypotheses:
                reasons.append("HYPOTHESIS_UNKNOWN")
        for obligation_id in lists["obligation_ids"]:
            if obligation_id not in obligations:
                reasons.append("OBLIGATION_UNKNOWN")

        provenance = certificate.get("provenance")
        if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_FIELDS:
            reasons.append("CERTIFICATE_PROVENANCE_INVALID")
        else:
            expected_events = sorted({
                item["evidence"]["source_event_id"] for item in selected
            })
            expected_adapters = sorted({
                item["evidence"]["adapter_version"] for item in selected
            })
            if provenance["builder_version"] != "proofnav.certificate-builder.v2":
                reasons.append("CERTIFICATE_BUILDER_INVALID")
            if provenance["admission_profile_id"] != snapshot["audit_trail"]["admission_profile_id"]:
                reasons.append("CERTIFICATE_ADMISSION_PROFILE_MISMATCH")
            if provenance["observation_event_ids"] != expected_events:
                reasons.append("CERTIFICATE_PROVENANCE_EVENT_MISMATCH")
            if provenance["evidence_adapter_versions"] != expected_adapters:
                reasons.append("CERTIFICATE_PROVENANCE_ADAPTER_MISMATCH")
            if provenance["ledger_event_count"] != snapshot["ledger_event_count"]:
                reasons.append("STALE_LEDGER_EVENT_COUNT")

        if requested == "FOUND":
            semantic = self._verify_positive(
                snapshot, certificate.get("payload"), lists,
                hypotheses, by_hypothesis, evidence,
            )
        elif requested == "NOT_FOUND":
            semantic = self._verify_refutation(
                snapshot, certificate.get("payload"), lists,
                hypotheses, by_hypothesis, evidence,
            )
        else:
            semantic = ([], [], [])
        reasons.extend(semantic[0])
        missing.extend(semantic[1])
        uncovered.extend(semantic[2])
        return _report(
            snapshot, "ACCEPT" if not reasons else "REJECT", requested,
            reasons, missing=missing, uncovered=uncovered,
            certificate=certificate,
        )

    @staticmethod
    def _verify_positive(snapshot, payload, lists, hypotheses,
                         by_hypothesis, evidence):
        reasons, missing = [], []
        if not isinstance(payload, dict) or set(payload) != {
                "hypothesis", "binding", "true_path", "unresolved_obligation_ids"}:
            return ["POSITIVE_PAYLOAD_INVALID"], [], []
        hypothesis_record = payload["hypothesis"]
        if not isinstance(hypothesis_record, dict):
            return ["POSITIVE_HYPOTHESIS_INVALID"], [], []
        hypothesis_id = hypothesis_record.get("hypothesis_id")
        hypothesis = hypotheses.get(hypothesis_id)
        if hypothesis is None or hypothesis_record != hypothesis:
            return ["POSITIVE_HYPOTHESIS_OUT_OF_SCOPE"], [], []
        if hypothesis["hypothesis_kind"] in RESIDUAL_HYPOTHESIS_KINDS:
            reasons.append("RESIDUAL_CANNOT_PROVE_FOUND")
        if lists["hypothesis_ids"] != [hypothesis_id]:
            reasons.append("POSITIVE_HYPOTHESIS_COVERAGE_INVALID")
        if payload["binding"] != hypothesis["binding"]:
            reasons.append("POSITIVE_BINDING_INCOHERENT")
        necessary = [
            item for item in by_hypothesis[hypothesis_id] if item["necessary"]
        ]
        expected_obligation_ids = sorted(item["obligation_id"] for item in necessary)
        if sorted(lists["obligation_ids"]) != expected_obligation_ids:
            reasons.append("POSITIVE_OBLIGATION_COVERAGE_INVALID")
        path = payload["true_path"]
        if not isinstance(path, list):
            return reasons + ["TRUE_PATH_INVALID"], [], []
        path_by_obligation = {}
        used_evidence = []
        for item in path:
            if not isinstance(item, dict):
                reasons.append("TRUE_PATH_ITEM_INVALID")
                continue
            obligation = next((
                value for value in necessary
                if value["obligation_id"] == item.get("obligation_id")
            ), None)
            if obligation is None or not _coverage_matches(item, hypothesis, obligation):
                reasons.append("TRUE_PATH_ITEM_INVALID")
                continue
            if obligation["obligation_id"] in path_by_obligation:
                reasons.append("DUPLICATE_OBLIGATION_COVERAGE")
            path_by_obligation[obligation["obligation_id"]] = item
            if obligation["status"] != "SATISFIED":
                reasons.append("POSITIVE_OBLIGATION_NOT_SATISFIED")
                missing.append(obligation["obligation_id"])
            if sorted(item["evidence_ids"]) != obligation["support_evidence_ids"]:
                reasons.append("TRUE_PATH_EVIDENCE_MISMATCH")
            used_evidence.extend(item["evidence_ids"])
            for evidence_id in item["evidence_ids"]:
                wrapper = evidence.get(evidence_id)
                if wrapper is None or not _wrapper_matches(
                        wrapper, hypothesis, obligation, "SUPPORTS", snapshot):
                    reasons.append("POSITIVE_BINDING_INCOHERENT")
        if sorted(path_by_obligation) != expected_obligation_ids:
            reasons.append("TRUE_PATH_INCOMPLETE")
            missing.extend(set(expected_obligation_ids) - set(path_by_obligation))
        if sorted(used_evidence) != sorted(lists["evidence_ids"]):
            reasons.append("CERTIFICATE_EVIDENCE_COVERAGE_INVALID")
        if payload["unresolved_obligation_ids"] != []:
            reasons.append("POSITIVE_UNRESOLVED_NONEMPTY")
        return reasons, missing, []

    @staticmethod
    def _verify_refutation(snapshot, payload, lists, hypotheses,
                            by_hypothesis, evidence):
        reasons, uncovered = [], []
        if not isinstance(payload, dict) or set(payload) != {
                "hypothesis_index", "refutation_cover",
                "uncovered_hypothesis_ids", "frontier_unresolved"}:
            return ["REFUTATION_PAYLOAD_INVALID"], [], []
        expected_index = [hypotheses[key] for key in sorted(hypotheses)]
        if payload["hypothesis_index"] != expected_index:
            reasons.append("HYPOTHESIS_INDEX_MISMATCH")
        expected_hypothesis_ids = sorted(hypotheses)
        if sorted(lists["hypothesis_ids"]) != expected_hypothesis_ids:
            reasons.append("HYPOTHESIS_COVERAGE_INVALID")
        if snapshot["closure_witness"] is None:
            reasons.append("SCOPE_NOT_CLOSED")
        if snapshot["topology"]["frontier_viewpoint_ids"]:
            reasons.append("FRONTIER_OPEN")
        if payload["frontier_unresolved"] != []:
            reasons.append("FRONTIER_OPEN")
        if payload["uncovered_hypothesis_ids"] != []:
            reasons.append("UNCOVERED_HYPOTHESES_NONEMPTY")
        cover = payload["refutation_cover"]
        if not isinstance(cover, list):
            return reasons + ["REFUTATION_COVER_INVALID"], [], expected_hypothesis_ids
        cover_by_hypothesis = {key: [] for key in hypotheses}
        used_evidence = []
        used_obligations = []
        for item in cover:
            if not isinstance(item, dict):
                reasons.append("REFUTATION_COVER_ITEM_INVALID")
                continue
            hypothesis = hypotheses.get(item.get("hypothesis_id"))
            if hypothesis is None:
                reasons.append("REFUTATION_HYPOTHESIS_INVALID")
                continue
            obligation = next((
                value for value in by_hypothesis[hypothesis["hypothesis_id"]]
                if value["obligation_id"] == item.get("obligation_id")
            ), None)
            if (obligation is None or not obligation["necessary"]
                    or not _coverage_matches(item, hypothesis, obligation)):
                reasons.append("REFUTATION_COVER_ITEM_INVALID")
                continue
            cover_by_hypothesis[hypothesis["hypothesis_id"]].append(obligation)
            if obligation["status"] != "REFUTED":
                reasons.append("REFUTATION_OBLIGATION_NOT_REFUTED")
            if sorted(item["evidence_ids"]) != obligation["refutation_evidence_ids"]:
                reasons.append("REFUTATION_EVIDENCE_MISMATCH")
            used_evidence.extend(item["evidence_ids"])
            used_obligations.append(obligation["obligation_id"])
            for evidence_id in item["evidence_ids"]:
                wrapper = evidence.get(evidence_id)
                if wrapper is None or not _wrapper_matches(
                        wrapper, hypothesis, obligation, "REFUTES", snapshot):
                    reasons.append("REFUTATION_BINDING_INCOHERENT")
        for hypothesis_id in expected_hypothesis_ids:
            hypothesis = hypotheses[hypothesis_id]
            selected = cover_by_hypothesis[hypothesis_id]
            if hypothesis["hypothesis_kind"] in RESIDUAL_HYPOTHESIS_KINDS:
                necessary = [
                    item for item in by_hypothesis[hypothesis_id] if item["necessary"]
                ]
                if (sorted(item["obligation_id"] for item in selected)
                        != sorted(item["obligation_id"] for item in necessary)
                        or any(item["predicate_kind"] != "coverage" for item in selected)):
                    uncovered.append(hypothesis_id)
            elif len(selected) != 1:
                uncovered.append(hypothesis_id)
        if uncovered:
            reasons.append("REFUTATION_COVER_INCOMPLETE")
        if sorted(used_evidence) != sorted(lists["evidence_ids"]):
            reasons.append("CERTIFICATE_EVIDENCE_COVERAGE_INVALID")
        if sorted(used_obligations) != sorted(lists["obligation_ids"]):
            reasons.append("CERTIFICATE_OBLIGATION_COVERAGE_INVALID")
        return reasons, [], uncovered


class OnlineVerifier(_OnlineVerifierCore):
    """Production verifier: controlled replay sources are never admitted."""

    def __init__(self):
        super().__init__(allow_controlled=False)


class M3OnlineVerifier(_OnlineVerifierCore):
    """Verifier for the explicit calibrated entity-SUPPORT successor."""

    def __init__(self):
        super().__init__(allow_m3=True)


__all__ = ["M3OnlineVerifier", "OnlineVerifier"]
