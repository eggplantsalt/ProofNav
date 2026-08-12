import copy
import json
import unittest

from proofnav.offline import (
    OracleOfflineVerifier, ReplayOnlineVerifier, ReplayTerminalController,
)
from proofnav.paired import validate_pair
from proofnav.runtime import CertificateBuilder
from tests.m1.fixtures import paired_case
from tests.m2.fixtures import (
    append_evaluations, complete_scenario, evidence_plan, execution, reseal,
    state_with_graph, truth_artifact,
)


class ClosedLoopTests(unittest.TestCase):

    def _assert_true_accept(self, bundle, verdict):
        state = bundle["state"]
        outcome = CertificateBuilder().build(state, verdict)
        self.assertEqual(outcome["status"], "CERTIFICATE", outcome)
        certificate = outcome["certificate"]
        json.dumps(certificate, sort_keys=True, allow_nan=False)
        online = ReplayOnlineVerifier().verify(state, certificate)
        self.assertEqual(online["status"], "ACCEPT", online)
        terminal = ReplayTerminalController().decide(
            state, verdict, certificate, execution(duet_stop=True),
        )
        self.assertEqual(terminal["directive"], "ACCEPT_" + verdict)
        self.assertEqual(terminal["accepted_certificate_id"], certificate["certificate_id"])
        self.assertEqual(
            terminal["accepted_certificate_digest"], certificate["certificate_digest"],
        )
        offline = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), terminal, certificate,
        )
        self.assertEqual(offline["outcome"], "TRUE_ACCEPT", offline)
        self.assertIsNone(offline["feedback_to_runtime"])
        return certificate

    def test_positive_certificate_online_gate_and_offline_truth(self):
        self._assert_true_accept(
            complete_scenario("positive_control", "FOUND"), "FOUND",
        )

    def test_four_false_premise_traces_and_incomplete_cover(self):
        for premise_class in (
                "entity_absent", "attribute_mismatch", "relation_mismatch",
                "room_anchor_mismatch"):
            with self.subTest(premise_class=premise_class):
                bundle = complete_scenario(premise_class, "NOT_FOUND")
                certificate = self._assert_true_accept(bundle, "NOT_FOUND")
                incomplete = copy.deepcopy(certificate)
                removed = incomplete["payload"]["refutation_cover"].pop()
                incomplete["evidence_ids"] = [
                    item for item in incomplete["evidence_ids"]
                    if item not in removed["evidence_ids"]
                ]
                incomplete["obligation_ids"].remove(removed["obligation_id"])
                incomplete = reseal(incomplete)
                rejected = ReplayOnlineVerifier().verify(bundle["state"], incomplete)
                self.assertEqual(rejected["status"], "REJECT", rejected)
                self.assertIn("REFUTATION_COVER_INCOMPLETE", rejected["reason_codes"])
                self.assertIn(removed["hypothesis_id"], rejected["uncovered_hypothesis_ids"])

                pair = paired_case(premise_class)
                validate_pair(pair)
                clean = pair["members"]["clean"]["agent_visible"]
                false = pair["members"]["false"]["agent_visible"]
                changed = [
                    key for key in clean["template_slots"]
                    if clean["template_slots"][key] != false["template_slots"][key]
                ]
                self.assertEqual(changed, [pair["changed_premise_audit"]["changed_slot"]])

    def test_false_premise_truth_refutes_the_declared_predicate_kind(self):
        expected = {
            "entity_absent": "coverage",
            "attribute_mismatch": "attribute",
            "relation_mismatch": "relation",
            "room_anchor_mismatch": "room_anchor",
        }
        for premise_class, changed_kind in expected.items():
            with self.subTest(premise_class=premise_class):
                truth = complete_scenario(
                    premise_class, "NOT_FOUND",
                )["truth"]
                non_open = [
                    item for item in truth["claims"]
                    if item["claim"] != "OPEN"
                ]
                self.assertTrue(any(
                    item["predicate_kind"] == changed_kind
                    and item["claim"] == "REFUTES"
                    for item in non_open
                ))
                self.assertFalse(any(
                    item["predicate_kind"] != changed_kind
                    and item["predicate_kind"] != "coverage"
                    and item["claim"] == "REFUTES"
                    for item in non_open
                ))

    def test_factual_error_is_script_truth_difference_not_corrupt_truth(self):
        # Controlled predicate output refutes all alternatives and produces a
        # structurally valid NOT certificate.
        state, _, _, _ = state_with_graph(
            "positive_control", graph="closed_one",
            object_ids={"vp0": ["target"]},
            episode_id="factual-error-script",
        )
        append_evaluations(
            state, evidence_plan(state.snapshot(), "NOT_FOUND"),
            "factually-wrong-refutation",
        )
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        terminal = ReplayTerminalController().decide(
            state, "NOT_FOUND", certificate, execution(),
        )
        # Hidden fact is a coherent FOUND evaluation over the same frozen
        # universe; no truth field is mutated after validation.
        found_plan = evidence_plan(state.snapshot(), "FOUND")
        hidden_truth = truth_artifact(
            state, "positive_control", found_plan, semantic_truth="FOUND",
        )
        offline = OracleOfflineVerifier().verify(
            hidden_truth, state.audit_bundle(), terminal, certificate,
        )
        self.assertEqual(offline["outcome"], "FALSE_ACCEPT", offline)
        self.assertTrue(offline["online_offline_conflict"])
        self.assertEqual(offline["audit_disposition"], "UNRESOLVED")
        self.assertFalse(offline["claim_matches_truth"])


if __name__ == "__main__":
    unittest.main()
