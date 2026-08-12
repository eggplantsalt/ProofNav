"""Offline-only scan-familywise reduction for the M3-A artifact."""

import copy
import math

from proofnav.calibration.artifact import _split_name, build_calibration_artifact
from proofnav.contracts import ContractViolation, canonical_sha256


_LABEL_FIELDS = frozenset((
    "sample_id", "scan_id", "split_name", "score", "target_matches_slot",
))


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def build_scan_familywise_artifact(labeled_samples, artifact_spec):
    """Aggregate labels by scan and return an artifact with no sample truth.

    The support threshold is precommitted in ``artifact_spec``.  A familywise
    error is a scan containing at least one selected false support.
    """

    if not isinstance(labeled_samples, list) or not labeled_samples:
        _fail("M3_EMPTY_CALIBRATION", "$.labeled_samples", "non-empty labels required")
    if not isinstance(artifact_spec, dict):
        _fail("TYPE_MAPPING", "$.artifact_spec", "expected an object")
    try:
        threshold = artifact_spec["calibration_parameters"]["support_threshold"]
    except (KeyError, TypeError):
        _fail("M3_CALIBRATION_THRESHOLD", "$.artifact_spec.calibration_parameters", "support_threshold required")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(float(threshold)):
        _fail("M3_CALIBRATION_THRESHOLD", "$.artifact_spec.calibration_parameters.support_threshold", "finite number required")

    sample_ids = set()
    scan_splits = {}
    error_scans = set()
    for index, sample in enumerate(labeled_samples):
        location = "$.labeled_samples[%d]" % index
        if not isinstance(sample, dict) or set(sample) != _LABEL_FIELDS:
            _fail("M3_OFFLINE_LABEL_FIELDS", location, "expected exactly %s" % sorted(_LABEL_FIELDS))
        for key in ("sample_id", "scan_id", "split_name"):
            if not isinstance(sample[key], str) or not sample[key]:
                _fail("TYPE_STRING", location + "." + key, "non-empty string required")
        if sample["sample_id"] in sample_ids:
            _fail("M3_SAMPLE_DUPLICATE", location + ".sample_id", "duplicate sample")
        sample_ids.add(sample["sample_id"])
        _split_name(sample["split_name"], location + ".split_name")
        prior = scan_splits.setdefault(sample["scan_id"], sample["split_name"])
        if prior != sample["split_name"]:
            _fail("M3_SCAN_SPLIT_OVERLAP", location + ".scan_id", "scan crosses splits")
        score = sample["score"]
        # Empty/all-masked proposal sets are genuine calibration examples,
        # not rows to discard.  They create no SUPPORT opportunity and hence
        # cannot trigger a false-support event, but still count toward the
        # predeclared scan-familywise sample and example totals.
        if score is not None and (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))):
            _fail(
                "M3_LABEL_SCORE", location + ".score",
                "finite score or null empty-selection marker required",
            )
        if not isinstance(sample["target_matches_slot"], bool):
            _fail("TYPE_BOOLEAN", location + ".target_matches_slot", "boolean required")
        if (score is not None and float(score) >= float(threshold)
                and not sample["target_matches_slot"]):
            error_scans.add(sample["scan_id"])

    scans = sorted(scan_splits)
    spec = copy.deepcopy(artifact_spec)
    spec["split_names"] = sorted(set(scan_splits.values()))
    spec["split_fingerprint"] = canonical_sha256([
        {"scan_id": scan, "split_name": scan_splits[scan]} for scan in scans
    ])
    domain = spec.get("validity_domain")
    if not isinstance(domain, dict):
        _fail("TYPE_MAPPING", "$.artifact_spec.validity_domain", "expected an object")
    applicability = domain.get("applicability_scan_ids")
    if not isinstance(applicability, list) or not applicability:
        _fail(
            "M3_APPLICATION_DOMAIN_REQUIRED",
            "$.artifact_spec.validity_domain.applicability_scan_ids",
            "runtime application scans must be predeclared",
        )
    if any(not isinstance(scan, str) or not scan for scan in applicability):
        _fail(
            "M3_APPLICATION_DOMAIN_REQUIRED",
            "$.artifact_spec.validity_domain.applicability_scan_ids",
            "runtime application scan IDs must be non-empty strings",
        )
    if applicability != sorted(set(applicability)):
        _fail(
            "M3_APPLICATION_DOMAIN_REQUIRED",
            "$.artifact_spec.validity_domain.applicability_scan_ids",
            "runtime application scan IDs must be sorted and unique",
        )
    if set(scans) & set(applicability):
        _fail(
            "M3_CALIBRATION_APPLICATION_OVERLAP",
            "$.artifact_spec.validity_domain",
            "calibration labels cannot define the runtime application slice",
        )
    domain["calibration_scan_ids"] = scans
    spec["aggregate_counts"] = {
        "scans": len(scans), "examples": len(labeled_samples),
        "errors": len(error_scans),
    }
    spec["risk_bound"] = {
        "upper_bound": float(len(error_scans)) / float(len(scans)),
        "confidence": None,
        "semantics": "descriptive_compatibility_not_statistical_guarantee",
    }
    return build_calibration_artifact(spec)
