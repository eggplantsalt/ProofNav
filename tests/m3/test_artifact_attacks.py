"""Calibration identity, aggregate-only, split, and domain attacks."""

import copy
import unittest

from proofnav.calibration import (
    build_calibration_artifact,
    load_registered_calibration_artifact,
    registered_calibration_artifacts,
    validate_calibration_artifact,
    validate_registered_calibration_artifact,
)
from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.offline import build_scan_familywise_artifact
from tests.m3.fixtures import (
    DEFAULT_CALIBRATION_SCAN,
    DEFAULT_RUNTIME_SCAN,
    REGISTERED_ARTIFACT_DIGEST,
    artifact_spec,
    changed,
    signal_record,
)


class CalibrationArtifactAttackTests(unittest.TestCase):

    def setUp(self):
        self.signal = signal_record()
        self.artifact = build_calibration_artifact(artifact_spec())

    def test_production_registry_contains_only_the_tracked_real_artifact(self):
        registry = registered_calibration_artifacts()
        self.assertEqual(set(registry), {REGISTERED_ARTIFACT_DIGEST})
        self.assertEqual(
            registry[REGISTERED_ARTIFACT_DIGEST]["purpose"],
            "real-descriptive-seen-scan-m3a-micro",
        )
        tracked = load_registered_calibration_artifact(
            REGISTERED_ARTIFACT_DIGEST,
        )
        self.assertEqual(tracked, self.artifact)
        self.assertEqual(tracked["aggregate_counts"], {
            "scans": 6, "examples": 54, "errors": 2,
        })
        self.assertEqual(tracked["risk_bound"]["upper_bound"], 1.0 / 3.0)

    def test_artifact_content_tamper_breaks_digest(self):
        for path, replacement in (
            (("calibration_parameters", "support_threshold"), 99.0),
            (("risk_bound", "upper_bound"), 0.9),
            (("model_identity", "checkpoint_digest"), "f" * 64),
            (("validity_domain", "applicability_scan_ids"), ["other-scan"]),
        ):
            with self.subTest(path=path):
                attacked = changed(self.artifact, path, replacement)
                with self.assertRaisesRegex(ContractViolation, "M3_ARTIFACT_DIGEST"):
                    validate_calibration_artifact(attacked)

    def test_resealed_model_checkpoint_feature_interface_mismatch_rejected(self):
        for field in (
                "model_digest", "checkpoint_digest", "feature_digest",
                "interface_digest", "config_digest", "tokenizer_digest"):
            with self.subTest(field=field):
                attacked = copy.deepcopy(self.artifact)
                attacked["model_identity"][field] = "f" * 64
                attacked.pop("artifact_digest")
                attacked["artifact_digest"] = canonical_sha256(attacked)
                with self.assertRaisesRegex(
                        ContractViolation, "M3_ARTIFACT_MODEL_IDENTITY"):
                    validate_calibration_artifact(attacked, self.signal)

    def test_artifact_forbids_test_and_val_unseen_selection(self):
        for split in ("test", "test_challenge", "val_unseen", "VAL-UNSEEN"):
            with self.subTest(split=split):
                spec = artifact_spec(split_names=["train", split])
                with self.assertRaisesRegex(
                        ContractViolation, "M3_CALIBRATION_TEST_LEAKAGE"):
                    build_calibration_artifact(spec)

    def test_runtime_artifact_cannot_contain_gt_or_per_sample_aliases(self):
        for key, value in (
                ("gt_obj_id", "hidden"),
                ("obj2vps", {"hidden": ["vp0"]}),
                ("target_label", True),
                ("samples", [{"sample_id": "secret"}])):
            with self.subTest(key=key):
                spec = artifact_spec()
                spec[key] = value
                with self.assertRaises(ContractViolation):
                    build_calibration_artifact(spec)

    def test_calibration_and_applicability_scans_must_be_disjoint(self):
        spec = artifact_spec()
        scans = spec["validity_domain"]["calibration_scan_ids"]
        spec["validity_domain"]["calibration_scan_ids"] = sorted(
            [DEFAULT_RUNTIME_SCAN] + scans[1:],
        )
        with self.assertRaisesRegex(
                ContractViolation, "M3_CALIBRATION_APPLICATION_OVERLAP"):
            build_calibration_artifact(spec)

    def test_runtime_uses_applicability_not_calibration_scans(self):
        validate_calibration_artifact(self.artifact, self.signal)
        calibration_signal = signal_record(scan=DEFAULT_CALIBRATION_SCAN)
        with self.assertRaisesRegex(ContractViolation, "M3_CALIBRATION_DOMAIN"):
            validate_calibration_artifact(self.artifact, calibration_signal)

    def test_resealed_smaller_candidate_is_structural_but_not_authority(self):
        spec = artifact_spec()
        spec["risk_bound"]["upper_bound"] = 0.01
        spec["aggregate_counts"]["errors"] = 0
        forged = build_calibration_artifact(spec)
        # Candidate/offline construction remains a useful public API.  Its
        # canonical digest does not make caller-selected aggregates trusted.
        self.assertIs(validate_calibration_artifact(forged), forged)
        with self.assertRaisesRegex(
                ContractViolation, "M3_ARTIFACT_NOT_REGISTERED"):
            validate_registered_calibration_artifact(forged, self.signal)

    def test_offline_builder_rejects_scan_split_overlap_and_test_labels(self):
        base = artifact_spec()
        overlap = [
            {"sample_id": "one", "scan_id": "scan-x", "split_name": "train",
             "score": 4.0, "target_matches_slot": True},
            {"sample_id": "two", "scan_id": "scan-x", "split_name": "dev",
             "score": 2.0, "target_matches_slot": False},
        ]
        with self.assertRaisesRegex(ContractViolation, "M3_SCAN_SPLIT_OVERLAP"):
            build_scan_familywise_artifact(overlap, base)

        leaked = [{
            "sample_id": "leak", "scan_id": "scan-z", "split_name": "val_unseen",
            "score": 4.0, "target_matches_slot": True,
        }]
        with self.assertRaisesRegex(
                ContractViolation, "M3_CALIBRATION_TEST_LEAKAGE"):
            build_scan_familywise_artifact(leaked, base)

    def test_offline_builder_outputs_aggregates_not_sample_truth(self):
        samples = [
            {"sample_id": "one", "scan_id": "micro-calibration-scan",
             "split_name": "train", "score": 4.0,
             "target_matches_slot": False},
            {"sample_id": "two", "scan_id": "micro-calibration-scan",
             "split_name": "train", "score": 2.0,
             "target_matches_slot": True},
        ]
        artifact = build_scan_familywise_artifact(samples, artifact_spec())
        serialized = str(artifact).lower()
        for forbidden in (
                "sample_id", "target_matches_slot", "gt_obj_id", "obj2vps"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(
            artifact["aggregate_counts"],
            {"scans": 1, "examples": 2, "errors": 1},
        )

    def test_offline_builder_retains_null_selection_as_no_support(self):
        samples = [
            {"sample_id": "empty", "scan_id": "micro-calibration-scan",
             "split_name": "train", "score": None,
             "target_matches_slot": False},
            {"sample_id": "below", "scan_id": "micro-calibration-scan",
             "split_name": "train", "score": 2.0,
             "target_matches_slot": False},
        ]
        artifact = build_scan_familywise_artifact(samples, artifact_spec())
        self.assertEqual(
            artifact["aggregate_counts"],
            {"scans": 1, "examples": 2, "errors": 0},
        )
        self.assertEqual(artifact["risk_bound"]["upper_bound"], 0.0)


if __name__ == "__main__":
    unittest.main()
