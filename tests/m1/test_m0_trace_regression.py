import json
import os
import unittest

from proofnav.contracts import ContractViolation
from proofnav.validation import validate_runtime_trace
from tests.m1.fixtures import m0_minimal_trace


class M0TraceRegressionTests(unittest.TestCase):

    def test_micro_trace_preserves_m0_boundaries(self):
        validate_runtime_trace(m0_minimal_trace())

    def test_travel_node_cannot_be_observation_endpoint(self):
        events = m0_minimal_trace()
        events[4]["observation_endpoint"] = "mid"
        with self.assertRaisesRegex(ContractViolation, "RUNTIME_ENDPOINT"):
            validate_runtime_trace(events)

    def test_evaluator_event_is_rejected(self):
        events = m0_minimal_trace()
        events[-1]["event_type"] = "metrics"
        with self.assertRaisesRegex(ContractViolation, "RUNTIME_EVALUATOR_EVENT"):
            validate_runtime_trace(events)

    def test_runtime_gt_injection_is_rejected(self):
        events = m0_minimal_trace()
        events[0]["gt_obj_id"] = "forbidden"
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            validate_runtime_trace(events)

    def test_real_m0_trace_when_local_artifact_is_present(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            ".m0-results", "traces", "dynamic_runtime_trace.jsonl",
        )
        if not os.path.exists(path):
            self.skipTest("local M0 artifact is intentionally not versioned")
        with open(path, encoding="utf-8") as infile:
            events = [json.loads(line) for line in infile if line.strip()]
        validate_runtime_trace(events)
        self.assertEqual(len(events), 66)


if __name__ == "__main__":
    unittest.main()
