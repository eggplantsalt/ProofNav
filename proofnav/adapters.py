"""Pure M1 adapters from frozen DUET values into auditable contracts.

These functions copy primitive metadata only.  They do not retain the original
observation, simulator, environment, tensors, logits, or evaluator objects.
"""

from .contracts import SCHEMA_VERSIONS, canonical_sha256
from .validation import validate_action, validate_observation


def _shape_dtype(value):
    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    if shape is None:
        if isinstance(value, (list, tuple)):
            shape = (len(value),)
        else:
            raise TypeError("value has no shape")
    return {
        "shape": [int(dimension) for dimension in shape],
        "dtype": str(dtype if dtype is not None else type(value).__name__),
    }


def derive_runtime_episode_id(scan, start_viewpoint, instruction):
    """Derive an opaque, agent-visible episode key without evaluator IDs.

    REVERIE's raw ``instr_id`` embeds ``objId``.  Hashing that identifier is
    still dictionary-reversible, so the successor key uses only values that
    are already visible to the running agent at episode start.
    """

    return "runtime-episode-" + canonical_sha256({
        "scan": str(scan),
        "start_viewpoint": str(start_viewpoint),
        "instruction": str(instruction),
    })[:32]


def sanitize_duet_observation(
        raw, event_id, event_seq, step, runtime_episode_id=None):
    """Copy the DUET observation allowlist and discard all GT-bearing fields."""

    candidates = []
    for candidate in raw["candidate"]:
        candidates.append({
            "viewpoint_id": str(candidate["viewpointId"]),
            "point_id": int(candidate["pointId"]),
            "heading": float(candidate["heading"]),
            "elevation": float(candidate["elevation"]),
            "position": [float(x) for x in candidate["position"]],
            "simulator_index": int(candidate["idx"]),
            "feature_schema": _shape_dtype(candidate["feature"]),
            "evidence_role": "unobserved_navigation_proposal",
        })
    value = {
        "schema_version": SCHEMA_VERSIONS["observation"],
        "event_id": str(event_id),
        "episode_id": str(
            raw["instr_id"] if runtime_episode_id is None
            else runtime_episode_id
        ),
        "event_seq": int(event_seq),
        "step": int(step),
        "source": "observation",
        "scan": str(raw["scan"]),
        "viewpoint": str(raw["viewpoint"]),
        "view_index": int(raw["viewIndex"]),
        "pose": {
            "heading": float(raw["heading"]),
            "elevation": float(raw["elevation"]),
            "position": [float(x) for x in raw["position"]],
        },
        "field_schema": {
            "feature": _shape_dtype(raw["feature"]),
            "obj_img_fts": _shape_dtype(raw["obj_img_fts"]),
            "obj_ang_fts": _shape_dtype(raw["obj_ang_fts"]),
            "obj_box_fts": _shape_dtype(raw["obj_box_fts"]),
        },
        "instruction": str(raw["instruction"]),
        "instruction_encoding_length": len(raw["instr_encoding"]),
        "candidates": candidates,
        "object_proposal_ids": [str(value) for value in raw["obj_ids"]],
        "audit_trail": {
            "producer": "proofnav.adapters.sanitize_duet_observation",
            "source_schema": "duet.reverie._get_obs@frozen-m0",
        },
    }
    return validate_observation(value)


def canonicalize_m0_action(model_scores_event, action_event):
    """Convert one M0 score/action pair without treating index as a global ID."""

    branches = {}
    for branch in ("local", "global", "fused"):
        source = model_scores_event[branch]
        branches[branch] = {
            "action_ids": [
                None if action_id is None else str(action_id)
                for action_id in source["action_ids"]
            ],
            "valid_mask": [bool(value) for value in source["valid_mask"]],
        }
    selected_action = action_event["selected_high_level_action"]
    value = {
        "schema_version": SCHEMA_VERSIONS["action"],
        "episode_id": str(action_event["instr_id"]),
        "step": int(action_event["step"]),
        "branches": branches,
        "selected_branch": str(action_event["selected_branch"]),
        "selected_index": int(action_event["selected_index"]),
        "selected_action_id": (
            None if selected_action is None else str(selected_action)
        ),
        "selected_action_kind": (
            "STOP" if selected_action is None else "VIEWPOINT"
        ),
        "proposal_score_semantics": "uncalibrated_duet_task_score",
        "audit_trail": {
            "producer": "proofnav.adapters.canonicalize_m0_action",
            "source_trace_schema": model_scores_event["trace_schema_version"],
            "model_event_seq": int(model_scores_event["event_seq"]),
            "action_event_seq": int(action_event["event_seq"]),
        },
    }
    return validate_action(value)
