"""Synthetic M2.1 event-sourced fixtures; never benchmark records."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256
from proofnav.offline.oracle_evidence import (
    ControlledProofState,
    OracleEvidenceProvider,
    seal_controlled_artifact,
    validate_controlled_truth,
)
from proofnav.runtime.semantics import (
    CONTROLLED_IDENTITY_WITNESS_PRODUCER,
    CONTROLLED_IDENTITY_WITNESS_SOURCE_SCHEMA,
    CONTROLLED_INTERFACE_AUDIT_REF,
    PRODUCTION_INTERFACE_AUDIT_REF,
    RESIDUAL_HYPOTHESIS_KINDS,
    location_binding_id,
    object_unit_id,
    view_unit_id,
)
from tests.m1.fixtures import observation as m1_observation
from tests.m1.fixtures import scope as m1_scope


def risk_claims(scope_value, found_upper=0.01, not_upper=0.01):
    return {
        "FOUND": {
            "decision": "FOUND",
            "risk_type": "false_found",
            "upper_bound": found_upper,
            "budget": scope_value["risk_budgets"]["false_found"],
            "calibration_version": scope_value["calibration_version"],
            "composition_version": "proofnav.composition.controlled.v2",
        },
        "NOT_FOUND": {
            "decision": "NOT_FOUND",
            "risk_type": "false_not_found",
            "upper_bound": not_upper,
            "budget": scope_value["risk_budgets"]["false_not_found"],
            "calibration_version": scope_value["calibration_version"],
            "composition_version": "proofnav.composition.controlled.v2",
        },
    }


def scope_value(episode_id="m21-episode", production=False, limits=None):
    value = m1_scope(episode_id, ["m1-placeholder-not-m2-authority"])
    value["domain"]["interface_audit_ref"] = (
        PRODUCTION_INTERFACE_AUDIT_REF
        if production else CONTROLLED_INTERFACE_AUDIT_REF
    )
    value["provenance"]["version"] = "m2.1-v2"
    value["audit_trail"]["change_log"].append(
        "M2.1 uses an event-derived dynamic universe; M1 IDs are ignored"
    )
    value["resource_limits"] = copy.deepcopy(limits or {
        "max_steps": 20,
        "max_observation_events": 20,
        "max_predicate_queries": 40,
    })
    return value


def proof_template(premise_class="positive_control"):
    kinds = {
        "positive_control": ("entity",),
        "entity_absent": ("entity",),
        "attribute_mismatch": ("entity", "attribute"),
        "relation_mismatch": ("entity", "relation"),
        "room_anchor_mismatch": ("entity", "room_anchor"),
    }[premise_class]
    predicates = []
    for kind in kinds:
        predicates.append({
            "predicate_id": "pred-%s-%s" % (premise_class, kind),
            "kind": kind,
            "necessary": True,
            "anchor_role": "reference-object" if kind == "relation" else None,
            "spatial_anchor_id": "instruction-room:kitchen" if kind == "room_anchor" else None,
        })
    return {
        "schema_version": SCHEMA_VERSIONS["proof_template"],
        "template_id": "template-" + premise_class,
        "generator_version": "proofnav.dynamic-universe.v2",
        "target_role": "target-object",
        "predicates": predicates,
        "audit_trail": {
            "producer": "tests.m2.fixtures.proof_template",
            "source_instruction_digest": canonical_sha256("Find the micro target."),
        },
    }


def _candidate(viewpoint_id, position):
    return {
        "viewpoint_id": viewpoint_id,
        "point_id": 12,
        "heading": 0.0,
        "elevation": 0.0,
        "position": [float(position), 0.0, 0.0],
        "simulator_index": 1,
        "feature_schema": {"shape": [772], "dtype": "float32"},
        "evidence_role": "unobserved_navigation_proposal",
    }


def controlled_observation(episode_id, viewpoint="vp0", event_seq=0, step=0,
                           candidates=None, object_ids=None, event_id=None):
    value = m1_observation(
        episode_id, event_id or "obs-%s-%d" % (viewpoint, event_seq),
        event_seq=event_seq, step=step, viewpoint=viewpoint,
    )
    coordinate = {"vp0": 0.0, "vp1": 1.0, "vp2": 2.0}.get(viewpoint, float(step))
    value["pose"]["position"] = [coordinate, 0.0, 0.0]
    value["candidates"] = [
        _candidate(target, {"vp0": 0, "vp1": 1, "vp2": 2}.get(target, index + 1))
        for index, target in enumerate(candidates or [])
    ]
    value["object_proposal_ids"] = list(object_ids or [])
    object_count = len(value["object_proposal_ids"])
    value["field_schema"]["obj_img_fts"]["shape"] = [object_count, 768]
    value["field_schema"]["obj_ang_fts"]["shape"] = [object_count, 4]
    value["field_schema"]["obj_box_fts"]["shape"] = [object_count, 3]
    value["audit_trail"] = {
        "producer": "proofnav.offline.controlled_replay",
        "source_schema": "proofnav.controlled-observation.v2",
    }
    return value


def production_observation(episode_id, candidates=None, object_ids=None):
    value = controlled_observation(
        episode_id, candidates=candidates, object_ids=object_ids,
    )
    value["audit_trail"] = {
        "producer": "proofnav.adapters.sanitize_duet_observation",
        "source_schema": "duet.reverie._get_obs@frozen-m0",
    }
    return value


def graph_observations(episode_id, graph="closed_one", object_ids=None):
    objects = object_ids or {"vp0": ["target"], "vp1": [], "vp2": []}
    if graph == "closed_one":
        layout = [("vp0", 0, 0, [])]
    elif graph == "open_two":
        layout = [("vp0", 0, 0, ["vp1"])]
    elif graph == "closed_two":
        layout = [("vp0", 0, 0, ["vp1"]), ("vp1", 5, 1, ["vp0"])]
    elif graph == "closed_three":
        layout = [
            ("vp0", 0, 0, ["vp1"]),
            ("vp1", 5, 1, ["vp0", "vp2"]),
            ("vp2", 9, 2, ["vp1"]),
        ]
    else:
        raise ValueError("unknown graph fixture")
    return [
        controlled_observation(
            episode_id, viewpoint, event_seq, step, candidates,
            objects.get(viewpoint, []),
        )
        for viewpoint, event_seq, step, candidates in layout
    ]


def empty_state(premise_class="positive_control", episode_id=None,
                production=False, limits=None):
    episode_id = episode_id or "m21-%s" % premise_class
    scope = scope_value(episode_id, production=production, limits=limits)
    template = proof_template(premise_class)
    if production:
        from proofnav.runtime import ProofState
        state = ProofState(scope, template, risk_claims(scope))
    else:
        state = ControlledProofState(scope, template, risk_claims(scope))
    return state, scope, template


def state_with_graph(premise_class="positive_control", graph="closed_one",
                     object_ids=None, episode_id=None, limits=None):
    state, scope, template = empty_state(
        premise_class, episode_id=episode_id, limits=limits,
    )
    observations = graph_observations(
        scope["episode_id"], graph=graph, object_ids=object_ids,
    )
    for observation in observations:
        state.ingest_observation(observation)
    return state, scope, template, observations


def controlled_identity_witness(state, left_unit_id, right_unit_id):
    """Build a canonical test-only witness from admitted observations."""

    bundle = state.audit_bundle()
    observations = [
        item["payload"] for item in bundle["transitions"]
        if item["event_type"] == "OBSERVATION"
    ]
    endpoints = []
    for unit_id in (left_unit_id, right_unit_id):
        source = next(
            observation for observation in observations
            if unit_id in {
                object_unit_id(observation["viewpoint"], object_id)
                for object_id in observation["object_proposal_ids"]
            }
        )
        endpoints.append({
            "unit_id": unit_id,
            "viewpoint_id": source["viewpoint"],
            "source_event_id": source["event_id"],
            "source_observation_digest": canonical_sha256(source),
        })
    profile = bundle["admission_profile"]
    witness = {
        "schema_version": SCHEMA_VERSIONS["identity_witness"],
        "claim": "SAME_ENTITY",
        "endpoints": sorted(endpoints, key=lambda item: item["unit_id"]),
        "audit_trail": {
            "producer": CONTROLLED_IDENTITY_WITNESS_PRODUCER,
            "source_schema": CONTROLLED_IDENTITY_WITNESS_SOURCE_SCHEMA,
            "observation_producer": profile["observation_producer"],
            "observation_source_schema": profile["observation_source_schema"],
            "interface_audit_ref": profile["interface_audit_ref"],
        },
    }
    witness["witness_id"] = "identity-" + canonical_sha256(witness)[:24]
    return witness


def _observation_for_binding(state, obligation):
    bundle = state.audit_bundle()
    observations = [
        item["payload"] for item in bundle["transitions"]
        if item["event_type"] == "OBSERVATION"
    ]
    binding = obligation["binding_requirement"]
    if obligation["predicate_kind"] == "coverage":
        for observation in observations:
            if location_binding_id(observation["viewpoint"]) == binding["location_binding_id"]:
                return observation, view_unit_id(observation["viewpoint"]), "viewpoint_view"
    for observation in observations:
        units = {
            object_unit_id(observation["viewpoint"], object_id)
            for object_id in observation["object_proposal_ids"]
        }
        subject = sorted(units & set(binding["subject_unit_ids"]))
        anchor = units & set(binding["anchor_unit_ids"])
        if subject and (obligation["predicate_kind"] != "relation" or anchor):
            return observation, subject[0], "object_slot"
    raise AssertionError("fixture cannot locate a source observation for binding")


def emit_evaluations(state, evaluations, emission_prefix="emission"):
    """Register queries and emit selected SUPPORTS/REFUTES wrappers.

    ``evaluations`` maps current obligation IDs to binary claims.  OPEN truth
    evaluations are not emitted.
    """

    current = {item["obligation_id"]: item for item in state.snapshot()["obligations"]}
    emissions = []
    for index, (obligation_id, claim) in enumerate(sorted(evaluations.items())):
        obligation = current[obligation_id]
        query = state.register_query(obligation["hypothesis_id"], obligation_id)
        observation, unit_id, role = _observation_for_binding(state, obligation)
        emissions.append({
            "emission_id": "%s-%d" % (emission_prefix, index),
            "query_id": query["query_id"],
            "hypothesis_id": obligation["hypothesis_id"],
            "obligation_id": obligation_id,
            "predicate_id": obligation["predicate_id"],
            "predicate_kind": obligation["predicate_kind"],
            "binding": copy.deepcopy(obligation["binding_requirement"]),
            "source_event_id": observation["event_id"],
            "evidence_role": role,
            "unit_id": unit_id,
            "claim": claim,
        })
    bundle = state.audit_bundle()
    script = {
        "schema_version": SCHEMA_VERSIONS["controlled_script"],
        "script_id": "script-" + canonical_sha256(emissions)[:20],
        "episode_id": bundle["scope"]["episode_id"],
        "scope_contract_id": bundle["scope"]["scope_contract_id"],
        "scope_version": bundle["scope"]["provenance"]["version"],
        "scope_digest": canonical_sha256(bundle["scope"]),
        "template_id": bundle["template"]["template_id"],
        "template_digest": canonical_sha256(bundle["template"]),
        "universe_digest": bundle["state"]["universe_digest"],
        "emissions": emissions,
        "audit_trail": {
            "producer": "proofnav.offline.controlled_evidence_script.v2",
            "source_artifact_digest": "",
        },
    }
    script = seal_controlled_artifact(script)
    wrappers = OracleEvidenceProvider(
        bundle["scope"], bundle["template"],
    ).emit(script, state.audit_bundle())
    return script, wrappers


def append_evaluations(state, evaluations, emission_prefix="emission"):
    script, wrappers = emit_evaluations(
        state, evaluations, emission_prefix=emission_prefix,
    )
    for wrapper in wrappers:
        state.append_evidence(wrapper)
    return script, wrappers


def truth_artifact(state, premise_class, evaluations, semantic_truth=None):
    snapshot = state.snapshot()
    bundle = state.audit_bundle()
    hypotheses = copy.deepcopy(snapshot["hypotheses"])
    obligations = [{
        key: copy.deepcopy(item[key]) for key in (
            "obligation_id", "hypothesis_id", "predicate_id",
            "predicate_kind", "necessary", "binding_requirement",
        )
    } for item in snapshot["obligations"]]
    claims = []
    for obligation in obligations:
        claims.append({
            "hypothesis_id": obligation["hypothesis_id"],
            "obligation_id": obligation["obligation_id"],
            "predicate_id": obligation["predicate_id"],
            "predicate_kind": obligation["predicate_kind"],
            "binding": copy.deepcopy(obligation["binding_requirement"]),
            "claim": evaluations.get(obligation["obligation_id"], "OPEN"),
        })
    by_hypothesis = {}
    for obligation in obligations:
        if obligation["necessary"]:
            by_hypothesis.setdefault(obligation["hypothesis_id"], []).append(obligation)
    hypothesis_by_id = {item["hypothesis_id"]: item for item in hypotheses}
    supported, refuted = [], []
    claim_by_obligation = {item["obligation_id"]: item["claim"] for item in claims}
    for hypothesis_id, necessary in by_hypothesis.items():
        polarities = [claim_by_obligation[item["obligation_id"]] for item in necessary]
        if (all(item == "SUPPORTS" for item in polarities)
                and hypothesis_by_id[hypothesis_id]["hypothesis_kind"]
                not in RESIDUAL_HYPOTHESIS_KINDS):
            supported.append(hypothesis_id)
        elif any(item == "REFUTES" for item in polarities):
            refuted.append(hypothesis_id)
    derived = "FOUND" if supported else (
        "NOT_FOUND" if set(refuted) == set(hypothesis_by_id) else None
    )
    value = {
        "schema_version": SCHEMA_VERSIONS["controlled_truth"],
        "episode_id": snapshot["episode_id"],
        "scope_contract_id": snapshot["scope_contract_id"],
        "scope_version": snapshot["scope_version"],
        "scope_digest": snapshot["scope_digest"],
        "template_id": snapshot["template_id"],
        "template_digest": snapshot["template_digest"],
        "universe_digest": snapshot["universe_digest"],
        "premise_class": premise_class,
        "semantic_truth": semantic_truth or derived,
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
    value = seal_controlled_artifact(value)
    validate_controlled_truth(value)
    # Keep the unused local visible to readers: truth identity is intentionally
    # derived from the same frozen decision bundle, not from evaluator input.
    assert bundle["state"]["universe_digest"] == value["universe_digest"]
    return value


def evidence_plan(snapshot, verdict):
    hypotheses = {item["hypothesis_id"]: item for item in snapshot["hypotheses"]}
    by_hypothesis = {key: [] for key in hypotheses}
    for obligation in snapshot["obligations"]:
        if obligation["necessary"]:
            by_hypothesis[obligation["hypothesis_id"]].append(obligation)
    if verdict == "FOUND":
        selected = next(
            hypothesis_id for hypothesis_id in sorted(hypotheses)
            if hypotheses[hypothesis_id]["hypothesis_kind"]
            not in RESIDUAL_HYPOTHESIS_KINDS
        )
        return {
            item["obligation_id"]: "SUPPORTS"
            for item in by_hypothesis[selected]
        }
    template_id = snapshot["template_id"]
    changed_kind = {
        "template-entity_absent": "entity",
        "template-attribute_mismatch": "attribute",
        "template-relation_mismatch": "relation",
        "template-room_anchor_mismatch": "room_anchor",
        # Used only by the factual-error script test; hidden truth is built
        # separately as FOUND.
        "template-positive_control": "entity",
    }[template_id]
    evaluations = {}
    for hypothesis_id in sorted(hypotheses):
        hypothesis = hypotheses[hypothesis_id]
        necessary = by_hypothesis[hypothesis_id]
        if hypothesis["hypothesis_kind"] in RESIDUAL_HYPOTHESIS_KINDS:
            coverage = next(
                item for item in necessary
                if item["predicate_kind"] == "coverage"
            )
            evaluations[coverage["obligation_id"]] = "REFUTES"
            continue
        changed = next((
            item for item in necessary
            if item["predicate_kind"] == changed_kind
        ), None)
        if changed is None:
            # This is only reachable for a deliberately unusual controlled
            # template; pick one real necessary predicate rather than treating
            # an opaque obligation ID as semantic authority.
            changed = sorted(
                necessary, key=lambda item: item["obligation_id"],
            )[0]
        for obligation in necessary:
            evaluations[obligation["obligation_id"]] = (
                "REFUTES" if obligation is changed else "SUPPORTS"
            )
    return evaluations


def complete_scenario(premise_class="positive_control", verdict="FOUND",
                      graph="closed_one", episode_id=None):
    if premise_class == "relation_mismatch":
        objects = {"vp0": ["subject", "anchor"], "vp1": [], "vp2": []}
    elif premise_class == "entity_absent" and verdict == "NOT_FOUND":
        objects = {"vp0": [], "vp1": [], "vp2": []}
    else:
        objects = {"vp0": ["target"], "vp1": [], "vp2": []}
    state, scope, template, observations = state_with_graph(
        premise_class, graph=graph, object_ids=objects, episode_id=episode_id,
    )
    evaluations = evidence_plan(state.snapshot(), verdict)
    script, wrappers = append_evaluations(state, evaluations)
    truth = truth_artifact(state, premise_class, evaluations, semantic_truth=verdict)
    return {
        "state": state,
        "scope": scope,
        "template": template,
        "observations": observations,
        "evaluations": evaluations,
        "script": script,
        "wrappers": wrappers,
        "truth": truth,
    }


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
