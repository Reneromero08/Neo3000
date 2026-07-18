#!/usr/bin/env python3
"""Frozen model-contact surface for the four-request relational-operation probe.

The controller owns private geometry construction, authority admission,
adjudication, and terminal evidence.  This module owns the immutable request
hash gate, the one-generation-per-request law, raw SSE capture before parsing,
and deterministic capture replay.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import baseline_harness
import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_scientific as capture_support


class ScientificSurfaceError(ValueError):
    """The frozen relational-operation execution surface changed or is unsafe."""


DESIGN_ID = "balanced-opaque-transform-only-contrastive-relational-operation-probe-v1"
REQUEST_IDS = ("G0-AB", "G0-BA", "G1-AB", "G1-BA")
MAXIMUM_MODEL_GENERATIONS_PER_REQUEST = 1
MAXIMUM_TOTAL_MODEL_GENERATIONS = 4
CAPTURE_SCHEMA_VERSION = 1
CAPTURE_HMAC_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/capture-hmac-v1\0"
MAX_CAPTURE_BYTES = 256 * 1024
MAX_RAW_RESPONSE_BYTES = 128 * 1024
CAPTURE_EXECUTION_FIELDS = capture_support.CAPTURE_EXECUTION_FIELDS
RawResponseSpool = capture_support.RawResponseSpool

_CONTRACT_FIELDS = {
    "design_id",
    "request_ids",
    "execution_order",
    "request_sha256",
    "private_binding_commitments",
    "geometry_commitments",
    "prediction_commitments",
    "fixed_transform_seed",
    "model_sha256",
    "binary_sha256",
    "carrier_root_sha256",
    "response_schema_sha256",
    "physical_slots",
    "sidecar_epochs",
    "maximum_model_generations_per_request",
    "maximum_total_model_generations",
    "request_dispatch",
    "raw_response_recording",
}


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


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScientificSurfaceError(message)


def _regular_bytes(path: Path, label: str, maximum: int) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise ScientificSurfaceError(f"{label} is not a regular file")
        data = path.read_bytes()
    except OSError as exc:
        raise ScientificSurfaceError(f"{label} is unreadable") from exc
    _require(0 < len(data) <= maximum, f"{label} has an unsafe size")
    return data


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def capture_schema() -> dict[str, Any]:
    return {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "required_fields": [
            "schema_version",
            "design_id",
            "request_id",
            "model_request_sha256",
            "captured_before_parsing",
            "raw_response_capture",
            "execution",
            "capture_hmac_sha256",
        ],
        "execution_fields": list(CAPTURE_EXECUTION_FIELDS),
        "exclusive_create": True,
        "authentication": "HMAC-SHA-256 under the private probe experiment key",
        "replay_without_model_contact": True,
    }


def _callable_source_binding() -> dict[str, Any]:
    callables = (
        kernel.CatalyticKernel0Adapter.launch_sidecar,
        runtime_support._HoloStateAdapter.prompt_geometry,
        runtime_support._HoloStateAdapter.execute_request,
        runtime_support._HoloStateAdapter.boundary_custody,
        baseline_harness.stream_completion,
        kernel._terminal_identity,
    )
    entries = []
    for value in callables:
        source = inspect.getsource(value).encode("utf-8")
        entries.append(
            {
                "qualified_name": f"{value.__module__}.{value.__qualname__}",
                "sha256": sha256_bytes(source),
            }
        )
    body = {"callables": entries}
    return {**body, "sha256": json_sha256(body)}


def frozen_scientific_binding(
    repository: Path,
    *,
    contract: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind the exact four requests and their immutable contact implementation."""
    repository = repository.resolve(strict=False)
    _require(set(contract) == _CONTRACT_FIELDS, "scientific contract fields changed")
    _require(contract.get("design_id") == DESIGN_ID, "design identity changed")
    _require(tuple(contract.get("request_ids", ())) == REQUEST_IDS, "request identities changed")
    _require(tuple(contract.get("execution_order", ())) == REQUEST_IDS, "execution order changed")
    _require(set(payloads) == set(REQUEST_IDS), "scientific payload set changed")
    request_hashes = {request_id: json_sha256(payloads[request_id]) for request_id in REQUEST_IDS}
    _require(request_hashes == contract.get("request_sha256"), "request hash binding changed")
    _require(
        contract.get("maximum_model_generations_per_request")
        == MAXIMUM_MODEL_GENERATIONS_PER_REQUEST
        and contract.get("maximum_total_model_generations")
        == MAXIMUM_TOTAL_MODEL_GENERATIONS,
        "generation ceiling changed",
    )
    _require(
        contract.get("physical_slots") == 1 and contract.get("sidecar_epochs") == 1,
        "physical execution topology changed",
    )
    module_path = repository / "scripts" / Path(__file__).name
    module_data = _regular_bytes(module_path, "frozen scientific module", 1024 * 1024)
    body = {
        "surface_version": 1,
        "module": {
            "path": "scripts/catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe_scientific.py",
            "byte_size": len(module_data),
            "sha256": sha256_bytes(module_data),
        },
        "dispatch_dependencies": _callable_source_binding(),
        "contract": dict(contract),
        "request_sha256": request_hashes,
        "capture_schema_sha256": json_sha256(capture_schema()),
        "one_request_started_maximum_per_request": True,
        "one_generation_maximum_per_request": True,
        "four_generations_maximum_overall": True,
        "captured_requests_replay_without_model_contact": True,
    }
    return {**body, "sha256": json_sha256(body)}


def capture_hmac(experiment_key: bytes, body: Mapping[str, Any]) -> str:
    _require(isinstance(experiment_key, bytes) and len(experiment_key) == 32, "experiment key changed")
    return hmac.new(
        experiment_key,
        CAPTURE_HMAC_DOMAIN + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def _capture_value(execution: Any, name: str) -> Any:
    if isinstance(execution, Mapping):
        return execution.get(name)
    return getattr(execution, name, None)


def capture_execution(
    path: Path,
    *,
    experiment_key: bytes,
    request_id: str,
    model_request_sha256: str,
    execution: Any,
    raw_response_bytes: bytes,
) -> dict[str, Any]:
    _require(request_id in REQUEST_IDS, "capture request changed")
    _require(bool(raw_response_bytes), "raw response capture is empty")
    _require(len(raw_response_bytes) <= MAX_RAW_RESPONSE_BYTES, "raw response capture exceeds byte ceiling")
    body = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "design_id": DESIGN_ID,
        "request_id": request_id,
        "model_request_sha256": model_request_sha256,
        "captured_before_parsing": True,
        "raw_response_capture": {
            "encoding": "base64",
            "byte_size": len(raw_response_bytes),
            "sha256": sha256_bytes(raw_response_bytes),
            "bytes": base64.b64encode(raw_response_bytes).decode("ascii"),
        },
        "execution": {
            name: _capture_value(execution, name) for name in CAPTURE_EXECUTION_FIELDS
        },
    }
    document = {**body, "capture_hmac_sha256": capture_hmac(experiment_key, body)}
    data = canonical_json_bytes(document) + b"\n"
    _require(len(data) <= MAX_CAPTURE_BYTES, "response capture exceeds byte ceiling")
    _exclusive_write(path, data)
    return verify_capture(
        path,
        experiment_key=experiment_key,
        request_id=request_id,
        model_request_sha256=model_request_sha256,
    )


def verify_capture(
    path: Path,
    *,
    experiment_key: bytes,
    request_id: str,
    model_request_sha256: str,
) -> dict[str, Any]:
    data = _regular_bytes(path, "response capture", MAX_CAPTURE_BYTES)
    try:
        body = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScientificSurfaceError("response capture is malformed") from exc
    _require(isinstance(body, dict), "response capture is not an object")
    _require(set(body) == set(capture_schema()["required_fields"]), "response capture fields changed")
    _require(
        body.get("schema_version") == CAPTURE_SCHEMA_VERSION
        and body.get("design_id") == DESIGN_ID
        and body.get("request_id") == request_id
        and body.get("model_request_sha256") == model_request_sha256
        and body.get("captured_before_parsing") is True,
        "response capture identity changed",
    )
    authenticated = {key: value for key, value in body.items() if key != "capture_hmac_sha256"}
    _require(
        hmac.compare_digest(
            str(body.get("capture_hmac_sha256", "")),
            capture_hmac(experiment_key, authenticated),
        ),
        "response capture authentication changed",
    )
    execution = body.get("execution")
    _require(
        isinstance(execution, dict) and set(execution) == set(CAPTURE_EXECUTION_FIELDS),
        "response capture execution fields changed",
    )
    raw = body.get("raw_response_capture")
    _require(isinstance(raw, dict), "raw response capture is malformed")
    try:
        raw_bytes = base64.b64decode(str(raw.get("bytes", "")), validate=True)
    except (ValueError, TypeError) as exc:
        raise ScientificSurfaceError("raw response capture encoding changed") from exc
    _require(
        set(raw) == {"encoding", "byte_size", "sha256", "bytes"}
        and raw.get("encoding") == "base64"
        and raw.get("byte_size") == len(raw_bytes)
        and raw.get("sha256") == sha256_bytes(raw_bytes)
        and bool(raw_bytes),
        "raw response capture identity changed",
    )
    return {**body, "capture_sha256": sha256_bytes(data)}


def replay_capture(capture: Mapping[str, Any]) -> SimpleNamespace:
    execution = capture.get("execution")
    _require(isinstance(execution, dict), "capture cannot be replayed")
    return SimpleNamespace(**execution)


def execute_and_capture_request(
    *,
    experiment_key: bytes,
    frozen_binding_sha256: str,
    payload: Mapping[str, Any],
    request_id: str,
    expected_request_sha256: str,
    generation_ordinal: int,
    live: Any,
    sidecar: Any,
    pool: Any,
    full_preflight: Mapping[str, Any],
    capture_path: Path,
    partial_path: Path,
    append_event: Callable[..., Mapping[str, Any]],
) -> dict[str, Any]:
    """Issue one request and authenticate its raw response before parsing."""
    _require(len(frozen_binding_sha256) == 64, "frozen scientific binding is absent")
    _require(request_id in REQUEST_IDS, "dispatch request changed")
    _require(1 <= generation_ordinal <= MAXIMUM_TOTAL_MODEL_GENERATIONS, "generation ordinal changed")
    request_sha = json_sha256(payload)
    _require(request_sha == expected_request_sha256, "request changed before model contact")
    geometry = live.prompt_geometry(sidecar=sidecar, payload=payload)
    token_ids = geometry.get("token_ids")
    terminal = geometry.get("public_root_terminal_token_index")
    _require(
        isinstance(token_ids, list)
        and isinstance(terminal, int)
        and 0 <= terminal < len(token_ids),
        "request prompt geometry is invalid",
    )
    before = dict(
        live.boundary_custody(
            preflight=full_preflight,
            sidecar=sidecar,
            boundary=f"before:{request_id}",
        )
    )
    _require(before.get("passed") is True, "pre-request custody failed")
    append_event(
        "request-started",
        request_id=request_id,
        facts={
            "model_request_sha256": request_sha,
            "generation_ordinal": generation_ordinal,
            "maximum_generations_for_request": 1,
            "rendered_prompt_tokens": len(token_ids),
            "carrier_terminal_token_index": terminal,
            "carrier_terminal_identity_sha256": kernel._terminal_identity(token_ids, terminal),
            "frozen_scientific_binding_sha256": frozen_binding_sha256,
        },
    )
    request = kernel.KernelRequest(request_id=request_id, ordinal=generation_ordinal)
    with RawResponseSpool(partial_path) as spool:
        with pool.lease() as lease_id:
            _require(lease_id == kernel.PHYSICAL_SLOT, "physical slot changed")
            execution = live.execute_request(
                sidecar=sidecar,
                payload=payload,
                request=request,
                raw_line_recorder=spool.record,
            )
    raw_response_bytes = _regular_bytes(partial_path, "raw response spool", MAX_RAW_RESPONSE_BYTES)
    capture = capture_execution(
        capture_path,
        experiment_key=experiment_key,
        request_id=request_id,
        model_request_sha256=request_sha,
        execution=execution,
        raw_response_bytes=raw_response_bytes,
    )
    append_event(
        "response-captured",
        request_id=request_id,
        facts={
            "capture_sha256": capture["capture_sha256"],
            "model_request_sha256": request_sha,
            "captured_before_parsing": True,
        },
    )
    partial_path.unlink()
    after = dict(
        live.boundary_custody(
            preflight=full_preflight,
            sidecar=sidecar,
            boundary=f"after:{request_id}",
        )
    )
    _require(after.get("passed") is True, "post-request custody failed")
    append_event(
        "request-custody-observed",
        request_id=request_id,
        facts={"passed": True, "custody_sha256": json_sha256(after)},
    )
    return capture


def request_set_is_exact(values: Sequence[str]) -> bool:
    return tuple(values) == REQUEST_IDS
