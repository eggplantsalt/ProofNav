"""Versioned constants and small primitives shared by the M1 contracts."""

import hashlib
import json


SCHEMA_VERSIONS = {
    "observation": "proofnav.observation.v1",
    "action": "proofnav.action.v1",
    "evidence": "proofnav.evidence.v1",
    "scope": "proofnav.scope.v1",
    "obligation": "proofnav.obligation.v1",
    "certificate": "proofnav.certificate.v1",
    "result": "proofnav.result.v1",
    "pair": "proofnav.paired.v1",
    "reference_check": "proofnav.reference-check.v1",
    "evaluation": "proofnav.evaluation.v1",
    # M2 extends the frozen M1 wire contracts; it does not mutate their v1
    # field sets.  M2 artifacts use separate, explicit versions.
    "proof_state": "proofnav.proof-state.v1",
    "ledger": "proofnav.evidence-ledger.v1",
    "m2_certificate": "proofnav.certificate.v2",
    "online_verification": "proofnav.online-verification.v1",
    "terminal_decision": "proofnav.terminal-decision.v1",
    "controlled_truth": "proofnav.controlled-truth.v1",
    "offline_verification": "proofnav.offline-verification.v1",
}

SEMANTIC_DECISIONS = frozenset(("FOUND", "NOT_FOUND"))
DECISION_STATUSES = frozenset(("VERIFIED", "UNRESOLVED"))
SEMANTIC_VERDICTS = frozenset(("FOUND", "NOT_FOUND", "UNRESOLVED"))

ACTION_BRANCHES = frozenset(("local", "global", "fused"))
EVIDENCE_SOURCES = frozenset(("observation",))
EVIDENCE_ROLES = frozenset(("viewpoint_view", "object_slot"))
EVIDENCE_CLAIMS = frozenset(("SUPPORTS", "REFUTES"))

OBLIGATION_STATUSES = frozenset(("OPEN", "SUPPORTED", "REFUTED"))
PREMISE_CLASSES = frozenset((
    "entity_absent",
    "attribute_mismatch",
    "relation_mismatch",
    "room_anchor_mismatch",
))
PREMISE_CLASS_TO_PREDICATE_KIND = {
    "entity_absent": "entity",
    "attribute_mismatch": "attribute",
    "relation_mismatch": "relation",
    "room_anchor_mismatch": "room_anchor",
}

TERMINATION_CAUSES = frozenset((
    "verifier_accept",
    "duet_stop",
    "no_frontier",
    "max_step",
    "budget",
    "verifier_reject",
    "error",
))

# Exact runtime/evaluator truth names.  Substrings are intentionally kept
# narrow: legitimate M1 fields such as travel_distance_meters must remain
# available to the cost ledger.
FORBIDDEN_AGENT_KEYS = frozenset((
    "gt_path",
    "gt_end_vps",
    "gt_obj_id",
    "obj2vps",
    "graphs",
    "shortest_paths",
    "shortest_distances",
    "bboxes",
    "evaluator_truth",
    "semantic_truth",
    "truth_source",
    "ground_truth",
    "target_label",
))

FORBIDDEN_RUNTIME_EVENT_TYPES = frozenset((
    "evaluation",
    "evaluator",
    "metrics",
    "ground_truth",
))


class ContractViolation(ValueError):
    """A machine-readable contract error raised before any method logic runs."""

    def __init__(self, code, location, message):
        self.code = str(code)
        self.location = str(location)
        self.message = str(message)
        super().__init__("%s at %s: %s" % (self.code, self.location, self.message))


def canonical_json(value):
    """Return a stable JSON representation for audit fingerprints."""

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def semantic_verdict(result):
    """Collapse the two-field result representation into its total 3-state value."""

    status = result.get("decision_status")
    decision = result.get("semantic_decision")
    if status == "UNRESOLVED" and decision is None:
        return "UNRESOLVED"
    if status == "VERIFIED" and decision in SEMANTIC_DECISIONS:
        return decision
    raise ContractViolation(
        "RESULT_DECISION_STATE",
        "$.decision_status",
        "expected VERIFIED+FOUND/NOT_FOUND or UNRESOLVED+null",
    )
