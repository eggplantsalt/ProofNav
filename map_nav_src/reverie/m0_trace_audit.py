"""Validate M0 runtime traces and tracing on/off prediction equivalence."""

import argparse
import json


ALLOWED_EVENTS = {
    "observation", "model_scores", "action", "termination", "execution",
    "prediction",
}
FORBIDDEN_KEYS = {
    "gt_path", "gt_end_vps", "gt_obj_id", "distance", "obj2vps", "graphs",
    "shortest_paths", "shortest_distances", "bboxes", "evaluator", "metrics",
    "sr", "oracle_sr", "spl", "rgs", "rgspl",
}
FORBIDDEN_NAME_FRAGMENTS = ("ground_truth", "connectivity")


def load_jsonl(path):
    with open(path) as infile:
        return [json.loads(line) for line in infile if line.strip()]


def scan_forbidden(value, location="$"):
    failures = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS or any(x in lowered for x in FORBIDDEN_NAME_FRAGMENTS):
                failures.append("%s.%s" % (location, key))
            failures.extend(scan_forbidden(child, "%s.%s" % (location, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(scan_forbidden(child, "%s[%d]" % (location, index)))
    return failures


def canonical_predictions(path):
    with open(path) as infile:
        values = json.load(infile)
    return {
        str(x["instr_id"]): {
            "trajectory": x["trajectory"],
            "step_actions": [segment[-1] for segment in x["trajectory"][1:]] + [None],
            "pred_objid": (
                None if x.get("pred_objid") is None else str(x["pred_objid"])
            ),
        }
        for x in values
    }


def normalized_actions(events):
    return [(
        x["episode_index"], x["step"], x["selected_branch"],
        x["selected_index"], x["selected_high_level_action"],
    ) for x in events if x["event_type"] == "action"]


def validate(events, require_multihop=False):
    failures = []
    models = {}
    observations = {}
    multihop_count = 0
    previous_by_episode = {}
    for event in events:
        if event.get("event_type") not in ALLOWED_EVENTS:
            failures.append("invalid event type: %r" % event.get("event_type"))
        failures.extend(scan_forbidden(event))
        episode_index = event.get("episode_index")
        previous = previous_by_episode.get(episode_index)
        if previous is None:
            if event.get("event_seq") != 0 or "causal_parent_seq" in event:
                failures.append("invalid first-event sequence for episode %r" % episode_index)
        else:
            if event.get("event_seq") != previous["event_seq"] + 1:
                failures.append("non-contiguous event sequence for episode %r" % episode_index)
            if event.get("causal_parent_seq") != previous["event_seq"]:
                failures.append("broken causal parent for episode %r" % episode_index)
            if event.get("monotonic_time_ns", 0) < previous.get("monotonic_time_ns", 0):
                failures.append("non-monotonic timestamp for episode %r" % episode_index)
        previous_by_episode[episode_index] = event
        key = (event.get("episode_index"), event.get("step"))
        if event.get("event_type") == "model_scores":
            models[key] = event
            for branch in ("local", "global", "fused"):
                part = event[branch]
                lengths = {
                    len(part["action_ids"]), len(part["valid_mask"]),
                    len(part["logits"]),
                }
                if len(lengths) != 1:
                    failures.append("%s length mismatch at %r" % (branch, key))
                if part["action_ids"][0] is not None:
                    failures.append("%s stop ID is not null at %r" % (branch, key))
        elif event.get("event_type") == "action":
            model = models.get(key)
            if model is None:
                failures.append("action lacks prior scores at %r" % (key,))
            else:
                branch = event["selected_branch"]
                index = event["selected_index"]
                action_ids = model[branch]["action_ids"]
                if index >= len(action_ids):
                    failures.append("selected index out of range at %r" % (key,))
                elif event["selected_high_level_action"] != action_ids[index]:
                    failures.append("selected action mapping mismatch at %r" % (key,))
        elif event.get("event_type") == "observation":
            observations[(event.get("episode_index"), event["observation_index"])] = event
            for candidate in event["candidate_schema"]:
                if candidate["evidence_role"] != "unobserved_navigation_proposal":
                    failures.append("candidate mislabeled as observation at %r" % (key,))
        elif event.get("event_type") == "termination":
            priority = event["trigger_priority"]
            expected_trigger = next(
                (name for name in priority if event["flags"].get(name)), None
            )
            if event["selected_trigger"] != expected_trigger:
                failures.append("termination priority mismatch at %r" % (key,))
            if event["environment_action_is_none"] != (expected_trigger is not None):
                failures.append("termination/action-none mismatch at %r" % (key,))
        elif event.get("event_type") == "execution":
            path = event["expanded_path"]
            if (not path or event["expanded_path_includes_source"]
                    or path[-1] != event["destination_viewpoint"]
                    or path[-1] != event["observation_endpoint"]):
                failures.append("execution path endpoints mismatch at %r" % (key,))
            if event["travel_only_nodes"] != path[:-1]:
                failures.append("travel-only expansion mismatch at %r" % (key,))
            if len(path) >= 2:
                multihop_count += 1
    for event in events:
        if event.get("event_type") == "execution":
            obs_key = (event["episode_index"], event["next_observation_index"])
            next_obs = observations.get(obs_key)
            if next_obs is None:
                failures.append("execution lacks endpoint observation at %r" % (obs_key,))
            elif next_obs["viewpoint"] != event["observation_endpoint"]:
                failures.append("endpoint observation mismatch at %r" % (obs_key,))
    if require_multihop and multihop_count == 0:
        failures.append("no two-hop-or-longer global execution found")
    return failures, multihop_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--repeat_trace")
    parser.add_argument("--tracing_on_predictions")
    parser.add_argument("--tracing_off_predictions")
    parser.add_argument("--require_multihop", action="store_true")
    args = parser.parse_args()

    events = load_jsonl(args.trace)
    failures, multihop_count = validate(events, args.require_multihop)
    action_repeat_equal = None
    if args.repeat_trace:
        repeated = load_jsonl(args.repeat_trace)
        repeat_failures, _ = validate(repeated, args.require_multihop)
        failures.extend(repeat_failures)
        action_repeat_equal = normalized_actions(events) == normalized_actions(repeated)
        if not action_repeat_equal:
            failures.append("fixed-sample action sequence differs across traced repeats")
    prediction_equal = None
    trajectory_equal = None
    derived_step_actions_equal = None
    pred_objid_equal = None
    if args.tracing_on_predictions and args.tracing_off_predictions:
        on_predictions = canonical_predictions(args.tracing_on_predictions)
        off_predictions = canonical_predictions(args.tracing_off_predictions)
        same_ids = set(on_predictions) == set(off_predictions)
        trajectory_equal = same_ids and all(
            on_predictions[key]["trajectory"] == off_predictions[key]["trajectory"]
            for key in on_predictions
        )
        derived_step_actions_equal = same_ids and all(
            on_predictions[key]["step_actions"] == off_predictions[key]["step_actions"]
            for key in on_predictions
        )
        pred_objid_equal = same_ids and all(
            on_predictions[key]["pred_objid"] == off_predictions[key]["pred_objid"]
            for key in on_predictions
        )
        prediction_equal = bool(
            trajectory_equal and derived_step_actions_equal and pred_objid_equal
        )
        if not prediction_equal:
            failures.append("tracing on/off canonical predictions differ")
    summary = {
        "event_count": len(events),
        "multihop_execution_count": multihop_count,
        "fixed_sample_action_repeat_equal": action_repeat_equal,
        "tracing_on_off_prediction_equal": prediction_equal,
        "tracing_on_off_trajectory_equal": trajectory_equal,
        "tracing_on_off_derived_step_actions_equal": derived_step_actions_equal,
        "tracing_on_off_pred_objid_equal": pred_objid_equal,
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(summary, sort_keys=True, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
