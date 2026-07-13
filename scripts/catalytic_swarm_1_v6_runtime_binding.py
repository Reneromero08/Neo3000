#!/usr/bin/env python3
"""Pre-persistence runtime identity rules for CatalyticSwarm-1 v6."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


V1_SCHEDULER_CONTRACT_SHA256 = "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e"
V5_PARTIAL_EXECUTION_BOUNDARY_SHA256 = "897148680e426caf58b9581f06224f904cb8ff5cd1a389b83c1ceedfc427f9d9"
V6_CLAIM_CONTRACT_SHA256 = "8136be5c402497b539595eeccf1329807eba59fab9813891f0293fd1d271acd8"
V6_RUNTIME_VERSION = "v6"
V6_SCHEMA_VERSION = 6
V6_ATTEMPT_VERSION = 6
V6_OPERATION = "catalytic-swarm-1-v6"
V6_VERDICT_KEY = "catalytic_swarm_1_v6"
V6_STATE_ROOT = "state/catalytic_swarm_1_v6"

ARTIFACT_PATHS = {
    "control": f"{V6_STATE_ROOT}/control-qualification-v6.json",
    "readiness": f"{V6_STATE_ROOT}/readiness-v6.json",
    "parser_canary": f"{V6_STATE_ROOT}/parser-canary-v6.json",
    "attempt": f"{V6_STATE_ROOT}/attempt-v6.json",
    "result": f"{V6_STATE_ROOT}/result-v6.json",
    "ledger": f"{V6_STATE_ROOT}/ledger-v6.jsonl",
    "task_results": f"{V6_STATE_ROOT}/task-results-v6.json",
}

STAGE_BINDINGS = {
    "control": {"operation": "catalytic-swarm-1-v6-control-qualification-v6", "verdict_field": "control_qualification_v6"},
    "readiness": {"operation": "catalytic-swarm-1-v6-readiness-v6", "verdict_field": "readiness_v6"},
    "parser_canary": {"operation": "catalytic-swarm-1-v6-parser-canary-v6", "verdict_field": "parser_canary_v6"},
    "attempt": {"operation": V6_OPERATION, "verdict_field": V6_VERDICT_KEY},
    "result": {"operation": V6_OPERATION, "verdict_field": V6_VERDICT_KEY},
    "ledger": {"operation": V6_OPERATION, "verdict_field": V6_VERDICT_KEY},
    "task_results": {"operation": "catalytic-swarm-1-v6-task-results", "verdict_field": V6_VERDICT_KEY},
}


class V6RuntimeBindingError(RuntimeError):
    """The active v6 runtime or persisted evidence identity is malformed."""


@dataclass(frozen=True)
class V6RuntimeBinding:
    runtime_version: str
    schema_version: int
    attempt_version: int
    operation: str
    verdict_key: str
    state_root: str
    predecessor_boundary_sha256: str
    claim_contract_evaluator_key: str
    claim_contract_lock_key: str
    claim_contract_sha256: str
    scheduler_contract_evaluator_key: str
    scheduler_contract_lock_key: str
    scheduler_contract_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_v6_runtime_binding() -> V6RuntimeBinding:
    return V6RuntimeBinding(
        runtime_version=V6_RUNTIME_VERSION,
        schema_version=V6_SCHEMA_VERSION,
        attempt_version=V6_ATTEMPT_VERSION,
        operation=V6_OPERATION,
        verdict_key=V6_VERDICT_KEY,
        state_root=V6_STATE_ROOT,
        predecessor_boundary_sha256=V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        claim_contract_evaluator_key="catalytic_swarm_1_v6",
        claim_contract_lock_key="catalytic_swarm_1_v6_sha256",
        claim_contract_sha256=V6_CLAIM_CONTRACT_SHA256,
        scheduler_contract_evaluator_key="catalytic_swarm_1",
        scheduler_contract_lock_key="catalytic_swarm_1_sha256",
        scheduler_contract_sha256=V1_SCHEDULER_CONTRACT_SHA256,
    )


def stage_identity(stage: str) -> dict[str, Any]:
    if stage not in STAGE_BINDINGS:
        raise V6RuntimeBindingError(f"unknown v6 artifact stage: {stage}")
    return {
        "runtime_version": V6_RUNTIME_VERSION,
        "schema_version": V6_SCHEMA_VERSION,
        "attempt_version": V6_ATTEMPT_VERSION,
        "operation": STAGE_BINDINGS[stage]["operation"],
        "verdict_field": STAGE_BINDINGS[stage]["verdict_field"],
        "claim_contract_sha256": V6_CLAIM_CONTRACT_SHA256,
        "scheduler_contract_sha256": V1_SCHEDULER_CONTRACT_SHA256,
        "predecessor_boundary_sha256": V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        "automatic_promotion": False,
    }


def validate_runtime_contract_bindings(
    evaluator: Mapping[str, Any], lock: Mapping[str, Any], *, object_sha256: Any
) -> dict[str, Any]:
    binding = build_v6_runtime_binding()
    claim = evaluator.get(binding.claim_contract_evaluator_key)
    scheduler = evaluator.get(binding.scheduler_contract_evaluator_key)
    if not isinstance(claim, Mapping) or not isinstance(scheduler, Mapping):
        raise V6RuntimeBindingError("v6 claim or scheduler contract is missing")
    observed_claim = str(object_sha256(claim)).lower()
    observed_scheduler = str(object_sha256(scheduler)).lower()
    if observed_claim != binding.claim_contract_sha256:
        raise V6RuntimeBindingError("v6 claim contract hash changed")
    if observed_scheduler != binding.scheduler_contract_sha256:
        raise V6RuntimeBindingError("v1 scheduler contract hash changed")
    if str(lock.get(binding.claim_contract_lock_key, "")).lower() != observed_claim:
        raise V6RuntimeBindingError("v6 claim contract lock binding changed")
    if str(lock.get(binding.scheduler_contract_lock_key, "")).lower() != observed_scheduler:
        raise V6RuntimeBindingError("v1 scheduler contract lock binding changed")
    return {"binding": binding.to_dict(), "claim_contract": dict(claim), "scheduler_contract": dict(scheduler)}


def _forbidden_keys() -> tuple[str, ...]:
    verdicts = tuple(["catalytic_swarm_1"] + [f"catalytic_swarm_1_v{version}" for version in range(2, 6)])
    stage_verdicts = tuple(
        f"{prefix}_v{version}"
        for prefix in ("control_qualification", "readiness", "parser_canary")
        for version in range(1, 6)
    )
    return verdicts + stage_verdicts


def apply_stage_identity(record: Mapping[str, Any], stage: str) -> dict[str, Any]:
    value = dict(record)
    leaked = sorted(set(_forbidden_keys()) & set(value))
    if leaked:
        raise V6RuntimeBindingError("v6 artifact retained predecessor key: " + ", ".join(leaked))
    identity = stage_identity(stage)
    value.update({
        "runtime_version": identity["runtime_version"],
        "schema_version": identity["schema_version"],
        "attempt_version": identity["attempt_version"],
        "operation": identity["operation"],
        "claim_contract_sha256": identity["claim_contract_sha256"],
        "scheduler_contract_sha256": identity["scheduler_contract_sha256"],
        "predecessor_boundary_sha256": identity["predecessor_boundary_sha256"],
        "automatic_promotion": False,
    })
    value.setdefault(identity["verdict_field"], "inconclusive")
    return value


def validate_persisted_v6_record(record: Mapping[str, Any], stage: str) -> None:
    if not isinstance(record, Mapping):
        raise V6RuntimeBindingError("v6 persisted record must be an object")
    identity = stage_identity(stage)
    checks = {
        "runtime_version": record.get("runtime_version") == identity["runtime_version"],
        "schema_version": record.get("schema_version") == identity["schema_version"],
        "attempt_version": record.get("attempt_version") == identity["attempt_version"],
        "operation": record.get("operation") == identity["operation"],
        "claim_contract_sha256": str(record.get("claim_contract_sha256", "")).lower() == identity["claim_contract_sha256"],
        "scheduler_contract_sha256": str(record.get("scheduler_contract_sha256", "")).lower() == identity["scheduler_contract_sha256"],
        "predecessor_boundary_sha256": str(record.get("predecessor_boundary_sha256", "")).lower() == identity["predecessor_boundary_sha256"],
        "automatic_promotion": record.get("automatic_promotion") is False,
        "verdict_field": identity["verdict_field"] in record,
        "predecessor_keys_absent": not any(key in record for key in _forbidden_keys()),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise V6RuntimeBindingError("v6 persisted evidence identity failed: " + ", ".join(failed))


def rename_v6_result_after_persistence(*_: Any, **__: Any) -> None:
    raise V6RuntimeBindingError("post-persistence verdict renaming is forbidden; persist v6 identity directly")
