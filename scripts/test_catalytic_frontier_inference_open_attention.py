from __future__ import annotations

import os
import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_inference_open_attention as experiment


class InferenceOpenAttentionTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(experiment.ENVIRONMENT_NAME, None)

    def test_classification_accepts_only_integrity_and_speed(self):
        integrity = {"identity": True, "output": True}
        speed = {"prompt": True, "wall": True}
        self.assertEqual(
            experiment.classify(integrity, speed),
            "accept-bounded-agents-a1-mma-open-b-boundary",
        )
        self.assertEqual(
            experiment.classify({**integrity, "output": False}, speed),
            "reject-integrity-agents-a1-open-b-boundary",
        )
        self.assertEqual(
            experiment.classify(integrity, {**speed, "prompt": False}),
            "reject-speed-agents-a1-open-b-boundary-exact",
        )

    def test_scoped_environment_restores_after_success(self):
        sidecar = object.__new__(experiment.FattnBModeSidecar)
        sidecar.materialize_mode = "1"
        readiness = {"launch_configuration": {"context_checkpoints": 0}}
        parent = (
            experiment.checkpoint_control.ScopedCheckpointDiscoverySidecar
        )
        with mock.patch.object(parent, "launch", return_value=readiness):
            observed = sidecar.launch()
        self.assertNotIn(experiment.ENVIRONMENT_NAME, os.environ)
        self.assertEqual(
            observed["launch_configuration"]["fattn_b_materialize"],
            1,
        )
        self.assertTrue(
            observed["launch_configuration"]["fattn_b_scratch_reserved"]
        )

    def test_scoped_environment_restores_after_failure(self):
        sidecar = object.__new__(experiment.FattnBModeSidecar)
        sidecar.materialize_mode = "0"
        parent = (
            experiment.checkpoint_control.ScopedCheckpointDiscoverySidecar
        )
        with mock.patch.object(
            parent,
            "launch",
            side_effect=RuntimeError("synthetic launch failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                sidecar.launch()
        self.assertNotIn(experiment.ENVIRONMENT_NAME, os.environ)

    def test_marker_parser_requires_exact_mode_and_geometry(self):
        marker = (
            "neo3000_fattn_b_probe: materialize=1 DKQ=256 DV=256 "
            "ncols1=8 ncols2=8 nbatch_fa=32 "
            "scratch_bytes_per_block=4096 reserve=1\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "route.log"
            path.write_text(marker, encoding="utf-8")
            parsed = experiment.marker_geometry(path, 1)
            self.assertEqual(len(parsed["markers"]), 1)
            self.assertEqual(
                parsed["normalized_geometry"][0],
                (256, 256, 8, 8, 32, 4096, 1),
            )
            self.assertEqual(
                parsed["derived_materialized_store_bytes_per_b_iteration"],
                [4096],
            )
            self.assertEqual(
                parsed["derived_materialized_load_bytes_per_b_iteration"],
                [4096],
            )
            with self.assertRaisesRegex(
                experiment.ExperimentError,
                "route marker mismatch",
            ):
                experiment.marker_geometry(path, 0)

    def test_marker_parser_rejects_wrong_scratch_formula(self):
        marker = (
            "neo3000_fattn_b_probe: materialize=0 DKQ=256 DV=256 "
            "ncols1=1 ncols2=8 nbatch_fa=64 "
            "scratch_bytes_per_block=1 reserve=1\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "route.log"
            path.write_text(marker, encoding="utf-8")
            with self.assertRaisesRegex(
                experiment.ExperimentError,
                "marker geometry invalid",
            ):
                experiment.marker_geometry(path, 0)

    def test_cuda_source_has_disjoint_blocks_and_two_phase_barriers(self):
        source = experiment.CUDA_MMA.read_text(encoding="utf-8")
        self.assertIn("const size_t block_linear", source)
        self.assertIn("block_linear*fattn_b_words_per_block", source)
        marker = source.index('"neo3000_fattn_b_probe:')
        warning = source.rfind("GGML_LOG_WARN(", 0, marker)
        self.assertGreaterEqual(warning, 0)
        store = source.index(
            "thread_scratch[k*T_B_VKQ::ne + l] = packed.bits;"
        )
        first_barrier = source.index("__syncthreads();", store)
        load = source.index("packed.bits =", first_barrier)
        second_barrier = source.index("__syncthreads();", load)
        self.assertLess(store, first_barrier)
        self.assertLess(first_barrier, load)
        self.assertLess(load, second_barrier)

    def test_exclusive_json_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            artifact = experiment.write_exclusive_json(path, {"answer": 42})
            self.assertEqual(artifact["bytes"], path.stat().st_size)
            with self.assertRaisesRegex(
                experiment.ExperimentError,
                "result path already exists",
            ):
                experiment.write_exclusive_json(path, {"answer": 43})

    def test_task_preparation_does_not_create_consumed_marker(self):
        codec = mock.Mock()
        codec.render_messages.return_value = "rendered"
        codec.tokenize.return_value = list(
            range(experiment.EXPECTED_TASK_A_PROMPT_TOKENS)
        )
        root = {"root_id": experiment.ROOT_ID}
        panel = [
            {"answer": "A"}
            for _ in range(experiment.BRANCH_NUMBER)
        ]
        panel[experiment.BRANCH_NUMBER - 1] = {
            "answer": experiment.EXPECTED_ANSWER
        }
        with mock.patch.object(experiment.water, "panel_for", return_value=panel):
            with mock.patch.object(
                experiment.latency.water.base,
                "_panel_hash",
                return_value=experiment.BRANCH_PANEL_SHA256,
            ):
                with mock.patch.object(
                    experiment.harness.carrier,
                    "_task_a_payload",
                    return_value={"prompt": "prepared"},
                ):
                    with mock.patch.object(
                        experiment.harness.carrier,
                        "task_a_messages",
                        return_value=[{"role": "user", "content": "task"}],
                    ):
                        prepared = experiment.prepare_task_and_branch(codec, root)
        self.assertEqual(prepared["payload"], {"prompt": "prepared"})

    def test_route_consumes_only_after_fallible_preparation(self):
        source = inspect.getsource(experiment.run_route)
        prepared = source.index("prepare_task_and_branch")
        consumed = source.index("create_consumed_marker")
        executed = source.index("task_and_branch", consumed)
        self.assertLess(prepared, consumed)
        self.assertLess(consumed, executed)

    def test_pre_readiness_log_path_falls_back_to_session_log(self):
        sidecar = mock.Mock()
        sidecar.readiness = {}
        sidecar.log_root = Path("logs")
        sidecar.session_id = "session"
        self.assertEqual(
            experiment.sidecar_log_source(sidecar),
            Path("logs") / "session.log",
        )

    def test_resource_gate_rejects_telemetry_or_ceiling_failure(self):
        valid = {
            "wddm_failure_reason": None,
            "wddm_sample_count": 2,
            "peak_wddm_bytes": experiment.harness.WDDM_CEILING_BYTES,
        }
        self.assertTrue(experiment.resource_gate(valid))
        self.assertFalse(
            experiment.resource_gate(
                {**valid, "wddm_failure_reason": "telemetry-lost"}
            )
        )
        self.assertFalse(
            experiment.resource_gate(
                {
                    **valid,
                    "peak_wddm_bytes": (
                        experiment.harness.WDDM_CEILING_BYTES + 1
                    ),
                }
            )
        )

    def test_latency_adjudication_uses_current_timing_schema(self):
        primary = [
            {"timing": {"prompt_ms": float(index)}}
            for index in range(1, experiment.COUNTED_REPETITIONS + 1)
        ]
        control = [
            {"timing": {"prompt_ms": float(index + 10)}}
            for index in range(1, experiment.COUNTED_REPETITIONS + 1)
        ]
        self.assertEqual(
            experiment.median_metric(primary, "prompt_ms"),
            5.0,
        )
        self.assertEqual(
            experiment.all_pairs_dominance(primary, control),
            1.0,
        )

    def test_offline_adjudicator_has_no_live_execution(self):
        source = inspect.getsource(experiment.adjudicate_existing)
        self.assertNotIn("run_route(", source)
        self.assertNotIn("require_stable(", source)
        self.assertNotIn("LiveSidecar", source)
        self.assertIn("completed_routes", source)
        self.assertIn("marker_geometry", source)

    def test_process_resources_accepts_live_peak_dedicated_schema(self):
        sidecar = mock.Mock()
        sidecar.process = None
        sidecar.telemetry.return_value = {
            "peak_dedicated_bytes": 2_362_318_848,
            "sample_count": 73,
            "failure_reason": None,
        }
        resources = experiment.harness.process_resources(sidecar, None)
        self.assertEqual(resources["peak_wddm_bytes"], 2_362_318_848)
        self.assertEqual(resources["wddm_sample_count"], 73)
        self.assertTrue(experiment.resource_gate(resources))

    def test_route_preserves_partial_result_before_resource_gate(self):
        source = inspect.getsource(experiment.run_route)
        result_assignment = source.index('result = {', source.index("resources ="))
        resource_gate = source.index("resource_gate(resources)", result_assignment)
        self.assertLess(result_assignment, resource_gate)

    def test_route_source_fails_cleanup_before_success_return(self):
        source = inspect.getsource(experiment.run_route)
        cleanup_gate = source.index(
            'cleanup.get("integrity", {}).get("passed") is not True'
        )
        success_return = source.index("return result", cleanup_gate)
        self.assertLess(cleanup_gate, success_return)


if __name__ == "__main__":
    unittest.main()
