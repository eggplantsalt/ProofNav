"""CPU checks for the default-off real DUET signal extraction boundary."""

import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

from proofnav.contracts import ContractViolation, canonical_sha256
from proofnav.offline.structural_audit import _offline_m3_signal
from proofnav.perception.evidence_adapter import validate_duet_signal
from proofnav.perception.duet_signal import (
    DUET_SIGNAL_SCHEMA_VERSION,
    DuetSignalSink,
    build_duet_signal,
)
from proofnav.perception.entity_template import build_entity_proof_template
from tests.m3.fixtures import HASHES, m3_observation, m3_template


ROOT = Path(__file__).resolve().parents[2]
PARSER_PATH = ROOT / "map_nav_src" / "reverie" / "parser.py"
AGENT_PATH = ROOT / "map_nav_src" / "reverie" / "agent_obj.py"
MAIN_PATH = ROOT / "map_nav_src" / "reverie" / "main_nav_obj.py"


def _identity():
    return {
        "model_digest": HASHES["model"],
        "checkpoint_digest": HASHES["checkpoint"],
        "feature_digest": HASHES["feature"],
        "interface_digest": HASHES["interface"],
        "config_digest": HASHES["config"],
        "tokenizer_digest": HASHES["tokenizer"],
    }


def _inputs(object_ids=None):
    object_ids = ["slot-a", "slot-b"] if object_ids is None else object_ids
    count = len(object_ids)
    observation = m3_observation(object_ids=object_ids)
    return {
        "observation": observation,
        "template_digest": canonical_sha256(m3_template()),
        "object_logits": np.asarray([4.0 - index for index in range(count)], dtype=np.float64),
        "object_valid_mask": np.asarray([True] * count, dtype=np.bool_),
        "panorama_features": np.zeros(
            observation["field_schema"]["feature"]["shape"], dtype=np.float64,
        ),
        "object_features": np.zeros(
            observation["field_schema"]["obj_img_fts"]["shape"], dtype=np.float64,
        ),
        "object_angle_features": np.zeros((count, 4), dtype=np.float64),
        "object_box_features": np.ones((count, 3), dtype=np.float64),
        "instruction_encoding": np.arange(
            observation["instruction_encoding_length"],
            dtype=np.int32,
        ),
        "model_identity": _identity(),
    }


class DuetSignalBuilderTests(unittest.TestCase):

    def test_exact_self_contained_signal_is_deterministic(self):
        inputs = _inputs()
        first = build_duet_signal(**inputs)
        second = build_duet_signal(**inputs)
        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], DUET_SIGNAL_SCHEMA_VERSION)
        self.assertEqual(first["observation"], inputs["observation"])
        self.assertEqual(
            first["observation_digest"], canonical_sha256(inputs["observation"]),
        )
        self.assertEqual(first["object_scores"]["proposal_ids"], ["slot-a", "slot-b"])
        self.assertEqual(first["object_scores"]["valid_mask"], [True, True])
        self.assertEqual(first["object_scores"]["logits"], [4.0, 3.0])
        self.assertEqual(first["object_scores"]["selected_index"], 0)
        self.assertFalse(first["evidence_authority"])
        sealed = copy.deepcopy(first)
        digest = sealed.pop("signal_digest")
        self.assertEqual(digest, canonical_sha256(sealed))

    def test_hashes_post_cast_content_and_all_registered_identities(self):
        first_inputs = _inputs()
        second_inputs = _inputs()
        # This difference survives float32 casting and must stale the signal.
        second_inputs["object_features"][0, 0] = 11.0
        first = build_duet_signal(**first_inputs)
        second = build_duet_signal(**second_inputs)
        self.assertNotEqual(
            first["content_digests"]["object_features"]["digest"],
            second["content_digests"]["object_features"]["digest"],
        )
        self.assertNotEqual(first["signal_digest"], second["signal_digest"])
        self.assertEqual(first["model_identity"], _identity())
        self.assertEqual(
            set(first["content_digests"]),
            {
                "panorama_features", "object_features",
                "object_angle_features", "object_box_features",
                "instruction_encoding",
            },
        )

    def test_instruction_template_and_model_changes_stale_signal(self):
        baseline = build_duet_signal(**_inputs())
        attacks = []

        instruction = _inputs()
        instruction["observation"]["instruction"] = "Find another object."
        attacks.append(instruction)

        template = _inputs()
        template["template_digest"] = "f" * 64
        attacks.append(template)

        model = _inputs()
        model["model_identity"]["interface_digest"] = "e" * 64
        attacks.append(model)

        for attacked in attacks:
            with self.subTest(kind=len(attacks)):
                self.assertNotEqual(
                    build_duet_signal(**attacked)["signal_digest"],
                    baseline["signal_digest"],
                )

    def test_candidate_first_duplicate_point_packing_runtime_offline_parity(self):
        inputs = _inputs()
        inputs["observation"]["candidates"] = [
            {
                "viewpoint_id": "candidate-a",
                "point_id": 12,
                "heading": 0.0,
                "elevation": 0.0,
                "position": [1.0, 0.0, 0.0],
                "simulator_index": 1,
                "feature_schema": {"shape": [772], "dtype": "float32"},
                "evidence_role": "unobserved_navigation_proposal",
            },
            {
                "viewpoint_id": "candidate-b",
                "point_id": 12,
                "heading": 0.0,
                "elevation": 0.0,
                "position": [2.0, 0.0, 0.0],
                "simulator_index": 2,
                "feature_schema": {"shape": [772], "dtype": "float32"},
                "evidence_role": "unobserved_navigation_proposal",
            },
        ]
        # DUET prepends both candidate rows, then removes their one shared
        # raw panorama row: 2 + 36 - 1 = 37 model-input rows.
        inputs["panorama_features"] = np.zeros((37, 772), dtype=np.float32)
        packed = build_duet_signal(**inputs)
        self.assertEqual(
            validate_duet_signal(packed)["content_digests"][
                "panorama_features"
            ]["shape"],
            [37, 772],
        )
        self.assertEqual(
            _offline_m3_signal(
                packed, packed["observation"], m3_template(),
            )["signal_digest"],
            packed["signal_digest"],
        )

        wrong = copy.deepcopy(packed)
        wrong["content_digests"]["panorama_features"]["shape"] = [36, 772]
        wrong.pop("signal_digest")
        wrong["signal_digest"] = canonical_sha256(wrong)
        with self.assertRaisesRegex(
                ContractViolation, "M3_SIGNAL_CONTENT_SCHEMA"):
            validate_duet_signal(wrong)
        with self.assertRaisesRegex(
                ContractViolation, "OFFLINE_M3_SIGNAL_CONTENT"):
            _offline_m3_signal(wrong, wrong["observation"], m3_template())

    def test_empty_proposals_are_a_signal_not_coverage(self):
        value = build_duet_signal(**_inputs(object_ids=[]))
        self.assertEqual(value["object_scores"]["proposal_ids"], [])
        self.assertEqual(value["object_scores"]["logits"], [])
        self.assertIsNone(value["object_scores"]["selected_index"])
        self.assertFalse(value["evidence_authority"])
        self.assertIn("uncalibrated", value["signal_semantics"])

    def test_gt_nonfinite_bad_mask_and_length_fail_closed(self):
        attacks = []
        gt = _inputs()
        gt["observation"]["gt_obj_id"] = "forbidden"
        attacks.append((gt, "M3_SIGNAL_GT"))

        nan = _inputs()
        nan["object_logits"][0] = np.nan
        attacks.append((nan, "M3_SIGNAL_NONFINITE"))

        inf_feature = _inputs()
        inf_feature["panorama_features"][0, 0] = np.inf
        attacks.append((inf_feature, "M3_SIGNAL_NONFINITE"))

        numeric_mask = _inputs()
        numeric_mask["object_valid_mask"] = [1, 1]
        attacks.append((numeric_mask, "M3_SIGNAL_MASK"))

        wrong_length = _inputs()
        wrong_length["object_logits"] = [4.0]
        attacks.append((wrong_length, "M3_SIGNAL_SCORE_LENGTH"))

        missing_identity = _inputs()
        missing_identity["model_identity"].pop("checkpoint_digest")
        attacks.append((missing_identity, "M3_SIGNAL_MODEL_IDENTITY"))

        for attacked, code in attacks:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ContractViolation, code):
                    build_duet_signal(**attacked)

    def test_jsonl_sink_round_trip_and_close(self):
        inputs = _inputs()
        template_digest = inputs.pop("template_digest")
        model_identity = inputs.pop("model_identity")
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "signal.jsonl")
            with DuetSignalSink(path, model_identity) as sink:
                inputs["template_digest"] = template_digest
                emitted = sink.emit(**inputs)
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(loaded, emitted)
            with self.assertRaisesRegex(ContractViolation, "M3_SIGNAL_CLOSED"):
                sink.emit(**inputs)


class DuetSignalDefaultOffTests(unittest.TestCase):

    def test_emitter_skips_rows_that_ended_before_current_model_step(self):
        """Execute the source emitter without importing the GPU DUET stack."""

        source = AGENT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        agent = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "GMapObjectNavAgent"
        )
        emitter = copy.deepcopy(next(
            node for node in agent.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_emit_proofnav_signals"
        ))
        emitter.decorator_list = []
        namespace = {
            "torch": type("FakeTorch", (), {
                "cat": staticmethod(lambda values, axis: np.concatenate(values, axis)),
            }),
        }
        module = ast.fix_missing_locations(ast.Module(body=[emitter], type_ignores=[]))
        exec(compile(module, str(AGENT_PATH), "exec"), namespace)

        emitted = []
        sink = type("Sink", (), {"emit": lambda self, **value: emitted.append(value)})()
        owner = type("Owner", (), {})()
        owner.proofnav_signal = sink
        owner.args = type("Args", (), {"angle_feat_size": 4})()
        owner._proofnav_signal_sanitizer = lambda ob, **event: {
            "instruction": ob["instruction"],
            "episode_id": ob["instr_id"],
            **event,
        }
        owner._proofnav_signal_template_builder = lambda instruction: {
            "instruction": instruction,
        }
        owner._proofnav_canonical_sha256 = canonical_sha256

        observations = [
            {"instr_id": "active", "instruction": "Find A", "instr_encoding": [1, 2]},
            {"instr_id": "ended", "instruction": "Find B", "instr_encoding": [3, 4]},
        ]
        common = {
            "view_lens": [np.asarray(1), np.asarray(1)],
            "obj_lens": [np.asarray(1), np.asarray(1)],
            "loc_fts": [np.zeros((2, 7)), np.zeros((2, 7))],
            "view_img_fts": [np.zeros((1, 3)), np.zeros((1, 3))],
            "obj_img_fts": [np.zeros((1, 3)), np.zeros((1, 3))],
        }
        namespace["_emit_proofnav_signals"](
            owner,
            observations,
            4,
            {"obj_logits": [
                np.asarray([0.0, 0.0, 7.0]),
                np.asarray([0.0, 0.0, 9.0]),
            ]},
            {"vp_obj_masks": [
                np.asarray([False, False, True]),
                np.asarray([False, False, True]),
            ]},
            common,
            {"txt_ids": [np.asarray([1, 2]), np.asarray([3, 4])]},
            active_mask=np.asarray([True, False]),
        )
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["observation"]["episode_id"], "active")
        self.assertEqual(emitted[0]["observation"]["event_seq"], 4)
        self.assertEqual(emitted[0]["object_logits"].tolist(), [7.0])

    def test_parser_defaults_are_exactly_none(self):
        spec = importlib.util.spec_from_file_location("proofnav_test_reverie_parser", PARSER_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            argv = ["parser.py", "--root_dir", directory, "--output_dir", directory]
            with mock.patch.object(sys, "argv", argv):
                args = module.parse_args()
        names = [
            "proofnav_signal_file",
            "proofnav_signal_model_digest", "proofnav_signal_checkpoint_digest",
            "proofnav_signal_feature_digest", "proofnav_signal_interface_digest",
            "proofnav_signal_config_digest", "proofnav_signal_tokenizer_digest",
        ]
        self.assertTrue(all(getattr(args, name) is None for name in names))

    def test_entity_template_is_code_owned_and_instruction_specific(self):
        first = build_entity_proof_template("Find the red chair.")
        repeat = build_entity_proof_template("Find the red chair.")
        changed = build_entity_proof_template("Find the blue chair.")
        self.assertEqual(first, repeat)
        self.assertNotEqual(first["template_id"], changed["template_id"])
        self.assertNotEqual(
            canonical_sha256(first), canonical_sha256(changed),
        )
        self.assertEqual(len(first["predicates"]), 1)
        self.assertEqual(first["predicates"][0]["kind"], "entity")
        self.assertTrue(first["predicates"][0]["necessary"])

    def test_agent_default_off_guard_precedes_optional_import_and_emit(self):
        source = AGENT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        agent = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "GMapObjectNavAgent"
        )
        build = next(
            node for node in agent.body
            if isinstance(node, ast.FunctionDef) and node.name == "_build_model"
        )
        calls = [
            node for node in ast.walk(build)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "set_proofnav_signal"
        ]
        self.assertEqual(calls, [])
        assignments = [
            node for node in build.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and target.attr == "proofnav_signal"
                for target in node.targets
            )
        ]
        self.assertEqual(len(assignments), 1)
        self.assertIsInstance(assignments[0].value, ast.Constant)
        self.assertIsNone(assignments[0].value.value)

        emit = next(
            node for node in agent.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_emit_proofnav_signals"
        )
        self.assertIsInstance(emit.body[1], ast.If)
        self.assertIn(
            "self.proofnav_signal is None",
            ast.get_source_segment(source, emit.body[1].test),
        )
        self.assertEqual(emit.args.args[-1].arg, "active_mask")
        loop = next(node for node in emit.body if isinstance(node, ast.For))
        active_guard = next(
            node for node in loop.body
            if isinstance(node, ast.If)
            and "active_mask[batch_index]"
            in ast.get_source_segment(source, node.test)
        )
        self.assertTrue(any(isinstance(node, ast.Continue) for node in active_guard.body))

        rollout = next(
            node for node in agent.body
            if isinstance(node, ast.FunctionDef) and node.name == "rollout"
        )
        guarded_calls = [
            node for node in ast.walk(rollout)
            if isinstance(node, ast.If)
            and "self.proofnav_signal is not None"
            in ast.get_source_segment(source, node.test)
            and "self._emit_proofnav_signals"
            in ast.get_source_segment(source, node)
        ]
        self.assertEqual(len(guarded_calls), 1)
        guarded_source = ast.get_source_segment(source, guarded_calls[0])
        self.assertIn("active_mask=np.logical_not(ended)", guarded_source)

    def test_validation_closes_signal_in_finally(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        valid = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "valid"
        )
        finalizers = [
            node.finalbody for node in ast.walk(valid)
            if isinstance(node, ast.Try)
            and "agent.set_proofnav_signal(signal_path)"
            in ast.get_source_segment(source, node)
        ]
        self.assertEqual(len(finalizers), 1)
        cleanup = "\n".join(
            ast.get_source_segment(source, node) for node in finalizers[0]
        )
        self.assertIn("agent.set_proofnav_signal(None)", cleanup)
        self.assertIn("agent.set_runtime_trace(None)", cleanup)


if __name__ == "__main__":
    unittest.main()
