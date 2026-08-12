import ast
import copy
import json
from pathlib import Path
import unittest

import proofnav.runtime as runtime_api
from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.offline import ReplayOnlineVerifier
from proofnav.runtime import CertificateBuilder, OnlineVerifier
from proofnav.validation import scan_forbidden_agent_fields, validate_runtime_trace
from proofnav.runtime.semantics import object_unit_id
from tests.m2.fixtures import (
    complete_scenario,
    empty_state,
    evidence_plan,
    emit_evaluations,
    production_observation,
    state_with_graph,
)


class FirewallAndReplayTests(unittest.TestCase):

    def test_gt_and_unknown_fields_cannot_enter_sequential_state(self):
        state, scope, _ = empty_state("positive_control")
        poisoned = production_observation(scope["episode_id"], object_ids=["target"])
        poisoned["gt_obj_id"] = "hidden"
        before = state.audit_bundle()
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            state.ingest_observation(poisoned)
        self.assertEqual(state.audit_bundle(), before)

        poisoned_scope = copy.deepcopy(scope)
        poisoned_scope["evaluator_truth"] = "FOUND"
        from proofnav.offline import ControlledProofState
        with self.assertRaisesRegex(ContractViolation, "AGENT_VISIBLE_GT"):
            ControlledProofState(
                poisoned_scope, complete_scenario()["template"], {},
            )

    def test_controlled_artifact_cannot_enter_production_state_or_verifier(self):
        controlled = complete_scenario("positive_control", "FOUND")
        certificate = CertificateBuilder().build(
            controlled["state"], "FOUND",
        )["certificate"]
        self.assertTrue(
            ReplayOnlineVerifier().verify(controlled["state"], certificate)["accepted"],
        )
        production_report = OnlineVerifier().verify(controlled["state"], certificate)
        self.assertEqual(production_report["status"], "REJECT")
        self.assertIn("CONTROLLED_SOURCE_FORBIDDEN", production_report["reason_codes"])

        production, scope, _ = empty_state("positive_control", production=True)
        observation = production_observation(
            scope["episode_id"], candidates=[], object_ids=["target"],
        )
        production.ingest_observation(observation)
        plan = evidence_plan(production.snapshot(), "FOUND")
        query = None
        for obligation_id in sorted(plan):
            obligation = next(
                item for item in production.snapshot()["obligations"]
                if item["obligation_id"] == obligation_id
            )
            query = production.register_query(obligation["hypothesis_id"], obligation_id)
        # Construct an otherwise exact query-bound wrapper with an alias that
        # looks like a production adapter.  Zero admission remains authoritative.
        evidence = {
            "schema_version": SCHEMA_VERSIONS["evidence"],
            "evidence_id": "aliased-production-evidence",
            "episode_id": observation["episode_id"],
            "source": "observation",
            "source_event_id": observation["event_id"],
            "event_seq": observation["event_seq"],
            "step": observation["step"],
            "scan": observation["scan"],
            "viewpoint": observation["viewpoint"],
            "view_index": observation["view_index"],
            "evidence_role": "object_slot",
            "unit_id": object_unit_id("vp0", "target"),
            "scope_contract_id": scope["scope_contract_id"],
            "obligation_id": query["obligation_id"],
            "predicate_id": query["predicate_id"],
            "claim": "SUPPORTS",
            "adapter_version": "proofnav.perception.plausible-alias.v2",
            "dependency_group": "plausible-runtime-group",
            "audit_trail": {
                "producer": "proofnav.perception.plausible",
                "source_field": "object_proposal_ids[0]",
            },
        }
        wrapper = dict(copy.deepcopy(query))
        wrapper.update({
            "schema_version": SCHEMA_VERSIONS["bound_evidence"],
            "source_observation_digest": canonical_sha256(observation),
            "evidence": evidence,
        })
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_ADAPTER_NOT_REGISTERED"):
            production.append_evidence(wrapper)
        self.assertEqual(
            production.snapshot()["budget_status"]["predicate_queries"], len(plan),
        )
        self.assertTrue(plan)

    def test_production_profile_is_exact_not_a_scope_config_alias(self):
        _, scope, template = empty_state("positive_control", production=True)
        forged_scope = copy.deepcopy(scope)
        forged_scope["domain"]["interface_audit_ref"] = "caller-approved-interface"
        from proofnav.runtime import ProofState
        from tests.m2.fixtures import risk_claims
        with self.assertRaisesRegex(ContractViolation, "SCOPE_INTERFACE_AUDIT"):
            ProofState(forged_scope, template, risk_claims(forged_scope))

    def test_controlled_evidence_scope_and_producer_are_exact(self):
        attacks = (
            (
                "scope",
                lambda wrapper: wrapper["evidence"].__setitem__(
                    "scope_contract_id", "scope-from-another-episode",
                ),
                "EVIDENCE_SCOPE_CONTRACT",
            ),
            (
                "producer",
                lambda wrapper: wrapper["evidence"]["audit_trail"].__setitem__(
                    "producer", "caller.asserted.evidence",
                ),
                "CONTROLLED_EVIDENCE_PRODUCER",
            ),
            (
                "dependency-group",
                lambda wrapper: wrapper["evidence"].__setitem__(
                    "dependency_group", "controlled-replay:other-event",
                ),
                "CONTROLLED_EVIDENCE_DEPENDENCY_GROUP",
            ),
        )
        for label, mutate, code in attacks:
            with self.subTest(label=label):
                state, _, _, _ = state_with_graph(
                    "positive_control", graph="closed_one",
                    object_ids={"vp0": ["target"]},
                    episode_id="controlled-provenance-" + label,
                )
                plan = evidence_plan(state.snapshot(), "FOUND")
                _, wrappers = emit_evaluations(state, plan, label)
                attacked = copy.deepcopy(wrappers[0])
                mutate(attacked)
                before = state.audit_bundle()
                with self.assertRaisesRegex(ContractViolation, code):
                    state.append_evidence(attacked)
                self.assertEqual(state.audit_bundle(), before)

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

    def test_hidden_truth_never_enters_state_certificate_or_feedback(self):
        bundle = complete_scenario("positive_control", "FOUND")
        certificate = CertificateBuilder().build(bundle["state"], "FOUND")["certificate"]
        report = ReplayOnlineVerifier().verify(bundle["state"], certificate)
        for value in (
                bundle["state"].audit_bundle(), certificate,
                report["structured_feedback"]):
            self.assertEqual(scan_forbidden_agent_fields(value), [])
        serialized = json.dumps(bundle["state"].audit_bundle(), sort_keys=True).lower()
        self.assertNotIn("semantic_truth", serialized)
        self.assertNotIn("supported_hypothesis_ids", serialized)

    def test_tracked_m0_slice_remains_online_only_without_rerun(self):
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
