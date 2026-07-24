#!/usr/bin/env python3
"""Preregister and execute neo-exp-0081 exactly once.

The experiment keeps the packed FP16 softmax operand B inside the existing
MMA FlashAttention kernel.  A process-fixed control writes every packed B
word to reserved global scratch and reloads the identical bits before the
V x softmax MMA.  Both routes use one binary, one model, the same scratch
reservation, launch geometry, prompts, sampler, and safety controls.

Builds, source audits, and unit tests are pre-science engineering checks.
Only ``--execute-once`` performs model-facing work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import baseline_harness
import catalytic_frontier_checkpoint_control as checkpoint_control
import catalytic_frontier_harness as harness
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_water_panel_qualifier as water


EXPERIMENT_ID = "neo-exp-0081"
ATTEMPT_ID = "frontier-attempt-0110"
ENVIRONMENT_NAME = "NEO3000_FATTN_B_MATERIALIZE"
ROUTE_ORDER = ("register_open", "global_materialized")
ROUTE_MODE = {"register_open": "0", "global_materialized": "1"}
WARMUPS_PER_ROUTE = 1
COUNTED_REPETITIONS = 9
MINIMUM_PROMPT_SPEEDUP = 1.02
MINIMUM_ALL_PAIRS_DOMINANCE = 0.70
ROOT_ID = water.ROOT_ID
BRANCH_NUMBER = 7
EXPECTED_ANSWER = "C"
EXPECTED_TASK_A_PROMPT_TOKENS = 543
EXPECTED_RETAINED_ROOT_TOKENS = 612
EXPECTED_BRANCH_PROMPT_TOKENS = 690
MODEL_SHA256 = harness.live_runtime.EXPECTED_MODEL_SHA256
BRANCH_PANEL_SHA256 = latency.PANEL_SHA256
MARKER_RE = re.compile(
    r"neo3000_fattn_b_probe: materialize=(?P<materialize>[01]) "
    r"DKQ=(?P<DKQ>\d+) DV=(?P<DV>\d+) "
    r"ncols1=(?P<ncols1>\d+) ncols2=(?P<ncols2>\d+) "
    r"nbatch_fa=(?P<nbatch_fa>\d+) "
    r"scratch_bytes_per_block=(?P<scratch_bytes_per_block>\d+) "
    r"reserve=(?P<reserve>[01])"
)
RUNTIME_FILES = (
    "ggml-base.dll",
    "ggml-cpu.dll",
    "ggml-cuda.dll",
    "ggml.dll",
    "llama-common.dll",
    "llama-server-impl.dll",
    "llama-server.exe",
    "llama.dll",
    "mtmd.dll",
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = ROOT / "build" / "candidate" / "bin" / "Release" / "llama-server.exe"
DEFAULT_MODEL = harness.DEFAULT_MODEL
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOG_DIR = ROOT / "lab" / f"{EXPERIMENT_ID}.logs.local"
DEFAULT_CONSUMED_MARKER = ROOT / "lab" / f"{EXPERIMENT_ID}.consumed.local.json"
ENGINEERING_INCIDENT_ROOT = ROOT / "tmp" / f"{EXPERIMENT_ID}-engineering-incidents"
CUDA_COMMON = ROOT / "ggml" / "src" / "ggml-cuda" / "fattn-common.cuh"
CUDA_MMA = ROOT / "ggml" / "src" / "ggml-cuda" / "fattn-mma-f16.cuh"
GRAPH_SOURCE = ROOT / "src" / "llama-graph.cpp"


class ExperimentError(RuntimeError):
    pass


class RouteExecutionError(ExperimentError):
    def __init__(self, message: str, evidence: Mapping[str, Any]):
        super().__init__(message)
        self.evidence = dict(evidence)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_exclusive_json(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ExperimentError(f"result path already exists: {path}") from error
    return {
        "path": str(path),
        "bytes": len(encoded),
        "sha256": sha256_bytes(encoded),
    }


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def run(
    command: list[str],
    *,
    timeout: int = 900,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def git(*arguments: str) -> str:
    return run(["git", *arguments], timeout=60).stdout.strip()


def require_clean_pushed_head(expected_commit: str) -> dict[str, str]:
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    upstream = git("rev-parse", "@{upstream}")
    status = git("status", "--porcelain")
    require(head == expected_commit, f"HEAD {head} != registered {expected_commit}")
    require(branch == "codex/catalytic-frontier", f"unexpected branch: {branch}")
    require(upstream == head, f"pushed head mismatch: {upstream} != {head}")
    require(not status, "worktree is not clean at execution boundary")
    return {"head": head, "branch": branch, "upstream": upstream}


def runtime_bundle(binary: Path) -> dict[str, Any]:
    directory = binary.resolve().parent
    require(binary.name == "llama-server.exe", "candidate entrypoint name changed")
    files: dict[str, dict[str, Any]] = {}
    for name in RUNTIME_FILES:
        path = directory / name
        require(path.is_file(), f"candidate runtime member missing: {name}")
        files[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return {
        "directory": str(directory),
        "files": files,
        "bundle_sha256": canonical_sha256(files),
    }


def static_audit(binary: Path) -> dict[str, Any]:
    common = CUDA_COMMON.read_text(encoding="utf-8")
    mma = CUDA_MMA.read_text(encoding="utf-8")
    graph = GRAPH_SOURCE.read_text(encoding="utf-8")
    store_position = mma.find(
        "thread_scratch[k*T_B_VKQ::ne + l] = packed.bits;"
    )
    first_barrier_position = mma.find("__syncthreads();", store_position)
    load_position = mma.find("packed.bits =", first_barrier_position)
    second_barrier_position = mma.find("__syncthreads();", load_position)
    gates = {
        "same_kernel_runtime_mode": (
            'getenv("NEO3000_FATTN_B_MATERIALIZE")' in mma
            and "materialize_fattn_b ? -Q->ne[0] : Q->ne[0]" in common
        ),
        "identical_scratch_reservation": (
            "reserve_fattn_b_probe" in common
            and "packed_b_scratch" in common
            and "true, materialize_fattn_b" in mma
        ),
        "block_linear_scratch_partition": all(
            token in mma
            for token in (
                "const size_t block_linear",
                "block_linear*fattn_b_words_per_block",
                "packed-B scratch geometry changed",
            )
        ),
        "two_phase_store_reload": (
            -1
            < store_position
            < first_barrier_position
            < load_position
            < second_barrier_position
        ),
        "volatile_global_address_space": (
            "volatile uint32_t * const thread_scratch" in mma
        ),
        "strict_environment_values": (
            "must be exactly 0 or 1" in mma
        ),
        "runtime_marker_complete": (
            "neo3000_fattn_b_probe:" in mma
            and "scratch_bytes_per_block=%zu reserve=1" in mma
            and "GGML_LOG_WARN(" in mma
        ),
        "flash_graph_path_present": (
            "ggml_flash_attn_ext" in graph
        ),
        "classical_nonflash_graph_present_but_not_control": all(
            token in graph
            for token in (
                "ggml_mul_mat(ctx0, k, q)",
                "ggml_soft_max_ext",
                "ggml_mul_mat(ctx0, v, kq)",
            )
        ),
    }
    require(all(gates.values()), f"static audit failed: {gates}")
    bundle = runtime_bundle(binary)
    return {
        "source_sha256": {
            str(CUDA_COMMON.relative_to(ROOT)): sha256_file(CUDA_COMMON),
            str(CUDA_MMA.relative_to(ROOT)): sha256_file(CUDA_MMA),
            str(GRAPH_SOURCE.relative_to(ROOT)): sha256_file(GRAPH_SOURCE),
        },
        "runtime_bundle": bundle,
        "gates": gates,
    }


class FattnBModeSidecar(checkpoint_control.ScopedCheckpointDiscoverySidecar):
    """Launch one child with a strict, process-local packed-B route."""

    def __init__(self, *args: Any, materialize_mode: str, **kwargs: Any):
        require(materialize_mode in {"0", "1"}, "invalid packed-B route mode")
        super().__init__(*args, **kwargs)
        self.materialize_mode = materialize_mode

    def launch(self) -> dict[str, Any]:
        require(
            ENVIRONMENT_NAME not in os.environ,
            f"{ENVIRONMENT_NAME} must be absent before scoped launch",
        )
        os.environ[ENVIRONMENT_NAME] = self.materialize_mode
        try:
            readiness = dict(super().launch())
        finally:
            os.environ.pop(ENVIRONMENT_NAME, None)
        require(
            ENVIRONMENT_NAME not in os.environ,
            f"{ENVIRONMENT_NAME} leaked after scoped launch",
        )
        configuration = dict(readiness.get("launch_configuration") or {})
        configuration.update(
            fattn_b_materialize=int(self.materialize_mode),
            fattn_b_scratch_reserved=True,
            environment_restored_after_launch=True,
        )
        readiness["launch_configuration"] = configuration
        return readiness


def build_sidecar(
    *,
    binary: Path,
    model: Path,
    evaluator: dict[str, Any],
    live_contract: dict[str, Any],
    stable_pids: set[int],
    state_root: Path,
    mode: str,
) -> FattnBModeSidecar:
    readiness_control = water.startup_readiness_control(evaluator)
    return FattnBModeSidecar(
        binary,
        model,
        evaluator,
        live_contract,
        detached=False,
        stable_pids=stable_pids,
        readiness_control=readiness_control,
        prelaunch_evidence={"stable_pids": sorted(stable_pids)},
        readiness_deadline_at=None,
        state_root=state_root,
        advisory_wddm=True,
        context_checkpoints=0,
        server_launch_args=(),
        moe_server_args=checkpoint_control.DEFAULT_MOE_SERVER_ARGS,
        readiness_deadline_seconds_after_identity=float(
            readiness_control["readiness_deadline_seconds"]
        ),
        stable_health_recovery_policy=water.startup_health_recovery_policy(),
        materialize_mode=mode,
    )


def create_consumed_marker(path: Path, expected_commit: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "expected_commit": expected_commit,
        "created_unix_ns": time.time_ns(),
        "meaning": "Task-A model-facing request is next; identity consumed",
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ExperimentError(f"consumption marker already exists: {path}") from error
    return {
        "path": str(path),
        "bytes": len(encoded),
        "sha256": sha256_bytes(encoded),
    }


def prepare_task_and_branch(
    codec: Any,
    root: Mapping[str, Any],
) -> dict[str, Any]:
    panel = water.panel_for(root)
    require(
        latency.water.base._panel_hash(panel) == BRANCH_PANEL_SHA256,
        "qualified water panel identity changed",
    )
    spec = panel[BRANCH_NUMBER - 1]
    require(spec["answer"] == EXPECTED_ANSWER, "water branch-7 answer changed")
    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    require(
        len(prompt_tokens) == EXPECTED_TASK_A_PROMPT_TOKENS,
        "Task-A prompt token count changed",
    )
    payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=latency.shared_tasks.derive_seed(ROOT_ID, "task-a"),
    )
    return {
        "spec": spec,
        "prompt_tokens": prompt_tokens,
        "payload": payload,
    }


def task_and_branch(
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    *,
    spec: Mapping[str, Any],
    prompt_tokens: list[int],
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Mapping[str, Any]]:
    task = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:task-a",
        payload,
    )
    parsed = harness.carrier.parse_task_a_output(task["content"])
    require(
        parsed["answer"] == harness.EXPECTED[ROOT_ID]["task_a"],
        "Task-A answer is incorrect",
    )
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task, payload),
        prompt_tokens,
        codec,
        props,
    )
    require(
        retained["retained_root_token_count"] == EXPECTED_RETAINED_ROOT_TOKENS,
        "retained Task-A root token count changed",
    )
    branch_tokens, _ = latency.branch_request(
        codec,
        retained,
        spec,
        cache_prompt=False,
    )
    require(
        len(branch_tokens) == EXPECTED_BRANCH_PROMPT_TOKENS,
        "water branch-7 prompt token count changed",
    )
    task_summary = {
        "prompt_tokens": task["prompt_tokens"],
        "completion_tokens": task["completion_tokens"],
        "content": task["content"],
        "input_token_sha256": canonical_sha256(prompt_tokens),
        "generated_token_ids": task["execution"]["generated_token_ids"],
        "generated_token_sha256": task["execution"]["generated_token_sha256"],
        "retained_root_tokens": retained["retained_root_tokens"],
        "retained_root_token_sha256": canonical_sha256(
            retained["retained_root_tokens"]
        ),
    }
    branch_identity = {
        "prompt_tokens": len(branch_tokens),
        "input_token_sha256": canonical_sha256(branch_tokens),
        "expected_answer": EXPECTED_ANSWER,
    }
    return task_summary, branch_identity, {"retained": retained, "spec": spec}


def run_tool_canary(sidecar: Any) -> dict[str, Any]:
    payload = baseline_harness.build_request_payload(
        "agents-a1-holostate",
        "",
        0.0,
        64,
        False,
        True,
        True,
    )
    measurement = sidecar.guarded(
        f"{EXPERIMENT_ID}:pi-tool-canary",
        lambda: baseline_harness.stream_completion(
            f"http://127.0.0.1:{harness.live_runtime.PORT}/v1/chat/completions",
            payload,
            repeat=1,
            timeout=1_000,
            request_label=f"{EXPERIMENT_ID}:pi-tool-canary",
        ),
        timeout=1_000,
    )
    validation = baseline_harness.validate_tool_call(measurement)
    require(validation.get("passed") is True, "Pi tool-call canary failed")
    require(len(measurement.tool_calls) == 1, "tool-call count changed")
    require(not measurement.content, "tool-call canary emitted plain content")
    return {
        "validation": validation,
        "tool_calls": measurement.tool_calls,
        "tool_calls_sha256": canonical_sha256(measurement.tool_calls),
        "generated_token_ids": measurement.generated_token_ids,
        "generated_token_sha256": measurement.generated_token_sha256,
        "measurement": asdict(measurement),
    }


def sidecar_log_source(sidecar: Any | None) -> Path | None:
    if sidecar is None:
        return None
    readiness_log = (getattr(sidecar, "readiness", {}) or {}).get("log_path")
    if readiness_log:
        return Path(str(readiness_log))
    return Path(sidecar.log_root) / f"{sidecar.session_id}.log"


def run_route(
    *,
    route: str,
    binary: Path,
    model: Path,
    evaluator: dict[str, Any],
    live_contract: dict[str, Any],
    stable_pids: set[int],
    root: Mapping[str, Any],
    log_path: Path,
    consumed_marker_path: Path,
    expected_commit: str,
    marker_state: dict[str, Any],
) -> dict[str, Any]:
    mode = ROUTE_MODE[route]
    state_root = Path(tempfile.mkdtemp(prefix=f"{EXPERIMENT_ID}-{route}-"))
    sidecar: FattnBModeSidecar | None = None
    cleanup: dict[str, Any] = {}
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    try:
        sidecar = build_sidecar(
            binary=binary,
            model=model,
            evaluator=evaluator,
            live_contract=live_contract,
            stable_pids=stable_pids,
            state_root=state_root,
            mode=mode,
        )
        readiness = sidecar.launch()
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        props = codec.props()
        prepared_task = prepare_task_and_branch(codec, root)
        spec = prepared_task["spec"]
        prompt_tokens = prepared_task["prompt_tokens"]
        payload = prepared_task["payload"]
        if marker_state.get("value") is None:
            marker_state["value"] = create_consumed_marker(
                consumed_marker_path,
                expected_commit,
            )
        task, branch_identity, prepared = task_and_branch(
            sidecar,
            codec,
            props,
            spec=spec,
            prompt_tokens=prompt_tokens,
            payload=payload,
        )
        boundary_records: list[dict[str, Any]] = []
        for boundary in ("pre-counted-batch",):
            started = time.monotonic()
            evidence = sidecar.exact_ownership(
                f"{EXPERIMENT_ID}:{route}:{boundary}"
            )
            boundary_records.append(
                {
                    "boundary": boundary,
                    "wall_seconds": time.monotonic() - started,
                    "evidence": evidence,
                }
            )
        warmups: list[dict[str, Any]] = []
        counted: list[dict[str, Any]] = []
        for index in range(1, WARMUPS_PER_ROUTE + 1):
            warmups.append(
                latency.run_timed_branch(
                    sidecar=sidecar,
                    codec=codec,
                    retained=prepared["retained"],
                    spec=prepared["spec"],
                    route="direct",
                    label=f"{EXPERIMENT_ID}:{route}:warmup-{index}",
                    batch_owned_request=True,
                )
            )
        for index in range(1, COUNTED_REPETITIONS + 1):
            counted.append(
                latency.run_timed_branch(
                    sidecar=sidecar,
                    codec=codec,
                    retained=prepared["retained"],
                    spec=prepared["spec"],
                    route="direct",
                    label=f"{EXPERIMENT_ID}:{route}:counted-{index}",
                    batch_owned_request=True,
                )
            )
        started = time.monotonic()
        evidence = sidecar.exact_ownership(
            f"{EXPERIMENT_ID}:{route}:post-counted-batch"
        )
        boundary_records.append(
            {
                "boundary": "post-counted-batch",
                "wall_seconds": time.monotonic() - started,
                "evidence": evidence,
            }
        )
        ownership_share = (
            sum(item["wall_seconds"] for item in boundary_records)
            / (len(warmups) + len(counted))
        )
        for record in [*warmups, *counted]:
            record["batch_ownership_amortized_seconds"] = ownership_share
            record["custody_adjusted_wall_seconds"] = (
                record["wall_seconds"] + ownership_share
            )
        tool = run_tool_canary(sidecar)
        baseline_private = readiness.get("process_memory", {}).get("private_bytes")
        resources = harness.process_resources(sidecar, baseline_private)
        result = {
            "route": route,
            "materialize_mode": int(mode),
            "readiness": readiness,
            "task_a": task,
            "branch_identity": branch_identity,
            "warmups": warmups,
            "counted": counted,
            "batch_ownership": boundary_records,
            "batch_ownership_amortized_seconds": ownership_share,
            "tool_canary": tool,
            "resources": resources,
        }
        require(
            resource_gate(resources),
            "route resource integrity failed",
        )
    except BaseException as caught:
        error = caught
    finally:
        cleanup = dict(harness.live_runtime.safe_sidecar_cleanup(sidecar))
        consumed = marker_state.get("value") is not None
        incident_nonce = time.time_ns()
        target_log_path = (
            log_path
            if consumed
            else ENGINEERING_INCIDENT_ROOT
            / f"{incident_nonce}-{route}-server.log"
        )
        log_record: dict[str, Any] = {"path": str(target_log_path)}
        try:
            source_log = sidecar_log_source(sidecar)
            require(
                source_log is not None and source_log.is_file(),
                "sidecar server log is unavailable",
            )
            target_log_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_log, target_log_path)
            log_record.update(
                bytes=target_log_path.stat().st_size,
                sha256=sha256_file(target_log_path),
            )
        except BaseException as log_error:
            log_record["error"] = f"{type(log_error).__name__}: {log_error}"
        cleanup["server_log"] = log_record
        cleanup["integrity"] = harness.live_runtime.cleanup_integrity(
            cleanup,
            stable_pids,
        )
        if not consumed:
            incident = {
                "experiment_id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "scientific_identity_consumed": False,
                "route": route,
                "materialize_mode": int(mode),
                "error_type": type(error).__name__ if error is not None else None,
                "error": str(error) if error is not None else None,
                "cleanup": cleanup,
            }
            incident_path = (
                ENGINEERING_INCIDENT_ROOT
                / f"{incident_nonce}-{route}.json"
            )
            try:
                cleanup["engineering_incident"] = write_exclusive_json(
                    incident_path,
                    incident,
                )
            except BaseException as incident_error:
                cleanup["engineering_incident_error"] = (
                    f"{type(incident_error).__name__}: {incident_error}"
                )
        shutil.rmtree(state_root, ignore_errors=True)
    if cleanup.get("integrity", {}).get("passed") is not True and error is None:
        error = ExperimentError(
            "route cleanup integrity failed: "
            + json.dumps(cleanup.get("integrity"), sort_keys=True)
        )
    if error is not None:
        evidence = {
            "route": route,
            "materialize_mode": int(mode),
            "error_type": type(error).__name__,
            "error": str(error),
            "cleanup": cleanup,
        }
        if result is not None:
            evidence["partial_result"] = result
        raise RouteExecutionError(
            f"{route} failed: {type(error).__name__}: {error}",
            evidence,
        ) from error
    require(result is not None, f"{route} result missing")
    result["cleanup"] = cleanup
    return result


def marker_geometry(log_path: Path, expected_mode: int) -> dict[str, Any]:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    markers = [
        {key: int(value) for key, value in match.groupdict().items()}
        for match in MARKER_RE.finditer(text)
    ]
    require(markers, f"no packed-B runtime marker in {log_path.name}")
    require(
        all(marker["materialize"] == expected_mode for marker in markers),
        f"packed-B route marker mismatch in {log_path.name}",
    )
    require(
        all(
            marker["DKQ"] == 256
            and marker["DV"] == 256
            and marker["reserve"] == 1
            and marker["scratch_bytes_per_block"]
            == marker["nbatch_fa"]
            * marker["ncols1"]
            * marker["ncols2"]
            * 2
            for marker in markers
        ),
        f"packed-B marker geometry invalid in {log_path.name}",
    )
    normalized = sorted(
        {
            (
                marker["DKQ"],
                marker["DV"],
                marker["ncols1"],
                marker["ncols2"],
                marker["nbatch_fa"],
                marker["scratch_bytes_per_block"],
                marker["reserve"],
            )
            for marker in markers
        }
    )
    materialized_bytes = sorted(
        {
            marker["scratch_bytes_per_block"]
            if marker["materialize"] == 1
            else 0
            for marker in markers
        }
    )
    return {
        "markers": markers,
        "normalized_geometry": normalized,
        "derived_materialized_store_bytes_per_b_iteration": materialized_bytes,
        "derived_materialized_load_bytes_per_b_iteration": materialized_bytes,
    }


def median_metric(records: list[dict[str, Any]], key: str) -> float:
    values = [float(record["timing"][key]) for record in records]
    require(len(values) == COUNTED_REPETITIONS, f"{key} sample count changed")
    return float(statistics.median(values))


def all_pairs_dominance(
    primary: list[dict[str, Any]],
    control: list[dict[str, Any]],
) -> float:
    primary_values = [
        float(record["timing"]["server_prompt_ms"]) for record in primary
    ]
    control_values = [
        float(record["timing"]["server_prompt_ms"]) for record in control
    ]
    wins = sum(
        primary_value < control_value
        for primary_value in primary_values
        for control_value in control_values
    )
    return wins / (len(primary_values)*len(control_values))


def classify(
    integrity_gates: Mapping[str, bool],
    speed_gates: Mapping[str, bool],
) -> str:
    if not all(integrity_gates.values()):
        return "reject-integrity-agents-a1-open-b-boundary"
    if not all(speed_gates.values()):
        return "reject-speed-agents-a1-open-b-boundary-exact"
    return "accept-bounded-agents-a1-mma-open-b-boundary"


def resource_gate(resources: Mapping[str, Any]) -> bool:
    sample_count = resources.get("wddm_sample_count")
    peak_bytes = resources.get("peak_wddm_bytes")
    return (
        resources.get("wddm_failure_reason") is None
        and isinstance(sample_count, int)
        and not isinstance(sample_count, bool)
        and sample_count > 0
        and isinstance(peak_bytes, int)
        and not isinstance(peak_bytes, bool)
        and peak_bytes <= harness.WDDM_CEILING_BYTES
    )


def adjudicate(
    *,
    routes: Mapping[str, dict[str, Any]],
    marker_evidence: Mapping[str, dict[str, Any]],
    before_bundle: Mapping[str, Any],
    after_bundle: Mapping[str, Any],
    static_evidence: Mapping[str, Any],
    stable_before: set[int],
    stable_after: set[int],
    environment_restored: bool,
) -> dict[str, Any]:
    primary = routes["register_open"]
    control = routes["global_materialized"]
    all_primary = [*primary["warmups"], *primary["counted"]]
    all_control = [*control["warmups"], *control["counted"]]
    primary_hashes = {
        record["generated_token_sha256"] for record in all_primary
    }
    control_hashes = {
        record["generated_token_sha256"] for record in all_control
    }
    primary_answers = {record["answer"] for record in all_primary}
    control_answers = {record["answer"] for record in all_control}
    primary_prompt = median_metric(primary["counted"], "server_prompt_ms")
    control_prompt = median_metric(control["counted"], "server_prompt_ms")
    primary_compute = statistics.median(
        float(record["timing"]["server_prompt_ms"])
        + float(record["timing"]["server_predicted_ms"])
        for record in primary["counted"]
    )
    control_compute = statistics.median(
        float(record["timing"]["server_prompt_ms"])
        + float(record["timing"]["server_predicted_ms"])
        for record in control["counted"]
    )
    primary_wall = statistics.median(
        float(record["custody_adjusted_wall_seconds"])
        for record in primary["counted"]
    )
    control_wall = statistics.median(
        float(record["custody_adjusted_wall_seconds"])
        for record in control["counted"]
    )
    prompt_speedup = control_prompt / primary_prompt
    compute_speedup = control_compute / primary_compute
    wall_speedup = control_wall / primary_wall
    dominance = all_pairs_dominance(
        primary["counted"],
        control["counted"],
    )
    integrity_gates = {
        "static_open_boundary_contract_exact": all(
            static_evidence["gates"].values()
        ),
        "same_runtime_bundle_before_after": before_bundle == after_bundle,
        "same_runtime_bundle_between_routes": (
            primary["readiness"]["binary"] == control["readiness"]["binary"]
        ),
        "model_identity_exact": (
            primary["readiness"]["model"]["sha256"] == MODEL_SHA256
            and control["readiness"]["model"]["sha256"] == MODEL_SHA256
        ),
        "checkpoint_zero_both_routes": (
            primary["readiness"]["launch_configuration"]["context_checkpoints"]
            == 0
            and control["readiness"]["launch_configuration"]["context_checkpoints"]
            == 0
        ),
        "scratch_reserved_both_routes": (
            primary["readiness"]["launch_configuration"][
                "fattn_b_scratch_reserved"
            ]
            is True
            and control["readiness"]["launch_configuration"][
                "fattn_b_scratch_reserved"
            ]
            is True
        ),
        "task_a_identity_exact": primary["task_a"] == control["task_a"],
        "branch_input_identity_exact": (
            primary["branch_identity"] == control["branch_identity"]
        ),
        "all_branch_answers_exact": (
            primary_answers == {EXPECTED_ANSWER}
            and control_answers == {EXPECTED_ANSWER}
        ),
        "all_branch_generated_tokens_exact": (
            len(primary_hashes) == 1
            and primary_hashes == control_hashes
        ),
        "all_branches_cache_disabled": all(
            record["cached_prompt_tokens"] == 0
            and record["fresh_prompt_tokens"] == EXPECTED_BRANCH_PROMPT_TOKENS
            for record in [*all_primary, *all_control]
        ),
        "tool_call_exact": (
            primary["tool_canary"]["validation"]["passed"] is True
            and control["tool_canary"]["validation"]["passed"] is True
            and primary["tool_canary"]["validation"]
            == control["tool_canary"]["validation"]
            and primary["tool_canary"]["generated_token_ids"]
            == control["tool_canary"]["generated_token_ids"]
        ),
        "runtime_marker_modes_exact": (
            all(
                marker["materialize"] == 0
                for marker in marker_evidence["register_open"]["markers"]
            )
            and all(
                marker["materialize"] == 1
                for marker in marker_evidence["global_materialized"]["markers"]
            )
        ),
        "runtime_marker_geometry_exact": (
            marker_evidence["register_open"]["normalized_geometry"]
            == marker_evidence["global_materialized"]["normalized_geometry"]
        ),
        "primary_materialization_zero_by_uniform_mode": (
            marker_evidence["register_open"][
                "derived_materialized_store_bytes_per_b_iteration"
            ]
            == [0]
            and marker_evidence["register_open"][
                "derived_materialized_load_bytes_per_b_iteration"
            ]
            == [0]
        ),
        "control_materialization_nonzero_by_uniform_mode": (
            bool(
                marker_evidence["global_materialized"][
                    "derived_materialized_store_bytes_per_b_iteration"
                ]
            )
            and all(
                value > 0
                for value in marker_evidence["global_materialized"][
                    "derived_materialized_store_bytes_per_b_iteration"
                ]
            )
            and marker_evidence["global_materialized"][
                "derived_materialized_store_bytes_per_b_iteration"
            ]
            == marker_evidence["global_materialized"][
                "derived_materialized_load_bytes_per_b_iteration"
            ]
        ),
        "resource_gates": (
            resource_gate(primary["resources"])
            and resource_gate(control["resources"])
        ),
        "cleanup_exact": all(
            route["cleanup"].get("integrity", {}).get("passed") is True
            for route in routes.values()
        ),
        "stable_listener_preserved": stable_after == set(
            stable_before
        ),
        "route_environment_restored": environment_restored,
    }
    speed_gates = {
        "prompt_speedup_at_least_1_02": (
            prompt_speedup >= MINIMUM_PROMPT_SPEEDUP
        ),
        "all_pairs_prompt_dominance_at_least_0_70": (
            dominance >= MINIMUM_ALL_PAIRS_DOMINANCE
        ),
        "complete_server_compute_non_regression": compute_speedup >= 1.0,
        "custody_adjusted_wall_non_regression": wall_speedup >= 1.0,
    }
    classification = classify(integrity_gates, speed_gates)
    return {
        "classification": classification,
        "verdict": "accept" if classification.startswith("accept-") else "reject",
        "integrity_gates": integrity_gates,
        "speed_gates": speed_gates,
        "metrics": {
            "primary_prompt_median_ms": primary_prompt,
            "control_prompt_median_ms": control_prompt,
            "prompt_speedup": prompt_speedup,
            "all_pairs_prompt_dominance": dominance,
            "primary_complete_compute_median_ms": primary_compute,
            "control_complete_compute_median_ms": control_compute,
            "complete_compute_speedup": compute_speedup,
            "primary_custody_adjusted_wall_median_seconds": primary_wall,
            "control_custody_adjusted_wall_median_seconds": control_wall,
            "custody_adjusted_wall_speedup": wall_speedup,
        },
    }


def execute(
    *,
    binary: Path,
    model: Path,
    expected_commit: str,
    output: Path,
    log_dir: Path,
    consumed_marker: Path,
) -> dict[str, Any]:
    identity = require_clean_pushed_head(expected_commit)
    require(output.resolve() != consumed_marker.resolve(), "output and marker collide")
    require(not output.exists(), f"result path already exists: {output}")
    require(not consumed_marker.exists(), f"marker path already exists: {consumed_marker}")
    require(not log_dir.exists(), f"log directory already exists: {log_dir}")
    require(model.is_file(), f"model missing: {model}")
    require(sha256_file(model) == MODEL_SHA256, "Agents-A1 model identity changed")
    require(ENVIRONMENT_NAME not in os.environ, f"{ENVIRONMENT_NAME} is already set")
    static_evidence = static_audit(binary)
    before_bundle = static_evidence["runtime_bundle"]
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_before = harness.live_runtime.require_stable()
    require(len(stable_before) == 1, "expected one protected stable listener")
    require(
        not harness.live_runtime.listener_pids(harness.live_runtime.PORT),
        "frontier port 9494 is occupied",
    )
    corpus = harness.carrier.load_public_corpus(ROOT)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    marker_state: dict[str, Any] = {"value": None}
    routes: dict[str, dict[str, Any]] = {}
    try:
        for route in ROUTE_ORDER:
            routes[route] = run_route(
                route=route,
                binary=binary,
                model=model,
                evaluator=evaluator,
                live_contract=live_contract,
                stable_pids=set(stable_before),
                root=roots[ROOT_ID],
                log_path=log_dir / f"{route}.log",
                consumed_marker_path=consumed_marker,
                expected_commit=expected_commit,
                marker_state=marker_state,
            )
        marker_evidence = {
            route: marker_geometry(
                log_dir / f"{route}.log",
                int(ROUTE_MODE[route]),
            )
            for route in ROUTE_ORDER
        }
        after_bundle = runtime_bundle(binary)
        stable_after = harness.live_runtime.require_stable()
        environment_restored = ENVIRONMENT_NAME not in os.environ
        require(
            not harness.live_runtime.listener_pids(harness.live_runtime.PORT),
            "frontier port remained occupied after both routes",
        )
        adjudication = adjudicate(
            routes=routes,
            marker_evidence=marker_evidence,
            before_bundle=before_bundle,
            after_bundle=after_bundle,
            static_evidence=static_evidence,
            stable_before=set(stable_before),
            stable_after=set(stable_after),
            environment_restored=environment_restored,
        )
        result = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "complete",
            "hypothesis": (
                "Keeping the real Agents-A1 MMA FlashAttention packed-B "
                "intermediate in registers is exact and faster than an otherwise "
                "identical forced global-address-space materialization."
            ),
            "intervention": (
                "Change only the uniform packed-B store/reload mode inside one "
                "candidate runtime; reserve identical scratch in both routes."
            ),
            "identity": identity,
            "model": {
                "path": str(model),
                "bytes": model.stat().st_size,
                "sha256": MODEL_SHA256,
            },
            "runtime_bundle_before": before_bundle,
            "runtime_bundle_after": after_bundle,
            "static_evidence": static_evidence,
            "configuration": {
                "route_order": list(ROUTE_ORDER),
                "warmups_per_route": WARMUPS_PER_ROUTE,
                "counted_repetitions_per_route": COUNTED_REPETITIONS,
                "root_id": ROOT_ID,
                "branch_number": BRANCH_NUMBER,
                "panel_sha256": BRANCH_PANEL_SHA256,
                "expected_answer": EXPECTED_ANSWER,
                "task_a_prompt_tokens": EXPECTED_TASK_A_PROMPT_TOKENS,
                "retained_root_tokens": EXPECTED_RETAINED_ROOT_TOKENS,
                "branch_prompt_tokens": EXPECTED_BRANCH_PROMPT_TOKENS,
                "minimum_prompt_speedup": MINIMUM_PROMPT_SPEEDUP,
                "minimum_all_pairs_dominance": MINIMUM_ALL_PAIRS_DOMINANCE,
                "primary_derived_materialized_bytes_per_b_iteration": 0,
                "control_derived_store_bytes_per_b_iteration": (
                    "nbatch_fa*ncols1*ncols2*2"
                ),
                "control_derived_load_bytes_per_b_iteration": (
                    "nbatch_fa*ncols1*ncols2*2"
                ),
                "traffic_note": (
                    "Byte counts are derived from the uniform runtime mode and "
                    "statically verified store/barrier/load path, not hardware "
                    "traffic counters."
                ),
            },
            "consumption_marker": marker_state["value"],
            "routes": routes,
            "runtime_marker_evidence": marker_evidence,
            "adjudication": adjudication,
            "claim_ceiling": (
                "One bounded Agents-A1 MMA FlashAttention packed-B open boundary; "
                "not reusable catalytic state, canonical .holo, restoration, "
                "recursive composition, or unbounded compute."
            ),
            "automatic_promotion": False,
            "research_goal_blocked": False,
            "next_boundary": (
                "If exact and fast, test a typed retained continuation reused by "
                "two suffix computations; if exact but not fast, retire packed-B "
                "materialization as a speed lever and return to the N/T/R/B frontier."
            ),
        }
        result["artifact"] = write_exclusive_json(output, result)
        return result
    except BaseException as caught:
        consumed = marker_state.get("value") is not None or consumed_marker.exists()
        if not consumed:
            shutil.rmtree(log_dir, ignore_errors=True)
            raise
        logs = {
            path.name: file_artifact(path)
            for path in sorted(log_dir.glob("*.log"))
            if path.is_file()
        }
        failure: dict[str, Any] = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed-after-consumption",
            "verdict": "reject-integrity-agents-a1-open-b-boundary",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "identity": identity,
            "model": {
                "path": str(model),
                "bytes": model.stat().st_size,
                "sha256": MODEL_SHA256,
            },
            "runtime_bundle_before": before_bundle,
            "static_evidence": static_evidence,
            "consumption_marker": marker_state.get("value"),
            "completed_routes": routes,
            "server_logs": logs,
            "automatic_promotion": False,
            "research_goal_blocked": False,
            "next_boundary": (
                "Preserve this consumed identity and create an evidence-motivated "
                "successor only after localizing the integrity failure."
            ),
        }
        if isinstance(caught, RouteExecutionError):
            failure["route_failure"] = caught.evidence
        try:
            failure["runtime_bundle_after_failure"] = runtime_bundle(binary)
        except BaseException as bundle_error:
            failure["runtime_bundle_after_failure_error"] = (
                f"{type(bundle_error).__name__}: {bundle_error}"
            )
        try:
            failure["stable_after_failure"] = sorted(
                harness.live_runtime.require_stable()
            )
            failure["frontier_port_free_after_failure"] = not (
                harness.live_runtime.listener_pids(harness.live_runtime.PORT)
            )
            failure["route_environment_restored_after_failure"] = (
                ENVIRONMENT_NAME not in os.environ
            )
        except BaseException as custody_error:
            failure["post_failure_custody_error"] = (
                f"{type(custody_error).__name__}: {custody_error}"
            )
        failure["artifact"] = write_exclusive_json(output, failure)
        raise ExperimentError(
            f"{EXPERIMENT_ID} failed after consumption; evidence preserved at {output}"
        ) from caught


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument(
        "--consumed-marker",
        type=Path,
        default=DEFAULT_CONSUMED_MARKER,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    if args.static_only:
        evidence = static_audit(binary)
        print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    require(bool(args.expected_commit), "--expected-commit is required")
    result = execute(
        binary=binary,
        model=args.model.resolve(strict=True),
        expected_commit=str(args.expected_commit),
        output=args.output.resolve(),
        log_dir=args.log_dir.resolve(),
        consumed_marker=args.consumed_marker.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
