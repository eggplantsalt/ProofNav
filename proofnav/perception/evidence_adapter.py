"""Exact M3 DUET-signal validation and entity SUPPORT/ABSTAIN adapter."""

import copy
import math

from proofnav.calibration.artifact import (
    validate_model_identity,
    validate_registered_calibration_artifact,
)
from proofnav.calibration.registry import require_registered_signal_digest
from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.runtime.semantics import object_unit_id, validate_binding
from proofnav.validation import assert_agent_visible, validate_evidence, validate_observation

from .duet_signal import (
    DUET_SIGNAL_PRODUCER,
    DUET_SIGNAL_SCHEMA_VERSION,
    DUET_SIGNAL_SOURCE_SCHEMA,
)


_SIGNAL_FIELDS = frozenset((
    "schema_version", "producer", "source_schema", "signal_semantics",
    "evidence_authority", "observation", "observation_digest",
    "object_scores", "content_digests", "instruction_digest",
    "template_digest", "model_identity", "signal_digest",
))
_SCORE_FIELDS = frozenset((
    "proposal_ids", "valid_mask", "logits", "selected_index",
    "selected_proposal_id", "selected_statistic",
))
_CONTENT_NAMES = frozenset((
    "panorama_features", "object_features", "object_angle_features",
    "object_box_features", "instruction_encoding",
))
_CONTENT_FIELDS = frozenset(("digest", "dtype", "shape"))
_QUERY_FIELDS = frozenset((
    "query_id", "hypothesis_id", "obligation_id", "predicate_id",
    "predicate_kind", "binding",
))
_DECISION_FIELDS = frozenset((
    "schema_version", "decision_id", "decision", "reason_code",
    "evidence_family", "predicate_kind", "polarity", "query_id",
    "hypothesis_id", "obligation_id", "predicate_id", "binding",
    "source_observation_digest", "signal_digest", "artifact_digest",
    "domain_id", "selected_statistic", "dependency_group",
    "adapter_version", "adapter_producer", "risk_atom_id",
    "decision_digest",
))
_WRAPPER_FIELDS = frozenset((
    "schema_version", "query_id", "hypothesis_id", "obligation_id",
    "predicate_id", "predicate_kind", "binding",
    "source_observation_digest", "evidence", "signal",
    "calibration_artifact", "adapter_decision", "risk_atom",
))

ADAPTER_VERSION = "proofnav.duet-entity-support-adapter.v1"
ADAPTER_PRODUCER = "proofnav.perception.evidence_adapter.adapt_entity_signal"


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _exact(value, fields, location):
    if not isinstance(value, dict):
        _fail("TYPE_MAPPING", location, "expected an object")
    missing = sorted(set(fields) - set(value))
    if missing:
        _fail("M3_MISSING_FIELDS", location, "missing %s" % missing)
    unknown = sorted(set(value) - set(fields))
    if unknown:
        _fail("M3_UNKNOWN_FIELDS", location, "unknown fields %s" % unknown)
    return value


def _sha(value, location):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        _fail("M3_SHA256", location, "lowercase SHA-256 required")
    return value


def _finite(value, location):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail("M3_NONFINITE", location, "finite number required")
    return float(value)


def validate_duet_signal(signal, observation=None, template=None,
                         expected_model_identity=None):
    """Validate the complete finite, self-contained DUET signal record."""

    signal = _exact(signal, _SIGNAL_FIELDS, "$.signal")
    assert_agent_visible(signal, "$.signal")
    constants = {
        "schema_version": DUET_SIGNAL_SCHEMA_VERSION,
        "producer": DUET_SIGNAL_PRODUCER,
        "source_schema": DUET_SIGNAL_SOURCE_SCHEMA,
        "signal_semantics": "uncalibrated_duet_object_proposal_score",
        "evidence_authority": False,
    }
    for key, expected in constants.items():
        if signal[key] != expected:
            _fail("M3_SIGNAL_SEMANTICS", "$.signal." + key, "expected %r" % expected)
    source = validate_observation(signal["observation"])
    if signal["observation_digest"] != canonical_sha256(source):
        _fail("M3_SIGNAL_OBSERVATION_DIGEST", "$.signal.observation_digest", "observation changed")
    if observation is not None and source != validate_observation(observation):
        _fail("M3_SIGNAL_OBSERVATION", "$.signal.observation", "does not match supplied observation")
    if signal["instruction_digest"] != canonical_sha256(source["instruction"]):
        _fail("M3_SIGNAL_INSTRUCTION", "$.signal.instruction_digest", "instruction changed")
    _sha(signal["template_digest"], "$.signal.template_digest")
    if template is not None and signal["template_digest"] != canonical_sha256(template):
        _fail("M3_SIGNAL_TEMPLATE", "$.signal.template_digest", "template changed")
    validate_model_identity(signal["model_identity"], "$.signal.model_identity")
    if expected_model_identity is not None and signal["model_identity"] != expected_model_identity:
        _fail("M3_SIGNAL_MODEL_IDENTITY", "$.signal.model_identity", "unexpected model identity")

    scores = _exact(signal["object_scores"], _SCORE_FIELDS, "$.signal.object_scores")
    proposals = scores["proposal_ids"]
    mask = scores["valid_mask"]
    logits = scores["logits"]
    if not isinstance(proposals, list) or not isinstance(mask, list) or not isinstance(logits, list):
        _fail("M3_SIGNAL_SCORES", "$.signal.object_scores", "three aligned arrays required")
    if proposals != source["object_proposal_ids"] or len(proposals) != len(mask) or len(mask) != len(logits):
        _fail("M3_SIGNAL_SCORE_LENGTH", "$.signal.object_scores", "proposal identity/length mismatch")
    if len(proposals) != len(set(proposals)):
        _fail("M3_SIGNAL_PROPOSAL_DUPLICATE", "$.signal.object_scores.proposal_ids", "unique slots required")
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, str) or not proposal:
            _fail("TYPE_STRING", "$.signal.object_scores.proposal_ids[%d]" % index, "non-empty string required")
    if any(not isinstance(value, bool) for value in mask):
        _fail("M3_SIGNAL_MASK", "$.signal.object_scores.valid_mask", "boolean mask required")
    logits = [_finite(value, "$.signal.object_scores.logits[%d]" % index) for index, value in enumerate(logits)]
    valid = [index for index, item in enumerate(mask) if item]
    selected_index = scores["selected_index"]
    if not valid:
        if any(scores[key] is not None for key in ("selected_index", "selected_proposal_id", "selected_statistic")):
            _fail("M3_SIGNAL_EMPTY_SELECTION", "$.signal.object_scores", "no valid proposal must have null selection")
    else:
        expected = max(valid, key=lambda index: (logits[index], -index))
        if isinstance(selected_index, bool) or selected_index != expected:
            _fail("M3_SIGNAL_SELECTED_INDEX", "$.signal.object_scores.selected_index", "must select max finite valid logit")
        if scores["selected_proposal_id"] != proposals[expected] or _finite(scores["selected_statistic"], "$.signal.object_scores.selected_statistic") != logits[expected]:
            _fail("M3_SIGNAL_SELECTION", "$.signal.object_scores", "selected identity/statistic mismatch")

    contents = _exact(signal["content_digests"], _CONTENT_NAMES, "$.signal.content_digests")
    expected_dtypes = dict((name, "float32") for name in _CONTENT_NAMES)
    expected_dtypes["instruction_encoding"] = "int64"
    # DUET consumes a candidate-first view tensor.  Multiple navigable
    # candidates can share one panorama point_id, so its packed row count may
    # exceed the raw 36-view observation schema.  Bind that exact audited
    # packing instead of incorrectly forcing the source panorama row count.
    candidate_count = len(source["candidates"])
    candidate_point_count = len({
        item["point_id"] for item in source["candidates"]
    })
    packed_view_rows = candidate_count + 36 - candidate_point_count
    packed_view_shape = [
        packed_view_rows, source["field_schema"]["feature"]["shape"][1],
    ]
    for name in sorted(_CONTENT_NAMES):
        item = _exact(contents[name], _CONTENT_FIELDS, "$.signal.content_digests." + name)
        _sha(item["digest"], "$.signal.content_digests.%s.digest" % name)
        shape = item["shape"]
        if (not isinstance(shape, list)
                or any(isinstance(dim, bool) or not isinstance(dim, int) or dim < 0 for dim in shape)
                or item["dtype"] != expected_dtypes[name]):
            _fail("M3_SIGNAL_CONTENT_SCHEMA", "$.signal.content_digests." + name, "post-cast shape/dtype mismatch")
        if name in ("object_features", "object_angle_features", "object_box_features") and (not shape or shape[0] != len(proposals)):
            _fail("M3_SIGNAL_CONTENT_SCHEMA", "$.signal.content_digests." + name, "object leading dimension mismatch")
        if name == "panorama_features" and shape != packed_view_shape:
            _fail(
                "M3_SIGNAL_CONTENT_SCHEMA",
                "$.signal.content_digests.panorama_features",
                "candidate-first packed panorama shape mismatch",
            )
        if name == "instruction_encoding" and shape != [source["instruction_encoding_length"]]:
            _fail("M3_SIGNAL_CONTENT_SCHEMA", "$.signal.content_digests." + name, "instruction length mismatch")

    sealed = copy.deepcopy(signal)
    digest = sealed.pop("signal_digest")
    _sha(digest, "$.signal.signal_digest")
    if digest != canonical_sha256(sealed):
        _fail("M3_SIGNAL_DIGEST", "$.signal.signal_digest", "signal content changed")
    return signal


def _validate_query(query):
    query = _exact(query, _QUERY_FIELDS, "$.query")
    for key in _QUERY_FIELDS - {"binding"}:
        if not isinstance(query[key], str) or not query[key]:
            _fail("TYPE_STRING", "$.query." + key, "non-empty string required")
    validate_binding(query["binding"], "$.query.binding")
    return query


def _decision(query, signal, artifact, decision, reason_code, risk_atom_id):
    result = {
        "schema_version": SCHEMA_VERSIONS["adapter_decision"],
        "decision_id": "decision-pending",
        "decision": decision,
        "reason_code": reason_code,
        "evidence_family": "duet_annotated_slot_entity_grounding",
        "predicate_kind": query["predicate_kind"],
        "polarity": "SUPPORTS" if decision == "SUPPORTS" else None,
        "query_id": query["query_id"],
        "hypothesis_id": query["hypothesis_id"],
        "obligation_id": query["obligation_id"],
        "predicate_id": query["predicate_id"],
        "binding": copy.deepcopy(query["binding"]),
        "source_observation_digest": signal["observation_digest"],
        "signal_digest": signal["signal_digest"],
        "artifact_digest": artifact["artifact_digest"] if artifact is not None else None,
        "domain_id": artifact["validity_domain"]["domain_id"] if artifact is not None else None,
        "selected_statistic": signal["object_scores"]["selected_statistic"],
        "dependency_group": "duet-observation:%s" % signal["observation"]["event_id"],
        "adapter_version": ADAPTER_VERSION,
        "adapter_producer": ADAPTER_PRODUCER,
        "risk_atom_id": risk_atom_id,
        "decision_digest": "pending",
    }
    identity = copy.deepcopy(result)
    identity.pop("decision_id")
    identity.pop("decision_digest")
    result["decision_id"] = "decision-" + canonical_sha256(identity)[:24]
    sealed = copy.deepcopy(result)
    sealed.pop("decision_digest")
    result["decision_digest"] = canonical_sha256(sealed)
    return validate_adapter_decision(result)


def validate_adapter_decision(value):
    value = _exact(value, _DECISION_FIELDS, "$.adapter_decision")
    if value["schema_version"] != SCHEMA_VERSIONS["adapter_decision"]:
        _fail("SCHEMA_VERSION", "$.adapter_decision.schema_version", "adapter-decision v1 required")
    if value["decision"] not in ("SUPPORTS", "ABSTAIN"):
        _fail("M3_ADAPTER_DECISION", "$.adapter_decision.decision", "M3-A only supports SUPPORTS/ABSTAIN")
    if value["adapter_version"] != ADAPTER_VERSION or value["adapter_producer"] != ADAPTER_PRODUCER:
        _fail("M3_ADAPTER_PRODUCER", "$.adapter_decision", "code-owned adapter required")
    for key in (
            "decision_id", "reason_code", "evidence_family", "predicate_kind",
            "query_id", "hypothesis_id", "obligation_id", "predicate_id",
            "dependency_group", "adapter_version", "adapter_producer"):
        if not isinstance(value[key], str) or not value[key]:
            _fail("TYPE_STRING", "$.adapter_decision." + key, "non-empty string required")
    if value["evidence_family"] != "duet_annotated_slot_entity_grounding":
        _fail("M3_ADAPTER_FAMILY", "$.adapter_decision.evidence_family", "unregistered family")
    for key in ("source_observation_digest", "signal_digest"):
        _sha(value[key], "$.adapter_decision." + key)
    if value["artifact_digest"] is not None:
        _sha(value["artifact_digest"], "$.adapter_decision.artifact_digest")
    if value["selected_statistic"] is not None:
        _finite(value["selected_statistic"], "$.adapter_decision.selected_statistic")
    if value["decision"] == "SUPPORTS":
        for key in ("artifact_digest", "domain_id", "risk_atom_id"):
            if not isinstance(value[key], str) or not value[key]:
                _fail("M3_ADAPTER_SUPPORT", "$.adapter_decision." + key, "required for SUPPORTS")
        if value["polarity"] != "SUPPORTS" or value["reason_code"] != "CALIBRATED_SUPPORT":
            _fail("M3_ADAPTER_SUPPORT", "$.adapter_decision", "invalid support semantics")
        if value["predicate_kind"] != "entity":
            _fail("M3_ADAPTER_SUPPORT", "$.adapter_decision.predicate_kind", "only entity SUPPORT is registered")
        expected_atom_id = "atom-" + canonical_sha256({
            "signal_digest": value["signal_digest"],
            "artifact_digest": value["artifact_digest"],
            "query_id": value["query_id"],
            "polarity": "SUPPORTS",
        })[:24]
        if value["risk_atom_id"] != expected_atom_id:
            _fail("M3_ADAPTER_RISK_ATOM_ID", "$.adapter_decision.risk_atom_id", "non-canonical risk atom identity")
    else:
        if value["polarity"] is not None or value["risk_atom_id"] is not None:
            _fail("M3_ADAPTER_ABSTAIN", "$.adapter_decision", "ABSTAIN has no evidence polarity or risk atom")
        allowed_reasons = {
            "UNSUPPORTED_PREDICATE", "MISSING_CALIBRATION_ARTIFACT",
            "CALIBRATION_DOMAIN_MISMATCH", "EMPTY_OR_MASKED_PROPOSALS",
            "UNSUPPORTED_SUBJECT_COMPONENT", "SUBJECT_BINDING_MISMATCH",
            "ENTITY_BINDING_MISMATCH", "BELOW_SUPPORT_THRESHOLD",
        }
        if value["reason_code"] not in allowed_reasons:
            _fail("M3_ADAPTER_ABSTAIN", "$.adapter_decision.reason_code", "unregistered abstention reason")
    validate_binding(value["binding"], "$.adapter_decision.binding")
    identity = copy.deepcopy(value)
    identity.pop("decision_id")
    identity.pop("decision_digest")
    expected_decision_id = "decision-" + canonical_sha256(identity)[:24]
    if value["decision_id"] != expected_decision_id:
        _fail("M3_ADAPTER_DECISION_ID", "$.adapter_decision.decision_id", "non-canonical decision identity")
    sealed = copy.deepcopy(value)
    digest = sealed.pop("decision_digest")
    if digest != canonical_sha256(sealed):
        _fail("M3_ADAPTER_DIGEST", "$.adapter_decision.decision_digest", "decision changed")
    return value


def adapt_entity_signal(query, signal, artifact=None):
    """Return SUPPORTS only in the exact registered entity/domain slice."""

    query = _validate_query(query)
    signal = validate_duet_signal(signal)
    if query["predicate_kind"] != "entity":
        return _decision(query, signal, None, "ABSTAIN", "UNSUPPORTED_PREDICATE", None)
    if artifact is None:
        return _decision(query, signal, None, "ABSTAIN", "MISSING_CALIBRATION_ARTIFACT", None)
    try:
        artifact = validate_registered_calibration_artifact(
            artifact, signal=signal,
        )
    except ContractViolation as error:
        if error.code == "M3_CALIBRATION_DOMAIN":
            return _decision(query, signal, artifact, "ABSTAIN", "CALIBRATION_DOMAIN_MISMATCH", None)
        raise
    require_registered_signal_digest(
        artifact["artifact_digest"], signal["signal_digest"],
    )
    scores = signal["object_scores"]
    if scores["selected_index"] is None:
        return _decision(query, signal, artifact, "ABSTAIN", "EMPTY_OR_MASKED_PROPOSALS", None)
    subject_units = query["binding"]["subject_unit_ids"]
    if len(subject_units) != 1:
        return _decision(query, signal, artifact, "ABSTAIN", "UNSUPPORTED_SUBJECT_COMPONENT", None)
    expected_unit = object_unit_id(signal["observation"]["viewpoint"], scores["selected_proposal_id"])
    if subject_units[0] != expected_unit:
        return _decision(query, signal, artifact, "ABSTAIN", "SUBJECT_BINDING_MISMATCH", None)
    binding = query["binding"]
    from proofnav.runtime.semantics import location_binding_id  # pylint: disable=import-outside-toplevel
    if (binding["anchor_binding_id"] is not None
            or binding["anchor_unit_ids"]
            or binding["spatial_anchor_id"] is not None
            or binding["location_binding_id"]
            != location_binding_id(signal["observation"]["viewpoint"])):
        return _decision(query, signal, artifact, "ABSTAIN", "ENTITY_BINDING_MISMATCH", None)
    threshold = artifact["calibration_parameters"]["support_threshold"]
    if scores["selected_statistic"] < threshold:
        return _decision(query, signal, artifact, "ABSTAIN", "BELOW_SUPPORT_THRESHOLD", None)
    atom_id = "atom-" + canonical_sha256({
        "signal_digest": signal["signal_digest"],
        "artifact_digest": artifact["artifact_digest"],
        "query_id": query["query_id"],
        "polarity": "SUPPORTS",
    })[:24]
    return _decision(query, signal, artifact, "SUPPORTS", "CALIBRATED_SUPPORT", atom_id)


def build_calibrated_bound_evidence(query, signal, artifact, scope_contract_id):
    """Build a v3 wrapper, or return an ABSTAIN decision without evidence."""

    decision = adapt_entity_signal(query, signal, artifact)
    if decision["decision"] == "ABSTAIN":
        return decision
    observation = signal["observation"]
    scores = signal["object_scores"]
    evidence_id = "evidence-" + canonical_sha256({
        "decision_digest": decision["decision_digest"],
        "scope_contract_id": scope_contract_id,
    })[:24]
    evidence = {
        "schema_version": SCHEMA_VERSIONS["evidence"],
        "evidence_id": evidence_id,
        "episode_id": observation["episode_id"],
        "source": "observation",
        "source_event_id": observation["event_id"],
        "event_seq": observation["event_seq"],
        "step": observation["step"],
        "scan": observation["scan"],
        "viewpoint": observation["viewpoint"],
        "view_index": observation["view_index"],
        "evidence_role": "object_slot",
        "unit_id": decision["binding"]["subject_unit_ids"][0],
        "scope_contract_id": scope_contract_id,
        "obligation_id": query["obligation_id"],
        "predicate_id": query["predicate_id"],
        "claim": "SUPPORTS",
        "adapter_version": ADAPTER_VERSION,
        "dependency_group": decision["dependency_group"],
        "audit_trail": {"producer": ADAPTER_PRODUCER, "source_field": "object_scores.selected_statistic"},
    }
    validate_evidence(evidence, {observation["event_id"]: observation})
    atom = {
        "schema_version": SCHEMA_VERSIONS["risk_atom"],
        "atom_id": decision["risk_atom_id"],
        "event_type": "false_support",
        "polarity": "SUPPORTS",
        "upper_bound": artifact["risk_bound"]["upper_bound"],
        "familywise": True,
        "family_key": "artifact:%s:source-observation:%s" % (artifact["artifact_digest"], observation["event_id"]),
        "evidence_id": evidence_id,
        "artifact_digest": artifact["artifact_digest"],
        "signal_digest": signal["signal_digest"],
        "dependency_group": decision["dependency_group"],
    }
    atom["atom_digest"] = canonical_sha256(atom)
    wrapper = dict((key, copy.deepcopy(query[key])) for key in _QUERY_FIELDS)
    wrapper.update({
        "schema_version": SCHEMA_VERSIONS["m3_bound_evidence"],
        "source_observation_digest": signal["observation_digest"],
        "evidence": evidence,
        "signal": copy.deepcopy(signal),
        "calibration_artifact": copy.deepcopy(artifact),
        "adapter_decision": decision,
        "risk_atom": atom,
    })
    _exact(wrapper, _WRAPPER_FIELDS, "$.m3_bound_evidence")
    return wrapper
