"""Synthetic M2 micro fixtures.  They are contracts, not benchmark records."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256
from proofnav.offline import ControlledProofState, OracleEvidenceProvider
from tests.m1.fixtures import obligation, observation, scope


def cost_ledger(observation_count=1, query_count=0):
    return {
        "travel_distance_meters": 0.0,
        "high_level_actions": 0,
        "expanded_path_edges": 0,
        "observation_events": observation_count,
        "predicate_queries": query_count,
        "online_compute_milliseconds": 0.1,
        "storage_bytes": 256,
        "offline_preprocessing_ref": "synthetic-m2-only",
    }


def budget_status(steps=1, observations=1, queries=0, within=True,
                  exhausted=None):
    return {
        "steps_used": steps,
        "observation_events": observations,
        "predicate_queries": queries,
        "within_budget": within,
        "exhausted_resources": list(exhausted or []),
    }


def risk_claims(scope_value, found_upper=0.01, not_upper=0.01):
    return {
        "FOUND": {
            "decision": "FOUND",
            "risk_type": "false_found",
            "upper_bound": found_upper,
            "budget": scope_value["risk_budgets"]["false_found"],
            "calibration_version": scope_value["calibration_version"],
            "composition_version": "proofnav.composition.controlled.v1",
        },
        "NOT_FOUND": {
            "decision": "NOT_FOUND",
            "risk_type": "false_not_found",
            "upper_bound": not_upper,
            "budget": scope_value["risk_budgets"]["false_not_found"],
            "calibration_version": scope_value["calibration_version"],
            "composition_version": "proofnav.composition.controlled.v1",
        },
    }


def scenario(premise_class="positive_control", semantic_truth="FOUND",
             hypothesis_ids=None, scope_closed=True, open_frontier=False,
             claims=None):
    hypothesis_ids = list(hypothesis_ids or ["hyp-a"])
    episode_id = "m2-%s-%s" % (premise_class, semantic_truth.lower())
    scope_value = scope(episode_id, hypothesis_ids)
    scope_value["resource_limits"] = {
        "max_steps": 20,
        "max_observation_events": 20,
        "max_predicate_queries": 20,
    }
    event_id = "obs-%s-0" % episode_id
    observations = [observation(episode_id, event_id)]
    obligations = [
        obligation(
            episode_id, "obl-%s" % hypothesis_id,
            hypothesis_id, "pred-%s-%s" % (premise_class, hypothesis_id),
            "OPEN", [],
        )
        for hypothesis_id in hypothesis_ids
    ]
    if claims is None:
        polarity = "SUPPORTS" if semantic_truth == "FOUND" else "REFUTES"
        claims = [
            {
                "obligation_id": item["obligation_id"],
                "claim": polarity,
                "source_event_id": event_id,
                "evidence_role": "object_slot",
                "unit_id": "vp0:object:%s" % item["hypothesis_id"],
            }
            for item in obligations
        ]
    supported = hypothesis_ids if semantic_truth == "FOUND" else []
    refuted = hypothesis_ids if semantic_truth == "NOT_FOUND" else []
    truth = {
        "schema_version": SCHEMA_VERSIONS["controlled_truth"],
        "episode_id": episode_id,
        "scope_contract_id": scope_value["scope_contract_id"],
        "scope_version": scope_value["provenance"]["version"],
        "scope_digest": canonical_sha256(scope_value),
        "semantic_truth": semantic_truth,
        "premise_class": premise_class,
        "hypothesis_ids": sorted(hypothesis_ids),
        "supported_hypothesis_ids": sorted(supported),
        "refuted_hypothesis_ids": sorted(refuted),
        "claims": copy.deepcopy(claims),
        "audit_trail": {
            "producer": "proofnav.offline.controlled_truth",
            "source_artifact_digest": canonical_sha256({
                "episode": episode_id,
                "premise_class": premise_class,
                "truth": semantic_truth,
                "claims": claims,
            }),
        },
    }
    frontier = []
    if open_frontier:
        frontier = [{
            "frontier_id": "frontier-0",
            "viewpoint_id": "vp-unobserved",
            "source_event_id": event_id,
            "kind": "graph_frontier",
        }]
    return {
        "scope": scope_value,
        "obligations": obligations,
        "observations": observations,
        "frontier_witnesses": frontier,
        "scope_closed": scope_closed,
        "budget_status": budget_status(),
        "cost_ledger": cost_ledger(),
        "risk_claims": risk_claims(scope_value),
        "truth": truth,
    }


def controlled_state(bundle, evidence=None):
    state = ControlledProofState(
        bundle["scope"], bundle["obligations"], bundle["observations"],
        bundle["frontier_witnesses"], bundle["scope_closed"],
        bundle["budget_status"], bundle["cost_ledger"], bundle["risk_claims"],
    )
    if evidence is None:
        provider = OracleEvidenceProvider(
            bundle["scope"], bundle["obligations"], bundle["observations"],
        )
        evidence = provider.emit(bundle["truth"])
    for item in evidence:
        state.append_evidence(item)
    return state


def controlled_evidence(bundle):
    return OracleEvidenceProvider(
        bundle["scope"], bundle["obligations"], bundle["observations"],
    ).emit(bundle["truth"])


def execution(**overrides):
    value = {
        "duet_stop": False,
        "no_frontier": False,
        "max_step": False,
        "budget_exhausted": False,
        "executable_action_available": True,
        "searchable_frontier": True,
        "execution_error": False,
    }
    value.update(overrides)
    return value


def reseal(certificate):
    value = copy.deepcopy(certificate)
    value.pop("certificate_id", None)
    value.pop("certificate_digest", None)
    value["certificate_digest"] = canonical_sha256(value)
    value["certificate_id"] = "cert-" + value["certificate_digest"][:20]
    return value
