#!/usr/bin/env python3
"""CPU-only safety and identity tests for the HoloState-v1 controller."""

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import holostate_live as holo


class RuntimePathTests(unittest.TestCase):
    def test_runtime_path_rejects_escape(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.require_runtime_path(holo.ROOT / "TASKS.md")

    def test_registry_declares_metadata_only(self) -> None:
        registry = holo.default_registry()
        self.assertTrue(registry["metadata_only"])
        self.assertIsNone(registry["sidecar"])
        self.assertEqual(registry["states"], {})


class IdentityTests(unittest.TestCase):
    def test_changed_prefix_produces_changed_identity(self) -> None:
        sidecar = {
            "model": {"sha256": holo.EXPECTED_MODEL_SHA256},
            "binary": {"sha256": holo.EXPECTED_BINARY_SHA256, "runtime_version": holo.EXPECTED_RUNTIME_VERSION},
            "chat_template_sha256": "TEMPLATE",
        }
        left, _ = holo.state_identity("A", "A" * 64, "B" * 64, 4096, sidecar)
        right, _ = holo.state_identity("A", "C" * 64, "B" * 64, 4096, sidecar)
        self.assertNotEqual(left, right)

    def test_identity_is_not_affected_by_display_name(self) -> None:
        sidecar = {
            "model": {"sha256": holo.EXPECTED_MODEL_SHA256},
            "binary": {"sha256": holo.EXPECTED_BINARY_SHA256, "runtime_version": holo.EXPECTED_RUNTIME_VERSION},
            "chat_template_sha256": "TEMPLATE",
        }
        left, _ = holo.state_identity("A", "A" * 64, "B" * 64, 4096, sidecar)
        right, _ = holo.state_identity("renamed", "A" * 64, "B" * 64, 4096, sidecar)
        self.assertEqual(left, right)


class EvictionTests(unittest.TestCase):
    def test_lowest_reuse_yield_then_oldest_is_selected(self) -> None:
        states = {
            "high": {"live": True, "reuse_count": 20, "estimated_bytes": 100, "last_use_timestamp": "2026-07-10T02:00:00Z"},
            "low-new": {"live": True, "reuse_count": 1, "estimated_bytes": 100, "last_use_timestamp": "2026-07-10T03:00:00Z"},
            "low-old": {"live": True, "reuse_count": 1, "estimated_bytes": 100, "last_use_timestamp": "2026-07-10T01:00:00Z"},
        }
        self.assertEqual(holo.select_eviction_candidate(states), "low-old")

    def test_non_live_history_is_not_selected(self) -> None:
        states = {"old": {"live": False, "reuse_count": 0, "estimated_bytes": 1, "last_use_timestamp": ""}}
        self.assertIsNone(holo.select_eviction_candidate(states))

    def test_evict_refuses_active_request(self) -> None:
        registry = holo.default_registry()
        registry["active_request"] = {"state_id": "x"}
        with mock.patch.object(holo, "load_registry", return_value=registry):
            with self.assertRaises(holo.NeoLoopError):
                holo.command_evict(SimpleNamespace(state=None))


class StopSafetyTests(unittest.TestCase):
    def test_stop_refuses_registered_stable_pid(self) -> None:
        registry = holo.default_registry()
        registry["sidecar"] = {"pid": 42, "stable_pids": [42]}
        with mock.patch.object(holo, "listener_pids", return_value={42}):
            allowed, reason = holo.stop_authorized(registry)
        self.assertFalse(allowed)
        self.assertIn("stable", reason)

    def test_stop_requires_exact_live_identity(self) -> None:
        registry = holo.default_registry()
        registry["sidecar"] = {"pid": 43, "stable_pids": [42]}
        with mock.patch.object(holo, "listener_pids", side_effect=[{42}, {43}]), mock.patch.object(
            holo, "status_from_registry", return_value={"live": False}
        ):
            allowed, _ = holo.stop_authorized(registry)
        self.assertFalse(allowed)


class OutputTests(unittest.TestCase):
    def test_final_structure_separates_reasoning_and_exact_final(self) -> None:
        result = holo.parse_final_structure("reasoning text\nHOLOSTATE A1 EXACT", "HOLOSTATE A1 EXACT")
        self.assertTrue(result["exact_final"])
        self.assertTrue(result["reasoning_present"])
        self.assertEqual(len(result["reasoning_sha256"]), 64)

    def test_deterministic_group_gate_requires_one_token_and_reasoning_hash(self) -> None:
        base = {
            "branch_name": "A1",
            "cleaned_greedy_token_sha256": "TOK",
            "structure": {"reasoning_sha256": "WHY", "final_content_sha256": "FINAL", "exact_final": True},
            "catalytic": True,
        }
        gate = holo.deterministic_group_gate([dict(base), dict(base)])
        self.assertTrue(gate["A1"]["exact"])


class StaticCapabilityTests(unittest.TestCase):
    def test_controller_has_only_declared_commands(self) -> None:
        parser = holo.build_parser()
        subparsers = next(action for action in parser._actions if action.dest == "command")
        self.assertEqual(set(subparsers.choices), {"start", "stop", "status", "warm", "branch", "list", "evict", "validate"})

    def test_subprocess_git_calls_are_read_only(self) -> None:
        tree = ast.parse(Path(holo.__file__).read_text(encoding="utf-8"))
        forbidden = {"commit", "push", "merge", "rebase", "checkout", "switch", "reset", "clean", "add"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "git_read":
                continue
            literal_args = [arg.value for arg in node.args[1:] if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
            self.assertFalse(forbidden.intersection(literal_args), literal_args)

    def test_launch_uses_proven_cache_controls_without_cache_reuse(self) -> None:
        source = Path(holo.__file__).read_text(encoding="utf-8")
        for flag in ("--cache-prompt", "--ctx-checkpoints", "--checkpoint-min-step", "--cache-ram", "--cache-idle-slots"):
            self.assertIn(f'"{flag}"', source)
        self.assertNotIn('"--cache-reuse"', source)

    def test_validation_guard_refuses_second_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "attempt.json"
            marker.write_text(json.dumps({"status": "complete"}), encoding="utf-8")
            with mock.patch.object(holo, "ATTEMPT_PATH", marker):
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_validation(SimpleNamespace(extended_requests=0, binary="x", model="y"))


if __name__ == "__main__":
    unittest.main()
