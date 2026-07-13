#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from catalytic_kernel_0 import (
    CARRIER_ID,
    REQUEST_IDS,
    CatalyticKernel0Error,
    build_carrier,
    build_model_request,
    build_public_shard,
    classify_kernel,
    derive_rank_delta,
    normalize_branch,
    normalize_extraction,
    normalize_transform,
    parse_response,
    run_catalytic_kernel_0,
)
from catalytic_swarm import PhysicalLeasePool


ROOT = Path(__file__).resolve().parents[1]


class FakeExecution:
    def __init__(self, content: str, *, warm: bool) -> None:
        self.content = content
        self.reasoning_content = ""
        self.tool_calls: list[Any] = []
        self.prompt_tokens = 7
        self.cached_prompt_tokens = 0 if warm else 5
        self.completion_tokens = 1
        self.generated_token_ids = [42]
        self.generated_token_count = 1
        self.completion_token_count_match = True
        self.generated_token_sha256 = hashlib.sha256(b"[42]").hexdigest().upper()
        self.nonempty_token_array_event_count = 1
        self.empty_token_array_event_count = 1
        self.token_merge_modes = {"initial": 1, "ignored-empty": 1}
        self.terminal_stop_evidence = {
            "observed": True,
            "stop": True,
            "stop_type": "eos",
            "stopping_word": "",
            "verbose_token_array_length": 0,
            "event_index": 1,
        }
        self.finish_reason = "stop"
        self.http_status = 200
        self.event_count = 3
        self.total_time_s = 0.01
        self.raw_sse = "RAW_SENTINEL"


class FakeAdapter:
    def __init__(self) -> None:
        self.request_ids: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.pool_sizes: list[int] = []
        self.cleanup_calls = 0

    def preflight(
        self,
        *,
        args: Any,
        repository_root: Path,
        run_root: Path,
        allowed_paths: Any,
    ) -> Mapping[str, Any]:
        return {
            "metadata": {
                "binary_identity": {"sha256": "B" * 64},
                "model_identity": {"sha256": "A" * 64},
                "stable": {"head": "1" * 40},
                "candidate": {"head": "2" * 40},
                "historical_cs1_sha256": "C" * 64,
            },
            "runtime": {},
        }

    def create_lease_pool(self, physical_slots: int) -> PhysicalLeasePool:
        self.pool_sizes.append(physical_slots)
        return PhysicalLeasePool(physical_slots)

    def launch_sidecar(
        self, *, preflight: Mapping[str, Any], run_id: str
    ) -> tuple[object, Mapping[str, Any]]:
        return object(), {"sidecar_pid": 1234, "readiness_seconds": 0.1}

    def prompt_geometry(
        self, *, sidecar: Any, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        assignment = json.loads(payload["messages"][1]["content"])
        ordinal = REQUEST_IDS.index(assignment["request_id"]) + 1
        return {
            "rendered_prompt": "IN_MEMORY_ONLY",
            "token_ids": [1, 2, 3, 4, 5, ordinal, 99],
            "public_root_terminal_token_index": 4,
        }

    def execute_request(
        self, *, sidecar: Any, payload: Mapping[str, Any], request: Any
    ) -> FakeExecution:
        self.request_ids.append(request.request_id)
        self.payloads.append(json.loads(json.dumps(payload)))
        values = {
            "borrow": {"carrier_id": CARRIER_ID},
            "branch-a": {"ranking": ["C00", "C01", "C02"]},
            "branch-b": {"ranking": ["C01", "C00", "C02"]},
            "transform": {"operator": "reconcile", "ranking": ["C01", "C02", "C00"]},
            "extract": {"candidate_id": "C01"},
            "restore": {"carrier_id": CARRIER_ID},
        }
        return FakeExecution(
            json.dumps(values[request.request_id], separators=(",", ":")),
            warm=request.request_id == "borrow",
        )

    def boundary_custody(
        self,
        *,
        preflight: Mapping[str, Any],
        sidecar: Any,
        boundary: str,
    ) -> Mapping[str, Any]:
        return {"passed": True, "boundary_sha256": hashlib.sha256(boundary.encode()).hexdigest().upper()}

    def resource_summary(
        self, *, sidecar: Any, boundary: str
    ) -> Mapping[str, Any]:
        return {
            "boundary": boundary,
            "observation_state": "unavailable",
            "observed_at": "2026-07-13T00:00:00+00:00",
        }

    def cleanup(
        self, *, sidecar: Any | None, preflight: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.cleanup_calls += 1
        return {
            "passed": True,
            "process_stopped": True,
            "port_free": True,
            "runtime_removed": True,
            "temporary_state_removed": True,
            "stable_preserved": True,
        }

    def postflight(self, *, preflight: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "passed": True,
            "candidate_head": "2" * 40,
            "candidate_status_sha256": "D" * 64,
        }


class CatalyticKernel0Tests(unittest.TestCase):
    def test_branch_schemas(self) -> None:
        self.assertEqual(
            parse_response("branch-a", '{"ranking":["C00","C01"]}'),
            {"ranking": ["C00", "C01"]},
        )
        for invalid in (
            '{"ranking":[]}',
            '{"ranking":["C00","C00"]}',
            '{"ranking":["C64"]}',
            '{"ranking":["C00"],"reason":"x"}',
        ):
            with self.assertRaises(CatalyticKernel0Error):
                parse_response("branch-a", invalid)

    def test_complementary_shard_isolation(self) -> None:
        carrier = json.loads(build_carrier()["carrier_root"])
        encoded = json.dumps(carrier, sort_keys=True)
        self.assertEqual(
            set(carrier),
            {
                "carrier_id",
                "task_definition",
                "candidate_ids",
                "candidate_programs",
                "kernel_instructions",
                "carrier_content_sha256",
            },
        )
        self.assertNotIn("public_examples", encoded)
        self.assertTrue(all("display" not in item for item in carrier["candidate_programs"]))
        left, right = build_public_shard("branch-a"), build_public_shard("branch-b")
        self.assertEqual(left["example_ids"], ["public-example-1", "public-example-2", "public-example-3"])
        self.assertEqual(right["example_ids"], ["public-example-3", "public-example-4", "public-example-5"])
        self.assertEqual(left["public_examples"][2], right["public_examples"][0])

    def test_no_protected_data_leak(self) -> None:
        carrier = build_carrier()
        artifacts: dict[str, dict[str, Any]] = {}
        payloads: dict[str, dict[str, Any]] = {}
        for request_id in ("borrow", "branch-a", "branch-b"):
            payload = build_model_request(request_id, carrier=carrier, artifacts=artifacts)
            payloads[request_id] = payload
            lowered = json.dumps(payload, sort_keys=True).casefold()
            self.assertNotIn("hidden_examples", lowered)
            self.assertNotIn("answer_candidate_id", lowered)
            if request_id == "branch-a":
                artifacts[request_id] = normalize_branch(request_id, ["C00", "C01", "C02"])
            if request_id == "branch-b":
                artifacts[request_id] = normalize_branch(request_id, ["C01", "C00", "C02"])
        transform = normalize_transform(
            artifacts["branch-a"],
            artifacts["branch-b"],
            operator="reconcile",
            ranking=["C01", "C02", "C00"],
        )
        artifacts["transform"] = transform
        artifacts["extract"] = normalize_extraction("C01", transform)
        for request_id in ("transform", "extract", "restore"):
            payloads[request_id] = build_model_request(
                request_id, carrier=carrier, artifacts=artifacts
            )
        for request_id, payload in payloads.items():
            lowered = json.dumps(payload, sort_keys=True).casefold()
            self.assertNotIn("hidden_examples", lowered, request_id)
            self.assertNotIn("answer_candidate_id", lowered, request_id)
        branch_a_assignment = json.loads(payloads["branch-a"]["messages"][1]["content"])
        branch_b_assignment = json.loads(payloads["branch-b"]["messages"][1]["content"])
        restore_assignment = json.loads(payloads["restore"]["messages"][1]["content"])
        self.assertEqual(set(branch_a_assignment), {"request_id", "instruction", "evidence_shard"})
        self.assertEqual(set(branch_b_assignment), {"request_id", "instruction", "evidence_shard"})
        self.assertEqual(set(restore_assignment), {"request_id", "carrier_id", "instruction"})

    def test_exact_two_parent_transform_binding(self) -> None:
        left = normalize_branch("branch-a", ["C00", "C01", "C02"])
        right = normalize_branch("branch-b", ["C01", "C00", "C02"])
        transform = normalize_transform(left, right, operator="reconcile", ranking=["C01", "C02", "C00"])
        self.assertEqual(transform["parent_artifact_sha256"], [left["artifact_sha256"], right["artifact_sha256"]])
        self.assertEqual(len(transform["dag_edges"]), 6)
        self.assertEqual({item["parent_artifact_id"] for item in transform["dag_edges"]}, {"branch-a", "branch-b"})

    def test_deterministic_rank_delta_derivation(self) -> None:
        delta = derive_rank_delta(["C00", "C01", "C02"], ["C01", "C03", "C00"])
        self.assertEqual(delta["promoted"], ["C01"])
        self.assertEqual(delta["demoted"], ["C00"])
        self.assertEqual(delta["introduced"], ["C03"])
        self.assertEqual(delta["removed"], ["C02"])
        self.assertEqual(delta, derive_rank_delta(["C00", "C01", "C02"], ["C01", "C03", "C00"]))

    def test_extraction_must_select_from_transform(self) -> None:
        left = normalize_branch("branch-a", ["C00", "C01", "C02"])
        right = normalize_branch("branch-b", ["C01", "C00", "C02"])
        transform = normalize_transform(left, right, operator="refine", ranking=["C01", "C02", "C00"])
        extraction = normalize_extraction("C01", transform)
        self.assertEqual(extraction["transform_artifact_sha256_consumed"], transform["artifact_sha256"])
        with self.assertRaises(CatalyticKernel0Error):
            parse_response("extract", '{"candidate_id":"C03"}', transform_artifact=transform)

    def test_carrier_restoration_and_six_request_runtime(self) -> None:
        from holostate_live import build_parser

        parsed = build_parser().parse_args(
            ["run-catalytic-kernel-0", "--model", "model.gguf", "--run-id", "ck0-parser"]
        )
        self.assertEqual(parsed.handler.__name__, "command_run_catalytic_kernel_0")
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            result = run_catalytic_kernel_0(
                {"run_id": "ck0-test-complete", "binary": "X", "model": "Y"},
                adapter=adapter,
                repository_root=ROOT,
                state_root=temporary,
            )
            result_path = Path(temporary) / "ck0-test-complete" / "result.json"
            persisted = result_path.read_text(encoding="utf-8")
        self.assertEqual(adapter.pool_sizes, [1])
        self.assertEqual(adapter.request_ids, list(REQUEST_IDS))
        self.assertEqual(result["completed_model_responses"], 6)
        self.assertTrue(result["restoration"]["passed"])
        self.assertEqual(result["lease_accounting"]["active_leases"], 0)
        self.assertEqual(result["lease_accounting"]["lease_count"], 6)
        self.assertEqual(result["lease_accounting"]["maximum_concurrent_leases"], 1)
        self.assertNotIn("RAW_SENTINEL", persisted)

    def test_collapse_versus_visible_classification(self) -> None:
        identical_a = normalize_branch("branch-a", ["C00", "C01", "C02"])
        identical_b = normalize_branch("branch-b", ["C00", "C01", "C02"])
        identity = normalize_transform(identical_a, identical_b, operator="reconcile", ranking=["C00", "C01", "C02"])
        copied = normalize_extraction("C00", identity)
        self.assertEqual(
            classify_kernel(identical_a, identical_b, identity, copied, restoration_passed=True, completed_request_count=6),
            "CATALYTIC_KERNEL_COLLAPSED",
        )
        different_b = normalize_branch("branch-b", ["C01", "C00", "C02"])
        changed = normalize_transform(identical_a, different_b, operator="combine", ranking=["C01", "C02", "C00"])
        extracted = normalize_extraction("C01", changed)
        self.assertEqual(
            classify_kernel(identical_a, different_b, changed, extracted, restoration_passed=True, completed_request_count=6),
            "CATALYTIC_KERNEL_VISIBLE",
        )


if __name__ == "__main__":
    unittest.main()
