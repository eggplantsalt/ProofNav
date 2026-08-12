"""Code-owned aggregate calibration artifact for the M3-A support slice.

The artifact deliberately contains no per-example label, target path, object
inventory, or evaluator lookup.  It is a sealed summary of a frozen offline
procedure; runtime only validates and consumes that summary.
"""

import copy
import math

from proofnav.contracts import (
    ContractViolation,
    SCHEMA_VERSIONS,
    canonical_sha256,
)
from proofnav.validation import assert_agent_visible


M3_EVIDENCE_FAMILY = "duet_annotated_slot_entity_grounding"
M3_ARTIFACT_PRODUCER = (
    "proofnav.calibration.artifact.build_calibration_artifact"
)
M3_ARTIFACT_FIELDS = frozenset((
    "schema_version", "evidence_family", "predicate_kind", "polarity",
    "score_semantics", "model_identity", "label_definition_digest",
    "split_fingerprint", "split_names", "calibration_method",
    "calibration_parameters", "validity_domain", "sample_unit",
    "dependency_unit", "risk_event", "risk_bound", "aggregate_counts",
    "generation", "artifact_digest",
))
MODEL_IDENTITY_FIELDS = frozenset((
    "model_digest", "checkpoint_digest", "feature_digest",
    "interface_digest", "config_digest", "tokenizer_digest",
))


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _exact(value, fields, location):
    if not isinstance(value, dict):
        _fail("TYPE_MAPPING", location, "expected an object")
    missing = sorted(set(fields) - set(value))
    if missing:
        _fail("M3_MISSING_FIELDS", location, "missing %s" % missing)
    unknown = sorted(set(value) - set(fields))
    if unknown:
        _fail("M3_UNKNOWN_FIELDS", location, "unknown fields %s" % unknown)
    return value


def _string(value, location):
    if not isinstance(value, str) or not value:
        _fail("TYPE_STRING", location, "expected a non-empty string")
    return value


def _sha256(value, location):
    _string(value, location)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        _fail("M3_SHA256", location, "expected a lowercase SHA-256 digest")
    return value


def _number(value, location, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("TYPE_NUMBER", location, "expected a finite number")
    result = float(value)
    if not math.isfinite(result):
        _fail("NUMBER_FINITE", location, "expected a finite number")
    if minimum is not None and result < minimum:
        _fail("NUMBER_RANGE", location, "must be >= %s" % minimum)
    if maximum is not None and result > maximum:
        _fail("NUMBER_RANGE", location, "must be <= %s" % maximum)
    return result


def validate_model_identity(value, location="$.model_identity"):
    value = _exact(value, MODEL_IDENTITY_FIELDS, location)
    for key in sorted(MODEL_IDENTITY_FIELDS):
        _sha256(value[key], location + "." + key)
    return value


def _split_name(value, location):
    value = _string(value, location)
    lowered = value.lower().replace("-", "_")
    if lowered == "test" or lowered.startswith("test_") or "val_unseen" in lowered:
        _fail(
            "M3_CALIBRATION_TEST_LEAKAGE", location,
            "test and val-unseen cannot select or fit calibration",
        )
    return value


def validate_calibration_artifact(artifact, signal=None):
    """Validate the exact sealed M3-A aggregate artifact.

    When ``signal`` is supplied, its full model identity and scan validity
    domain are also checked.  No aliasing or partial identity match is allowed.
    """

    artifact = _exact(artifact, M3_ARTIFACT_FIELDS, "$.calibration_artifact")
    assert_agent_visible(artifact, "$.calibration_artifact")
    if artifact["schema_version"] != SCHEMA_VERSIONS["calibration_artifact"]:
        _fail("SCHEMA_VERSION", "$.calibration_artifact.schema_version", "calibration-artifact v1 required")
    constants = {
        "evidence_family": M3_EVIDENCE_FAMILY,
        "predicate_kind": "entity",
        "polarity": "SUPPORTS",
        "score_semantics": "selected_absolute_object_logit",
        "calibration_method": "fixed_threshold_descriptive_micro",
        "sample_unit": "scan_familywise",
        "dependency_unit": "source_observation_lineage",
        "risk_event": "false_support",
    }
    for key, expected in constants.items():
        if artifact[key] != expected:
            _fail("M3_ARTIFACT_SEMANTICS", "$.calibration_artifact." + key, "expected %s" % expected)
    validate_model_identity(artifact["model_identity"], "$.calibration_artifact.model_identity")
    for key in ("label_definition_digest", "split_fingerprint"):
        _sha256(artifact[key], "$.calibration_artifact." + key)

    splits = artifact["split_names"]
    if not isinstance(splits, list) or not splits:
        _fail("M3_SPLIT_NAMES", "$.calibration_artifact.split_names", "expected a non-empty array")
    for index, name in enumerate(splits):
        _split_name(name, "$.calibration_artifact.split_names[%d]" % index)
    if len(splits) != len(set(splits)):
        _fail("M3_SPLIT_DUPLICATE", "$.calibration_artifact.split_names", "split names must be unique")

    params = _exact(
        artifact["calibration_parameters"], {"support_threshold"},
        "$.calibration_artifact.calibration_parameters",
    )
    _number(params["support_threshold"], "$.calibration_artifact.calibration_parameters.support_threshold")

    domain = _exact(
        artifact["validity_domain"], {
            "domain_id", "calibration_scan_ids", "applicability_scan_ids",
            "shift_policy",
        },
        "$.calibration_artifact.validity_domain",
    )
    if domain["domain_id"] != "descriptive_seen_scan_micro":
        _fail("M3_DOMAIN_ID", "$.calibration_artifact.validity_domain.domain_id", "unregistered M3-A domain")
    if domain["shift_policy"] != "exact_match_or_abstain":
        _fail("M3_SHIFT_POLICY", "$.calibration_artifact.validity_domain.shift_policy", "exact match is required")
    scan_sets = {}
    for field in ("calibration_scan_ids", "applicability_scan_ids"):
        scans = domain[field]
        location = "$.calibration_artifact.validity_domain." + field
        if not isinstance(scans, list) or not scans:
            _fail("M3_DOMAIN_SCANS", location, "expected a non-empty scan allowlist")
        for index, scan in enumerate(scans):
            _string(scan, "%s[%d]" % (location, index))
        if scans != sorted(set(scans)):
            _fail("M3_DOMAIN_SCANS", location, "scan IDs must be sorted and unique")
        scan_sets[field] = set(scans)
    if scan_sets["calibration_scan_ids"] & scan_sets["applicability_scan_ids"]:
        _fail(
            "M3_CALIBRATION_APPLICATION_OVERLAP",
            "$.calibration_artifact.validity_domain",
            "calibration and runtime applicability scans must be disjoint",
        )

    bound = _exact(
        artifact["risk_bound"], {"upper_bound", "confidence", "semantics"},
        "$.calibration_artifact.risk_bound",
    )
    _number(bound["upper_bound"], "$.calibration_artifact.risk_bound.upper_bound", 0, 1)
    if bound["confidence"] is not None:
        _fail("M3_DESCRIPTIVE_CONFIDENCE", "$.calibration_artifact.risk_bound.confidence", "descriptive micro artifact has no confidence guarantee")
    if bound["semantics"] != "descriptive_compatibility_not_statistical_guarantee":
        _fail("M3_BOUND_SEMANTICS", "$.calibration_artifact.risk_bound.semantics", "descriptive compatibility semantics required")

    counts = _exact(
        artifact["aggregate_counts"], {"scans", "examples", "errors"},
        "$.calibration_artifact.aggregate_counts",
    )
    for key in ("scans", "examples", "errors"):
        value = counts[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            _fail("M3_AGGREGATE_COUNT", "$.calibration_artifact.aggregate_counts." + key, "expected a non-negative integer")
    if counts["scans"] == 0 or counts["examples"] == 0:
        _fail("M3_EMPTY_CALIBRATION", "$.calibration_artifact.aggregate_counts", "non-empty aggregate calibration is required")
    if counts["errors"] > counts["scans"]:
        _fail("M3_FAMILYWISE_COUNT", "$.calibration_artifact.aggregate_counts.errors", "errors count erroneous scans, not examples")
    if counts["scans"] != len(domain["calibration_scan_ids"]):
        _fail(
            "M3_CALIBRATION_SCAN_COUNT",
            "$.calibration_artifact.aggregate_counts.scans",
            "aggregate scan count must match the calibration scan identities",
        )
    if counts["examples"] < counts["scans"]:
        _fail(
            "M3_CALIBRATION_EXAMPLE_COUNT",
            "$.calibration_artifact.aggregate_counts.examples",
            "every calibration scan needs at least one labeled example",
        )
    empirical_familywise = float(counts["errors"]) / float(counts["scans"])
    if float(bound["upper_bound"]) < empirical_familywise:
        _fail(
            "M3_RISK_BOUND_UNDERREPORT",
            "$.calibration_artifact.risk_bound.upper_bound",
            "descriptive bound cannot be below observed scan-familywise error",
        )

    generation = _exact(
        artifact["generation"], {"command", "producer", "source_revision"},
        "$.calibration_artifact.generation",
    )
    for key in generation:
        _string(generation[key], "$.calibration_artifact.generation." + key)
    if generation["producer"] != M3_ARTIFACT_PRODUCER:
        _fail("M3_ARTIFACT_PRODUCER", "$.calibration_artifact.generation.producer", "code-owned producer required")

    sealed = copy.deepcopy(artifact)
    claimed_digest = sealed.pop("artifact_digest")
    _sha256(claimed_digest, "$.calibration_artifact.artifact_digest")
    if claimed_digest != canonical_sha256(sealed):
        _fail("M3_ARTIFACT_DIGEST", "$.calibration_artifact.artifact_digest", "artifact content changed")

    if signal is not None:
        if not isinstance(signal, dict):
            _fail("TYPE_MAPPING", "$.signal", "expected an object")
        if signal.get("model_identity") != artifact["model_identity"]:
            _fail("M3_ARTIFACT_MODEL_IDENTITY", "$.calibration_artifact.model_identity", "signal identity mismatch")
        observation = signal.get("observation")
        if not isinstance(observation, dict):
            _fail("M3_SIGNAL_OBSERVATION", "$.signal.observation", "nested signal observation required")
        if observation.get("scan") not in domain["applicability_scan_ids"]:
            _fail("M3_CALIBRATION_DOMAIN", "$.signal.observation.scan", "scan is outside the exact calibration domain")
    return artifact


def validate_registered_calibration_artifact(artifact, signal=None):
    """Validate structure, then require an exact code-owned registry entry.

    Keeping this distinct from :func:`validate_calibration_artifact` lets an
    offline builder inspect a candidate artifact without accidentally granting
    it production authority.
    """

    artifact = validate_calibration_artifact(artifact, signal=signal)
    from .registry import (  # pylint: disable=import-outside-toplevel
        require_registered_calibration_artifact_digest,
    )
    require_registered_calibration_artifact_digest(artifact["artifact_digest"])
    return artifact


def build_calibration_artifact(spec):
    """Seal an exact aggregate specification with the registered producer."""

    if not isinstance(spec, dict):
        _fail("TYPE_MAPPING", "$.artifact_spec", "expected an object")
    expected = M3_ARTIFACT_FIELDS - {"schema_version", "artifact_digest"}
    _exact(spec, expected, "$.artifact_spec")
    artifact = copy.deepcopy(spec)
    artifact["schema_version"] = SCHEMA_VERSIONS["calibration_artifact"]
    artifact["artifact_digest"] = canonical_sha256(artifact)
    return validate_calibration_artifact(artifact)
