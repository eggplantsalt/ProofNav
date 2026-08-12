"""Permanent regressions for the four counterexamples reproduced on old M2."""

import copy
import unittest

from proofnav.contracts import ContractViolation
from proofnav.offline import (
    OracleOfflineVerifier, ReplayOnlineVerifier, ReplayTerminalController,
)
from proofnav.runtime import CertificateBuilder
from tests.m2.fixtures import (
    append_evaluations,
    complete_scenario,
    controlled_observation,
    evidence_plan,
    execution,
    reseal,
    state_with_graph,
)


class OldM2Counterexamples(unittest.TestCase):

    def test_unvisited_candidate_cannot_be_hidden_by_forged_scope_closed(self):
        state, _, _, observations = state_with_graph(
            "entity_absent", graph="open_two",
            object_ids={"vp0": [], "vp1": []},
        )
        self.assertEqual(observations[0]["candidates"][0]["viewpoint_id"], "vp1")
        snapshot = state.snapshot()
        self.assertEqual(snapshot["topology"]["frontier_viewpoint_ids"], ["vp1"])
        self.assertIsNone(snapshot["closure_witness"])
        plan = evidence_plan(snapshot, "NOT_FOUND")
        append_evaluations(state, plan)
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED", outcome)
        self.assertIn("FRONTIER_OPEN", outcome["feedback"]["reason_codes"])
        # The old bulk constructor authority no longer exists.
        with self.assertRaises(TypeError):
            type(state)(None, None, None, [], True, {}, {}, {})

    def test_mixed_object_positive_support_cannot_form_true_path(self):
        state, _, _, _ = state_with_graph(
            "attribute_mismatch", graph="closed_one",
            object_ids={"vp0": ["object-a", "object-b"]},
        )
        snapshot = state.snapshot()
        subject_hypotheses = [
            item for item in snapshot["hypotheses"]
            if item["hypothesis_kind"] == "subject"
        ]
        self.assertEqual(len(subject_hypotheses), 2)
        first = subject_hypotheses[0]
        obligations = [
            item for item in snapshot["obligations"]
            if item["hypothesis_id"] == first["hypothesis_id"]
        ]
        plan = {item["obligation_id"]: "SUPPORTS" for item in obligations}
        _, wrappers = append_evaluations(state, plan)
        # A second object's unit cannot be substituted under the first
        # hypothesis even when obligation/predicate IDs remain unchanged.
        attacked = copy.deepcopy(wrappers[0])
        attacked["evidence"]["evidence_id"] = "mixed-object-attack"
        attacked["evidence"]["unit_id"] = subject_hypotheses[1]["binding"]["subject_unit_ids"][0]
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_SUBJECT_BINDING"):
            state.append_evidence(attacked)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        mixed = copy.deepcopy(certificate)
        mixed["payload"]["true_path"][0]["binding"] = subject_hypotheses[1]["binding"]
        report = ReplayOnlineVerifier().verify(state, reseal(mixed))
        self.assertEqual(report["status"], "REJECT", report)
        self.assertIn("TRUE_PATH_ITEM_INVALID", report["reason_codes"])

    def test_future_observation_cannot_close_current_decision(self):
        state, scope, _, _ = state_with_graph(
            "positive_control", graph="open_two",
            object_ids={"vp0": ["target"]},
        )
        future = controlled_observation(
            scope["episode_id"], viewpoint="vp1", event_seq=99, step=99,
            candidates=["vp0"], object_ids=["target-later"],
        )
        before = state.audit_bundle()
        with self.assertRaisesRegex(ContractViolation, "OBSERVATION_TIME_CUT"):
            state.ingest_observation(future)
        self.assertEqual(state.audit_bundle(), before)

    def test_tampered_certificate_rejection_is_not_false_reject(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        tampered = copy.deepcopy(certificate)
        tampered["certificate_digest"] = "f" * 64
        online = ReplayOnlineVerifier().verify(state, tampered)
        self.assertEqual(online["status"], "REJECT", online)
        terminal = ReplayTerminalController().decide(
            state, "FOUND", tampered, execution(),
        )
        offline = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), terminal, tampered,
        )
        self.assertEqual(offline["outcome"], "CORRECT_REJECT", offline)
        self.assertNotEqual(offline["outcome"], "FALSE_REJECT")


if __name__ == "__main__":
    unittest.main()
