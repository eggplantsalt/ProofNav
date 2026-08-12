"""Canonical M2.1 event-folding and typed-binding semantics.

This module contains deterministic contract primitives.  Runtime state and the
online verifier both fold raw transition records through these primitives; the
offline auditor intentionally has its own structural implementation and never
imports this module.
"""

import copy
import math

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_json, canonical_sha256
from proofnav.validation import validate_evidence, validate_observation, validate_scope


PREDICATE_KINDS = frozenset(("entity", "attribute", "relation", "room_anchor"))
RESIDUAL_HYPOTHESIS_KINDS = frozenset((
    "location_residual", "anchor_residual",
))
TRANSITION_TYPES = frozenset((
    "OBSERVATION", "IDENTITY_LINK", "QUERY", "EVIDENCE", "REVOKE", "CONTINUE",
))
PRODUCTION_INTERFACE_AUDIT_REF = (
    "m0.offline_adjacency.v1:sha256:"
    "2d2cf87d402b7d6e7283bf86c5da56cacd49312359d367c8c5d6234dbe9b47b8"
)
CONTROLLED_INTERFACE_AUDIT_REF = "m0.offline_adjacency.v1:micro"
CONTROLLED_IDENTITY_WITNESS_PRODUCER = (
    "proofnav.offline.controlled_identity_witness.v1"
)
CONTROLLED_IDENTITY_WITNESS_SOURCE_SCHEMA = (
    "proofnav.controlled-identity-witness.v1"
)
M3_ENTITY_SUPPORT_PROFILE_ID = "proofnav.admission.m3-entity-support.v1"

_CONTINUE_TERMINAL_FIELDS = {
    "schema_version", "directive", "terminal", "semantic_verdict", "cause",
    "proposed_verdict", "proposed_certificate_id",
    "proposed_certificate_digest", "accepted_certificate_id",
    "accepted_certificate_digest", "decision_cut", "transition_tip",
    "proof_state_digest", "certificate_accepted", "online_verification",
    "feedback", "duet_signal",
}
_CONTINUE_ONLINE_FIELDS = {
    "schema_version", "status", "accepted", "requested_verdict",
    "reason_codes", "missing_obligation_ids", "uncovered_hypothesis_ids",
    "frontier_viewpoint_ids", "scope_digest", "template_digest",
    "universe_digest", "binding_digest", "decision_cut", "transition_tip",
    "proof_state_digest", "certificate_id", "certificate_digest",
    "calculated_certificate_digest", "structured_feedback",
}
_CONTINUE_FEEDBACK_FIELDS = {
    "recommended_action", "reason_codes", "missing_obligation_ids",
    "uncovered_hypothesis_ids", "frontier_viewpoint_ids",
}
_CONTINUE_EXECUTION_FIELDS = {
    "duet_stop", "no_frontier", "max_step", "budget_exhausted",
    "executable_action_available", "searchable_frontier", "execution_error",
}


def registered_admission_profile(controlled=False, m3=False):
    """Return a code-owned profile; callers cannot register aliases."""

    if controlled and m3:
        fail(
            "ADMISSION_PROFILE_MODE", "$.admission_profile",
            "controlled replay and M3 production admission are disjoint",
        )
    if controlled:
        return {
            "profile_id": "proofnav.admission.controlled-replay.v2",
            "observation_producer": "proofnav.offline.controlled_replay",
            "observation_source_schema": "proofnav.controlled-observation.v2",
            "interface_audit_ref": CONTROLLED_INTERFACE_AUDIT_REF,
            "evidence_mode": "controlled_replay",
            "identity_link_mode": "controlled_replay",
        }
    if m3:
        return {
            "profile_id": M3_ENTITY_SUPPORT_PROFILE_ID,
            "observation_producer": "proofnav.adapters.sanitize_duet_observation",
            "observation_source_schema": "duet.reverie._get_obs@frozen-m0",
            "interface_audit_ref": PRODUCTION_INTERFACE_AUDIT_REF,
            "evidence_mode": "m3_entity_support",
            "identity_link_mode": "production_zero",
        }
    return {
        "profile_id": "proofnav.admission.production-zero.v2",
        "observation_producer": "proofnav.adapters.sanitize_duet_observation",
        "observation_source_schema": "duet.reverie._get_obs@frozen-m0",
        "interface_audit_ref": PRODUCTION_INTERFACE_AUDIT_REF,
        "evidence_mode": "production_zero",
        "identity_link_mode": "production_zero",
    }


def fail(code, location, message):
    raise ContractViolation(code, location, message)


def exact(value, fields, location, code="M21_UNKNOWN_FIELDS"):
    if not isinstance(value, dict):
        fail("TYPE_MAPPING", location, "expected an object")
    missing = sorted(set(fields) - set(value))
    if missing:
        fail("M21_MISSING_FIELDS", location, "missing %s" % missing)
    unknown = sorted(set(value) - set(fields))
    if unknown:
        fail(code, location, "unknown fields %s" % unknown)
    return value


def nonempty_string(value, location):
    if not isinstance(value, str) or not value:
        fail("TYPE_STRING", location, "expected a non-empty string")
    return value


def nullable_string(value, location):
    if value is not None:
        nonempty_string(value, location)
    return value


def string_list(value, location, unique=True):
    if not isinstance(value, list):
        fail("TYPE_LIST", location, "expected an array")
    for index, item in enumerate(value):
        nonempty_string(item, "%s[%d]" % (location, index))
    if unique and len(value) != len(set(value)):
        fail("DUPLICATE_VALUE", location, "values must be unique")
    return value


def validate_template(value):
    fields = {
        "schema_version", "template_id", "generator_version", "target_role",
        "predicates", "audit_trail",
    }
    value = exact(value, fields, "$.template")
    if value["schema_version"] != SCHEMA_VERSIONS["proof_template"]:
        fail("SCHEMA_VERSION", "$.template.schema_version", "proof-template v2 required")
    for key in ("template_id", "generator_version", "target_role"):
        nonempty_string(value[key], "$.template." + key)
    if value["generator_version"] != "proofnav.dynamic-universe.v2":
        fail("GENERATOR_VERSION", "$.template.generator_version", "unregistered generator")
    if not isinstance(value["predicates"], list) or not value["predicates"]:
        fail("TEMPLATE_PREDICATES", "$.template.predicates", "at least one predicate is required")
    predicate_ids = set()
    anchored_count = 0
    for index, predicate in enumerate(value["predicates"]):
        location = "$.template.predicates[%d]" % index
        predicate = exact(predicate, {
            "predicate_id", "kind", "necessary", "anchor_role", "spatial_anchor_id",
        }, location)
        nonempty_string(predicate["predicate_id"], location + ".predicate_id")
        if predicate["predicate_id"] in predicate_ids:
            fail("TEMPLATE_PREDICATE_DUPLICATE", location + ".predicate_id", "duplicate ID")
        predicate_ids.add(predicate["predicate_id"])
        if predicate["kind"] not in PREDICATE_KINDS:
            fail("TEMPLATE_PREDICATE_KIND", location + ".kind", "unsupported kind")
        if not isinstance(predicate["necessary"], bool):
            fail("TYPE_BOOLEAN", location + ".necessary", "expected boolean")
        nullable_string(predicate["anchor_role"], location + ".anchor_role")
        nullable_string(predicate["spatial_anchor_id"], location + ".spatial_anchor_id")
        if predicate["kind"] == "relation":
            anchored_count += 1
            if not predicate["necessary"]:
                fail(
                    "TEMPLATE_ANCHORED_NECESSARY", location + ".necessary",
                    "M2.1 anchored predicates must be necessary",
                )
            if predicate["anchor_role"] is None or predicate["spatial_anchor_id"] is not None:
                fail("TEMPLATE_RELATION_BINDING", location, "relation needs anchor_role only")
        elif predicate["kind"] == "room_anchor":
            anchored_count += 1
            if not predicate["necessary"]:
                fail(
                    "TEMPLATE_ANCHORED_NECESSARY", location + ".necessary",
                    "M2.1 anchored predicates must be necessary",
                )
            if predicate["spatial_anchor_id"] is None or predicate["anchor_role"] is not None:
                fail("TEMPLATE_ROOM_BINDING", location, "room_anchor needs spatial_anchor_id only")
        elif predicate["anchor_role"] is not None or predicate["spatial_anchor_id"] is not None:
            fail("TEMPLATE_BINDING", location, "entity/attribute cannot declare an anchor")
    if anchored_count > 1:
        fail(
            "TEMPLATE_ANCHORED_CARDINALITY", "$.template.predicates",
            "M2.1 supports at most one relation or room_anchor predicate",
        )
    if not any(item["necessary"] for item in value["predicates"]):
        fail("TEMPLATE_NECESSARY", "$.template.predicates", "a necessary predicate is required")
    audit = exact(value["audit_trail"], {"producer", "source_instruction_digest"}, "$.template.audit_trail")
    nonempty_string(audit["producer"], "$.template.audit_trail.producer")
    if not isinstance(audit["source_instruction_digest"], str) or len(audit["source_instruction_digest"]) != 64:
        fail("TEMPLATE_INSTRUCTION_DIGEST", "$.template.audit_trail.source_instruction_digest", "SHA-256 required")
    return value


def validate_admission_profile(value):
    fields = {
        "profile_id", "observation_producer", "observation_source_schema",
        "interface_audit_ref", "evidence_mode", "identity_link_mode",
    }
    value = exact(value, fields, "$.admission_profile")
    for key in fields - {"evidence_mode", "identity_link_mode"}:
        nonempty_string(value[key], "$.admission_profile." + key)
    if value["evidence_mode"] not in (
            "production_zero", "controlled_replay", "m3_entity_support"):
        fail("ADMISSION_EVIDENCE_MODE", "$.admission_profile.evidence_mode", "invalid mode")
    if value["identity_link_mode"] not in ("production_zero", "controlled_replay"):
        fail("ADMISSION_LINK_MODE", "$.admission_profile.identity_link_mode", "invalid mode")
    registered = (
        registered_admission_profile(True), registered_admission_profile(False),
        registered_admission_profile(m3=True),
    )
    if value not in registered:
        fail(
            "ADMISSION_PROFILE_NOT_CODE_OWNED", "$.admission_profile",
            "profile must exactly match a registered M2.1 boundary",
        )
    return value


def object_unit_id(viewpoint_id, object_id):
    return "objunit-" + canonical_sha256({
        "viewpoint_id": str(viewpoint_id), "object_proposal_id": str(object_id),
    })[:20]


def view_unit_id(viewpoint_id):
    return "viewunit-" + canonical_sha256({"viewpoint_id": str(viewpoint_id)})[:20]


def location_binding_id(viewpoint_id):
    return "loc-" + canonical_sha256({"viewpoint_id": str(viewpoint_id)})[:20]


def _subject_binding_id(unit_ids):
    return "subject-" + canonical_sha256({"subject_unit_ids": sorted(unit_ids)})[:20]


def _binding(subject_units, anchor_units, viewpoint_id, spatial_anchor_id):
    subject_units = sorted(subject_units)
    anchor_units = sorted(anchor_units)
    return {
        "subject_binding_id": _subject_binding_id(subject_units) if subject_units else None,
        "subject_unit_ids": subject_units,
        "anchor_binding_id": _subject_binding_id(anchor_units) if anchor_units else None,
        "anchor_unit_ids": anchor_units,
        "location_binding_id": location_binding_id(viewpoint_id),
        "spatial_anchor_id": spatial_anchor_id,
    }


def validate_binding(value, location="$.binding"):
    value = exact(value, {
        "subject_binding_id", "subject_unit_ids", "anchor_binding_id",
        "anchor_unit_ids", "location_binding_id", "spatial_anchor_id",
    }, location)
    nullable_string(value["subject_binding_id"], location + ".subject_binding_id")
    string_list(value["subject_unit_ids"], location + ".subject_unit_ids")
    nullable_string(value["anchor_binding_id"], location + ".anchor_binding_id")
    string_list(value["anchor_unit_ids"], location + ".anchor_unit_ids")
    nonempty_string(value["location_binding_id"], location + ".location_binding_id")
    nullable_string(value["spatial_anchor_id"], location + ".spatial_anchor_id")
    if bool(value["subject_binding_id"]) != bool(value["subject_unit_ids"]):
        fail("BINDING_SUBJECT", location, "subject ID and units must co-occur")
    if bool(value["anchor_binding_id"]) != bool(value["anchor_unit_ids"]):
        fail("BINDING_ANCHOR", location, "anchor ID and units must co-occur")
    if value["subject_unit_ids"] and value["subject_binding_id"] != _subject_binding_id(value["subject_unit_ids"]):
        fail("BINDING_SUBJECT_ID", location + ".subject_binding_id", "does not match units")
    if value["anchor_unit_ids"] and value["anchor_binding_id"] != _subject_binding_id(value["anchor_unit_ids"]):
        fail("BINDING_ANCHOR_ID", location + ".anchor_binding_id", "does not match units")
    return value


def _validate_observation_profile(observation, profile, location):
    validate_observation(observation)
    audit = observation["audit_trail"]
    if audit["producer"] != profile["observation_producer"]:
        fail("OBSERVATION_PRODUCER", location + ".audit_trail.producer", "unregistered producer")
    if audit["source_schema"] != profile["observation_source_schema"]:
        fail("OBSERVATION_SOURCE_SCHEMA", location + ".audit_trail.source_schema", "unregistered source schema")
    feature_shape = observation["field_schema"]["feature"]["shape"]
    if (len(feature_shape) != 2 or feature_shape[0] != 36
            or feature_shape[1] <= 0
            or observation["field_schema"]["feature"]["dtype"] != "float32"):
        fail(
            "OBSERVATION_PANORAMA_SCHEMA", location + ".field_schema.feature",
            "audited interface requires 36 x D float32 panorama features",
        )
    if not 0 <= observation["view_index"] < 36:
        fail("OBSERVATION_VIEW_INDEX", location + ".view_index", "expected [0,35]")
    for index, candidate in enumerate(observation["candidates"]):
        if not 0 <= candidate["point_id"] < 36:
            fail(
                "OBSERVATION_CANDIDATE_POINT",
                "%s.candidates[%d].point_id" % (location, index),
                "expected [0,35]",
            )
        if (candidate["feature_schema"]["shape"] != [feature_shape[1]]
                or candidate["feature_schema"]["dtype"] != "float32"):
            fail(
                "OBSERVATION_CANDIDATE_SCHEMA",
                "%s.candidates[%d].feature_schema" % (location, index),
                "candidate feature must match the panorama width",
            )
    object_ids = observation["object_proposal_ids"]
    if len(object_ids) != len(set(object_ids)):
        fail(
            "OBSERVATION_OBJECT_ID_DUPLICATE", location + ".object_proposal_ids",
            "object proposal IDs must be unique within an observation",
        )
    row_counts = []
    for name in ("obj_img_fts", "obj_ang_fts", "obj_box_fts"):
        shape = observation["field_schema"][name]["shape"]
        if not shape:
            fail(
                "OBSERVATION_OBJECT_SCHEMA", location + ".field_schema." + name,
                "object feature schema needs a row dimension",
            )
        row_counts.append(shape[0])
    if len(set(row_counts)) != 1 or row_counts[0] != len(object_ids):
        fail(
            "OBSERVATION_OBJECT_ENUMERATION", location + ".object_proposal_ids",
            "object IDs and all object feature row counts must agree",
        )
    expected_object_shapes = {
        "obj_img_fts": [len(object_ids), 768],
        "obj_ang_fts": [len(object_ids), 4],
        "obj_box_fts": [len(object_ids), 3],
    }
    if any(
            observation["field_schema"][name]["shape"] != expected
            or observation["field_schema"][name]["dtype"] != "float32"
            for name, expected in expected_object_shapes.items()):
        fail(
            "OBSERVATION_OBJECT_SCHEMA", location + ".field_schema",
            "object feature schemas must match the frozen DUET interface",
        )


def _validate_transition_chain(transitions):
    previous = "0" * 64
    for index, transition in enumerate(transitions):
        location = "$.transitions[%d]" % index
        transition = exact(transition, {
            "schema_version", "transition_seq", "event_type", "parent_transition_digest",
            "payload", "payload_digest", "transition_digest",
        }, location)
        if transition["schema_version"] != SCHEMA_VERSIONS["proof_transition"]:
            fail("SCHEMA_VERSION", location + ".schema_version", "proof-transition v2 required")
        if transition["transition_seq"] != index:
            fail("TRANSITION_SEQUENCE", location + ".transition_seq", "must be contiguous")
        if transition["event_type"] not in TRANSITION_TYPES:
            fail("TRANSITION_TYPE", location + ".event_type", "invalid transition type")
        if transition["parent_transition_digest"] != previous:
            fail("TRANSITION_PARENT", location + ".parent_transition_digest", "broken causal parent")
        if transition["payload_digest"] != canonical_sha256(transition["payload"]):
            fail("TRANSITION_PAYLOAD_DIGEST", location + ".payload_digest", "payload was modified")
        body = copy.deepcopy(transition)
        claimed = body.pop("transition_digest")
        if claimed != canonical_sha256(body):
            fail("TRANSITION_DIGEST", location + ".transition_digest", "transition was modified")
        previous = claimed
    return previous


def make_transition(transitions, event_type, payload):
    if event_type not in TRANSITION_TYPES:
        fail("TRANSITION_TYPE", "$.event_type", "invalid transition type")
    value = {
        "schema_version": SCHEMA_VERSIONS["proof_transition"],
        "transition_seq": len(transitions),
        "event_type": event_type,
        "parent_transition_digest": (
            transitions[-1]["transition_digest"] if transitions else "0" * 64
        ),
        "payload": copy.deepcopy(payload),
        "payload_digest": canonical_sha256(payload),
    }
    value["transition_digest"] = canonical_sha256(value)
    return value


def _topology(scope, observations, profile):
    visited = []
    visited_set = set()
    discovered = {scope["start_viewpoint"]}
    edges = {}
    observation_ids = set()
    previous_event_seq = None
    previous_step = None
    for index, observation in enumerate(observations):
        location = "$.observations[%d]" % index
        _validate_observation_profile(observation, profile, location)
        if observation["episode_id"] != scope["episode_id"]:
            fail("OBSERVATION_EPISODE", location + ".episode_id", "scope mismatch")
        if observation["scan"] != scope["scan_id"]:
            fail("OBSERVATION_SCAN", location + ".scan", "scope mismatch")
        if observation["event_id"] in observation_ids:
            fail("OBSERVATION_DUPLICATE", location + ".event_id", "duplicate ID")
        observation_ids.add(observation["event_id"])
        if index == 0:
            if observation["event_seq"] != 0 or observation["step"] != 0:
                fail("OBSERVATION_SEQUENCE", location, "first observation must be event_seq=0, step=0")
            if observation["viewpoint"] != scope["start_viewpoint"]:
                fail("OBSERVATION_START", location + ".viewpoint", "must start at scope start")
        else:
            if observation["event_seq"] <= previous_event_seq:
                fail("OBSERVATION_SEQUENCE", location + ".event_seq", "must strictly increase")
            # M2.1 controlled replay uses one admitted observation per
            # high-level decision step.  Event sequence numbers may have gaps
            # because the source trace interleaves model/action events, but a
            # missing observation step would make both the decision cut and
            # action/cost accounting ambiguous.
            if observation["step"] != previous_step + 1:
                fail(
                    "OBSERVATION_TIME_CUT", location + ".step",
                    "observation steps must be contiguous",
                )
            if observation["viewpoint"] not in visited_set and observation["viewpoint"] not in discovered:
                fail("OBSERVATION_UNDISCOVERED", location + ".viewpoint", "endpoint was not previously discovered")
        previous_event_seq = observation["event_seq"]
        previous_step = observation["step"]
        viewpoint = observation["viewpoint"]
        if viewpoint not in visited_set:
            visited.append(viewpoint)
            visited_set.add(viewpoint)
        candidate_ids = [item["viewpoint_id"] for item in observation["candidates"]]
        if len(candidate_ids) != len(set(candidate_ids)):
            fail("OBSERVATION_CANDIDATE_DUPLICATE", location + ".candidates", "duplicate viewpoint")
        for candidate in observation["candidates"]:
            target = candidate["viewpoint_id"]
            discovered.add(target)
            edge_key = (viewpoint, target)
            if edge_key not in edges:
                edges[edge_key] = {
                    "source_viewpoint_id": viewpoint,
                    "target_viewpoint_id": target,
                    "discovery_event_id": observation["event_id"],
                }
    edge_values = sorted(edges.values(), key=lambda item: (
        item["source_viewpoint_id"], item["target_viewpoint_id"], item["discovery_event_id"],
    ))
    frontier = sorted(discovered - visited_set)
    return {
        "visited_viewpoint_ids": sorted(visited_set),
        "discovered_edges": edge_values,
        "frontier_viewpoint_ids": frontier,
        "observation_event_ids": [item["event_id"] for item in observations],
        "observation_digest": canonical_sha256(observations),
        "visited_digest": canonical_sha256(sorted(visited_set)),
        "candidate_edge_digest": canonical_sha256(edge_values),
        "frontier_digest": canonical_sha256(frontier),
    }


def _units(observations):
    units = {}
    for observation in observations:
        for object_id in observation["object_proposal_ids"]:
            unit_id = object_unit_id(observation["viewpoint"], object_id)
            record = units.setdefault(unit_id, {
                "unit_id": unit_id,
                "viewpoint_id": observation["viewpoint"],
                "object_proposal_id": object_id,
                "source_event_ids": [],
            })
            if observation["event_id"] not in record["source_event_ids"]:
                record["source_event_ids"].append(observation["event_id"])
    for record in units.values():
        record["source_event_ids"].sort()
    return units


def _validate_identity_witness(value, observations, profile):
    """Validate one code-owned, observation-bound identity assertion."""

    location = "$.identity_witness"
    value = exact(value, {
        "schema_version", "witness_id", "claim", "endpoints", "audit_trail",
    }, location)
    if value["schema_version"] != SCHEMA_VERSIONS["identity_witness"]:
        fail("SCHEMA_VERSION", location + ".schema_version", "identity-witness v1 required")
    nonempty_string(value["witness_id"], location + ".witness_id")
    if value["claim"] != "SAME_ENTITY":
        fail("IDENTITY_WITNESS_CLAIM", location + ".claim", "SAME_ENTITY required")
    if not isinstance(value["endpoints"], list) or len(value["endpoints"]) != 2:
        fail("IDENTITY_WITNESS_ARITY", location + ".endpoints", "exactly two endpoints required")
    observations_by_event = {item["event_id"]: item for item in observations}
    normalized = []
    for index, endpoint in enumerate(value["endpoints"]):
        endpoint_location = "%s.endpoints[%d]" % (location, index)
        endpoint = exact(endpoint, {
            "unit_id", "viewpoint_id", "source_event_id",
            "source_observation_digest",
        }, endpoint_location)
        for key in ("unit_id", "viewpoint_id", "source_event_id",
                    "source_observation_digest"):
            nonempty_string(endpoint[key], endpoint_location + "." + key)
        source = observations_by_event.get(endpoint["source_event_id"])
        if source is None:
            fail("IDENTITY_WITNESS_SOURCE_EVENT", endpoint_location, "unknown source event")
        if endpoint["source_observation_digest"] != canonical_sha256(source):
            fail("IDENTITY_WITNESS_SOURCE_DIGEST", endpoint_location, "source observation mismatch")
        if endpoint["viewpoint_id"] != source["viewpoint"]:
            fail("IDENTITY_WITNESS_VIEWPOINT", endpoint_location, "source viewpoint mismatch")
        valid_units = {
            object_unit_id(source["viewpoint"], object_id)
            for object_id in source["object_proposal_ids"]
        }
        if endpoint["unit_id"] not in valid_units:
            fail("IDENTITY_WITNESS_UNIT", endpoint_location, "unit is not enumerated by source")
        normalized.append(copy.deepcopy(endpoint))
    if value["endpoints"] != sorted(normalized, key=lambda item: item["unit_id"]):
        fail("IDENTITY_WITNESS_ORDER", location + ".endpoints", "endpoints must use canonical unit order")
    unit_ids = [item["unit_id"] for item in normalized]
    if len(set(unit_ids)) != 2:
        fail("IDENTITY_LINK_SELF", location + ".endpoints", "endpoint units must differ")
    if len({item["viewpoint_id"] for item in normalized}) != 2:
        fail("IDENTITY_LINK_SAME_VIEWPOINT", location + ".endpoints", "endpoints must be cross-viewpoint")
    audit = exact(value["audit_trail"], {
        "producer", "source_schema", "observation_producer",
        "observation_source_schema", "interface_audit_ref",
    }, location + ".audit_trail")
    expected_audit = {
        "producer": CONTROLLED_IDENTITY_WITNESS_PRODUCER,
        "source_schema": CONTROLLED_IDENTITY_WITNESS_SOURCE_SCHEMA,
        "observation_producer": profile["observation_producer"],
        "observation_source_schema": profile["observation_source_schema"],
        "interface_audit_ref": profile["interface_audit_ref"],
    }
    if audit != expected_audit:
        fail("IDENTITY_WITNESS_PROVENANCE", location + ".audit_trail", "unregistered adapter provenance")
    identity = copy.deepcopy(value)
    claimed_id = identity.pop("witness_id")
    expected_id = "identity-" + canonical_sha256(identity)[:24]
    if claimed_id != expected_id:
        fail("IDENTITY_WITNESS_ID", location + ".witness_id", "non-canonical witness ID")
    return {
        "link_id": claimed_id,
        "subject_unit_ids": unit_ids,
        "identity_witness": copy.deepcopy(value),
    }


def _subject_groups(units, links):
    parent = {unit_id: unit_id for unit_id in units}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for link in links:
        left, right = link["subject_unit_ids"]
        if left not in units or right not in units:
            fail("IDENTITY_LINK_UNIT", "$.identity_links", "link references unknown unit")
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            fail("IDENTITY_LINK_REDUNDANT", "$.identity_links", "units are already linked")
        left_viewpoints = {
            units[item]["viewpoint_id"] for item in units if find(item) == left_root
        }
        right_viewpoints = {
            units[item]["viewpoint_id"] for item in units if find(item) == right_root
        }
        if left_viewpoints & right_viewpoints:
            fail(
                "IDENTITY_LINK_VIEWPOINT_COLLISION", "$.identity_links",
                "an identity component may contain at most one slot per viewpoint",
            )
        parent[right_root] = left_root
    groups = {}
    for unit_id in units:
        groups.setdefault(find(unit_id), []).append(unit_id)
    return sorted((sorted(value) for value in groups.values()), key=lambda value: value)


def derive_universe(scope, template, observations, links):
    units = _units(observations)
    subject_groups = _subject_groups(units, links)
    relation_predicates = [item for item in template["predicates"] if item["kind"] == "relation"]
    room_predicates = [item for item in template["predicates"] if item["kind"] == "room_anchor"]
    hypotheses = []
    obligations = []

    def add_hypothesis(kind, binding, derivation_event_ids):
        validate_binding(binding)
        hypothesis_id = "hyp-" + canonical_sha256({
            "scope_digest": canonical_sha256(scope),
            "template_id": template["template_id"],
            "hypothesis_kind": kind,
            "binding": binding,
        })[:24]
        hypothesis = {
            "hypothesis_id": hypothesis_id,
            "hypothesis_kind": kind,
            "binding": copy.deepcopy(binding),
            "derivation_event_ids": sorted(set(derivation_event_ids)),
        }
        hypotheses.append(hypothesis)
        predicate_values = template["predicates"] if kind not in RESIDUAL_HYPOTHESIS_KINDS else [{
            "predicate_id": "coverage:" + template["template_id"],
            "kind": "coverage",
            "necessary": True,
            "anchor_role": None,
            "spatial_anchor_id": None,
        }]
        for predicate in predicate_values:
            obligation_id = "obl-" + canonical_sha256({
                "hypothesis_id": hypothesis_id,
                "predicate_id": predicate["predicate_id"],
                "binding": binding,
            })[:24]
            obligations.append({
                "obligation_id": obligation_id,
                "hypothesis_id": hypothesis_id,
                "predicate_id": predicate["predicate_id"],
                "predicate_kind": predicate["kind"],
                "necessary": predicate["necessary"],
                "binding_requirement": copy.deepcopy(binding),
            })

    event_by_unit = {
        unit_id: units[unit_id]["source_event_ids"] for unit_id in units
    }
    event_by_viewpoint = {}
    for observation in observations:
        event_by_viewpoint.setdefault(observation["viewpoint"], []).append(
            observation["event_id"],
        )
    if relation_predicates:
        for subject_units in subject_groups:
            subject_viewpoints = {units[key]["viewpoint_id"] for key in subject_units}
            for anchor_units in subject_groups:
                if subject_units == anchor_units:
                    continue
                anchor_viewpoints = {units[key]["viewpoint_id"] for key in anchor_units}
                for viewpoint in sorted(subject_viewpoints & anchor_viewpoints):
                    binding = _binding(subject_units, anchor_units, viewpoint, None)
                    events = sum((event_by_unit[key] for key in subject_units + anchor_units), [])
                    add_hypothesis("subject_relation", binding, events)
            # Enumerated anchor slots do not prove that the observation
            # interface exhausted the possible anchors for this subject.  A
            # separate, subject-and-location-bound coverage obligation closes
            # that remainder.  Without it a visible subject with no anchor
            # slots would leave no relation hypothesis at all and a generic
            # location residual could make NOT_FOUND vacuous.
            for viewpoint in sorted(subject_viewpoints):
                subject_events = sum((
                    event_by_unit[key] for key in subject_units
                    if units[key]["viewpoint_id"] == viewpoint
                ), [])
                add_hypothesis(
                    "anchor_residual",
                    _binding(subject_units, [], viewpoint, None),
                    subject_events + event_by_viewpoint.get(viewpoint, []),
                )
    elif room_predicates:
        spatial_anchor_id = room_predicates[0]["spatial_anchor_id"]
        for subject_units in subject_groups:
            for viewpoint in sorted({units[key]["viewpoint_id"] for key in subject_units}):
                binding = _binding(subject_units, [], viewpoint, spatial_anchor_id)
                events = sum((event_by_unit[key] for key in subject_units), [])
                add_hypothesis("subject_room", binding, events)
    else:
        for subject_units in subject_groups:
            viewpoints = sorted({units[key]["viewpoint_id"] for key in subject_units})
            binding = _binding(subject_units, [], viewpoints[0], None)
            events = sum((event_by_unit[key] for key in subject_units), [])
            add_hypothesis("subject", binding, events)

    for viewpoint in sorted(event_by_viewpoint):
        add_hypothesis(
            "location_residual", _binding([], [], viewpoint, None),
            event_by_viewpoint[viewpoint],
        )

    hypotheses.sort(key=lambda item: item["hypothesis_id"])
    obligations.sort(key=lambda item: item["obligation_id"])
    bindings = sorted(
        [copy.deepcopy(item["binding"]) for item in hypotheses],
        key=canonical_json,
    )
    return {
        "units": sorted(units.values(), key=lambda item: item["unit_id"]),
        "bindings": bindings,
        "hypotheses": hypotheses,
        "obligations": obligations,
        "binding_digest": canonical_sha256(bindings),
        "universe_digest": canonical_sha256({
            "hypotheses": hypotheses, "obligations": obligations,
            "generator_version": template["generator_version"],
        }),
    }


def _validate_bound_evidence(
        wrapper, observations, queries, universe, profile, scope, template):
    base_fields = {
        "schema_version", "query_id", "hypothesis_id", "obligation_id",
        "predicate_id", "predicate_kind", "binding", "source_observation_digest",
        "evidence",
    }
    m3_mode = profile["evidence_mode"] == "m3_entity_support"
    fields = base_fields | ({
        "signal", "calibration_artifact", "adapter_decision", "risk_atom",
    } if m3_mode else set())
    wrapper = exact(wrapper, fields, "$.bound_evidence")
    expected_schema = SCHEMA_VERSIONS[
        "m3_bound_evidence" if m3_mode else "bound_evidence"
    ]
    if wrapper["schema_version"] != expected_schema:
        fail(
            "SCHEMA_VERSION", "$.bound_evidence.schema_version",
            "registered bound-evidence version required",
        )
    query = queries.get(wrapper["query_id"])
    if query is None:
        fail("EVIDENCE_QUERY_MISSING", "$.bound_evidence.query_id", "query must precede evidence")
    obligation_by_id = {item["obligation_id"]: item for item in universe["obligations"]}
    obligation = obligation_by_id.get(wrapper["obligation_id"])
    if obligation is None:
        fail("EVIDENCE_OBLIGATION", "$.bound_evidence.obligation_id", "unknown current obligation")
    exact_match = {
        "hypothesis_id": obligation["hypothesis_id"],
        "obligation_id": obligation["obligation_id"],
        "predicate_id": obligation["predicate_id"],
        "predicate_kind": obligation["predicate_kind"],
        "binding": obligation["binding_requirement"],
    }
    for key, expected in exact_match.items():
        if wrapper[key] != expected or query[key] != expected:
            fail("EVIDENCE_BINDING_MISMATCH", "$.bound_evidence." + key, "query/obligation mismatch")
    validate_binding(wrapper["binding"], "$.bound_evidence.binding")
    observation_map = {item["event_id"]: item for item in observations}
    evidence = wrapper["evidence"]
    validate_evidence(evidence, observation_map)
    if evidence["scope_contract_id"] != scope["scope_contract_id"]:
        fail(
            "EVIDENCE_SCOPE_CONTRACT", "$.bound_evidence.evidence.scope_contract_id",
            "evidence belongs to a different scope contract",
        )
    if evidence["obligation_id"] != wrapper["obligation_id"] or evidence["predicate_id"] != wrapper["predicate_id"]:
        fail("EVIDENCE_INDEX_MISMATCH", "$.bound_evidence.evidence", "M1 evidence index mismatch")
    source_observation = observation_map[evidence["source_event_id"]]
    if wrapper["source_observation_digest"] != canonical_sha256(source_observation):
        fail("EVIDENCE_OBSERVATION_DIGEST", "$.bound_evidence.source_observation_digest", "source changed")
    if profile["evidence_mode"] == "production_zero":
        fail("EVIDENCE_ADAPTER_NOT_REGISTERED", "$.bound_evidence.evidence.adapter_version", "M2.1 production admission is sealed")
    if m3_mode:
        # This local import keeps the frozen M2 core importable without the M3
        # adapter while still making the production fold recompute the exact
        # code-owned decision rather than trusting wrapper fields.
        from proofnav.perception.evidence_adapter import (  # pylint: disable=import-outside-toplevel
            build_calibrated_bound_evidence, validate_duet_signal,
        )
        if wrapper["predicate_kind"] != "entity":
            fail(
                "M3_UNSUPPORTED_PREDICATE", "$.bound_evidence.predicate_kind",
                "M3-A admits only entity SUPPORT evidence",
            )
        validate_duet_signal(
            wrapper["signal"], observation=source_observation,
            template=template,
        )
        expected_wrapper = build_calibrated_bound_evidence(
            query, wrapper["signal"], wrapper["calibration_artifact"],
            scope["scope_contract_id"],
        )
        expected_calibration = (
            "proofnav.calibration-artifact.v1:"
            + wrapper["calibration_artifact"].get("artifact_digest", "")
        )
        if scope["calibration_version"] != expected_calibration:
            fail(
                "M3_RISK_CALIBRATION_VERSION", "$.scope.calibration_version",
                "scope must name the exact evidence artifact digest",
            )
        if (not isinstance(expected_wrapper, dict)
                or expected_wrapper.get("schema_version")
                != SCHEMA_VERSIONS["m3_bound_evidence"]
                or wrapper != expected_wrapper):
            fail(
                "M3_EVIDENCE_RECOMPUTE_MISMATCH", "$.bound_evidence",
                "wrapper differs from the code-owned adapter decision",
            )
        if evidence["claim"] != "SUPPORTS":
            fail(
                "M3_REFUTE_NOT_REGISTERED", "$.bound_evidence.evidence.claim",
                "M3-A has no calibrated REFUTE adapter",
            )
        return wrapper
    if evidence["adapter_version"] != "proofnav.controlled-oracle.replay.v2":
        fail("CONTROLLED_ADAPTER_REQUIRED", "$.bound_evidence.evidence.adapter_version", "exact replay adapter required")
    if evidence["audit_trail"]["producer"] != "proofnav.offline.OracleEvidenceProvider.v2":
        fail(
            "CONTROLLED_EVIDENCE_PRODUCER",
            "$.bound_evidence.evidence.audit_trail.producer",
            "exact controlled evidence producer required",
        )
    if evidence["dependency_group"] != "controlled-replay:%s" % evidence["source_event_id"]:
        fail(
            "CONTROLLED_EVIDENCE_DEPENDENCY_GROUP",
            "$.bound_evidence.evidence.dependency_group",
            "dependency group must bind the source observation",
        )
    binding = wrapper["binding"]
    unit_map = {item["unit_id"]: item for item in universe["units"]}
    source_units = {
        unit_id for unit_id, record in unit_map.items()
        if evidence["source_event_id"] in record["source_event_ids"]
    }
    if wrapper["predicate_kind"] == "coverage":
        if evidence["evidence_role"] != "viewpoint_view":
            fail("EVIDENCE_ROLE_BINDING", "$.bound_evidence.evidence.evidence_role", "coverage needs viewpoint view")
        expected = view_unit_id(source_observation["viewpoint"])
        if evidence["unit_id"] != expected or binding["location_binding_id"] != location_binding_id(source_observation["viewpoint"]):
            fail("EVIDENCE_COVERAGE_BINDING", "$.bound_evidence.evidence.unit_id", "wrong location coverage")
    else:
        if evidence["evidence_role"] != "object_slot":
            fail("EVIDENCE_ROLE_BINDING", "$.bound_evidence.evidence.evidence_role", "predicate needs object slot")
        if evidence["unit_id"] not in binding["subject_unit_ids"] or evidence["unit_id"] not in source_units:
            fail("EVIDENCE_SUBJECT_BINDING", "$.bound_evidence.evidence.unit_id", "wrong subject unit")
        if wrapper["predicate_kind"] == "relation":
            if not binding["anchor_unit_ids"] or not (set(binding["anchor_unit_ids"]) & source_units):
                fail("EVIDENCE_ANCHOR_BINDING", "$.bound_evidence.binding.anchor_unit_ids", "anchor not co-observed")
            if binding["location_binding_id"] != location_binding_id(source_observation["viewpoint"]):
                fail(
                    "EVIDENCE_RELATION_LOCATION_BINDING",
                    "$.bound_evidence.binding.location_binding_id",
                    "relation source viewpoint does not match the hypothesis location",
                )
        if wrapper["predicate_kind"] == "room_anchor":
            if binding["location_binding_id"] != location_binding_id(source_observation["viewpoint"]):
                fail("EVIDENCE_ROOM_BINDING", "$.bound_evidence.binding.location_binding_id", "wrong subject location")
            if binding["spatial_anchor_id"] is None:
                fail("EVIDENCE_ROOM_BINDING", "$.bound_evidence.binding.spatial_anchor_id", "missing room anchor")
    return wrapper


def _risk_claims(value, scope):
    if not isinstance(value, dict) or set(value) - {"FOUND", "NOT_FOUND"}:
        fail("RISK_CLAIMS", "$.risk_claims", "only FOUND/NOT_FOUND keys are allowed")
    normalized = copy.deepcopy(value)
    for decision, claim in normalized.items():
        fields = {
            "decision", "risk_type", "upper_bound", "budget",
            "calibration_version", "composition_version",
        }
        exact(claim, fields, "$.risk_claims." + decision)
        expected_type = "false_found" if decision == "FOUND" else "false_not_found"
        if claim["decision"] != decision or claim["risk_type"] != expected_type:
            fail("RISK_DECISION", "$.risk_claims." + decision, "decision/type mismatch")
        for key in ("upper_bound", "budget"):
            item = claim[key]
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or not 0 <= item <= 1:
                fail("RISK_RANGE", "$.risk_claims.%s.%s" % (decision, key), "expected [0,1]")
        if claim["budget"] != scope["risk_budgets"][expected_type]:
            fail("RISK_BUDGET", "$.risk_claims." + decision, "scope mismatch")
        if claim["calibration_version"] != scope["calibration_version"]:
            fail("RISK_CALIBRATION", "$.risk_claims." + decision, "scope mismatch")
        nonempty_string(claim["composition_version"], "$.risk_claims.%s.composition_version" % decision)
    return normalized


def _validate_continue_terminal(terminal, prior, rejected_digest):
    """Validate the exact non-terminal record stored in a CONTINUE event.

    This is a structural, decision-cut check.  It deliberately does not treat
    a verifier-provided reason string as authority; later offline taxonomy
    independently audits the frozen bundle/certificate pair.
    """

    terminal = exact(
        terminal, _CONTINUE_TERMINAL_FIELDS, "$.continue.terminal_decision",
    )
    if terminal["schema_version"] != SCHEMA_VERSIONS["terminal_decision"]:
        fail("CONTINUE_TERMINAL_VERSION", "$.continue.terminal_decision.schema_version", "terminal-decision v2 required")
    if (terminal["directive"] != "CONTINUE_SEARCH"
            or terminal["terminal"] is not False
            or terminal["semantic_verdict"] is not None
            or terminal["cause"] != "verifier_reject_or_defer"):
        fail("CONTINUE_TERMINAL_STATE", "$.continue.terminal_decision", "not an exact continue decision")
    if terminal["proposed_verdict"] not in (None, "FOUND", "NOT_FOUND"):
        fail("CONTINUE_TERMINAL_VERDICT", "$.continue.terminal_decision.proposed_verdict", "invalid proposal")
    for key in (
            "proposed_certificate_id", "proposed_certificate_digest",
            "accepted_certificate_id", "accepted_certificate_digest"):
        nullable_string(terminal[key], "$.continue.terminal_decision." + key)
    proposed_id = terminal["proposed_certificate_id"]
    proposed_digest = terminal["proposed_certificate_digest"]
    if bool(proposed_id) != bool(proposed_digest):
        fail("CONTINUE_CERTIFICATE_IDENTITY", "$.continue.terminal_decision", "proposal ID and digest must co-occur")
    if proposed_digest is not None and proposed_id != "cert-" + proposed_digest[:20]:
        fail("CONTINUE_CERTIFICATE_IDENTITY", "$.continue.terminal_decision", "proposal ID is not the digest prefix")
    if (terminal["accepted_certificate_id"] is not None
            or terminal["accepted_certificate_digest"] is not None
            or terminal["certificate_accepted"] is not False):
        fail("CONTINUE_ACCEPTED_IDENTITY", "$.continue.terminal_decision", "a continue cannot carry accepted identity")
    if (terminal["decision_cut"] != prior["decision_cut"]
            or terminal["transition_tip"] != prior["transition_tip"]
            or terminal["proof_state_digest"] != prior["proof_state_digest"]):
        fail("CONTINUE_STATE_DIGEST", "$.continue.terminal_decision", "terminal is not bound to the prior state")
    if rejected_digest != proposed_digest:
        fail("CONTINUE_CERTIFICATE_IDENTITY", "$.continue.rejected_certificate_digest", "proposal digest mismatch")

    online = exact(
        terminal["online_verification"], _CONTINUE_ONLINE_FIELDS,
        "$.continue.terminal_decision.online_verification",
    )
    if online["schema_version"] != SCHEMA_VERSIONS["online_verification"]:
        fail("CONTINUE_VERIFICATION_VERSION", "$.continue.terminal_decision.online_verification.schema_version", "online-verification v2 required")
    if online["status"] not in ("REJECT", "DEFER") or online["accepted"] is not False:
        fail("CONTINUE_VERIFICATION", "$.continue.terminal_decision.online_verification", "requires a non-accepting rejection/defer")
    if online["requested_verdict"] not in (None, "FOUND", "NOT_FOUND"):
        fail("CONTINUE_VERIFICATION_VERDICT", "$.continue.terminal_decision.online_verification.requested_verdict", "invalid verifier verdict")
    for key in (
            "reason_codes", "missing_obligation_ids",
            "uncovered_hypothesis_ids", "frontier_viewpoint_ids"):
        string_list(
            online[key],
            "$.continue.terminal_decision.online_verification." + key,
        )
    expected_state = {
        "scope_digest": prior["scope_digest"],
        "template_digest": prior["template_digest"],
        "universe_digest": prior["universe_digest"],
        "binding_digest": prior["binding_digest"],
        "decision_cut": prior["decision_cut"],
        "transition_tip": prior["transition_tip"],
        "proof_state_digest": prior["proof_state_digest"],
        "frontier_viewpoint_ids": prior["topology"]["frontier_viewpoint_ids"],
    }
    for key, expected in expected_state.items():
        if online[key] != expected:
            fail("CONTINUE_VERIFICATION_STATE", "$.continue.terminal_decision.online_verification." + key, "verifier report is not bound to the prior state")
    if (online["certificate_id"] != proposed_id
            or online["certificate_digest"] != proposed_digest):
        fail("CONTINUE_CERTIFICATE_IDENTITY", "$.continue.terminal_decision.online_verification", "verifier/proposal identity mismatch")
    nullable_string(
        online["calculated_certificate_digest"],
        "$.continue.terminal_decision.online_verification.calculated_certificate_digest",
    )
    if online["status"] == "DEFER":
        if (proposed_id is not None
                or online["calculated_certificate_digest"] is not None
                or online["requested_verdict"] is not None
                or "CERTIFICATE_ABSENT" not in online["reason_codes"]):
            fail("CONTINUE_DEFER_IDENTITY", "$.continue.terminal_decision.online_verification", "DEFER is reserved for an absent certificate")

    feedback = exact(
        online["structured_feedback"], _CONTINUE_FEEDBACK_FIELDS,
        "$.continue.terminal_decision.online_verification.structured_feedback",
    )
    if feedback["recommended_action"] != "CONTINUE_EVIDENCE_COLLECTION":
        fail("CONTINUE_FEEDBACK", "$.continue.terminal_decision.feedback", "continue action required")
    for key in _CONTINUE_FEEDBACK_FIELDS - {"recommended_action"}:
        if feedback[key] != online[key]:
            fail("CONTINUE_FEEDBACK", "$.continue.terminal_decision.feedback", "feedback/report mismatch")
    if terminal["feedback"] != feedback:
        fail("CONTINUE_FEEDBACK", "$.continue.terminal_decision.feedback", "terminal/report feedback mismatch")

    execution = exact(
        terminal["duet_signal"], _CONTINUE_EXECUTION_FIELDS,
        "$.continue.terminal_decision.duet_signal",
    )
    if any(not isinstance(value, bool) for value in execution.values()):
        fail("CONTINUE_EXECUTION", "$.continue.terminal_decision.duet_signal", "execution signals must be boolean")
    forced = (
        execution["execution_error"]
        or execution["budget_exhausted"]
        or not prior["budget_status"]["within_budget"]
        or not prior["budget_status"]["can_continue"]
        or execution["max_step"]
        or not execution["executable_action_available"]
        or (
            execution["no_frontier"]
            and not execution["searchable_frontier"]
            and not prior["topology"]["frontier_viewpoint_ids"]
        )
    )
    if forced:
        fail("CONTINUE_EXECUTION", "$.continue.terminal_decision.duet_signal", "signals require FINALIZE_UNRESOLVED")
    return terminal


def recompute_view(
        bundle, allow_controlled=False, allow_m3=False,
        _validate_continues=True):
    bundle = exact(bundle, {
        "schema_version", "scope", "template", "admission_profile", "risk_claims",
        "transitions",
    }, "$")
    if bundle["schema_version"] != SCHEMA_VERSIONS["audit_bundle"]:
        fail("SCHEMA_VERSION", "$.schema_version", "decision-audit-bundle v2 required")
    scope = copy.deepcopy(bundle["scope"])
    validate_scope(scope)
    template = copy.deepcopy(bundle["template"])
    validate_template(template)
    profile = copy.deepcopy(bundle["admission_profile"])
    validate_admission_profile(profile)
    if scope["observation_interface_version"] != SCHEMA_VERSIONS["observation"]:
        fail("SCOPE_INTERFACE", "$.scope.observation_interface_version", "M1 observation v1 required")
    if scope["domain"]["interface_audit_ref"] != profile["interface_audit_ref"]:
        fail("SCOPE_INTERFACE_AUDIT", "$.scope.domain.interface_audit_ref", "unregistered audit")
    if allow_controlled and allow_m3:
        fail(
            "ADMISSION_PROFILE_MODE", "$.admission_profile",
            "one verifier may authorize only one non-default admission mode",
        )
    if profile["evidence_mode"] == "controlled_replay" and not allow_controlled:
        fail("CONTROLLED_SOURCE_FORBIDDEN", "$.admission_profile.evidence_mode", "production verifier")
    if profile["evidence_mode"] == "m3_entity_support" and not allow_m3:
        fail(
            "M3_SOURCE_FORBIDDEN", "$.admission_profile.evidence_mode",
            "the explicit M3 verifier is required",
        )
    if profile["evidence_mode"] == "m3_entity_support":
        if bundle["risk_claims"] != {}:
            fail(
                "M3_CALLER_RISK_FORBIDDEN", "$.risk_claims",
                "M3 certificate risk is derived from selected evidence",
            )
        risk_claims = {}
    else:
        risk_claims = _risk_claims(bundle["risk_claims"], scope)
    transitions = copy.deepcopy(bundle["transitions"])
    tip = _validate_transition_chain(transitions)
    observations = []
    links = []
    queries = {}
    evidence_by_id = {}
    revoked = set()
    continues = []

    for transition in transitions:
        event_type = transition["event_type"]
        payload = transition["payload"]
        if event_type == "OBSERVATION":
            observations.append(copy.deepcopy(payload))
            _topology(scope, observations, profile)
        elif event_type == "IDENTITY_LINK":
            if profile["identity_link_mode"] == "production_zero":
                fail("IDENTITY_LINK_NOT_REGISTERED", "$.identity_link", "M2.1 production link admission is sealed")
            link = _validate_identity_witness(payload, observations, profile)
            if link["link_id"] in {item["link_id"] for item in links}:
                fail("IDENTITY_LINK_DUPLICATE", "$.identity_link.link_id", "duplicate ID")
            candidate_links = links + [link]
            # Re-folding the union-find here enforces cross-viewpoint
            # injectivity for both direct and transitive merges.
            _subject_groups(_units(observations), candidate_links)
            links.append(link)
        elif event_type == "QUERY":
            payload = exact(payload, {
                "query_id", "hypothesis_id", "obligation_id", "predicate_id",
                "predicate_kind", "binding",
            }, "$.query")
            universe = derive_universe(scope, template, observations, links)
            obligation = next((
                item for item in universe["obligations"]
                if item["obligation_id"] == payload["obligation_id"]
            ), None)
            if obligation is None:
                fail("QUERY_OBLIGATION", "$.query.obligation_id", "unknown current obligation")
            expected = {
                "hypothesis_id": obligation["hypothesis_id"],
                "obligation_id": obligation["obligation_id"],
                "predicate_id": obligation["predicate_id"],
                "predicate_kind": obligation["predicate_kind"],
                "binding": obligation["binding_requirement"],
            }
            for key, item in expected.items():
                if payload[key] != item:
                    fail("QUERY_BINDING_MISMATCH", "$.query." + key, "obligation mismatch")
            expected_query_id = "query-" + canonical_sha256(expected)[:24]
            if payload["query_id"] != expected_query_id:
                fail("QUERY_ID", "$.query.query_id", "non-canonical ID")
            if payload["query_id"] in queries:
                fail("QUERY_DUPLICATE", "$.query.query_id", "already registered")
            queries[payload["query_id"]] = copy.deepcopy(payload)
        elif event_type == "EVIDENCE":
            universe = derive_universe(scope, template, observations, links)
            wrapper = _validate_bound_evidence(
                payload, observations, queries, universe, profile, scope,
                template,
            )
            evidence_id = wrapper["evidence"]["evidence_id"]
            if evidence_id in evidence_by_id:
                fail("EVIDENCE_DUPLICATE_ID", "$.bound_evidence.evidence.evidence_id", "already recorded")
            semantic = copy.deepcopy(wrapper)
            semantic["evidence"].pop("evidence_id", None)
            fingerprint = canonical_sha256(semantic)
            if fingerprint in {item["fingerprint"] for item in evidence_by_id.values()}:
                fail("EVIDENCE_DUPLICATE_SEMANTIC", "$.bound_evidence", "semantic duplicate")
            evidence_by_id[evidence_id] = {
                "wrapper": copy.deepcopy(wrapper), "fingerprint": fingerprint,
            }
        elif event_type == "REVOKE":
            payload = exact(payload, {"evidence_id", "reason"}, "$.revoke")
            nonempty_string(payload["reason"], "$.revoke.reason")
            if payload["evidence_id"] not in evidence_by_id:
                fail("EVIDENCE_UNKNOWN", "$.revoke.evidence_id", "cannot revoke unknown evidence")
            if payload["evidence_id"] in revoked:
                fail("EVIDENCE_ALREADY_REVOKED", "$.revoke.evidence_id", "already revoked")
            revoked.add(payload["evidence_id"])
        elif event_type == "CONTINUE":
            payload = exact(payload, {
                "terminal_decision", "terminal_digest", "proof_state_digest",
                "rejected_certificate_digest",
            }, "$.continue")
            if not isinstance(payload["terminal_decision"], dict):
                fail("TYPE_MAPPING", "$.continue.terminal_decision", "expected an object")
            nonempty_string(payload["terminal_digest"], "$.continue.terminal_digest")
            nonempty_string(payload["proof_state_digest"], "$.continue.proof_state_digest")
            nullable_string(payload["rejected_certificate_digest"], "$.continue.rejected_certificate_digest")
            if payload["terminal_digest"] != canonical_sha256(payload["terminal_decision"]):
                fail("CONTINUE_TERMINAL_DIGEST", "$.continue.terminal_digest", "terminal was modified")
            if _validate_continues:
                # The prior state is the prefix immediately before this
                # CONTINUE. Prefix mode validates the full event semantics but
                # does not recurse again for its own earlier CONTINUE events.
                prior_bundle = copy.deepcopy(bundle)
                prior_bundle["transitions"] = transitions[:transition["transition_seq"]]
                prior = recompute_view(
                    prior_bundle, allow_controlled=allow_controlled,
                    allow_m3=allow_m3, _validate_continues=False,
                )
                if payload["proof_state_digest"] != prior["proof_state_digest"]:
                    fail("CONTINUE_STATE_DIGEST", "$.continue.proof_state_digest", "not prior state")
                _validate_continue_terminal(
                    payload["terminal_decision"], prior,
                    payload["rejected_certificate_digest"],
                )
            continues.append(copy.deepcopy(payload))

    expected_instruction_digest = template["audit_trail"]["source_instruction_digest"]
    for index, observation in enumerate(observations):
        if canonical_sha256(observation["instruction"]) != expected_instruction_digest:
            fail(
                "TEMPLATE_INSTRUCTION_MISMATCH",
                "$.observations[%d].instruction" % index,
                "proof template is not bound to the admitted instruction",
            )

    topology = _topology(scope, observations, profile)
    universe = derive_universe(scope, template, observations, links)
    active = [
        copy.deepcopy(evidence_by_id[key]["wrapper"])
        for key in sorted(evidence_by_id) if key not in revoked
    ]
    support = {item["obligation_id"]: [] for item in universe["obligations"]}
    refute = {item["obligation_id"]: [] for item in universe["obligations"]}
    for wrapper in active:
        target = support if wrapper["evidence"]["claim"] == "SUPPORTS" else refute
        if wrapper["obligation_id"] in target:
            target[wrapper["obligation_id"]].append(wrapper["evidence"]["evidence_id"])
    resolutions = []
    for obligation in universe["obligations"]:
        support_ids = sorted(support[obligation["obligation_id"]])
        refute_ids = sorted(refute[obligation["obligation_id"]])
        if support_ids and refute_ids:
            status = "CONFLICTED"
        elif support_ids:
            status = "SATISFIED"
        elif refute_ids:
            status = "REFUTED"
        else:
            status = "OPEN"
        item = copy.deepcopy(obligation)
        item.update({
            "status": status,
            "support_evidence_ids": support_ids,
            "refutation_evidence_ids": refute_ids,
        })
        resolutions.append(item)

    max_step = max((item["step"] for item in observations), default=-1)
    proof_queries = len(queries) + len(links)
    budget = {
        "steps_used": max_step + 1,
        "observation_events": len(observations),
        # Identity assertions consume the existing proof-query budget; they
        # are not a free oracle hidden outside complete-cost accounting.
        "predicate_queries": proof_queries,
    }
    limits = scope["resource_limits"]
    comparisons = {
        "steps_used": "max_steps",
        "observation_events": "max_observation_events",
        "predicate_queries": "max_predicate_queries",
    }
    budget["within_budget"] = all(budget[key] <= limits[limit] for key, limit in comparisons.items())
    budget["can_continue"] = all(budget[key] < limits[limit] for key, limit in comparisons.items())
    budget["exhausted_resources"] = sorted(
        key for key, limit in comparisons.items() if budget[key] >= limits[limit]
    )
    # The frozen M2.1 convention is: the initial observation is step zero and
    # every subsequent observation follows exactly one high-level action.
    # This makes these proof-critical counters derivable instead of caller
    # supplied.  M4 may replace this with explicit ACTION transitions only by
    # a schema/version change.
    high_level_actions = max_step if max_step >= 0 else 0
    travel = 0.0
    previous = None
    for observation in observations:
        if previous is not None and observation["viewpoint"] != previous["viewpoint"]:
            travel += math.sqrt(sum(
                (float(a) - float(b)) ** 2
                for a, b in zip(previous["pose"]["position"], observation["pose"]["position"])
            ))
        previous = observation
    cost = {
        "travel_distance_meters": travel,
        "high_level_actions": high_level_actions,
        "expanded_path_edges": high_level_actions,
        "observation_events": len(observations),
        "predicate_queries": proof_queries,
        "online_compute_milliseconds": 0.0,
        "storage_bytes": len(canonical_json(transitions).encode("utf-8")),
        "offline_preprocessing_ref": scope["domain"]["interface_audit_ref"],
    }
    decision_cut = {
        "transition_seq": len(transitions) - 1,
        "transition_digest": tip,
        "max_observation_event_seq": max((item["event_seq"] for item in observations), default=-1),
        "max_step": max_step,
    }
    closure = None
    if observations and not topology["frontier_viewpoint_ids"]:
        closure = {
            "schema_version": SCHEMA_VERSIONS["closure_witness"],
            "scope_contract_id": scope["scope_contract_id"],
            "scope_version": scope["provenance"]["version"],
            "scope_digest": canonical_sha256(scope),
            "observation_interface_version": scope["observation_interface_version"],
            "interface_audit_ref": profile["interface_audit_ref"],
            "generator_version": template["generator_version"],
            "decision_cut": copy.deepcopy(decision_cut),
            "observation_event_ids": topology["observation_event_ids"],
            "observation_digest": topology["observation_digest"],
            "visited_viewpoint_ids": topology["visited_viewpoint_ids"],
            "visited_digest": topology["visited_digest"],
            "candidate_edge_digest": topology["candidate_edge_digest"],
            "frontier_viewpoint_ids": [],
            "frontier_digest": topology["frontier_digest"],
            "universe_digest": universe["universe_digest"],
            "binding_digest": universe["binding_digest"],
        }
        closure["witness_digest"] = canonical_sha256(closure)

    ledger_digest = canonical_sha256({
        "schema_version": SCHEMA_VERSIONS["ledger"],
        "identity_witnesses": [
            copy.deepcopy(item["identity_witness"]) for item in links
        ],
        "active_bound_evidence": active,
        "revoked_evidence_ids": sorted(revoked),
    })
    semantic_payload = {
        "schema_version": SCHEMA_VERSIONS["proof_state"],
        "episode_id": scope["episode_id"],
        "scope_contract_id": scope["scope_contract_id"],
        "scope_version": scope["provenance"]["version"],
        "scope_digest": canonical_sha256(scope),
        "template_id": template["template_id"],
        "template_digest": canonical_sha256(template),
        "state_version": len(transitions),
        "decision_cut": decision_cut,
        "transition_tip": tip,
        "topology": topology,
        "closure_witness": closure,
        "bindings": universe["bindings"],
        "binding_digest": universe["binding_digest"],
        "hypotheses": universe["hypotheses"],
        "hypothesis_ids": [item["hypothesis_id"] for item in universe["hypotheses"]],
        "universe_digest": universe["universe_digest"],
        "obligations": resolutions,
        "queries": [queries[key] for key in sorted(queries)],
        "active_bound_evidence": active,
        "revoked_evidence_ids": sorted(revoked),
        "ledger_digest": ledger_digest,
        "ledger_event_count": len(links) + len(evidence_by_id) + len(revoked),
        "budget_status": budget,
        "cost_ledger": cost,
        "risk_claims": risk_claims,
        "continue_count": len(continues),
    }
    semantic_payload["proof_state_digest"] = canonical_sha256(semantic_payload)
    semantic_payload["audit_trail"] = {
        "producer": "proofnav.runtime.state.v2",
        "transition_count": len(transitions),
        "transition_tip": tip,
        "admission_profile_id": profile["profile_id"],
    }
    return semantic_payload
