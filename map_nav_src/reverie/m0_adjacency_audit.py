"""Offline audit of MatterSim candidate unions against connectivity truth.

This is evaluator/offline tooling.  Its output must never be read by the policy
or written to ``runtime_trace.jsonl``.
"""

import argparse
import glob
import json
import math
import os

import MatterSim


def annotation_scans(annotation_dir):
    scans = set()
    files = sorted(glob.glob(os.path.join(annotation_dir, "REVERIE_*_enc.json")))
    for path in files:
        with open(path) as infile:
            for item in json.load(infile):
                if "scan" in item:
                    scans.add(str(item["scan"]))
    return scans, files


def connectivity_truth(path):
    with open(path) as infile:
        records = json.load(infile)
    included = [bool(x["included"]) for x in records]
    truth = {}
    for i, item in enumerate(records):
        if not included[i]:
            continue
        truth[str(item["image_id"])] = {
            str(records[j]["image_id"])
            for j, connected in enumerate(item["unobstructed"])
            if connected and included[j]
        }
    return truth


def simulator_candidate_union(sim, scan, viewpoint):
    candidates = set()
    for view_index in range(36):
        if view_index == 0:
            sim.newEpisode([scan], [viewpoint], [0], [math.radians(-30)])
        elif view_index % 12 == 0:
            sim.makeAction([0], [1.0], [1.0])
        else:
            sim.makeAction([0], [1.0], [0])
        state = sim.getState()[0]
        if state.viewIndex != view_index:
            raise RuntimeError("MatterSim view-index mismatch")
        candidates.update(
            str(x.viewpointId) for x in state.navigableLocations[1:]
        )
    return candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connectivity_dir", required=True)
    parser.add_argument("--annotation_dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    scans, annotation_files = annotation_scans(args.annotation_dir)
    sim = MatterSim.Simulator()
    sim.setNavGraphPath(args.connectivity_dir)
    sim.setRenderingEnabled(False)
    sim.setDiscretizedViewingAngles(True)
    sim.setBatchSize(1)
    sim.initialize()

    mismatches = []
    viewpoint_count = 0
    directed_edge_count = 0
    for scan in sorted(scans):
        truth = connectivity_truth(os.path.join(
            args.connectivity_dir, "%s_connectivity.json" % scan
        ))
        for viewpoint, expected in sorted(truth.items()):
            actual = simulator_candidate_union(sim, scan, viewpoint)
            viewpoint_count += 1
            directed_edge_count += len(expected)
            if actual != expected:
                mismatches.append({
                    "scan": scan,
                    "viewpoint": viewpoint,
                    "missing_from_candidate_union": sorted(expected - actual),
                    "extra_in_candidate_union": sorted(actual - expected),
                })

    report = {
        "audit_type": "m0.offline_adjacency.v1",
        "scope": "all included connectivity viewpoints in every REVERIE annotation scan",
        "annotation_files": [os.path.basename(x) for x in annotation_files],
        "scan_count": len(scans),
        "viewpoint_count": viewpoint_count,
        "directed_connectivity_edge_count": directed_edge_count,
        "mismatch_count": len(mismatches),
        "candidate_completeness_contract_passed": len(mismatches) == 0,
        "mismatches": mismatches,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps({
        key: report[key] for key in (
            "scan_count", "viewpoint_count", "directed_connectivity_edge_count",
            "mismatch_count", "candidate_completeness_contract_passed",
        )
    }, sort_keys=True))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
