import ast
import copy
from pathlib import Path
import unittest

from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.offline import (
    OracleOfflineVerifier, ReplayOnlineVerifier, ReplayTerminalController,
    seal_controlled_artifact, validate_controlled_script,
    validate_controlled_truth,
)
from proofnav.runtime import CertificateBuilder, TerminalController
from proofnav.runtime.terminal import _TerminalControllerCore
from tests.m2.fixtures import (
    append_evaluations, complete_scenario, controlled_observation,
    empty_state, evidence_plan, execution, reseal, truth_artifact,
)


class _ForcedRejectingReplayVerifier(object):
    """Test-only faulty online policy over an otherwise valid replay report."""

    _allow_controlled = True

    def __init__(self, reason="TEST_ONLY_FORCED_REJECT"):
        self._delegate = ReplayOnlineVerifier()
        self._reason = reason

    def verify(self, state_or_bundle, certificate):
        report = self._delegate.verify(state_or_bundle, certificate)
        assert report["status"] == "ACCEPT"
        report = copy.deepcopy(report)
        report["status"] = "REJECT"
        report["accepted"] = False
        report["reason_codes"] = [self._reason]
        report["structured_feedback"]["recommended_action"] = (
            "CONTINUE_EVIDENCE_COLLECTION"
        )
        report["structured_feedback"]["reason_codes"] = [self._reason]
        return report


class OfflineAuditTests(unittest.TestCase):

    def test_true_accept_and_no_mutation_or_runtime_feedback(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        terminal = ReplayTerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        inputs = copy.deepcopy((bundle["truth"], state.audit_bundle(), terminal, certificate))
        result = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), terminal, certificate,
        )
        self.assertEqual(result["outcome"], "TRUE_ACCEPT", result)
        self.assertTrue(result["structural_valid"])
        self.assertTrue(result["certificate_structural_valid"])
        self.assertTrue(result["terminal_structural_valid"])
        self.assertIsNone(result["feedback_to_runtime"])
        self.assertEqual(
            (bundle["truth"], state.audit_bundle(), terminal, certificate), inputs,
        )

    def test_only_valid_true_certificate_forced_reject_is_false_reject(self):
        for reason in ("TEST_ONLY_FORCED_REJECT", "VERDICT_TYPE_INVALID"):
            with self.subTest(reason=reason):
                bundle = complete_scenario("positive_control", "FOUND")
                state = bundle["state"]
                certificate = CertificateBuilder().build(
                    state, "FOUND",
                )["certificate"]
                controller = _TerminalControllerCore(
                    _ForcedRejectingReplayVerifier(reason),
                )
                terminal = controller.decide(
                    state, "FOUND", certificate, execution(),
                )
                self.assertEqual(
                    terminal["online_verification"]["status"], "REJECT",
                )
                result = OracleOfflineVerifier().verify(
                    bundle["truth"], state.audit_bundle(), terminal,
                    certificate,
                )
                self.assertEqual(result["outcome"], "FALSE_REJECT", result)
                self.assertTrue(result["claim_matches_truth"])
                self.assertTrue(result["certificate_structural_valid"])
                self.assertTrue(result["terminal_structural_valid"])

    def test_digest_damage_and_production_firewall_are_correct_rejects(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        damaged = copy.deepcopy(certificate)
        damaged["certificate_digest"] = "0" * 64
        terminal = ReplayTerminalController().decide(
            state, "FOUND", damaged, execution(),
        )
        result = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), terminal, damaged,
        )
        self.assertEqual(result["outcome"], "CORRECT_REJECT", result)
        self.assertFalse(result["certificate_structural_valid"])

        production_terminal = TerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        self.assertIn(
            "CONTROLLED_SOURCE_FORBIDDEN",
            production_terminal["online_verification"]["reason_codes"],
        )
        firewall = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), production_terminal, certificate,
        )
        self.assertEqual(firewall["outcome"], "CORRECT_REJECT", firewall)
        self.assertNotEqual(firewall["outcome"], "FALSE_REJECT")

    def test_stale_and_wrong_provenance_rejections_are_correct(self):
        provenance_bundle = complete_scenario("positive_control", "FOUND")
        provenance_state = provenance_bundle["state"]
        certificate = CertificateBuilder().build(
            provenance_state, "FOUND",
        )["certificate"]
        wrong_provenance = copy.deepcopy(certificate)
        wrong_provenance["provenance"]["builder_version"] = "caller.builder.alias"
        wrong_provenance = reseal(wrong_provenance)
        terminal = ReplayTerminalController().decide(
            provenance_state, "FOUND", wrong_provenance, execution(),
        )
        report = OracleOfflineVerifier().verify(
            provenance_bundle["truth"], provenance_state.audit_bundle(),
            terminal, wrong_provenance,
        )
        self.assertEqual(report["outcome"], "CORRECT_REJECT", report)
        self.assertFalse(report["certificate_structural_valid"])

        stale_bundle = complete_scenario("positive_control", "FOUND")
        stale_state = stale_bundle["state"]
        stale_certificate = CertificateBuilder().build(
            stale_state, "FOUND",
        )["certificate"]
        deferred = ReplayTerminalController().decide(
            stale_state, None, None, execution(),
        )
        stale_state.record_continue(deferred)
        current_truth = truth_artifact(
            stale_state, "positive_control",
            evidence_plan(stale_state.snapshot(), "FOUND"),
            semantic_truth="FOUND",
        )
        stale_terminal = ReplayTerminalController().decide(
            stale_state, "FOUND", stale_certificate, execution(),
        )
        stale_report = OracleOfflineVerifier().verify(
            current_truth, stale_state.audit_bundle(), stale_terminal,
            stale_certificate,
        )
        self.assertEqual(
            stale_report["outcome"], "CORRECT_REJECT", stale_report,
        )
        self.assertFalse(stale_report["certificate_structural_valid"])

    def test_accepted_terminal_certificate_substitution_is_false_accept(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        terminal = ReplayTerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        substituted = copy.deepcopy(certificate)
        substituted["certificate_digest"] = "e" * 64
        result = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), terminal, substituted,
        )
        self.assertEqual(result["outcome"], "FALSE_ACCEPT", result)
        self.assertFalse(result["terminal_structural_valid"])

    def test_genuine_valid_other_scope_is_wrong_scope(self):
        artifact = complete_scenario(
            "positive_control", "FOUND", episode_id="artifact-scope-a",
        )
        truth_b = complete_scenario(
            "positive_control", "FOUND", episode_id="truth-scope-b",
        )["truth"]
        state = artifact["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        terminal = ReplayTerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        result = OracleOfflineVerifier().verify(
            truth_b, state.audit_bundle(), terminal, certificate,
        )
        self.assertEqual(result["outcome"], "WRONG_SCOPE", result)
        self.assertTrue(result["certificate_structural_valid"])

    def test_no_certificate_is_unresolved(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        terminal = ReplayTerminalController().decide(
            state, "FOUND", None, execution(max_step=True),
        )
        result = OracleOfflineVerifier().verify(
            bundle["truth"], state.audit_bundle(), terminal, None,
        )
        self.assertEqual(result["outcome"], "UNRESOLVED", result)

    def test_controlled_truth_rejects_internal_inconsistency(self):
        valid = complete_scenario("positive_control", "FOUND")["truth"]
        cases = []

        overlap = copy.deepcopy(valid)
        overlap["refuted_hypothesis_ids"] = list(overlap["supported_hypothesis_ids"])
        cases.append(("CONTROLLED_TRUTH_OVERLAP", seal_controlled_artifact(overlap)))

        wrong_hypothesis = copy.deepcopy(valid)
        wrong_hypothesis["claims"][0]["hypothesis_id"] = "hyp-not-in-universe"
        cases.append(("CONTROLLED_TRUTH_HYPOTHESIS_ID", seal_controlled_artifact(wrong_hypothesis)))

        wrong_predicate = copy.deepcopy(valid)
        wrong_predicate["claims"][0]["predicate_id"] = "wrong-predicate"
        cases.append(("CONTROLLED_TRUTH_PREDICATE_ID", seal_controlled_artifact(wrong_predicate)))

        wrong_binding = copy.deepcopy(valid)
        wrong_binding["claims"][0]["binding"]["location_binding_id"] = "loc-wrong"
        cases.append(("CONTROLLED_TRUTH_BINDING", seal_controlled_artifact(wrong_binding)))

        wrong_polarity = copy.deepcopy(valid)
        for claim in wrong_polarity["claims"]:
            claim["claim"] = "OPEN"
        wrong_polarity["supported_hypothesis_ids"] = []
        cases.append(("CONTROLLED_TRUTH_UNRESOLVED", seal_controlled_artifact(wrong_polarity)))

        for code, value in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ContractViolation, code):
                    validate_controlled_truth(value)

        digest_damage = copy.deepcopy(valid)
        digest_damage["audit_trail"]["source_artifact_digest"] = "f" * 64
        with self.assertRaisesRegex(ContractViolation, "CONTROLLED_TRUTH_DIGEST"):
            validate_controlled_truth(digest_damage)

        wrong_kind_shape = copy.deepcopy(valid)
        subject = next(
            item for item in wrong_kind_shape["hypotheses"]
            if item["hypothesis_kind"] == "subject"
        )
        subject["hypothesis_kind"] = "subject_room"
        wrong_kind_shape["universe_digest"] = canonical_sha256({
            "hypotheses": wrong_kind_shape["hypotheses"],
            "obligations": wrong_kind_shape["obligations"],
            "generator_version": "proofnav.dynamic-universe.v2",
        })
        with self.assertRaisesRegex(
                ContractViolation, "CONTROLLED_HYPOTHESIS_BINDING_SHAPE"):
            validate_controlled_truth(
                seal_controlled_artifact(wrong_kind_shape),
            )

        wrong_premise = copy.deepcopy(valid)
        wrong_premise["premise_class"] = "attribute_mismatch"
        with self.assertRaisesRegex(ContractViolation, "CONTROLLED_TRUTH_PREMISE"):
            validate_controlled_truth(seal_controlled_artifact(wrong_premise))

    def test_script_truth_identity_binding_checked_but_polarity_independent(self):
        bundle = complete_scenario("positive_control", "FOUND")
        script = copy.deepcopy(bundle["script"])
        # Script polarity may be factually wrong; identity/binding may not.
        script["emissions"][0]["claim"] = "REFUTES"
        script = seal_controlled_artifact(script)
        validate_controlled_script(script, bundle["truth"])
        wrong = copy.deepcopy(script)
        wrong["emissions"][0]["hypothesis_id"] = "wrong-hypothesis"
        wrong = seal_controlled_artifact(wrong)
        with self.assertRaisesRegex(ContractViolation, "CONTROLLED_SCRIPT_BINDING"):
            validate_controlled_script(wrong, bundle["truth"])

    def test_offline_structural_path_has_no_runtime_dependency(self):
        root = Path(__file__).resolve().parents[2]
        for relative in (
                "proofnav/offline/oracle_verifier.py",
                "proofnav/offline/structural_audit.py"):
            path = root / relative
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
            self.assertFalse(
                [name for name in imports if name.startswith("proofnav.runtime")],
                relative,
            )

    def test_runtime_offline_accounting_conforms_on_revisit(self):
        state, scope, _ = empty_state(
            "entity_absent", episode_id="offline-revisit-conformance",
        )
        state.ingest_observation(controlled_observation(
            scope["episode_id"], "vp0", 0, 0, ["vp1"], [],
        ))
        state.ingest_observation(controlled_observation(
            scope["episode_id"], "vp1", 5, 1, ["vp0"], [],
        ))
        state.ingest_observation(controlled_observation(
            scope["episode_id"], "vp0", 9, 2, ["vp1"], [],
            event_id="obs-vp0-revisit",
        ))
        plan = evidence_plan(state.snapshot(), "NOT_FOUND")
        append_evaluations(state, plan, "revisit")
        truth = truth_artifact(
            state, "entity_absent", plan, semantic_truth="NOT_FOUND",
        )
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        terminal = ReplayTerminalController().decide(
            state, "NOT_FOUND", certificate, execution(),
        )
        result = OracleOfflineVerifier().verify(
            truth, state.audit_bundle(), terminal, certificate,
        )
        self.assertEqual(result["outcome"], "TRUE_ACCEPT", result)
        self.assertTrue(result["structural_valid"])
        self.assertEqual(state.snapshot()["cost_ledger"]["high_level_actions"], 2)


if __name__ == "__main__":
    unittest.main()
