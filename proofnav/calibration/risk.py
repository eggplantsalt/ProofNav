"""Conservative M3 certificate-risk composition from selected atoms."""

import math

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256


M3_COMPOSITION_VERSION = "proofnav.strict-familywise-union.v1"
_ATOM_FIELDS = frozenset((
    "schema_version", "atom_id", "event_type", "polarity", "upper_bound",
    "familywise", "family_key", "evidence_id", "artifact_digest",
    "signal_digest", "dependency_group", "atom_digest",
))


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def validate_risk_atom(atom, wrapper=None, location="$.risk_atom"):
    """Validate the exact self-sealed M3-A false-support atom."""

    if not isinstance(atom, dict) or set(atom) != _ATOM_FIELDS:
        _fail("M3_RISK_ATOM_FIELDS", location, "exact risk-atom v1 fields required")
    if atom["schema_version"] != SCHEMA_VERSIONS["risk_atom"]:
        _fail("SCHEMA_VERSION", location + ".schema_version", "risk-atom v1 required")
    if atom["event_type"] != "false_support" or atom["polarity"] != "SUPPORTS":
        _fail("M3_RISK_POLARITY", location, "M3-A only composes false SUPPORT risk")
    bound = atom["upper_bound"]
    if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(float(bound)) or not 0 <= bound <= 1:
        _fail("M3_RISK_RANGE", location + ".upper_bound", "expected [0,1]")
    for key in ("atom_id", "family_key", "evidence_id", "artifact_digest", "signal_digest", "dependency_group"):
        if not isinstance(atom[key], str) or not atom[key]:
            _fail("TYPE_STRING", location + "." + key, "non-empty string required")
    for key in ("artifact_digest", "signal_digest", "atom_digest"):
        value = atom[key]
        if (not isinstance(value, str) or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)):
            _fail("M3_SHA256", location + "." + key, "lowercase SHA-256 required")
    if not isinstance(atom["familywise"], bool) or not atom["familywise"]:
        _fail("M3_RISK_FAMILYWISE", location + ".familywise", "only calibrated familywise dedup is registered")
    sealed = dict(atom)
    claimed_digest = sealed.pop("atom_digest")
    if claimed_digest != canonical_sha256(sealed):
        _fail("M3_RISK_ATOM_DIGEST", location + ".atom_digest", "risk atom changed")
    if wrapper is not None:
        if atom["evidence_id"] != wrapper.get("evidence", {}).get("evidence_id"):
            _fail("M3_RISK_EVIDENCE", location + ".evidence_id", "atom must bind selected evidence")
        if atom["artifact_digest"] != wrapper.get("calibration_artifact", {}).get("artifact_digest"):
            _fail("M3_RISK_ARTIFACT", location + ".artifact_digest", "atom/artifact mismatch")
        if atom["signal_digest"] != wrapper.get("signal", {}).get("signal_digest"):
            _fail("M3_RISK_SIGNAL", location + ".signal_digest", "atom/signal mismatch")
        if atom["dependency_group"] != wrapper.get("evidence", {}).get("dependency_group"):
            _fail("M3_RISK_DEPENDENCY", location + ".dependency_group", "atom/evidence mismatch")
        decision = wrapper.get("adapter_decision", {})
        if atom["atom_id"] != decision.get("risk_atom_id"):
            _fail("M3_RISK_ATOM_ID", location + ".atom_id", "atom/adapter decision mismatch")
        expected_family = "artifact:%s:source-observation:%s" % (
            atom["artifact_digest"],
            wrapper.get("evidence", {}).get("source_event_id"),
        )
        if atom["family_key"] != expected_family:
            _fail("M3_RISK_FAMILY_KEY", location + ".family_key", "non-canonical family key")
    return atom


def compose_certificate_risk(wrappers, verdict, scope):
    """Derive an M2-shaped claim from certificate-selected M3 wrappers.

    Familywise atoms sharing the exact artifact-and-source family key are
    counted once.  Merely reusing a dependency-group string never authorizes
    deduplication.  The M3-A slice has no REFUTE/residual/link atoms, therefore
    NOT_FOUND always fails closed.
    """

    if verdict not in ("FOUND", "NOT_FOUND"):
        _fail("M3_RISK_VERDICT", "$.verdict", "FOUND or NOT_FOUND required")
    if not isinstance(scope, dict) or "risk_budgets" not in scope or "calibration_version" not in scope:
        _fail("M3_RISK_SCOPE", "$.scope", "validated scope fields required")
    if verdict == "NOT_FOUND":
        _fail("M3_NOT_FOUND_SEALED", "$.verdict", "M3-A has no refutation, residual, or identity atoms")
    if not isinstance(wrappers, list) or not wrappers:
        _fail("M3_RISK_EMPTY", "$.wrappers", "selected evidence wrappers required")

    families = {}
    artifact_digests = set()
    descriptive_artifact = False
    for index, wrapper in enumerate(wrappers):
        if not isinstance(wrapper, dict):
            _fail("TYPE_MAPPING", "$.wrappers[%d]" % index, "expected an object")
        if wrapper.get("schema_version") != SCHEMA_VERSIONS["m3_bound_evidence"]:
            _fail("M3_RISK_WRAPPER", "$.wrappers[%d].schema_version" % index, "M3 bound-evidence v3 required")
        if wrapper.get("evidence", {}).get("claim") != "SUPPORTS" or wrapper.get("adapter_decision", {}).get("decision") != "SUPPORTS":
            _fail("M3_RISK_POLARITY", "$.wrappers[%d]" % index, "selected SUPPORT wrapper required")
        # Rebuild the entire wrapper from its immutable inputs.  This prevents
        # a caller from lowering an atom bound, inventing a family key, or
        # making a tampered artifact/signal/decision internally agree.
        from proofnav.perception.evidence_adapter import (  # pylint: disable=import-outside-toplevel
            build_calibrated_bound_evidence,
        )
        query = {
            key: wrapper.get(key) for key in (
                "query_id", "hypothesis_id", "obligation_id", "predicate_id",
                "predicate_kind", "binding",
            )
        }
        expected = build_calibrated_bound_evidence(
            query, wrapper.get("signal"), wrapper.get("calibration_artifact"),
            scope.get("scope_contract_id"),
        )
        if expected != wrapper:
            _fail(
                "M3_RISK_WRAPPER_RECOMPUTE", "$.wrappers[%d]" % index,
                "selected wrapper differs from code-owned adapter output",
            )
        atom = validate_risk_atom(
            wrapper.get("risk_atom"), wrapper,
            "$.wrappers[%d].risk_atom" % index,
        )
        artifact_bound = wrapper["calibration_artifact"]["risk_bound"]
        descriptive_artifact = descriptive_artifact or (
            artifact_bound["confidence"] is None
            or artifact_bound["semantics"]
            == "descriptive_compatibility_not_statistical_guarantee"
        )
        artifact_digests.add(atom["artifact_digest"])
        prior = families.get(atom["family_key"])
        if prior is not None and prior != atom["upper_bound"]:
            _fail("M3_RISK_FAMILY_CONFLICT", "$.wrappers[%d].risk_atom" % index, "same family has inconsistent bound")
        families[atom["family_key"]] = atom["upper_bound"]
    if len(artifact_digests) != 1:
        _fail(
            "M3_RISK_ARTIFACT_MIX", "$.wrappers",
            "M3-A certificates require one exact calibration artifact",
        )
    artifact_digest = next(iter(artifact_digests))
    expected_calibration = (
        "proofnav.calibration-artifact.v1:" + artifact_digest
    )
    if scope.get("calibration_version") != expected_calibration:
        _fail(
            "M3_RISK_CALIBRATION_VERSION", "$.scope.calibration_version",
            "scope must name the exact selected artifact digest",
        )
    if descriptive_artifact:
        _fail(
            "M3_NO_STATISTICAL_GUARANTEE",
            "$.wrappers[*].calibration_artifact.risk_bound",
            "descriptive empirical error cannot authorize a certificate",
        )
    upper = min(1.0, sum(float(value) for value in families.values()))
    budget = scope["risk_budgets"].get("false_found")
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(float(budget)) or not 0 <= budget <= 1:
        _fail("M3_RISK_BUDGET", "$.scope.risk_budgets.false_found", "expected [0,1]")
    # Keep the frozen six-field M2 claim shape.  The exact selected atom set is
    # already bound into each certificate wrapper; this version refuses any
    # caller-provided upper bound.
    return {
        "decision": "FOUND",
        "risk_type": "false_found",
        "upper_bound": upper,
        "budget": budget,
        "calibration_version": scope["calibration_version"],
        "composition_version": "%s:%s" % (
            M3_COMPOSITION_VERSION,
            canonical_sha256(sorted(families))[:16],
        ),
    }
