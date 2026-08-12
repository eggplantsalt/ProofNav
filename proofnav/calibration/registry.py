"""Fail-closed, code-owned trust anchor for M3 calibration artifacts.

Structural artifact validation deliberately remains public: offline builders
need to construct and inspect candidate summaries.  Production admission is a
separate operation and accepts only an exact artifact digest committed to the
package registry.  Consequently a caller cannot make up aggregate counts,
reseal a smaller bound, and turn that self-consistent object into authority.
"""

import json
import copy
from pathlib import Path

from proofnav.contracts import ContractViolation, canonical_sha256


REGISTRY_SCHEMA_VERSION = "proofnav.calibration-registry.v1"
REGISTRY_MANIFEST_DIGEST = (
    "ec8ad033195d3f79e5b3b2ed8788eac19492efe2927c579d04a655647636c316"
)
_REGISTRY_PATH = Path(__file__).with_name("registered_artifacts.json")
_REGISTRY_FIELDS = frozenset(("schema_version", "entries"))
_ENTRY_FIELDS = frozenset((
    "artifact_digest", "artifact_resource", "purpose",
    "signal_manifest_digest", "signal_manifest_resource", "source_revision",
    "replay_digest", "replay_resource",
))
_SIGNAL_MANIFEST_FIELDS = frozenset((
    "schema_version", "artifact_digest", "source_jsonl_sha256",
    "partition_rule", "scan_ids", "signal_count", "signal_digests",
))
_SIGNAL_MANIFEST_VERSION = "proofnav.registered-signal-manifest.v1"


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _sha256(value, location):
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        _fail("M3_REGISTRY_DIGEST", location, "lowercase SHA-256 required")
    return value


def _load_registry():
    try:
        with _REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as error:
        _fail("M3_REGISTRY_UNAVAILABLE", "$.calibration_registry", str(error))
    if not isinstance(manifest, dict) or set(manifest) != _REGISTRY_FIELDS:
        _fail(
            "M3_REGISTRY_SCHEMA", "$.calibration_registry",
            "exact schema_version+entries manifest required",
        )
    if manifest["schema_version"] != REGISTRY_SCHEMA_VERSION:
        _fail(
            "M3_REGISTRY_SCHEMA", "$.calibration_registry.schema_version",
            "calibration-registry v1 required",
        )
    entries = manifest["entries"]
    if not isinstance(entries, list) or not entries:
        _fail(
            "M3_REGISTRY_EMPTY", "$.calibration_registry.entries",
            "at least one code-owned artifact is required",
        )
    prior = None
    by_digest = {}
    artifacts = {}
    signal_digests = {}
    observation_digests = {}
    for index, entry in enumerate(entries):
        location = "$.calibration_registry.entries[%d]" % index
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            _fail("M3_REGISTRY_SCHEMA", location, "exact registry entry required")
        digest = _sha256(entry["artifact_digest"], location + ".artifact_digest")
        _sha256(
            entry["signal_manifest_digest"],
            location + ".signal_manifest_digest",
        )
        _sha256(entry["replay_digest"], location + ".replay_digest")
        for key in (
                "artifact_resource", "purpose", "signal_manifest_resource",
                "source_revision", "replay_resource"):
            if not isinstance(entry[key], str) or not entry[key]:
                _fail("M3_REGISTRY_SCHEMA", location + "." + key, "non-empty string required")
        if prior is not None and digest <= prior:
            _fail(
                "M3_REGISTRY_ORDER", location + ".artifact_digest",
                "artifact digests must be sorted and unique",
            )
        prior = digest
        by_digest[digest] = dict(entry)
        resource = Path(entry["artifact_resource"])
        if resource.is_absolute() or ".." in resource.parts:
            _fail(
                "M3_REGISTRY_RESOURCE", location + ".artifact_resource",
                "artifact resource must stay inside proofnav.calibration",
            )
        resource_path = Path(__file__).parent / resource
        try:
            with resource_path.open("r", encoding="utf-8") as handle:
                artifact = json.load(handle)
        except (OSError, ValueError) as error:
            _fail("M3_REGISTRY_RESOURCE", location + ".artifact_resource", str(error))
        if not isinstance(artifact, dict) or artifact.get("artifact_digest") != digest:
            _fail(
                "M3_REGISTRY_RESOURCE_DIGEST", location + ".artifact_resource",
                "tracked artifact does not declare the registered digest",
            )
        body = copy.deepcopy(artifact)
        body.pop("artifact_digest")
        if canonical_sha256(body) != digest:
            _fail(
                "M3_REGISTRY_RESOURCE_DIGEST", location + ".artifact_resource",
                "tracked artifact content does not match the registered digest",
            )
        if artifact.get("generation", {}).get("source_revision") != entry["source_revision"]:
            _fail(
                "M3_REGISTRY_RESOURCE_REVISION", location + ".artifact_resource",
                "tracked artifact and registry revisions differ",
            )
        artifacts[digest] = artifact
        signal_resource = Path(entry["signal_manifest_resource"])
        if signal_resource.is_absolute() or ".." in signal_resource.parts:
            _fail(
                "M3_SIGNAL_REGISTRY_RESOURCE",
                location + ".signal_manifest_resource",
                "signal manifest must stay inside proofnav.calibration",
            )
        signal_path = Path(__file__).parent / signal_resource
        try:
            with signal_path.open("r", encoding="utf-8") as handle:
                signal_manifest = json.load(handle)
        except (OSError, ValueError) as error:
            _fail(
                "M3_SIGNAL_REGISTRY_RESOURCE",
                location + ".signal_manifest_resource", str(error),
            )
        if canonical_sha256(signal_manifest) != entry["signal_manifest_digest"]:
            _fail(
                "M3_SIGNAL_REGISTRY_SEAL",
                location + ".signal_manifest_resource",
                "signal manifest differs from its code-owned digest",
            )
        if (not isinstance(signal_manifest, dict)
                or set(signal_manifest) != _SIGNAL_MANIFEST_FIELDS
                or signal_manifest["schema_version"] != _SIGNAL_MANIFEST_VERSION
                or signal_manifest["artifact_digest"] != digest):
            _fail(
                "M3_SIGNAL_REGISTRY_SCHEMA",
                location + ".signal_manifest_resource",
                "exact artifact-bound registered-signal manifest required",
            )
        _sha256(
            signal_manifest["source_jsonl_sha256"],
            location + ".signal_manifest_resource.source_jsonl_sha256",
        )
        scans = signal_manifest["scan_ids"]
        signals = signal_manifest["signal_digests"]
        if (not isinstance(scans, list) or scans != sorted(set(scans))
                or any(not isinstance(value, str) or not value for value in scans)
                or not isinstance(signals, list)
                or signals != sorted(set(signals))
                or any(not isinstance(value, str) or len(value) != 64
                       for value in signals)
                or signal_manifest["signal_count"] != len(signals)
                or set(scans) != set(artifact["validity_domain"]["applicability_scan_ids"])):
            _fail(
                "M3_SIGNAL_REGISTRY_SCHEMA",
                location + ".signal_manifest_resource",
                "sorted exact signal/scan allowlists must match the artifact",
            )
        for index, signal_digest in enumerate(signals):
            _sha256(
                signal_digest,
                "%s.signal_manifest_resource.signal_digests[%d]" % (
                    location, index,
                ),
            )
        if signal_manifest["partition_rule"] != (
                "int(SHA256(scan_id)[:8],16) % 3 == 2"):
            _fail(
                "M3_SIGNAL_REGISTRY_PARTITION",
                location + ".signal_manifest_resource.partition_rule",
                "frozen partition-2 rule required",
            )
        signal_digests[digest] = frozenset(signals)
        replay_resource = Path(entry["replay_resource"])
        if replay_resource.is_absolute() or ".." in replay_resource.parts:
            _fail("M3_REPLAY_RESOURCE", location + ".replay_resource", "invalid replay path")
        replay_path = Path(__file__).parent / replay_resource
        try:
            with replay_path.open("r", encoding="utf-8") as handle:
                replay = json.load(handle)
        except (OSError, ValueError) as error:
            _fail("M3_REPLAY_RESOURCE", location + ".replay_resource", str(error))
        if canonical_sha256(replay) != entry["replay_digest"]:
            _fail("M3_REPLAY_SEAL", location + ".replay_resource", "replay changed")
        if (not isinstance(replay, dict)
                or replay.get("schema_version") != "proofnav.registered-signal-replay.v1"
                or replay.get("artifact_digest") != digest
                or not isinstance(replay.get("signals"), list)
                or not replay["signals"]
                or replay.get("selected_signal_digest")
                != replay["signals"][-1].get("signal_digest")):
            _fail("M3_REPLAY_SCHEMA", location + ".replay_resource", "invalid exact prefix")
        admitted_observations = set()
        for replay_signal in replay["signals"]:
            signal_body = copy.deepcopy(replay_signal)
            signal_digest = signal_body.pop("signal_digest", None)
            observation = replay_signal.get("observation")
            observation_digest = replay_signal.get("observation_digest")
            if (signal_digest not in signal_digests[digest]
                    or canonical_sha256(signal_body) != signal_digest
                    or not isinstance(observation, dict)
                    or canonical_sha256(observation) != observation_digest):
                _fail("M3_REPLAY_SIGNAL", location + ".replay_resource", "unsealed signal/observation")
            admitted_observations.add(observation_digest)
        observation_digests[digest] = frozenset(admitted_observations)
    # The JSON file is convenient for review and extension, while this
    # in-code digest is the actual trust anchor.  Updating the allowlist is an
    # explicit source change, not a runtime/caller parameter.
    if canonical_sha256(manifest) != REGISTRY_MANIFEST_DIGEST:
        _fail(
            "M3_REGISTRY_SEAL", "$.calibration_registry",
            "registry manifest differs from the code-owned trust anchor",
        )
    return by_digest, artifacts, signal_digests, observation_digests


(
    _REGISTERED_BY_DIGEST,
    _REGISTERED_ARTIFACTS,
    _REGISTERED_SIGNAL_DIGESTS,
    _REGISTERED_OBSERVATION_DIGESTS,
) = _load_registry()


def registered_calibration_artifacts():
    """Return review metadata keyed by exact admitted artifact digest."""

    return dict(
        (digest, dict(entry))
        for digest, entry in _REGISTERED_BY_DIGEST.items()
    )


def is_registered_calibration_artifact_digest(digest):
    """Return whether ``digest`` is an exact code-owned registry entry."""

    return isinstance(digest, str) and digest in _REGISTERED_BY_DIGEST


def load_registered_calibration_artifact(digest):
    """Return the exact tracked aggregate for a registered production digest."""

    require_registered_calibration_artifact_digest(digest)
    return copy.deepcopy(_REGISTERED_ARTIFACTS[digest])


def is_registered_signal_digest(artifact_digest, signal_digest):
    """Return whether the exact frozen signal belongs to an artifact replay."""

    return (
        isinstance(artifact_digest, str)
        and isinstance(signal_digest, str)
        and signal_digest in _REGISTERED_SIGNAL_DIGESTS.get(
            artifact_digest, frozenset(),
        )
    )


def require_registered_signal_digest(
        artifact_digest, signal_digest, location="$.signal.signal_digest"):
    """Reject fabricated/live signals outside the sealed fixed-micro replay."""

    require_registered_calibration_artifact_digest(artifact_digest)
    _sha256(signal_digest, location)
    if not is_registered_signal_digest(artifact_digest, signal_digest):
        _fail(
            "M3_SIGNAL_NOT_REGISTERED", location,
            "M3-A authority is limited to the sealed recorded micro replay",
        )
    return signal_digest


def is_registered_observation_digest(artifact_digest, observation_digest):
    return observation_digest in _REGISTERED_OBSERVATION_DIGESTS.get(
        artifact_digest, frozenset(),
    )


def require_registered_observation_digest(
        artifact_digest, observation_digest,
        location="$.observation"):
    require_registered_calibration_artifact_digest(artifact_digest)
    _sha256(observation_digest, location)
    if not is_registered_observation_digest(artifact_digest, observation_digest):
        _fail(
            "M3_OBSERVATION_NOT_REGISTERED", location,
            "M3-A transition is outside the sealed real episode prefix",
        )
    return observation_digest


def require_registered_calibration_artifact_digest(
        digest, location="$.calibration_artifact.artifact_digest"):
    """Reject a structurally valid but untrusted/self-reported artifact."""

    _sha256(digest, location)
    if digest not in _REGISTERED_BY_DIGEST:
        _fail(
            "M3_ARTIFACT_NOT_REGISTERED", location,
            "artifact digest is not in the code-owned calibration registry",
        )
    return dict(_REGISTERED_BY_DIGEST[digest])


__all__ = [
    "REGISTRY_MANIFEST_DIGEST",
    "REGISTRY_SCHEMA_VERSION",
    "is_registered_calibration_artifact_digest",
    "is_registered_signal_digest",
    "is_registered_observation_digest",
    "load_registered_calibration_artifact",
    "registered_calibration_artifacts",
    "require_registered_calibration_artifact_digest",
    "require_registered_signal_digest",
    "require_registered_observation_digest",
]
