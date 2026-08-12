import copy
import unittest

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS
from proofnav.offline.oracle_evidence import (
    ControlledProofState, ReplayOnlineVerifier,
)
from proofnav.offline.structural_audit import (
    audit_certificate, recompute_offline_state, validate_audit_bundle,
)
from proofnav.runtime import CertificateBuilder
from proofnav.runtime.certificate import _coverage_item, _finalize
from proofnav.runtime.semantics import registered_admission_profile
from tests.m2.fixtures import (
    append_evaluations, proof_template, risk_claims, scope_value,
    state_with_graph, truth_artifact,
)


class RelationUniverseCompletenessTests(unittest.TestCase):

    @staticmethod
    def _single_visible_subject_state(episode_id):
        return state_with_graph(
            "relation_mismatch", graph="closed_one",
            object_ids={"vp0": ["subject"]}, episode_id=episode_id,
        )[0]

    def test_subject_anchor_residual_blocks_not_until_covered(self):
        state = self._single_visible_subject_state("relation-anchor-residual")
        snapshot = state.snapshot()
        hypotheses = {
            item["hypothesis_id"]: item for item in snapshot["hypotheses"]
        }
        by_kind = {
            item["hypothesis_kind"]: item for item in snapshot["hypotheses"]
        }
        self.assertEqual(set(by_kind), {"anchor_residual", "location_residual"})
        self.assertNotIn("subject_relation", {
            item["hypothesis_kind"] for item in snapshot["hypotheses"]
        })

        anchor = by_kind["anchor_residual"]
        self.assertTrue(anchor["binding"]["subject_unit_ids"])
        self.assertIsNotNone(anchor["binding"]["subject_binding_id"])
        self.assertEqual(anchor["binding"]["anchor_unit_ids"], [])
        self.assertIsNone(anchor["binding"]["anchor_binding_id"])
        anchor_obligation = next(
            item for item in snapshot["obligations"]
            if item["hypothesis_id"] == anchor["hypothesis_id"]
        )
        self.assertEqual(anchor_obligation["predicate_kind"], "coverage")

        # Closing only the generic location remainder must not erase the
        # subject-conditioned possibility of an unenumerated relation anchor.
        location_obligation = next(
            item for item in snapshot["obligations"]
            if hypotheses[item["hypothesis_id"]]["hypothesis_kind"]
            == "location_residual"
        )
        append_evaluations(
            state, {location_obligation["obligation_id"]: "REFUTES"},
            "location-covered",
        )
        incomplete = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(incomplete["status"], "UNRESOLVED", incomplete)
        self.assertIn(
            anchor["hypothesis_id"],
            incomplete["feedback"]["uncovered_hypothesis_ids"],
        )

        append_evaluations(
            state, {anchor_obligation["obligation_id"]: "REFUTES"},
            "anchor-covered",
        )
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "CERTIFICATE", outcome)
        certificate = outcome["certificate"]
        self.assertTrue(
            ReplayOnlineVerifier().verify(state, certificate)["accepted"],
        )

        bundle = state.audit_bundle()
        offline_state = validate_audit_bundle(bundle)
        self.assertEqual(offline_state, state.snapshot())
        self.assertTrue(
            audit_certificate(bundle, certificate, state=offline_state)["valid"],
        )

        evaluations = {
            location_obligation["obligation_id"]: "REFUTES",
            anchor_obligation["obligation_id"]: "REFUTES",
        }
        truth = truth_artifact(
            state, "relation_mismatch", evaluations,
            semantic_truth="NOT_FOUND",
        )
        self.assertIn(
            anchor["hypothesis_id"], truth["refuted_hypothesis_ids"],
        )

    def test_anchor_residual_cannot_be_selected_for_found(self):
        state = self._single_visible_subject_state("relation-residual-not-found")
        snapshot = state.snapshot()
        residual_ids = {
            item["hypothesis_id"] for item in snapshot["hypotheses"]
            if item["hypothesis_kind"] in {
                "anchor_residual", "location_residual",
            }
        }
        evaluations = {
            item["obligation_id"]: "SUPPORTS"
            for item in snapshot["obligations"]
            if item["hypothesis_id"] in residual_ids
        }
        append_evaluations(state, evaluations, "residual-support")
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED", outcome)
        self.assertIn(
            "POSITIVE_PATH_INCOMPLETE", outcome["feedback"]["reason_codes"],
        )

        # A malicious builder cannot bypass that rule: construct an otherwise
        # self-consistent positive payload around the anchor residual and let
        # both online and independent offline verification reject it.
        snapshot = state.snapshot()
        anchor = next(
            item for item in snapshot["hypotheses"]
            if item["hypothesis_kind"] == "anchor_residual"
        )
        obligation = next(
            item for item in snapshot["obligations"]
            if item["hypothesis_id"] == anchor["hypothesis_id"]
        )
        evidence_ids = obligation["support_evidence_ids"]
        payload = {
            "hypothesis": copy.deepcopy(anchor),
            "binding": copy.deepcopy(anchor["binding"]),
            "true_path": [
                _coverage_item(anchor, obligation, evidence_ids),
            ],
            "unresolved_obligation_ids": [],
        }
        bundle = state.audit_bundle()
        forged = _finalize(
            bundle, snapshot, "positive", "FOUND",
            [anchor["hypothesis_id"]], [obligation["obligation_id"]],
            evidence_ids, payload,
        )
        online = ReplayOnlineVerifier().verify(state, forged)
        self.assertEqual(online["status"], "REJECT", online)
        self.assertIn("RESIDUAL_CANNOT_PROVE_FOUND", online["reason_codes"])
        offline = audit_certificate(
            bundle, forged, state=validate_audit_bundle(bundle),
        )
        self.assertFalse(offline["valid"])
        self.assertIn("OFFLINE_POSITIVE_RESIDUAL", offline["reason_codes"])

    def test_multiple_or_mixed_anchored_predicates_fail_closed(self):
        scope = scope_value("anchored-template-cardinality")
        templates = []

        multiple_rooms = proof_template("room_anchor_mismatch")
        multiple_rooms["predicates"].append({
            "predicate_id": "pred-second-room",
            "kind": "room_anchor",
            "necessary": True,
            "anchor_role": None,
            "spatial_anchor_id": "instruction-room:hallway",
        })
        templates.append(multiple_rooms)

        mixed = proof_template("relation_mismatch")
        mixed["predicates"].append({
            "predicate_id": "pred-mixed-room",
            "kind": "room_anchor",
            "necessary": True,
            "anchor_role": None,
            "spatial_anchor_id": "instruction-room:kitchen",
        })
        templates.append(mixed)

        for template in templates:
            with self.subTest(template=template["template_id"]):
                with self.assertRaisesRegex(
                        ContractViolation, "TEMPLATE_ANCHORED_CARDINALITY"):
                    ControlledProofState(scope, template, risk_claims(scope))

                base = {
                    "schema_version": SCHEMA_VERSIONS["audit_bundle"],
                    "scope": copy.deepcopy(scope),
                    "template": copy.deepcopy(template),
                    "admission_profile": registered_admission_profile(True),
                    "risk_claims": risk_claims(scope),
                    "transitions": [],
                }
                with self.assertRaisesRegex(
                        ContractViolation,
                        "OFFLINE_TEMPLATE_ANCHORED_CARDINALITY"):
                    recompute_offline_state(base)

        optional = proof_template("relation_mismatch")
        next(
            item for item in optional["predicates"]
            if item["kind"] == "relation"
        )["necessary"] = False
        with self.assertRaisesRegex(
                ContractViolation, "TEMPLATE_ANCHORED_NECESSARY"):
            ControlledProofState(scope, optional, risk_claims(scope))


if __name__ == "__main__":
    unittest.main()
