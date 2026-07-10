#!/usr/bin/env python3
"""CPU-only safety and identity tests for the HoloState-v1 controller."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import holostate_live as holo
import neo_loop


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
            "accepted": True,
        }
        gate = holo.deterministic_group_gate([dict(base), dict(base)])
        self.assertTrue(gate["A1"]["exact"])

    def test_cached_progress_derives_fresh_delta_from_logical_minus_cache(self) -> None:
        fresh, method = holo.derive_fresh_prompt_tokens(8026, 7878, 8026)
        self.assertEqual((fresh, method), (148, "logical-minus-cache"))

    def test_uncached_progress_retains_reported_processed_count(self) -> None:
        fresh, method = holo.derive_fresh_prompt_tokens(8010, 0, 8010)
        self.assertEqual((fresh, method), (8010, "reported-processed"))


class StaticCapabilityTests(unittest.TestCase):
    def test_controller_has_only_declared_commands(self) -> None:
        parser = holo.build_parser()
        subparsers = next(action for action in parser._actions if action.dest == "command")
        self.assertEqual(
            set(subparsers.choices),
            {"start", "stop", "status", "warm", "branch", "list", "evict", "validate", "qualify-budget", "validate-v2"},
        )

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


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = holo.load_json(holo.EVALUATOR_PATH)
        cls.contract = holo.validate_holostate_contract(cls.evaluator["holostate_live_contract"])

    def test_budget_candidates_are_locked_and_ascending(self) -> None:
        self.assertEqual(
            self.contract["reasoning_budget"]["qualification_candidates"],
            [1024, 1280, 1536, 2048],
        )

    def test_768_is_only_prior_lower_bound_not_branch_budget(self) -> None:
        self.assertEqual(self.contract["prior_lower_bound_evidence"]["configured_max_tokens"], 768)
        tree = ast.parse(Path(holo.__file__).read_text(encoding="utf-8"))
        branch = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "branch_state")
        self.assertNotIn(768, [node.value for node in ast.walk(branch) if isinstance(node, ast.Constant)])

    def test_principal_quality_requirements_remain_coupled(self) -> None:
        sampling = self.contract["sampling"]
        self.assertEqual(sampling["reasoning_mode"], "auto")
        self.assertTrue(sampling["reasoning_required"])
        self.assertTrue(sampling["exact_final_required"])
        self.assertTrue(sampling["cache_reuse_required"])
        self.assertTrue(sampling["normal_generation_stop_required"])

    def test_selected_budget_requires_locked_candidate(self) -> None:
        unlocked = copy.deepcopy(self.contract)
        unlocked["reasoning_budget"]["selected_max_tokens"] = None
        with self.assertRaises(holo.NeoLoopError):
            holo.selected_reasoning_budget(unlocked)
        unlocked["reasoning_budget"]["selected_max_tokens"] = 1280
        self.assertEqual(holo.selected_reasoning_budget(unlocked), 1280)
        unlocked["reasoning_budget"]["selected_max_tokens"] = 999
        with self.assertRaises(holo.NeoLoopError):
            holo.selected_reasoning_budget(unlocked)

    def test_every_claim_bearing_contract_mutation_changes_hash(self) -> None:
        baseline = neo_loop.holostate_contract_hash(self.evaluator)
        mutations = [
            lambda c: c["branches"]["A1"].__setitem__("suffix", "changed prompt"),
            lambda c: c["branches"]["A1"].__setitem__("expected_final", "changed final"),
            lambda c: c["sampling"].__setitem__("reasoning_required", False),
            lambda c: c["sampling"].__setitem__("reasoning_mode", "disabled"),
            lambda c: c["reasoning_budget"].__setitem__("selected_max_tokens", 1024),
            lambda c: c["reasoning_budget"]["qualification_candidates"].append(4096),
            lambda c: c["fixed_interleaving_sequence"].reverse(),
            lambda c: c.__setitem__("extended_request_count", 19),
            lambda c: c["roots"]["A"]["sources"].append("AGENTS.md"),
            lambda c: c["binary_identity"].__setitem__("sha256", "0" * 64),
            lambda c: c["chat_template_identity"].__setitem__("required", False),
        ]
        for mutate in mutations:
            evaluator = copy.deepcopy(self.evaluator)
            mutate(evaluator["holostate_live_contract"])
            self.assertNotEqual(baseline, neo_loop.holostate_contract_hash(evaluator))

    def test_all_root_sources_are_protected_by_lock_generation(self) -> None:
        lock = neo_loop.make_lock(self.evaluator)
        expected = {
            source
            for root in self.contract["roots"].values()
            for source in root["sources"]
        }
        self.assertTrue(expected.issubset(lock["protected_file_hashes"]))

    def test_missing_complete_contract_hash_rejects_lock(self) -> None:
        lock = neo_loop.make_lock(self.evaluator)
        lock.pop("holostate_contract_sha256")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "lock.json"
            path.write_text(json.dumps(lock), encoding="utf-8")
            with mock.patch.object(neo_loop, "LOCK_PATH", path):
                with self.assertRaises(neo_loop.NeoLoopError):
                    neo_loop.verify_lock(self.evaluator)

    def test_unlocked_selected_budget_mutation_rejects_before_launch(self) -> None:
        lock = neo_loop.make_lock(self.evaluator)
        mutated = copy.deepcopy(self.evaluator)
        mutated["holostate_live_contract"]["reasoning_budget"]["selected_max_tokens"] = 1024
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "lock.json"
            path.write_text(json.dumps(lock), encoding="utf-8")
            with mock.patch.object(neo_loop, "LOCK_PATH", path):
                with self.assertRaises(neo_loop.NeoLoopError):
                    neo_loop.verify_lock(mutated)


class CompletionClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = holo.load_json(holo.EVALUATOR_PATH)["holostate_live_contract"]

    def result(
        self,
        *,
        completion: int = 100,
        configured: int = 128,
        exact: bool = True,
        reasoning: bool = True,
        cached: int = 80,
        fresh: int = 20,
        logical: int = 100,
        stop: bool = True,
        stop_type: str = "eos",
    ) -> dict:
        return {
            "configured_max_tokens": configured,
            "completion_tokens": completion,
            "logical_prompt_tokens": logical,
            "cached_prompt_tokens": cached,
            "fresh_prompt_tokens": fresh,
            "stop_event_received": stop,
            "stop_type": stop_type,
            "structure": {"exact_final": exact, "reasoning_present": reasoning},
        }

    def test_budget_exhaustion_is_not_wrong_final(self) -> None:
        exhausted = self.result(completion=128, exact=False, stop_type="limit")
        wrong = self.result(completion=90, exact=False)
        self.assertEqual(holo.classify_completion(exhausted, self.contract), "completion-budget-exhausted")
        self.assertEqual(holo.classify_completion(wrong, self.contract), "wrong-final-content")

    def test_abnormal_non_budget_stop_is_not_wrong_final(self) -> None:
        abnormal = self.result(completion=90, exact=False, stop=False)
        self.assertEqual(holo.classify_completion(abnormal, self.contract), "non-normal-stop")

    def test_reasoning_missing(self) -> None:
        self.assertEqual(
            holo.classify_completion(self.result(reasoning=False), self.contract),
            "reasoning-missing",
        )

    def test_reuse_failed_when_cache_absent_or_all_fresh(self) -> None:
        self.assertEqual(holo.classify_completion(self.result(cached=0), self.contract), "reuse-failed")
        self.assertEqual(holo.classify_completion(self.result(fresh=100), self.contract), "reuse-failed")

    def test_accepted_requires_normal_stop_quality_and_reuse(self) -> None:
        item = self.result()
        self.assertEqual(holo.classify_completion(item, self.contract), "accepted")
        self.assertTrue(item["normal_generation_stop"])


class OneShotWorkflowTests(unittest.TestCase):
    def test_qualification_stops_at_first_accepted_budget(self) -> None:
        called: list[int] = []

        def run(budget: int) -> dict:
            called.append(budget)
            return {
                "configured_max_tokens": budget,
                "finish_classification": "accepted" if budget == 1280 else "completion-budget-exhausted",
                "accepted": budget == 1280,
            }

        results, selected = holo.first_accepted_budget([1024, 1280, 1536, 2048], run)
        self.assertEqual(called, [1024, 1280])
        self.assertEqual(len(results), 2)
        self.assertEqual(selected, 1280)

    def test_qualification_stops_after_2048_if_none_pass(self) -> None:
        called: list[int] = []

        def run(budget: int) -> dict:
            called.append(budget)
            return {"finish_classification": "completion-budget-exhausted", "accepted": False}

        _, selected = holo.first_accepted_budget([1024, 1280, 1536, 2048], run)
        self.assertEqual(called, [1024, 1280, 1536, 2048])
        self.assertIsNone(selected)

    def test_qualification_cannot_claim_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "reasoning-budget-qualification-v1.json"
            with mock.patch.object(holo, "STATE_ROOT", root):
                holo.claim_runtime_json_once(marker, {"status": "running"})
                with self.assertRaises(holo.NeoLoopError):
                    holo.claim_runtime_json_once(marker, {"status": "running"})

    def test_validation_v2_cannot_run_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "validation-attempt-v2.json"
            marker.write_text("{}", encoding="utf-8")
            with mock.patch.object(holo, "STATE_ROOT", root), mock.patch.object(holo, "V2_ATTEMPT_PATH", marker), mock.patch.object(
                holo, "V2_RESULT_PATH", root / "validation-result-v2.json"
            ):
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_validation_v2(SimpleNamespace(extended_requests=20, binary="x", model="y"))

    def test_versioned_paths_do_not_alias_v1_evidence(self) -> None:
        self.assertEqual(len({holo.ATTEMPT_PATH, holo.RESULT_PATH, holo.QUALIFICATION_PATH, holo.V2_ATTEMPT_PATH, holo.V2_RESULT_PATH}), 5)

    def test_preserved_v1_evidence_is_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp) / "attempt.json"
            result = Path(temp) / "result.json"
            attempt.write_bytes(b"attempt bytes")
            result.write_bytes(b"result bytes")
            attempt_hash = hashlib.sha256(attempt.read_bytes()).hexdigest().upper()
            result_hash = hashlib.sha256(result.read_bytes()).hexdigest().upper()
            with mock.patch.object(holo, "ATTEMPT_PATH", attempt), mock.patch.object(holo, "RESULT_PATH", result), mock.patch.object(
                holo, "PRIOR_V1_ATTEMPT_SHA256", attempt_hash
            ), mock.patch.object(holo, "PRIOR_V1_RESULT_SHA256", result_hash):
                before = (attempt.read_bytes(), result.read_bytes())
                evidence = holo.preserved_v1_evidence()
                after = (attempt.read_bytes(), result.read_bytes())
            self.assertEqual(before, after)
            self.assertEqual(evidence["attempt_sha256"], attempt_hash)

    def test_failed_branch_payload_is_checkpointed_with_hashes_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "validation-result-v2.json"
            branch = {
                "finish_classification": "completion-budget-exhausted",
                "configured_max_tokens": 1024,
                "completion_tokens": 1024,
                "raw_output_sha256": "A" * 64,
                "cleaned_greedy_token_sha256": "B" * 64,
                "reasoning_sha256": "C" * 64,
                "final_content_sha256": "D" * 64,
                "cached_prompt_tokens": 7000,
                "fresh_prompt_tokens": 148,
                "prompt_ms": 1000.0,
                "decode_tps": 12.0,
                "total_seconds": 90.0,
            }
            payload = {"branch_results": [branch]}
            with mock.patch.object(holo, "STATE_ROOT", root):
                holo.checkpoint_result(path, payload)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["branch_results"][0], branch)


class TimeoutTests(unittest.TestCase):
    def test_guarded_timeout_settles_worker_before_returning(self) -> None:
        sidecar = object.__new__(holo.LiveSidecar)
        sidecar.require_active = mock.Mock()
        sidecar.process = None
        started = time.monotonic()
        with self.assertRaises(holo.NeoLoopError):
            sidecar.guarded("slow", lambda: time.sleep(0.25), timeout=0.01)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.2)
        self.assertLess(elapsed, 0.6)


class CleanupGateTests(unittest.TestCase):
    def valid_cleanup(self) -> dict:
        return {
            "process_stopped": True,
            "port_free": True,
            "runtime_removed": True,
            "wddm": {"telemetry_failures": []},
            "retirement_samples": [
                {"available": False, "bytes": None} for _ in range(5)
            ],
            "stable_after": {"healthy": True, "listener_pids": [31188]},
        }

    def test_complete_cleanup_passes(self) -> None:
        self.assertTrue(holo.cleanup_integrity(self.valid_cleanup(), {31188})["passed"])

    def test_incomplete_cleanup_rejects_acceptance(self) -> None:
        cleanup = self.valid_cleanup()
        cleanup["runtime_removed"] = False
        cleanup["retirement_samples"][0] = {"available": True, "bytes": 1}
        gate = holo.cleanup_integrity(cleanup, {31188})
        self.assertFalse(gate["passed"])
        self.assertIn("sidecar-runtime-not-removed", gate["reasons"])
        self.assertIn("WDDM-retirement-not-empty", gate["reasons"])


if __name__ == "__main__":
    unittest.main()
