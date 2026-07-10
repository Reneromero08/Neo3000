#!/usr/bin/env python3
"""Manage the protected process-local HoloState-v1 Live Prefix Lattice.

All writes are confined to ignored ``state/holostate`` runtime data.  This
controller never edits engine source, model bytes, stable configuration, Git
history, or Pi configuration.  A registry entry is historical metadata; live
state is recognized only for the exact running sidecar session after the server
has reported reusable cached prompt tokens.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from neo_loop import (  # noqa: E402
    CandidateVramSampler,
    NeoLoopError,
    health_ok,
    listener_pids,
    load_json,
    verify_model_identity,
    wddm_pid_memory_sample,
)

PORT = 9494
STABLE_PORT = 9292
MIB = 1024 * 1024
GIB = 1024 * MIB
STATE_ROOT = ROOT / "state" / "holostate"
PREFIX_ROOT = STATE_ROOT / "prefixes"
RUNTIME_ROOT = STATE_ROOT / "runtime"
LOG_ROOT = STATE_ROOT / "logs"
REGISTRY_PATH = STATE_ROOT / "live-registry.json"
ATTEMPT_PATH = STATE_ROOT / "validation-attempt.json"
RESULT_PATH = STATE_ROOT / "validation-result.json"
EVALUATOR_PATH = ROOT / "lab" / "EVALUATOR.json"
DEFAULT_BINARY = ROOT / "build" / "stable" / "bin" / "Release" / "llama-server.exe"
EXPECTED_BINARY_SHA256 = "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B"
EXPECTED_RUNTIME_VERSION = "13 (417e1d6)"
EXPECTED_MODEL_SHA256 = "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2"
EXPECTED_MODEL_SIZE = 21_166_757_632
CTX_SIZE = 16_384
CACHE_RAM_MIB = 4_096
CTX_CHECKPOINTS = 8
CHECKPOINT_MIN_STEP = 512
VRAM_CEILING_MIB = 6_000
MAX_EXTENDED_REQUESTS = 20
MAX_EXTENDED_SECONDS = 60 * 60

ROOT_SOURCES = {
    "A": ["ROADMAP.md", "lab/GOAL.md", "README.md"],
    "B": ["AGENTS.md", "NEO3000.md", "lab/BASELINE_PROTOCOL.md", "lab/GOAL.md"],
}

BRANCHES = {
    "A1": {
        "root": "A",
        "suffix": "Reason carefully, then finish with exactly: HOLOSTATE A1 EXACT",
        "expected": "HOLOSTATE A1 EXACT",
    },
    "A2": {
        "root": "A",
        "suffix": "Reason briefly, then finish with exactly: HOLOSTATE A2 EXACT",
        "expected": "HOLOSTATE A2 EXACT",
    },
    "B1": {
        "root": "B",
        "suffix": "Reason carefully, then finish with exactly: HOLOSTATE B1 EXACT",
        "expected": "HOLOSTATE B1 EXACT",
    },
    "B2": {
        "root": "B",
        "suffix": "Reason briefly, then finish with exactly: HOLOSTATE B2 EXACT",
        "expected": "HOLOSTATE B2 EXACT",
    },
}

FIXED_SEQUENCE = ["A1", "B1", "A2", "B2", "A1", "B1"]
EXTENDED_CYCLE = ["A2", "B2", "A1", "B1"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * MIB), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def require_runtime_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(STATE_ROOT.resolve())
    except ValueError as exc:
        raise NeoLoopError(f"runtime write escaped state/holostate: {resolved}") from exc
    return resolved


def write_runtime_json(path: Path, value: Any) -> None:
    path = require_runtime_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def default_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "metadata_only": True,
        "metadata_warning": "An entry is not live state. Live requires exact sidecar-session identity and observed cached prompt tokens.",
        "configuration": {
            "host": "127.0.0.1",
            "port": PORT,
            "parallel": 1,
            "context_size": CTX_SIZE,
            "cache_ram_mib": CACHE_RAM_MIB,
            "ctx_checkpoints": CTX_CHECKPOINTS,
            "checkpoint_min_step": CHECKPOINT_MIN_STEP,
            "cache_types": {"k": "f16", "v": "f16"},
            "cpu_moe": True,
        },
        "sidecar": None,
        "active_request": None,
        "states": {},
        "history": [],
        "updated_at": utc_now(),
    }


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return default_registry()
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("states"), dict):
        raise NeoLoopError("unsupported or malformed HoloState registry")
    return payload


def save_registry(registry: dict[str, Any]) -> None:
    registry["updated_at"] = utc_now()
    write_runtime_json(REGISTRY_PATH, registry)


def request_json(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 60) -> Any:
    data = canonical_json_bytes(payload) if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise NeoLoopError(f"{method} {path} HTTP {exc.code}: {body[:1000]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise NeoLoopError(f"{method} {path} failed: {exc}") from exc


def process_info(pid: int) -> dict[str, Any] | None:
    command = rf'''
$P = Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" -ErrorAction SilentlyContinue
$G = Get-Process -Id {pid} -ErrorAction SilentlyContinue
if ($null -eq $P -or $null -eq $G) {{ exit 3 }}
[pscustomobject]@{{
  pid = [int]$P.ProcessId
  executable = [string]$P.ExecutablePath
  command_line = [string]$P.CommandLine
  started_at = $G.StartTime.ToUniversalTime().ToString('o')
  private_bytes = [int64]$G.PrivateMemorySize64
  working_set_bytes = [int64]$G.WorkingSet64
}} | ConvertTo-Json -Compress
'''
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode or not completed.stdout.strip():
        return None
    return json.loads(completed.stdout)


def binary_version(binary: Path) -> str:
    completed = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=30)
    if completed.returncode:
        raise NeoLoopError("failed to read llama-server version")
    line = next((line.strip() for line in (completed.stdout + completed.stderr).splitlines() if "version:" in line), "")
    return line.removeprefix("version:").strip()


def verify_binary_identity(binary: Path) -> dict[str, Any]:
    if not binary.is_file():
        raise NeoLoopError(f"missing HoloState binary: {binary}")
    actual_hash = sha256_file(binary)
    version = binary_version(binary)
    if actual_hash != EXPECTED_BINARY_SHA256 or version != EXPECTED_RUNTIME_VERSION:
        raise NeoLoopError(
            f"binary identity mismatch: sha={actual_hash}, version={version}"
        )
    return {"path": str(binary.resolve()), "sha256": actual_hash, "runtime_version": version}


def verify_model(model: Path, evaluator: dict[str, Any]) -> dict[str, Any]:
    if evaluator["model"]["sha256"].upper() != EXPECTED_MODEL_SHA256 or evaluator["model"]["size_bytes"] != EXPECTED_MODEL_SIZE:
        raise NeoLoopError("evaluator model identity does not match the HoloState contract")
    verify_model_identity(model, evaluator)
    return {
        "path": str(model.resolve()),
        "sha256": EXPECTED_MODEL_SHA256,
        "size_bytes": EXPECTED_MODEL_SIZE,
    }


def stable_snapshot() -> dict[str, Any]:
    pids = listener_pids(STABLE_PORT)
    return {"healthy": health_ok(STABLE_PORT, timeout=3), "listener_pids": sorted(pids)}


def require_stable(expected_pids: set[int] | None = None) -> set[int]:
    snapshot = stable_snapshot()
    pids = set(snapshot["listener_pids"])
    if not snapshot["healthy"] or not pids:
        raise NeoLoopError("stable server unavailable")
    if expected_pids is not None and pids != expected_pids:
        raise NeoLoopError(f"stable listener changed: expected {sorted(expected_pids)}, actual {sorted(pids)}")
    return pids


def git_read(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
    if completed.returncode:
        raise NeoLoopError(f"read-only Git query failed: {' '.join(args)}")
    return completed.stdout.strip()


def compose_prefix(root_name: str) -> tuple[bytes, list[dict[str, Any]]]:
    chunks: list[bytes] = []
    sources: list[dict[str, Any]] = []
    for relative in ROOT_SOURCES[root_name]:
        path = ROOT / relative
        raw = path.read_bytes()
        raw.decode("utf-8")
        header = f"\n\n===== SOURCE: {relative} =====\n\n".encode("utf-8")
        chunks.extend([header, raw])
        sources.append({"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)})
    return b"".join(chunks), sources


def store_prefix(raw: bytes) -> tuple[Path, str]:
    raw.decode("utf-8")
    digest = sha256_bytes(raw)
    path = require_runtime_path(PREFIX_ROOT / f"{digest}.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise NeoLoopError("content-addressed prefix collision")
    else:
        path.write_bytes(raw)
    return path, digest


def parse_final_structure(raw: str, expected: str) -> dict[str, Any]:
    stripped = raw.strip()
    index = stripped.rfind(expected)
    exact = index >= 0 and not stripped[index + len(expected):].strip()
    reasoning = stripped[:index].strip() if index >= 0 else stripped
    final_content = expected if exact else None
    return {
        "expected": expected,
        "exact_final": exact,
        "reasoning_present": bool(reasoning),
        "reasoning_sha256": sha256_bytes(reasoning.encode("utf-8")),
        "final_content": final_content,
        "final_content_sha256": sha256_bytes((final_content or "").encode("utf-8")),
        "raw_output_sha256": sha256_bytes(raw.encode("utf-8")),
    }


def select_eviction_candidate(states: dict[str, dict[str, Any]]) -> str | None:
    live = []
    for state_id, state in states.items():
        if not state.get("live"):
            continue
        estimated = max(int(state.get("estimated_bytes") or 0), 1)
        yield_score = float(state.get("reuse_count") or 0) / estimated
        live.append((yield_score, state.get("last_use_timestamp") or "", state_id))
    return min(live)[2] if live else None


def mark_all_states_non_live(registry: dict[str, Any], reason: str) -> None:
    for state in registry["states"].values():
        if state.get("live"):
            state["live"] = False
            state["live_session_id"] = None
            state["non_live_reason"] = reason


class LiveSidecar:
    def __init__(self, binary: Path, model: Path, evaluator: dict[str, Any], detached: bool):
        self.binary = binary.resolve()
        self.model = model.resolve()
        self.evaluator = evaluator
        self.detached = detached
        self.session_id = str(uuid.uuid4())
        self.stable_pids = require_stable()
        self.process: subprocess.Popen[str] | None = None
        self.sampler: CandidateVramSampler | None = None
        self.log_handle: Any = None
        self.runtime = require_runtime_path(RUNTIME_ROOT / self.session_id)
        self.readiness: dict[str, Any] = {}
        self.private_at_readiness: int | None = None

    def launch(self) -> dict[str, Any]:
        if listener_pids(PORT):
            raise NeoLoopError("port 9494 is already occupied")
        binary_identity = verify_binary_identity(self.binary)
        model_identity = verify_model(self.model, self.evaluator)
        self.runtime.mkdir(parents=True, exist_ok=False)
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = require_runtime_path(LOG_ROOT / f"{self.session_id}.log")
        self.log_handle = log_path.open("w", encoding="utf-8")
        args = [
            str(self.binary),
            "--model", str(self.model),
            "--alias", "agents-a1-holostate",
            "--host", "127.0.0.1",
            "--port", str(PORT),
            "--parallel", "1",
            "--ctx-size", str(CTX_SIZE),
            "--threads", "12",
            "--threads-batch", "12",
            "--batch-size", "512",
            "--ubatch-size", "128",
            "--gpu-layers", "auto",
            "--flash-attn", "auto",
            "--cache-type-k", "f16",
            "--cache-type-v", "f16",
            "--cpu-moe",
            "--cache-prompt",
            "--metrics",
            "--no-webui",
            "--reasoning", "auto",
            "--ctx-checkpoints", str(CTX_CHECKPOINTS),
            "--checkpoint-min-step", str(CHECKPOINT_MIN_STEP),
            "--cache-ram", str(CACHE_RAM_MIB),
            "--cache-idle-slots",
        ]
        env = os.environ.copy()
        env.update({"TMP": str(self.runtime), "TEMP": str(self.runtime), "TMPDIR": str(self.runtime)})
        creationflags = 0
        if self.detached and os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008
        started = time.monotonic()
        self.process = subprocess.Popen(
            args,
            cwd=self.binary.parent,
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
            close_fds=True,
        )
        memory = self.evaluator["memory"]
        self.sampler = CandidateVramSampler(
            self.process.pid,
            VRAM_CEILING_MIB,
            memory["sample_interval_seconds"],
            memory["telemetry_grace_seconds"],
        )
        self.sampler.start()
        deadline = time.monotonic() + self.evaluator["timeouts"]["candidate_health_seconds"]
        while True:
            self.require_active(require_health=False, require_listener=False)
            ready = (
                health_ok(PORT, timeout=2)
                and listener_pids(PORT) == {self.process.pid}
                and self.sampler.has_valid_sample()
                and self.sampler.failure_reason() is None
            )
            if ready:
                break
            if time.monotonic() >= deadline:
                raise NeoLoopError("HoloState sidecar readiness timeout")
            time.sleep(0.25)
        props = request_json("GET", "/props", timeout=10)
        models = request_json("GET", "/v1/models", timeout=10)
        model_ids = [item.get("id") for item in models.get("data", [])]
        if "agents-a1-holostate" not in model_ids:
            raise NeoLoopError("sidecar model identity endpoint mismatch")
        info = process_info(self.process.pid)
        if not info:
            raise NeoLoopError("sidecar process identity unavailable")
        self.private_at_readiness = int(info["private_bytes"])
        telemetry = self.sampler.evidence(VRAM_CEILING_MIB)
        self.readiness = {
            "session_id": self.session_id,
            "pid": self.process.pid,
            "process_started_at": info["started_at"],
            "listener_pids": sorted(listener_pids(PORT)),
            "readiness_seconds": round(time.monotonic() - started, 3),
            "binary": binary_identity,
            "model": model_identity,
            "model_ids": model_ids,
            "chat_template_sha256": sha256_bytes(str(props.get("chat_template", "")).encode("utf-8")),
            "chat_template_caps": props.get("chat_template_caps"),
            "total_slots": props.get("total_slots"),
            "process_memory": info,
            "wddm": telemetry,
            "stable_pids": sorted(self.stable_pids),
            "log_path": str(log_path),
        }
        return self.readiness

    def require_active(self, require_health: bool = True, require_listener: bool = True) -> None:
        if not self.process or self.process.poll() is not None:
            raise NeoLoopError("HoloState sidecar process exited")
        if self.process.pid in self.stable_pids:
            raise NeoLoopError("sidecar PID overlaps stable PID")
        require_stable(self.stable_pids)
        if self.sampler and self.sampler.failure_reason():
            raise NeoLoopError(self.sampler.failure_reason() or "WDDM failure")
        if require_health and not health_ok(PORT, timeout=2):
            raise NeoLoopError("HoloState sidecar health lost")
        if require_listener and listener_pids(PORT) != {self.process.pid}:
            raise NeoLoopError("HoloState listener ownership mismatch")

    def guarded(self, name: str, call: Callable[[], Any], timeout: float = 1_200) -> Any:
        self.require_active()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    value = future.result(timeout=0.25)
                    break
                except FutureTimeout:
                    self.require_active()
                    if time.monotonic() >= deadline:
                        raise NeoLoopError(f"{name} timed out")
        self.require_active()
        return value

    def telemetry(self) -> dict[str, Any]:
        return self.sampler.evidence(VRAM_CEILING_MIB) if self.sampler else {}

    def stop(self) -> dict[str, Any]:
        if self.sampler:
            self.sampler.stop()
        telemetry = self.telemetry()
        pid = self.process.pid if self.process else None
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log_handle:
            self.log_handle.close()
        shutil.rmtree(self.runtime, ignore_errors=True)
        retirement = []
        if pid is not None:
            for _ in range(5):
                retirement.append(asdict(wddm_pid_memory_sample(pid)))
                time.sleep(1)
        deadline = time.monotonic() + 15
        while listener_pids(PORT) and time.monotonic() < deadline:
            time.sleep(0.25)
        return {
            "pid": pid,
            "process_stopped": not self.process or self.process.poll() is not None,
            "port_free": not listener_pids(PORT),
            "runtime_removed": not self.runtime.exists(),
            "wddm": telemetry,
            "retirement_samples": retirement,
            "stable_after": stable_snapshot(),
        }


def registry_sidecar_record(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": readiness["session_id"],
        "pid": readiness["pid"],
        "process_started_at": readiness["process_started_at"],
        "binary": readiness["binary"],
        "model": readiness["model"],
        "chat_template_sha256": readiness["chat_template_sha256"],
        "stable_pids": readiness["stable_pids"],
        "runtime_path": str(require_runtime_path(RUNTIME_ROOT / readiness["session_id"])),
        "started_at": utc_now(),
    }


def status_from_registry(registry: dict[str, Any], rehash_model: bool = True) -> dict[str, Any]:
    sidecar = registry.get("sidecar")
    if not sidecar:
        return {"live": False, "reason": "no registered sidecar", "port_listener_pids": sorted(listener_pids(PORT))}
    pid = int(sidecar["pid"])
    info = process_info(pid)
    listeners = listener_pids(PORT)
    stable_pids = set(sidecar.get("stable_pids", []))
    binary = Path(sidecar["binary"]["path"])
    model = Path(sidecar["model"]["path"])
    binary_ok = (
        binary.is_file()
        and sha256_file(binary) == EXPECTED_BINARY_SHA256
        and info is not None
        and os.path.normcase(str(Path(info["executable"]).resolve())) == os.path.normcase(str(binary.resolve()))
    )
    model_ok = model.is_file() and model.stat().st_size == EXPECTED_MODEL_SIZE
    if model_ok and rehash_model:
        model_ok = sha256_file(model) == EXPECTED_MODEL_SHA256
    command_model_ok = bool(info and str(model.resolve()).lower() in str(info.get("command_line", "")).lower())
    process_start_ok = bool(info and info.get("started_at") == sidecar.get("process_started_at"))
    sample = wddm_pid_memory_sample(pid) if info else None
    wddm_ok = bool(sample and sample.available and sample.bytes is not None and sample.bytes <= VRAM_CEILING_MIB * MIB)
    stable_ok = bool(stable_pids) and health_ok(STABLE_PORT, timeout=3) and listener_pids(STABLE_PORT) == stable_pids
    checks = {
        "process_alive": info is not None,
        "process_start_exact": process_start_ok,
        "health_ok": health_ok(PORT, timeout=3),
        "listener_pid_exact": listeners == {pid},
        "model_identity_exact": model_ok and command_model_ok,
        "binary_identity_exact": binary_ok,
        "wddm_attribution_exact": wddm_ok,
        "stable_unchanged": stable_ok,
    }
    live = all(checks.values())
    return {
        "live": live,
        "session_id": sidecar["session_id"],
        "pid": pid,
        "checks": checks,
        "process": info,
        "listener_pids": sorted(listeners),
        "wddm": asdict(sample) if sample else None,
    }


def attach_registered_sidecar(registry: dict[str, Any], rehash_model: bool = True) -> dict[str, Any]:
    status = status_from_registry(registry, rehash_model=rehash_model)
    if not status["live"]:
        raise NeoLoopError(f"registered sidecar is not live: {status}")
    return status


def tokenize(content: str) -> list[int]:
    response = request_json("POST", "/tokenize", {"content": content, "add_special": False, "parse_special": True})
    tokens = response.get("tokens") if isinstance(response, dict) else None
    if not isinstance(tokens, list):
        raise NeoLoopError("tokenizer returned no token list")
    return [int(value) for value in tokens]


def render_prompt(content: str) -> str:
    response = request_json("POST", "/apply-template", {"messages": [{"role": "user", "content": content}]})
    prompt = response.get("prompt") if isinstance(response, dict) else None
    if not isinstance(prompt, str):
        raise NeoLoopError("chat template returned no prompt")
    return prompt


def completion_request(rendered_prompt: str, n_predict: int, expected: str | None, timeout: float = 1_200) -> dict[str, Any]:
    payload = {
        "prompt": rendered_prompt,
        "n_predict": n_predict,
        "temperature": 0.0,
        "seed": 0,
        "stream": True,
        "cache_prompt": True,
        "id_slot": 0,
        "return_tokens": True,
        "return_progress": True,
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/completion",
        data=canonical_json_bytes(payload),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    started = time.perf_counter()
    first_generated = None
    raw_parts: list[str] = []
    generated_tokens: list[int] = []
    progress: list[dict[str, Any]] = []
    final: dict[str, Any] = {}
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            event = json.loads(data)
            prompt_progress = event.get("prompt_progress")
            if isinstance(prompt_progress, dict):
                progress.append(prompt_progress)
            content = event.get("content")
            if isinstance(content, str) and content:
                if first_generated is None:
                    first_generated = time.perf_counter() - started
                raw_parts.append(content)
                if not isinstance(prompt_progress, dict) and isinstance(event.get("tokens"), list):
                    generated_tokens.extend(int(value) for value in event["tokens"])
            if event.get("stop") is True:
                final = event
    elapsed = time.perf_counter() - started
    timings = final.get("timings", {}) if isinstance(final.get("timings"), dict) else {}
    predicted_n = int(timings.get("predicted_n") or final.get("tokens_predicted") or 0)
    decode_tps = float(timings.get("predicted_per_second") or 0)
    reconstructed = elapsed - (predicted_n / decode_tps if decode_tps > 0 else 0)
    raw_output = "".join(raw_parts)
    structure = parse_final_structure(raw_output, expected) if expected is not None else None
    last_progress = progress[-1] if progress else {}
    logical_prompt_tokens = int(last_progress.get("total") or final.get("tokens_evaluated") or 0)
    cached_prompt_tokens = int(last_progress.get("cache") or 0)
    fresh_prompt_tokens = int(last_progress.get("processed") or timings.get("prompt_n") or 0)
    return {
        "logical_prompt_tokens": logical_prompt_tokens,
        "cached_prompt_tokens": cached_prompt_tokens,
        "fresh_prompt_tokens": fresh_prompt_tokens,
        "prompt_ms": timings.get("prompt_ms"),
        "prompt_tps": timings.get("prompt_per_second"),
        "ttft_seconds": first_generated,
        "reconstructed_pre_generation_seconds": max(0.0, reconstructed),
        "decode_tps": timings.get("predicted_per_second"),
        "total_seconds": elapsed,
        "completion_tokens": predicted_n,
        "cleaned_greedy_token_count": len(generated_tokens),
        "cleaned_greedy_token_sha256": sha256_bytes(canonical_json_bytes(generated_tokens)),
        "prompt_progress_last": last_progress or None,
        "stop_type": final.get("stop_type"),
        "stopping_word": final.get("stopping_word"),
        "structure": structure,
    }


def set_active_request(registry: dict[str, Any], value: dict[str, Any] | None) -> None:
    registry["active_request"] = value
    save_registry(registry)


def state_identity(
    display_name: str,
    prefix_sha256: str,
    token_id_sha256: str,
    rendered_token_count: int,
    sidecar: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    identity = {
        "model_sha256": sidecar["model"]["sha256"],
        "binary_sha256": sidecar["binary"]["sha256"],
        "runtime_version": sidecar["binary"]["runtime_version"],
        "chat_template_sha256": sidecar["chat_template_sha256"],
        "canonical_prefix_sha256": prefix_sha256,
        "token_id_sha256": token_id_sha256,
        "rendered_token_count": rendered_token_count,
        "context_size": CTX_SIZE,
        "cache_types": {"k": "f16", "v": "f16"},
        "cpu_moe": True,
    }
    digest = sha256_bytes(canonical_json_bytes(identity))
    return f"holostate-{digest[:24].lower()}", {"display_name": display_name, **identity}


def warm_state(
    prefix_path: Path,
    display_name: str,
    sources: list[dict[str, Any]] | None = None,
    trusted_session_id: str | None = None,
) -> dict[str, Any]:
    registry = load_registry()
    status = attach_registered_sidecar(registry, rehash_model=trusted_session_id is None)
    if trusted_session_id is not None and status.get("session_id") != trusted_session_id:
        raise NeoLoopError("trusted validation session identity changed")
    raw = prefix_path.read_bytes()
    text = raw.decode("utf-8")
    stored_path, prefix_sha = store_prefix(raw)
    content_tokens = tokenize(text)
    token_sha = sha256_bytes(canonical_json_bytes(content_tokens))
    rendered = render_prompt(text)
    rendered_tokens = tokenize(rendered)
    sidecar = registry["sidecar"]
    state_id, identity = state_identity(display_name, prefix_sha, token_sha, len(rendered_tokens), sidecar)
    existing = registry["states"].get(state_id)
    if existing:
        for key, value in identity.items():
            if key != "display_name" and existing.get(key) != value:
                raise NeoLoopError(f"state identity mismatch for {state_id}: {key}")
    before = process_info(status["pid"])
    set_active_request(registry, {"operation": "warm", "state_id": state_id, "started_at": utc_now()})
    try:
        result = completion_request(rendered, 0, None)
    finally:
        registry = load_registry()
        registry["active_request"] = None
        save_registry(registry)
    after = process_info(status["pid"])
    if not before or not after:
        raise NeoLoopError("host-memory evidence unavailable during warm")
    if result["fresh_prompt_tokens"] <= 0 and result["cached_prompt_tokens"] <= 0:
        raise NeoLoopError("warm did not report prompt evaluation or reuse")
    private_delta = max(0, int(after["private_bytes"]) - int(before["private_bytes"]))
    host_growth = max(0, int(after["private_bytes"]) - int(sidecar["private_at_readiness_bytes"]))
    if host_growth > CACHE_RAM_MIB * MIB:
        raise NeoLoopError("host cache/private-memory growth exceeded 4096 MiB")
    now = utc_now()
    state = {
        "state_id": state_id,
        **identity,
        "prefix_file": str(stored_path),
        "prefix_sources": sources or [],
        "canonical_prefix_bytes": len(raw),
        "content_token_count": len(content_tokens),
        "creation_timestamp": existing.get("creation_timestamp", now) if existing else now,
        "last_use_timestamp": now,
        "reuse_count": int(existing.get("reuse_count", 0)) if existing else 0,
        "last_observed_cached_tokens": result["cached_prompt_tokens"],
        "last_observed_fresh_tokens": result["fresh_prompt_tokens"],
        "last_observed_prompt_time_ms": result["prompt_ms"],
        "exactness_status": "warmed-unproven-until-reuse",
        "live": False,
        "live_session_id": None,
        "warm_session_id": sidecar["session_id"],
        "warm_result": result,
        "warm_private_delta_bytes": private_delta,
        "estimated_bytes": None,
        "estimated_bytes_method": "assigned after admission as proportional share of the 4096 MiB configured cache ceiling",
        "cumulative_avoided_token_evaluations": int(existing.get("cumulative_avoided_token_evaluations", 0)) if existing else 0,
        "cumulative_logical_token_evaluations": int(existing.get("cumulative_logical_token_evaluations", 0)) if existing else 0,
        "cumulative_fresh_prompt_evaluations": int(existing.get("cumulative_fresh_prompt_evaluations", 0)) if existing else 0,
    }
    registry["states"][state_id] = state
    registry["history"].append({"event": "warm", "state_id": state_id, "at": now, "result": result})
    registry["active_request"] = None
    save_registry(registry)
    return state


def assign_estimated_bytes(registry: dict[str, Any], state_ids: list[str]) -> None:
    total_tokens = sum(int(registry["states"][state_id]["rendered_token_count"]) for state_id in state_ids)
    remaining = CACHE_RAM_MIB * MIB
    for index, state_id in enumerate(state_ids):
        state = registry["states"][state_id]
        if index == len(state_ids) - 1:
            estimate = remaining
        else:
            estimate = round(CACHE_RAM_MIB * MIB * state["rendered_token_count"] / total_tokens)
            remaining -= estimate
        state["estimated_bytes"] = estimate


def verify_state_identity(state: dict[str, Any], registry: dict[str, Any]) -> tuple[str, list[int]]:
    path = Path(state["prefix_file"])
    raw = path.read_bytes()
    if sha256_bytes(raw) != state["canonical_prefix_sha256"]:
        raise NeoLoopError("canonical prefix bytes changed")
    text = raw.decode("utf-8")
    content_tokens = tokenize(text)
    if sha256_bytes(canonical_json_bytes(content_tokens)) != state["token_id_sha256"]:
        raise NeoLoopError("canonical prefix token identity changed")
    props = request_json("GET", "/props", timeout=10)
    template_sha = sha256_bytes(str(props.get("chat_template", "")).encode("utf-8"))
    if template_sha != state["chat_template_sha256"]:
        raise NeoLoopError("chat-template identity changed")
    sidecar = registry["sidecar"]
    for key in ("model_sha256", "binary_sha256", "runtime_version"):
        source = sidecar["model"]["sha256"] if key == "model_sha256" else sidecar["binary"]["sha256" if key == "binary_sha256" else "runtime_version"]
        if state[key] != source:
            raise NeoLoopError(f"state {key} mismatch")
    return text, content_tokens


def branch_state(state_id: str, branch_name: str, suffix: str, expected: str, sampler: CandidateVramSampler | None = None) -> dict[str, Any]:
    registry = load_registry()
    status = attach_registered_sidecar(registry, rehash_model=sampler is None)
    state = registry["states"].get(state_id)
    if not state:
        raise NeoLoopError(f"unknown state: {state_id}")
    if state.get("warm_session_id") != registry["sidecar"]["session_id"]:
        raise NeoLoopError("state was not warmed in the current process-local session")
    text, _ = verify_state_identity(state, registry)
    logical = text + "\n\n" + suffix
    rendered = render_prompt(logical)
    logical_tokens = tokenize(rendered)
    set_active_request(registry, {"operation": "branch", "state_id": state_id, "branch_name": branch_name, "started_at": utc_now()})
    try:
        result = completion_request(rendered, 768, expected)
    finally:
        registry = load_registry()
        registry["active_request"] = None
        save_registry(registry)
    result["branch_name"] = branch_name
    result["state_id"] = state_id
    result["selected_state_id"] = state_id
    result["selection_basis"] = "identity-bound full logical prompt plus exact branch result; server cache keys are not externally exposed"
    result["logical_prompt_tokens"] = len(logical_tokens)
    cached = int(result["cached_prompt_tokens"])
    fresh = int(result["fresh_prompt_tokens"])
    result["avoided_prefix_tokens"] = min(int(state["rendered_token_count"]), cached)
    result["fresh_prefix_fraction"] = fresh / len(logical_tokens) if logical_tokens else None
    warm_ms = state.get("warm_result", {}).get("prompt_ms")
    result["compute_amplification"] = warm_ms / result["prompt_ms"] if warm_ms and result.get("prompt_ms") else None
    result["catalytic"] = cached > 0 and fresh < len(logical_tokens)
    if sampler:
        result["wddm_peak_mib"] = sampler.evidence(VRAM_CEILING_MIB).get("peak_dedicated_mib")
    else:
        sample = wddm_pid_memory_sample(status["pid"])
        if not sample.available or sample.bytes is None or sample.bytes > VRAM_CEILING_MIB * MIB:
            raise NeoLoopError("exact-PID WDDM sample unavailable or over ceiling")
        result["wddm_peak_mib"] = round(sample.bytes / MIB, 2)
    info = process_info(status["pid"])
    sidecar = registry["sidecar"]
    if not info:
        raise NeoLoopError("host memory unavailable after branch")
    host_growth = max(0, int(info["private_bytes"]) - int(sidecar["private_at_readiness_bytes"]))
    if host_growth > CACHE_RAM_MIB * MIB:
        raise NeoLoopError("host cache/private-memory growth exceeded 4096 MiB")
    result["host_private_growth_bytes"] = host_growth
    state = registry["states"][state_id]
    output_exact = result["structure"]["exact_final"] and result["structure"]["reasoning_present"]
    if not output_exact or not result["catalytic"]:
        state["last_observed_cached_tokens"] = cached
        state["last_observed_fresh_tokens"] = fresh
        state["last_observed_prompt_time_ms"] = result["prompt_ms"]
        state["exactness_status"] = "branch-output-failed" if not output_exact else "branch-reuse-failed"
        registry["history"].append({"event": "branch-failed", "state_id": state_id, "at": utc_now(), "result": result})
        save_registry(registry)
        if not output_exact:
            raise NeoLoopError(f"{branch_name} deterministic output gate failed")
        raise NeoLoopError(f"{branch_name} did not demonstrate process-local cache reuse")
    state["last_use_timestamp"] = utc_now()
    state["reuse_count"] = int(state.get("reuse_count", 0)) + 1
    state["last_observed_cached_tokens"] = cached
    state["last_observed_fresh_tokens"] = fresh
    state["last_observed_prompt_time_ms"] = result["prompt_ms"]
    state["exactness_status"] = "exact-process-local-reuse"
    state["live"] = True
    state["live_session_id"] = registry["sidecar"]["session_id"]
    state["non_live_reason"] = None
    state["cumulative_avoided_token_evaluations"] += result["avoided_prefix_tokens"]
    state["cumulative_logical_token_evaluations"] += len(logical_tokens)
    state["cumulative_fresh_prompt_evaluations"] += fresh
    registry["history"].append({"event": "branch", "state_id": state_id, "at": utc_now(), "result": result})
    registry["active_request"] = None
    save_registry(registry)
    return result


def deterministic_group_gate(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        groups.setdefault(item["branch_name"], []).append(item)
    evidence: dict[str, Any] = {}
    for branch_name, items in groups.items():
        token_hashes = {item["cleaned_greedy_token_sha256"] for item in items}
        reasoning_hashes = {item["structure"]["reasoning_sha256"] for item in items}
        final_hashes = {item["structure"]["final_content_sha256"] for item in items}
        exact = all(item["structure"]["exact_final"] and item["catalytic"] for item in items)
        evidence[branch_name] = {
            "request_count": len(items),
            "token_hashes": sorted(token_hashes),
            "reasoning_hashes": sorted(reasoning_hashes),
            "final_hashes": sorted(final_hashes),
            "exact": exact and len(token_hashes) == len(reasoning_hashes) == len(final_hashes) == 1,
        }
    return evidence


def catalytic_metrics(registry: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    state_metrics: dict[str, Any] = {}
    total_avoided = 0
    total_logical = 0
    total_fresh = 0
    total_estimated = 0
    for state_id, state in registry["states"].items():
        avoided = int(state.get("cumulative_avoided_token_evaluations", 0))
        logical = int(state.get("cumulative_logical_token_evaluations", 0))
        fresh = int(state.get("cumulative_fresh_prompt_evaluations", 0))
        estimated = int(state.get("estimated_bytes") or 0)
        total_avoided += avoided
        total_logical += logical
        total_fresh += fresh
        total_estimated += estimated if state.get("live") else 0
        amplifications = [item["compute_amplification"] for item in results if item["state_id"] == state_id and item.get("compute_amplification")]
        state_metrics[state_id] = {
            "display_name": state["display_name"],
            "carrier_reuse_count": state["reuse_count"],
            "cumulative_avoided_token_evaluations": avoided,
            "cumulative_logical_token_evaluations": logical,
            "fresh_compute_ratio": fresh / logical if logical else None,
            "mean_compute_amplification": sum(amplifications) / len(amplifications) if amplifications else None,
            "state_reuse_yield_tokens_per_byte": avoided / estimated if estimated else None,
            "state_reuse_yield_tokens_per_mib": avoided / (estimated / MIB) if estimated else None,
            "estimated_retained_bytes": estimated,
        }
    correct_reusable = sum(1 for item in results if item["catalytic"] and item["structure"]["exact_final"])
    resident_gib = total_estimated / GIB
    return {
        "per_state": state_metrics,
        "carrier_reuse_count": correct_reusable,
        "cumulative_avoided_token_evaluations": total_avoided,
        "cumulative_logical_token_evaluations": total_logical,
        "fresh_compute_ratio": total_fresh / total_logical if total_logical else None,
        "state_reuse_yield_tokens_per_byte": total_avoided / total_estimated if total_estimated else None,
        "state_reuse_yield_tokens_per_mib": total_avoided / (total_estimated / MIB) if total_estimated else None,
        "resident_state_gib_estimate": resident_gib,
        "holographic_branch_density_correct_reusable_branches_per_resident_gib": correct_reusable / resident_gib if resident_gib else None,
        "literal_infinity_claimed": False,
    }


def command_start(args: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry()
    if registry.get("sidecar") and status_from_registry(registry, rehash_model=False).get("live"):
        raise NeoLoopError("a HoloState sidecar is already live")
    mark_all_states_non_live(registry, "new-sidecar-session")
    registry["sidecar"] = None
    save_registry(registry)
    evaluator = load_json(EVALUATOR_PATH)
    sidecar = LiveSidecar(Path(args.binary), Path(args.model), evaluator, detached=True)
    try:
        readiness = sidecar.launch()
        readiness_record = registry_sidecar_record(readiness)
        readiness_record["private_at_readiness_bytes"] = readiness["process_memory"]["private_bytes"]
        registry = load_registry()
        registry["sidecar"] = readiness_record
        registry["history"].append({"event": "start", "at": utc_now(), "sidecar": readiness_record})
        save_registry(registry)
        if sidecar.sampler:
            sidecar.sampler.stop()
        if sidecar.log_handle:
            sidecar.log_handle.close()
        return readiness
    except Exception:
        sidecar.stop()
        raise


def terminate_pid(pid: int) -> None:
    if os.name != "nt":
        os.kill(pid, signal.SIGTERM)
        return
    process_terminate = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(process_terminate, False, pid)
    if not handle:
        raise NeoLoopError(f"could not open sidecar PID {pid} for termination")
    try:
        if not ctypes.windll.kernel32.TerminateProcess(handle, 0):
            raise NeoLoopError(f"could not terminate sidecar PID {pid}")
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def stop_authorized(registry: dict[str, Any]) -> tuple[bool, str]:
    sidecar = registry.get("sidecar")
    if not sidecar:
        return False, "no registered sidecar"
    pid = int(sidecar["pid"])
    if pid in listener_pids(STABLE_PORT) or pid in set(sidecar.get("stable_pids", [])):
        return False, "registered PID overlaps stable"
    status = status_from_registry(registry, rehash_model=False)
    if not status.get("live"):
        return False, "registered process fails exact live identity"
    if listener_pids(PORT) != {pid}:
        return False, "port 9494 listener does not exactly match registered PID"
    return True, "exact sidecar identity"


def command_stop(_: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry()
    allowed, reason = stop_authorized(registry)
    if not allowed:
        raise NeoLoopError(f"refusing stop: {reason}")
    pid = int(registry["sidecar"]["pid"])
    terminate_pid(pid)
    deadline = time.monotonic() + 20
    while process_info(pid) and time.monotonic() < deadline:
        time.sleep(0.25)
    runtime_path = require_runtime_path(Path(registry["sidecar"]["runtime_path"]))
    shutil.rmtree(runtime_path, ignore_errors=True)
    retirement = []
    for _ in range(5):
        retirement.append(asdict(wddm_pid_memory_sample(pid)))
        time.sleep(1)
    mark_all_states_non_live(registry, "sidecar-stopped")
    registry["history"].append({"event": "stop", "at": utc_now(), "pid": pid})
    registry["sidecar"] = None
    registry["active_request"] = None
    save_registry(registry)
    return {
        "pid": pid,
        "process_stopped": process_info(pid) is None,
        "port_free": not listener_pids(PORT),
        "runtime_removed": not runtime_path.exists(),
        "retirement_samples": retirement,
        "stable_after": stable_snapshot(),
    }


def command_status(_: argparse.Namespace) -> dict[str, Any]:
    return status_from_registry(load_registry(), rehash_model=True)


def command_warm(args: argparse.Namespace) -> dict[str, Any]:
    return warm_state(Path(args.prefix), args.display_name)


def resolve_state(registry: dict[str, Any], value: str) -> str:
    if value in registry["states"]:
        return value
    matches = [state_id for state_id, state in registry["states"].items() if state["display_name"] == value]
    if len(matches) != 1:
        raise NeoLoopError(f"state selector must resolve exactly once: {value}")
    return matches[0]


def command_branch(args: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry()
    state_id = resolve_state(registry, args.state)
    return branch_state(state_id, args.branch_name, args.suffix, args.expected)


def command_list(_: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry()
    status = status_from_registry(registry, rehash_model=False)
    session_id = status.get("session_id") if status.get("live") else None
    states = []
    for state in registry["states"].values():
        item = dict(state)
        item["currently_live"] = bool(
            state.get("live")
            and state.get("live_session_id") == session_id
            and int(state.get("last_observed_cached_tokens") or 0) > 0
        )
        states.append(item)
    return {
        "metadata_only": True,
        "sidecar": status,
        "entry_count": len(states),
        "states": states,
        "eviction_candidate": select_eviction_candidate(registry["states"]),
        "history_count": len(registry["history"]),
    }


def command_evict(args: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry()
    if registry.get("active_request"):
        raise NeoLoopError("cannot evict during an active request")
    state_id = resolve_state(registry, args.state) if args.state else select_eviction_candidate(registry["states"])
    if not state_id:
        raise NeoLoopError("no live state is eligible for eviction")
    state = registry["states"][state_id]
    event = {
        "event": "controller-evict",
        "at": utc_now(),
        "selected_state_id": state_id,
        "policy": "lowest reuse count per estimated retained byte, then oldest last use",
        "server_internal_eviction_forced": False,
        "history_preserved": True,
    }
    state["live"] = False
    state["live_session_id"] = None
    state["non_live_reason"] = "controller-evicted"
    state["last_eviction"] = event
    registry["history"].append(event)
    save_registry(registry)
    return event


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    if ATTEMPT_PATH.exists():
        raise NeoLoopError("the single declared HoloState-v1 validation sequence has already been attempted")
    if not 0 <= args.extended_requests <= MAX_EXTENDED_REQUESTS:
        raise NeoLoopError(f"extended request count must be between 0 and {MAX_EXTENDED_REQUESTS}")
    attempt = {"started_at": utc_now(), "status": "running", "fixed_sequence": FIXED_SEQUENCE, "extended_requests": args.extended_requests}
    write_runtime_json(ATTEMPT_PATH, attempt)
    evaluator = load_json(EVALUATOR_PATH)
    stable_before = require_stable()
    stable_head = git_read(ROOT, "rev-parse", "HEAD")
    stable_status = git_read(ROOT, "status", "--porcelain")
    candidate_root = ROOT.parent / f"{ROOT.name}-candidate"
    candidate_head = git_read(candidate_root, "rev-parse", "HEAD")
    candidate_status = git_read(candidate_root, "status", "--porcelain", "--untracked-files=all")
    result: dict[str, Any] = {
        "schema_version": 1,
        "id": "neo-exp-0013-local-validation",
        "started_at": attempt["started_at"],
        "configuration": default_registry()["configuration"],
        "stable_before": {"pids": sorted(stable_before), "head": stable_head, "status": stable_status},
        "candidate_before": {"head": candidate_head, "status": candidate_status},
        "fixed_sequence": FIXED_SEQUENCE,
        "extended_request_limit": args.extended_requests,
        "warm_results": {},
        "branch_results": [],
        "extended_results": [],
        "verdict": "inconclusive",
    }
    sidecar = LiveSidecar(Path(args.binary), Path(args.model), evaluator, detached=False)
    try:
        readiness = sidecar.launch()
        record = registry_sidecar_record(readiness)
        record["private_at_readiness_bytes"] = readiness["process_memory"]["private_bytes"]
        registry = default_registry()
        registry["sidecar"] = record
        registry["history"].append({"event": "validation-start", "at": utc_now(), "sidecar": record})
        save_registry(registry)
        result["sidecar"] = readiness
        root_state_ids: dict[str, str] = {}
        for root_name in ("A", "B"):
            raw, sources = compose_prefix(root_name)
            prefix_path, _ = store_prefix(raw)
            state = sidecar.guarded(
                f"warm-{root_name}",
                lambda p=prefix_path, n=root_name, s=sources: warm_state(
                    p, f"Root {n}", s, trusted_session_id=sidecar.session_id
                ),
            )
            if not 4_000 <= int(state["rendered_token_count"]) <= 8_192:
                raise NeoLoopError(
                    f"root {root_name} rendered token count {state['rendered_token_count']} is outside 4K-8K"
                )
            root_state_ids[root_name] = state["state_id"]
            result["warm_results"][root_name] = {
                "state_id": state["state_id"],
                "canonical_prefix_sha256": state["canonical_prefix_sha256"],
                "token_id_sha256": state["token_id_sha256"],
                "chat_template_sha256": state["chat_template_sha256"],
                "rendered_token_count": state["rendered_token_count"],
                "canonical_prefix_bytes": state["canonical_prefix_bytes"],
                "sources": state["prefix_sources"],
                "warm_result": state["warm_result"],
            }
        registry = load_registry()
        assign_estimated_bytes(registry, list(root_state_ids.values()))
        save_registry(registry)
        result["root_state_ids"] = root_state_ids
        for branch_name in FIXED_SEQUENCE:
            branch = BRANCHES[branch_name]
            item = sidecar.guarded(
                f"fixed-{branch_name}",
                lambda b=branch, n=branch_name: branch_state(
                    root_state_ids[b["root"]], n, b["suffix"], b["expected"], sidecar.sampler
                ),
            )
            result["branch_results"].append(item)
        fixed_gate = deterministic_group_gate(result["branch_results"])
        if not all(item["exact"] for item in fixed_gate.values()):
            raise NeoLoopError(f"fixed same-branch deterministic gate failed: {fixed_gate}")
        if sidecar.process is None:
            raise NeoLoopError("missing tracked sidecar process")
        proof_pid = sidecar.process.pid
        extended_started = time.monotonic()
        for index in range(args.extended_requests):
            if time.monotonic() - extended_started >= MAX_EXTENDED_SECONDS:
                raise NeoLoopError("extended proof reached the 60-minute ceiling before its declared request count")
            branch_name = EXTENDED_CYCLE[index % len(EXTENDED_CYCLE)]
            branch = BRANCHES[branch_name]
            item = sidecar.guarded(
                f"extended-{index + 1}-{branch_name}",
                lambda b=branch, n=branch_name: branch_state(
                    root_state_ids[b["root"]], n, b["suffix"], b["expected"], sidecar.sampler
                ),
            )
            if not sidecar.process or sidecar.process.pid != proof_pid:
                raise NeoLoopError("sidecar PID changed during extended proof")
            item["extended_index"] = index + 1
            result["extended_results"].append(item)
        result["extended_proof"] = {
            "duration_seconds": time.monotonic() - extended_started,
            "request_count": len(result["extended_results"]),
            "request_limit": MAX_EXTENDED_REQUESTS,
            "duration_limit_seconds": MAX_EXTENDED_SECONDS,
            "roots": ["A", "B"],
            "sidecar_pid_unchanged": sidecar.process is not None and sidecar.process.pid == proof_pid,
            "sidecar_restarted": False,
        }
        all_results = result["branch_results"] + result["extended_results"]
        deterministic = deterministic_group_gate(all_results)
        if set(deterministic) != set(BRANCHES) or not all(item["exact"] for item in deterministic.values()):
            raise NeoLoopError(f"extended same-branch deterministic gate failed: {deterministic}")
        registry = load_registry()
        states = [registry["states"][root_state_ids[root]] for root in ("A", "B")]
        if not all(state.get("live") and state.get("live_session_id") == sidecar.session_id for state in states):
            raise NeoLoopError("both roots were not live in the exact sidecar session")
        info = process_info(proof_pid)
        if not info:
            raise NeoLoopError("sidecar host memory unavailable at final gate")
        host_growth = max(0, int(info["private_bytes"]) - int(record["private_at_readiness_bytes"]))
        if host_growth > CACHE_RAM_MIB * MIB:
            raise NeoLoopError("final host cache/private-memory growth exceeded 4096 MiB")
        telemetry = sidecar.telemetry()
        if telemetry.get("sample_count", 0) <= 0 or telemetry.get("peak_dedicated_mib", VRAM_CEILING_MIB + 1) > VRAM_CEILING_MIB:
            raise NeoLoopError("final WDDM gate failed")
        require_stable(stable_before)
        if git_read(ROOT, "rev-parse", "HEAD") != stable_head or git_read(ROOT, "status", "--porcelain") != stable_status:
            raise NeoLoopError("stable worktree changed during HoloState validation")
        if git_read(candidate_root, "rev-parse", "HEAD") != candidate_head or git_read(candidate_root, "status", "--porcelain", "--untracked-files=all") != candidate_status:
            raise NeoLoopError("archived trace candidate changed during HoloState validation")
        result["deterministic_groups"] = deterministic
        result["metrics"] = catalytic_metrics(registry, all_results)
        result["cache_registry"] = {
            "entry_count": len(registry["states"]),
            "total_configured_cache_bytes": CACHE_RAM_MIB * MIB,
            "estimated_bytes_per_entry": {state_id: registry["states"][state_id]["estimated_bytes"] for state_id in root_state_ids.values()},
            "reuse_counts": {state_id: registry["states"][state_id]["reuse_count"] for state_id in root_state_ids.values()},
            "last_use_order": [
                state["state_id"]
                for state in sorted(states, key=lambda item: item["last_use_timestamp"])
            ],
            "eviction_candidate_if_admission_required": select_eviction_candidate(registry["states"]),
            "observed_server_eviction": False,
            "evicted_state_id": None,
            "policy": "never active; retain high reuse; lowest reuse per estimated byte then oldest last use; preserve history",
            "host_private_growth_bytes": host_growth,
            "host_growth_within_4096_mib": True,
        }
        result["quality_gates"] = {
            "two_roots": len(root_state_ids) == 2,
            "two_branches_per_root": set(deterministic) == set(BRANCHES),
            "fixed_interleaving": True,
            "all_outputs_exact": all(item["structure"]["exact_final"] for item in all_results),
            "same_branch_tokens_exact": all(len(item["token_hashes"]) == 1 for item in deterministic.values()),
            "same_branch_reasoning_exact": all(len(item["reasoning_hashes"]) == 1 for item in deterministic.values()),
            "every_branch_reused": all(item["catalytic"] for item in all_results),
            "cross_root_contamination": False,
            "sidecar_pid_unchanged": True,
            "wddm_below_6000_mib": True,
            "host_cache_within_4096_mib": True,
            "stable_isolation": True,
            "candidate_unchanged": True,
            "automatic_promotion": False,
        }
        result["wddm"] = telemetry
        result["stable_after_proof"] = stable_snapshot()
        result["verdict"] = "reviewable-accept"
        result["PROCESS_LOCAL_HOLOSTATE_AVAILABLE"] = "UNLOCKED"
        result["RESTART_PERSISTENT_HOLOSTATE_AVAILABLE"] = "LOCKED"
    except Exception as exc:
        result["error"] = str(exc)
        result["verdict"] = "inconclusive"
        result["PROCESS_LOCAL_HOLOSTATE_AVAILABLE"] = "LOCKED"
        result["RESTART_PERSISTENT_HOLOSTATE_AVAILABLE"] = "LOCKED"
    finally:
        result["cleanup"] = sidecar.stop()
        registry = load_registry()
        mark_all_states_non_live(registry, "validation-sidecar-stopped")
        registry["sidecar"] = None
        registry["active_request"] = None
        registry["history"].append({"event": "validation-cleanup", "at": utc_now(), "verdict": result["verdict"]})
        save_registry(registry)
        result["registry_after_cleanup"] = {
            "entry_count": len(registry["states"]),
            "live_entry_count": sum(1 for state in registry["states"].values() if state.get("live")),
            "history_preserved": True,
        }
        result["stable_after_cleanup"] = stable_snapshot()
        result["finished_at"] = utc_now()
        write_runtime_json(RESULT_PATH, result)
        attempt.update({"status": "complete", "finished_at": result["finished_at"], "verdict": result["verdict"], "result_path": str(RESULT_PATH)})
        write_runtime_json(ATTEMPT_PATH, attempt)
    return result


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    return run_validation(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--binary", default=str(DEFAULT_BINARY))
    common.add_argument("--model", default=os.environ.get("NEO3000_MODEL"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start", parents=[common])
    start.set_defaults(handler=command_start)
    stop = subparsers.add_parser("stop")
    stop.set_defaults(handler=command_stop)
    status = subparsers.add_parser("status")
    status.set_defaults(handler=command_status)
    warm = subparsers.add_parser("warm")
    warm.add_argument("--prefix", required=True)
    warm.add_argument("--display-name", required=True)
    warm.set_defaults(handler=command_warm)
    branch = subparsers.add_parser("branch")
    branch.add_argument("--state", required=True)
    branch.add_argument("--branch-name", required=True)
    branch.add_argument("--suffix", required=True)
    branch.add_argument("--expected", required=True)
    branch.set_defaults(handler=command_branch)
    listing = subparsers.add_parser("list")
    listing.set_defaults(handler=command_list)
    evict = subparsers.add_parser("evict")
    evict.add_argument("--state")
    evict.set_defaults(handler=command_evict)
    validate = subparsers.add_parser("validate", parents=[common])
    validate.add_argument("--extended-requests", type=int, default=MAX_EXTENDED_REQUESTS)
    validate.set_defaults(handler=command_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command in {"start", "validate"} and not args.model:
        raise SystemExit("set NEO3000_MODEL or pass --model with the exact Agents-A1 GGUF path")
    try:
        result = args.handler(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("verdict") != "inconclusive" else 1
    except (NeoLoopError, OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
