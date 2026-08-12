import copy
import itertools
import unittest

from proofnav.contracts import ContractViolation, SCHEMA_VERSIONS, canonical_sha256
from proofnav.offline import (
    OracleEvidenceProvider, ReplayOnlineVerifier, seal_controlled_artifact,
)
from proofnav.offline.structural_audit import recompute_offline_state
from proofnav.runtime import CertificateBuilder
from proofnav.runtime.semantics import object_unit_id
from tests.m2.fixtures import (
    append_evaluations, complete_scenario, controlled_identity_witness,
    emit_evaluations, empty_state, evidence_plan, production_observation,
    reseal, state_with_graph,
)


class MetamorphicTests(unittest.TestCase):

    @staticmethod
    def _reseal_identity_witness(witness):
        value = copy.deepcopy(witness)
        value.pop("witness_id", None)
        value["witness_id"] = "identity-" + canonical_sha256(value)[:24]
        return value

    def test_equivalent_replay_has_identical_state_and_certificate_digest(self):
        first = complete_scenario(
            "positive_control", "FOUND", episode_id="deterministic-replay",
        )
        second = complete_scenario(
            "positive_control", "FOUND", episode_id="deterministic-replay",
        )
        self.assertEqual(first["state"].audit_bundle(), second["state"].audit_bundle())
        first_certificate = CertificateBuilder().build(
            first["state"], "FOUND",
        )["certificate"]
        second_certificate = CertificateBuilder().build(
            second["state"], "FOUND",
        )["certificate"]
        self.assertEqual(first_certificate, second_certificate)
        self.assertEqual(
            first_certificate["certificate_digest"],
            second_certificate["certificate_digest"],
        )

    def test_same_event_id_changed_candidate_changes_digest_and_invalidates_cert(self):
        closed = complete_scenario("entity_absent", "NOT_FOUND", graph="closed_one")
        certificate = CertificateBuilder().build(closed["state"], "NOT_FOUND")["certificate"]
        original_observation = closed["observations"][0]
        changed_state, _, _, changed_observations = state_with_graph(
            "entity_absent", graph="open_two", object_ids={"vp0": []},
            episode_id=closed["scope"]["episode_id"],
        )
        changed_observations[0]["event_id"] = original_observation["event_id"]
        # Rebuild so the altered content and same ID are transition-authentic.
        changed_state, _, _, _ = state_with_graph(
            "entity_absent", graph="open_two", object_ids={"vp0": []},
            episode_id=closed["scope"]["episode_id"],
        )
        self.assertNotEqual(
            closed["state"].snapshot()["topology"]["observation_digest"],
            changed_state.snapshot()["topology"]["observation_digest"],
        )
        report = ReplayOnlineVerifier().verify(changed_state, certificate)
        self.assertEqual(report["status"], "REJECT")

    def test_evidence_order_changes_audit_cut_but_not_resolution(self):
        def build(reverse):
            state, _, _, _ = state_with_graph(
                "attribute_mismatch", graph="closed_one",
                object_ids={"vp0": ["target"]},
                episode_id="evidence-order",
            )
            plan = evidence_plan(state.snapshot(), "FOUND")
            _, wrappers = emit_evaluations(state, plan)
            for item in (list(reversed(wrappers)) if reverse else wrappers):
                state.append_evidence(item)
            return state
        first, second = build(False), build(True)
        statuses = lambda state: {
            item["obligation_id"]: item["status"] for item in state.snapshot()["obligations"]
        }
        self.assertEqual(statuses(first), statuses(second))
        self.assertNotEqual(first.snapshot()["transition_tip"], second.snapshot()["transition_tip"])
        for state in (first, second):
            certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
            self.assertTrue(ReplayOnlineVerifier().verify(state, certificate)["accepted"])

    def test_wrong_subject_and_wrong_anchor_relation_are_rejected(self):
        state, _, _, _ = state_with_graph(
            "relation_mismatch", graph="closed_one",
            object_ids={"vp0": ["subject", "anchor", "other"]},
        )
        snapshot = state.snapshot()
        relation = next(
            item for item in snapshot["obligations"]
            if item["predicate_kind"] == "relation"
        )
        _, wrappers = emit_evaluations(state, {relation["obligation_id"]: "SUPPORTS"})
        wrapper = wrappers[0]
        units = {
            item["unit_id"] for item in snapshot["hypotheses"]
            if False
        }
        del units  # readability: all usable units are encoded in hypotheses.
        alternative = next(
            item for item in snapshot["hypotheses"]
            if (item["hypothesis_kind"] == "subject_relation"
                and item["hypothesis_id"] != relation["hypothesis_id"]
                and item["binding"]["subject_unit_ids"]
                    != relation["binding_requirement"]["subject_unit_ids"])
        )
        wrong_subject = copy.deepcopy(wrapper)
        wrong_subject["evidence"]["evidence_id"] = "wrong-subject"
        wrong_subject["evidence"]["unit_id"] = alternative["binding"]["subject_unit_ids"][0]
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_SUBJECT_BINDING"):
            state.append_evidence(wrong_subject)
        anchor_alternative = next(
            item for item in snapshot["hypotheses"]
            if (item["hypothesis_kind"] == "subject_relation"
                and item["binding"]["subject_unit_ids"]
                    == relation["binding_requirement"]["subject_unit_ids"]
                and item["binding"]["anchor_unit_ids"]
                    != relation["binding_requirement"]["anchor_unit_ids"])
        )
        wrong_anchor = copy.deepcopy(wrapper)
        wrong_anchor["evidence"]["evidence_id"] = "wrong-anchor"
        wrong_anchor["binding"]["anchor_binding_id"] = (
            anchor_alternative["binding"]["anchor_binding_id"]
        )
        wrong_anchor["binding"]["anchor_unit_ids"] = (
            anchor_alternative["binding"]["anchor_unit_ids"]
        )
        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_BINDING_MISMATCH"):
            state.append_evidence(wrong_anchor)

    def test_relation_evidence_cannot_move_between_linked_viewpoints(self):
        state, _, _, observations = state_with_graph(
            "relation_mismatch", graph="closed_two",
            object_ids={"vp0": ["s0", "a0"], "vp1": ["s1", "a1"]},
            episode_id="relation-location-cut",
        )
        for left, right in (
                (object_unit_id("vp0", "s0"), object_unit_id("vp1", "s1")),
                (object_unit_id("vp0", "a0"), object_unit_id("vp1", "a1"))):
            state.link_identity(controlled_identity_witness(state, left, right))
        relation = next(
            item for item in state.snapshot()["obligations"]
            if (item["predicate_kind"] == "relation"
                and item["binding_requirement"]["location_binding_id"]
                    == "loc-" + canonical_sha256({"viewpoint_id": "vp0"})[:20])
        )
        _, wrappers = emit_evaluations(
            state, {relation["obligation_id"]: "SUPPORTS"}, "relation-location",
        )
        attacked = copy.deepcopy(wrappers[0])
        source = observations[1]
        evidence = attacked["evidence"]
        evidence.update({
            "evidence_id": "relation-from-wrong-viewpoint",
            "source_event_id": source["event_id"],
            "event_seq": source["event_seq"],
            "step": source["step"],
            "viewpoint": source["viewpoint"],
            "view_index": source["view_index"],
            "unit_id": object_unit_id("vp1", "s1"),
            "dependency_group": "controlled-replay:" + source["event_id"],
        })
        attacked["source_observation_digest"] = canonical_sha256(source)
        with self.assertRaisesRegex(
                ContractViolation, "EVIDENCE_RELATION_LOCATION_BINDING"):
            state.append_evidence(attacked)

    def test_explicit_identity_link_supports_one_subject_across_viewpoints(self):
        state, scope, template, observations = state_with_graph(
            "attribute_mismatch", graph="closed_two",
            object_ids={"vp0": ["slot-a"], "vp1": ["slot-b"]},
            episode_id="cross-view-identity",
        )
        unit_a = object_unit_id("vp0", "slot-a")
        unit_b = object_unit_id("vp1", "slot-b")
        pre_link = next(
            item for item in state.snapshot()["obligations"]
            if (item["predicate_kind"] == "entity"
                and item["binding_requirement"]["subject_unit_ids"] == [unit_a])
        )
        _, pre_link_wrappers = emit_evaluations(
            state, {pre_link["obligation_id"]: "SUPPORTS"}, "pre-link",
        )
        state.append_evidence(pre_link_wrappers[0])
        before_link = state.snapshot()
        state.link_identity(controlled_identity_witness(state, unit_a, unit_b))
        snapshot = state.snapshot()
        self.assertEqual(
            snapshot["budget_status"]["predicate_queries"],
            before_link["budget_status"]["predicate_queries"] + 1,
        )
        self.assertEqual(
            snapshot["cost_ledger"]["predicate_queries"],
            before_link["cost_ledger"]["predicate_queries"] + 1,
        )
        self.assertEqual(
            snapshot["ledger_event_count"],
            before_link["ledger_event_count"] + 1,
        )
        self.assertNotEqual(snapshot["ledger_digest"], before_link["ledger_digest"])
        subjects = [
            item for item in snapshot["hypotheses"]
            if item["hypothesis_kind"] == "subject"
        ]
        self.assertEqual(len(subjects), 1)
        self.assertEqual(subjects[0]["binding"]["subject_unit_ids"], sorted([unit_a, unit_b]))
        self.assertTrue(all(
            item["status"] == "OPEN" for item in snapshot["obligations"]
            if item["hypothesis_id"] == subjects[0]["hypothesis_id"]
        ))
        obligations = [
            item for item in snapshot["obligations"]
            if item["hypothesis_id"] == subjects[0]["hypothesis_id"]
        ]
        emissions = []
        for index, obligation in enumerate(sorted(obligations, key=lambda item: item["predicate_kind"])):
            query = state.register_query(
                obligation["hypothesis_id"], obligation["obligation_id"],
            )
            source = observations[index]
            source_unit = unit_a if index == 0 else unit_b
            emissions.append({
                "emission_id": "cross-view-%d" % index,
                "query_id": query["query_id"],
                "hypothesis_id": obligation["hypothesis_id"],
                "obligation_id": obligation["obligation_id"],
                "predicate_id": obligation["predicate_id"],
                "predicate_kind": obligation["predicate_kind"],
                "binding": copy.deepcopy(obligation["binding_requirement"]),
                "source_event_id": source["event_id"],
                "evidence_role": "object_slot",
                "unit_id": source_unit,
                "claim": "SUPPORTS",
            })
        bundle = state.audit_bundle()
        script = seal_controlled_artifact({
            "schema_version": SCHEMA_VERSIONS["controlled_script"],
            "script_id": "script-cross-view",
            "episode_id": scope["episode_id"],
            "scope_contract_id": scope["scope_contract_id"],
            "scope_version": scope["provenance"]["version"],
            "scope_digest": canonical_sha256(scope),
            "template_id": template["template_id"],
            "template_digest": canonical_sha256(template),
            "universe_digest": bundle["state"]["universe_digest"],
            "emissions": emissions,
            "audit_trail": {
                "producer": "proofnav.offline.controlled_evidence_script.v2",
                "source_artifact_digest": "",
            },
        })
        for wrapper in OracleEvidenceProvider(scope, template).emit(
                script, state.audit_bundle()):
            state.append_evidence(wrapper)
        outcome = CertificateBuilder().build(state, "FOUND")
        self.assertEqual(outcome["status"], "CERTIFICATE", outcome)
        self.assertEqual(
            outcome["certificate"]["payload"]["binding"]["subject_unit_ids"],
            sorted([unit_a, unit_b]),
        )
        self.assertTrue(
            ReplayOnlineVerifier().verify(state, outcome["certificate"])["accepted"],
        )
        offline_base = {
            key: copy.deepcopy(state.audit_bundle()[key]) for key in (
                "schema_version", "scope", "template", "admission_profile",
                "risk_claims", "transitions",
            )
        }
        offline = recompute_offline_state(offline_base)
        self.assertEqual(offline["proof_state_digest"], state.snapshot()["proof_state_digest"])

    def test_identity_witness_rejects_direct_same_viewpoint_merge(self):
        state, _, _, _ = state_with_graph(
            "positive_control", graph="closed_one",
            object_ids={"vp0": ["slot-a", "slot-b"]},
            episode_id="same-view-identity",
        )
        witness = controlled_identity_witness(
            state,
            object_unit_id("vp0", "slot-a"),
            object_unit_id("vp0", "slot-b"),
        )
        before = state.snapshot()["proof_state_digest"]
        with self.assertRaisesRegex(ContractViolation, "IDENTITY_LINK_SAME_VIEWPOINT"):
            state.link_identity(witness)
        self.assertEqual(state.snapshot()["proof_state_digest"], before)

    def test_identity_witness_rejects_transitive_viewpoint_collision(self):
        state, _, _, _ = state_with_graph(
            "positive_control", graph="closed_two",
            object_ids={"vp0": ["slot-a", "slot-c"], "vp1": ["slot-b"]},
            episode_id="transitive-identity-collision",
        )
        unit_a = object_unit_id("vp0", "slot-a")
        unit_b = object_unit_id("vp1", "slot-b")
        unit_c = object_unit_id("vp0", "slot-c")
        state.link_identity(controlled_identity_witness(state, unit_a, unit_b))
        before = state.snapshot()["proof_state_digest"]
        with self.assertRaisesRegex(
                ContractViolation, "IDENTITY_LINK_VIEWPOINT_COLLISION"):
            state.link_identity(controlled_identity_witness(state, unit_b, unit_c))
        self.assertEqual(state.snapshot()["proof_state_digest"], before)

    def test_identity_witness_rejects_forged_source_and_digest_online_offline(self):
        state, _, _, observations = state_with_graph(
            "positive_control", graph="closed_two",
            object_ids={"vp0": ["slot-a"], "vp1": ["slot-b"]},
            episode_id="identity-source-binding",
        )
        witness = controlled_identity_witness(
            state,
            object_unit_id("vp0", "slot-a"),
            object_unit_id("vp1", "slot-b"),
        )
        forged_source = copy.deepcopy(witness)
        forged_source["endpoints"][0]["source_event_id"] = "obs-does-not-exist"
        forged_source = self._reseal_identity_witness(forged_source)
        with self.assertRaisesRegex(ContractViolation, "IDENTITY_WITNESS_SOURCE_EVENT"):
            state.link_identity(forged_source)

        forged_digest = copy.deepcopy(witness)
        forged_digest["endpoints"][0]["source_observation_digest"] = "f" * 64
        forged_digest = self._reseal_identity_witness(forged_digest)
        with self.assertRaisesRegex(ContractViolation, "IDENTITY_WITNESS_SOURCE_DIGEST"):
            state.link_identity(forged_digest)

        wrong_claim = copy.deepcopy(witness)
        wrong_claim["claim"] = "DIFFERENT_ENTITY"
        wrong_claim = self._reseal_identity_witness(wrong_claim)
        with self.assertRaisesRegex(ContractViolation, "IDENTITY_WITNESS_CLAIM"):
            state.link_identity(wrong_claim)

        forged_provenance = copy.deepcopy(witness)
        forged_provenance["audit_trail"]["producer"] = "caller.asserted.identity"
        forged_provenance = self._reseal_identity_witness(forged_provenance)
        with self.assertRaisesRegex(ContractViolation, "IDENTITY_WITNESS_PROVENANCE"):
            state.link_identity(forged_provenance)

        # Independently construct a raw transition for the offline fold; it
        # must reject the same forged observation digest without consulting
        # runtime semantics or a cached state snapshot.
        base_bundle = state.audit_bundle()
        base = {
            key: copy.deepcopy(base_bundle[key]) for key in (
                "schema_version", "scope", "template", "admission_profile",
                "risk_claims", "transitions",
            )
        }
        parent = base["transitions"][-1]["transition_digest"]
        transition = {
            "schema_version": SCHEMA_VERSIONS["proof_transition"],
            "transition_seq": len(base["transitions"]),
            "event_type": "IDENTITY_LINK",
            "parent_transition_digest": parent,
            "payload": forged_digest,
            "payload_digest": canonical_sha256(forged_digest),
        }
        transition["transition_digest"] = canonical_sha256(transition)
        base["transitions"].append(transition)
        with self.assertRaisesRegex(ContractViolation, "OFFLINE_IDENTITY_SOURCE_DIGEST"):
            recompute_offline_state(base)

    def test_production_identity_link_admission_remains_zero(self):
        state, scope, _ = empty_state(
            "positive_control", episode_id="production-link-firewall",
            production=True,
        )
        observation = production_observation(
            scope["episode_id"], object_ids=["slot-a", "slot-b"],
        )
        state.ingest_observation(observation)
        # The production seal is checked before accepting even a syntactically
        # plausible controlled witness.
        witness = controlled_identity_witness(
            state,
            object_unit_id("vp0", "slot-a"),
            object_unit_id("vp0", "slot-b"),
        )
        with self.assertRaisesRegex(ContractViolation, "IDENTITY_LINK_NOT_REGISTERED"):
            state.link_identity(witness)

    def test_broken_transition_parent_is_rejected_after_bundle_reseal(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        attacked = state.audit_bundle()
        transition = attacked["transitions"][1]
        transition["parent_transition_digest"] = "a" * 64
        transition.pop("transition_digest")
        transition["transition_digest"] = canonical_sha256(transition)
        body = copy.deepcopy(attacked)
        body.pop("bundle_digest")
        attacked["bundle_digest"] = canonical_sha256(body)
        report = ReplayOnlineVerifier().verify(attacked, certificate)
        self.assertEqual(report["status"], "REJECT")
        self.assertIn("TRANSITION_PARENT", report["reason_codes"])

    def test_wrong_hypothesis_refutation_cannot_cover(self):
        bundle = complete_scenario("attribute_mismatch", "NOT_FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "NOT_FOUND")["certificate"]
        attacked = copy.deepcopy(certificate)
        cover = attacked["payload"]["refutation_cover"]
        self.assertGreaterEqual(len(cover), 2)
        cover[0]["hypothesis_id"] = cover[1]["hypothesis_id"]
        report = ReplayOnlineVerifier().verify(state, reseal(attacked))
        self.assertEqual(report["status"], "REJECT")
        self.assertIn("REFUTATION_COVER_ITEM_INVALID", report["reason_codes"])

    def test_exhaustive_closure_binding_time_logic_never_accepts_both(self):
        # 2 topology states x 4 evidence states x 2 time cuts. Binding attacks
        # are covered independently above; this cartesian gate checks that
        # closure/time do not turn a logical state into both verdicts.
        for graph, status, future in itertools.product(
                ("closed_one", "open_two"),
                ("open", "support", "refute", "conflict"),
                (False, True)):
            with self.subTest(graph=graph, status=status, future=future):
                state, _, _, _ = state_with_graph(
                    "positive_control", graph=graph,
                    object_ids={"vp0": ["target"]},
                    episode_id="grid-%s-%s-%s" % (graph, status, future),
                )
                plan = evidence_plan(state.snapshot(), "FOUND")
                if status != "open":
                    _, wrappers = emit_evaluations(state, plan, "grid")
                    support = wrappers[0]
                    refute = copy.deepcopy(support)
                    refute["evidence"]["evidence_id"] = "grid-refute"
                    refute["evidence"]["claim"] = "REFUTES"
                    refute["evidence"]["audit_trail"]["source_field"] = "grid-refute"
                    if future:
                        attacked = copy.deepcopy(support)
                        attacked["evidence"]["event_seq"] = 99
                        with self.assertRaisesRegex(ContractViolation, "EVIDENCE_PROVENANCE"):
                            state.append_evidence(attacked)
                    if status in ("support", "conflict"):
                        state.append_evidence(support)
                    if status in ("refute", "conflict"):
                        state.append_evidence(refute)
                accepted = []
                for verdict in ("FOUND", "NOT_FOUND"):
                    outcome = CertificateBuilder().build(state, verdict)
                    if outcome["certificate"] is not None:
                        if ReplayOnlineVerifier().verify(state, outcome["certificate"])["accepted"]:
                            accepted.append(verdict)
                self.assertLessEqual(len(accepted), 1, accepted)
                if status == "support":
                    self.assertEqual(accepted, ["FOUND"])
                if status == "refute" and graph == "closed_one":
                    # Residual remains uncovered: object refutation alone is
                    # intentionally insufficient for NOT_FOUND.
                    self.assertEqual(accepted, [])

    def test_malformed_certificate_is_stable_reject(self):
        bundle = complete_scenario("positive_control", "FOUND")
        state = bundle["state"]
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        malformed = ["not-an-object", {"requested_verdict": "FOUND"}]
        broken = copy.deepcopy(certificate)
        broken["payload"] = None
        malformed.append(reseal(broken))
        for value in malformed:
            with self.subTest(value=type(value).__name__):
                report = ReplayOnlineVerifier().verify(state, value)
                self.assertEqual(report["status"], "REJECT")


if __name__ == "__main__":
    unittest.main()
