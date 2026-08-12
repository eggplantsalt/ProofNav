import copy
import unittest

from proofnav.contracts import ContractViolation
from proofnav.evaluator import evaluate_predictions, truth_from_pairs
from tests.m1.fixtures import (
    found_example,
    not_found_example,
    paired_case,
    unresolved_example,
)


class EvaluatorTests(unittest.TestCase):

    def test_original_duet_output_is_backward_compatible(self):
        predictions = [{
            "instr_id": "legacy-1",
            "trajectory": [["vp0"], ["vp1"]],
            "pred_objid": "7",
        }]
        summary = evaluate_predictions(predictions)
        self.assertEqual(summary["mode"], "duet_legacy")
        self.assertTrue(summary["legacy_records_valid"])
        self.assertFalse(summary["proofnav_semantics_evaluated"])

    def test_versioned_three_state_evaluation(self):
        found, found_context = found_example()
        not_found, not_context = not_found_example()
        unresolved, unresolved_context = unresolved_example("max_step")
        predictions = [found, not_found, unresolved]
        contexts = {
            found["instr_id"]: found_context,
            not_found["instr_id"]: not_context,
            unresolved["instr_id"]: unresolved_context,
        }
        truth = {
            found["instr_id"]: "FOUND",
            not_found["instr_id"]: "NOT_FOUND",
            unresolved["instr_id"]: "NOT_FOUND",
        }
        summary = evaluate_predictions(predictions, truth, contexts)
        self.assertEqual(summary["mode"], "proofnav")
        self.assertEqual(summary["verdict_counts"], {
            "FOUND": 1, "NOT_FOUND": 1, "UNRESOLVED": 1,
        })
        self.assertEqual(summary["accepted_certificate_count"], 2)
        self.assertEqual(summary["termination_counts"]["max_step"], 1)
        self.assertAlmostEqual(summary["unresolved_rate"], 1 / 3)
        self.assertIn("boundary_note", summary)

    def test_evaluator_rejects_truth_in_online_context(self):
        result, context = found_example()
        context = copy.deepcopy(context)
        context["evaluator_truth"] = "FOUND"
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            evaluate_predictions(
                [result], {result["instr_id"]: "FOUND"},
                {result["instr_id"]: context},
            )

    def test_paired_truth_extraction_is_offline_only(self):
        pair = paired_case("entity_absent")
        truth = truth_from_pairs([pair])
        self.assertEqual(set(truth.values()), {"FOUND", "NOT_FOUND"})
        for role in ("clean", "false"):
            self.assertNotIn("semantic_truth", pair["members"][role]["agent_visible"])


if __name__ == "__main__":
    unittest.main()
