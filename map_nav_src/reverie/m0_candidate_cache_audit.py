"""Offline runtime check for first-build versus cached candidate schemas."""

import argparse
import json
import os

import numpy as np

from utils.data import ImageFeaturesDB
from reverie.data_utils import ObjectFeatureDB, construct_instrs, load_obj2vps
from reverie.env import ReverieObjectNavBatch


DECISION_FIELDS = (
    "viewpointId", "pointId", "heading", "elevation", "position", "idx",
    "feature",
)


def equal_value(left, right):
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return np.array_equal(np.asarray(left), np.asarray(right))
    return left == right


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    annotation_dir = os.path.join(args.root_dir, "REVERIE", "annotations")
    view_db = ImageFeaturesDB(os.path.join(
        args.root_dir, "R2R", "features",
        "pth_vit_base_patch16_224_imagenet.hdf5",
    ), 768)
    obj_db = ObjectFeatureDB(os.path.join(
        args.root_dir, "REVERIE", "features",
        "obj.avg.top3.min80_vit_base_patch16_224_imagenet.hdf5",
    ), 768)
    data = construct_instrs(
        annotation_dir, "reverie", ["val_unseen"], "bert", max_instr_len=200
    )
    env = ReverieObjectNavBatch(
        view_db, obj_db, data,
        os.path.join(args.root_dir, "R2R", "connectivity"),
        load_obj2vps(os.path.join(annotation_dir, "BBoxes.json")),
        batch_size=1, angle_feat_size=4, max_objects=None, seed=0,
        name="m0_candidate_cache_audit",
    )
    first = env.reset()[0]
    cached = env._get_obs()[0]

    first_by_id = {str(x["viewpointId"]): x for x in first["candidate"]}
    cached_by_id = {str(x["viewpointId"]): x for x in cached["candidate"]}
    shared_ids = sorted(set(first_by_id) & set(cached_by_id))
    decision_fields_equal = (
        set(first_by_id) == set(cached_by_id)
        and all(
            equal_value(first_by_id[candidate_id][field],
                        cached_by_id[candidate_id][field])
            for candidate_id in shared_ids
            for field in DECISION_FIELDS
        )
    )

    agent_path = os.path.join(os.path.dirname(__file__), "agent_obj.py")
    with open(agent_path) as infile:
        agent_source = infile.read()
    report = {
        "audit_type": "m0.candidate_cache.v1",
        "instr_id": str(first["instr_id"]),
        "scan": str(first["scan"]),
        "viewpoint": str(first["viewpoint"]),
        "candidate_count": len(first["candidate"]),
        "first_candidate_key_sets": sorted({
            tuple(sorted(str(key) for key in x.keys())) for x in first["candidate"]
        }),
        "cached_candidate_key_sets": sorted({
            tuple(sorted(str(key) for key in x.keys())) for x in cached["candidate"]
        }),
        "first_distance_present": all("distance" in x for x in first["candidate"]),
        "cached_distance_present": any("distance" in x for x in cached["candidate"]),
        "candidate_ids_equal": set(first_by_id) == set(cached_by_id),
        "decision_fields_equal": bool(decision_fields_equal),
        "agent_reads_candidate_distance": (
            "['distance']" in agent_source or '["distance"]' in agent_source
        ),
    }
    report["contract_passed"] = bool(
        report["first_distance_present"]
        and not report["cached_distance_present"]
        and report["candidate_ids_equal"]
        and report["decision_fields_equal"]
        and not report["agent_reads_candidate_distance"]
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True, indent=2))
    if not report["contract_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
