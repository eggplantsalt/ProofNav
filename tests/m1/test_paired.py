import copy
import unittest

from proofnav.contracts import ContractViolation
from proofnav.paired import (
    pair_fingerprint,
    validate_pair,
    validate_pair_collection,
)
from tests.m1.fixtures import all_paired_cases, paired_case


class PairedContractTests(unittest.TestCase):

    def test_all_four_premise_classes(self):
        pairs = all_paired_cases()
        report = validate_pair_collection(pairs)
        self.assertEqual(report["pair_count"], 4)
        self.assertEqual(set(report["premise_classes"]), {
            "entity_absent",
            "attribute_mismatch",
            "relation_mismatch",
            "room_anchor_mismatch",
        })

    def test_multi_change_is_rejected(self):
        pair = paired_case("attribute_mismatch")
        false_visible = pair["members"]["false"]["agent_visible"]
        false_visible["template_slots"]["anchor"] = "desk"
        pair["members"]["clean"]["agent_visible"]["template_slots"]["anchor"] = "table"
        with self.assertRaisesRegex(ContractViolation, "PAIR_MULTI_CHANGE"):
            validate_pair(pair, verify_fingerprint=False)

    def test_scope_mismatch_is_rejected(self):
        pair = paired_case("relation_mismatch")
        pair["members"]["false"]["agent_visible"]["scope_contract_id"] = "different-scope"
        with self.assertRaisesRegex(ContractViolation, "SCOPE_CONTRACT_ID_MISMATCH"):
            validate_pair(pair, verify_fingerprint=False)

    def test_missing_gt_provenance_is_rejected(self):
        pair = paired_case("entity_absent")
        del pair["members"]["false"]["evaluator_only"]["truth_source"]["record_id"]
        with self.assertRaisesRegex(ContractViolation, "PAIR_MISSING_FIELDS"):
            validate_pair(pair, verify_fingerprint=False)

    def test_missing_pair_field_is_rejected(self):
        pair = paired_case("attribute_mismatch")
        del pair["instruction_template"]
        with self.assertRaisesRegex(ContractViolation, "PAIR_MISSING_FIELDS"):
            validate_pair(pair, verify_fingerprint=False)

    def test_incomplete_changed_premise_audit_is_rejected(self):
        pair = paired_case("relation_mismatch")
        pair["changed_premise_audit"]["review_status"] = "pending"
        with self.assertRaisesRegex(ContractViolation, "PAIR_AUDIT_REVIEW"):
            validate_pair(pair, verify_fingerprint=False)

    def test_split_leakage_is_rejected(self):
        first = paired_case("entity_absent", index=7, split="train")
        second = paired_case("attribute_mismatch", index=8, split="test")
        shared_scene = first["members"]["clean"]["agent_visible"]["scene_id"]
        for role in ("clean", "false"):
            second["members"][role]["agent_visible"]["scene_id"] = shared_scene
        second["deduplication"]["canonical_sha256"] = pair_fingerprint(second)
        with self.assertRaisesRegex(ContractViolation, "PAIR_SPLIT_LEAKAGE"):
            validate_pair_collection([first, second])

    def test_duplicate_content_is_rejected(self):
        first = paired_case("room_anchor_mismatch", index=1)
        second = copy.deepcopy(first)
        second["pair_id"] = "different-pair-id"
        for role in ("clean", "false"):
            second["members"][role]["member_id"] += "-copy"
            second["members"][role]["agent_visible"]["episode_id"] += "-copy"
        # IDs are excluded by the dedup fingerprint, so this remains a duplicate.
        second["deduplication"]["canonical_sha256"] = pair_fingerprint(second)
        with self.assertRaisesRegex(ContractViolation, "PAIR_DUPLICATE_CONTENT"):
            validate_pair_collection([first, second])

    def test_fingerprint_tampering_is_rejected(self):
        pair = paired_case("relation_mismatch")
        pair["deduplication"]["canonical_sha256"] = "f" * 64
        with self.assertRaisesRegex(ContractViolation, "PAIR_DEDUP_FINGERPRINT"):
            validate_pair(pair)


if __name__ == "__main__":
    unittest.main()
