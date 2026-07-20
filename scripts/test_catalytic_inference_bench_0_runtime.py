#!/usr/bin/env python3
"""Focused mocked tests for the Catalytic Inference Bench 0 live runtime."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from catalytic_inference_bench_0_runtime import (  # noqa: E402
    CLAIMS_LOCKED,
    HOST_PRIVATE_GROWTH_CEILING_BYTES,
    WDDM_PEAK_CEILING_BYTES,
    CatalyticInferenceRuntimeError,
    _HoloStateAdapter,
    _aggregate_cost,
    _normalize_resource_observation,
    _normalized_transport,
    _path_is_link_or_reparse,
    _porcelain_v2_status_is_clean,
    _preflight_binary_identity,
    _require_request_safety,
    _safe_exception,
    run_catalytic_inference_bench_0,
)
from catalytic_inference_bench_0 import (  # noqa: E402
    CatalyticInferenceBench0Error,
)
from catalytic_swarm import PhysicalLeasePool  # noqa: E402


REQUEST_IDS = (
    "warm",
    "direct",
    "seed-1",
    "seed-2",
    "seed-3",
    "transform-1",
    "transform-2",
    "transform-3",
    "verify-1",
    "verify-2",
    "verify-3",
    "extract",
    "restore",
)
PARENTS = {
    "warm": (),
    "direct": (),
    "seed-1": (),
    "seed-2": (),
    "seed-3": (),
    "transform-1": ("seed-1",),
    "transform-2": ("seed-2",),
    "transform-3": ("seed-3",),
    "verify-1": ("transform-1", "transform-2"),
    "verify-2": ("transform-2", "transform-3"),
    "verify-3": ("transform-1", "transform-3"),
    "extract": ("verify-1", "verify-2", "verify-3"),
    "restore": ("extract",),
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def ancestors(request_id: str) -> tuple[str, ...]:
    found: set[str] = set()
    pending = list(PARENTS[request_id])
    while pending:
        item = pending.pop()
        if item not in found:
            found.add(item)
            pending.extend(PARENTS[item])
    return tuple(item for item in REQUEST_IDS if item in found)


def depth(request_id: str) -> int:
    return 0 if not PARENTS[request_id] else 1 + max(depth(item) for item in PARENTS[request_id])


@dataclasses.dataclass(frozen=True)
class FakeRequest:
    ordinal: int
    request_id: str
    phase: str
    physical_slot: int
    system_root: str
    system_root_sha256: str
    parent_ids: tuple[str, ...]
    ancestor_ids: tuple[str, ...]
    depth: int
    assignment: Mapping[str, Any]
    response_schema: Mapping[str, Any]
    max_tokens: int = 128

    @property
    def assignment_json(self) -> str:
        return canonical(self.assignment)


@dataclasses.dataclass(frozen=True)
class FakePlan:
    task_id: str
    task_suite_sha256: str
    public_system_root: str
    public_system_root_sha256: str
    physical_slot_count: int
    requests: tuple[FakeRequest, ...]
    plan_sha256: str

    def request(self, request_id: str) -> FakeRequest:
        return next(item for item in self.requests if item.request_id == request_id)


@dataclasses.dataclass(frozen=True)
class FakeObservation:
    request_id: str
    ordinal: int
    phase: str
    completed: bool
    safety_passed: bool
    hidden_leak_detected: bool
    physical_slot: int
    public_system_root_sha256: str
    public_root_terminal_token_index: int
    root_reused: bool
    parent_ids: tuple[str, ...]
    ancestor_ids: tuple[str, ...]
    depth: int
    candidate_id: str | None
    changed_from_parent: bool | None
    reconciliation: str | None
    source_transform_ids: tuple[str, ...]
    restoration_passed: bool | None
    restoration_receipt_sha256: str | None
    response_sha256: str | None
    prompt_tokens: int
    cached_prompt_tokens: int
    fresh_prompt_tokens: int
    completion_tokens: int
    finish_reason: str

    def to_dict(self) -> dict[str, Any]:
        value = dataclasses.asdict(self)
        value["parent_ids"] = list(self.parent_ids)
        value["ancestor_ids"] = list(self.ancestor_ids)
        value["source_transform_ids"] = list(self.source_transform_ids)
        return value


@dataclasses.dataclass(frozen=True)
class FakeAssessment:
    status: str
    mechanism_classification: str
    completed_request_count: int


def fake_protocol() -> types.ModuleType:
    module = types.ModuleType("catalytic_inference_bench_0")
    module.BENCH_ID = "catalytic-inference-bench-0"
    module.FROZEN_TASK_ID = "cs1-task-06"
    module.WARM_ID = "warm"
    module.EXTRACT_ID = "extract"
    module.RESTORE_ID = "restore"
    module.MECHANISM_VISIBLE = "MECHANISM_VISIBLE"
    module.MECHANISM_INCONCLUSIVE = "MECHANISM_INCONCLUSIVE"
    module.NormalizedObservation = FakeObservation

    root = canonical({"task_id": "cs1-task-06", "public_candidates": [f"C{i:02d}" for i in range(64)]})
    root_sha = hashlib.sha256(root.encode()).hexdigest().upper()
    phases = {
        "warm": "warm",
        "direct": "direct",
        **{f"seed-{i}": "seed" for i in range(1, 4)},
        **{f"transform-{i}": "transform" for i in range(1, 4)},
        **{f"verify-{i}": "verify" for i in range(1, 4)},
        "extract": "extract",
        "restore": "restore",
    }
    requests = tuple(
        FakeRequest(
            ordinal=index,
            request_id=request_id,
            phase=phases[request_id],
            physical_slot=0,
            system_root=root,
            system_root_sha256=root_sha,
            parent_ids=PARENTS[request_id],
            ancestor_ids=ancestors(request_id),
            depth=depth(request_id),
            assignment={
                "request_id": request_id,
                "operation": phases[request_id],
                "parent_ids": list(PARENTS[request_id]),
                "ancestor_ids": list(ancestors(request_id)),
                "depth": depth(request_id),
            },
            response_schema={"type": "object", "additionalProperties": False},
        )
        for index, request_id in enumerate(REQUEST_IDS, 1)
    )
    plan = FakePlan(
        task_id="cs1-task-06",
        task_suite_sha256="A" * 64,
        public_system_root=root,
        public_system_root_sha256=root_sha,
        physical_slot_count=1,
        requests=requests,
        plan_sha256=hashlib.sha256(canonical([item.request_id for item in requests]).encode()).hexdigest().upper(),
    )

    def validate_no_hidden_leak(value: Any) -> None:
        encoded = canonical(value).casefold()
        if "hidden_examples" in encoded or "answer_candidate_id" in encoded:
            raise ValueError("private leak")

    def build_model_request(
        request: FakeRequest,
        *,
        model: str,
        stream: bool,
        parent_artifacts: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        assignment = json.loads(request.assignment_json)
        if assignment.get("actual_parent_artifacts") != parent_artifacts:
            raise ValueError("actual parent artifacts differ")
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_root},
                {"role": "user", "content": request.assignment_json},
            ],
            "temperature": 0.0,
            "seed": 60600 + request.ordinal,
            "max_tokens": request.max_tokens,
            "stream": stream,
            "cache_prompt": True,
            "return_tokens": True,
            "return_progress": True,
            "verbose": True,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.request_id.replace("-", "_"),
                    "strict": True,
                    "schema": request.response_schema,
                },
            },
        }

    def validate_model_request(
        request: FakeRequest,
        payload: Mapping[str, Any],
        *,
        parent_artifacts: list[Mapping[str, Any]],
    ) -> None:
        required = {
            "model", "messages", "temperature", "seed", "max_tokens", "stream",
            "cache_prompt", "return_tokens", "return_progress", "verbose",
            "chat_template_kwargs", "response_format",
        }
        if set(payload) != required:
            raise ValueError("payload key set mismatch")
        if payload["messages"][0]["content"] != request.system_root:
            raise ValueError("root mismatch")
        assignment = json.loads(payload["messages"][1]["content"])
        if assignment["actual_parent_artifacts"] != parent_artifacts:
            raise ValueError("parent artifact mismatch")
        validate_no_hidden_leak(payload)

    def validate_response(request: FakeRequest, value: Mapping[str, Any]) -> dict[str, Any]:
        if value.get("request_id") != request.request_id:
            raise ValueError("request mismatch")
        if request.request_id == "warm":
            if value.get("root_status") != "ready":
                raise ValueError("warm mismatch")
        elif request.request_id == "restore":
            if value.get("restoration_status") != "restored":
                raise ValueError("restore mismatch")
        else:
            ranking = value.get("ranked_candidates")
            if not isinstance(ranking, list) or len(ranking) != 3:
                raise ValueError("ranked artifact missing")
            if any(not isinstance(item, dict) or "candidate_id" not in item for item in ranking):
                raise ValueError("ranked artifact malformed")
        return dict(value)

    def parse_structured_response(request: FakeRequest, content: str) -> dict[str, Any]:
        value = json.loads(content)
        if content != canonical(value):
            raise ValueError("not canonical")
        return validate_response(request, value)

    def normalize_observation(
        request: FakeRequest,
        structured: Mapping[str, Any],
        *,
        completed: bool,
        safety_passed: bool,
        root_reused: bool,
        public_root_terminal_token_index: int,
        hidden_leak_detected: bool,
        physical_slot: int,
        public_system_root_sha256: str,
        prompt_tokens: int,
        cached_prompt_tokens: int,
        fresh_prompt_tokens: int,
        completion_tokens: int,
        finish_reason: str,
    ) -> FakeObservation:
        ranking = structured.get("ranked_candidates", [])
        candidate = ranking[0]["candidate_id"] if ranking else None
        return FakeObservation(
            request_id=request.request_id,
            ordinal=request.ordinal,
            phase=request.phase,
            completed=completed,
            safety_passed=safety_passed,
            hidden_leak_detected=hidden_leak_detected,
            physical_slot=physical_slot,
            public_system_root_sha256=public_system_root_sha256,
            public_root_terminal_token_index=public_root_terminal_token_index,
            root_reused=root_reused,
            parent_ids=request.parent_ids,
            ancestor_ids=request.ancestor_ids,
            depth=request.depth,
            candidate_id=candidate,
            changed_from_parent=True if request.phase == "transform" else None,
            reconciliation="ranked-reconcile" if request.phase == "verify" else None,
            source_transform_ids=("transform-1", "transform-2", "transform-3") if request.request_id == "extract" else (),
            restoration_passed=None,
            restoration_receipt_sha256=None,
            response_sha256=hashlib.sha256(canonical(structured).encode()).hexdigest().upper(),
            prompt_tokens=prompt_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
            fresh_prompt_tokens=fresh_prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
        )

    def validate_normalized_metadata(observation: FakeObservation) -> None:
        if not isinstance(observation, FakeObservation):
            raise ValueError("wrong observation")

    def classify(_plan: FakePlan, observations: Any) -> FakeAssessment:
        complete = len(observations) == 13
        restoration = bool(
            complete and observations[-1].restoration_passed is True
        )
        return FakeAssessment(
            status="complete" if complete else "incomplete",
            mechanism_classification=(
                "MECHANISM_VISIBLE"
                if complete and restoration
                else "MECHANISM_INCONCLUSIVE"
            ),
            completed_request_count=len(observations),
        )

    def bind_runtime_restoration(
        observation: FakeObservation,
        **boundaries: Any,
    ) -> FakeObservation:
        passed = (
            observation.request_id == "restore"
            and boundaries["root_identity_passed"] is True
            and boundaries["cache_terminal_admitted"] is True
            and boundaries["active_leases"] == 0
            and boundaries["cleanup_passed"] is True
            and boundaries["custody_passed"] is True
            and boundaries["sidecar_port_free"] is True
            and boundaries["stable_preserved"] is True
        )
        receipt = hashlib.sha256(canonical(boundaries).encode()).hexdigest().upper()
        return dataclasses.replace(
            observation,
            restoration_passed=passed,
            restoration_receipt_sha256=receipt,
        )

    def summarize(_plan: FakePlan, observations: Any, assessment: FakeAssessment) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "bench_id": module.BENCH_ID,
            "task_id": module.FROZEN_TASK_ID,
            "plan_sha256": plan.plan_sha256,
            "status": assessment.status,
            "mechanism_classification": assessment.mechanism_classification,
            "completed_request_count": len(observations),
            "metadata_only": True,
        }

    module.build_catalytic_inference_bench_0_plan = lambda: plan
    module.validate_catalytic_inference_bench_0_plan = lambda value: None if value is plan else (_ for _ in ()).throw(ValueError("plan"))
    module.build_model_request = build_model_request
    module.validate_model_request = validate_model_request
    module.validate_no_hidden_leak = validate_no_hidden_leak
    module.parse_structured_response = parse_structured_response
    module.validate_structured_response = validate_response
    module.normalize_observation = normalize_observation
    module.bind_runtime_restoration = bind_runtime_restoration
    module.validate_normalized_metadata = validate_normalized_metadata
    module.classify_catalytic_inference_bench_0 = classify
    module.summarize_catalytic_inference_bench_0 = summarize
    module.frozen_task = lambda: object()
    return module


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
        self.token_merge_modes = {"initial": 1, "ignored-empty": 1, "absent": 1}
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
    def __init__(
        self,
        events: list[str],
        *,
        fail_preflight: bool = False,
        fail_request: str | None = None,
        pause_after_ordinal: int | None = None,
        unsafe_custody: bool = False,
        unsafe_resources: bool = False,
        fail_final_postflight: bool = False,
    ) -> None:
        self.events = events
        self.fail_preflight = fail_preflight
        self.fail_request = fail_request
        self.pause_after_ordinal = pause_after_ordinal
        self.unsafe_custody = unsafe_custody
        self.unsafe_resources = unsafe_resources
        self.fail_final_postflight = fail_final_postflight
        self.preflight_calls = 0
        self.sidecar_launches = 0
        self.cleanup_calls = 0
        self.postflight_calls = 0
        self.request_ids: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.pool_sizes: list[int] = []
        self.claim_snapshot = dict(CLAIMS_LOCKED)

    def preflight(self, *, args: Any, repository_root: Path, run_root: Path, allowed_paths: Any) -> Mapping[str, Any]:
        self.preflight_calls += 1
        self.events.append("preflight")
        if self.fail_preflight:
            if run_root.exists():
                raise AssertionError("runtime state existed before preflight rejection")
            raise CatalyticInferenceRuntimeError("unexpected repo change")
        return {
            "metadata": {
                "binary_identity": {"sha256": "B" * 64},
                "model_identity": {"sha256": "M" * 64},
                "stable": {"head": "S" * 40},
                "candidate": {"head": "C" * 40},
                "historical_cs1_sha256": "H" * 64,
            },
            "runtime": {},
        }

    def create_lease_pool(self, physical_slots: int) -> PhysicalLeasePool:
        self.pool_sizes.append(physical_slots)
        return PhysicalLeasePool(physical_slots)

    def launch_sidecar(self, *, preflight: Mapping[str, Any], run_id: str) -> tuple[object, Mapping[str, Any]]:
        self.sidecar_launches += 1
        self.events.append("sidecar:launch")
        return object(), {"sidecar_pid": 1234, "readiness_seconds": 0.1}

    def prompt_geometry(self, *, sidecar: Any, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        assignment = json.loads(payload["messages"][1]["content"])
        ordinal = REQUEST_IDS.index(assignment["request_id"]) + 1
        return {
            "rendered_prompt": "IN_MEMORY_ONLY",
            "token_ids": [1, 2, 3, 4, 5, ordinal, 99],
            "public_root_terminal_token_index": 5,
        }

    def execute_request(self, *, sidecar: Any, payload: Mapping[str, Any], request: FakeRequest) -> FakeExecution:
        self.events.append(f"execute:{request.request_id}")
        self.request_ids.append(request.request_id)
        self.payloads.append(json.loads(canonical(payload)))
        if request.request_id == self.fail_request:
            raise RuntimeError("RAW_SENTINEL request failure")
        ranking_map = {
            "direct": ("C00", "C01", "C02"),
            "seed-1": ("C01", "C03", "C04"),
            "seed-2": ("C02", "C04", "C05"),
            "seed-3": ("C03", "C05", "C06"),
            "transform-1": ("C04", "C01", "C03"),
            "transform-2": ("C05", "C02", "C04"),
            "transform-3": ("C06", "C03", "C05"),
            "verify-1": ("C04", "C05", "C01"),
            "verify-2": ("C05", "C06", "C02"),
            "verify-3": ("C04", "C06", "C03"),
            "extract": ("C05", "C04", "C06"),
        }
        if request.request_id == "warm":
            value = {
                "request_id": "warm",
                "root_status": "ready",
                "public_system_root_sha256": request.system_root_sha256,
            }
        elif request.request_id == "restore":
            value = {
                "request_id": "restore",
                "parent_ids": list(request.parent_ids),
                "ancestor_ids": list(request.ancestor_ids),
                "depth": request.depth,
                "restoration_status": "restored",
                "restored_public_system_root_sha256": request.system_root_sha256,
                "slot": 0,
                "slot_state": "public-root",
            }
        else:
            value = {
                "request_id": request.request_id,
                "parent_ids": list(request.parent_ids),
                "ancestor_ids": list(request.ancestor_ids),
                "depth": request.depth,
                "ranked_candidates": [
                    {"candidate_id": candidate_id, "relation": f"rank-{index}"}
                    for index, candidate_id in enumerate(ranking_map[request.request_id], 1)
                ],
                "reason_codes": ["public-fit", "relational-consistency"],
            }
            if request.phase == "transform":
                value["transformation"] = "reordered-by-public-relations"
            if request.phase == "verify":
                value["reconciliation"] = "ranked-reconcile"
            if request.request_id == "extract":
                value["source_transform_ids"] = ["transform-1", "transform-2", "transform-3"]
        return FakeExecution(canonical(value), warm=request.request_id == "warm")

    def boundary_custody(self, *, preflight: Mapping[str, Any], sidecar: Any, boundary: str) -> Mapping[str, Any]:
        return {"passed": not self.unsafe_custody, "boundary_sha256": hashlib.sha256(boundary.encode()).hexdigest().upper()}

    def resource_summary(self, *, sidecar: Any, boundary: str) -> Mapping[str, Any]:
        unsafe = self.unsafe_resources
        return {
            "boundary": boundary,
            "observation_state": "measured",
            "host_private_bytes": 10**15 if unsafe else 1000,
            "host_private_ceiling_exceeded": unsafe,
            "wddm_peak_bytes": 10**15 if unsafe else 2000,
            "wddm_ceiling_exceeded": unsafe,
            "observed_at": "2026-07-13T00:00:00+00:00",
        }

    def cleanup(self, *, sidecar: Any | None, preflight: Mapping[str, Any]) -> Mapping[str, Any]:
        self.cleanup_calls += 1
        self.events.append("cleanup")
        return {"passed": True, "process_stopped": True, "port_free": True, "stable_preserved": True}

    def postflight(self, *, preflight: Mapping[str, Any]) -> Mapping[str, Any]:
        self.postflight_calls += 1
        if self.fail_final_postflight and self.postflight_calls >= 2:
            raise CatalyticInferenceRuntimeError("final custody failure")
        return {"passed": True, "historical_preserved": True}

    def supports_request_boundary_resume(self, *, checkpoint: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"passed": True, "mode": "mock-continuity"}

    def after_request_boundary(self, *, request: FakeRequest, checkpoint_path: Path) -> None:
        if self.pause_after_ordinal == request.ordinal:
            self.pause_after_ordinal = None
            raise RuntimeError("intentional boundary pause")


class CatalyticInferenceBench0RuntimeTests(unittest.TestCase):
    def test_preflight_accepts_one_exact_experiment_binary_identity(self) -> None:
        binary = Path("candidate-llama-server.exe")
        expected = {
            "path": str(binary),
            "sha256": "A" * 64,
            "runtime_version": "160 (89762c0)",
        }
        runtime = types.SimpleNamespace(
            verify_binary_identity=mock.Mock(),
            verify_binary_identity_against=mock.Mock(return_value=expected),
        )
        args = argparse.Namespace(
            expected_binary_sha256="A" * 64,
            expected_runtime_version="160 (89762c0)",
        )
        self.assertEqual(_preflight_binary_identity(runtime, binary, args), expected)
        runtime.verify_binary_identity.assert_not_called()
        runtime.verify_binary_identity_against.assert_called_once_with(
            binary,
            expected_sha256="A" * 64,
            expected_runtime_version="160 (89762c0)",
        )
        with self.assertRaisesRegex(
            CatalyticInferenceRuntimeError,
            "explicit runtime binary identity is incomplete or malformed",
        ):
            _preflight_binary_identity(
                runtime,
                binary,
                argparse.Namespace(
                    expected_binary_sha256="A" * 64,
                    expected_runtime_version=None,
                ),
            )

    @staticmethod
    def _resource(
        boundary: str,
        *,
        host: int | None = 1000,
        wddm: int | None = 2000,
        state: str = "measured",
        host_breach: bool = False,
        wddm_breach: bool = False,
    ) -> dict[str, Any]:
        value: dict[str, Any] = {
            "boundary": boundary,
            "observation_state": state,
            "observed_at": "2026-07-13T00:00:00+00:00",
        }
        if host is not None:
            value["host_private_bytes"] = host
            value["host_private_ceiling_exceeded"] = host_breach
        if wddm is not None:
            value["wddm_peak_bytes"] = wddm
            value["wddm_ceiling_exceeded"] = wddm_breach
        return value

    def test_bounded_transform_diagnostic_is_preserved_without_error_text(self) -> None:
        error_text = "private free-form error text"
        error_sha256 = hashlib.sha256(error_text.encode("utf-8")).hexdigest().upper()
        diagnostic = {
            "request_id": "transform-1",
            "output_candidate_ranking": ["C01", "C00", "C03"],
            "relational_change_candidate_ids": ["C03", "C01", "C00"],
            "relation_operator": "combine",
            "relation_edge_pairs": [
                {
                    "subject_candidate_id": "C01",
                    "object_candidate_id": "C00",
                }
            ],
            "failed_semantic_gate": "relation-edge-coverage",
            "error_message_sha256": error_sha256,
        }
        error = CatalyticInferenceBench0Error(
            error_text,
            semantic_diagnostic=diagnostic,
        )
        persisted = _safe_exception(error, boundary="transform-1")
        self.assertEqual(persisted["semantic_diagnostic"], diagnostic)
        self.assertNotIn(error_text, canonical(persisted))
        self.assertEqual(
            set(persisted["semantic_diagnostic"]),
            {
                "request_id",
                "output_candidate_ranking",
                "relational_change_candidate_ids",
                "relation_operator",
                "relation_edge_pairs",
                "failed_semantic_gate",
                "error_message_sha256",
            },
        )
        injected = RuntimeError(error_text)
        injected.semantic_diagnostic = diagnostic
        self.assertNotIn(
            "semantic_diagnostic",
            _safe_exception(injected, boundary="transform-1"),
        )
        malformed = CatalyticInferenceBench0Error(
            error_text,
            semantic_diagnostic={**diagnostic, "error_message_sha256": "B" * 64},
        )
        self.assertNotIn(
            "semantic_diagnostic",
            _safe_exception(malformed, boundary="transform-1"),
        )

    def test_complete_resource_measurements_under_ceilings_pass(self) -> None:
        before = self._resource("before:warm", host=1000, wddm=2000)
        after = self._resource("after:warm", host=1200, wddm=2500)
        _require_request_safety(
            request_id="warm",
            before_custody={"passed": True},
            after_custody={"passed": True},
            before_resource=before,
            after_resource=after,
        )
        summary = _aggregate_cost(
            [{"transport": {}, "resources": {"before": before, "after": after}}],
            [before, after],
            readiness={"private_bytes": 900},
        )
        self.assertEqual(summary["resource_observability"], "complete")
        self.assertEqual(summary["maximum_host_private_bytes"], 1200)
        self.assertEqual(summary["peak_wddm_bytes"], 2500)
        self.assertFalse(summary["measured_host_ceiling_breach"])
        self.assertFalse(summary["measured_wddm_ceiling_breach"])

    def test_unavailable_pre_request_wddm_is_advisory(self) -> None:
        stale_numeric = _normalize_resource_observation(
            self._resource(
                "before:warm", host=1000, wddm=2000, state="unavailable"
            ),
            boundary="before:warm",
        )
        self.assertEqual(stale_numeric["observation_state"], "unavailable")
        before = self._resource(
            "before:warm", host=1000, wddm=None, state="unavailable"
        )
        after = self._resource("after:warm", host=1200, wddm=2500)
        _require_request_safety(
            request_id="warm",
            before_custody={"passed": True},
            after_custody={"passed": True},
            before_resource=before,
            after_resource=after,
        )
        summary = _aggregate_cost(
            [{"transport": {}, "resources": {"before": before, "after": after}}],
            [before, after],
            readiness={"private_bytes": 900},
        )
        self.assertEqual(summary["resource_observability"], "partial")
        self.assertEqual(summary["wddm_measurement_count"], 1)

    def test_unavailable_host_private_measurement_is_advisory(self) -> None:
        before = self._resource(
            "before:warm", host=None, wddm=2000, state="unavailable"
        )
        after = self._resource("after:warm", host=1200, wddm=2500)
        _require_request_safety(
            request_id="warm",
            before_custody={"passed": True},
            after_custody={"passed": True},
            before_resource=before,
            after_resource=after,
        )
        summary = _aggregate_cost(
            [{"transport": {}, "resources": {"before": before, "after": after}}],
            [before, after],
            readiness={"private_bytes": 900},
        )
        self.assertEqual(summary["resource_observability"], "partial")
        self.assertEqual(summary["host_private_measurement_count"], 1)

    def test_memory_error_from_resource_inspection_is_bounded_and_advisory(self) -> None:
        adapter = object.__new__(_HoloStateAdapter)
        adapter._host_private_baseline_bytes = 900
        adapter.h = types.SimpleNamespace(
            process_info=mock.Mock(side_effect=MemoryError("private sample unavailable"))
        )
        sidecar = types.SimpleNamespace(
            process=types.SimpleNamespace(pid=1234),
            telemetry=lambda: {"peak_bytes": 2000, "failure_reason": None},
        )
        observation = adapter.resource_summary(sidecar=sidecar, boundary="before:warm")
        _require_request_safety(
            request_id="warm",
            before_custody={"passed": True},
            after_custody={"passed": True},
            before_resource=observation,
            after_resource=observation,
        )
        self.assertEqual(observation["observation_state"], "observation-error")
        self.assertEqual(observation["exception_type"], "MemoryError")
        self.assertRegex(observation["exception_message_sha256"], r"^[0-9A-F]{64}$")
        self.assertNotIn("private sample unavailable", canonical(observation))

    def test_ordinary_resource_exception_is_bounded_and_advisory(self) -> None:
        adapter = object.__new__(_HoloStateAdapter)
        adapter._host_private_baseline_bytes = 900
        adapter.h = types.SimpleNamespace(
            process_info=mock.Mock(side_effect=OSError("inspection temporarily failed"))
        )
        sidecar = types.SimpleNamespace(
            process=types.SimpleNamespace(pid=1234),
            telemetry=lambda: {"peak_bytes": 2000, "failure_reason": None},
        )
        observation = adapter.resource_summary(sidecar=sidecar, boundary="before:warm")
        _require_request_safety(
            request_id="warm",
            before_custody={"passed": True},
            after_custody={"passed": True},
            before_resource=observation,
            after_resource=observation,
        )
        self.assertEqual(observation["exception_type"], "OSError")
        self.assertNotIn("inspection temporarily failed", canonical(observation))

    def test_measured_host_ceiling_breach_stops(self) -> None:
        before = self._resource("before:warm")
        after = self._resource(
            "after:warm",
            host=1000 + HOST_PRIVATE_GROWTH_CEILING_BYTES + 1,
            host_breach=False,
        )
        with self.assertRaisesRegex(
            CatalyticInferenceRuntimeError, "host-private growth exceeded"
        ):
            _require_request_safety(
                request_id="warm",
                before_custody={"passed": True},
                after_custody={"passed": True},
                before_resource=before,
                after_resource=after,
                host_baseline_bytes=1000,
            )

    def test_measured_wddm_ceiling_breach_stops(self) -> None:
        before = self._resource("before:warm")
        after = self._resource(
            "after:warm", wddm=WDDM_PEAK_CEILING_BYTES + 1, wddm_breach=True
        )
        with self.assertRaisesRegex(
            CatalyticInferenceRuntimeError, "WDDM peak exceeded"
        ):
            _require_request_safety(
                request_id="warm",
                before_custody={"passed": True},
                after_custody={"passed": True},
                before_resource=before,
                after_resource=after,
            )

    def test_mechanism_classification_is_independent_from_partial_resources(self) -> None:
        class PartialResourceAdapter(FakeAdapter):
            def resource_summary(
                self, *, sidecar: Any, boundary: str
            ) -> Mapping[str, Any]:
                return {
                    "boundary": boundary,
                    "observation_state": "unavailable",
                    "host_private_bytes": 1000,
                    "host_private_ceiling_exceeded": False,
                    "observed_at": "2026-07-13T00:00:00+00:00",
                }

        protocol = fake_protocol()
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            sys.modules, {"catalytic_inference_bench_0": protocol}
        ):
            root = Path(temporary)
            result = run_catalytic_inference_bench_0(
                argparse.Namespace(run_id="partial-resources", binary="B", model="M"),
                adapter=PartialResourceAdapter([]),
                repository_root=root,
                state_root=root / "state" / "catalytic_inference_bench_0",
                scorer=lambda *_args, hidden=False, **_kwargs: (
                    (16, 16) if hidden else (5, 5)
                ),
            )
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["mechanism_classification"], "MECHANISM_VISIBLE")
        self.assertEqual(result["resource_observability"], "partial")
        self.assertFalse(result["resource_summary"]["measured_host_ceiling_breach"])
        self.assertFalse(result["resource_summary"]["measured_wddm_ceiling_breach"])

    def test_complete_epoch_ranked_parent_artifacts_and_nonclaiming_persistence(self) -> None:
        protocol = fake_protocol()
        events: list[str] = []
        adapter = FakeAdapter(events)

        def scorer(_task: Any, candidate_id: str, *, hidden: bool) -> tuple[int, int]:
            events.append(f"score:{'hidden' if hidden else 'public'}:{candidate_id}")
            return (16, 16) if hidden else (5, 5)

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            sys.modules, {"catalytic_inference_bench_0": protocol}
        ):
            root = Path(temporary)
            result = run_catalytic_inference_bench_0(
                argparse.Namespace(run_id="ranked-epoch", binary="B", model="M"),
                adapter=adapter,
                repository_root=root,
                state_root=root / "state" / "catalytic_inference_bench_0",
                scorer=scorer,
            )
            run_root = root / "state" / "catalytic_inference_bench_0" / "ranked-epoch"
            persisted = "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted(run_root.glob("*.json"))
            )
            closure_present = (run_root / "closure.json").is_file()
            run_lock_absent = not (run_root / "run.lock").exists()

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["mechanism_classification"], "MECHANISM_VISIBLE")
        self.assertEqual(adapter.request_ids, list(REQUEST_IDS))
        self.assertEqual(adapter.sidecar_launches, 1)
        self.assertEqual(adapter.pool_sizes, [1])
        self.assertEqual(result["lease_accounting"]["lease_count"], 13)
        self.assertEqual(result["lease_accounting"]["maximum_concurrent_leases"], 1)
        self.assertEqual(result["lease_accounting"]["active_leases"], 0)
        self.assertEqual(len(result["request_records"]), 13)
        self.assertTrue(closure_present)
        self.assertTrue(run_lock_absent)
        self.assertIsInstance(result["terminal_checkpoint_sha256"], str)
        with self.subTest(case="optional-empty-generated-token-array"):
            execution = FakeExecution("{}", warm=True)
            execution.generated_token_ids = []
            execution.generated_token_count = 0
            execution.completion_token_count_match = False
            execution.generated_token_sha256 = hashlib.sha256(b"[]").hexdigest().upper()
            execution.nonempty_token_array_event_count = 0
            execution.empty_token_array_event_count = 1
            execution.token_merge_modes = {"absent": 2, "ignored-empty": 1}
            normalized = _normalized_transport(
                execution, rendered_tokens=7, max_tokens=128
            )
            self.assertEqual(
                normalized["metadata"]["generated_token_evidence_mode"],
                "usage-plus-source-bound-terminal-eos",
            )
            self.assertIs(
                normalized["metadata"]["full_generated_sequence_known"], False
            )
            self.assertIs(
                normalized["metadata"]["completion_token_count_match"], False
            )
        with self.subTest(case="contradictory-nonempty-generated-token-array"):
            execution = FakeExecution("{}", warm=True)
            execution.generated_token_ids = [42, 43]
            execution.generated_token_count = 2
            execution.completion_token_count_match = False
            execution.generated_token_sha256 = hashlib.sha256(
                b"[42,43]"
            ).hexdigest().upper()
            with self.assertRaisesRegex(
                CatalyticInferenceRuntimeError, "contradicts usage accounting"
            ):
                _normalized_transport(execution, rendered_tokens=7, max_tokens=128)
        with self.subTest(case="empty-array-without-terminal-eos"):
            execution = FakeExecution("{}", warm=True)
            execution.generated_token_ids = []
            execution.generated_token_count = 0
            execution.completion_token_count_match = False
            execution.generated_token_sha256 = hashlib.sha256(b"[]").hexdigest().upper()
            execution.nonempty_token_array_event_count = 0
            execution.empty_token_array_event_count = 1
            execution.token_merge_modes = {"absent": 2, "ignored-empty": 1}
            execution.terminal_stop_evidence = None
            with self.assertRaisesRegex(
                CatalyticInferenceRuntimeError, "terminal EOS evidence"
            ):
                _normalized_transport(execution, rendered_tokens=7, max_tokens=128)
        self.assertEqual(
            sum(record["cache_adjudication"]["adjudicated"] is True for record in result["request_records"]),
            13,
        )
        roots = {payload["messages"][0]["content"] for payload in adapter.payloads}
        self.assertEqual(len(roots), 1)
        for payload in adapter.payloads:
            encoded = canonical(payload)
            self.assertNotIn("hidden_examples", encoded)
            self.assertNotIn("answer_candidate_id", encoded)
            self.assertEqual(payload["stream_options"], {"include_usage": True})
            self.assertIs(payload["response_format"]["json_schema"]["strict"], True)
        for request_id in (*[f"transform-{i}" for i in range(1, 4)], *[f"verify-{i}" for i in range(1, 4)]):
            payload = adapter.payloads[REQUEST_IDS.index(request_id)]
            assignment = json.loads(payload["messages"][1]["content"])
            parents = assignment["actual_parent_artifacts"]
            self.assertEqual([item["producer_request_id"] for item in parents], list(PARENTS[request_id]))
            self.assertTrue(all("ranked_structure" in item for item in parents))
            self.assertTrue(all("public_scores" in item for item in parents))
        restore_assignment = json.loads(adapter.payloads[-1]["messages"][1]["content"])
        self.assertEqual(set(restore_assignment["actual_parent_artifacts"][0]), {"producer_request_id", "artifact_kind", "artifact_sha256"})
        self.assertNotIn("ranked_structure", restore_assignment["actual_parent_artifacts"][0])
        self.assertLess(events.index("execute:extract"), events.index("score:hidden:C00"))
        self.assertLess(events.index("score:hidden:C00"), events.index("score:hidden:C05"))
        self.assertLess(events.index("score:hidden:C05"), events.index("execute:restore"))
        self.assertEqual(result["post_extraction_hidden_score"]["direct_baseline"]["candidate_id"], "C00")
        self.assertEqual(result["post_extraction_hidden_score"]["final_catalytic"]["candidate_id"], "C05")
        self.assertNotIn("RAW_SENTINEL", persisted)
        self.assertNotIn("raw_sse", persisted.casefold())
        self.assertNotIn("reasoning_content", persisted.casefold())
        self.assertFalse(result["raw_output_persisted"])
        self.assertEqual(result["claims"], CLAIMS_LOCKED)
        self.assertFalse(result["automatic_promotion"])
        self.assertEqual(adapter.claim_snapshot, CLAIMS_LOCKED)

    def test_run_id_preflight_failure_checkpoint_and_boundary_resume_matrix(self) -> None:
        protocol = fake_protocol()
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            sys.modules, {"catalytic_inference_bench_0": protocol}
        ):
            root = Path(temporary)
            state_root = root / "state" / "catalytic_inference_bench_0"
            for invalid in (None, "", "../escape", "a/b", "a\\b", ".", "x" * 65):
                with self.subTest(case="run-id", value=invalid):
                    adapter = FakeAdapter([])
                    with self.assertRaises(CatalyticInferenceRuntimeError):
                        run_catalytic_inference_bench_0(
                            argparse.Namespace(run_id=invalid, binary="B", model="M"),
                            adapter=adapter,
                            repository_root=root,
                            state_root=state_root,
                            scorer=lambda *_args, **_kwargs: (1, 1),
                        )
                    self.assertEqual(adapter.preflight_calls, 0)

            with self.subTest(case="preflight-before-state"):
                adapter = FakeAdapter([], fail_preflight=True)
                with self.assertRaisesRegex(CatalyticInferenceRuntimeError, "unexpected repo change"):
                    run_catalytic_inference_bench_0(
                        argparse.Namespace(run_id="preflight-reject", binary="B", model="M"),
                        adapter=adapter,
                        repository_root=root,
                        state_root=state_root,
                        scorer=lambda *_args, **_kwargs: (1, 1),
                    )
                self.assertFalse((state_root / "preflight-reject").exists())

            with self.subTest(case="porcelain-v2-candidate-cleanliness"):
                self.assertTrue(
                    _porcelain_v2_status_is_clean(
                        "# branch.oid abc\n# branch.head main\n"
                    )
                )
                for dirty in (
                    "1 .M N... 100644 100644 100644 a b file.py",
                    "1 M. N... 100644 100644 100644 a b file.py",
                    "2 R. N... 100644 100644 100644 a b R100 new.py\told.py",
                    "u UU N... 100644 100644 100644 100644 a b c file.py",
                    "? untracked.txt",
                ):
                    self.assertFalse(_porcelain_v2_status_is_clean(dirty))
                with mock.patch(
                    "catalytic_inference_bench_0_runtime.os.lstat",
                    return_value=types.SimpleNamespace(
                        st_mode=stat.S_IFDIR,
                        st_file_attributes=0x400,
                    ),
                ):
                    self.assertTrue(_path_is_link_or_reparse(Path("junction")))

            for case, kwargs in (
                ("custody-boundary-enforced", {"unsafe_custody": True}),
                ("resource-boundary-enforced", {"unsafe_resources": True}),
            ):
                with self.subTest(case=case):
                    adapter = FakeAdapter([], **kwargs)
                    failed = run_catalytic_inference_bench_0(
                        argparse.Namespace(run_id=case, binary="B", model="M"),
                        adapter=adapter,
                        repository_root=root,
                        state_root=state_root,
                        scorer=lambda *_args, **_kwargs: (1, 1),
                    )
                    self.assertEqual(failed["status"], "failed")
                    self.assertEqual(failed["mechanism_classification"], "MECHANISM_INCONCLUSIVE")

            with self.subTest(case="uncertain-request-failure"):
                events: list[str] = []
                adapter = FakeAdapter(events, fail_request="seed-2")
                failed = run_catalytic_inference_bench_0(
                    argparse.Namespace(run_id="failed-request", binary="B", model="M"),
                    adapter=adapter,
                    repository_root=root,
                    state_root=state_root,
                    scorer=lambda *_args, hidden=False, **_kwargs: (16, 16) if hidden else (5, 5),
                )
                checkpoint = json.loads((state_root / "failed-request" / "checkpoint.json").read_text(encoding="utf-8"))
                persisted = (state_root / "failed-request" / "result.json").read_text(encoding="utf-8")
                self.assertEqual(failed["status"], "failed")
                self.assertFalse(checkpoint["resume_safe"])
                self.assertEqual(checkpoint["inflight_request_id"], "seed-2")
                self.assertEqual(adapter.cleanup_calls, 1)
                self.assertNotIn("RAW_SENTINEL", persisted)
                resume_adapter = FakeAdapter([])
                with self.assertRaisesRegex(CatalyticInferenceRuntimeError, "uncertain in-flight"):
                    run_catalytic_inference_bench_0(
                        argparse.Namespace(run_id="failed-request", binary="B", model="M"),
                        adapter=resume_adapter,
                        repository_root=root,
                        state_root=state_root,
                        scorer=lambda *_args, **_kwargs: (1, 1),
                    )
                self.assertEqual(resume_adapter.sidecar_launches, 0)

            with self.subTest(case="safe-boundary-resume-and-idempotence"):
                events = []

                def scorer(_task: Any, candidate_id: str, *, hidden: bool) -> tuple[int, int]:
                    events.append(f"score:{'hidden' if hidden else 'public'}:{candidate_id}")
                    return (16, 16) if hidden else (5, 5)

                first = FakeAdapter(events, pause_after_ordinal=5)
                partial = run_catalytic_inference_bench_0(
                    argparse.Namespace(run_id="resume-safe", binary="B", model="M"),
                    adapter=first,
                    repository_root=root,
                    state_root=state_root,
                    scorer=scorer,
                )
                partial_checkpoint = json.loads((state_root / "resume-safe" / "checkpoint.json").read_text(encoding="utf-8"))
                self.assertEqual(partial["status"], "failed")
                self.assertTrue(partial_checkpoint["resume_safe"])
                self.assertEqual(partial_checkpoint["next_request_ordinal"], 6)
                second = FakeAdapter(events)
                complete = run_catalytic_inference_bench_0(
                    argparse.Namespace(run_id="resume-safe", binary="B", model="M"),
                    adapter=second,
                    repository_root=root,
                    state_root=state_root,
                    scorer=scorer,
                )
                self.assertEqual(complete["status"], "complete")
                self.assertEqual(first.request_ids + second.request_ids, list(REQUEST_IDS))
                self.assertEqual(second.request_ids[0], "transform-1")
                self.assertEqual(complete["lease_accounting"]["lease_count"], 13)
                self.assertEqual(complete["lease_accounting"]["active_leases"], 0)
                self.assertEqual(complete["sidecar_instance_count"], 2)
                idempotent = FakeAdapter([])
                again = run_catalytic_inference_bench_0(
                    argparse.Namespace(run_id="resume-safe", binary="B", model="M"),
                    adapter=idempotent,
                    repository_root=root,
                    state_root=state_root,
                    scorer=scorer,
                )
                self.assertEqual(again, complete)
                self.assertEqual(idempotent.sidecar_launches, 0)
                self.assertEqual(idempotent.request_ids, [])
                self.assertEqual(first.claim_snapshot, CLAIMS_LOCKED)
                self.assertEqual(second.claim_snapshot, CLAIMS_LOCKED)

                result_path = state_root / "resume-safe" / "result.json"
                tampered = json.loads(result_path.read_text(encoding="utf-8"))
                tampered["automatic_promotion"] = True
                result_path.write_text(canonical(tampered) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    CatalyticInferenceRuntimeError, "digest mismatch"
                ):
                    run_catalytic_inference_bench_0(
                        argparse.Namespace(run_id="resume-safe", binary="B", model="M"),
                        adapter=FakeAdapter([]),
                        repository_root=root,
                        state_root=state_root,
                        scorer=scorer,
                    )

            with self.subTest(case="final-custody-terminal-consistency"):
                adapter = FakeAdapter([], fail_final_postflight=True)
                failed = run_catalytic_inference_bench_0(
                    argparse.Namespace(run_id="final-custody", binary="B", model="M"),
                    adapter=adapter,
                    repository_root=root,
                    state_root=state_root,
                    scorer=lambda *_args, hidden=False, **_kwargs: (16, 16) if hidden else (5, 5),
                )
                run_root = state_root / "final-custody"
                checkpoint = json.loads((run_root / "checkpoint.json").read_text(encoding="utf-8"))
                persisted_result = json.loads((run_root / "result.json").read_text(encoding="utf-8"))
                closure = json.loads((run_root / "closure.json").read_text(encoding="utf-8"))
                self.assertEqual(failed["status"], "failed")
                self.assertEqual(checkpoint["status"], "failed")
                self.assertEqual(persisted_result["status"], "failed")
                self.assertIs(closure["terminal_custody"]["passed"], False)
                self.assertEqual(
                    closure["result_sha256"],
                    hashlib.sha256(canonical(persisted_result).encode()).hexdigest().upper(),
                )
                self.assertEqual(
                    closure["checkpoint_sha256"],
                    hashlib.sha256(canonical(checkpoint).encode()).hexdigest().upper(),
                )
                self.assertEqual(
                    checkpoint["result_sha256"],
                    hashlib.sha256(canonical(persisted_result).encode()).hexdigest().upper(),
                )

            with self.subTest(case="checkpoint-tamper-rejected"):
                adapter = FakeAdapter([])
                complete = run_catalytic_inference_bench_0(
                    argparse.Namespace(run_id="checkpoint-bound", binary="B", model="M"),
                    adapter=adapter,
                    repository_root=root,
                    state_root=state_root,
                    scorer=lambda *_args, hidden=False, **_kwargs: (16, 16) if hidden else (5, 5),
                )
                self.assertEqual(complete["status"], "complete")
                checkpoint_path = state_root / "checkpoint-bound" / "checkpoint.json"
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                checkpoint["next_request_ordinal"] = 999
                checkpoint_path.write_text(canonical(checkpoint) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    CatalyticInferenceRuntimeError,
                    "terminal checkpoint digest mismatch",
                ):
                    run_catalytic_inference_bench_0(
                        argparse.Namespace(run_id="checkpoint-bound", binary="B", model="M"),
                        adapter=FakeAdapter([]),
                        repository_root=root,
                        state_root=state_root,
                        scorer=lambda *_args, **_kwargs: (1, 1),
                    )


if __name__ == "__main__":
    unittest.main()
