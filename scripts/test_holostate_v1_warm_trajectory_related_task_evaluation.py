#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import holostate_v1_warm_trajectory_related_task_evaluation as probe


class FakeHoloState:
    @staticmethod
    def render_messages(messages, _kwargs):
        return "".join(f"<{item['role']}>{item['content']}</{item['role']}>\n" for item in messages)

    @staticmethod
    def tokenize(value):
        return list(value.encode("utf-8"))

    @staticmethod
    def exact_common_token_prefix(left, right):
        count = 0
        for a, b in zip(left, right):
            if a != b:
                break
            count += 1
        return count

    @staticmethod
    def cache_diagnostic_detokenize(token_ids):
        return bytes(token_ids).decode("utf-8")


def execution(*, prompt=100, cached=0, completion=7, content='{"answer":"A"}'):
    return SimpleNamespace(
        content=content,
        reasoning_content="",
        tool_calls=[],
        prompt_tokens=prompt,
        cached_prompt_tokens=cached,
        completion_tokens=completion,
        generated_token_ids=[1] * completion,
        generated_token_count=completion,
        completion_token_count_match=True,
        generated_token_sha256=probe.sha256_bytes(probe.canonical_json_bytes([1] * completion)),
        nonempty_token_array_event_count=1,
        empty_token_array_event_count=0,
        token_merge_modes=["append"],
        terminal_stop_evidence={"observed": True, "stop": True},
        finish_reason="stop",
        http_status=200,
        event_count=2,
    )


class WarmTrajectoryStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = probe.load_public_corpus(ROOT)
        cls.by_id = {item["pair_id"]: item for item in cls.corpus["task_pairs"]}

    def test_01_frozen_corpus_evaluator_and_pair_hashes(self):
        self.assertEqual(probe.sha256_file(ROOT / probe.PUBLIC_CORPUS_PATH), probe.PUBLIC_CORPUS_SHA256)
        custody = probe.protected_evaluator_custody(ROOT)
        self.assertTrue(custody["regular"] and custody["ignored"] and not custody["tracked"])
        evaluator = json.loads((ROOT / probe.PROTECTED_EVALUATOR_PATH).read_bytes())
        for pair_id in probe.PAIR_IDS:
            self.assertEqual(
                evaluator["task_pairs"][pair_id]["public_pair_sha256"],
                probe.public_pair_sha256(self.by_id[pair_id]),
            )

    def test_02_exact_preregistration_reconstruction(self):
        value = probe.validate_preregistration(ROOT)
        self.assertEqual(value["design_id"], probe.DESIGN_ID)
        self.assertEqual(value["post_hoc_semantic_xor_accounting"]["classification"], "POST_HOC_WORKER_PLUS_CONTROLLER_XOR_ACCOUNTING_DIAGNOSTIC")

    def test_03_task_a_schema_and_word_limits(self):
        valid = {"state": ["one invariant", "two invariant", "three invariant", "four invariant"], "answer": "B"}
        self.assertEqual(probe.parse_task_a_output(probe.canonical_json_text(valid)), valid)
        with self.assertRaises(probe.WarmTrajectoryEvaluationError):
            probe.parse_task_a_output('{"state":["one"],"answer":"A"}')
        with self.assertRaises(probe.WarmTrajectoryEvaluationError):
            probe.parse_task_a_output(probe.canonical_json_text({"state": ["word " * 25] * 4, "answer": "A"}))

    def test_04_task_a_capture_is_shared_between_routes(self):
        pair = self.by_id[probe.PAIR_IDS[0]]
        task_a_json = probe.canonical_json_text({"state": ["a", "b", "c", "d"], "answer": "A"})
        catalytic = probe.task_b_messages(pair, task_a_json)
        direct = probe.task_b_messages(pair, task_a_json)
        self.assertEqual(catalytic, direct)
        self.assertEqual(catalytic[-2], {"role": "assistant", "content": task_a_json})

    def test_05_catalytic_suffix_contains_no_replayed_evidence(self):
        pair = self.by_id[probe.PAIR_IDS[0]]
        suffix = probe.task_b_user_message(pair)["content"]
        self.assertNotIn(pair["evidence"], suffix)
        self.assertIn(pair["task_b"]["question"], suffix)
        for choice in pair["task_b"]["choices"].values():
            self.assertIn(choice, suffix)

    def test_06_direct_replay_contains_exact_evidence_and_task_a_json(self):
        pair = self.by_id[probe.PAIR_IDS[1]]
        task_a_json = probe.canonical_json_text({"state": ["a", "b", "c", "d"], "answer": "B"})
        messages = probe.task_b_messages(pair, task_a_json)
        joined = "\n".join(item["content"] for item in messages)
        self.assertIn(pair["evidence"], joined)
        self.assertIn(task_a_json, joined)

    def test_07_cache_isolation_law(self):
        pair = self.by_id[probe.PAIR_IDS[0]]
        catalytic = probe.task_b_request_template(pair, "catalytic")
        direct = probe.task_b_request_template(pair, "direct")
        self.assertTrue(catalytic["cache_prompt"])
        self.assertFalse(direct["cache_prompt"])
        left = dict(catalytic)
        right = dict(direct)
        left.pop("route")
        right.pop("route")
        left.pop("cache_prompt")
        right.pop("cache_prompt")
        self.assertEqual(left, right)
        checkpoint = probe._raw_completion_payload("checkpoint", seed=1, cache_prompt=False, n_predict=0)
        readdress = probe._raw_completion_payload("checkpoint", seed=1, cache_prompt=True, n_predict=0)
        self.assertFalse(checkpoint["cache_prompt"])
        self.assertTrue(readdress["cache_prompt"])

    def test_08_route_order_counterbalance_and_twelve_request_ceiling(self):
        self.assertEqual(
            tuple(probe.ROUTE_ORDER.values()),
            (("catalytic", "direct"), ("direct", "catalytic"), ("catalytic", "direct"), ("direct", "catalytic")),
        )
        self.assertEqual(len(probe.REQUEST_ORDER), probe.MAXIMUM_GENERATIONS)
        self.assertEqual(len(set(probe.REQUEST_ORDER)), 12)

    def test_09_fixed_seeds_and_task_b_seed_parity(self):
        first = {pair_id: (probe.derive_seed(pair_id, "task-a"), probe.derive_seed(pair_id, "task-b")) for pair_id in probe.PAIR_IDS}
        second = {pair_id: (probe.derive_seed(pair_id, "task-a"), probe.derive_seed(pair_id, "task-b")) for pair_id in probe.PAIR_IDS}
        self.assertEqual(first, second)
        self.assertEqual(len({value[1] for value in first.values()}), 4)

    def test_10_fixed_request_template_hashes_cover_exact_order(self):
        hashes = probe.fixed_request_templates(self.corpus)
        self.assertEqual(tuple(hashes), probe.REQUEST_ORDER)
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))

    def test_11_capture_is_raw_first_authenticated_and_no_overwrite(self):
        temp = Path(tempfile.mkdtemp(prefix="warm-trajectory-capture-", dir=ROOT / "state"))
        try:
            request_id = probe.REQUEST_ORDER[0]
            capture_path = temp / "capture.json"
            partial_path = temp / ".raw.partial"
            raw_line = b'data: {"choices":[{"delta":{"content":"{}"}}]}\n'

            def invoke(recorder):
                recorder(raw_line)
                return execution(content="{}")

            value = probe.capture_request_once(
                capture_path,
                partial_path,
                experiment_key=b"k" * 32,
                request_id=request_id,
                model_request_sha256="A" * 64,
                generation_ordinal=1,
                invoke=invoke,
            )
            self.assertTrue(value["captured_before_parsing"])
            self.assertFalse(partial_path.exists())
            self.assertEqual(probe.raw_sse_bytes(value), raw_line)
            with self.assertRaises(probe.WarmTrajectoryEvaluationError):
                probe.capture_request_once(
                    capture_path,
                    partial_path,
                    experiment_key=b"k" * 32,
                    request_id=request_id,
                    model_request_sha256="A" * 64,
                    generation_ordinal=1,
                    invoke=invoke,
                )
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_12_evaluator_opening_is_delayed_until_terminal_gates(self):
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaises(probe.WarmTrajectoryEvaluationError):
                probe.score_protected(
                    ROOT,
                    self.corpus,
                    {},
                    completed_capture_ids=(),
                    cleanup_passed=False,
                    postflight_passed=False,
                )
            loader.assert_not_called()

    def test_13_checkpoint_geometry_identity_reuse_and_closure(self):
        pair = self.by_id[probe.PAIR_IDS[2]]
        task_a_json = probe.canonical_json_text({"state": ["a", "b", "c", "d"], "answer": "C"})
        geometry = probe.render_checkpoint_and_task_b(FakeHoloState(), pair, task_a_json)
        metadata = {
            "model_identity": {"sha256": probe.MODEL_SHA256},
            "binary_identity": {"sha256": probe.BINARY_SHA256},
            "stable": {"chat_template_sha256": "C" * 64},
        }
        identity = probe.checkpoint_identity(
            geometry,
            pair_id=pair["pair_id"],
            task_a_capture_sha256="D" * 64,
            preflight_metadata=metadata,
        )
        count = identity["checkpoint_token_count"]
        reuse = probe.evaluate_checkpoint_reuse(
            identity,
            warm_execution=execution(prompt=count, cached=0, completion=0),
            catalytic_capture={"execution": vars(execution(prompt=count + 20, cached=count))},
            direct_capture={"execution": vars(execution(prompt=count + 20, cached=0))},
            readdress_execution=execution(prompt=count, cached=count, completion=0),
        )
        self.assertTrue(reuse["passed"])
        self.assertTrue(reuse["checkpoint_freshly_materialized"])
        rejected = probe.evaluate_checkpoint_reuse(
            identity,
            warm_execution=execution(prompt=count, cached=count, completion=0),
            catalytic_capture={"execution": vars(execution(prompt=count + 20, cached=count))},
            direct_capture={"execution": vars(execution(prompt=count + 20, cached=0))},
            readdress_execution=execution(prompt=count, cached=count, completion=0),
        )
        self.assertFalse(rejected["passed"])
        self.assertTrue(probe.verify_checkpoint_closure(identity, dict(identity), reuse)["passed"])

    def test_14_resource_arithmetic_and_integer_cross_products(self):
        records = []
        for request_id in probe.REQUEST_ORDER:
            route_cached = 60 if request_id.endswith("task-b-catalytic") else 0
            records.append(
                {
                    "request_id": request_id,
                    "logical_prompt_tokens": 100,
                    "reused_prompt_tokens": route_cached,
                    "fresh_prompt_tokens": 100 - route_cached,
                    "completion_tokens": 10,
                    "fresh_prompt_plus_completion_tokens": 110 - route_cached,
                    "maximum_request_context": 200,
                    "generation_count": 1,
                }
            )
        resources = probe.account_resources(
            records,
            {"task_a_correct": 4, "catalytic_task_b_correct": 4, "direct_task_b_correct": 4},
        )
        self.assertEqual(resources["catalytic_task_b"]["fresh_prompt_plus_completion_tokens"], 200)
        self.assertEqual(resources["direct_task_b"]["fresh_prompt_plus_completion_tokens"], 440)
        self.assertTrue(resources["catalytic_fresh_tokens_per_correct_strictly_lower"])

    def test_15_decision_law(self):
        scoring = {"task_a_correct": 4, "task_a_state_correct": 4, "catalytic_task_b_correct": 4, "direct_task_b_correct": 4}
        resources = {"catalytic_fresh_tokens_per_correct_strictly_lower": True}
        self.assertEqual(
            probe.classify_result(scoring, resources, reuse_closure_passed=True, cleanup_passed=True, postflight_passed=True),
            "PROCESS_LOCAL_WARM_TRAJECTORY_CATALYTIC_INFERENCE_SUPPORTED",
        )
        self.assertEqual(
            probe.classify_result(scoring, resources, reuse_closure_passed=False, cleanup_passed=True, postflight_passed=True),
            "INCONCLUSIVE",
        )

    def test_16_post_hoc_xor_accounting_is_exact_and_closed(self):
        item = probe.POST_HOC_XOR_ACCOUNTING
        worker = item["worker_plus_controller_route"]
        direct = item["direct_baseline_route"]
        self.assertEqual((worker["fresh_prompt_tokens"], worker["completion_tokens"], worker["fresh_prompt_plus_completion_tokens"]), (1668, 83, 1751))
        self.assertEqual((direct["fresh_prompt_tokens"], direct["completion_tokens"], direct["fresh_prompt_plus_completion_tokens"]), (1373, 57, 1430))
        self.assertEqual(1751 * 3, 5253)
        self.assertEqual(1430 * 4, 5720)
        self.assertTrue(item["line_closed"] and 5253 < 5720)

    def test_17_no_protected_disclosure_or_live_state(self):
        public_text = (ROOT / probe.PUBLIC_CORPUS_PATH).read_text(encoding="utf-8")
        prereg_text = (ROOT / probe.PREREGISTRATION_PATH).read_text(encoding="utf-8")
        for forbidden in probe.PRIVATE_FORBIDDEN_PUBLIC_KEYS:
            self.assertNotIn(f'"{forbidden}"', public_text)
            self.assertNotIn(f'"{forbidden}"', prereg_text)
        self.assertFalse((ROOT / probe.STATE_ROOT).exists())
        self.assertFalse((ROOT / probe.AUTHORITY_RECEIPT_PATH).exists())

    def test_18_static_validator_passes(self):
        result = probe.validate_static(ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["model_requests_issued"], 0)
        self.assertEqual(result["sidecar_launches"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
