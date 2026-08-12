"""Code-owned DUET action-cut envelope for M3-B terminal evidence.

The nested M3-A signal remains an uncalibrated proposal.  This successor binds
the action selected from the same forward pass and marks only an explicit DUET
STOP as eligible for positive terminal evidence.  Forced endings never become
REFUTE, coverage, or NOT_FOUND evidence.
"""

import copy
import json
import os

from proofnav.contracts import ContractViolation, canonical_sha256

from .duet_signal import build_duet_signal


TERMINAL_SIGNAL_SCHEMA_VERSION = "proofnav.duet-terminal-evidence-signal.v1"
TERMINAL_SIGNAL_PRODUCER = "proofnav.perception.terminal_signal"
_DECISION_FIELDS = frozenset((
    "active_before_decision", "selected_navigation_index", "duet_stop",
    "no_frontier", "max_step", "environment_action_is_none",
    "evidence_eligibility",
))
_FIELDS = frozenset((
    "schema_version", "producer", "base_signal", "decision_context",
    "terminal_signal_digest",
))


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _exact(value, fields, location):
    if not isinstance(value, dict) or set(value) != fields:
        _fail("M3B_TERMINAL_SCHEMA", location, "exact terminal signal schema required")
    return value


def validate_terminal_signal(value):
    """Validate the signal and its action-cut eligibility independently."""

    value = _exact(value, _FIELDS, "$.terminal_signal")
    if (value["schema_version"] != TERMINAL_SIGNAL_SCHEMA_VERSION
            or value["producer"] != TERMINAL_SIGNAL_PRODUCER):
        _fail("M3B_TERMINAL_VERSION", "$.terminal_signal", "code-owned version required")
    # Local import avoids a construction-time import cycle.
    from .evidence_adapter import validate_duet_signal
    validate_duet_signal(value["base_signal"])
    decision = _exact(
        value["decision_context"], _DECISION_FIELDS,
        "$.terminal_signal.decision_context",
    )
    for key in (
            "active_before_decision", "duet_stop", "no_frontier",
            "max_step", "environment_action_is_none"):
        if not isinstance(decision[key], bool):
            _fail("M3B_TERMINAL_TYPE", "$.decision_context." + key, "boolean required")
    index = decision["selected_navigation_index"]
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        _fail("M3B_TERMINAL_INDEX", "$.decision_context.selected_navigation_index", "nonnegative integer required")
    if not decision["active_before_decision"]:
        _fail("M3B_TERMINAL_INACTIVE", "$.decision_context", "ended rows are forbidden")
    forced = decision["no_frontier"] or decision["max_step"]
    expected_none = decision["duet_stop"] or forced
    if decision["environment_action_is_none"] != expected_none:
        _fail("M3B_TERMINAL_ACTION", "$.decision_context", "action-null identity mismatch")
    expected_eligibility = (
        "TERMINAL_SUPPORT" if decision["duet_stop"]
        else ("FORCED_END_ABSTAIN" if forced else "SEARCH_PROPOSAL")
    )
    if decision["evidence_eligibility"] != expected_eligibility:
        _fail("M3B_TERMINAL_ELIGIBILITY", "$.decision_context", "non-canonical eligibility")
    sealed = copy.deepcopy(value)
    digest = sealed.pop("terminal_signal_digest")
    if digest != canonical_sha256(sealed):
        _fail("M3B_TERMINAL_DIGEST", "$.terminal_signal_digest", "record changed")
    return value


def build_terminal_signal(*, decision_context, **base_inputs):
    base = build_duet_signal(**base_inputs)
    value = {
        "schema_version": TERMINAL_SIGNAL_SCHEMA_VERSION,
        "producer": TERMINAL_SIGNAL_PRODUCER,
        "base_signal": base,
        "decision_context": copy.deepcopy(decision_context),
    }
    value["terminal_signal_digest"] = canonical_sha256(value)
    return validate_terminal_signal(value)


class DuetTerminalSignalSink(object):
    """Separate JSONL sink; it never changes the legacy or M3-A outputs."""

    def __init__(self, path, model_identity):
        if not isinstance(path, str) or not path.strip():
            _fail("M3B_TERMINAL_PATH", "$.path", "non-empty path required")
        self.path = os.path.abspath(path)
        self.model_identity = copy.deepcopy(model_identity)
        parent = os.path.dirname(self.path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        self._file = open(self.path, "w", encoding="utf-8")
        self._event_records = {}

    def emit(self, **kwargs):
        if self._file is None:
            _fail("M3B_TERMINAL_CLOSED", "$.sink", "sink is closed")
        observation = kwargs.get("observation", {})
        event_key = (
            observation.get("episode_id"), observation.get("event_seq"),
        )
        if (not isinstance(event_key[0], str)
                or isinstance(event_key[1], bool)
                or not isinstance(event_key[1], int)):
            _fail(
                "M3B_TERMINAL_EVENT_KEY", "$.observation",
                "episode_id and event_seq are required before emission",
            )
        # Evaluation iterators may pad their final batch by replaying initial
        # episodes.  An event-sourced sink admits the first causal event once;
        # a batch wrap is not a second observation or statistical sample.
        if event_key in self._event_records:
            return copy.deepcopy(self._event_records[event_key])
        kwargs["model_identity"] = self.model_identity
        value = build_terminal_signal(**kwargs)
        self._file.write(json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n")
        self._file.flush()
        self._event_records[event_key] = copy.deepcopy(value)
        return value

    def close(self):
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None


__all__ = [
    "DuetTerminalSignalSink", "TERMINAL_SIGNAL_PRODUCER",
    "TERMINAL_SIGNAL_SCHEMA_VERSION", "build_terminal_signal",
    "validate_terminal_signal",
]
