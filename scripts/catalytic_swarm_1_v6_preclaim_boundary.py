#!/usr/bin/env python3
"""Canonical tracked binding for the consumed CS1-v6 preclaim boundary."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v3_preclaim_boundary import (
    EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v3_preclaim_boundary,
)
from catalytic_swarm_1_v4_partial_execution_boundary import (
    EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v4_partial_execution_boundary,
)
from catalytic_swarm_1_v5_partial_execution_boundary import (
    EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v5_partial_execution_boundary,
)


# Frozen after canonical construction; always lowercase by contract.
EXPECTED_V6_PRECLAIM_BOUNDARY_SHA256 = (
    "64c296f8332afc2fd224fc9d3510c2d12395d5d4c9cdc7955b659fadaa2f8eb3"
)

V6_PROTECTED_MAIN = "ef8caa5c0132d1581321d8ba9fd9643a8d246fbb"
V6_CLAIM_CONTRACT_SHA256 = (
    "8136be5c402497b539595eeccf1329807eba59fab9813891f0293fd1d271acd8"
)
V6_RUNTIME_EVIDENCE_BINDING_SHA256 = (
    "3ccb810684824a5935c89150e0f84ca820f8402f7650d3fdcf027e84ac9f9ad3"
)
V6_SCHEDULER_CONTRACT_SHA256 = (
    "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e"
)
V6_CLASSIFICATION = (
    "HARNESS SELF-CONTAMINATION / PRE-INFERENCE / "
    "SCIENTIFICALLY NON-ADJUDICATING"
)

V6_CONTROL_ARTIFACT_PATH = (
    "state/catalytic_swarm_1_v6/control-qualification-v6.json"
)
V6_CONTROL_ARTIFACT_SIZE_BYTES = 1577
V6_CONTROL_ARTIFACT_SHA256 = (
    "9172468FB5D102C36BC78E553C8FD804394C4BE5FFE98E94CA18314F1E2BC9A4"
)

V6_ABSENT_ARTIFACT_PATHS = (
    "state/catalytic_swarm_1_v6/readiness-v6.json",
    "state/catalytic_swarm_1_v6/parser-canary-v6.json",
    "state/catalytic_swarm_1_v6/attempt-v6.json",
    "state/catalytic_swarm_1_v6/result-v6.json",
    "state/catalytic_swarm_1_v6/ledger-v6.jsonl",
    "state/catalytic_swarm_1_v6/task-results-v6.json",
)

V6_EXACT_COMMAND_ARGV_SHA256 = (
    "0181781a6be0e2c96b0cecfecccd669d172fdb477609f9ae63214840083c3861"
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


def _predecessor_preservation() -> dict[str, Any]:
    v3 = build_catalytic_swarm_1_v3_preclaim_boundary()
    v4 = build_catalytic_swarm_1_v4_partial_execution_boundary()
    v5 = build_catalytic_swarm_1_v5_partial_execution_boundary()
    return {
        "v3": {
            "boundary_id": v3["id"],
            "boundary_sha256": EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
            "artifact": copy.deepcopy(v3["artifact"]),
            "absent_artifact_paths": copy.deepcopy(v3["absent_artifact_paths"]),
        },
        "v4": {
            "boundary_id": v4["id"],
            "boundary_sha256": EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
            "artifacts": copy.deepcopy(v4["artifacts"]),
        },
        "v5": {
            "boundary_id": v5["id"],
            "boundary_sha256": EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
            "artifacts": copy.deepcopy(v5["artifacts"]),
        },
    }


def build_catalytic_swarm_1_v6_preclaim_boundary() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v6_preclaim_boundary",
        "schema_version": 1,
        "protected_main": V6_PROTECTED_MAIN,
        "protected_execution_commit": V6_PROTECTED_MAIN,
        "contracts": {
            "claim_contract_sha256": V6_CLAIM_CONTRACT_SHA256,
            "runtime_evidence_binding_sha256": V6_RUNTIME_EVIDENCE_BINDING_SHA256,
            "scheduler_contract_sha256": V6_SCHEDULER_CONTRACT_SHA256,
        },
        "command": {
            "name": "audit-catalytic-swarm-1-v6",
            "argv_shape": [
                "python",
                "-B",
                "scripts/holostate_live.py",
                "audit-catalytic-swarm-1-v6",
                "--binary",
                "<path-bound-by-sha256>",
                "--model",
                "<path-bound-by-sha256>",
                "--authorized-main",
                V6_PROTECTED_MAIN,
            ],
            "argv_hash_mode": "canonical-json-utf8-v1",
            "exact_argv_sha256": V6_EXACT_COMMAND_ARGV_SHA256,
            "local_path_values_committed": False,
            "invocation_count": 1,
            "authority_consumed": True,
            "retry_count": 0,
            "no_retry": True,
            "retired": True,
        },
        "timestamps": {
            "shell_start_utc": "2026-07-13T05:06:47.9147053Z",
            "controller_start_utc": "2026-07-13T05:06:48.342436+00:00",
            "controller_finish_utc": "2026-07-13T05:07:07.630329+00:00",
            "shell_finish_utc": "2026-07-13T05:07:07.6718445Z",
        },
        "identities": {
            "status": "supplied-but-unverified",
            "verification_reached": False,
            "supplied_path_hash_mode": "utf8-v1",
            "claim_contract_sha256": V6_CLAIM_CONTRACT_SHA256,
            "runtime_evidence_binding_sha256": V6_RUNTIME_EVIDENCE_BINDING_SHA256,
            "scheduler_contract_sha256": V6_SCHEDULER_CONTRACT_SHA256,
            "predecessor_v5_boundary_sha256": EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
            "model": {
                "status": "supplied-but-unverified",
                "path_supplied": True,
                "verified_during_v6": False,
                "file_name": "Agents-A1-Q4_K_M.gguf",
                "supplied_path_sha256": "300e48320ae5763140dc0d6f45a583a6f9fe499e3b4a98a2f7163fc6d6e8d123",
                "size_bytes": 21166757632,
                "sha256": "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2",
            },
            "binary": {
                "status": "supplied-but-unverified",
                "path_supplied": True,
                "verified_during_v6": False,
                "file_name": "llama-server.exe",
                "supplied_path_sha256": "2a6a09cdc80ba83d90f80340ead2b437df421c4ab378e7942f9febbb6577b0bb",
                "version": "13 (417e1d6)",
                "sha256": "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B",
            },
        },
        "outcome": {
            "process_exit_code": 1,
            "status": "complete",
            "control_qualification": "inconclusive",
            "error": "NeoLoopError: CatalyticSwarm-1 requires a clean stable worktree",
            "failure_stage": "runtime-preclaim",
            "classification": V6_CLASSIFICATION,
            "fail_closed": True,
            "experiment_adjudicated": False,
            "task_advantage_adjudicated": False,
        },
        "runtime": {
            "live_model_requests": 0,
            "model_requests": 0,
            "completed_model_responses": 0,
            "sidecar_launches": 0,
            "common_root_warms": 0,
            "comparison_requests": 0,
            "completed_arms": 0,
            "completed_tasks": 0,
            "wddm_sampling": "not-started",
            "deep_requests": 0,
            "automatic_promotion": False,
        },
        "artifact": {
            "stage": "control",
            "path": V6_CONTROL_ARTIFACT_PATH,
            "size_bytes": V6_CONTROL_ARTIFACT_SIZE_BYTES,
            "sha256": V6_CONTROL_ARTIFACT_SHA256,
            "preserve_raw_bytes": True,
            "started_at": "2026-07-13T05:06:48.342436+00:00",
            "finished_at": "2026-07-13T05:07:07.630329+00:00",
        },
        "absent_artifact_paths": list(V6_ABSENT_ARTIFACT_PATHS),
        "custody": {
            "stable": {
                "pid": 32684,
                "port": 9292,
            },
            "candidate": {
                "commit": "14de9c71593e5aea4fcfcadeda47ba5c623fadcf",
            },
            "ordinary_status_after_claim_before_ignore_repair": [
                f"?? {V6_CONTROL_ARTIFACT_PATH}"
            ],
            "tracked_status_after_claim_before_ignore_repair": [],
            "preclaim_status_snapshot": "not-recorded-by-v6-harness",
            "causal_attribution": (
                "the harness claimed its control artifact before the clean-worktree "
                "gate while the active V6 evidence root was not ignored"
            ),
            "repair_law": (
                "capture clean ordinary and tracked status before claim; hash every "
                "historical CS1 namespace; after claim admit only exact authorized "
                "V6 paths and explicitly inventory ignored evidence"
            ),
        },
        "causal_diagnosis": {
            "directly_observed": (
                "the exact preserved control artifact records one consumed no-retry "
                "invocation, a clean-stable-worktree error, and zero model requests "
                "and sidecar launches"
            ),
            "statically_proved": (
                "protected main claims the V6 control artifact before calling the "
                "V6 prepare path whose shared preclaim gate reads ordinary Git status"
            ),
            "cause": (
                "the newly claimed V6 marker was ordinary untracked state because "
                "the protected ignore policy ended at V5, so the harness contaminated "
                "the cleanliness gate with its own evidence before inference"
            ),
            "unavailable": (
                "runtime verification of the supplied model and binary identities; "
                "the preclaim failure occurred before either identity was verified"
            ),
            "defect": "runtime-marker-claim-before-preclaim-cleanliness-capture",
            "scientific_interpretation": V6_CLASSIFICATION,
        },
        "predecessor_preservation": _predecessor_preservation(),
        "claims": {
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_catalytic_swarm_1_v6_preclaim_boundary(
    value: Mapping[str, Any],
) -> None:
    expected = build_catalytic_swarm_1_v6_preclaim_boundary()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v6 preclaim boundary differs from canonical")
    observed = sha256_object(value)
    if observed != EXPECTED_V6_PRECLAIM_BOUNDARY_SHA256:
        raise ValueError(
            "CS1-v6 preclaim boundary hash drifted: "
            f"{observed} != {EXPECTED_V6_PRECLAIM_BOUNDARY_SHA256}"
        )
    if observed != observed.lower():
        raise ValueError("CS1-v6 preclaim boundary hash must be lowercase")
