#!/usr/bin/env python3
from __future__ import annotations

import json
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

import holostate_v1_inherited_task_a_carrier_evaluation as probe


class FakeCodec:
    @staticmethod
    def render_messages(messages, _kwargs):
        return "".join(f"<{item['role']}>{item['content']}</{item['role']}>\n" for item in messages)

    @staticmethod
    def tokenize(value):
        return list(value.encode("utf-8"))

    @staticmethod
    def detokenize(token_ids):
        return bytes(token_ids).decode("utf-8")


def task_a_json(answer="A"):
    return probe.canonical_json_text(
        {"state": ["one invariant", "two invariant", "three invariant", "four invariant"], "answer": answer}
    )


def capture_execution(*, prompt=100, cached=0, completion=5, content='{"answer":"A"}'):
    execution = {
        "content": content,
        "reasoning_content": "",
        "tool_calls": [],
        "prompt_tokens": prompt,
        "cached_prompt_tokens": cached,
        "completion_tokens": completion,
        "generated_token_ids": [1] * completion,
        "generated_token_count": completion,
        "completion_token_count_match": True,
        "generated_token_sha256": probe.sha256_bytes(probe.canonical_json_bytes([1] * completion)),
        "nonempty_token_array_event_count": 1 if completion else 0,
        "empty_token_array_event_count": 0 if completion else 1,
        "token_merge_modes": ["append"] if completion else [],
        "terminal_stop_evidence": {"observed": True, "stop": True},
        "finish_reason": "stop",
        "http_status": 200,
        "event_count": 2,
    }
    return {"execution": execution}


def closure_execution(*, prompt, cached):
    return SimpleNamespace(
        prompt_tokens=prompt,
        cached_prompt_tokens=cached,
        completion_tokens=0,
        terminal_stop_evidence={"observed": True, "stop": True},
        http_status=200,
    )


class InheritedCarrierStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = probe.load_public_corpus(ROOT)
        cls.by_id = {item["pair_id"]: item for item in cls.corpus["task_pairs"]}

    def test_01_source_bindings_and_custody(self):
        values = probe._verify_source_bindings(ROOT)
        self.assertEqual(values["record_id"], "neo-exp-0048")
        self.assertEqual(probe.sha256_file(ROOT / probe.PUBLIC_CORPUS_PATH), probe.PUBLIC_CORPUS_SHA256)
        custody = probe.protected_evaluator_custody(ROOT)
        self.assertTrue(custody["regular"] and custody["ignored"] and not custody["tracked"])
        self.assertFalse(custody["bytes_opened"])

    def test_02_exact_preregistration_reconstruction(self):
        value = probe.validate_preregistration(ROOT)
        self.assertEqual(value["design_id"], probe.DESIGN_ID)
        self.assertEqual(value["execution"]["materialization_operations"], 0)
        self.assertEqual(value["next_action"], "AUTHORIZE_ONE_LIVE_INHERITED_TASK_A_CARRIER_EVALUATION")

    def test_03_exact_generation_and_inference_geometry(self):
        self.assertEqual(len(probe.REQUEST_ORDER), 12)
        self.assertEqual(len(probe.INFERENCE_ORDER), 16)
        self.assertEqual(len(probe.CLOSURE_OPERATION_ORDER), 4)
        self.assertFalse(any("material" in item for item in probe.INFERENCE_ORDER))
        for offset, pair_id in enumerate(probe.PAIR_IDS):
            self.assertEqual(
                probe.INFERENCE_ORDER[offset * 4 : offset * 4 + 4],
                (
                    f"{pair_id}-task-a",
                    f"{pair_id}-task-b-inherited",
                    f"{pair_id}-carrier-closure-readdress",
                    f"{pair_id}-task-b-direct",
                ),
            )

    def test_04_source_seeds_are_preserved(self):
        for pair_id in probe.PAIR_IDS:
            self.assertEqual(probe.derive_seed(pair_id, "task-a"), probe.source.derive_seed(pair_id, "task-a"))
            self.assertEqual(probe.derive_seed(pair_id, "task-b"), probe.source.derive_seed(pair_id, "task-b"))

    def test_05_routes_receive_identical_semantic_messages(self):
        pair = self.by_id[probe.PAIR_IDS[0]]
        inherited = probe.task_b_request_template(pair, "inherited")
        direct = probe.task_b_request_template(pair, "direct")
        self.assertEqual(inherited["messages"], direct["messages"])
        self.assertEqual(inherited["seed"], direct["seed"])
        self.assertTrue(inherited["cache_prompt"])
        self.assertFalse(direct["cache_prompt"])

    def test_06_dynamic_derivation_is_minimal_and_fully_bound(self):
        pair = self.by_id[probe.PAIR_IDS[0]]
        derived = probe.derive_inherited_prefix(FakeCodec(), pair, task_a_json(), task_a_capture_sha256="A" * 64)
        self.assertGreater(derived["expected_inherited_prefix_token_count"], 0)
        self.assertGreater(derived["suffix_token_count"], 0)
        self.assertEqual(
            derived["full_token_count"],
            derived["expected_inherited_prefix_token_count"] + derived["suffix_token_count"],
        )
        self.assertEqual(probe.json_sha256(derived["_payload"]), derived["dynamic_task_b_request_sha256"])
        self.assertFalse(derived["historical_count_used_as_live_expectation"])

    def test_07_derivation_record_is_authenticated_without_prompt_disclosure(self):
        pair = self.by_id[probe.PAIR_IDS[1]]
        derived = probe.derive_inherited_prefix(FakeCodec(), pair, task_a_json("B"), task_a_capture_sha256="B" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            observed = probe.write_derivation_record(path, b"k" * 32, derived)
            self.assertEqual(observed["derivation_sha256"], derived["derivation_sha256"])
            self.assertNotIn("_full_prompt", observed)
            self.assertNotIn("_payload", observed)

    def test_08_exact_partial_and_absent_reuse_are_scientific_outcomes(self):
        derivation = {"expected_inherited_prefix_token_count": 80}
        direct = capture_execution(prompt=100, cached=0)
        exact = probe.evaluate_inherited_reuse(derivation, capture_execution(prompt=100, cached=80), direct)
        partial = probe.evaluate_inherited_reuse(derivation, capture_execution(prompt=100, cached=40), direct)
        absent = probe.evaluate_inherited_reuse(derivation, capture_execution(prompt=100, cached=0), direct)
        self.assertTrue(exact["exact_inherited_prefix_reuse"])
        self.assertTrue(partial["partial_inherited_prefix_reuse"])
        self.assertFalse(absent["exact_inherited_prefix_reuse"])
        self.assertFalse(absent["false_reuse_stops_panel"])

    def test_09_direct_cache_contamination_is_detected(self):
        report = probe.evaluate_inherited_reuse(
            {"expected_inherited_prefix_token_count": 80},
            capture_execution(prompt=100, cached=80),
            capture_execution(prompt=100, cached=1),
        )
        self.assertFalse(report["direct_freshness_passed"])

    def test_10_closure_reports_exact_and_partial_readdress(self):
        pair_id = probe.PAIR_IDS[0]
        derivation = {"derivation_sha256": "D" * 64, "expected_inherited_prefix_token_count": 80}
        payload = probe._raw_completion_payload("x" * 80, seed=1, cache_prompt=True, n_predict=0)
        exact = probe.closure_operation_record(
            closure_execution(prompt=80, cached=80), pair_id=pair_id, payload=payload,
            derivation=derivation, operation_ordinal=1,
        )
        partial = probe.closure_operation_record(
            closure_execution(prompt=80, cached=40), pair_id=pair_id, payload=payload,
            derivation=derivation, operation_ordinal=1,
        )
        self.assertTrue(exact["exact_closure"])
        self.assertTrue(partial["partial_readdress"])

    def test_11_resource_accounting_includes_closure_and_excludes_materialization(self):
        records = []
        for request_id in probe.REQUEST_ORDER:
            cached = 80 if request_id.endswith("task-b-inherited") else 0
            records.append(probe.resource_record(capture_execution(prompt=100, cached=cached), request_id))
        closures = []
        for ordinal, pair_id in enumerate(probe.PAIR_IDS, start=1):
            payload = probe._raw_completion_payload("x" * 80, seed=1, cache_prompt=True, n_predict=0)
            closures.append(probe.closure_operation_record(
                closure_execution(prompt=80, cached=70), pair_id=pair_id, payload=payload,
                derivation={"derivation_sha256": "D" * 64, "expected_inherited_prefix_token_count": 80},
                operation_ordinal=ordinal,
            ))
        value = probe.account_resources(
            records, closures,
            {"task_a_correct": 4, "inherited_task_b_correct": 4, "direct_task_b_correct": 4},
        )
        self.assertEqual(value["materialization_request_count"], 0)
        self.assertEqual(value["primary_inherited_marginal_including_closure"]["request_count"], 8)
        self.assertFalse(value["historical_projection"]["decision_authority"])

    def test_12_decision_law_has_valid_negative_and_advantage_outcomes(self):
        scoring = {"inherited_task_b_correct": 4, "direct_task_b_correct": 4}
        reports = {pair_id: {"exact_inherited_prefix_reuse": True, "direct_freshness_passed": True} for pair_id in probe.PAIR_IDS}
        resources = {"inherited_fresh_tokens_per_correct_strictly_lower": True}
        self.assertEqual(
            probe.classify_result(scoring, resources, reports, complete_panel=True, cleanup_passed=True, postflight_passed=True),
            "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_FRESH_TOKEN_ADVANTAGE_SUPPORTED",
        )
        reports[probe.PAIR_IDS[0]]["exact_inherited_prefix_reuse"] = False
        self.assertEqual(
            probe.classify_result(scoring, resources, reports, complete_panel=True, cleanup_passed=True, postflight_passed=True),
            "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_EXACT_REUSE_NOT_SUPPORTED",
        )

    def test_13_reuse_without_advantage_is_distinct(self):
        reports = {pair_id: {"exact_inherited_prefix_reuse": True, "direct_freshness_passed": True} for pair_id in probe.PAIR_IDS}
        value = probe.classify_result(
            {"inherited_task_b_correct": 4, "direct_task_b_correct": 4},
            {"inherited_fresh_tokens_per_correct_strictly_lower": False}, reports,
            complete_panel=True, cleanup_passed=True, postflight_passed=True,
        )
        self.assertEqual(value, "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_REUSE_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE")

    def test_14_direct_cache_contamination_is_inconclusive(self):
        reports = {pair_id: {"exact_inherited_prefix_reuse": True, "direct_freshness_passed": True} for pair_id in probe.PAIR_IDS}
        reports[probe.PAIR_IDS[-1]]["direct_freshness_passed"] = False
        value = probe.classify_result(
            {"inherited_task_b_correct": 4, "direct_task_b_correct": 4},
            {"inherited_fresh_tokens_per_correct_strictly_lower": True}, reports,
            complete_panel=True, cleanup_passed=True, postflight_passed=True,
        )
        self.assertEqual(value, "INCONCLUSIVE")

    def test_15_evaluator_is_not_opened_before_terminal_gates(self):
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaises(probe.InheritedCarrierEvaluationError):
                probe.score_protected(
                    ROOT, self.corpus, {}, completed_capture_ids=(), completed_closure_ids=(),
                    cleanup_passed=False, postflight_passed=False,
                )
            loader.assert_not_called()

    def test_16_attempt_7_captures_exercise_all_four_derivations_offline(self):
        replay = probe.offline_replay_attempt_7_task_a_captures(ROOT)
        self.assertEqual(set(replay), set(probe.PAIR_IDS))
        self.assertTrue(all(not value["raw_task_a_output_disclosed"] for value in replay.values()))

    def test_17_authority_never_persists_raw_id(self):
        raw = "a" * 64
        authority = probe.build_external_authority(
            raw, authorized_commit="b" * 40, current_commit="b" * 40,
            preregistration_sha256="C" * 64,
        )
        self.assertNotIn(raw, probe.canonical_json_text(authority))
        self.assertFalse(authority["raw_authority_id_persisted"])

    def test_18_controller_source_contains_no_materialization_or_retry_path(self):
        text = (ROOT / "scripts/holostate_v1_inherited_task_a_carrier_evaluation.py").read_text(encoding="utf-8")
        run_source = text[text.index("def run_evaluation"):text.index("class _OfflineByteCodec")]
        self.assertNotIn("carrier-materialization", run_source)
        self.assertNotIn("perform_warm", run_source)
        self.assertEqual(run_source.count("with pool.lease() as lease_id"), 1)

    def test_19_static_validation_proves_zero_contact_state(self):
        value = probe.validate_static(ROOT)
        self.assertEqual(value["status"], "pass")
        self.assertEqual(value["proofs"]["materialization_operations"], 0)
        self.assertEqual(value["model_requests_issued"], 0)
        self.assertTrue(value["runtime_artifacts_absent"] and value["archive_absent"])

    def test_20_prompt_codec_uses_only_non_generation_endpoints(self):
        calls = []
        responses = iter([{"prompt": "abc"}, {"tokens": [1, 2]}, {"content": "abc"}])
        with mock.patch.object(probe, "_prompt_codec_request", side_effect=lambda port, endpoint, payload: (calls.append(endpoint), next(responses))[1]):
            codec = probe.SidecarPromptCodec(9494)
            self.assertEqual(codec.render_messages([], {}), "abc")
            self.assertEqual(codec.tokenize("abc"), [1, 2])
            self.assertEqual(codec.detokenize([1, 2]), "abc")
        self.assertEqual(calls, ["/apply-template", "/tokenize", "/detokenize"])
        self.assertNotIn("/completion", calls)

    def test_21_live_preflight_rejects_before_authority_or_evaluator_access(self):
        class CompletePreflight:
            completed = False

            def __init__(self, _repository):
                pass

            def preflight(self, **kwargs):
                self.assert_expected(kwargs["args"])
                type(self).completed = True
                return {"metadata": {"stable": {"head": "a" * 40}}, "runtime": {}}

            @staticmethod
            def assert_expected(args):
                if args.expected_binary_sha256 != probe.BINARY_SHA256:
                    raise AssertionError("binary hash was not passed to preflight")
                if args.expected_runtime_version != probe.RUNTIME_VERSION:
                    raise AssertionError("runtime version was not passed to preflight")

        args = SimpleNamespace(
            repository=str(ROOT), design_id=probe.DESIGN_ID, binary="unused", model="unused",
            external_authority_id="not-hex", authorized_commit="a" * 40,
        )
        evaluator_path = (ROOT / probe.PROTECTED_EVALUATOR_PATH).resolve(strict=False)
        original_read_bytes = Path.read_bytes
        evaluator_reads = []

        def guarded_read_bytes(path):
            if Path(path).resolve(strict=False) == evaluator_path:
                evaluator_reads.append(str(path))
                raise AssertionError("protected evaluator was read before authority admission")
            return original_read_bytes(path)

        with (
            mock.patch.object(probe.kernel, "CatalyticKernel0Adapter", CompletePreflight),
            mock.patch.object(probe, "_public_preflight", return_value={"stable": {"head": "a" * 40}}),
            mock.patch.object(Path, "read_bytes", guarded_read_bytes),
            self.assertRaisesRegex(probe.InheritedCarrierEvaluationError, "authority ID must be"),
        ):
            probe.run_evaluation(args, repository_root=ROOT)
        self.assertTrue(CompletePreflight.completed)
        self.assertEqual(evaluator_reads, [])
        self.assertFalse((ROOT / probe.AUTHORITY_RECEIPT_PATH).exists())
        self.assertFalse((ROOT / probe.STATE_ROOT).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
