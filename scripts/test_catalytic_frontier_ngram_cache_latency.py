#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_checkpoint_control as checkpoint
import catalytic_frontier_ngram_cache_latency as ngram
import catalytic_frontier_single_request_latency as latency


class CatalyticFrontierNgramCacheLatencyTests(unittest.TestCase):
    def test_dedicated_entrypoint_changes_only_speculative_mode(self) -> None:
        source = inspect.getsource(ngram)
        self.assertIn('root_boundary="strict-prefix"', source)
        self.assertIn('speculative_mode="ngram-cache"', source)
        self.assertNotIn("fanout", source.lower())

    def test_scoped_launch_argument_is_exact_and_allowlisted(self) -> None:
        self.assertEqual(checkpoint.NGRAM_CACHE_SERVER_ARGS, ("--spec-type", "ngram-cache"))
        self.assertEqual(checkpoint.normalize_server_launch_args(()), ())
        self.assertEqual(
            checkpoint.normalize_server_launch_args(("--spec-type", "ngram-cache")),
            checkpoint.NGRAM_CACHE_SERVER_ARGS,
        )
        with self.assertRaises(latency.harness.FrontierHarnessError):
            checkpoint.normalize_server_launch_args(("--spec-type", "ngram-mod"))

    def test_default_launcher_hook_is_empty(self) -> None:
        sidecar = object.__new__(latency.harness.live_runtime.LiveSidecar)
        self.assertEqual(sidecar.server_launch_args(), [])

    def test_checkpoint_sidecar_reports_exact_speculative_identity(self) -> None:
        sidecar = object.__new__(checkpoint.ScopedCheckpointDiscoverySidecar)
        sidecar.scoped_server_launch_args = checkpoint.NGRAM_CACHE_SERVER_ARGS
        self.assertEqual(sidecar.server_launch_args(), ["--spec-type", "ngram-cache"])

    def test_timing_recorder_preserves_draft_acceptance(self) -> None:
        recorder = latency.TimingRecorder(origin=10.0)
        progress = b'data: {"prompt_progress":{"total":690,"cache":689}}\n'
        generated = b'data: {"content":"C","tokens":[42]}\n'
        terminal = b'data: {"stop":true,"timings":{"prompt_ms":50.0,"predicted_ms":80.0,"prompt_n":1,"predicted_n":6,"draft_n":5,"draft_n_accepted":5}}\n'
        with mock.patch.object(latency.time, "monotonic", side_effect=[10.1, 10.2, 10.3]):
            recorder(progress)
            recorder(generated)
            recorder(terminal)
        summary = recorder.summary(request_wall_seconds=0.4)
        self.assertEqual(summary["draft_n"], 5.0)
        self.assertEqual(summary["draft_n_accepted"], 5.0)

    def test_canonical_strict_prefix_predecessor_is_frozen(self) -> None:
        self.assertEqual(latency.STRICT_PREFIX_NO_SPEC_MEDIANS["predicted_ms"], 225.1865)
        self.assertEqual(
            latency.STRICT_PREFIX_NO_SPEC_MEDIANS["effective_wall_seconds_including_restore"],
            0.46100000001024455,
        )
        self.assertEqual(latency.STRICT_PREFIX_NO_SPEC_DIRECT_MEDIANS["prompt_ms"], 10414.7795)
        self.assertEqual(latency.STRICT_PREFIX_NGRAM_MIN_SPEEDUP, 1.25)

    def test_learning_and_second_carrier_are_acceptance_critical(self) -> None:
        source = inspect.getsource(latency.evaluate)
        self.assertIn("learning_warmup_charged", source)
        self.assertIn("ngram_second_carrier_declared", source)
        self.assertIn("catalytic_counted_accepted_draft_tokens", source)

    def test_launch_global_control_is_labeled_ngram_only(self) -> None:
        source = inspect.getsource(latency.evaluate)
        self.assertIn('"ngram-only" if speculative_mode == "ngram-cache"', source)
        self.assertIn('"cache-disabled-ngram-only"', source)
        self.assertIn('"canonical-neo-exp-0064-no-spec"', source)
        self.assertIn('"ngram_only_control_change_vs_neo_exp_0064_no_spec"', source)

    def test_draft_acceptance_gate_cannot_pass_from_control_route_only(self) -> None:
        catalytic = [
            {"timing": {"draft_n": 0, "draft_n_accepted": 0}},
            {"timing": {"draft_n": 0, "draft_n_accepted": 0}},
        ]
        control = [
            {"timing": {"draft_n": 8, "draft_n_accepted": 8}},
            {"timing": {"draft_n": 8, "draft_n_accepted": 8}},
        ]
        metrics = latency.draft_acceptance_metrics(catalytic, control)
        self.assertFalse(metrics["gate"])
        self.assertEqual(metrics["catalytic_accepted_draft_tokens"], 0)
        self.assertEqual(metrics["control_accepted_draft_tokens"], 16)

    def test_cleanup_closure_is_charged_before_acceptance(self) -> None:
        result = {
            "trial_design": {"speculative_mode": "ngram-cache"},
            "verdict": "accept",
            "classification": "strict-prefix-plus-ngram-cache-latency-supported-bounded",
            "next_boundary": "PROFILE",
            "metrics": {
                "counted_full_lifecycle": {
                    "catalytic_wall_seconds": 10.0,
                    "direct_wall_seconds": 100.0,
                }
            },
            "resources": {},
            "quality_gates": {
                "counted_full_lifecycle_wall_advantage": True,
                "fast_single_request_catalytic_inference_supported": True,
            },
        }
        cleanup = {
            "process_stopped": True,
            "runtime_removed": True,
            "port_free": True,
            "retirement_samples": [
                {"available": False, "bytes": None} for _ in range(5)
            ],
            "wddm": {},
            "stable_after": {"healthy": True, "listener_pids": [3860]},
            "readiness_controlled": False,
        }
        finalized = latency.finalize_result_after_cleanup(
            result,
            cleanup=cleanup,
            cleanup_wall_seconds=5.0,
            stable_pids={3860},
        )
        self.assertEqual(finalized["metrics"]["counted_full_lifecycle"]["catalytic_wall_seconds"], 15.0)
        self.assertTrue(finalized["quality_gates"]["ngram_process_retirement_closure"])
        self.assertEqual(finalized["verdict"], "accept")

        failed_result = {
            **result,
            "verdict": "accept",
            "metrics": {"counted_full_lifecycle": {"catalytic_wall_seconds": 10.0, "direct_wall_seconds": 100.0}},
            "resources": {},
            "quality_gates": dict(result["quality_gates"]),
        }
        failed_cleanup = dict(cleanup, process_stopped=False)
        rejected = latency.finalize_result_after_cleanup(
            failed_result,
            cleanup=failed_cleanup,
            cleanup_wall_seconds=5.0,
            stable_pids={3860},
        )
        self.assertEqual(rejected["verdict"], "reject")
        self.assertFalse(rejected["quality_gates"]["ngram_process_retirement_closure"])

    def test_ngram_cache_is_process_local_and_not_root_serialized(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        source = (repository / "common/speculative.cpp").read_text(encoding="utf-8")
        start = source.index("struct common_speculative_impl_ngram_cache")
        end = source.index("static common_speculative_impl_ngram_cache create_state_ngram_cache", start)
        block = source[start:end]
        self.assertIn("ngram_cache_context", block)
        self.assertIn("common_ngram_cache_update", block)
        self.assertNotIn("get_state(", block)
        self.assertNotIn("set_state(", block)


if __name__ == "__main__":
    unittest.main()
