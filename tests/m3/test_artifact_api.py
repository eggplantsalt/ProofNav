"""Focused public-API checks for the M3 artifact/adapter vertical slice."""

import copy
import unittest

from proofnav.calibration import (
    build_calibration_artifact,
    compose_certificate_risk,
    validate_risk_atom,
)
from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.perception import build_calibrated_bound_evidence
from proofnav.runtime import CertificateBuilder, M3OnlineVerifier, M3ProofState
from tests.m3.fixtures import (
    artifact_spec, real_replay_signals, real_scope, real_template,
    selected_entity_query,
)


class M3ArtifactApiTests(unittest.TestCase):

    def _chain(self, episode="m3-artifact-api"):
        del episode
        scope = real_scope(1.0)
        signals = real_replay_signals()
        signal = signals[-1]
        artifact = build_calibration_artifact(artifact_spec())
        state = M3ProofState(scope, real_template())
        for record in signals:
            state.ingest_observation(record["observation"])
        identity = selected_entity_query(state.snapshot(), signal)
        query = state.register_query(
            identity["hypothesis_id"], identity["obligation_id"],
        )
        wrapper = build_calibrated_bound_evidence(
            query, signal, artifact, scope["scope_contract_id"],
        )
        return scope, state, wrapper

    def test_real_wrapper_state_certificate_verifier_found_chain(self):
        _, state, wrapper = self._chain()
        validate_risk_atom(wrapper["risk_atom"], wrapper)
        state.append_evidence(wrapper)
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertEqual(outcome["status"], "CERTIFICATE")
        self.assertEqual(
            outcome["certificate"]["risk_claim"]["upper_bound"], 1.0 / 3.0,
        )
        report = M3OnlineVerifier().verify(state, outcome["certificate"])
        self.assertTrue(report["accepted"])
        self.assertEqual(report["reason_codes"], [])

    def test_decision_and_atom_resealing_cannot_change_authority(self):
        scope, _, wrapper = self._chain("m3-artifact-tamper")
        attacked = copy.deepcopy(wrapper)
        attacked["adapter_decision"]["decision_id"] = "decision-forged"
        attacked["adapter_decision"].pop("decision_digest")
        attacked["adapter_decision"]["decision_digest"] = canonical_sha256(
            attacked["adapter_decision"],
        )
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_WRAPPER_RECOMPUTE"):
            compose_certificate_risk([attacked], "FOUND", scope)

        attacked = copy.deepcopy(wrapper)
        attacked["risk_atom"]["family_key"] = "caller-family"
        attacked["risk_atom"].pop("atom_digest")
        attacked["risk_atom"]["atom_digest"] = canonical_sha256(
            attacked["risk_atom"],
        )
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_WRAPPER_RECOMPUTE"):
            compose_certificate_risk([attacked], "FOUND", scope)

    def test_aggregate_bound_cannot_underreport_observed_familywise_error(self):
        spec = artifact_spec()
        spec["aggregate_counts"] = {"scans": 6, "examples": 54, "errors": 6}
        spec["risk_bound"]["upper_bound"] = 0.5
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_BOUND_UNDERREPORT"):
            build_calibration_artifact(spec)


if __name__ == "__main__":
    unittest.main()
