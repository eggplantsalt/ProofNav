import ast
import copy
import json
from pathlib import Path
import unittest

import proofnav.runtime as runtime_api
from proofnav.contracts import ContractViolation
from proofnav.offline import ReplayOnlineVerifier
from proofnav.runtime import CertificateBuilder, OnlineVerifier, ProofState
from proofnav.validation import (
    scan_forbidden_agent_fields,
    validate_evidence,
    validate_runtime_trace,
)
from tests.m2.fixtures import (
    controlled_evidence,
    controlled_state,
    scenario,
)


class FirewallAndReplayTests(unittest.TestCase):

    def test_proposal_travel_and_missing_observation_are_rejected(self):
        bundle = scenario()
        item = controlled_evidence(bundle)[0]
        observations = {
            value["event_id"]: value for value in bundle["observations"]
        }
        for forbidden_source in ("proposal", "travel_only"):
            changed = copy.deepcopy(item)
            changed["source"] = forbidden_source
            with self.subTest(source=forbidden_source):
                with self.assertRaisesRegex(ContractViolation, "EVIDENCE_SOURCE"):
                    validate_evidence(changed, observations)
        missing = copy.deepcopy(item)
        missing["source_event_id"] = "never-observed"
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_EVENT_MISSING"):
            validate_evidence(missing, observations)

        wrong_scope = copy.deepcopy(item)
        wrong_scope["scope_contract_id"] = "different-scope"
        state = controlled_state(bundle, evidence=[])
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_SCOPE"):
            state.append_evidence(wrong_scope)

    def test_gt_and_evaluator_aliases_cannot_enter_observation_or_scope(self):
        bundle = scenario()
        poisoned_observation = copy.deepcopy(bundle["observations"][0])
        poisoned_observation["gt_obj_id"] = "hidden"
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            ProofState(
                bundle["scope"], bundle["obligations"], [poisoned_observation],
                [], True, bundle["budget_status"], bundle["cost_ledger"],
                bundle["risk_claims"],
            )
        poisoned_scope = copy.deepcopy(bundle["scope"])
        poisoned_scope["evaluator_truth"] = "FOUND"
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            ProofState(
                poisoned_scope, bundle["obligations"], bundle["observations"],
                [], True, bundle["budget_status"], bundle["cost_ledger"],
                bundle["risk_claims"],
            )

    def test_oracle_evidence_cannot_enter_production_state_or_verifier(self):
        bundle = scenario()
        oracle_item = controlled_evidence(bundle)[0]
        state = ProofState(
            bundle["scope"], bundle["obligations"], bundle["observations"],
            [], True, bundle["budget_status"], bundle["cost_ledger"],
            bundle["risk_claims"],
        )
        with self.assertRaisesRegex(ContractViolation, "CONTROLLED_EVIDENCE_FORBIDDEN"):
            state.append_evidence(oracle_item)

        controlled = controlled_state(bundle)
        certificate = CertificateBuilder().build(controlled, "FOUND")["certificate"]
        self.assertTrue(ReplayOnlineVerifier().verify(controlled, certificate)["accepted"])
        production_report = OnlineVerifier().verify(controlled, certificate)
        self.assertFalse(production_report["accepted"])
        self.assertIn("CONTROLLED_SOURCE_FORBIDDEN", production_report["reason_codes"])

    def test_aliasing_oracle_as_perception_still_cannot_open_production(self):
        bundle = scenario()
        item = copy.deepcopy(controlled_evidence(bundle)[0])
        item["evidence_id"] = "aliased-evidence"
        item["adapter_version"] = "proofnav.perception.plausible-alias.v1"
        item["dependency_group"] = "plausible-observation-group"
        item["audit_trail"] = {
            "producer": "plausible.runtime.adapter",
            "source_field": "object_proposal_ids[0]",
        }
        state = ProofState(
            bundle["scope"], bundle["obligations"], bundle["observations"],
            [], True, bundle["budget_status"], bundle["cost_ledger"],
            bundle["risk_claims"],
        )
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_ADAPTER_NOT_REGISTERED"):
            state.append_evidence(item)

    def test_runtime_import_graph_has_no_offline_reverse_dependency(self):
        runtime_dir = Path(runtime_api.__file__).resolve().parent
        forbidden = ("proofnav.offline", "oracle_evidence", "oracle_verifier")
        imports = []
        for path in sorted(runtime_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
        self.assertFalse([
            name for name in imports if any(token in name for token in forbidden)
        ])
        for forbidden_export in (
                "OracleEvidenceProvider", "ControlledProofState",
                "ReplayOnlineVerifier", "ReplayTerminalController"):
            self.assertFalse(hasattr(runtime_api, forbidden_export))

    def test_hidden_truth_fields_do_not_appear_in_proof_certificate_or_feedback(self):
        bundle = scenario()
        state = controlled_state(bundle)
        snapshot = state.snapshot()
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        report = ReplayOnlineVerifier().verify(state, certificate)
        for value in (snapshot, certificate, report["structured_feedback"]):
            self.assertEqual(scan_forbidden_agent_fields(value), [])

    def test_tracked_m0_replay_slice_remains_online_only(self):
        path = Path(__file__).resolve().parents[1] / "fixtures" / "m0_runtime_trace_slice.jsonl"
        with path.open(encoding="utf-8") as infile:
            events = [json.loads(line) for line in infile if line.strip()]
        validate_runtime_trace(events)
        serialized = json.dumps(events, sort_keys=True).lower()
        for token in (
                "gt_path", "gt_obj_id", "semantic_truth", "evaluator_truth",
                "oracle", "offline_verification"):
            self.assertNotIn(token, serialized)
        action = next(item for item in events if item["event_type"] == "action")
        model = next(item for item in events if item["event_type"] == "model_scores")
        self.assertEqual(
            action["selected_high_level_action"],
            model[action["selected_branch"]]["action_ids"][action["selected_index"]],
        )


if __name__ == "__main__":
    unittest.main()
