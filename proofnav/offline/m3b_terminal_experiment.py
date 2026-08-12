"""Precommitted M3-B terminal-cut experiment.

The policy and six seen-domain confirmation scans are frozen in
``docs/M3B_SCIENTIFIC_PRECOMMIT.md``.  This module filters to those scans
before loading evaluator annotations.  It emits a descriptive report and an
explicit hypothetical binomial bound; it never builds a runtime calibration
artifact or grants certificate authority.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import math
import os

from proofnav.adapters import derive_runtime_episode_id
from proofnav.contracts import canonical_sha256
from proofnav.perception.terminal_signal import validate_terminal_signal


SUPPORT_THRESHOLD = 3.0
CONFIRMATORY_SCANS = (
    "B6ByNegPMKs", "D7N2EKCX4Sj", "S9hNv5qa7GM",
    "ac26ZMwG7aT", "p5wJjkQkbXX", "ur6pFq6Qu1A",
)
REPORT_SCHEMA_VERSION = "proofnav.m3b-terminal-experiment-report.v1"


def _raw_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def one_sided_clopper_pearson_upper(errors, units, confidence=0.95):
    """Exact binomial upper endpoint without a scipy dependency.

    This numerical quantity is applicable only under the stated i.i.d.
    Bernoulli/exchangeability assumptions; callers must not turn it into a
    runtime guarantee merely because it was computed here.
    """

    if (isinstance(errors, bool) or isinstance(units, bool)
            or not isinstance(errors, int) or not isinstance(units, int)
            or units <= 0 or errors < 0 or errors > units):
        raise ValueError("expected 0 <= integer errors <= positive units")
    if not isinstance(confidence, (int, float)) or not 0 < confidence < 1:
        raise ValueError("confidence must be in (0,1)")
    if errors == units:
        return 1.0
    alpha = 1.0 - float(confidence)

    def cdf(probability):
        return sum(
            math.comb(units, index)
            * probability ** index
            * (1.0 - probability) ** (units - index)
            for index in range(errors + 1)
        )

    lower, upper = 0.0, 1.0
    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        # Binomial CDF at fixed k decreases with p.
        if cdf(midpoint) > alpha:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def minimum_zero_error_units(alpha=0.05, confidence=0.95):
    if not 0 < alpha < 1 or not 0 < confidence < 1:
        raise ValueError("alpha and confidence must be in (0,1)")
    return int(math.ceil(
        math.log(1.0 - confidence) / math.log(1.0 - alpha)
    ))


def _read_terminal_signals(path):
    records = []
    with open(path, "r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                records.append(validate_terminal_signal(json.loads(line)))
            except Exception as error:
                raise ValueError(
                    "invalid terminal signal line %d: %s" %
                    (line_number, error)
                )
    if not records:
        raise ValueError("terminal signal JSONL is empty")
    return records


def _source_replay_diagnostics(records):
    starts = {}
    for item in records:
        episode_id = _episode(item)
        if _event_seq(item) == 0:
            starts[episode_id] = starts.get(episode_id, 0) + 1
    return {
        "unique_episode_count": len(starts),
        "wrapped_episode_ids": sorted(
            episode_id for episode_id, count in starts.items() if count > 1
        ),
        "wrapped_episode_count": sum(count > 1 for count in starts.values()),
    }


def _annotation_index(path):
    with open(path, "r", encoding="utf-8") as stream:
        annotations = json.load(stream)
    index = {}
    for item in annotations:
        target = str(item["objId"])
        for instruction in item["instructions"]:
            episode_id = derive_runtime_episode_id(
                item["scan"], item["path"][0], instruction,
            )
            if episode_id in index:
                raise ValueError("duplicate annotation episode %s" % episode_id)
            index[episode_id] = {
                "scan": item["scan"],
                "instruction": instruction,
                "target_object_id": target,
            }
    return index


def _selected(record):
    return record["base_signal"]["object_scores"]["selected_proposal_id"]


def _score(record):
    return record["base_signal"]["object_scores"]["selected_statistic"]


def _episode(record):
    return record["base_signal"]["observation"]["episode_id"]


def _scan(record):
    return record["base_signal"]["observation"]["scan"]


def _event_seq(record):
    return record["base_signal"]["observation"]["event_seq"]


def _truth(record, annotations):
    episode_id = _episode(record)
    if episode_id not in annotations:
        raise ValueError("missing annotation for %s" % episode_id)
    item = annotations[episode_id]
    observation = record["base_signal"]["observation"]
    if (item["scan"] != observation["scan"]
            or item["instruction"] != observation["instruction"]):
        raise ValueError("offline tuple join mismatch for %s" % episode_id)
    selected = _selected(record)
    return selected is not None and str(selected) == item["target_object_id"]


def _method_summary(records, annotations, mode):
    by_episode = {}
    for record in records:
        by_episode.setdefault(_episode(record), []).append(record)
    accepted = []
    for episode_records in by_episode.values():
        ordered = sorted(episode_records, key=_event_seq)
        if mode == "all_step":
            chosen = ordered
        elif mode == "episode_max":
            finite = [item for item in ordered if _score(item) is not None]
            chosen = ([max(finite, key=lambda item: (_score(item), -_event_seq(item)))]
                      if finite else [])
        elif mode == "terminal_cut":
            chosen = [
                item for item in ordered
                if item["decision_context"]["duet_stop"]
            ]
            if len(chosen) > 1:
                raise ValueError("episode has multiple explicit DUET stops")
        elif mode == "last_active":
            chosen = [ordered[-1]]
        else:
            raise ValueError("unknown method %s" % mode)
        accepted.extend(
            item for item in chosen
            if _score(item) is not None
            and float(_score(item)) >= SUPPORT_THRESHOLD
        )

    false_records = [item for item in accepted if not _truth(item, annotations)]
    true_records = [item for item in accepted if _truth(item, annotations)]
    error_scans = sorted({_scan(item) for item in false_records})
    accepted_episodes = sorted({_episode(item) for item in accepted})
    total_episodes = len(by_episode)
    units = len({_scan(item) for item in records})
    return {
        "accepted_record_count": len(accepted),
        "true_support_count": len(true_records),
        "false_support_count": len(false_records),
        "accepted_episode_count": len(accepted_episodes),
        "episode_count": total_episodes,
        "episode_coverage": (
            float(len(accepted_episodes)) / total_episodes
            if total_episodes else 0.0
        ),
        "error_scan_ids": error_scans,
        "error_scan_count": len(error_scans),
        "scan_count": units,
        "empirical_scan_familywise_error": float(len(error_scans)) / units,
        "hypothetical_iid_one_sided_95pct_cp_upper":
            one_sided_clopper_pearson_upper(len(error_scans), units),
    }


def run_terminal_experiment(signal_file, annotation_file, output_file,
                            precommit_file="docs/M3B_SCIENTIFIC_PRECOMMIT.md"):
    all_records = _read_terminal_signals(signal_file)
    # Method/split filtering is complete before evaluator truth is opened.
    records = [
        item for item in all_records if _scan(item) in CONFIRMATORY_SCANS
    ]
    present = sorted({_scan(item) for item in records})
    if present != sorted(CONFIRMATORY_SCANS):
        raise ValueError("confirmatory scan set incomplete: %s" % present)
    confirm_digests = [item["terminal_signal_digest"] for item in records]
    if len(confirm_digests) != len(set(confirm_digests)):
        raise ValueError("confirmatory slice contains duplicate terminal signals")
    by_episode = {}
    for item in records:
        by_episode.setdefault(_episode(item), []).append(_event_seq(item))
    for episode_id, sequences in by_episode.items():
        if sorted(sequences) != list(range(len(sequences))):
            raise ValueError(
                "confirmatory episode is not one exact causal prefix: %s" %
                episode_id
            )
    annotations = _annotation_index(annotation_file)
    methods = {
        name: _method_summary(records, annotations, name)
        for name in ("all_step", "episode_max", "terminal_cut", "last_active")
    }
    baseline = methods["all_step"]
    champion = methods["terminal_cut"]
    continue_gate = (
        champion["error_scan_count"] < baseline["error_scan_count"]
        and champion["accepted_episode_count"]
        >= 0.5 * baseline["accepted_episode_count"]
    )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "DIRECTIONAL_CONTINUE" if continue_gate else "REVISE",
        "policy": {
            "support_threshold": SUPPORT_THRESHOLD,
            "champion": "explicit_duet_stop_terminal_cut",
            "statistical_unit": "scan_familywise",
            "confirmatory_scan_ids": list(CONFIRMATORY_SCANS),
        },
        "truth_firewall": {
            "method_and_scan_filter_frozen_before_annotation_load": True,
            "annotation_use": "offline_evaluation_only",
            "runtime_target_id_access": False,
        },
        "source": {
            "signal_file": signal_file,
            "signal_file_sha256": _raw_sha256(signal_file),
            "annotation_file": annotation_file,
            "annotation_file_sha256": _raw_sha256(annotation_file),
            "precommit_file": precommit_file,
            "precommit_file_sha256": _raw_sha256(precommit_file),
            "all_source_record_count": len(all_records),
            "source_replay_diagnostics":
                _source_replay_diagnostics(all_records),
            "confirmatory_record_count": len(records),
            "confirmatory_episode_count": len({_episode(item) for item in records}),
        },
        "methods": methods,
        "continue_gate": {
            "passed": bool(continue_gate),
            "requires_fewer_error_scans": True,
            "requires_at_least_half_baseline_episode_coverage": True,
        },
        "statistical_semantics": {
            "current_results_are_descriptive": True,
            "iid_exchangeability_established": False,
            "cp_value_is_hypothetical_under_iid_bernoulli_scans": True,
            "alpha_target": 0.05,
            "confidence_target": 0.95,
            "minimum_independent_zero_error_units_for_target":
                minimum_zero_error_units(),
            "authoritative_calibration_artifact_created": False,
        },
        "capability_boundary": {
            "supports": ["entity_SUPPORT_eligibility_at_explicit_DUET_STOP"],
            "sealed": [
                "REFUTE", "residual_coverage", "NOT_FOUND", "SAME_ENTITY",
                "attribute", "relation", "room",
            ],
        },
    }
    report["report_digest"] = canonical_sha256(report)
    parent = os.path.dirname(os.path.abspath(output_file))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(output_file, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal-file", required=True)
    parser.add_argument("--annotation-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument(
        "--precommit-file", default="docs/M3B_SCIENTIFIC_PRECOMMIT.md",
    )
    args = parser.parse_args(argv)
    report = run_terminal_experiment(
        args.signal_file, args.annotation_file, args.output_file,
        args.precommit_file,
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()


__all__ = [
    "CONFIRMATORY_SCANS", "REPORT_SCHEMA_VERSION", "SUPPORT_THRESHOLD",
    "minimum_zero_error_units", "one_sided_clopper_pearson_upper",
    "run_terminal_experiment",
]
