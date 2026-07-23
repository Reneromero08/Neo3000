#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_single_request_latency as latency


class CatalyticFrontierSingleRequestLatencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repository = Path(__file__).resolve().parents[1]
        corpus = latency.harness.carrier.load_public_corpus(repository)
        cls.root = next(item for item in corpus["roots"] if item["root_id"] == latency.ROOT_ID)

    def test_branch_is_bound_to_qualified_water_control(self) -> None:
        panel = latency.water.panel_for(self.root)
        self.assertEqual(latency.water.base._panel_hash(panel), latency.PANEL_SHA256)
        self.assertEqual(latency.BRANCH_NUMBER, 7)
        self.assertEqual(panel[latency.BRANCH_NUMBER - 1]["answer"], latency.EXPECTED_ANSWER)
        self.assertEqual(latency.EXPECTED_ANSWER, "C")

    def test_trial_order_is_four_pairs_with_abba_first_route_balance(self) -> None:
        self.assertEqual(latency.COUNTED_PAIRS, 4)
        self.assertEqual(
            tuple(order[0] for order in latency.PAIR_ROUTE_ORDERS),
            ("catalytic", "direct", "direct", "catalytic"),
        )
        self.assertTrue(all(set(order) == {"catalytic", "direct"} for order in latency.PAIR_ROUTE_ORDERS))
        self.assertEqual(latency.WARMUP_ROUTE_ORDER, ("catalytic", "direct"))

    def test_timing_recorder_captures_ttft_terminal_and_server_prompt_time(self) -> None:
        recorder = latency.TimingRecorder(origin=10.0)
        progress = b'data: {"prompt_progress":{"total":690,"cache":543}}\n'
        generated = b'data: {"content":"C","tokens":[42]}\n'
        terminal = b'data: {"stop":true,"timings":{"prompt_ms":250.0,"prompt_per_second":588.0,"predicted_ms":50.0,"predicted_per_second":20.0,"prompt_n":147,"predicted_n":1}}\n'
        with mock.patch.object(latency.time, "monotonic", side_effect=[10.1, 10.5, 11.0]):
            recorder(progress)
            recorder(generated)
            recorder(terminal)
        summary = recorder.summary(request_wall_seconds=1.1)
        self.assertAlmostEqual(summary["first_event_seconds"], 0.1)
        self.assertAlmostEqual(summary["ttft_seconds"], 0.5)
        self.assertAlmostEqual(summary["terminal_event_seconds"], 1.0)
        self.assertEqual(summary["prompt_ms"], 250.0)
        self.assertEqual(summary["server_prompt_n"], 147.0)

    def test_root_response_requires_checkpoint_zero_and_invariant_identity(self) -> None:
        response = {
            "action": "root-save",
            "root_id": latency.ROOT_ID,
            "id_slot": 0,
            "n_tokens": latency.EXPECTED_PROMPT_ROOT_TOKENS,
            "n_bytes": 1234,
            "n_checkpoints": 0,
            "timings": {"root_ms": 2.5},
        }
        saved = latency.validate_root_response(response, action="root-save")
        restored = latency.validate_root_response(
            {**response, "action": "root-restore"},
            action="root-restore",
            expected=saved,
        )
        self.assertEqual(restored["n_tokens"], latency.EXPECTED_PROMPT_ROOT_TOKENS)
        with self.assertRaises(latency.harness.FrontierHarnessError):
            latency.validate_root_response(
                {**response, "n_checkpoints": 1},
                action="root-save",
            )

    def test_branch_payloads_differ_only_by_cache_flag(self) -> None:
        retained = {
            "terminal_stop_identity": {"token_id": 99},
            "retained_root_tokens": [1, 2],
        }
        spec = {"question": "q", "choices": {"A": "a", "B": "b", "C": "c", "D": "d"}, "answer": "C"}

        def payload(tokens: list[int], *, seed: int, cache_prompt: bool) -> dict[str, object]:
            return {"prompt": list(tokens), "seed": seed, "cache_prompt": cache_prompt, "temperature": 0}

        with (
            mock.patch.object(
                latency.harness.carrier,
                "derive_continuation_suffix",
                return_value={"suffix_tokens": [3, 4]},
            ),
            mock.patch.object(latency.harness.carrier, "_branch_payload", side_effect=payload),
        ):
            catalytic_tokens, catalytic = latency.branch_request(object(), retained, spec, cache_prompt=True)
            direct_tokens, direct = latency.branch_request(object(), retained, spec, cache_prompt=False)
        self.assertEqual(catalytic_tokens, direct_tokens)
        self.assertEqual(catalytic["prompt"], direct["prompt"])
        self.assertEqual(catalytic["seed"], direct["seed"])
        self.assertTrue(catalytic["cache_prompt"])
        self.assertFalse(direct["cache_prompt"])

    def test_timed_branch_passes_sse_recorder_and_binds_generated_hash(self) -> None:
        execution = {"generated_token_ids": [1, 2, 3]}
        completion = {
            "content": json.dumps({"answer": "C"}),
            "execution": execution,
            "prompt_tokens": 690,
            "cached_prompt_tokens": 543,
            "fresh_prompt_tokens": 147,
            "completion_tokens": 3,
            "fresh_model_tokens": 150,
            "wall_seconds": 1.0,
        }
        with (
            mock.patch.object(latency, "branch_request", return_value=(list(range(690)), {"cache_prompt": True})),
            mock.patch.object(latency.harness, "run_completion", return_value=completion) as run_completion,
            mock.patch.object(latency.harness.carrier, "parse_branch_output", return_value="C"),
            mock.patch.object(
                latency.TimingRecorder,
                "summary",
                return_value={
                    "prompt_ms": 100.0,
                    "ttft_seconds": 0.2,
                    "server_prompt_n": 147,
                    "server_predicted_n": 3,
                },
            ),
        ):
            record = latency.run_timed_branch(
                sidecar=object(),
                codec=object(),
                retained={},
                spec={"answer": "C"},
                route="catalytic",
                label="test",
            )
        self.assertTrue(record["correct"])
        self.assertEqual(record["route"], "catalytic")
        self.assertIsInstance(run_completion.call_args.kwargs["recorder"], latency.TimingRecorder)
        expected_hash = latency.harness.sha256_bytes(latency.harness.carrier.canonical_json_bytes([1, 2, 3]))
        self.assertEqual(record["generated_token_sha256"], expected_hash)

    def test_classification_requires_utility_paired_wins_and_all_speed_gates(self) -> None:
        self.assertEqual(
            latency.classify_result(
                utility_exact=True,
                paired_wins=3,
                prompt_speedup=1.25,
                ttft_speedup=1.25,
                effective_wall_speedup=1.25,
                full_lifecycle_wall_advantage=True,
                full_lifecycle_fresh_advantage=True,
            ),
            "fast-single-request-catalytic-latency-supported-bounded",
        )
        self.assertEqual(
            latency.classify_result(
                utility_exact=True,
                paired_wins=2,
                prompt_speedup=2.0,
                ttft_speedup=2.0,
                effective_wall_speedup=2.0,
                full_lifecycle_wall_advantage=True,
                full_lifecycle_fresh_advantage=True,
            ),
            "exact-reuse-without-preregistered-latency-gate",
        )
        self.assertEqual(
            latency.classify_result(
                utility_exact=False,
                paired_wins=4,
                prompt_speedup=2.0,
                ttft_speedup=2.0,
                effective_wall_speedup=2.0,
                full_lifecycle_wall_advantage=True,
                full_lifecycle_fresh_advantage=True,
            ),
            "single-request-utility-or-identity-failure",
        )
        self.assertEqual(
            latency.classify_result(
                utility_exact=True,
                paired_wins=4,
                prompt_speedup=2.0,
                ttft_speedup=2.0,
                effective_wall_speedup=2.0,
                full_lifecycle_wall_advantage=False,
                full_lifecycle_fresh_advantage=True,
            ),
            "exact-reuse-without-preregistered-latency-gate",
        )

    def test_distribution_reports_median_and_interpolated_p95(self) -> None:
        observed = latency.distribution([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(observed["median"], 2.5)
        self.assertAlmostEqual(observed["p95"], 3.85)

    def test_checkpoint_cli_is_fixed_to_zero_and_no_scaling_argument_exists(self) -> None:
        with mock.patch.object(sys, "argv", ["catalytic_frontier_single_request_latency.py"]):
            args = latency.parse_args()
        self.assertEqual(args.ctx_checkpoints, 0)
        self.assertEqual(args.binary, latency.DEFAULT_BINARY)
        self.assertNotIn("--fanout", inspect.getsource(latency.parse_args))

    def test_pinned_binary_guard_precedes_stable_contact(self) -> None:
        source = inspect.getsource(latency.main)
        self.assertLess(source.index("water.require_pinned_binary(binary)"), source.index("require_stable()"))

    def test_harness_recorder_hook_is_optional_and_backward_compatible(self) -> None:
        parameter = inspect.signature(latency.harness.run_completion).parameters["recorder"]
        self.assertIsNone(parameter.default)
        observer = inspect.signature(latency.harness.run_completion).parameters["guard_phase_observer"]
        self.assertIsNone(observer.default)

    def test_timed_branch_can_capture_one_guard_phase_record(self) -> None:
        completion = {
            "content": json.dumps({"answer": "C"}),
            "execution": {"generated_token_ids": [1, 2, 3]},
            "prompt_tokens": 690,
            "cached_prompt_tokens": 689,
            "fresh_prompt_tokens": 1,
            "completion_tokens": 3,
            "fresh_model_tokens": 4,
            "wall_seconds": 0.5,
        }
        guard_record = {
            "name": "frontier:profile",
            "wddm_policy_active": False,
            "phase_seconds": {
                "pre_active": 0.01,
                "pre_ownership": 0.04,
                "call": 0.25,
                "executor_wait": 0.25,
                "post_active": 0.01,
                "post_ownership": 0.04,
            },
            "poll_active_count": 1,
            "poll_active_seconds": 0.01,
            "pre_ownership": {
                "boundary": "pre-request:frontier:profile",
                "passed": True,
            },
            "post_ownership": {
                "boundary": "post-request:frontier:profile",
                "passed": True,
            },
            "total_seconds": 0.35,
        }

        def run_completion(_sidecar, _label, _payload, **kwargs):
            kwargs["guard_phase_observer"](guard_record)
            return completion

        with (
            mock.patch.object(
                latency,
                "branch_request",
                return_value=(list(range(690)), {"cache_prompt": True}),
            ),
            mock.patch.object(latency.harness, "run_completion", side_effect=run_completion),
            mock.patch.object(latency.harness.carrier, "parse_branch_output", return_value="C"),
            mock.patch.object(
                latency.TimingRecorder,
                "summary",
                return_value={
                    "prompt_ms": 100.0,
                    "ttft_seconds": 0.2,
                    "server_prompt_n": 1,
                    "server_predicted_n": 3,
                },
            ),
        ):
            record = latency.run_timed_branch(
                sidecar=object(),
                codec=object(),
                retained={},
                spec={"answer": "C"},
                route="catalytic",
                label="profile",
                profile_guard_phases=True,
            )

        self.assertEqual(record["timing"]["guard_phase"], guard_record)

    def test_guard_phase_schema_fails_closed(self) -> None:
        with self.assertRaises(latency.harness.FrontierHarnessError):
            latency.validate_guard_phase_record(
                {
                    "name": "frontier:profile",
                    "phase_seconds": {},
                },
                expected_name="frontier:profile",
            )

    def test_timing_identity_mismatch_fails_closed(self) -> None:
        completion = {
            "content": json.dumps({"answer": "C"}),
            "execution": {"generated_token_ids": [1, 2, 3]},
            "prompt_tokens": 690,
            "cached_prompt_tokens": 543,
            "fresh_prompt_tokens": 147,
            "completion_tokens": 3,
            "fresh_model_tokens": 150,
            "wall_seconds": 1.0,
        }
        with (
            mock.patch.object(latency, "branch_request", return_value=(list(range(690)), {"cache_prompt": True})),
            mock.patch.object(latency.harness, "run_completion", return_value=completion),
            mock.patch.object(latency.TimingRecorder, "summary", return_value={"server_prompt_n": 146, "server_predicted_n": 3}),
        ):
            with self.assertRaises(latency.harness.FrontierHarnessError):
                latency.run_timed_branch(sidecar=object(), codec=object(), retained={}, spec={"answer": "C"}, route="catalytic", label="test")

    def test_artifact_paths_must_be_unused(self) -> None:
        with mock.patch.object(Path, "exists", return_value=False):
            latency.require_unused_artifact_paths(Path("result.json"), Path("server.log"))
            with self.assertRaises(latency.harness.FrontierHarnessError):
                latency.require_unused_artifact_paths(Path("result.json"), Path("result.json"))
        with mock.patch.object(Path, "exists", return_value=True):
            with self.assertRaises(latency.harness.FrontierHarnessError):
                latency.require_unused_artifact_paths(Path("result.json"))


if __name__ == "__main__":
    unittest.main()
