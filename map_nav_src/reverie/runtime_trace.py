"""Default-off, sanitized runtime tracing for the frozen DUET REVERIE policy.

The sink accepts only explicitly copied primitive values.  It intentionally has
no environment, observation-dict, simulator, evaluator, or graph-container
reference, so evaluator truth cannot be reached through the sink.
"""

import json
import math
import time
import uuid

import numpy as np


TRACE_SCHEMA_VERSION = "m0.runtime.v1"


def _shape_dtype(value):
    return {
        "shape": [int(x) for x in value.shape],
        "dtype": str(value.dtype),
    }


def _score(value):
    value = float(value)
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return value


def _scores(tensor):
    return [_score(x) for x in tensor.detach().cpu().tolist()]


def _bools(tensor):
    return [bool(x) for x in tensor.detach().cpu().tolist()]


def _ids_with_padding(ids, length):
    copied = [None if x is None else str(x) for x in ids[:length]]
    return copied + [None] * (length - len(copied))


class RuntimeTraceSink(object):
    """Write an allowlisted JSONL trace for at most ``max_episodes`` episodes."""

    def __init__(self, path, fusion_mode, max_episodes=1):
        self.path = path
        self.fusion_mode = str(fusion_mode)
        self.max_episodes = int(max_episodes)
        self.run_id = str(uuid.uuid4())
        self._file = open(path, "w", encoding="utf-8")
        self._episodes_started = 0
        self._active = {}

    def close(self):
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None
        self._active = {}

    def begin_batch(self, obs):
        self._active = {}
        for batch_index, ob in enumerate(obs):
            if self._episodes_started >= self.max_episodes:
                break
            episode_index = self._episodes_started
            self._episodes_started += 1
            self._active[batch_index] = {
                "episode_index": episode_index,
                "instr_id": str(ob["instr_id"]),
                "event_seq": 0,
                "observation_index": 0,
                "last_event_seq": None,
            }
            self.observation(batch_index, ob, step=0, causal_parent_seq=None)

    def _emit(self, batch_index, step, event_type, payload, causal_parent_seq=None):
        state = self._active.get(batch_index)
        if state is None:
            return None
        if causal_parent_seq is None:
            causal_parent_seq = state["last_event_seq"]
        event_seq = state["event_seq"]
        event = {
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "episode_index": state["episode_index"],
            "instr_id": state["instr_id"],
            "step": int(step),
            "event_seq": event_seq,
            "event_type": event_type,
            "monotonic_time_ns": time.monotonic_ns(),
        }
        if causal_parent_seq is not None:
            event["causal_parent_seq"] = int(causal_parent_seq)
        event.update(payload)
        self._file.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        self._file.flush()
        state["event_seq"] += 1
        state["last_event_seq"] = event_seq
        return event_seq

    def observation(self, batch_index, ob, step, causal_parent_seq):
        state = self._active.get(batch_index)
        if state is None:
            return
        candidate_schema = []
        for candidate in ob["candidate"]:
            candidate_schema.append({
                "viewpoint_id": str(candidate["viewpointId"]),
                "point_id": int(candidate["pointId"]),
                "heading": float(candidate["heading"]),
                "elevation": float(candidate["elevation"]),
                "position": [float(x) for x in candidate["position"]],
                "simulator_index": int(candidate["idx"]),
                "feature_schema": _shape_dtype(candidate["feature"]),
                "original_keys": sorted(str(x) for x in candidate.keys()),
                "candidate_distance_present": "distance" in candidate,
                "candidate_distance_semantics": "angular_representative_selection_only",
                "evidence_role": "unobserved_navigation_proposal",
            })
        payload = {
            "observation_index": state["observation_index"],
            "scan": str(ob["scan"]),
            "viewpoint": str(ob["viewpoint"]),
            "view_index": int(ob["viewIndex"]),
            "pose": {
                "heading": float(ob["heading"]),
                "elevation": float(ob["elevation"]),
                "position": [float(x) for x in ob["position"]],
            },
            "field_schema": {
                "feature": _shape_dtype(ob["feature"]),
                "obj_img_fts": _shape_dtype(ob["obj_img_fts"]),
                "obj_ang_fts": _shape_dtype(ob["obj_ang_fts"]),
                "obj_box_fts": _shape_dtype(ob["obj_box_fts"]),
                "instr_encoding": _shape_dtype(np.asarray(ob["instr_encoding"])),
            },
            "instruction_length_chars": len(ob["instruction"]),
            "candidate_ids": [str(x["viewpointId"]) for x in ob["candidate"]],
            "candidate_schema": candidate_schema,
            "object_proposal_ids": [str(x) for x in ob["obj_ids"]],
        }
        self._emit(batch_index, step, "observation", payload, causal_parent_seq)
        state["observation_index"] += 1

    def model_scores(self, batch_index, step, nav_outs, nav_inputs, pano_inputs, gmap):
        if batch_index not in self._active:
            return
        local_logits = nav_outs["local_logits"][batch_index]
        global_logits = nav_outs["global_logits"][batch_index]
        fused_logits = nav_outs["fused_logits"][batch_index]

        local_ids = _ids_with_padding(
            nav_inputs["vp_cand_vpids"][batch_index], len(local_logits)
        )
        global_ids = _ids_with_padding(
            nav_inputs["gmap_vpids"][batch_index], len(global_logits)
        )
        object_start = int(pano_inputs["view_lens"][batch_index].item()) + 1
        object_ids = [str(x) for x in pano_inputs["obj_ids"][batch_index]]
        object_logits = nav_outs["obj_logits"][batch_index][
            object_start:object_start + len(object_ids)
        ]

        visited, unvisited = [], []
        for viewpoint in gmap.node_positions.keys():
            target = visited if gmap.graph.visited(viewpoint) else unvisited
            target.append(str(viewpoint))

        self._emit(batch_index, step, "model_scores", {
            "score_semantics": "uncalibrated_duet_task_scores",
            "fusion_mode": self.fusion_mode,
            "local": {
                "action_ids": local_ids,
                "valid_mask": _bools(nav_inputs["vp_nav_masks"][batch_index]),
                "logits": _scores(local_logits),
            },
            "global": {
                "action_ids": global_ids,
                "valid_mask": _bools(nav_inputs["gmap_masks"][batch_index]),
                "visited_mask": _bools(nav_inputs["gmap_visited_masks"][batch_index]),
                "logits": _scores(global_logits),
            },
            "fused": {
                "action_ids": global_ids,
                "valid_mask": _bools(
                    nav_inputs["gmap_masks"][batch_index]
                    & nav_inputs["gmap_visited_masks"][batch_index].logical_not()
                ),
                "logits": _scores(fused_logits),
            },
            "objects": {
                "proposal_ids": object_ids,
                "valid_mask": [True] * len(object_ids),
                "logits": _scores(object_logits),
            },
            "graph_map": {
                "visited_viewpoints": visited,
                "unvisited_viewpoints": unvisited,
            },
        })

    def action(self, batch_index, step, selected_index, selected_high_level_action):
        branch = self.fusion_mode if self.fusion_mode in ("local", "global") else "fused"
        self._emit(batch_index, step, "action", {
            "selected_branch": branch,
            "selected_index": int(selected_index),
            "selected_high_level_action": (
                None if selected_high_level_action is None
                else str(selected_high_level_action)
            ),
        })

    def termination(self, batch_index, step, flags, environment_action_is_none):
        copied_flags = {str(k): bool(v) for k, v in flags.items()}
        trigger_priority = [
            "duet_stop", "episode_already_done", "no_frontier", "max_step",
        ]
        selected_trigger = next(
            (name for name in trigger_priority if copied_flags.get(name)), None
        )
        return self._emit(batch_index, step, "termination", {
            "flags": copied_flags,
            "trigger_priority": trigger_priority,
            "selected_trigger": selected_trigger,
            "environment_action_is_none": bool(environment_action_is_none),
        })

    def execution(self, batch_index, step, source_viewpoint, destination_viewpoint,
                  expanded_path):
        copied_path = [str(x) for x in expanded_path]
        state = self._active.get(batch_index)
        if state is None:
            return None
        return self._emit(batch_index, step, "execution", {
            "source_viewpoint": str(source_viewpoint),
            "destination_viewpoint": str(destination_viewpoint),
            "expanded_path": copied_path,
            "expanded_path_includes_source": False,
            "travel_only_nodes": copied_path[:-1],
            "observation_endpoint": copied_path[-1],
            "next_observation_index": state["observation_index"],
        })

    def next_observations(self, obs, step):
        for batch_index, ob in enumerate(obs):
            state = self._active.get(batch_index)
            if state is not None:
                self.observation(
                    batch_index, ob, step,
                    causal_parent_seq=state["last_event_seq"],
                )

    def predictions(self, traj):
        for batch_index, prediction in enumerate(traj):
            if batch_index not in self._active:
                continue
            copied_trajectory = [
                [str(viewpoint) for viewpoint in path]
                for path in prediction["path"]
            ]
            state = self._active[batch_index]
            self._emit(batch_index, len(copied_trajectory) - 1, "prediction", {
                "trajectory": copied_trajectory,
                "pred_objid": (
                    None if prediction["pred_objid"] is None
                    else str(prediction["pred_objid"])
                ),
            }, causal_parent_seq=state["last_event_seq"])
        self._active = {}
