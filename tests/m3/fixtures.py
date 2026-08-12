"""Small deterministic M3 fixtures; never calibration or benchmark records.

The values in this module deliberately look like content identities rather
than real resource hashes.  They make staleness and substitution attacks
readable without loading DUET, HDF5, MatterSim, or evaluator truth.
"""

import copy
import json
from pathlib import Path

import numpy as np

from proofnav.calibration import load_registered_calibration_artifact
from proofnav.contracts import canonical_sha256
from proofnav.perception import build_duet_signal, build_entity_proof_template
from proofnav.runtime.semantics import object_unit_id
from tests.m2.fixtures import (
    controlled_observation,
    proof_template,
    risk_claims,
    scope_value,
)


HASHES = {
    "model": "5ed16b0e2b2af6182f4ec60039f48015b9e545647fb459f091ba6e1698297d17",
    "checkpoint": "c74aad4b4c330785c945844ba6a30490962623e938843477e0d062459a9918dc",
    "feature": "6246c6d17401bfacfd0e91ddeab71df9592b9193bd12af22db8f69677509ccc5",
    "interface": "dd62c54efd9456b25273622af865bd396b5460b538221f5840c12c8902ec34b1",
    "config": "0dcbeb53b2fd7c44d79f903fd1df3a2c9aada7a77c07ba982d108ceaa10df780",
    "tokenizer": "07cd6281d985191602d9c3dab43a6562a973e82a27e90d34137a175e8f189106",
    "labels": "7a80131cf589932bbf6bddeb88b3f84022259fe3e5053cc4abfc39aca02bdda4",
    "split": "2bafd4417f7b0a9f1cff6a55412df9c540905b6c802fd57fd2293c312f1167f2",
}
REGISTERED_ARTIFACT_DIGEST = (
    "d2548e03e38c24423f846c372d66ed0abd1dc78b672bf9f6c965566d699f830f"
)
DEFAULT_RUNTIME_SCAN = "1LXtFkjw3qL"
DEFAULT_CALIBRATION_SCAN = "1pXnuDYAj8r"
_REAL_REPLAY_PATH = Path(__file__).parent / "data" / "m3a_seen_micro_replay.json"


def real_replay_signals():
    """Load the tracked, GT-free real DUET prefix used for success paths."""

    with _REAL_REPLAY_PATH.open("r", encoding="utf-8") as handle:
        replay = json.load(handle)
    if (replay.get("schema_version") != "proofnav.registered-signal-replay.v1"
            or replay.get("artifact_digest") != REGISTERED_ARTIFACT_DIGEST):
        raise AssertionError("tracked M3 replay identity drift")
    signals = copy.deepcopy(replay["signals"])
    if replay.get("selected_signal_digest") != signals[-1]["signal_digest"]:
        raise AssertionError("tracked M3 selected signal drift")
    return signals


def real_signal_record():
    return real_replay_signals()[-1]


def real_template():
    return build_entity_proof_template(
        real_signal_record()["observation"]["instruction"],
    )


def real_scope(false_found_budget=1.0):
    signals = real_replay_signals()
    selected = signals[-1]
    value = scope_value(selected["observation"]["episode_id"], production=True)
    value["scan_id"] = selected["observation"]["scan"]
    value["start_viewpoint"] = signals[0]["observation"]["viewpoint"]
    value["calibration_version"] = (
        "proofnav.calibration-artifact.v1:" + REGISTERED_ARTIFACT_DIGEST
    )
    value["risk_budgets"]["false_found"] = float(false_found_budget)
    value["resource_limits"]["max_steps"] = 16
    value["resource_limits"]["max_observation_events"] = 16
    return value


def changed(value, path, replacement):
    """Return a deep copy with one nested mapping field replaced."""

    result = copy.deepcopy(value)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    return result


def identities(**overrides):
    value = {
        "model_digest": HASHES["model"],
        "checkpoint_digest": HASHES["checkpoint"],
        "feature_digest": HASHES["feature"],
        "interface_digest": HASHES["interface"],
        "config_digest": HASHES["config"],
        "tokenizer_digest": HASHES["tokenizer"],
    }
    value.update(overrides)
    return value


def m3_template(premise_class="positive_control"):
    if premise_class == "positive_control":
        return build_entity_proof_template("Find the micro target.")
    return proof_template(premise_class)


def m3_observation(episode_id="m3-episode", object_ids=None, production=True,
                   viewpoint="vp0", event_seq=0, step=0):
    object_ids = ["slot-a", "slot-b"] if object_ids is None else object_ids
    value = controlled_observation(
        episode_id, viewpoint=viewpoint, event_seq=event_seq, step=step,
        candidates=[], object_ids=object_ids,
    )
    value["scan"] = DEFAULT_RUNTIME_SCAN
    if production:
        value["audit_trail"] = {
            "producer": "proofnav.adapters.sanitize_duet_observation",
            "source_schema": "duet.reverie._get_obs@frozen-m0",
        }
    return value


def m3_scope(episode_id="m3-episode"):
    value = scope_value(episode_id, production=True)
    value["scan_id"] = DEFAULT_RUNTIME_SCAN
    # The M3 successor may replace this legacy field internally, but the
    # frozen M1 scope remains a useful exact-domain input.
    value["calibration_version"] = (
        "proofnav.calibration-artifact.v1:" + REGISTERED_ARTIFACT_DIGEST
    )
    return value


def m3_risk_budgets(scope):
    value = risk_claims(scope)
    # A caller value is intentionally retained in the fixture so tests can
    # prove that M3 ignores/rejects it instead of treating it as authority.
    value["FOUND"]["upper_bound"] = 0.0
    value["NOT_FOUND"]["upper_bound"] = 0.0
    return value


def signal_record(episode_id="m3-episode", score=4.0, proposal_ids=None,
                  valid_mask=None, selected_index=0,
                  scan=DEFAULT_RUNTIME_SCAN):
    """Build the public nested DUET signal contract using tiny CPU arrays."""

    if selected_index not in (0, None):
        raise ValueError("the public builder derives selection; reorder logits instead")
    proposal_ids = ["slot-a", "slot-b"] if proposal_ids is None else proposal_ids
    valid_mask = [True] * len(proposal_ids) if valid_mask is None else valid_mask
    logits = ([] if not proposal_ids else
              [float(score)] + [float(score) - index - 1.0
                                for index in range(len(proposal_ids) - 1)])
    observation = m3_observation(episode_id, proposal_ids)
    observation["scan"] = scan
    count = len(proposal_ids)
    instruction_length = observation["instruction_encoding_length"]
    return build_duet_signal(
        observation=observation,
        template_digest=canonical_sha256(m3_template()),
        object_logits=logits,
        object_valid_mask=np.asarray(valid_mask, dtype=np.bool_),
        panorama_features=[[0.0] * 772 for _ in range(36)],
        object_features=[[0.0] * 768 for _ in range(count)],
        object_angle_features=[[0.0] * 4 for _ in range(count)],
        object_box_features=[[0.0] * 3 for _ in range(count)],
        instruction_encoding=list(range(instruction_length)),
        model_identity=identities(),
    )


def artifact_spec(**overrides):
    """Exact tracked real artifact as a candidate-builder specification.

    Successful production-path tests use this registered aggregate.  Tests
    that mutate the returned specification intentionally create unregistered
    candidates and must expect production rejection.
    """

    value = load_registered_calibration_artifact(REGISTERED_ARTIFACT_DIGEST)
    value.pop("schema_version")
    value.pop("artifact_digest")
    value.update(copy.deepcopy(overrides))
    return value


def entity_query(snapshot, object_id="slot-a"):
    unit_id = object_unit_id("vp0", object_id)
    obligation = next(
        item for item in snapshot["obligations"]
        if item["predicate_kind"] == "entity"
        and unit_id in item["binding_requirement"]["subject_unit_ids"]
    )
    return {
        "hypothesis_id": obligation["hypothesis_id"],
        "obligation_id": obligation["obligation_id"],
        "predicate_id": obligation["predicate_id"],
        "predicate_kind": obligation["predicate_kind"],
        "binding": copy.deepcopy(obligation["binding_requirement"]),
    }


def selected_entity_query(snapshot, signal):
    unit_id = object_unit_id(
        signal["observation"]["viewpoint"],
        signal["object_scores"]["selected_proposal_id"],
    )
    obligation = next(
        item for item in snapshot["obligations"]
        if item["predicate_kind"] == "entity"
        and item["binding_requirement"]["subject_unit_ids"] == [unit_id]
    )
    return {
        "hypothesis_id": obligation["hypothesis_id"],
        "obligation_id": obligation["obligation_id"],
        "predicate_id": obligation["predicate_id"],
        "predicate_kind": obligation["predicate_kind"],
        "binding": copy.deepcopy(obligation["binding_requirement"]),
    }


# The exact categories that the M3 gate must exercise.  Keeping this list in a
# fixture lets the report audit test coverage without treating test names as
# the sole specification.
ADVERSARIAL_CATEGORIES = frozenset((
    "caller_risk",
    "artifact_digest",
    "model_checkpoint_feature_interface_digest",
    "instruction_template_staleness",
    "missing_artifact",
    "unsupported_predicate",
    "refute_sealed",
    "empty_proposals",
    "nonfinite_or_malformed",
    "domain_shift",
    "dependency_correlation",
    "revisit",
    "order",
    "revocation",
    "polarity",
    "wrong_binding",
    "residual_sealed",
    "identity_sealed",
    "runtime_gt_leakage",
    "calibration_split_leakage",
    "m3_off_legacy",
))
