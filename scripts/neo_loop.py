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
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from listener_probe import (  # shared checked ownership substrate for protected v3 controllers
    ListenerOwnershipEvidence,
    ListenerQueryEvidence,
    qualify_listener_ownership,
    query_listener_pids,
)
from wddm_telemetry_resilience import (
    ResilientWddmTelemetry,
    WddmTelemetryPolicy,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT.parent / f"{ROOT.name}-candidate"
EVALUATOR_PATH = ROOT / "lab" / "EVALUATOR.json"
LOCK_PATH = ROOT / "lab" / "EVALUATOR.lock.json"
RESULTS_PATH = ROOT / "lab" / "results.jsonl"
LOCK_DYNAMIC_PATHS = {"lab/EVALUATOR.lock.json", "lab/results.jsonl"}
CANDIDATE_BUILD_DIR = CANDIDATE_ROOT / "build" / "candidate"
WDDM_DEDICATED_COUNTER = r"\GPU Process Memory(*)\Dedicated Usage"
WDDM_QUERY_TIMEOUT_SECONDS = 10.0
WDDM_SAMPLER_STOP_MARGIN_SECONDS = 2.0
WDDM_SAMPLER_STOP_FAILURE = "candidate-vram-telemetry-sampler-stop-timeout"


class NeoLoopError(RuntimeError):
    """A declared safety or quality gate failed."""


@dataclass
class CycleResult:
    verdict: str
    reason: str
    commit: str
    evidence: dict[str, Any]


@dataclass
class ProcessVramSample:
    available: bool
    bytes: int | None
    instances: list[str]
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "MISSING"


def sha256_protected_text_file(path: Path) -> str:
    """Hash protected source semantics independently of checkout EOL policy."""
    if not path.is_file():
        return "MISSING"
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def gate_definition_hashes(evaluator: dict[str, Any]) -> dict[str, str]:
    gates = evaluator.get("gates", {})
    return {
        gate["id"]: sha256_bytes(canonical_json_bytes(gate))
        for gate in gates.values()
    }


def holostate_contract_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing HoloState contract as one object."""
    contract = evaluator.get("holostate_live_contract")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing holostate_live_contract")
    return sha256_bytes(canonical_json_bytes(contract))


def holostate_worker_protocol_hash(evaluator: dict[str, Any]) -> str:
    """Hash the preserved complete HoloState worker protocol v1 object."""
    protocol = evaluator.get("holostate_worker_protocol_v1")
    if not isinstance(protocol, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v1")
    return sha256_bytes(canonical_json_bytes(protocol))


def holostate_worker_protocol_v1_adjudication_hash(evaluator: dict[str, Any]) -> str:
    """Hash the later interpretation without changing the executed v1 record."""
    adjudication = evaluator.get("holostate_worker_protocol_v1_adjudication")
    if not isinstance(adjudication, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v1_adjudication")
    return sha256_bytes(canonical_json_bytes(adjudication))


def holostate_worker_protocol_v2_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing HoloState worker protocol v2 object."""
    protocol = evaluator.get("holostate_worker_protocol_v2")
    if not isinstance(protocol, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v2")
    return sha256_bytes(canonical_json_bytes(protocol))


def holostate_worker_protocol_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete tracked adjudication of the ignored one-shot evidence."""
    evidence = evaluator.get("holostate_worker_protocol_v1_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v1_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def holostate_worker_protocol_v2_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the tracked v2 adjudication after the ignored one-shot evidence exists."""
    evidence = evaluator.get("holostate_worker_protocol_v2_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v2_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def holostate_worker_protocol_v3_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing HoloState worker protocol v3 object."""
    protocol = evaluator.get("holostate_worker_protocol_v3")
    if not isinstance(protocol, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v3")
    return sha256_bytes(canonical_json_bytes(protocol))


def holostate_worker_protocol_v3_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the tracked v3 adjudication after readiness evidence exists."""
    evidence = evaluator.get("holostate_worker_protocol_v3_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v3_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def holostate_worker_protocol_v4_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing HoloState worker protocol v4 object."""
    protocol = evaluator.get("holostate_worker_protocol_v4")
    if not isinstance(protocol, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v4")
    return sha256_bytes(canonical_json_bytes(protocol))


def holostate_worker_protocol_v4_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the tracked v4 adjudication after the one-shot artifacts exist."""
    evidence = evaluator.get("holostate_worker_protocol_v4_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing holostate_worker_protocol_v4_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def catalytic_swarm_0_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing CatalyticSwarm-0 contract."""
    contract = evaluator.get("catalytic_swarm_0")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_0")
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_0_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the tracked adjudication of the one-shot CatalyticSwarm-0 proof."""
    evidence = evaluator.get("catalytic_swarm_0_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_0_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def catalytic_swarm_0_v2_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete separately versioned CatalyticSwarm-0 v2 contract."""
    contract = evaluator.get("catalytic_swarm_0_v2")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_0_v2")
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_0_v2_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the tracked adjudication of the one-shot CatalyticSwarm-0 v2 proof."""
    evidence = evaluator.get("catalytic_swarm_0_v2_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_0_v2_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def catalytic_swarm_1_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing CatalyticSwarm-1 contract."""
    contract = evaluator.get("catalytic_swarm_1")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1")
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_1_evidence_hash(evaluator: dict[str, Any]) -> str:
    """Hash the tracked adjudication of the one-shot CatalyticSwarm-1 attempt."""
    evidence = evaluator.get("catalytic_swarm_1_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1_evidence")
    return sha256_bytes(canonical_json_bytes(evidence))


def catalytic_swarm_1_cache_diagnostic_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete separately versioned CS1 cache diagnostic contract."""
    contract = evaluator.get("catalytic_swarm_1_cache_diagnostic")
    if not isinstance(contract, dict):
        raise NeoLoopError(
            "evaluator is missing catalytic_swarm_1_cache_diagnostic"
        )
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_1_cache_diagnostic_evidence_hash(
    evaluator: dict[str, Any],
) -> str:
    """Hash the completed, separately bound CS1 cache-diagnostic evidence."""
    evidence = evaluator.get("catalytic_swarm_1_cache_diagnostic_evidence")
    if not isinstance(evidence, dict):
        raise NeoLoopError(
            "evaluator is missing catalytic_swarm_1_cache_diagnostic_evidence"
        )
    return sha256_bytes(canonical_json_bytes(evidence))


def catalytic_swarm_1_v2_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete claim-bearing CatalyticSwarm-1 v2 contract."""
    contract = evaluator.get("catalytic_swarm_1_v2")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1_v2")
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_1_v2_preclaim_boundary_hash(evaluator: dict[str, Any]) -> str:
    """Hash the immutable fail-closed CS1-v2 consumed-attempt boundary."""
    boundary = evaluator.get("catalytic_swarm_1_v2_preclaim_boundary")
    if not isinstance(boundary, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1_v2_preclaim_boundary")
    return sha256_bytes(canonical_json_bytes(boundary))


def catalytic_swarm_1_v3_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete separately versioned CS1-v3 contract."""
    contract = evaluator.get("catalytic_swarm_1_v3")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1_v3")
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_1_v3_runtime_evidence_binding_hash(
    evaluator: dict[str, Any],
) -> str:
    """Hash the complete CS1-v3 runtime-evidence identity binding."""
    contract = evaluator.get("catalytic_swarm_1_v3_runtime_evidence_binding")
    if not isinstance(contract, dict):
        raise NeoLoopError(
            "evaluator is missing catalytic_swarm_1_v3_runtime_evidence_binding"
        )
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_1_v3_preclaim_boundary_hash(evaluator: dict[str, Any]) -> str:
    """Hash the canonical tracked binding of the consumed CS1-v3 attempt."""
    boundary = evaluator.get("catalytic_swarm_1_v3_preclaim_boundary")
    if not isinstance(boundary, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1_v3_preclaim_boundary")
    return sha256_bytes(canonical_json_bytes(boundary))


def catalytic_swarm_1_v4_hash(evaluator: dict[str, Any]) -> str:
    """Hash the complete separately versioned CS1-v4 claim contract."""
    contract = evaluator.get("catalytic_swarm_1_v4")
    if not isinstance(contract, dict):
        raise NeoLoopError("evaluator is missing catalytic_swarm_1_v4")
    return sha256_bytes(canonical_json_bytes(contract))


def catalytic_swarm_1_v4_runtime_evidence_binding_hash(
    evaluator: dict[str, Any],
) -> str:
    """Hash the complete CS1-v4 runtime-evidence identity binding."""
    contract = evaluator.get("catalytic_swarm_1_v4_runtime_evidence_binding")
    if not isinstance(contract, dict):
        raise NeoLoopError(
            "evaluator is missing catalytic_swarm_1_v4_runtime_evidence_binding"
        )
    return sha256_bytes(canonical_json_bytes(contract))


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


def protected_lock_paths(evaluator: dict[str, Any]) -> list[str]:
    """Derive the complete protected hash surface from the evaluator."""
    protected_files = evaluator["protected_paths"]["files"]
    controller_files = evaluator["controller_files"]
    benchmark_files = evaluator["benchmark_prompt_sources"]
    holostate_sources = [
        source
        for root in evaluator["holostate_live_contract"]["roots"].values()
        for source in root["sources"]
    ]
    worker_protocol_v1_sources = [
        source
        for root in evaluator["holostate_worker_protocol_v1"]["roots"].values()
        for source in root["sources"]
    ]
    worker_protocol_v2_sources = [
        source
        for root in evaluator["holostate_worker_protocol_v2"]["roots"].values()
        for source in root["sources"]
    ]
    worker_protocol_v3_sources = [
        source
        for root in evaluator["holostate_worker_protocol_v3"]["roots"].values()
        for source in root["sources"]
    ]
    worker_protocol_v4_sources = [
        source
        for root in evaluator["holostate_worker_protocol_v4"]["roots"].values()
        for source in root["sources"]
    ]
    return sorted(
        path for path in set(
            protected_files
            + controller_files
            + benchmark_files
            + holostate_sources
            + worker_protocol_v1_sources
            + worker_protocol_v2_sources
            + worker_protocol_v3_sources
            + worker_protocol_v4_sources
        )
        if path not in LOCK_DYNAMIC_PATHS
    )


def make_lock(evaluator: dict[str, Any]) -> dict[str, Any]:
    protected_files = evaluator["protected_paths"]["files"]
    controller_files = evaluator["controller_files"]
    hashed_files = protected_lock_paths(evaluator)
    protected_hashes: dict[str, str] = {}
    for path in hashed_files:
        digest = sha256_protected_text_file(ROOT / path)
        if digest == "MISSING":
            raise NeoLoopError(f"protected file is missing during lock generation: {path}")
        protected_hashes[path] = digest
    lock = {
        "schema_version": 2,
        "generated_at": utc_now(),
        "evaluator_sha256": sha256_protected_text_file(EVALUATOR_PATH),
        "protected_text_hash_mode": "crlf-to-lf-v1",
        "protected_file_hashes": protected_hashes,
        "benchmark_prompt_hashes": {
            prompt["id"]: sha256_bytes(prompt["text"].encode("utf-8"))
            for prompt in evaluator["inline_prompt_sources"]
        },
        "gate_definition_hashes": gate_definition_hashes(evaluator),
        "holostate_contract_sha256": holostate_contract_hash(evaluator),
        "holostate_worker_protocol_sha256": holostate_worker_protocol_hash(evaluator),
        "holostate_worker_protocol_evidence_sha256": holostate_worker_protocol_evidence_hash(evaluator),
        "holostate_worker_protocol_v1_adjudication_sha256": holostate_worker_protocol_v1_adjudication_hash(evaluator),
        "holostate_worker_protocol_v2_sha256": holostate_worker_protocol_v2_hash(evaluator),
        "holostate_worker_protocol_v3_sha256": holostate_worker_protocol_v3_hash(evaluator),
        "holostate_worker_protocol_v4_sha256": holostate_worker_protocol_v4_hash(evaluator),
        "catalytic_swarm_0_sha256": catalytic_swarm_0_hash(evaluator),
        "catalytic_swarm_0_v2_sha256": catalytic_swarm_0_v2_hash(evaluator),
        "catalytic_swarm_1_sha256": catalytic_swarm_1_hash(evaluator),
        "catalytic_swarm_1_cache_diagnostic_sha256": (
            catalytic_swarm_1_cache_diagnostic_hash(evaluator)
        ),
        "catalytic_swarm_1_cache_diagnostic_evidence_sha256": (
            catalytic_swarm_1_cache_diagnostic_evidence_hash(evaluator)
        ),
        "catalytic_swarm_1_v2_sha256": catalytic_swarm_1_v2_hash(evaluator),
        "catalytic_swarm_1_v2_preclaim_boundary_sha256": (
            catalytic_swarm_1_v2_preclaim_boundary_hash(evaluator)
        ),
        "catalytic_swarm_1_v3_sha256": catalytic_swarm_1_v3_hash(evaluator),
        "catalytic_swarm_1_v3_runtime_evidence_binding_sha256": (
            catalytic_swarm_1_v3_runtime_evidence_binding_hash(evaluator)
        ),
        "catalytic_swarm_1_v3_preclaim_boundary_sha256": (
            catalytic_swarm_1_v3_preclaim_boundary_hash(evaluator)
        ),
        "catalytic_swarm_1_v4_sha256": catalytic_swarm_1_v4_hash(evaluator),
        "catalytic_swarm_1_v4_runtime_evidence_binding_sha256": (
            catalytic_swarm_1_v4_runtime_evidence_binding_hash(evaluator)
        ),
        "model_identity": evaluator["model"],
        "baseline_source_commit": git(ROOT, "rev-parse", "HEAD"),
        "stable_launch": evaluator["stable_launch"],
        "candidate_launch": evaluator["candidate_launch"],
        "protected_paths": evaluator["protected_paths"]["files"],
        "candidate_editable_paths": evaluator["candidate_editable_paths"]["paths"],
        "controller_files": controller_files,
    }
    if "holostate_worker_protocol_v2_evidence" in evaluator:
        lock["holostate_worker_protocol_v2_evidence_sha256"] = (
            holostate_worker_protocol_v2_evidence_hash(evaluator)
        )
    if "holostate_worker_protocol_v3_evidence" in evaluator:
        lock["holostate_worker_protocol_v3_evidence_sha256"] = (
            holostate_worker_protocol_v3_evidence_hash(evaluator)
        )
    if "holostate_worker_protocol_v4_evidence" in evaluator:
        lock["holostate_worker_protocol_v4_evidence_sha256"] = (
            holostate_worker_protocol_v4_evidence_hash(evaluator)
        )
    if "catalytic_swarm_0_evidence" in evaluator:
        lock["catalytic_swarm_0_evidence_sha256"] = (
            catalytic_swarm_0_evidence_hash(evaluator)
        )
    if "catalytic_swarm_0_v2_evidence" in evaluator:
        lock["catalytic_swarm_0_v2_evidence_sha256"] = (
            catalytic_swarm_0_v2_evidence_hash(evaluator)
        )
    if "catalytic_swarm_1_evidence" in evaluator:
        lock["catalytic_swarm_1_evidence_sha256"] = (
            catalytic_swarm_1_evidence_hash(evaluator)
        )
    return lock


def write_lock() -> None:
    evaluator = load_json(EVALUATOR_PATH)
    lock = make_lock(evaluator)
    LOCK_PATH.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {LOCK_PATH}")


def verify_lock(evaluator: dict[str, Any]) -> dict[str, Any]:
    lock = load_json(LOCK_PATH)
    if lock.get("schema_version") != 2:
        raise NeoLoopError("unsupported evaluator lock schema")
    if lock.get("protected_text_hash_mode") != "crlf-to-lf-v1":
        raise NeoLoopError("unsupported protected text hash mode")
    if lock.get("evaluator_sha256") != sha256_protected_text_file(EVALUATOR_PATH):
        raise NeoLoopError("evaluator manifest differs from its lockfile")
    duplicated_bindings = {
        "model_identity": evaluator["model"],
        "stable_launch": evaluator["stable_launch"],
        "candidate_launch": evaluator["candidate_launch"],
        "protected_paths": evaluator["protected_paths"]["files"],
        "candidate_editable_paths": evaluator["candidate_editable_paths"]["paths"],
        "controller_files": evaluator["controller_files"],
    }
    for key, expected in duplicated_bindings.items():
        if lock.get(key) != expected:
            raise NeoLoopError(f"lockfile {key} differs from evaluator")
    expected_hashes = lock.get("protected_file_hashes", {})
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        raise NeoLoopError("lockfile contains no protected hashes")
    required_hash_paths = protected_lock_paths(evaluator)
    if set(expected_hashes) != set(required_hash_paths):
        missing = sorted(set(required_hash_paths) - set(expected_hashes))
        extra = sorted(set(expected_hashes) - set(required_hash_paths))
        raise NeoLoopError(
            "lockfile protected hash surface differs from evaluator "
            f"(missing={missing}, extra={extra})"
        )
    for path, expected in expected_hashes.items():
        actual = sha256_protected_text_file(ROOT / path)
        if expected == "MISSING" or actual == "MISSING":
            raise NeoLoopError(f"protected file is missing: {path}")
        if actual != expected:
            raise NeoLoopError(
                f"protected hash changed: {path} (expected {expected}, actual {actual})"
            )
    for prompt in evaluator["inline_prompt_sources"]:
        expected = lock["benchmark_prompt_hashes"].get(prompt["id"])
        actual = sha256_bytes(prompt["text"].encode("utf-8"))
        if expected != actual:
            raise NeoLoopError(f"benchmark prompt changed: {prompt['id']} (expected {expected}, actual {actual})")
    expected_gates = lock.get("gate_definition_hashes")
    if not isinstance(expected_gates, dict):
        raise NeoLoopError("lockfile missing gate definition hashes")
    actual_gates = gate_definition_hashes(evaluator)
    if expected_gates != actual_gates:
        raise NeoLoopError("evaluator gate definitions differ from their lockfile")
    expected_holostate = lock.get("holostate_contract_sha256")
    actual_holostate = holostate_contract_hash(evaluator)
    if expected_holostate != actual_holostate:
        raise NeoLoopError("HoloState contract differs from its locked complete-object hash")
    expected_worker_protocol = lock.get("holostate_worker_protocol_sha256")
    actual_worker_protocol = holostate_worker_protocol_hash(evaluator)
    if expected_worker_protocol != actual_worker_protocol:
        raise NeoLoopError("HoloState worker protocol differs from its locked complete-object hash")
    expected_worker_evidence = lock.get("holostate_worker_protocol_evidence_sha256")
    actual_worker_evidence = holostate_worker_protocol_evidence_hash(evaluator)
    if expected_worker_evidence != actual_worker_evidence:
        raise NeoLoopError("HoloState worker evidence differs from its locked complete-object hash")
    expected_v1_adjudication = lock.get("holostate_worker_protocol_v1_adjudication_sha256")
    actual_v1_adjudication = holostate_worker_protocol_v1_adjudication_hash(evaluator)
    if expected_v1_adjudication != actual_v1_adjudication:
        raise NeoLoopError("HoloState worker v1 adjudication differs from its locked complete-object hash")
    expected_worker_v2 = lock.get("holostate_worker_protocol_v2_sha256")
    actual_worker_v2 = holostate_worker_protocol_v2_hash(evaluator)
    if expected_worker_v2 != actual_worker_v2:
        raise NeoLoopError("HoloState worker protocol v2 differs from its locked complete-object hash")
    has_v2_evidence = "holostate_worker_protocol_v2_evidence" in evaluator
    has_v2_evidence_lock = "holostate_worker_protocol_v2_evidence_sha256" in lock
    if has_v2_evidence != has_v2_evidence_lock:
        raise NeoLoopError("HoloState worker v2 evidence and lock must appear together")
    if has_v2_evidence:
        expected_worker_v2_evidence = lock["holostate_worker_protocol_v2_evidence_sha256"]
        actual_worker_v2_evidence = holostate_worker_protocol_v2_evidence_hash(evaluator)
        if expected_worker_v2_evidence != actual_worker_v2_evidence:
            raise NeoLoopError("HoloState worker v2 evidence differs from its locked complete-object hash")
    expected_worker_v3 = lock.get("holostate_worker_protocol_v3_sha256")
    actual_worker_v3 = holostate_worker_protocol_v3_hash(evaluator)
    if expected_worker_v3 != actual_worker_v3:
        raise NeoLoopError("HoloState worker protocol v3 differs from its locked complete-object hash")
    has_v3_evidence = "holostate_worker_protocol_v3_evidence" in evaluator
    has_v3_evidence_lock = "holostate_worker_protocol_v3_evidence_sha256" in lock
    if has_v3_evidence != has_v3_evidence_lock:
        raise NeoLoopError("HoloState worker v3 evidence and lock must appear together")
    if has_v3_evidence:
        expected_worker_v3_evidence = lock["holostate_worker_protocol_v3_evidence_sha256"]
        actual_worker_v3_evidence = holostate_worker_protocol_v3_evidence_hash(evaluator)
        if expected_worker_v3_evidence != actual_worker_v3_evidence:
            raise NeoLoopError("HoloState worker v3 evidence differs from its locked complete-object hash")
    expected_worker_v4 = lock.get("holostate_worker_protocol_v4_sha256")
    actual_worker_v4 = holostate_worker_protocol_v4_hash(evaluator)
    if expected_worker_v4 != actual_worker_v4:
        raise NeoLoopError("HoloState worker protocol v4 differs from its locked complete-object hash")
    has_v4_evidence = "holostate_worker_protocol_v4_evidence" in evaluator
    has_v4_evidence_lock = "holostate_worker_protocol_v4_evidence_sha256" in lock
    if has_v4_evidence != has_v4_evidence_lock:
        raise NeoLoopError("HoloState worker v4 evidence and lock must appear together")
    if has_v4_evidence:
        expected_worker_v4_evidence = lock["holostate_worker_protocol_v4_evidence_sha256"]
        actual_worker_v4_evidence = holostate_worker_protocol_v4_evidence_hash(evaluator)
        if expected_worker_v4_evidence != actual_worker_v4_evidence:
            raise NeoLoopError("HoloState worker v4 evidence differs from its locked complete-object hash")
    expected_swarm_0 = lock.get("catalytic_swarm_0_sha256")
    actual_swarm_0 = catalytic_swarm_0_hash(evaluator)
    if expected_swarm_0 != actual_swarm_0:
        raise NeoLoopError("CatalyticSwarm-0 contract differs from its locked complete-object hash")
    has_swarm_0_evidence = "catalytic_swarm_0_evidence" in evaluator
    has_swarm_0_evidence_lock = "catalytic_swarm_0_evidence_sha256" in lock
    if has_swarm_0_evidence != has_swarm_0_evidence_lock:
        raise NeoLoopError("CatalyticSwarm-0 evidence and lock must appear together")
    if has_swarm_0_evidence:
        expected_swarm_0_evidence = lock["catalytic_swarm_0_evidence_sha256"]
        actual_swarm_0_evidence = catalytic_swarm_0_evidence_hash(evaluator)
        if expected_swarm_0_evidence != actual_swarm_0_evidence:
            raise NeoLoopError("CatalyticSwarm-0 evidence differs from its locked complete-object hash")
    expected_swarm_0_v2 = lock.get("catalytic_swarm_0_v2_sha256")
    actual_swarm_0_v2 = catalytic_swarm_0_v2_hash(evaluator)
    if expected_swarm_0_v2 != actual_swarm_0_v2:
        raise NeoLoopError(
            "CatalyticSwarm-0 v2 contract differs from its locked complete-object hash"
        )
    has_swarm_0_v2_evidence = "catalytic_swarm_0_v2_evidence" in evaluator
    has_swarm_0_v2_evidence_lock = (
        "catalytic_swarm_0_v2_evidence_sha256" in lock
    )
    if has_swarm_0_v2_evidence != has_swarm_0_v2_evidence_lock:
        raise NeoLoopError("CatalyticSwarm-0 v2 evidence and lock must appear together")
    if has_swarm_0_v2_evidence:
        expected_swarm_0_v2_evidence = lock[
            "catalytic_swarm_0_v2_evidence_sha256"
        ]
        actual_swarm_0_v2_evidence = catalytic_swarm_0_v2_evidence_hash(
            evaluator
        )
        if expected_swarm_0_v2_evidence != actual_swarm_0_v2_evidence:
            raise NeoLoopError(
                "CatalyticSwarm-0 v2 evidence differs from its locked complete-object hash"
            )
    expected_swarm_1 = lock.get("catalytic_swarm_1_sha256")
    actual_swarm_1 = catalytic_swarm_1_hash(evaluator)
    if expected_swarm_1 != actual_swarm_1:
        raise NeoLoopError(
            "CatalyticSwarm-1 contract differs from its locked complete-object hash"
        )
    has_swarm_1_evidence = "catalytic_swarm_1_evidence" in evaluator
    has_swarm_1_evidence_lock = "catalytic_swarm_1_evidence_sha256" in lock
    if has_swarm_1_evidence != has_swarm_1_evidence_lock:
        raise NeoLoopError("CatalyticSwarm-1 evidence and lock must appear together")
    if has_swarm_1_evidence:
        expected_swarm_1_evidence = lock["catalytic_swarm_1_evidence_sha256"]
        actual_swarm_1_evidence = catalytic_swarm_1_evidence_hash(evaluator)
        if expected_swarm_1_evidence != actual_swarm_1_evidence:
            raise NeoLoopError(
                "CatalyticSwarm-1 evidence differs from its locked complete-object hash"
            )
    expected_cache_diagnostic = lock.get(
        "catalytic_swarm_1_cache_diagnostic_sha256"
    )
    actual_cache_diagnostic = catalytic_swarm_1_cache_diagnostic_hash(evaluator)
    if expected_cache_diagnostic != actual_cache_diagnostic:
        raise NeoLoopError(
            "CatalyticSwarm-1 cache diagnostic differs from its locked complete-object hash"
        )
    expected_cache_diagnostic_evidence = lock.get(
        "catalytic_swarm_1_cache_diagnostic_evidence_sha256"
    )
    actual_cache_diagnostic_evidence = (
        catalytic_swarm_1_cache_diagnostic_evidence_hash(evaluator)
    )
    if expected_cache_diagnostic_evidence != actual_cache_diagnostic_evidence:
        raise NeoLoopError(
            "CatalyticSwarm-1 cache diagnostic evidence differs from its locked complete-object hash"
        )
    expected_swarm_1_v2 = lock.get("catalytic_swarm_1_v2_sha256")
    actual_swarm_1_v2 = catalytic_swarm_1_v2_hash(evaluator)
    if expected_swarm_1_v2 != actual_swarm_1_v2:
        raise NeoLoopError(
            "CatalyticSwarm-1 v2 contract differs from its locked complete-object hash"
        )
    expected_v2_preclaim = lock.get("catalytic_swarm_1_v2_preclaim_boundary_sha256")
    actual_v2_preclaim = catalytic_swarm_1_v2_preclaim_boundary_hash(evaluator)
    if expected_v2_preclaim != actual_v2_preclaim:
        raise NeoLoopError(
            "CatalyticSwarm-1 v2 preclaim boundary differs from its locked complete-object hash"
        )
    expected_swarm_1_v3 = lock.get("catalytic_swarm_1_v3_sha256")
    actual_swarm_1_v3 = catalytic_swarm_1_v3_hash(evaluator)
    if expected_swarm_1_v3 != actual_swarm_1_v3:
        raise NeoLoopError(
            "CatalyticSwarm-1 v3 contract differs from its locked complete-object hash"
        )
    expected_v3_runtime_binding = lock.get(
        "catalytic_swarm_1_v3_runtime_evidence_binding_sha256"
    )
    actual_v3_runtime_binding = catalytic_swarm_1_v3_runtime_evidence_binding_hash(
        evaluator
    )
    if expected_v3_runtime_binding != actual_v3_runtime_binding:
        raise NeoLoopError(
            "CatalyticSwarm-1 v3 runtime-evidence binding differs from its locked complete-object hash"
        )
    expected_v3_preclaim = lock.get("catalytic_swarm_1_v3_preclaim_boundary_sha256")
    actual_v3_preclaim = catalytic_swarm_1_v3_preclaim_boundary_hash(evaluator)
    if expected_v3_preclaim != actual_v3_preclaim:
        raise NeoLoopError(
            "CatalyticSwarm-1 v3 preclaim boundary differs from its locked complete-object hash"
        )
    expected_swarm_1_v4 = lock.get("catalytic_swarm_1_v4_sha256")
    actual_swarm_1_v4 = catalytic_swarm_1_v4_hash(evaluator)
    if expected_swarm_1_v4 != actual_swarm_1_v4:
        raise NeoLoopError(
            "CatalyticSwarm-1 v4 contract differs from its locked complete-object hash"
        )
    expected_v4_runtime_binding = lock.get(
        "catalytic_swarm_1_v4_runtime_evidence_binding_sha256"
    )
    actual_v4_runtime_binding = catalytic_swarm_1_v4_runtime_evidence_binding_hash(
        evaluator
    )
    if expected_v4_runtime_binding != actual_v4_runtime_binding:
        raise NeoLoopError(
            "CatalyticSwarm-1 v4 runtime-evidence binding differs from its locked complete-object hash"
        )
    return lock


def request_json(url: str, timeout: float = 30) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
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


def build_failure_evidence(exit_code: int, stdout: str, stderr: str) -> dict[str, Any]:
    """Keep causal CMake diagnostics without embedding an unbounded build log."""
    combined = stdout + ("\n" if stdout and stderr else "") + stderr
    lines = combined.splitlines()
    first_block: list[str] = []
    for index, line in enumerate(lines):
        if "CMake Error" in line:
            first_block = [candidate for candidate in lines[index:index + 16] if candidate.strip()]
            break
    needles = ("cannot find", "no sources", "duplicate target")
    diagnostics = [line.strip() for line in lines if any(needle in line.lower() for needle in needles)]
    log_path = CANDIDATE_BUILD_DIR / "neo-loop-build.local.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(combined, encoding="utf-8", errors="replace")
        local_log = str(log_path.relative_to(CANDIDATE_ROOT)).replace("\\", "/")
    except OSError:
        local_log = None
    return {
        "exit": exit_code,
        "first_cmake_error_block": first_block,
        "diagnostic_lines": diagnostics[:32],
        "stdout_tail": stdout.splitlines()[-20:],
        "stderr_tail": stderr.splitlines()[-20:],
        "candidate_build_log": local_log,
    }


def stop_candidate(process: subprocess.Popen[str] | None) -> dict[str, Any]:
    if process is None or process.poll() is not None:
        return {"candidate_process_stopped": True, "pid": process.pid if process else None}
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=20)
    return {"candidate_process_stopped": process.poll() is not None, "pid": process.pid}


def select_wddm_pid_memory(samples: list[dict[str, Any]], pid: int) -> ProcessVramSample:
    """Select only WDDM dedicated-memory rows owned by one exact PID."""
    marker = f"pid_{pid}_"
    matches = [
        sample for sample in samples
        if str(sample.get("instance", "")).lower().startswith(marker.lower())
    ]
    if not matches:
        return ProcessVramSample(False, None, [], "no-matching-pid-instance")
    values: list[float] = []
    instances: list[str] = []
    for sample in matches:
        if sample.get("status") != 0:
            return ProcessVramSample(False, None, instances, "counter-status-error")
        try:
            value = float(sample.get("value"))
        except (TypeError, ValueError):
            return ProcessVramSample(False, None, instances, "nonnumeric-counter-value")
        if not math.isfinite(value) or value < 0:
            return ProcessVramSample(False, None, instances, "invalid-counter-value")
        values.append(value)
        instances.append(str(sample["instance"]))
    return ProcessVramSample(True, int(sum(values)), instances)


def wddm_pid_memory_sample(pid: int) -> ProcessVramSample:
    """Read one Windows WDDM dedicated-memory sample for an exact process PID."""
    script = rf'''
$Counter = Get-Counter '{WDDM_DEDICATED_COUNTER}'
$Rows = @($Counter.CounterSamples | ForEach-Object {{
    [pscustomobject]@{{
        instance = $_.InstanceName
        status = [int] $_.Status
        value = [string] $_.CookedValue
    }}
}})
[pscustomobject]@{{ samples = $Rows }} | ConvertTo-Json -Compress -Depth 3
'''
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=WDDM_QUERY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ProcessVramSample(False, None, [], f"counter-query-failed: {exc}")
    if completed.returncode:
        return ProcessVramSample(False, None, [], f"counter-query-failed: {completed.stderr.strip()[:200]}")
    try:
        payload = json.loads(completed.stdout)
        rows = payload.get("samples", [])
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValueError("samples was not a list")
        return select_wddm_pid_memory(rows, pid)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return ProcessVramSample(False, None, [], f"counter-parse-failed: {exc}")


class CandidateVramSampler:
    """PID-filtered WDDM sampler retaining a compact peak, never raw streams."""

    def __init__(
        self,
        pid: int,
        ceiling_mib: int,
        interval_seconds: float,
        grace_seconds: float,
        sample_fn=wddm_pid_memory_sample,
        wddm_policy: WddmTelemetryPolicy | None = None,
    ):
        self.pid = pid
        self.ceiling_bytes = ceiling_mib * 1024 * 1024
        self.interval_seconds = interval_seconds
        self.grace_seconds = grace_seconds
        self.sample_fn = sample_fn
        self.wddm_policy = wddm_policy
        self.started_at = time.monotonic()
        self.first_valid_at: float | None = None
        self.last_valid_at: float | None = None
        self.maximum_valid_sample_gap_seconds = 0.0
        self.peak_bytes = 0
        self.sample_count = 0
        self.instances: set[str] = set()
        self.failures: list[str] = []
        self._failure_reason: str | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._sampler_stop_attempted = False
        self._sampler_stop_timed_out = False
        self._sampler_stop_failure_reason: str | None = None
        self._sampler_stop_wait_seconds: float | None = None
        self._resilient_telemetry = (
            ResilientWddmTelemetry(
                ceiling_bytes=self.ceiling_bytes,
                policy=wddm_policy,
                started_at=self.started_at,
            )
            if wddm_policy is not None
            else None
        )

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=f"neo-vram-{self.pid}", daemon=True)
        self._thread.start()

    def stop(self) -> bool | None:
        """Stop sampling after allowing the in-flight WDDM query to time out.

        ``wddm_pid_memory_sample`` has a ten-second subprocess timeout.  The
        join therefore waits through that timeout plus a fixed margin.  A
        still-live worker is retained as explicit fail-closed evidence rather
        than being silently abandoned as a daemon thread.  Policy-absent
        callers retain the original best-effort join and evidence surface.
        """

        self._stop.set()
        thread = self._thread
        if self._resilient_telemetry is None:
            if thread is not None:
                thread.join(timeout=max(5.0, self.interval_seconds * 2))
            return None

        timeout_seconds = WDDM_QUERY_TIMEOUT_SECONDS + WDDM_SAMPLER_STOP_MARGIN_SECONDS
        wait_started = time.monotonic()
        if thread is not None:
            thread.join(timeout=timeout_seconds)
        wait_seconds = max(0.0, time.monotonic() - wait_started)
        thread_alive = bool(thread is not None and thread.is_alive())
        with self._lock:
            self._sampler_stop_attempted = True
            self._sampler_stop_wait_seconds = wait_seconds
            if thread_alive:
                self._sampler_stop_timed_out = True
                self._sampler_stop_failure_reason = WDDM_SAMPLER_STOP_FAILURE
                now = time.monotonic()
                if self._resilient_telemetry is not None:
                    self._resilient_telemetry.fail_closed(
                        WDDM_SAMPLER_STOP_FAILURE,
                        now=now,
                        trigger_kind="sampler-stop",
                    )
                elif self._failure_reason is None:
                    self._failure_reason = WDDM_SAMPLER_STOP_FAILURE
        return not thread_alive

    def sample_once(self) -> None:
        sample = self.sample_fn(self.pid)
        now = time.monotonic()
        with self._lock:
            if self._resilient_telemetry is not None:
                try:
                    if sample.available and sample.bytes is not None:
                        marker = f"pid_{self.pid}_".lower()
                        if not sample.instances or any(
                            not str(instance).lower().startswith(marker)
                            for instance in sample.instances
                        ):
                            raise ValueError("sample did not contain only exact-PID instances")
                    self._resilient_telemetry.observe_sample(sample, now=now)
                except ValueError as exc:
                    self._resilient_telemetry.observe_unavailable(
                        f"invalid-exact-pid-sample: {exc}",
                        now=now,
                    )
                snapshot = self._resilient_telemetry.snapshot(now=now)
                self.first_valid_at = self._resilient_telemetry.first_valid_at
                self.last_valid_at = self._resilient_telemetry.last_valid_at
                self.maximum_valid_sample_gap_seconds = (
                    snapshot.maximum_valid_sample_gap_seconds or 0.0
                )
                self.sample_count = snapshot.sample_count
                self.peak_bytes = snapshot.peak_bytes or 0
                self.instances = set(snapshot.exact_instances)
                self.failures = list(snapshot.recent_failures)
                return
            if sample.available and sample.bytes is not None:
                if self.last_valid_at is not None:
                    self.maximum_valid_sample_gap_seconds = max(
                        self.maximum_valid_sample_gap_seconds,
                        max(0.0, now - self.last_valid_at),
                    )
                self.sample_count += 1
                self.peak_bytes = max(self.peak_bytes, sample.bytes)
                self.instances.update(sample.instances)
                if self.first_valid_at is None:
                    self.first_valid_at = now
                self.last_valid_at = now
                if sample.bytes > self.ceiling_bytes:
                    self._failure_reason = "candidate-memory-ceiling"
            else:
                self.failures.append(sample.error or "telemetry-unavailable")
                if self.first_valid_at is not None:
                    self._failure_reason = "candidate-vram-telemetry-lost"

    def _run(self) -> None:
        while not self._stop.is_set():
            self.sample_once()
            self._stop.wait(self.interval_seconds)

    def _legacy_failure_reason_locked(self, now: float) -> str | None:
        if self._failure_reason:
            return self._failure_reason
        if self.first_valid_at is None and now - self.started_at >= self.grace_seconds:
            return "candidate-vram-telemetry-unavailable"
        return None

    def failure_reason(self) -> str | None:
        now = time.monotonic()
        with self._lock:
            if self._resilient_telemetry is not None:
                return self._resilient_telemetry.failure_reason(now=now)
            return self._legacy_failure_reason_locked(now)

    def has_valid_sample(self) -> bool:
        with self._lock:
            if self._resilient_telemetry is not None:
                return self._resilient_telemetry.has_valid_sample()
            return self.first_valid_at is not None

    def has_fresh_valid_sample(self) -> bool:
        """Return freshness admission state without changing legacy callers."""
        now = time.monotonic()
        with self._lock:
            if self._resilient_telemetry is not None:
                return self._resilient_telemetry.has_fresh_valid_sample(now=now)
            return self.first_valid_at is not None

    def telemetry_snapshot(self) -> dict[str, Any]:
        """Return one synchronized, bounded view of the current telemetry state."""
        now = time.monotonic()
        with self._lock:
            if self._resilient_telemetry is not None:
                snapshot = self._resilient_telemetry.snapshot(now=now).to_dict()
                snapshot["mode"] = "resilient"
                snapshot["policy"] = asdict(self.wddm_policy)
                snapshot.update(self._sampler_lifecycle_locked())
                return snapshot
            last_valid_age = (
                max(0.0, now - self.last_valid_at)
                if self.last_valid_at is not None
                else None
            )
            maximum_gap = (
                max(self.maximum_valid_sample_gap_seconds, last_valid_age or 0.0)
                if self.last_valid_at is not None
                else None
            )
            failure = self._legacy_failure_reason_locked(now)
            snapshot = {
                "mode": "legacy",
                "policy": None,
                "failure_reason": failure,
                "admission_ready": self.first_valid_at is not None and failure is None,
                "has_valid_sample": self.first_valid_at is not None,
                "sample_count": self.sample_count,
                "peak_bytes": self.peak_bytes if self.sample_count else None,
                "first_valid_sample_seconds": (
                    max(0.0, self.first_valid_at - self.started_at)
                    if self.first_valid_at is not None
                    else None
                ),
                "last_valid_sample_age_seconds": last_valid_age,
                "maximum_valid_sample_gap_seconds": maximum_gap,
                "consecutive_failures": 0,
                "maximum_consecutive_failures": 0,
                "total_failures": len(self.failures),
                "recovered_gap_count": 0,
                "transient_gap_active": False,
                "exact_instances": tuple(sorted(self.instances)),
                "recent_failures": tuple(self.failures[-16:]),
            }
            return snapshot

    def _sampler_lifecycle_locked(self) -> dict[str, Any]:
        return {
            "sampler_stop_attempted": self._sampler_stop_attempted,
            "sampler_stop_timed_out": self._sampler_stop_timed_out,
            "sampler_stop_failure_reason": self._sampler_stop_failure_reason,
            "sampler_stop_wait_seconds": self._sampler_stop_wait_seconds,
            "sampler_stop_timeout_seconds": (
                WDDM_QUERY_TIMEOUT_SECONDS + WDDM_SAMPLER_STOP_MARGIN_SECONDS
            ),
            "sampler_thread_alive": bool(
                self._thread is not None and self._thread.is_alive()
            ),
        }

    def evidence(self, ceiling_mib: int) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            evidence = {
                "source": "Windows GPU Process Memory Dedicated Usage (PID-filtered)",
                "candidate_pid": self.pid,
                "counter_instances": sorted(self.instances),
                "sample_count": self.sample_count,
                "first_valid_sample_seconds": round(self.first_valid_at - self.started_at, 3) if self.first_valid_at else None,
                "peak_dedicated_bytes": self.peak_bytes if self.sample_count else None,
                "peak_dedicated_mib": round(self.peak_bytes / (1024 * 1024), 2) if self.sample_count else None,
                "ceiling_mib": ceiling_mib,
                "telemetry_failures": self.failures[-8:],
            }
            if self._resilient_telemetry is not None:
                evidence["resilience_policy"] = asdict(self.wddm_policy)
                evidence["sample_interval_seconds"] = self.interval_seconds
                telemetry_snapshot = self._resilient_telemetry.snapshot(now=now).to_dict()
                telemetry_snapshot["mode"] = "resilient"
                telemetry_snapshot["policy"] = asdict(self.wddm_policy)
                telemetry_snapshot.update(self._sampler_lifecycle_locked())
                evidence["telemetry_snapshot"] = telemetry_snapshot
                evidence.update(self._sampler_lifecycle_locked())
            return evidence
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


def run_harness(port: int, model: str, output: Path, args: list[str], timeout: int, abort_check=None) -> tuple[int, dict[str, Any]]:
    command = [sys.executable, str(ROOT / "scripts" / "baseline_harness.py"), f"--base-url=http://127.0.0.1:{port}/v1", f"--model={model}", "--output", str(output), *args]
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + timeout
    abort_reason: str | None = None
    while process.poll() is None:
        if abort_check:
            abort_reason = abort_check()
            if abort_reason:
                process.terminate()
                break
        if time.monotonic() >= deadline:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            raise NeoLoopError(f"benchmark timeout after {timeout}s")
        time.sleep(0.25)
    try:
        stdout, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
    if abort_reason:
        return 125, {"exit": 125, "aborted_reason": abort_reason, "stdout_tail": stdout.splitlines()[-8:], "stderr_tail": stderr.splitlines()[-8:]}
    result: dict[str, Any] = {"exit": process.returncode, "stdout_tail": stdout.splitlines()[-8:], "stderr_tail": stderr.splitlines()[-8:]}
    if output.is_file():
        result["report"] = load_json(output)
    return process.returncode, result


def gate_harness_args(gate: dict[str, Any], repeat: int, timeout: int) -> list[str]:
    args = [
        f"--prompt={gate['prompt']}",
        f"--expect-content={gate['expected_content']}",
        f"--max-tokens={gate['max_tokens']}",
        f"--temperature={gate['temperature']}",
        f"--repeat={repeat}",
        f"--timeout={timeout}",
    ]
    if gate["thinking_mode"] == "disabled":
        args.append("--disable-thinking")
    return args


def validate_smoke(report: dict[str, Any], require_reasoning: bool, min_tps: float | None) -> tuple[bool, str]:
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
    if min_tps is not None:
        tps = summary.get("median_reported_tokens_per_second")
        if not isinstance(tps, (int, float)) or tps < min_tps:
            return False, f"performance gate failed: {tps!r} TPS < {min_tps}"
    return True, "ok"


def validate_gate(report: dict[str, Any], gate: dict[str, Any], score_performance: bool) -> tuple[bool, str]:
    minimum = gate["min_decode_tps"] if score_performance else None
    return validate_smoke(report, gate["reasoning_required"], minimum)


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
    stable_port = evaluator["stable_launch"]["port"]
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
    process: subprocess.Popen[str] | None = None
    sampler: CandidateVramSampler | None = None
    evidence: dict[str, Any] = {"stable_health_before": True, "stable_listener_pids_before": sorted(stable_pids_before)}
    try:
        try:
            preflight_result = preflight(evaluator)
        except NeoLoopError as exc:
            return CycleResult("reject", str(exc), candidate_commit, evidence)
        evidence["preflight"] = {key: value for key, value in preflight_result.items() if key != "lock"}
        candidate_runtime.mkdir(parents=True, exist_ok=True)
        candidate_port = evaluator["candidate_launch"]["port"]
        build_script = CANDIDATE_ROOT / "scripts" / "build_candidate.ps1"
        build_rc, build_out, build_err = run_powershell(build_script, CANDIDATE_ROOT, timeouts["build_seconds"])
        evidence["build"] = build_failure_evidence(build_rc, build_out, build_err)
        if build_rc:
            return CycleResult("reject", "build-failure", candidate_commit, evidence)
        if not health_ok(stable_port, timeout=timeouts["stable_health_seconds"]):
            raise NeoLoopError("stable server died during candidate build")

        binary = CANDIDATE_BUILD_DIR / "bin" / "Release" / "llama-server.exe"
        model = os.environ.get("NEO3000_MODEL", "")
        if not binary.is_file() or not model or not Path(model).is_file():
            raise NeoLoopError("candidate binary or NEO3000_MODEL is unavailable")
        verify_model_identity(Path(model), evaluator)
        launch = evaluator["candidate_launch"]
        args = [str(binary), "--model", model, "--alias", launch["model_alias"], "--host", "127.0.0.1", "--port", str(candidate_port), "--ctx-size", str(launch["ctx_size"]), "--threads", str(launch["threads"]), "--threads-batch", str(launch["threads"]), "--batch-size", str(launch["batch"]), "--ubatch-size", str(launch["ubatch"]), "--gpu-layers", "auto", "--flash-attn", "auto", "--cache-type-k", "f16", "--cache-type-v", "f16", "--cache-prompt", "--metrics", "--no-webui", "--reasoning", "auto", "--cpu-moe"]
        environment = os.environ.copy()
        environment.update({"TMP": str(candidate_runtime), "TEMP": str(candidate_runtime), "TMPDIR": str(candidate_runtime)})
        process = subprocess.Popen(args, cwd=CANDIDATE_ROOT, env=environment, text=True)
        memory_config = evaluator["memory"]
        sampler = CandidateVramSampler(
            process.pid,
            memory_config["candidate_vram_mib_ceiling"],
            memory_config["sample_interval_seconds"],
            memory_config["telemetry_grace_seconds"],
        )
        sampler.start()

        def memory_gate() -> str | None:
            assert sampler is not None
            reason = sampler.failure_reason()
            if reason and process and process.poll() is None:
                process.terminate()
            return reason

        deadline = time.monotonic() + timeouts["candidate_health_seconds"]
        crashes = 0
        while time.monotonic() < deadline and not health_ok(candidate_port, timeout=3):
            if memory_gate():
                evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
                return CycleResult("reject", memory_gate() or "candidate-vram-telemetry-unavailable", candidate_commit, evidence)
            if process.poll() is not None:
                crashes += 1
                break
            time.sleep(2)
        if not health_ok(candidate_port, timeout=3):
            if crashes >= evaluator["crash_ceiling_per_cycle"]:
                return CycleResult("reject", "candidate-crash-ceiling", candidate_commit, evidence)
            return CycleResult("reject", "candidate-health-timeout", candidate_commit, evidence)
        telemetry_deadline = min(deadline, time.monotonic() + memory_config["telemetry_grace_seconds"])
        while not sampler.has_valid_sample() and time.monotonic() < telemetry_deadline:
            if memory_gate():
                evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
                return CycleResult("reject", memory_gate() or "candidate-vram-telemetry-unavailable", candidate_commit, evidence)
            time.sleep(0.25)
        if not sampler.has_valid_sample():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", "candidate-vram-telemetry-unavailable", candidate_commit, evidence)
        candidate_listener_pids = listener_pids(candidate_port)
        evidence["candidate_process_pid"] = process.pid
        evidence["candidate_listener_pids"] = sorted(candidate_listener_pids)
        if candidate_listener_pids != {process.pid}:
            return CycleResult("reject", "candidate-listener-pid-mismatch", candidate_commit, evidence)
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)

        gates = evaluator["gates"]
        transport_gate = gates["transport"]
        smoke_file = candidate_runtime / "transport.json"
        smoke_rc, smoke = run_harness(
            candidate_port,
            launch["model_alias"],
            smoke_file,
            gate_harness_args(transport_gate, transport_gate["counted_run_count"], timeouts["benchmark_seconds"]),
            timeouts["benchmark_seconds"],
            memory_gate,
        )
        evidence["transport"] = smoke
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)
        smoke_ok, smoke_reason = validate_gate(smoke.get("report", {}), transport_gate, False)
        if smoke_rc or not smoke_ok:
            return CycleResult("reject", smoke_reason, candidate_commit, evidence)

        reasoning_gate = gates["reasoning"]
        reasoning_file = candidate_runtime / "reasoning.json"
        reasoning_rc, reasoning = run_harness(
            candidate_port,
            launch["model_alias"],
            reasoning_file,
            gate_harness_args(reasoning_gate, reasoning_gate["counted_run_count"], timeouts["benchmark_seconds"]),
            timeouts["benchmark_seconds"],
            memory_gate,
        )
        evidence["reasoning"] = reasoning
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)
        reasoning_ok, reasoning_reason = validate_gate(reasoning.get("report", {}), reasoning_gate, False)
        if reasoning_rc or not reasoning_ok:
            return CycleResult("reject", reasoning_reason, candidate_commit, evidence)

        tool_file = candidate_runtime / "tool.json"
        tool_rc, tool = run_harness(candidate_port, launch["model_alias"], tool_file, ["--tool-test", "--repeat=1", "--max-tokens=512", f"--timeout={timeouts['benchmark_seconds']}"], timeouts["benchmark_seconds"], memory_gate)
        evidence["tool"] = tool
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)
        if tool_rc or not tool.get("report", {}).get("tool_call_passed"):
            return CycleResult("reject", "malformed-tool-call", candidate_commit, evidence)

        if not cancellation_gate(candidate_port, launch["model_alias"], timeouts["benchmark_seconds"]):
            return CycleResult("reject", "cancellation-regression", candidate_commit, evidence)
        repeat_gate = gates["repeat"]
        repeat_file = candidate_runtime / "repeat.json"
        repeat_rc, repeat = run_harness(
            candidate_port,
            launch["model_alias"],
            repeat_file,
            gate_harness_args(repeat_gate, repeat_gate["counted_run_count"], timeouts["benchmark_seconds"]),
            timeouts["benchmark_seconds"],
            memory_gate,
        )
        evidence["repeat"] = repeat
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)
        repeat_ok, repeat_reason = validate_gate(repeat.get("report", {}), repeat_gate, False)
        if repeat_rc or not repeat_ok:
            return CycleResult("reject", f"repeated-turn-regression: {repeat_reason}", candidate_commit, evidence)
        performance_gate = gates["warm_performance"]
        warmup_file = candidate_runtime / "warmup.json"
        warmup_rc, warmup = run_harness(
            candidate_port,
            launch["model_alias"],
            warmup_file,
            gate_harness_args(performance_gate, performance_gate["warmup_count"], timeouts["benchmark_seconds"]),
            timeouts["benchmark_seconds"],
            memory_gate,
        )
        evidence["warm_performance_warmup"] = warmup
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)
        warmup_ok, warmup_reason = validate_gate(warmup.get("report", {}), performance_gate, False)
        if warmup_rc or not warmup_ok:
            return CycleResult("reject", f"warmup-regression: {warmup_reason}", candidate_commit, evidence)
        performance_file = candidate_runtime / "warm-performance.json"
        performance_rc, performance = run_harness(
            candidate_port,
            launch["model_alias"],
            performance_file,
            gate_harness_args(performance_gate, performance_gate["counted_run_count"], timeouts["benchmark_seconds"]),
            timeouts["benchmark_seconds"],
            memory_gate,
        )
        evidence["warm_performance"] = performance
        if memory_gate():
            evidence["candidate_memory"] = sampler.evidence(memory_config["candidate_vram_mib_ceiling"])
            return CycleResult("reject", memory_gate() or "candidate-memory-ceiling", candidate_commit, evidence)
        performance_ok, performance_reason = validate_gate(performance.get("report", {}), performance_gate, True)
        if performance_rc or not performance_ok:
            return CycleResult("reject", performance_reason, candidate_commit, evidence)
        return CycleResult("reviewable-accept", "all-safety-and-quality-gates-passed", candidate_commit, evidence)
    finally:
        if sampler:
            sampler.stop()
            evidence["candidate_memory"] = sampler.evidence(evaluator["memory"]["candidate_vram_mib_ceiling"])
        evidence["cleanup"] = stop_candidate(process)
        shutil.rmtree(candidate_runtime, ignore_errors=True)
        evidence["candidate_runtime_removed"] = not candidate_runtime.exists()
        if not health_ok(stable_port, timeout=timeouts["stable_health_seconds"]):
            raise NeoLoopError("stable server died after candidate teardown")
        evidence["stable_health_after"] = True
        if listener_pids(stable_port) != stable_pids_before:
            raise NeoLoopError("stable listener changed during candidate cycle")
        evidence["stable_listener_unchanged"] = True
        if git(ROOT, "rev-parse", "HEAD") != stable_head_before or git(ROOT, "status", "--porcelain") != stable_status_before:
            raise NeoLoopError("stable worktree changed during candidate cycle")
        evidence["stable_worktree_unchanged"] = True
        verify_lock(evaluator)
        evidence["protected_hashes_after"] = True


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
        if args.preflight:
            print(json.dumps({"preflight": "reject", "reason": str(exc)}, indent=2))
            return 1
        result = CycleResult("reject", str(exc), "unknown", {})
    record = {"id": f"neo-loop-{utc_now().replace(':', '').replace('-', '')[:15]}", "timestamp": utc_now(), "hypothesis": args.hypothesis, "verdict": result.verdict, "reason": result.reason, "commit": result.commit, "evidence": result.evidence}
    print(json.dumps(record, indent=2))
    with RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return 0 if result.verdict == "reviewable-accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
