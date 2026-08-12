"""Verifier-gated terminal state machine, independent of DUET rollout code."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS
from proofnav.runtime.verifier import OnlineVerifier


_EXECUTION_FIELDS = {
    "duet_stop", "no_frontier", "max_step", "budget_exhausted",
    "executable_action_available", "searchable_frontier", "execution_error",
}


def _execution_error_report(snapshot, reason):
    return {
        "schema_version": SCHEMA_VERSIONS["online_verification"],
        "status": "REJECT",
        "accepted": False,
        "requested_verdict": None,
        "reason_codes": [reason],
        "missing_obligation_ids": [],
        "uncovered_hypothesis_ids": [],
        "frontier_witnesses": copy.deepcopy(snapshot["frontier_witnesses"]),
        "scope_digest": snapshot["scope_digest"],
        "proof_state_digest": snapshot["proof_state_digest"],
        "certificate_digest": None,
        "structured_feedback": {
            "recommended_action": "CONTINUE_EVIDENCE_COLLECTION",
            "reason_codes": [reason],
            "missing_obligation_ids": [],
            "uncovered_hypothesis_ids": [],
            "frontier_witness_ids": [
                item["frontier_id"] for item in snapshot["frontier_witnesses"]
            ],
        },
    }


class _TerminalControllerCore(object):

    def __init__(self, verifier):
        self._verifier = verifier

    def decide(self, state, proposed_verdict, certificate, execution):
        snapshot = state.snapshot()
        if not isinstance(execution, dict) or set(execution) != _EXECUTION_FIELDS:
            verification = _execution_error_report(snapshot, "EXECUTION_SIGNAL_INVALID")
            execution = {
                "duet_stop": False,
                "no_frontier": False,
                "max_step": False,
                "budget_exhausted": False,
                "executable_action_available": False,
                "searchable_frontier": False,
                "execution_error": True,
            }
        elif any(not isinstance(execution[key], bool) for key in _EXECUTION_FIELDS):
            verification = _execution_error_report(snapshot, "EXECUTION_SIGNAL_TYPE_INVALID")
            execution = copy.deepcopy(execution)
            execution["execution_error"] = True
            execution["executable_action_available"] = False
        elif proposed_verdict not in (None, "FOUND", "NOT_FOUND"):
            verification = _execution_error_report(snapshot, "VERDICT_TYPE_INVALID")
        elif (certificate is not None and not isinstance(certificate, dict)):
            verification = _execution_error_report(snapshot, "CERTIFICATE_TYPE_INVALID")
        elif certificate is not None and certificate.get("requested_verdict") != proposed_verdict:
            verification = _execution_error_report(snapshot, "PROPOSAL_CERTIFICATE_MISMATCH")
        else:
            verification = self._verifier.verify(state, certificate)

        if verification["accepted"]:
            verdict = verification["requested_verdict"]
            return self._decision(
                "ACCEPT_" + verdict, True, verdict, "verifier_accept",
                verification, execution,
            )

        forced_cause = None
        if execution["execution_error"]:
            forced_cause = "error"
        elif execution["budget_exhausted"] or not snapshot["budget_status"]["within_budget"]:
            forced_cause = "budget"
        elif execution["max_step"]:
            forced_cause = "max_step"
        elif not execution["executable_action_available"]:
            forced_cause = "no_executable_action"
        elif execution["no_frontier"] and not execution["searchable_frontier"]:
            forced_cause = "no_frontier"
        if forced_cause is not None:
            return self._decision(
                "FINALIZE_UNRESOLVED", True, "UNRESOLVED", forced_cause,
                verification, execution,
            )
        # A DUET STOP is merely a proposal here.  If search remains possible,
        # it cannot bypass proof verification.
        return self._decision(
            "CONTINUE_SEARCH", False, None, "verifier_reject_or_defer",
            verification, execution,
        )

    @staticmethod
    def _decision(directive, terminal, semantic_verdict, cause,
                  verification, execution):
        return {
            "schema_version": SCHEMA_VERSIONS["terminal_decision"],
            "directive": directive,
            "terminal": terminal,
            "semantic_verdict": semantic_verdict,
            "cause": cause,
            "certificate_accepted": verification["accepted"],
            "online_verification": copy.deepcopy(verification),
            "feedback": copy.deepcopy(verification["structured_feedback"]),
            "duet_signal": copy.deepcopy(execution),
        }


class TerminalController(_TerminalControllerCore):
    """Production terminal controller with a non-configurable verifier."""

    def __init__(self):
        super().__init__(OnlineVerifier())
