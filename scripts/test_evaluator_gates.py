#!/usr/bin/env python3
"""Focused regression tests for split transport, reasoning, and warm-performance gates."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from catalytic_swarm_advantage_protocol import (
    ONE_SHOT_PATHS as CATALYTIC_SWARM_1_PATHS,
    build_catalytic_swarm_1_contract,
)
from catalytic_swarm_1_cache_diagnostic_protocol import (
    ONE_SHOT_PATHS as CACHE_DIAGNOSTIC_PATHS,
    build_cache_diagnostic_contract,
)
from catalytic_swarm_1_v2_protocol import (
    DIAGNOSTIC_EVIDENCE_SHA256,
    EXPECTED_CONTRACT_SHA256,
    build_cache_diagnostic_evidence_binding,
    build_catalytic_swarm_1_v2_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


harness = load_module("baseline_harness_under_test", ROOT / "scripts" / "baseline_harness.py")
neo_loop = load_module("neo_loop_gates_under_test", ROOT / "scripts" / "neo_loop.py")
EVALUATOR = json.loads((ROOT / "lab" / "EVALUATOR.json").read_text(encoding="utf-8"))


def payload(disable_thinking: bool = False, tool_test: bool = False):
    return harness.build_request_payload(
        "agents-a1", "Reply with exactly: NEO3000 ONLINE", 0.0, 64, False, tool_test, disable_thinking
    )


def report(*, exact: bool = True, reasoning: str = "reason", content: str = "NEO3000 ONLINE", tps: float = 12.0):
    return {
        "summary": {"all_http_200": True, "all_streamed_multiple_events": True, "median_reported_tokens_per_second": tps},
        "exact_response_passed": exact,
        "measurements": [{"reasoning_content": reasoning, "content": content}],
    }


class HarnessTransportTests(unittest.TestCase):
    def test_disable_thinking_inserts_only_the_documented_override(self) -> None:
        request = payload(disable_thinking=True)
        self.assertEqual(request["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(request["model"], "agents-a1")
        self.assertEqual(request["max_tokens"], 64)
        self.assertTrue(request["stream"])

    def test_default_mode_has_no_override(self) -> None:
        request = payload()
        self.assertNotIn("chat_template_kwargs", request)
        self.assertEqual(harness.thinking_metadata(request)["thinking_mode"], "auto")

    def test_tool_mode_stays_unchanged_without_explicit_override(self) -> None:
        request = payload(tool_test=True)
        self.assertEqual(request["tool_choice"], "required")
        self.assertIn("tools", request)
        self.assertNotIn("chat_template_kwargs", request)

    def test_effective_mode_metadata_is_recordable(self) -> None:
        self.assertEqual(harness.thinking_metadata(payload(disable_thinking=True)), {
            "thinking_mode": "disabled", "chat_template_kwargs": {"enable_thinking": False},
        })


class EvaluatorGateTests(unittest.TestCase):
    def test_protected_hash_is_checkout_eol_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lf = root / "lf.txt"
            crlf = root / "crlf.txt"
            lf.write_bytes(b"alpha\nbeta\n")
            crlf.write_bytes(b"alpha\r\nbeta\r\n")
            self.assertEqual(
                neo_loop.sha256_protected_text_file(lf),
                neo_loop.sha256_protected_text_file(crlf),
            )

    def test_protected_lock_rejects_missing_or_unknown_text_hash_mode(self) -> None:
        lock = neo_loop.load_json(neo_loop.LOCK_PATH)
        for mode in (None, "raw-bytes-v1"):
            changed = copy.deepcopy(lock)
            changed["protected_text_hash_mode"] = mode
            with mock.patch.object(neo_loop, "load_json", return_value=changed):
                with self.assertRaisesRegex(
                    neo_loop.NeoLoopError, "unsupported protected text hash mode"
                ):
                    neo_loop.verify_lock(EVALUATOR)

    def test_failed_preflight_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            results = Path(temp) / "results.jsonl"
            with mock.patch.object(
                neo_loop.sys, "argv", ["neo_loop.py", "--preflight"]
            ), mock.patch.object(
                neo_loop, "load_json", side_effect=neo_loop.NeoLoopError("blocked")
            ), mock.patch.object(
                neo_loop, "RESULTS_PATH", results
            ), mock.patch("builtins.print"):
                self.assertEqual(neo_loop.main(), 1)
            self.assertFalse(results.exists())

    def test_full_canonical_gate_identity_changes_hash(self) -> None:
        baseline = neo_loop.gate_definition_hashes(EVALUATOR)
        mutations = [
            ("transport", "max_tokens", 65),
            ("transport", "expected_content", "WRONG"),
            ("transport", "thinking_mode", "auto"),
            ("transport", "chat_template_kwargs", None),
            ("reasoning", "reasoning_required", False),
            ("warm_performance", "performance_scored", False),
            ("warm_performance", "warmup_count", 2),
            ("warm_performance", "min_decode_tps", 9.0),
        ]
        for gate, field, value in mutations:
            changed = copy.deepcopy(EVALUATOR)
            changed["gates"][gate][field] = value
            self.assertNotEqual(baseline, neo_loop.gate_definition_hashes(changed), field)

    def test_reasoning_gate_rejects_empty_reasoning_and_missing_final_content(self) -> None:
        gate = EVALUATOR["gates"]["reasoning"]
        self.assertFalse(neo_loop.validate_gate(report(reasoning=""), gate, False)[0])
        self.assertFalse(neo_loop.validate_gate(report(exact=False, content=""), gate, False)[0])

    def test_transport_rejects_reasoning_only_or_wrong_final_content(self) -> None:
        gate = EVALUATOR["gates"]["transport"]
        self.assertFalse(neo_loop.validate_gate(report(exact=False, reasoning="reason", content=""), gate, False)[0])
        self.assertFalse(neo_loop.validate_gate(report(exact=False, content="WRONG"), gate, False)[0])

    def test_repeat_uses_disabled_thinking_while_reasoning_keeps_auto(self) -> None:
        repeat_args = neo_loop.gate_harness_args(EVALUATOR["gates"]["repeat"], 3, 300)
        reasoning_args = neo_loop.gate_harness_args(EVALUATOR["gates"]["reasoning"], 1, 300)
        self.assertIn("--disable-thinking", repeat_args)
        self.assertNotIn("--disable-thinking", reasoning_args)

    def test_warmup_is_unscored_but_counted_run_keeps_ten_tps_floor(self) -> None:
        gate = EVALUATOR["gates"]["warm_performance"]
        slow = report(tps=9.9)
        self.assertTrue(neo_loop.validate_gate(slow, gate, False)[0])
        self.assertFalse(neo_loop.validate_gate(slow, gate, True)[0])
        self.assertEqual(gate["min_decode_tps"], 10.0)

    def test_catalytic_swarm_complete_object_hash_covers_execution_law(self) -> None:
        baseline = neo_loop.catalytic_swarm_0_hash(EVALUATOR)
        mutations = [
            (("plan", "physical_slot_count"), 2),
            (("plan", "definition", "logical_workers", 0, "max_tokens"), 65),
            (("parser_canary", "expected_content"), "{}"),
            (("blackboard", "max_entries"), 33),
            (("one_shot", "capability_retry_allowed"), True),
            (("availability", "automatic_promotion"), True),
        ]
        for path, value in mutations:
            changed = copy.deepcopy(EVALUATOR)
            cursor = changed["catalytic_swarm_0"]
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            self.assertNotEqual(baseline, neo_loop.catalytic_swarm_0_hash(changed), path)

    def test_catalytic_swarm_v2_is_a_complete_v1_successor(self) -> None:
        v1 = EVALUATOR["catalytic_swarm_0"]
        v2 = EVALUATOR["catalytic_swarm_0_v2"]
        self.assertEqual(list(v2), [
            "id",
            "schema_version",
            "attempt_version",
            "connector",
            "predecessor_v1",
            "causal_intervention",
            "control_objective",
            "plan",
            "root_and_prior_evidence",
            "transport",
            "structured_output",
            "parser_canary",
            "communication",
            "blackboard",
            "stream_ledger",
            "readiness_control",
            "memory",
            "stable_isolation",
            "one_shot",
            "cleanup",
            "stop_law",
            "verdicts",
            "availability",
            "automatic_promotion",
        ])
        self.assertEqual(v2["id"], "catalytic_swarm_0_v2")
        self.assertEqual(v2["schema_version"], 2)
        self.assertEqual(v2["attempt_version"], 2)
        self.assertEqual(
            v2["causal_intervention"]["sole_intervention"],
            "Bounded exact-PID WDDM transient-gap resilience plus fresh-sample boundary admission.",
        )
        self.assertTrue(v2["causal_intervention"]["inherits_complete_v1_control_object"])
        self.assertFalse(v2["causal_intervention"]["automatic_retry_allowed"])

        for key in (
            "control_objective",
            "plan",
            "root_and_prior_evidence",
            "transport",
            "structured_output",
            "parser_canary",
            "communication",
            "memory",
            "stable_isolation",
            "cleanup",
            "stop_law",
            "availability",
            "automatic_promotion",
        ):
            self.assertEqual(v2[key], v1[key], key)

        expected_blackboard = copy.deepcopy(v1["blackboard"])
        expected_blackboard["path"] = "state/catalytic_swarm/blackboard-v2.json"
        self.assertEqual(v2["blackboard"], expected_blackboard)
        expected_ledger = copy.deepcopy(v1["stream_ledger"])
        expected_ledger["path"] = "state/catalytic_swarm/ledger-v2.jsonl"
        self.assertEqual(v2["stream_ledger"], expected_ledger)

        expected_verdicts = copy.deepcopy(v1["verdicts"])
        expected_verdicts["catalytic_swarm_0_v2"] = expected_verdicts.pop("catalytic_swarm_0")
        self.assertEqual(v2["verdicts"], expected_verdicts)

    def test_catalytic_swarm_v2_binds_v1_evidence_and_connector_authority(self) -> None:
        v2 = EVALUATOR["catalytic_swarm_0_v2"]
        self.assertEqual(v2["connector"], {
            "branch": "codex/catalytic-swarm-wddm-v2",
            "head": "428edaaa2772d6805c4733a9d629a7812838a932",
            "protected_base": "3fcef46c4863814f3396d1466269d4a3ef0f8c9a",
            "connector_commit_count": 2,
            "imported_as_single_architectural_commit": True,
            "files": [
                "scripts/wddm_telemetry_resilience.py",
                "scripts/test_wddm_telemetry_resilience.py",
            ],
            "source_hash_authority": "lab/EVALUATOR.lock.json protected_file_hashes",
        })
        self.assertEqual(v2["predecessor_v1"], {
            "id": "catalytic_swarm_0",
            "integration_commit": "8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280",
            "evidence_commit": "3fcef46c4863814f3396d1466269d4a3ef0f8c9a",
            "contract_sha256": "ca8987fd5d8f1d3043a2c78147e2ec6f2ab8006cccfc4c958398ba8f7d0a9cd4",
            "evidence_object_sha256": "1e8bc8416e1a772f14cfebd39ce98850c61b2ff3cc8ed57a1953c4521445a426",
            "artifacts": {
                "state/catalytic_swarm/control-qualification-v1.json": "864F74F58792E120422BB4078439E40AAE96546D58282DED38BB7665678A3E53",
                "state/catalytic_swarm/readiness-v1.json": "76351D413785D6E239F1E20FB152EDF78DF312EEBE85D86FC343C6B25D7C1CCC",
            },
            "control_qualification": "pass",
            "readiness": "inconclusive",
            "capability_attempt_created": False,
            "logical_workers_executed": 0,
            "retry_allowed": False,
            "immutable_prior_evidence": True,
        })
        for path in v2["connector"]["files"]:
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])

    def test_catalytic_swarm_v2_only_changes_readiness_by_declared_policy(self) -> None:
        v1 = EVALUATOR["catalytic_swarm_0"]["readiness_control"]
        v2 = copy.deepcopy(EVALUATOR["catalytic_swarm_0_v2"]["readiness_control"])
        policy = v2.pop("wddm_transient_gap_policy")
        boundary = v2.pop("fresh_sample_boundary_law")
        admission_additions = {}
        for key in (
            "WDDM_failure_reason_must_be_none",
            "fresh_exact_WDDM_PID_sample_required",
            "maximum_WDDM_sample_age_seconds",
            "consecutive_WDDM_failures_required",
        ):
            admission_additions[key] = v2["admission_law"].pop(key)
        self.assertEqual(v2, v1)
        self.assertEqual(admission_additions, {
            "WDDM_failure_reason_must_be_none": True,
            "fresh_exact_WDDM_PID_sample_required": True,
            "maximum_WDDM_sample_age_seconds": 5.0,
            "consecutive_WDDM_failures_required": 0,
        })

        self.assertEqual(policy, {
            "measurement_source": "Windows GPU Process Memory(*)\\Dedicated Usage",
            "exact_pid_instance_prefix": "pid_<sidecar PID>_",
            "exact_pid_instances_only": True,
            "sample_interval_seconds": 1.0,
            "initial_attribution_grace_seconds": 60.0,
            "maximum_tolerated_consecutive_unavailable_queries": 2,
            "hard_failure_on_consecutive_unavailable_query": 3,
            "maximum_valid_sample_gap_seconds": 30.0,
            "admission_freshness_seconds": 5.0,
            "memory_ceiling_mib": 6000,
            "ceiling_violation_policy": "immediate-hard-failure",
            "bounded_error_metadata_required": True,
            "transient_failure_reason_before_hard_failure": None,
            "active_transient_gap_admission_ready": False,
            "valid_recovery_resets_failure_streak": True,
            "valid_recovery_recorded": True,
            "aggregate_nvidia_smi_fallback": "forbidden",
            "device_wide_fallback": "forbidden",
            "state_methods": [
                "has_valid_sample",
                "has_fresh_valid_sample",
                "failure_reason",
                "telemetry_snapshot",
            ],
            "transition_event_kinds": [
                "gap-start",
                "unavailable",
                "recovery",
                "hard-failure",
            ],
            "transition_event_limit": 512,
            "transition_full_ledger_required_at_terminal": True,
            "transition_overflow_policy": "immediate-hard-failure",
            "transition_reason_max_characters": 256,
            "transition_reason_sha256_required": True,
            "sampler_query_timeout_seconds": 10.0,
            "sampler_stop_margin_seconds": 2.0,
            "sampler_stop_timeout_seconds": 12.0,
            "sampler_thread_still_alive_policy": "hard-failure-and-non-accept",
            "retirement_sample_error_required": "no-matching-pid-instance",
            "retirement_query_failures_policy": "cleanup-failure-and-inconclusive",
        })
        self.assertEqual(boundary, {
            "wait_method": "wait_for_fresh_wddm",
            "maximum_wait_seconds": 30.0,
            "boundaries": [
                "readiness-admission",
                "before-parser-canary",
                "after-parser-canary",
                "before-capability-attempt",
                "before-each-worker-request",
                "after-each-worker-request",
                "before-teardown",
            ],
            "active_transient_gap_blocks_model_requests": True,
            "admission_requirements": {
                "failure_reason": None,
                "fresh_exact_pid_sample_required": True,
                "maximum_last_valid_sample_age_seconds": 5.0,
                "consecutive_failures": 0,
                "memory_mib_at_or_below": 6000,
            },
            "continuous_checks_during_wait": [
                "sidecar-process-liveness",
                "stable-health",
                "sidecar-health",
                "listener-ownership",
                "readiness-or-request-deadline",
                "hard-WDDM-failure",
            ],
            "deadline_law": "Stop at the earliest boundary deadline, request deadline, hard WDDM failure, or valid-sample gap over 30 seconds.",
        })

    def test_catalytic_swarm_v2_uses_only_v2_one_shot_paths(self) -> None:
        v1 = EVALUATOR["catalytic_swarm_0"]["one_shot"]
        v2 = EVALUATOR["catalytic_swarm_0_v2"]["one_shot"]
        expected = copy.deepcopy(v1)
        paths = {
            "control_qualification_path": "state/catalytic_swarm/control-qualification-v2.json",
            "readiness_path": "state/catalytic_swarm/readiness-v2.json",
            "parser_canary_path": "state/catalytic_swarm/parser-canary-v2.json",
            "attempt_path": "state/catalytic_swarm/attempt-v2.json",
            "result_path": "state/catalytic_swarm/result-v2.json",
            "ledger_path": "state/catalytic_swarm/ledger-v2.jsonl",
            "blackboard_path": "state/catalytic_swarm/blackboard-v2.json",
        }
        expected.update(paths)
        expected["control_failure_artifacts"] = [paths["control_qualification_path"]]
        expected["readiness_failure_artifacts"] = [
            paths["control_qualification_path"],
            paths["readiness_path"],
        ]
        expected["parser_canary_failure_artifacts"] = [
            paths["control_qualification_path"],
            paths["readiness_path"],
            paths["parser_canary_path"],
        ]
        self.assertEqual(v2, expected)
        self.assertFalse(any("-v1." in path for path in paths.values()))

    def test_catalytic_swarm_v2_complete_object_hash_covers_successor_law(self) -> None:
        baseline = neo_loop.catalytic_swarm_0_v2_hash(EVALUATOR)
        mutations = [
            (("predecessor_v1", "evidence_object_sha256"), "0" * 64),
            (("causal_intervention", "automatic_retry_allowed"), True),
            (("plan", "physical_slot_count"), 2),
            (("parser_canary", "expected_content"), "{}"),
            (("readiness_control", "wddm_transient_gap_policy", "maximum_tolerated_consecutive_unavailable_queries"), 3),
            (("readiness_control", "wddm_transient_gap_policy", "admission_freshness_seconds"), 6.0),
            (("readiness_control", "wddm_transient_gap_policy", "transition_event_limit"), 511),
            (("readiness_control", "wddm_transient_gap_policy", "sampler_stop_timeout_seconds"), 11.0),
            (("readiness_control", "fresh_sample_boundary_law", "active_transient_gap_blocks_model_requests"), False),
            (("one_shot", "attempt_path"), "state/catalytic_swarm/attempt-v1.json"),
            (("availability", "automatic_promotion"), True),
        ]
        for path, value in mutations:
            changed = copy.deepcopy(EVALUATOR)
            cursor = changed["catalytic_swarm_0_v2"]
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            self.assertNotEqual(baseline, neo_loop.catalytic_swarm_0_v2_hash(changed), path)

    def test_catalytic_swarm_v2_controller_test_surface_is_protected(self) -> None:
        for path in (
            "scripts/test_neo_loop_vram.py",
            "scripts/test_evaluator_gates.py",
        ):
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])

    def test_rank_head_parent_dependence_surface_is_protected(self) -> None:
        controller_paths = (
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",
            "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",
        )
        for path in controller_paths:
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])
        self.assertIn(
            "lab/ck0_balanced_opaque_rank_head_v2_binding_2_parent_dependence_1.json",
            EVALUATOR["protected_paths"]["files"],
        )

    def test_catalytic_swarm_1_complete_object_is_exact_and_evidence_bound(self) -> None:
        self.assertEqual(
            EVALUATOR["catalytic_swarm_1"],
            build_catalytic_swarm_1_contract(),
        )
        self.assertEqual(
            neo_loop.catalytic_swarm_1_hash(EVALUATOR),
            "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e",
        )
        self.assertIsInstance(EVALUATOR["catalytic_swarm_1_evidence"], dict)
        self.assertEqual(
            neo_loop.catalytic_swarm_1_evidence_hash(EVALUATOR),
            "e308b5953b90d5a28b902b728292440443a9299e58db8049f756557d5693a3d5",
        )
        self.assertEqual(
            EVALUATOR["catalytic_swarm_1"]["one_shot"]["paths"],
            CATALYTIC_SWARM_1_PATHS,
        )

    def test_catalytic_swarm_1_hash_covers_full_contract(self) -> None:
        baseline = neo_loop.catalytic_swarm_1_hash(EVALUATOR)
        mutations = [
            (("predecessor", "evidence_sha256"), "0" * 64),
            (("task_suite", "suite_sha256"), "0" * 64),
            (("arms", "serial-chain", "plan_sha256"), "0" * 64),
            (("execution_order", "cs1-task-01", 0), "best-of-n"),
            (("budget_law", "maximum_tokens_per_request"), 64),
            (("claim_limits", "automatic_promotion"), True),
        ]
        for path, value in mutations:
            changed = copy.deepcopy(EVALUATOR)
            cursor = changed["catalytic_swarm_1"]
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            self.assertNotEqual(
                baseline,
                neo_loop.catalytic_swarm_1_hash(changed),
                path,
            )

    def test_catalytic_swarm_1_evidence_hash_covers_full_object(self) -> None:
        baseline = neo_loop.catalytic_swarm_1_evidence_hash(EVALUATOR)
        changed = copy.deepcopy(EVALUATOR)
        changed["catalytic_swarm_1_evidence"]["automatic_promotion"] = True
        self.assertNotEqual(
            baseline,
            neo_loop.catalytic_swarm_1_evidence_hash(changed),
        )

    def test_catalytic_swarm_1_connector_surface_is_protected(self) -> None:
        for path in (
            "scripts/catalytic_advantage_tasks.py",
            "scripts/catalytic_swarm_advantage.py",
            "scripts/catalytic_swarm_advantage_protocol.py",
            "scripts/test_catalytic_swarm_advantage.py",
            "scripts/test_catalytic_swarm_advantage_protocol.py",
        ):
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])

    def test_cache_diagnostic_and_v2_objects_are_exact_and_bound(self) -> None:
        self.assertEqual(
            EVALUATOR["catalytic_swarm_1_cache_diagnostic"],
            build_cache_diagnostic_contract(),
        )
        self.assertEqual(
            neo_loop.catalytic_swarm_1_cache_diagnostic_hash(EVALUATOR),
            "be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b",
        )
        self.assertEqual(
            EVALUATOR["catalytic_swarm_1_cache_diagnostic_evidence"],
            build_cache_diagnostic_evidence_binding(),
        )
        self.assertEqual(
            neo_loop.catalytic_swarm_1_cache_diagnostic_evidence_hash(EVALUATOR),
            DIAGNOSTIC_EVIDENCE_SHA256,
        )
        self.assertEqual(
            EVALUATOR["catalytic_swarm_1_v2"],
            build_catalytic_swarm_1_v2_contract(),
        )
        self.assertEqual(
            neo_loop.catalytic_swarm_1_v2_hash(EVALUATOR),
            EXPECTED_CONTRACT_SHA256,
        )
        self.assertEqual(
            EVALUATOR["catalytic_swarm_1_cache_diagnostic"]["one_shot"]["paths"],
            CACHE_DIAGNOSTIC_PATHS,
        )
        self.assertTrue(
            set(CACHE_DIAGNOSTIC_PATHS.values()).isdisjoint(
                CATALYTIC_SWARM_1_PATHS.values()
            )
        )

    def test_cache_diagnostic_hash_covers_full_object(self) -> None:
        baseline = neo_loop.catalytic_swarm_1_cache_diagnostic_hash(EVALUATOR)
        changed = copy.deepcopy(EVALUATOR)
        changed["catalytic_swarm_1_cache_diagnostic"]["request_law"][
            "maximum_model_requests"
        ] = 4
        self.assertNotEqual(
            baseline,
            neo_loop.catalytic_swarm_1_cache_diagnostic_hash(changed),
        )

    def test_cache_diagnostic_connector_surface_is_protected(self) -> None:
        for path in (
            "scripts/catalytic_swarm_1_cache_diagnostic.py",
            "scripts/catalytic_swarm_1_cache_diagnostic_protocol.py",
            "scripts/test_catalytic_swarm_1_cache_diagnostic.py",
            "scripts/test_catalytic_swarm_1_cache_diagnostic_protocol.py",
        ):
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])

    def test_v2_connector_surface_is_protected(self) -> None:
        for path in (
            "scripts/catalytic_swarm_1_v2_root_law.py",
            "scripts/test_catalytic_swarm_1_v2_root_law.py",
            "scripts/catalytic_swarm_1_v2_protocol.py",
            "scripts/test_catalytic_swarm_1_v2_protocol.py",
            "scripts/test_catalytic_swarm_1_v2_controller.py",
        ):
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])


    def test_semantic_xor_worker_baseline_surface_is_protected(self) -> None:
        controller_paths = (
            "scripts/catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation_scientific.py",
            "scripts/catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation.py",
            "scripts/test_catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation.py",
        )
        for path in controller_paths:
            self.assertIn(path, EVALUATOR["protected_paths"]["files"])
            self.assertIn(path, EVALUATOR["controller_files"])
        self.assertIn(
            "lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1.json",
            EVALUATOR["protected_paths"]["files"],
        )
        self.assertIn(
            "lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_2.json",
            EVALUATOR["protected_paths"]["files"],
        )
        self.assertIn(
            "lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_3.json",
            EVALUATOR["protected_paths"]["files"],
        )


if __name__ == "__main__":
    unittest.main()
