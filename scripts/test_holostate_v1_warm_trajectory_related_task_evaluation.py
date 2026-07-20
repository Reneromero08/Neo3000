#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import holostate_v1_warm_trajectory_related_task_evaluation as probe


@contextmanager
def evaluator_access_spy(evaluator_path: Path, *, deny: bool):
    target = evaluator_path.resolve(strict=False)
    events = {"open": 0, "read_bytes": 0, "sha256_file": 0}
    original_open = Path.open
    original_read_bytes = Path.read_bytes
    original_sha256_file = probe.sha256_file

    def is_target(path) -> bool:
        return Path(path).resolve(strict=False) == target

    def guarded_open(path, *args, **kwargs):
        if is_target(path):
            events["open"] += 1
            if deny:
                raise AssertionError("protected evaluator was opened before terminal scoring")
        return original_open(path, *args, **kwargs)

    def guarded_read_bytes(path):
        if is_target(path):
            events["read_bytes"] += 1
            if deny:
                raise AssertionError("protected evaluator bytes were read before terminal scoring")
        return original_read_bytes(path)

    def guarded_sha256_file(path):
        if is_target(path):
            events["sha256_file"] += 1
            if deny:
                raise AssertionError("protected evaluator bytes were hashed before terminal scoring")
        return original_sha256_file(path)

    with (
        mock.patch.object(Path, "open", guarded_open),
        mock.patch.object(Path, "read_bytes", guarded_read_bytes),
        mock.patch.object(probe, "sha256_file", guarded_sha256_file),
    ):
        yield events


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

    def test_01b_zero_output_stream_ignores_prompt_progress_token_markers(self):
        events = [
            b'data: {"content":"","tokens":[0],"stop":false,"tokens_predicted":0,"tokens_evaluated":3,"prompt_progress":{"total":3,"cache":0,"processed":3}}\n',
            b'data: {"content":"","tokens":[],"stop":true,"tokens_predicted":0,"tokens_evaluated":3,"stop_type":"limit","timings":{"predicted_n":0}}\n',
        ]

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter(events)

        recorded = []
        with mock.patch.object(probe.urllib.request, "urlopen", return_value=Response()):
            value = probe._stream_raw_completion(
                port=9494,
                payload=probe._raw_completion_payload(
                    "checkpoint", seed=1, cache_prompt=False, n_predict=0
                ),
                recorder=recorded.append,
            )
        self.assertEqual(value.completion_tokens, 0)
        self.assertEqual(value.generated_token_ids, [])
        self.assertEqual(value.generated_token_count, 0)
        self.assertEqual(value.nonempty_token_array_event_count, 0)
        self.assertEqual(value.empty_token_array_event_count, 1)
        self.assertEqual(recorded, events)

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
        closure_payload = probe._raw_completion_payload(
            str(geometry["checkpoint_prompt"]),
            seed=probe.derive_seed(pair["pair_id"], "task-b"),
            cache_prompt=True,
            n_predict=0,
        )
        closure_operation = probe.carrier_operation_record(
            execution(prompt=count, cached=count, completion=0),
            operation_id=f"{pair['pair_id']}-carrier-closure-readdress",
            pair_id=pair["pair_id"],
            operation_kind="carrier-closure-readdress",
            payload=closure_payload,
            checkpoint_id=identity["checkpoint_id"],
            operation_ordinal=6,
        )
        self.assertTrue(
            probe.verify_checkpoint_closure(
                identity, dict(identity), reuse, closure_operation
            )["passed"]
        )

    def test_14_resource_arithmetic_and_integer_cross_products(self):
        records = []
        for request_id in probe.REQUEST_ORDER:
            route_cached = 60 if request_id.endswith("task-b-catalytic") else 0
            records.append(
                {
                    "request_id": request_id,
                    "operation_id": request_id,
                    "operation_kind": "model-generation",
                    "inference_request_count": 1,
                    "logical_prompt_tokens": 100,
                    "reused_prompt_tokens": route_cached,
                    "fresh_prompt_tokens": 100 - route_cached,
                    "completion_tokens": 10,
                    "fresh_prompt_plus_completion_tokens": 110 - route_cached,
                    "maximum_request_context": 200,
                    "generation_count": 1,
                }
            )
        carrier_operations = []
        for ordinal, operation_id in enumerate(probe.CARRIER_OPERATION_ORDER, 1):
            is_closure = operation_id.endswith("carrier-closure-readdress")
            carrier_operations.append(
                {
                    "operation_id": operation_id,
                    "pair_id": operation_id.split("-carrier-")[0],
                    "operation_kind": (
                        "carrier-closure-readdress" if is_closure else "carrier-materialization"
                    ),
                    "operation_ordinal": ordinal,
                    "checkpoint_id": f"checkpoint-{ordinal}",
                    "payload_sha256": "A" * 64,
                    "cache_prompt": is_closure,
                    "n_predict": 0,
                    "inference_request_count": 1,
                    "generation_count": 0,
                    "logical_prompt_tokens": 30 if not is_closure else 10,
                    "reused_prompt_tokens": 0 if not is_closure else 5,
                    "fresh_prompt_tokens": 30 if not is_closure else 5,
                    "completion_tokens": 0,
                    "fresh_prompt_plus_completion_tokens": 30 if not is_closure else 5,
                    "maximum_request_context": 30 if not is_closure else 10,
                    "terminal_http_status": 200,
                    "terminal_stop_evidence": {"observed": True, "stop": True},
                }
            )
        resources = probe.account_resources(
            records,
            carrier_operations,
            {"task_a_correct": 4, "catalytic_task_b_correct": 4, "direct_task_b_correct": 4},
        )
        self.assertEqual(resources["catalytic_task_b_suffix"]["fresh_prompt_plus_completion_tokens"], 200)
        self.assertEqual(resources["carrier_materialization"]["fresh_prompt_plus_completion_tokens"], 120)
        self.assertEqual(resources["carrier_closure_readdress"]["fresh_prompt_plus_completion_tokens"], 20)
        self.assertEqual(resources["complete_catalytic_marginal"]["fresh_prompt_plus_completion_tokens"], 340)
        self.assertEqual(resources["direct_task_b"]["fresh_prompt_plus_completion_tokens"], 440)
        self.assertEqual(resources["complete_catalytic_marginal"]["request_count"], 12)
        self.assertEqual(resources["complete_catalytic_marginal"]["generation_count"], 4)
        self.assertEqual(resources["total_sequence_shared_task_a_counted_once"]["request_count"], 20)
        self.assertEqual(resources["total_sequence_shared_task_a_counted_once"]["generation_count"], 12)
        self.assertEqual(resources["shared_task_a"]["request_count"], 4)
        self.assertEqual(
            resources["integer_cross_products"],
            {
                "complete_catalytic_tokens_x_direct_correct": 1360,
                "direct_tokens_x_complete_catalytic_correct": 1760,
            },
        )
        self.assertTrue(resources["complete_catalytic_fresh_tokens_per_correct_strictly_lower"])

    def test_15_decision_law(self):
        scoring = {"task_a_correct": 4, "task_a_state_correct": 4, "catalytic_task_b_correct": 4, "direct_task_b_correct": 4}
        resources = {"complete_catalytic_fresh_tokens_per_correct_strictly_lower": True}
        self.assertEqual(
            probe.classify_result(scoring, resources, reuse_closure_passed=True, cleanup_passed=True, postflight_passed=True),
            "PROCESS_LOCAL_WARM_TRAJECTORY_CATALYTIC_INFERENCE_SUPPORTED",
        )
        self.assertEqual(
            probe.classify_result(scoring, resources, reuse_closure_passed=False, cleanup_passed=True, postflight_passed=True),
            "INCONCLUSIVE",
        )

    def test_15b_failed_reuse_or_closure_is_recorded_without_semantic_early_stop(self):
        outcome = probe.checkpoint_gate_outcome(
            {"passed": True},
            {"passed": False},
        )
        self.assertEqual(
            outcome,
            {
                "reuse_passed": True,
                "closure_passed": False,
                "continue_execution": True,
            },
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

    def _terminal_outcomes(self):
        evaluator = json.loads((ROOT / probe.PROTECTED_EVALUATOR_PATH).read_bytes())
        outcomes = {}
        for pair_id in probe.PAIR_IDS:
            protected = evaluator["task_pairs"][pair_id]
            outcomes[pair_id] = {
                "task_a": {
                    "state": [str(group[0]) for group in protected["state_required_concepts"]],
                    "answer": protected["task_a_answer"],
                },
                "catalytic_answer": protected["task_b_answer"],
                "direct_answer": protected["task_b_answer"],
            }
        return outcomes

    def test_19_precontact_custody_is_metadata_only(self):
        evaluator_path = ROOT / probe.PROTECTED_EVALUATOR_PATH
        with evaluator_access_spy(evaluator_path, deny=True) as events:
            custody = probe.protected_evaluator_custody(ROOT)
        self.assertEqual(events, {"open": 0, "read_bytes": 0, "sha256_file": 0})
        self.assertEqual(
            custody["expected_sha256_from_tracked_binding"],
            probe.PROTECTED_EVALUATOR_SHA256,
        )
        self.assertFalse(custody["bytes_opened"])
        self.assertFalse(custody["bytes_hashed"])
        self.assertFalse(custody["bytes_parsed"])
        self.assertFalse(custody["sha256_verified"])

    def test_20_preregistration_reconstruction_never_reads_evaluator(self):
        evaluator_path = ROOT / probe.PROTECTED_EVALUATOR_PATH
        with evaluator_access_spy(evaluator_path, deny=True) as events:
            rendered = probe.build_preregistration_document(ROOT)
            validated = probe.validate_preregistration(ROOT)
        self.assertEqual(rendered, validated)
        self.assertEqual(events, {"open": 0, "read_bytes": 0, "sha256_file": 0})

    def test_21_static_validation_never_reads_evaluator(self):
        evaluator_path = ROOT / probe.PROTECTED_EVALUATOR_PATH
        with evaluator_access_spy(evaluator_path, deny=True) as events:
            result = probe.validate_static(ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(events, {"open": 0, "read_bytes": 0, "sha256_file": 0})

    def test_22_live_preflight_before_authority_never_reads_evaluator(self):
        class CompletePreflight:
            completed = False

            def __init__(self, _repository):
                pass

            def preflight(self, **_kwargs):
                if _kwargs["args"].expected_binary_sha256 != probe.BINARY_SHA256:
                    raise AssertionError("Attempt-5 binary hash was not passed to preflight")
                if _kwargs["args"].expected_runtime_version != probe.RUNTIME_VERSION:
                    raise AssertionError("Attempt-5 runtime version was not passed to preflight")
                type(self).completed = True
                return {"metadata": {"stable": {"head": "a" * 40}}, "runtime": {}}

        args = SimpleNamespace(
            repository=str(ROOT),
            design_id=probe.DESIGN_ID,
            binary="unused",
            model="unused",
            external_authority_id="unused",
            authorized_commit="a" * 40,
        )
        evaluator_path = ROOT / probe.PROTECTED_EVALUATOR_PATH
        with (
            evaluator_access_spy(evaluator_path, deny=True) as events,
            mock.patch.object(probe.kernel, "CatalyticKernel0Adapter", CompletePreflight),
            mock.patch.object(
                probe,
                "_public_preflight",
                return_value={"stable": {"head": "a" * 40}},
            ),
            self.assertRaisesRegex(probe.WarmTrajectoryEvaluationError, "authority ID must be"),
        ):
            probe.run_evaluation(args, repository_root=ROOT)
        self.assertTrue(CompletePreflight.completed)
        self.assertEqual(events, {"open": 0, "read_bytes": 0, "sha256_file": 0})
        self.assertFalse((ROOT / probe.AUTHORITY_RECEIPT_PATH).exists())
        self.assertFalse((ROOT / probe.STATE_ROOT).exists())

    def test_23_all_request_and_checkpoint_constructors_are_evaluator_blind(self):
        evaluator_path = ROOT / probe.PROTECTED_EVALUATOR_PATH
        with evaluator_access_spy(evaluator_path, deny=True) as events:
            hashes = probe.fixed_request_templates(self.corpus)
            for pair_id in probe.PAIR_IDS:
                pair = self.by_id[pair_id]
                task_a_json = probe.canonical_json_text(
                    {"state": ["one", "two", "three", "four"], "answer": "A"}
                )
                probe.task_a_payload(pair)
                probe.task_b_request_template(pair, "catalytic")
                probe.task_b_request_template(pair, "direct")
                probe.render_checkpoint_and_task_b(FakeHoloState(), pair, task_a_json)
        self.assertEqual(tuple(hashes), probe.REQUEST_ORDER)
        self.assertEqual(events, {"open": 0, "read_bytes": 0, "sha256_file": 0})

    def test_24_protected_scoring_refuses_fewer_than_twelve_captures(self):
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaisesRegex(probe.WarmTrajectoryEvaluationError, "before all captures"):
                probe.score_protected(
                    ROOT,
                    self.corpus,
                    {},
                    completed_capture_ids=probe.REQUEST_ORDER[:-1],
                    cleanup_passed=True,
                    postflight_passed=True,
                )
            loader.assert_not_called()

    def test_25_protected_scoring_refuses_before_cleanup(self):
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaisesRegex(probe.WarmTrajectoryEvaluationError, "cleanup/postflight"):
                probe.score_protected(
                    ROOT,
                    self.corpus,
                    {},
                    completed_capture_ids=probe.REQUEST_ORDER,
                    cleanup_passed=False,
                    postflight_passed=True,
                )
            loader.assert_not_called()

    def test_26_protected_scoring_refuses_before_postflight(self):
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaisesRegex(probe.WarmTrajectoryEvaluationError, "cleanup/postflight"):
                probe.score_protected(
                    ROOT,
                    self.corpus,
                    {},
                    completed_capture_ids=probe.REQUEST_ORDER,
                    cleanup_passed=True,
                    postflight_passed=False,
                )
            loader.assert_not_called()

    def test_27_terminal_scoring_opens_hashes_and_parses_exactly_once(self):
        evaluator_path = ROOT / probe.PROTECTED_EVALUATOR_PATH
        outcomes = self._terminal_outcomes()
        original_json_loads = probe.json.loads
        with (
            evaluator_access_spy(evaluator_path, deny=False) as events,
            mock.patch.object(probe.json, "loads", wraps=original_json_loads) as loads,
        ):
            scoring = probe.score_protected(
                ROOT,
                self.corpus,
                outcomes,
                completed_capture_ids=probe.REQUEST_ORDER,
                cleanup_passed=True,
                postflight_passed=True,
            )
        self.assertEqual(events, {"open": 1, "read_bytes": 1, "sha256_file": 0})
        self.assertEqual(loads.call_count, 1)
        custody = scoring["protected_evaluator_custody"]
        self.assertTrue(custody["bytes_opened"])
        self.assertTrue(custody["bytes_hashed"])
        self.assertTrue(custody["bytes_parsed"])
        self.assertTrue(custody["sha256_verified"])
        self.assertEqual(scoring["task_a_correct"], 4)
        self.assertEqual(scoring["catalytic_task_b_correct"], 4)
        self.assertEqual(scoring["direct_task_b_correct"], 4)

    def test_28_same_size_evaluator_tampering_fails_terminal_hash_gate(self):
        temp = Path(tempfile.mkdtemp(prefix="warm-trajectory-evaluator-", dir=ROOT / "state"))
        try:
            subprocess.run(["git", "init", "--quiet"], cwd=temp, check=True)
            relative = probe.PROTECTED_EVALUATOR_PATH
            (temp / ".gitignore").write_text(
                f"/{relative.as_posix()}\n", encoding="utf-8", newline="\n"
            )
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            tampered = bytearray((ROOT / relative).read_bytes())
            tampered[10] ^= 1
            target.write_bytes(tampered)
            self.assertEqual(target.stat().st_size, probe.PROTECTED_EVALUATOR_SIZE)
            with self.assertRaisesRegex(probe.WarmTrajectoryEvaluationError, "hash changed"):
                probe.score_protected(
                    temp,
                    self.corpus,
                    self._terminal_outcomes(),
                    completed_capture_ids=probe.REQUEST_ORDER,
                    cleanup_passed=True,
                    postflight_passed=True,
                )
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_29_public_surfaces_exclude_protected_values(self):
        preregistration = probe.build_preregistration_document(ROOT)
        probe._assert_public_no_smuggle(preregistration)
        scoring = probe.score_protected(
            ROOT,
            self.corpus,
            self._terminal_outcomes(),
            completed_capture_ids=probe.REQUEST_ORDER,
            cleanup_passed=True,
            postflight_passed=True,
        )
        probe._assert_public_no_smuggle(scoring)
        self.assertFalse(scoring["protected_answers_disclosed"])

    def test_30_zero_output_carrier_operation_counts_prompt_inference(self):
        pair_id = probe.PAIR_IDS[0]
        payload = probe._raw_completion_payload(
            "checkpoint", seed=probe.derive_seed(pair_id, "task-b"), cache_prompt=False, n_predict=0
        )
        record = probe.carrier_operation_record(
            execution(prompt=240, cached=0, completion=0, content=""),
            operation_id=f"{pair_id}-carrier-materialization",
            pair_id=pair_id,
            operation_kind="carrier-materialization",
            payload=payload,
            checkpoint_id="checkpoint-1",
            operation_ordinal=1,
        )
        self.assertEqual(record["generation_count"], 0)
        self.assertEqual(record["completion_tokens"], 0)
        self.assertEqual(record["fresh_prompt_tokens"], 240)
        self.assertEqual(record["fresh_prompt_plus_completion_tokens"], 240)
        self.assertEqual(probe.verify_carrier_operation_record(record, payload=payload), record)

    def test_31_carrier_operation_is_authenticated_and_replayable_from_journal(self):
        temp = Path(tempfile.mkdtemp(prefix="warm-trajectory-journal-", dir=ROOT / "state"))
        try:
            key = b"j" * 32
            pair_id = probe.PAIR_IDS[0]
            payload = probe._raw_completion_payload(
                "checkpoint",
                seed=probe.derive_seed(pair_id, "task-b"),
                cache_prompt=False,
                n_predict=0,
            )
            record = probe.carrier_operation_record(
                execution(prompt=200, cached=0, completion=0, content=""),
                operation_id=f"{pair_id}-carrier-materialization",
                pair_id=pair_id,
                operation_kind="carrier-materialization",
                payload=payload,
                checkpoint_id="checkpoint-1",
                operation_ordinal=1,
            )
            writer = probe.JournalWriter(temp / "journal.jsonl", key)
            event = writer.append(
                "carrier-operation-captured",
                request_id=record["operation_id"],
                facts=record,
            )
            replayed = json.loads((temp / "journal.jsonl").read_text(encoding="utf-8"))
            verified = probe.verify_journal_event(
                replayed,
                key,
                expected_previous="0" * 64,
                expected_ordinal=1,
                expected_state="carrier-operation-captured",
            )
            self.assertEqual(verified, event)
            self.assertEqual(
                probe.verify_carrier_operation_record(verified["facts"], payload=payload),
                record,
            )
            tampered = dict(replayed)
            tampered["facts"] = {**record, "fresh_prompt_tokens": 199}
            with self.assertRaisesRegex(probe.WarmTrajectoryEvaluationError, "authentication"):
                probe.verify_journal_event(
                    tampered,
                    key,
                    expected_previous="0" * 64,
                    expected_ordinal=1,
                )
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_32_suffix_only_savings_cannot_trigger_supported_classification(self):
        records = []
        for request_id in probe.REQUEST_ORDER:
            route_cached = 60 if request_id.endswith("task-b-catalytic") else 0
            records.append(
                {
                    "request_id": request_id,
                    "operation_id": request_id,
                    "operation_kind": "model-generation",
                    "inference_request_count": 1,
                    "logical_prompt_tokens": 100,
                    "reused_prompt_tokens": route_cached,
                    "fresh_prompt_tokens": 100 - route_cached,
                    "completion_tokens": 10,
                    "fresh_prompt_plus_completion_tokens": 110 - route_cached,
                    "maximum_request_context": 200,
                    "generation_count": 1,
                }
            )
        carrier_operations = []
        for ordinal, operation_id in enumerate(probe.CARRIER_OPERATION_ORDER, 1):
            is_closure = operation_id.endswith("carrier-closure-readdress")
            fresh = 0 if is_closure else 100
            carrier_operations.append(
                {
                    "operation_id": operation_id,
                    "pair_id": operation_id.split("-carrier-")[0],
                    "operation_kind": (
                        "carrier-closure-readdress" if is_closure else "carrier-materialization"
                    ),
                    "operation_ordinal": ordinal,
                    "checkpoint_id": f"checkpoint-{ordinal}",
                    "payload_sha256": "A" * 64,
                    "cache_prompt": is_closure,
                    "n_predict": 0,
                    "inference_request_count": 1,
                    "generation_count": 0,
                    "logical_prompt_tokens": 100,
                    "reused_prompt_tokens": 100 if is_closure else 0,
                    "fresh_prompt_tokens": fresh,
                    "completion_tokens": 0,
                    "fresh_prompt_plus_completion_tokens": fresh,
                    "maximum_request_context": 100,
                    "terminal_http_status": 200,
                    "terminal_stop_evidence": {"observed": True, "stop": True},
                }
            )
        scoring = {
            "task_a_correct": 4,
            "task_a_state_correct": 4,
            "catalytic_task_b_correct": 4,
            "direct_task_b_correct": 4,
        }
        resources = probe.account_resources(records, carrier_operations, scoring)
        self.assertTrue(
            resources["secondary_suffix_only_diagnostic"][
                "suffix_fresh_tokens_per_correct_strictly_lower"
            ]
        )
        self.assertFalse(resources["complete_catalytic_fresh_tokens_per_correct_strictly_lower"])
        self.assertEqual(
            probe.classify_result(
                scoring,
                resources,
                reuse_closure_passed=True,
                cleanup_passed=True,
                postflight_passed=True,
            ),
            "PROCESS_LOCAL_WARM_TRAJECTORY_REUSE_SUPPORTED_WITHOUT_TASK_ADVANTAGE",
        )

    def test_33_closure_scope_is_immediate_and_does_not_claim_direct_preservation(self):
        pair = self.by_id[probe.PAIR_IDS[0]]
        task_a_json = probe.canonical_json_text(
            {"state": ["a", "b", "c", "d"], "answer": "A"}
        )
        geometry = probe.render_checkpoint_and_task_b(FakeHoloState(), pair, task_a_json)
        identity = probe.checkpoint_identity(
            geometry,
            pair_id=pair["pair_id"],
            task_a_capture_sha256="D" * 64,
            preflight_metadata={
                "model_identity": {"sha256": probe.MODEL_SHA256},
                "binary_identity": {"sha256": probe.BINARY_SHA256},
                "stable": {"chat_template_sha256": "C" * 64},
            },
        )
        count = identity["checkpoint_token_count"]
        payload = probe._raw_completion_payload(
            str(geometry["checkpoint_prompt"]),
            seed=probe.derive_seed(pair["pair_id"], "task-b"),
            cache_prompt=True,
            n_predict=0,
        )
        operation = probe.carrier_operation_record(
            execution(prompt=count, cached=count, completion=0, content=""),
            operation_id=f"{pair['pair_id']}-carrier-closure-readdress",
            pair_id=pair["pair_id"],
            operation_kind="carrier-closure-readdress",
            payload=payload,
            checkpoint_id=identity["checkpoint_id"],
            operation_ordinal=2,
        )
        closure = probe.verify_checkpoint_closure(
            identity,
            dict(identity),
            {
                "root_readdressable_immediately_after_catalytic": True,
                "checkpoint_freshly_materialized": True,
                "direct_route_fresh": True,
            },
            operation,
        )
        self.assertTrue(closure["passed"])
        self.assertEqual(closure["scope"], "immediate-post-catalytic-readdress")
        self.assertFalse(closure["direct_replay_preserved_root_claimed"])
        self.assertTrue(closure["final_process_cleanup_required_separately"])

    def test_34_preregistration_binds_complete_cycle_accounting_without_scientific_drift(self):
        value = probe.build_preregistration_document(ROOT)
        self.assertEqual(value["attempt"]["attempt_id"], probe.ATTEMPT_ID)
        self.assertEqual(
            value["attempt"]["prior_authority_receipt_sha256"],
            probe.PRIOR_AUTHORITY_RECEIPT_SHA256,
        )
        self.assertFalse(value["attempt"]["scientific_surface_changed"])
        self.assertEqual(
            value["attempt"]["runtime_binary_identity"],
            {
                "sha256": probe.BINARY_SHA256,
                "runtime_version": probe.RUNTIME_VERSION,
            },
        )
        self.assertEqual(value["execution"]["carrier_operation_order"], list(probe.CARRIER_OPERATION_ORDER))
        self.assertEqual(value["execution"]["total_inference_requests"], 20)
        self.assertEqual(value["execution"]["maximum_generations"], 12)
        self.assertTrue(value["resource_law"]["zero_output_prompt_inference_is_counted"])
        self.assertTrue(value["resource_law"]["suffix_only_diagnostic_has_no_decision_authority"])
        self.assertEqual(
            value["bindings"]["frozen_scientific"]["sha256"],
            "EB8A386E6453DB0B1948C4542F35AEFDEF58D5EB1CBFAB46FEC4D309101BC6C7",
        )

    def test_35_receipt_verifier_accepts_persisted_flags_without_raw_authority_key(self):
        repository = Path(tempfile.mkdtemp(prefix="warm-trajectory-receipt-positive-", dir=ROOT / "state"))
        try:
            root = b"receipt-positive-root"
            authority = probe.build_external_authority(
                "1" * 64,
                authorized_commit="a" * 40,
                current_commit="a" * 40,
                preregistration_sha256="B" * 64,
            )
            receipt = probe.consume_authority_once(repository, root, authority)
            self.assertEqual(receipt["attempt_id"], probe.ATTEMPT_ID)
            self.assertFalse(receipt["raw_authority_id_persisted"])
            self.assertFalse(receipt["authority"]["raw_authority_id_persisted"])
            self.assertFalse(probe._contains_exact_mapping_key(receipt, "raw_authority_id"))
        finally:
            shutil.rmtree(repository, ignore_errors=True)

    def test_36_receipt_verifier_rejects_exact_raw_authority_key(self):
        repository = Path(tempfile.mkdtemp(prefix="warm-trajectory-receipt-negative-", dir=ROOT / "state"))
        try:
            root = b"receipt-negative-root"
            authority = probe.build_external_authority(
                "2" * 64,
                authorized_commit="b" * 40,
                current_commit="b" * 40,
                preregistration_sha256="C" * 64,
            )
            probe.consume_authority_once(repository, root, authority)
            path = repository / probe.AUTHORITY_RECEIPT_PATH
            value = json.loads(path.read_bytes())
            value["authority"]["raw_authority_id"] = "not-a-real-authority"
            body = {key: item for key, item in value.items() if key != "receipt_hmac_sha256"}
            value["receipt_hmac_sha256"] = probe._authority_hmac(root, body)
            path.write_bytes(probe.canonical_json_bytes(value) + b"\n")
            with self.assertRaisesRegex(
                probe.WarmTrajectoryEvaluationError,
                "authority receipt disclosure boundary changed",
            ):
                probe.verify_authority_receipt(repository, root)
        finally:
            shutil.rmtree(repository, ignore_errors=True)

    def test_37_attempt_7_preserves_attempt_6_terminal_evidence(self):
        prior = probe.verify_prior_execution(ROOT, probe._load_private_root(ROOT))
        self.assertEqual(prior["authority_receipt_sha256"], probe.PRIOR_AUTHORITY_RECEIPT_SHA256)
        self.assertEqual(prior["evidence_sha256"], probe.PRIOR_EVIDENCE_SHA256)
        self.assertEqual(prior["archive_sha256"], probe.PRIOR_ARCHIVE_SHA256)
        self.assertFalse((ROOT / probe.AUTHORITY_RECEIPT_PATH).exists())
        self.assertFalse((ROOT / probe.STATE_ROOT).exists())

    def test_38_attempt_6_capture_retains_normalized_accounting(self):
        path = (
            ROOT
            / probe.PRIOR_STATE_ROOT
            / "captures"
            / "warm-trajectory-archive-01-task-a.json"
        )
        self.assertEqual(probe.sha256_file(path), probe.PRIOR_EVIDENCE_SHA256[path.relative_to(ROOT / probe.PRIOR_STATE_ROOT).as_posix()])
        capture = json.loads(path.read_bytes())
        self.assertEqual(capture["execution"]["prompt_tokens"], 901)
        self.assertEqual(capture["execution"]["completion_tokens"], 108)
        normalized = probe.normalized_capture_execution(capture)
        self.assertEqual(normalized["prompt_tokens"], 901)
        self.assertEqual(normalized["cached_prompt_tokens"], 0)
        self.assertEqual(normalized["completion_tokens"], 108)
        self.assertEqual(normalized["finish_reason"], "stop")
        self.assertEqual(normalized["event_count"], 109)
        self.assertEqual(normalized["terminal_stop_evidence"], {"observed": True, "stop": True})
        resource = probe.resource_record(capture, "warm-trajectory-archive-01-task-a")
        self.assertEqual(resource["fresh_prompt_plus_completion_tokens"], 1009)

    def test_39_checkpoint_boundary_comes_from_full_task_b_prompt(self):
        class FullPromptOnlyHoloState(FakeHoloState):
            @staticmethod
            def render_messages(messages, kwargs):
                if len(messages) != 4:
                    raise AssertionError("standalone checkpoint rendering is forbidden")
                return FakeHoloState.render_messages(messages, kwargs)

        pair = self.by_id[probe.PAIR_IDS[0]]
        task_a_json = probe.canonical_json_text(
            {"state": ["one", "two", "three", "four"], "answer": "A"}
        )
        geometry = probe.render_checkpoint_and_task_b(
            FullPromptOnlyHoloState(),
            pair,
            task_a_json,
        )
        self.assertIn(task_a_json, geometry["checkpoint_prompt"])
        self.assertTrue(geometry["full_prompt"].startswith(geometry["checkpoint_prompt"]))
        self.assertLess(geometry["checkpoint_token_count"], geometry["full_prompt_token_count"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
