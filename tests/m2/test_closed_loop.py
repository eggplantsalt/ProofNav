import copy
import json
import unittest

from proofnav.contracts import canonical_sha256
from proofnav.offline import (
    OracleOfflineVerifier,
    ReplayOnlineVerifier,
    ReplayTerminalController,
)
from proofnav.paired import validate_pair
from proofnav.runtime import CertificateBuilder
from tests.m1.fixtures import paired_case
from tests.m2.fixtures import controlled_state, execution, reseal, scenario


class ClosedLoopTests(unittest.TestCase):

    def test_positive_certificate_online_gate_and_offline_truth(self):
        bundle = scenario()
        state = controlled_state(bundle)
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertEqual(outcome["status"], "CERTIFICATE")
        certificate = outcome["certificate"]
        json.dumps(certificate, sort_keys=True, allow_nan=False)
        online = ReplayOnlineVerifier().verify(state, certificate)
        self.assertEqual(online["status"], "ACCEPT", online)
        self.assertEqual(online["certificate_digest"], certificate["certificate_digest"])
        terminal = ReplayTerminalController().decide(
            state, "FOUND", certificate, execution(duet_stop=True),
        )
        self.assertEqual(terminal["directive"], "ACCEPT_FOUND")
        self.assertEqual(terminal["semantic_verdict"], "FOUND")
        offline = OracleOfflineVerifier().verify(bundle["truth"], terminal, certificate)
        self.assertEqual(offline["outcome"], "TRUE_ACCEPT", offline)
        self.assertIsNone(offline["feedback_to_runtime"])

    def test_four_false_premise_traces_complete_and_incomplete(self):
        classes = (
            "entity_absent", "attribute_mismatch", "relation_mismatch",
            "room_anchor_mismatch",
        )
        for premise_class in classes:
            with self.subTest(premise_class=premise_class):
                bundle = scenario(
                    premise_class=premise_class,
                    semantic_truth="NOT_FOUND",
                    hypothesis_ids=["hyp-a", "hyp-b"],
                )
                state = controlled_state(bundle)
                outcome = CertificateBuilder().build(state, "NOT_FOUND")
                self.assertEqual(outcome["status"], "CERTIFICATE", outcome)
                certificate = outcome["certificate"]
                online = ReplayOnlineVerifier().verify(state, certificate)
                self.assertTrue(online["accepted"], online)
                terminal = ReplayTerminalController().decide(
                    state, "NOT_FOUND", certificate, execution(duet_stop=True),
                )
                self.assertEqual(terminal["directive"], "ACCEPT_NOT_FOUND")
                offline = OracleOfflineVerifier().verify(
                    bundle["truth"], terminal, certificate,
                )
                self.assertEqual(offline["outcome"], "TRUE_ACCEPT", offline)

                incomplete = copy.deepcopy(certificate)
                removed = incomplete["payload"]["refutation_cover"].pop()
                incomplete["evidence_ids"] = [
                    item for item in incomplete["evidence_ids"]
                    if item not in removed["evidence_ids"]
                ]
                incomplete["obligation_ids"].remove(removed["obligation_id"])
                incomplete = reseal(incomplete)
                rejected = ReplayOnlineVerifier().verify(state, incomplete)
                self.assertEqual(rejected["status"], "REJECT", rejected)
                self.assertIn("REFUTATION_COVER_INCOMPLETE", rejected["reason_codes"])
                self.assertIn(removed["hypothesis_id"], rejected["uncovered_hypothesis_ids"])
                unresolved = ReplayTerminalController().decide(
                    state, "NOT_FOUND", incomplete,
                    execution(
                        no_frontier=True, searchable_frontier=False,
                        executable_action_available=False,
                    ),
                )
                self.assertEqual(unresolved["semantic_verdict"], "UNRESOLVED")

                pair = paired_case(premise_class)
                validate_pair(pair)
                clean = pair["members"]["clean"]["agent_visible"]
                false = pair["members"]["false"]["agent_visible"]
                self.assertEqual(
                    set(clean["template_slots"]) ^ set(false["template_slots"]),
                    set(),
                )
                changed = [
                    key for key in clean["template_slots"]
                    if clean["template_slots"][key] != false["template_slots"][key]
                ]
                self.assertEqual(changed, [pair["changed_premise_audit"]["changed_slot"]])

    def test_offline_verifier_detects_factually_wrong_online_acceptance(self):
        bundle = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
        )
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        terminal = ReplayTerminalController().decide(
            state, "NOT_FOUND", certificate, execution(),
        )
        hidden_truth = copy.deepcopy(bundle["truth"])
        hidden_truth["semantic_truth"] = "FOUND"
        hidden_truth["supported_hypothesis_ids"] = ["hyp-a"]
        hidden_truth["refuted_hypothesis_ids"] = []
        hidden_truth["audit_trail"]["source_artifact_digest"] = canonical_sha256(
            {"counterexample": "predicate output refutes a truly present hypothesis"}
        )
        offline = OracleOfflineVerifier().verify(hidden_truth, terminal, certificate)
        self.assertEqual(offline["outcome"], "FALSE_ACCEPT")
        self.assertTrue(offline["online_offline_conflict"])
        self.assertEqual(offline["audit_disposition"], "UNRESOLVED")
        self.assertIsNone(offline["feedback_to_runtime"])


if __name__ == "__main__":
    unittest.main()
