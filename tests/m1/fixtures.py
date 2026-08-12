"""Synthetic micro fixtures only; these are not benchmark records or results."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256
from proofnav.paired import pair_fingerprint


def observation(episode_id, event_id, event_seq=0, step=0, viewpoint="vp0"):
    return {
        "schema_version": SCHEMA_VERSIONS["observation"],
        "event_id": event_id,
        "episode_id": episode_id,
        "event_seq": event_seq,
        "step": step,
        "source": "observation",
        "scan": "micro-scan",
        "viewpoint": viewpoint,
        "view_index": 12,
        "pose": {"heading": 0.0, "elevation": 0.0, "position": [0.0, 0.0, 0.0]},
        "field_schema": {
            "feature": {"shape": [36, 772], "dtype": "float32"},
            "obj_img_fts": {"shape": [1, 768], "dtype": "float32"},
            "obj_ang_fts": {"shape": [1, 4], "dtype": "float32"},
            "obj_box_fts": {"shape": [1, 3], "dtype": "float32"},
        },
        "instruction": "Find the micro target.",
        "instruction_encoding_length": 5,
        "candidates": [{
            "viewpoint_id": "vp1",
            "point_id": 12,
            "heading": 0.0,
            "elevation": 0.0,
            "position": [1.0, 0.0, 0.0],
            "simulator_index": 1,
            "feature_schema": {"shape": [772], "dtype": "float32"},
            "evidence_role": "unobserved_navigation_proposal",
        }],
        "object_proposal_ids": ["obj-1"],
        "audit_trail": {
            "producer": "tests.m1.fixtures",
            "source_schema": "synthetic.micro.v1",
        },
    }


def scope(episode_id, hypothesis_ids):
    return {
        "schema_version": SCHEMA_VERSIONS["scope"],
        "scope_contract_id": "scope-" + episode_id,
        "episode_id": episode_id,
        "scan_id": "micro-scan",
        "start_viewpoint": "vp0",
        "domain": {
            "kind": "candidate_reachable_component",
            "rule": "closure from start under the audited local candidate interface",
            "interface_audit_ref": "m0.offline_adjacency.v1:micro",
            "disclosure": "intensional_rule_only",
        },
        "hypothesis_ids": list(hypothesis_ids),
        "observation_interface_version": SCHEMA_VERSIONS["observation"],
        "predicate_schema_version": "proofnav.predicate.micro.v1",
        "calibration_version": "proofnav.calibration.micro.v1",
        "risk_budgets": {"false_found": 0.05, "false_not_found": 0.05},
        "resource_limits": {
            "max_steps": 4,
            "max_observation_events": 4,
            "max_predicate_queries": 4,
        },
        "provenance": {
            "source": "synthetic_micro_fixture",
            "version": "v1",
            "record_id": episode_id,
        },
        "audit_trail": {
            "created_by": "tests.m1.fixtures",
            "change_log": ["initial synthetic contract fixture"],
        },
    }


def evidence(episode_id, evidence_id, event_id, obligation_id, predicate_id, claim):
    return {
        "schema_version": SCHEMA_VERSIONS["evidence"],
        "evidence_id": evidence_id,
        "episode_id": episode_id,
        "source": "observation",
        "source_event_id": event_id,
        "event_seq": 0,
        "step": 0,
        "scan": "micro-scan",
        "viewpoint": "vp0",
        "view_index": 12,
        "evidence_role": "object_slot",
        "unit_id": "vp0:object:obj-1",
        "scope_contract_id": "scope-" + episode_id,
        "obligation_id": obligation_id,
        "predicate_id": predicate_id,
        "claim": claim,
        "adapter_version": "proofnav.perception.micro-fixture.v1",
        "dependency_group": "micro-view-vp0",
        "audit_trail": {
            "producer": "tests.m1.fixtures",
            "source_field": "object_proposal_ids[0]",
        },
    }


def obligation(episode_id, obligation_id, hypothesis_id, predicate_id, status, evidence_ids):
    return {
        "schema_version": SCHEMA_VERSIONS["obligation"],
        "obligation_id": obligation_id,
        "episode_id": episode_id,
        "scope_contract_id": "scope-" + episode_id,
        "hypothesis_id": hypothesis_id,
        "predicate_id": predicate_id,
        "necessary": True,
        "status": status,
        "evidence_ids": list(evidence_ids),
        "audit_trail": {"producer": "tests.m1.fixtures"},
    }


def _costs(observation_count=1):
    return {
        "travel_distance_meters": 0.0,
        "high_level_actions": 0,
        "expanded_path_edges": 0,
        "observation_events": observation_count,
        "predicate_queries": observation_count,
        "online_compute_milliseconds": 0.1,
        "storage_bytes": 256,
        "offline_preprocessing_ref": "synthetic-micro-only",
    }


def _result(episode_id, decision, status, termination, certificate, risk, verifier, event_ids):
    return {
        "schema_version": SCHEMA_VERSIONS["result"],
        "instr_id": episode_id,
        "trajectory": [["vp0"]],
        "pred_objid": "obj-1" if decision == "FOUND" else None,
        "semantic_decision": decision,
        "decision_status": status,
        "termination": {
            "cause": termination,
            "execution_stopped": True,
            "duet_flags": {
                "duet_stop": termination == "duet_stop",
                "no_frontier": termination == "no_frontier",
                "max_step": termination == "max_step",
            },
        },
        "certificate": certificate,
        "online_verifier": verifier,
        "scope_contract_id": "scope-" + episode_id,
        "risk_claim": risk,
        "budget_status": {
            "within_budget": termination != "budget",
            "exhausted_resources": ["steps"] if termination == "budget" else [],
        },
        "cost_ledger": _costs(),
        "audit_trail": {
            "producer": "tests.m1.fixtures",
            "source_versions": {
                "duet": "main@93e8b233",
                "m0_trace": "m0.runtime.v1",
                "proofnav_contracts": SCHEMA_VERSIONS["result"],
            },
            "event_ids": list(event_ids),
        },
    }


def found_example():
    episode_id = "micro-found"
    event_id = "obs-found-0"
    obs = observation(episode_id, event_id)
    item = evidence(
        episode_id, "ev-found", event_id, "obl-entity", "pred-entity", "SUPPORTS",
    )
    obl = obligation(
        episode_id, "obl-entity", "hyp-entity", "pred-entity", "SUPPORTED", ["ev-found"],
    )
    cert = {
        "schema_version": SCHEMA_VERSIONS["certificate"],
        "certificate_id": "cert-found",
        "certificate_type": "positive",
        "episode_id": episode_id,
        "scope_contract_id": "scope-" + episode_id,
        "entity_binding": {"entity_id": "obj-1", "binding_event_id": event_id},
        "true_path": [{
            "obligation_id": "obl-entity",
            "predicate_id": "pred-entity",
            "evidence_ids": ["ev-found"],
        }],
        "unresolved_obligation_ids": [],
        "audit_trail": {
            "producer": "tests.m1.fixtures",
            "source_versions": {
                "observation": SCHEMA_VERSIONS["observation"],
                "evidence": SCHEMA_VERSIONS["evidence"],
                "scope": SCHEMA_VERSIONS["scope"],
                "obligation": SCHEMA_VERSIONS["obligation"],
            },
            "event_ids": [event_id],
        },
    }
    risk = {
        "decision": "FOUND",
        "risk_type": "false_found",
        "upper_bound": 0.02,
        "budget": 0.05,
        "calibration_version": "proofnav.calibration.micro.v1",
        "composition_version": "proofnav.composition.micro.v1",
    }
    result = _result(
        episode_id, "FOUND", "VERIFIED", "verifier_accept", cert, risk,
        {"accepted": True, "reason_codes": [], "remaining_obligation_ids": []},
        [event_id],
    )
    context = {
        "scope": scope(episode_id, ["hyp-entity"]),
        "obligations": [obl],
        "evidence": [item],
        "observations": [obs],
    }
    return result, context


def not_found_example():
    episode_id = "micro-not-found"
    event_id = "obs-not-found-0"
    obs = observation(episode_id, event_id)
    evidence_items = [
        evidence(episode_id, "ev-refute-a", event_id, "obl-a", "pred-a", "REFUTES"),
        evidence(episode_id, "ev-refute-b", event_id, "obl-b", "pred-b", "REFUTES"),
    ]
    obligations = [
        obligation(episode_id, "obl-a", "hyp-a", "pred-a", "REFUTED", ["ev-refute-a"]),
        obligation(episode_id, "obl-b", "hyp-b", "pred-b", "REFUTED", ["ev-refute-b"]),
    ]
    cert = {
        "schema_version": SCHEMA_VERSIONS["certificate"],
        "certificate_id": "cert-not-found",
        "certificate_type": "refutation_cover",
        "episode_id": episode_id,
        "scope_contract_id": "scope-" + episode_id,
        "hypothesis_index": ["hyp-a", "hyp-b"],
        "refutation_cover": [
            {
                "hypothesis_id": "hyp-a", "obligation_id": "obl-a",
                "predicate_id": "pred-a", "evidence_ids": ["ev-refute-a"],
            },
            {
                "hypothesis_id": "hyp-b", "obligation_id": "obl-b",
                "predicate_id": "pred-b", "evidence_ids": ["ev-refute-b"],
            },
        ],
        "uncovered_hypothesis_ids": [],
        "frontier_unresolved": [],
        "audit_trail": {
            "producer": "tests.m1.fixtures",
            "source_versions": {
                "observation": SCHEMA_VERSIONS["observation"],
                "evidence": SCHEMA_VERSIONS["evidence"],
                "scope": SCHEMA_VERSIONS["scope"],
                "obligation": SCHEMA_VERSIONS["obligation"],
            },
            "event_ids": [event_id],
        },
    }
    risk = {
        "decision": "NOT_FOUND",
        "risk_type": "false_not_found",
        "upper_bound": 0.03,
        "budget": 0.05,
        "calibration_version": "proofnav.calibration.micro.v1",
        "composition_version": "proofnav.composition.micro.v1",
    }
    result = _result(
        episode_id, "NOT_FOUND", "VERIFIED", "verifier_accept", cert, risk,
        {"accepted": True, "reason_codes": [], "remaining_obligation_ids": []},
        [event_id],
    )
    context = {
        "scope": scope(episode_id, ["hyp-a", "hyp-b"]),
        "obligations": obligations,
        "evidence": evidence_items,
        "observations": [obs],
    }
    return result, context


def unresolved_example(cause="no_frontier"):
    episode_id = "micro-unresolved"
    event_id = "obs-unresolved-0"
    obs = observation(episode_id, event_id)
    obl = obligation(episode_id, "obl-open", "hyp-open", "pred-open", "OPEN", [])
    result = _result(
        episode_id, None, "UNRESOLVED", cause, None, None,
        {
            "accepted": False,
            "reason_codes": ["OPEN_OBLIGATION"],
            "remaining_obligation_ids": ["obl-open"],
        },
        [event_id],
    )
    context = {
        "scope": scope(episode_id, ["hyp-open"]),
        "obligations": [obl],
        "evidence": [],
        "observations": [obs],
    }
    return result, context


def _predicate(predicate_id, kind, subject, arguments):
    return {
        "predicate_id": predicate_id,
        "kind": kind,
        "subject": subject,
        "operator": "satisfies",
        "arguments": arguments,
    }


def paired_case(premise_class, index=0, split="val_unseen"):
    specifications = {
        "entity_absent": (
            "entity", "chair", "unicorn",
            {"entity": "chair", "existence": "present"},
            {"entity": "unicorn", "existence": "absent"},
        ),
        "attribute_mismatch": (
            "attribute", "red chair", "blue chair",
            {"entity": "chair", "attribute": "red"},
            {"entity": "chair", "attribute": "blue"},
        ),
        "relation_mismatch": (
            "relation", "chair left of the table", "chair right of the table",
            {"entity": "chair", "relation": "left_of", "anchor": "table"},
            {"entity": "chair", "relation": "right_of", "anchor": "table"},
        ),
        "room_anchor_mismatch": (
            "room_anchor", "chair in the kitchen", "chair in the hallway",
            {"entity": "chair", "room_anchor": "kitchen"},
            {"entity": "chair", "room_anchor": "hallway"},
        ),
    }
    kind, clean_target, false_target, clean_args, false_args = specifications[premise_class]
    pair_id = "pair-%s-%d" % (premise_class, index)
    scene_id = "micro-scene-%s-%d" % (premise_class, index)
    template_id = "micro-template-%s" % premise_class
    scope_id = "micro-scope-%s-%d" % (premise_class, index)
    changed_id = "pred-target"
    clean_predicate = _predicate(changed_id, kind, "target", clean_args)
    false_predicate = _predicate(changed_id, kind, "target", false_args)
    context_predicate = _predicate(
        "pred-context", "relation", "table", {"relation": "near", "anchor": "start"},
    )
    template = {"template_id": template_id, "text": "Find the {target}."}
    opportunity_hash = canonical_sha256({"scene": scene_id, "start": "vp0", "scope": scope_id})
    context_hash = canonical_sha256({"scene": scene_id, "non_target": "matched"})

    def member(role, target, predicate, truth):
        record_id = "%s-%s" % (pair_id, role)
        source_hash = canonical_sha256({"record": record_id, "truth": truth})
        return {
            "member_id": record_id,
            "agent_visible": {
                "episode_id": record_id,
                "scene_id": scene_id,
                "start_viewpoint": "vp0",
                "instruction": template["text"].format(target=target),
                "template_id": template_id,
                "template_slots": {"target": target},
                "predicates": [predicate, copy.deepcopy(context_predicate)],
                "scope_contract_id": scope_id,
            },
            "evaluator_only": {
                "semantic_truth": truth,
                "split": split,
                "truth_source": {
                    "source_kind": "synthetic_micro_fixture",
                    "artifact_id": "tests.m1.fixtures",
                    "record_id": record_id,
                    "field_paths": ["semantic_truth", "predicates.pred-target"],
                    "content_sha256": source_hash,
                },
                "reachability": {
                    "start_in_scope": True,
                    "navigation_opportunity_hash": opportunity_hash,
                    "target_condition_reachable": truth == "FOUND",
                    "audit_ref": "synthetic-reachability-audit:%s" % pair_id,
                },
                "non_target_conditions": {
                    "matched": True,
                    "context_hash": context_hash,
                    "audit_ref": "synthetic-context-audit:%s" % pair_id,
                },
            },
        }

    pair = {
        "schema_version": SCHEMA_VERSIONS["pair"],
        "pair_id": pair_id,
        "premise_class": premise_class,
        "split": split,
        "instruction_template": template,
        "members": {
            "clean": member("clean", clean_target, clean_predicate, "FOUND"),
            "false": member("false", false_target, false_predicate, "NOT_FOUND"),
        },
        "changed_premise_audit": {
            "premise_class": premise_class,
            "predicate_id": changed_id,
            "changed_slot": "target",
            "before": clean_predicate,
            "after": false_predicate,
            "auditor": "synthetic-micro-auditor",
            "review_status": "reviewed",
        },
        "deduplication": {
            "canonical_sha256": "0" * 64,
            "near_duplicate_group": None,
        },
        "audit_trail": {
            "producer": "tests.m1.fixtures",
            "source_versions": {"pair_contract": SCHEMA_VERSIONS["pair"]},
            "events": ["created", "reviewed"],
        },
    }
    pair["deduplication"]["canonical_sha256"] = pair_fingerprint(pair)
    return pair


def all_paired_cases():
    return [
        paired_case("entity_absent", 0),
        paired_case("attribute_mismatch", 1),
        paired_case("relation_mismatch", 2),
        paired_case("room_anchor_mismatch", 3),
    ]


def m0_minimal_trace():
    header = {
        "trace_schema_version": "m0.runtime.v1",
        "run_id": "micro-run",
        "episode_index": 0,
        "instr_id": "micro-trace",
    }

    def event(seq, step, event_type, payload):
        value = dict(header)
        value.update({"event_seq": seq, "step": step, "event_type": event_type})
        if seq:
            value["causal_parent_seq"] = seq - 1
        value.update(payload)
        return value

    return [
        event(0, 0, "observation", {
            "observation_index": 0,
            "viewpoint": "vp0",
            "candidate_schema": [{
                "viewpoint_id": "vp1",
                "evidence_role": "unobserved_navigation_proposal",
                "candidate_distance_present": True,
                "candidate_distance_semantics": "angular_representative_selection_only",
            }],
        }),
        event(1, 0, "model_scores", {
            "local": {"action_ids": [None, "vp1"], "valid_mask": [True, True], "logits": [0.0, 1.0]},
            "global": {"action_ids": [None, "vp1"], "valid_mask": [True, True], "logits": [0.0, 1.0]},
            "fused": {"action_ids": [None, "vp1"], "valid_mask": [True, True], "logits": [0.0, 1.0]},
        }),
        event(2, 0, "action", {
            "selected_branch": "fused", "selected_index": 1,
            "selected_high_level_action": "vp1",
        }),
        event(3, 0, "termination", {
            "selected_trigger": None, "environment_action_is_none": False,
        }),
        event(4, 0, "execution", {
            "expanded_path": ["mid", "vp1"],
            "travel_only_nodes": ["mid"],
            "observation_endpoint": "vp1",
            "next_observation_index": 1,
        }),
        event(5, 1, "observation", {
            "observation_index": 1,
            "viewpoint": "vp1",
            "candidate_schema": [],
        }),
        event(6, 1, "prediction", {
            "trajectory": [["vp0"], ["mid", "vp1"]], "pred_objid": None,
        }),
    ]
