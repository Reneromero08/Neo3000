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
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import holostate_live as holo
import baseline_harness as harness
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

    def test_catalytic_runtime_path_rejects_resolved_escape(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.require_catalytic_runtime_path(holo.ROOT / "TASKS.md")

    def test_catalytic_atomic_writer_stays_inside_declared_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            holo, "CATALYTIC_STATE_ROOT", Path(temp)
        ):
            path = Path(temp) / "attempt-v1.json"
            holo.claim_catalytic_runtime_json_once(path, {"owner": "test"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"owner": "test"})
            with self.assertRaises(holo.NeoLoopError):
                holo.claim_catalytic_runtime_json_once(path, {"owner": "other"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"owner": "test"})

    def test_catalytic_claim_removes_owned_partial_on_base_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            holo, "CATALYTIC_STATE_ROOT", Path(temp)
        ):
            path = Path(temp) / "attempt-v2.json"
            with mock.patch.object(holo.os, "fsync", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    holo.claim_catalytic_runtime_json_once(path, {"status": "running"})
            self.assertFalse(path.exists())

    def test_preclaim_memory_ledger_is_bounded_and_has_no_file(self) -> None:
        ledger = holo.BoundedInMemoryLedger(max_bytes=2048, max_records=2)
        record = {"reasoning_fragment_length": 5, "reasoning_fragment_sha256": "A" * 64}
        ledger.recorder("warm-A", 1)(record)
        snapshot = ledger.snapshot(include_records=True)
        self.assertTrue(snapshot["within_limits"])
        self.assertEqual(snapshot["record_count"], 1)
        self.assertNotIn("reasoning_text", json.dumps(snapshot))
        ledger.recorder("canary", 2)(record)
        with self.assertRaises(holo.NeoLoopError):
            ledger.recorder("extra", 3)(record)


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
            {
                "start", "stop", "status", "warm", "branch", "list", "evict",
                "audit-catalytic-swarm-0", "audit-catalytic-swarm-0-v2",
            },
        )

    def test_catalytic_swarm_v1_command_is_hard_retired(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.command_audit_catalytic_swarm_0(
                SimpleNamespace(binary="x", model="y")
            )

    def test_worker_protocol_v2_command_is_hard_retired(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.command_audit_worker_protocol_v2(SimpleNamespace(binary="x", model="y"))

    def test_worker_protocol_v3_command_is_hard_retired(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.command_audit_worker_protocol_v3(SimpleNamespace(binary="x", model="y"))

    def test_worker_protocol_v4_command_is_hard_retired(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.command_audit_worker_protocol_v4(SimpleNamespace(binary="x", model="y"))

    def test_exact_gbnf_literal_is_stable_and_escaped(self) -> None:
        content = '{"kind":"proposal","claim":"SWARM CANARY"}'
        grammar = holo.exact_gbnf_literal(content)
        self.assertEqual(grammar, "root ::= " + json.dumps(content, ensure_ascii=False))
        lane = {
            "thinking_mode": "disabled",
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0.0,
            "max_tokens": 64,
            "seed": 0,
            "grammar": grammar,
        }
        protocol = holo.load_json(holo.EVALUATOR_PATH)["holostate_worker_protocol_v4"]
        payload = holo.build_worker_chat_payload(protocol, "root", "assignment", lane)
        self.assertEqual(payload["grammar"], grammar)
        self.assertEqual(payload["max_tokens"], 64)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})

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

    def test_lock_rejects_omitted_or_injected_protected_hash_path(self) -> None:
        baseline = neo_loop.make_lock(self.evaluator)
        required_path = "scripts/holostate_live.py"
        self.assertIn(required_path, baseline["protected_file_hashes"])
        mutations = []
        omitted = copy.deepcopy(baseline)
        omitted["protected_file_hashes"].pop(required_path)
        mutations.append(omitted)
        injected = copy.deepcopy(baseline)
        injected["protected_file_hashes"]["injected/extra.py"] = "0" * 64
        mutations.append(injected)
        for lock in mutations:
            with self.subTest(paths=sorted(lock["protected_file_hashes"])):
                with mock.patch.object(neo_loop, "load_json", return_value=lock):
                    with self.assertRaisesRegex(
                        neo_loop.NeoLoopError, "protected hash surface"
                    ):
                        neo_loop.verify_lock(self.evaluator)

    def test_lock_rejects_reauthored_duplicated_evaluator_lists(self) -> None:
        baseline = neo_loop.make_lock(self.evaluator)
        for key in (
            "model_identity",
            "stable_launch",
            "candidate_launch",
            "protected_paths",
            "candidate_editable_paths",
            "controller_files",
        ):
            with self.subTest(key=key):
                lock = copy.deepcopy(baseline)
                if isinstance(lock[key], list):
                    lock[key] = list(lock[key]) + ["injected"]
                else:
                    lock[key] = {**lock[key], "injected": True}
                with mock.patch.object(neo_loop, "load_json", return_value=lock):
                    with self.assertRaisesRegex(neo_loop.NeoLoopError, key):
                        neo_loop.verify_lock(self.evaluator)

    def test_lock_generation_and_verification_reject_missing_protected_file(self) -> None:
        missing = "injected/definitely-missing.py"
        evaluator = copy.deepcopy(self.evaluator)
        evaluator["protected_paths"]["files"].append(missing)
        with self.assertRaisesRegex(neo_loop.NeoLoopError, "missing"):
            neo_loop.make_lock(evaluator)

        lock = neo_loop.make_lock(self.evaluator)
        lock["protected_paths"] = evaluator["protected_paths"]["files"]
        lock["protected_file_hashes"][missing] = "MISSING"
        with mock.patch.object(neo_loop, "load_json", return_value=lock):
            with self.assertRaisesRegex(neo_loop.NeoLoopError, "missing"):
                neo_loop.verify_lock(evaluator)

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


class WorkerProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = holo.load_json(holo.EVALUATOR_PATH)
        cls.protocol = holo.validate_worker_protocol(
            cls.evaluator["holostate_worker_protocol_v1"]
        )

    def test_reference_envelope_hash_is_exact(self) -> None:
        envelope = self.protocol["reference_envelope"]
        self.assertEqual(envelope["text"], holo.WORKER_REFERENCE_ENVELOPE)
        self.assertEqual(
            hashlib.sha256(envelope["text"].encode("utf-8")).hexdigest().upper(),
            envelope["sha256"],
        )

    def test_root_and_assignment_are_separate_messages(self) -> None:
        lane = self.protocol["lanes"]["F"]
        assignment = lane["assignments"]["A1"]
        payload = holo.build_worker_chat_payload(
            self.protocol, "SYSTEM ROOT", assignment["user_message"], lane
        )
        self.assertEqual([item["role"] for item in payload["messages"]], ["system", "user"])
        self.assertEqual(payload["messages"][0]["content"], "SYSTEM ROOT")
        self.assertEqual(payload["messages"][1]["content"], assignment["user_message"])
        self.assertTrue(payload["return_tokens"])
        self.assertTrue(payload["return_progress"])
        self.assertTrue(payload["verbose"])

    def test_fast_lane_always_disables_thinking(self) -> None:
        lane = self.protocol["lanes"]["F"]
        payload = holo.build_worker_chat_payload(self.protocol, "SYSTEM", "USER", lane)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(payload["max_tokens"], 64)

    def test_deep_lane_retains_reasoning_auto_at_768(self) -> None:
        lane = self.protocol["lanes"]["D"]
        payload = holo.build_worker_chat_payload(self.protocol, "SYSTEM", "USER", lane)
        self.assertNotIn("chat_template_kwargs", payload)
        self.assertEqual(payload["max_tokens"], 768)
        self.assertNotIn("reasoning steps", lane["assignments"]["A1"]["user_message"])

    def test_chat_stream_extracts_exact_server_token_array(self) -> None:
        self.assertEqual(
            harness.extract_generated_token_ids({"__verbose": {"tokens": [1, "2", 3]}}),
            [1, 2, 3],
        )

    def measurement(self, *, content: str, reasoning: str) -> SimpleNamespace:
        return SimpleNamespace(
            prompt_tokens=100,
            cached_prompt_tokens=80,
            completion_tokens=3,
            reported_tokens_per_second=20.0,
            total_time_s=1.0,
            content=content,
            reasoning_content=reasoning,
            tool_calls=[],
            finish_reason="stop",
            time_to_first_event_s=0.1,
            time_to_first_token_s=0.2,
            time_to_first_content_s=0.3,
            timings={"prompt_ms": 100.0, "prompt_per_second": 1000.0},
            http_status=200,
            event_count=5,
            generated_token_ids=[1, 2, 3],
            generated_token_count=3,
            nonempty_token_array_event_count=3,
            empty_token_array_event_count=1,
            token_merge_modes={"initial": 1, "delta-append": 2, "ignored-empty": 1},
            completion_token_count_match=True,
            generated_token_sha256=harness.token_array_sha256([1, 2, 3]),
            prompt_progress=[{"total": 100, "cache": 80, "processed": 100, "time_ms": 10.0}],
        )

    def test_reasoning_and_content_are_captured_separately(self) -> None:
        identity = {
            "system_message_characters": 6,
            "system_message_sha256": "A" * 64,
            "reference_envelope_sha256": "B" * 64,
        }
        with mock.patch.object(holo, "tokenize", return_value=[1, 2, 3]):
            result = holo.compact_worker_measurement(
                self.measurement(content="HOLOSTATE FAST A", reasoning="opaque payload"),
                root_name="A",
                assignment_name="A1",
                lane_name="F",
                expected_content="HOLOSTATE FAST A",
                system_identity=identity,
                user_message="Return exactly: HOLOSTATE FAST A",
                configured_max_tokens=64,
            )
        self.assertEqual(result["assistant_content"]["text"], "HOLOSTATE FAST A")
        self.assertTrue(result["reasoning_content"]["present"])
        self.assertEqual(result["reasoning_content"]["characters"], len("opaque payload"))
        self.assertNotIn("text", result["reasoning_content"])
        self.assertNotIn("first_256", result["reasoning_content"])
        self.assertTrue(result["completion_token_ids"]["complete"])
        self.assertNotIn("ids", result["completion_token_ids"])
        self.assertEqual(result["reported_processed_prompt_tokens"], 100)

    def test_complete_token_array_is_retained_only_when_reasoning_is_empty(self) -> None:
        identity = {
            "system_message_characters": 6,
            "system_message_sha256": "A" * 64,
            "reference_envelope_sha256": "B" * 64,
        }
        with mock.patch.object(holo, "tokenize", return_value=[4, 5]):
            result = holo.compact_worker_measurement(
                self.measurement(content="HOLOSTATE FAST A", reasoning=""),
                root_name="A",
                assignment_name="A1",
                lane_name="F",
                expected_content="HOLOSTATE FAST A",
                system_identity=identity,
                user_message="Return exactly: HOLOSTATE FAST A",
                configured_max_tokens=64,
            )
        self.assertEqual(result["completion_token_ids"]["ids"], [1, 2, 3])

    def worker_result(self, *, content: str, reasoning: bool, cached: int = 80) -> dict:
        return {
            "assistant_content": {"text": content},
            "reasoning_content": {"present": reasoning},
            "tool_calls": [],
            "expected_content": content,
            "http_status": 200,
            "finish_reason": "stop",
            "prompt_token_identity_matches": True,
            "completion_token_ids": {
                "complete": True,
                "count": 3,
                "completion_token_count_match": True,
                "sha256": "C" * 64,
            },
            "logical_prompt_tokens": 100,
            "cached_prompt_tokens": cached,
            "fresh_prompt_tokens": 100 - cached,
        }

    def test_fast_lane_requires_empty_reasoning_content(self) -> None:
        item = self.worker_result(content="HOLOSTATE FAST A", reasoning=True)
        self.assertEqual(
            holo.classify_worker_measurement(item, self.protocol["lanes"]["F"]),
            "unexpected-reasoning-content",
        )

    def test_visible_content_match_is_byte_exact(self) -> None:
        item = self.worker_result(content=" HOLOSTATE FAST A", reasoning=False)
        item["expected_content"] = "HOLOSTATE FAST A"
        self.assertEqual(
            holo.classify_worker_measurement(item, self.protocol["lanes"]["F"]),
            "wrong-assistant-content",
        )

    def test_deep_lane_requires_nonempty_reasoning_content(self) -> None:
        item = self.worker_result(content="HOLOSTATE DEEP A", reasoning=False)
        self.assertEqual(
            holo.classify_worker_measurement(item, self.protocol["lanes"]["D"]),
            "reasoning-content-missing",
        )

    def test_cache_reuse_remains_mandatory(self) -> None:
        item = self.worker_result(content="HOLOSTATE FAST A", reasoning=False, cached=0)
        self.assertEqual(
            holo.classify_worker_measurement(item, self.protocol["lanes"]["F"]),
            "reuse-failed",
        )

    def test_missing_prompt_usage_is_instrumentation_not_capability_reject(self) -> None:
        item = self.worker_result(content="HOLOSTATE FAST A", reasoning=False)
        item["logical_prompt_tokens"] = None
        classification = holo.classify_worker_measurement(item, self.protocol["lanes"]["F"])
        self.assertEqual(classification, "prompt-usage-missing")
        self.assertTrue(holo.is_worker_instrumentation_failure(classification))

    def test_unexpected_tool_calls_reject_exact_content_gate(self) -> None:
        item = self.worker_result(content="HOLOSTATE FAST A", reasoning=False)
        item["tool_calls"] = [{"function": {"name": "unexpected"}}]
        self.assertEqual(
            holo.classify_worker_measurement(item, self.protocol["lanes"]["F"]),
            "unexpected-tool-calls",
        )

    def test_complete_generated_token_evidence_is_mandatory(self) -> None:
        item = self.worker_result(content="HOLOSTATE FAST A", reasoning=False)
        item["completion_token_ids"]["complete"] = False
        self.assertEqual(
            holo.classify_worker_measurement(item, self.protocol["lanes"]["F"]),
            "completion-token-evidence-missing",
        )

    def test_fast_lane_failure_stops_the_audit_path(self) -> None:
        with self.assertRaises(holo.NeoLoopError):
            holo.require_fast_worker_acceptance({
                "assignment_name": "A1",
                "accepted": False,
                "finish_classification": "wrong-assistant-content",
            })

    def test_deep_failure_does_not_erase_fast_availability(self) -> None:
        state = holo.worker_availability_state("reviewable-accept", safety_passed=True)
        self.assertEqual(state["PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE"], "UNLOCKED")
        self.assertEqual(state["PROCESS_LOCAL_HOLOSTATE_AVAILABLE"], "LOCKED")
        self.assertEqual(state["RESTART_PERSISTENT_HOLOSTATE_AVAILABLE"], "LOCKED")

    def test_A_and_B_identities_cannot_cross_select(self) -> None:
        def item(name: str, root: str, content: str, system_hash: str) -> dict:
            digest = hashlib.sha256(content.encode()).hexdigest().upper()
            return {
                "assignment_name": name,
                "root_name": root,
                "accepted": True,
                "assistant_content": {"text": content, "sha256": digest},
                "assistant_content_token_ids_sha256": digest,
                "completion_token_ids": {"complete": True, "sha256": digest},
                "system_message_sha256": system_hash,
            }

        results = [
            item("A1", "B", "HOLOSTATE FAST A", "A" * 64),
            item("A2", "A", "HOLOSTATE FAST A", "A" * 64),
            item("B1", "B", "HOLOSTATE FAST B", "B" * 64),
            item("B2", "B", "HOLOSTATE FAST B", "B" * 64),
        ]
        gate = holo.fast_worker_determinism_gate(results, self.protocol)
        self.assertFalse(gate["passed"])
        self.assertIn("A1-root-cross-selection", gate["reasons"])

    def test_every_worker_protocol_mutation_changes_complete_hash(self) -> None:
        baseline = neo_loop.holostate_worker_protocol_hash(self.evaluator)
        for path, value in [
            (("reference_envelope", "text"), "changed"),
            (("lanes", "F", "max_tokens"), 65),
            (("lanes", "D", "max_tokens"), 769),
            (("one_shot", "retry_allowed"), True),
        ]:
            evaluator = copy.deepcopy(self.evaluator)
            target = evaluator["holostate_worker_protocol_v1"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertNotEqual(baseline, neo_loop.holostate_worker_protocol_hash(evaluator))

    def test_worker_sources_and_complete_hash_are_lock_protected(self) -> None:
        lock = neo_loop.make_lock(self.evaluator)
        expected_sources = {
            source
            for root in self.protocol["roots"].values()
            for source in root["sources"]
        }
        self.assertTrue(expected_sources.issubset(lock["protected_file_hashes"]))
        self.assertEqual(
            lock["holostate_worker_protocol_sha256"],
            neo_loop.holostate_worker_protocol_hash(self.evaluator),
        )

    def test_worker_evidence_is_complete_object_hash_protected(self) -> None:
        baseline = neo_loop.holostate_worker_protocol_evidence_hash(self.evaluator)
        evaluator = copy.deepcopy(self.evaluator)
        evaluator["holostate_worker_protocol_v1_evidence"]["fast_verdict"] = "inconclusive"
        self.assertNotEqual(
            baseline,
            neo_loop.holostate_worker_protocol_evidence_hash(evaluator),
        )


class WorkerProtocolV2ParserTests(unittest.TestCase):
    def merge_sequence(self, incoming: list[list[int] | None]) -> tuple[list[int], list[str]]:
        accumulated: list[int] = []
        modes: list[str] = []
        for item in incoming:
            accumulated, mode = harness.merge_generated_token_ids(accumulated, item)
            modes.append(mode)
        return accumulated, modes

    def test_delta_arrays_accumulate_and_final_empty_is_ignored(self) -> None:
        tokens, modes = self.merge_sequence([[11], [12], [], [13]])
        self.assertEqual(tokens, [11, 12, 13])
        self.assertEqual(modes[-2], "ignored-empty")

    def test_cumulative_arrays_replace_only_with_extensions(self) -> None:
        tokens, modes = self.merge_sequence([[11], [11, 12], [11, 12, 13], []])
        self.assertEqual(tokens, [11, 12, 13])
        self.assertEqual(modes[1:3], ["cumulative-extension", "cumulative-extension"])

    def test_duplicate_or_shorter_cumulative_snapshot_does_not_duplicate(self) -> None:
        tokens, modes = self.merge_sequence([[11, 12], [11], [11, 12]])
        self.assertEqual(tokens, [11, 12])
        self.assertEqual(modes[1], "duplicate-or-shorter-snapshot")
        self.assertEqual(modes[2], "cumulative-extension")

    def test_multi_token_delta_arrays_append(self) -> None:
        tokens, _ = self.merge_sequence([[11, 12], [13, 14], []])
        self.assertEqual(tokens, [11, 12, 13, 14])

    def test_absent_array_preserves_evidence(self) -> None:
        tokens, mode = harness.merge_generated_token_ids([11, 12], None)
        self.assertEqual(tokens, [11, 12])
        self.assertEqual(mode, "absent")

    def test_ambiguous_repeated_delta_cannot_silently_pass_completion_count(self) -> None:
        tokens, _ = self.merge_sequence([[42], [42]])
        self.assertEqual(tokens, [42])
        self.assertNotEqual(len(tokens), 2)

    def test_malformed_token_array_rejects(self) -> None:
        with self.assertRaises(harness.HarnessError):
            harness.extract_generated_token_ids({"__verbose": {"tokens": [11, {"bad": 12}]}})
        with self.assertRaises(harness.HarnessError):
            harness.extract_generated_token_ids({"__verbose": {"tokens": "11"}})
        with self.assertRaises(harness.HarnessError):
            harness.extract_generated_token_ids({"__verbose": {"tokens": [True]}})
        with self.assertRaises(harness.HarnessError):
            harness.extract_generated_token_ids({"__verbose": {"tokens": [11.5]}})

    def test_stream_ledger_metadata_never_contains_reasoning_text(self) -> None:
        secret = "hidden reasoning must not persist"
        record = harness.stream_ledger_record(
            {
                "__verbose": {"tokens": [11]},
                "usage": {"unexpected_text": secret, "completion_tokens": 1},
                "prompt_progress": {"unexpected_text": secret, "processed": 1},
                "choices": [{"delta": {"content": "visible", "reasoning_content": secret}}],
            },
            event_index=1,
            request_label="test",
            event_token_ids=[11],
            merge_mode="initial",
        )
        encoded = json.dumps(record, sort_keys=True)
        self.assertNotIn(secret, encoded)
        self.assertEqual(record["reasoning_fragment_length"], len(secret))
        self.assertEqual(len(record["reasoning_fragment_sha256"]), 64)
        self.assertTrue(record["usage"]["unexpected_text"]["text_redacted"])

    def test_bounded_ledger_rejects_before_crossing_record_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(holo, "STATE_ROOT", root):
                ledger = holo.BoundedStreamLedger(root / "stream.jsonl", max_bytes=4096, max_records=1)
                recorder = ledger.recorder("canary", 1)
                recorder({"event_index": 1})
                with self.assertRaises(holo.NeoLoopError):
                    recorder({"event_index": 2})
                ledger.close()
            self.assertEqual(ledger.record_count, 1)
            self.assertEqual(ledger.failure, "stream-ledger-ceiling-exceeded")


class WorkerProtocolV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = holo.load_json(holo.EVALUATOR_PATH)
        cls.protocol = holo.validate_worker_protocol_v2(
            cls.evaluator["holostate_worker_protocol_v2"]
        )

    def measurement(self, *, count_match: bool = True) -> SimpleNamespace:
        token_ids = [11, 12, 13]
        return SimpleNamespace(
            prompt_tokens=10,
            cached_prompt_tokens=0,
            completion_tokens=3,
            reported_tokens_per_second=20.0,
            total_time_s=1.0,
            content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[],
            finish_reason="stop",
            time_to_first_event_s=0.1,
            time_to_first_token_s=0.2,
            time_to_first_content_s=0.3,
            timings={"prompt_ms": 100.0, "prompt_per_second": 100.0},
            http_status=200,
            event_count=4,
            generated_token_ids=token_ids,
            generated_token_count=3,
            nonempty_token_array_event_count=3,
            empty_token_array_event_count=1,
            token_merge_modes={"initial": 1, "delta-append": 2, "ignored-empty": 1},
            completion_token_count_match=count_match,
            generated_token_sha256=harness.token_array_sha256(token_ids),
            prompt_progress=[],
        )

    def run_canary(self, measurement: SimpleNamespace) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(holo, "STATE_ROOT", root):
                ledger = holo.BoundedStreamLedger(root / "stream.jsonl", max_bytes=8192, max_records=10)

                def fake_stream(*args, **kwargs):
                    kwargs["event_recorder"]({
                        "event_index": 1,
                        "request_label": "parser-canary",
                        "token_array_length": 1,
                        "token_array_sha256": "A" * 64,
                        "token_array_empty": False,
                        "merge_mode": "initial",
                        "content_fragment_length": 0,
                        "content_fragment_sha256": "B" * 64,
                        "reasoning_fragment_length": 0,
                        "reasoning_fragment_sha256": "C" * 64,
                        "tool_fragment_present": False,
                    })
                    return measurement

                with mock.patch.object(holo, "render_messages", return_value="rendered"), mock.patch.object(
                    holo, "tokenize", return_value=list(range(10))
                ), mock.patch.object(holo, "stream_completion", side_effect=fake_stream):
                    result = holo.run_parser_canary(self.protocol, ledger, request_sequence_index=1)
                ledger.close()
                return result

    def test_parser_canary_passes_only_with_complete_token_evidence(self) -> None:
        result = self.run_canary(self.measurement())
        self.assertTrue(result["accepted"])
        self.assertTrue(result["completion_token_count_match"])
        self.assertEqual(result["generated_token_count"], 3)

    def test_completion_count_mismatch_is_instrumentation_failure(self) -> None:
        result = self.run_canary(self.measurement(count_match=False))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["finish_classification"], "stream-token-count-mismatch")

    def test_failed_canary_does_not_persist_reasoning_token_ids(self) -> None:
        measurement = self.measurement()
        measurement.reasoning_content = "hidden"
        result = self.run_canary(measurement)
        self.assertFalse(result["accepted"])
        self.assertIsNone(result["generated_token_ids"])
        self.assertNotIn("text", result["reasoning_content"])

    def test_v2_assignments_are_distinct_with_repeat_only_sequence(self) -> None:
        assignments = self.protocol["lanes"]["F"]["assignments"]
        self.assertNotEqual(assignments["A1"]["expected_content"], assignments["A2"]["expected_content"])
        self.assertNotEqual(assignments["B1"]["expected_content"], assignments["B2"]["expected_content"])
        self.assertEqual(
            self.protocol["one_shot"]["sequence"],
            [
                "parser-canary", "warm-A", "warm-B", "fast-A1", "fast-B1",
                "fast-A2", "fast-B2", "fast-A1-repeat", "fast-B1-repeat",
                "deep-A1", "stop",
            ],
        )

    def test_warm_instrumentation_failure_never_rejects_fast_capability(self) -> None:
        item = {
            "finish_classification": "stream-token-count-mismatch",
            "resource_gate": {"passed": True},
        }
        self.assertEqual(holo.classify_warm_failure(item), "warm-token-instrumentation-failed")

    def test_v2_complete_object_hash_changes_on_parser_law_mutation(self) -> None:
        baseline = neo_loop.holostate_worker_protocol_v2_hash(self.evaluator)
        evaluator = copy.deepcopy(self.evaluator)
        evaluator["holostate_worker_protocol_v2"]["token_accumulation"][
            "empty_arrays_preserve_accumulated_evidence"
        ] = False
        self.assertNotEqual(baseline, neo_loop.holostate_worker_protocol_v2_hash(evaluator))

    def test_fast_v2_repeat_determinism_compares_repeats_not_distinct_branches(self) -> None:
        def item(label: str, assignment: str, root: str, content: str, tokens: list[int]) -> dict:
            content_hash = hashlib.sha256(content.encode()).hexdigest().upper()
            token_hash = harness.token_array_sha256(tokens)
            return {
                "request_label": label,
                "assignment_name": assignment,
                "root_name": root,
                "state_id": f"state-{root}",
                "accepted": True,
                "assistant_content": {"text": content, "sha256": content_hash},
                "reasoning_content": {"present": False},
                "finish_reason": "stop",
                "completion_token_ids": {"ids": tokens, "sha256": token_hash},
                "system_message_sha256": root * 64,
            }

        results = [
            item("fast-A1", "A1", "A", "HOLOSTATE FAST A1", [1]),
            item("fast-B1", "B1", "B", "HOLOSTATE FAST B1", [2]),
            item("fast-A2", "A2", "A", "HOLOSTATE FAST A2", [3]),
            item("fast-B2", "B2", "B", "HOLOSTATE FAST B2", [4]),
            item("fast-A1-repeat", "A1", "A", "HOLOSTATE FAST A1", [1]),
            item("fast-B1-repeat", "B1", "B", "HOLOSTATE FAST B1", [2]),
        ]
        gate = holo.fast_worker_v2_determinism_gate(results, self.protocol)
        self.assertTrue(gate["passed"], gate["reasons"])
        self.assertTrue(gate["repeat_determinism"]["A1"]["exact"])
        self.assertTrue(gate["distinct_branches"]["A"]["passed"])

    def test_v1_later_adjudication_does_not_rewrite_locked_result(self) -> None:
        original = self.evaluator["holostate_worker_protocol_v1_evidence"]
        adjudication = self.evaluator["holostate_worker_protocol_v1_adjudication"]
        self.assertEqual(original["fast_verdict"], "reject")
        self.assertEqual(adjudication["worker_protocol_v1"], "instrumentation-reject")
        self.assertEqual(adjudication["fast_worker_capability"], "untested-inconclusive")
        self.assertEqual(adjudication["deep_worker_capability"], "untested-inconclusive")

    def test_v2_evidence_is_optional_paired_and_complete_object_hashed(self) -> None:
        baseline = neo_loop.holostate_worker_protocol_v2_evidence_hash(self.evaluator)
        lock = neo_loop.make_lock(self.evaluator)
        self.assertEqual(lock["holostate_worker_protocol_v2_evidence_sha256"], baseline)
        evaluator = copy.deepcopy(self.evaluator)
        evaluator["holostate_worker_protocol_v2_evidence"]["worker_protocol_v2"] = "reviewable-accept"
        self.assertNotEqual(
            baseline,
            neo_loop.holostate_worker_protocol_v2_evidence_hash(evaluator),
        )

    def test_v2_collision_refuses_before_preclaim_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "worker-protocol-attempt-v2.json"
            marker.write_text("{}", encoding="utf-8")
            with mock.patch.object(holo, "WORKER_PROTOCOL_V2_ATTEMPT_PATH", marker), mock.patch.object(
                holo, "WORKER_PROTOCOL_V2_RESULT_PATH", root / "result.json"
            ), mock.patch.object(holo, "WORKER_PROTOCOL_V2_STREAM_PATH", root / "stream.jsonl"):
                with self.assertRaises(holo.NeoLoopError):
                    holo.prepare_worker_v2_audit_claim(SimpleNamespace(binary="x", model="y"))

    def test_global_ledger_or_resource_failure_locks_fast_availability(self) -> None:
        base = {
            "cleanup_gate": {"passed": True},
            "parser_canary": {"request_label": "parser-canary", "resource_gate": {"passed": True}},
            "warm_results": {},
            "fast_results": [],
            "deep_result": None,
            "stream_ledger": {
                "sha256": "A" * 64,
                "failure": None,
                "within_limits": True,
            },
        }
        self.assertTrue(holo.worker_protocol_v2_final_safety(base, [])["passed"])
        ledger_failed = copy.deepcopy(base)
        ledger_failed["stream_ledger"]["failure"] = "stream-ledger-ceiling-exceeded"
        self.assertFalse(holo.worker_protocol_v2_final_safety(ledger_failed, [])["passed"])
        deep_resource_failed = copy.deepcopy(base)
        deep_resource_failed["deep_result"] = {
            "request_label": "deep-A1",
            "resource_gate": {"passed": False},
        }
        self.assertFalse(holo.worker_protocol_v2_final_safety(deep_resource_failed, [])["passed"])
        availability = holo.worker_availability_state("reviewable-accept", safety_passed=False)
        self.assertEqual(availability["PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")

    def test_runner_canary_failure_claims_once_and_never_warms_root(self) -> None:
        class FakeSidecar:
            def __init__(self, *args, **kwargs) -> None:
                self.process = SimpleNamespace(pid=99)

            def launch(self) -> dict:
                return {"pid": 99, "listener_pid": 99}

            def guarded(self, label, operation, timeout=1200):
                return operation()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt_path = root / "worker-protocol-attempt-v2.json"
            result_path = root / "worker-protocol-result-v2.json"
            stream_path = root / "worker-protocol-v2-stream.jsonl"
            prior = {"historical": {"sha256": "A" * 64, "size_bytes": 1}}
            preclaim = {
                "protocol": self.protocol,
                "lock": {
                    "holostate_worker_protocol_v2_sha256": "B" * 64,
                    "evaluator_sha256": "C" * 64,
                },
                "stable_head": "HEAD",
                "stable_before": {42},
                "stable_status": "",
                "candidate_root": root,
                "candidate_head": "CANDIDATE",
                "candidate_status": "",
                "binary_identity": {"sha256": holo.EXPECTED_BINARY_SHA256},
                "model_identity": {"sha256": holo.EXPECTED_MODEL_SHA256},
                "stable_template_sha256": self.protocol["chat_template_identity"]["sha256"],
                "prior_before": prior,
                "evaluator": self.evaluator,
                "live_contract": self.evaluator["holostate_live_contract"],
            }

            def fake_git_read(path, *args):
                if args[:2] == ("rev-parse", "HEAD"):
                    return "HEAD" if Path(path) == holo.ROOT else "CANDIDATE"
                if args and args[0] == "status":
                    return ""
                raise AssertionError(args)

            canary_failure = {
                "request_label": "parser-canary",
                "accepted": False,
                "finish_classification": "stream-token-count-mismatch",
                "resource_gate": {"passed": True},
            }
            cleanup = {
                "process_stopped": True,
                "port_free": True,
                "runtime_removed": True,
                "wddm": {},
                "retirement_samples": [
                    {"available": False, "bytes": None} for _ in range(5)
                ],
                "stable_after": {"healthy": True, "listener_pids": [42]},
            }
            with mock.patch.object(holo, "STATE_ROOT", root), mock.patch.object(
                holo, "WORKER_PROTOCOL_V2_ATTEMPT_PATH", attempt_path
            ), mock.patch.object(holo, "WORKER_PROTOCOL_V2_RESULT_PATH", result_path), mock.patch.object(
                holo, "WORKER_PROTOCOL_V2_STREAM_PATH", stream_path
            ), mock.patch.object(holo, "prepare_worker_v2_audit_claim", return_value=preclaim), mock.patch.object(
                holo, "LiveSidecar", FakeSidecar
            ), mock.patch.object(holo, "run_parser_canary", return_value=canary_failure), mock.patch.object(
                holo, "worker_resource_gate", return_value={"passed": True}
            ), mock.patch.object(holo, "prepare_worker_root") as prepare_root, mock.patch.object(
                holo, "safe_sidecar_cleanup", return_value=cleanup
            ), mock.patch.object(holo, "git_read", side_effect=fake_git_read), mock.patch.object(
                holo, "require_stable", return_value={42}
            ), mock.patch.object(holo, "preserved_worker_prior_evidence", return_value=prior):
                result = holo.run_worker_protocol_v2_audit(SimpleNamespace(binary="x", model="y"))
            prepare_root.assert_not_called()
            self.assertEqual(result["worker_protocol_v2"], "instrumentation-reject")
            self.assertEqual(result["fast_requests_attempted"], 0)
            self.assertEqual(result["fast_requests_executed"], 0)
            self.assertEqual(result["warm_results"], {})
            self.assertTrue(attempt_path.is_file())
            self.assertTrue(result_path.is_file())
            self.assertTrue(stream_path.is_file())


class WorkerProtocolV3ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = holo.load_json(holo.EVALUATOR_PATH)
        cls.protocol_v2 = holo.validate_worker_protocol_v2(
            cls.evaluator["holostate_worker_protocol_v2"]
        )
        cls.protocol = holo.validate_worker_protocol_v3(
            cls.evaluator["holostate_worker_protocol_v3"],
            cls.protocol_v2,
        )

    def patch_v3_paths(self, stack: ExitStack, root: Path) -> dict[str, Path]:
        paths = {
            "readiness": root / "worker-protocol-readiness-v3.json",
            "attempt": root / "worker-protocol-attempt-v3.json",
            "result": root / "worker-protocol-result-v3.json",
            "stream": root / "worker-protocol-v3-stream.jsonl",
        }
        stack.enter_context(mock.patch.object(holo, "STATE_ROOT", root))
        for key, attribute in {
            "readiness": "WORKER_PROTOCOL_V3_READINESS_PATH",
            "attempt": "WORKER_PROTOCOL_V3_ATTEMPT_PATH",
            "result": "WORKER_PROTOCOL_V3_RESULT_PATH",
            "stream": "WORKER_PROTOCOL_V3_STREAM_PATH",
        }.items():
            stack.enter_context(mock.patch.object(holo, attribute, paths[key]))
        return paths

    def preclaim(self, candidate_root: Path) -> dict:
        prior = {"historical": {"sha256": "A" * 64, "size_bytes": 1}}
        return {
            "protocol": self.protocol,
            "lock": {
                "holostate_worker_protocol_v3_sha256": "B" * 64,
                "evaluator_sha256": "C" * 64,
            },
            "stable_head": "HEAD",
            "stable_status": "",
            "candidate_root": candidate_root,
            "candidate_head": "CANDIDATE",
            "candidate_status": "",
            "binary_identity": {"sha256": holo.EXPECTED_BINARY_SHA256},
            "model_identity": {"sha256": holo.EXPECTED_MODEL_SHA256},
            "stable_template_sha256": self.protocol["chat_template_identity"]["sha256"],
            "prior_before": prior,
            "evaluator": self.evaluator,
            "live_contract": self.evaluator["holostate_live_contract"],
        }

    @staticmethod
    def query(*, passed: bool, pids: set[int]) -> SimpleNamespace:
        payload = {
            "passed": passed,
            "port": holo.STABLE_PORT,
            "pids": sorted(pids),
            "attempt_count": 1,
            "timeout_count": 0,
            "unavailable_count": 0 if passed else 1,
            "latencies_seconds": [0.01],
            "errors": [] if passed else ["listener-query-unavailable"],
        }
        return SimpleNamespace(
            passed=passed,
            pids=frozenset(pids),
            to_dict=lambda: payload,
        )

    @staticmethod
    def cleanup(*, stable_pids: set[int] = {42}, admitted: bool = True) -> dict:
        return {
            "not_launched": not admitted,
            "readiness_controlled": True,
            "readiness_admitted": admitted,
            "process_stopped": True,
            "port_free": True,
            "runtime_removed": True,
            "wddm": {"failure_reason": None},
            "retirement_samples": (
                [{"available": False, "bytes": None} for _ in range(5)]
                if admitted else []
            ),
            "stable_after": {"healthy": True, "listener_pids": sorted(stable_pids)},
            "pre_teardown_ownership": {"passed": True} if admitted else None,
            "post_teardown_ownership": {"passed": True},
            "not_launched_port_state_observed": not admitted,
        }

    @staticmethod
    def fake_git_read(path: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "HEAD" if Path(path) == holo.ROOT else "CANDIDATE"
        if args and args[0] == "status":
            return ""
        raise AssertionError(args)

    def test_v3_exactly_inherits_v2_and_hash_covers_mutations(self) -> None:
        changed = {
            "id", "schema_version", "attempt_version", "prior_evidence",
            "stream_ledger", "one_shot",
        }
        self.assertEqual(set(self.protocol), set(self.protocol_v2) | {"readiness_control"})
        for key in set(self.protocol_v2) - changed:
            self.assertEqual(
                holo.canonical_json_bytes(self.protocol[key]),
                holo.canonical_json_bytes(self.protocol_v2[key]),
                key,
            )
        baseline = neo_loop.holostate_worker_protocol_v3_hash(self.evaluator)
        for path, value in (
            (("lanes", "F", "max_tokens"), 65),
            (("readiness_control", "maximum_retry_attempts"), 5),
        ):
            evaluator = copy.deepcopy(self.evaluator)
            target = evaluator["holostate_worker_protocol_v3"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertNotEqual(baseline, neo_loop.holostate_worker_protocol_v3_hash(evaluator))
            with self.assertRaises(holo.NeoLoopError):
                holo.validate_worker_protocol_v3(
                    evaluator["holostate_worker_protocol_v3"],
                    self.protocol_v2,
                )

    def test_v3_evidence_and_lock_are_optional_but_paired(self) -> None:
        without_evidence = copy.deepcopy(self.evaluator)
        without_evidence.pop("holostate_worker_protocol_v3_evidence", None)
        baseline_lock = neo_loop.make_lock(without_evidence)
        self.assertNotIn("holostate_worker_protocol_v3_evidence_sha256", baseline_lock)
        evaluator = copy.deepcopy(self.evaluator)
        evaluator.setdefault(
            "holostate_worker_protocol_v3_evidence",
            {"schema_version": 3, "readiness_v3": "pass"},
        )
        lock = neo_loop.make_lock(evaluator)
        evidence_hash = neo_loop.holostate_worker_protocol_v3_evidence_hash(evaluator)
        self.assertEqual(lock["holostate_worker_protocol_v3_evidence_sha256"], evidence_hash)
        mutated = copy.deepcopy(evaluator)
        mutated["holostate_worker_protocol_v3_evidence"]["readiness_v3"] = "reject"
        self.assertNotEqual(
            evidence_hash,
            neo_loop.holostate_worker_protocol_v3_evidence_hash(mutated),
        )
        with mock.patch.object(neo_loop, "load_json", return_value=lock):
            self.assertEqual(neo_loop.verify_lock(evaluator), lock)
        evidence_only = copy.deepcopy(lock)
        evidence_only.pop("holostate_worker_protocol_v3_evidence_sha256")
        with mock.patch.object(neo_loop, "load_json", return_value=evidence_only):
            with self.assertRaises(neo_loop.NeoLoopError):
                neo_loop.verify_lock(evaluator)
        lock_only = copy.deepcopy(baseline_lock)
        lock_only["holostate_worker_protocol_v3_evidence_sha256"] = "D" * 64
        with mock.patch.object(neo_loop, "load_json", return_value=lock_only):
            with self.assertRaises(neo_loop.NeoLoopError):
                neo_loop.verify_lock(without_evidence)

    def test_v3_prior_bindings_preserve_all_historical_hashes(self) -> None:
        tracked = self.protocol["prior_evidence"]["tracked_complete_objects"]
        self.assertEqual(tracked, {
            "holostate_worker_protocol_v1": neo_loop.holostate_worker_protocol_hash(self.evaluator),
            "holostate_worker_protocol_v1_evidence": neo_loop.holostate_worker_protocol_evidence_hash(self.evaluator),
            "holostate_worker_protocol_v1_adjudication": neo_loop.holostate_worker_protocol_v1_adjudication_hash(self.evaluator),
            "holostate_worker_protocol_v2": neo_loop.holostate_worker_protocol_v2_hash(self.evaluator),
            "holostate_worker_protocol_v2_evidence": neo_loop.holostate_worker_protocol_v2_evidence_hash(self.evaluator),
        })
        self.assertEqual(self.protocol["prior_evidence"]["files"], {
            "state/holostate/validation-attempt.json": holo.PRIOR_V1_ATTEMPT_SHA256,
            "state/holostate/validation-result.json": holo.PRIOR_V1_RESULT_SHA256,
            "state/holostate/reasoning-budget-qualification-v1.json": holo.PRIOR_QUALIFICATION_SHA256,
            "state/holostate/worker-protocol-attempt-v1.json": holo.PRIOR_WORKER_V1_ATTEMPT_SHA256,
            "state/holostate/worker-protocol-result-v1.json": holo.PRIOR_WORKER_V1_RESULT_SHA256,
            "state/holostate/worker-protocol-attempt-v2.json": holo.PRIOR_WORKER_V2_ATTEMPT_SHA256,
            "state/holostate/worker-protocol-result-v2.json": holo.PRIOR_WORKER_V2_RESULT_SHA256,
            "state/holostate/worker-protocol-v2-stream.jsonl": holo.PRIOR_WORKER_V2_STREAM_SHA256,
        })

    def test_v3_collision_refuses_before_any_preclaim_work(self) -> None:
        for collision_name in ("readiness", "attempt", "result", "stream"):
            with self.subTest(collision_name=collision_name), tempfile.TemporaryDirectory() as temp:
                with ExitStack() as stack:
                    paths = self.patch_v3_paths(stack, Path(temp))
                    paths[collision_name].write_text("{}", encoding="utf-8")
                    loader = stack.enter_context(mock.patch.object(holo, "load_locked_worker_protocol_v3"))
                    binary = stack.enter_context(mock.patch.object(holo, "verify_binary_identity"))
                    model = stack.enter_context(mock.patch.object(holo, "verify_model"))
                    listener = stack.enter_context(mock.patch.object(holo, "query_listener_pids"))
                    with self.assertRaises(holo.NeoLoopError):
                        holo.prepare_worker_v3_audit_claim(SimpleNamespace(binary="x", model="y"))
                    loader.assert_not_called()
                    binary.assert_not_called()
                    model.assert_not_called()
                    listener.assert_not_called()

    def test_v3_readiness_failure_creates_only_readiness_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v3_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v3_audit_claim", return_value=preclaim))
            query = stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42, 43}),
            ))
            sidecar = stack.enter_context(mock.patch.object(holo, "LiveSidecar"))
            sequence = stack.enter_context(mock.patch.object(holo, "execute_worker_v3_capability_sequence"))
            stack.enter_context(mock.patch.object(
                holo,
                "readiness_v3_no_sidecar_cleanup",
                return_value=self.cleanup(stable_pids={42, 43}, admitted=False),
            ))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            result = holo.run_worker_protocol_v3_audit(SimpleNamespace(binary="x", model="y"))
            self.assertEqual(result["readiness_v3"], "reject")
            self.assertEqual(result["FAST_PROCESS_LOCAL_HOLOSTATE"], "inconclusive")
            self.assertEqual(result["DEEP_PROCESS_LOCAL_HOLOSTATE"], "inconclusive")
            self.assertTrue(paths["readiness"].is_file())
            self.assertFalse(paths["attempt"].exists())
            self.assertFalse(paths["result"].exists())
            self.assertFalse(paths["stream"].exists())
            query.assert_called_once()
            sidecar.assert_not_called()
            sequence.assert_not_called()

    def test_v3_readiness_pass_claims_capability_once_and_zero_execution_cannot_reject_fast(self) -> None:
        constructor_kwargs: dict = {}

        class FakeSidecar:
            def __init__(self, *args, **kwargs) -> None:
                constructor_kwargs.update(kwargs)
                self.process = SimpleNamespace(pid=99)
                self.readiness_failure_evidence = {}
                self.ownership_boundaries: list[dict] = []

            def launch(self) -> dict:
                return {"pid": 99, "process_memory": {"private_bytes": 100}}

            def exact_ownership(self, boundary: str, **kwargs) -> dict:
                evidence = {"boundary": boundary, "passed": True}
                self.ownership_boundaries.append(evidence)
                return evidence

            def require_active(self, **kwargs) -> None:
                return None

        def execute(_sidecar, _readiness, _protocol, _ledger, result) -> None:
            result["worker_protocol_v3"] = "capability-reject"
            result["verdict"] = "capability-reject"
            result["FAST_PROCESS_LOCAL_HOLOSTATE"] = "reject"
            result["fast_requests_executed"] = 0

        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v3_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v3_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42}),
            ))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", FakeSidecar))
            sequence = stack.enter_context(mock.patch.object(
                holo,
                "execute_worker_v3_capability_sequence",
                side_effect=execute,
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "safe_sidecar_cleanup",
                return_value=self.cleanup(),
            ))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            claim = stack.enter_context(mock.patch.object(
                holo,
                "claim_runtime_json_once",
                wraps=holo.claim_runtime_json_once,
            ))
            result = holo.run_worker_protocol_v3_audit(SimpleNamespace(binary="x", model="y"))
            claimed_paths = [call.args[0] for call in claim.call_args_list]
            self.assertEqual(claimed_paths.count(paths["readiness"]), 1)
            self.assertEqual(claimed_paths.count(paths["attempt"]), 1)
            self.assertEqual(claimed_paths.count(paths["result"]), 1)
            self.assertTrue(paths["stream"].is_file())
            sequence.assert_called_once()
            readiness_hash = holo.sha256_file(paths["readiness"])
            attempt = json.loads(paths["attempt"].read_text(encoding="utf-8"))
            recorded = json.loads(paths["result"].read_text(encoding="utf-8"))
            self.assertEqual(attempt["readiness_sha256"], readiness_hash)
            self.assertEqual(recorded["readiness_sha256"], readiness_hash)
            self.assertTrue(result["readiness_evidence_preserved"])
            self.assertIn("readiness_deadline_at", constructor_kwargs)
            self.assertEqual(result["FAST_PROCESS_LOCAL_HOLOSTATE"], "inconclusive")
            self.assertEqual(result["worker_protocol_v3"], "inconclusive")
            self.assertEqual(result["PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")

    def test_v3_readiness_deadline_clamps_every_listener_window(self) -> None:
        control = self.protocol["readiness_control"]
        with mock.patch.object(holo.time, "monotonic", return_value=100.0):
            options = holo.listener_retry_options(
                control,
                shared_boundary=True,
                deadline_at=101.5,
            )
            self.assertEqual(options["timeout_seconds"], 1.5)
            self.assertEqual(options["max_window_seconds"], 1.5)
            self.assertEqual(options["maximum_total_query_window_seconds"], 1.5)
            with self.assertRaises(holo.HoloStateReadinessError):
                holo.listener_retry_options(control, deadline_at=100.0)

    def test_v3_reuses_preclaim_runtime_identity_without_rehashing_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / "llama-server.exe"
            model = root / "model.gguf"
            binary.write_bytes(b"bin")
            model.write_bytes(b"gguf")
            sidecar = object.__new__(holo.LiveSidecar)
            sidecar.binary = binary.resolve()
            sidecar.model = model.resolve()
            sidecar.evaluator = self.evaluator
            sidecar.readiness_control = self.protocol["readiness_control"]
            sidecar.preverified_binary_identity = {
                "path": str(binary.resolve()),
                "sha256": holo.EXPECTED_BINARY_SHA256,
                "runtime_version": holo.EXPECTED_RUNTIME_VERSION,
            }
            sidecar.preverified_model_identity = {
                "path": str(model.resolve()),
                "sha256": holo.EXPECTED_MODEL_SHA256,
                "size_bytes": 4,
            }
            with mock.patch.object(holo, "EXPECTED_MODEL_SIZE", 4), mock.patch.object(
                holo,
                "verify_binary_identity",
            ) as binary_verify, mock.patch.object(holo, "verify_model") as model_verify:
                binary_identity, model_identity = sidecar.runtime_identities()
            binary_verify.assert_not_called()
            model_verify.assert_not_called()
            self.assertEqual(binary_identity["sha256"], holo.EXPECTED_BINARY_SHA256)
            self.assertEqual(model_identity["sha256"], holo.EXPECTED_MODEL_SHA256)

    def test_v3_canary_failures_preserve_inherited_instrumentation_verdict(self) -> None:
        base = {
            "worker_protocol_v3": "inconclusive",
            "verdict": "inconclusive",
            "parser_canary_attempted": False,
            "parser_canary_executed": False,
        }
        sidecar = SimpleNamespace(
            guarded=mock.Mock(side_effect=RuntimeError("transport failed")),
        )
        with mock.patch.object(holo, "checkpoint_result"):
            with self.assertRaises(holo.NeoLoopError):
                holo.execute_worker_v3_capability_sequence(
                    sidecar,
                    {},
                    self.protocol,
                    mock.Mock(),
                    base,
                )
        self.assertEqual(base["worker_protocol_v3"], "instrumentation-reject")
        self.assertEqual(base["parser_canary"]["finish_classification"], "parser-canary-gate-failed")

        canary = {
            "request_label": "parser-canary",
            "accepted": True,
            "finish_classification": "accepted",
        }
        base = {
            "worker_protocol_v3": "inconclusive",
            "verdict": "inconclusive",
            "parser_canary_attempted": False,
            "parser_canary_executed": False,
        }
        sidecar = SimpleNamespace(guarded=mock.Mock(return_value=canary))
        with mock.patch.object(holo, "checkpoint_result"), mock.patch.object(
            holo,
            "worker_resource_gate",
            return_value={"passed": False},
        ):
            with self.assertRaises(holo.NeoLoopError):
                holo.execute_worker_v3_capability_sequence(
                    sidecar,
                    {},
                    self.protocol,
                    mock.Mock(),
                    base,
                )
        self.assertEqual(base["worker_protocol_v3"], "instrumentation-reject")
        self.assertEqual(base["parser_canary"]["finish_classification"], "canary-memory-or-isolation-failed")

    def test_never_started_wrong_sidecar_owner_is_a_restored_hard_reject(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            sidecar = object.__new__(holo.LiveSidecar)
            sidecar.readiness_control = self.protocol["readiness_control"]
            sidecar.readiness_deadline_at = None
            sidecar.admitted = False
            sidecar.stable_pids = {42}
            sidecar.process = None
            sidecar.sampler = None
            sidecar.log_handle = None
            sidecar.runtime = Path(temp) / "runtime"
            sidecar.runtime.mkdir()
            sidecar.readiness_failure_evidence = {}
            stable = SimpleNamespace(
                passed=True,
                hard_mismatch=False,
                actual_pids=frozenset({42}),
                to_dict=lambda: {"passed": True, "actual_pids": [42]},
            )
            occupied = SimpleNamespace(
                passed=True,
                pids=frozenset({777}),
                to_dict=lambda: {"passed": True, "pids": [777]},
            )
            with mock.patch.object(
                holo,
                "qualify_listener_ownership",
                return_value=stable,
            ), mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=occupied,
            ), mock.patch.object(holo, "health_ok", return_value=True):
                cleanup = sidecar.stop()
            self.assertTrue(cleanup["not_launched"])
            self.assertFalse(cleanup["port_free"])
            self.assertTrue(cleanup["not_launched_port_state_observed"])
            self.assertTrue(holo.cleanup_integrity(cleanup, {42})["passed"])
            self.assertEqual(
                holo.classify_worker_v3_readiness_failure(
                    holo.HoloStateReadinessError("sidecar-listener-pid-mismatch")
                ),
                "reject",
            )

    def test_v3_attempt_claim_failure_after_readiness_still_cleans_up(self) -> None:
        class FakeSidecar:
            def __init__(self, *args, **kwargs) -> None:
                self.process = SimpleNamespace(pid=99)
                self.readiness_failure_evidence = {}
                self.ownership_boundaries = []

            def launch(self) -> dict:
                return {"pid": 99}

            def exact_ownership(self, boundary: str, **kwargs) -> dict:
                return {"boundary": boundary, "passed": True}

            def require_active(self, **kwargs) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v3_paths(stack, root)
            paths["attempt"].write_text("{}", encoding="utf-8")
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v3_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42}),
            ))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", FakeSidecar))
            cleanup = stack.enter_context(mock.patch.object(
                holo,
                "safe_sidecar_cleanup",
                return_value=self.cleanup(),
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            with self.assertRaises(holo.NeoLoopError):
                holo.run_worker_protocol_v3_audit(SimpleNamespace(binary="x", model="y"))
            cleanup.assert_called_once()
            self.assertTrue(paths["readiness"].is_file())
            self.assertFalse(paths["result"].exists())
            self.assertFalse(paths["stream"].exists())

    def test_guarded_requires_fresh_pre_and_post_request_ownership(self) -> None:
        sidecar = object.__new__(holo.LiveSidecar)
        sidecar.require_active = mock.Mock()
        sidecar.exact_ownership = mock.Mock(return_value={"passed": True})
        self.assertEqual(sidecar.guarded("probe", lambda: "ok", timeout=1), "ok")
        self.assertEqual(
            [call.args[0] for call in sidecar.exact_ownership.call_args_list],
            ["pre-request:probe", "post-request:probe"],
        )
        blocked = object.__new__(holo.LiveSidecar)
        blocked.require_active = mock.Mock()
        blocked.exact_ownership = mock.Mock(side_effect=holo.NeoLoopError("wrong owner"))
        operation = mock.Mock(return_value="should-not-run")
        with self.assertRaises(holo.NeoLoopError):
            blocked.guarded("blocked", operation, timeout=1)
        operation.assert_not_called()

    def test_v3_stop_checks_pre_and_post_teardown_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            sidecar = object.__new__(holo.LiveSidecar)
            sidecar.readiness_control = self.protocol["readiness_control"]
            sidecar.readiness_deadline_at = None
            sidecar.admitted = True
            sidecar.stable_pids = {42}
            sidecar.process = mock.Mock(pid=99)
            sidecar.process.poll.side_effect = [None, None, 0]
            sidecar.sampler = None
            sidecar.log_handle = None
            sidecar.runtime = Path(temp) / "runtime"
            sidecar.runtime.mkdir()
            sidecar.exact_ownership = mock.Mock(return_value={"boundary": "pre-teardown", "passed": True})
            stable = SimpleNamespace(
                passed=True,
                actual_pids=frozenset({42}),
                to_dict=lambda: {"passed": True, "actual_pids": [42]},
            )
            empty = SimpleNamespace(
                passed=True,
                actual_pids=frozenset(),
                to_dict=lambda: {"passed": True, "actual_pids": []},
            )
            with mock.patch.object(
                holo,
                "qualify_runtime_ownership",
                return_value=(stable, empty),
            ) as post, mock.patch.object(
                holo,
                "wddm_pid_memory_sample",
                return_value=neo_loop.ProcessVramSample(False, None, []),
            ), mock.patch.object(holo.time, "sleep"), mock.patch.object(
                holo,
                "health_ok",
                return_value=True,
            ):
                cleanup = sidecar.stop()
            sidecar.exact_ownership.assert_called_once_with("pre-teardown")
            sidecar.process.terminate.assert_called_once()
            self.assertEqual(post.call_args.kwargs["sidecar_pids"], set())
            self.assertEqual(len(cleanup["retirement_samples"]), 5)
            self.assertTrue(holo.cleanup_integrity(cleanup, {42})["passed"])

    def test_failed_ownership_boundary_cannot_unlock_fast(self) -> None:
        class FakeSidecar:
            def __init__(self, *args, **kwargs) -> None:
                self.process = SimpleNamespace(pid=99)
                self.readiness_failure_evidence = {}
                self.ownership_boundaries = []

            def launch(self) -> dict:
                return {"pid": 99}

            def exact_ownership(self, boundary: str, **kwargs) -> dict:
                evidence = {"boundary": boundary, "passed": True}
                self.ownership_boundaries.append(evidence)
                return evidence

            def require_active(self, **kwargs) -> None:
                return None

        def execute(sidecar, _readiness, _protocol, _ledger, result) -> None:
            sidecar.ownership_boundaries.append({"boundary": "post-request-error:deep-A1", "passed": False})
            result["worker_protocol_v3"] = "reviewable-accept"
            result["verdict"] = "reviewable-accept"
            result["FAST_PROCESS_LOCAL_HOLOSTATE"] = "reviewable-accept"
            result["fast_requests_executed"] = 6

        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            self.patch_v3_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v3_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42}),
            ))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", FakeSidecar))
            stack.enter_context(mock.patch.object(
                holo,
                "execute_worker_v3_capability_sequence",
                side_effect=execute,
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "safe_sidecar_cleanup",
                return_value=self.cleanup(),
            ))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            result = holo.run_worker_protocol_v3_audit(SimpleNamespace(binary="x", model="y"))
            self.assertFalse(result["ownership_boundary_gate"]["passed"])
            self.assertEqual(result["FAST_PROCESS_LOCAL_HOLOSTATE"], "inconclusive")
            self.assertEqual(result["PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")

    def test_legacy_resource_gate_retains_exact_listener_validation(self) -> None:
        sidecar = SimpleNamespace(
            process=SimpleNamespace(pid=99),
            readiness_control=None,
            last_exact_ownership=None,
            sampler=None,
            require_active=mock.Mock(side_effect=holo.NeoLoopError("listener mismatch")),
            telemetry=mock.Mock(return_value={"sample_count": 1, "peak_dedicated_mib": 1.0}),
        )
        readiness = {"process_memory": {"private_bytes": 100}}
        with mock.patch.object(
            holo,
            "process_info",
            return_value={"private_bytes": 100},
        ), mock.patch.object(holo, "listener_pids", return_value={99}):
            gate = holo.worker_resource_gate(sidecar, readiness, self.protocol_v2)
        sidecar.require_active.assert_called_once_with(require_listener=True)
        self.assertFalse(gate["passed"])
        self.assertTrue(any("listener mismatch" in reason for reason in gate["reasons"]))


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

    def test_retired_qualification_and_validation_v2_create_no_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qualification = root / "qualification.json"
            validation_attempt = root / "validation-attempt-v2.json"
            validation_result = root / "validation-result-v2.json"
            with mock.patch.object(holo, "QUALIFICATION_PATH", qualification), mock.patch.object(
                holo, "V2_ATTEMPT_PATH", validation_attempt
            ), mock.patch.object(holo, "V2_RESULT_PATH", validation_result):
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_budget_qualification(SimpleNamespace(binary="x", model="y"))
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_validation_v2(SimpleNamespace(binary="x", model="y"))
            self.assertFalse(qualification.exists())
            self.assertFalse(validation_attempt.exists())
            self.assertFalse(validation_result.exists())

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
        self.assertEqual(
            len({
                holo.ATTEMPT_PATH,
                holo.RESULT_PATH,
                holo.QUALIFICATION_PATH,
                holo.V2_ATTEMPT_PATH,
                holo.V2_RESULT_PATH,
                holo.WORKER_PROTOCOL_ATTEMPT_PATH,
                holo.WORKER_PROTOCOL_RESULT_PATH,
                holo.WORKER_PROTOCOL_V2_ATTEMPT_PATH,
                holo.WORKER_PROTOCOL_V2_RESULT_PATH,
                holo.WORKER_PROTOCOL_V2_STREAM_PATH,
                holo.WORKER_PROTOCOL_V3_READINESS_PATH,
                holo.WORKER_PROTOCOL_V3_ATTEMPT_PATH,
                holo.WORKER_PROTOCOL_V3_RESULT_PATH,
                holo.WORKER_PROTOCOL_V3_STREAM_PATH,
            }),
            14,
        )

    def test_worker_protocol_cannot_run_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "worker-protocol-result-v1.json"
            result.write_text("{}", encoding="utf-8")
            with mock.patch.object(holo, "STATE_ROOT", root), mock.patch.object(
                holo, "WORKER_PROTOCOL_ATTEMPT_PATH", root / "worker-protocol-attempt-v1.json"
            ), mock.patch.object(holo, "WORKER_PROTOCOL_RESULT_PATH", result):
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_worker_protocol_audit(SimpleNamespace(binary="x", model="y"))

    def test_failed_preclaim_does_not_consume_worker_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "worker-protocol-attempt-v1.json"
            result = root / "worker-protocol-result-v1.json"
            with mock.patch.object(holo, "STATE_ROOT", root), mock.patch.object(
                holo, "WORKER_PROTOCOL_ATTEMPT_PATH", marker
            ), mock.patch.object(holo, "WORKER_PROTOCOL_RESULT_PATH", result), mock.patch.object(
                holo, "prepare_worker_audit_claim", side_effect=holo.NeoLoopError("preclaim failed")
            ):
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_worker_protocol_audit(SimpleNamespace(binary="x", model="y"))
            self.assertFalse(marker.exists())
            self.assertFalse(result.exists())

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

    def test_prior_qualification_and_validation_evidence_remain_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {
                "state/holostate/validation-attempt.json": b"attempt",
                "state/holostate/validation-result.json": b"result",
                "state/holostate/reasoning-budget-qualification-v1.json": b"qualification",
            }
            expected: dict[str, str] = {}
            for relative, raw in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                expected[relative] = hashlib.sha256(raw).hexdigest().upper()
            protocol = copy.deepcopy(
                holo.load_json(holo.EVALUATOR_PATH)["holostate_worker_protocol_v1"]
            )
            protocol["prior_evidence"]["files"] = expected
            before = {relative: (root / relative).read_bytes() for relative in files}
            with mock.patch.object(holo, "ROOT", root):
                evidence = holo.preserved_worker_prior_evidence(protocol)
            after = {relative: (root / relative).read_bytes() for relative in files}
            self.assertEqual(before, after)
            self.assertEqual(set(evidence), set(files))

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
        sidecar.exact_ownership = mock.Mock(return_value={"passed": True})
        sidecar.process = None
        started = time.monotonic()
        with self.assertRaises(holo.NeoLoopError):
            sidecar.guarded("slow", lambda: time.sleep(0.25), timeout=0.01)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.2)
        self.assertLess(elapsed, 0.6)


class CleanupGateTests(unittest.TestCase):
    def test_cleanup_fallback_terminates_exact_sidecar_after_stop_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            runtime.mkdir()
            process = mock.Mock(pid=123)
            process.poll.side_effect = [None, 0]
            sidecar = SimpleNamespace(
                stop=mock.Mock(side_effect=RuntimeError("telemetry failed")),
                process=process,
                log_handle=None,
                runtime=runtime,
            )
            with mock.patch.object(holo, "listener_pids", return_value=set()), mock.patch.object(
                holo, "stable_snapshot", return_value={"healthy": True, "listener_pids": [42]}
            ):
                cleanup = holo.safe_sidecar_cleanup(sidecar)
            process.terminate.assert_called_once()
            self.assertTrue(cleanup["process_stopped"])
            self.assertTrue(cleanup["runtime_removed"])
            self.assertIn("telemetry failed", cleanup["cleanup_error"])

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


class WorkerProtocolV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = holo.load_json(holo.EVALUATOR_PATH)
        cls.protocol_v2 = holo.validate_worker_protocol_v2(
            cls.evaluator["holostate_worker_protocol_v2"]
        )
        cls.protocol_v3 = holo.validate_worker_protocol_v3(
            cls.evaluator["holostate_worker_protocol_v3"], cls.protocol_v2
        )
        cls.protocol = holo.validate_worker_protocol_v4(
            cls.evaluator["holostate_worker_protocol_v4"], cls.protocol_v3
        )

    def patch_v4_paths(self, stack: ExitStack, root: Path) -> dict[str, Path]:
        paths = {
            "readiness": root / "worker-protocol-readiness-v4.json",
            "tokenizer": root / "worker-protocol-tokenizer-v4.json",
            "attempt": root / "worker-protocol-attempt-v4.json",
            "result": root / "worker-protocol-result-v4.json",
            "stream": root / "worker-protocol-v4-stream.jsonl",
        }
        stack.enter_context(mock.patch.object(holo, "STATE_ROOT", root))
        for key, attribute in {
            "readiness": "WORKER_PROTOCOL_V4_READINESS_PATH",
            "tokenizer": "WORKER_PROTOCOL_V4_TOKENIZER_PATH",
            "attempt": "WORKER_PROTOCOL_V4_ATTEMPT_PATH",
            "result": "WORKER_PROTOCOL_V4_RESULT_PATH",
            "stream": "WORKER_PROTOCOL_V4_STREAM_PATH",
        }.items():
            stack.enter_context(mock.patch.object(holo, attribute, paths[key]))
        return paths

    def preclaim(self, candidate_root: Path) -> dict:
        prior = {"historical": {"sha256": "A" * 64, "size_bytes": 1}}
        return {
            "protocol": self.protocol,
            "lock": {
                "holostate_worker_protocol_v4_sha256": "B" * 64,
                "evaluator_sha256": "C" * 64,
            },
            "stable_head": "HEAD",
            "stable_status": "",
            "candidate_root": candidate_root,
            "candidate_head": "CANDIDATE",
            "candidate_status": "",
            "binary_identity": {"sha256": holo.EXPECTED_BINARY_SHA256},
            "model_identity": {"sha256": holo.EXPECTED_MODEL_SHA256},
            "stable_template_sha256": self.protocol["chat_template_identity"]["sha256"],
            "prior_before": prior,
            "source_authority": {"integration_source_commit": "HEAD"},
            "evaluator": self.evaluator,
            "live_contract": self.evaluator["holostate_live_contract"],
        }

    @staticmethod
    def query(*, passed: bool, pids: set[int]) -> SimpleNamespace:
        payload = {
            "passed": passed,
            "pids": sorted(pids),
            "attempt_count": 1,
            "timeout_count": 0,
            "unavailable_count": 0 if passed else 1,
            "latencies_seconds": [0.01],
            "errors": [] if passed else ["listener-query-unavailable"],
        }
        return SimpleNamespace(passed=passed, pids=frozenset(pids), to_dict=lambda: payload)

    @staticmethod
    def cleanup(stable_pids: set[int] = {42}, admitted: bool = True) -> dict:
        return {
            "not_launched": not admitted,
            "readiness_controlled": True,
            "readiness_admitted": admitted,
            "process_stopped": True,
            "port_free": True,
            "runtime_removed": True,
            "wddm": {"failure_reason": None},
            "retirement_samples": (
                [{"available": False, "bytes": None} for _ in range(5)] if admitted else []
            ),
            "stable_after": {"healthy": True, "listener_pids": sorted(stable_pids)},
            "pre_teardown_ownership": {"passed": True} if admitted else None,
            "post_teardown_ownership": {"passed": True},
            "not_launched_port_state_observed": not admitted,
        }

    @staticmethod
    def fake_git_read(path: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "HEAD" if Path(path) == holo.ROOT else "CANDIDATE"
        if args and args[0] == "status":
            return ""
        raise AssertionError(args)

    class FakeAdmittedSidecar:
        def __init__(self, *args, **kwargs) -> None:
            self.process = SimpleNamespace(pid=99)
            self.readiness_failure_evidence = {}
            self.ownership_boundaries = []

        def launch(self):
            return {"pid": 99, "process_memory": {"private_bytes": 100}}

        def exact_ownership(self, boundary: str, **kwargs):
            return {"boundary": boundary, "passed": True}

        def require_active(self, **kwargs):
            return None

        def guarded(self, _label, function, **kwargs):
            return function()

    def test_v4_complete_object_hash_and_validator_cover_claim_mutations(self) -> None:
        baseline = neo_loop.holostate_worker_protocol_v4_hash(self.evaluator)
        for path, value in (
            (("terminal_eos_accounting", "one_terminal_token_reconciliation", "usage_delta"), 2),
            (("tokenizer_qualification", "expected_visible_token_count"), 5),
            (("lanes", "F", "max_tokens"), 65),
        ):
            evaluator = copy.deepcopy(self.evaluator)
            target = evaluator["holostate_worker_protocol_v4"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertNotEqual(baseline, neo_loop.holostate_worker_protocol_v4_hash(evaluator))
            with self.assertRaises(holo.NeoLoopError):
                holo.validate_worker_protocol_v4(
                    evaluator["holostate_worker_protocol_v4"], self.protocol_v3
                )

    def test_v4_evidence_and_lock_are_optional_but_paired(self) -> None:
        without = copy.deepcopy(self.evaluator)
        without.pop("holostate_worker_protocol_v4_evidence", None)
        baseline_lock = neo_loop.make_lock(without)
        self.assertNotIn("holostate_worker_protocol_v4_evidence_sha256", baseline_lock)
        evaluator = copy.deepcopy(without)
        evaluator["holostate_worker_protocol_v4_evidence"] = {
            "schema_version": 4,
            "worker_protocol_v4": "inconclusive",
        }
        lock = neo_loop.make_lock(evaluator)
        self.assertEqual(
            lock["holostate_worker_protocol_v4_evidence_sha256"],
            neo_loop.holostate_worker_protocol_v4_evidence_hash(evaluator),
        )
        with mock.patch.object(neo_loop, "load_json", return_value=lock):
            self.assertEqual(neo_loop.verify_lock(evaluator), lock)
        missing_pair = copy.deepcopy(lock)
        missing_pair.pop("holostate_worker_protocol_v4_evidence_sha256")
        with mock.patch.object(neo_loop, "load_json", return_value=missing_pair):
            with self.assertRaises(neo_loop.NeoLoopError):
                neo_loop.verify_lock(evaluator)

    def test_v4_all_five_collisions_refuse_before_loader_or_network(self) -> None:
        for collision in ("readiness", "tokenizer", "attempt", "result", "stream"):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                paths = self.patch_v4_paths(stack, Path(temp))
                paths[collision].write_text("{}", encoding="utf-8")
                loader = stack.enter_context(mock.patch.object(holo, "load_locked_worker_protocol_v4"))
                network = stack.enter_context(mock.patch.object(holo, "request_json"))
                with self.assertRaises(holo.NeoLoopError):
                    holo.prepare_worker_v4_audit_claim(SimpleNamespace(binary="x", model="y"))
                loader.assert_not_called()
                network.assert_not_called()

    def test_v4_readiness_failure_creates_only_readiness_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v4_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v4_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42, 43}),
            ))
            sidecar = stack.enter_context(mock.patch.object(holo, "LiveSidecar"))
            stack.enter_context(mock.patch.object(
                holo,
                "readiness_v3_no_sidecar_cleanup",
                return_value=self.cleanup(stable_pids={42, 43}, admitted=False),
            ))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            result = holo.run_worker_protocol_v4_audit(SimpleNamespace(binary="x", model="y"))
            self.assertEqual(result["readiness_v4"], "reject")
            self.assertTrue(paths["readiness"].is_file())
            self.assertFalse(paths["tokenizer"].exists())
            self.assertFalse(paths["attempt"].exists())
            self.assertFalse(paths["result"].exists())
            self.assertFalse(paths["stream"].exists())
            sidecar.assert_not_called()

    def test_v4_tokenizer_failure_creates_no_capability_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v4_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v4_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42}),
            ))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", self.FakeAdmittedSidecar))
            stack.enter_context(mock.patch.object(
                holo,
                "run_worker_v4_tokenizer_qualification",
                return_value={
                    "status": "complete",
                    "tokenizer_v4": "reject",
                    "generation_executed": False,
                    "reasons": ["tokenizer-repeat-mismatch"],
                },
            ))
            stack.enter_context(mock.patch.object(holo, "worker_resource_gate", return_value={"passed": True}))
            stack.enter_context(mock.patch.object(holo, "safe_sidecar_cleanup", return_value=self.cleanup()))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            result = holo.run_worker_protocol_v4_audit(SimpleNamespace(binary="x", model="y"))
            self.assertEqual(result["readiness_v4"], "pass")
            self.assertEqual(result["tokenizer_v4"], "reject")
            self.assertTrue(paths["readiness"].is_file())
            self.assertTrue(paths["tokenizer"].is_file())
            self.assertFalse(paths["attempt"].exists())
            self.assertFalse(paths["result"].exists())
            self.assertFalse(paths["stream"].exists())

    def test_v4_tokenizer_resource_failure_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v4_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            stack.enter_context(mock.patch.object(holo, "prepare_worker_v4_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42}),
            ))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", self.FakeAdmittedSidecar))
            stack.enter_context(mock.patch.object(
                holo,
                "run_worker_v4_tokenizer_qualification",
                return_value={
                    "status": "complete",
                    "tokenizer_v4": "pass",
                    "generation_executed": False,
                    "reasons": [],
                },
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "worker_resource_gate",
                return_value={"passed": False, "reasons": ["exact-PID-WDDM-gate-failed"]},
            ))
            stack.enter_context(mock.patch.object(holo, "safe_sidecar_cleanup", return_value=self.cleanup()))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(
                holo,
                "preserved_worker_prior_evidence",
                return_value=preclaim["prior_before"],
            ))
            result = holo.run_worker_protocol_v4_audit(SimpleNamespace(binary="x", model="y"))
            artifact = json.loads(paths["tokenizer"].read_text(encoding="utf-8"))
            self.assertEqual(result["tokenizer_v4"], "inconclusive")
            self.assertEqual(artifact["tokenizer_v4"], "inconclusive")
            self.assertTrue(artifact["tokenizer_artifact_owned"])
            self.assertFalse(paths["attempt"].exists())
            self.assertFalse(paths["result"].exists())
            self.assertFalse(paths["stream"].exists())

    def test_v4_tokenizer_claim_race_does_not_overwrite_unowned_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v4_paths(stack, root)
            preclaim = self.preclaim(root / "candidate")
            original_claim = holo.claim_runtime_json_once

            def raced_claim(path: Path, value: dict) -> None:
                if path == paths["tokenizer"]:
                    path.write_text('{"owner":"other"}\n', encoding="utf-8")
                    raise holo.NeoLoopError("one-shot operation already claimed")
                original_claim(path, value)

            stack.enter_context(mock.patch.object(holo, "prepare_worker_v4_audit_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo,
                "query_listener_pids",
                return_value=self.query(passed=True, pids={42}),
            ))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", self.FakeAdmittedSidecar))
            stack.enter_context(mock.patch.object(holo, "claim_runtime_json_once", side_effect=raced_claim))
            stack.enter_context(mock.patch.object(holo, "safe_sidecar_cleanup", return_value=self.cleanup()))
            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=self.fake_git_read))
            stack.enter_context(mock.patch.object(holo, "preserved_worker_prior_evidence", return_value=preclaim["prior_before"]))
            result = holo.run_worker_protocol_v4_audit(SimpleNamespace(binary="x", model="y"))
            self.assertEqual(result["tokenizer_v4"], "inconclusive")
            self.assertFalse(result["tokenizer_artifact_owned"])
            self.assertIsNone(result["tokenizer_sha256"])
            self.assertEqual(paths["tokenizer"].read_text(encoding="utf-8"), '{"owner":"other"}\n')
            self.assertFalse(paths["attempt"].exists())
            self.assertFalse(paths["result"].exists())
            self.assertFalse(paths["stream"].exists())

    def test_v4_canary_infrastructure_failures_remain_inconclusive(self) -> None:
        cases = (
            (
                "guarded-exception",
                mock.Mock(side_effect=holo.NeoLoopError("listener ownership unavailable")),
                {"passed": True},
                "parser-canary-execution-inconclusive",
            ),
            (
                "resource-gate",
                mock.Mock(return_value={"accepted": True, "finish_classification": "accepted"}),
                {"passed": False, "reasons": ["exact-PID-WDDM-gate-failed"]},
                "canary-memory-or-isolation-failed",
            ),
        )
        for name, guarded, resource_gate, classification in cases:
            with self.subTest(name=name), mock.patch.object(
                holo, "checkpoint_result"
            ), mock.patch.object(holo, "worker_resource_gate", return_value=resource_gate):
                result = {"parser_canary_attempted": False}
                sidecar = SimpleNamespace(guarded=guarded)
                with self.assertRaises(holo.NeoLoopError):
                    holo.execute_worker_v4_capability_sequence(
                        sidecar,
                        {"process_memory": {"private_bytes": 0}},
                        self.protocol,
                        SimpleNamespace(),
                        result,
                    )
                self.assertEqual(result["worker_protocol_v4"], "inconclusive")
                self.assertEqual(result["verdict"], "inconclusive")
                self.assertEqual(
                    result["parser_canary"]["finish_classification"],
                    classification,
                )

    def test_strict_v4_tokenizer_rejects_bool_and_text_tokens(self) -> None:
        for value in ([True], ["1"], None):
            with self.subTest(value=value), self.assertRaises(holo.NeoLoopError):
                holo.strict_v4_token_ids(value, label="test")

    def test_tokenizer_v4_qualification_is_repeatable_round_trip_and_generation_free(self) -> None:
        responses = [
            {"tokens": [60738, 30094, 18916, 8378]},
            {"tokens": [60738, 30094, 18916, 8378]},
            {"content": "TOKEN ARRAY CANARY"},
        ]
        with mock.patch.object(holo, "request_json", side_effect=responses) as request, mock.patch.object(
            holo,
            "stream_completion",
        ) as generation:
            result = holo.run_worker_v4_tokenizer_qualification(self.protocol)
        self.assertEqual(result["tokenizer_v4"], "pass")
        self.assertTrue(result["repeat_equal"])
        self.assertTrue(result["round_trip_equal"])
        self.assertFalse(result["generation_executed"])
        self.assertEqual(request.call_count, 3)
        generation.assert_not_called()

    def canary_measurement(self, **overrides) -> SimpleNamespace:
        base = {
            "content": "TOKEN ARRAY CANARY",
            "reasoning_content": "",
            "tool_calls": [],
            "finish_reason": "stop",
            "completion_tokens": 5,
            "prompt_tokens": 7,
            "cached_prompt_tokens": 0,
            "generated_token_ids": [],
            "generated_token_sha256": holo.sha256_bytes(holo.canonical_json_bytes([])),
            "nonempty_token_array_event_count": 0,
            "empty_token_array_event_count": 1,
            "token_merge_modes": {"absent": 1, "ignored-empty": 1},
            "completion_token_count_match": False,
            "stop_type": "eos",
            "stopping_word": "",
            "terminal_stop_evidence": {
                "observed": True,
                "stop": True,
                "stop_type": "eos",
                "stopping_word": "",
                "verbose_token_array_length": 0,
                "event_index": 1,
            },
            "prompt_progress": [],
            "timings": {},
            "total_time_s": 1.0,
            "event_count": 2,
            "http_status": 200,
            "time_to_first_event_s": 0.1,
            "time_to_first_token_s": 0.2,
            "time_to_first_content_s": 0.2,
            "reported_tokens_per_second": 10.0,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_v4_canary_accepts_exact_four_visible_plus_one_terminal_eos(self) -> None:
        ledger = SimpleNamespace(record_count=0, failure=None, recorder=lambda *_: mock.Mock())
        measurement = self.canary_measurement()

        def fake_stream(*_args, **_kwargs):
            ledger.record_count += 1
            return measurement

        with mock.patch.object(holo, "render_messages", return_value="rendered"), mock.patch.object(
            holo,
            "tokenize",
            return_value=list(range(7)),
        ), mock.patch.object(holo, "stream_completion", side_effect=fake_stream), mock.patch.object(
            holo,
            "strict_v4_sidecar_tokenize",
            return_value=([60738, 30094, 18916, 8378], {"request_sha256": "A", "response_sha256": "B"}),
        ):
            result = holo.run_parser_canary_v4(self.protocol, ledger, request_sequence_index=1)
        self.assertTrue(result["accepted"], result["gate_reasons"])
        evidence = result["visible_token_evidence"]
        self.assertEqual(evidence["usage_delta"], 1)
        self.assertEqual(evidence["terminal_control_token_count"], 1)
        self.assertFalse(result["terminal_eos_id_known"])
        self.assertFalse(result["full_generated_sequence_known"])

    def test_v4_canary_rejects_missing_direct_terminal_evidence(self) -> None:
        ledger = SimpleNamespace(record_count=0, failure=None, recorder=lambda *_: mock.Mock())
        measurement = self.canary_measurement(
            stop_type=None,
            stopping_word=None,
            terminal_stop_evidence=None,
        )

        def fake_stream(*_args, **_kwargs):
            ledger.record_count += 1
            return measurement

        with mock.patch.object(holo, "render_messages", return_value="rendered"), mock.patch.object(
            holo,
            "tokenize",
            return_value=list(range(7)),
        ), mock.patch.object(holo, "stream_completion", side_effect=fake_stream), mock.patch.object(
            holo,
            "strict_v4_sidecar_tokenize",
            return_value=([60738, 30094, 18916, 8378], {"request_sha256": "A", "response_sha256": "B"}),
        ):
            result = holo.run_parser_canary_v4(self.protocol, ledger, request_sequence_index=1)
        self.assertFalse(result["accepted"])
        self.assertIn("terminal-eos-accounting-not-proven", result["gate_reasons"])

    def test_deep_channel_acceptance_never_requires_reconstructed_tokens(self) -> None:
        result = {
            "http_status": 200,
            "prompt_token_identity_matches": True,
            "finish_reason": "stop",
            "assistant_content": {"text": "HOLOSTATE DEEP A"},
            "expected_content": "HOLOSTATE DEEP A",
            "tool_calls": [],
            "reasoning_content": {"present": True},
            "logical_prompt_tokens": 100,
            "cached_prompt_tokens": 90,
            "fresh_prompt_tokens": 10,
            "native_token_array": {"count_match": False},
        }
        classification = holo.classify_worker_v4_channels(
            result,
            self.protocol["lanes"]["D"],
            warm=False,
            token_evidence_required=False,
        )
        self.assertEqual(classification, "accepted-token-sequence-unavailable")

    def test_fast_repeat_gate_compares_visible_sequence_and_terminal_metadata(self) -> None:
        labels = [
            ("fast-A1", "A1", "A"), ("fast-B1", "B1", "B"),
            ("fast-A2", "A2", "A"), ("fast-B2", "B2", "B"),
            ("fast-A1-repeat", "A1", "A"), ("fast-B1-repeat", "B1", "B"),
        ]
        results = []
        for label, assignment, root in labels:
            content = self.protocol["lanes"]["F"]["assignments"][assignment]["expected_content"]
            tokens = [1, 2, 3, 4, 10 if assignment.endswith("1") else 20]
            results.append({
                "request_label": label,
                "assignment_name": assignment,
                "root_name": root,
                "accepted": True,
                "assistant_content": {"text": content, "sha256": holo.sha256_bytes(content.encode())},
                "visible_token_evidence": {
                    "token_ids": tokens,
                    "token_sha256": holo.sha256_bytes(holo.canonical_json_bytes(tokens)),
                    "usage_delta": 1,
                    "terminal_control_token_count": 1,
                    "terminal_stop_type": "eos",
                },
                "completion_tokens": len(tokens) + 1,
                "state_id": f"state-{root}",
                "system_message_sha256": f"system-{root}",
                "reasoning_content": {"present": False},
                "tool_calls": [],
                "finish_reason": "stop",
            })
        gate = holo.fast_worker_v4_determinism_gate(results, self.protocol)
        self.assertTrue(gate["passed"], gate["reasons"])
        self.assertFalse(gate["unknown_terminal_eos_token_id_compared"])
        broken = copy.deepcopy(results)
        broken[-2]["visible_token_evidence"]["usage_delta"] = 0
        self.assertFalse(holo.fast_worker_v4_determinism_gate(broken, self.protocol)["passed"])


class CatalyticSwarm0LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = holo.load_json(holo.EVALUATOR_PATH)
        protocol_v2 = holo.validate_worker_protocol_v2(
            cls.evaluator["holostate_worker_protocol_v2"]
        )
        protocol_v3 = holo.validate_worker_protocol_v3(
            cls.evaluator["holostate_worker_protocol_v3"], protocol_v2
        )
        cls.protocol_v4 = holo.validate_worker_protocol_v4(
            cls.evaluator["holostate_worker_protocol_v4"], protocol_v3
        )
        cls.contract = holo.validate_catalytic_swarm_0(
            cls.evaluator["catalytic_swarm_0"], cls.protocol_v4
        )
        cls.v2_contract = holo.validate_catalytic_swarm_0_v2(
            cls.evaluator["catalytic_swarm_0_v2"],
            cls.contract,
            cls.protocol_v4,
        )

    def patch_paths(self, stack: ExitStack, root: Path) -> dict[str, Path]:
        names = {
            "control": "control-qualification-v1.json",
            "readiness": "readiness-v1.json",
            "canary": "parser-canary-v1.json",
            "attempt": "attempt-v1.json",
            "result": "result-v1.json",
            "ledger": "ledger-v1.jsonl",
            "blackboard": "blackboard-v1.json",
        }
        paths = {key: root / value for key, value in names.items()}
        stack.enter_context(mock.patch.object(holo, "CATALYTIC_STATE_ROOT", root))
        attributes = {
            "control": "CATALYTIC_CONTROL_QUALIFICATION_PATH",
            "readiness": "CATALYTIC_READINESS_PATH",
            "canary": "CATALYTIC_PARSER_CANARY_PATH",
            "attempt": "CATALYTIC_ATTEMPT_PATH",
            "result": "CATALYTIC_RESULT_PATH",
            "ledger": "CATALYTIC_LEDGER_PATH",
            "blackboard": "CATALYTIC_BLACKBOARD_PATH",
        }
        for key, attribute in attributes.items():
            stack.enter_context(mock.patch.object(holo, attribute, paths[key]))
        stack.enter_context(
            mock.patch.object(
                holo,
                "CATALYTIC_ARTIFACT_PATHS",
                tuple(paths[key] for key in names),
            )
        )
        return paths

    def patch_v2_paths(self, stack: ExitStack, root: Path) -> dict[str, Path]:
        names = {
            "control": "control-qualification-v2.json",
            "readiness": "readiness-v2.json",
            "canary": "parser-canary-v2.json",
            "attempt": "attempt-v2.json",
            "result": "result-v2.json",
            "ledger": "ledger-v2.jsonl",
            "blackboard": "blackboard-v2.json",
        }
        paths = {key: root / value for key, value in names.items()}
        stack.enter_context(mock.patch.object(holo, "CATALYTIC_STATE_ROOT", root))
        attributes = {
            "control": "CATALYTIC_V2_CONTROL_QUALIFICATION_PATH",
            "readiness": "CATALYTIC_V2_READINESS_PATH",
            "canary": "CATALYTIC_V2_PARSER_CANARY_PATH",
            "attempt": "CATALYTIC_V2_ATTEMPT_PATH",
            "result": "CATALYTIC_V2_RESULT_PATH",
            "ledger": "CATALYTIC_V2_LEDGER_PATH",
            "blackboard": "CATALYTIC_V2_BLACKBOARD_PATH",
        }
        for key, attribute in attributes.items():
            stack.enter_context(mock.patch.object(holo, attribute, paths[key]))
        stack.enter_context(
            mock.patch.object(
                holo,
                "CATALYTIC_V2_ARTIFACT_PATHS",
                tuple(paths[key] for key in names),
            )
        )
        return paths

    def preclaim(self, root: Path) -> dict:
        return {
            "evaluator": self.evaluator,
            "live_contract": self.evaluator["holostate_live_contract"],
            "protocol_v4": self.protocol_v4,
            "contract": self.contract,
            "lock": {"catalytic_swarm_0_sha256": "A" * 64},
            "prior_before": {"v4": "preserved"},
            "stable_branch": "main",
            "stable_head": "HEAD",
            "stable_status": "",
            "candidate_root": root / "candidate",
            "candidate_head": "CANDIDATE",
            "candidate_status": "",
            "binary_identity": {"sha256": holo.EXPECTED_BINARY_SHA256},
            "model_identity": {"sha256": holo.EXPECTED_MODEL_SHA256},
            "stable_template_sha256": self.contract["transport"]["chat_template_identity"]["sha256"],
        }

    def preclaim_v2(self, root: Path) -> dict:
        return {
            "evaluator": self.evaluator,
            "live_contract": self.evaluator["holostate_live_contract"],
            "protocol_v4": self.protocol_v4,
            "contract": self.v2_contract,
            "lock": {"catalytic_swarm_0_v2_sha256": "B" * 64},
            "prior_before": {"v4": "preserved"},
            "predecessor_v1_artifacts": {"v1": "preserved"},
            "frozen_root_source_ref": self.v2_contract["predecessor_v1"][
                "integration_commit"
            ],
            "frozen_root_sources": [],
            "stable_branch": "main",
            "stable_head": "HEAD",
            "stable_status": "",
            "candidate_root": root / "candidate",
            "candidate_head": "CANDIDATE",
            "candidate_status": "",
            "binary_identity": {"sha256": holo.EXPECTED_BINARY_SHA256},
            "model_identity": {"sha256": holo.EXPECTED_MODEL_SHA256},
            "stable_template_sha256": self.v2_contract["transport"][
                "chat_template_identity"
            ]["sha256"],
        }

    @staticmethod
    def query(pids: set[int]) -> SimpleNamespace:
        return SimpleNamespace(
            passed=True,
            pids=frozenset(pids),
            to_dict=lambda: {"passed": True, "pids": sorted(pids)},
        )

    @staticmethod
    def cleanup(stable: set[int] = {42}) -> dict:
        return {
            "not_launched": False,
            "readiness_controlled": True,
            "readiness_admitted": True,
            "process_stopped": True,
            "port_free": True,
            "runtime_removed": True,
            "wddm": {"failure_reason": None},
            "retirement_samples": [
                {"available": False, "bytes": None} for _ in range(5)
            ],
            "stable_after": {"healthy": True, "listener_pids": sorted(stable)},
            "pre_teardown_ownership": {"passed": True},
            "post_teardown_ownership": {"passed": True},
        }

    class FakeSidecar:
        def __init__(self, *args, **kwargs) -> None:
            self.process = SimpleNamespace(pid=99)
            self.ownership_boundaries = []

        def launch(self):
            return {
                "pid": 99,
                "binary": {"sha256": holo.EXPECTED_BINARY_SHA256},
                "model": {"sha256": holo.EXPECTED_MODEL_SHA256},
                "chat_template_sha256": holo.load_json(holo.EVALUATOR_PATH)[
                    "catalytic_swarm_0"
                ]["transport"]["chat_template_identity"]["sha256"],
                "process_memory": {"private_bytes": 100},
            }

        def exact_ownership(self, boundary, **kwargs):
            item = {"boundary": boundary, "passed": True}
            self.ownership_boundaries.append(item)
            return item

        def require_active(self, **kwargs):
            return None

        def guarded(self, _label, function, **kwargs):
            return function()

    def install_live_stage(
        self,
        stack: ExitStack,
        temp: Path,
        *,
        warm_accepted: bool = True,
        canary_accepted: bool = True,
    ) -> tuple[dict[str, Path], mock.Mock, mock.Mock]:
        paths = self.patch_paths(stack, temp)
        stack.enter_context(mock.patch.object(
            holo, "prepare_catalytic_swarm_0_claim",
            return_value=self.preclaim(temp),
        ))
        stack.enter_context(mock.patch.object(
            holo, "qualify_catalytic_control_outputs",
            return_value={
                "passed": True, "reasons": [], "generation_executed": False,
            },
        ))
        stack.enter_context(mock.patch.object(
            holo, "query_listener_pids", return_value=self.query({42}),
        ))
        stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
        stack.enter_context(mock.patch.object(holo, "LiveSidecar", self.FakeSidecar))
        stack.enter_context(mock.patch.object(
            holo, "prepare_catalytic_root",
            return_value=(
                "root",
                {
                    "state_id": "state",
                    "system_message_sha256": self.contract[
                        "root_and_prior_evidence"
                    ]["system_message_sha256"],
                },
            ),
        ))
        warm = stack.enter_context(mock.patch.object(
            holo, "run_worker_v4_chat_request",
            return_value={"accepted": warm_accepted, "finish_classification": "accepted"},
        ))
        canary = stack.enter_context(mock.patch.object(
            holo, "run_catalytic_parser_canary",
            return_value={
                "accepted": canary_accepted,
                "finish_classification": (
                    "accepted" if canary_accepted else "structured-reject"
                ),
            },
        ))
        stack.enter_context(mock.patch.object(
            holo,
            "worker_resource_gate",
            return_value={"passed": True, "host_private_growth_bytes": 10},
        ))
        cleanup = stack.enter_context(mock.patch.object(
            holo, "safe_sidecar_cleanup", return_value=self.cleanup(),
        ))
        stack.enter_context(mock.patch.object(
            holo, "cleanup_integrity", return_value={"passed": True, "reasons": []},
        ))
        return paths, cleanup, canary

    def test_complete_contract_hash_and_validator_reject_plan_drift(self) -> None:
        baseline = neo_loop.catalytic_swarm_0_hash(self.evaluator)
        changed = copy.deepcopy(self.evaluator)
        changed["catalytic_swarm_0"]["plan"]["definition"]["physical_slots"] = 2
        self.assertNotEqual(baseline, neo_loop.catalytic_swarm_0_hash(changed))
        with self.assertRaises(holo.NeoLoopError):
            holo.validate_catalytic_swarm_0(
                changed["catalytic_swarm_0"], self.protocol_v4
            )

    def test_v2_validator_rejects_any_undeclared_inherited_change(self) -> None:
        changed = copy.deepcopy(self.v2_contract)
        changed["plan"]["worker_seeds"]["cs0-w01"] += 1
        with self.assertRaisesRegex(holo.NeoLoopError, "inherited v1 law"):
            holo.validate_catalytic_swarm_0_v2(
                changed,
                self.contract,
                self.protocol_v4,
            )

    def test_v2_frozen_root_uses_exact_v1_integration_bytes(self) -> None:
        raw, sources = holo.compose_prefix(
            "A",
            self.protocol_v4,
            source_ref=self.v2_contract["predecessor_v1"]["integration_commit"],
        )
        self.assertEqual(
            holo.sha256_bytes(raw),
            self.v2_contract["root_and_prior_evidence"]["canonical_prefix_sha256"],
        )
        self.assertEqual(
            [item["path"] for item in sources],
            self.protocol_v4["roots"]["A"]["sources"],
        )

    def test_v2_control_failure_creates_only_v2_control_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v2_paths(stack, root)
            v1_sentinel = root / "control-qualification-v1.json"
            v1_sentinel.write_text("immutable-v1", encoding="utf-8")
            stack.enter_context(mock.patch.object(
                holo,
                "prepare_catalytic_swarm_0_v2_claim",
                return_value=self.preclaim_v2(root),
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "qualify_catalytic_control_outputs",
                return_value={
                    "passed": False,
                    "reasons": ["forced"],
                    "generation_executed": False,
                },
            ))
            result = holo.run_catalytic_swarm_0_audit(
                SimpleNamespace(binary="x", model="y"), version=2
            )
            self.assertEqual(result["control_qualification_v2"], "reject")
            self.assertEqual(result["catalytic_swarm_0_v2"], "instrumentation-reject")
            self.assertTrue(paths["control"].is_file())
            self.assertFalse(any(paths[key].exists() for key in list(paths)[1:]))
            self.assertEqual(v1_sentinel.read_text(encoding="utf-8"), "immutable-v1")

    def test_v2_readiness_nonpass_creates_no_canary_or_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            paths = self.patch_v2_paths(stack, root)
            stack.enter_context(mock.patch.object(
                holo,
                "prepare_catalytic_swarm_0_v2_claim",
                return_value=self.preclaim_v2(root),
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "qualify_catalytic_control_outputs",
                return_value={
                    "passed": True,
                    "reasons": [],
                    "generation_executed": False,
                },
            ))
            stack.enter_context(mock.patch.object(
                holo, "query_listener_pids", return_value=self.query({42, 43})
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "readiness_v3_no_sidecar_cleanup",
                return_value={"not_launched": True},
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "cleanup_integrity",
                return_value={"passed": True, "reasons": []},
            ))
            result = holo.run_catalytic_swarm_0_audit(
                SimpleNamespace(binary="x", model="y"), version=2
            )
            self.assertIn(result["readiness_v2"], {"reject", "inconclusive"})
            self.assertEqual(result["catalytic_swarm_0_v2"], "inconclusive")
            self.assertTrue(paths["control"].is_file())
            self.assertTrue(paths["readiness"].is_file())
            self.assertFalse(paths["canary"].exists())
            self.assertFalse(paths["attempt"].exists())

    def test_resilient_guarded_uses_named_canary_and_worker_boundaries(self) -> None:
        sidecar = object.__new__(holo.LiveSidecar)
        sidecar.wddm_policy = holo.WddmTelemetryPolicy()
        sidecar.require_active = mock.Mock()
        sidecar.exact_ownership = mock.Mock(return_value={"passed": True})
        sidecar.wait_for_fresh_wddm = mock.Mock(return_value={"telemetry": {}})

        self.assertEqual(
            sidecar.guarded("catalytic-parser-canary", lambda: "canary", timeout=1),
            "canary",
        )
        self.assertEqual(
            sidecar.guarded("cs0-w01", lambda: "worker", timeout=1),
            "worker",
        )
        boundaries = [call.args[0] for call in sidecar.wait_for_fresh_wddm.call_args_list]
        self.assertEqual(
            boundaries,
            [
                "before-parser-canary",
                "after-parser-canary",
                "before-each-worker-request:cs0-w01",
                "after-each-worker-request:cs0-w01",
            ],
        )

    def test_fresh_wddm_failure_records_compact_named_boundary_evidence(self) -> None:
        class Sampler:
            @staticmethod
            def telemetry_snapshot():
                return {
                    "failure_reason": "candidate-vram-telemetry-lost",
                    "admission_ready": False,
                    "transition_events": [{"kind": "hard-failure"}],
                    "freshness_boundaries": [{"boundary": "duplicated"}],
                }

        cases = (
            ("timeout-boundary", None, time.monotonic() - 1.0),
            (
                "hard-failure-boundary",
                holo.NeoLoopError("candidate-vram-telemetry-lost"),
                None,
            ),
        )
        for boundary, active_error, deadline_at in cases:
            with self.subTest(boundary=boundary):
                sidecar = object.__new__(holo.LiveSidecar)
                sidecar.wddm_policy = holo.WddmTelemetryPolicy()
                sidecar.sampler = Sampler()
                sidecar.wddm_freshness_boundaries = []
                sidecar.last_exact_ownership = None
                sidecar.require_active = mock.Mock(side_effect=active_error)
                sidecar.exact_ownership = mock.Mock(return_value={"passed": True})

                with self.assertRaises(holo.HoloStateReadinessError) as caught:
                    sidecar.wait_for_fresh_wddm(
                        boundary,
                        0.1,
                        deadline_at=deadline_at,
                    )

                record = caught.exception.evidence["freshness_boundary"]
                self.assertEqual(record["boundary"], boundary)
                self.assertFalse(record["passed"])
                self.assertEqual(sidecar.wddm_freshness_boundaries, [record])
                self.assertNotIn("transition_events", record["telemetry"])
                self.assertNotIn("freshness_boundaries", record["telemetry"])
                self.assertEqual(
                    record["telemetry"]["failure_reason"],
                    "candidate-vram-telemetry-lost",
                )

    def test_completed_request_boundary_error_retains_value(self) -> None:
        completed = {"accepted": True, "completion_tokens": 5}
        sidecar = object.__new__(holo.LiveSidecar)
        sidecar.wddm_policy = holo.WddmTelemetryPolicy()
        sidecar.require_active = mock.Mock()
        sidecar.exact_ownership = mock.Mock(return_value={"passed": True})
        sidecar.wait_for_fresh_wddm = mock.Mock(
            side_effect=[
                {"passed": True},
                holo.HoloStateReadinessError("post-boundary-failed"),
            ]
        )

        with self.assertRaises(holo.CompletedRequestBoundaryError) as caught:
            sidecar.guarded(
                "catalytic-parser-canary",
                lambda: completed,
                timeout=1,
            )

        error = caught.exception
        self.assertIs(error.completed_value, completed)
        self.assertTrue(error.request_completed)
        self.assertEqual(error.request_name, "catalytic-parser-canary")
        self.assertIsInstance(error.boundary_error, holo.HoloStateReadinessError)
        self.assertEqual(
            [call.args[0] for call in sidecar.wait_for_fresh_wddm.call_args_list],
            ["before-parser-canary", "after-parser-canary"],
        )

    def test_legacy_guarded_deadline_starts_after_pre_request_gates(self) -> None:
        sidecar = object.__new__(holo.LiveSidecar)
        sidecar.wddm_policy = None
        active_calls = 0

        def require_active(**_kwargs):
            nonlocal active_calls
            active_calls += 1
            if active_calls == 1:
                time.sleep(0.1)

        sidecar.require_active = mock.Mock(side_effect=require_active)
        sidecar.exact_ownership = mock.Mock(return_value={"passed": True})
        self.assertEqual(
            sidecar.guarded("legacy-budget", lambda: "complete", timeout=0.05),
            "complete",
        )
        self.assertEqual(active_calls, 2)

    def test_resilient_retirement_requires_exact_empty_pid_samples(self) -> None:
        cleanup = self.cleanup()
        cleanup.update({
            "wddm_resilience_active": True,
            "wddm": {"failure_reason": None},
            "retirement_samples": [
                {
                    "available": False,
                    "bytes": None,
                    "error": "no-matching-pid-instance",
                    "instances": [],
                }
                for _ in range(5)
            ],
        })
        self.assertTrue(holo.cleanup_integrity(cleanup, {42})["passed"])

        query_failed = copy.deepcopy(cleanup)
        query_failed["retirement_samples"][2]["error"] = "Get-Counter timeout"
        gate = holo.cleanup_integrity(query_failed, {42})
        self.assertFalse(gate["passed"])
        self.assertIn("WDDM-retirement-query-unproven", gate["reasons"])

    def test_v2_validator_rejects_identity_policy_path_and_retry_mutations(self) -> None:
        mutations = (
            (("schema_version",), 2.0),
            (("schema_version",), True),
            (
                (
                    "readiness_control",
                    "wddm_transient_gap_policy",
                    "transition_event_limit",
                ),
                511,
            ),
            (
                ("one_shot", "result_path"),
                "state/catalytic_swarm/result-v3.json",
            ),
            (("causal_intervention", "automatic_retry_allowed"), True),
            (("one_shot", "capability_retry_allowed"), True),
        )
        for keys, value in mutations:
            with self.subTest(keys=keys, value=value):
                changed = copy.deepcopy(self.v2_contract)
                target = changed
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(holo.NeoLoopError):
                    holo.validate_catalytic_swarm_0_v2(
                        changed,
                        self.contract,
                        self.protocol_v4,
                    )

    def terminal_wddm_cleanup(self, *, recovered_gap_count: int = 1) -> dict:
        policy = self.v2_contract["readiness_control"][
            "wddm_transient_gap_policy"
        ]
        telemetry_policy = holo.WddmTelemetryPolicy(
            initial_grace_seconds=policy["initial_attribution_grace_seconds"],
            max_consecutive_failures=policy[
                "maximum_tolerated_consecutive_unavailable_queries"
            ],
            max_valid_sample_gap_seconds=policy[
                "maximum_valid_sample_gap_seconds"
            ],
            admission_freshness_seconds=policy["admission_freshness_seconds"],
        )
        tracker = neo_loop.ResilientWddmTelemetry(
            ceiling_bytes=policy["memory_ceiling_mib"] * holo.MIB,
            policy=telemetry_policy,
            started_at=0.0,
            transition_event_limit=policy["transition_event_limit"],
        )
        exact_instance = "pid_99_luid_0x00000000_phys_0_eng_0_engtype_3d"
        observed_at = 0.1
        tracker.observe_valid(
            bytes_used=1234,
            instances=(exact_instance,),
            now=observed_at,
        )
        for index in range(recovered_gap_count):
            observed_at += 0.01
            tracker.observe_unavailable(
                f"Get-Counter télémétrie indisponible ☃ {index}",
                now=observed_at,
            )
            observed_at += 0.01
            tracker.observe_valid(
                bytes_used=1234,
                instances=(exact_instance,),
                now=observed_at,
            )
        snapshot = tracker.snapshot(now=observed_at + 0.001).to_dict()
        snapshot.update({
            "sampler_stop_attempted": True,
            "sampler_stop_timed_out": False,
            "sampler_stop_failure_reason": None,
            "sampler_thread_alive": False,
        })
        boundary_telemetry = {
            key: snapshot[key]
            for key in (
                "failure_reason",
                "admission_ready",
                "has_valid_sample",
                "consecutive_failures",
                "transient_gap_active",
                "last_valid_sample_age_seconds",
                "peak_bytes",
            )
        }
        boundary_names = [
            "readiness-admission",
            "before-parser-canary",
            "after-parser-canary",
            "before-capability-attempt",
            *[
                boundary
                for worker_id in self.v2_contract["plan"][
                    "fixed_execution_order"
                ]
                for boundary in (
                    f"before-each-worker-request:{worker_id}",
                    f"after-each-worker-request:{worker_id}",
                )
            ],
            "before-teardown",
        ]
        boundaries = [
            {
                "boundary": boundary,
                "passed": True,
                "telemetry": dict(boundary_telemetry),
            }
            for boundary in boundary_names
        ]
        return {
            "pid": 99,
            "wddm_resilience_active": True,
            "wddm": {
                "candidate_pid": 99,
                "source": (
                    "Windows GPU Process Memory Dedicated Usage (PID-filtered)"
                ),
                "sample_interval_seconds": policy["sample_interval_seconds"],
                "ceiling_mib": policy["memory_ceiling_mib"],
                "resilience_policy": {
                    "initial_grace_seconds": policy[
                        "initial_attribution_grace_seconds"
                    ],
                    "max_consecutive_failures": policy[
                        "maximum_tolerated_consecutive_unavailable_queries"
                    ],
                    "max_valid_sample_gap_seconds": policy[
                        "maximum_valid_sample_gap_seconds"
                    ],
                    "admission_freshness_seconds": policy[
                        "admission_freshness_seconds"
                    ],
                },
                "telemetry_snapshot": snapshot,
                "freshness_boundary_count": len(boundaries),
                "freshness_boundaries": boundaries,
            },
        }

    def test_terminal_wddm_reconciliation_accepts_tuple_unicode_and_fails_closed(self) -> None:
        cleanup = self.terminal_wddm_cleanup()
        events = cleanup["wddm"]["telemetry_snapshot"]["transition_events"]
        self.assertIsInstance(events, tuple)
        self.assertIn("☃", events[0]["reason"])
        accepted = holo.reconcile_v2_terminal_wddm(self.v2_contract, cleanup)
        self.assertTrue(accepted["passed"], accepted["reasons"])

        mutations = {
            "inconsistent": (
                "transition_ledger_sha256",
                "0" * 64,
                "wddm-terminal:transition_ledger_sha256",
            ),
            "truncated": (
                "transition_events_omitted",
                1,
                "wddm-terminal:transition_events_omitted",
            ),
            "active-gap": (
                "transient_gap_active",
                True,
                "wddm-terminal:transient_gap_active",
            ),
        }
        for name, (field, value, expected_reason) in mutations.items():
            with self.subTest(name=name):
                changed = copy.deepcopy(cleanup)
                changed["wddm"]["telemetry_snapshot"][field] = value
                gate = holo.reconcile_v2_terminal_wddm(
                    self.v2_contract,
                    changed,
                )
                self.assertFalse(gate["passed"])
                self.assertIn(expected_reason, gate["reasons"])

    def final_artifact_fixture(self) -> tuple[dict, dict, dict, list[dict]]:
        plan = holo.build_catalytic_swarm_0_plan()
        board_contract = self.v2_contract["blackboard"]
        board = holo.AppendOnlyBlackboard(
            max_entries=board_contract["max_entries"],
            max_entry_bytes=board_contract["max_entry_bytes"],
            max_references=board_contract["max_references"],
            max_parents=board_contract["max_parents"],
            max_artifacts=board_contract["max_artifacts"],
        )

        def worker_runner(spec, _context):
            return holo.expected_control_contribution(spec).to_dict()

        def verifier(spec, _contribution, _context):
            return holo.VerificationReceipt(
                worker_id=spec.worker_id,
                passed=True,
                checks=holo.REQUIRED_VERIFICATION_CHECKS,
                artifact_refs=(),
                verifier=holo.VERIFIER_ID,
            )

        swarm = holo.run_swarm(
            plan,
            worker_runner=worker_runner,
            verifier=verifier,
            blackboard=board,
        )
        persisted_board = board.snapshot()
        worker_results = []
        ledger_records: list[dict] = []
        request_ranges = {}
        global_index = 0
        for execution in swarm.executions:
            spec = execution.spec
            summary = {
                "record_type": "worker-summary",
                "worker_id": spec.worker_id,
                "ordinal": spec.ordinal,
                "phase": spec.phase,
                "lease_id": execution.lease_id,
                "assigned_parent_worker_ids": list(spec.parent_worker_ids),
                "visible_blackboard_entry_ids": list(
                    execution.visible_entry_ids
                ),
                "verification_receipt": execution.receipt.to_dict(),
                "created_blackboard_entry_id": execution.entry_id,
                "blackboard_head_hash": execution.blackboard_head_hash,
            }
            worker_results.append({
                "worker_id": spec.worker_id,
                "ordinal": spec.ordinal,
                "phase": spec.phase,
                "worker_summary": summary,
            })
            global_index += 1
            first_index = global_index
            ledger_records.append({
                "global_record_index": global_index,
                "request_sequence_index": spec.ordinal,
                "request_label": spec.worker_id,
                "record_type": "stream-event",
            })
            global_index += 1
            ledger_records.append({
                **summary,
                "global_record_index": global_index,
                "request_sequence_index": spec.ordinal,
                "request_label": spec.worker_id,
            })
            request_ranges[spec.worker_id] = {
                "request_sequence_index": spec.ordinal,
                "first_record_index": first_index,
                "last_record_index": global_index,
            }
        ledger_contract = self.v2_contract["stream_ledger"]
        result = {
            "blackboard": copy.deepcopy(persisted_board),
            "worker_results": worker_results,
            "swarm": swarm.to_dict(),
            "stream_ledger": {
                "failure": None,
                "within_limits": True,
                "sha256": "A" * 64,
                "path": ledger_contract["path"],
                "max_bytes": ledger_contract["max_bytes"],
                "max_records": ledger_contract["max_records"],
                "size_bytes": 1,
                "record_count": len(ledger_records),
                "request_ranges": request_ranges,
            },
        }
        return result, persisted_board, board.snapshot(), ledger_records

    def test_final_artifact_reconciliation_rejects_incomplete_proof_surfaces(self) -> None:
        result, persisted, in_memory, ledger_records = self.final_artifact_fixture()
        base = holo.reconcile_catalytic_final_artifacts(
            self.v2_contract,
            result,
            persisted,
            in_memory,
            ledger_records,
        )
        self.assertTrue(base["passed"], base["reasons"])

        genesis = holo.AppendOnlyBlackboard(max_entries=32).snapshot()
        genesis_result = copy.deepcopy(result)
        genesis_result["blackboard"] = copy.deepcopy(genesis)
        gate = holo.reconcile_catalytic_final_artifacts(
            self.v2_contract,
            genesis_result,
            genesis,
            genesis,
            ledger_records,
        )
        self.assertFalse(gate["passed"])
        self.assertTrue(gate["blackboard_chain_valid"])
        self.assertIn("blackboard-entry-count", gate["reasons"])

        stale_result = copy.deepcopy(result)
        stale_result["blackboard"] = genesis
        gate = holo.reconcile_catalytic_final_artifacts(
            self.v2_contract,
            stale_result,
            persisted,
            in_memory,
            ledger_records,
        )
        self.assertFalse(gate["passed"])
        self.assertIn("persisted-result-blackboard-mismatch", gate["reasons"])

        incomplete = copy.deepcopy(result)
        incomplete["worker_results"].pop()
        gate = holo.reconcile_catalytic_final_artifacts(
            self.v2_contract,
            incomplete,
            persisted,
            in_memory,
            ledger_records,
        )
        self.assertFalse(gate["passed"])
        self.assertIn("worker-result-count", gate["reasons"])

        missing_summary = copy.deepcopy(ledger_records)
        missing_summary[1]["record_type"] = "stream-event"
        gate = holo.reconcile_catalytic_final_artifacts(
            self.v2_contract,
            result,
            persisted,
            in_memory,
            missing_summary,
        )
        self.assertFalse(gate["passed"])
        self.assertIn("stream-ledger-worker-proof:cs0-w01", gate["reasons"])

    def test_large_terminal_wddm_evidence_is_single_copy_and_under_ceiling(self) -> None:
        cleanup = self.terminal_wddm_cleanup(recovered_gap_count=170)
        terminal_gate = holo.reconcile_v2_terminal_wddm(
            self.v2_contract,
            cleanup,
        )
        self.assertTrue(terminal_gate["passed"], terminal_gate["reasons"])
        self.assertEqual(terminal_gate["transition_event_count"], 510)

        result, _persisted, _in_memory, _ledger_records = (
            self.final_artifact_fixture()
        )
        result["cleanup"] = cleanup
        result["final_sidecar_telemetry"] = holo.compact_wddm_telemetry(
            cleanup["wddm"]
        )
        self.assertNotIn(
            "transition_events",
            result["final_sidecar_telemetry"]["telemetry_snapshot"],
        )
        self.assertNotIn("freshness_boundaries", result["final_sidecar_telemetry"])

        def count_key(value, key):
            if isinstance(value, dict):
                return (key in value) + sum(
                    count_key(item, key) for item in value.values()
                )
            if isinstance(value, (list, tuple)):
                return sum(count_key(item, key) for item in value)
            return 0

        self.assertEqual(count_key(result, "transition_events"), 1)
        self.assertEqual(count_key(result, "freshness_boundaries"), 1)
        self.assertLess(len(holo.canonical_json_bytes(result)), 2 * holo.MIB)

    def test_validator_rejects_weakened_nested_control_laws(self) -> None:
        mutations = (
            (("connector", "source_hash_authority"), "unprotected"),
            (("connector", "undeclared"), True),
            (("root_and_prior_evidence", "undeclared"), True),
            (("transport", "lane", "undeclared"), True),
            (("structured_output", "verifier", "id"), "other"),
            (("transport", "lane", "requires", "empty_tool_calls"), False),
            (("parser_canary", "requires", "valid_json"), False),
            (("communication", "complete_sse_streams_in_worker_context"), True),
            (("blackboard", "genesis_hash"), "1" * 64),
            (("stream_ledger", "worker_summary_fields"), []),
            (("stable_isolation", "stable_health_required"), False),
            (("one_shot", "capability_claim_requires_frozen_readiness_pass"), False),
            (("cleanup", "runtime_removed"), False),
            (("availability", "SOTA_SWARM_CLAIM"), "UNLOCKED"),
        )
        for keys, value in mutations:
            with self.subTest(keys=keys):
                changed = copy.deepcopy(self.contract)
                target = changed
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(holo.NeoLoopError):
                    holo.validate_catalytic_swarm_0(changed, self.protocol_v4)

    def test_preclaim_requires_checked_out_main_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            self.patch_paths(stack, Path(temp))
            evaluator = copy.deepcopy(self.evaluator)
            evaluator.pop("catalytic_swarm_0_evidence", None)
            lock = {
                "holostate_worker_protocol_v4_sha256": self.contract[
                    "root_and_prior_evidence"
                ]["holostate_worker_protocol_v4_sha256"],
                "holostate_worker_protocol_v4_evidence_sha256": self.contract[
                    "root_and_prior_evidence"
                ]["holostate_worker_protocol_v4_evidence_sha256"],
            }
            stack.enter_context(mock.patch.object(
                holo,
                "load_locked_catalytic_swarm_0",
                return_value=(
                    evaluator,
                    evaluator["holostate_live_contract"],
                    self.protocol_v4,
                    self.contract,
                    lock,
                ),
            ))
            stack.enter_context(mock.patch.object(
                holo, "preserved_catalytic_v4_evidence", return_value={},
            ))
            stack.enter_context(mock.patch.object(
                holo, "git_read", return_value="detached-or-alias",
            ))
            network = stack.enter_context(mock.patch.object(holo, "request_json"))
            with self.assertRaisesRegex(holo.NeoLoopError, "checked-out branch main"):
                holo.prepare_catalytic_swarm_0_claim(
                    SimpleNamespace(binary="x", model="y")
                )
            network.assert_not_called()

    def test_all_seven_collisions_refuse_before_loader_or_network(self) -> None:
        for collision in range(7):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                paths = self.patch_paths(stack, Path(temp))
                list(paths.values())[collision].write_text("{}", encoding="utf-8")
                loader = stack.enter_context(mock.patch.object(holo, "load_locked_catalytic_swarm_0"))
                network = stack.enter_context(mock.patch.object(holo, "request_json"))
                with self.assertRaises(holo.NeoLoopError):
                    holo.prepare_catalytic_swarm_0_claim(SimpleNamespace(binary="x", model="y"))
                loader.assert_not_called()
                network.assert_not_called()

    def test_control_failure_creates_no_later_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            paths = self.patch_paths(stack, Path(temp))
            stack.enter_context(mock.patch.object(holo, "prepare_catalytic_swarm_0_claim", return_value=self.preclaim(Path(temp))))
            stack.enter_context(mock.patch.object(
                holo,
                "qualify_catalytic_control_outputs",
                return_value={"passed": False, "reasons": ["forced"], "generation_executed": False},
            ))
            result = holo.run_catalytic_swarm_0_audit(SimpleNamespace(binary="x", model="y"))
            self.assertEqual(result["control_qualification_v1"], "reject")
            self.assertEqual(result["STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")
            self.assertEqual(result["CATALYTIC_SWARM_CONTROL_AVAILABLE"], "LOCKED")
            self.assertTrue(paths["control"].is_file())
            durable = json.loads(paths["control"].read_text(encoding="utf-8"))
            self.assertEqual(durable["catalytic_swarm_0"], "instrumentation-reject")
            self.assertEqual(durable["CATALYTIC_SWARM_CONTROL_AVAILABLE"], "LOCKED")
            self.assertFalse(any(paths[key].exists() for key in list(paths)[1:]))

    def test_readiness_failure_creates_no_canary_or_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            paths = self.patch_paths(stack, Path(temp))
            preclaim = self.preclaim(Path(temp))
            stack.enter_context(mock.patch.object(holo, "prepare_catalytic_swarm_0_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo, "qualify_catalytic_control_outputs", return_value={"passed": True, "reasons": [], "generation_executed": False}
            ))
            stack.enter_context(mock.patch.object(holo, "query_listener_pids", return_value=self.query({42, 43})))
            stack.enter_context(mock.patch.object(holo, "readiness_v3_no_sidecar_cleanup", return_value={"not_launched": True}))
            stack.enter_context(mock.patch.object(holo, "cleanup_integrity", return_value={"passed": True, "reasons": []}))
            result = holo.run_catalytic_swarm_0_audit(SimpleNamespace(binary="x", model="y"))
            self.assertIn(result["readiness_v1"], {"reject", "inconclusive"})
            self.assertEqual(result["STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")
            self.assertEqual(result["CATALYTIC_SWARM_CONTROL_AVAILABLE"], "LOCKED")
            self.assertTrue(paths["control"].exists())
            self.assertTrue(paths["readiness"].exists())
            durable = json.loads(paths["readiness"].read_text(encoding="utf-8"))
            self.assertEqual(durable["catalytic_swarm_0"], "inconclusive")
            self.assertEqual(durable["STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")
            self.assertFalse(paths["canary"].exists())
            self.assertFalse(paths["attempt"].exists())

    def test_parser_canary_failure_creates_no_attempt_ledger_or_blackboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            paths = self.patch_paths(stack, Path(temp))
            preclaim = self.preclaim(Path(temp))
            stack.enter_context(mock.patch.object(holo, "prepare_catalytic_swarm_0_claim", return_value=preclaim))
            stack.enter_context(mock.patch.object(
                holo, "qualify_catalytic_control_outputs", return_value={"passed": True, "reasons": [], "generation_executed": False}
            ))
            stack.enter_context(mock.patch.object(holo, "query_listener_pids", return_value=self.query({42})))
            stack.enter_context(mock.patch.object(holo, "health_ok", return_value=True))
            stack.enter_context(mock.patch.object(holo, "LiveSidecar", self.FakeSidecar))
            stack.enter_context(mock.patch.object(
                holo,
                "prepare_catalytic_root",
                return_value=("root", {"state_id": "state", "system_message_sha256": self.contract["root_and_prior_evidence"]["system_message_sha256"]}),
            ))
            stack.enter_context(mock.patch.object(
                holo,
                "run_worker_v4_chat_request",
                return_value={"accepted": True},
            ))
            stack.enter_context(mock.patch.object(holo, "worker_resource_gate", return_value={"passed": True}))
            stack.enter_context(mock.patch.object(
                holo,
                "run_catalytic_parser_canary",
                return_value={"accepted": False, "gate_reasons": ["forced"]},
            ))
            stack.enter_context(mock.patch.object(holo, "safe_sidecar_cleanup", return_value=self.cleanup()))
            result = holo.run_catalytic_swarm_0_audit(SimpleNamespace(binary="x", model="y"))
            self.assertEqual(result["parser_canary_v1"], "reject")
            self.assertEqual(result["STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE"], "LOCKED")
            self.assertEqual(result["CATALYTIC_SWARM_CONTROL_AVAILABLE"], "LOCKED")
            self.assertTrue(paths["canary"].exists())
            durable = json.loads(paths["canary"].read_text(encoding="utf-8"))
            self.assertEqual(durable["CATALYTIC_SWARM_CONTROL_AVAILABLE"], "LOCKED")
            self.assertFalse(paths["attempt"].exists())
            self.assertFalse(paths["ledger"].exists())
            self.assertFalse(paths["blackboard"].exists())

    def test_post_launch_artifact_claim_collisions_always_cleanup(self) -> None:
        for target in ("canary", "attempt", "result", "blackboard"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                paths, cleanup, _canary = self.install_live_stage(stack, Path(temp))
                original = holo.claim_catalytic_runtime_json_once

                def claim(path, payload, *, max_bytes=2 * holo.MIB):
                    if path == paths[target]:
                        raise holo.NeoLoopError(f"forced-{target}-collision")
                    return original(path, payload, max_bytes=max_bytes)

                stack.enter_context(mock.patch.object(
                    holo, "claim_catalytic_runtime_json_once", side_effect=claim,
                ))
                with self.assertRaises(holo.NeoLoopError):
                    holo.run_catalytic_swarm_0_audit(
                        SimpleNamespace(binary="x", model="y")
                    )
                cleanup.assert_called()
                self.assertFalse(paths["ledger"].exists())
                if target in {"result", "blackboard"}:
                    durable = json.loads(
                        paths["attempt"].read_text(encoding="utf-8")
                    )
                    self.assertEqual(durable["catalytic_swarm_0"], "inconclusive")
                    self.assertEqual(
                        durable["CATALYTIC_SWARM_CONTROL_AVAILABLE"], "LOCKED"
                    )

    def test_ledger_claim_failure_cleans_sidecar_and_persists_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            paths, cleanup, _canary = self.install_live_stage(stack, Path(temp))
            preclaim = self.preclaim(Path(temp))
            stack.enter_context(mock.patch.object(
                holo, "BoundedStreamLedger",
                side_effect=holo.NeoLoopError("stream-ledger-ceiling-exceeded"),
            ))

            def git_value(root, *args):
                if args == ("branch", "--show-current"):
                    return "feature-after-launch"
                if args[0] == "status":
                    return ""
                if Path(root) == preclaim["candidate_root"]:
                    return "CANDIDATE"
                return "HEAD"

            stack.enter_context(mock.patch.object(holo, "git_read", side_effect=git_value))
            stack.enter_context(mock.patch.object(
                holo, "preserved_catalytic_v4_evidence",
                return_value=preclaim["prior_before"],
            ))
            result = holo.run_catalytic_swarm_0_audit(
                SimpleNamespace(binary="x", model="y")
            )
            cleanup.assert_called()
            self.assertEqual(result["catalytic_swarm_0"], "instrumentation-reject")
            self.assertIn("stable-branch-changed", result["isolation_gate"]["reasons"])
            self.assertEqual(result["final_sidecar_telemetry"], self.cleanup()["wddm"])
            self.assertEqual(result["maximum_host_private_growth_bytes"], 10)
            self.assertTrue(paths["result"].is_file())
            self.assertEqual(
                json.loads(paths["result"].read_text(encoding="utf-8"))["status"],
                "complete",
            )

    def test_warm_failure_leaves_parser_unattempted_and_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            paths, _cleanup, canary = self.install_live_stage(
                stack, Path(temp), warm_accepted=False,
            )
            result = holo.run_catalytic_swarm_0_audit(
                SimpleNamespace(binary="x", model="y")
            )
            artifact = json.loads(paths["canary"].read_text(encoding="utf-8"))
            self.assertEqual(result["parser_canary_v1"], "inconclusive")
            self.assertEqual(result["STRUCTURED_HOLOSTATE_MICROWORKER"], "inconclusive")
            self.assertTrue(artifact["warm_attempted"])
            self.assertTrue(artifact["warm_executed"])
            self.assertFalse(artifact["parser_canary_attempted"])
            self.assertIsNotNone(artifact["warm_A"])
            canary.assert_not_called()

    def test_executed_parser_failure_is_reject_with_partial_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            paths, _cleanup, _canary = self.install_live_stage(
                stack, Path(temp), canary_accepted=False,
            )
            result = holo.run_catalytic_swarm_0_audit(
                SimpleNamespace(binary="x", model="y")
            )
            artifact = json.loads(paths["canary"].read_text(encoding="utf-8"))
            self.assertEqual(result["parser_canary_v1"], "reject")
            self.assertEqual(result["STRUCTURED_HOLOSTATE_MICROWORKER"], "reject")
            self.assertTrue(artifact["parser_canary_attempted"])
            self.assertTrue(artifact["parser_canary_executed"])
            self.assertIsNotNone(artifact["parser_canary"])
            self.assertIn("preclaim_stream_provenance", artifact)

    def test_failure_and_transport_classifiers_are_fail_closed(self) -> None:
        self.assertEqual(
            holo.catalytic_worker_failure_classification(RuntimeError("unknown")),
            "inconclusive",
        )
        self.assertEqual(
            holo.catalytic_worker_failure_classification("WDDM telemetry lost"),
            "inconclusive",
        )
        self.assertEqual(
            holo.catalytic_worker_failure_classification("stream-ledger-invalid"),
            "instrumentation-reject",
        )
        self.assertEqual(
            holo.catalytic_transport_failure_classification(
                ["exact-control-content-mismatch", "top-level-transport-not-accepted"],
                {},
            ),
            "capability-reject",
        )
        self.assertEqual(
            holo.catalytic_transport_failure_classification(
                ["visible-token-evidence-missing"], {},
            ),
            "instrumentation-reject",
        )
        self.assertEqual(
            holo.catalytic_transport_failure_classification(
                ["prompt-reuse-evidence-invalid"],
                {
                    "logical_prompt_tokens": 100,
                    "cached_prompt_tokens": 0,
                    "fresh_prompt_tokens": 100,
                    "prompt_token_identity_matches": True,
                },
            ),
            "capability-reject",
        )
        self.assertEqual(
            holo.catalytic_transport_failure_classification(
                ["prompt-reuse-evidence-invalid"],
                {
                    "logical_prompt_tokens": 100,
                    "cached_prompt_tokens": 90,
                    "fresh_prompt_tokens": 9,
                    "prompt_token_identity_matches": False,
                },
            ),
            "instrumentation-reject",
        )

    def test_resource_summary_includes_warm_canary_and_workers(self) -> None:
        summary = holo.catalytic_resource_summary(
            {
                "warm_A": {"resource_gate": {"host_private_growth_bytes": 30}},
                "parser_canary": {
                    "resource_gate": {"host_private_growth_bytes": 50}
                },
            },
            [
                {
                    "measurement": {
                        "resource_gate": {"host_private_growth_bytes": 40}
                    }
                }
            ],
        )
        self.assertEqual(summary["maximum_host_private_growth_bytes"], 50)
        self.assertEqual(summary["resource_gate_observation_count"], 3)

    def test_swallowed_verifier_failure_preserves_runtime_and_receipt(self) -> None:
        plan = holo.build_catalytic_swarm_0_plan()
        contribution = holo.expected_control_contribution(plan.logical_workers[0])

        class Transport:
            accepted = True
            reasons = ()

            @staticmethod
            def to_dict():
                return {
                    "accepted": True,
                    "content_sha256": "A" * 64,
                    "token_claim_scope": "exact-generated-token-sequence",
                }

        class Ledger:
            def __init__(self):
                self.records = []

            def append(self, record, **kwargs):
                self.records.append(record)

        sidecar = self.FakeSidecar()
        result = {"worker_results": []}
        board = holo.AppendOnlyBlackboard(max_entries=32)
        ledger = Ledger()
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            v1_blackboard = root / "blackboard-v1.json"
            v2_blackboard = root / "blackboard-v2.json"
            v2_result = root / "result-v2.json"
            v1_blackboard.write_text("immutable-v1", encoding="utf-8")
            writes: list[Path] = []

            def record_write(path, _value, **_kwargs):
                writes.append(Path(path))

            stack.enter_context(mock.patch.object(
                holo, "run_worker_v4_chat_request", return_value={"accepted": True},
            ))
            stack.enter_context(mock.patch.object(
                holo, "worker_resource_gate", return_value={"passed": True},
            ))
            stack.enter_context(mock.patch.object(
                holo, "validate_fast_transport", return_value=Transport(),
            ))
            stack.enter_context(mock.patch.object(
                holo, "parse_structured_fast_result",
                return_value=(Transport(), contribution),
            ))
            stack.enter_context(mock.patch.object(
                holo, "write_catalytic_runtime_json", side_effect=record_write,
            ))
            swarm = holo.execute_catalytic_swarm_sequence(
                sidecar,
                {"process_memory": {"private_bytes": 1}},
                self.protocol_v4,
                self.contract,
                "root",
                {"state_id": "state"},
                ledger,
                board,
                result,
                result_path=v2_result,
                blackboard_path=v2_blackboard,
            )
            v1_blackboard_after = v1_blackboard.read_text(encoding="utf-8")
        self.assertNotEqual(swarm.verdict, "reviewable-accept")
        self.assertEqual(result["failure_classification"], "capability-reject")
        self.assertEqual(len(result["worker_results"]), 1)
        self.assertFalse(result["worker_failure"]["verification_receipt"]["passed"])
        self.assertEqual(result["worker_failure"]["visible_blackboard_entry_ids"], [])
        self.assertTrue(any(item["record_type"] == "worker-failure" for item in ledger.records))
        self.assertIn(v2_blackboard, writes)
        self.assertNotIn(v1_blackboard, writes)
        self.assertEqual(v1_blackboard_after, "immutable-v1")


if __name__ == "__main__":
    unittest.main()
