"""Attacks on the explicit M3 profile before calibrated evidence admission."""

import copy
import inspect
import unittest

from proofnav.contracts import ContractViolation
from proofnav.runtime import (
    CertificateBuilder,
    M3OnlineVerifier,
    M3ProofState,
    OnlineVerifier,
    ProofState,
)
from tests.m2.fixtures import controlled_observation, risk_claims
from tests.m3.fixtures import (
    DEFAULT_RUNTIME_SCAN, m3_observation, m3_scope, m3_template,
)


class M3RuntimeBoundaryTests(unittest.TestCase):

    def test_caller_cannot_supply_m3_risk_upper_bound(self):
        scope = m3_scope("m3-caller-risk")
        template = m3_template()
        self.assertEqual(
            list(inspect.signature(M3ProofState).parameters),
            ["scope", "template"],
        )
        with self.assertRaises(TypeError):
            M3ProofState(scope, template, risk_claims(scope))

        state = M3ProofState(scope, template)
        self.assertEqual(state.audit_bundle()["risk_claims"], {})
        self.assertEqual(state.snapshot()["risk_claims"], {})

        # Even a perfectly resealed caller mutation is not an M3 bundle.
        attacked = state.audit_bundle()
        attacked["risk_claims"] = risk_claims(scope)
        attacked.pop("bundle_digest")
        from proofnav.contracts import canonical_sha256
        attacked["bundle_digest"] = canonical_sha256(attacked)
        report = M3OnlineVerifier().verify(attacked, None)
        self.assertEqual(report["status"], "REJECT", report)
        self.assertIn("M3_CALLER_RISK_FORBIDDEN", report["reason_codes"])

    def test_m3_profile_requires_the_explicit_verifier(self):
        state = M3ProofState(m3_scope("m3-profile-gate"), m3_template())
        m3_report = M3OnlineVerifier().verify(state, None)
        self.assertEqual(m3_report["status"], "DEFER", m3_report)
        self.assertIn("CERTIFICATE_ABSENT", m3_report["reason_codes"])

        legacy_report = OnlineVerifier().verify(state, None)
        self.assertEqual(legacy_report["status"], "REJECT", legacy_report)
        self.assertIn("M3_SOURCE_FORBIDDEN", legacy_report["reason_codes"])

    def test_empty_proposals_leave_location_residual_open(self):
        episode_id = "m3-empty-proposals"
        state = M3ProofState(m3_scope(episode_id), m3_template())
        state.ingest_observation(m3_observation(episode_id, object_ids=[]))
        snapshot = state.snapshot()
        self.assertEqual(
            [item["hypothesis_kind"] for item in snapshot["hypotheses"]],
            ["location_residual"],
        )
        residual = snapshot["obligations"][0]
        self.assertEqual(residual["predicate_kind"], "coverage")
        self.assertEqual(residual["status"], "OPEN")
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED", outcome)
        self.assertIn("REFUTATION_COVER_INCOMPLETE", outcome["feedback"]["reason_codes"])

    def test_same_object_id_across_viewpoints_does_not_link_identity(self):
        episode_id = "m3-id-equality"
        state = M3ProofState(m3_scope(episode_id), m3_template())
        first = controlled_observation(
            episode_id, viewpoint="vp0", event_seq=0, step=0,
            candidates=["vp1"], object_ids=["same-id"],
        )
        second = controlled_observation(
            episode_id, viewpoint="vp1", event_seq=5, step=1,
            candidates=["vp0"], object_ids=["same-id"],
        )
        for observation in (first, second):
            observation["scan"] = DEFAULT_RUNTIME_SCAN
            observation["audit_trail"] = {
                "producer": "proofnav.adapters.sanitize_duet_observation",
                "source_schema": "duet.reverie._get_obs@frozen-m0",
            }
            state.ingest_observation(observation)

        subjects = [
            item for item in state.snapshot()["hypotheses"]
            if item["hypothesis_kind"] == "subject"
        ]
        self.assertEqual(len(subjects), 2)
        self.assertTrue(all(
            len(item["binding"]["subject_unit_ids"]) == 1
            for item in subjects
        ))
        with self.assertRaisesRegex(
                ContractViolation, "IDENTITY_LINK_NOT_REGISTERED"):
            state.link_identity({"claim": "SAME_ENTITY", "because": "same-id"})

    def test_instruction_change_makes_m3_observation_fail_closed(self):
        episode_id = "m3-instruction-stale"
        state = M3ProofState(m3_scope(episode_id), m3_template())
        observation = m3_observation(episode_id)
        observation["instruction"] = "Find a different target."
        before = state.audit_bundle()
        with self.assertRaisesRegex(
                ContractViolation, "TEMPLATE_INSTRUCTION_MISMATCH"):
            state.ingest_observation(observation)
        self.assertEqual(state.audit_bundle(), before)

    def test_gt_alias_cannot_enter_m3_event_log(self):
        episode_id = "m3-gt-firewall"
        state = M3ProofState(m3_scope(episode_id), m3_template())
        for poison in (
            {"gt_obj_id": "hidden"},
            {"obj2vps": {"hidden": ["vp0"]}},
            {"evaluator_truth": "FOUND"},
        ):
            with self.subTest(poison=next(iter(poison))):
                observation = m3_observation(episode_id)
                observation.update(copy.deepcopy(poison))
                before = state.audit_bundle()
                with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
                    state.ingest_observation(observation)
                self.assertEqual(state.audit_bundle(), before)

    def test_m3_off_uses_unchanged_m2_production_zero_profile(self):
        scope = m3_scope("m3-off-legacy")
        # M2's constructor and caller-owned controlled risk contract remain
        # available only through the old, explicit class.
        state = ProofState(scope, m3_template(), risk_claims(scope))
        bundle = state.audit_bundle()
        self.assertEqual(
            bundle["admission_profile"]["profile_id"],
            "proofnav.admission.production-zero.v2",
        )
        self.assertEqual(
            bundle["admission_profile"]["evidence_mode"], "production_zero",
        )
        report = OnlineVerifier().verify(state, None)
        self.assertEqual(report["status"], "DEFER", report)
        self.assertNotIn("M3_SOURCE_FORBIDDEN", report["reason_codes"])


if __name__ == "__main__":
    unittest.main()
