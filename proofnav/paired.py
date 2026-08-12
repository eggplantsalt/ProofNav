"""M1 contract and validator for strict paired false-premise examples."""

import argparse
import json
import re

from .contracts import (
    ContractViolation,
    PREMISE_CLASSES,
    PREMISE_CLASS_TO_PREDICATE_KIND,
    SCHEMA_VERSIONS,
    canonical_sha256,
)
from .validation import assert_agent_visible


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _fail(code, location, message):
    raise ContractViolation(code, location, message)


def _required(value, keys, location):
    if not isinstance(value, dict):
        _fail("PAIR_TYPE", location, "expected an object")
    missing = sorted(set(keys) - set(value))
    if missing:
        _fail("PAIR_MISSING_FIELDS", location, "missing %s" % missing)
    return value


def _only(value, keys, location):
    unknown = sorted(set(value) - set(keys))
    if unknown:
        _fail("PAIR_UNKNOWN_FIELDS", location, "unknown fields %s" % unknown)
    return value


def _nonempty_string(value, location):
    if not isinstance(value, str) or not value:
        _fail("PAIR_STRING", location, "expected a non-empty string")
    return value


def _normalized_member(member):
    visible = dict(member["agent_visible"])
    visible.pop("episode_id", None)
    return visible


def pair_fingerprint(pair):
    """Hash semantic pair content while ignoring IDs, split, and audit metadata."""

    return canonical_sha256({
        "premise_class": pair["premise_class"],
        "instruction_template": pair["instruction_template"],
        "clean": _normalized_member(pair["members"]["clean"]),
        "false": _normalized_member(pair["members"]["false"]),
        "changed_premise": {
            key: pair["changed_premise_audit"][key]
            for key in ("predicate_id", "changed_slot", "before", "after")
        },
    })


def _validate_truth_source(value, location):
    fields = (
        "source_kind", "artifact_id", "record_id", "field_paths",
        "content_sha256",
    )
    value = _only(_required(value, fields, location), fields, location)
    for key in ("source_kind", "artifact_id", "record_id"):
        _nonempty_string(value[key], "%s.%s" % (location, key))
    if not isinstance(value["field_paths"], list) or not value["field_paths"]:
        _fail("PAIR_PROVENANCE_PATH", location + ".field_paths", "must not be empty")
    for index, path in enumerate(value["field_paths"]):
        _nonempty_string(path, "%s.field_paths[%d]" % (location, index))
    if not isinstance(value["content_sha256"], str) or not _SHA256.match(value["content_sha256"]):
        _fail("PAIR_PROVENANCE_HASH", location + ".content_sha256", "expected lowercase SHA-256")


def _validate_member(member, role, pair, location):
    member_fields = (
        "member_id", "agent_visible", "evaluator_only",
    )
    member = _only(_required(member, member_fields, location), member_fields, location)
    _nonempty_string(member["member_id"], location + ".member_id")
    visible_fields = (
        "episode_id", "scene_id", "start_viewpoint", "instruction",
        "template_id", "template_slots", "predicates", "scope_contract_id",
    )
    visible = _only(
        _required(member["agent_visible"], visible_fields, location + ".agent_visible"),
        visible_fields, location + ".agent_visible",
    )
    assert_agent_visible(visible, location + ".agent_visible")
    for key in (
        "episode_id", "scene_id", "start_viewpoint", "instruction",
        "template_id", "scope_contract_id",
    ):
        _nonempty_string(visible[key], "%s.agent_visible.%s" % (location, key))
    if not isinstance(visible["template_slots"], dict) or not visible["template_slots"]:
        _fail("PAIR_TEMPLATE_SLOTS", location + ".agent_visible.template_slots", "must not be empty")
    for key, value in visible["template_slots"].items():
        _nonempty_string(key, location + ".agent_visible.template_slots.<key>")
        _nonempty_string(value, "%s.agent_visible.template_slots.%s" % (location, key))
    predicates = visible["predicates"]
    if not isinstance(predicates, list) or not predicates:
        _fail("PAIR_PREDICATES", location + ".agent_visible.predicates", "must not be empty")
    predicate_ids = []
    for index, predicate in enumerate(predicates):
        predicate_location = "%s.agent_visible.predicates[%d]" % (location, index)
        predicate_fields = (
            "predicate_id", "kind", "subject", "operator", "arguments",
        )
        predicate = _only(
            _required(predicate, predicate_fields, predicate_location),
            predicate_fields, predicate_location,
        )
        for key in ("predicate_id", "kind", "subject", "operator"):
            _nonempty_string(predicate[key], "%s.%s" % (predicate_location, key))
        if not isinstance(predicate["arguments"], dict):
            _fail("PAIR_PREDICATE_ARGUMENTS", predicate_location + ".arguments", "expected object")
        predicate_ids.append(predicate["predicate_id"])
    if len(predicate_ids) != len(set(predicate_ids)):
        _fail("PAIR_PREDICATE_DUPLICATE", location + ".agent_visible.predicates", "IDs must be unique")
    try:
        rendered = pair["instruction_template"]["text"].format(**visible["template_slots"])
    except (KeyError, ValueError) as error:
        _fail("PAIR_TEMPLATE_RENDER", location + ".agent_visible.template_slots", str(error))
    if rendered != visible["instruction"]:
        _fail("PAIR_TEMPLATE_RENDER", location + ".agent_visible.instruction", "does not match template+slots")

    offline_fields = (
        "semantic_truth", "split", "truth_source", "reachability",
        "non_target_conditions",
    )
    offline = _only(
        _required(member["evaluator_only"], offline_fields, location + ".evaluator_only"),
        offline_fields, location + ".evaluator_only",
    )
    expected_truth = "FOUND" if role == "clean" else "NOT_FOUND"
    if offline["semantic_truth"] != expected_truth:
        _fail("PAIR_TRUTH", location + ".evaluator_only.semantic_truth", "expected %s" % expected_truth)
    if offline["split"] != pair["split"]:
        _fail("PAIR_SPLIT_MEMBER", location + ".evaluator_only.split", "does not match pair split")
    _validate_truth_source(offline["truth_source"], location + ".evaluator_only.truth_source")
    reachability_fields = (
        "start_in_scope", "navigation_opportunity_hash",
        "target_condition_reachable", "audit_ref",
    )
    reachability = _only(
        _required(
            offline["reachability"], reachability_fields,
            location + ".evaluator_only.reachability",
        ),
        reachability_fields, location + ".evaluator_only.reachability",
    )
    if reachability["start_in_scope"] is not True:
        _fail("PAIR_START_SCOPE", location + ".evaluator_only.reachability.start_in_scope", "must be true")
    if reachability["target_condition_reachable"] not in (True, False, None):
        _fail("PAIR_REACHABILITY", location + ".evaluator_only.reachability.target_condition_reachable", "expected boolean or null")
    for key in ("navigation_opportunity_hash", "audit_ref"):
        _nonempty_string(reachability[key], "%s.evaluator_only.reachability.%s" % (location, key))
    condition_fields = (
        "matched", "context_hash", "audit_ref",
    )
    conditions = _only(
        _required(
            offline["non_target_conditions"], condition_fields,
            location + ".evaluator_only.non_target_conditions",
        ),
        condition_fields, location + ".evaluator_only.non_target_conditions",
    )
    if conditions["matched"] is not True:
        _fail("PAIR_NON_TARGET_MATCH", location + ".evaluator_only.non_target_conditions.matched", "must be true")
    for key in ("context_hash", "audit_ref"):
        _nonempty_string(conditions[key], "%s.evaluator_only.non_target_conditions.%s" % (location, key))
    return member


def validate_pair(pair, verify_fingerprint=True):
    fields = (
        "schema_version", "pair_id", "premise_class", "split",
        "instruction_template", "members", "changed_premise_audit",
        "deduplication", "audit_trail",
    )
    pair = _only(_required(pair, fields, "$"), fields, "$")
    if pair["schema_version"] != SCHEMA_VERSIONS["pair"]:
        _fail("PAIR_SCHEMA_VERSION", "$.schema_version", "expected %s" % SCHEMA_VERSIONS["pair"])
    _nonempty_string(pair["pair_id"], "$.pair_id")
    _nonempty_string(pair["split"], "$.split")
    if pair["premise_class"] not in PREMISE_CLASSES:
        _fail("PAIR_PREMISE_CLASS", "$.premise_class", "invalid class")
    template_fields = (
        "template_id", "text",
    )
    template = _only(
        _required(pair["instruction_template"], template_fields, "$.instruction_template"),
        template_fields, "$.instruction_template",
    )
    _nonempty_string(template["template_id"], "$.instruction_template.template_id")
    _nonempty_string(template["text"], "$.instruction_template.text")
    members = _required(pair["members"], ("clean", "false"), "$.members")
    if set(members) != {"clean", "false"}:
        _fail("PAIR_MEMBER_KEYS", "$.members", "only clean and false are allowed")
    clean = _validate_member(members["clean"], "clean", pair, "$.members.clean")
    false = _validate_member(members["false"], "false", pair, "$.members.false")
    clean_visible = clean["agent_visible"]
    false_visible = false["agent_visible"]
    for key in ("scene_id", "start_viewpoint", "template_id", "scope_contract_id"):
        if clean_visible[key] != false_visible[key]:
            _fail("PAIR_%s_MISMATCH" % key.upper(), "$.members", "%s differs" % key)
    if clean_visible["template_id"] != template["template_id"]:
        _fail("PAIR_TEMPLATE_ID", "$.instruction_template.template_id", "does not match members")

    clean_slots = clean_visible["template_slots"]
    false_slots = false_visible["template_slots"]
    if set(clean_slots) != set(false_slots):
        _fail("PAIR_TEMPLATE_SLOT_SET", "$.members", "slot keys differ")
    changed_slots = sorted(
        key for key in clean_slots if clean_slots[key] != false_slots[key]
    )
    if len(changed_slots) != 1:
        _fail("PAIR_MULTI_CHANGE", "$.members.*.agent_visible.template_slots", "expected exactly one changed slot")

    clean_predicates = {
        predicate["predicate_id"]: predicate
        for predicate in clean_visible["predicates"]
    }
    false_predicates = {
        predicate["predicate_id"]: predicate
        for predicate in false_visible["predicates"]
    }
    if set(clean_predicates) != set(false_predicates):
        _fail("PAIR_PREDICATE_ID_SET", "$.members", "predicate IDs differ")
    changed_predicates = sorted(
        predicate_id for predicate_id in clean_predicates
        if clean_predicates[predicate_id] != false_predicates[predicate_id]
    )
    if len(changed_predicates) != 1:
        _fail("PAIR_MULTI_CHANGE", "$.members.*.agent_visible.predicates", "expected exactly one changed predicate")

    audit_fields = (
        "premise_class", "predicate_id", "changed_slot", "before", "after",
        "auditor", "review_status",
    )
    audit = _only(
        _required(pair["changed_premise_audit"], audit_fields, "$.changed_premise_audit"),
        audit_fields, "$.changed_premise_audit",
    )
    if audit["premise_class"] != pair["premise_class"]:
        _fail("PAIR_AUDIT_CLASS", "$.changed_premise_audit.premise_class", "class mismatch")
    if audit["predicate_id"] != changed_predicates[0]:
        _fail("PAIR_AUDIT_PREDICATE", "$.changed_premise_audit.predicate_id", "does not identify the sole change")
    if audit["changed_slot"] != changed_slots[0]:
        _fail("PAIR_AUDIT_SLOT", "$.changed_premise_audit.changed_slot", "does not identify the sole slot change")
    if audit["before"] != clean_predicates[changed_predicates[0]]:
        _fail("PAIR_AUDIT_BEFORE", "$.changed_premise_audit.before", "does not match clean predicate")
    if audit["after"] != false_predicates[changed_predicates[0]]:
        _fail("PAIR_AUDIT_AFTER", "$.changed_premise_audit.after", "does not match false predicate")
    expected_kind = PREMISE_CLASS_TO_PREDICATE_KIND[pair["premise_class"]]
    if audit["before"]["kind"] != expected_kind or audit["after"]["kind"] != expected_kind:
        _fail("PAIR_CLASS_KIND", "$.changed_premise_audit", "predicate kind does not match premise class")
    _nonempty_string(audit["auditor"], "$.changed_premise_audit.auditor")
    if audit["review_status"] != "reviewed":
        _fail("PAIR_AUDIT_REVIEW", "$.changed_premise_audit.review_status", "must be reviewed")

    clean_offline = clean["evaluator_only"]
    false_offline = false["evaluator_only"]
    clean_reach = clean_offline["reachability"]
    false_reach = false_offline["reachability"]
    if clean_reach["navigation_opportunity_hash"] != false_reach["navigation_opportunity_hash"]:
        _fail("PAIR_REACHABILITY_MISMATCH", "$.members", "navigation opportunity differs")
    clean_conditions = clean_offline["non_target_conditions"]
    false_conditions = false_offline["non_target_conditions"]
    if clean_conditions["context_hash"] != false_conditions["context_hash"]:
        _fail("PAIR_NON_TARGET_MISMATCH", "$.members", "non-target context differs")

    dedup_fields = (
        "canonical_sha256", "near_duplicate_group",
    )
    dedup = _only(
        _required(pair["deduplication"], dedup_fields, "$.deduplication"),
        dedup_fields, "$.deduplication",
    )
    if not isinstance(dedup["canonical_sha256"], str) or not _SHA256.match(dedup["canonical_sha256"]):
        _fail("PAIR_DEDUP_HASH", "$.deduplication.canonical_sha256", "expected lowercase SHA-256")
    if dedup["near_duplicate_group"] is not None:
        _nonempty_string(dedup["near_duplicate_group"], "$.deduplication.near_duplicate_group")
    if verify_fingerprint and dedup["canonical_sha256"] != pair_fingerprint(pair):
        _fail("PAIR_DEDUP_FINGERPRINT", "$.deduplication.canonical_sha256", "does not match canonical content")
    audit_trail_fields = (
        "producer", "source_versions", "events",
    )
    audit_trail = _only(
        _required(pair["audit_trail"], audit_trail_fields, "$.audit_trail"),
        audit_trail_fields, "$.audit_trail",
    )
    _nonempty_string(audit_trail["producer"], "$.audit_trail.producer")
    if (not isinstance(audit_trail["source_versions"], dict)
            or set(audit_trail["source_versions"]) != {"pair_contract"}
            or audit_trail["source_versions"]["pair_contract"] != SCHEMA_VERSIONS["pair"]):
        _fail(
            "PAIR_AUDIT_VERSIONS", "$.audit_trail.source_versions",
            "must identify the exact pair contract",
        )
    if not isinstance(audit_trail["events"], list) or not audit_trail["events"]:
        _fail("PAIR_AUDIT_EVENTS", "$.audit_trail.events", "must not be empty")
    for index, event in enumerate(audit_trail["events"]):
        _nonempty_string(event, "$.audit_trail.events[%d]" % index)
    return pair


def validate_pair_collection(pairs):
    if not isinstance(pairs, list) or not pairs:
        _fail("PAIR_COLLECTION", "$", "expected a non-empty array")
    pair_ids = {}
    member_ids = {}
    fingerprints = {}
    scene_splits = {}
    classes = set()
    for index, pair in enumerate(pairs):
        try:
            validate_pair(pair)
        except ContractViolation as error:
            raise ContractViolation(
                error.code, "$[%d]%s" % (index, error.location[1:]), error.message,
            )
        pair_id = pair["pair_id"]
        if pair_id in pair_ids:
            _fail("PAIR_DUPLICATE_ID", "$[%d].pair_id" % index, "also appears at index %d" % pair_ids[pair_id])
        pair_ids[pair_id] = index
        classes.add(pair["premise_class"])
        fingerprint = pair["deduplication"]["canonical_sha256"]
        if fingerprint in fingerprints:
            _fail("PAIR_DUPLICATE_CONTENT", "$[%d].deduplication" % index, "duplicates index %d" % fingerprints[fingerprint])
        fingerprints[fingerprint] = index
        scene = pair["members"]["clean"]["agent_visible"]["scene_id"]
        split = pair["split"]
        previous_split = scene_splits.get(scene)
        if previous_split is not None and previous_split != split:
            _fail("PAIR_SPLIT_LEAKAGE", "$[%d].split" % index, "scene appears in %s and %s" % (previous_split, split))
        scene_splits[scene] = split
        for role in ("clean", "false"):
            member_id = pair["members"][role]["member_id"]
            if member_id in member_ids:
                _fail("PAIR_DUPLICATE_MEMBER", "$[%d].members.%s.member_id" % (index, role), "duplicate member ID")
            member_ids[member_id] = (index, role)
    return {
        "schema_version": SCHEMA_VERSIONS["pair"],
        "pair_count": len(pairs),
        "premise_classes": sorted(classes),
        "split_counts": {
            split: sum(pair["split"] == split for pair in pairs)
            for split in sorted({pair["split"] for pair in pairs})
        },
    }


def main():
    parser = argparse.ArgumentParser(description="ProofNav M1 paired-data validator")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as infile:
        report = validate_pair_collection(json.load(infile))
    rendered = json.dumps(report, sort_keys=True, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as outfile:
            outfile.write(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
