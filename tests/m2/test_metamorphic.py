import copy
import itertools
import unittest

from proofnav.offline import ReplayOnlineVerifier
from proofnav.runtime import CertificateBuilder
from tests.m1.fixtures import obligation
from tests.m2.fixtures import (
    controlled_evidence,
    controlled_state,
    reseal,
    scenario,
)


class MetamorphicTests(unittest.TestCase):

    def test_evidence_order_permutation_is_certificate_invariant(self):
        bundle = scenario(hypothesis_ids=["hyp-a", "hyp-b"])
        items = controlled_evidence(bundle)
        first = controlled_state(bundle, evidence=items)
        second = controlled_state(bundle, evidence=list(reversed(items)))
        first_certificate = CertificateBuilder().build(first, "FOUND")["certificate"]
        second_certificate = CertificateBuilder().build(second, "FOUND")["certificate"]
        self.assertEqual(first.snapshot()["proof_state_digest"], second.snapshot()["proof_state_digest"])
        self.assertEqual(first_certificate, second_certificate)
        self.assertEqual(
            ReplayOnlineVerifier().verify(first, first_certificate),
            ReplayOnlineVerifier().verify(second, second_certificate),
        )

    def test_irrelevant_optional_evidence_does_not_change_legal_verdict(self):
        bundle = scenario()
        optional = obligation(
            bundle["scope"]["episode_id"], "obl-optional", "hyp-a",
            "pred-optional", "OPEN", [],
        )
        optional["necessary"] = False
        bundle["obligations"].append(optional)
        bundle["truth"]["claims"].append({
            "obligation_id": "obl-optional",
            "claim": "REFUTES",
            "source_event_id": bundle["observations"][0]["event_id"],
            "evidence_role": "viewpoint_view",
            "unit_id": "vp0:view:12",
        })
        items = controlled_evidence(bundle)
        without_optional = controlled_state(bundle, evidence=[items[0]])
        with_optional = controlled_state(bundle, evidence=items)
        for state in (without_optional, with_optional):
            certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
            report = ReplayOnlineVerifier().verify(state, certificate)
            self.assertTrue(report["accepted"], report)
            self.assertEqual(report["requested_verdict"], "FOUND")

    def test_remove_required_support_invalidates_found(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        state.revoke_evidence(certificate["evidence_ids"][0], "metamorphic removal")
        self.assertFalse(ReplayOnlineVerifier().verify(state, certificate)["accepted"])
        self.assertEqual(CertificateBuilder().build(state, "FOUND")["status"], "UNRESOLVED")

    def test_add_uncovered_hypothesis_invalidates_not_found(self):
        one = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
            hypothesis_ids=["hyp-a"],
        )
        certificate = CertificateBuilder().build(
            controlled_state(one), "NOT_FOUND",
        )["certificate"]
        two = scenario(
            premise_class="entity_absent", semantic_truth="NOT_FOUND",
            hypothesis_ids=["hyp-a", "hyp-b"],
        )
        report = ReplayOnlineVerifier().verify(controlled_state(two), certificate)
        self.assertFalse(report["accepted"])

    def test_open_frontier_and_repeat_verification(self):
        closed = scenario(
            premise_class="relation_mismatch", semantic_truth="NOT_FOUND",
        )
        state = controlled_state(closed)
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        verifier = ReplayOnlineVerifier()
        self.assertEqual(verifier.verify(state, certificate), verifier.verify(state, certificate))
        opened = scenario(
            premise_class="relation_mismatch", semantic_truth="NOT_FOUND",
            scope_closed=False, open_frontier=True,
        )
        self.assertEqual(
            CertificateBuilder().build(controlled_state(opened), "NOT_FOUND")["status"],
            "UNRESOLVED",
        )

    def test_exhaustive_two_hypothesis_states_never_accept_both_verdicts(self):
        statuses = ("open", "support", "refute", "conflict")
        for left, right in itertools.product(statuses, repeat=2):
            with self.subTest(left=left, right=right):
                bundle = scenario(
                    premise_class="attribute_mismatch", semantic_truth="NOT_FOUND",
                    hypothesis_ids=["hyp-a", "hyp-b"],
                )
                base = controlled_evidence(bundle)
                evidence = []
                for index, status in enumerate((left, right)):
                    refute = copy.deepcopy(base[index])
                    refute["evidence_id"] += "-refute"
                    refute["audit_trail"]["source_field"] += ".refute"
                    support = copy.deepcopy(base[index])
                    support["evidence_id"] += "-support"
                    support["claim"] = "SUPPORTS"
                    support["audit_trail"]["source_field"] += ".support"
                    if status in ("refute", "conflict"):
                        evidence.append(refute)
                    if status in ("support", "conflict"):
                        evidence.append(support)
                state = controlled_state(bundle, evidence=evidence)
                accepted = []
                for verdict in ("FOUND", "NOT_FOUND"):
                    outcome = CertificateBuilder().build(state, verdict)
                    if outcome["certificate"] is not None:
                        report = ReplayOnlineVerifier().verify(
                            state, outcome["certificate"],
                        )
                        if report["accepted"]:
                            accepted.append(verdict)
                self.assertLessEqual(len(accepted), 1, accepted)
                if "conflict" not in (left, right):
                    self.assertEqual("FOUND" in accepted, "support" in (left, right))
                    self.assertEqual("NOT_FOUND" in accepted, left == right == "refute")

    def test_malformed_certificate_is_rejected_without_exception(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        malformed_values = [
            "not-an-object",
            {"requested_verdict": "FOUND"},
            dict(copy.deepcopy(certificate), payload=None),
        ]
        malformed_path = copy.deepcopy(certificate)
        malformed_path["payload"]["true_path"][0]["evidence_ids"] = None
        malformed_values.append(reseal(malformed_path))
        for value in malformed_values:
            with self.subTest(value_type=type(value).__name__):
                report = ReplayOnlineVerifier().verify(state, value)
                self.assertEqual(report["status"], "REJECT")
                self.assertFalse(report["accepted"])


if __name__ == "__main__":
    unittest.main()
