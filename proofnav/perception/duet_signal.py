"""Default-off extraction of the real, agent-visible DUET object signal.

The module is CPU-testable and has no import-time dependency on torch,
MatterSim, the REVERIE environment, or evaluator state.  The record contains a
sanitized observation for independent replay, but binds large arrays by their
post-cast content digests instead of copying them into the proof log.

The output is an uncalibrated proposal signal, never evidence authority.
``panorama_features`` is DUET's candidate-first packed view tensor, whose row
count can exceed 36 when multiple candidates share a panorama point ID.
"""

import hashlib
import json
import os

import numpy as np

from proofnav.contracts import (
    ContractViolation,
    FORBIDDEN_AGENT_KEYS,
    canonical_sha256,
)
from proofnav.validation import validate_observation


DUET_SIGNAL_SCHEMA_VERSION = "proofnav.duet-model-signal.v1"
DUET_SIGNAL_PRODUCER = "proofnav.perception.duet_signal.build_duet_signal"
DUET_SIGNAL_SOURCE_SCHEMA = (
    "duet.reverie.forward_navigation_per_step@frozen-m0"
)

_MODEL_IDENTITY_FIELDS = frozenset((
    "model_digest",
    "checkpoint_digest",
    "feature_digest",
    "interface_digest",
    "config_digest",
    "tokenizer_digest",
))


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _sha256_hex(value, location):
    if not isinstance(value, str):
        _fail("M3_SIGNAL_DIGEST", location, "expected sha256 hex string")
    value = value.lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        _fail("M3_SIGNAL_DIGEST", location, "expected sha256 hex string")
    return value


def _forbidden_key_walk(value, location="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_AGENT_KEYS:
                _fail(
                    "M3_SIGNAL_GT", "%s.%s" % (location, key),
                    "evaluator truth is forbidden at the DUET signal seam",
                )
            _forbidden_key_walk(child, "%s.%s" % (location, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _forbidden_key_walk(child, "%s[%d]" % (location, index))


def _as_numpy(value, dtype, location):
    """Detach a tensor-like value without importing torch, then cast exactly."""

    try:
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "numpy"):
            value = value.numpy()
        array = np.asarray(value, dtype=dtype)
    except Exception as exc:
        _fail("M3_SIGNAL_ARRAY", location, "cannot cast array: %s" % exc)
    if array.dtype.kind == "f" and not bool(np.isfinite(array).all()):
        _fail("M3_SIGNAL_NONFINITE", location, "post-cast values must be finite")
    return np.ascontiguousarray(array)


def _as_mask(value, location):
    try:
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "numpy"):
            value = value.numpy()
        array = np.asarray(value)
    except Exception as exc:
        _fail("M3_SIGNAL_ARRAY", location, "cannot read mask: %s" % exc)
    if array.dtype != np.dtype(np.bool_):
        _fail("M3_SIGNAL_MASK", location, "mask values must have boolean dtype")
    return np.ascontiguousarray(array, dtype=np.bool_)


def _content_digest(value, dtype, location):
    """Hash dtype, shape, and C-order bytes after the explicit model-side cast."""

    array = _as_numpy(value, dtype, location)
    descriptor = {
        "dtype": str(array.dtype),
        "shape": [int(x) for x in array.shape],
        "bytes_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
    }
    return {
        "digest": canonical_sha256(descriptor),
        "dtype": descriptor["dtype"],
        "shape": descriptor["shape"],
    }


def _model_identity(value):
    if not isinstance(value, dict) or set(value) != _MODEL_IDENTITY_FIELDS:
        _fail(
            "M3_SIGNAL_MODEL_IDENTITY", "$.model_identity",
            "expected exactly %s" % sorted(_MODEL_IDENTITY_FIELDS),
        )
    return {
        key: _sha256_hex(value[key], "$.model_identity.%s" % key)
        for key in sorted(_MODEL_IDENTITY_FIELDS)
    }


def build_duet_signal(
    *,
    observation,
    template_digest,
    object_logits,
    object_valid_mask,
    panorama_features,
    object_features,
    object_angle_features,
    object_box_features,
    instruction_encoding,
    model_identity,
):
    """Build one deterministic, self-contained, GT-free DUET signal record."""

    if not isinstance(observation, dict):
        _fail("M3_SIGNAL_OBSERVATION", "$.observation", "must be a mapping")
    _forbidden_key_walk(observation, "$.observation")
    try:
        observation = validate_observation(json.loads(json.dumps(
            observation, sort_keys=True, allow_nan=False,
        )))
    except ContractViolation:
        raise
    except (TypeError, ValueError) as exc:
        _fail("M3_SIGNAL_OBSERVATION", "$.observation", str(exc))

    proposal_ids = observation["object_proposal_ids"]
    logits = _as_numpy(object_logits, np.float32, "$.object_scores.logits")
    valid_mask = _as_mask(object_valid_mask, "$.object_scores.valid_mask")
    if logits.ndim != 1 or valid_mask.ndim != 1:
        _fail("M3_SIGNAL_SCORE_SHAPE", "$.object_scores", "scores/mask must be rank one")
    if len(logits) != len(valid_mask) or len(logits) != len(proposal_ids):
        _fail(
            "M3_SIGNAL_SCORE_LENGTH", "$.object_scores",
            "proposal IDs, logits, and mask must have identical lengths",
        )

    content_digests = {
        "panorama_features": _content_digest(
            panorama_features, np.float32,
            "$.content_digests.panorama_features",
        ),
        "object_features": _content_digest(
            object_features, np.float32,
            "$.content_digests.object_features",
        ),
        "object_angle_features": _content_digest(
            object_angle_features, np.float32,
            "$.content_digests.object_angle_features",
        ),
        "object_box_features": _content_digest(
            object_box_features, np.float32,
            "$.content_digests.object_box_features",
        ),
        "instruction_encoding": _content_digest(
            instruction_encoding, np.int64,
            "$.content_digests.instruction_encoding",
        ),
    }
    for name in (
        "object_features", "object_angle_features", "object_box_features",
    ):
        shape = content_digests[name]["shape"]
        if not shape or shape[0] != len(proposal_ids):
            _fail(
                "M3_SIGNAL_FEATURE_LENGTH",
                "$.content_digests.%s.shape" % name,
                "leading dimension must equal proposal count",
            )
    encoding_shape = content_digests["instruction_encoding"]["shape"]
    if (len(encoding_shape) != 1 or
            encoding_shape[0] != observation["instruction_encoding_length"]):
        _fail(
            "M3_SIGNAL_INSTRUCTION_LENGTH",
            "$.content_digests.instruction_encoding.shape",
            "encoding length does not match sanitized observation",
        )

    selected_index = None
    selected_proposal_id = None
    selected_statistic = None
    valid_indices = [
        index for index, valid in enumerate(valid_mask.tolist()) if bool(valid)
    ]
    if valid_indices:
        selected_index = max(valid_indices, key=lambda index: (logits[index], -index))
        selected_proposal_id = str(proposal_ids[selected_index])
        selected_statistic = float(logits[selected_index])

    value = {
        "schema_version": DUET_SIGNAL_SCHEMA_VERSION,
        "producer": DUET_SIGNAL_PRODUCER,
        "source_schema": DUET_SIGNAL_SOURCE_SCHEMA,
        "signal_semantics": "uncalibrated_duet_object_proposal_score",
        "evidence_authority": False,
        "observation": observation,
        "observation_digest": canonical_sha256(observation),
        "object_scores": {
            "proposal_ids": [str(value) for value in proposal_ids],
            "valid_mask": [bool(value) for value in valid_mask.tolist()],
            "logits": [float(value) for value in logits.tolist()],
            "selected_index": selected_index,
            "selected_proposal_id": selected_proposal_id,
            "selected_statistic": selected_statistic,
        },
        "content_digests": content_digests,
        "instruction_digest": canonical_sha256(observation["instruction"]),
        "template_digest": _sha256_hex(template_digest, "$.template_digest"),
        "model_identity": _model_identity(model_identity),
    }
    value["signal_digest"] = canonical_sha256(value)

    # Central exact-schema validation is imported locally to avoid a module
    # import cycle while the signal boundary constructs its own value.
    try:
        from proofnav.perception.evidence_adapter import validate_duet_signal
    except ModuleNotFoundError as exc:
        if exc.name != "proofnav.perception.evidence_adapter":
            raise
        validate_duet_signal = None
    if validate_duet_signal is not None:
        return validate_duet_signal(
            value, observation=observation,
            expected_model_identity=value["model_identity"],
        )
    return value


class DuetSignalSink(object):
    """Flush signal records to a JSONL stream separate from the M0 trace."""

    def __init__(self, path, model_identity):
        if not isinstance(path, str) or not path.strip():
            _fail("M3_SIGNAL_PATH", "$.path", "must be a non-empty path")
        self.path = os.path.abspath(path)
        self.model_identity = _model_identity(model_identity)
        parent = os.path.dirname(self.path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        self._file = open(self.path, "w", encoding="utf-8")

    def emit(self, **kwargs):
        if self._file is None:
            _fail("M3_SIGNAL_CLOSED", "$.sink", "cannot emit after close")
        kwargs["model_identity"] = self.model_identity
        value = build_duet_signal(**kwargs)
        self._file.write(json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n")
        self._file.flush()
        return value

    def close(self):
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
