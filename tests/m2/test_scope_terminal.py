import copy
import unittest

from proofnav.contracts import ContractViolation
from proofnav.offline import ReplayOnlineVerifier, ReplayTerminalController
from proofnav.runtime import CertificateBuilder
from tests.m2.fixtures import (
    controlled_evidence,
    controlled_state,
    execution,
    reseal,
    scenario,
)


class ScopeAndTerminalTests(unittest.TestCase):

    def test_open_frontier_blocks_not_found(self):
        bundle = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
            scope_closed=False, open_frontier=True,
        )
        state = controlled_state(bundle)
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED")
        self.assertIn("FRONTIER_OPEN", outcome["feedback"]["reason_codes"])

    def test_added_hypothesis_invalidates_old_certificate(self):
        first = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
            hypothesis_ids=["hyp-a"],
        )
        old_certificate = CertificateBuilder().build(
            controlled_state(first), "NOT_FOUND",
        )["certificate"]
        expanded = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
            hypothesis_ids=["hyp-a", "hyp-b"],
        )
        report = ReplayOnlineVerifier().verify(
            controlled_state(expanded), old_certificate,
        )
        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any(code.startswith("SCOPE_") for code in report["reason_codes"]))

    def test_scope_version_and_digest_change_rejects_stale_certificate(self):
        original = scenario()
        certificate = CertificateBuilder().build(
            controlled_state(original), "FOUND",
        )["certificate"]
        changed = scenario()
        changed["scope"]["provenance"]["version"] = "v2"
        changed["truth"]["scope_version"] = "v2"
        from proofnav.contracts import canonical_sha256
        changed["truth"]["scope_digest"] = canonical_sha256(changed["scope"])
        report = ReplayOnlineVerifier().verify(controlled_state(changed), certificate)
        self.assertEqual(report["status"], "REJECT")
        self.assertIn("SCOPE_SCOPE_VERSION_MISMATCH", report["reason_codes"])
        self.assertIn("SCOPE_SCOPE_DIGEST_MISMATCH", report["reason_codes"])

    def test_no_vp_left_with_incomplete_cover_is_unresolved(self):
        bundle = scenario(
            premise_class="relation_mismatch", semantic_truth="NOT_FOUND",
        )
        state = controlled_state(bundle, evidence=[])
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertIsNone(outcome["certificate"])
        decision = ReplayTerminalController().decide(
            state, "NOT_FOUND", None,
            execution(
                no_frontier=True, searchable_frontier=False,
                executable_action_available=False,
            ),
        )
        self.assertEqual(decision["directive"], "FINALIZE_UNRESOLVED")
        self.assertEqual(decision["semantic_verdict"], "UNRESOLVED")

    def test_complete_cover_is_scope_relative_only(self):
        bundle = scenario(
            premise_class="room_anchor_mismatch", semantic_truth="NOT_FOUND",
            hypothesis_ids=["in-scope-a", "in-scope-b"],
        )
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        self.assertEqual(
            certificate["payload"]["hypothesis_index"],
            ["in-scope-a", "in-scope-b"],
        )
        self.assertNotIn("out-of-scope", str(certificate))
        self.assertTrue(ReplayOnlineVerifier().verify(state, certificate)["accepted"])

    def test_revoke_makes_certificate_stale_and_reopens_positive(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        state.revoke_evidence(certificate["evidence_ids"][0], "predicate adapter invalidated")
        report = ReplayOnlineVerifier().verify(state, certificate)
        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any(code.startswith("STALE_") for code in report["reason_codes"]))
        rebuilt = CertificateBuilder().build(state, "FOUND")
        self.assertEqual(rebuilt["status"], "UNRESOLVED")

    def test_ledger_append_revoke_chain_is_auditable(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        appended = state.ledger.audit_log()
        self.assertEqual([item["event_type"] for item in appended], ["APPEND"])
        self.assertEqual(appended[0]["previous_digest"], "0" * 64)
        self.assertEqual(appended[0]["admission_scope_version"], bundle["scope"]["provenance"]["version"])
        self.assertEqual(appended[0]["admission_scope_digest"], state.snapshot()["scope_digest"])
        state.revoke_evidence(certificate["evidence_ids"][0], "audit-chain-test")
        events = state.ledger.audit_log()
        self.assertEqual([item["event_type"] for item in events], ["APPEND", "REVOKE"])
        self.assertEqual(events[1]["previous_digest"], events[0]["entry_digest"])
        self.assertEqual(
            state.snapshot()["audit_trail"]["ledger_audit_chain_tip"],
            events[1]["entry_digest"],
        )

    def test_duplicate_and_conflicting_evidence_fail_closed(self):
        bundle = scenario(
            premise_class="attribute_mismatch", semantic_truth="NOT_FOUND",
        )
        items = controlled_evidence(bundle)
        state = controlled_state(bundle, evidence=[])
        state.append_evidence(items[0])
        duplicate = copy.deepcopy(items[0])
        duplicate["evidence_id"] = "different-id-same-semantics"
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_DUPLICATE_SEMANTIC"):
            state.append_evidence(duplicate)
        support = copy.deepcopy(items[0])
        support["evidence_id"] = "conflicting-support"
        support["claim"] = "SUPPORTS"
        support["audit_trail"]["source_field"] = "claims[conflicting-support]"
        state.append_evidence(support)
        snapshot = state.snapshot()
        self.assertEqual(snapshot["obligations"][0]["status"], "CONFLICTED")
        self.assertEqual(CertificateBuilder().build(state, "FOUND")["status"], "UNRESOLVED")
        self.assertEqual(CertificateBuilder().build(state, "NOT_FOUND")["status"], "UNRESOLVED")

    def test_wrong_evidence_and_certificate_verdict_type_are_rejected(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        wrong_evidence = copy.deepcopy(certificate)
        wrong_evidence["evidence_ids"] = ["missing-evidence"]
        wrong_evidence["payload"]["true_path"][0]["evidence_ids"] = ["missing-evidence"]
        wrong_evidence = reseal(wrong_evidence)
        report = ReplayOnlineVerifier().verify(state, wrong_evidence)
        self.assertIn("EVIDENCE_MISSING_OR_REVOKED", report["reason_codes"])
        duplicate_coverage = copy.deepcopy(certificate)
        evidence_id = duplicate_coverage["evidence_ids"][0]
        duplicate_coverage["evidence_ids"].append(evidence_id)
        duplicate_coverage["payload"]["true_path"][0]["evidence_ids"].append(evidence_id)
        report = ReplayOnlineVerifier().verify(state, reseal(duplicate_coverage))
        self.assertIn("DUPLICATE_EVIDENCE_COVERAGE", report["reason_codes"])
        missing_predicate = copy.deepcopy(certificate)
        missing_predicate["payload"]["true_path"] = []
        missing_predicate["evidence_ids"] = []
        missing_predicate["obligation_ids"] = []
        report = ReplayOnlineVerifier().verify(state, reseal(missing_predicate))
        self.assertIn("TRUE_PATH_INCOMPLETE", report["reason_codes"])
        wrong_type = copy.deepcopy(certificate)
        wrong_type["certificate_type"] = "refutation_cover"
        wrong_type = reseal(wrong_type)
        report = ReplayOnlineVerifier().verify(state, wrong_type)
        self.assertIn("CERTIFICATE_VERDICT_MISMATCH", report["reason_codes"])

    def test_risk_and_budget_exhaustion_prevent_certificates(self):
        risky = scenario()
        risky["risk_claims"]["FOUND"]["upper_bound"] = 0.2
        state = controlled_state(risky)
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertIn("RISK_BUDGET_EXCEEDED", outcome["feedback"]["reason_codes"])

        exhausted = scenario()
        exhausted["budget_status"] = {
            "steps_used": 20,
            "observation_events": 1,
            "predicate_queries": 0,
            "within_budget": False,
            "exhausted_resources": ["steps_used"],
        }
        state = controlled_state(exhausted)
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertIn("BUDGET_EXHAUSTED", outcome["feedback"]["reason_codes"])

    def test_cost_and_resource_snapshot_tampering_is_rejected(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        changed_cost = copy.deepcopy(certificate)
        changed_cost["cost_snapshot"]["travel_distance_meters"] = 99.0
        report = ReplayOnlineVerifier().verify(state, reseal(changed_cost))
        self.assertIn("COST_SNAPSHOT_MISMATCH", report["reason_codes"])
        changed_budget = copy.deepcopy(certificate)
        changed_budget["budget_snapshot"]["steps_used"] = 19
        report = ReplayOnlineVerifier().verify(state, reseal(changed_budget))
        self.assertIn("BUDGET_SNAPSHOT_MISMATCH", report["reason_codes"])

    def test_invalid_risk_and_cost_types_fail_before_method_logic(self):
        invalid_risk = scenario()
        invalid_risk["risk_claims"]["FOUND"]["upper_bound"] = "low"
        with self.assertRaisesRegex(ContractViolation, "RISK_RANGE"):
            controlled_state(invalid_risk)
        invalid_cost = scenario()
        invalid_cost["cost_ledger"]["predicate_queries"] = 0.5
        with self.assertRaisesRegex(ContractViolation, "COST_VALUE"):
            controlled_state(invalid_cost)

    def test_duet_stop_max_step_and_budget_do_not_manufacture_not_found(self):
        bundle = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
        )
        state = controlled_state(bundle, evidence=[])
        controller = ReplayTerminalController()
        stopped = controller.decide(
            state, "NOT_FOUND", None, execution(duet_stop=True),
        )
        self.assertEqual(stopped["directive"], "CONTINUE_SEARCH")
        self.assertIsNone(stopped["semantic_verdict"])
        maxed = controller.decide(
            state, "NOT_FOUND", None, execution(max_step=True),
        )
        self.assertEqual(maxed["semantic_verdict"], "UNRESOLVED")
        budgeted = controller.decide(
            state, "NOT_FOUND", None, execution(budget_exhausted=True),
        )
        self.assertEqual(budgeted["semantic_verdict"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
