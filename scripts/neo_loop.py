#!/usr/bin/env python3
"""Run one bounded Neo3000 candidate cycle without touching stable.

The controller is deliberately conservative: it never pushes, merges, rebases,
or writes the candidate worktree.  A human or supervised agent prepares the
candidate diff; this program only verifies, builds, evaluates, tears down, and
records it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT.parent / f"{ROOT.name}-candidate"
EVALUATOR_PATH = ROOT / "lab" / "EVALUATOR.json"
LOCK_PATH = ROOT / "lab" / "EVALUATOR.lock.json"
RESULTS_PATH = ROOT / "lab" / "results.jsonl"
LOCK_DYNAMIC_PATHS = {"lab/EVALUATOR.lock.json", "lab/results.jsonl"}


class NeoLoopError(RuntimeError):
    """A declared safety or quality gate failed."""


@dataclass
class CycleResult:
    verdict: str
    reason: str
    commit: str
    evidence: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "MISSING"


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise NeoLoopError(f"missing required file: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def git(root: Path, *args: str, timeout: int = 30) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, timeout=timeout
    )
    if completed.returncode:
        raise NeoLoopError(
            f"git {' '.join(args)} failed: {(completed.stderr or completed.stdout).strip()[:500]}"
        )
    return completed.stdout.strip()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def require_distinct_paths(left: Path, right: Path, label: str) -> None:
    if left.resolve() == right.resolve() or is_within(left, right) or is_within(right, left):
        raise NeoLoopError(f"isolation failure: overlapping {label}: {left} and {right}")


def make_lock(evaluator: dict[str, Any]) -> dict[str, Any]:
    protected_files = evaluator["protected_paths"]["files"]
    controller_files = evaluator["controller_files"]
    benchmark_files = evaluator["benchmark_prompt_sources"]
    hashed_files = sorted(
        path for path in set(protected_files + controller_files + benchmark_files)
        if path not in LOCK_DYNAMIC_PATHS
    )
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "evaluator_sha256": sha256_file(EVALUATOR_PATH),
        "protected_file_hashes": {path: sha256_file(ROOT / path) for path in hashed_files},
        "benchmark_prompt_hashes": {
            prompt["id"]: sha256_bytes(prompt["text"].encode("utf-8"))
            for prompt in evaluator["inline_prompt_sources"]
        },
        "model_identity": evaluator["model"],
        "baseline_source_commit": git(ROOT, "rev-parse", "HEAD"),
        "stable_launch": evaluator["stable_launch"],
        "candidate_launch": evaluator["candidate_launch"],
        "protected_paths": evaluator["protected_paths"]["files"],
        "candidate_editable_paths": evaluator["candidate_editable_paths"]["paths"],
        "controller_files": controller_files,
    }


def write_lock() -> None:
    evaluator = load_json(EVALUATOR_PATH)
    lock = make_lock(evaluator)
    LOCK_PATH.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {LOCK_PATH}")


def verify_lock(evaluator: dict[str, Any]) -> dict[str, Any]:
    lock = load_json(LOCK_PATH)
    if lock.get("schema_version") != 1:
        raise NeoLoopError("unsupported evaluator lock schema")
    if lock.get("evaluator_sha256") != sha256_file(EVALUATOR_PATH):
        raise NeoLoopError("evaluator manifest differs from its lockfile")
    for key in ("model_identity", "stable_launch", "candidate_launch", "protected_paths", "candidate_editable_paths"):
        if key not in lock:
            raise NeoLoopError(f"lockfile missing {key}")
    expected_hashes = lock.get("protected_file_hashes", {})
    if not expected_hashes:
        raise NeoLoopError("lockfile contains no protected hashes")
    for path, expected in expected_hashes.items():
        actual = sha256_file(ROOT / path)
        if actual != expected:
            raise NeoLoopError(
                f"protected hash changed: {path} (expected {expected}, actual {actual})"
            )
    for prompt in evaluator["inline_prompt_sources"]:
        expected = lock["benchmark_prompt_hashes"].get(prompt["id"])
        actual = sha256_bytes(prompt["text"].encode("utf-8"))
        if expected != actual:
            raise NeoLoopError(f"benchmark prompt changed: {prompt['id']} (expected {expected}, actual {actual})")
    return lock


def request_json(url: str, timeout: float = 30) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise NeoLoopError(f"request failed for {url}: {exc}") from exc


def health_ok(port: int, timeout: float = 10.0) -> bool:
    try:
        status, body = request_json(f"http://127.0.0.1:{port}/health", timeout)
        return status == 200 and isinstance(body, dict) and body.get("status") == "ok"
    except NeoLoopError:
        return False


def port_is_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def listener_pids(port: int) -> set[int]:
    command = (
        "Get-NetTCPConnection -State Listen -LocalPort "
        f"{port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"
    )
    completed = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=10)
    return {int(line) for line in completed.stdout.splitlines() if line.strip().isdigit()}


def candidate_changes(baseline: str) -> list[str]:
    changed = set()
    for args in (("diff", "--name-only", f"{baseline}...HEAD"), ("diff", "--name-only"), ("diff", "--cached", "--name-only")):
        changed.update(filter(None, git(CANDIDATE_ROOT, *args).splitlines()))
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=CANDIDATE_ROOT, text=True, capture_output=True, timeout=30, check=True,
    )
    for line in completed.stdout.splitlines():
        if len(line) >= 4:
            changed.add(line[3:].replace("\\", "/"))
    return sorted(changed)


def allowed_candidate_path(path: str, allowlist: list[str]) -> bool:
    normalized = path.replace("\\", "/").rstrip("/")
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix.rstrip("/") + "/") for prefix in allowlist)


def preflight(evaluator: dict[str, Any]) -> dict[str, Any]:
    lock = verify_lock(evaluator)
    if not CANDIDATE_ROOT.is_dir() or CANDIDATE_ROOT.resolve() == ROOT.resolve():
        raise NeoLoopError("candidate worktree is missing or identical to stable")
    if git(ROOT, "branch", "--show-current") != "main":
        raise NeoLoopError("stable worktree is not on main")
    candidate_branch = git(CANDIDATE_ROOT, "branch", "--show-current")
    if candidate_branch == "main":
        raise NeoLoopError("candidate worktree may not use main")
    stable_build = ROOT / evaluator["isolation"]["stable_build_directory"]
    candidate_build = CANDIDATE_ROOT / evaluator["isolation"]["candidate_build_directory"]
    stable_runtime = ROOT / evaluator["isolation"]["stable_runtime_directory"]
    candidate_runtime = CANDIDATE_ROOT / evaluator["isolation"]["candidate_runtime_directory"]
    require_distinct_paths(stable_build, candidate_build, "build directories")
    require_distinct_paths(stable_runtime, candidate_runtime, "runtime directories")
    stable_port = evaluator["stable_launch"]["port"]
    candidate_port = evaluator["candidate_launch"]["port"]
    if stable_port == candidate_port or port_is_listening(candidate_port):
        raise NeoLoopError(f"candidate port collision at {candidate_port}")
    baseline = git(CANDIDATE_ROOT, "merge-base", "HEAD", "main")
    changes = candidate_changes(baseline)
    forbidden = [path for path in changes if not allowed_candidate_path(path, evaluator["candidate_editable_paths"]["paths"])]
    if forbidden:
        raise NeoLoopError(f"candidate path allowlist violation: {', '.join(forbidden)}")
    return {"baseline": baseline, "changes": changes, "candidate_branch": candidate_branch, "lock": lock}


def run_powershell(script: Path, workdir: Path, timeout: int) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Clean"],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        raise NeoLoopError(f"build timeout after {timeout}s") from exc


def stop_candidate(process: subprocess.Popen[str] | None) -> dict[str, Any]:
    if process is None or process.poll() is not None:
        return {"candidate_process_stopped": True, "pid": process.pid if process else None}
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=20)
    return {"candidate_process_stopped": process.poll() is not None, "pid": process.pid}


def candidate_vram_mib(pid: int) -> int | None:
    command = "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits"
    try:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        for line in completed.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) == 2 and parts[0].isdigit() and int(parts[0]) == pid:
                return int(parts[1])
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def verify_model_identity(model: Path, evaluator: dict[str, Any]) -> None:
    expected = evaluator["model"]
    if model.stat().st_size != expected["size_bytes"]:
        raise NeoLoopError(
            f"model size changed: expected {expected['size_bytes']}, actual {model.stat().st_size}"
        )
    actual_hash = sha256_file(model).upper()
    if actual_hash != expected["sha256"].upper():
        raise NeoLoopError(
            f"model identity changed: expected {expected['sha256']}, actual {actual_hash}"
        )


def run_harness(port: int, model: str, output: Path, args: list[str], timeout: int) -> tuple[int, dict[str, Any]]:
    command = [sys.executable, str(ROOT / "scripts" / "baseline_harness.py"), f"--base-url=http://127.0.0.1:{port}/v1", f"--model={model}", "--output", str(output), *args]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise NeoLoopError(f"benchmark timeout after {timeout}s") from exc
    result: dict[str, Any] = {"exit": completed.returncode, "stdout_tail": completed.stdout.splitlines()[-8:], "stderr_tail": completed.stderr.splitlines()[-8:]}
    if output.is_file():
        result["report"] = load_json(output)
    return completed.returncode, result


def validate_smoke(report: dict[str, Any], require_reasoning: bool, min_tps: float) -> tuple[bool, str]:
    summary = report.get("summary", {})
    measurements = report.get("measurements", [])
    if not summary.get("all_http_200") or not summary.get("all_streamed_multiple_events"):
        return False, "malformed or incomplete text stream"
    if report.get("exact_response_passed") is not True:
        return False, "text quality gate failed"
    if not measurements or not all(isinstance(item.get("content"), str) for item in measurements):
        return False, "malformed text payload"
    if require_reasoning and not all(isinstance(item.get("reasoning_content"), str) and item["reasoning_content"] for item in measurements):
        return False, "reasoning content missing or malformed"
    tps = summary.get("median_reported_tokens_per_second")
    if not isinstance(tps, (int, float)) or tps < min_tps:
        return False, f"performance gate failed: {tps!r} TPS < {min_tps}"
    return True, "ok"


def cancellation_gate(port: int, model: str, timeout: int) -> bool:
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "Count upward slowly."}], "max_tokens": 256, "stream": True}).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json", "Accept": "text/event-stream"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if not response.readline().startswith(b"data:"):
                return False
        return health_ok(port, timeout=10)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def cycle(declared_hypothesis: str) -> CycleResult:
    evaluator = load_json(EVALUATOR_PATH)
    preflight_result = preflight(evaluator)
    stable_port = evaluator["stable_launch"]["port"]
    candidate_port = evaluator["candidate_launch"]["port"]
    timeouts = evaluator["timeouts"]
    if not health_ok(stable_port, timeout=timeouts["stable_health_seconds"]):
        raise NeoLoopError("stable server not healthy at cycle start")
    stable_pids_before = listener_pids(stable_port)
    if not stable_pids_before:
        raise NeoLoopError("stable server has no listener PID")
    stable_head_before = git(ROOT, "rev-parse", "HEAD")
    stable_status_before = git(ROOT, "status", "--porcelain")
    candidate_commit = git(CANDIDATE_ROOT, "rev-parse", "HEAD")
    candidate_runtime = CANDIDATE_ROOT / evaluator["isolation"]["candidate_runtime_directory"]
    candidate_runtime.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen[str] | None = None
    evidence: dict[str, Any] = {"preflight": {key: value for key, value in preflight_result.items() if key != "lock"}}
    try:
        build_script = CANDIDATE_ROOT / "scripts" / "build_candidate.ps1"
        build_rc, build_out, build_err = run_powershell(build_script, CANDIDATE_ROOT, timeouts["build_seconds"])
        evidence["build"] = {"exit": build_rc, "stdout_tail": build_out.splitlines()[-8:], "stderr_tail": build_err.splitlines()[-8:]}
        if build_rc:
            return CycleResult("reject", "build-failure", candidate_commit, evidence)
        if not health_ok(stable_port, timeout=timeouts["stable_health_seconds"]):
            raise NeoLoopError("stable server died during candidate build")

        binary = CANDIDATE_ROOT / evaluator["isolation"]["candidate_build_directory"] / "bin" / "Release" / "llama-server.exe"
        model = os.environ.get("NEO3000_MODEL", "")
        if not binary.is_file() or not model or not Path(model).is_file():
            raise NeoLoopError("candidate binary or NEO3000_MODEL is unavailable")
        verify_model_identity(Path(model), evaluator)
        launch = evaluator["candidate_launch"]
        args = [str(binary), "--model", model, "--alias", launch["model_alias"], "--host", "127.0.0.1", "--port", str(candidate_port), "--ctx-size", str(launch["ctx_size"]), "--threads", str(launch["threads"]), "--threads-batch", str(launch["threads"]), "--batch-size", str(launch["batch"]), "--ubatch-size", str(launch["ubatch"]), "--gpu-layers", "auto", "--flash-attn", "auto", "--cache-type-k", "f16", "--cache-type-v", "f16", "--cache-prompt", "--metrics", "--no-webui", "--reasoning", "auto", "--cpu-moe"]
        environment = os.environ.copy()
        environment.update({"TMP": str(candidate_runtime), "TEMP": str(candidate_runtime), "TMPDIR": str(candidate_runtime)})
        process = subprocess.Popen(args, cwd=CANDIDATE_ROOT, env=environment, text=True)
        deadline = time.monotonic() + timeouts["candidate_health_seconds"]
        crashes = 0
        while time.monotonic() < deadline and not health_ok(candidate_port, timeout=3):
            if process.poll() is not None:
                crashes += 1
                break
            time.sleep(2)
        if not health_ok(candidate_port, timeout=3):
            if crashes >= evaluator["crash_ceiling_per_cycle"]:
                return CycleResult("reject", "candidate-crash-ceiling", candidate_commit, evidence)
            return CycleResult("reject", "candidate-health-timeout", candidate_commit, evidence)
        memory = candidate_vram_mib(process.pid)
        evidence["candidate_vram_mib"] = memory
        if memory is not None and memory > evaluator["memory"]["candidate_vram_mib_ceiling"]:
            return CycleResult("reject", "candidate-memory-ceiling", candidate_commit, evidence)

        smoke_file = candidate_runtime / "smoke.json"
        smoke_rc, smoke = run_harness(candidate_port, launch["model_alias"], smoke_file, ["--repeat=1", "--max-tokens=64", f"--timeout={timeouts['benchmark_seconds']}"], timeouts["benchmark_seconds"])
        evidence["smoke"] = smoke
        smoke_ok, smoke_reason = validate_smoke(smoke.get("report", {}), False, evaluator["performance"]["min_decode_tps"])
        if smoke_rc or not smoke_ok:
            return CycleResult("reject", smoke_reason, candidate_commit, evidence)

        reasoning_file = candidate_runtime / "reasoning.json"
        reasoning_rc, reasoning = run_harness(
            candidate_port,
            launch["model_alias"],
            reasoning_file,
            [
                "--prompt=Reason briefly, then reply with exactly: NEO3000 REASONING OK",
                "--expect-content=NEO3000 REASONING OK",
                "--repeat=1",
                "--max-tokens=128",
                f"--timeout={timeouts['benchmark_seconds']}",
            ],
            timeouts["benchmark_seconds"],
        )
        evidence["reasoning"] = reasoning
        reasoning_ok, reasoning_reason = validate_smoke(
            reasoning.get("report", {}), True, evaluator["performance"]["min_decode_tps"]
        )
        if reasoning_rc or not reasoning_ok:
            return CycleResult("reject", reasoning_reason, candidate_commit, evidence)

        tool_file = candidate_runtime / "tool.json"
        tool_rc, tool = run_harness(candidate_port, launch["model_alias"], tool_file, ["--tool-test", "--repeat=1", "--max-tokens=512", f"--timeout={timeouts['benchmark_seconds']}"], timeouts["benchmark_seconds"])
        evidence["tool"] = tool
        if tool_rc or not tool.get("report", {}).get("tool_call_passed"):
            return CycleResult("reject", "malformed-tool-call", candidate_commit, evidence)

        if not cancellation_gate(candidate_port, launch["model_alias"], timeouts["benchmark_seconds"]):
            return CycleResult("reject", "cancellation-regression", candidate_commit, evidence)
        repeat_file = candidate_runtime / "repeat.json"
        repeat_rc, repeat = run_harness(candidate_port, launch["model_alias"], repeat_file, ["--repeat=3", "--max-tokens=64", f"--timeout={timeouts['benchmark_seconds']}"], timeouts["benchmark_seconds"])
        evidence["repeat"] = repeat
        repeat_ok, repeat_reason = validate_smoke(repeat.get("report", {}), False, evaluator["performance"]["min_decode_tps"])
        if repeat_rc or not repeat_ok:
            return CycleResult("reject", f"repeated-turn-regression: {repeat_reason}", candidate_commit, evidence)
        return CycleResult("reviewable-accept", "all-safety-and-quality-gates-passed", candidate_commit, evidence)
    finally:
        evidence["cleanup"] = stop_candidate(process)
        shutil.rmtree(candidate_runtime, ignore_errors=True)
        evidence["candidate_runtime_removed"] = not candidate_runtime.exists()
        if not health_ok(stable_port, timeout=timeouts["stable_health_seconds"]):
            raise NeoLoopError("stable server died after candidate teardown")
        if listener_pids(stable_port) != stable_pids_before:
            raise NeoLoopError("stable listener changed during candidate cycle")
        if git(ROOT, "rev-parse", "HEAD") != stable_head_before or git(ROOT, "status", "--porcelain") != stable_status_before:
            raise NeoLoopError("stable worktree changed during candidate cycle")
        verify_lock(evaluator)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis", default="neo-loop-validation")
    parser.add_argument("--write-lock", action="store_true", help="regenerate the tracked lockfile after intentional evaluator changes")
    parser.add_argument("--preflight", action="store_true", help="run static lock, branch, path, and port gates only")
    args = parser.parse_args()
    if args.write_lock:
        write_lock()
        return 0
    try:
        evaluator = load_json(EVALUATOR_PATH)
        if args.preflight:
            print(json.dumps(preflight(evaluator), indent=2, default=str))
            return 0
        result = cycle(args.hypothesis)
    except (NeoLoopError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        result = CycleResult("reject", str(exc), "unknown", {})
    record = {"id": f"neo-loop-{utc_now().replace(':', '').replace('-', '')[:15]}", "timestamp": utc_now(), "hypothesis": args.hypothesis, "verdict": result.verdict, "reason": result.reason, "commit": result.commit, "evidence": result.evidence}
    print(json.dumps(record, indent=2))
    with RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return 0 if result.verdict == "reviewable-accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
