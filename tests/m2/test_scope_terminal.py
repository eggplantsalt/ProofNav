import copy
import unittest

from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.offline import (
    OracleOfflineVerifier, ReplayOnlineVerifier, ReplayTerminalController,
)
from proofnav.offline.structural_audit import structural_result
from proofnav.runtime import CertificateBuilder
from tests.m2.fixtures import (
    append_evaluations,
    complete_scenario,
    controlled_observation,
    evidence_plan,
    emit_evaluations,
    execution,
    reseal,
    state_with_graph,
    truth_artifact,
)


class ScopeAndTerminalTests(unittest.TestCase):

    def test_open_frontier_blocks_not_found_without_caller_authority(self):
        state, scope, _, _ = state_with_graph(
            "entity_absent", graph="open_two",
            object_ids={"vp0": [], "vp1": []},
        )
        plan = evidence_plan(state.snapshot(), "NOT_FOUND")
        append_evaluations(state, plan)
        snapshot = state.snapshot()
        self.assertEqual(snapshot["topology"]["frontier_viewpoint_ids"], ["vp1"])
        self.assertIsNone(snapshot["closure_witness"])
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED")
        self.assertIn("FRONTIER_OPEN", outcome["feedback"]["reason_codes"])
        # no_vp_left is orthogonal and cannot manufacture closure.
        decision = ReplayTerminalController().decide(
            state, "NOT_FOUND", None,
            execution(no_frontier=True, searchable_frontier=False),
        )
        self.assertEqual(decision["directive"], "CONTINUE_SEARCH")
        self.assertEqual(scope["start_viewpoint"], "vp0")

    def test_complete_two_and_three_node_closure_witness(self):
        for graph, expected in (("closed_two", ["vp0", "vp1"]),
                                ("closed_three", ["vp0", "vp1", "vp2"])):
            with self.subTest(graph=graph):
                state, _, _, observations = state_with_graph(
                    "entity_absent", graph=graph,
                    object_ids={"vp0": [], "vp1": [], "vp2": []},
                    episode_id="closure-" + graph,
                )
                snapshot = state.snapshot()
                witness = snapshot["closure_witness"]
                self.assertIsNotNone(witness)
                self.assertEqual(witness["visited_viewpoint_ids"], expected)
                self.assertEqual(witness["observation_event_ids"], [
                    item["event_id"] for item in observations
                ])
                self.assertEqual(witness["observation_digest"], canonical_sha256(observations))
                self.assertEqual(witness["frontier_viewpoint_ids"], [])

    def test_object_enumeration_must_match_feature_rows_and_be_unique(self):
        from tests.m2.fixtures import empty_state
        for label, mutation in (
                ("row-mismatch", lambda obs: obs["object_proposal_ids"].clear()),
                ("duplicate-id", lambda obs: obs["object_proposal_ids"].append("target"))):
            with self.subTest(label=label):
                state, scope, _ = empty_state(
                    "entity_absent", episode_id="object-enum-" + label,
                )
                observation = controlled_observation(
                    scope["episode_id"], object_ids=["target"], candidates=[],
                )
                mutation(observation)
                with self.assertRaisesRegex(
                        ContractViolation,
                        "OBSERVATION_OBJECT_(ENUMERATION|ID_DUPLICATE)"):
                    state.ingest_observation(observation)

    def test_instruction_and_audited_feature_interface_are_exact(self):
        from tests.m2.fixtures import empty_state
        attacks = (
            (
                "instruction",
                lambda obs: obs.__setitem__("instruction", "A different instruction."),
                "TEMPLATE_INSTRUCTION_MISMATCH",
            ),
            (
                "panorama-shape",
                lambda obs: obs["field_schema"]["feature"].__setitem__(
                    "shape", [35, 772],
                ),
                "OBSERVATION_PANORAMA_SCHEMA",
            ),
            (
                "candidate-width",
                lambda obs: obs["candidates"][0]["feature_schema"].__setitem__(
                    "shape", [771],
                ),
                "OBSERVATION_CANDIDATE_SCHEMA",
            ),
            (
                "object-dtype",
                lambda obs: obs["field_schema"]["obj_img_fts"].__setitem__(
                    "dtype", "float64",
                ),
                "OBSERVATION_OBJECT_SCHEMA",
            ),
        )
        for label, mutate, code in attacks:
            with self.subTest(label=label):
                state, scope, _ = empty_state(
                    "positive_control", episode_id="exact-interface-" + label,
                )
                observation = controlled_observation(
                    scope["episode_id"], candidates=["vp1"],
                    object_ids=["target"],
                )
                mutate(observation)
                before = state.audit_bundle()
                with self.assertRaisesRegex(ContractViolation, code):
                    state.ingest_observation(observation)
                self.assertEqual(state.audit_bundle(), before)

    def test_new_candidate_makes_old_not_found_certificate_stale(self):
        bundle = complete_scenario("entity_absent", "NOT_FOUND", graph="closed_one")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        self.assertTrue(ReplayOnlineVerifier().verify(state, certificate)["accepted"])
        state.ingest_observation(controlled_observation(
            bundle["scope"]["episode_id"], viewpoint="vp0", event_seq=5, step=1,
            candidates=["vp1"], object_ids=[], event_id="obs-repeat-new-edge",
        ))
        snapshot = state.snapshot()
        self.assertEqual(snapshot["topology"]["frontier_viewpoint_ids"], ["vp1"])
        report = ReplayOnlineVerifier().verify(state, certificate)
        self.assertEqual(report["status"], "REJECT", report)
        self.assertTrue(any(code.startswith("STALE_") for code in report["reason_codes"]))
        self.assertEqual(CertificateBuilder().build(state, "NOT_FOUND")["status"], "UNRESOLVED")

    def test_external_frontier_or_cached_state_change_cannot_forge_closure(self):
        state, _, _, _ = state_with_graph(
            "entity_absent", graph="open_two",
            object_ids={"vp0": [], "vp1": []},
        )
        forged = state.audit_bundle()
        forged["state"]["topology"]["frontier_viewpoint_ids"] = []
        forged["state"]["closure_witness"] = {"caller_says": True}
        forged_body = copy.deepcopy(forged)
        forged_body.pop("bundle_digest")
        forged["bundle_digest"] = canonical_sha256(forged_body)
        outcome = CertificateBuilder().build(forged, "NOT_FOUND")
        self.assertEqual(outcome["status"], "UNRESOLVED")
        self.assertIn("AUDIT_STATE_MISMATCH", outcome["feedback"]["reason_codes"])
        unknown = state.audit_bundle()
        unknown["frontier_witnesses"] = []
        self.assertIn(
            "AUDIT_BUNDLE_SCHEMA",
            CertificateBuilder().build(unknown, "NOT_FOUND")["feedback"]["reason_codes"],
        )

    def test_revoke_stales_certificate_and_reopens_positive(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        state.revoke_evidence(certificate["evidence_ids"][0], "predicate invalidated")
        report = ReplayOnlineVerifier().verify(state, certificate)
        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any(code.startswith("STALE_") for code in report["reason_codes"]))
        self.assertEqual(CertificateBuilder().build(state, "FOUND")["status"], "UNRESOLVED")
        self.assertEqual(
            [item["event_type"] for item in state.ledger.audit_log()],
            ["APPEND", "REVOKE"],
        )

    def test_duplicate_conflict_and_wrong_binding_fail_closed(self):
        state, _, _, _ = state_with_graph(
            "attribute_mismatch", graph="closed_one",
            object_ids={"vp0": ["target"]},
        )
        plan = evidence_plan(state.snapshot(), "FOUND")
        _, wrappers = emit_evaluations(state, plan)
        state.append_evidence(wrappers[0])
        duplicate = copy.deepcopy(wrappers[0])
        duplicate["evidence"]["evidence_id"] = "semantic-duplicate"
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_DUPLICATE_SEMANTIC"):
            state.append_evidence(duplicate)
        # Finish support, then add a contrary response to the same exact typed query.
        state.append_evidence(wrappers[1])
        conflict = copy.deepcopy(wrappers[0])
        conflict["evidence"]["evidence_id"] = "conflicting-refute"
        conflict["evidence"]["claim"] = "REFUTES"
        conflict["evidence"]["audit_trail"]["source_field"] = "adversarial-conflict"
        state.append_evidence(conflict)
        self.assertIn("CONFLICTED", [item["status"] for item in state.snapshot()["obligations"]])
        self.assertEqual(CertificateBuilder().build(state, "FOUND")["status"], "UNRESOLVED")

    def test_cost_budget_and_query_counts_are_derived(self):
        state, _, _, observations = state_with_graph(
            "entity_absent", graph="closed_two",
            object_ids={"vp0": [], "vp1": []},
        )
        snapshot = state.snapshot()
        self.assertEqual(snapshot["budget_status"]["steps_used"], 2)
        self.assertEqual(snapshot["budget_status"]["observation_events"], 2)
        self.assertEqual(snapshot["budget_status"]["predicate_queries"], 0)
        self.assertEqual(snapshot["cost_ledger"]["observation_events"], len(observations))
        plan = evidence_plan(snapshot, "NOT_FOUND")
        append_evaluations(state, plan)
        updated = state.snapshot()
        self.assertEqual(updated["budget_status"]["predicate_queries"], len(plan))
        self.assertEqual(updated["cost_ledger"]["predicate_queries"], len(plan))
        cert = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        tampered = copy.deepcopy(cert)
        tampered["budget_snapshot"]["predicate_queries"] = 0
        tampered["cost_snapshot"]["observation_events"] = 99
        report = ReplayOnlineVerifier().verify(state, reseal(tampered))
        self.assertIn("BUDGET_SNAPSHOT_MISMATCH", report["reason_codes"])
        self.assertIn("COST_SNAPSHOT_MISMATCH", report["reason_codes"])

    def test_reject_continue_next_observation_rebuild_accept(self):
        state, scope, _, _ = state_with_graph(
            "entity_absent", graph="open_two",
            object_ids={"vp0": [], "vp1": []},
        )
        decision = ReplayTerminalController().decide(
            state, "NOT_FOUND", None, execution(duet_stop=True),
        )
        self.assertEqual(decision["directive"], "CONTINUE_SEARCH")
        state.record_continue(decision)
        self.assertEqual(state.snapshot()["continue_count"], 1)
        state.ingest_observation(controlled_observation(
            scope["episode_id"], viewpoint="vp1", event_seq=5, step=1,
            candidates=["vp0"], object_ids=[],
        ))
        final_plan = evidence_plan(state.snapshot(), "NOT_FOUND")
        append_evaluations(state, final_plan)
        outcome = CertificateBuilder().build(state, "NOT_FOUND")
        self.assertEqual(outcome["status"], "CERTIFICATE", outcome)
        accepted = ReplayTerminalController().decide(
            state, "NOT_FOUND", outcome["certificate"], execution(),
        )
        self.assertEqual(accepted["directive"], "ACCEPT_NOT_FOUND")
        self.assertEqual(
            accepted["accepted_certificate_digest"],
            outcome["certificate"]["certificate_digest"],
        )
        truth = truth_artifact(
            state, "entity_absent", final_plan, semantic_truth="NOT_FOUND",
        )
        offline = OracleOfflineVerifier().verify(
            truth, state.audit_bundle(), accepted, outcome["certificate"],
        )
        self.assertEqual(offline["outcome"], "TRUE_ACCEPT", offline)

    def test_continue_record_is_exact_and_offline_rechecks_its_prefix(self):
        attacks = (
            ("extra-truth", lambda decision: decision.__setitem__(
                "semantic_truth", "NOT_FOUND")),
            ("accepted-flag", lambda decision: decision["online_verification"].__setitem__(
                "accepted", True)),
            ("feedback", lambda decision: decision.__setitem__("feedback", {})),
            ("online-state", lambda decision: decision["online_verification"].__setitem__(
                "proof_state_digest", "f" * 64)),
        )
        for label, mutate in attacks:
            with self.subTest(label=label):
                state, _, _, _ = state_with_graph(
                    "entity_absent", graph="open_two",
                    object_ids={"vp0": [], "vp1": []},
                    episode_id="continue-exact-" + label,
                )
                decision = ReplayTerminalController().decide(
                    state, "NOT_FOUND", None, execution(),
                )
                mutate(decision)
                before = state.audit_bundle()
                with self.assertRaises(ContractViolation):
                    state.record_continue(decision)
                self.assertEqual(state.audit_bundle(), before)

        state, _, _, _ = state_with_graph(
            "entity_absent", graph="open_two",
            object_ids={"vp0": [], "vp1": []},
            episode_id="continue-offline-prefix",
        )
        decision = ReplayTerminalController().decide(
            state, "NOT_FOUND", None, execution(),
        )
        state.record_continue(decision)
        attacked = state.audit_bundle()
        transition = attacked["transitions"][-1]
        transition["payload"]["terminal_decision"]["online_verification"][
            "accepted"
        ] = True
        transition["payload"]["terminal_digest"] = canonical_sha256(
            transition["payload"]["terminal_decision"],
        )
        transition["payload_digest"] = canonical_sha256(transition["payload"])
        body = copy.deepcopy(transition)
        body.pop("transition_digest")
        transition["transition_digest"] = canonical_sha256(body)
        bundle_body = copy.deepcopy(attacked)
        bundle_body.pop("bundle_digest")
        attacked["bundle_digest"] = canonical_sha256(bundle_body)
        result = structural_result(attacked)
        self.assertFalse(result["valid"])
        self.assertIn("OFFLINE_CONTINUE_VERIFICATION", result["reason_codes"])

    def test_terminal_forced_signals_never_manufacture_not_found(self):
        state, _, _, _ = state_with_graph(
            "entity_absent", graph="closed_one", object_ids={"vp0": []},
        )
        controller = ReplayTerminalController()
        stopped = controller.decide(state, "NOT_FOUND", None, execution(duet_stop=True))
        self.assertEqual(stopped["directive"], "CONTINUE_SEARCH")
        for signal in ("max_step", "budget_exhausted"):
            decision = controller.decide(state, "NOT_FOUND", None, execution(**{signal: True}))
            self.assertEqual(decision["semantic_verdict"], "UNRESOLVED")
            self.assertIsNone(decision["accepted_certificate_digest"])

    def test_exact_budget_can_accept_but_cannot_continue(self):
        state, _, _, _ = state_with_graph(
            "positive_control", graph="closed_one",
            object_ids={"vp0": ["target"]},
            limits={
                "max_steps": 1,
                "max_observation_events": 1,
                "max_predicate_queries": 1,
            },
        )
        snapshot = state.snapshot()
        self.assertTrue(snapshot["budget_status"]["within_budget"])
        self.assertFalse(snapshot["budget_status"]["can_continue"])
        unresolved = ReplayTerminalController().decide(
            state, None, None, execution(),
        )
        self.assertEqual(unresolved["directive"], "FINALIZE_UNRESOLVED")
        self.assertEqual(unresolved["cause"], "budget")

        # The last allowed query may still close a certificate, and verifier
        # acceptance takes precedence over forced unresolved finalization.
        append_evaluations(state, evidence_plan(state.snapshot(), "FOUND"))
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        accepted = ReplayTerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        self.assertEqual(accepted["directive"], "ACCEPT_FOUND")


if __name__ == "__main__":
    unittest.main()
