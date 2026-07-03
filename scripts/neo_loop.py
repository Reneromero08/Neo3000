#!/usr/bin/env python3
"""Neo3000 deterministic candidate-build-and-evaluate loop.

neo-loop is machinery, not a second reasoning model. It builds a candidate,
launches it in isolation, runs immutable quality gates, tears down the
candidate, and records a compact result. It never promotes automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
CANDIDATE_ROOT = Path(str(ROOT) + "-candidate")
EVALUATOR_PATH = ROOT / "lab" / "EVALUATOR.json"
RESULTS_PATH = ROOT / "lab" / "results.jsonl"
STABLE_PORT = 9292
CANDIDATE_PORT = 9393
STABLE_BINARY = ROOT / "build" / "stable" / "bin" / "Release" / "llama-server.exe"
CANDIDATE_BUILD_DIR = CANDIDATE_ROOT / "build" / "candidate"
CANDIDATE_BUILD_SCRIPT = ROOT / "scripts" / "build_candidate.ps1"


class NeoLoopError(RuntimeError):
    pass


@dataclass
class CycleResult:
    verdict: str
    reason: str
    commit: str
    evidence: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise NeoLoopError(f"missing: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def request_json(url: str, timeout: float = 30) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise NeoLoopError(f"HTTP {e.code} at {url}: {body[:300]}")
    except urllib.error.URLError as e:
        raise NeoLoopError(f"cannot reach {url}: {e.reason}")


def health_ok(port: int, timeout: float = 30.0) -> bool:
    try:
        status, body = request_json(f"http://127.0.0.1:{port}/health", timeout)
        return status == 200 and isinstance(body, dict) and body.get("status") == "ok"
    except NeoLoopError:
        return False


def run_powershell(script: str, workdir: Path, timeout: int = 600) -> tuple[int, str, str]:
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", script, "-Clean"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def compute_protected_hashes(evaluator: dict, root: Path) -> dict[str, str]:
    hashes = {}
    for path in evaluator["protected_paths"]["files"]:
        full = root / path
        hashes[path] = sha256_file(full)
    return hashes


def verify_protected_hashes(evaluator: dict, root: Path, expected: dict[str, str]) -> bool:
    current = compute_protected_hashes(evaluator, root)
    for path, expected_hash in expected.items():
        if current.get(path) != expected_hash:
            raise NeoLoopError(f"protected hash changed: {path} (expected {expected_hash[:16]}..., got {current.get(path, 'MISSING')[:16]}...)")
    return True


def run_benchmark(port: int, args: list[str], timeout: int = 600) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / "scripts" / "baseline_harness.py")] + args
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout + result.stderr


def is_process_running(name: str) -> bool:
    try:
        result = subprocess.run(
            ["powershell", "-Command", f"Get-Process -Name '{name}' -ErrorAction SilentlyContinue"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def kill_process(name: str) -> None:
    subprocess.run(
        ["powershell", "-Command", f"Get-Process -Name '{name}' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"],
        capture_output=True, timeout=10,
    )
    time.sleep(2)


def cycle(declared_hypothesis: str) -> CycleResult:
    evaluator = load_json(EVALUATOR_PATH)

    # 1. Verify stable health
    if not health_ok(STABLE_PORT, timeout=10):
        raise NeoLoopError("stable server not healthy at start of cycle")

    # 2. Compute baseline hashes
    baseline_hashes = compute_protected_hashes(evaluator, ROOT)

    # 3. Verify candidate worktree
    if not CANDIDATE_ROOT.exists():
        raise NeoLoopError(f"candidate worktree missing: {CANDIDATE_ROOT}")
    candidate_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(CANDIDATE_ROOT), capture_output=True, text=True, timeout=30,
    )
    if candidate_status.stdout.strip():
        raise NeoLoopError(f"candidate worktree is not clean:\n{candidate_status.stdout[:500]}")

    # 4. Get candidate commit
    candidate_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(CANDIDATE_ROOT), capture_output=True, text=True, timeout=10,
    ).stdout.strip()

    # 5. Build candidate
    print("building candidate...", flush=True)
    build_rc, build_out, build_err = run_powershell(
        str(CANDIDATE_BUILD_SCRIPT), CANDIDATE_ROOT, timeout=600
    )
    if build_rc != 0:
        return CycleResult(
            verdict="reject", reason="build-failure",
            commit=candidate_commit,
            evidence={"build_exit": build_rc, "build_stderr": build_err[:500]},
        )

    # Verify stable survived the build
    if not health_ok(STABLE_PORT, timeout=10):
        raise NeoLoopError("stable server died during candidate build")

    # 6. Find candidate binary
    candidate_binary = CANDIDATE_BUILD_DIR / "bin" / "Release" / "llama-server.exe"
    if not candidate_binary.exists():
        return CycleResult(
            verdict="reject", reason="binary-missing",
            commit=candidate_commit,
            evidence={"expected": str(candidate_binary)},
        )

    # 7. Launch candidate
    model = os.environ.get("NEO3000_MODEL", "")
    if not model or not Path(model).exists():
        raise NeoLoopError("NEO3000_MODEL not set or model file not found")

    print("launching candidate...", flush=True)
    subprocess.Popen(
        [
            candidate_binary,
            "--model", model,
            "--alias", "agents-a1-candidate",
            "--host", "127.0.0.1",
            "--port", str(CANDIDATE_PORT),
            "--ctx-size", "4096",
            "--threads", "12",
            "--threads-batch", "12",
            "--batch-size", "512",
            "--ubatch-size", "128",
            "--gpu-layers", "auto",
            "--flash-attn", "auto",
            "--cache-type-k", "f16",
            "--cache-type-v", "f16",
            "--cache-prompt",
            "--metrics",
            "--no-webui",
            "--reasoning", "auto",
            "--cpu-moe",
        ],
        cwd=str(CANDIDATE_ROOT),
    )

    # Wait for health
    for _ in range(60):
        if health_ok(CANDIDATE_PORT, timeout=5):
            break
        time.sleep(5)
    else:
        kill_process("llama-server")
        return CycleResult(
            verdict="reject", reason="candidate-startup-timeout",
            commit=candidate_commit, evidence={},
        )

    # Verify stable still up
    if not health_ok(STABLE_PORT, timeout=10):
        kill_process("llama-server")
        raise NeoLoopError("stable server died during candidate launch")

    # 8. Run quality gates
    print("running benchmarks...", flush=True)
    results: dict[str, Any] = {"benchmarks": {}}

    # Smoke test
    smoke_rc, smoke_out = run_benchmark(CANDIDATE_PORT, [f"--base-url=http://127.0.0.1:{CANDIDATE_PORT}/v1", "--model=agents-a1-candidate", "--repeat=1"], timeout=300)
    results["benchmarks"]["smoke"] = {"exit": smoke_rc, "output_lines": smoke_out.splitlines()[-10:]}

    # Tool test
    tool_rc, tool_out = run_benchmark(CANDIDATE_PORT, [f"--base-url=http://127.0.0.1:{CANDIDATE_PORT}/v1", "--model=agents-a1-candidate", "--tool-test", "--output", str(ROOT / "lab" / "cand-tool.local.json"), "--repeat=1", "--max-tokens=512"], timeout=300)
    tool_passed = tool_rc == 0
    results["benchmarks"]["tool_call"] = {"exit": tool_rc, "passed": tool_passed}

    # 9. Verify protected hashes unchanged
    try:
        verify_protected_hashes(evaluator, ROOT, baseline_hashes)
        results["protected_hashes_ok"] = True
    except NeoLoopError as e:
        results["protected_hashes_ok"] = False
        results["hash_error"] = str(e)

    # 10. Stop candidate
    print("tearing down candidate...", flush=True)
    kill_process("llama-server")
    time.sleep(3)

    # 11. Verify stable health
    if not health_ok(STABLE_PORT, timeout=10):
        raise NeoLoopError("stable server died after candidate teardown")

    # 12. Classify
    if not results.get("protected_hashes_ok", False):
        return CycleResult(verdict="reject", reason="protected-hash-change", commit=candidate_commit, evidence=results)
    if not tool_passed:
        return CycleResult(verdict="reject", reason="tool-call-failure", commit=candidate_commit, evidence=results)
    if smoke_rc != 0:
        return CycleResult(verdict="reject", reason="smoke-test-failure", commit=candidate_commit, evidence=results)

    return CycleResult(
        verdict="reviewable-accept",
        reason="all-gates-passed",
        commit=candidate_commit,
        evidence=results,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis", type=str, default="", help="declared causal hypothesis")
    args = parser.parse_args()

    if not args.hypothesis:
        args.hypothesis = "neo-loop-validation"

    try:
        result = cycle(args.hypothesis)
    except NeoLoopError as e:
        result = CycleResult(verdict="reject", reason=f"loop-error: {e}", commit="unknown", evidence={})
    except Exception as e:
        result = CycleResult(verdict="reject", reason=f"exception: {e}", commit="unknown", evidence={})

    record = {
        "id": f"neo-loop-{utc_now().replace(':', '').replace('-', '')[:15]}",
        "timestamp": utc_now(),
        "hypothesis": args.hypothesis,
        "verdict": result.verdict,
        "reason": result.reason,
        "commit": result.commit,
        "evidence": result.evidence,
    }

    print(json.dumps(record, indent=2))
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    print(f"result appended to {RESULTS_PATH}")
    return 0 if result.verdict.startswith("reviewable") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NeoLoopError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"neo_loop: {exc}", file=sys.stderr)
        raise SystemExit(2)
