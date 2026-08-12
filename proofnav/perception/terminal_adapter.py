"""Fail-closed M3-B admission over an explicit DUET action cut.

The current registered artifact is descriptive only, so this successor never
emits ledger evidence.  It nevertheless executes the full code-owned timing,
instruction-domain, base-adapter, and statistical gates and records the first
reason that prevents authoritative SUPPORT.
"""

import copy

from proofnav.contracts import canonical_sha256

from .evidence_adapter import adapt_entity_signal
from .grounding_scope import classify_entity_only_instruction
from .terminal_signal import validate_terminal_signal


TERMINAL_ADMISSION_SCHEMA_VERSION = "proofnav.terminal-evidence-admission.v1"
_FIELDS = frozenset((
    "schema_version", "decision", "reason_code", "terminal_signal_digest",
    "base_signal_digest", "grounding_scope", "base_adapter_decision",
    "admission_digest",
))


def _seal(terminal_signal, grounding_scope, reason, base_decision=None):
    result = {
        "schema_version": TERMINAL_ADMISSION_SCHEMA_VERSION,
        "decision": "ABSTAIN",
        "reason_code": reason,
        "terminal_signal_digest": terminal_signal["terminal_signal_digest"],
        "base_signal_digest": terminal_signal["base_signal"]["signal_digest"],
        "grounding_scope": copy.deepcopy(grounding_scope),
        "base_adapter_decision": copy.deepcopy(base_decision),
    }
    result["admission_digest"] = canonical_sha256(result)
    return validate_terminal_admission(result)


def validate_terminal_admission(value):
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("exact terminal-admission schema required")
    if (value["schema_version"] != TERMINAL_ADMISSION_SCHEMA_VERSION
            or value["decision"] != "ABSTAIN"):
        raise ValueError("M3-B v1 is fail-closed ABSTAIN only")
    allowed = {
        "NON_TERMINAL_EVIDENCE", "FORCED_END_IS_NOT_EVIDENCE",
        "UNSUPPORTED_TYPED_GROUNDING", "STATISTICAL_RISK_UNAVAILABLE",
        "BASE_ADAPTER_ABSTAIN",
    }
    if value["reason_code"] not in allowed:
        raise ValueError("unknown terminal admission reason")
    sealed = copy.deepcopy(value)
    digest = sealed.pop("admission_digest")
    if digest != canonical_sha256(sealed):
        raise ValueError("terminal admission changed")
    return value


def adapt_terminal_entity_signal(query, terminal_signal, artifact=None):
    terminal_signal = validate_terminal_signal(terminal_signal)
    observation = terminal_signal["base_signal"]["observation"]
    grounding = classify_entity_only_instruction(observation["instruction"])
    decision = terminal_signal["decision_context"]
    if decision["evidence_eligibility"] == "SEARCH_PROPOSAL":
        return _seal(
            terminal_signal, grounding, "NON_TERMINAL_EVIDENCE",
        )
    if decision["evidence_eligibility"] == "FORCED_END_ABSTAIN":
        return _seal(
            terminal_signal, grounding, "FORCED_END_IS_NOT_EVIDENCE",
        )
    if not grounding["entity_only_eligible"]:
        return _seal(
            terminal_signal, grounding, "UNSUPPORTED_TYPED_GROUNDING",
        )
    base = adapt_entity_signal(query, terminal_signal["base_signal"], artifact)
    if base["decision"] != "SUPPORTS":
        return _seal(
            terminal_signal, grounding, "BASE_ADAPTER_ABSTAIN", base,
        )
    risk = artifact["risk_bound"]
    if (risk["confidence"] is None
            or risk["semantics"]
            == "descriptive_compatibility_not_statistical_guarantee"):
        return _seal(
            terminal_signal, grounding, "STATISTICAL_RISK_UNAVAILABLE", base,
        )
    # There is intentionally no fall-through SUPPORT schema in v1.  A future
    # statistically valid artifact requires a new exact wrapper and an
    # independent offline implementation, not a local relaxation here.
    raise ValueError("statistical successor requires a new schema")


__all__ = [
    "TERMINAL_ADMISSION_SCHEMA_VERSION", "adapt_terminal_entity_signal",
    "validate_terminal_admission",
]
