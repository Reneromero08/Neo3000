#!/usr/bin/env python3
"""Live, repeatable runtime for Catalytic Inference Bench 0.

The protocol/specification module remains pure.  This module owns only live
custody, one-slot execution, in-memory streaming, request-boundary checkpoints,
and metadata-only closure.  ``holostate_live`` is deliberately imported only
inside the default adapter so importing this module cannot form a cycle with
the command dispatcher.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import inspect
import json
import os
import re
import shutil
import stat
import tempfile
import time
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence


STATE_SCHEMA_VERSION = 1
MODEL_ALIAS = "agents-a1-holostate"
MIB = 1024 * 1024
HOST_PRIVATE_GROWTH_CEILING_BYTES = 4096 * MIB
WDDM_PEAK_CEILING_BYTES = 6000 * MIB
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TRANSFORM_REQUEST_IDS = frozenset({"transform-1", "transform-2", "transform-3"})
TRANSFORM_RELATION_OPERATORS = frozenset(
    {"combine", "oppose", "eliminate", "refine", "reconcile"}
)
TRANSFORM_SEMANTIC_GATES = frozenset(
    {
        "transform-static-schema",
        "transform-parent-context",
        "transform-consumption-binding",
        "relational-change-schema",
        "relational-change-candidate-duplicates",
        "relational-change-candidate-coverage",
        "relational-change-public-evidence",
        "relation-edge-schema",
        "relation-edge-candidate-membership",
        "relation-edge-duplicates",
        "relation-edge-public-evidence",
        "relation-edge-coverage",
    }
)
CANDIDATE_ID_PATTERN = re.compile(r"^C(?:[0-5][0-9]|6[0-3])$")
SHA256_PATTERN = re.compile(r"^[A-F0-9]{64}$")
STATE_FILENAMES = (
    "manifest.json",
    "checkpoint.json",
    "result.json",
    "closure.json",
    "run.lock",
)
FORBIDDEN_PERSISTED_KEYS = frozenset(
    {
        "content",
        "messages",
        "output",
        "payload",
        "raw",
        "raw_output",
        "raw_sse",
        "reasoning",
        "reasoning_content",
        "rendered_prompt",
        "sse",
        "text",
        "token_ids",
        "user_message",
    }
)
FORBIDDEN_PRIVATE_MARKERS = ("hidden_examples", "answer_candidate_id", "answer_key")
CLAIMS_LOCKED = {
    "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
    "SOTA_SWARM_CLAIM": "LOCKED",
    "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
    "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
    "DEEP": "DISABLED",
    "automatic_promotion": False,
}


class CatalyticInferenceRuntimeError(ValueError):
    """A live boundary is unsafe, malformed, or incompatible with resume."""


class RuntimeAdapter(Protocol):
    """Mockable live seams; protocol/scoring logic stays outside this interface."""

    def preflight(
        self,
        *,
        args: Any,
        repository_root: Path,
        run_root: Path,
        allowed_paths: Sequence[Path],
    ) -> Mapping[str, Any]: ...

    def create_lease_pool(self, physical_slots: int) -> Any: ...

    def launch_sidecar(
        self, *, preflight: Mapping[str, Any], run_id: str
    ) -> tuple[Any, Mapping[str, Any]]: ...

    def prompt_geometry(
        self, *, sidecar: Any, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def execute_request(
        self,
        *,
        sidecar: Any,
        payload: Mapping[str, Any],
        request: Any,
    ) -> Any: ...

    def boundary_custody(
        self,
        *,
        preflight: Mapping[str, Any],
        sidecar: Any,
        boundary: str,
    ) -> Mapping[str, Any]: ...

    def resource_summary(
        self, *, sidecar: Any, boundary: str
    ) -> Mapping[str, Any]: ...

    def cleanup(
        self, *, sidecar: Any | None, preflight: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def postflight(self, *, preflight: Mapping[str, Any]) -> Mapping[str, Any]: ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _json_sha256(value: Any) -> str:
    return _sha256(_canonical_json_bytes(value))


def _porcelain_v2_status_is_clean(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return all(
        not line or line.startswith("# ")
        for line in value.splitlines()
    )


def _path_is_link_or_reparse(path: Path) -> bool:
    metadata = os.lstat(path)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & 0x400)


def _require_safe_state_ancestry(repository: Path, target: Path) -> None:
    try:
        relative = target.relative_to(repository)
    except ValueError as exc:
        raise CatalyticInferenceRuntimeError(
            "runtime state must remain lexically below the repository"
        ) from exc
    current = repository
    for part in relative.parts:
        current = current / part
        if not os.path.lexists(current):
            continue
        if _path_is_link_or_reparse(current):
            raise CatalyticInferenceRuntimeError(
                f"runtime state ancestry contains a link or reparse point: {current.name}"
            )
        if current != target and not current.is_dir():
            raise CatalyticInferenceRuntimeError(
                f"runtime state ancestor is not a directory: {current.name}"
            )


def validate_run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_PATTERN.fullmatch(value):
        raise CatalyticInferenceRuntimeError(
            "--run-id must be 1-64 safe ASCII letters, digits, dot, underscore, or dash"
        )
    if value in {".", ".."} or value.endswith("."):
        raise CatalyticInferenceRuntimeError("--run-id is not a safe path component")
    return value


def _arg(args: Any, name: str) -> Any:
    if isinstance(args, Mapping):
        return args.get(name)
    return getattr(args, name, None)


def _validate_persistable(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CatalyticInferenceRuntimeError(f"{path} has a non-string key")
            lowered = key.casefold()
            if lowered in FORBIDDEN_PERSISTED_KEYS:
                raise CatalyticInferenceRuntimeError(
                    f"{path} contains forbidden persisted field {key!r}"
                )
            if any(marker in lowered for marker in FORBIDDEN_PRIVATE_MARKERS):
                raise CatalyticInferenceRuntimeError(
                    f"{path} contains protected evaluator field {key!r}"
                )
            _validate_persistable(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_persistable(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(marker in lowered for marker in FORBIDDEN_PRIVATE_MARKERS):
            raise CatalyticInferenceRuntimeError(
                f"{path} contains protected evaluator material"
            )
    elif value is not None and type(value) not in {bool, int, float}:
        raise CatalyticInferenceRuntimeError(f"{path} is not normalized JSON metadata")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _validate_persistable(value)
    encoded = _canonical_json_bytes(value) + b"\n"
    if len(encoded) > 4 * 1024 * 1024:
        raise CatalyticInferenceRuntimeError("normalized checkpoint exceeds 4 MiB")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalyticInferenceRuntimeError(f"invalid runtime state file: {path.name}") from exc
    if not isinstance(value, dict):
        raise CatalyticInferenceRuntimeError(f"runtime state file is not an object: {path.name}")
    _validate_persistable(value)
    return value


class _RunLock(AbstractContextManager["_RunLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.descriptor: int | None = None

    def __enter__(self) -> "_RunLock":
        try:
            self.descriptor = os.open(
                self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
        except FileExistsError as exc:
            raise CatalyticInferenceRuntimeError(
                "run ID is already active or has an uncertain stale lock"
            ) from exc
        os.write(self.descriptor, str(os.getpid()).encode("ascii"))
        os.fsync(self.descriptor)
        return self

    def release(self) -> None:
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


def _protocol_module() -> Any:
    try:
        return importlib.import_module("catalytic_inference_bench_0")
    except ModuleNotFoundError:
        package = __package__
        if package:
            return importlib.import_module(".catalytic_inference_bench_0", package)
        raise


def _public_preflight(preflight: Mapping[str, Any]) -> dict[str, Any]:
    metadata = preflight.get("metadata")
    if not isinstance(metadata, Mapping):
        raise CatalyticInferenceRuntimeError("preflight adapter returned no normalized metadata")
    value = json.loads(_canonical_json_bytes(metadata))
    _validate_persistable(value)
    return value


def _observation_dict(observation: Any) -> dict[str, Any]:
    if hasattr(observation, "to_dict"):
        value = observation.to_dict()
    elif dataclasses.is_dataclass(observation):
        value = dataclasses.asdict(observation)
    else:
        raise CatalyticInferenceRuntimeError("protocol observation is not serializable")
    if not isinstance(value, dict):
        raise CatalyticInferenceRuntimeError("protocol observation is not an object")
    _validate_persistable(value)
    return value


def _restore_observation(protocol: Any, value: Mapping[str, Any]) -> Any:
    cls = protocol.NormalizedObservation
    fields = {field.name for field in dataclasses.fields(cls)}
    if set(value) != fields:
        raise CatalyticInferenceRuntimeError("checkpoint observation field set changed")
    restored = dict(value)
    for name in (
        "parent_ids",
        "ancestor_ids",
        "source_transform_ids",
        "consumed_artifact_sha256",
    ):
        if name in restored:
            restored[name] = tuple(restored[name])
    observation = cls(**restored)
    protocol.validate_normalized_metadata(observation)
    return observation


def _validated_semantic_diagnostic(
    exc: BaseException,
    *,
    boundary: str,
    error_message_sha256: str,
) -> dict[str, Any] | None:
    semantic_diagnostic = getattr(exc, "semantic_diagnostic", None)
    exception_class = type(exc)
    if (
        not isinstance(semantic_diagnostic, Mapping)
        or exception_class.__name__ != "CatalyticInferenceBench0Error"
        or exception_class.__module__.split(".")[-1]
        != "catalytic_inference_bench_0"
    ):
        return None
    try:
        normalized = json.loads(_canonical_json_bytes(semantic_diagnostic))
        if set(normalized) != {
            "request_id",
            "output_candidate_ranking",
            "relational_change_candidate_ids",
            "relation_operator",
            "relation_edge_pairs",
            "failed_semantic_gate",
            "error_message_sha256",
        }:
            return None
        request_id = normalized["request_id"]
        ranking = normalized["output_candidate_ranking"]
        change_ids = normalized["relational_change_candidate_ids"]
        operator = normalized["relation_operator"]
        edge_pairs = normalized["relation_edge_pairs"]
        gate = normalized["failed_semantic_gate"]
        diagnostic_sha256 = normalized["error_message_sha256"]
        valid_ranking = (
            isinstance(ranking, list)
            and 0 <= len(ranking) <= 3
            and all(
                isinstance(item, str)
                and CANDIDATE_ID_PATTERN.fullmatch(item) is not None
                for item in ranking
            )
            and len(set(ranking)) == len(ranking)
        )
        valid_change_ids = (
            isinstance(change_ids, list)
            and 0 <= len(change_ids) <= 3
            and all(
                isinstance(item, str)
                and CANDIDATE_ID_PATTERN.fullmatch(item) is not None
                for item in change_ids
            )
        )
        if (
            not isinstance(request_id, str)
            or request_id not in TRANSFORM_REQUEST_IDS
            or request_id != boundary
            or not valid_ranking
            or not valid_change_ids
            or (
                operator is not None
                and (
                    not isinstance(operator, str)
                    or operator not in TRANSFORM_RELATION_OPERATORS
                )
            )
            or not isinstance(edge_pairs, list)
            or not 0 <= len(edge_pairs) <= 3
            or not isinstance(gate, str)
            or gate not in TRANSFORM_SEMANTIC_GATES
            or not isinstance(diagnostic_sha256, str)
            or SHA256_PATTERN.fullmatch(diagnostic_sha256) is None
            or diagnostic_sha256 != error_message_sha256
        ):
            return None
        for pair in edge_pairs:
            if not isinstance(pair, Mapping) or set(pair) != {
                "subject_candidate_id",
                "object_candidate_id",
            }:
                return None
            for candidate_id in pair.values():
                if candidate_id is not None and (
                    not isinstance(candidate_id, str)
                    or CANDIDATE_ID_PATTERN.fullmatch(candidate_id) is None
                ):
                    return None
        _validate_persistable(normalized)
        return normalized
    except (CatalyticInferenceRuntimeError, TypeError, ValueError, OverflowError):
        return None


def _safe_exception(exc: BaseException, *, boundary: str) -> dict[str, Any]:
    message = str(exc)
    result = {
        "boundary": boundary,
        "error_type": type(exc).__name__,
        "error_message_sha256": _sha256(message.encode("utf-8", errors="replace")),
        "error_message_characters": len(message),
    }
    semantic_diagnostic = _validated_semantic_diagnostic(
        exc,
        boundary=boundary,
        error_message_sha256=result["error_message_sha256"],
    )
    if semantic_diagnostic is not None:
        result["semantic_diagnostic"] = semantic_diagnostic
    return result


def _valid_resource_bytes(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _bounded_resource_exception(exc: BaseException) -> dict[str, str]:
    message = str(exc)
    return {
        "exception_type": type(exc).__name__[:128] or "Exception",
        "exception_message_sha256": _sha256(
            message.encode("utf-8", errors="replace")
        ),
    }


def _resource_error_observation(
    *, boundary: str, exc: BaseException
) -> dict[str, Any]:
    return {
        "boundary": boundary,
        "observation_state": "observation-error",
        **_bounded_resource_exception(exc),
        "observed_at": _utc_now(),
    }


def _normalize_resource_observation(
    value: Mapping[str, Any], *, boundary: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("resource observer returned a non-object")
    observed_at = value.get("observed_at")
    if isinstance(observed_at, str) and 1 <= len(observed_at) <= 64:
        try:
            parsed_observed_at = datetime.fromisoformat(observed_at)
            if parsed_observed_at.tzinfo is None:
                raise ValueError("resource timestamp has no timezone")
        except ValueError:
            observed_at = None
    else:
        observed_at = None
    result: dict[str, Any] = {
        "boundary": boundary,
        "observed_at": observed_at or _utc_now(),
    }
    host = _valid_resource_bytes(value.get("host_private_bytes"))
    wddm = _valid_resource_bytes(value.get("wddm_peak_bytes"))
    if host is not None:
        result["host_private_bytes"] = host
        if type(value.get("host_private_ceiling_exceeded")) is bool:
            result["host_private_ceiling_exceeded"] = value[
                "host_private_ceiling_exceeded"
            ]
    if wddm is not None:
        result["wddm_peak_bytes"] = wddm
        result["wddm_ceiling_exceeded"] = (
            value.get("wddm_ceiling_exceeded") is True
            or wddm > WDDM_PEAK_CEILING_BYTES
        )

    exception_type = value.get("exception_type")
    exception_sha = value.get("exception_message_sha256")
    bounded_error = (
        isinstance(exception_type, str)
        and 1 <= len(exception_type) <= 128
        and isinstance(exception_sha, str)
        and re.fullmatch(r"[0-9A-Fa-f]{64}", exception_sha) is not None
    )
    if bounded_error:
        result["exception_type"] = exception_type
        result["exception_message_sha256"] = exception_sha.upper()

    declared_state = value.get("observation_state")
    if bounded_error or declared_state == "observation-error":
        result["observation_state"] = "observation-error"
        if not bounded_error:
            result.update(
                _bounded_resource_exception(
                    RuntimeError("resource observation error had no bounded identity")
                )
            )
    elif declared_state not in {None, "measured", "unavailable"}:
        result["observation_state"] = "observation-error"
        result.update(
            _bounded_resource_exception(
                RuntimeError("resource observation declared an invalid state")
            )
        )
    elif declared_state == "unavailable":
        result["observation_state"] = "unavailable"
    elif host is not None and wddm is not None:
        result["observation_state"] = "measured"
    else:
        result["observation_state"] = "unavailable"
    return result


def _observe_resource(
    live: RuntimeAdapter, *, sidecar: Any, boundary: str
) -> dict[str, Any]:
    try:
        value = live.resource_summary(sidecar=sidecar, boundary=boundary)
        return _normalize_resource_observation(value, boundary=boundary)
    except Exception as exc:
        return _resource_error_observation(boundary=boundary, exc=exc)


def _validated_persisted_resource_observation(
    value: Any, *, boundary: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CatalyticInferenceRuntimeError(
            "checkpoint resource observation is not an object"
        )
    normalized = _normalize_resource_observation(value, boundary=boundary)
    if dict(value) != normalized:
        raise CatalyticInferenceRuntimeError(
            "checkpoint resource observation is not exact normalized metadata"
        )
    return normalized


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalized_transport(execution: Any, *, rendered_tokens: int, max_tokens: int) -> dict[str, Any]:
    content = _get(execution, "content")
    reasoning = _get(execution, "reasoning_content", "")
    tool_calls = _get(execution, "tool_calls", [])
    prompt_tokens = _get(execution, "prompt_tokens")
    cached_tokens = _get(execution, "cached_prompt_tokens")
    completion_tokens = _get(execution, "completion_tokens")
    generated_ids = _get(execution, "generated_token_ids")
    generated_count = _get(execution, "generated_token_count")
    count_match = _get(execution, "completion_token_count_match")
    generated_sha256 = _get(execution, "generated_token_sha256")
    nonempty_array_events = _get(execution, "nonempty_token_array_event_count")
    empty_array_events = _get(execution, "empty_token_array_event_count")
    token_merge_modes = _get(execution, "token_merge_modes")
    terminal_stop = _get(execution, "terminal_stop_evidence")
    finish_reason = _get(execution, "finish_reason")
    http_status = _get(execution, "http_status")
    event_count = _get(execution, "event_count")
    if not isinstance(content, str) or not content:
        raise CatalyticInferenceRuntimeError("strict structured response content is empty")
    if reasoning not in {"", None}:
        raise CatalyticInferenceRuntimeError("reasoning channel must remain empty")
    if tool_calls not in ([], None):
        raise CatalyticInferenceRuntimeError("tool calls are forbidden in the bench")
    if http_status != 200 or finish_reason != "stop":
        raise CatalyticInferenceRuntimeError("stream transport did not finish with HTTP 200 / stop")
    integer_fields = (
        prompt_tokens,
        cached_tokens,
        completion_tokens,
        generated_count,
        event_count,
        nonempty_array_events,
        empty_array_events,
    )
    if any(isinstance(item, bool) or not isinstance(item, int) for item in integer_fields):
        raise CatalyticInferenceRuntimeError("stream token/event accounting is incomplete")
    if prompt_tokens != rendered_tokens or cached_tokens < 0 or cached_tokens > prompt_tokens:
        raise CatalyticInferenceRuntimeError("rendered/prompt/cache token accounting differs")
    if completion_tokens <= 0 or completion_tokens > max_tokens:
        raise CatalyticInferenceRuntimeError("completion token bound failed")
    if (
        not isinstance(generated_ids, list)
        or any(isinstance(item, bool) or not isinstance(item, int) for item in generated_ids)
        or len(generated_ids) != generated_count
        or generated_sha256 != _json_sha256(generated_ids)
        or not isinstance(token_merge_modes, Mapping)
    ):
        raise CatalyticInferenceRuntimeError(
            "in-memory generated-token evidence is internally inconsistent"
        )
    if generated_count == 0 and count_match is False:
        if (
            generated_sha256 != _json_sha256([])
            or nonempty_array_events != 0
            or empty_array_events != 1
            or not isinstance(token_merge_modes, Mapping)
            or token_merge_modes.get("ignored-empty") != 1
            or any(
                name not in {"absent", "ignored-empty"}
                for name in token_merge_modes
            )
            or not isinstance(terminal_stop, Mapping)
            or terminal_stop.get("observed") is not True
            or terminal_stop.get("stop") is not True
            or terminal_stop.get("stop_type") != "eos"
            or terminal_stop.get("stopping_word") != ""
            or terminal_stop.get("verbose_token_array_length") != 0
            or isinstance(terminal_stop.get("event_index"), bool)
            or not isinstance(terminal_stop.get("event_index"), int)
            or not 1 <= terminal_stop["event_index"] <= event_count
        ):
            raise CatalyticInferenceRuntimeError(
                "empty token-array fallback lacks exact terminal EOS evidence"
            )
        generated_token_evidence_mode = "usage-plus-source-bound-terminal-eos"
        full_generated_sequence_known = False
    elif count_match is True and generated_count == completion_tokens:
        generated_token_evidence_mode = "exact-count-match"
        full_generated_sequence_known = True
    else:
        raise CatalyticInferenceRuntimeError(
            "nonempty generated-token evidence contradicts usage accounting"
        )
    if event_count <= 0:
        raise CatalyticInferenceRuntimeError("in-memory SSE stream contained no events")
    return {
        "structured_content": content,
        "metadata": {
            "http_status": http_status,
            "event_count": event_count,
            "prompt_tokens": prompt_tokens,
            "cached_prompt_tokens": cached_tokens,
            "fresh_prompt_tokens": prompt_tokens - cached_tokens,
            "completion_tokens": completion_tokens,
            "finish_reason": finish_reason,
            "generated_token_count": generated_count,
            "generated_token_sha256": generated_sha256,
            "generated_token_evidence_mode": generated_token_evidence_mode,
            "completion_token_count_match": count_match,
            "full_generated_sequence_known": full_generated_sequence_known,
            "nonempty_token_array_event_count": nonempty_array_events,
            "empty_token_array_event_count": empty_array_events,
            "token_merge_modes": dict(token_merge_modes),
            "terminal_stop_evidence": dict(terminal_stop)
            if isinstance(terminal_stop, Mapping)
            else None,
            "reasoning_channel_empty": True,
            "tool_call_count": 0,
            "total_time_seconds": float(_get(execution, "total_time_s", 0.0) or 0.0),
        },
    }


def _extract_ranked_artifact(
    protocol: Any, request: Any, structured: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Reduce validated output to the typed relational artifact sent to children."""
    if getattr(request, "request_id") in {
        getattr(protocol, "WARM_ID"),
        getattr(protocol, "RESTORE_ID"),
    }:
        return None
    lineage_fields = {
        "request_id",
        "parent_ids",
        "ancestor_ids",
        "depth",
        "public_system_root_sha256",
        "root_status",
    }
    body = {key: structured[key] for key in sorted(structured) if key not in lineage_fields}
    if not body:
        raise CatalyticInferenceRuntimeError("candidate request produced no relational artifact")
    artifact = {
        "producer_request_id": request.request_id,
        "artifact_kind": str(getattr(request, "phase")),
        "ranked_structure": body,
        "artifact_sha256": _json_sha256(body),
    }
    protocol.validate_no_hidden_leak(artifact)
    if len(_canonical_json_bytes(artifact)) > 4096:
        raise CatalyticInferenceRuntimeError("normalized ranked artifact exceeds 4096 bytes")
    return artifact


def _runtime_request(
    protocol: Any,
    request: Any,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[Any, list[dict[str, Any]]]:
    parent_ids = tuple(getattr(request, "parent_ids"))
    actual: list[dict[str, Any]] = []
    for parent_id in parent_ids:
        parent = artifacts.get(parent_id)
        if parent is None:
            raise CatalyticInferenceRuntimeError(
                f"request {request.request_id} lacks actual parent artifact {parent_id}"
            )
        if request.request_id == protocol.RESTORE_ID:
            # Restoration proves slot/root state only.  It receives a typed
            # extraction receipt, never candidate rankings or scores.
            actual.append(
                {
                    "producer_request_id": parent_id,
                    "artifact_kind": "extraction-receipt",
                    "artifact_sha256": parent["artifact_sha256"],
                }
            )
        else:
            actual.append(json.loads(_canonical_json_bytes(parent)))
    if len(actual) > 3:
        raise CatalyticInferenceRuntimeError("parent artifact fan-in exceeds three")
    assignment = json.loads(_canonical_json_bytes(dict(request.assignment)))
    assignment["actual_parent_artifacts"] = actual
    assignment["artifact_visibility"] = "exact-direct-parents-only"
    dynamic = dataclasses.replace(request, assignment=assignment)
    return dynamic, actual


def _build_payload(
    protocol: Any,
    request: Any,
    observations: Sequence[Any],
    fallback_artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    builder = protocol.build_model_request
    parameters = inspect.signature(builder).parameters
    kwargs: dict[str, Any] = {"model": MODEL_ALIAS, "stream": True}
    validator_kwargs: dict[str, Any] = {}
    if "parent_observations" in parameters:
        kwargs["parent_observations"] = tuple(observations)
        validator_kwargs["parent_observations"] = tuple(observations)
        payload = builder(request, **kwargs)
        actual_parents = [
            dict(item)
            for item in protocol.build_dynamic_parent_context(
                request, tuple(observations)
            )
        ]
    else:
        dynamic_request, actual_parents = _runtime_request(
            protocol, request, fallback_artifacts
        )
        request = dynamic_request
        if "parent_artifacts" in parameters:
            kwargs["parent_artifacts"] = list(actual_parents)
            validator_kwargs["parent_artifacts"] = list(actual_parents)
        payload = builder(request, **kwargs)
    # Validate the pure logical payload before adding server-only telemetry
    # flags.  The corrected spec intentionally rejects transport extensions.
    protocol.validate_model_request(request, payload, **validator_kwargs)
    payload = dict(payload)
    payload["stream_options"] = {"include_usage": True}
    payload["cache_prompt"] = True
    payload["return_tokens"] = True
    payload["return_progress"] = True
    payload["verbose"] = True
    protocol.validate_no_hidden_leak(payload)
    messages = payload.get("messages")
    if not isinstance(messages, list) or messages[0] != {
        "role": "system",
        "content": request.system_root,
    }:
        raise CatalyticInferenceRuntimeError("runtime changed the exact public system root")
    if payload.get("stream") is not True:
        raise CatalyticInferenceRuntimeError("runtime requires in-memory SSE streaming")
    if "stop" in payload:
        raise CatalyticInferenceRuntimeError("runtime forbids request stop sequences")
    if payload.get("stream_options") != {"include_usage": True}:
        raise CatalyticInferenceRuntimeError("runtime requires terminal SSE usage accounting")
    if payload.get("cache_prompt") is not True:
        raise CatalyticInferenceRuntimeError("protocol request must enable exact prompt caching")
    if payload.get("return_tokens") is not True:
        raise CatalyticInferenceRuntimeError("protocol request must request token evidence")
    return payload, actual_parents


def _cache_adjudication(
    *,
    terminal: int,
    common_prefix: int,
    prompt_tokens: int,
    cached_tokens: int,
    completion_tokens: int,
    warm: bool,
) -> dict[str, Any]:
    try:
        root_law = importlib.import_module("catalytic_swarm_1_v2_root_law")
    except ModuleNotFoundError:
        root_law = importlib.import_module(".catalytic_swarm_1_v2_root_law", __package__)
    observation = root_law.RootCacheObservation(
        public_root_terminal_token_index=terminal,
        common_prefix_tokens=common_prefix,
        legacy_required_cached_prompt_tokens=common_prefix,
        actual_cached_prompt_tokens=cached_tokens,
        branch_prompt_tokens=prompt_tokens,
        fresh_prompt_tokens=prompt_tokens - cached_tokens,
        completion_tokens=completion_tokens,
        response_completed=True,
        transport_passed=True,
        token_evidence_passed=True,
    )
    admission = root_law.adjudicate_root_cache(observation).to_dict()
    return {
        "adjudicated": True,
        "required": not warm,
        "admitted": bool(admission["admitted"]),
        "classification": admission["classification"],
        "public_root_terminal_token_index": terminal,
        "common_prefix_tokens": common_prefix,
        "actual_cached_prompt_tokens": cached_tokens,
        "root_margin_tokens": admission["root_margin_tokens"],
    }


def _score(
    scorer: Callable[..., tuple[int, int]],
    task: Any,
    candidate_id: str,
    *,
    hidden: bool,
) -> dict[str, Any]:
    passed, total = scorer(task, candidate_id, hidden=hidden)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (passed, total)):
        raise CatalyticInferenceRuntimeError("scorer returned invalid counts")
    if passed > total:
        raise CatalyticInferenceRuntimeError("scorer passed count exceeds total")
    return {"candidate_id": candidate_id, "passed": passed, "total": total}


def _require_request_safety(
    *,
    request_id: str,
    before_custody: Mapping[str, Any],
    after_custody: Mapping[str, Any],
    before_resource: Mapping[str, Any],
    after_resource: Mapping[str, Any],
    host_baseline_bytes: int | None = None,
) -> None:
    for label, custody in (
        ("before", before_custody),
        ("after", after_custody),
    ):
        if not isinstance(custody, Mapping) or custody.get("passed") is not True:
            raise CatalyticInferenceRuntimeError(
                f"{request_id}: {label} custody boundary failed"
            )
    resources: list[Mapping[str, Any]] = []
    for resource in (before_resource, after_resource):
        if not isinstance(resource, Mapping):
            continue
        _require_measured_resource_ceiling(
            request_id=request_id,
            resource=resource,
            host_baseline_bytes=host_baseline_bytes,
        )
        resources.append(resource)
    hosts = [
        _valid_resource_bytes(resource.get("host_private_bytes"))
        for resource in resources
    ]
    if (
        len(hosts) == 2
        and hosts[0] is not None
        and hosts[1] is not None
        and hosts[1] - hosts[0] > HOST_PRIVATE_GROWTH_CEILING_BYTES
    ):
        raise CatalyticInferenceRuntimeError(
            f"{request_id}: host-private growth exceeded exploratory ceiling"
        )


def _require_measured_resource_ceiling(
    *,
    request_id: str,
    resource: Mapping[str, Any],
    host_baseline_bytes: int | None = None,
) -> None:
    host = _valid_resource_bytes(resource.get("host_private_bytes"))
    peak = _valid_resource_bytes(resource.get("wddm_peak_bytes"))
    baseline = _valid_resource_bytes(host_baseline_bytes)
    if host is not None and (
        resource.get("host_private_ceiling_exceeded") is True
        or (
            baseline is not None
            and host - baseline > HOST_PRIVATE_GROWTH_CEILING_BYTES
        )
    ):
        raise CatalyticInferenceRuntimeError(
            f"{request_id}: host-private growth exceeded exploratory ceiling"
        )
    if peak is not None and (
        peak > WDDM_PEAK_CEILING_BYTES
        or resource.get("wddm_ceiling_exceeded") is True
    ):
        raise CatalyticInferenceRuntimeError(
            f"{request_id}: WDDM peak exceeded exploratory ceiling"
        )


def _candidate_id(protocol: Any, structured: Mapping[str, Any], artifact: Mapping[str, Any] | None) -> str | None:
    for key in ("selected_candidate_id", "candidate_id"):
        value = structured.get(key)
        if isinstance(value, str):
            return value
    if artifact is None:
        return None
    ranked = artifact.get("ranked_structure")
    if isinstance(ranked, Mapping):
        for key in ("selected_candidate_id", "top_candidate_id", "candidate_id"):
            value = ranked.get(key)
            if isinstance(value, str):
                return value
        for key in ("candidate_ranking", "ranked_candidates", "ranking"):
            values = ranked.get(key)
            if isinstance(values, list) and values:
                first = values[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, Mapping) and isinstance(first.get("candidate_id"), str):
                    return first["candidate_id"]
    return None


def _ranked_candidate_ids(
    structured: Mapping[str, Any], artifact: Mapping[str, Any] | None
) -> tuple[str, ...]:
    """Extract an ordered, bounded candidate ranking from validated structure."""
    discovered: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and re.fullmatch(r"C(?:0[0-9]|[1-5][0-9]|6[0-3])", value):
            if value not in discovered:
                discovered.append(value)
        elif isinstance(value, Mapping):
            if isinstance(value.get("candidate_id"), str):
                add(value["candidate_id"])
        elif isinstance(value, list):
            for item in value:
                add(item)

    for key in (
        "candidate_ranking",
        "ranked_candidates",
        "ranked_candidate_ids",
        "ranking",
        "candidates",
        "selected_candidate_id",
        "top_candidate_id",
        "candidate_id",
    ):
        if key in structured:
            add(structured[key])
    if artifact is not None:
        ranked = artifact.get("ranked_structure")
        if isinstance(ranked, Mapping):
            for key in (
                "candidate_ranking",
                "ranked_candidates",
                "ranked_candidate_ids",
                "ranking",
                "candidates",
                "selected_candidate_id",
                "top_candidate_id",
                "candidate_id",
            ):
                if key in ranked:
                    add(ranked[key])
    if len(discovered) > 8:
        raise CatalyticInferenceRuntimeError("ranked artifact exceeds eight candidates")
    return tuple(discovered)


def _default_scorer() -> Callable[..., tuple[int, int]]:
    try:
        module = importlib.import_module("catalytic_advantage_tasks")
    except ModuleNotFoundError:
        module = importlib.import_module(".catalytic_advantage_tasks", __package__)
    return module.score_candidate


def _lease_accounting(pool: Any) -> dict[str, Any]:
    return {
        "physical_slots": 1,
        "lease_count": int(getattr(pool, "lease_count", 0)),
        "maximum_concurrent_leases": int(getattr(pool, "max_concurrent", 0)),
        "active_leases": int(getattr(pool, "active_count", 0)),
    }


def _aggregate_cost(
    request_records: Sequence[Mapping[str, Any]],
    resource_observations: Sequence[Mapping[str, Any]],
    *,
    readiness: Mapping[str, Any] | None,
) -> dict[str, Any]:
    cached = fresh = completion = 0
    wall = 0.0
    host_values: list[int] = []
    wddm_values: list[int] = []
    per_request_host_growth: list[int] = []
    for record in request_records:
        transport = record.get("transport", {})
        resources = record.get("resources", {})
        before = resources.get("before", {}) if isinstance(resources, Mapping) else {}
        after = resources.get("after", {}) if isinstance(resources, Mapping) else {}
        cached += int(transport.get("cached_prompt_tokens", 0))
        fresh += int(transport.get("fresh_prompt_tokens", 0))
        completion += int(transport.get("completion_tokens", 0))
        wall += float(transport.get("total_time_seconds", 0.0))
        before_host = _valid_resource_bytes(before.get("host_private_bytes"))
        after_host = _valid_resource_bytes(after.get("host_private_bytes"))
        if before_host is not None and after_host is not None:
            per_request_host_growth.append(max(0, after_host - before_host))

    complete_observations = 0
    observation_errors = 0
    for observation in resource_observations:
        host = _valid_resource_bytes(observation.get("host_private_bytes"))
        wddm = _valid_resource_bytes(observation.get("wddm_peak_bytes"))
        if host is not None:
            host_values.append(host)
        if wddm is not None:
            wddm_values.append(wddm)
        if (
            host is not None
            and wddm is not None
            and observation.get("observation_state") == "measured"
        ):
            complete_observations += 1
        if observation.get("observation_state") == "observation-error":
            observation_errors += 1

    if not host_values and not wddm_values:
        observability = "unavailable"
    elif (
        len(resource_observations) == 2 * len(request_records)
        and len(resource_observations) > 0
        and complete_observations == len(resource_observations)
    ):
        observability = "complete"
    else:
        observability = "partial"
    readiness_baseline = _valid_resource_bytes(
        readiness.get("private_bytes") if isinstance(readiness, Mapping) else None
    )
    readiness_growth = (
        [max(0, value - readiness_baseline) for value in host_values]
        if readiness_baseline is not None
        else []
    )
    measured_host_breach = any(
        observation.get("host_private_ceiling_exceeded") is True
        and _valid_resource_bytes(observation.get("host_private_bytes")) is not None
        for observation in resource_observations
    ) or any(value > HOST_PRIVATE_GROWTH_CEILING_BYTES for value in readiness_growth)
    measured_wddm_breach = any(
        value > WDDM_PEAK_CEILING_BYTES for value in wddm_values
    ) or any(
        observation.get("wddm_ceiling_exceeded") is True
        and _valid_resource_bytes(observation.get("wddm_peak_bytes")) is not None
        for observation in resource_observations
    )
    return {
        "fresh_prompt_tokens": fresh,
        "cached_prompt_tokens": cached,
        "completion_tokens": completion,
        "model_wall_time_seconds": round(wall, 6),
        "resource_observability": observability,
        "resource_observation_count": len(resource_observations),
        "complete_resource_observation_count": complete_observations,
        "resource_observation_error_count": observation_errors,
        "host_private_measurement_count": len(host_values),
        "wddm_measurement_count": len(wddm_values),
        "host_private_baseline_bytes": readiness_baseline,
        "maximum_host_private_bytes": max(host_values) if host_values else None,
        "peak_wddm_bytes": max(wddm_values) if wddm_values else None,
        "maximum_per_request_host_private_growth_bytes": (
            max(per_request_host_growth) if per_request_host_growth else None
        ),
        "maximum_host_private_growth_from_readiness_bytes": (
            max(readiness_growth) if readiness_growth else None
        ),
        "measured_host_ceiling_breach": measured_host_breach,
        "measured_wddm_ceiling_breach": measured_wddm_breach,
    }


def _checkpoint(
    *,
    protocol: Any,
    run_id: str,
    plan: Any,
    status: str,
    observations: Sequence[Any],
    request_records: Sequence[Mapping[str, Any]],
    resource_observations: Sequence[Mapping[str, Any]],
    artifacts: Mapping[str, Mapping[str, Any]],
    public_scores: Mapping[str, Mapping[str, Any]],
    hidden_score: Mapping[str, Any] | None,
    next_ordinal: int,
    resume_safe: bool,
    inflight_request_id: str | None,
    lease: Mapping[str, Any],
    sidecar_instances: int,
    cleanup: Mapping[str, Any] | None = None,
    postflight: Mapping[str, Any] | None = None,
    failure: Mapping[str, Any] | None = None,
    result_sha256: str | None = None,
) -> dict[str, Any]:
    artifact_index = {
        request_id: {
            "artifact_kind": artifact["artifact_kind"],
            "artifact_sha256": artifact["artifact_sha256"],
        }
        for request_id, artifact in artifacts.items()
    }
    value = {
        "schema_version": STATE_SCHEMA_VERSION,
        "bench_id": protocol.BENCH_ID,
        "run_id": run_id,
        "task_id": protocol.FROZEN_TASK_ID,
        "plan_sha256": plan.plan_sha256,
        "status": status,
        "next_request_ordinal": next_ordinal,
        "completed_request_count": len(observations),
        "resume_safe": resume_safe,
        "inflight_request_id": inflight_request_id,
        "observations": [_observation_dict(item) for item in observations],
        "request_records": list(request_records),
        "resource_observations": list(resource_observations),
        "artifact_index": artifact_index,
        "public_scores": dict(public_scores),
        "post_extraction_hidden_score": dict(hidden_score) if hidden_score else None,
        "lease_accounting": dict(lease),
        "sidecar_instance_count": sidecar_instances,
        "cleanup": dict(cleanup) if cleanup else None,
        "postflight_custody": dict(postflight) if postflight else None,
        "failure": dict(failure) if failure else None,
        "result_sha256": result_sha256,
        "claims": dict(CLAIMS_LOCKED),
        "claiming": False,
        "automatic_promotion": False,
        "updated_at": _utc_now(),
    }
    _validate_persistable(value)
    return value


def _validate_terminal_result(
    protocol: Any,
    *,
    run_id: str,
    plan: Any,
    checkpoint: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    checkpoint_core = dict(checkpoint)
    checkpoint_core["result_sha256"] = None
    if result.get("terminal_checkpoint_sha256") != _json_sha256(checkpoint_core):
        raise CatalyticInferenceRuntimeError(
            "terminal checkpoint digest mismatch"
        )
    expected_digest = checkpoint.get("result_sha256")
    if not isinstance(expected_digest, str) or expected_digest != _json_sha256(result):
        raise CatalyticInferenceRuntimeError("terminal result digest mismatch")
    if (
        result.get("run_id") != run_id
        or result.get("plan_sha256") != plan.plan_sha256
        or result.get("task_id") != protocol.FROZEN_TASK_ID
        or result.get("status") != checkpoint.get("status")
        or result.get("claims") != CLAIMS_LOCKED
        or result.get("claiming") is not False
        or result.get("automatic_promotion") is not False
    ):
        raise CatalyticInferenceRuntimeError("terminal result identity or claim boundary mismatch")
    if result.get("status") == "complete" and (
        result.get("completed_request_count") != 13
        or result.get("mechanism_classification")
        not in {
            protocol.MECHANISM_VISIBLE,
            getattr(protocol, "MECHANISM_WEAK", "MECHANISM_WEAK"),
            getattr(protocol, "MECHANISM_COLLAPSED", "MECHANISM_COLLAPSED"),
        }
    ):
        raise CatalyticInferenceRuntimeError("completed terminal result is not an exact bench closure")


def _bind_terminal_result(
    result: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    checkpoint_core = json.loads(_canonical_json_bytes(checkpoint))
    checkpoint_core["result_sha256"] = None
    bound_result = json.loads(_canonical_json_bytes(result))
    bound_result["terminal_checkpoint_sha256"] = _json_sha256(checkpoint_core)
    bound_checkpoint = dict(checkpoint_core)
    bound_checkpoint["result_sha256"] = _json_sha256(bound_result)
    return bound_result, bound_checkpoint


def _build_closure(
    *,
    run_id: str,
    paths: Mapping[str, Path],
    terminal_custody: Mapping[str, Any],
) -> dict[str, Any]:
    custody = json.loads(_canonical_json_bytes(terminal_custody))
    if type(custody.get("passed")) is not bool:
        raise CatalyticInferenceRuntimeError("terminal custody has no boolean result")
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "run_id": run_id,
        "manifest_sha256": _json_sha256(_read_json(paths["manifest.json"])),
        "result_sha256": _json_sha256(_read_json(paths["result.json"])),
        "checkpoint_sha256": _json_sha256(_read_json(paths["checkpoint.json"])),
        "terminal_custody": custody,
        "run_lock_absent": not paths["run.lock"].exists(),
    }


def _validate_closure(
    *,
    run_id: str,
    paths: Mapping[str, Path],
) -> dict[str, Any]:
    closure = _read_json(paths["closure.json"])
    result = _read_json(paths["result.json"])
    if set(closure) != {
        "schema_version",
        "run_id",
        "manifest_sha256",
        "result_sha256",
        "checkpoint_sha256",
        "terminal_custody",
        "run_lock_absent",
    }:
        raise CatalyticInferenceRuntimeError("terminal closure field set mismatch")
    if (
        closure.get("schema_version") != STATE_SCHEMA_VERSION
        or closure.get("run_id") != run_id
        or closure.get("manifest_sha256")
        != _json_sha256(_read_json(paths["manifest.json"]))
        or closure.get("result_sha256")
        != _json_sha256(result)
        or closure.get("checkpoint_sha256")
        != _json_sha256(_read_json(paths["checkpoint.json"]))
        or closure.get("run_lock_absent") is not True
        or not isinstance(closure.get("terminal_custody"), Mapping)
        or type(closure["terminal_custody"].get("passed")) is not bool
        or (
            result.get("status") == "complete"
            and closure["terminal_custody"].get("passed") is not True
        )
    ):
        raise CatalyticInferenceRuntimeError("terminal closure identity mismatch")
    return closure


def _load_prefix(protocol: Any, checkpoint: Mapping[str, Any], plan: Any) -> tuple[list[Any], list[dict[str, Any]]]:
    raw = checkpoint.get("observations")
    records = checkpoint.get("request_records")
    if not isinstance(raw, list) or not isinstance(records, list) or len(raw) != len(records):
        raise CatalyticInferenceRuntimeError("checkpoint request prefix is malformed")
    observations = []
    canonical_validator = getattr(protocol, "validate_structured_response", None)
    for index, item in enumerate(raw):
        observation = _restore_observation(protocol, item)
        request = plan.requests[index]
        artifact = getattr(observation, "artifact", None)
        if isinstance(artifact, Mapping) and callable(canonical_validator):
            canonical_artifact = canonical_validator(
                request,
                artifact,
                parent_observations=tuple(observations),
            )
            if canonical_artifact != artifact:
                raise CatalyticInferenceRuntimeError(
                    "checkpoint artifact is not the canonical protocol projection"
                )
        observations.append(observation)
    expected_ids = [item.request_id for item in plan.requests[: len(observations)]]
    if [item.request_id for item in observations] != expected_ids:
        raise CatalyticInferenceRuntimeError("checkpoint is not an exact request prefix")
    if [record.get("request_id") for record in records] != expected_ids:
        raise CatalyticInferenceRuntimeError(
            "checkpoint request records are not an exact request prefix"
        )
    if checkpoint.get("next_request_ordinal") != len(observations) + 1:
        raise CatalyticInferenceRuntimeError("checkpoint boundary ordinal is inconsistent")
    return observations, [dict(item) for item in records]


def _default_adapter(repository_root: Path) -> RuntimeAdapter:
    return _HoloStateAdapter(repository_root)


class _HoloStateAdapter:
    """Thin default adapter around existing HoloState safety helpers."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.h = importlib.import_module("holostate_live")
        self.custody = importlib.import_module("catalytic_runtime_custody")
        self.swarm = importlib.import_module("catalytic_swarm")
        self.harness = importlib.import_module("baseline_harness")
        self._host_private_baseline_bytes: int | None = None

    def preflight(self, *, args: Any, repository_root: Path, run_root: Path, allowed_paths: Sequence[Path]) -> Mapping[str, Any]:
        if repository_root.resolve() != self.repository_root:
            raise CatalyticInferenceRuntimeError("default adapter repository root changed")
        try:
            authorized = run_root.relative_to(repository_root).as_posix()
            allowed = [path.relative_to(repository_root).as_posix() for path in allowed_paths]
        except ValueError as exc:
            raise CatalyticInferenceRuntimeError("run state must remain below the repository") from exc
        custody = self.custody.capture_preclaim_custody(
            repository_root,
            authorized_root=authorized,
            allowed_paths=allowed,
        )
        evaluator, live_contract, _worker, predecessor, lock = self.h.load_locked_catalytic_swarm_0_v2()
        binary_arg = _arg(args, "binary")
        model_arg = _arg(args, "model")
        if not isinstance(binary_arg, str) or not Path(binary_arg).is_absolute():
            raise CatalyticInferenceRuntimeError("--binary must be an exact absolute path")
        if not isinstance(model_arg, str) or not Path(model_arg).is_absolute():
            raise CatalyticInferenceRuntimeError("--model must be an exact absolute path")
        binary = Path(binary_arg).resolve()
        model = Path(model_arg).resolve()
        binary_identity = self.h.verify_binary_identity(binary)
        model_identity = self.h.verify_model(model, evaluator)
        branch = self.h.git_read(repository_root, "branch", "--show-current")
        head = self.h.git_read(repository_root, "rev-parse", "HEAD")
        local_main = self.h.git_read(repository_root, "rev-parse", "main")
        origin_main = self.h.git_read(repository_root, "rev-parse", "origin/main")
        remote_tokens = self.h.git_read(
            repository_root, "ls-remote", "origin", "refs/heads/main"
        ).split()
        remote_main = remote_tokens[0] if remote_tokens else ""
        if branch != "main" or not (head == local_main == origin_main == remote_main):
            raise CatalyticInferenceRuntimeError(
                "bench requires exact checked-out HEAD = main = origin/main = remote main"
            )
        stable_pids = self.h.require_stable()
        if len(stable_pids) != 1 or self.h.listener_pids(self.h.PORT):
            raise CatalyticInferenceRuntimeError(
                "bench requires one stable listener and a free sidecar port"
            )
        props = self.h.request_json("GET", "/props", timeout=10, port=self.h.STABLE_PORT)
        template_sha = self.h.sha256_bytes(
            str(props.get("chat_template", "")).encode("utf-8")
        )
        if template_sha != live_contract["chat_template_identity"]["sha256"]:
            raise CatalyticInferenceRuntimeError("stable chat-template identity changed")
        candidate_root = repository_root.parent / f"{repository_root.name}-candidate"
        if not candidate_root.is_dir():
            raise CatalyticInferenceRuntimeError("archived candidate worktree is missing")
        candidate_head = self.h.git_read(candidate_root, "rev-parse", "HEAD")
        candidate_status = self.h.git_read(
            candidate_root, "status", "--porcelain=v2", "--branch", "--untracked-files=all"
        )
        expected_candidate = predecessor["stable_isolation"]["archived_trace_candidate_head"]
        if candidate_head != expected_candidate or not _porcelain_v2_status_is_clean(
            candidate_status
        ):
            raise CatalyticInferenceRuntimeError("archived candidate custody changed")
        stable_status = self.h.git_read(
            repository_root, "status", "--porcelain=v2", "--branch", "--untracked-files=all"
        )
        historical = [
            {
                "root": item.root,
                "exists": item.exists,
                "sha256": item.sha256,
                "entry_count": len(item.entries),
            }
            for item in custody.historical_namespaces
        ]
        metadata = {
            "binary_identity": binary_identity,
            "model_identity": model_identity,
            "stable": {
                "branch": branch,
                "head": head,
                "status_sha256": _sha256(stable_status.encode("utf-8")),
                "listener_pids": sorted(stable_pids),
                "chat_template_sha256": template_sha,
            },
            "candidate": {
                "head": candidate_head,
                "status_sha256": _sha256(candidate_status.encode("utf-8")),
            },
            "historical_cs1": historical,
            "historical_cs1_sha256": _json_sha256(historical),
            "evaluator_lock_sha256": _json_sha256(lock),
        }
        return {
            "metadata": metadata,
            "runtime": {
                "custody": custody,
                "evaluator": evaluator,
                "live_contract": live_contract,
                "predecessor": predecessor,
                "binary": binary,
                "model": model,
                "stable_pids": set(stable_pids),
                "stable_status": stable_status,
                "candidate_root": candidate_root,
                "candidate_head": candidate_head,
                "candidate_status": candidate_status,
                "temp_root": None,
            },
        }

    def create_lease_pool(self, physical_slots: int) -> Any:
        return self.swarm.PhysicalLeasePool(physical_slots)

    def launch_sidecar(self, *, preflight: Mapping[str, Any], run_id: str) -> tuple[Any, Mapping[str, Any]]:
        runtime = preflight["runtime"]
        predecessor = runtime["predecessor"]
        readiness_control = predecessor["readiness_control"]
        temp_root = Path(tempfile.mkdtemp(prefix=f"neo3000-cib0-{run_id}-"))
        runtime["temp_root"] = temp_root
        deadline = time.monotonic() + float(readiness_control["readiness_deadline_seconds"])
        sidecar = self.h.LiveSidecar(
            runtime["binary"],
            runtime["model"],
            runtime["evaluator"],
            runtime["live_contract"],
            detached=False,
            stable_pids=runtime["stable_pids"],
            readiness_control=readiness_control,
            prelaunch_evidence={"stable_pids": sorted(runtime["stable_pids"])},
            readiness_deadline_at=deadline,
            preverified_binary_identity=preflight["metadata"]["binary_identity"],
            preverified_model_identity=preflight["metadata"]["model_identity"],
            state_root=temp_root,
            wddm_policy=self.h.catalytic_swarm_1_wddm_policy(predecessor),
        )
        readiness = sidecar.launch()
        readiness_private = _valid_resource_bytes(
            readiness.get("process_memory", {}).get("private_bytes")
            if isinstance(readiness.get("process_memory"), Mapping)
            else None
        )
        self._host_private_baseline_bytes = readiness_private
        return sidecar, {
            "sidecar_pid": int(readiness["pid"]),
            "readiness_seconds": float(readiness["readiness_seconds"]),
            "private_bytes": readiness_private,
            "stable_pids": list(readiness["stable_pids"]),
            "chat_template_sha256": str(readiness["chat_template_sha256"]),
        }

    def prompt_geometry(self, *, sidecar: Any, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        messages = payload["messages"]
        rendered = self.h.render_messages(messages, payload.get("chat_template_kwargs"))
        token_ids = self.h.tokenize(rendered)
        terminal = self.h.locate_public_root_terminal_token_index(
            rendered, token_ids, messages[0]["content"]
        )
        return {
            "rendered_prompt": rendered,
            "token_ids": token_ids,
            "public_root_terminal_token_index": terminal,
        }

    def execute_request(self, *, sidecar: Any, payload: Mapping[str, Any], request: Any) -> Any:
        completed = False

        def call() -> Any:
            nonlocal completed
            value = self.harness.stream_completion(
                f"http://127.0.0.1:{self.h.PORT}/v1/chat/completions",
                dict(payload),
                repeat=1,
                timeout=900,
                event_recorder=None,
                request_label=None,
            )
            completed = True
            return value

        return sidecar.guarded(
            f"cib0:{request.request_id}",
            call,
            timeout=1_000,
            request_completed=lambda: completed,
        )

    def boundary_custody(self, *, preflight: Mapping[str, Any], sidecar: Any, boundary: str) -> Mapping[str, Any]:
        runtime = preflight["runtime"]
        stable = self.h.git_read(
            self.repository_root, "status", "--porcelain=v2", "--branch", "--untracked-files=all"
        )
        candidate = self.h.git_read(
            runtime["candidate_root"], "status", "--porcelain=v2", "--branch", "--untracked-files=all"
        )
        if stable != runtime["stable_status"] or candidate != runtime["candidate_status"]:
            raise CatalyticInferenceRuntimeError(f"{boundary}: stable/candidate custody changed")
        self.h.require_stable(runtime["stable_pids"])
        ownership = sidecar.exact_ownership(boundary)
        return {
            "passed": bool(ownership.get("passed")),
            "stable_status_sha256": _sha256(stable.encode("utf-8")),
            "candidate_status_sha256": _sha256(candidate.encode("utf-8")),
        }

    def resource_summary(self, *, sidecar: Any, boundary: str) -> Mapping[str, Any]:
        result: dict[str, Any] = {
            "boundary": boundary,
            "observed_at": _utc_now(),
        }
        first_error: BaseException | None = None
        host: int | None = None
        try:
            info = self.h.process_info(sidecar.process.pid) if sidecar.process else None
            host = _valid_resource_bytes(
                info.get("private_bytes") if isinstance(info, Mapping) else None
            )
        except Exception as exc:
            first_error = exc
        if host is not None:
            result["host_private_bytes"] = host
            if self._host_private_baseline_bytes is not None:
                result["host_private_ceiling_exceeded"] = (
                    host - self._host_private_baseline_bytes
                    > HOST_PRIVATE_GROWTH_CEILING_BYTES
                )

        wddm: int | None = None
        try:
            telemetry = sidecar.telemetry()
            if not isinstance(telemetry, Mapping):
                raise TypeError("WDDM telemetry returned a non-object")
            wddm = _valid_resource_bytes(telemetry.get("peak_bytes"))
            failure_reason = telemetry.get("failure_reason")
            if failure_reason is not None and first_error is None:
                first_error = RuntimeError(str(failure_reason))
        except Exception as exc:
            if first_error is None:
                first_error = exc
        if wddm is not None:
            result["wddm_peak_bytes"] = wddm
            result["wddm_ceiling_exceeded"] = wddm > WDDM_PEAK_CEILING_BYTES

        if first_error is not None:
            result["observation_state"] = "observation-error"
            result.update(_bounded_resource_exception(first_error))
        elif host is not None and wddm is not None:
            result["observation_state"] = "measured"
        else:
            result["observation_state"] = "unavailable"
        return result

    def cleanup(self, *, sidecar: Any | None, preflight: Mapping[str, Any]) -> Mapping[str, Any]:
        runtime = preflight["runtime"]
        cleanup = self.h.safe_sidecar_cleanup(sidecar)
        gate = self.h.cleanup_integrity(cleanup, runtime["stable_pids"])
        temp_root = runtime.get("temp_root")
        if isinstance(temp_root, Path):
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_removed = not isinstance(temp_root, Path) or not temp_root.exists()
        return {
            "passed": bool(gate.get("passed")) and temp_removed,
            "process_stopped": cleanup.get("process_stopped", cleanup.get("not_launched") is True),
            "port_free": cleanup.get("port_free") is True,
            "runtime_removed": cleanup.get("runtime_removed", cleanup.get("not_launched") is True),
            "stable_preserved": cleanup.get("stable_after", {}).get("listener_pids") == sorted(runtime["stable_pids"]),
            "temporary_state_removed": temp_removed,
        }

    def postflight(self, *, preflight: Mapping[str, Any]) -> Mapping[str, Any]:
        runtime = preflight["runtime"]
        report = self.custody.validate_postclaim_custody(runtime["custody"])
        self.h.verify_binary_identity(runtime["binary"])
        self.h.verify_model(runtime["model"], runtime["evaluator"])
        self.h.require_stable(runtime["stable_pids"])
        if self.h.listener_pids(self.h.PORT):
            raise CatalyticInferenceRuntimeError("sidecar port remained occupied after cleanup")
        candidate_head = self.h.git_read(runtime["candidate_root"], "rev-parse", "HEAD")
        candidate_status = self.h.git_read(
            runtime["candidate_root"],
            "status",
            "--porcelain=v2",
            "--branch",
            "--untracked-files=all",
        )
        if (
            candidate_head != runtime["candidate_head"]
            or candidate_status != runtime["candidate_status"]
            or not _porcelain_v2_status_is_clean(candidate_status)
        ):
            raise CatalyticInferenceRuntimeError("candidate custody changed")
        return {
            "passed": True,
            "changed_evidence_path_count": len(report.changed_evidence_paths),
            "historical_namespace_count": len(report.historical_namespace_hashes),
            "stable_listener_pids": sorted(runtime["stable_pids"]),
            "candidate_head": candidate_head,
            "candidate_status_sha256": _sha256(
                candidate_status.encode("utf-8")
            ),
        }

    def supports_request_boundary_resume(self, *, checkpoint: Mapping[str, Any]) -> Mapping[str, Any]:
        # The proven root carrier is process-local.  A cleaned sidecar cannot
        # safely inherit a partial epoch, so the default live adapter fails
        # closed; test adapters may prove continuity explicitly.
        return {"passed": checkpoint.get("completed_request_count") == 0, "mode": "process-local"}


def run_catalytic_inference_bench_0(
    args: Any,
    *,
    adapter: RuntimeAdapter | None = None,
    repository_root: str | os.PathLike[str] | None = None,
    state_root: str | os.PathLike[str] | None = None,
    scorer: Callable[..., tuple[int, int]] | None = None,
) -> dict[str, Any]:
    """Execute one complete non-claiming epoch or safely resume an exact prefix."""
    protocol = _protocol_module()
    run_id = validate_run_id(_arg(args, "run_id"))
    repository = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[1]
    )
    state_base = (
        Path(state_root).resolve()
        if state_root is not None
        else repository / "state" / "catalytic_inference_bench_0"
    )
    run_root = state_base / run_id
    paths = {name: run_root / name for name in STATE_FILENAMES}
    _require_safe_state_ancestry(repository, run_root)
    plan = protocol.build_catalytic_inference_bench_0_plan()
    protocol.validate_catalytic_inference_bench_0_plan(plan)
    if plan.task_id != "cs1-task-06" or len(plan.requests) != 13 or plan.physical_slot_count != 1:
        raise CatalyticInferenceRuntimeError("corrected protocol geometry is not cs1-task-06 / 13 / one-slot")
    live = adapter if adapter is not None else _default_adapter(repository)

    # This call is deliberately before mkdir/write: unexpected repo state can
    # never be hidden by the newly ignored run namespace.
    preflight = live.preflight(
        args=args,
        repository_root=repository,
        run_root=run_root,
        allowed_paths=tuple(paths.values()),
    )
    preflight_metadata = _public_preflight(preflight)
    if run_root.exists() and (not run_root.is_dir() or run_root.is_symlink()):
        raise CatalyticInferenceRuntimeError("run root must be a real directory")
    run_root.mkdir(parents=True, exist_ok=True)
    _require_safe_state_ancestry(repository, run_root)
    for path in paths.values():
        if not os.path.lexists(path):
            continue
        if _path_is_link_or_reparse(path) or not path.is_file():
            raise CatalyticInferenceRuntimeError(
                f"runtime state file is not a regular file: {path.name}"
            )
    unexpected = sorted(
        child.name for child in run_root.iterdir() if child.name not in STATE_FILENAMES
    )
    if unexpected:
        raise CatalyticInferenceRuntimeError(
            "run root contains unexpected state: " + ", ".join(unexpected)
        )

    with _RunLock(paths["run.lock"]) as run_lock:
        manifest = {
            "schema_version": STATE_SCHEMA_VERSION,
            "bench_id": protocol.BENCH_ID,
            "run_id": run_id,
            "task_id": protocol.FROZEN_TASK_ID,
            "plan_sha256": plan.plan_sha256,
            "task_suite_sha256": plan.task_suite_sha256,
            "public_system_root_sha256": plan.public_system_root_sha256,
            "request_count": len(plan.requests),
            "physical_slot_count": 1,
            "preflight": preflight_metadata,
            "claims": dict(CLAIMS_LOCKED),
            "claiming": False,
            "automatic_promotion": False,
        }
        if paths["manifest.json"].exists():
            if _read_json(paths["manifest.json"]) != manifest:
                raise CatalyticInferenceRuntimeError(
                    "run ID is bound to different protocol/runtime custody"
                )
        else:
            if paths["checkpoint.json"].exists() or paths["result.json"].exists():
                raise CatalyticInferenceRuntimeError("run state exists without its manifest")
            _atomic_write_json(paths["manifest.json"], manifest)

        observations: list[Any] = []
        request_records: list[dict[str, Any]] = []
        resource_observations: list[dict[str, Any]] = []
        artifacts: dict[str, dict[str, Any]] = {}
        public_scores: dict[str, dict[str, Any]] = {}
        hidden_score: dict[str, Any] | None = None
        start_ordinal = 1
        prior_lease_count = 0
        prior_max_concurrent = 0
        prior_sidecar_instances = 0
        if paths["checkpoint.json"].exists():
            prior = _read_json(paths["checkpoint.json"])
            if prior.get("run_id") != run_id or prior.get("plan_sha256") != plan.plan_sha256:
                raise CatalyticInferenceRuntimeError("checkpoint identity mismatch")
            if prior.get("status") in {"complete", "failed"}:
                if not paths["result.json"].exists():
                    raise CatalyticInferenceRuntimeError(
                        "terminal checkpoint is missing its bound result"
                    )
                terminal_result = _read_json(paths["result.json"])
                _validate_terminal_result(
                    protocol,
                    run_id=run_id,
                    plan=plan,
                    checkpoint=prior,
                    result=terminal_result,
                )
                if not paths["closure.json"].exists():
                    raise CatalyticInferenceRuntimeError(
                        "terminal state is missing its closure"
                    )
                _validate_closure(run_id=run_id, paths=paths)
            if prior.get("status") == "complete":
                run_lock.release()
                live.postflight(preflight=preflight)
                return terminal_result
            observations, request_records = _load_prefix(protocol, prior, plan)
            if prior.get("resume_safe") is not True or prior.get("inflight_request_id") is not None:
                raise CatalyticInferenceRuntimeError(
                    "run stopped with an uncertain in-flight request; use a new run ID"
                )
            reconstructed_resources: list[dict[str, Any]] = []
            for record in request_records:
                request_id = record.get("request_id")
                resources = record.get("resources")
                if (
                    not isinstance(request_id, str)
                    or not isinstance(resources, Mapping)
                    or set(resources) != {"before", "after"}
                ):
                    raise CatalyticInferenceRuntimeError(
                        "checkpoint request resource boundary is malformed"
                    )
                for label in ("before", "after"):
                    reconstructed_resources.append(
                        _validated_persisted_resource_observation(
                            resources[label], boundary=f"{label}:{request_id}"
                        )
                    )
            prior_resources = prior.get("resource_observations")
            if prior_resources != reconstructed_resources:
                raise CatalyticInferenceRuntimeError(
                    "checkpoint resource-observation prefix is inconsistent"
                )
            resource_observations = reconstructed_resources
            start_ordinal = len(observations) + 1
            resume_method = getattr(live, "supports_request_boundary_resume", None)
            resume = (
                resume_method(checkpoint=prior)
                if callable(resume_method)
                else {"passed": False, "mode": "unsupported"}
            )
            if not isinstance(resume, Mapping) or resume.get("passed") is not True:
                raise CatalyticInferenceRuntimeError(
                    "adapter cannot prove process-local cache continuity for this prefix"
                )
            # Artifacts are reconstructed from bounded request records, never
            # from raw output.  Records retain the normalized typed artifact.
            for record in request_records:
                artifact = record.get("normalized_artifact")
                if isinstance(artifact, Mapping):
                    artifacts[str(record["request_id"])] = dict(artifact)
                score = record.get("public_score")
                if isinstance(score, Mapping):
                    public_scores[str(record["request_id"])] = dict(score)
            stored_hidden = prior.get("post_extraction_hidden_score")
            if isinstance(stored_hidden, Mapping):
                hidden_score = dict(stored_hidden)
            prior_lease = prior.get("lease_accounting")
            if isinstance(prior_lease, Mapping):
                prior_lease_count = int(prior_lease.get("lease_count", 0))
                prior_max_concurrent = int(
                    prior_lease.get("maximum_concurrent_leases", 0)
                )
            prior_sidecar_instances = int(prior.get("sidecar_instance_count", 0))

        lease_pool = live.create_lease_pool(1)

        def current_lease() -> dict[str, Any]:
            current = _lease_accounting(lease_pool)
            current["lease_count"] += prior_lease_count
            current["maximum_concurrent_leases"] = max(
                current["maximum_concurrent_leases"], prior_max_concurrent
            )
            return current

        sidecar: Any | None = None
        sidecar_instances = prior_sidecar_instances
        readiness: Mapping[str, Any] | None = None
        cleanup: Mapping[str, Any] = {"passed": False}
        postflight: Mapping[str, Any] = {"passed": False}
        failure: dict[str, Any] | None = None
        interruption: BaseException | None = None
        safe_boundary = True
        inflight: str | None = None
        scorer_fn = scorer or _default_scorer()
        task = protocol.frozen_task()
        warm_tokens: list[int] | None = None
        warm_terminal: int | None = None
        host_baseline_bytes: int | None = None

        try:
            sidecar, readiness = live.launch_sidecar(preflight=preflight, run_id=run_id)
            sidecar_instances += 1
            host_baseline_bytes = _valid_resource_bytes(
                readiness.get("private_bytes")
                if isinstance(readiness, Mapping)
                else None
            )
            warm_payload, warm_parents = _build_payload(
                protocol, plan.requests[0], observations, artifacts
            )
            warm_geometry = live.prompt_geometry(sidecar=sidecar, payload=warm_payload)
            warm_tokens = list(warm_geometry["token_ids"])
            warm_terminal = int(warm_geometry["public_root_terminal_token_index"])
            if not warm_tokens or warm_terminal <= 0:
                raise CatalyticInferenceRuntimeError("public-root terminal geometry is unavailable")

            for request in plan.requests[start_ordinal - 1 :]:
                payload, actual_parents = _build_payload(
                    protocol, request, observations, artifacts
                )
                geometry = (
                    warm_geometry
                    if request.request_id == protocol.WARM_ID
                    else live.prompt_geometry(sidecar=sidecar, payload=payload)
                )
                token_ids = list(geometry["token_ids"])
                terminal = int(geometry["public_root_terminal_token_index"])
                if terminal != warm_terminal:
                    raise CatalyticInferenceRuntimeError("public-root terminal index drifted")
                common_prefix = 0
                for left, right in zip(warm_tokens, token_ids):
                    if left != right:
                        break
                    common_prefix += 1
                before_custody = live.boundary_custody(
                    preflight=preflight,
                    sidecar=sidecar,
                    boundary=f"before:{request.request_id}",
                )
                before_resource = _observe_resource(
                    live,
                    sidecar=sidecar,
                    boundary=f"before:{request.request_id}",
                )
                resource_observations.append(before_resource)
                _require_measured_resource_ceiling(
                    request_id=request.request_id,
                    resource=before_resource,
                    host_baseline_bytes=host_baseline_bytes,
                )
                inflight = request.request_id
                safe_boundary = False
                _atomic_write_json(
                    paths["checkpoint.json"],
                    _checkpoint(
                        protocol=protocol,
                        run_id=run_id,
                        plan=plan,
                        status="running",
                        observations=observations,
                        request_records=request_records,
                        resource_observations=resource_observations,
                        artifacts=artifacts,
                        public_scores=public_scores,
                        hidden_score=hidden_score,
                        next_ordinal=request.ordinal,
                        resume_safe=False,
                        inflight_request_id=inflight,
                        lease=current_lease(),
                        sidecar_instances=sidecar_instances,
                    ),
                )
                with lease_pool.lease() as lease_id:
                    if lease_id != 0:
                        raise CatalyticInferenceRuntimeError("one-slot pool returned a nonzero lease")
                    execution = live.execute_request(
                        sidecar=sidecar, payload=payload, request=request
                    )
                if getattr(lease_pool, "active_count", 0) != 0:
                    raise CatalyticInferenceRuntimeError("physical lease was not returned")
                transport = _normalized_transport(
                    execution,
                    rendered_tokens=len(token_ids),
                    max_tokens=int(request.max_tokens),
                )
                parse_kwargs: dict[str, Any] = {}
                if "parent_observations" in inspect.signature(
                    protocol.parse_structured_response
                ).parameters:
                    parse_kwargs["parent_observations"] = tuple(observations)
                structured = protocol.parse_structured_response(
                    request, transport["structured_content"], **parse_kwargs
                )
                cache = _cache_adjudication(
                    terminal=terminal,
                    common_prefix=common_prefix,
                    prompt_tokens=transport["metadata"]["prompt_tokens"],
                    cached_tokens=transport["metadata"]["cached_prompt_tokens"],
                    completion_tokens=transport["metadata"]["completion_tokens"],
                    warm=request.request_id == protocol.WARM_ID,
                )
                if cache["required"] and not cache["admitted"]:
                    raise CatalyticInferenceRuntimeError(
                        f"{request.request_id}: exact public-root cache admission failed"
                    )
                ranked_candidate_ids = _ranked_candidate_ids(structured, None)
                candidate_id = (
                    ranked_candidate_ids[0]
                    if ranked_candidate_ids
                    else _candidate_id(protocol, structured, None)
                )
                ranked_public_scores = [
                    _score(scorer_fn, task, ranked_id, hidden=False)
                    for ranked_id in ranked_candidate_ids
                ]
                after_resource = _observe_resource(
                    live,
                    sidecar=sidecar,
                    boundary=f"after:{request.request_id}",
                )
                resource_observations.append(after_resource)
                after_custody = live.boundary_custody(
                    preflight=preflight,
                    sidecar=sidecar,
                    boundary=f"after:{request.request_id}",
                )
                _require_request_safety(
                    request_id=request.request_id,
                    before_custody=before_custody,
                    after_custody=after_custody,
                    before_resource=before_resource,
                    after_resource=after_resource,
                    host_baseline_bytes=host_baseline_bytes,
                )
                normalize_kwargs = {
                    "completed": True,
                    "safety_passed": True,
                    "root_reused": bool(cache["admitted"]),
                    "public_root_terminal_token_index": terminal,
                    "hidden_leak_detected": False,
                    "physical_slot": 0,
                    "public_system_root_sha256": request.system_root_sha256,
                    "prompt_tokens": transport["metadata"]["prompt_tokens"],
                    "cached_prompt_tokens": transport["metadata"]["cached_prompt_tokens"],
                    "fresh_prompt_tokens": transport["metadata"]["fresh_prompt_tokens"],
                    "completion_tokens": transport["metadata"]["completion_tokens"],
                    "finish_reason": "stop",
                }
                parameters = inspect.signature(protocol.normalize_observation).parameters
                if "parent_observations" in parameters:
                    normalize_kwargs["parent_observations"] = tuple(observations)
                normalize_kwargs = {
                    key: value for key, value in normalize_kwargs.items() if key in parameters
                }
                observation = protocol.normalize_observation(
                    request, structured, **normalize_kwargs
                )
                observations.append(observation)
                protocol_artifact = getattr(observation, "artifact", None)
                if protocol_artifact is None:
                    # Compatibility seam for injected/mock protocols.  The
                    # corrected protocol owns its typed artifact projection on
                    # NormalizedObservation; older test doubles expose only a
                    # validated structured response, which is reduced here to
                    # the same bounded, metadata-only parent carrier.
                    fallback_artifact = _extract_ranked_artifact(
                        protocol, request, structured
                    )
                    if fallback_artifact is not None:
                        protocol_artifact = fallback_artifact["ranked_structure"]
                artifact: dict[str, Any] | None = None
                if isinstance(protocol_artifact, Mapping) and request.request_id not in {
                    protocol.WARM_ID,
                    protocol.RESTORE_ID,
                }:
                    artifact = {
                        "producer_request_id": request.request_id,
                        "artifact_kind": request.phase,
                        "ranked_structure": json.loads(
                            _canonical_json_bytes(protocol_artifact)
                        ),
                        "public_scores": json.loads(
                            _canonical_json_bytes(ranked_public_scores)
                        ),
                        "artifact_sha256": str(
                            getattr(observation, "artifact_sha256", "")
                        ),
                    }
                    artifacts[request.request_id] = artifact
                public_score: dict[str, Any] | None = None
                if ranked_public_scores:
                    public_score = {
                        "ranked": ranked_public_scores,
                        "selected_candidate_id": candidate_id,
                    }
                    public_scores[request.request_id] = public_score
                elif candidate_id is not None:
                    selected_score = _score(
                        scorer_fn, task, candidate_id, hidden=False
                    )
                    public_score = {
                        "ranked": [selected_score],
                        "selected_candidate_id": candidate_id,
                    }
                    public_scores[request.request_id] = public_score
                record = {
                    "request_id": request.request_id,
                    "ordinal": request.ordinal,
                    "phase": request.phase,
                    "parent_artifact_ids": [
                        item.get("request_id", item.get("producer_request_id"))
                        for item in actual_parents
                    ],
                    "normalized_artifact": artifact,
                    "model_request_sha256": _json_sha256(payload),
                    "assignment_body_sha256": getattr(
                        observation, "assignment_body_sha256", None
                    ),
                    "consumed_artifact_sha256": list(
                        getattr(observation, "consumed_artifact_sha256", ())
                    ),
                    "observation_sha256": _json_sha256(_observation_dict(observation)),
                    "transport": transport["metadata"],
                    "cache_adjudication": cache,
                    "public_score": public_score,
                    "custody": {"before": dict(before_custody), "after": dict(after_custody)},
                    "resources": {"before": dict(before_resource), "after": dict(after_resource)},
                }
                request_records.append(record)
                if request.request_id == protocol.EXTRACT_ID:
                    if candidate_id is None:
                        raise CatalyticInferenceRuntimeError("extraction has no scoreable candidate")
                    direct_request_id = getattr(protocol, "DIRECT_ID", "direct")
                    direct_public = public_scores.get(direct_request_id)
                    direct_candidate_id = (
                        direct_public.get("selected_candidate_id")
                        if isinstance(direct_public, Mapping)
                        else None
                    )
                    if not isinstance(direct_candidate_id, str):
                        raise CatalyticInferenceRuntimeError(
                            "direct baseline has no scoreable candidate"
                        )
                    direct_hidden = _score(
                        scorer_fn, task, direct_candidate_id, hidden=True
                    )
                    catalytic_hidden = _score(
                        scorer_fn, task, candidate_id, hidden=True
                    )
                    hidden_score = {
                        "direct_baseline": direct_hidden,
                        "final_catalytic": catalytic_hidden,
                        "difference_passed": (
                            catalytic_hidden["passed"] - direct_hidden["passed"]
                        ),
                        "scored_after_extraction_ordinal": request.ordinal,
                        "no_later_selection_request": True,
                    }
                inflight = None
                safe_boundary = True
                _atomic_write_json(
                    paths["checkpoint.json"],
                    _checkpoint(
                        protocol=protocol,
                        run_id=run_id,
                        plan=plan,
                        status="running",
                        observations=observations,
                        request_records=request_records,
                        resource_observations=resource_observations,
                        artifacts=artifacts,
                        public_scores=public_scores,
                        hidden_score=hidden_score,
                        next_ordinal=request.ordinal + 1,
                        resume_safe=True,
                        inflight_request_id=None,
                        lease=current_lease(),
                        sidecar_instances=sidecar_instances,
                    ),
                )
                hook = getattr(live, "after_request_boundary", None)
                if callable(hook):
                    hook(request=request, checkpoint_path=paths["checkpoint.json"])
        except BaseException as exc:
            failure = _safe_exception(exc, boundary=inflight or "runtime")
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                interruption = exc
        finally:
            try:
                cleanup = live.cleanup(sidecar=sidecar, preflight=preflight)
            except BaseException as exc:
                cleanup = {"passed": False, "failure": _safe_exception(exc, boundary="cleanup")}
                failure = failure or cleanup["failure"]
            try:
                postflight = live.postflight(preflight=preflight)
            except BaseException as exc:
                postflight = {"passed": False, "failure": _safe_exception(exc, boundary="postflight")}
                failure = failure or postflight["failure"]

        lease = current_lease()
        lease_passed = (
            lease["active_leases"] == 0
            and lease["maximum_concurrent_leases"] <= 1
            and lease["lease_count"] == len(observations)
        )
        if (
            observations
            and getattr(observations[-1], "request_id", None) == protocol.RESTORE_ID
            and hasattr(protocol, "bind_runtime_restoration")
        ):
            restore_record = request_records[-1]
            restore_cache = restore_record.get("cache_adjudication", {})
            restore_custody = restore_record.get("custody", {})
            before_restore_custody = restore_custody.get("before", {})
            after_restore_custody = restore_custody.get("after", {})
            observations[-1] = protocol.bind_runtime_restoration(
                observations[-1],
                run_id=run_id,
                root_identity_passed=(
                    getattr(observations[-1], "public_system_root_sha256", None)
                    == plan.public_system_root_sha256
                ),
                cache_terminal_admitted=restore_cache.get("admitted") is True,
                active_leases=lease["active_leases"],
                cleanup_passed=cleanup.get("passed") is True,
                custody_passed=(
                    before_restore_custody.get("passed") is True
                    and after_restore_custody.get("passed") is True
                    and postflight.get("passed") is True
                ),
                sidecar_port_free=cleanup.get("port_free") is True,
                stable_preserved=cleanup.get("stable_preserved") is True,
            )
            restore_record["observation_sha256"] = _json_sha256(
                _observation_dict(observations[-1])
            )
            restore_record["restoration_receipt_sha256"] = getattr(
                observations[-1], "restoration_receipt_sha256", None
            )
        assessment = protocol.classify_catalytic_inference_bench_0(plan, observations)
        success = (
            failure is None
            and len(observations) == 13
            and getattr(assessment, "status") == "complete"
            and cleanup.get("passed") is True
            and postflight.get("passed") is True
            and lease_passed
        )
        summary = protocol.summarize_catalytic_inference_bench_0(
            plan, observations, assessment
        )
        status = "complete" if success else "failed"
        mechanism = (
            assessment.mechanism_classification
            if success
            else protocol.MECHANISM_INCONCLUSIVE
        )
        resource_summary = _aggregate_cost(
            request_records,
            resource_observations,
            readiness=readiness,
        )
        result = {
            **summary,
            "run_id": run_id,
            "status": status,
            "mechanism_classification": mechanism,
            "preflight": preflight_metadata,
            "readiness": dict(readiness) if readiness else None,
            "request_records": request_records,
            "resource_observations": resource_observations,
            "resource_summary": resource_summary,
            "resource_observability": resource_summary["resource_observability"],
            "post_extraction_hidden_score": hidden_score,
            "lease_accounting": lease,
            "lease_gate_passed": lease_passed,
            "sidecar_instance_count": sidecar_instances,
            "cleanup": dict(cleanup),
            "postflight_custody": dict(postflight),
            "failure": failure,
            "metadata_only": True,
            "sse_persistence": "in-memory-only",
            "raw_output_persisted": False,
            "claims": dict(CLAIMS_LOCKED),
            "claiming": False,
            "automatic_promotion": False,
        }
        provisional_checkpoint = _checkpoint(
            protocol=protocol,
            run_id=run_id,
            plan=plan,
            status=status,
            observations=observations,
            request_records=request_records,
            resource_observations=resource_observations,
            artifacts=artifacts,
            public_scores=public_scores,
            hidden_score=hidden_score,
            next_ordinal=len(observations) + 1,
            resume_safe=safe_boundary and not success,
            inflight_request_id=None if safe_boundary else inflight,
            lease=lease,
            sidecar_instances=sidecar_instances,
            cleanup=cleanup,
            postflight=postflight,
            failure=failure,
            result_sha256=None,
        )
        result, final_checkpoint = _bind_terminal_result(
            result, provisional_checkpoint
        )
        _atomic_write_json(paths["result.json"], result)
        _atomic_write_json(paths["checkpoint.json"], final_checkpoint)
        run_lock.release()
        terminal_custody: Mapping[str, Any] = {
            "passed": False,
            "stage": "not-observed",
        }
        try:
            terminal_custody = live.postflight(preflight=preflight)
            if terminal_custody.get("passed") is not True:
                raise CatalyticInferenceRuntimeError("terminal custody did not pass")
            final_custody = live.postflight(preflight=preflight)
            if final_custody.get("passed") is not True:
                raise CatalyticInferenceRuntimeError("final custody did not pass")
            closure = _build_closure(
                run_id=run_id,
                paths=paths,
                terminal_custody=final_custody,
            )
            _atomic_write_json(paths["closure.json"], closure)
        except BaseException as exc:
            final_failure = _safe_exception(exc, boundary="final-postflight")
            result["status"] = "failed"
            result["mechanism_classification"] = protocol.MECHANISM_INCONCLUSIVE
            result["failure"] = final_failure
            failed_checkpoint = _checkpoint(
                protocol=protocol,
                run_id=run_id,
                plan=plan,
                status="failed",
                observations=observations,
                request_records=request_records,
                resource_observations=resource_observations,
                artifacts=artifacts,
                public_scores=public_scores,
                hidden_score=hidden_score,
                next_ordinal=len(observations) + 1,
                resume_safe=False,
                inflight_request_id=None,
                lease=lease,
                sidecar_instances=sidecar_instances,
                cleanup=cleanup,
                postflight=postflight,
                failure=final_failure,
                result_sha256=None,
            )
            result, failed_checkpoint = _bind_terminal_result(
                result, failed_checkpoint
            )
            _atomic_write_json(paths["result.json"], result)
            _atomic_write_json(paths["checkpoint.json"], failed_checkpoint)
            failed_custody = {
                "passed": False,
                "last_observation": json.loads(
                    _canonical_json_bytes(terminal_custody)
                ),
                "failure": final_failure,
            }
            closure = _build_closure(
                run_id=run_id,
                paths=paths,
                terminal_custody=failed_custody,
            )
            _atomic_write_json(paths["closure.json"], closure)
            success = False
        if interruption is not None:
            raise interruption
        return result


__all__ = [
    "CatalyticInferenceRuntimeError",
    "CLAIMS_LOCKED",
    "RuntimeAdapter",
    "run_catalytic_inference_bench_0",
    "validate_run_id",
]
