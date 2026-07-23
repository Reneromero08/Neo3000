import unittest
import inspect
from pathlib import Path

import catalytic_frontier_checkpoint_control as checkpoint
import catalytic_frontier_cuda_root_host_control as host_control
import catalytic_frontier_cuda_root_partial_moe_latency as partial_moe
import catalytic_frontier_cuda_root_partial_moe_33_latency as partial_moe_33
import catalytic_frontier_single_request_latency as latency


class CudaRootLatencyTests(unittest.TestCase):
    def response(self, action: str, *, device_after: int | None = None) -> dict:
        n_device = 79_800_000
        n_gpu = 79_700_000
        n_host = latency.STRICT_PREFIX_LOGICAL_ROOT_BYTES - n_device
        return {
            "action": action,
            "root_id": latency.ROOT_ID,
            "id_slot": 0,
            "n_tokens": 689,
            "n_bytes": latency.STRICT_PREFIX_LOGICAL_ROOT_BYTES,
            "n_host_bytes": n_host,
            "n_device_bytes": n_device,
            "n_device_bytes_after": n_device if device_after is None else device_after,
            "n_gpu_bytes": n_gpu,
            "n_gpu_bytes_after": n_gpu if device_after is None else device_after,
            "n_checkpoints": 0,
            "timings": {"root_ms": 4.0},
        }

    def test_launcher_allows_only_exact_cuda_root_identity(self):
        self.assertEqual(checkpoint.CUDA_ROOT_SERVER_ARGS, ("--cache-ram-root-device",))
        self.assertEqual(
            checkpoint.normalize_server_launch_args(("--cache-ram-root-device",)),
            checkpoint.CUDA_ROOT_SERVER_ARGS,
        )
        with self.assertRaises(Exception):
            checkpoint.normalize_server_launch_args(("--cache-ram-root-device", "--spec-type", "ngram-cache"))

    def test_device_receipt_requires_exact_accounting_and_nonzero_storage(self):
        saved = latency.validate_root_response(
            self.response("root-save"),
            action="root-save",
            root_storage="device",
        )
        restored = latency.validate_root_response(
            self.response("root-restore"),
            action="root-restore",
            expected=saved,
            root_storage="device",
        )
        self.assertEqual(restored["n_device_bytes"], saved["n_device_bytes"])
        self.assertEqual(restored["n_gpu_bytes"], saved["n_gpu_bytes"])

        broken = self.response("root-save")
        broken["n_device_bytes"] = 0
        broken["n_device_bytes_after"] = 0
        broken["n_host_bytes"] = broken["n_bytes"]
        with self.assertRaises(Exception):
            latency.validate_root_response(broken, action="root-save", root_storage="device")

        cpu_only = self.response("root-save")
        cpu_only["n_gpu_bytes"] = 0
        cpu_only["n_gpu_bytes_after"] = 0
        with self.assertRaises(Exception):
            latency.validate_root_response(cpu_only, action="root-save", root_storage="device")

    def test_device_erase_requires_zero_remaining_bytes(self):
        saved = latency.validate_root_response(
            self.response("root-save"),
            action="root-save",
            root_storage="device",
        )
        erased = latency.validate_root_response(
            self.response("root-erase", device_after=0),
            action="root-erase",
            expected=saved,
            root_storage="device",
        )
        self.assertEqual(erased["n_device_bytes_after"], 0)
        self.assertEqual(erased["n_gpu_bytes_after"], 0)

        with self.assertRaises(Exception):
            latency.validate_root_response(
                self.response("root-erase"),
                action="root-erase",
                expected=saved,
                root_storage="device",
            )

    def test_cuda_gates_are_stricter_than_direct_advantage(self):
        self.assertEqual(latency.STRICT_PREFIX_HOST_ROOT_RESTORE_SERVER_MEDIAN_MS, 13.9525)
        self.assertEqual(latency.CUDA_ROOT_MIN_RESTORE_SPEEDUP, 2.0)
        self.assertEqual(latency.CUDA_ROOT_MIN_EFFECTIVE_WALL_SPEEDUP, 1.02)
        self.assertEqual(len(latency.CUDA_ROOT_BINARY_SHA256), 64)
        self.assertEqual(latency.CUDA_ROOT_BINARY_SHA256, latency.CUDA_ROOT_RUNTIME_SHA256["llama-server.exe"])
        self.assertEqual(
            set(latency.CUDA_ROOT_RUNTIME_SHA256),
            {"ggml-base.dll", "ggml-cpu.dll", "ggml-cuda.dll", "ggml.dll", "llama-common.dll", "llama-server-impl.dll", "llama-server.exe", "llama.dll", "mtmd.dll"},
        )
        self.assertTrue(all(len(value) == 64 for value in latency.CUDA_ROOT_RUNTIME_SHA256.values()))
        source = Path(latency.__file__).read_text(encoding="utf-8")
        self.assertIn("cuda-resident-strict-prefix-root-latency-supported-bounded", source)
        self.assertIn("cuda_device_bytes_zero_after_erase", source)
        self.assertIn("cuda_wddm_at_or_below_6000_mib", source)

    def test_cleanup_wddm_accepts_current_dedicated_schema_and_legacy_schema(self):
        self.assertEqual(
            latency.cleanup_peak_wddm_bytes({"wddm": {"peak_dedicated_bytes": 2_444_107_776}}),
            2_444_107_776,
        )
        self.assertEqual(
            latency.cleanup_peak_wddm_bytes({"wddm": {"peak_bytes": 2_444_107_776}}),
            2_444_107_776,
        )
        self.assertIsNone(latency.cleanup_peak_wddm_bytes({"wddm": {"peak_dedicated_bytes": None}}))

    def test_same_runtime_host_control_changes_only_root_storage(self):
        source = inspect.getsource(host_control)
        self.assertIn('root_boundary="strict-prefix"', source)
        self.assertIn('root_storage="host"', source)
        self.assertIn('runtime_identity="cuda-bundle"', source)
        self.assertNotIn("--cache-ram-root-device", source)
        self.assertEqual(latency.RUNTIME_IDENTITY_MODES, ("canonical", "cuda-bundle"))

    def test_partial_moe_profile_is_exact_and_cuda_root_stays_enabled(self):
        self.assertEqual(checkpoint.DEFAULT_MOE_SERVER_ARGS, ("--cpu-moe",))
        self.assertEqual(checkpoint.PARTIAL_MOE_26_SERVER_ARGS, ("--n-cpu-moe", "26"))
        self.assertEqual(
            checkpoint.normalize_moe_server_args(("--n-cpu-moe", "26")),
            checkpoint.PARTIAL_MOE_26_SERVER_ARGS,
        )
        with self.assertRaises(Exception):
            checkpoint.normalize_moe_server_args(("--n-cpu-moe", "25"))
        source = inspect.getsource(partial_moe)
        self.assertIn('root_storage="device"', source)
        self.assertIn('runtime_identity="cuda-bundle"', source)
        self.assertIn("PARTIAL_MOE_26_SERVER_ARGS", source)

    def test_partial_moe_readiness_uses_current_wddm_schema(self):
        self.assertEqual(
            latency.readiness_peak_wddm_bytes({"wddm": {"peak_dedicated_bytes": 5_483 * 1024 * 1024}}),
            5_483 * 1024 * 1024,
        )
        self.assertIsNone(latency.readiness_peak_wddm_bytes({"wddm": {}}))

    def test_repaired_partial_moe_profile_is_exactly_seven_gpu_expert_layers(self):
        self.assertEqual(checkpoint.PARTIAL_MOE_33_SERVER_ARGS, ("--n-cpu-moe", "33"))
        self.assertEqual(
            checkpoint.normalize_moe_server_args(("--n-cpu-moe", "33")),
            checkpoint.PARTIAL_MOE_33_SERVER_ARGS,
        )
        source = inspect.getsource(partial_moe_33)
        self.assertIn("PARTIAL_MOE_33_SERVER_ARGS", source)
        self.assertIn('root_storage="device"', source)


if __name__ == "__main__":
    unittest.main()
