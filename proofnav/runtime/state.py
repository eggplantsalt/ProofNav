"""Sequential, event-sourced M2.1 proof state.

The state owns its observation cut, dynamic hypothesis universe, evidence
ledger, frontier, resource counters, and costs.  Callers may only append typed
transitions; they cannot inject a precomputed snapshot or a closure boolean.
Every proposed transition is folded by :func:`recompute_view` before it is
committed, so a failed transition leaves the state unchanged.
"""

import copy

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.runtime.semantics import (
    make_transition, recompute_view, registered_admission_profile,
)


_PRODUCTION_PROFILE_ID = "proofnav.admission.production-zero.v2"
_CONTROLLED_PROFILE_ID = "proofnav.admission.controlled-replay.v2"


def _copy(value):
    return copy.deepcopy(value)


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _production_admission_profile(scope):
    """Return the only code-owned production admission profile for M2.1."""

    del scope
    return registered_admission_profile(False)


def _controlled_admission_profile(scope):
    """Return the exact offline replay profile; it is not runtime-configurable."""

    del scope
    return registered_admission_profile(True)


def _validate_code_owned_profile(scope, profile):
    expected = (
        _controlled_admission_profile(scope)
        if profile.get("profile_id") == _CONTROLLED_PROFILE_ID
        else _production_admission_profile(scope)
    )
    if profile != expected:
        _fail(
            "ADMISSION_PROFILE_NOT_CODE_OWNED", "$.admission_profile",
            "profile must exactly match a registered M2.1 code-owned profile",
        )
    return expected


class EvidenceLedger(object):
    """Read-only compatibility view over evidence/revocation transitions.

    Mutation belongs to :class:`ProofState`, because an evidence event also
    changes the decision cut, resource view, and proof-state digest.  Keeping a
    separately mutable ledger would recreate the split-state bug M2.1 repairs.
    """

    def __init__(self, owner):
        self._owner = owner

    def append(self, evidence):
        del evidence
        _fail(
            "LEDGER_MUTATION_FORBIDDEN", "$.ledger.append",
            "use ProofState.append_evidence(bound_evidence)",
        )

    def revoke(self, evidence_id, reason):
        del evidence_id, reason
        _fail(
            "LEDGER_MUTATION_FORBIDDEN", "$.ledger.revoke",
            "use ProofState.revoke_evidence(evidence_id, reason)",
        )

    def active_evidence(self):
        """Return M1 evidence records nested in active bound-evidence events."""

        return [
            _copy(item["evidence"])
            for item in self._owner.snapshot()["active_bound_evidence"]
        ]

    def audit_log(self):
        """Return a stable ledger-only projection of the transition chain."""

        events = []
        previous_digest = "0" * 64
        for transition in self._owner._transitions:
            if transition["event_type"] not in (
                    "IDENTITY_LINK", "EVIDENCE", "REVOKE"):
                continue
            if transition["event_type"] == "IDENTITY_LINK":
                witness = transition["payload"]
                evidence_id = witness["witness_id"]
                evidence_digest = canonical_sha256(witness)
                reason = None
                event_type = "IDENTITY_LINK"
            elif transition["event_type"] == "EVIDENCE":
                bound = transition["payload"]
                evidence_id = bound["evidence"]["evidence_id"]
                evidence_digest = canonical_sha256(bound)
                reason = None
                event_type = "APPEND"
            else:
                evidence_id = transition["payload"]["evidence_id"]
                evidence_digest = None
                reason = transition["payload"]["reason"]
                event_type = "REVOKE"
            record = {
                "sequence": len(events),
                "event_type": event_type,
                "evidence_id": evidence_id,
                "evidence_digest": evidence_digest,
                "previous_digest": previous_digest,
                "reason": reason,
                "source_transition_seq": transition["transition_seq"],
                "source_transition_digest": transition["transition_digest"],
            }
            record["entry_digest"] = canonical_sha256(record)
            previous_digest = record["entry_digest"]
            events.append(record)
        return events

    @property
    def event_count(self):
        return self._owner.snapshot()["ledger_event_count"]

    @property
    def semantic_digest(self):
        return self._owner.snapshot()["ledger_digest"]


# Kept as an import-compatible name while offline replay migrates to the
# event-sourced core.  It intentionally has no independent mutation semantics.
_BaseEvidenceLedger = EvidenceLedger


class _ProofStateCore(object):
    """Event-sourced core shared by production and offline controlled replay."""

    def __init__(self, scope, template, risk_claims, admission_profile):
        self._scope = _copy(scope)
        self._template = _copy(template)
        self._risk_claims = _copy(risk_claims)
        self._admission_profile = _validate_code_owned_profile(
            self._scope, _copy(admission_profile),
        )
        self._allow_controlled = (
            self._admission_profile["evidence_mode"] == "controlled_replay"
        )
        self._transitions = []
        # This validates scope, template, risk claims, and the exact profile
        # before the object becomes externally usable.
        self._view = recompute_view(self._base_bundle(), self._allow_controlled)
        self._ledger_view = EvidenceLedger(self)

    def _base_bundle(self, transitions=None):
        return {
            "schema_version": SCHEMA_VERSIONS["audit_bundle"],
            "scope": _copy(self._scope),
            "template": _copy(self._template),
            "admission_profile": _copy(self._admission_profile),
            "risk_claims": _copy(self._risk_claims),
            "transitions": _copy(
                self._transitions if transitions is None else transitions
            ),
        }

    def _commit(self, event_type, payload):
        """Validate a candidate transition against the full fold, then commit."""

        candidate = _copy(self._transitions)
        transition = make_transition(candidate, event_type, _copy(payload))
        candidate.append(transition)
        candidate_view = recompute_view(
            self._base_bundle(candidate), self._allow_controlled,
        )
        self._transitions = candidate
        self._view = candidate_view
        return _copy(transition)

    @property
    def ledger(self):
        return self._ledger_view

    def ingest_observation(self, observation):
        """Admit one next observation and derive topology/universe from it."""

        transition = self._commit("OBSERVATION", observation)
        return _copy(transition["payload"])

    def link_identity(self, identity_witness):
        """Admit a typed controlled witness linking two observed slots.

        Earlier query/evidence events remain immutable audit records, but their
        pre-link obligation IDs no longer resolve in the new universe.  This
        gives sequential replay a safe way to discover cross-view identity:
        the universe changes, every old certificate becomes stale, and fresh
        queries are required for the merged subject.
        """

        if not isinstance(identity_witness, dict):
            _fail("TYPE_MAPPING", "$.identity_witness", "expected an object")
        self._commit("IDENTITY_LINK", identity_witness)
        return _copy(identity_witness)

    def register_query(self, hypothesis_id, obligation_id):
        """Register the canonical query for one current dynamic obligation."""

        snapshot = self.snapshot()
        obligation = next((
            item for item in snapshot["obligations"]
            if item["obligation_id"] == obligation_id
            and item["hypothesis_id"] == hypothesis_id
        ), None)
        if obligation is None:
            _fail(
                "QUERY_OBLIGATION", "$.obligation_id",
                "no current obligation matches the hypothesis and obligation IDs",
            )
        identity = {
            "hypothesis_id": obligation["hypothesis_id"],
            "obligation_id": obligation["obligation_id"],
            "predicate_id": obligation["predicate_id"],
            "predicate_kind": obligation["predicate_kind"],
            "binding": _copy(obligation["binding_requirement"]),
        }
        payload = dict(identity)
        payload["query_id"] = "query-" + canonical_sha256(identity)[:24]
        self._commit("QUERY", payload)
        return _copy(payload)

    def append_evidence(self, bound_evidence):
        """Admit one query-bound evidence wrapper at the current causal cut."""

        transition = self._commit("EVIDENCE", bound_evidence)
        return _copy(transition["payload"])

    def revoke_evidence(self, evidence_id, reason):
        """Append an auditable revocation; prior transitions remain immutable."""

        payload = {"evidence_id": evidence_id, "reason": reason}
        self._commit("REVOKE", payload)
        return _copy(payload)

    def record_continue(self, terminal_decision):
        """Record a verified rejection/defer before the next observation.

        The terminal record is bound to the *prior* decision cut.  Appending the
        CONTINUE transition necessarily creates a new state digest, after which
        controlled replay can ingest the next observation.
        """

        if not isinstance(terminal_decision, dict):
            _fail("TYPE_MAPPING", "$.terminal_decision", "expected an object")
        terminal = _copy(terminal_decision)
        if terminal.get("directive") != "CONTINUE_SEARCH" or terminal.get("terminal") is not False:
            _fail(
                "CONTINUE_TERMINAL_STATE", "$.terminal_decision.directive",
                "only a non-terminal CONTINUE_SEARCH decision may be recorded",
            )
        online = terminal.get("online_verification")
        if not isinstance(online, dict) or online.get("status") not in ("REJECT", "DEFER"):
            _fail(
                "CONTINUE_VERIFICATION", "$.terminal_decision.online_verification.status",
                "CONTINUE requires a rejected or deferred online verification",
            )
        snapshot = self.snapshot()
        if terminal.get("proof_state_digest") != snapshot["proof_state_digest"]:
            _fail(
                "CONTINUE_STATE_DIGEST", "$.terminal_decision.proof_state_digest",
                "terminal does not bind the current proof state",
            )
        if terminal.get("decision_cut") != snapshot["decision_cut"]:
            _fail(
                "CONTINUE_DECISION_CUT", "$.terminal_decision.decision_cut",
                "terminal does not bind the current causal cut",
            )
        proposed_digest = terminal.get("proposed_certificate_digest")
        online_digest = online.get("certificate_digest")
        if proposed_digest != online_digest:
            _fail(
                "CONTINUE_CERTIFICATE_IDENTITY", "$.terminal_decision.proposed_certificate_digest",
                "terminal proposal and verifier certificate digests differ",
            )
        terminal_digest = canonical_sha256(terminal)
        payload = {
            "terminal_decision": terminal,
            "terminal_digest": terminal_digest,
            "proof_state_digest": snapshot["proof_state_digest"],
            "rejected_certificate_digest": proposed_digest,
        }
        self._commit("CONTINUE", payload)
        return _copy(payload)

    def snapshot(self):
        """Return the current canonical semantic view."""

        # Every mutation is transactionally re-folded before `_view` is
        # committed, and no internal reference is exposed.  Returning a deep
        # copy keeps reads O(size) instead of revalidating the entire history;
        # certificate/verifier/offline trust boundaries still re-fold raw
        # transitions independently.
        return _copy(self._view)

    def audit_bundle(self):
        """Return the self-contained v2 decision audit artifact."""

        bundle = self._base_bundle()
        bundle["state"] = self.snapshot()
        bundle["bundle_digest"] = canonical_sha256(bundle)
        return bundle


class ProofState(_ProofStateCore):
    """Production M2.1 state with non-configurable zero evidence admission."""

    def __init__(self, scope, template, risk_claims):
        super().__init__(
            scope, template, risk_claims,
            _production_admission_profile(scope),
        )
