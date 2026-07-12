#!/usr/bin/env python3
"""Canonical tracked binding for the consumed CS1-v3 preclaim failure."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256 = (
    "fb8d4270320f73e9307da5b67325cc30edeaab04e7e1ac4a01068a5a94107e14"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_catalytic_swarm_1_v3_preclaim_boundary() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v3_preclaim_boundary",
        "schema_version": 1,
        "protected_main": "16d0f439936188391b984df50deebd16734aca4f",
        "contracts": {
            "claim_contract_sha256": "433b4d4e418614c2e9c2b177f46b68d24710921b11d8d7e848a226da22c1fd27",
            "runtime_evidence_binding_sha256": "09d3c7753d3840b568d85642791425931dedc7bd34c017a16e84e606b7d3d681",
            "scheduler_contract_sha256": "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e",
        },
        "command": {
            "name": "audit-catalytic-swarm-1-v3",
            "invocation_count": 1,
            "authority_consumed": True,
            "retry_count": 0,
            "no_retry": True,
        },
        "stop": {
            "stage": "preclaim",
            "error": "NeoLoopError: CatalyticSwarm-1 v3 one-shot path law changed: one-shot key order or cardinality changed",
            "controller_message": "CatalyticSwarm-1 v3 one-shot path law changed: one-shot key order or cardinality changed",
            "causal_classification": "insertion-order-sensitive-one-shot-mapping-admission",
            "cause": "the evaluator contains the exact seven semantic path keys in sorted JSON order while v3 admission requires mapping iteration order to equal runtime stage order",
            "fail_closed": True,
            "experiment_adjudicated": False,
        },
        "runtime": {
            "model_path_supplied": True,
            "model_identity": {
                "filename": "Agents-A1-Q4_K_M.gguf",
                "size_bytes": 21166757632,
                "sha256": "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2",
            },
            "binary_identity": {
                "path": "build/stable/bin/Release/llama-server.exe",
                "runtime_version": "13 (417e1d6)",
                "sha256": "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B",
            },
            "model_requests": 0,
            "sidecar_launches": 0,
            "warm_requests": 0,
            "comparison_requests": 0,
            "completed_arms": 0,
            "completed_tasks": 0,
            "wddm_sampling": "not-started",
            "automatic_promotion": False,
        },
        "artifact": {
            "path": "state/catalytic_swarm_1_v3/control-qualification-v3.json",
            "size_bytes": 960,
            "sha256": "FCAD4C71807DCC61409A09720A092DD50D8DD96AB76A8946BF418EEBF74DE8A6",
        },
        "absent_artifact_paths": [
            "state/catalytic_swarm_1_v3/readiness-v3.json",
            "state/catalytic_swarm_1_v3/parser-canary-v3.json",
            "state/catalytic_swarm_1_v3/attempt-v3.json",
            "state/catalytic_swarm_1_v3/result-v3.json",
            "state/catalytic_swarm_1_v3/ledger-v3.jsonl",
            "state/catalytic_swarm_1_v3/task-results-v3.json",
        ],
        "custody": {
            "tracked_worktree_clean": True,
            "stable": {
                "pid": 32684,
                "port": 9292,
                "health_ok": True,
                "listener_preserved": True,
            },
            "candidate": {
                "head": "14de9c71593e5aea4fcfcadeda47ba5c623fadcf",
                "clean": True,
            },
            "candidate_port_9393_free": True,
            "sidecar_port_9494_free": True,
        },
        "claims": {
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_catalytic_swarm_1_v3_preclaim_boundary(
    value: Mapping[str, Any],
) -> None:
    expected = build_catalytic_swarm_1_v3_preclaim_boundary()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v3 preclaim boundary differs from canonical")
    if sha256_object(value) != EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256:
        raise ValueError("CS1-v3 preclaim boundary hash drifted")
