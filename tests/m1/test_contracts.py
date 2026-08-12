import copy
import unittest

from proofnav.adapters import canonicalize_m0_action, sanitize_duet_observation
from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, semantic_verdict
from proofnav.reference_checker import check_reference
from proofnav.validation import (
    validate_action,
    validate_evidence,
    validate_observation,
    validate_result,
    validate_scope,
)
from tests.m1.fixtures import (
    found_example,
    m0_minimal_trace,
    not_found_example,
    unresolved_example,
)


class ContractTests(unittest.TestCase):

    def test_schema_versions_are_explicit(self):
        self.assertEqual(SCHEMA_VERSIONS["result"], "proofnav.result.v1")
        result, context = found_example()
        validate_result(result)
        validate_scope(context["scope"])
        validate_observation(context["observations"][0])

    def test_three_semantic_states(self):
        examples = [
            (found_example(), "FOUND", True),
            (not_found_example(), "NOT_FOUND", True),
            (unresolved_example(), "UNRESOLVED", False),
        ]
        for (result, context), expected, certificate_accepted in examples:
            with self.subTest(verdict=expected):
                self.assertEqual(semantic_verdict(result), expected)
                report = check_reference(result, **context)
                self.assertTrue(report["record_valid"], report)
                self.assertEqual(report["certificate_accepted"], certificate_accepted)

    def test_termination_cause_is_not_semantic_verdict(self):
        result, _ = not_found_example()
        result["termination"]["cause"] = "no_frontier"
        result["termination"]["duet_flags"]["no_frontier"] = True
        with self.assertRaisesRegex(ContractViolation, "SEMANTIC_TERMINATION"):
            validate_result(result)
        unresolved, _ = unresolved_example("duet_stop")
        self.assertEqual(semantic_verdict(validate_result(unresolved)), "UNRESOLVED")

    def test_agent_visible_gt_injection_is_rejected(self):
        _, context = found_example()
        observation = copy.deepcopy(context["observations"][0])
        observation["gt_obj_id"] = "obj-1"
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            validate_observation(observation)

    def test_observation_allowlist_rejects_unknown_alias(self):
        _, context = found_example()
        observation = copy.deepcopy(context["observations"][0])
        observation["hidden_target_hint"] = "obj-1"
        with self.assertRaisesRegex(ContractViolation, "UNKNOWN_FIELDS"):
            validate_observation(observation)

    def test_proposal_and_travel_only_cannot_be_evidence(self):
        _, context = found_example()
        for invalid_source in ("proposal", "travel_only"):
            item = copy.deepcopy(context["evidence"][0])
            item["source"] = invalid_source
            with self.subTest(source=invalid_source):
                with self.assertRaisesRegex(ContractViolation, "EVIDENCE_SOURCE"):
                    validate_evidence(item, {
                        context["observations"][0]["event_id"]: context["observations"][0]
                    })

    def test_evidence_must_match_observation_provenance(self):
        _, context = found_example()
        item = copy.deepcopy(context["evidence"][0])
        item["viewpoint"] = "travel-node"
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_PROVENANCE"):
            validate_evidence(item, {
                context["observations"][0]["event_id"]: context["observations"][0]
            })

    def test_branch_aware_action_mapping(self):
        model, action = m0_minimal_trace()[1:3]
        canonical = canonicalize_m0_action(model, action)
        self.assertEqual(canonical["selected_branch"], "fused")
        self.assertEqual(canonical["selected_action_id"], "vp1")
        validate_action(canonical)
        wrong = copy.deepcopy(canonical)
        wrong["selected_action_id"] = "different-vp"
        with self.assertRaisesRegex(ContractViolation, "ACTION_ID_MAPPING"):
            validate_action(wrong)

    def test_duet_observation_adapter_copies_allowlist_only(self):
        raw = {
            "instr_id": "episode",
            "scan": "scan",
            "viewpoint": "vp0",
            "viewIndex": 12,
            "heading": 0.0,
            "elevation": 0.0,
            "position": (0.0, 0.0, 0.0),
            "feature": [[0.0], [1.0]],
            "candidate": [{
                "viewpointId": "vp1", "pointId": 0, "heading": 0.0,
                "elevation": 0.0, "position": (1.0, 0.0, 0.0), "idx": 1,
                "feature": [0.0], "distance": 0.1,
            }],
            "obj_img_fts": [[0.0]],
            "obj_ang_fts": [[0.0]],
            "obj_box_fts": [[0.0]],
            "obj_ids": [1],
            "instruction": "Find it.",
            "instr_encoding": [1, 2],
            "gt_path": ["vp0", "vp1"],
            "gt_obj_id": "1",
            "distance": 0.0,
        }
        value = sanitize_duet_observation(raw, "event-0", 0, 0)
        self.assertNotIn("gt_path", value)
        self.assertNotIn("gt_obj_id", value)
        self.assertNotIn("distance", value["candidates"][0])
        self.assertEqual(
            value["candidates"][0]["evidence_role"],
            "unobserved_navigation_proposal",
        )


if __name__ == "__main__":
    unittest.main()
