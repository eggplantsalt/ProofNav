"""Entity SUPPORT/ABSTAIN adapter and binding/polarity attacks."""

import copy
import unittest

from proofnav.calibration import build_calibration_artifact
from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.perception import (
    adapt_entity_signal,
    build_calibrated_bound_evidence,
    validate_adapter_decision,
    validate_duet_signal,
)
from proofnav.runtime import M3ProofState
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


class EntityAdapterAttackTests(unittest.TestCase):

    def setUp(self):
        self.scope = m3_scope("m3-adapter")
        self.template = m3_template()
        self.signal = signal_record("m3-adapter")
        self.artifact = build_calibration_artifact(artifact_spec())
        self.state = M3ProofState(self.scope, self.template)
        self.state.ingest_observation(self.signal["observation"])
        identity = entity_query(self.state.snapshot(), "slot-a")
        self.query = self.state.register_query(
            identity["hypothesis_id"], identity["obligation_id"],
        )

    def test_no_artifact_logit_is_only_abstaining_proposal(self):
        decision = adapt_entity_signal(self.query, self.signal, None)
        self.assertEqual(decision["decision"], "ABSTAIN")
        self.assertEqual(decision["reason_code"], "MISSING_CALIBRATION_ARTIFACT")
        self.assertIsNone(decision["risk_atom_id"])

    def test_public_synthetic_signal_cannot_become_registered_authority(self):
        with self.assertRaisesRegex(
                ContractViolation, "M3_SIGNAL_NOT_REGISTERED"):
            adapt_entity_signal(self.query, self.signal, self.artifact)

    def test_resealed_forged_high_logit_cannot_become_replay_authority(self):
        signals = real_replay_signals()
        signal = copy.deepcopy(signals[-1])
        state = M3ProofState(real_scope(), real_template())
        for record in signals:
            state.ingest_observation(record["observation"])
        identity = selected_entity_query(state.snapshot(), signal)
        query = state.register_query(
            identity["hypothesis_id"], identity["obligation_id"],
        )
        selected = signal["object_scores"]["selected_index"]
        signal["object_scores"]["logits"][selected] = 1000000.0
        signal["object_scores"]["selected_statistic"] = 1000000.0
        signal.pop("signal_digest")
        signal["signal_digest"] = canonical_sha256(signal)
        # The record is internally well formed and self-sealed, but its exact
        # content was not emitted by the frozen active-only replay.
        validate_duet_signal(signal)
        with self.assertRaisesRegex(
                ContractViolation, "M3_SIGNAL_NOT_REGISTERED"):
            adapt_entity_signal(query, signal, self.artifact)

    def test_unsupported_predicates_and_refute_direction_are_sealed(self):
        for kind in ("attribute", "relation", "room_anchor", "coverage"):
            with self.subTest(kind=kind):
                query = copy.deepcopy(self.query)
                query["predicate_kind"] = kind
                decision = adapt_entity_signal(query, self.signal, self.artifact)
                self.assertEqual(decision["decision"], "ABSTAIN")
                self.assertEqual(decision["reason_code"], "UNSUPPORTED_PREDICATE")

        signals = real_replay_signals()
        signal = signals[-1]
        scope = real_scope()
        state = M3ProofState(scope, real_template())
        for record in signals:
            state.ingest_observation(record["observation"])
        identity = selected_entity_query(state.snapshot(), signal)
        query = state.register_query(
            identity["hypothesis_id"], identity["obligation_id"],
        )
        attacked = adapt_entity_signal(query, signal, self.artifact)
        attacked["decision"] = "REFUTES"
        attacked["polarity"] = "REFUTES"
        attacked["reason_code"] = "CALIBRATED_REFUTATION"
        attacked.pop("decision_digest")
        attacked["decision_digest"] = canonical_sha256(attacked)
        with self.assertRaisesRegex(ContractViolation, "M3_ADAPTER_DECISION"):
            validate_adapter_decision(attacked)

    def test_empty_all_masked_low_score_and_domain_shift_abstain(self):
        real = real_replay_signals()
        state = M3ProofState(real_scope(), real_template())
        for record in real:
            state.ingest_observation(record["observation"])
        selected = selected_entity_query(state.snapshot(), real[-1])
        selected_query = state.register_query(
            selected["hypothesis_id"], selected["obligation_id"],
        )
        low = real[1]
        low_unit = __import__(
            "proofnav.runtime.semantics", fromlist=["object_unit_id"],
        ).object_unit_id(
            low["observation"]["viewpoint"],
            low["object_scores"]["selected_proposal_id"],
        )
        low_obligation = next(
            item for item in state.snapshot()["obligations"]
            if item["predicate_kind"] == "entity"
            and item["binding_requirement"]["subject_unit_ids"] == [low_unit]
        )
        low_query = state.register_query(
            low_obligation["hypothesis_id"], low_obligation["obligation_id"],
        )
        for signal, query, expected in (
                (real[0], selected_query, "EMPTY_OR_MASKED_PROPOSALS"),
                (low, low_query, "BELOW_SUPPORT_THRESHOLD")):
            with self.subTest(expected=expected):
                decision = adapt_entity_signal(query, signal, self.artifact)
                self.assertEqual(decision["decision"], "ABSTAIN")
                self.assertEqual(decision["reason_code"], expected)

        attacks = (
            (signal_record("m3-adapter", valid_mask=[False, False]),
             "M3_SIGNAL_NOT_REGISTERED"),
            (signal_record("m3-adapter", scan="unseen-scan"),
             "CALIBRATION_DOMAIN_MISMATCH"),
        )
        for signal, expected in attacks:
            with self.subTest(expected=expected):
                if expected == "CALIBRATION_DOMAIN_MISMATCH":
                    decision = adapt_entity_signal(
                        self.query, signal, self.artifact,
                    )
                    self.assertEqual(decision["decision"], "ABSTAIN")
                    self.assertEqual(decision["reason_code"], expected)
                else:
                    with self.assertRaisesRegex(
                            ContractViolation, "M3_SIGNAL_NOT_REGISTERED"):
                        adapt_entity_signal(self.query, signal, self.artifact)

    def test_wrong_subject_binding_abstains_without_evidence(self):
        signals = real_replay_signals()
        signal = signals[-1]
        scope = real_scope()
        state = M3ProofState(scope, real_template())
        for record in signals:
            state.ingest_observation(record["observation"])
        wrong_id = next(
            value for value in signal["object_scores"]["proposal_ids"]
            if value != signal["object_scores"]["selected_proposal_id"]
        )
        unit_id = __import__(
            "proofnav.runtime.semantics", fromlist=["object_unit_id"],
        ).object_unit_id(signal["observation"]["viewpoint"], wrong_id)
        obligation = next(
            item for item in state.snapshot()["obligations"]
            if item["predicate_kind"] == "entity"
            and item["binding_requirement"]["subject_unit_ids"] == [unit_id]
        )
        wrong_query = state.register_query(
            obligation["hypothesis_id"], obligation["obligation_id"],
        )
        decision = build_calibrated_bound_evidence(
            wrong_query, signal, self.artifact,
            scope["scope_contract_id"],
        )
        self.assertEqual(decision["decision"], "ABSTAIN")
        self.assertEqual(decision["reason_code"], "SUBJECT_BINDING_MISMATCH")
        self.assertNotIn("evidence", decision)

    def test_template_instruction_and_signal_digest_tamper_fail_closed(self):
        attacks = []
        template = copy.deepcopy(self.signal)
        template["template_digest"] = "f" * 64
        attacks.append((template, "M3_SIGNAL_DIGEST"))
        instruction = copy.deepcopy(self.signal)
        instruction["instruction_digest"] = "f" * 64
        attacks.append((instruction, "M3_SIGNAL_INSTRUCTION"))
        observation = copy.deepcopy(self.signal)
        observation["observation"]["instruction"] = "changed"
        attacks.append((observation, "M3_SIGNAL_OBSERVATION_DIGEST"))
        for attacked, code in attacks:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ContractViolation, code):
                    adapt_entity_signal(self.query, attacked, self.artifact)

    def test_resealed_signal_model_identity_change_breaks_artifact_match(self):
        for field in self.signal["model_identity"]:
            with self.subTest(field=field):
                attacked = copy.deepcopy(self.signal)
                attacked["model_identity"][field] = "f" * 64
                attacked.pop("signal_digest")
                attacked["signal_digest"] = canonical_sha256(attacked)
                validate_duet_signal(attacked)
                with self.assertRaisesRegex(
                        ContractViolation, "M3_ARTIFACT_MODEL_IDENTITY"):
                    adapt_entity_signal(self.query, attacked, self.artifact)

    def test_adapter_nan_and_missing_field_fail_closed(self):
        nonfinite = copy.deepcopy(self.signal)
        nonfinite["object_scores"]["logits"][0] = float("nan")
        with self.assertRaisesRegex(ContractViolation, "M3_NONFINITE"):
            adapt_entity_signal(self.query, nonfinite, self.artifact)

        missing = copy.deepcopy(self.signal)
        missing.pop("content_digests")
        with self.assertRaisesRegex(ContractViolation, "M3_MISSING_FIELDS"):
            adapt_entity_signal(self.query, missing, self.artifact)


if __name__ == "__main__":
    unittest.main()
