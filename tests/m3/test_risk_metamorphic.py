"""Small exhaustive/metamorphic checks for derived M3 certificate risk."""

import copy
import itertools
import unittest

from proofnav.calibration import (
    build_calibration_artifact,
    compose_certificate_risk,
)
from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.perception import build_calibrated_bound_evidence
from proofnav.runtime import M3ProofState
from tests.m3.fixtures import (
    artifact_spec, real_replay_signals, real_scope, real_template,
    selected_entity_query,
)


def reseal_atom(atom):
    value = copy.deepcopy(atom)
    value.pop("atom_digest", None)
    value["atom_digest"] = canonical_sha256(value)
    return value


class RiskCompositionMetamorphicTests(unittest.TestCase):

    def _wrapper(self, episode_id="m3-risk"):
        del episode_id
        scope = real_scope(1.0)
        signals = real_replay_signals()
        signal = signals[-1]
        state = M3ProofState(scope, real_template())
        for record in signals:
            state.ingest_observation(record["observation"])
        identity = selected_entity_query(state.snapshot(), signal)
        query = state.register_query(
            identity["hypothesis_id"], identity["obligation_id"],
        )
        artifact = build_calibration_artifact(artifact_spec())
        wrapper = build_calibrated_bound_evidence(
            query, signal, artifact, scope["scope_contract_id"],
        )
        self.assertEqual(wrapper["adapter_decision"]["decision"], "SUPPORTS")
        return scope, wrapper

    def test_order_permutation_is_risk_invariant(self):
        scope, first = self._wrapper("m3-risk-order-a")
        second = copy.deepcopy(first)
        expected = compose_certificate_risk([first, second], "FOUND", scope)
        for permutation in itertools.permutations([first, second]):
            with self.subTest(order=[item["evidence"]["evidence_id"]
                                     for item in permutation]):
                self.assertEqual(
                    compose_certificate_risk(list(permutation), "FOUND", scope),
                    expected,
                )
        self.assertAlmostEqual(expected["upper_bound"], 1.0 / 3.0)

    def test_same_family_reuse_deduplicates_but_arbitrary_group_does_not(self):
        scope, first = self._wrapper("m3-risk-family-a")
        same_family = copy.deepcopy(first)
        self.assertAlmostEqual(
            compose_certificate_risk([first, same_family], "FOUND", scope)["upper_bound"],
            1.0 / 3.0,
        )

        attacked = copy.deepcopy(first)
        attacked["risk_atom"]["family_key"] = "caller:independent"
        attacked["risk_atom"] = reseal_atom(attacked["risk_atom"])
        # A caller cannot manufacture a second calibrated family from a
        # shared/different dependency-group string or a resealed atom.
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_WRAPPER_RECOMPUTE"):
            compose_certificate_risk([first, attacked], "FOUND", scope)

    def test_revisit_does_not_reduce_risk(self):
        scope, first = self._wrapper("m3-risk-revisit")
        repeated = copy.deepcopy(first)
        for count in range(1, 6):
            with self.subTest(count=count):
                risk = compose_certificate_risk(
                    [first] + [repeated] * count, "FOUND", scope,
                )
                self.assertEqual(risk["upper_bound"], 1.0 / 3.0)

    def test_polarity_swap_and_not_found_are_rejected(self):
        scope, wrapper = self._wrapper("m3-risk-polarity")
        attacked = copy.deepcopy(wrapper)
        attacked["risk_atom"]["polarity"] = "REFUTES"
        attacked["risk_atom"]["event_type"] = "false_refutation"
        attacked["risk_atom"] = reseal_atom(attacked["risk_atom"])
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_WRAPPER_RECOMPUTE"):
            compose_certificate_risk([attacked], "FOUND", scope)
        with self.assertRaisesRegex(ContractViolation, "M3_NOT_FOUND_SEALED"):
            compose_certificate_risk([wrapper], "NOT_FOUND", scope)

    def test_missing_or_tampered_atom_fails_closed(self):
        scope, wrapper = self._wrapper("m3-risk-atom")
        missing = copy.deepcopy(wrapper)
        missing.pop("risk_atom")
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_WRAPPER_RECOMPUTE"):
            compose_certificate_risk([missing], "FOUND", scope)

        attacked = copy.deepcopy(wrapper)
        attacked["risk_atom"]["upper_bound"] = 0.0
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_WRAPPER_RECOMPUTE"):
            compose_certificate_risk([attacked], "FOUND", scope)

    def test_risk_uses_registered_bound_never_caller_upper_bound(self):
        scope, first = self._wrapper("m3-risk-authority")
        risk = compose_certificate_risk([first], "FOUND", scope)
        self.assertEqual(risk["upper_bound"], 1.0 / 3.0)
        self.assertNotEqual(risk["upper_bound"], 0.0)
        self.assertEqual(set(risk), {
            "decision", "risk_type", "upper_bound", "budget",
            "calibration_version", "composition_version",
        })

    def test_scope_cannot_misname_selected_calibration_artifact(self):
        scope, wrapper = self._wrapper("m3-risk-version-binding")
        attacked_scope = copy.deepcopy(scope)
        attacked_scope["calibration_version"] = (
            "proofnav.calibration-artifact.v1:" + "f" * 64
        )
        with self.assertRaisesRegex(
                ContractViolation, "M3_RISK_CALIBRATION_VERSION"):
            compose_certificate_risk([wrapper], "FOUND", attacked_scope)


if __name__ == "__main__":
    unittest.main()
