"""Independent offline M1 evaluator with a one-way truth boundary."""

import argparse
import json

from .contracts import ContractViolation, SCHEMA_VERSIONS, semantic_verdict
from .paired import validate_pair_collection
from .reference_checker import check_reference
from .validation import assert_agent_visible, validate_result


def _legacy_prediction(record, index):
    if not isinstance(record, dict):
        raise ContractViolation("LEGACY_TYPE", "$[%d]" % index, "expected object")
    missing = {"instr_id", "trajectory", "pred_objid"} - set(record)
    if missing:
        raise ContractViolation(
            "LEGACY_FIELDS", "$[%d]" % index, "missing %s" % sorted(missing),
        )
    if not isinstance(record["instr_id"], str) or not record["instr_id"]:
        raise ContractViolation("LEGACY_INSTR_ID", "$[%d].instr_id" % index, "invalid ID")
    trajectory = record["trajectory"]
    if not isinstance(trajectory, list) or not trajectory:
        raise ContractViolation("LEGACY_TRAJECTORY", "$[%d].trajectory" % index, "invalid trajectory")
    for segment_index, segment in enumerate(trajectory):
        if not isinstance(segment, list) or not segment:
            raise ContractViolation(
                "LEGACY_TRAJECTORY", "$[%d].trajectory[%d]" % (index, segment_index),
                "invalid segment",
            )
    return record


def prediction_mode(predictions):
    if not isinstance(predictions, list):
        raise ContractViolation("PREDICTION_LIST", "$", "expected an array")
    if not predictions:
        raise ContractViolation("PREDICTION_EMPTY", "$", "must not be empty")
    if not all(isinstance(record, dict) for record in predictions):
        raise ContractViolation("PREDICTION_MODE", "$", "all records must be objects")
    modes = {
        "proofnav" if record.get("schema_version") is not None else "duet_legacy"
        for record in predictions
    }
    if len(modes) != 1:
        raise ContractViolation("PREDICTION_MODE", "$", "mixed/invalid prediction records")
    return next(iter(modes))


def truth_from_pairs(pairs):
    """Extract evaluator truth without returning any agent-visible member object."""

    validate_pair_collection(pairs)
    values = {}
    for pair in pairs:
        for role in ("clean", "false"):
            member = pair["members"][role]
            instr_id = member["agent_visible"]["episode_id"]
            truth = member["evaluator_only"]["semantic_truth"]
            if instr_id in values:
                raise ContractViolation("TRUTH_DUPLICATE", "$.pairs", "duplicate episode %s" % instr_id)
            values[instr_id] = truth
    return values


def _cost_totals(records):
    keys = (
        "travel_distance_meters", "high_level_actions", "expanded_path_edges",
        "observation_events", "predicate_queries", "online_compute_milliseconds",
        "storage_bytes",
    )
    return {
        key: sum(float(record["cost_ledger"][key]) for record in records)
        for key in keys
    }


def evaluate_predictions(predictions, truth_by_instr_id=None, contexts_by_instr_id=None):
    """Evaluate serialized predictions; truth is never passed to the checker."""

    mode = prediction_mode(predictions)
    if mode == "duet_legacy":
        for index, record in enumerate(predictions):
            _legacy_prediction(record, index)
        return {
            "schema_version": SCHEMA_VERSIONS["evaluation"],
            "mode": "duet_legacy",
            "prediction_count": len(predictions),
            "legacy_records_valid": True,
            "proofnav_semantics_evaluated": False,
            "note": "Use the frozen REVERIE evaluator for SR/SPL/RGS/RGSPL.",
        }

    truth_by_instr_id = truth_by_instr_id or {}
    contexts_by_instr_id = contexts_by_instr_id or {}
    records = []
    verdict_counts = {"FOUND": 0, "NOT_FOUND": 0, "UNRESOLVED": 0}
    termination_counts = {}
    truth_counts = {"FOUND": 0, "NOT_FOUND": 0}
    correct_by_truth = {"FOUND": 0, "NOT_FOUND": 0}
    false_found = 0
    false_not_found = 0
    correct = 0
    resolved_correct = 0
    truth_labeled_resolved = 0
    accepted_certificates = 0
    checked_certificates = 0
    invalid_reference_records = 0
    seen_ids = set()
    for index, prediction in enumerate(predictions):
        validate_result(prediction)
        instr_id = prediction["instr_id"]
        if instr_id in seen_ids:
            raise ContractViolation("PREDICTION_DUPLICATE", "$[%d].instr_id" % index, instr_id)
        seen_ids.add(instr_id)
        context = contexts_by_instr_id.get(instr_id)
        if context is None:
            raise ContractViolation("EVALUATION_CONTEXT", "$[%d]" % index, "missing online-only context")
        assert_agent_visible(context, "$.contexts.%s" % instr_id)
        required_context = {"scope", "obligations", "evidence", "observations"}
        if not isinstance(context, dict) or set(context) != required_context:
            raise ContractViolation("EVALUATION_CONTEXT", "$.contexts.%s" % instr_id, "incomplete context")

        # The checker is called before and without retrieving evaluator truth.
        reference = check_reference(
            prediction, context["scope"], context["obligations"],
            context["evidence"], context["observations"],
        )
        verdict = semantic_verdict(prediction)
        verdict_counts[verdict] += 1
        termination = prediction["termination"]["cause"]
        termination_counts[termination] = termination_counts.get(termination, 0) + 1
        if verdict != "UNRESOLVED":
            checked_certificates += 1
            accepted_certificates += int(reference["certificate_accepted"])
        invalid_reference_records += int(not reference["record_valid"])

        truth = truth_by_instr_id.get(instr_id)
        semantic_correct = None
        if truth is not None:
            if truth not in ("FOUND", "NOT_FOUND"):
                raise ContractViolation("EVALUATOR_TRUTH", "$.truth.%s" % instr_id, "invalid truth")
            truth_counts[truth] += 1
            semantic_correct = verdict == truth
            correct += int(semantic_correct)
            correct_by_truth[truth] += int(semantic_correct)
            if verdict != "UNRESOLVED":
                truth_labeled_resolved += 1
                resolved_correct += int(semantic_correct)
            false_found += int(verdict == "FOUND" and truth == "NOT_FOUND")
            false_not_found += int(verdict == "NOT_FOUND" and truth == "FOUND")
        records.append({
            "instr_id": instr_id,
            "semantic_verdict": verdict,
            "evaluator_truth": truth,
            "semantic_correct": semantic_correct,
            "termination_cause": termination,
            "certificate_check": reference,
            "risk_claim": prediction["risk_claim"],
            "budget_status": prediction["budget_status"],
            "cost_ledger": prediction["cost_ledger"],
        })

    truth_total = sum(truth_counts.values())
    per_class_accuracy = {
        label: (
            correct_by_truth[label] / truth_counts[label]
            if truth_counts[label] else None
        )
        for label in ("FOUND", "NOT_FOUND")
    }
    available_class_accuracies = [
        value for value in per_class_accuracy.values() if value is not None
    ]
    summary = {
        "schema_version": SCHEMA_VERSIONS["evaluation"],
        "mode": "proofnav",
        "prediction_count": len(predictions),
        "truth_labeled_count": truth_total,
        "verdict_counts": verdict_counts,
        "termination_counts": termination_counts,
        "truth_counts": truth_counts,
        "per_class_accuracy": per_class_accuracy,
        "balanced_decision_accuracy": (
            sum(available_class_accuracies) / len(available_class_accuracies)
            if available_class_accuracies else None
        ),
        "overall_decision_accuracy": correct / truth_total if truth_total else None,
        "resolved_decision_accuracy": (
            resolved_correct / truth_labeled_resolved
            if truth_labeled_resolved else None
        ),
        "unresolved_rate": verdict_counts["UNRESOLVED"] / len(predictions),
        "false_found_count": false_found,
        "false_not_found_count": false_not_found,
        "checked_certificate_count": checked_certificates,
        "accepted_certificate_count": accepted_certificates,
        "certificate_acceptance_rate": (
            accepted_certificates / checked_certificates
            if checked_certificates else None
        ),
        "invalid_reference_record_count": invalid_reference_records,
        "cost_totals": _cost_totals(predictions),
        "records": records,
        "boundary_note": "evaluator truth was not passed to the M1 reference checker",
    }
    return summary


def _load(path):
    with open(path, encoding="utf-8") as infile:
        return json.load(infile)


def main():
    parser = argparse.ArgumentParser(description="ProofNav M1 offline evaluator")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--truth")
    parser.add_argument("--contexts")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = evaluate_predictions(
        _load(args.predictions),
        truth_by_instr_id=_load(args.truth) if args.truth else None,
        contexts_by_instr_id=_load(args.contexts) if args.contexts else None,
    )
    with open(args.output, "w", encoding="utf-8") as outfile:
        json.dump(summary, outfile, sort_keys=True, indent=2)


if __name__ == "__main__":
    main()
