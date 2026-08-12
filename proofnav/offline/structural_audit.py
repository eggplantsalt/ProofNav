"""Independent structural reconstruction for M2.1 offline auditing.

This module intentionally does not import ``proofnav.runtime``.  It folds raw
transition records itself so an online implementation bug cannot become the
definition of offline correctness.  Hidden truth is not returned from any
function in this module and no result is suitable as runtime feedback.
"""

import copy
import math

from proofnav.calibration.registry import (
    is_registered_calibration_artifact_digest,
    is_registered_signal_digest,
)
from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_json, canonical_sha256
from proofnav.validation import validate_evidence, validate_observation, validate_scope


_TRANSITION_TYPES = frozenset((
    "OBSERVATION", "IDENTITY_LINK", "QUERY", "EVIDENCE", "REVOKE", "CONTINUE",
))
_PREDICATE_KINDS = frozenset((
    "entity", "attribute", "relation", "room_anchor", "coverage",
))
_RESIDUAL_HYPOTHESIS_KINDS = frozenset((
    "location_residual", "anchor_residual",
))
_PRODUCTION_INTERFACE_AUDIT_REF = (
    "m0.offline_adjacency.v1:sha256:"
    "2d2cf87d402b7d6e7283bf86c5da56cacd49312359d367c8c5d6234dbe9b47b8"
)
_CONTROLLED_INTERFACE_AUDIT_REF = "m0.offline_adjacency.v1:micro"
_CONTROLLED_IDENTITY_WITNESS_PRODUCER = (
    "proofnav.offline.controlled_identity_witness.v1"
)
_CONTROLLED_IDENTITY_WITNESS_SOURCE_SCHEMA = (
    "proofnav.controlled-identity-witness.v1"
)
_M3_PROFILE_ID = "proofnav.admission.m3-entity-support.v1"
_M3_SIGNAL_FIELDS = {
    "schema_version", "producer", "source_schema", "signal_semantics",
    "evidence_authority", "observation", "observation_digest",
    "object_scores", "content_digests", "instruction_digest",
    "template_digest", "model_identity", "signal_digest",
}
_M3_MODEL_FIELDS = {
    "model_digest", "checkpoint_digest", "feature_digest",
    "interface_digest", "config_digest", "tokenizer_digest",
}
_M3_ARTIFACT_FIELDS = {
    "schema_version", "evidence_family", "predicate_kind", "polarity",
    "score_semantics", "model_identity", "label_definition_digest",
    "split_fingerprint", "split_names", "calibration_method",
    "calibration_parameters", "validity_domain", "sample_unit",
    "dependency_unit", "risk_event", "risk_bound", "aggregate_counts",
    "generation", "artifact_digest",
}
_M3_DECISION_FIELDS = {
    "schema_version", "decision_id", "decision", "reason_code",
    "evidence_family", "predicate_kind", "polarity", "query_id",
    "hypothesis_id", "obligation_id", "predicate_id", "binding",
    "source_observation_digest", "signal_digest", "artifact_digest",
    "domain_id", "selected_statistic", "dependency_group",
    "adapter_version", "adapter_producer", "risk_atom_id",
    "decision_digest",
}
_M3_ATOM_FIELDS = {
    "schema_version", "atom_id", "event_type", "polarity", "upper_bound",
    "familywise", "family_key", "evidence_id", "artifact_digest",
    "signal_digest", "dependency_group", "atom_digest",
}


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _exact(value, fields, location):
    if not isinstance(value, dict):
        _fail("TYPE_MAPPING", location, "expected an object")
    missing = sorted(set(fields) - set(value))
    unknown = sorted(set(value) - set(fields))
    if missing or unknown:
        _fail("OFFLINE_SCHEMA", location, "missing=%s unknown=%s" % (missing, unknown))
    return value


def _string(value, location):
    if not isinstance(value, str) or not value:
        _fail("TYPE_STRING", location, "expected a non-empty string")
    return value


def _nullable_string(value, location):
    if value is not None:
        _string(value, location)
    return value


def _sha256(value, location):
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        _fail("OFFLINE_M3_SHA256", location, "lowercase SHA-256 required")
    return value


def _finite(value, location, minimum=None, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value))):
        _fail("OFFLINE_M3_NUMBER", location, "finite number required")
    value = float(value)
    if minimum is not None and value < minimum:
        _fail("OFFLINE_M3_RANGE", location, "value below minimum")
    if maximum is not None and value > maximum:
        _fail("OFFLINE_M3_RANGE", location, "value above maximum")
    return value


def _string_list(value, location):
    if not isinstance(value, list):
        _fail("TYPE_LIST", location, "expected an array")
    for index, item in enumerate(value):
        _string(item, "%s[%d]" % (location, index))
    if len(value) != len(set(value)):
        _fail("OFFLINE_DUPLICATE", location, "duplicate value")
    return value


def _subject_binding_id(unit_ids):
    return "subject-" + canonical_sha256({
        "subject_unit_ids": sorted(unit_ids),
    })[:20]


def _object_unit_id(viewpoint_id, object_id):
    return "objunit-" + canonical_sha256({
        "viewpoint_id": str(viewpoint_id),
        "object_proposal_id": str(object_id),
    })[:20]


def _view_unit_id(viewpoint_id):
    return "viewunit-" + canonical_sha256({"viewpoint_id": str(viewpoint_id)})[:20]


def _location_binding_id(viewpoint_id):
    return "loc-" + canonical_sha256({"viewpoint_id": str(viewpoint_id)})[:20]


def _binding(subject_units, anchor_units, viewpoint_id, spatial_anchor_id):
    subject_units = sorted(subject_units)
    anchor_units = sorted(anchor_units)
    return {
        "subject_binding_id": _subject_binding_id(subject_units) if subject_units else None,
        "subject_unit_ids": subject_units,
        "anchor_binding_id": _subject_binding_id(anchor_units) if anchor_units else None,
        "anchor_unit_ids": anchor_units,
        "location_binding_id": _location_binding_id(viewpoint_id),
        "spatial_anchor_id": spatial_anchor_id,
    }


def _validate_binding(value, location):
    value = _exact(value, {
        "subject_binding_id", "subject_unit_ids", "anchor_binding_id",
        "anchor_unit_ids", "location_binding_id", "spatial_anchor_id",
    }, location)
    _nullable_string(value["subject_binding_id"], location + ".subject_binding_id")
    _string_list(value["subject_unit_ids"], location + ".subject_unit_ids")
    _nullable_string(value["anchor_binding_id"], location + ".anchor_binding_id")
    _string_list(value["anchor_unit_ids"], location + ".anchor_unit_ids")
    _string(value["location_binding_id"], location + ".location_binding_id")
    _nullable_string(value["spatial_anchor_id"], location + ".spatial_anchor_id")
    expected_subject = (
        _subject_binding_id(value["subject_unit_ids"])
        if value["subject_unit_ids"] else None
    )
    expected_anchor = (
        _subject_binding_id(value["anchor_unit_ids"])
        if value["anchor_unit_ids"] else None
    )
    if value["subject_binding_id"] != expected_subject:
        _fail("OFFLINE_BINDING_SUBJECT", location, "non-canonical subject binding")
    if value["anchor_binding_id"] != expected_anchor:
        _fail("OFFLINE_BINDING_ANCHOR", location, "non-canonical anchor binding")
    return value


def _validate_template(template):
    template = _exact(template, {
        "schema_version", "template_id", "generator_version", "target_role",
        "predicates", "audit_trail",
    }, "$.template")
    if template["schema_version"] != SCHEMA_VERSIONS["proof_template"]:
        _fail("SCHEMA_VERSION", "$.template.schema_version", "proof-template v2 required")
    for key in ("template_id", "generator_version", "target_role"):
        _string(template[key], "$.template." + key)
    if template["generator_version"] != "proofnav.dynamic-universe.v2":
        _fail("OFFLINE_GENERATOR", "$.template.generator_version", "unregistered generator")
    if not isinstance(template["predicates"], list) or not template["predicates"]:
        _fail("OFFLINE_TEMPLATE", "$.template.predicates", "non-empty array required")
    seen = set()
    anchored_count = 0
    for index, predicate in enumerate(template["predicates"]):
        location = "$.template.predicates[%d]" % index
        predicate = _exact(predicate, {
            "predicate_id", "kind", "necessary", "anchor_role", "spatial_anchor_id",
        }, location)
        _string(predicate["predicate_id"], location + ".predicate_id")
        if predicate["predicate_id"] in seen:
            _fail("OFFLINE_TEMPLATE_DUPLICATE", location, "duplicate predicate")
        seen.add(predicate["predicate_id"])
        if predicate["kind"] not in _PREDICATE_KINDS - {"coverage"}:
            _fail("OFFLINE_TEMPLATE_KIND", location + ".kind", "unsupported predicate")
        if not isinstance(predicate["necessary"], bool):
            _fail("TYPE_BOOLEAN", location + ".necessary", "expected boolean")
        _nullable_string(predicate["anchor_role"], location + ".anchor_role")
        _nullable_string(predicate["spatial_anchor_id"], location + ".spatial_anchor_id")
        if predicate["kind"] == "relation":
            anchored_count += 1
            if not predicate["necessary"]:
                _fail(
                    "OFFLINE_TEMPLATE_ANCHORED_NECESSARY", location,
                    "anchored predicate must be necessary",
                )
            if predicate["anchor_role"] is None or predicate["spatial_anchor_id"] is not None:
                _fail("OFFLINE_TEMPLATE_BINDING", location, "relation binding is invalid")
        elif predicate["kind"] == "room_anchor":
            anchored_count += 1
            if not predicate["necessary"]:
                _fail(
                    "OFFLINE_TEMPLATE_ANCHORED_NECESSARY", location,
                    "anchored predicate must be necessary",
                )
            if predicate["spatial_anchor_id"] is None or predicate["anchor_role"] is not None:
                _fail("OFFLINE_TEMPLATE_BINDING", location, "room binding is invalid")
        elif predicate["anchor_role"] is not None or predicate["spatial_anchor_id"] is not None:
            _fail("OFFLINE_TEMPLATE_BINDING", location, "unexpected anchor")
    if anchored_count > 1:
        _fail(
            "OFFLINE_TEMPLATE_ANCHORED_CARDINALITY", "$.template.predicates",
            "M2.1 supports at most one relation or room_anchor predicate",
        )
    if not any(item["necessary"] for item in template["predicates"]):
        _fail("OFFLINE_TEMPLATE", "$.template.predicates", "missing necessary predicate")
    audit = _exact(template["audit_trail"], {
        "producer", "source_instruction_digest",
    }, "$.template.audit_trail")
    _string(audit["producer"], "$.template.audit_trail.producer")
    if not isinstance(audit["source_instruction_digest"], str) or len(audit["source_instruction_digest"]) != 64:
        _fail("OFFLINE_TEMPLATE_DIGEST", "$.template.audit_trail", "SHA-256 required")
    return template


def _validate_profile(profile, scope):
    profile = _exact(profile, {
        "profile_id", "observation_producer", "observation_source_schema",
        "interface_audit_ref", "evidence_mode", "identity_link_mode",
    }, "$.admission_profile")
    for key in profile:
        _string(profile[key], "$.admission_profile." + key)
    if profile["interface_audit_ref"] != scope["domain"]["interface_audit_ref"]:
        _fail("OFFLINE_PROFILE_SCOPE", "$.admission_profile.interface_audit_ref", "scope mismatch")
    controlled = {
        "profile_id": "proofnav.admission.controlled-replay.v2",
        "observation_producer": "proofnav.offline.controlled_replay",
        "observation_source_schema": "proofnav.controlled-observation.v2",
        "interface_audit_ref": _CONTROLLED_INTERFACE_AUDIT_REF,
        "evidence_mode": "controlled_replay",
        "identity_link_mode": "controlled_replay",
    }
    production = {
        "profile_id": "proofnav.admission.production-zero.v2",
        "observation_producer": "proofnav.adapters.sanitize_duet_observation",
        "observation_source_schema": "duet.reverie._get_obs@frozen-m0",
        "interface_audit_ref": _PRODUCTION_INTERFACE_AUDIT_REF,
        "evidence_mode": "production_zero",
        "identity_link_mode": "production_zero",
    }
    m3 = {
        "profile_id": "proofnav.admission.m3-entity-support.v1",
        "observation_producer": "proofnav.adapters.sanitize_duet_observation",
        "observation_source_schema": "duet.reverie._get_obs@frozen-m0",
        "interface_audit_ref": _PRODUCTION_INTERFACE_AUDIT_REF,
        "evidence_mode": "m3_entity_support",
        "identity_link_mode": "production_zero",
    }
    if profile not in (controlled, production, m3):
        _fail("OFFLINE_PROFILE_NOT_CODE_OWNED", "$.admission_profile", "unknown profile")
    return profile


def _validate_risk_claims(value, scope):
    if not isinstance(value, dict) or set(value) - {"FOUND", "NOT_FOUND"}:
        _fail("OFFLINE_RISK", "$.risk_claims", "invalid decisions")
    for decision, claim in value.items():
        claim = _exact(claim, {
            "decision", "risk_type", "upper_bound", "budget",
            "calibration_version", "composition_version",
        }, "$.risk_claims." + decision)
        expected_type = "false_found" if decision == "FOUND" else "false_not_found"
        if claim["decision"] != decision or claim["risk_type"] != expected_type:
            _fail("OFFLINE_RISK", "$.risk_claims." + decision, "decision mismatch")
        for key in ("upper_bound", "budget"):
            item = claim[key]
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or not 0 <= item <= 1:
                _fail("OFFLINE_RISK", "$.risk_claims.%s.%s" % (decision, key), "invalid bound")
        if claim["budget"] != scope["risk_budgets"][expected_type]:
            _fail("OFFLINE_RISK", "$.risk_claims.%s.budget" % decision, "scope mismatch")
        if claim["calibration_version"] != scope["calibration_version"]:
            _fail("OFFLINE_RISK", "$.risk_claims.%s.calibration_version" % decision, "scope mismatch")
        _string(claim["composition_version"], "$.risk_claims.%s.composition_version" % decision)
    return copy.deepcopy(value)


def _validate_continue_terminal(terminal, prior, rejected_digest):
    """Independently validate a stored non-terminal verifier decision."""

    terminal = _exact(
        terminal, _TERMINAL_FIELDS, "$.continue.terminal_decision",
    )
    if terminal["schema_version"] != SCHEMA_VERSIONS["terminal_decision"]:
        _fail("OFFLINE_CONTINUE_TERMINAL_VERSION", "$.continue.terminal_decision", "wrong terminal version")
    if (terminal["directive"] != "CONTINUE_SEARCH"
            or terminal["terminal"] is not False
            or terminal["semantic_verdict"] is not None
            or terminal["cause"] != "verifier_reject_or_defer"):
        _fail("OFFLINE_CONTINUE_TERMINAL", "$.continue.terminal_decision", "not an exact continue")
    if terminal["proposed_verdict"] not in (None, "FOUND", "NOT_FOUND"):
        _fail("OFFLINE_CONTINUE_VERDICT", "$.continue.terminal_decision", "invalid proposed verdict")
    for key in (
            "proposed_certificate_id", "proposed_certificate_digest",
            "accepted_certificate_id", "accepted_certificate_digest"):
        _nullable_string(terminal[key], "$.continue.terminal_decision." + key)
    proposed_id = terminal["proposed_certificate_id"]
    proposed_digest = terminal["proposed_certificate_digest"]
    if (bool(proposed_id) != bool(proposed_digest)
            or (proposed_digest is not None
                and proposed_id != "cert-" + proposed_digest[:20])):
        _fail("OFFLINE_CONTINUE_CERTIFICATE", "$.continue.terminal_decision", "invalid proposal identity")
    if (terminal["accepted_certificate_id"] is not None
            or terminal["accepted_certificate_digest"] is not None
            or terminal["certificate_accepted"] is not False):
        _fail("OFFLINE_CONTINUE_ACCEPTED", "$.continue.terminal_decision", "continue cannot accept a certificate")
    if (terminal["decision_cut"] != prior["decision_cut"]
            or terminal["transition_tip"] != prior["transition_tip"]
            or terminal["proof_state_digest"] != prior["proof_state_digest"]):
        _fail("OFFLINE_CONTINUE_STATE", "$.continue.terminal_decision", "terminal is not the prior state")
    if rejected_digest != proposed_digest:
        _fail("OFFLINE_CONTINUE_CERTIFICATE", "$.continue", "proposal digest mismatch")

    online = _exact(
        terminal["online_verification"], _ONLINE_FIELDS,
        "$.continue.terminal_decision.online_verification",
    )
    if online["schema_version"] != SCHEMA_VERSIONS["online_verification"]:
        _fail("OFFLINE_CONTINUE_VERIFICATION_VERSION", "$.continue.terminal_decision.online_verification", "wrong online version")
    if online["status"] not in ("REJECT", "DEFER") or online["accepted"] is not False:
        _fail("OFFLINE_CONTINUE_VERIFICATION", "$.continue.terminal_decision.online_verification", "requires non-accepting reject/defer")
    if online["requested_verdict"] not in (None, "FOUND", "NOT_FOUND"):
        _fail("OFFLINE_CONTINUE_VERDICT", "$.continue.terminal_decision.online_verification", "invalid verdict")
    for key in (
            "reason_codes", "missing_obligation_ids",
            "uncovered_hypothesis_ids", "frontier_viewpoint_ids"):
        _string_list(
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
            _fail("OFFLINE_CONTINUE_VERIFICATION_STATE", "$.continue.terminal_decision.online_verification." + key, "report is not the prior state")
    if (online["certificate_id"] != proposed_id
            or online["certificate_digest"] != proposed_digest):
        _fail("OFFLINE_CONTINUE_CERTIFICATE", "$.continue.terminal_decision.online_verification", "report/proposal identity mismatch")
    _nullable_string(
        online["calculated_certificate_digest"],
        "$.continue.terminal_decision.online_verification.calculated_certificate_digest",
    )
    if online["status"] == "DEFER" and (
            proposed_id is not None
            or online["calculated_certificate_digest"] is not None
            or online["requested_verdict"] is not None
            or "CERTIFICATE_ABSENT" not in online["reason_codes"]):
        _fail("OFFLINE_CONTINUE_DEFER", "$.continue.terminal_decision.online_verification", "DEFER requires an absent certificate")

    feedback = _exact(
        online["structured_feedback"], _FEEDBACK_FIELDS,
        "$.continue.terminal_decision.online_verification.structured_feedback",
    )
    if feedback["recommended_action"] != "CONTINUE_EVIDENCE_COLLECTION":
        _fail("OFFLINE_CONTINUE_FEEDBACK", "$.continue.terminal_decision.feedback", "wrong recommendation")
    for key in _FEEDBACK_FIELDS - {"recommended_action"}:
        if feedback[key] != online[key]:
            _fail("OFFLINE_CONTINUE_FEEDBACK", "$.continue.terminal_decision.feedback", "feedback/report mismatch")
    if terminal["feedback"] != feedback:
        _fail("OFFLINE_CONTINUE_FEEDBACK", "$.continue.terminal_decision.feedback", "terminal/report mismatch")

    execution = _exact(
        terminal["duet_signal"], _EXECUTION_FIELDS,
        "$.continue.terminal_decision.duet_signal",
    )
    if any(not isinstance(value, bool) for value in execution.values()):
        _fail("OFFLINE_CONTINUE_EXECUTION", "$.continue.terminal_decision.duet_signal", "signals must be boolean")
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
        _fail("OFFLINE_CONTINUE_EXECUTION", "$.continue.terminal_decision.duet_signal", "signals require unresolved finalization")
    return terminal


def _validate_transition_chain(transitions):
    if not isinstance(transitions, list):
        _fail("TYPE_LIST", "$.transitions", "expected an array")
    previous = "0" * 64
    for index, transition in enumerate(transitions):
        location = "$.transitions[%d]" % index
        transition = _exact(transition, {
            "schema_version", "transition_seq", "event_type", "parent_transition_digest",
            "payload", "payload_digest", "transition_digest",
        }, location)
        if transition["schema_version"] != SCHEMA_VERSIONS["proof_transition"]:
            _fail("SCHEMA_VERSION", location + ".schema_version", "proof-transition v2 required")
        if transition["transition_seq"] != index:
            _fail("OFFLINE_TRANSITION_SEQUENCE", location, "non-contiguous sequence")
        if transition["event_type"] not in _TRANSITION_TYPES:
            _fail("OFFLINE_TRANSITION_TYPE", location, "invalid event type")
        if transition["parent_transition_digest"] != previous:
            _fail("OFFLINE_TRANSITION_PARENT", location, "broken parent")
        if transition["payload_digest"] != canonical_sha256(transition["payload"]):
            _fail("OFFLINE_TRANSITION_PAYLOAD", location, "payload was modified")
        body = copy.deepcopy(transition)
        claimed = body.pop("transition_digest")
        if claimed != canonical_sha256(body):
            _fail("OFFLINE_TRANSITION_DIGEST", location, "transition was modified")
        previous = claimed
    return previous


def _topology(scope, observations, profile):
    visited = set()
    discovered = {scope["start_viewpoint"]}
    edges = {}
    event_ids = set()
    previous_event_seq = None
    previous_step = None
    for index, observation in enumerate(observations):
        location = "$.observations[%d]" % index
        validate_observation(observation)
        if observation["audit_trail"] != {
                "producer": profile["observation_producer"],
                "source_schema": profile["observation_source_schema"]}:
            _fail("OFFLINE_OBSERVATION_PROFILE", location + ".audit_trail", "unregistered source")
        feature_shape = observation["field_schema"]["feature"]["shape"]
        if (len(feature_shape) != 2 or feature_shape[0] != 36
                or feature_shape[1] <= 0
                or observation["field_schema"]["feature"]["dtype"] != "float32"
                or not 0 <= observation["view_index"] < 36):
            _fail("OFFLINE_PANORAMA_SCHEMA", location, "invalid audited panorama schema")
        for candidate in observation["candidates"]:
            if (not 0 <= candidate["point_id"] < 36
                    or candidate["feature_schema"]["shape"] != [feature_shape[1]]
                    or candidate["feature_schema"]["dtype"] != "float32"):
                _fail("OFFLINE_CANDIDATE_SCHEMA", location, "invalid candidate schema")
        object_ids = observation["object_proposal_ids"]
        if len(object_ids) != len(set(object_ids)):
            _fail("OFFLINE_OBJECT_ID_DUPLICATE", location, "duplicate object proposal ID")
        row_counts = []
        for name in ("obj_img_fts", "obj_ang_fts", "obj_box_fts"):
            shape = observation["field_schema"][name]["shape"]
            if not shape:
                _fail("OFFLINE_OBJECT_SCHEMA", location, "missing object row dimension")
            row_counts.append(shape[0])
        if len(set(row_counts)) != 1 or row_counts[0] != len(object_ids):
            _fail("OFFLINE_OBJECT_ENUMERATION", location, "IDs/feature rows disagree")
        expected_shapes = {
            "obj_img_fts": [len(object_ids), 768],
            "obj_ang_fts": [len(object_ids), 4],
            "obj_box_fts": [len(object_ids), 3],
        }
        if any(
                observation["field_schema"][name]["shape"] != expected
                or observation["field_schema"][name]["dtype"] != "float32"
                for name, expected in expected_shapes.items()):
            _fail("OFFLINE_OBJECT_SCHEMA", location, "invalid object feature schema")
        if observation["episode_id"] != scope["episode_id"] or observation["scan"] != scope["scan_id"]:
            _fail("OFFLINE_OBSERVATION_SCOPE", location, "scope mismatch")
        if observation["event_id"] in event_ids:
            _fail("OFFLINE_OBSERVATION_DUPLICATE", location, "duplicate event")
        event_ids.add(observation["event_id"])
        if index == 0:
            if observation["event_seq"] != 0 or observation["step"] != 0:
                _fail("OFFLINE_OBSERVATION_SEQUENCE", location, "first observation must be 0/0")
            if observation["viewpoint"] != scope["start_viewpoint"]:
                _fail("OFFLINE_OBSERVATION_START", location, "wrong start")
        else:
            if observation["event_seq"] <= previous_event_seq:
                _fail("OFFLINE_OBSERVATION_SEQUENCE", location, "event sequence did not advance")
            if observation["step"] != previous_step + 1:
                _fail("OFFLINE_OBSERVATION_TIME_CUT", location, "observation steps are not contiguous")
            if observation["viewpoint"] not in visited and observation["viewpoint"] not in discovered:
                _fail("OFFLINE_OBSERVATION_UNDISCOVERED", location, "viewpoint not discovered")
        previous_event_seq = observation["event_seq"]
        previous_step = observation["step"]
        viewpoint = observation["viewpoint"]
        visited.add(viewpoint)
        targets = [item["viewpoint_id"] for item in observation["candidates"]]
        if len(targets) != len(set(targets)):
            _fail("OFFLINE_CANDIDATE_DUPLICATE", location, "duplicate candidate")
        for target in targets:
            discovered.add(target)
            edges.setdefault((viewpoint, target), {
                "source_viewpoint_id": viewpoint,
                "target_viewpoint_id": target,
                "discovery_event_id": observation["event_id"],
            })
    edge_values = sorted(edges.values(), key=lambda item: (
        item["source_viewpoint_id"], item["target_viewpoint_id"], item["discovery_event_id"],
    ))
    frontier = sorted(discovered - visited)
    return {
        "visited_viewpoint_ids": sorted(visited),
        "discovered_edges": edge_values,
        "frontier_viewpoint_ids": frontier,
        "observation_event_ids": [item["event_id"] for item in observations],
        "observation_digest": canonical_sha256(observations),
        "visited_digest": canonical_sha256(sorted(visited)),
        "candidate_edge_digest": canonical_sha256(edge_values),
        "frontier_digest": canonical_sha256(frontier),
    }


def _units(observations):
    units = {}
    for observation in observations:
        for object_id in observation["object_proposal_ids"]:
            unit_id = _object_unit_id(observation["viewpoint"], object_id)
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
    """Independently authenticate a controlled identity-link witness."""

    location = "$.identity_witness"
    value = _exact(value, {
        "schema_version", "witness_id", "claim", "endpoints", "audit_trail",
    }, location)
    if value["schema_version"] != SCHEMA_VERSIONS["identity_witness"]:
        _fail("SCHEMA_VERSION", location + ".schema_version", "identity-witness v1 required")
    _string(value["witness_id"], location + ".witness_id")
    if value["claim"] != "SAME_ENTITY":
        _fail("OFFLINE_IDENTITY_CLAIM", location + ".claim", "SAME_ENTITY required")
    if not isinstance(value["endpoints"], list) or len(value["endpoints"]) != 2:
        _fail("OFFLINE_IDENTITY_ARITY", location + ".endpoints", "two endpoints required")
    observations_by_event = {item["event_id"]: item for item in observations}
    endpoints = []
    for index, endpoint in enumerate(value["endpoints"]):
        endpoint_location = "%s.endpoints[%d]" % (location, index)
        endpoint = _exact(endpoint, {
            "unit_id", "viewpoint_id", "source_event_id",
            "source_observation_digest",
        }, endpoint_location)
        for key in endpoint:
            _string(endpoint[key], endpoint_location + "." + key)
        source = observations_by_event.get(endpoint["source_event_id"])
        if source is None:
            _fail("OFFLINE_IDENTITY_SOURCE_EVENT", endpoint_location, "unknown source event")
        if endpoint["source_observation_digest"] != canonical_sha256(source):
            _fail("OFFLINE_IDENTITY_SOURCE_DIGEST", endpoint_location, "source digest mismatch")
        if endpoint["viewpoint_id"] != source["viewpoint"]:
            _fail("OFFLINE_IDENTITY_VIEWPOINT", endpoint_location, "source viewpoint mismatch")
        valid_units = {
            _object_unit_id(source["viewpoint"], object_id)
            for object_id in source["object_proposal_ids"]
        }
        if endpoint["unit_id"] not in valid_units:
            _fail("OFFLINE_IDENTITY_UNIT", endpoint_location, "unit is not source-enumerated")
        endpoints.append(copy.deepcopy(endpoint))
    if value["endpoints"] != sorted(endpoints, key=lambda item: item["unit_id"]):
        _fail("OFFLINE_IDENTITY_ORDER", location + ".endpoints", "non-canonical endpoint order")
    unit_ids = [item["unit_id"] for item in endpoints]
    if len(set(unit_ids)) != 2:
        _fail("OFFLINE_IDENTITY_SELF", location + ".endpoints", "units must differ")
    if len({item["viewpoint_id"] for item in endpoints}) != 2:
        _fail("OFFLINE_IDENTITY_SAME_VIEWPOINT", location + ".endpoints", "cross-viewpoint only")
    audit = _exact(value["audit_trail"], {
        "producer", "source_schema", "observation_producer",
        "observation_source_schema", "interface_audit_ref",
    }, location + ".audit_trail")
    expected_audit = {
        "producer": _CONTROLLED_IDENTITY_WITNESS_PRODUCER,
        "source_schema": _CONTROLLED_IDENTITY_WITNESS_SOURCE_SCHEMA,
        "observation_producer": profile["observation_producer"],
        "observation_source_schema": profile["observation_source_schema"],
        "interface_audit_ref": profile["interface_audit_ref"],
    }
    if audit != expected_audit:
        _fail("OFFLINE_IDENTITY_PROVENANCE", location + ".audit_trail", "unregistered provenance")
    identity = copy.deepcopy(value)
    claimed_id = identity.pop("witness_id")
    if claimed_id != "identity-" + canonical_sha256(identity)[:24]:
        _fail("OFFLINE_IDENTITY_ID", location + ".witness_id", "non-canonical witness ID")
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
            _fail("OFFLINE_LINK_UNIT", "$.identity_links", "unknown unit")
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            _fail("OFFLINE_LINK_REDUNDANT", "$.identity_links", "units already linked")
        left_viewpoints = {
            units[item]["viewpoint_id"] for item in units if find(item) == left_root
        }
        right_viewpoints = {
            units[item]["viewpoint_id"] for item in units if find(item) == right_root
        }
        if left_viewpoints & right_viewpoints:
            _fail(
                "OFFLINE_LINK_VIEWPOINT_COLLISION", "$.identity_links",
                "identity component is not viewpoint-to-slot injective",
            )
        parent[right_root] = left_root
    groups = {}
    for unit_id in units:
        groups.setdefault(find(unit_id), []).append(unit_id)
    return sorted((sorted(value) for value in groups.values()), key=lambda value: value)


def _derive_universe(scope, template, observations, links):
    units = _units(observations)
    groups = _subject_groups(units, links)
    relation = [item for item in template["predicates"] if item["kind"] == "relation"]
    room = [item for item in template["predicates"] if item["kind"] == "room_anchor"]
    hypotheses = []
    obligations = []

    def add_hypothesis(kind, binding, event_ids):
        hypothesis_id = "hyp-" + canonical_sha256({
            "scope_digest": canonical_sha256(scope),
            "template_id": template["template_id"],
            "hypothesis_kind": kind,
            "binding": binding,
        })[:24]
        hypotheses.append({
            "hypothesis_id": hypothesis_id,
            "hypothesis_kind": kind,
            "binding": copy.deepcopy(binding),
            "derivation_event_ids": sorted(set(event_ids)),
        })
        predicates = template["predicates"] if kind not in _RESIDUAL_HYPOTHESIS_KINDS else [{
            "predicate_id": "coverage:" + template["template_id"],
            "kind": "coverage", "necessary": True,
            "anchor_role": None, "spatial_anchor_id": None,
        }]
        for predicate in predicates:
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

    events_by_unit = {key: value["source_event_ids"] for key, value in units.items()}
    events_by_viewpoint = {}
    for observation in observations:
        events_by_viewpoint.setdefault(observation["viewpoint"], []).append(
            observation["event_id"],
        )
    if relation:
        for subject_units in groups:
            subject_vps = {units[key]["viewpoint_id"] for key in subject_units}
            for anchor_units in groups:
                if subject_units == anchor_units:
                    continue
                anchor_vps = {units[key]["viewpoint_id"] for key in anchor_units}
                for viewpoint in sorted(subject_vps & anchor_vps):
                    events = sum((events_by_unit[key] for key in subject_units + anchor_units), [])
                    add_hypothesis(
                        "subject_relation",
                        _binding(subject_units, anchor_units, viewpoint, None),
                        events,
                    )
            for viewpoint in sorted(subject_vps):
                subject_events = sum((
                    events_by_unit[key] for key in subject_units
                    if units[key]["viewpoint_id"] == viewpoint
                ), [])
                add_hypothesis(
                    "anchor_residual",
                    _binding(subject_units, [], viewpoint, None),
                    subject_events + events_by_viewpoint.get(viewpoint, []),
                )
    elif room:
        spatial_anchor_id = room[0]["spatial_anchor_id"]
        for subject_units in groups:
            viewpoints = sorted({units[key]["viewpoint_id"] for key in subject_units})
            for viewpoint in viewpoints:
                events = sum((events_by_unit[key] for key in subject_units), [])
                add_hypothesis(
                    "subject_room", _binding(subject_units, [], viewpoint, spatial_anchor_id), events,
                )
    else:
        for subject_units in groups:
            viewpoints = sorted({units[key]["viewpoint_id"] for key in subject_units})
            events = sum((events_by_unit[key] for key in subject_units), [])
            add_hypothesis("subject", _binding(subject_units, [], viewpoints[0], None), events)
    for viewpoint in sorted(events_by_viewpoint):
        add_hypothesis(
            "location_residual", _binding([], [], viewpoint, None), events_by_viewpoint[viewpoint],
        )
    hypotheses.sort(key=lambda item: item["hypothesis_id"])
    obligations.sort(key=lambda item: item["obligation_id"])
    bindings = sorted([copy.deepcopy(item["binding"]) for item in hypotheses], key=canonical_json)
    return {
        "units": sorted(units.values(), key=lambda item: item["unit_id"]),
        "bindings": bindings,
        "hypotheses": hypotheses,
        "obligations": obligations,
        "binding_digest": canonical_sha256(bindings),
        "universe_digest": canonical_sha256({
            "hypotheses": hypotheses,
            "obligations": obligations,
            "generator_version": template["generator_version"],
        }),
    }


def _offline_m3_signal(signal, observation, template):
    """Independently validate the self-contained, tensor-digest signal."""

    signal = _exact(signal, _M3_SIGNAL_FIELDS, "$.bound_evidence.signal")
    expected_constants = {
        "schema_version": SCHEMA_VERSIONS["duet_model_signal"],
        "producer": "proofnav.perception.duet_signal.build_duet_signal",
        "source_schema": "duet.reverie.forward_navigation_per_step@frozen-m0",
        "signal_semantics": "uncalibrated_duet_object_proposal_score",
        "evidence_authority": False,
    }
    for key, expected in expected_constants.items():
        if signal[key] != expected:
            _fail("OFFLINE_M3_SIGNAL_SEMANTICS", "$.bound_evidence.signal." + key, "constant mismatch")
    source = validate_observation(signal["observation"])
    if source != observation:
        _fail("OFFLINE_M3_SIGNAL_OBSERVATION", "$.bound_evidence.signal.observation", "admitted observation mismatch")
    if (signal["observation_digest"] != canonical_sha256(source)
            or signal["instruction_digest"] != canonical_sha256(source["instruction"])
            or signal["template_digest"] != canonical_sha256(template)):
        _fail("OFFLINE_M3_SIGNAL_IDENTITY", "$.bound_evidence.signal", "observation/instruction/template changed")
    _sha256(signal["observation_digest"], "$.bound_evidence.signal.observation_digest")
    _sha256(signal["instruction_digest"], "$.bound_evidence.signal.instruction_digest")
    _sha256(signal["template_digest"], "$.bound_evidence.signal.template_digest")
    identity = _exact(signal["model_identity"], _M3_MODEL_FIELDS, "$.bound_evidence.signal.model_identity")
    for key in sorted(identity):
        _sha256(identity[key], "$.bound_evidence.signal.model_identity." + key)

    scores = _exact(signal["object_scores"], {
        "proposal_ids", "valid_mask", "logits", "selected_index",
        "selected_proposal_id", "selected_statistic",
    }, "$.bound_evidence.signal.object_scores")
    proposals, mask, logits = (
        scores["proposal_ids"], scores["valid_mask"], scores["logits"],
    )
    if (not isinstance(proposals, list) or proposals != source["object_proposal_ids"]
            or len(proposals) != len(set(proposals))
            or not isinstance(mask, list) or not isinstance(logits, list)
            or len(mask) != len(proposals) or len(logits) != len(proposals)
            or any(not isinstance(item, bool) for item in mask)):
        _fail("OFFLINE_M3_SIGNAL_SCORES", "$.bound_evidence.signal.object_scores", "unaligned scores")
    logits = [
        _finite(value, "$.bound_evidence.signal.object_scores.logits[%d]" % index)
        for index, value in enumerate(logits)
    ]
    valid = [index for index, item in enumerate(mask) if item]
    if not valid:
        if any(scores[key] is not None for key in (
                "selected_index", "selected_proposal_id", "selected_statistic")):
            _fail("OFFLINE_M3_SIGNAL_SELECTION", "$.bound_evidence.signal.object_scores", "empty selection must be null")
    else:
        selected = max(valid, key=lambda index: (logits[index], -index))
        if (scores["selected_index"] != selected
                or scores["selected_proposal_id"] != proposals[selected]
                or _finite(scores["selected_statistic"], "$.bound_evidence.signal.object_scores.selected_statistic") != logits[selected]):
            _fail("OFFLINE_M3_SIGNAL_SELECTION", "$.bound_evidence.signal.object_scores", "not the canonical maximum")

    contents = _exact(signal["content_digests"], {
        "panorama_features", "object_features", "object_angle_features",
        "object_box_features", "instruction_encoding",
    }, "$.bound_evidence.signal.content_digests")
    packed_view_rows = (
        len(source["candidates"]) + 36
        - len({item["point_id"] for item in source["candidates"]})
    )
    expected_shapes = {
        "panorama_features": [
            packed_view_rows,
            source["field_schema"]["feature"]["shape"][1],
        ],
        "object_features": source["field_schema"]["obj_img_fts"]["shape"],
        "object_angle_features": source["field_schema"]["obj_ang_fts"]["shape"],
        "object_box_features": source["field_schema"]["obj_box_fts"]["shape"],
        "instruction_encoding": [source["instruction_encoding_length"]],
    }
    for name, item in contents.items():
        item = _exact(item, {"digest", "dtype", "shape"}, "$.bound_evidence.signal.content_digests." + name)
        _sha256(item["digest"], "$.bound_evidence.signal.content_digests.%s.digest" % name)
        expected_dtype = "int64" if name == "instruction_encoding" else "float32"
        if item["dtype"] != expected_dtype or item["shape"] != expected_shapes[name]:
            _fail("OFFLINE_M3_SIGNAL_CONTENT", "$.bound_evidence.signal.content_digests." + name, "shape/dtype mismatch")
    sealed = copy.deepcopy(signal)
    digest = sealed.pop("signal_digest")
    if digest != canonical_sha256(sealed):
        _fail("OFFLINE_M3_SIGNAL_DIGEST", "$.bound_evidence.signal.signal_digest", "signal changed")
    return signal


def _offline_m3_artifact(artifact, signal):
    artifact = _exact(artifact, _M3_ARTIFACT_FIELDS, "$.bound_evidence.calibration_artifact")
    constants = {
        "schema_version": SCHEMA_VERSIONS["calibration_artifact"],
        "evidence_family": "duet_annotated_slot_entity_grounding",
        "predicate_kind": "entity", "polarity": "SUPPORTS",
        "score_semantics": "selected_absolute_object_logit",
        "calibration_method": "fixed_threshold_descriptive_micro",
        "sample_unit": "scan_familywise",
        "dependency_unit": "source_observation_lineage",
        "risk_event": "false_support",
    }
    for key, expected in constants.items():
        if artifact[key] != expected:
            _fail("OFFLINE_M3_ARTIFACT_SEMANTICS", "$.bound_evidence.calibration_artifact." + key, "constant mismatch")
    if artifact["model_identity"] != signal["model_identity"]:
        _fail("OFFLINE_M3_ARTIFACT_MODEL", "$.bound_evidence.calibration_artifact.model_identity", "signal mismatch")
    _exact(artifact["model_identity"], _M3_MODEL_FIELDS, "$.bound_evidence.calibration_artifact.model_identity")
    for key in _M3_MODEL_FIELDS:
        _sha256(artifact["model_identity"][key], "$.bound_evidence.calibration_artifact.model_identity." + key)
    for key in ("label_definition_digest", "split_fingerprint"):
        _sha256(artifact[key], "$.bound_evidence.calibration_artifact." + key)
    splits = artifact["split_names"]
    if (not isinstance(splits, list) or not splits or splits != sorted(set(splits))
            or any(not isinstance(item, str) or not item for item in splits)):
        _fail("OFFLINE_M3_ARTIFACT_SPLITS", "$.bound_evidence.calibration_artifact.split_names", "invalid splits")
    for name in splits:
        normalized = name.lower().replace("-", "_")
        if normalized == "test" or normalized.startswith("test_") or "val_unseen" in normalized:
            _fail("OFFLINE_M3_CALIBRATION_LEAKAGE", "$.bound_evidence.calibration_artifact.split_names", "forbidden split")
    params = _exact(artifact["calibration_parameters"], {"support_threshold"}, "$.bound_evidence.calibration_artifact.calibration_parameters")
    _finite(params["support_threshold"], "$.bound_evidence.calibration_artifact.calibration_parameters.support_threshold")
    domain = _exact(artifact["validity_domain"], {
        "domain_id", "calibration_scan_ids", "applicability_scan_ids",
        "shift_policy",
    }, "$.bound_evidence.calibration_artifact.validity_domain")
    if (domain["domain_id"] != "descriptive_seen_scan_micro"
            or domain["shift_policy"] != "exact_match_or_abstain"):
        _fail("OFFLINE_M3_ARTIFACT_DOMAIN", "$.bound_evidence.calibration_artifact.validity_domain", "unregistered domain")
    scan_sets = []
    for field in ("calibration_scan_ids", "applicability_scan_ids"):
        values = domain[field]
        if (not isinstance(values, list) or not values
                or values != sorted(set(values))
                or any(not isinstance(item, str) or not item for item in values)):
            _fail("OFFLINE_M3_ARTIFACT_DOMAIN", "$.bound_evidence.calibration_artifact.validity_domain." + field, "invalid scan set")
        scan_sets.append(set(values))
    if scan_sets[0] & scan_sets[1]:
        _fail("OFFLINE_M3_CALIBRATION_APPLICATION_OVERLAP", "$.bound_evidence.calibration_artifact.validity_domain", "scan overlap")
    if signal["observation"]["scan"] not in scan_sets[1]:
        _fail("OFFLINE_M3_ARTIFACT_SHIFT", "$.bound_evidence.signal.observation.scan", "out of domain")
    bound = _exact(artifact["risk_bound"], {"upper_bound", "confidence", "semantics"}, "$.bound_evidence.calibration_artifact.risk_bound")
    _finite(bound["upper_bound"], "$.bound_evidence.calibration_artifact.risk_bound.upper_bound", 0, 1)
    if (bound["confidence"] is not None
            or bound["semantics"] != "descriptive_compatibility_not_statistical_guarantee"):
        _fail("OFFLINE_M3_ARTIFACT_BOUND", "$.bound_evidence.calibration_artifact.risk_bound", "wrong semantics")
    counts = _exact(artifact["aggregate_counts"], {"scans", "examples", "errors"}, "$.bound_evidence.calibration_artifact.aggregate_counts")
    if (any(isinstance(counts[key], bool) or not isinstance(counts[key], int) or counts[key] < 0 for key in counts)
            or counts["scans"] == 0 or counts["examples"] == 0
            or counts["errors"] > counts["scans"]):
        _fail("OFFLINE_M3_ARTIFACT_COUNTS", "$.bound_evidence.calibration_artifact.aggregate_counts", "invalid aggregate")
    generation = _exact(artifact["generation"], {"command", "producer", "source_revision"}, "$.bound_evidence.calibration_artifact.generation")
    if (generation["producer"] != "proofnav.calibration.artifact.build_calibration_artifact"
            or any(not isinstance(item, str) or not item for item in generation.values())):
        _fail("OFFLINE_M3_ARTIFACT_PRODUCER", "$.bound_evidence.calibration_artifact.generation", "wrong producer")
    sealed = copy.deepcopy(artifact)
    digest = sealed.pop("artifact_digest")
    if digest != canonical_sha256(sealed):
        _fail("OFFLINE_M3_ARTIFACT_DIGEST", "$.bound_evidence.calibration_artifact.artifact_digest", "artifact changed")
    if not is_registered_calibration_artifact_digest(digest):
        _fail(
            "OFFLINE_M3_ARTIFACT_NOT_REGISTERED",
            "$.bound_evidence.calibration_artifact.artifact_digest",
            "artifact digest is not in the code-owned calibration registry",
        )
    return artifact


def _offline_m3_extension(wrapper, query, evidence, observation, scope, template):
    signal = _offline_m3_signal(wrapper["signal"], observation, template)
    artifact = _offline_m3_artifact(wrapper["calibration_artifact"], signal)
    if not is_registered_signal_digest(
            artifact["artifact_digest"], signal["signal_digest"]):
        _fail(
            "OFFLINE_M3_SIGNAL_NOT_REGISTERED",
            "$.bound_evidence.signal.signal_digest",
            "signal is outside the sealed recorded micro replay",
        )
    expected_calibration = (
        "proofnav.calibration-artifact.v1:" + artifact["artifact_digest"]
    )
    if scope["calibration_version"] != expected_calibration:
        _fail(
            "OFFLINE_M3_RISK_CALIBRATION_VERSION",
            "$.scope.calibration_version",
            "scope does not name the exact evidence artifact digest",
        )
    if wrapper["predicate_kind"] != "entity" or evidence["claim"] != "SUPPORTS":
        _fail("OFFLINE_M3_POLARITY", "$.bound_evidence", "only entity SUPPORT is admitted")
    scores = signal["object_scores"]
    if scores["selected_index"] is None:
        _fail("OFFLINE_M3_ABSTAIN", "$.bound_evidence.signal", "empty signal cannot enter ledger")
    if scores["selected_statistic"] < artifact["calibration_parameters"]["support_threshold"]:
        _fail("OFFLINE_M3_ABSTAIN", "$.bound_evidence.signal", "below-threshold signal cannot enter ledger")
    if len(wrapper["binding"]["subject_unit_ids"]) != 1:
        _fail("OFFLINE_M3_BINDING", "$.bound_evidence.binding", "single subject slot required")
    expected_unit = _object_unit_id(observation["viewpoint"], scores["selected_proposal_id"])
    if wrapper["binding"]["subject_unit_ids"] != [expected_unit] or evidence["unit_id"] != expected_unit:
        _fail("OFFLINE_M3_BINDING", "$.bound_evidence.binding", "selected slot mismatch")
    dependency = "duet-observation:%s" % observation["event_id"]
    adapter_version = "proofnav.duet-entity-support-adapter.v1"
    adapter_producer = "proofnav.perception.evidence_adapter.adapt_entity_signal"
    atom_id = "atom-" + canonical_sha256({
        "signal_digest": signal["signal_digest"],
        "artifact_digest": artifact["artifact_digest"],
        "query_id": query["query_id"], "polarity": "SUPPORTS",
    })[:24]
    decision = _exact(wrapper["adapter_decision"], _M3_DECISION_FIELDS, "$.bound_evidence.adapter_decision")
    expected_decision = {
        "schema_version": SCHEMA_VERSIONS["adapter_decision"],
        "decision": "SUPPORTS", "reason_code": "CALIBRATED_SUPPORT",
        "evidence_family": "duet_annotated_slot_entity_grounding",
        "predicate_kind": "entity", "polarity": "SUPPORTS",
        "query_id": query["query_id"], "hypothesis_id": query["hypothesis_id"],
        "obligation_id": query["obligation_id"], "predicate_id": query["predicate_id"],
        "binding": query["binding"], "source_observation_digest": signal["observation_digest"],
        "signal_digest": signal["signal_digest"], "artifact_digest": artifact["artifact_digest"],
        "domain_id": artifact["validity_domain"]["domain_id"],
        "selected_statistic": scores["selected_statistic"],
        "dependency_group": dependency, "adapter_version": adapter_version,
        "adapter_producer": adapter_producer, "risk_atom_id": atom_id,
    }
    for key, expected in expected_decision.items():
        if decision[key] != expected:
            _fail("OFFLINE_M3_DECISION", "$.bound_evidence.adapter_decision." + key, "decision mismatch")
    identity = copy.deepcopy(decision)
    decision_id = identity.pop("decision_id")
    decision_digest = identity.pop("decision_digest")
    expected_id = "decision-" + canonical_sha256(identity)[:24]
    if decision_id != expected_id:
        _fail("OFFLINE_M3_DECISION_ID", "$.bound_evidence.adapter_decision.decision_id", "noncanonical ID")
    sealed = copy.deepcopy(decision)
    sealed.pop("decision_digest")
    if decision_digest != canonical_sha256(sealed):
        _fail("OFFLINE_M3_DECISION_DIGEST", "$.bound_evidence.adapter_decision.decision_digest", "decision changed")
    expected_evidence_id = "evidence-" + canonical_sha256({
        "decision_digest": decision_digest,
        "scope_contract_id": scope["scope_contract_id"],
    })[:24]
    if (evidence["evidence_id"] != expected_evidence_id
            or evidence["adapter_version"] != adapter_version
            or evidence["dependency_group"] != dependency
            or evidence["audit_trail"] != {
                "producer": adapter_producer,
                "source_field": "object_scores.selected_statistic",
            }):
        _fail("OFFLINE_M3_EVIDENCE_PROVENANCE", "$.bound_evidence.evidence", "adapter output mismatch")
    atom = _exact(wrapper["risk_atom"], _M3_ATOM_FIELDS, "$.bound_evidence.risk_atom")
    expected_atom = {
        "schema_version": SCHEMA_VERSIONS["risk_atom"], "atom_id": atom_id,
        "event_type": "false_support", "polarity": "SUPPORTS",
        "upper_bound": artifact["risk_bound"]["upper_bound"], "familywise": True,
        "family_key": "artifact:%s:source-observation:%s" % (
            artifact["artifact_digest"], observation["event_id"],
        ),
        "evidence_id": expected_evidence_id, "artifact_digest": artifact["artifact_digest"],
        "signal_digest": signal["signal_digest"], "dependency_group": dependency,
    }
    expected_atom["atom_digest"] = canonical_sha256(expected_atom)
    if atom != expected_atom:
        _fail("OFFLINE_M3_RISK_ATOM", "$.bound_evidence.risk_atom", "atom mismatch")
    return wrapper


def _validate_bound_evidence(
        wrapper, observations, queries, universe, profile, scope, template):
    m3_mode = profile["profile_id"] == _M3_PROFILE_ID
    base_fields = {
        "schema_version", "query_id", "hypothesis_id", "obligation_id",
        "predicate_id", "predicate_kind", "binding", "source_observation_digest",
        "evidence",
    }
    fields = base_fields | ({
        "signal", "calibration_artifact", "adapter_decision", "risk_atom",
    } if m3_mode else set())
    wrapper = _exact(wrapper, fields, "$.bound_evidence")
    expected_schema = SCHEMA_VERSIONS[
        "m3_bound_evidence" if m3_mode else "bound_evidence"
    ]
    if wrapper["schema_version"] != expected_schema:
        _fail("SCHEMA_VERSION", "$.bound_evidence.schema_version", "wrong bound-evidence version")
    query = queries.get(wrapper["query_id"])
    if query is None:
        _fail("OFFLINE_EVIDENCE_QUERY", "$.bound_evidence.query_id", "query must precede evidence")
    obligation = next((
        item for item in universe["obligations"]
        if item["obligation_id"] == wrapper["obligation_id"]
    ), None)
    if obligation is None:
        _fail("OFFLINE_EVIDENCE_OBLIGATION", "$.bound_evidence.obligation_id", "unknown obligation")
    expected = {
        "hypothesis_id": obligation["hypothesis_id"],
        "obligation_id": obligation["obligation_id"],
        "predicate_id": obligation["predicate_id"],
        "predicate_kind": obligation["predicate_kind"],
        "binding": obligation["binding_requirement"],
    }
    for key, expected_value in expected.items():
        if wrapper[key] != expected_value or query.get(key) != expected_value:
            _fail("OFFLINE_EVIDENCE_BINDING", "$.bound_evidence." + key, "query/obligation mismatch")
    _validate_binding(wrapper["binding"], "$.bound_evidence.binding")
    observation_map = {item["event_id"]: item for item in observations}
    evidence = wrapper["evidence"]
    validate_evidence(evidence, observation_map)
    if evidence["scope_contract_id"] != scope["scope_contract_id"]:
        _fail(
            "OFFLINE_EVIDENCE_SCOPE", "$.bound_evidence.evidence.scope_contract_id",
            "evidence belongs to a different scope contract",
        )
    if evidence["obligation_id"] != wrapper["obligation_id"] or evidence["predicate_id"] != wrapper["predicate_id"]:
        _fail("OFFLINE_EVIDENCE_INDEX", "$.bound_evidence.evidence", "index mismatch")
    observation = observation_map[evidence["source_event_id"]]
    if wrapper["source_observation_digest"] != canonical_sha256(observation):
        _fail("OFFLINE_EVIDENCE_OBSERVATION", "$.bound_evidence.source_observation_digest", "source changed")
    if profile["evidence_mode"] == "production_zero":
        _fail("OFFLINE_EVIDENCE_FIREWALL", "$.bound_evidence", "production admission is sealed")
    if m3_mode:
        _offline_m3_extension(
            wrapper, query, evidence, observation, scope, template,
        )
        return wrapper
    if (evidence["adapter_version"] != "proofnav.controlled-oracle.replay.v2"
            or evidence["audit_trail"]["producer"] != "proofnav.offline.OracleEvidenceProvider.v2"):
        _fail("OFFLINE_EVIDENCE_PROVENANCE", "$.bound_evidence.evidence", "wrong controlled source")
    if evidence["dependency_group"] != "controlled-replay:%s" % evidence["source_event_id"]:
        _fail(
            "OFFLINE_EVIDENCE_PROVENANCE", "$.bound_evidence.evidence.dependency_group",
            "dependency group does not bind the source observation",
        )
    binding = wrapper["binding"]
    unit_map = {item["unit_id"]: item for item in universe["units"]}
    source_units = {
        unit_id for unit_id, record in unit_map.items()
        if evidence["source_event_id"] in record["source_event_ids"]
    }
    if wrapper["predicate_kind"] == "coverage":
        if evidence["evidence_role"] != "viewpoint_view":
            _fail("OFFLINE_EVIDENCE_ROLE", "$.bound_evidence", "coverage needs viewpoint view")
        if (evidence["unit_id"] != _view_unit_id(observation["viewpoint"])
                or binding["location_binding_id"] != _location_binding_id(observation["viewpoint"])):
            _fail("OFFLINE_EVIDENCE_COVERAGE_BINDING", "$.bound_evidence", "wrong viewpoint")
    else:
        if evidence["evidence_role"] != "object_slot":
            _fail("OFFLINE_EVIDENCE_ROLE", "$.bound_evidence", "predicate needs object slot")
        if evidence["unit_id"] not in binding["subject_unit_ids"] or evidence["unit_id"] not in source_units:
            _fail("OFFLINE_EVIDENCE_SUBJECT", "$.bound_evidence", "wrong subject")
        if wrapper["predicate_kind"] == "relation":
            if not binding["anchor_unit_ids"] or not (set(binding["anchor_unit_ids"]) & source_units):
                _fail("OFFLINE_EVIDENCE_ANCHOR", "$.bound_evidence", "anchor not co-observed")
            if binding["location_binding_id"] != _location_binding_id(observation["viewpoint"]):
                _fail(
                    "OFFLINE_EVIDENCE_RELATION_LOCATION", "$.bound_evidence",
                    "relation source viewpoint does not match hypothesis location",
                )
        if wrapper["predicate_kind"] == "room_anchor":
            if (binding["location_binding_id"] != _location_binding_id(observation["viewpoint"])
                    or binding["spatial_anchor_id"] is None):
                _fail("OFFLINE_EVIDENCE_ROOM", "$.bound_evidence", "wrong room binding")
    return wrapper


def recompute_offline_state(base_bundle, _validate_continues=True):
    """Independently fold a six-field audit base bundle into proof state."""

    base_bundle = _exact(copy.deepcopy(base_bundle), {
        "schema_version", "scope", "template", "admission_profile",
        "risk_claims", "transitions",
    }, "$")
    if base_bundle["schema_version"] != SCHEMA_VERSIONS["audit_bundle"]:
        _fail("SCHEMA_VERSION", "$.schema_version", "audit-bundle v2 required")
    scope = base_bundle["scope"]
    validate_scope(scope)
    template = _validate_template(base_bundle["template"])
    profile = _validate_profile(base_bundle["admission_profile"], scope)
    if profile["evidence_mode"] == "m3_entity_support":
        if base_bundle["risk_claims"] != {}:
            _fail(
                "OFFLINE_M3_CALLER_RISK", "$.risk_claims",
                "M3 risk must be composed from selected evidence",
            )
        risks = {}
    else:
        risks = _validate_risk_claims(base_bundle["risk_claims"], scope)
    transitions = base_bundle["transitions"]
    tip = _validate_transition_chain(transitions)
    observations = []
    links = []
    queries = {}
    evidence_by_id = {}
    fingerprints = set()
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
                _fail("OFFLINE_LINK_FIREWALL", "$.identity_link", "production linking sealed")
            link = _validate_identity_witness(payload, observations, profile)
            if link["link_id"] in {item["link_id"] for item in links}:
                _fail("OFFLINE_LINK_DUPLICATE", "$.identity_link", "duplicate link")
            candidate_links = links + [link]
            _subject_groups(_units(observations), candidate_links)
            links.append(link)
        elif event_type == "QUERY":
            payload = _exact(payload, {
                "query_id", "hypothesis_id", "obligation_id", "predicate_id",
                "predicate_kind", "binding",
            }, "$.query")
            universe = _derive_universe(scope, template, observations, links)
            obligation = next((
                item for item in universe["obligations"]
                if item["obligation_id"] == payload["obligation_id"]
            ), None)
            if obligation is None:
                _fail("OFFLINE_QUERY_OBLIGATION", "$.query", "unknown obligation")
            expected = {
                "hypothesis_id": obligation["hypothesis_id"],
                "obligation_id": obligation["obligation_id"],
                "predicate_id": obligation["predicate_id"],
                "predicate_kind": obligation["predicate_kind"],
                "binding": obligation["binding_requirement"],
            }
            for key, expected_value in expected.items():
                if payload[key] != expected_value:
                    _fail("OFFLINE_QUERY_BINDING", "$.query." + key, "obligation mismatch")
            if payload["query_id"] != "query-" + canonical_sha256(expected)[:24]:
                _fail("OFFLINE_QUERY_ID", "$.query.query_id", "non-canonical ID")
            if payload["query_id"] in queries:
                _fail("OFFLINE_QUERY_DUPLICATE", "$.query.query_id", "duplicate query")
            queries[payload["query_id"]] = copy.deepcopy(payload)
        elif event_type == "EVIDENCE":
            universe = _derive_universe(scope, template, observations, links)
            wrapper = _validate_bound_evidence(
                payload, observations, queries, universe, profile, scope,
                template,
            )
            evidence_id = wrapper["evidence"]["evidence_id"]
            if evidence_id in evidence_by_id:
                _fail("OFFLINE_EVIDENCE_DUPLICATE", "$.bound_evidence", "duplicate ID")
            semantic = copy.deepcopy(wrapper)
            semantic["evidence"].pop("evidence_id", None)
            fingerprint = canonical_sha256(semantic)
            if fingerprint in fingerprints:
                _fail("OFFLINE_EVIDENCE_DUPLICATE", "$.bound_evidence", "semantic duplicate")
            fingerprints.add(fingerprint)
            evidence_by_id[evidence_id] = copy.deepcopy(wrapper)
        elif event_type == "REVOKE":
            payload = _exact(payload, {"evidence_id", "reason"}, "$.revoke")
            _string(payload["reason"], "$.revoke.reason")
            if payload["evidence_id"] not in evidence_by_id or payload["evidence_id"] in revoked:
                _fail("OFFLINE_REVOKE", "$.revoke.evidence_id", "unknown/already revoked")
            revoked.add(payload["evidence_id"])
        elif event_type == "CONTINUE":
            payload = _exact(payload, {
                "terminal_decision", "terminal_digest", "proof_state_digest",
                "rejected_certificate_digest",
            }, "$.continue")
            if payload["terminal_digest"] != canonical_sha256(payload["terminal_decision"]):
                _fail("OFFLINE_CONTINUE_TERMINAL", "$.continue.terminal_digest", "terminal was modified")
            _string(payload["proof_state_digest"], "$.continue.proof_state_digest")
            _nullable_string(payload["rejected_certificate_digest"], "$.continue.rejected_certificate_digest")
            terminal = payload["terminal_decision"]
            if _validate_continues:
                prior_base = copy.deepcopy(base_bundle)
                prior_base["transitions"] = transitions[:transition["transition_seq"]]
                prior = recompute_offline_state(
                    prior_base, _validate_continues=False,
                )
                if payload["proof_state_digest"] != prior["proof_state_digest"]:
                    _fail("OFFLINE_CONTINUE_STATE", "$.continue", "not the prior state")
                _validate_continue_terminal(
                    terminal, prior, payload["rejected_certificate_digest"],
                )
            continues.append(copy.deepcopy(payload))

    expected_instruction_digest = template["audit_trail"]["source_instruction_digest"]
    for observation in observations:
        if canonical_sha256(observation["instruction"]) != expected_instruction_digest:
            _fail("OFFLINE_TEMPLATE_INSTRUCTION", "$.observations", "instruction digest mismatch")

    topology = _topology(scope, observations, profile)
    universe = _derive_universe(scope, template, observations, links)
    active = [
        copy.deepcopy(evidence_by_id[key])
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
        status = "OPEN"
        if support_ids and refute_ids:
            status = "CONFLICTED"
        elif support_ids:
            status = "SATISFIED"
        elif refute_ids:
            status = "REFUTED"
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
    # Independent implementation of the frozen M2.1 controlled convention:
    # initial observation is step zero; every later step follows one action.
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
    state = {
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
        "risk_claims": risks,
        "continue_count": len(continues),
    }
    state["proof_state_digest"] = canonical_sha256(state)
    state["audit_trail"] = {
        "producer": "proofnav.runtime.state.v2",
        "transition_count": len(transitions),
        "transition_tip": tip,
        "admission_profile_id": profile["profile_id"],
    }
    return state


def validate_audit_bundle(audit_bundle):
    """Validate bundle identity and compare its state with an independent fold."""

    bundle = copy.deepcopy(audit_bundle)
    bundle = _exact(bundle, {
        "schema_version", "scope", "template", "admission_profile",
        "risk_claims", "transitions", "state", "bundle_digest",
    }, "$")
    digest_payload = copy.deepcopy(bundle)
    claimed = digest_payload.pop("bundle_digest")
    if claimed != canonical_sha256(digest_payload):
        _fail("OFFLINE_BUNDLE_DIGEST", "$.bundle_digest", "bundle was modified")
    base = {
        key: copy.deepcopy(bundle[key]) for key in (
            "schema_version", "scope", "template", "admission_profile",
            "risk_claims", "transitions",
        )
    }
    recomputed = recompute_offline_state(base)
    if bundle["state"] != recomputed:
        _fail("OFFLINE_STATE_MISMATCH", "$.state", "state does not match raw transitions")
    return recomputed


def structural_result(audit_bundle):
    """Return a stable non-throwing structural result for taxonomy code."""

    try:
        state = validate_audit_bundle(audit_bundle)
        return {"valid": True, "reason_codes": [], "state": state}
    except ContractViolation as error:
        return {
            "valid": False,
            "reason_codes": [error.code],
            "state": None,
        }
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return {
            "valid": False,
            "reason_codes": ["OFFLINE_STRUCTURE_INVALID"],
            "state": None,
        }


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
_ONLINE_FIELDS = {
    "schema_version", "status", "accepted", "requested_verdict",
    "reason_codes", "missing_obligation_ids", "uncovered_hypothesis_ids",
    "frontier_viewpoint_ids", "scope_digest", "template_digest",
    "universe_digest", "binding_digest", "decision_cut", "transition_tip",
    "proof_state_digest", "certificate_id", "certificate_digest",
    "calculated_certificate_digest", "structured_feedback",
}
_FEEDBACK_FIELDS = {
    "recommended_action", "reason_codes", "missing_obligation_ids",
    "uncovered_hypothesis_ids", "frontier_viewpoint_ids",
}
_TERMINAL_FIELDS = {
    "schema_version", "directive", "terminal", "semantic_verdict", "cause",
    "proposed_verdict", "proposed_certificate_id",
    "proposed_certificate_digest", "accepted_certificate_id",
    "accepted_certificate_digest", "decision_cut", "transition_tip",
    "proof_state_digest", "certificate_accepted", "online_verification",
    "feedback", "duet_signal",
}
_EXECUTION_FIELDS = {
    "duet_stop", "no_frontier", "max_step", "budget_exhausted",
    "executable_action_available", "searchable_frontier", "execution_error",
}


def certificate_identity(certificate):
    """Return claimed and independently calculated certificate identities."""

    if not isinstance(certificate, dict):
        return None, None, None
    claimed_id = certificate.get("certificate_id")
    claimed_digest = certificate.get("certificate_digest")
    try:
        body = copy.deepcopy(certificate)
        body.pop("certificate_id", None)
        body.pop("certificate_digest", None)
        calculated = canonical_sha256(body)
    except (TypeError, ValueError):
        calculated = None
    return claimed_id, claimed_digest, calculated


def _certificate_indexes(state):
    hypotheses = {item["hypothesis_id"]: item for item in state["hypotheses"]}
    obligations = {item["obligation_id"]: item for item in state["obligations"]}
    by_hypothesis = {key: [] for key in hypotheses}
    for obligation in state["obligations"]:
        by_hypothesis[obligation["hypothesis_id"]].append(obligation)
    for values in by_hypothesis.values():
        values.sort(key=lambda item: item["obligation_id"])
    evidence = {
        item["evidence"]["evidence_id"]: item
        for item in state["active_bound_evidence"]
    }
    return hypotheses, obligations, by_hypothesis, evidence


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
        and isinstance(item.get("evidence_ids"), list)
        and bool(item["evidence_ids"])
        and all(isinstance(value, str) and value for value in item["evidence_ids"])
        and len(item["evidence_ids"]) == len(set(item["evidence_ids"]))
    )


def _wrapper_matches(wrapper, hypothesis, obligation, polarity, state):
    evidence = wrapper.get("evidence", {})
    cut = state["decision_cut"]
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
        and evidence.get("source_event_id") in state["topology"]["observation_event_ids"]
    )


def audit_certificate(audit_bundle, certificate, state=None):
    """Independently audit certificate structure and proof semantics."""

    reasons = []
    try:
        if state is None:
            state = validate_audit_bundle(audit_bundle)
        if not isinstance(certificate, dict):
            return {
                "valid": False, "reason_codes": ["OFFLINE_CERTIFICATE_TYPE"],
                "requested_verdict": None,
            }
        if set(certificate) != _CERTIFICATE_FIELDS:
            reasons.append("OFFLINE_CERTIFICATE_SCHEMA")
        if certificate.get("schema_version") != SCHEMA_VERSIONS["m2_certificate"]:
            reasons.append("OFFLINE_CERTIFICATE_VERSION")
        requested = certificate.get("requested_verdict")
        if requested not in ("FOUND", "NOT_FOUND"):
            reasons.append("OFFLINE_CERTIFICATE_VERDICT")
        expected_type = {
            "FOUND": "positive", "NOT_FOUND": "refutation_cover",
        }.get(requested)
        if certificate.get("certificate_type") != expected_type:
            reasons.append("OFFLINE_CERTIFICATE_TYPE_VERDICT")
        claimed_id, claimed_digest, calculated = certificate_identity(certificate)
        if claimed_digest != calculated:
            reasons.append("OFFLINE_CERTIFICATE_DIGEST")
        if calculated is None or claimed_id != "cert-" + calculated[:20]:
            reasons.append("OFFLINE_CERTIFICATE_ID")

        expected_identity = {
            "episode_id": state["episode_id"],
            "scope_contract_id": state["scope_contract_id"],
            "scope_version": state["scope_version"],
            "scope_digest": state["scope_digest"],
            "template_id": state["template_id"],
            "template_digest": state["template_digest"],
            "proof_state_version": state["state_version"],
            "decision_cut": state["decision_cut"],
            "transition_tip": state["transition_tip"],
            "proof_state_digest": state["proof_state_digest"],
            "audit_bundle_digest": audit_bundle["bundle_digest"],
            "universe_digest": state["universe_digest"],
            "binding_digest": state["binding_digest"],
            "closure_witness": state["closure_witness"],
            "ledger_digest": state["ledger_digest"],
        }
        for key, expected in expected_identity.items():
            if certificate.get(key) != expected:
                reasons.append("OFFLINE_CERTIFICATE_%s" % key.upper())
        if certificate.get("budget_snapshot") != state["budget_status"]:
            reasons.append("OFFLINE_CERTIFICATE_BUDGET")
        if certificate.get("cost_snapshot") != state["cost_ledger"]:
            reasons.append("OFFLINE_CERTIFICATE_COST")
        if not state["budget_status"]["within_budget"]:
            reasons.append("OFFLINE_CERTIFICATE_BUDGET_EXHAUSTED")
        m3_profile = (
            state.get("audit_trail", {}).get("admission_profile_id")
            == _M3_PROFILE_ID
        )
        if not m3_profile:
            expected_risk = state["risk_claims"].get(requested)
            if certificate.get("risk_claim") != expected_risk:
                reasons.append("OFFLINE_CERTIFICATE_RISK")
            elif (expected_risk is not None
                  and expected_risk["upper_bound"] > expected_risk["budget"]):
                reasons.append("OFFLINE_CERTIFICATE_RISK_EXCEEDED")

        hypotheses, obligations, by_hypothesis, evidence = _certificate_indexes(state)
        lists = {}
        for field in ("hypothesis_ids", "obligation_ids", "evidence_ids"):
            value = certificate.get(field)
            if (not isinstance(value, list)
                    or any(not isinstance(item, str) or not item for item in value)
                    or len(value) != len(set(value))):
                reasons.append("OFFLINE_CERTIFICATE_%s" % field.upper())
                value = []
            lists[field] = value
        selected = []
        for evidence_id in lists["evidence_ids"]:
            wrapper = evidence.get(evidence_id)
            if wrapper is None:
                reasons.append("OFFLINE_CERTIFICATE_EVIDENCE_MISSING")
            else:
                selected.append(wrapper)
        if m3_profile:
            if requested != "FOUND" or not selected:
                reasons.append("OFFLINE_M3_VERDICT_SEALED")
            else:
                families = {}
                artifact_digests = set()
                for wrapper in selected:
                    atom = wrapper.get("risk_atom", {})
                    family_key = atom.get("family_key")
                    bound = atom.get("upper_bound")
                    if (not isinstance(family_key, str) or not family_key
                            or isinstance(bound, bool)
                            or not isinstance(bound, (int, float))
                            or not math.isfinite(float(bound))
                            or not 0 <= float(bound) <= 1):
                        reasons.append("OFFLINE_M3_RISK_ATOM")
                        continue
                    if family_key in families and families[family_key] != bound:
                        reasons.append("OFFLINE_M3_RISK_FAMILY_CONFLICT")
                    families[family_key] = float(bound)
                    artifact_digest = wrapper.get(
                        "calibration_artifact", {},
                    ).get("artifact_digest")
                    if not isinstance(artifact_digest, str):
                        reasons.append("OFFLINE_M3_RISK_ARTIFACT")
                    else:
                        artifact_digests.add(artifact_digest)
                scope = audit_bundle.get("scope", {})
                budget = scope.get("risk_budgets", {}).get("false_found")
                if len(artifact_digests) != 1:
                    reasons.append("OFFLINE_M3_RISK_ARTIFACT_MIX")
                else:
                    expected_calibration = (
                        "proofnav.calibration-artifact.v1:"
                        + next(iter(artifact_digests))
                    )
                    if scope.get("calibration_version") != expected_calibration:
                        reasons.append("OFFLINE_M3_RISK_CALIBRATION_VERSION")
                if (isinstance(budget, bool) or not isinstance(budget, (int, float))
                        or not math.isfinite(float(budget)) or not 0 <= budget <= 1):
                    reasons.append("OFFLINE_M3_RISK_BUDGET")
                else:
                    expected_risk = {
                        "decision": "FOUND", "risk_type": "false_found",
                        "upper_bound": min(1.0, sum(families.values())),
                        "budget": budget,
                        "calibration_version": scope.get("calibration_version"),
                        "composition_version": "%s:%s" % (
                            "proofnav.strict-familywise-union.v1",
                            canonical_sha256(sorted(families))[:16],
                        ),
                    }
                    if certificate.get("risk_claim") != expected_risk:
                        reasons.append("OFFLINE_CERTIFICATE_RISK")
                    elif expected_risk["upper_bound"] > expected_risk["budget"]:
                        reasons.append("OFFLINE_CERTIFICATE_RISK_EXCEEDED")
        if any(item not in hypotheses for item in lists["hypothesis_ids"]):
            reasons.append("OFFLINE_CERTIFICATE_HYPOTHESIS_UNKNOWN")
        if any(item not in obligations for item in lists["obligation_ids"]):
            reasons.append("OFFLINE_CERTIFICATE_OBLIGATION_UNKNOWN")

        provenance = certificate.get("provenance")
        if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_FIELDS:
            reasons.append("OFFLINE_CERTIFICATE_PROVENANCE")
        else:
            expected_events = sorted({
                item["evidence"]["source_event_id"] for item in selected
            })
            expected_adapters = sorted({
                item["evidence"]["adapter_version"] for item in selected
            })
            if provenance["builder_version"] != "proofnav.certificate-builder.v2":
                reasons.append("OFFLINE_CERTIFICATE_BUILDER")
            if provenance["admission_profile_id"] != state["audit_trail"]["admission_profile_id"]:
                reasons.append("OFFLINE_CERTIFICATE_PROFILE")
            if provenance["observation_event_ids"] != expected_events:
                reasons.append("OFFLINE_CERTIFICATE_EVENTS")
            if provenance["evidence_adapter_versions"] != expected_adapters:
                reasons.append("OFFLINE_CERTIFICATE_ADAPTERS")
            if provenance["ledger_event_count"] != state["ledger_event_count"]:
                reasons.append("OFFLINE_CERTIFICATE_LEDGER_COUNT")

        payload = certificate.get("payload")
        if requested == "FOUND":
            if not isinstance(payload, dict) or set(payload) != {
                    "hypothesis", "binding", "true_path", "unresolved_obligation_ids"}:
                reasons.append("OFFLINE_POSITIVE_PAYLOAD")
            else:
                hypothesis_record = payload["hypothesis"]
                hypothesis_id = (
                    hypothesis_record.get("hypothesis_id")
                    if isinstance(hypothesis_record, dict) else None
                )
                hypothesis = hypotheses.get(hypothesis_id)
                if hypothesis is None or hypothesis_record != hypothesis:
                    reasons.append("OFFLINE_POSITIVE_HYPOTHESIS")
                else:
                    if hypothesis["hypothesis_kind"] in _RESIDUAL_HYPOTHESIS_KINDS:
                        reasons.append("OFFLINE_POSITIVE_RESIDUAL")
                    if lists["hypothesis_ids"] != [hypothesis_id]:
                        reasons.append("OFFLINE_POSITIVE_HYPOTHESIS_COVERAGE")
                    if payload["binding"] != hypothesis["binding"]:
                        reasons.append("OFFLINE_POSITIVE_BINDING")
                    necessary = [
                        item for item in by_hypothesis[hypothesis_id]
                        if item["necessary"]
                    ]
                    expected_obligations = sorted(item["obligation_id"] for item in necessary)
                    if sorted(lists["obligation_ids"]) != expected_obligations:
                        reasons.append("OFFLINE_POSITIVE_OBLIGATION_COVERAGE")
                    path = payload["true_path"]
                    if not isinstance(path, list):
                        reasons.append("OFFLINE_POSITIVE_PATH")
                    else:
                        path_by_obligation = {}
                        used_evidence = []
                        for item in path:
                            obligation = next((
                                candidate for candidate in necessary
                                if isinstance(item, dict)
                                and candidate["obligation_id"] == item.get("obligation_id")
                            ), None)
                            if obligation is None or not _coverage_matches(item, hypothesis, obligation):
                                reasons.append("OFFLINE_POSITIVE_PATH_ITEM")
                                continue
                            if obligation["obligation_id"] in path_by_obligation:
                                reasons.append("OFFLINE_POSITIVE_PATH_DUPLICATE")
                            path_by_obligation[obligation["obligation_id"]] = item
                            if obligation["status"] != "SATISFIED":
                                reasons.append("OFFLINE_POSITIVE_UNSATISFIED")
                            if sorted(item["evidence_ids"]) != obligation["support_evidence_ids"]:
                                reasons.append("OFFLINE_POSITIVE_EVIDENCE_SET")
                            used_evidence.extend(item["evidence_ids"])
                            for evidence_id in item["evidence_ids"]:
                                wrapper = evidence.get(evidence_id)
                                if wrapper is None or not _wrapper_matches(
                                        wrapper, hypothesis, obligation, "SUPPORTS", state):
                                    reasons.append("OFFLINE_POSITIVE_BINDING")
                        if sorted(path_by_obligation) != expected_obligations:
                            reasons.append("OFFLINE_POSITIVE_PATH_INCOMPLETE")
                        if sorted(used_evidence) != sorted(lists["evidence_ids"]):
                            reasons.append("OFFLINE_POSITIVE_EVIDENCE_COVERAGE")
                    if payload["unresolved_obligation_ids"] != []:
                        reasons.append("OFFLINE_POSITIVE_UNRESOLVED")
        elif requested == "NOT_FOUND":
            if not isinstance(payload, dict) or set(payload) != {
                    "hypothesis_index", "refutation_cover",
                    "uncovered_hypothesis_ids", "frontier_unresolved"}:
                reasons.append("OFFLINE_REFUTATION_PAYLOAD")
            else:
                expected_index = [hypotheses[key] for key in sorted(hypotheses)]
                if payload["hypothesis_index"] != expected_index:
                    reasons.append("OFFLINE_REFUTATION_INDEX")
                if sorted(lists["hypothesis_ids"]) != sorted(hypotheses):
                    reasons.append("OFFLINE_REFUTATION_HYPOTHESIS_COVERAGE")
                if state["closure_witness"] is None or state["topology"]["frontier_viewpoint_ids"]:
                    reasons.append("OFFLINE_REFUTATION_SCOPE_OPEN")
                if payload["frontier_unresolved"] != [] or payload["uncovered_hypothesis_ids"] != []:
                    reasons.append("OFFLINE_REFUTATION_UNRESOLVED")
                cover = payload["refutation_cover"]
                if not isinstance(cover, list):
                    reasons.append("OFFLINE_REFUTATION_COVER")
                else:
                    selected_by_hypothesis = {key: [] for key in hypotheses}
                    used_evidence = []
                    used_obligations = []
                    for item in cover:
                        hypothesis = (
                            hypotheses.get(item.get("hypothesis_id"))
                            if isinstance(item, dict) else None
                        )
                        obligation = None
                        if hypothesis is not None:
                            obligation = next((
                                candidate for candidate in by_hypothesis[hypothesis["hypothesis_id"]]
                                if candidate["obligation_id"] == item.get("obligation_id")
                            ), None)
                        if (hypothesis is None or obligation is None
                                or not obligation["necessary"]
                                or not _coverage_matches(item, hypothesis, obligation)):
                            reasons.append("OFFLINE_REFUTATION_COVER_ITEM")
                            continue
                        selected_by_hypothesis[hypothesis["hypothesis_id"]].append(obligation)
                        if obligation["status"] != "REFUTED":
                            reasons.append("OFFLINE_REFUTATION_NOT_REFUTED")
                        if sorted(item["evidence_ids"]) != obligation["refutation_evidence_ids"]:
                            reasons.append("OFFLINE_REFUTATION_EVIDENCE_SET")
                        used_evidence.extend(item["evidence_ids"])
                        used_obligations.append(obligation["obligation_id"])
                        for evidence_id in item["evidence_ids"]:
                            wrapper = evidence.get(evidence_id)
                            if wrapper is None or not _wrapper_matches(
                                    wrapper, hypothesis, obligation, "REFUTES", state):
                                reasons.append("OFFLINE_REFUTATION_BINDING")
                    for hypothesis_id, hypothesis in hypotheses.items():
                        selected_obligations = selected_by_hypothesis[hypothesis_id]
                        if hypothesis["hypothesis_kind"] in _RESIDUAL_HYPOTHESIS_KINDS:
                            necessary = [
                                item for item in by_hypothesis[hypothesis_id]
                                if item["necessary"]
                            ]
                            if (sorted(item["obligation_id"] for item in selected_obligations)
                                    != sorted(item["obligation_id"] for item in necessary)
                                    or any(item["predicate_kind"] != "coverage" for item in selected_obligations)):
                                reasons.append("OFFLINE_REFUTATION_RESIDUAL_COVERAGE")
                        elif len(selected_obligations) != 1:
                            reasons.append("OFFLINE_REFUTATION_HYPOTHESIS_COVERAGE")
                    if sorted(used_evidence) != sorted(lists["evidence_ids"]):
                        reasons.append("OFFLINE_REFUTATION_EVIDENCE_COVERAGE")
                    if sorted(used_obligations) != sorted(lists["obligation_ids"]):
                        reasons.append("OFFLINE_REFUTATION_OBLIGATION_COVERAGE")
        reasons = sorted(set(reasons))
        return {
            "valid": not reasons,
            "reason_codes": reasons,
            "requested_verdict": requested,
            "certificate_id": claimed_id,
            "certificate_digest": claimed_digest,
            "calculated_certificate_digest": calculated,
        }
    except ContractViolation as error:
        return {
            "valid": False, "reason_codes": [error.code],
            "requested_verdict": (
                certificate.get("requested_verdict")
                if isinstance(certificate, dict) else None
            ),
        }
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return {
            "valid": False,
            "reason_codes": ["OFFLINE_CERTIFICATE_STRUCTURE_INVALID"],
            "requested_verdict": (
                certificate.get("requested_verdict")
                if isinstance(certificate, dict) else None
            ),
        }


def audit_terminal(state, terminal, certificate):
    """Check terminal/certificate/report identity without trusting verdict logic."""

    reasons = []
    try:
        terminal = _exact(copy.deepcopy(terminal), _TERMINAL_FIELDS, "$.terminal")
        if terminal["schema_version"] != SCHEMA_VERSIONS["terminal_decision"]:
            reasons.append("OFFLINE_TERMINAL_VERSION")
        online = _exact(terminal["online_verification"], _ONLINE_FIELDS, "$.terminal.online_verification")
        if online["schema_version"] != SCHEMA_VERSIONS["online_verification"]:
            reasons.append("OFFLINE_ONLINE_VERSION")
        if online["status"] not in ("ACCEPT", "REJECT", "DEFER"):
            reasons.append("OFFLINE_ONLINE_STATUS")
        if online["accepted"] is not (online["status"] == "ACCEPT"):
            reasons.append("OFFLINE_ONLINE_ACCEPTED")
        for key in (
                "reason_codes", "missing_obligation_ids", "uncovered_hypothesis_ids",
                "frontier_viewpoint_ids"):
            value = online[key]
            if (not isinstance(value, list)
                    or any(not isinstance(item, str) or not item for item in value)
                    or len(value) != len(set(value))):
                reasons.append("OFFLINE_ONLINE_LIST")
        feedback = _exact(online["structured_feedback"], _FEEDBACK_FIELDS, "$.terminal.online_verification.structured_feedback")
        if terminal["feedback"] != feedback:
            reasons.append("OFFLINE_TERMINAL_FEEDBACK")
        expected_recommendation = "FINALIZE" if online["status"] == "ACCEPT" else "CONTINUE_EVIDENCE_COLLECTION"
        if feedback["recommended_action"] != expected_recommendation:
            reasons.append("OFFLINE_ONLINE_FEEDBACK")
        for key in (
                "reason_codes", "missing_obligation_ids", "uncovered_hypothesis_ids",
                "frontier_viewpoint_ids"):
            if feedback[key] != online[key]:
                reasons.append("OFFLINE_ONLINE_FEEDBACK")

        if not isinstance(terminal["duet_signal"], dict) or set(terminal["duet_signal"]) != _EXECUTION_FIELDS:
            reasons.append("OFFLINE_TERMINAL_EXECUTION")
        elif any(not isinstance(value, bool) for value in terminal["duet_signal"].values()):
            reasons.append("OFFLINE_TERMINAL_EXECUTION")
        for key in ("terminal", "certificate_accepted"):
            if not isinstance(terminal[key], bool):
                reasons.append("OFFLINE_TERMINAL_BOOLEAN")
        if terminal["proposed_verdict"] not in (None, "FOUND", "NOT_FOUND"):
            reasons.append("OFFLINE_TERMINAL_VERDICT")

        claimed_id, claimed_digest, calculated = certificate_identity(certificate)
        if terminal["proposed_certificate_id"] != claimed_id:
            reasons.append("OFFLINE_TERMINAL_PROPOSED_ID")
        if terminal["proposed_certificate_digest"] != claimed_digest:
            reasons.append("OFFLINE_TERMINAL_PROPOSED_DIGEST")
        if certificate is None:
            if online["certificate_id"] is not None or online["certificate_digest"] is not None:
                reasons.append("OFFLINE_ONLINE_CERTIFICATE_IDENTITY")
        else:
            if online["certificate_id"] != claimed_id or online["certificate_digest"] != claimed_digest:
                reasons.append("OFFLINE_ONLINE_CERTIFICATE_IDENTITY")
            if online["calculated_certificate_digest"] != calculated:
                reasons.append("OFFLINE_ONLINE_CERTIFICATE_CALCULATION")
            if terminal["proposed_verdict"] != certificate.get("requested_verdict"):
                reasons.append("OFFLINE_TERMINAL_PROPOSAL_VERDICT")

        preflight_firewall = (
            online["status"] == "REJECT"
            and "CONTROLLED_SOURCE_FORBIDDEN" in online["reason_codes"]
            and not online["accepted"]
            and online["proof_state_digest"] is None
        )
        if not preflight_firewall:
            expected_state = {
                "scope_digest": state["scope_digest"],
                "template_digest": state["template_digest"],
                "universe_digest": state["universe_digest"],
                "binding_digest": state["binding_digest"],
                "decision_cut": state["decision_cut"],
                "transition_tip": state["transition_tip"],
                "proof_state_digest": state["proof_state_digest"],
            }
            for key, expected in expected_state.items():
                if online[key] != expected:
                    reasons.append("OFFLINE_ONLINE_STATE_IDENTITY")
            if terminal["decision_cut"] != state["decision_cut"]:
                reasons.append("OFFLINE_TERMINAL_CUT")
            if terminal["transition_tip"] != state["transition_tip"]:
                reasons.append("OFFLINE_TERMINAL_TIP")
            if terminal["proof_state_digest"] != state["proof_state_digest"]:
                reasons.append("OFFLINE_TERMINAL_STATE")
            if online["frontier_viewpoint_ids"] != state["topology"]["frontier_viewpoint_ids"]:
                reasons.append("OFFLINE_ONLINE_FRONTIER")

        if terminal["certificate_accepted"] != online["accepted"]:
            reasons.append("OFFLINE_TERMINAL_ACCEPTANCE")
        if online["accepted"]:
            if not (
                    terminal["terminal"] is True
                    and terminal["directive"] == "ACCEPT_" + str(online["requested_verdict"])
                    and terminal["semantic_verdict"] == online["requested_verdict"]
                    and terminal["cause"] == "verifier_accept"
                    and terminal["proposed_verdict"] == online["requested_verdict"]
                    and terminal["accepted_certificate_id"] == claimed_id
                    and terminal["accepted_certificate_digest"] == claimed_digest
                    and claimed_digest == calculated):
                reasons.append("OFFLINE_TERMINAL_ACCEPT_IDENTITY")
        else:
            if terminal["accepted_certificate_id"] is not None or terminal["accepted_certificate_digest"] is not None:
                reasons.append("OFFLINE_TERMINAL_REJECT_IDENTITY")
            if terminal["directive"] == "CONTINUE_SEARCH":
                if terminal["terminal"] is not False or terminal["semantic_verdict"] is not None:
                    reasons.append("OFFLINE_TERMINAL_CONTINUE")
            elif terminal["directive"] == "FINALIZE_UNRESOLVED":
                if terminal["terminal"] is not True or terminal["semantic_verdict"] != "UNRESOLVED":
                    reasons.append("OFFLINE_TERMINAL_UNRESOLVED")
            else:
                reasons.append("OFFLINE_TERMINAL_DIRECTIVE")
        reasons = sorted(set(reasons))
        return {
            "valid": not reasons,
            "reason_codes": reasons,
            "online_status": online["status"],
            "online_accepted": online["accepted"],
            "preflight_firewall": preflight_firewall,
        }
    except ContractViolation as error:
        return {
            "valid": False, "reason_codes": [error.code],
            "online_status": None, "online_accepted": False,
            "preflight_firewall": False,
        }
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return {
            "valid": False,
            "reason_codes": ["OFFLINE_TERMINAL_STRUCTURE_INVALID"],
            "online_status": None, "online_accepted": False,
            "preflight_firewall": False,
        }
