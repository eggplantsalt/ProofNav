"""M2 hypothesis state, evidence ledger, and auditable proof snapshots."""

import copy
import math

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.validation import (
    assert_agent_visible,
    validate_evidence,
    validate_obligation,
    validate_observation,
    validate_scope,
)


RESOLUTION_STATES = frozenset(("OPEN", "SATISFIED", "REFUTED", "CONFLICTED"))
_CONTROLLED_TOKENS = (
    "oracle", "fixture", "ground_truth", "evaluator", "controlled_truth",
)


def _violation(code, location, message):
    raise ContractViolation(code, location, message)


def _copy(value):
    return copy.deepcopy(value)


def _require_exact_mapping(value, fields, location, code="M2_UNKNOWN_FIELDS"):
    if not isinstance(value, dict):
        _violation("TYPE_MAPPING", location, "expected an object")
    missing = sorted(set(fields) - set(value))
    if missing:
        _violation("M2_MISSING_FIELDS", location, "missing %s" % missing)
    unknown = sorted(set(value) - set(fields))
    if unknown:
        _violation(code, location, "unknown fields %s" % unknown)
    return value


def _validate_frontier(witnesses, observations):
    if not isinstance(witnesses, list):
        _violation("TYPE_LIST", "$.frontier_witnesses", "expected an array")
    seen = set()
    normalized = []
    fields = ("frontier_id", "viewpoint_id", "source_event_id", "kind")
    for index, witness in enumerate(witnesses):
        location = "$.frontier_witnesses[%d]" % index
        witness = _require_exact_mapping(witness, fields, location)
        for key in ("frontier_id", "viewpoint_id", "source_event_id"):
            if not isinstance(witness[key], str) or not witness[key]:
                _violation("TYPE_STRING", location + "." + key, "expected a non-empty string")
        if witness["kind"] != "graph_frontier":
            _violation("FRONTIER_KIND", location + ".kind", "expected graph_frontier")
        if witness["frontier_id"] in seen:
            _violation("FRONTIER_DUPLICATE", location + ".frontier_id", "duplicate ID")
        if witness["source_event_id"] not in observations:
            _violation("FRONTIER_EVENT_MISSING", location + ".source_event_id", "unknown observation")
        seen.add(witness["frontier_id"])
        normalized.append(_copy(witness))
    return sorted(normalized, key=lambda item: item["frontier_id"])


def _validate_budget_status(value, scope):
    fields = (
        "steps_used", "observation_events", "predicate_queries",
        "within_budget", "exhausted_resources",
    )
    value = _require_exact_mapping(value, fields, "$.budget_status")
    limits = scope["resource_limits"]
    used_to_limit = {
        "steps_used": "max_steps",
        "observation_events": "max_observation_events",
        "predicate_queries": "max_predicate_queries",
    }
    exhausted = []
    for used_key, limit_key in used_to_limit.items():
        used = value[used_key]
        if isinstance(used, bool) or not isinstance(used, int) or used < 0:
            _violation("TYPE_INTEGER", "$.budget_status." + used_key, "expected non-negative integer")
        if used >= limits[limit_key]:
            exhausted.append(used_key)
    if not isinstance(value["within_budget"], bool):
        _violation("TYPE_BOOLEAN", "$.budget_status.within_budget", "expected boolean")
    if not isinstance(value["exhausted_resources"], list):
        _violation("TYPE_LIST", "$.budget_status.exhausted_resources", "expected array")
    if len(value["exhausted_resources"]) != len(set(value["exhausted_resources"])):
        _violation("BUDGET_DUPLICATE", "$.budget_status.exhausted_resources", "duplicate resource")
    valid_resources = set(used_to_limit)
    if not set(value["exhausted_resources"]).issubset(valid_resources):
        _violation("BUDGET_RESOURCE", "$.budget_status.exhausted_resources", "unknown resource")
    expected_within = not exhausted
    if value["within_budget"] != expected_within:
        _violation("BUDGET_STATUS", "$.budget_status.within_budget", "does not match resource counters")
    if set(value["exhausted_resources"]) != set(exhausted):
        _violation("BUDGET_STATUS", "$.budget_status.exhausted_resources", "does not match resource counters")
    normalized = _copy(value)
    normalized["exhausted_resources"] = sorted(normalized["exhausted_resources"])
    return normalized


def _validate_cost_ledger(value):
    fields = (
        "travel_distance_meters", "high_level_actions", "expanded_path_edges",
        "observation_events", "predicate_queries", "online_compute_milliseconds",
        "storage_bytes", "offline_preprocessing_ref",
    )
    value = _require_exact_mapping(value, fields, "$.cost_ledger")
    real_fields = ("travel_distance_meters", "online_compute_milliseconds")
    integer_fields = (
        "high_level_actions", "expanded_path_edges", "observation_events",
        "predicate_queries", "storage_bytes",
    )
    for key in real_fields:
        item = value[key]
        if (isinstance(item, bool) or not isinstance(item, (int, float))
                or not math.isfinite(item) or item < 0):
            _violation("COST_VALUE", "$.cost_ledger." + key, "expected non-negative number")
    for key in integer_fields:
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            _violation("COST_VALUE", "$.cost_ledger." + key, "expected non-negative integer")
    if not isinstance(value["offline_preprocessing_ref"], str) or not value["offline_preprocessing_ref"]:
        _violation("TYPE_STRING", "$.cost_ledger.offline_preprocessing_ref", "expected a non-empty string")
    return _copy(value)


def _validate_risk_claim(value, decision, scope):
    fields = (
        "decision", "risk_type", "upper_bound", "budget",
        "calibration_version", "composition_version",
    )
    value = _require_exact_mapping(value, fields, "$.risk_claims.%s" % decision)
    expected_type = "false_found" if decision == "FOUND" else "false_not_found"
    if value["decision"] != decision:
        _violation("RISK_DECISION", "$.risk_claims.%s.decision" % decision, "decision mismatch")
    if value["risk_type"] != expected_type:
        _violation("RISK_TYPE", "$.risk_claims.%s.risk_type" % decision, "risk type mismatch")
    for key in ("upper_bound", "budget"):
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not 0 <= number <= 1:
            _violation("RISK_RANGE", "$.risk_claims.%s.%s" % (decision, key), "expected [0,1]")
    expected_budget = scope["risk_budgets"][expected_type]
    if value["budget"] != expected_budget:
        _violation("RISK_BUDGET", "$.risk_claims.%s.budget" % decision, "scope budget mismatch")
    if value["calibration_version"] != scope["calibration_version"]:
        _violation("RISK_CALIBRATION", "$.risk_claims.%s.calibration_version" % decision, "scope calibration mismatch")
    if not isinstance(value["composition_version"], str) or not value["composition_version"]:
        _violation("TYPE_STRING", "$.risk_claims.%s.composition_version" % decision, "expected string")
    return _copy(value)


class _BaseEvidenceLedger(object):
    """Append-only evidence/revocation events plus order-invariant semantic digest."""

    def __init__(self, episode_id, scope_contract_id, scope_version,
                 scope_digest, observations, obligations):
        self._episode_id = episode_id
        self._scope_contract_id = scope_contract_id
        self._scope_version = scope_version
        self._scope_digest = scope_digest
        self._observations = observations
        self._obligations = obligations
        self._evidence = {}
        self._revoked = set()
        self._semantic_fingerprints = {}
        self._events = []
        self._chain_tip = "0" * 64

    def _admit_adapter(self, evidence):
        raise NotImplementedError

    @staticmethod
    def _semantic_fingerprint(evidence):
        value = _copy(evidence)
        value.pop("evidence_id", None)
        return canonical_sha256(value)

    def append(self, evidence):
        evidence = _copy(evidence)
        validate_evidence(evidence, self._observations)
        if evidence["episode_id"] != self._episode_id:
            _violation("EVIDENCE_EPISODE", "$.episode_id", "state episode mismatch")
        if evidence["scope_contract_id"] != self._scope_contract_id:
            _violation("EVIDENCE_SCOPE", "$.scope_contract_id", "state scope mismatch")
        obligation = self._obligations.get(evidence["obligation_id"])
        if obligation is None:
            _violation("EVIDENCE_OBLIGATION", "$.obligation_id", "unknown obligation")
        if evidence["predicate_id"] != obligation["predicate_id"]:
            _violation("EVIDENCE_PREDICATE", "$.predicate_id", "obligation predicate mismatch")
        self._admit_adapter(evidence)
        evidence_id = evidence["evidence_id"]
        if evidence_id in self._evidence:
            _violation("EVIDENCE_DUPLICATE_ID", "$.evidence_id", "already recorded")
        fingerprint = self._semantic_fingerprint(evidence)
        if fingerprint in self._semantic_fingerprints:
            _violation("EVIDENCE_DUPLICATE_SEMANTIC", "$.evidence_id", "semantic duplicate")
        self._evidence[evidence_id] = evidence
        self._semantic_fingerprints[fingerprint] = evidence_id
        self._record("APPEND", evidence_id, canonical_sha256(evidence), None)
        return _copy(evidence)

    def revoke(self, evidence_id, reason):
        if not isinstance(reason, str) or not reason:
            _violation("TYPE_STRING", "$.reason", "expected non-empty audit reason")
        if evidence_id not in self._evidence:
            _violation("EVIDENCE_UNKNOWN", "$.evidence_id", "cannot revoke unknown evidence")
        if evidence_id in self._revoked:
            _violation("EVIDENCE_ALREADY_REVOKED", "$.evidence_id", "already revoked")
        self._revoked.add(evidence_id)
        self._record("REVOKE", evidence_id, canonical_sha256(self._evidence[evidence_id]), reason)

    def _record(self, event_type, evidence_id, evidence_digest, reason):
        payload = {
            "sequence": len(self._events),
            "event_type": event_type,
            "evidence_id": evidence_id,
            "evidence_digest": evidence_digest,
            "previous_digest": self._chain_tip,
            "reason": reason,
            "admission_scope_version": self._scope_version,
            "admission_scope_digest": self._scope_digest,
        }
        payload["entry_digest"] = canonical_sha256(payload)
        self._chain_tip = payload["entry_digest"]
        self._events.append(payload)

    def active_evidence(self):
        return [
            _copy(self._evidence[key])
            for key in sorted(self._evidence)
            if key not in self._revoked
        ]

    def audit_log(self):
        return _copy(self._events)

    @property
    def event_count(self):
        return len(self._events)

    @property
    def semantic_digest(self):
        return canonical_sha256({
            "schema_version": SCHEMA_VERSIONS["ledger"],
            "scope_contract_id": self._scope_contract_id,
            "scope_version": self._scope_version,
            "scope_digest": self._scope_digest,
            "active": self.active_evidence(),
            "revoked": sorted(self._revoked),
        })

    @property
    def audit_chain_tip(self):
        return self._chain_tip


class EvidenceLedger(_BaseEvidenceLedger):
    """M2 production admission is deliberately closed until M3 registers code."""

    def _admit_adapter(self, evidence):
        values = (
            evidence["adapter_version"], evidence["dependency_group"],
            evidence["audit_trail"]["producer"],
            evidence["audit_trail"]["source_field"],
        )
        lowered = " ".join(values).lower()
        if any(token in lowered for token in _CONTROLLED_TOKENS):
            _violation("CONTROLLED_EVIDENCE_FORBIDDEN", "$.adapter_version", "offline/replay source")
        # A string prefix or config allowlist can be forged by an oracle fixture.
        # M2 has no real perception adapter, so the only sound production policy
        # is zero admission.  M3 must add a code-owned adapter boundary and bump
        # the admission version before production evidence can close a proof.
        _violation(
            "EVIDENCE_ADAPTER_NOT_REGISTERED", "$.adapter_version",
            "M2 production admission is sealed until a code-owned M3 adapter exists",
        )


class _ProofStateCore(object):

    def __init__(self, scope, obligations, observations, frontier_witnesses,
                 scope_closed, budget_status, cost_ledger, risk_claims,
                 ledger_class):
        scope = _copy(scope)
        validate_scope(scope)
        assert_agent_visible(scope)
        self._scope = scope
        self._scope_digest = canonical_sha256(scope)
        self._scope_version = scope["provenance"]["version"]
        self._observations = {}
        for observation in observations:
            observation = _copy(observation)
            validate_observation(observation)
            if observation["episode_id"] != scope["episode_id"]:
                _violation("OBSERVATION_EPISODE", "$.observations", "scope episode mismatch")
            event_id = observation["event_id"]
            if event_id in self._observations:
                _violation("OBSERVATION_DUPLICATE", "$.observations", "duplicate event ID")
            self._observations[event_id] = observation
        self._obligations = {}
        hypothesis_counts = {hypothesis: 0 for hypothesis in scope["hypothesis_ids"]}
        for obligation in obligations:
            obligation = _copy(obligation)
            validate_obligation(obligation)
            if obligation["episode_id"] != scope["episode_id"]:
                _violation("OBLIGATION_EPISODE", "$.obligations", "scope episode mismatch")
            if obligation["scope_contract_id"] != scope["scope_contract_id"]:
                _violation("OBLIGATION_SCOPE", "$.obligations", "scope ID mismatch")
            if obligation["hypothesis_id"] not in hypothesis_counts:
                _violation("OBLIGATION_HYPOTHESIS", "$.obligations", "hypothesis is out of scope")
            if obligation["status"] != "OPEN" or obligation["evidence_ids"]:
                _violation("M2_OBLIGATION_SEED", "$.obligations", "M2 derives state from an OPEN seed")
            obligation_id = obligation["obligation_id"]
            if obligation_id in self._obligations:
                _violation("OBLIGATION_DUPLICATE", "$.obligations", "duplicate obligation ID")
            self._obligations[obligation_id] = obligation
            if obligation["necessary"]:
                hypothesis_counts[obligation["hypothesis_id"]] += 1
        missing = sorted(key for key, count in hypothesis_counts.items() if count == 0)
        if missing:
            _violation("HYPOTHESIS_WITHOUT_OBLIGATION", "$.obligations", "missing necessary obligations %s" % missing)
        if not isinstance(scope_closed, bool):
            _violation("TYPE_BOOLEAN", "$.scope_closed", "expected boolean")
        self._scope_closed = scope_closed
        self._frontier = _validate_frontier(frontier_witnesses, self._observations)
        if scope_closed and self._frontier:
            _violation("SCOPE_CLOSED_WITH_FRONTIER", "$.frontier_witnesses", "closed scope has open frontier")
        self._budget_status = _validate_budget_status(budget_status, scope)
        self._cost_ledger = _validate_cost_ledger(cost_ledger)
        if not isinstance(risk_claims, dict) or not set(risk_claims).issubset({"FOUND", "NOT_FOUND"}):
            _violation("RISK_CLAIMS", "$.risk_claims", "only FOUND/NOT_FOUND keys are allowed")
        self._risk_claims = {
            decision: _validate_risk_claim(claim, decision, scope)
            for decision, claim in risk_claims.items()
        }
        self._ledger = ledger_class(
            scope["episode_id"], scope["scope_contract_id"],
            self._scope_version, self._scope_digest,
            self._observations, self._obligations,
        )
        self._version = 0

    @property
    def ledger(self):
        return self._ledger

    def append_evidence(self, evidence):
        value = self._ledger.append(evidence)
        self._version += 1
        return value

    def revoke_evidence(self, evidence_id, reason):
        self._ledger.revoke(evidence_id, reason)
        self._version += 1

    def _resolutions(self):
        supports = {key: [] for key in self._obligations}
        refutes = {key: [] for key in self._obligations}
        for item in self._ledger.active_evidence():
            target = supports if item["claim"] == "SUPPORTS" else refutes
            target[item["obligation_id"]].append(item["evidence_id"])
        values = []
        for obligation_id in sorted(self._obligations):
            obligation = self._obligations[obligation_id]
            support_ids = sorted(supports[obligation_id])
            refute_ids = sorted(refutes[obligation_id])
            if support_ids and refute_ids:
                status = "CONFLICTED"
            elif support_ids:
                status = "SATISFIED"
            elif refute_ids:
                status = "REFUTED"
            else:
                status = "OPEN"
            values.append({
                "obligation_id": obligation_id,
                "hypothesis_id": obligation["hypothesis_id"],
                "predicate_id": obligation["predicate_id"],
                "necessary": obligation["necessary"],
                "status": status,
                "support_evidence_ids": support_ids,
                "refutation_evidence_ids": refute_ids,
            })
        return values

    def snapshot(self):
        payload = {
            "schema_version": SCHEMA_VERSIONS["proof_state"],
            "episode_id": self._scope["episode_id"],
            "scope_contract_id": self._scope["scope_contract_id"],
            "scope_version": self._scope_version,
            "scope_digest": self._scope_digest,
            "state_version": self._version,
            "hypothesis_ids": sorted(self._scope["hypothesis_ids"]),
            "obligations": self._resolutions(),
            "active_evidence": self._ledger.active_evidence(),
            "ledger_digest": self._ledger.semantic_digest,
            "scope_closed": self._scope_closed,
            "frontier_witnesses": _copy(self._frontier),
            "budget_status": _copy(self._budget_status),
            "cost_ledger": _copy(self._cost_ledger),
            "risk_claims": _copy(self._risk_claims),
            "observation_event_ids": sorted(self._observations),
            "ledger_event_count": self._ledger.event_count,
        }
        payload["proof_state_digest"] = canonical_sha256(payload)
        payload["audit_trail"] = {
            "producer": "proofnav.runtime.state",
            "ledger_schema_version": SCHEMA_VERSIONS["ledger"],
            "ledger_event_count": self._ledger.event_count,
            "ledger_audit_chain_tip": self._ledger.audit_chain_tip,
            "scope_provenance": _copy(self._scope["provenance"]),
        }
        return payload


class ProofState(_ProofStateCore):
    """Production proof state with fail-closed evidence admission."""

    def __init__(self, scope, obligations, observations, frontier_witnesses,
                 scope_closed, budget_status, cost_ledger, risk_claims):
        super().__init__(
            scope, obligations, observations, frontier_witnesses, scope_closed,
            budget_status, cost_ledger, risk_claims, EvidenceLedger,
        )
