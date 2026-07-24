from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_harness as harness
import catalytic_frontier_terminal_logits_continuation as terminal


def root_receipt(*, action: str, terminal_logits: bool) -> dict[str, object]:
    n_logits = 151_936 if terminal_logits else 0
    host_bytes = 200 + n_logits * 4
    device_bytes = 2_000
    erased = action == "root-erase"
    return {
        "action": action,
        "root_id": terminal.TERMINAL_ROOT_ID if terminal_logits else terminal.BASE_ROOT_ID,
        "n_tokens": (
            terminal.EXPECTED_TERMINAL_TOKENS
            if terminal_logits
            else terminal.EXPECTED_BASE_TOKENS
        ),
        "n_bytes": host_bytes + device_bytes,
        "n_host_bytes": host_bytes,
        "n_device_bytes": device_bytes,
        "n_device_bytes_after": 0 if erased else device_bytes,
        "n_gpu_bytes": device_bytes,
        "n_gpu_bytes_after": 0 if erased else device_bytes,
        "n_checkpoints": 0,
        "n_roots_after": 0 if erased else 1,
        "n_total_bytes_after": 0 if erased else host_bytes + device_bytes,
        "n_total_device_bytes_after": 0 if erased else device_bytes,
        "n_total_gpu_bytes_after": 0 if erased else device_bytes,
        "has_terminal_logits": terminal_logits,
        "n_terminal_logits": n_logits,
        "n_terminal_logits_bytes": n_logits * 4,
        "terminal_logits_fnv64": "1" * 16 if terminal_logits else "",
        "terminal_prompt_fnv64": "2" * 16 if terminal_logits else "",
        "terminal_sampler_fnv64": "3" * 16 if terminal_logits else "",
        "terminal_position": (
            terminal.EXPECTED_TERMINAL_TOKENS - 1 if terminal_logits else -1
        ),
        "timings": {"root_ms": 1.0},
    }


class TerminalLogitsContinuationTests(unittest.TestCase):
    def test_preregistered_geometry_is_t16_and_order_balanced(self):
        self.assertEqual(terminal.COUNTED_PAIRS, 16)
        self.assertEqual(len(terminal.PAIR_ORDERS), 16)
        self.assertEqual(
            terminal.PAIR_ORDERS.count(("primary", "control")),
            terminal.PAIR_ORDERS.count(("control", "primary")),
        )
        self.assertEqual(terminal.EXPECTED_BASE_TOKENS, 689)
        self.assertEqual(terminal.EXPECTED_TERMINAL_TOKENS, 690)
        self.assertEqual(terminal.MIN_PROMPT_SPEEDUP, 1.50)
        self.assertEqual(terminal.MIN_TTFT_SPEEDUP, 1.08)
        self.assertEqual(terminal.MIN_WALL_SPEEDUP, 1.05)
        self.assertEqual(terminal.MIN_PAIR_DOMINANCE, 0.70)
        self.assertEqual(terminal.MAX_GENERATION_REGRESSION, 0.05)

    def test_terminal_root_receipt_requires_exact_f32_and_digest_geometry(self):
        receipt = root_receipt(action="root-save", terminal_logits=True)
        validated = terminal.validate_root(
            receipt,
            action="root-save",
            root_id=terminal.TERMINAL_ROOT_ID,
            n_tokens=terminal.EXPECTED_TERMINAL_TOKENS,
            terminal=True,
        )
        self.assertEqual(
            validated["n_terminal_logits_bytes"],
            validated["n_terminal_logits"] * 4,
        )

        with self.assertRaises(terminal.ExperimentError):
            terminal.validate_root(
                {**receipt, "n_terminal_logits_bytes": 1},
                action="root-save",
                root_id=terminal.TERMINAL_ROOT_ID,
                n_tokens=terminal.EXPECTED_TERMINAL_TOKENS,
                terminal=True,
            )
        with self.assertRaises(terminal.ExperimentError):
            terminal.validate_root(
                {**receipt, "terminal_logits_fnv64": "not-a-digest"},
                action="root-save",
                root_id=terminal.TERMINAL_ROOT_ID,
                n_tokens=terminal.EXPECTED_TERMINAL_TOKENS,
                terminal=True,
            )

    def test_root_erase_preserves_receipt_and_closes_device_state(self):
        saved = root_receipt(action="root-save", terminal_logits=True)
        erased = root_receipt(action="root-erase", terminal_logits=True)
        validated = terminal.validate_root(
            erased,
            action="root-erase",
            root_id=terminal.TERMINAL_ROOT_ID,
            n_tokens=terminal.EXPECTED_TERMINAL_TOKENS,
            expected=saved,
            terminal=True,
        )
        self.assertEqual(validated["n_device_bytes_after"], 0)
        self.assertEqual(validated["n_gpu_bytes_after"], 0)

    def test_harness_emits_terminal_flags_only_on_the_valid_actions(self):
        with mock.patch.object(
            harness,
            "request_json",
            return_value=({"action": "ok"}, 0.01),
        ) as request:
            harness.ram_root_action(
                action="root-save",
                root_id="terminal",
                storage="device",
                include_terminal_logits=True,
            )
            self.assertTrue(request.call_args.args[2]["include_terminal_logits"])

            harness.ram_root_action(
                action="root-restore",
                root_id="terminal",
                require_terminal_logits=True,
            )
            self.assertTrue(request.call_args.args[2]["require_terminal_logits"])

        with self.assertRaises(RuntimeError):
            harness.ram_root_action(
                action="root-erase",
                root_id="terminal",
                include_terminal_logits=True,
            )
        with self.assertRaises(RuntimeError):
            harness.ram_root_action(
                action="root-save",
                root_id="terminal",
                require_terminal_logits=True,
            )

    def test_consumption_marker_is_exclusive_and_declares_no_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "consumed.json"
            receipt = terminal.create_consumed_marker(marker, "a" * 40)
            value = json.loads(marker.read_text(encoding="utf-8"))
            self.assertFalse(value["retry_allowed"])
            self.assertEqual(value["id"], terminal.EXPERIMENT_ID)
            self.assertEqual(receipt["sha256"], harness.live_runtime.sha256_file(marker))
            with self.assertRaises(terminal.ExperimentError):
                terminal.create_consumed_marker(marker, "a" * 40)

    def test_source_orders_admission_and_fast_path_before_decode(self):
        source = (ROOT / "tools" / "server" / "server-context.cpp").read_text(
            encoding="utf-8"
        )
        admission = source.index(
            '"Terminal-logits continuation identity mismatch"'
        )
        capture_contract = source[
            source.index("if (task.params.neo3000_capture_terminal_logits) {") :
            admission
        ]
        self.assertIn("task.params.n_cmpl != 1", capture_contract)
        ordinary_prompt_processing = source.index(
            "if (slot.task->params.cache_prompt) {",
            admission,
        )
        fast_path = source.index(
            "if (slot.terminal_logits_pending_use) {",
            admission,
        )
        self.assertLess(admission, fast_path)
        self.assertLess(fast_path, ordinary_prompt_processing)

        capture = source.index(
            '"neo3000 terminal-logits boundary captured'
        )
        zero_output = source.index(
            "A zero-token request is used to materialize",
            capture,
        )
        self.assertLess(capture, zero_output)
        self.assertIn("terminal_logits.size()", source)

    def test_controller_promotes_689_to_690_without_storing_an_answer(self):
        source = Path(terminal.__file__).read_text(encoding="utf-8")
        self.assertIn("base_tokens = branch_tokens[:-1]", source)
        self.assertIn('promotion_payload["neo3000_capture_terminal_logits"] = True', source)
        self.assertIn("include_terminal_logits=True", source)
        self.assertIn("require_terminal_logits=True", source)
        self.assertIn("mismatched-terminal-negative", source)
        self.assertNotIn("sampled_token =", source)
        self.assertNotIn("answer_text =", source)
        evaluate_source = source.split("def evaluate(", 1)[1].split(
            "def static_audit(", 1
        )[0]
        self.assertNotIn("prepare_task_and_branch(", evaluate_source)

    def test_capture_and_live_use_bind_the_same_sampler_contract(self):
        tokens = [1, 2, 3]
        capture = terminal.completion_payload(
            tokens,
            cache_prompt=True,
            n_predict=0,
        )
        live = terminal.completion_payload(tokens, cache_prompt=True)
        self.assertEqual(capture["grammar"], live["grammar"])
        for key in ("temperature", "seed", "backend_sampling"):
            self.assertEqual(capture[key], live[key])


if __name__ == "__main__":
    unittest.main()
