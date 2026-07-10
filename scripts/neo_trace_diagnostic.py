#!/usr/bin/env python3
"""Protected, stable-side controller for one matched Checkpoint 1A diagnostic.

This file deliberately has no git, build, promotion, or stable-process mutation
operations.  It can launch and stop only the candidate process object it creates.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from neo_loop import (
    CandidateVramSampler,
    NeoLoopError,
    gate_harness_args,
    health_ok,
    listener_pids,
    load_json,
    run_harness,
    stop_candidate,
    validate_gate,
    verify_lock,
    verify_model_identity,
    wddm_pid_memory_sample,
)


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT.parent / f"{ROOT.name}-candidate"
EVALUATOR_PATH = ROOT / "lab" / "EVALUATOR.json"
LOCAL_ROOT = CANDIDATE_ROOT / "benchmarks" / "local" / "trace-diagnostic"
MIB = 1024 * 1024
TRACE_BYTE_LIMIT = 64 * MIB
TRACE_RECORD_LIMIT = 200_000


@dataclass(frozen=True)
class ReadinessState:
    process_alive: bool
    health_ready: bool
    listener_matches: bool
    telemetry_attributed: bool
    memory_within_ceiling: bool
    ready: bool


@dataclass
class PhaseWindow:
    name: str
    start_monotonic_ns: int
    end_monotonic_ns: int | None = None
    candidate_cpu_seconds_before: float | None = None
    candidate_cpu_seconds_after: float | None = None
    candidate_cpu_seconds_delta: float | None = None
    result: dict[str, Any] | None = None


class PhaseRecorder:
    """Records strictly ordered, non-overlapping controller phase windows."""

    def __init__(self, clock: Callable[[], int] = time.monotonic_ns):
        self.clock = clock
        self.windows: list[PhaseWindow] = []

    def start(self, name: str, cpu_before: float | None = None) -> PhaseWindow:
        now = self.clock()
        if self.windows and self.windows[-1].end_monotonic_ns is None:
            raise NeoLoopError(f"phase {self.windows[-1].name} is still open")
        if self.windows and now < int(self.windows[-1].end_monotonic_ns):
            raise NeoLoopError("phase clock moved backwards")
        window = PhaseWindow(name, now, candidate_cpu_seconds_before=cpu_before)
        self.windows.append(window)
        return window

    def end(self, window: PhaseWindow, cpu_after: float | None = None, result: dict[str, Any] | None = None) -> None:
        if not self.windows or self.windows[-1] is not window or window.end_monotonic_ns is not None:
            raise NeoLoopError("phase window close order violation")
        now = self.clock()
        if now < window.start_monotonic_ns:
            raise NeoLoopError("phase end precedes phase start")
        window.end_monotonic_ns = now
        window.candidate_cpu_seconds_after = cpu_after
        if cpu_after is not None and window.candidate_cpu_seconds_before is not None:
            window.candidate_cpu_seconds_delta = round(cpu_after - window.candidate_cpu_seconds_before, 6)
        window.result = result


class TraceArtifactMonitor:
    """Incrementally validates newline-delimited schema-v2 trace artifacts."""

    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.offsets = {path: 0 for path in paths}
        self.buffers = {path: b"" for path in paths}
        self.records = 0
        self.total_bytes = 0
        self.header_records = 0
        self.writer_open_counts: list[int] = []
        self.failure: str | None = None

    def poll(self, final: bool = False) -> str | None:
        if self.failure:
            return self.failure
        self.total_bytes = sum(path.stat().st_size for path in self.paths if path.exists())
        if self.total_bytes > TRACE_BYTE_LIMIT:
            self.failure = "trace-byte-limit"
            return self.failure
        for path in self.paths:
            if not path.exists():
                continue
            size = path.stat().st_size
            offset = self.offsets[path]
            if size < offset:
                self.failure = "trace-file-rewritten"
                return self.failure
            if size == offset:
                continue
            with path.open("rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
            self.offsets[path] = size
            data = self.buffers[path] + chunk
            lines = data.split(b"\n")
            self.buffers[path] = lines.pop()
            for raw in lines:
                if not raw.strip():
                    continue
                try:
                    record = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self.failure = "trace-invalid-json"
                    return self.failure
                self.records += 1
                if self.records > TRACE_RECORD_LIMIT:
                    self.failure = "trace-record-limit"
                    return self.failure
                if record.get("schema_version") != 2:
                    self.failure = "trace-schema-version"
                    return self.failure
                try:
                    dropped = max(
                        int(record.get("dropped_event_count", 0) or 0),
                        int(record.get("dropped_events", 0) or 0),
                        int(record.get("dropped_records", 0) or 0),
                    )
                except (TypeError, ValueError):
                    self.failure = "trace-drop-count-invalid"
                    return self.failure
                if record.get("trace_truncated") is True or int(dropped or 0) > 0:
                    self.failure = "trace-truncated-or-dropped"
                    return self.failure
                if "writer_open_count" in record:
                    self.header_records += 1
                    try:
                        self.writer_open_counts.append(int(record["writer_open_count"]))
                    except (TypeError, ValueError):
                        self.failure = "trace-writer-open-count-invalid"
                        return self.failure
        if final and any(value.strip() for value in self.buffers.values()):
            self.failure = "trace-incomplete-final-line"
        return self.failure

    def evidence(self) -> dict[str, Any]:
        return {
            "paths": [str(path) for path in self.paths],
            "combined_bytes": self.total_bytes,
            "record_count": self.records,
            "schema_version": 2,
            "header_records": self.header_records,
            "writer_open_count_values": sorted(set(self.writer_open_counts)),
            "writer_open_count_valid": bool(self.writer_open_counts) and all(value == 1 for value in self.writer_open_counts),
            "trace_truncated": False if not self.failure else None,
            "dropped_records": 0 if not self.failure else None,
            "failure": self.failure,
        }


def readiness_state(process: Any, port: int, pid: int, sampler: Any,
                    health_fn: Callable[[int], bool] = health_ok,
                    listener_fn: Callable[[int], set[int]] = listener_pids) -> ReadinessState:
    alive = process.poll() is None
    healthy = health_fn(port)
    listener_matches = listener_fn(port) == {pid}
    attributed = sampler.has_valid_sample()
    failure = sampler.failure_reason()
    within = failure != "candidate-memory-ceiling"
    return ReadinessState(alive, healthy, listener_matches, attributed, within,
                          alive and healthy and listener_matches and attributed and within and failure is None)


def wait_for_readiness(process: Any, sampler: Any, port: int, timeout: float,
                       health_fn: Callable[[int], bool] = health_ok,
                       listener_fn: Callable[[int], set[int]] = listener_pids,
                       clock: Callable[[], float] = time.monotonic,
                       sleeper: Callable[[float], None] = time.sleep,
                       poll_seconds: float = 0.25) -> ReadinessState:
    deadline = clock() + timeout
    last = readiness_state(process, port, process.pid, sampler, health_fn, listener_fn)
    while not last.ready:
        if process.poll() is not None:
            raise NeoLoopError("candidate-process-exited-before-readiness")
        if sampler.failure_reason():
            raise NeoLoopError(sampler.failure_reason())
        if clock() >= deadline:
            raise NeoLoopError(f"candidate-readiness-timeout: {asdict(last)}")
        sleeper(poll_seconds)
        last = readiness_state(process, port, process.pid, sampler, health_fn, listener_fn)
    return last


def stable_integrity(port: int, expected_pids: set[int],
                     health_fn: Callable[[int], bool] = health_ok,
                     listener_fn: Callable[[int], set[int]] = listener_pids) -> tuple[bool, dict[str, Any]]:
    current_pids = listener_fn(port)
    healthy = health_fn(port)
    evidence = {"healthy": healthy, "listener_pids": sorted(current_pids), "expected_listener_pids": sorted(expected_pids)}
    return healthy and current_pids == expected_pids, evidence


def cleanup_candidate(process: Any, runtime: Path, stop_fn: Callable[[Any], dict[str, Any]] = stop_candidate) -> dict[str, Any]:
    """Stop only the exact launched process object and remove only its runtime."""
    stopped = stop_fn(process)
    if runtime.exists():
        shutil.rmtree(runtime)
    return {**stopped, "runtime_removed": not runtime.exists(), "launched_pid": process.pid if process else None}


def sampler_details(sampler: CandidateVramSampler, ceiling_mib: int, pre_count: int | None = None) -> dict[str, Any]:
    evidence = sampler.evidence(ceiling_mib)
    with sampler._lock:  # Preserve every attribution miss; base evidence intentionally keeps only a tail.
        failures = list(sampler.failures)
    if pre_count is None:
        pre_count = len(failures) if sampler.has_valid_sample() else 0
    evidence["pre_first_valid_misses"] = failures[:pre_count]
    evidence["post_attribution_failures"] = failures[pre_count:]
    return evidence


def process_cpu_seconds(pid: int) -> float | None:
    command = f"$p=Get-Process -Id {pid} -ErrorAction Stop; [double]$p.TotalProcessorTime.TotalSeconds"
    completed = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                               capture_output=True, text=True, timeout=10)
    try:
        return float(completed.stdout.strip()) if completed.returncode == 0 else None
    except ValueError:
        return None


def require_local_path(path: Path) -> Path:
    resolved = path.resolve()
    local = LOCAL_ROOT.resolve()
    if resolved != local and local not in resolved.parents:
        raise NeoLoopError(f"diagnostic output must remain under {local}")
    return resolved


def active_failure(process: Any, sampler: CandidateVramSampler, candidate_port: int,
                   stable_port: int, stable_pids: set[int], trace: TraceArtifactMonitor | None) -> str | None:
    if process.poll() is not None:
        return "candidate-process-exited"
    reason = sampler.failure_reason()
    if reason:
        return reason
    if listener_pids(candidate_port) != {process.pid}:
        return "candidate-listener-mismatch"
    stable_ok, _ = stable_integrity(stable_port, stable_pids)
    if not stable_ok:
        return "stable-server-mismatch"
    return trace.poll() if trace else None


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {})
    measurements = report.get("measurements", [])
    return {
        "summary": summary,
        "exact_response_passed": report.get("exact_response_passed"),
        "measurement_count": len(measurements),
        "measurements": [{
            "status": item.get("status"),
            "content": item.get("content"),
            "reasoning_present": bool(item.get("reasoning_content")),
            "reported_tokens_per_second": item.get("reported_tokens_per_second"),
            "time_to_first_token_ms": item.get("time_to_first_token_ms"),
        } for item in measurements],
    }


def median_decode(result: dict[str, Any]) -> float | None:
    value = result.get("summary", {}).get("median_reported_tokens_per_second")
    return float(value) if isinstance(value, (int, float)) else None


def phase_evidence(window: PhaseWindow, binary_mode: str, candidate_pid: int | None) -> dict[str, Any]:
    evidence = asdict(window)
    evidence["binary_mode"] = binary_mode
    evidence["candidate_pid"] = candidate_pid
    return evidence


def run_phase(name: str, gate: dict[str, Any], repeat: int, score: bool, process: Any,
              sampler: CandidateVramSampler, recorder: PhaseRecorder, evaluator: dict[str, Any],
              output_dir: Path, trace: TraceArtifactMonitor | None, stable_pids: set[int],
              baseline_phase: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate_port = evaluator["candidate_launch"]["port"]
    stable_port = evaluator["stable_launch"]["port"]
    failure = active_failure(process, sampler, candidate_port, stable_port, stable_pids, trace)
    if failure:
        raise NeoLoopError(failure)
    window = recorder.start(name, process_cpu_seconds(process.pid))
    harness_output = output_dir / f"{name}.local.json"
    exit_code, raw = run_harness(
        candidate_port,
        evaluator["candidate_launch"]["model_alias"],
        harness_output,
        gate_harness_args(gate, repeat, evaluator["timeouts"]["benchmark_seconds"]),
        evaluator["timeouts"]["benchmark_seconds"],
        abort_check=lambda: active_failure(process, sampler, candidate_port, stable_port, stable_pids, trace),
    )
    if exit_code != 0 or "report" not in raw:
        raise NeoLoopError(raw.get("aborted_reason") or f"{name}-harness-exit-{exit_code}")
    valid, reason = validate_gate(raw["report"], gate, score)
    summary = report_summary(raw["report"])
    summary["gate_valid"] = valid
    summary["gate_reason"] = reason
    if not valid:
        raise NeoLoopError(f"{name}: {reason}")
    if trace and trace.poll():
        raise NeoLoopError(trace.failure)
    if baseline_phase is not None:
        control_tps = median_decode(baseline_phase)
        trace_tps = median_decode(summary)
        if control_tps and trace_tps is not None:
            summary["matched_control_decode_tps"] = control_tps
            summary["decode_ratio_to_control"] = round(trace_tps / control_tps, 6)
            if trace_tps < control_tps * 0.8:
                raise NeoLoopError(f"{name}-decode-regression-over-20-percent")
    recorder.end(window, process_cpu_seconds(process.pid), summary)
    return summary


def launch_args(binary: Path, model: Path, evaluator: dict[str, Any]) -> list[str]:
    cfg = evaluator["candidate_launch"]
    return [str(binary), "--model", str(model), "--alias", cfg["model_alias"],
            "--host", "127.0.0.1", "--port", str(cfg["port"]), "--ctx-size", str(cfg["ctx_size"]),
            "--threads", str(cfg["threads"]), "--threads-batch", str(cfg["threads"]),
            "--batch-size", str(cfg["batch"]), "--ubatch-size", str(cfg["ubatch"]),
            "--gpu-layers", "auto", "--flash-attn", "auto", "--cache-type-k", "f16",
            "--cache-type-v", "f16", "--cache-prompt", "--metrics", "--no-webui",
            "--reasoning", "auto", "--cpu-moe"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--binary-mode", required=True, choices=("trace-disabled", "trace-enabled"))
    parser.add_argument("--telemetry-only", action="store_true")
    parser.add_argument("--trace-path", action="append", type=Path, default=[])
    parser.add_argument("--baseline-result", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = require_local_path(args.output)
    trace_paths = [require_local_path(path) for path in args.trace_path]
    if args.binary_mode == "trace-enabled" and not trace_paths:
        raise NeoLoopError("trace-enabled mode requires --trace-path")
    if args.binary_mode == "trace-disabled" and trace_paths:
        raise NeoLoopError("trace-disabled mode cannot declare trace paths")
    if not args.telemetry_only and args.binary_mode == "trace-enabled" and not args.baseline_result:
        raise NeoLoopError("trace-enabled workload requires --baseline-result")
    binary = args.binary.resolve()
    if CANDIDATE_ROOT.resolve() not in binary.parents:
        raise NeoLoopError("binary is not inside the isolated candidate worktree")
    evaluator = load_json(EVALUATOR_PATH)
    verify_lock(evaluator)
    stable_port = evaluator["stable_launch"]["port"]
    candidate_port = evaluator["candidate_launch"]["port"]
    if not health_ok(stable_port):
        raise NeoLoopError("stable server unhealthy before launch")
    stable_pids = listener_pids(stable_port)
    if not stable_pids:
        raise NeoLoopError("stable server has no listener PID")
    if listener_pids(candidate_port):
        raise NeoLoopError("candidate port is already occupied")
    verify_model_identity(args.model.resolve(), evaluator)
    output.parent.mkdir(parents=True, exist_ok=True)
    for path in trace_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
    runtime = CANDIDATE_ROOT / evaluator["isolation"]["candidate_runtime_directory"] / f"trace-diagnostic-{int(time.time())}"
    runtime.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update({"TMP": str(runtime), "TEMP": str(runtime), "TMPDIR": str(runtime)})
    if trace_paths:
        env["NEO_COMPUTE_TRACE_PATH"] = str(trace_paths[0])
        env["NEO_COMPUTE_TRACE_REQUEST_ID"] = "checkpoint1a-fixed-diagnostic"
    recorder = PhaseRecorder()
    startup = recorder.start("startup")
    process: subprocess.Popen[str] | None = None
    sampler: CandidateVramSampler | None = None
    trace = TraceArtifactMonitor(trace_paths) if trace_paths else None
    result: dict[str, Any] = {
        "schema_version": 1,
        "mode": args.binary_mode,
        "telemetry_only": args.telemetry_only,
        "stable_before": {"healthy": True, "listener_pids": sorted(stable_pids)},
        "candidate_binary": str(binary),
        "model": str(args.model.resolve()),
        "verdict": "reject",
    }
    error: str | None = None
    pre_miss_count: int | None = None
    try:
        process = subprocess.Popen(launch_args(binary, args.model.resolve(), evaluator), cwd=CANDIDATE_ROOT,
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        startup.candidate_cpu_seconds_before = 0.0
        memory = evaluator["memory"]
        sampler = CandidateVramSampler(process.pid, memory["candidate_vram_mib_ceiling"],
                                       memory["sample_interval_seconds"], memory["telemetry_grace_seconds"])
        sampler.start()  # Must be immediate after Popen, before any readiness or inference work.
        ready = wait_for_readiness(process, sampler, candidate_port, evaluator["timeouts"]["candidate_health_seconds"])
        with sampler._lock:
            pre_miss_count = len(sampler.failures)
        recorder.end(startup, process_cpu_seconds(process.pid), {"readiness": asdict(ready)})
        result["candidate_pid"] = process.pid
        result["readiness"] = {**asdict(ready), "readiness_seconds": round((startup.end_monotonic_ns - startup.start_monotonic_ns) / 1_000_000_000, 3)}
        if not args.telemetry_only:
            baseline = load_json(require_local_path(args.baseline_result)) if args.baseline_result else None
            baseline_phases = {item["name"]: item.get("result", {}) for item in baseline.get("phases", [])} if baseline else {}
            gates = evaluator["gates"]
            sequence = [
                ("cold_reasoning", gates["reasoning"], 1, False),
                ("warm_transport", gates["repeat"], 3, False),
                ("warm_reasoning", gates["reasoning"], 1, False),
                ("performance_warmup", gates["warm_performance"], 1, False),
                ("performance_counted", gates["warm_performance"], 2, True),
            ]
            for name, gate, repeat, score in sequence:
                run_phase(name, gate, repeat, score, process, sampler, recorder, evaluator, output.parent,
                          trace, stable_pids, baseline_phases.get(name))
        if trace and trace.poll():
            raise NeoLoopError(trace.failure)
        if trace and not args.telemetry_only and not trace.evidence()["writer_open_count_valid"]:
            raise NeoLoopError("trace-writer-open-count-mismatch")
        result["verdict"] = "accept"
    except (NeoLoopError, OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        error = str(exc)
        result["error"] = error
    finally:
        if recorder.windows and recorder.windows[-1].end_monotonic_ns is None:
            recorder.end(recorder.windows[-1], process_cpu_seconds(process.pid) if process else None,
                         {"error": error or result.get("error") or "phase-incomplete"})
        teardown = recorder.start("teardown", process_cpu_seconds(process.pid) if process else None)
        result["cleanup"] = cleanup_candidate(process, runtime) if process else {"runtime_removed": False}
        if sampler:
            sampler.stop()
            result["telemetry"] = sampler_details(sampler, evaluator["memory"]["candidate_vram_mib_ceiling"], pre_miss_count)
        if trace:
            trace.poll(final=True)
            result["trace"] = trace.evidence()
            if trace.failure or (not args.telemetry_only and not trace.evidence()["writer_open_count_valid"]):
                result["verdict"] = "reject"
                result["error"] = result.get("error") or trace.failure or "trace-writer-open-count-mismatch"
        retirement = []
        if process:
            for _ in range(5):
                sample = wddm_pid_memory_sample(process.pid)
                retirement.append({"available": sample.available, "bytes": sample.bytes, "instances": sample.instances, "error": sample.error})
                time.sleep(1.0)
        result["retirement_samples"] = retirement
        deadline = time.monotonic() + 15
        while listener_pids(candidate_port) and time.monotonic() < deadline:
            time.sleep(0.25)
        result["candidate_listener_pids_after"] = sorted(listener_pids(candidate_port))
        stable_ok, stable_after = stable_integrity(stable_port, stable_pids)
        result["stable_after"] = stable_after
        recorder.end(teardown, None, {"stable_unchanged": stable_ok, "candidate_port_free": not result["candidate_listener_pids_after"]})
        if not stable_ok or result["candidate_listener_pids_after"]:
            result["verdict"] = "reject"
            result["error"] = result.get("error") or "cleanup-integrity-failure"
        try:
            verify_lock(evaluator)
            result["protected_lock_verified_after"] = True
        except NeoLoopError as exc:
            result["protected_lock_verified_after"] = False
            result["verdict"] = "reject"
            result["error"] = result.get("error") or str(exc)
        result["phases"] = [phase_evidence(window, args.binary_mode, process.pid if process else None) for window in recorder.windows]
        result["trace_timestamp_partition"] = {
            "clock": "time.monotonic_ns",
            "windows": [{"name": window.name,
                         "start_monotonic_ns": window.start_monotonic_ns,
                         "end_monotonic_ns": window.end_monotonic_ns}
                        for window in recorder.windows],
        }
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "output": str(output), "error": result.get("error")}))
    return 0 if result["verdict"] == "accept" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NeoLoopError as exc:
        print(json.dumps({"verdict": "reject", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
