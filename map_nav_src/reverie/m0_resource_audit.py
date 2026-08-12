"""Validate the extracted resources required by the frozen REVERIE baseline."""

import argparse
import json
import os

import h5py
import torch


SPLITS = ("train", "val_train_seen", "val_seen", "val_unseen", "test")


def annotation_summary(annotation_dir):
    summaries = {}
    all_scans = set()
    for split in SPLITS:
        path = os.path.join(annotation_dir, "REVERIE_%s_enc.json" % split)
        with open(path) as infile:
            items = json.load(infile)
        required = {"path", "scan", "heading", "instructions", "instr_encodings"}
        for index, item in enumerate(items):
            missing = required - set(item)
            if missing:
                raise ValueError("%s[%d] missing %s" % (split, index, sorted(missing)))
            if len(item["instructions"]) != len(item["instr_encodings"]):
                raise ValueError("%s[%d] instruction/encoding count mismatch" % (split, index))
            if split == "test":
                if "id" not in item:
                    raise ValueError("test[%d] lacks anonymous episode id" % index)
            elif "path_id" not in item or "objId" not in item:
                raise ValueError("%s[%d] lacks evaluator fields" % (split, index))
            all_scans.add(str(item["scan"]))
        summaries[split] = {
            "path_count": len(items),
            "instruction_count": sum(len(x["instructions"]) for x in items),
            "scan_count": len({str(x["scan"]) for x in items}),
        }
    return summaries, all_scans


def connectivity_summary(connectivity_dir, expected_scans):
    with open(os.path.join(connectivity_dir, "scans.txt")) as infile:
        listed_scans = {line.strip() for line in infile if line.strip()}
    if not expected_scans <= listed_scans:
        raise ValueError("annotation scans missing from connectivity scans.txt")
    viewpoints = set()
    edge_count = 0
    for scan in sorted(expected_scans):
        with open(os.path.join(connectivity_dir, "%s_connectivity.json" % scan)) as infile:
            items = json.load(infile)
        for i, item in enumerate(items):
            if not item["included"]:
                continue
            viewpoints.add("%s_%s" % (scan, item["image_id"]))
            for j, connected in enumerate(item["unobstructed"]):
                if connected and items[j]["included"]:
                    if not items[j]["unobstructed"][i]:
                        raise ValueError("asymmetric edge in scan %s" % scan)
                    edge_count += 1
    return {
        "listed_scan_count": len(listed_scans),
        "reverie_scan_count": len(expected_scans),
        "reverie_included_viewpoint_count": len(viewpoints),
        "reverie_directed_edge_count": edge_count,
    }, viewpoints


def panorama_summary(path, expected_viewpoints):
    shape_counts = {}
    keys = set()
    with h5py.File(path, "r") as infile:
        for key, dataset in infile.items():
            keys.add(str(key))
            shape = tuple(int(x) for x in dataset.shape)
            if len(shape) != 2 or shape[0] != 36 or shape[1] < 768:
                raise ValueError("invalid panorama feature shape %s: %r" % (key, shape))
            shape_counts[str(shape)] = shape_counts.get(str(shape), 0) + 1
        if not keys:
            raise ValueError("empty panorama HDF5")
    missing = sorted(expected_viewpoints - keys)
    if missing:
        raise ValueError("%d REVERIE viewpoints missing panorama features" % len(missing))
    return {
        "key_count": len(keys),
        "shape_counts": shape_counts,
        "missing_reverie_viewpoint_count": len(missing),
    }


def object_summary(path):
    shape_counts = {}
    with h5py.File(path, "r") as infile:
        key_count = len(infile)
        for key, dataset in infile.items():
            shape = tuple(int(x) for x in dataset.shape)
            if len(shape) != 2 or shape[1] < 768:
                raise ValueError("invalid object feature shape %s: %r" % (key, shape))
            shape_counts[str(shape)] = shape_counts.get(str(shape), 0) + 1
            for attr in ("directions", "sizes", "obj_ids"):
                if attr not in dataset.attrs:
                    raise ValueError("object feature %s lacks %s" % (key, attr))
                if len(dataset.attrs[attr]) != shape[0]:
                    raise ValueError("object feature %s attr length mismatch" % key)
        if not key_count:
            raise ValueError("empty object HDF5")
    return {"key_count": key_count, "shape_counts": shape_counts}


def checkpoint_summary(path):
    state = torch.load(path, map_location="cpu")
    if set(state) != {"vln_bert", "critic"}:
        raise ValueError("unexpected checkpoint top-level keys: %s" % sorted(state))
    summary = {}
    for component in ("vln_bert", "critic"):
        component_state = state[component]
        if "state_dict" not in component_state or "epoch" not in component_state:
            raise ValueError("checkpoint component %s has invalid schema" % component)
        summary[component] = {
            "epoch": int(component_state["epoch"]),
            "parameter_tensor_count": len(component_state["state_dict"]),
        }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    annotation_dir = os.path.join(args.root_dir, "REVERIE", "annotations")
    connectivity_dir = os.path.join(args.root_dir, "R2R", "connectivity")
    annotations, scans = annotation_summary(annotation_dir)
    connectivity, viewpoints = connectivity_summary(connectivity_dir, scans)

    bbox_path = os.path.join(annotation_dir, "BBoxes.json")
    with open(bbox_path) as infile:
        bbox_count = len(json.load(infile))
    if bbox_count == 0:
        raise ValueError("empty BBoxes.json")

    report = {
        "audit_type": "m0.resource_schema.v1",
        "annotations": annotations,
        "connectivity": connectivity,
        "bbox_viewpoint_count": bbox_count,
        "panorama_hdf5": panorama_summary(os.path.join(
            args.root_dir, "R2R", "features",
            "pth_vit_base_patch16_224_imagenet.hdf5",
        ), viewpoints),
        "object_hdf5": object_summary(os.path.join(
            args.root_dir, "REVERIE", "features",
            "obj.avg.top3.min80_vit_base_patch16_224_imagenet.hdf5",
        )),
        "checkpoint": checkpoint_summary(os.path.join(
            args.root_dir, "REVERIE", "trained_models", "best_val_unseen",
        )),
        "passed": True,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
