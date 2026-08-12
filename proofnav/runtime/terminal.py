"""M2.1 verifier-gated terminal state machine with explicit identities."""

import copy

from proofnav.contracts import SCHEMA_VERSIONS
from proofnav.runtime.verifier import OnlineVerifier, _canonical_view, _empty_view, _report


_EXECUTION_FIELDS = {
    "duet_stop", "no_frontier", "max_step", "budget_exhausted",
    "executable_action_available", "searchable_frontier", "execution_error",
}


def _copy(value):
    return copy.deepcopy(value)


def _safe_execution():
    return {
        "duet_stop": False,
        "no_frontier": False,
        "max_step": False,
        "budget_exhausted": False,
        "executable_action_available": False,
        "searchable_frontier": False,
        "execution_error": True,
    }


def _proposal_identity(certificate):
    if not isinstance(certificate, dict):
        return None, None
    return certificate.get("certificate_id"), certificate.get("certificate_digest")


def _with_rejection_reason(report, reason):
    value = _copy(report)
    reasons = sorted(set(value.get("reason_codes", []) + [reason]))
    value["status"] = "REJECT"
    value["accepted"] = False
    value["reason_codes"] = reasons
    feedback = value.setdefault("structured_feedback", {})
    feedback["recommended_action"] = "CONTINUE_EVIDENCE_COLLECTION"
    feedback["reason_codes"] = reasons
    return value


class _TerminalControllerCore(object):

    def __init__(self, verifier):
        self._verifier = verifier

    def decide(self, state_or_bundle, proposed_verdict, certificate, execution):
        """Verify one proposal and choose accept, continue, or UNRESOLVED.

        The terminal record binds the proposed certificate identity even when
        rejected, and binds an accepted identity only after all three views
        (proposal, certificate, and online report) agree.
        """

        try:
            _, snapshot, bundle_reasons = _canonical_view(
                state_or_bundle, self._verifier._allow_controlled,
            )
        except Exception:  # The verifier returns the stable, specific reason.
            snapshot = _empty_view()
            bundle_reasons = ["AUDIT_BUNDLE_INVALID"]

        proposed_id, proposed_digest = _proposal_identity(certificate)
        if not isinstance(execution, dict) or set(execution) != _EXECUTION_FIELDS:
            verification = _report(
                snapshot, "REJECT", proposed_verdict,
                bundle_reasons + ["EXECUTION_SIGNAL_INVALID"],
                certificate=certificate,
            )
            execution = _safe_execution()
        elif any(not isinstance(execution[key], bool) for key in _EXECUTION_FIELDS):
            verification = _report(
                snapshot, "REJECT", proposed_verdict,
                bundle_reasons + ["EXECUTION_SIGNAL_TYPE_INVALID"],
                certificate=certificate,
            )
            execution = _copy(execution)
            execution["execution_error"] = True
            execution["executable_action_available"] = False
        else:
            execution = _copy(execution)
            verification = self._verifier.verify(state_or_bundle, certificate)
            if proposed_verdict not in (None, "FOUND", "NOT_FOUND"):
                verification = _with_rejection_reason(
                    verification, "VERDICT_TYPE_INVALID",
                )
            elif certificate is not None and not isinstance(certificate, dict):
                verification = _with_rejection_reason(
                    verification, "CERTIFICATE_TYPE_INVALID",
                )
            elif (certificate is not None
                  and certificate.get("requested_verdict") != proposed_verdict):
                verification = _with_rejection_reason(
                    verification, "PROPOSAL_CERTIFICATE_MISMATCH",
                )

        # Accepted identity is stricter than a boolean returned by a verifier.
        if verification.get("accepted"):
            identity_consistent = (
                proposed_verdict == verification.get("requested_verdict")
                and proposed_id is not None
                and proposed_digest is not None
                and proposed_id == verification.get("certificate_id")
                and proposed_digest == verification.get("certificate_digest")
                and proposed_digest == verification.get("calculated_certificate_digest")
                and verification.get("decision_cut") == snapshot.get("decision_cut")
                and verification.get("proof_state_digest")
                == snapshot.get("proof_state_digest")
            )
            if not identity_consistent:
                verification = _with_rejection_reason(
                    verification, "TERMINAL_CERTIFICATE_IDENTITY_MISMATCH",
                )

        if verification.get("accepted"):
            verdict = verification["requested_verdict"]
            return self._decision(
                "ACCEPT_" + verdict, True, verdict, "verifier_accept",
                proposed_verdict, proposed_id, proposed_digest,
                proposed_id, proposed_digest, snapshot,
                verification, execution,
            )

        budget = snapshot.get("budget_status", {})
        topology = snapshot.get("topology", {})
        frontier_open = bool(topology.get("frontier_viewpoint_ids", []))
        forced_cause = None
        if execution["execution_error"] or not snapshot.get("proof_state_digest"):
            forced_cause = "error"
        elif (execution["budget_exhausted"]
              or not budget.get("within_budget", False)
              or not budget.get("can_continue", False)):
            forced_cause = "budget"
        elif execution["max_step"]:
            forced_cause = "max_step"
        elif not execution["executable_action_available"]:
            forced_cause = "no_executable_action"
        elif (execution["no_frontier"] and not execution["searchable_frontier"]
              and not frontier_open):
            forced_cause = "no_frontier"
        if forced_cause is not None:
            return self._decision(
                "FINALIZE_UNRESOLVED", True, "UNRESOLVED", forced_cause,
                proposed_verdict, proposed_id, proposed_digest,
                None, None, snapshot, verification, execution,
            )

        # DUET STOP and no_vp_left are proposals, not semantic proofs.  If the
        # derived frontier/budget still permits action, a rejection is a real
        # sequential CONTINUE that the state can record before the next event.
        return self._decision(
            "CONTINUE_SEARCH", False, None, "verifier_reject_or_defer",
            proposed_verdict, proposed_id, proposed_digest,
            None, None, snapshot, verification, execution,
        )

    @staticmethod
    def _decision(directive, terminal, semantic_verdict, cause,
                  proposed_verdict, proposed_id, proposed_digest,
                  accepted_id, accepted_digest, snapshot,
                  verification, execution):
        return {
            "schema_version": SCHEMA_VERSIONS["terminal_decision"],
            "directive": directive,
            "terminal": terminal,
            "semantic_verdict": semantic_verdict,
            "cause": cause,
            "proposed_verdict": proposed_verdict,
            "proposed_certificate_id": proposed_id,
            "proposed_certificate_digest": proposed_digest,
            "accepted_certificate_id": accepted_id,
            "accepted_certificate_digest": accepted_digest,
            "decision_cut": _copy(snapshot.get("decision_cut")),
            "transition_tip": snapshot.get("transition_tip"),
            "proof_state_digest": snapshot.get("proof_state_digest"),
            "certificate_accepted": verification.get("accepted") is True,
            "online_verification": _copy(verification),
            "feedback": _copy(verification.get("structured_feedback", {})),
            "duet_signal": _copy(execution),
        }


class TerminalController(_TerminalControllerCore):
    """Production terminal controller with non-configurable zero admission."""

    def __init__(self):
        super().__init__(OnlineVerifier())


__all__ = ["TerminalController"]
