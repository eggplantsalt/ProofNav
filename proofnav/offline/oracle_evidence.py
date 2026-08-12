"""Controlled M2 evidence provider for offline tests and deterministic replay.

This module is deliberately outside :mod:`proofnav.runtime`.  Its evidence is
wire-compatible with M1 evidence but visibly tagged so production admission
and production online verification reject it.
"""

import copy

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.runtime.state import _BaseEvidenceLedger, _ProofStateCore
from proofnav.runtime.terminal import _TerminalControllerCore
from proofnav.runtime.verifier import _OnlineVerifierCore
from proofnav.validation import validate_obligation, validate_observation


_PREMISE_CLASSES = {
    "entity_absent", "attribute_mismatch", "relation_mismatch",
    "room_anchor_mismatch", "positive_control",
}


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _exact(value, fields, location):
    if not isinstance(value, dict):
        _fail("TYPE_MAPPING", location, "expected an object")
    if set(value) != set(fields):
        _fail("CONTROLLED_TRUTH_SCHEMA", location, "expected exact fields %s" % sorted(fields))
    return value


def validate_controlled_truth(value):
    fields = {
        "schema_version", "episode_id", "scope_contract_id", "scope_version",
        "scope_digest", "semantic_truth", "premise_class", "hypothesis_ids",
        "supported_hypothesis_ids", "refuted_hypothesis_ids", "claims",
        "audit_trail",
    }
    value = _exact(value, fields, "$")
    if value["schema_version"] != SCHEMA_VERSIONS["controlled_truth"]:
        _fail("SCHEMA_VERSION", "$.schema_version", "controlled truth version mismatch")
    for key in ("episode_id", "scope_contract_id", "scope_version", "scope_digest"):
        if not isinstance(value[key], str) or not value[key]:
            _fail("TYPE_STRING", "$." + key, "expected non-empty string")
    if value["semantic_truth"] not in ("FOUND", "NOT_FOUND"):
        _fail("CONTROLLED_TRUTH_VERDICT", "$.semantic_truth", "invalid verdict")
    if value["premise_class"] not in _PREMISE_CLASSES:
        _fail("CONTROLLED_TRUTH_PREMISE", "$.premise_class", "invalid class")
    for key in ("hypothesis_ids", "supported_hypothesis_ids", "refuted_hypothesis_ids"):
        values = value[key]
        if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
            _fail("TYPE_LIST", "$." + key, "expected string array")
        if len(values) != len(set(values)):
            _fail("CONTROLLED_TRUTH_DUPLICATE", "$." + key, "duplicate ID")
    universe = set(value["hypothesis_ids"])
    if not set(value["supported_hypothesis_ids"]).issubset(universe):
        _fail("CONTROLLED_TRUTH_SCOPE", "$.supported_hypothesis_ids", "out-of-scope hypothesis")
    if not set(value["refuted_hypothesis_ids"]).issubset(universe):
        _fail("CONTROLLED_TRUTH_SCOPE", "$.refuted_hypothesis_ids", "out-of-scope hypothesis")
    if value["semantic_truth"] == "FOUND" and not value["supported_hypothesis_ids"]:
        _fail("CONTROLLED_TRUTH_FOUND", "$.supported_hypothesis_ids", "FOUND needs support")
    if value["semantic_truth"] == "NOT_FOUND" and set(value["refuted_hypothesis_ids"]) != universe:
        _fail("CONTROLLED_TRUTH_NOT_FOUND", "$.refuted_hypothesis_ids", "NOT_FOUND must refute universe")
    if not isinstance(value["claims"], list):
        _fail("TYPE_LIST", "$.claims", "expected array")
    claim_fields = {"obligation_id", "claim", "source_event_id", "evidence_role", "unit_id"}
    for index, claim in enumerate(value["claims"]):
        claim = _exact(claim, claim_fields, "$.claims[%d]" % index)
        for key in ("obligation_id", "source_event_id", "unit_id"):
            if not isinstance(claim[key], str) or not claim[key]:
                _fail("TYPE_STRING", "$.claims[%d].%s" % (index, key), "expected string")
        if claim["claim"] not in ("SUPPORTS", "REFUTES"):
            _fail("CONTROLLED_TRUTH_CLAIM", "$.claims[%d].claim" % index, "invalid polarity")
        if claim["evidence_role"] not in ("viewpoint_view", "object_slot"):
            _fail("CONTROLLED_TRUTH_ROLE", "$.claims[%d].evidence_role" % index, "invalid role")
    audit = _exact(value["audit_trail"], {"producer", "source_artifact_digest"}, "$.audit_trail")
    if audit["producer"] != "proofnav.offline.controlled_truth":
        _fail("CONTROLLED_TRUTH_PRODUCER", "$.audit_trail.producer", "offline producer required")
    if not isinstance(audit["source_artifact_digest"], str) or len(audit["source_artifact_digest"]) != 64:
        _fail("CONTROLLED_TRUTH_DIGEST", "$.audit_trail.source_artifact_digest", "SHA-256 required")
    return value


class ControlledEvidenceLedger(_BaseEvidenceLedger):

    def _admit_adapter(self, evidence):
        if evidence["adapter_version"] != "proofnav.controlled-oracle.replay.v1":
            _fail("CONTROLLED_ADAPTER_REQUIRED", "$.adapter_version", "exact replay adapter required")
        if evidence["audit_trail"]["producer"] != "proofnav.offline.OracleEvidenceProvider":
            _fail("CONTROLLED_PRODUCER_REQUIRED", "$.audit_trail.producer", "exact provider required")


class ControlledProofState(_ProofStateCore):
    """Offline-only state using the same proof semantics and M1 evidence wire format."""

    def __init__(self, scope, obligations, observations, frontier_witnesses,
                 scope_closed, budget_status, cost_ledger, risk_claims):
        super().__init__(
            scope, obligations, observations, frontier_witnesses, scope_closed,
            budget_status, cost_ledger, risk_claims, ControlledEvidenceLedger,
        )


class OracleEvidenceProvider(object):
    """Translate hidden controlled claims into observation-tethered evidence."""

    def __init__(self, scope, obligations, observations):
        self._scope = copy.deepcopy(scope)
        self._obligations = {}
        for obligation in obligations:
            validate_obligation(obligation)
            self._obligations[obligation["obligation_id"]] = copy.deepcopy(obligation)
        self._observations = {}
        for observation in observations:
            validate_observation(observation)
            self._observations[observation["event_id"]] = copy.deepcopy(observation)

    def emit(self, truth):
        truth = copy.deepcopy(truth)
        validate_controlled_truth(truth)
        if truth["episode_id"] != self._scope["episode_id"]:
            _fail("CONTROLLED_TRUTH_EPISODE", "$.episode_id", "scope mismatch")
        if truth["scope_contract_id"] != self._scope["scope_contract_id"]:
            _fail("CONTROLLED_TRUTH_SCOPE", "$.scope_contract_id", "scope mismatch")
        if truth["scope_version"] != self._scope["provenance"]["version"]:
            _fail("CONTROLLED_TRUTH_SCOPE_VERSION", "$.scope_version", "scope mismatch")
        if truth["scope_digest"] != canonical_sha256(self._scope):
            _fail("CONTROLLED_TRUTH_SCOPE_DIGEST", "$.scope_digest", "scope mismatch")
        if sorted(truth["hypothesis_ids"]) != sorted(self._scope["hypothesis_ids"]):
            _fail("CONTROLLED_TRUTH_UNIVERSE", "$.hypothesis_ids", "scope universe mismatch")
        values = []
        for index, claim in enumerate(truth["claims"]):
            obligation = self._obligations.get(claim["obligation_id"])
            observation = self._observations.get(claim["source_event_id"])
            if obligation is None:
                _fail("CONTROLLED_TRUTH_OBLIGATION", "$.claims[%d]" % index, "unknown obligation")
            if observation is None:
                _fail("CONTROLLED_TRUTH_EVENT", "$.claims[%d]" % index, "unknown observation")
            identity = {
                "truth_digest": truth["audit_trail"]["source_artifact_digest"],
                "claim_index": index,
                "obligation_id": claim["obligation_id"],
                "claim": claim["claim"],
                "source_event_id": claim["source_event_id"],
            }
            values.append({
                "schema_version": SCHEMA_VERSIONS["evidence"],
                "evidence_id": "controlled-" + canonical_sha256(identity)[:20],
                "episode_id": observation["episode_id"],
                "source": "observation",
                "source_event_id": observation["event_id"],
                "event_seq": observation["event_seq"],
                "step": observation["step"],
                "scan": observation["scan"],
                "viewpoint": observation["viewpoint"],
                "view_index": observation["view_index"],
                "evidence_role": claim["evidence_role"],
                "unit_id": claim["unit_id"],
                "scope_contract_id": self._scope["scope_contract_id"],
                "obligation_id": obligation["obligation_id"],
                "predicate_id": obligation["predicate_id"],
                "claim": claim["claim"],
                "adapter_version": "proofnav.controlled-oracle.replay.v1",
                "dependency_group": "controlled-replay:%s" % observation["event_id"],
                "audit_trail": {
                    "producer": "proofnav.offline.OracleEvidenceProvider",
                    "source_field": "claims[%d]" % index,
                },
            })
        return values


class ReplayOnlineVerifier(_OnlineVerifierCore):
    """Offline replay of the online semantics with controlled source admission."""

    def __init__(self):
        super().__init__(allow_controlled=True)


class ReplayTerminalController(_TerminalControllerCore):
    """Offline-only closed-loop controller used by M2 counterexample tests."""

    def __init__(self):
        super().__init__(ReplayOnlineVerifier())
