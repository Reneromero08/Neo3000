#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_harness as harness
import catalytic_frontier_ram_root as ram_root


class CatalyticFrontierRamRootTests(unittest.TestCase):
    def response(self, action: str = "root-save") -> dict[str, object]:
        return {
            "action": action,
            "root_id": ram_root.ROOT_ID,
            "id_slot": 0,
            "id_slot_source": 0,
            "n_tokens": 285,
            "n_bytes": 80_000_000,
            "n_checkpoints": 1,
            "timings": {"root_ms": 12.5},
        }

    def test_root_response_requires_stable_identity_and_size(self) -> None:
        saved = ram_root.validate_root_response(self.response(), action="root-save")
        restored = ram_root.validate_root_response(
            self.response("root-restore"),
            action="root-restore",
            expected=saved,
        )
        self.assertEqual(restored["n_tokens"], 285)
        changed = self.response("root-restore")
        changed["n_bytes"] = 79_999_999
        with self.assertRaises(harness.FrontierHarnessError):
            ram_root.validate_root_response(changed, action="root-restore", expected=saved)

    def test_experimental_binary_identity_is_exact_not_lock_derived(self) -> None:
        binary = Path(__file__).resolve()
        with (
            mock.patch.object(harness.live_runtime, "sha256_file", return_value="A" * 64),
            mock.patch.object(harness.live_runtime, "binary_version", return_value="178 (6c63039)"),
        ):
            identity = harness.discovery_binary_identity(binary)
        self.assertEqual(identity["sha256"], "A" * 64)
        self.assertEqual(identity["runtime_version"], "178 (6c63039)")

    def test_live_restore_discriminator_separates_restore_from_live_state(self) -> None:
        self.assertEqual(
            ram_root.classify_live_restore(
                expected="D",
                live_answer="D",
                restored_answer="C",
                direct_answer="D",
            ),
            "restore-divergence",
        )
        self.assertEqual(
            ram_root.classify_live_restore(
                expected="D",
                live_answer="C",
                restored_answer="C",
                direct_answer="D",
            ),
            "live-prefix-state-divergence",
        )
        self.assertEqual(
            ram_root.classify_live_restore(
                expected="D",
                live_answer="C",
                restored_answer="D",
                direct_answer="D",
            ),
            "live-route-only-divergence",
        )
        self.assertEqual(
            ram_root.classify_live_restore(
                expected="D",
                live_answer="D",
                restored_answer="D",
                direct_answer="C",
            ),
            "direct-control-failed",
        )

    def test_prompt_root_materialization_payload_is_fresh_and_zero_output(self) -> None:
        tokens = [11, 22, 33]
        payload = ram_root.prompt_root_materialization_payload(tokens)
        self.assertEqual(payload["prompt"], tokens)
        self.assertEqual(payload["n_predict"], 0)
        self.assertIs(payload["cache_prompt"], False)
        self.assertNotIn("grammar", payload)
        self.assertEqual(payload["id_slot"], 0)

    def test_run_completion_forwards_zero_output_terminal_kind(self) -> None:
        execution = SimpleNamespace(
            prompt_tokens=3,
            cached_prompt_tokens=0,
            completion_tokens=0,
        )
        sidecar = mock.Mock()
        sidecar.guarded.return_value = execution
        with mock.patch.object(
            harness.carrier,
            "validate_inference_terminal_evidence",
            return_value={"terminal_evidence_passed": True},
        ) as validate:
            record = harness.run_completion(
                sidecar,
                "zero-output-probe",
                {"prompt": [11, 22, 33], "n_predict": 0},
                operation_kind="zero-output-root-readdress",

            )
        self.assertEqual(record["fresh_model_tokens"], 3)
        self.assertEqual(
            validate.call_args.kwargs["operation_kind"],
            "zero-output-root-readdress",
        )

if __name__ == "__main__":
    unittest.main()
