"""Reproduce the frozen M3-A real-signal compatibility micro slice.

This is an offline diagnostic, not a benchmark runner and not a statistical
guarantee generator.  It consumes an already-produced DUET signal JSONL and
the official REVERIE ``val_train_seen`` annotation file.  Annotation truth is
used only to build the aggregate calibration summary and, after the runtime
terminal record is immutable, to classify that record offline.

The demonstration record is selected without labels: it is the first record
in canonical ``(scan, episode, event_seq, signal_digest)`` order from scan
partition 2 whose frozen selected absolute logit is at least 3.0.  Partition 1
is calibration and partition 0 is unused development data, exactly as frozen
in ``docs/M3_SCIENTIFIC_PRECOMMIT.md``.
"""

from __future__ import print_function

import argparse
import copy
import hashlib
import json
import os

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256
from proofnav.adapters import derive_runtime_episode_id
from proofnav.offline.calibration_builder import build_scan_familywise_artifact
from proofnav.offline.oracle_evidence import (
    seal_controlled_artifact,
    validate_controlled_truth,
)
from proofnav.offline.oracle_verifier import OracleOfflineVerifier
from proofnav.offline.structural_audit import (
    audit_certificate,
    audit_terminal,
    structural_result,
)
from proofnav.perception import (
    build_calibrated_bound_evidence,
    build_entity_proof_template,
    validate_duet_signal,
)
from proofnav.runtime import (
    CertificateBuilder,
    M3OnlineVerifier,
    M3ProofState,
    M3TerminalController,
)
from proofnav.runtime.semantics import (
    PRODUCTION_INTERFACE_AUDIT_REF,
    object_unit_id,
)


SUPPORT_THRESHOLD = 3.0
CALIBRATION_PARTITION = 1
DEMONSTRATION_PARTITION = 2
STRICT_FALSE_FOUND_BUDGET = 0.05
DIAGNOSTIC_FALSE_FOUND_BUDGET = 1.0
SOURCE_REVISION = "working-tree-after-465b9d4d48125f0c3c063065776886c6916bd52f"
SELECTION_RULE = (
    "first canonical (scan,episode,event_seq,signal_digest) record in "
    "SHA256 scan partition 2 with finite selected_absolute_object_logit >= 3.0"
)
LABEL_DEFINITION = {
    "version": "proofnav.m3a-offline-annotated-slot-label.v1",
    "truth_source": "official_REVERIE_val_train_seen_annotation_objId",
    "positive": "selected_proposal_id_string_equals_annotation_objId_string",
    "empty_selection": "null_score_is_no_support_opportunity_and_never_false_support",
    "aggregation": "scan_has_error_if_any_threshold_selected_slot_is_false",
}


def _raw_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _partition(scan_id):
    prefix = hashlib.sha256(scan_id.encode("utf-8")).hexdigest()[:8]
    return int(prefix, 16) % 3


def _read_json(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path, value):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(
            value, stream, ensure_ascii=False, sort_keys=True, indent=2,
            allow_nan=False,
        )
        stream.write("\n")


def _load_signals(path):
    records = []
    with open(path, "r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            validate_duet_signal(record)
            records.append(record)
    if not records:
        raise ValueError("signal JSONL is empty")
    identities = {canonical_sha256(item["model_identity"]) for item in records}
    if len(identities) != 1:
        raise ValueError("micro slice mixes model identities")
    digests = [item["signal_digest"] for item in records]
    if len(digests) != len(set(digests)):
        raise ValueError("signal JSONL contains duplicate signal digests")
    return records


def _canonical_demo(signals):
    """Choose a demonstration using signal/domain fields only, never truth."""

    eligible = []
    for signal in signals:
        observation = signal["observation"]
        score = signal["object_scores"]["selected_statistic"]
        if (_partition(observation["scan"]) == DEMONSTRATION_PARTITION
                and score is not None
                and float(score) >= SUPPORT_THRESHOLD):
            eligible.append(signal)
    if not eligible:
        raise ValueError("no signal-only eligible demonstration record")
    return sorted(eligible, key=lambda item: (
        item["observation"]["scan"],
        item["observation"]["episode_id"],
        item["observation"]["event_seq"],
        item["signal_digest"],
    ))[0]


def _annotation_index(path):
    """Return hidden labels keyed by episode ID for offline use only."""

    annotations = _read_json(path)
    if not isinstance(annotations, list) or not annotations:
        raise ValueError("annotation file must contain a non-empty list")
    index = {}
    for item in annotations:
        obj_id = str(item["objId"])
        instructions = item["instructions"]
        for instruction in instructions:
            episode_id = derive_runtime_episode_id(
                item["scan"], item["path"][0], instruction,
            )
            if episode_id in index:
                raise ValueError("duplicate annotation episode %s" % episode_id)
            index[episode_id] = {
                "target_object_id": obj_id,
                "instruction": instruction,
            }
    return index


def _truth_for_signal(signal, annotations):
    episode_id = signal["observation"]["episode_id"]
    if episode_id not in annotations:
        raise ValueError("missing annotation for signal episode %s" % episode_id)
    truth = annotations[episode_id]
    if truth["instruction"] != signal["observation"]["instruction"]:
        raise ValueError("instruction mismatch for signal episode %s" % episode_id)
    selected = signal["object_scores"]["selected_proposal_id"]
    return {
        "target_object_id": truth["target_object_id"],
        "target_matches_slot": (
            selected is not None and str(selected) == truth["target_object_id"]
        ),
    }


def _calibration_labels(signals, annotations):
    labels = []
    for signal in signals:
        observation = signal["observation"]
        if _partition(observation["scan"]) != CALIBRATION_PARTITION:
            continue
        truth = _truth_for_signal(signal, annotations)
        labels.append({
            "sample_id": signal["signal_digest"],
            "scan_id": observation["scan"],
            "split_name": "val_train_seen",
            # Null is retained: an empty/all-masked proposal observation is a
            # no-SUPPORT opportunity, not a row eligible for deletion.
            "score": signal["object_scores"]["selected_statistic"],
            "target_matches_slot": truth["target_matches_slot"],
        })
    return labels


def _artifact_spec(signals, command):
    model_identity = copy.deepcopy(signals[0]["model_identity"])
    applicability = sorted({
        item["observation"]["scan"] for item in signals
        if _partition(item["observation"]["scan"]) == DEMONSTRATION_PARTITION
    })
    return {
        "evidence_family": "duet_annotated_slot_entity_grounding",
        "predicate_kind": "entity",
        "polarity": "SUPPORTS",
        "score_semantics": "selected_absolute_object_logit",
        "model_identity": model_identity,
        "label_definition_digest": canonical_sha256(LABEL_DEFINITION),
        # The offline builder replaces these two fields from the actual
        # calibration labels after enforcing scan/split consistency.
        "split_fingerprint": "0" * 64,
        "split_names": ["val_train_seen"],
        "calibration_method": "fixed_threshold_descriptive_micro",
        "calibration_parameters": {"support_threshold": SUPPORT_THRESHOLD},
        "validity_domain": {
            "domain_id": "descriptive_seen_scan_micro",
            "calibration_scan_ids": ["replaced-by-offline-builder"],
            "applicability_scan_ids": applicability,
            "shift_policy": "exact_match_or_abstain",
        },
        "sample_unit": "scan_familywise",
        "dependency_unit": "source_observation_lineage",
        "risk_event": "false_support",
        "risk_bound": {
            "upper_bound": 1.0,
            "confidence": None,
            "semantics": "descriptive_compatibility_not_statistical_guarantee",
        },
        "aggregate_counts": {"scans": 1, "examples": 1, "errors": 1},
        "generation": {
            "command": command,
            "producer": "proofnav.calibration.artifact.build_calibration_artifact",
            "source_revision": SOURCE_REVISION,
        },
    }


def _scope(signal, artifact, observation_count, budget):
    observation = signal["observation"]
    scope_identity = canonical_sha256({
        "episode_id": observation["episode_id"],
        "scan": observation["scan"],
        "artifact_digest": artifact["artifact_digest"],
        "false_found_budget": budget,
        "selection_rule": SELECTION_RULE,
    })
    return {
        "schema_version": SCHEMA_VERSIONS["scope"],
        "scope_contract_id": "scope-m3a-" + scope_identity[:24],
        "episode_id": observation["episode_id"],
        "scan_id": observation["scan"],
        "start_viewpoint": None,  # replaced by the episode's first record
        "domain": {
            "kind": "candidate_reachable_component",
            "rule": "closure from start under the audited local candidate interface",
            "interface_audit_ref": PRODUCTION_INTERFACE_AUDIT_REF,
            "disclosure": "intensional_rule_only",
        },
        "hypothesis_ids": ["m1-placeholder-not-m3-authority"],
        "observation_interface_version": SCHEMA_VERSIONS["observation"],
        "predicate_schema_version": "proofnav.predicate.entity-only.m3a.v1",
        "calibration_version": (
            "proofnav.calibration-artifact.v1:" + artifact["artifact_digest"]
        ),
        "risk_budgets": {
            "false_found": float(budget),
            "false_not_found": 0.05,
        },
        "resource_limits": {
            "max_steps": max(16, observation_count),
            "max_observation_events": max(16, observation_count),
            "max_predicate_queries": 4,
        },
        "provenance": {
            "source": "frozen_duet_val_train_seen_micro_signal",
            "version": "m3a-descriptive-seen-micro.v1",
            "record_id": observation["episode_id"],
        },
        "audit_trail": {
            "created_by": "proofnav.offline.m3_micro_slice",
            "change_log": [
                "signal-only canonical demonstration selection",
                "M3 dynamic hypothesis universe; M1 placeholder IDs ignored",
            ],
        },
    }


def _episode_prefix(signals, selected):
    observation = selected["observation"]
    records = [
        item for item in signals
        if item["observation"]["episode_id"] == observation["episode_id"]
        and item["observation"]["event_seq"] <= observation["event_seq"]
    ]
    records.sort(key=lambda item: item["observation"]["event_seq"])
    if [item["observation"]["event_seq"] for item in records] != list(range(len(records))):
        raise ValueError("demonstration episode prefix has a missing event")
    return records


def _execution(max_step=False):
    return {
        "duet_stop": not max_step,
        "no_frontier": False,
        "max_step": bool(max_step),
        "budget_exhausted": False,
        "executable_action_available": not max_step,
        "searchable_frontier": not max_step,
        "execution_error": False,
    }


def _run_runtime_chain(signals, selected, artifact, budget):
    """Run the online chain without receiving or loading evaluator truth."""

    prefix = _episode_prefix(signals, selected)
    scope = _scope(selected, artifact, len(prefix), budget)
    scope["start_viewpoint"] = prefix[0]["observation"]["viewpoint"]
    template = build_entity_proof_template(
        selected["observation"]["instruction"],
    )
    state = M3ProofState(scope, template)
    for signal in prefix:
        validate_duet_signal(signal, template=template)
        state.ingest_observation(signal["observation"])

    selected_scores = selected["object_scores"]
    unit_id = object_unit_id(
        selected["observation"]["viewpoint"],
        selected_scores["selected_proposal_id"],
    )
    obligation = next((
        item for item in state.snapshot()["obligations"]
        if item["predicate_kind"] == "entity"
        and item["binding_requirement"]["subject_unit_ids"] == [unit_id]
    ), None)
    if obligation is None:
        raise ValueError("selected proposal has no current entity obligation")
    query = state.register_query(
        obligation["hypothesis_id"], obligation["obligation_id"],
    )
    wrapper = build_calibrated_bound_evidence(
        query, selected, artifact, scope["scope_contract_id"],
    )
    if wrapper.get("decision") == "ABSTAIN":
        raise ValueError(
            "precommitted eligible signal unexpectedly abstained: %s" %
            wrapper.get("reason_code")
        )
    state.append_evidence(wrapper)

    outcome = CertificateBuilder().build(state, "FOUND")
    certificate = outcome["certificate"] if outcome["status"] == "CERTIFICATE" else None
    online = M3OnlineVerifier().verify(state, certificate)
    terminal = M3TerminalController().decide(
        state, "FOUND", certificate,
        _execution(max_step=(certificate is None)),
    )
    bundle = state.audit_bundle()
    structure = structural_result(bundle)
    certificate_audit = (
        audit_certificate(bundle, certificate, state=structure["state"])
        if certificate is not None and structure["valid"]
        else {
            "valid": False,
            "reason_codes": ["NO_CERTIFICATE_WITHIN_RISK_BUDGET"],
            "requested_verdict": "FOUND",
        }
    )
    terminal_audit = (
        audit_terminal(structure["state"], terminal, certificate)
        if structure["valid"] else {
            "valid": False,
            "reason_codes": ["OFFLINE_AUDIT_BUNDLE_INVALID"],
            "online_status": None,
            "online_accepted": False,
        }
    )
    return {
        "scope": scope,
        "template": template,
        "query": query,
        "wrapper": wrapper,
        "builder_outcome": outcome,
        "online_verification": online,
        "terminal": terminal,
        "audit_bundle": bundle,
        "structural_audit": structure,
        "certificate_audit": certificate_audit,
        "terminal_audit": terminal_audit,
    }


def _partition_summary(signals, annotations):
    summary = {}
    for partition in range(3):
        records = [
            item for item in signals
            if _partition(item["observation"]["scan"]) == partition
        ]
        supports = [
            item for item in records
            if item["object_scores"]["selected_statistic"] is not None
            and item["object_scores"]["selected_statistic"] >= SUPPORT_THRESHOLD
        ]
        false_supports = sum(
            not _truth_for_signal(item, annotations)["target_matches_slot"]
            for item in supports
        )
        error_scans = sorted({
            item["observation"]["scan"] for item in supports
            if not _truth_for_signal(item, annotations)["target_matches_slot"]
        })
        summary[str(partition)] = {
            "role": {0: "development_unused", 1: "calibration", 2: "demonstration"}[partition],
            "scans": sorted({item["observation"]["scan"] for item in records}),
            "record_count": len(records),
            "null_selection_count": sum(
                item["object_scores"]["selected_statistic"] is None
                for item in records
            ),
            "threshold_support_count": len(supports),
            "false_support_count_offline_diagnostic": false_supports,
            "error_scans_offline_diagnostic": error_scans,
        }
    return summary


def _hidden_truth_after_terminal(chain, target_object_id):
    """Build a sealed offline truth artifact after runtime is immutable.

    Official annotation object IDs are compared only here against observed
    annotated slot IDs.  Residual coverage remains OPEN because this label
    source does not establish proposal completeness.
    """

    bundle = chain["audit_bundle"]
    state = bundle["state"]
    unit_truth = {}
    for transition in bundle["transitions"]:
        if transition["event_type"] != "OBSERVATION":
            continue
        observation = transition["payload"]
        for proposal_id in observation["object_proposal_ids"]:
            unit_id = object_unit_id(observation["viewpoint"], proposal_id)
            matches = str(proposal_id) == str(target_object_id)
            prior = unit_truth.setdefault(unit_id, matches)
            if prior != matches:
                raise ValueError("offline slot truth changed for %s" % unit_id)

    hypotheses = copy.deepcopy(state["hypotheses"])
    obligations = [{
        key: copy.deepcopy(item[key]) for key in (
            "obligation_id", "hypothesis_id", "predicate_id",
            "predicate_kind", "necessary", "binding_requirement",
        )
    } for item in state["obligations"]]
    claims = []
    for obligation in obligations:
        binding = obligation["binding_requirement"]
        subject_units = binding["subject_unit_ids"]
        if obligation["predicate_kind"] == "entity" and len(subject_units) == 1:
            claim = "SUPPORTS" if unit_truth[subject_units[0]] else "REFUTES"
        else:
            claim = "OPEN"
        claims.append({
            "hypothesis_id": obligation["hypothesis_id"],
            "obligation_id": obligation["obligation_id"],
            "predicate_id": obligation["predicate_id"],
            "predicate_kind": obligation["predicate_kind"],
            "binding": copy.deepcopy(binding),
            "claim": claim,
        })

    hypothesis_by_id = {
        item["hypothesis_id"]: item for item in hypotheses
    }
    necessary = {}
    for obligation in obligations:
        if obligation["necessary"]:
            necessary.setdefault(obligation["hypothesis_id"], []).append(
                obligation["obligation_id"],
            )
    claim_by_obligation = {
        item["obligation_id"]: item["claim"] for item in claims
    }
    supported = []
    refuted = []
    for hypothesis_id, obligation_ids in necessary.items():
        polarities = [claim_by_obligation[item] for item in obligation_ids]
        if (all(item == "SUPPORTS" for item in polarities)
                and hypothesis_by_id[hypothesis_id]["hypothesis_kind"]
                not in ("location_residual", "anchor_residual")):
            supported.append(hypothesis_id)
        elif any(item == "REFUTES" for item in polarities):
            refuted.append(hypothesis_id)
    if not supported:
        raise ValueError(
            "selected episode prefix does not contain the annotated target; "
            "the registered positive-control truth would be unresolved"
        )
    truth = {
        "schema_version": SCHEMA_VERSIONS["controlled_truth"],
        "episode_id": state["episode_id"],
        "scope_contract_id": state["scope_contract_id"],
        "scope_version": state["scope_version"],
        "scope_digest": state["scope_digest"],
        "template_id": state["template_id"],
        "template_digest": state["template_digest"],
        "universe_digest": state["universe_digest"],
        "premise_class": "positive_control",
        "semantic_truth": "FOUND",
        "hypotheses": hypotheses,
        "obligations": obligations,
        "claims": claims,
        "supported_hypothesis_ids": sorted(supported),
        "refuted_hypothesis_ids": sorted(refuted),
        "audit_trail": {
            "producer": "proofnav.offline.controlled_truth.v2",
            "source_artifact_digest": "",
        },
    }
    truth = seal_controlled_artifact(truth)
    validate_controlled_truth(truth)
    return truth


def _save_chain(output_dir, name, chain):
    paths = {}
    values = {
        "audit_bundle": chain["audit_bundle"],
        "builder_outcome": chain["builder_outcome"],
        "online_verification": chain["online_verification"],
        "terminal": chain["terminal"],
    }
    for kind, value in values.items():
        path = os.path.join(output_dir, "%s_%s.json" % (name, kind))
        _write_json(path, value)
        paths[kind] = {
            "path": path,
            "sha256": _raw_sha256(path),
        }
    return paths


def _save_offline_audit(output_dir, name, truth, report):
    paths = {}
    for kind, value in (("hidden_truth", truth), ("oracle_audit", report)):
        path = os.path.join(output_dir, "%s_%s.json" % (name, kind))
        _write_json(path, value)
        paths[kind] = {"path": path, "sha256": _raw_sha256(path)}
    return paths


def run(signal_file, annotation_file, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    signals = _load_signals(signal_file)
    # Select the demonstration before evaluator truth is even loaded.  The
    # selector also has no annotation/truth argument, making the separation
    # both temporal and structural inside this offline diagnostic.
    selected = _canonical_demo(signals)
    annotations = _annotation_index(annotation_file)

    command = (
        "python -m proofnav.offline.m3_micro_slice "
        "--signal-file %s --annotation-file %s --output-dir %s" % (
            signal_file, annotation_file, output_dir,
        )
    )
    labels = _calibration_labels(signals, annotations)
    artifact = build_scan_familywise_artifact(
        labels, _artifact_spec(signals, command),
    )
    artifact_path = os.path.join(output_dir, "m3a_calibration_artifact.json")
    _write_json(artifact_path, artifact)

    permissive = _run_runtime_chain(
        signals, selected, artifact, DIAGNOSTIC_FALSE_FOUND_BUDGET,
    )
    strict = _run_runtime_chain(
        signals, selected, artifact, STRICT_FALSE_FOUND_BUDGET,
    )
    # Runtime terminal records are now immutable.  Only at this point does the
    # hidden evaluator label enter the formal independent offline verifier.
    demo_truth = _truth_for_signal(selected, annotations)
    permissive_truth = _hidden_truth_after_terminal(
        permissive, demo_truth["target_object_id"],
    )
    strict_truth = _hidden_truth_after_terminal(
        strict, demo_truth["target_object_id"],
    )
    oracle = OracleOfflineVerifier()
    permissive_oracle = oracle.verify(
        permissive_truth, permissive["audit_bundle"],
        permissive["terminal"],
        permissive["builder_outcome"].get("certificate"),
    )
    strict_oracle = oracle.verify(
        strict_truth, strict["audit_bundle"], strict["terminal"],
        strict["builder_outcome"].get("certificate"),
    )
    permissive_files = _save_chain(output_dir, "budget_1p00", permissive)
    strict_files = _save_chain(output_dir, "budget_0p05", strict)
    permissive_files.update(_save_offline_audit(
        output_dir, "budget_1p00", permissive_truth, permissive_oracle,
    ))
    strict_files.update(_save_offline_audit(
        output_dir, "budget_0p05", strict_truth, strict_oracle,
    ))

    permissive_safe = (
        permissive["builder_outcome"]["status"] == "UNRESOLVED"
        and permissive["terminal"]["semantic_verdict"] == "UNRESOLVED"
        and permissive["structural_audit"]["valid"]
        and permissive["terminal_audit"]["valid"]
        and permissive_oracle["outcome"] == "UNRESOLVED"
    )
    strict_safe = (
        strict["builder_outcome"]["status"] == "UNRESOLVED"
        and strict["terminal"]["semantic_verdict"] == "UNRESOLVED"
        and strict["structural_audit"]["valid"]
        and strict["terminal_audit"]["valid"]
        and strict_oracle["outcome"] == "UNRESOLVED"
    )
    report = {
        "report_version": "proofnav.m3a-real-micro-slice-report.v1",
        "scientific_status": (
            "descriptive_diagnostic_only_no_statistical_certificate"
        ),
        "inputs": {
            "signal_file": signal_file,
            "signal_file_sha256": _raw_sha256(signal_file),
            "annotation_file": annotation_file,
            "annotation_file_sha256": _raw_sha256(annotation_file),
            "signal_records": len(signals),
            "episodes": len({item["observation"]["episode_id"] for item in signals}),
            "scans": len({item["observation"]["scan"] for item in signals}),
        },
        "precommitted_protocol": {
            "support_threshold": SUPPORT_THRESHOLD,
            "scan_partition": "int(SHA256(scan_id)[:8],16) % 3",
            "calibration_partition": CALIBRATION_PARTITION,
            "demonstration_partition": DEMONSTRATION_PARTITION,
            "demonstration_selection": SELECTION_RULE,
            "strict_false_found_budget": STRICT_FALSE_FOUND_BUDGET,
            "diagnostic_false_found_budget": DIAGNOSTIC_FALSE_FOUND_BUDGET,
        },
        "partitions": _partition_summary(signals, annotations),
        "calibration": {
            "artifact_path": artifact_path,
            "artifact_file_sha256": _raw_sha256(artifact_path),
            "artifact_digest": artifact["artifact_digest"],
            "aggregate_counts": artifact["aggregate_counts"],
            "risk_bound": artifact["risk_bound"],
            "null_calibration_examples_retained": sum(
                item["score"] is None for item in labels
            ),
            "label_definition_digest": artifact["label_definition_digest"],
            "contains_per_sample_truth": False,
        },
        "demonstration": {
            "episode_id": selected["observation"]["episode_id"],
            "scan": selected["observation"]["scan"],
            "event_seq": selected["observation"]["event_seq"],
            "step": selected["observation"]["step"],
            "viewpoint": selected["observation"]["viewpoint"],
            "signal_digest": selected["signal_digest"],
            "selected_proposal_id_runtime": selected["object_scores"]["selected_proposal_id"],
            "selected_statistic_runtime": selected["object_scores"]["selected_statistic"],
            "target_object_id_offline_only": demo_truth["target_object_id"],
            "target_matches_slot_offline_only": demo_truth["target_matches_slot"],
        },
        "diagnostic_budget_1p00": {
            "builder_status": permissive["builder_outcome"]["status"],
            "derived_risk_claim": (
                permissive["builder_outcome"].get("certificate") or {}
            ).get("risk_claim"),
            "online_status": permissive["online_verification"]["status"],
            "terminal_directive": permissive["terminal"]["directive"],
            "independent_structural_valid": permissive["structural_audit"]["valid"],
            "independent_certificate_valid": permissive["certificate_audit"]["valid"],
            "independent_terminal_valid": permissive["terminal_audit"]["valid"],
            "offline_outcome": permissive_oracle["outcome"],
            "offline_safety_interpretation": (
                "CORRECT_ABSTAIN" if permissive_safe else "AUDIT_FAILURE"
            ),
            "oracle_reason_codes": permissive_oracle["reason_codes"],
            "files": permissive_files,
            "interpretation": (
                "descriptive artifact has no statistical authority; "
                "budget 1.0 cannot unlock a certificate"
            ),
        },
        "strict_budget_0p05": {
            "builder_status": strict["builder_outcome"]["status"],
            "builder_reason_codes": strict["builder_outcome"]["feedback"]["reason_codes"],
            "online_status": strict["online_verification"]["status"],
            "terminal_directive": strict["terminal"]["directive"],
            "terminal_semantic_verdict": strict["terminal"]["semantic_verdict"],
            "independent_structural_valid": strict["structural_audit"]["valid"],
            "independent_terminal_valid": strict["terminal_audit"]["valid"],
            "offline_outcome": strict_oracle["outcome"],
            "offline_safety_interpretation": (
                "CORRECT_ABSTAIN" if strict_safe else "AUDIT_FAILURE"
            ),
            "oracle_reason_codes": strict_oracle["reason_codes"],
            "files": strict_files,
            "interpretation": (
                "descriptive artifact has no statistical authority; "
                "budget 0.05 cannot unlock a certificate"
            ),
        },
        "runtime_truth_boundary": {
            "runtime_chain_function_accepts_truth": False,
            "runtime_artifact_is_aggregate_only": True,
            "demo_selector_accepts_truth_or_annotations": False,
            "truth_loaded_after_signal_only_demo_selection": True,
            "truth_used_only_for_calibration_and_post_terminal_oracle_audit": True,
            "formal_oracle_offline_verifier_used": True,
        },
        "limitations": [
            "val_train_seen scans overlap the frozen checkpoint training domain",
            "risk bound is descriptive 2/6 scan-familywise, with no confidence guarantee",
            "both 1.0 and 0.05 budgets are UNRESOLVED because no statistical upper bound exists",
            "entity REFUTE, residual coverage, identity, attribute, relation, and room remain sealed",
        ],
    }
    report_path = os.path.join(output_dir, "m3a_micro_slice_report.json")
    _write_json(report_path, report)
    return report_path, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--signal-file",
        default=".m3-results/signals/val_train_seen_opaque.jsonl",
    )
    parser.add_argument(
        "--annotation-file",
        default="datasets/REVERIE/annotations/REVERIE_val_train_seen_enc.json",
    )
    parser.add_argument(
        "--output-dir",
        default=".m3-results/m3a_micro_slice_opaque",
    )
    args = parser.parse_args(argv)
    report_path, report = run(
        args.signal_file, args.annotation_file, args.output_dir,
    )
    print(json.dumps({
        "report_path": report_path,
        "artifact_digest": report["calibration"]["artifact_digest"],
        "aggregate_counts": report["calibration"]["aggregate_counts"],
        "risk_bound": report["calibration"]["risk_bound"],
        "demo_episode": report["demonstration"]["episode_id"],
        "budget_1p00": report["diagnostic_budget_1p00"]["offline_outcome"],
        "budget_0p05": report["strict_budget_0p05"]["offline_outcome"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
