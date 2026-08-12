"""A deliberately small M1 fixture/reference checker.

This module checks serialized examples against the frozen semantics.  It is not
the M2 online verifier: it has no runtime hook, rejection feedback loop,
certificate constructor, perception model, or calibrated-risk implementation.
It also never accepts evaluator truth as input.
"""

from .contracts import ContractViolation, SCHEMA_VERSIONS, semantic_verdict
from .validation import (
    validate_evidence,
    validate_obligation,
    validate_observation,
    validate_result,
    validate_scope,
)


def _report(verdict=None):
    return {
        "schema_version": SCHEMA_VERSIONS["reference_check"],
        "record_valid": False,
        "checked_verdict": verdict,
        "certificate_accepted": False,
        "reason_codes": [],
        "remaining_obligation_ids": [],
    }


def _reason(report, code):
    if code not in report["reason_codes"]:
        report["reason_codes"].append(code)


def _required(mapping, keys, report, prefix):
    if not isinstance(mapping, dict):
        _reason(report, prefix + "_TYPE")
        return False
    missing = set(keys) - set(mapping)
    if missing:
        _reason(report, prefix + "_FIELDS")
        return False
    return True


def _only(mapping, keys, report, prefix):
    unknown = set(mapping) - set(keys)
    if unknown:
        _reason(report, prefix + "_UNKNOWN_FIELDS")
        return False
    return True


def _validate_context(result, scope, obligations, evidence, observations, report):
    validate_result(result)
    validate_scope(scope)
    if result["scope_contract_id"] != scope["scope_contract_id"]:
        _reason(report, "SCOPE_ID_MISMATCH")
    if result["instr_id"] != scope["episode_id"]:
        _reason(report, "EPISODE_ID_MISMATCH")
    observation_by_id = {}
    for observation in observations:
        validate_observation(observation)
        if observation["event_id"] in observation_by_id:
            _reason(report, "DUPLICATE_OBSERVATION_ID")
        observation_by_id[observation["event_id"]] = observation
    evidence_by_id = {}
    for item in evidence:
        validate_evidence(item, observation_by_id)
        if item["evidence_id"] in evidence_by_id:
            _reason(report, "DUPLICATE_EVIDENCE_ID")
        evidence_by_id[item["evidence_id"]] = item
        if item["scope_contract_id"] != scope["scope_contract_id"]:
            _reason(report, "EVIDENCE_SCOPE_MISMATCH")
        if item["episode_id"] != result["instr_id"]:
            _reason(report, "EVIDENCE_EPISODE_MISMATCH")
    obligation_by_id = {}
    for obligation in obligations:
        validate_obligation(obligation)
        if obligation["obligation_id"] in obligation_by_id:
            _reason(report, "DUPLICATE_OBLIGATION_ID")
        obligation_by_id[obligation["obligation_id"]] = obligation
        if obligation["scope_contract_id"] != scope["scope_contract_id"]:
            _reason(report, "OBLIGATION_SCOPE_MISMATCH")
        if obligation["episode_id"] != result["instr_id"]:
            _reason(report, "OBLIGATION_EPISODE_MISMATCH")
        if obligation["hypothesis_id"] not in scope["hypothesis_ids"]:
            _reason(report, "OBLIGATION_OUT_OF_SCOPE")
        if not set(obligation["evidence_ids"]) <= set(evidence_by_id):
            _reason(report, "OBLIGATION_EVIDENCE_MISSING")
    event_ids = set(result["audit_trail"]["event_ids"])
    if not event_ids <= set(observation_by_id):
        _reason(report, "RESULT_EVENT_MISSING")
    return observation_by_id, evidence_by_id, obligation_by_id


def _check_risk_against_scope(result, scope, report):
    risk = result["risk_claim"]
    risk_type = risk["risk_type"]
    if risk["budget"] > scope["risk_budgets"][risk_type]:
        _reason(report, "RISK_EXCEEDS_SCOPE_BUDGET")
    if risk["calibration_version"] != scope["calibration_version"]:
        _reason(report, "CALIBRATION_VERSION_MISMATCH")


def _check_evidence_refs(entry, obligation, expected_claim, evidence_by_id, report):
    evidence_ids = entry.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        _reason(report, "CERTIFICATE_EVIDENCE_EMPTY")
        return
    for evidence_id in evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None:
            _reason(report, "CERTIFICATE_EVIDENCE_MISSING")
            continue
        if item["claim"] != expected_claim:
            _reason(report, "CERTIFICATE_EVIDENCE_POLARITY")
        if item["obligation_id"] != obligation["obligation_id"]:
            _reason(report, "CERTIFICATE_EVIDENCE_OBLIGATION")
        if item["predicate_id"] != obligation["predicate_id"]:
            _reason(report, "CERTIFICATE_EVIDENCE_PREDICATE")


def _check_certificate_header(certificate, result, scope, observation_by_id, report):
    if not _required(certificate, (
        "schema_version", "certificate_id", "certificate_type",
        "episode_id", "scope_contract_id", "audit_trail",
    ), report, "CERTIFICATE"):
        return False
    if certificate["schema_version"] != SCHEMA_VERSIONS["certificate"]:
        _reason(report, "CERTIFICATE_VERSION")
    if certificate["episode_id"] != result["instr_id"]:
        _reason(report, "CERTIFICATE_EPISODE_MISMATCH")
    if certificate["scope_contract_id"] != scope["scope_contract_id"]:
        _reason(report, "CERTIFICATE_SCOPE_MISMATCH")
    audit = certificate["audit_trail"]
    audit_fields = ("producer", "source_versions", "event_ids")
    if not isinstance(audit, dict) or not set(audit_fields) <= set(audit):
        _reason(report, "CERTIFICATE_AUDIT")
    else:
        if not _only(audit, audit_fields, report, "CERTIFICATE_AUDIT"):
            return False
        if not isinstance(audit["producer"], str) or not audit["producer"]:
            _reason(report, "CERTIFICATE_AUDIT_PRODUCER")
        expected_sources = {"observation", "evidence", "scope", "obligation"}
        if (not isinstance(audit["source_versions"], dict)
                or set(audit["source_versions"]) != expected_sources
                or not all(
                    isinstance(version, str) and version
                    for version in audit["source_versions"].values()
                )):
            _reason(report, "CERTIFICATE_AUDIT_VERSIONS")
        if not isinstance(audit["event_ids"], list) or not set(audit["event_ids"]) <= set(observation_by_id):
            _reason(report, "CERTIFICATE_AUDIT_EVENTS")
    return True


def _check_found(result, scope, obligation_by_id, evidence_by_id,
                 observation_by_id, report):
    certificate = result["certificate"]
    fields = (
        "schema_version", "certificate_id", "certificate_type", "episode_id",
        "scope_contract_id", "entity_binding", "true_path",
        "unresolved_obligation_ids", "audit_trail",
    )
    if not _check_certificate_header(
            certificate, result, scope, observation_by_id, report):
        return
    _only(certificate, fields, report, "POSITIVE_CERTIFICATE")
    if certificate.get("certificate_type") != "positive":
        _reason(report, "FOUND_CERTIFICATE_TYPE")
        return
    if not _required(certificate, (
        "entity_binding", "true_path", "unresolved_obligation_ids",
    ), report, "POSITIVE_CERTIFICATE"):
        return
    binding = certificate["entity_binding"]
    if (not isinstance(binding, dict)
            or set(binding) != {"entity_id", "binding_event_id"}):
        _reason(report, "FOUND_ENTITY_BINDING")
    else:
        if binding["binding_event_id"] not in observation_by_id:
            _reason(report, "FOUND_BINDING_EVENT")
        if result["pred_objid"] != binding["entity_id"]:
            _reason(report, "FOUND_BINDING_OUTPUT")
    if certificate["unresolved_obligation_ids"]:
        _reason(report, "FOUND_UNRESOLVED")
    necessary = {
        obligation_id: obligation
        for obligation_id, obligation in obligation_by_id.items()
        if obligation["necessary"]
    }
    for obligation in necessary.values():
        if obligation["status"] != "SUPPORTED":
            report["remaining_obligation_ids"].append(obligation["obligation_id"])
            _reason(report, "FOUND_OBLIGATION_NOT_SUPPORTED")
    covered = set()
    path = certificate["true_path"]
    if not isinstance(path, list) or not path:
        _reason(report, "FOUND_TRUE_PATH_EMPTY")
        return
    for entry in path:
        if isinstance(entry, dict):
            _only(
                entry, ("obligation_id", "predicate_id", "evidence_ids"),
                report, "TRUE_PATH_ENTRY",
            )
        if not _required(entry, (
            "obligation_id", "predicate_id", "evidence_ids",
        ), report, "TRUE_PATH_ENTRY"):
            continue
        obligation = necessary.get(entry["obligation_id"])
        if obligation is None:
            _reason(report, "FOUND_UNKNOWN_OBLIGATION")
            continue
        covered.add(obligation["obligation_id"])
        if entry["predicate_id"] != obligation["predicate_id"]:
            _reason(report, "FOUND_PREDICATE_MISMATCH")
        _check_evidence_refs(entry, obligation, "SUPPORTS", evidence_by_id, report)
    if covered != set(necessary):
        _reason(report, "FOUND_INCOMPLETE_TRUE_PATH")
        report["remaining_obligation_ids"].extend(sorted(set(necessary) - covered))
    _check_risk_against_scope(result, scope, report)


def _check_not_found(result, scope, obligation_by_id, evidence_by_id,
                     observation_by_id, report):
    certificate = result["certificate"]
    fields = (
        "schema_version", "certificate_id", "certificate_type", "episode_id",
        "scope_contract_id", "hypothesis_index", "refutation_cover",
        "uncovered_hypothesis_ids", "frontier_unresolved", "audit_trail",
    )
    if not _check_certificate_header(
            certificate, result, scope, observation_by_id, report):
        return
    _only(certificate, fields, report, "REFUTATION_CERTIFICATE")
    if certificate.get("certificate_type") != "refutation_cover":
        _reason(report, "NOT_FOUND_CERTIFICATE_TYPE")
        return
    if not _required(certificate, (
        "hypothesis_index", "refutation_cover", "uncovered_hypothesis_ids",
        "frontier_unresolved",
    ), report, "REFUTATION_CERTIFICATE"):
        return
    hypotheses = scope["hypothesis_ids"]
    if certificate["hypothesis_index"] != hypotheses:
        _reason(report, "NOT_FOUND_HYPOTHESIS_INDEX")
    if certificate["uncovered_hypothesis_ids"]:
        _reason(report, "NOT_FOUND_UNCOVERED")
    if certificate["frontier_unresolved"]:
        _reason(report, "NOT_FOUND_FRONTIER_UNRESOLVED")
    cover = certificate["refutation_cover"]
    if not isinstance(cover, list) or not cover:
        _reason(report, "NOT_FOUND_COVER_EMPTY")
        return
    covered = set()
    for entry in cover:
        if isinstance(entry, dict):
            _only(
                entry, (
                    "hypothesis_id", "obligation_id", "predicate_id",
                    "evidence_ids",
                ), report, "REFUTATION_ENTRY",
            )
        if not _required(entry, (
            "hypothesis_id", "obligation_id", "predicate_id", "evidence_ids",
        ), report, "REFUTATION_ENTRY"):
            continue
        hypothesis_id = entry["hypothesis_id"]
        if hypothesis_id not in hypotheses:
            _reason(report, "NOT_FOUND_OUT_OF_SCOPE_HYPOTHESIS")
            continue
        covered.add(hypothesis_id)
        obligation = obligation_by_id.get(entry["obligation_id"])
        if obligation is None:
            _reason(report, "NOT_FOUND_UNKNOWN_OBLIGATION")
            continue
        if obligation["hypothesis_id"] != hypothesis_id:
            _reason(report, "NOT_FOUND_OBLIGATION_HYPOTHESIS")
        if obligation["status"] != "REFUTED":
            _reason(report, "NOT_FOUND_OBLIGATION_NOT_REFUTED")
        if entry["predicate_id"] != obligation["predicate_id"]:
            _reason(report, "NOT_FOUND_PREDICATE_MISMATCH")
        _check_evidence_refs(entry, obligation, "REFUTES", evidence_by_id, report)
    if covered != set(hypotheses):
        _reason(report, "NOT_FOUND_INCOMPLETE_COVER")
        report["remaining_obligation_ids"].extend(sorted(set(hypotheses) - covered))
    _check_risk_against_scope(result, scope, report)


def check_reference(result, scope, obligations, evidence, observations):
    """Check one synthetic/M1 example using online-only context."""

    report = _report()
    try:
        verdict = semantic_verdict(result)
        report["checked_verdict"] = verdict
        observation_by_id, evidence_by_id, obligation_by_id = _validate_context(
            result, scope, obligations, evidence, observations, report,
        )
        if verdict == "FOUND":
            _check_found(
                result, scope, obligation_by_id, evidence_by_id,
                observation_by_id, report,
            )
        elif verdict == "NOT_FOUND":
            _check_not_found(
                result, scope, obligation_by_id, evidence_by_id,
                observation_by_id, report,
            )
        else:
            report["remaining_obligation_ids"] = sorted(
                obligation["obligation_id"]
                for obligation in obligation_by_id.values()
                if obligation["necessary"] and obligation["status"] == "OPEN"
            )
        report["record_valid"] = not report["reason_codes"]
        report["certificate_accepted"] = bool(
            report["record_valid"] and verdict in ("FOUND", "NOT_FOUND")
        )
    except ContractViolation as error:
        report["reason_codes"].append(error.code)
        report["contract_error"] = {
            "location": error.location,
            "message": error.message,
        }
    return report
