"""Controlled truth and evidence-script support for M2.1 replay.

Hidden truth and emitted predicate evidence are deliberately different
artifacts.  A script may emit a factually wrong predicate result; that must not
make the hidden truth internally inconsistent.  Both artifacts are offline
only, while emitted records use the same M1 evidence record nested in the M2.1
typed-binding wrapper.
"""

import copy

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.validation import validate_evidence, validate_observation, validate_scope


_PREMISE_CLASSES = frozenset((
    "entity_absent", "attribute_mismatch", "relation_mismatch",
    "room_anchor_mismatch", "positive_control",
))
_SUBJECT_HYPOTHESIS_KINDS = frozenset((
    "subject", "subject_relation", "subject_room",
))
_RESIDUAL_HYPOTHESIS_KINDS = frozenset((
    "location_residual", "anchor_residual",
))
_TRUTH_POLARITIES = frozenset(("SUPPORTS", "REFUTES", "OPEN"))


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _exact(value, fields, location, code="CONTROLLED_SCHEMA"):
    if not isinstance(value, dict):
        _fail("TYPE_MAPPING", location, "expected an object")
    missing = sorted(set(fields) - set(value))
    if missing:
        _fail(code, location, "missing fields %s" % missing)
    unknown = sorted(set(value) - set(fields))
    if unknown:
        _fail(code, location, "unknown fields %s" % unknown)
    return value


def _string(value, location):
    if not isinstance(value, str) or not value:
        _fail("TYPE_STRING", location, "expected a non-empty string")
    return value


def _string_list(value, location):
    if not isinstance(value, list):
        _fail("TYPE_LIST", location, "expected an array")
    for index, item in enumerate(value):
        _string(item, "%s[%d]" % (location, index))
    if len(value) != len(set(value)):
        _fail("CONTROLLED_DUPLICATE", location, "values must be unique")
    return value


def _validate_binding(value, location):
    fields = {
        "subject_binding_id", "subject_unit_ids", "anchor_binding_id",
        "anchor_unit_ids", "location_binding_id", "spatial_anchor_id",
    }
    value = _exact(value, fields, location)
    for key in ("subject_binding_id", "anchor_binding_id", "spatial_anchor_id"):
        if value[key] is not None:
            _string(value[key], location + "." + key)
    _string_list(value["subject_unit_ids"], location + ".subject_unit_ids")
    _string_list(value["anchor_unit_ids"], location + ".anchor_unit_ids")
    _string(value["location_binding_id"], location + ".location_binding_id")
    if bool(value["subject_binding_id"]) != bool(value["subject_unit_ids"]):
        _fail("CONTROLLED_BINDING_SUBJECT", location, "subject ID and units must co-occur")
    if bool(value["anchor_binding_id"]) != bool(value["anchor_unit_ids"]):
        _fail("CONTROLLED_BINDING_ANCHOR", location, "anchor ID and units must co-occur")
    expected_subject = (
        "subject-" + canonical_sha256({
            "subject_unit_ids": sorted(value["subject_unit_ids"]),
        })[:20]
        if value["subject_unit_ids"] else None
    )
    expected_anchor = (
        "subject-" + canonical_sha256({
            "subject_unit_ids": sorted(value["anchor_unit_ids"]),
        })[:20]
        if value["anchor_unit_ids"] else None
    )
    if value["subject_binding_id"] != expected_subject:
        _fail("CONTROLLED_BINDING_SUBJECT", location + ".subject_binding_id", "non-canonical ID")
    if value["anchor_binding_id"] != expected_anchor:
        _fail("CONTROLLED_BINDING_ANCHOR", location + ".anchor_binding_id", "non-canonical ID")
    return value


def _artifact_digest(value):
    """Hash an artifact while excluding only its self-referential digest."""

    payload = copy.deepcopy(value)
    audit = payload.get("audit_trail")
    if isinstance(audit, dict):
        audit.pop("source_artifact_digest", None)
    return canonical_sha256(payload)


def seal_controlled_artifact(value):
    """Return a copy with its canonical ``source_artifact_digest`` filled."""

    result = copy.deepcopy(value)
    if not isinstance(result.get("audit_trail"), dict):
        _fail("CONTROLLED_AUDIT", "$.audit_trail", "expected an audit object")
    result["audit_trail"]["source_artifact_digest"] = _artifact_digest(result)
    return result


def _catalogs(value):
    hypotheses = {}
    for index, hypothesis in enumerate(value["hypotheses"]):
        location = "$.hypotheses[%d]" % index
        hypothesis = _exact(hypothesis, {
            "hypothesis_id", "hypothesis_kind", "binding", "derivation_event_ids",
        }, location)
        hypothesis_id = _string(hypothesis["hypothesis_id"], location + ".hypothesis_id")
        if hypothesis_id in hypotheses:
            _fail("CONTROLLED_HYPOTHESIS_DUPLICATE", location, "duplicate hypothesis")
        kind = hypothesis["hypothesis_kind"]
        if kind not in _SUBJECT_HYPOTHESIS_KINDS | _RESIDUAL_HYPOTHESIS_KINDS:
            _fail("CONTROLLED_HYPOTHESIS_KIND", location + ".hypothesis_kind", "invalid kind")
        binding = _validate_binding(hypothesis["binding"], location + ".binding")
        subject = bool(binding["subject_unit_ids"])
        anchor = bool(binding["anchor_unit_ids"])
        spatial = binding["spatial_anchor_id"] is not None
        expected_shape = {
            "subject": (True, False, False),
            "subject_relation": (True, True, False),
            "subject_room": (True, False, True),
            "location_residual": (False, False, False),
            "anchor_residual": (True, False, False),
        }[kind]
        if (subject, anchor, spatial) != expected_shape:
            _fail(
                "CONTROLLED_HYPOTHESIS_BINDING_SHAPE", location + ".binding",
                "binding does not match the typed hypothesis kind",
            )
        if set(binding["subject_unit_ids"]) & set(binding["anchor_unit_ids"]):
            _fail(
                "CONTROLLED_HYPOTHESIS_BINDING_SHAPE", location + ".binding",
                "subject and anchor units must be disjoint",
            )
        _string_list(hypothesis["derivation_event_ids"], location + ".derivation_event_ids")
        hypotheses[hypothesis_id] = copy.deepcopy(hypothesis)

    obligations = {}
    for index, obligation in enumerate(value["obligations"]):
        location = "$.obligations[%d]" % index
        obligation = _exact(obligation, {
            "obligation_id", "hypothesis_id", "predicate_id", "predicate_kind",
            "necessary", "binding_requirement",
        }, location)
        obligation_id = _string(obligation["obligation_id"], location + ".obligation_id")
        if obligation_id in obligations:
            _fail("CONTROLLED_OBLIGATION_DUPLICATE", location, "duplicate obligation")
        for key in ("hypothesis_id", "predicate_id", "predicate_kind"):
            _string(obligation[key], location + "." + key)
        if obligation["hypothesis_id"] not in hypotheses:
            _fail("CONTROLLED_OBLIGATION_HYPOTHESIS", location, "unknown hypothesis")
        if not isinstance(obligation["necessary"], bool):
            _fail("TYPE_BOOLEAN", location + ".necessary", "expected boolean")
        _validate_binding(obligation["binding_requirement"], location + ".binding_requirement")
        if obligation["binding_requirement"] != hypotheses[obligation["hypothesis_id"]]["binding"]:
            _fail("CONTROLLED_OBLIGATION_BINDING", location, "hypothesis binding mismatch")
        hypothesis_kind = hypotheses[obligation["hypothesis_id"]]["hypothesis_kind"]
        if hypothesis_kind in _RESIDUAL_HYPOTHESIS_KINDS:
            if obligation["predicate_kind"] != "coverage" or not obligation["necessary"]:
                _fail(
                    "CONTROLLED_RESIDUAL_OBLIGATION", location,
                    "residual hypotheses require necessary coverage",
                )
        elif obligation["predicate_kind"] == "coverage":
            _fail(
                "CONTROLLED_SUBJECT_OBLIGATION", location,
                "subject hypotheses cannot use coverage obligations",
            )
        obligations[obligation_id] = copy.deepcopy(obligation)
    if not hypotheses or not obligations:
        _fail("CONTROLLED_UNIVERSE_EMPTY", "$", "truth needs a non-empty dynamic universe")
    for hypothesis_id in hypotheses:
        hypothesis_obligations = [
            item for item in obligations.values()
            if item["hypothesis_id"] == hypothesis_id
        ]
        if not any(item["necessary"] for item in hypothesis_obligations):
            _fail("CONTROLLED_HYPOTHESIS_UNPROVABLE", "$.obligations", "missing necessary obligation")
        if (hypotheses[hypothesis_id]["hypothesis_kind"]
                in _RESIDUAL_HYPOTHESIS_KINDS
                and len(hypothesis_obligations) != 1):
            _fail(
                "CONTROLLED_RESIDUAL_OBLIGATION", "$.obligations",
                "a residual hypothesis has exactly one coverage obligation",
            )
    return hypotheses, obligations


def validate_controlled_truth(value):
    """Validate a self-consistent v2 truth artifact and derive its verdict.

    Every dynamic obligation has one authoritative typed evaluation.  A
    subject hypothesis is supported only when all its necessary obligations
    SUPPORT; any necessary REFUTES excludes it.  OPEN is never treated as a
    refutation.  NOT_FOUND therefore requires a refutation for every dynamic
    hypothesis, including location-residual coverage hypotheses.
    """

    fields = {
        "schema_version", "episode_id", "scope_contract_id", "scope_version",
        "scope_digest", "template_id", "template_digest", "universe_digest",
        "premise_class", "semantic_truth", "hypotheses", "obligations",
        "claims", "supported_hypothesis_ids", "refuted_hypothesis_ids",
        "audit_trail",
    }
    value = _exact(value, fields, "$")
    if value["schema_version"] != SCHEMA_VERSIONS["controlled_truth"]:
        _fail("SCHEMA_VERSION", "$.schema_version", "controlled-truth v2 required")
    for key in (
            "episode_id", "scope_contract_id", "scope_version", "scope_digest",
            "template_id", "template_digest", "universe_digest"):
        _string(value[key], "$." + key)
    if value["premise_class"] not in _PREMISE_CLASSES:
        _fail("CONTROLLED_TRUTH_PREMISE", "$.premise_class", "invalid premise class")
    if value["semantic_truth"] not in ("FOUND", "NOT_FOUND"):
        _fail("CONTROLLED_TRUTH_VERDICT", "$.semantic_truth", "invalid verdict")
    expected_direction = (
        "FOUND" if value["premise_class"] == "positive_control"
        else "NOT_FOUND"
    )
    if value["semantic_truth"] != expected_direction:
        _fail(
            "CONTROLLED_TRUTH_PREMISE", "$.semantic_truth",
            "premise class and semantic truth direction disagree",
        )
    if not isinstance(value["hypotheses"], list) or not isinstance(value["obligations"], list):
        _fail("TYPE_LIST", "$.hypotheses", "hypotheses/obligations must be arrays")
    hypotheses, obligations = _catalogs(value)

    if value["universe_digest"] != canonical_sha256({
            "hypotheses": value["hypotheses"],
            "obligations": value["obligations"],
            "generator_version": "proofnav.dynamic-universe.v2",
    }):
        _fail("CONTROLLED_TRUTH_UNIVERSE_DIGEST", "$.universe_digest", "catalog was modified")
    if not isinstance(value["claims"], list):
        _fail("TYPE_LIST", "$.claims", "expected an array")
    claims = {}
    claim_fields = {
        "hypothesis_id", "obligation_id", "predicate_id", "predicate_kind",
        "binding", "claim",
    }
    for index, claim in enumerate(value["claims"]):
        location = "$.claims[%d]" % index
        claim = _exact(claim, claim_fields, location)
        obligation_id = _string(claim["obligation_id"], location + ".obligation_id")
        if obligation_id in claims:
            _fail("CONTROLLED_TRUTH_CLAIM_DUPLICATE", location, "one evaluation per obligation")
        obligation = obligations.get(obligation_id)
        if obligation is None:
            _fail("CONTROLLED_TRUTH_OBLIGATION", location, "unknown obligation")
        expected = {
            "hypothesis_id": obligation["hypothesis_id"],
            "predicate_id": obligation["predicate_id"],
            "predicate_kind": obligation["predicate_kind"],
            "binding": obligation["binding_requirement"],
        }
        for key, expected_value in expected.items():
            if claim[key] != expected_value:
                _fail("CONTROLLED_TRUTH_%s" % key.upper(), location + "." + key, "obligation mismatch")
        _validate_binding(claim["binding"], location + ".binding")
        if claim["claim"] not in _TRUTH_POLARITIES:
            _fail("CONTROLLED_TRUTH_CLAIM", location + ".claim", "invalid polarity")
        claims[obligation_id] = copy.deepcopy(claim)
    if set(claims) != set(obligations):
        _fail("CONTROLLED_TRUTH_CLAIM_COVERAGE", "$.claims", "every obligation needs an evaluation")

    supported = set()
    refuted = set()
    for hypothesis_id, hypothesis in hypotheses.items():
        necessary = [
            item for item in obligations.values()
            if item["hypothesis_id"] == hypothesis_id and item["necessary"]
        ]
        polarities = [claims[item["obligation_id"]]["claim"] for item in necessary]
        if all(item == "SUPPORTS" for item in polarities):
            if hypothesis["hypothesis_kind"] in _SUBJECT_HYPOTHESIS_KINDS:
                supported.add(hypothesis_id)
        elif any(item == "REFUTES" for item in polarities):
            refuted.add(hypothesis_id)
    declared_supported = _string_list(
        value["supported_hypothesis_ids"], "$.supported_hypothesis_ids",
    )
    declared_refuted = _string_list(
        value["refuted_hypothesis_ids"], "$.refuted_hypothesis_ids",
    )
    if set(declared_supported) & set(declared_refuted):
        _fail("CONTROLLED_TRUTH_OVERLAP", "$", "supported/refuted sets must be disjoint")
    if set(declared_supported) != supported:
        _fail("CONTROLLED_TRUTH_SUPPORTED", "$.supported_hypothesis_ids", "does not match evaluations")
    if set(declared_refuted) != refuted:
        _fail("CONTROLLED_TRUTH_REFUTED", "$.refuted_hypothesis_ids", "does not match evaluations")
    expected_verdict = None
    if supported:
        expected_verdict = "FOUND"
    elif refuted == set(hypotheses):
        expected_verdict = "NOT_FOUND"
    if expected_verdict is None:
        _fail("CONTROLLED_TRUTH_UNRESOLVED", "$.claims", "OPEN obligations do not prove a binary truth")
    if value["semantic_truth"] != expected_verdict:
        _fail("CONTROLLED_TRUTH_VERDICT", "$.semantic_truth", "does not follow from evaluations")

    audit = _exact(value["audit_trail"], {
        "producer", "source_artifact_digest",
    }, "$.audit_trail")
    if audit["producer"] != "proofnav.offline.controlled_truth.v2":
        _fail("CONTROLLED_TRUTH_PRODUCER", "$.audit_trail.producer", "offline v2 producer required")
    if audit["source_artifact_digest"] != _artifact_digest(value):
        _fail("CONTROLLED_TRUTH_DIGEST", "$.audit_trail.source_artifact_digest", "artifact was modified")
    return value


def validate_controlled_script(value, truth=None):
    """Validate an evidence-emission script, independently of its polarity.

    If ``truth`` is supplied, identity and typed binding must match its dynamic
    universe, but emitted polarity is intentionally *not* compared.  This is
    how adversarial factual predicate errors are represented without corrupting
    hidden truth.
    """

    fields = {
        "schema_version", "script_id", "episode_id", "scope_contract_id",
        "scope_version", "scope_digest", "template_id", "template_digest",
        "universe_digest", "emissions", "audit_trail",
    }
    value = _exact(value, fields, "$")
    if value["schema_version"] != SCHEMA_VERSIONS["controlled_script"]:
        _fail("SCHEMA_VERSION", "$.schema_version", "controlled-evidence-script v2 required")
    for key in fields - {"schema_version", "emissions", "audit_trail"}:
        _string(value[key], "$." + key)
    if not isinstance(value["emissions"], list):
        _fail("TYPE_LIST", "$.emissions", "expected an array")
    emission_fields = {
        "emission_id", "query_id", "hypothesis_id", "obligation_id",
        "predicate_id", "predicate_kind", "binding", "source_event_id",
        "evidence_role", "unit_id", "claim",
    }
    seen = set()
    for index, emission in enumerate(value["emissions"]):
        location = "$.emissions[%d]" % index
        emission = _exact(emission, emission_fields, location)
        for key in emission_fields - {"binding"}:
            _string(emission[key], location + "." + key)
        if emission["emission_id"] in seen:
            _fail("CONTROLLED_SCRIPT_DUPLICATE", location + ".emission_id", "duplicate ID")
        seen.add(emission["emission_id"])
        if emission["claim"] not in ("SUPPORTS", "REFUTES"):
            _fail("CONTROLLED_SCRIPT_CLAIM", location + ".claim", "emission must be binary")
        if emission["evidence_role"] not in ("viewpoint_view", "object_slot"):
            _fail("CONTROLLED_SCRIPT_ROLE", location + ".evidence_role", "invalid role")
        _validate_binding(emission["binding"], location + ".binding")
    audit = _exact(value["audit_trail"], {
        "producer", "source_artifact_digest",
    }, "$.audit_trail")
    if audit["producer"] != "proofnav.offline.controlled_evidence_script.v2":
        _fail("CONTROLLED_SCRIPT_PRODUCER", "$.audit_trail.producer", "offline v2 producer required")
    if audit["source_artifact_digest"] != _artifact_digest(value):
        _fail("CONTROLLED_SCRIPT_DIGEST", "$.audit_trail.source_artifact_digest", "artifact was modified")

    if truth is not None:
        truth = copy.deepcopy(truth)
        validate_controlled_truth(truth)
        for key in (
                "episode_id", "scope_contract_id", "scope_version", "scope_digest",
                "template_id", "template_digest", "universe_digest"):
            if value[key] != truth[key]:
                _fail("CONTROLLED_SCRIPT_TRUTH_IDENTITY", "$." + key, "truth mismatch")
        obligations = {item["obligation_id"]: item for item in truth["obligations"]}
        for index, emission in enumerate(value["emissions"]):
            obligation = obligations.get(emission["obligation_id"])
            if obligation is None:
                _fail("CONTROLLED_SCRIPT_OBLIGATION", "$.emissions[%d]" % index, "unknown obligation")
            expected = {
                "hypothesis_id": obligation["hypothesis_id"],
                "predicate_id": obligation["predicate_id"],
                "predicate_kind": obligation["predicate_kind"],
                "binding": obligation["binding_requirement"],
            }
            for key, expected_value in expected.items():
                if emission[key] != expected_value:
                    _fail("CONTROLLED_SCRIPT_BINDING", "$.emissions[%d].%s" % (index, key), "truth mismatch")
    return value


def _bundle_core(bundle):
    if not isinstance(bundle, dict):
        _fail("TYPE_MAPPING", "$.audit_bundle", "expected an object")
    expected = {
        "schema_version", "scope", "template", "admission_profile",
        "risk_claims", "transitions", "state", "bundle_digest",
    }
    _exact(bundle, expected, "$.audit_bundle", "AUDIT_BUNDLE_SCHEMA")
    if bundle["schema_version"] != SCHEMA_VERSIONS["audit_bundle"]:
        _fail("SCHEMA_VERSION", "$.audit_bundle.schema_version", "audit-bundle v2 required")
    payload = copy.deepcopy(bundle)
    claimed = payload.pop("bundle_digest")
    if claimed != canonical_sha256(payload):
        _fail("AUDIT_BUNDLE_DIGEST", "$.audit_bundle.bundle_digest", "bundle was modified")
    return bundle


class ControlledProofState(object):
    """Factory for the offline-only event-sourced controlled state.

    Runtime imports are deliberately lazy.  Importing this module merely to
    validate hidden truth therefore does not initialize runtime verification
    code inside the independent offline auditor.
    """

    def __new__(cls, scope, template, risk_claims):
        del cls
        from proofnav.runtime.state import (  # pylint: disable=import-outside-toplevel
            _ProofStateCore, _controlled_admission_profile,
        )
        return _ProofStateCore(
            scope, template, risk_claims, _controlled_admission_profile(scope),
        )


class OracleEvidenceProvider(object):
    """Turn a v2 emission script into query-bound M1 evidence wrappers."""

    def __init__(self, scope, template):
        self._scope = copy.deepcopy(scope)
        self._template = copy.deepcopy(template)
        validate_scope(self._scope)

    def emit(self, script, audit_bundle):
        script = copy.deepcopy(script)
        validate_controlled_script(script)
        bundle = copy.deepcopy(audit_bundle)
        _bundle_core(bundle)
        state = bundle["state"]
        identity = {
            "episode_id": self._scope["episode_id"],
            "scope_contract_id": self._scope["scope_contract_id"],
            "scope_version": self._scope["provenance"]["version"],
            "scope_digest": canonical_sha256(self._scope),
            "template_id": self._template["template_id"],
            "template_digest": canonical_sha256(self._template),
            "universe_digest": state.get("universe_digest"),
        }
        for key, expected in identity.items():
            if script[key] != expected:
                _fail("CONTROLLED_SCRIPT_STATE_IDENTITY", "$." + key, "current state mismatch")
        if bundle["scope"] != self._scope or bundle["template"] != self._template:
            _fail("CONTROLLED_PROVIDER_BUNDLE", "$.audit_bundle", "provider scope/template mismatch")
        if bundle["admission_profile"].get("evidence_mode") != "controlled_replay":
            _fail("CONTROLLED_PROVIDER_PROFILE", "$.audit_bundle.admission_profile", "controlled replay required")
        if bundle["state"].get("proof_state_digest") != state.get("proof_state_digest"):
            _fail("CONTROLLED_PROVIDER_STATE", "$.audit_bundle.state", "invalid state")

        observations = {}
        for transition in bundle["transitions"]:
            if transition.get("event_type") == "OBSERVATION":
                observation = transition.get("payload")
                validate_observation(observation)
                observations[observation["event_id"]] = observation
        queries = {item["query_id"]: item for item in state.get("queries", [])}
        obligations = {item["obligation_id"]: item for item in state.get("obligations", [])}
        cut = state.get("decision_cut", {})
        values = []
        for index, emission in enumerate(script["emissions"]):
            location = "$.emissions[%d]" % index
            query = queries.get(emission["query_id"])
            obligation = obligations.get(emission["obligation_id"])
            observation = observations.get(emission["source_event_id"])
            if query is None:
                _fail("CONTROLLED_SCRIPT_QUERY", location + ".query_id", "query not admitted at cut")
            if obligation is None:
                _fail("CONTROLLED_SCRIPT_OBLIGATION", location + ".obligation_id", "obligation not current")
            if observation is None:
                _fail("CONTROLLED_SCRIPT_EVENT", location + ".source_event_id", "observation not admitted at cut")
            expected = {
                "hypothesis_id": obligation["hypothesis_id"],
                "obligation_id": obligation["obligation_id"],
                "predicate_id": obligation["predicate_id"],
                "predicate_kind": obligation["predicate_kind"],
                "binding": obligation["binding_requirement"],
            }
            for key, expected_value in expected.items():
                if emission[key] != expected_value or query.get(key) != expected_value:
                    _fail("CONTROLLED_SCRIPT_BINDING", location + "." + key, "query/obligation mismatch")
            if (observation["event_seq"] > cut.get("max_observation_event_seq", -1)
                    or observation["step"] > cut.get("max_step", -1)):
                _fail("CONTROLLED_SCRIPT_FUTURE", location + ".source_event_id", "observation is after decision cut")
            binding = obligation["binding_requirement"]
            source_units = {
                "objunit-" + canonical_sha256({
                    "viewpoint_id": str(observation["viewpoint"]),
                    "object_proposal_id": str(object_id),
                })[:20]
                for object_id in observation["object_proposal_ids"]
            }
            location_id = "loc-" + canonical_sha256({
                "viewpoint_id": str(observation["viewpoint"]),
            })[:20]
            if obligation["predicate_kind"] == "coverage":
                expected_unit = "viewunit-" + canonical_sha256({
                    "viewpoint_id": str(observation["viewpoint"]),
                })[:20]
                if (emission["evidence_role"] != "viewpoint_view"
                        or emission["unit_id"] != expected_unit
                        or binding["location_binding_id"] != location_id):
                    _fail("CONTROLLED_SCRIPT_COVERAGE_BINDING", location, "wrong viewpoint binding")
            else:
                if emission["evidence_role"] != "object_slot":
                    _fail("CONTROLLED_SCRIPT_ROLE", location + ".evidence_role", "object predicate needs object_slot")
                if (emission["unit_id"] not in binding["subject_unit_ids"]
                        or emission["unit_id"] not in source_units):
                    _fail("CONTROLLED_SCRIPT_SUBJECT_BINDING", location + ".unit_id", "wrong subject unit")
                if (obligation["predicate_kind"] == "relation"
                        and (not binding["anchor_unit_ids"]
                             or not (set(binding["anchor_unit_ids"]) & source_units))):
                    _fail("CONTROLLED_SCRIPT_ANCHOR_BINDING", location, "anchor is not co-observed")
                if (obligation["predicate_kind"] == "room_anchor"
                        and (binding["location_binding_id"] != location_id
                             or binding["spatial_anchor_id"] is None)):
                    _fail("CONTROLLED_SCRIPT_ROOM_BINDING", location, "room binding mismatch")
            evidence_identity = {
                "script_id": script["script_id"],
                "emission_id": emission["emission_id"],
                "query_id": emission["query_id"],
                "source_event_id": emission["source_event_id"],
                "claim": emission["claim"],
            }
            evidence = {
                "schema_version": SCHEMA_VERSIONS["evidence"],
                "evidence_id": "controlled-" + canonical_sha256(evidence_identity)[:20],
                "episode_id": observation["episode_id"],
                "source": "observation",
                "source_event_id": observation["event_id"],
                "event_seq": observation["event_seq"],
                "step": observation["step"],
                "scan": observation["scan"],
                "viewpoint": observation["viewpoint"],
                "view_index": observation["view_index"],
                "evidence_role": emission["evidence_role"],
                "unit_id": emission["unit_id"],
                "scope_contract_id": self._scope["scope_contract_id"],
                "obligation_id": emission["obligation_id"],
                "predicate_id": emission["predicate_id"],
                "claim": emission["claim"],
                "adapter_version": "proofnav.controlled-oracle.replay.v2",
                "dependency_group": "controlled-replay:%s" % observation["event_id"],
                "audit_trail": {
                    "producer": "proofnav.offline.OracleEvidenceProvider.v2",
                    "source_field": "emissions[%d]" % index,
                },
            }
            validate_evidence(evidence, observations)
            values.append({
                "schema_version": SCHEMA_VERSIONS["bound_evidence"],
                "query_id": emission["query_id"],
                "hypothesis_id": emission["hypothesis_id"],
                "obligation_id": emission["obligation_id"],
                "predicate_id": emission["predicate_id"],
                "predicate_kind": emission["predicate_kind"],
                "binding": copy.deepcopy(emission["binding"]),
                "source_observation_digest": canonical_sha256(observation),
                "evidence": evidence,
            })
        return values


class ReplayOnlineVerifier(object):
    """Offline replay of online semantics with controlled-source admission."""

    def __init__(self):
        from proofnav.runtime.verifier import _OnlineVerifierCore  # pylint: disable=import-outside-toplevel
        self._allow_controlled = True
        self._delegate = _OnlineVerifierCore(allow_controlled=True)

    def verify(self, state, certificate):
        return self._delegate.verify(state, certificate)


class ReplayTerminalController(object):
    """Offline-only controller used by controlled sequential replay."""

    def __init__(self):
        from proofnav.runtime.terminal import _TerminalControllerCore  # pylint: disable=import-outside-toplevel
        self._delegate = _TerminalControllerCore(ReplayOnlineVerifier())

    def decide(self, state, proposed_verdict, certificate, execution):
        return self._delegate.decide(state, proposed_verdict, certificate, execution)
