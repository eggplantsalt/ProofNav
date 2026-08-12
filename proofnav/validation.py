"""Strict, dependency-free validators for the ProofNav M1 JSON contracts.

The validators operate on plain dictionaries so serialized artifacts can be
audited without importing DUET, MatterSim, PyTorch, or evaluator objects.
"""

import math

from .contracts import (
    ACTION_BRANCHES,
    ContractViolation,
    DECISION_STATUSES,
    EVIDENCE_CLAIMS,
    EVIDENCE_ROLES,
    EVIDENCE_SOURCES,
    FORBIDDEN_AGENT_KEYS,
    FORBIDDEN_RUNTIME_EVENT_TYPES,
    OBLIGATION_STATUSES,
    SCHEMA_VERSIONS,
    SEMANTIC_DECISIONS,
    TERMINATION_CAUSES,
    semantic_verdict,
)


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _mapping(value, location):
    if not isinstance(value, dict):
        _fail("TYPE_MAPPING", location, "expected an object")
    return value


def _list(value, location, nonempty=False):
    if not isinstance(value, list):
        _fail("TYPE_LIST", location, "expected an array")
    if nonempty and not value:
        _fail("EMPTY_LIST", location, "must not be empty")
    return value


def _string(value, location, nullable=False):
    if nullable and value is None:
        return value
    if not isinstance(value, str) or not value:
        _fail("TYPE_STRING", location, "expected a non-empty string")
    return value


def _integer(value, location, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("TYPE_INTEGER", location, "expected an integer")
    if minimum is not None and value < minimum:
        _fail("INTEGER_RANGE", location, "must be >= %s" % minimum)
    return value


def _number(value, location, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("TYPE_NUMBER", location, "expected a finite number")
    value = float(value)
    if not math.isfinite(value):
        _fail("NUMBER_FINITE", location, "expected a finite number")
    if minimum is not None and value < minimum:
        _fail("NUMBER_RANGE", location, "must be >= %s" % minimum)
    if maximum is not None and value > maximum:
        _fail("NUMBER_RANGE", location, "must be <= %s" % maximum)
    return value


def _bool(value, location):
    if not isinstance(value, bool):
        _fail("TYPE_BOOLEAN", location, "expected a boolean")
    return value


def _required(value, keys, location="$"):
    value = _mapping(value, location)
    missing = sorted(set(keys) - set(value))
    if missing:
        _fail("MISSING_FIELDS", location, "missing %s" % missing)
    return value


def _only(value, keys, location="$", code="UNKNOWN_FIELDS"):
    unknown = sorted(set(value) - set(keys))
    if unknown:
        _fail(code, location, "unknown fields %s" % unknown)
    return value


def _version(value, contract, location="$"):
    expected = SCHEMA_VERSIONS[contract]
    if value.get("schema_version") != expected:
        _fail(
            "SCHEMA_VERSION", location + ".schema_version",
            "expected %s" % expected,
        )


def scan_forbidden_agent_fields(value, location="$", inherited_key=None):
    """Return all evaluator-only key paths reachable from an online object."""

    failures = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            child_location = "%s.%s" % (location, key)
            if lowered in FORBIDDEN_AGENT_KEYS or lowered.startswith("gt_"):
                failures.append(child_location)
            failures.extend(
                scan_forbidden_agent_fields(child, child_location, lowered)
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(scan_forbidden_agent_fields(
                child, "%s[%d]" % (location, index), inherited_key,
            ))
    return failures


def assert_agent_visible(value, location="$"):
    failures = scan_forbidden_agent_fields(value, location)
    if failures:
        _fail(
            "AGENT_VISIBLE_GT",
            failures[0],
            "evaluator-only field is forbidden from the online contract",
        )


def _shape_dtype(value, location):
    value = _only(
        _required(value, ("shape", "dtype"), location),
        ("shape", "dtype"), location,
    )
    for index, dim in enumerate(_list(value["shape"], location + ".shape")):
        _integer(dim, "%s.shape[%d]" % (location, index), minimum=0)
    _string(value["dtype"], location + ".dtype")


def validate_observation(value):
    fields = (
        "schema_version", "event_id", "episode_id", "event_seq", "step",
        "source", "scan", "viewpoint", "view_index", "pose",
        "field_schema", "instruction", "instruction_encoding_length",
        "candidates", "object_proposal_ids", "audit_trail",
    )
    value = _required(value, fields)
    _version(value, "observation")
    assert_agent_visible(value)
    _only(value, fields)
    for key in ("event_id", "episode_id", "scan", "viewpoint", "instruction"):
        _string(value[key], "$.%s" % key)
    _integer(value["event_seq"], "$.event_seq", minimum=0)
    _integer(value["step"], "$.step", minimum=0)
    _integer(value["view_index"], "$.view_index", minimum=0)
    if value["source"] != "observation":
        _fail("OBSERVATION_SOURCE", "$.source", "must be observation")
    pose_fields = ("heading", "elevation", "position")
    pose = _only(_required(value["pose"], pose_fields, "$.pose"), pose_fields, "$.pose")
    _number(pose["heading"], "$.pose.heading")
    _number(pose["elevation"], "$.pose.elevation")
    position = _list(pose["position"], "$.pose.position")
    if len(position) != 3:
        _fail("POSITION_LENGTH", "$.pose.position", "expected xyz")
    for index, coordinate in enumerate(position):
        _number(coordinate, "$.pose.position[%d]" % index)
    schemas = _mapping(value["field_schema"], "$.field_schema")
    _only(
        schemas, ("feature", "obj_img_fts", "obj_ang_fts", "obj_box_fts"),
        "$.field_schema",
    )
    for name in ("feature", "obj_img_fts", "obj_ang_fts", "obj_box_fts"):
        if name not in schemas:
            _fail("MISSING_FIELDS", "$.field_schema", "missing %s" % name)
        _shape_dtype(schemas[name], "$.field_schema.%s" % name)
    _integer(
        value["instruction_encoding_length"],
        "$.instruction_encoding_length", minimum=0,
    )
    for index, candidate in enumerate(_list(value["candidates"], "$.candidates")):
        location = "$.candidates[%d]" % index
        candidate_fields = (
            "viewpoint_id", "point_id", "heading", "elevation", "position",
            "simulator_index", "feature_schema", "evidence_role",
        )
        candidate = _only(
            _required(candidate, candidate_fields, location), candidate_fields, location,
        )
        _string(candidate["viewpoint_id"], location + ".viewpoint_id")
        _integer(candidate["point_id"], location + ".point_id", minimum=0)
        _integer(candidate["simulator_index"], location + ".simulator_index", minimum=1)
        _number(candidate["heading"], location + ".heading")
        _number(candidate["elevation"], location + ".elevation")
        candidate_position = _list(candidate["position"], location + ".position")
        if len(candidate_position) != 3:
            _fail("POSITION_LENGTH", location + ".position", "expected xyz")
        for coordinate_index, coordinate in enumerate(candidate_position):
            _number(coordinate, "%s.position[%d]" % (location, coordinate_index))
        if candidate["evidence_role"] != "unobserved_navigation_proposal":
            _fail(
                "CANDIDATE_EVIDENCE_ROLE", location + ".evidence_role",
                "candidate must remain an unobserved proposal",
            )
        _shape_dtype(candidate["feature_schema"], location + ".feature_schema")
    for index, object_id in enumerate(_list(
            value["object_proposal_ids"], "$.object_proposal_ids")):
        _string(object_id, "$.object_proposal_ids[%d]" % index)
    audit_fields = ("producer", "source_schema")
    audit = _only(
        _required(value["audit_trail"], audit_fields, "$.audit_trail"),
        audit_fields, "$.audit_trail",
    )
    for key in audit_fields:
        _string(audit[key], "$.audit_trail.%s" % key)
    return value


def validate_action(value):
    fields = (
        "schema_version", "episode_id", "step", "branches",
        "selected_branch", "selected_index", "selected_action_id",
        "selected_action_kind", "proposal_score_semantics", "audit_trail",
    )
    value = _required(value, fields)
    _version(value, "action")
    assert_agent_visible(value)
    _only(value, fields)
    _string(value["episode_id"], "$.episode_id")
    _integer(value["step"], "$.step", minimum=0)
    selected_branch = value["selected_branch"]
    if selected_branch not in ACTION_BRANCHES:
        _fail("ACTION_BRANCH", "$.selected_branch", "invalid branch")
    branches = _mapping(value["branches"], "$.branches")
    _only(branches, ACTION_BRANCHES, "$.branches")
    if set(branches) != ACTION_BRANCHES:
        _fail("ACTION_BRANCH_SET", "$.branches", "local/global/fused branches are required")
    if selected_branch not in branches:
        _fail("ACTION_BRANCH_MISSING", "$.branches", "selected branch is absent")
    for branch, record in branches.items():
        if branch not in ACTION_BRANCHES:
            _fail("ACTION_BRANCH", "$.branches.%s" % branch, "invalid branch")
        record = _only(
            _required(record, ("action_ids", "valid_mask"), "$.branches.%s" % branch),
            ("action_ids", "valid_mask"), "$.branches.%s" % branch,
        )
        action_ids = _list(record["action_ids"], "$.branches.%s.action_ids" % branch, nonempty=True)
        valid_mask = _list(record["valid_mask"], "$.branches.%s.valid_mask" % branch, nonempty=True)
        if len(action_ids) != len(valid_mask):
            _fail("ACTION_LENGTH", "$.branches.%s" % branch, "ID/mask lengths differ")
        if action_ids[0] is not None:
            _fail("ACTION_STOP_ID", "$.branches.%s.action_ids[0]" % branch, "STOP must map to null")
        for index, valid in enumerate(valid_mask):
            _bool(valid, "$.branches.%s.valid_mask[%d]" % (branch, index))
        for index, action_id in enumerate(action_ids[1:], 1):
            _string(action_id, "$.branches.%s.action_ids[%d]" % (branch, index))
    selected_index = _integer(value["selected_index"], "$.selected_index", minimum=0)
    selected = branches[selected_branch]
    if selected_index >= len(selected["action_ids"]):
        _fail("ACTION_INDEX", "$.selected_index", "out of selected-branch range")
    if not selected["valid_mask"][selected_index]:
        _fail("ACTION_MASK", "$.selected_index", "selected action is masked")
    if value["selected_action_id"] != selected["action_ids"][selected_index]:
        _fail("ACTION_ID_MAPPING", "$.selected_action_id", "does not match selected branch/index")
    expected_kind = "STOP" if value["selected_action_id"] is None else "VIEWPOINT"
    if value["selected_action_kind"] != expected_kind:
        _fail("ACTION_KIND", "$.selected_action_kind", "expected %s" % expected_kind)
    if value["proposal_score_semantics"] != "uncalibrated_duet_task_score":
        _fail(
            "ACTION_SCORE_SEMANTICS", "$.proposal_score_semantics",
            "DUET scores must not be labeled calibrated evidence",
        )
    audit_fields = (
        "producer", "source_trace_schema", "model_event_seq", "action_event_seq",
    )
    audit = _only(
        _required(value["audit_trail"], audit_fields, "$.audit_trail"),
        audit_fields, "$.audit_trail",
    )
    _string(audit["producer"], "$.audit_trail.producer")
    _string(audit["source_trace_schema"], "$.audit_trail.source_trace_schema")
    _integer(audit["model_event_seq"], "$.audit_trail.model_event_seq", minimum=0)
    _integer(audit["action_event_seq"], "$.audit_trail.action_event_seq", minimum=0)
    return value


def validate_evidence(value, observations_by_id=None):
    fields = (
        "schema_version", "evidence_id", "episode_id", "source",
        "source_event_id", "event_seq", "step", "scan", "viewpoint",
        "view_index", "evidence_role", "unit_id", "scope_contract_id",
        "obligation_id", "predicate_id", "claim", "adapter_version",
        "dependency_group", "audit_trail",
    )
    value = _required(value, fields)
    _version(value, "evidence")
    assert_agent_visible(value)
    _only(value, fields)
    for key in (
        "evidence_id", "episode_id", "source_event_id", "scan", "viewpoint",
        "unit_id", "scope_contract_id", "obligation_id", "predicate_id",
        "adapter_version", "dependency_group",
    ):
        _string(value[key], "$.%s" % key)
    if value["source"] not in EVIDENCE_SOURCES:
        _fail(
            "EVIDENCE_SOURCE", "$.source",
            "only a real observation event can originate evidence",
        )
    if value["evidence_role"] not in EVIDENCE_ROLES:
        _fail("EVIDENCE_ROLE", "$.evidence_role", "invalid discrete evidence unit")
    if value["claim"] not in EVIDENCE_CLAIMS:
        _fail("EVIDENCE_CLAIM", "$.claim", "invalid evidence claim")
    _integer(value["event_seq"], "$.event_seq", minimum=0)
    _integer(value["step"], "$.step", minimum=0)
    _integer(value["view_index"], "$.view_index", minimum=0)
    audit_fields = ("producer", "source_field")
    audit = _only(
        _required(value["audit_trail"], audit_fields, "$.audit_trail"),
        audit_fields, "$.audit_trail",
    )
    for key in audit_fields:
        _string(audit[key], "$.audit_trail.%s" % key)
    if observations_by_id is not None:
        observation = observations_by_id.get(value["source_event_id"])
        if observation is None:
            _fail(
                "EVIDENCE_EVENT_MISSING", "$.source_event_id",
                "does not identify an observed event",
            )
        validate_observation(observation)
        comparisons = {
            "episode_id": "episode_id",
            "event_seq": "event_seq",
            "step": "step",
            "scan": "scan",
            "viewpoint": "viewpoint",
            "view_index": "view_index",
        }
        for evidence_key, observation_key in comparisons.items():
            if value[evidence_key] != observation[observation_key]:
                _fail(
                    "EVIDENCE_PROVENANCE", "$.%s" % evidence_key,
                    "does not match source observation",
                )
    return value


def validate_scope(value):
    fields = (
        "schema_version", "scope_contract_id", "episode_id", "scan_id",
        "start_viewpoint", "domain", "hypothesis_ids",
        "observation_interface_version", "predicate_schema_version",
        "calibration_version", "risk_budgets", "resource_limits",
        "provenance", "audit_trail",
    )
    value = _required(value, fields)
    _version(value, "scope")
    assert_agent_visible(value)
    _only(value, fields)
    for key in (
        "scope_contract_id", "episode_id", "scan_id", "start_viewpoint",
        "observation_interface_version", "predicate_schema_version",
        "calibration_version",
    ):
        _string(value[key], "$.%s" % key)
    domain_fields = (
        "kind", "rule", "interface_audit_ref", "disclosure",
    )
    domain = _only(
        _required(value["domain"], domain_fields, "$.domain"),
        domain_fields, "$.domain",
    )
    if domain["kind"] != "candidate_reachable_component":
        _fail("SCOPE_DOMAIN", "$.domain.kind", "unsupported M1 scope kind")
    if domain["disclosure"] != "intensional_rule_only":
        _fail(
            "SCOPE_DISCLOSURE", "$.domain.disclosure",
            "the online contract must not expose a full connectivity table",
        )
    for key in ("rule", "interface_audit_ref"):
        _string(domain[key], "$.domain.%s" % key)
    hypotheses = _list(value["hypothesis_ids"], "$.hypothesis_ids", nonempty=True)
    if len(hypotheses) != len(set(hypotheses)):
        _fail("SCOPE_HYPOTHESIS_DUPLICATE", "$.hypothesis_ids", "IDs must be unique")
    for index, hypothesis in enumerate(hypotheses):
        _string(hypothesis, "$.hypothesis_ids[%d]" % index)
    budget_fields = ("false_found", "false_not_found")
    budgets = _only(
        _required(value["risk_budgets"], budget_fields, "$.risk_budgets"),
        budget_fields, "$.risk_budgets",
    )
    for key in ("false_found", "false_not_found"):
        _number(budgets[key], "$.risk_budgets.%s" % key, minimum=0, maximum=1)
    limit_fields = (
        "max_steps", "max_observation_events", "max_predicate_queries",
    )
    limits = _only(
        _required(value["resource_limits"], limit_fields, "$.resource_limits"),
        limit_fields, "$.resource_limits",
    )
    for key in limits:
        _integer(limits[key], "$.resource_limits.%s" % key, minimum=0)
    provenance_fields = ("source", "version", "record_id")
    provenance = _only(
        _required(value["provenance"], provenance_fields, "$.provenance"),
        provenance_fields, "$.provenance",
    )
    for key in provenance_fields:
        _string(provenance[key], "$.provenance.%s" % key)
    audit_fields = ("created_by", "change_log")
    audit = _only(
        _required(value["audit_trail"], audit_fields, "$.audit_trail"),
        audit_fields, "$.audit_trail",
    )
    _string(audit["created_by"], "$.audit_trail.created_by")
    _list(audit["change_log"], "$.audit_trail.change_log", nonempty=True)
    return value


def validate_obligation(value):
    fields = (
        "schema_version", "obligation_id", "episode_id", "scope_contract_id",
        "hypothesis_id", "predicate_id", "necessary", "status",
        "evidence_ids", "audit_trail",
    )
    value = _required(value, fields)
    _version(value, "obligation")
    assert_agent_visible(value)
    _only(value, fields)
    for key in (
        "obligation_id", "episode_id", "scope_contract_id", "hypothesis_id",
        "predicate_id",
    ):
        _string(value[key], "$.%s" % key)
    _bool(value["necessary"], "$.necessary")
    if value["status"] not in OBLIGATION_STATUSES:
        _fail("OBLIGATION_STATUS", "$.status", "invalid state")
    evidence_ids = _list(value["evidence_ids"], "$.evidence_ids")
    for index, evidence_id in enumerate(evidence_ids):
        _string(evidence_id, "$.evidence_ids[%d]" % index)
    if value["status"] == "OPEN" and evidence_ids:
        _fail("OPEN_WITH_EVIDENCE", "$.evidence_ids", "OPEN must not claim closing evidence")
    if value["status"] != "OPEN" and not evidence_ids:
        _fail("CLOSED_WITHOUT_EVIDENCE", "$.evidence_ids", "closed obligation needs evidence")
    audit = _only(
        _required(value["audit_trail"], ("producer",), "$.audit_trail"),
        ("producer",), "$.audit_trail",
    )
    _string(audit["producer"], "$.audit_trail.producer")
    return value


def _validate_trajectory(value):
    trajectory = _list(value, "$.trajectory", nonempty=True)
    for segment_index, segment in enumerate(trajectory):
        segment = _list(segment, "$.trajectory[%d]" % segment_index, nonempty=True)
        for node_index, viewpoint in enumerate(segment):
            _string(
                viewpoint,
                "$.trajectory[%d][%d]" % (segment_index, node_index),
            )


def _validate_risk_claim(value, decision):
    fields = (
        "decision", "risk_type", "upper_bound", "budget",
        "calibration_version", "composition_version",
    )
    value = _only(
        _required(value, fields, "$.risk_claim"), fields, "$.risk_claim",
    )
    if value["decision"] != decision:
        _fail("RISK_DECISION", "$.risk_claim.decision", "must match semantic decision")
    expected = "false_found" if decision == "FOUND" else "false_not_found"
    if value["risk_type"] != expected:
        _fail("RISK_TYPE", "$.risk_claim.risk_type", "expected %s" % expected)
    upper = _number(value["upper_bound"], "$.risk_claim.upper_bound", minimum=0, maximum=1)
    budget = _number(value["budget"], "$.risk_claim.budget", minimum=0, maximum=1)
    if upper > budget:
        _fail("RISK_BUDGET", "$.risk_claim.upper_bound", "exceeds claimed budget")
    _string(value["calibration_version"], "$.risk_claim.calibration_version")
    _string(value["composition_version"], "$.risk_claim.composition_version")


def _validate_cost_ledger(value):
    fields = (
        "travel_distance_meters", "high_level_actions", "expanded_path_edges",
        "observation_events", "predicate_queries", "online_compute_milliseconds",
        "storage_bytes", "offline_preprocessing_ref",
    )
    value = _only(
        _required(value, fields, "$.cost_ledger"), fields, "$.cost_ledger",
    )
    _number(value["travel_distance_meters"], "$.cost_ledger.travel_distance_meters", minimum=0)
    _number(value["online_compute_milliseconds"], "$.cost_ledger.online_compute_milliseconds", minimum=0)
    for key in (
        "high_level_actions", "expanded_path_edges", "observation_events",
        "predicate_queries", "storage_bytes",
    ):
        _integer(value[key], "$.cost_ledger.%s" % key, minimum=0)
    _string(value["offline_preprocessing_ref"], "$.cost_ledger.offline_preprocessing_ref")


def validate_result(value):
    fields = (
        "schema_version", "instr_id", "trajectory", "pred_objid",
        "semantic_decision", "decision_status", "termination",
        "certificate", "online_verifier", "scope_contract_id", "risk_claim",
        "budget_status", "cost_ledger", "audit_trail",
    )
    value = _required(value, fields)
    _version(value, "result")
    assert_agent_visible(value)
    _only(value, fields)
    _string(value["instr_id"], "$.instr_id")
    _string(value["pred_objid"], "$.pred_objid", nullable=True)
    _string(value["scope_contract_id"], "$.scope_contract_id")
    _validate_trajectory(value["trajectory"])
    if value["decision_status"] not in DECISION_STATUSES:
        _fail("DECISION_STATUS", "$.decision_status", "invalid status")
    decision = value["semantic_decision"]
    if decision is not None and decision not in SEMANTIC_DECISIONS:
        _fail("SEMANTIC_DECISION", "$.semantic_decision", "invalid decision")
    verdict = semantic_verdict(value)
    termination_fields = (
        "cause", "execution_stopped", "duet_flags",
    )
    termination = _only(
        _required(value["termination"], termination_fields, "$.termination"),
        termination_fields, "$.termination",
    )
    if termination["cause"] not in TERMINATION_CAUSES:
        _fail("TERMINATION_CAUSE", "$.termination.cause", "invalid cause")
    _bool(termination["execution_stopped"], "$.termination.execution_stopped")
    duet_flag_fields = (
        "duet_stop", "no_frontier", "max_step",
    )
    duet_flags = _only(
        _required(termination["duet_flags"], duet_flag_fields, "$.termination.duet_flags"),
        duet_flag_fields, "$.termination.duet_flags",
    )
    for key in duet_flags:
        _bool(duet_flags[key], "$.termination.duet_flags.%s" % key)
    verifier_fields = (
        "accepted", "reason_codes", "remaining_obligation_ids",
    )
    verifier = _only(
        _required(value["online_verifier"], verifier_fields, "$.online_verifier"),
        verifier_fields, "$.online_verifier",
    )
    _bool(verifier["accepted"], "$.online_verifier.accepted")
    _list(verifier["reason_codes"], "$.online_verifier.reason_codes")
    _list(verifier["remaining_obligation_ids"], "$.online_verifier.remaining_obligation_ids")
    budget_fields = (
        "within_budget", "exhausted_resources",
    )
    budget = _only(
        _required(value["budget_status"], budget_fields, "$.budget_status"),
        budget_fields, "$.budget_status",
    )
    _bool(budget["within_budget"], "$.budget_status.within_budget")
    _list(budget["exhausted_resources"], "$.budget_status.exhausted_resources")
    _validate_cost_ledger(value["cost_ledger"])
    audit_fields = (
        "producer", "source_versions", "event_ids",
    )
    audit = _only(
        _required(value["audit_trail"], audit_fields, "$.audit_trail"),
        audit_fields, "$.audit_trail",
    )
    _string(audit["producer"], "$.audit_trail.producer")
    source_versions = _only(
        _mapping(audit["source_versions"], "$.audit_trail.source_versions"),
        ("duet", "m0_trace", "proofnav_contracts"),
        "$.audit_trail.source_versions",
    )
    if set(source_versions) != {"duet", "m0_trace", "proofnav_contracts"}:
        _fail(
            "RESULT_SOURCE_VERSIONS", "$.audit_trail.source_versions",
            "duet/m0_trace/proofnav_contracts are required",
        )
    for key, version in source_versions.items():
        _string(version, "$.audit_trail.source_versions.%s" % key)
    _list(audit["event_ids"], "$.audit_trail.event_ids")

    if verdict in SEMANTIC_DECISIONS:
        if termination["cause"] != "verifier_accept":
            _fail(
                "SEMANTIC_TERMINATION", "$.termination.cause",
                "verified decisions require verifier_accept",
            )
        if not verifier["accepted"]:
            _fail("VERIFIER_GATE", "$.online_verifier.accepted", "verified decision was not accepted")
        if value["certificate"] is None:
            _fail("CERTIFICATE_REQUIRED", "$.certificate", "verified decision needs a certificate")
        if value["risk_claim"] is None:
            _fail("RISK_REQUIRED", "$.risk_claim", "verified decision needs a risk claim")
        if not budget["within_budget"]:
            _fail("BUDGET_REQUIRED", "$.budget_status.within_budget", "verified decision is over budget")
        _validate_risk_claim(value["risk_claim"], verdict)
    else:
        if termination["cause"] == "verifier_accept":
            _fail("UNRESOLVED_ACCEPT", "$.termination.cause", "UNRESOLVED cannot be verifier-accepted")
        if verifier["accepted"]:
            _fail("UNRESOLVED_ACCEPT", "$.online_verifier.accepted", "UNRESOLVED cannot be accepted")
        if value["certificate"] is not None:
            _fail("UNRESOLVED_CERTIFICATE", "$.certificate", "must be null")
        if value["risk_claim"] is not None:
            _fail("UNRESOLVED_RISK", "$.risk_claim", "must be null")
    return value


def validate_runtime_trace(events):
    """Validate the M0/M1 truth boundary without importing M0 audit tooling."""

    events = _list(events, "$", nonempty=True)
    previous_by_episode = {}
    models = {}
    observations = {}
    common_fields = {
        "trace_schema_version", "run_id", "episode_index", "instr_id",
        "step", "event_seq", "event_type", "monotonic_time_ns",
        "causal_parent_seq",
    }
    payload_fields = {
        "observation": {
            "observation_index", "scan", "viewpoint", "view_index", "pose",
            "field_schema", "instruction_length_chars", "candidate_ids",
            "candidate_schema", "object_proposal_ids",
        },
        "model_scores": {
            "score_semantics", "fusion_mode", "local", "global", "fused",
            "objects", "graph_map",
        },
        "action": {
            "selected_branch", "selected_index", "selected_high_level_action",
        },
        "termination": {
            "flags", "trigger_priority", "selected_trigger",
            "environment_action_is_none",
        },
        "execution": {
            "source_viewpoint", "destination_viewpoint", "expanded_path",
            "expanded_path_includes_source", "travel_only_nodes",
            "observation_endpoint", "next_observation_index",
        },
        "prediction": {"trajectory", "pred_objid"},
    }
    for index, event in enumerate(events):
        location = "$[%d]" % index
        event = _mapping(event, location)
        event_type = event.get("event_type")
        if event_type in FORBIDDEN_RUNTIME_EVENT_TYPES:
            _fail("RUNTIME_EVALUATOR_EVENT", location + ".event_type", "offline event in runtime trace")
        if event_type not in payload_fields:
            _fail("RUNTIME_EVENT_TYPE", location + ".event_type", "invalid runtime event")
        assert_agent_visible(event, location)
        _only(
            event, common_fields | payload_fields[event_type], location,
            code="RUNTIME_UNKNOWN_FIELD",
        )
        episode = event.get("episode_index", event.get("episode_id"))
        seq = event.get("event_seq")
        if episode is None or not isinstance(seq, int):
            _fail("RUNTIME_EVENT_HEADER", location, "missing episode/event_seq")
        previous = previous_by_episode.get(episode)
        if previous is None:
            if seq != 0:
                _fail("RUNTIME_SEQUENCE", location + ".event_seq", "first event must be zero")
        else:
            if seq != previous["event_seq"] + 1:
                _fail("RUNTIME_SEQUENCE", location + ".event_seq", "sequence is not contiguous")
            if event.get("causal_parent_seq") != previous["event_seq"]:
                _fail("RUNTIME_CAUSALITY", location + ".causal_parent_seq", "broken parent")
        previous_by_episode[episode] = event
        key = (episode, event.get("step"))
        if event_type == "model_scores":
            models[key] = event
        elif event_type == "action":
            model = models.get(key)
            if model is None:
                _fail("RUNTIME_ACTION_ORDER", location, "action has no prior model_scores")
            branch = event.get("selected_branch")
            if branch not in ("local", "global", "fused"):
                _fail("RUNTIME_ACTION_BRANCH", location + ".selected_branch", "invalid branch")
            ids = model[branch]["action_ids"]
            masks = model[branch]["valid_mask"]
            selected_index = event["selected_index"]
            if selected_index >= len(ids) or selected_index >= len(masks):
                _fail("RUNTIME_ACTION_INDEX", location + ".selected_index", "out of range")
            if not masks[selected_index]:
                _fail("RUNTIME_ACTION_MASK", location + ".selected_index", "masked action")
            if ids[selected_index] != event["selected_high_level_action"]:
                _fail("RUNTIME_ACTION_MAPPING", location, "index-to-ID mismatch")
        elif event_type == "observation":
            observations[(episode, event.get("observation_index"))] = event
            for candidate_index, candidate in enumerate(event.get("candidate_schema", [])):
                if candidate.get("evidence_role") != "unobserved_navigation_proposal":
                    _fail(
                        "RUNTIME_PROPOSAL_EVIDENCE",
                        "%s.candidate_schema[%d]" % (location, candidate_index),
                        "candidate is not an observed endpoint",
                    )
        elif event_type == "execution":
            path = event.get("expanded_path", [])
            if not path or event.get("travel_only_nodes") != path[:-1]:
                _fail("RUNTIME_TRAVEL_ONLY", location, "invalid expanded path partition")
            if event.get("observation_endpoint") != path[-1]:
                _fail("RUNTIME_ENDPOINT", location, "endpoint mismatch")
    for index, event in enumerate(events):
        if event.get("event_type") == "execution":
            episode = event.get("episode_index", event.get("episode_id"))
            observation = observations.get((episode, event.get("next_observation_index")))
            if observation is None:
                _fail("RUNTIME_ENDPOINT_OBSERVATION", "$[%d]" % index, "missing endpoint observation")
            if observation.get("viewpoint") != event.get("observation_endpoint"):
                _fail("RUNTIME_ENDPOINT_OBSERVATION", "$[%d]" % index, "wrong endpoint observation")
    return events
