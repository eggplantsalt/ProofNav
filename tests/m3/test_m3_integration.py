"""Full M3 successor admission, certificate, terminal, and replay attacks."""

import copy
import unittest

from proofnav.calibration import build_calibration_artifact
from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.offline.structural_audit import (
    audit_certificate,
    audit_terminal,
    structural_result,
)
from proofnav.perception import adapt_entity_signal, build_calibrated_bound_evidence
from proofnav.runtime import (
    CertificateBuilder,
    M3OnlineVerifier,
    M3ProofState,
    M3TerminalController,
)
from tests.m2.fixtures import execution, reseal
from tests.m3.fixtures import (
    artifact_spec,
    entity_query,
    m3_scope,
    m3_template,
    real_replay_signals,
    real_scope,
    real_template,
    selected_entity_query,
    signal_record,
)


class M3IntegrationAttackTests(unittest.TestCase):

    def _chain(self, episode_id="m3-integration", budget=1.0):
        del episode_id
        scope = real_scope(budget)
        template = real_template()
        signals = real_replay_signals()
        signal = signals[-1]
        artifact = build_calibration_artifact(artifact_spec())
        state = M3ProofState(scope, template)
        for record in signals:
            state.ingest_observation(record["observation"])
        identity = selected_entity_query(state.snapshot(), signal)
        query = state.register_query(
            identity["hypothesis_id"], identity["obligation_id"],
        )
        wrapper = build_calibrated_bound_evidence(
            query, signal, artifact, scope["scope_contract_id"],
        )
        return scope, template, signal, artifact, state, query, wrapper

    def test_non_oracle_support_reaches_verifier_gated_found_terminal(self):
        _, _, _, _, state, _, wrapper = self._chain()
        state.append_evidence(wrapper)
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertEqual(outcome["status"], "CERTIFICATE", outcome)
        certificate = outcome["certificate"]
        self.assertEqual(certificate["risk_claim"]["upper_bound"], 1.0 / 3.0)
        report = M3OnlineVerifier().verify(state, certificate)
        self.assertEqual(report["status"], "ACCEPT", report)
        terminal = M3TerminalController().decide(
            state, "FOUND", certificate, execution(duet_stop=True),
        )
        self.assertEqual(terminal["directive"], "ACCEPT_FOUND", terminal)
        self.assertEqual(
            terminal["accepted_certificate_digest"],
            certificate["certificate_digest"],
        )

        # The offline structural implementation independently accepts the
        # raw transition bundle, certificate, and terminal identity.
        structure = structural_result(state.audit_bundle())
        self.assertTrue(structure["valid"], structure)
        cert_audit = audit_certificate(
            state.audit_bundle(), certificate, state=structure["state"],
        )
        self.assertTrue(cert_audit["valid"], cert_audit)
        terminal_audit = audit_terminal(
            structure["state"], terminal, certificate,
        )
        self.assertTrue(terminal_audit["valid"], terminal_audit)

    def test_certificate_caller_risk_reduction_rejected_even_if_resealed(self):
        _, _, _, _, state, _, wrapper = self._chain("m3-cert-risk")
        state.append_evidence(wrapper)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        attacked = copy.deepcopy(certificate)
        attacked["risk_claim"]["upper_bound"] = 0.0
        attacked = reseal(attacked)
        report = M3OnlineVerifier().verify(state, attacked)
        self.assertEqual(report["status"], "REJECT", report)
        self.assertIn("RISK_CLAIM_MISMATCH", report["reason_codes"])

    def test_unregistered_resealed_artifact_fails_adapter_state_online_offline(self):
        scope, _, signal, _, state, query, wrapper = self._chain(
            "m3-unregistered-artifact",
        )
        spec = artifact_spec()
        spec["risk_bound"]["upper_bound"] = 0.01
        spec["aggregate_counts"]["errors"] = 0
        forged = build_calibration_artifact(spec)

        with self.assertRaisesRegex(
                ContractViolation, "M3_ARTIFACT_NOT_REGISTERED"):
            adapt_entity_signal(query, signal, forged)

        attacked_wrapper = copy.deepcopy(wrapper)
        attacked_wrapper["calibration_artifact"] = forged
        with self.assertRaisesRegex(
                ContractViolation, "M3_ARTIFACT_NOT_REGISTERED"):
            state.append_evidence(attacked_wrapper)

        # Start from a valid admitted transition, then replace its artifact
        # with the independently sealed candidate and reseal the raw event
        # chain.  Runtime and offline folds both consult the same code-owned
        # trust root, but independently reconstruct all evidence semantics.
        state.append_evidence(wrapper)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        attacked_bundle = state.audit_bundle()
        transition = attacked_bundle["transitions"][-1]
        self.assertEqual(transition["event_type"], "EVIDENCE")
        transition["payload"]["calibration_artifact"] = forged
        transition["payload_digest"] = canonical_sha256(transition["payload"])
        transition.pop("transition_digest")
        transition["transition_digest"] = canonical_sha256(transition)
        attacked_bundle.pop("bundle_digest")
        attacked_bundle["bundle_digest"] = canonical_sha256(attacked_bundle)

        online = M3OnlineVerifier().verify(attacked_bundle, certificate)
        self.assertEqual(online["status"], "REJECT", online)
        self.assertIn("M3_ARTIFACT_NOT_REGISTERED", online["reason_codes"])
        offline = structural_result(attacked_bundle)
        self.assertFalse(offline["valid"], offline)
        self.assertEqual(
            offline["reason_codes"], ["OFFLINE_M3_ARTIFACT_NOT_REGISTERED"],
        )

    def test_state_admission_recomputes_every_nested_authority(self):
        attacks = (
            ("signal", lambda wrapper: wrapper["signal"].__setitem__(
                "template_digest", "f" * 64)),
            ("artifact", lambda wrapper: wrapper["calibration_artifact"][
                "risk_bound"].__setitem__("upper_bound", 0.0)),
            ("decision", lambda wrapper: wrapper["adapter_decision"].__setitem__(
                "reason_code", "CALLER_SUPPORT")),
            ("atom", lambda wrapper: wrapper["risk_atom"].__setitem__(
                "upper_bound", 0.0)),
            ("binding", lambda wrapper: wrapper["evidence"].__setitem__(
                "unit_id", "objunit-wrong")),
            ("subject-binding", lambda wrapper: wrapper["binding"].__setitem__(
                "subject_unit_ids", ["objunit-wrong"])),
            ("anchor-binding", lambda wrapper: wrapper["binding"].update({
                "anchor_binding_id": "subject-forged",
                "anchor_unit_ids": ["objunit-forged"],
            })),
            ("location-binding", lambda wrapper: wrapper["binding"].__setitem__(
                "location_binding_id", "loc-wrong")),
            ("room-binding", lambda wrapper: wrapper["binding"].__setitem__(
                "spatial_anchor_id", "instruction-room:forged")),
            ("dependency", lambda wrapper: wrapper["evidence"].__setitem__(
                "dependency_group", "caller:independent")),
            ("family", lambda wrapper: wrapper["risk_atom"].__setitem__(
                "family_key", "caller:independent")),
            ("polarity", lambda wrapper: wrapper["evidence"].__setitem__(
                "claim", "REFUTES")),
        )
        for label, mutate in attacks:
            with self.subTest(label=label):
                _, _, _, _, state, _, wrapper = self._chain(
                    "m3-admission-" + label,
                )
                attacked = copy.deepcopy(wrapper)
                mutate(attacked)
                before = state.audit_bundle()
                with self.assertRaises(ContractViolation):
                    state.append_evidence(attacked)
                self.assertEqual(state.audit_bundle(), before)

    def test_revocation_removes_authority_but_preserves_cost_and_history(self):
        _, _, _, _, state, _, wrapper = self._chain("m3-revoke")
        state.append_evidence(wrapper)
        before = state.snapshot()
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        state.revoke_evidence(wrapper["evidence"]["evidence_id"], "adapter-recall")
        after = state.snapshot()
        self.assertEqual(after["active_bound_evidence"], [])
        self.assertGreater(after["ledger_event_count"], before["ledger_event_count"])
        self.assertGreaterEqual(
            after["cost_ledger"]["storage_bytes"],
            before["cost_ledger"]["storage_bytes"],
        )
        self.assertEqual(
            CertificateBuilder().build(state, "FOUND")["status"], "UNRESOLVED",
        )
        report = M3OnlineVerifier().verify(state, certificate)
        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any(code.startswith("STALE_")
                            for code in report["reason_codes"]), report)

    def test_duplicate_semantic_evidence_cannot_be_recounted(self):
        _, _, _, _, state, _, wrapper = self._chain("m3-duplicate")
        state.append_evidence(wrapper)
        attacked = copy.deepcopy(wrapper)
        attacked["evidence"]["evidence_id"] = "evidence-caller-duplicate"
        # Caller cannot update all derived decision/atom identities to create
        # a second independent observation from the same signal/query.
        with self.assertRaises(ContractViolation):
            state.append_evidence(attacked)
        self.assertEqual(len(state.snapshot()["active_bound_evidence"]), 1)

    def test_repeated_certificate_build_reuses_evidence_without_new_cost(self):
        _, _, _, _, state, _, wrapper = self._chain("m3-cert-reuse")
        state.append_evidence(wrapper)
        before = state.snapshot()
        first = CertificateBuilder().build(state, "FOUND")["certificate"]
        second = CertificateBuilder().build(state, "FOUND")["certificate"]
        after = state.snapshot()
        self.assertEqual(first, second)
        self.assertEqual(first["evidence_ids"], [wrapper["evidence"]["evidence_id"]])
        self.assertEqual(after["cost_ledger"], before["cost_ledger"])
        self.assertEqual(after["ledger_event_count"], before["ledger_event_count"])

    def test_unregistered_artifact_successor_cannot_stale_old_certificate(self):
        scope, _, signal, _, state, query, first = self._chain(
            "m3-artifact-successor",
        )
        state.append_evidence(first)
        old = CertificateBuilder().build(state, "FOUND")["certificate"]
        spec = artifact_spec()
        spec["calibration_parameters"]["support_threshold"] = 3.5
        candidate = build_calibration_artifact(spec)
        with self.assertRaisesRegex(
                ContractViolation, "M3_ARTIFACT_NOT_REGISTERED"):
            build_calibrated_bound_evidence(
                query, signal, candidate, scope["scope_contract_id"],
            )
        accepted = M3OnlineVerifier().verify(state, old)
        self.assertEqual(accepted["status"], "ACCEPT", accepted)

    def test_not_found_and_residual_coverage_remain_sealed(self):
        _, _, _, _, state, _, wrapper = self._chain("m3-not-sealed")
        state.append_evidence(wrapper)
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED", outcome)
        self.assertIn("M3_NOT_FOUND_SEALED", outcome["feedback"]["reason_codes"])
        residuals = [
            item for item in state.snapshot()["obligations"]
            if item["predicate_kind"] == "coverage"
        ]
        self.assertTrue(residuals)
        self.assertTrue(all(item["status"] == "OPEN" for item in residuals))

    def test_relation_anchor_residual_remains_open_under_m3_profile(self):
        episode_id = "m3-anchor-residual"
        scope = m3_scope(episode_id)
        template = m3_template("relation_mismatch")
        signal = signal_record(episode_id, proposal_ids=["subject"])
        # Rebind the signal to the relation template; it remains a proposal
        # only because relation evidence itself is sealed.
        signal["template_digest"] = canonical_sha256(template)
        signal.pop("signal_digest")
        signal["signal_digest"] = canonical_sha256(signal)
        state = M3ProofState(scope, template)
        state.ingest_observation(signal["observation"])
        anchor_residuals = [
            item for item in state.snapshot()["hypotheses"]
            if item["hypothesis_kind"] == "anchor_residual"
        ]
        self.assertTrue(anchor_residuals)
        for hypothesis in anchor_residuals:
            obligations = [
                item for item in state.snapshot()["obligations"]
                if item["hypothesis_id"] == hypothesis["hypothesis_id"]
            ]
            self.assertEqual([item["predicate_kind"] for item in obligations],
                             ["coverage"])
            self.assertEqual(obligations[0]["status"], "OPEN")
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertIn("M3_NOT_FOUND_SEALED", outcome["feedback"]["reason_codes"])

    def test_artifact_template_interface_change_makes_old_artifact_stale(self):
        _, _, signal, _, state, query, wrapper = self._chain("m3-stale")
        for field in ("interface_digest", "checkpoint_digest", "feature_digest"):
            with self.subTest(field=field):
                attacked = copy.deepcopy(wrapper)
                attacked["signal"]["model_identity"][field] = "f" * 64
                attacked["signal"].pop("signal_digest")
                attacked["signal"]["signal_digest"] = canonical_sha256(
                    attacked["signal"],
                )
                before = state.audit_bundle()
                with self.assertRaises(ContractViolation):
                    state.append_evidence(attacked)
                self.assertEqual(state.audit_bundle(), before)

        # A new code-owned template changes query IDs and the signal's exact
        # template identity; an old query/evidence cannot be replayed.
        other_template = m3_template("attribute_mismatch")
        self.assertNotEqual(signal["template_digest"], canonical_sha256(other_template))
        self.assertEqual(query["predicate_kind"], "entity")


if __name__ == "__main__":
    unittest.main()
