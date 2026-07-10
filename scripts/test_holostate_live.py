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
                "audit-worker-protocol-v2",
            },
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
            }),
            10,
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


if __name__ == "__main__":
    unittest.main()
