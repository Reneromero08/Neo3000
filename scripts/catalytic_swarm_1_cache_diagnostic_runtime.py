#!/usr/bin/env python3
"""Live orchestration for the separately versioned CS1 cache-admission diagnostic.

The module accepts ``holostate_live`` as a runtime binding to avoid an import
cycle. It owns only the diagnostic's separate state root and never mutates the
executed CatalyticSwarm-1 v1 artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from catalytic_swarm_1_cache_diagnostic import (
    CacheDiagnosticError,
    CacheProbeObservation,
    classify_diagnostic,
    classify_probe,
)
from catalytic_swarm_1_cache_diagnostic_protocol import (
    CHECKPOINT_MIN_STEP,
    MAX_MODEL_REQUESTS,
    ONE_SHOT_PATHS,
    PREDECESSOR_ARTIFACTS,
    PREDECESSOR_EVIDENCE_SHA256,
    TASK_ID,
    contract_sha256,
    validate_cache_diagnostic_contract,
)
from catalytic_swarm_advantage import build_all_arm_plans, render_turn_assignment

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_LEDGER_BYTES = 4 * 1024 * 1024
MAX_LEDGER_RECORDS = 3
MINIMAL_CONTENT = '{"candidate_id":"C00"}'


class CacheDiagnosticRuntimeError(RuntimeError):
    """The protected live diagnostic could not complete its declared boundary."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def common_prefix_token_count(left: Sequence[int], right: Sequence[int]) -> int:
    if isinstance(left, (str, bytes)) or isinstance(right, (str, bytes)):
        raise CacheDiagnosticRuntimeError("token identities must be sequences")
    count = 0
    for lhs, rhs in zip(left, right):
        if isinstance(lhs, bool) or not isinstance(lhs, int):
            raise CacheDiagnosticRuntimeError("left token identity is malformed")
        if isinstance(rhs, bool) or not isinstance(rhs, int):
            raise CacheDiagnosticRuntimeError("right token identity is malformed")
        if lhs != rhs:
            break
        count += 1
    return count


def public_root_terminal_token_index(
    token_ids: Sequence[int],
    system_message: str,
    *,
    detokenize: Callable[[list[int]], str],
) -> int:
    """Find the smallest token prefix whose decoded text contains the full root."""
    if not isinstance(system_message, str) or not system_message:
        raise CacheDiagnosticRuntimeError("system message is unavailable")
    values = list(token_ids)
    if not values or any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise CacheDiagnosticRuntimeError("rendered token identity is malformed")

    def contains_root(prefix_length: int) -> bool:
        decoded = detokenize(values[:prefix_length])
        return isinstance(decoded, str) and system_message in decoded

    if not contains_root(len(values)):
        raise CacheDiagnosticRuntimeError(
            "detokenized rendered prompt does not contain the complete public root"
        )
    low, high = 1, len(values)
    while low < high:
        middle = (low + high) // 2
        if contains_root(middle):
            high = middle
        else:
            low = middle + 1
    return low


def diagnostic_paths(root: Path) -> dict[str, Path]:
    resolved_root = root.resolve()
    result: dict[str, Path] = {}
    for name, relative in ONE_SHOT_PATHS.items():
        path = (root.parents[1] / relative).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise CacheDiagnosticRuntimeError(
                f"diagnostic path escapes the declared root: {relative}"
            ) from exc
        result[name] = path
    return result


def _require_owned_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CacheDiagnosticRuntimeError(f"path escapes diagnostic state root: {path}") from exc
    return resolved


def claim_json_once(path: Path, value: Mapping[str, Any], *, root: Path) -> None:
    target = _require_owned_path(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise CacheDiagnosticRuntimeError("diagnostic JSON exceeds its byte ceiling")
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            target.unlink(missing_ok=True)
        finally:
            raise


def write_json(path: Path, value: Mapping[str, Any], *, root: Path) -> None:
    target = _require_owned_path(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise CacheDiagnosticRuntimeError("diagnostic JSON exceeds its byte ceiling")
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


class DiagnosticLedger:
    """Tiny metadata-only JSONL ledger with one record per completed request."""

    def __init__(self, path: Path, *, root: Path) -> None:
        self.path = _require_owned_path(path, root)
        self.records: list[dict[str, Any]] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(descriptor)

    def append(self, record: Mapping[str, Any]) -> None:
        if len(self.records) >= MAX_LEDGER_RECORDS:
            raise CacheDiagnosticRuntimeError("diagnostic ledger record ceiling exceeded")
        value = dict(record)
        forbidden = canonical_json_bytes(value).lower()
        for marker in (
            b"hidden_examples",
            b"answer_candidate_id",
            b"reasoning_text",
            b"raw_sse",
            b"raw_payload",
        ):
            if marker in forbidden:
                raise CacheDiagnosticRuntimeError("diagnostic ledger contains forbidden data")
        value["record_index"] = len(self.records) + 1
        encoded = canonical_json_bytes(value) + b"\n"
        if self.path.stat().st_size + len(encoded) > MAX_LEDGER_BYTES:
            raise CacheDiagnosticRuntimeError("diagnostic ledger byte ceiling exceeded")
        with self.path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        self.records.append(value)

    def snapshot(self) -> dict[str, Any]:
        raw = self.path.read_bytes()
        return {
            "path": str(self.path),
            "record_count": len(self.records),
            "size_bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "metadata_only": True,
            "raw_sse_persisted": False,
            "within_limits": len(self.records) <= MAX_LEDGER_RECORDS and len(raw) <= MAX_LEDGER_BYTES,
        }


def reconcile_request_boundaries(
    labels: Sequence[str],
    *,
    completed_requests: int,
    custody_checks: int,
    host_memory_checks: int,
    ledger_records: int,
) -> dict[str, Any]:
    if isinstance(completed_requests, bool) or not isinstance(completed_requests, int):
        raise CacheDiagnosticRuntimeError("completed request count is malformed")
    if completed_requests < 0 or completed_requests > MAX_MODEL_REQUESTS:
        raise CacheDiagnosticRuntimeError("completed request count exceeds diagnostic law")
    pre = [
        label for label in labels
        if isinstance(label, str) and label.startswith("pre-request:cs1-cache-diagnostic-")
    ]
    post = [
        label for label in labels
        if isinstance(label, str) and label.startswith("post-request:cs1-cache-diagnostic-")
    ]
    reasons: list[str] = []
    if len(pre) != completed_requests:
        reasons.append("pre-request-boundary-count")
    if len(post) != completed_requests:
        reasons.append("post-request-boundary-count")
    if custody_checks != completed_requests * 2:
        reasons.append("custody-check-count")
    if host_memory_checks != completed_requests:
        reasons.append("host-memory-check-count")
    if ledger_records != completed_requests:
        reasons.append("ledger-record-count")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "completed_requests": completed_requests,
        "pre_request_boundaries": len(pre),
        "post_request_boundaries": len(post),
        "custody_checks": custody_checks,
        "host_memory_checks": host_memory_checks,
        "ledger_records": ledger_records,
        "full_schedule_completed": completed_requests == MAX_MODEL_REQUESTS,
    }


def _retired_predecessor_paths(rt: Any) -> dict[str, Path]:
    return {
        "control": rt.CATALYTIC_SWARM_1_CONTROL_PATH,
        "readiness": rt.CATALYTIC_SWARM_1_READINESS_PATH,
        "parser_canary": rt.CATALYTIC_SWARM_1_PARSER_CANARY_PATH,
        "attempt": rt.CATALYTIC_SWARM_1_ATTEMPT_PATH,
        "result": rt.CATALYTIC_SWARM_1_RESULT_PATH,
        "ledger": rt.CATALYTIC_SWARM_1_LEDGER_PATH,
    }


def _preserve_predecessor(rt: Any, evaluator: Mapping[str, Any]) -> dict[str, Any]:
    evidence_hash = rt.catalytic_swarm_1_evidence_hash(dict(evaluator))
    if evidence_hash.lower() != PREDECESSOR_EVIDENCE_SHA256.lower():
        raise CacheDiagnosticRuntimeError("CS1-v1 evidence object changed")
    artifacts: dict[str, Any] = {}
    for name, path in _retired_predecessor_paths(rt).items():
        actual = rt.sha256_file(path).upper()
        if actual != PREDECESSOR_ARTIFACTS[name].upper():
            raise CacheDiagnosticRuntimeError(f"CS1-v1 {name} artifact changed")
        artifacts[name] = {"path": str(path), "sha256": actual, "size_bytes": path.stat().st_size}
    if rt.CATALYTIC_SWARM_1_TASK_RESULTS_PATH.exists():
        raise CacheDiagnosticRuntimeError("CS1-v1 task-results absence changed")
    return {"evidence_object_sha256": evidence_hash, "artifacts": artifacts, "task_results_absent": True, "preserved": True}


def _exact_custody(rt: Any, candidate_root: Path) -> dict[str, str]:
    return {
        "stable": rt.git_read(rt.ROOT, "status", "--porcelain=v2", "--branch", "--untracked-files=all"),
        "candidate": rt.git_read(candidate_root, "status", "--porcelain=v2", "--branch", "--untracked-files=all"),
    }


def _minimal_lane(rt: Any) -> dict[str, Any]:
    return {
        "thinking_mode": "disabled",
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": 32,
        "temperature": 0.0,
        "seed": 14101,
        "requires": {
            "accepted_v4_token_evidence": True,
            "empty_reasoning_content": True,
            "empty_tool_calls": True,
            "finish_reason": "stop",
        },
        "grammar": rt.exact_gbnf_literal(MINIMAL_CONTENT),
    }


def _probe_request(
    rt: Any,
    *,
    sidecar: Any,
    protocol_v4: dict[str, Any],
    task: Any,
    label: str,
    assignment: str,
    lane: dict[str, Any],
    system_message: str,
    system_identity: dict[str, Any],
    request_sequence_index: int,
    on_completed: Callable[[str], None],
) -> tuple[CacheProbeObservation, dict[str, Any]]:
    payload = rt.build_worker_chat_payload(protocol_v4, system_message, assignment, lane)
    rendered = rt.render_messages(payload["messages"], lane["chat_template_kwargs"])
    rendered_ids = rt.tokenize(rendered)
    warm_rendered = system_identity.get("_warm_rendered_prompt")
    warm_ids = system_identity.get("_warm_prompt_token_ids")
    if not isinstance(warm_rendered, str) or not isinstance(warm_ids, list):
        raise CacheDiagnosticRuntimeError("warm prompt identity is unavailable")
    warm_root_index = public_root_terminal_token_index(warm_ids, system_message, detokenize=rt.detokenize)
    branch_root_index = public_root_terminal_token_index(rendered_ids, system_message, detokenize=rt.detokenize)
    if warm_root_index != branch_root_index:
        raise CacheDiagnosticRuntimeError("warm and branch public-root terminal token indices disagree")
    common_prefix = common_prefix_token_count(warm_ids, rendered_ids)
    required_cache = rt.catalytic_swarm_1_required_cached_prefix(
        warm_rendered, warm_ids, rendered, rendered_ids, system_message
    )
    transient = rt.BoundedInMemoryLedger(max_bytes=rt.MIB, max_records=10_000)
    request_label = f"cs1-cache-diagnostic-{label}"
    measurement = rt.stream_completion(
        f"http://127.0.0.1:{rt.PORT}{protocol_v4['endpoint']}",
        payload,
        repeat=1,
        timeout=1_200,
        event_recorder=transient.recorder(request_label, request_sequence_index),
        request_label=request_label,
    )
    on_completed(request_label)
    content = measurement.content
    transport_passed = False
    token_evidence_passed = False
    logical_prompt_tokens = len(rendered_ids)
    cached_prompt_tokens = 0
    completion_tokens = 0
    finish_reason = None
    reasoning_present = True
    tool_calls: list[Any] = []
    evidence_scope = None
    try:
        rt.parse_candidate_content(content, task)
        compact = rt.compact_worker_v4_measurement(
            measurement,
            root_name=task.task_id,
            assignment_name=label,
            lane_name="F",
            expected_content=content,
            system_identity=system_identity,
            user_message=assignment,
            configured_max_tokens=32,
        )
        token_result = rt.resolve_worker_v4_visible_token_evidence(
            measurement,
            expected_content=content,
            logical_prompt_tokens=compact.get("logical_prompt_tokens"),
        )
        evidence = token_result["visible_token_evidence"]
        classification = rt.classify_worker_v4_channels(compact, lane, warm=False, token_evidence_required=True)
        transport_passed = classification == "accepted"
        token_evidence_passed = evidence.get("accepted") is True
        logical_prompt_tokens = int(compact["logical_prompt_tokens"])
        cached_prompt_tokens = int(compact["cached_prompt_tokens"])
        completion_tokens = int(compact["completion_tokens"])
        finish_reason = compact.get("finish_reason")
        reasoning_present = compact.get("reasoning_content", {}).get("present") is True
        tool_calls = list(compact.get("tool_calls", []))
        evidence_scope = evidence.get("claim_scope")
    except Exception:
        pass
    if cached_prompt_tokens < 0 or cached_prompt_tokens > logical_prompt_tokens:
        cached_prompt_tokens = 0
    observation = CacheProbeObservation(
        label=label,
        request_sequence_index=request_sequence_index,
        warm_prompt_tokens=len(warm_ids),
        branch_prompt_tokens=logical_prompt_tokens,
        public_root_terminal_token_index=warm_root_index,
        common_prefix_tokens=common_prefix,
        required_cached_prompt_tokens=required_cache,
        actual_cached_prompt_tokens=cached_prompt_tokens,
        fresh_prompt_tokens=logical_prompt_tokens - cached_prompt_tokens,
        completion_tokens=max(0, completion_tokens),
        cache_checkpoint_min_step=CHECKPOINT_MIN_STEP,
        response_completed=True,
        transport_passed=transport_passed and finish_reason == "stop" and not reasoning_present and tool_calls == [],
        token_evidence_passed=token_evidence_passed,
    )
    return observation, {
        "kind": "probe",
        "label": label,
        "request_sequence_index": request_sequence_index,
        "observation": observation.to_dict(),
        "content_sha256": sha256_bytes(content.encode("utf-8")),
        "token_evidence_scope": evidence_scope,
        "raw_sse_persisted": False,
        "reasoning_text_persisted": False,
        "hidden_data_persisted": False,
    }


def run_live_cache_diagnostic(rt: Any, args: Any) -> dict[str, Any]:
    """Execute the separately authorized three-request diagnostic once."""
    evaluator = rt.load_json(rt.EVALUATOR_PATH)
    lock = rt.verify_lock(evaluator)
    contract = evaluator.get("catalytic_swarm_1_cache_diagnostic")
    validate_cache_diagnostic_contract(contract)
    expected_contract_hash = contract_sha256(contract)
    if lock.get("catalytic_swarm_1_cache_diagnostic_sha256") != expected_contract_hash:
        raise CacheDiagnosticRuntimeError("cache diagnostic contract lock differs")
    state_root = rt.CATALYTIC_SWARM_1_CACHE_DIAGNOSTIC_STATE_ROOT
    paths = diagnostic_paths(state_root)
    if state_root.exists() or any(path.exists() for path in paths.values()):
        raise CacheDiagnosticRuntimeError("cache diagnostic boundary already exists")
    predecessor = _preserve_predecessor(rt, evaluator)
    candidate_root = rt.ROOT.parent / f"{rt.ROOT.name}-candidate"
    if rt.git_read(rt.ROOT, "branch", "--show-current") != "main":
        raise CacheDiagnosticRuntimeError("stable worktree is not on main")
    head = rt.git_read(rt.ROOT, "rev-parse", "HEAD")
    if rt.git_read(rt.ROOT, "rev-parse", "main") != head or rt.git_read(rt.ROOT, "rev-parse", "origin/main") != head:
        raise CacheDiagnosticRuntimeError("stable main refs are not synchronized")
    candidate_head = rt.git_read(candidate_root, "rev-parse", "HEAD")
    custody_expected = _exact_custody(rt, candidate_root)
    binary_path = Path(args.binary)
    model_path = Path(args.model)
    if rt.sha256_file(binary_path).upper() != rt.EXPECTED_BINARY_SHA256:
        raise CacheDiagnosticRuntimeError("diagnostic binary identity differs")
    model_identity = rt.verify_model_identity(model_path, evaluator["model"])
    protocol_v4 = evaluator["holostate_worker_protocol_v4"]
    predecessor_contract = evaluator["catalytic_swarm_0_v2"]
    live_contract = evaluator["holostate_live_contract"]
    task = next(item for item in rt.build_frozen_task_suite().tasks if item.task_id == TASK_ID)
    control = {
        "schema_version": 1,
        "operation": "catalytic-swarm-1-cache-diagnostic-control-v1",
        "started_at": rt.utc_now(),
        "status": "running",
        "contract_sha256": expected_contract_hash,
        "protocol_commit": head,
        "predecessor": predecessor,
        "generation_executed": False,
        "live_model_requests": 0,
        "automatic_promotion": False,
    }
    claim_json_once(paths["control"], control, root=state_root)
    control.update({"status": "complete", "control_qualification_v1": "pass", "finished_at": rt.utc_now()})
    write_json(paths["control"], control, root=state_root)
    readiness_control = predecessor_contract["readiness_control"]
    deadline_at = time.monotonic() + float(readiness_control["readiness_deadline_seconds"])
    readiness_record = {
        "schema_version": 1,
        "operation": "catalytic-swarm-1-cache-diagnostic-readiness-v1",
        "started_at": rt.utc_now(),
        "status": "running",
        "contract_sha256": expected_contract_hash,
        "automatic_promotion": False,
    }
    claim_json_once(paths["readiness"], readiness_record, root=state_root)
    sidecar = None
    stable_pids: set[int] | None = None
    readiness = None
    ledger = None
    completed_requests = 0
    custody_checks = 0
    host_memory_checks = 0
    observations: list[CacheProbeObservation] = []
    lease_pool = rt.PhysicalLeasePool(1)
    execution_error: BaseException | None = None
    result = {
        "schema_version": 1,
        "operation": "catalytic-swarm-1-cache-diagnostic",
        "started_at": rt.utc_now(),
        "status": "running",
        "contract_sha256": expected_contract_hash,
        "cache_diagnostic": "inconclusive",
        "cache_admission": "unadjudicated",
        "live_model_request_count": 0,
        "automatic_promotion": False,
        "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
        "SOTA_SWARM_CLAIM": "LOCKED",
        "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
        "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
    }

    def require_boundary(label: str, *, require_host: bool) -> None:
        nonlocal custody_checks, host_memory_checks
        observed = _exact_custody(rt, candidate_root)
        rt.require_custody_snapshot(custody_expected, observed, boundary=label)
        custody_checks += 1
        if require_host:
            if sidecar is None or sidecar.process is None or readiness is None:
                raise CacheDiagnosticRuntimeError("post-request boundary lacks live sidecar")
            resource = rt.worker_resource_gate(sidecar, readiness, predecessor_contract)
            if resource.get("passed") is not True:
                raise CacheDiagnosticRuntimeError(f"{label}: resource gate failed")
            info = rt.process_info(sidecar.process.pid)
            if not isinstance(info, dict):
                raise CacheDiagnosticRuntimeError(f"{label}: process memory unavailable")
            rt.require_host_memory_growth(
                baseline_private_bytes=int(readiness["process_memory"]["private_bytes"]),
                current_private_bytes=int(info["private_bytes"]),
                ceiling_bytes=int(predecessor_contract["memory"]["host_cache_mib_ceiling"]) * rt.MIB,
                boundary=label,
            )
            host_memory_checks += 1

    def before_request(label: str) -> None:
        require_boundary(f"pre-request:cs1-cache-diagnostic-{label}", require_host=False)
        sidecar.wait_for_fresh_wddm(
            f"pre-request:cs1-cache-diagnostic-{label}",
            float(readiness_control["fresh_sample_boundary_law"]["maximum_wait_seconds"]),
        )

    def after_completed_request(label: str) -> None:
        nonlocal completed_requests
        completed_requests += 1
        result["live_model_request_count"] = completed_requests
        sidecar.wait_for_fresh_wddm(
            f"post-request:cs1-cache-diagnostic-{label}",
            float(readiness_control["fresh_sample_boundary_law"]["maximum_wait_seconds"]),
        )
        require_boundary(f"post-request:cs1-cache-diagnostic-{label}", require_host=True)

    try:
        discovery = rt.query_listener_pids(
            rt.STABLE_PORT,
            **rt.listener_retry_options(readiness_control, deadline_at=deadline_at),
        )
        if not discovery.passed or len(discovery.pids) != 1:
            raise CacheDiagnosticRuntimeError("stable listener qualification failed")
        stable_pids = set(discovery.pids)
        if not rt.health_ok(rt.STABLE_PORT, timeout=3):
            raise CacheDiagnosticRuntimeError("stable health unavailable")
        sidecar = rt.LiveSidecar(
            binary_path,
            model_path,
            evaluator,
            live_contract,
            detached=False,
            stable_pids=stable_pids,
            readiness_control=readiness_control,
            prelaunch_evidence={"stable_listener_discovery": discovery.to_dict()},
            readiness_deadline_at=deadline_at,
            state_root=state_root,
            wddm_policy=rt.catalytic_swarm_1_wddm_policy(predecessor_contract),
        )
        readiness = sidecar.launch()
        sidecar.exact_ownership("catalytic-swarm-1-cache-diagnostic-readiness-final", deadline_at=deadline_at)
        sidecar.wait_for_fresh_wddm(
            "readiness-admission",
            float(readiness_control["fresh_sample_boundary_law"]["maximum_wait_seconds"]),
            deadline_at=deadline_at,
        )
        readiness_record.update({
            "status": "complete",
            "readiness_v1": "pass",
            "stable_pids": sorted(stable_pids),
            "sidecar_pid": sidecar.process.pid if sidecar.process else None,
            "sidecar": readiness,
            "model_identity": model_identity,
            "finished_at": rt.utc_now(),
        })
        write_json(paths["readiness"], readiness_record, root=state_root)
        attempt = {
            "schema_version": 1,
            "operation": "catalytic-swarm-1-cache-diagnostic",
            "started_at": rt.utc_now(),
            "status": "running",
            "contract_sha256": expected_contract_hash,
            "maximum_model_requests": MAX_MODEL_REQUESTS,
            "automatic_promotion": False,
        }
        claim_json_once(paths["attempt"], attempt, root=state_root)
        claim_json_once(paths["result"], result, root=state_root)
        ledger = DiagnosticLedger(paths["ledger"], root=state_root)
        before_request("common-root-warm")
        with lease_pool.lease() as lease_id:
            warm_summary, _warm_metadata, system_message, system_identity = rt.catalytic_swarm_1_warm_request(
                sidecar,
                protocol_v4,
                predecessor_contract,
                readiness,
                task,
                request_sequence_index=1,
                lease_id=lease_id,
                model_request_completed=lambda _label: after_completed_request("common-root-warm"),
            )
        ledger.append({
            "kind": "warm",
            "label": "common-root-warm",
            "request_sequence_index": 1,
            "prompt_tokens": warm_summary["prompt_tokens"],
            "cached_prompt_tokens": warm_summary["cached_prompt_tokens"],
            "fresh_prompt_tokens": warm_summary["fresh_prompt_tokens"],
            "completion_tokens": warm_summary["completion_tokens"],
            "public_root_sha256": warm_summary["public_root_sha256"],
            "raw_sse_persisted": False,
            "reasoning_text_persisted": False,
            "hidden_data_persisted": False,
        })
        serial_plan = next(plan for plan in build_all_arm_plans() if plan.arm == "serial-chain")
        first_turn = serial_plan.turns[0]
        realistic_assignment = render_turn_assignment(task, first_turn, ())
        probe_specs = (
            ("minimal-branch", "Return exactly the canonical candidate object for C00.", _minimal_lane(rt)),
            ("realistic-first-turn", realistic_assignment, rt.catalytic_swarm_1_lane(first_turn)),
        )
        for sequence_index, (label, assignment, lane) in enumerate(probe_specs, start=2):
            before_request(label)
            with lease_pool.lease():
                observation, metadata = _probe_request(
                    rt,
                    sidecar=sidecar,
                    protocol_v4=protocol_v4,
                    task=task,
                    label=label,
                    assignment=assignment,
                    lane=lane,
                    system_message=system_message,
                    system_identity=system_identity,
                    request_sequence_index=sequence_index,
                    on_completed=after_completed_request,
                )
            ledger.append(metadata)
            observations.append(observation)
            result["observations"] = [item.to_dict() for item in observations]
            result["probe_verdicts"] = [classify_probe(item).to_dict() for item in observations]
            write_json(paths["result"], result, root=state_root)
            if not observation.transport_passed or not observation.token_evidence_passed:
                raise CacheDiagnosticRuntimeError(f"{label}: transport or token evidence failed after observation persistence")
        diagnostic = classify_diagnostic(observations)
        result.update({
            "status": "complete",
            "cache_diagnostic": diagnostic.verdict,
            "cache_admission": diagnostic.cache_admission,
            "diagnostic": diagnostic.to_dict(),
        })
    except BaseException as exc:
        execution_error = exc
        result.update({
            "status": "complete",
            "error": f"{type(exc).__name__}: {exc}",
            "cache_diagnostic": "instrumentation-reject" if isinstance(exc, (CacheDiagnosticError, ValueError, json.JSONDecodeError)) else "inconclusive",
            "cache_admission": "unadjudicated",
        })
    finally:
        cleanup = rt.safe_sidecar_cleanup(sidecar) if sidecar is not None else rt.readiness_v3_no_sidecar_cleanup(readiness_control, stable_pids)
        cleanup_gate = rt.cleanup_integrity(cleanup, stable_pids)
        ledger_snapshot = ledger.snapshot() if ledger is not None else None
        freshness = cleanup.get("wddm", {}).get("freshness_boundaries", []) if isinstance(cleanup, Mapping) else []
        labels = [item.get("boundary") for item in freshness if isinstance(item, Mapping) and isinstance(item.get("boundary"), str)]
        reconciliation = reconcile_request_boundaries(
            labels,
            completed_requests=completed_requests,
            custody_checks=custody_checks,
            host_memory_checks=host_memory_checks,
            ledger_records=(ledger_snapshot or {}).get("record_count", 0),
        )
        predecessor_after = _preserve_predecessor(rt, evaluator)
        final_custody = _exact_custody(rt, candidate_root)
        isolation_passed = final_custody == custody_expected and rt.git_read(rt.ROOT, "rev-parse", "HEAD") == head and rt.git_read(candidate_root, "rev-parse", "HEAD") == candidate_head
        safety = cleanup_gate.get("passed") is True and reconciliation["passed"] is True and isolation_passed and predecessor_after["preserved"] is True
        if result.get("cache_diagnostic") in {"reviewable-accept", "reject"} and not safety:
            result["cache_diagnostic"] = "inconclusive"
            result["cache_admission"] = "unadjudicated"
        result.update({
            "finished_at": rt.utc_now(),
            "completed_model_requests": completed_requests,
            "custody_checks": custody_checks,
            "host_memory_checks": host_memory_checks,
            "ledger": ledger_snapshot,
            "terminal_reconciliation": reconciliation,
            "lease_evidence": {
                "physical_slots": lease_pool.physical_slots,
                "lease_count": lease_pool.lease_count,
                "maximum_concurrent": lease_pool.max_concurrent,
                "active_after": lease_pool.active_count,
            },
            "cleanup": rt.compact_catalytic_swarm_1_cleanup(cleanup),
            "cleanup_gate": cleanup_gate,
            "isolation_passed": isolation_passed,
            "predecessor_after": predecessor_after,
            "protocol_safety_passed": safety,
            "authority_consumed": True,
            "no_retry": True,
            "automatic_promotion": False,
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
        })
        if paths["result"].exists():
            write_json(paths["result"], result, root=state_root)
        if paths["attempt"].exists():
            attempt = json.loads(paths["attempt"].read_text(encoding="utf-8"))
            attempt.update({
                "status": "complete",
                "finished_at": result["finished_at"],
                "cache_diagnostic": result["cache_diagnostic"],
                "result_sha256": sha256_bytes(paths["result"].read_bytes()) if paths["result"].is_file() else None,
                "ledger_sha256": sha256_bytes(paths["ledger"].read_bytes()) if paths["ledger"].is_file() else None,
                "authority_consumed": True,
                "no_retry": True,
                "automatic_promotion": False,
            })
            write_json(paths["attempt"], attempt, root=state_root)
    if isinstance(execution_error, (KeyboardInterrupt, SystemExit)):
        raise execution_error
    return result
