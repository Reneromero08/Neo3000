from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_sidecar as linux
import catalytic_frontier_harness as harness


class LinuxSidecarTests(unittest.TestCase):
    def test_static_machine_laws(self):
        audit = linux.static_audit()
        self.assertTrue(all(audit["gates"].values()))
        self.assertFalse(audit["contact"])

    def test_launch_contract_is_linux_cuda_single_slot(self):
        source = Path(linux.__file__).read_text(encoding="utf-8")
        for value in (
            '"--host"',
            '"127.0.0.1"',
            '"--parallel"',
            '"--ctx-checkpoints"',
            '"--cache-ram-root-device"',
            '"--gpu-layers"',
            '"auto"',
            '"--cpu-moe"',
        ):
            self.assertIn(value, source)
        self.assertNotIn("WDDM", source)
        self.assertNotIn("CREATE_NEW_PROCESS_GROUP", source)

    def test_runtime_identity_includes_dynamic_server_implementation(self):
        source = Path(linux.__file__).read_text(encoding="utf-8")
        verify = source[
            source.index("def verify_identities(") :
            source.index("def launch_args(")
        ]
        self.assertIn("linked_library_identities(self.binary)", verify)
        self.assertIn('"libllama-server-impl.so"', source)

    def test_ldd_parser_preserves_paths_with_spaces(self):
        path = ROOT / "build" / "library with spaces.so"
        with mock.patch.object(Path, "resolve", return_value=path):
            parsed = linux.parse_ldd_paths(
                "libexample.so => /tmp/library with spaces.so (0x1234)\n"
            )
        self.assertEqual(parsed, {path})

    def test_cleanup_preserves_transaction_files(self):
        source = Path(linux.__file__).read_text(encoding="utf-8")
        stop = source[source.index("def stop(") : source.index("def static_audit(")]
        self.assertIn("self.process.terminate()", stop)
        self.assertIn('"run_root_preserved"', stop)
        self.assertNotIn("rmtree", stop)
        self.assertNotIn(".unlink(", stop)
        self.assertNotIn("os.remove", stop)

    def test_request_guards_use_proc_ownership_without_http(self):
        source = Path(linux.__file__).read_text(encoding="utf-8")
        exact = source[
            source.index("def exact_ownership(") :
            source.index("def guarded(", source.index("def exact_ownership("))
        ]
        self.assertIn("pid_owns_listener", exact)
        self.assertIn("/proc/", exact)
        self.assertNotIn("health_ok", exact)

    def test_shared_harness_dispatches_native_resource_accounting(self):
        expected = {
            "resource_semantics": "linux-proc-rss-plus-nvidia-compute-process"
        }

        class Native:
            def resource_snapshot(self, baseline_private):
                self.baseline_private = baseline_private
                return expected

        sidecar = Native()
        self.assertEqual(harness.process_resources(sidecar, 17), expected)
        self.assertEqual(sidecar.baseline_private, 17)

    def test_guarded_enforces_requested_timeout(self):
        sidecar = object.__new__(linux.LinuxSidecar)
        sidecar.exact_ownership = mock.Mock(return_value={})
        sidecar._sample = mock.Mock(return_value={})

        with self.assertRaisesRegex(
            linux.LinuxSidecarError,
            "guarded callback exceeded",
        ):
            sidecar.guarded(
                "timeout-behavior",
                lambda: time.sleep(0.2),
                timeout=0.01,
            )

        self.assertEqual(
            [call.args[0] for call in sidecar.exact_ownership.call_args_list],
            ["pre:timeout-behavior", "timeout:timeout-behavior"],
        )
        self.assertEqual(
            [call.args[0] for call in sidecar._sample.call_args_list],
            ["pre:timeout-behavior", "timeout:timeout-behavior"],
        )


if __name__ == "__main__":
    unittest.main()
