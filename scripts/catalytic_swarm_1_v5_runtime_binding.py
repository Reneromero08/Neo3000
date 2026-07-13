#!/usr/bin/env python3
"""Pre-persistence runtime identity rules for CatalyticSwarm-1 v5."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


V1_SCHEDULER_CONTRACT_SHA256 = "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e"
V5_CLAIM_CONTRACT_SHA256 = "6238ff09ba290e55ad6c5cc2c93b4cbc239d573644192cf101696416a7083e3c"
V5_RUNTIME_VERSION = "v5"
V5_SCHEMA_VERSION = 5
V5_ATTEMPT_VERSION = 5
V5_OPERATION = "catalytic-swarm-1-v5"
V5_VERDICT_KEY = "catalytic_swarm_1_v5"
V5_STATE_ROOT = "state/catalytic_swarm_1_v5"

STAGE_BINDINGS = {
    "control": {"operation": "catalytic-swarm-1-v5-control-qualification-v5", "verdict_field": "control_qualification_v5"},
    "readiness": {"operation": "catalytic-swarm-1-v5-readiness-v5", "verdict_field": "readiness_v5"},
    "parser_canary": {"operation": "catalytic-swarm-1-v5-parser-canary-v5", "verdict_field": "parser_canary_v5"},
    "attempt": {"operation": V5_OPERATION, "verdict_field": V5_VERDICT_KEY},
    "result": {"operation": V5_OPERATION, "verdict_field": V5_VERDICT_KEY},
    "task_results": {"operation": "catalytic-swarm-1-v5-task-results", "verdict_field": V5_VERDICT_KEY},
}


class V5RuntimeBindingError(RuntimeError):
    """The active v5 runtime or persisted evidence identity is malformed."""


@dataclass(frozen=True)
class V5RuntimeBinding:
    runtime_version: str
    schema_version: int
    attempt_version: int
    operation: str
    verdict_key: str
    state_root: str
    claim_contract_evaluator_key: str
    claim_contract_lock_key: str
    claim_contract_sha256: str
    scheduler_contract_evaluator_key: str
    scheduler_contract_lock_key: str
    scheduler_contract_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_v5_runtime_binding() -> V5RuntimeBinding:
    return V5RuntimeBinding(
        runtime_version=V5_RUNTIME_VERSION,
        schema_version=V5_SCHEMA_VERSION,
        attempt_version=V5_ATTEMPT_VERSION,
        operation=V5_OPERATION,
        verdict_key=V5_VERDICT_KEY,
        state_root=V5_STATE_ROOT,
        claim_contract_evaluator_key="catalytic_swarm_1_v5",
        claim_contract_lock_key="catalytic_swarm_1_v5_sha256",
        claim_contract_sha256=V5_CLAIM_CONTRACT_SHA256,
        scheduler_contract_evaluator_key="catalytic_swarm_1",
        scheduler_contract_lock_key="catalytic_swarm_1_sha256",
        scheduler_contract_sha256=V1_SCHEDULER_CONTRACT_SHA256,
    )


def stage_identity(stage: str) -> dict[str, Any]:
    if stage not in STAGE_BINDINGS:
        raise V5RuntimeBindingError(f"unknown v5 artifact stage: {stage}")
    return {
        "schema_version": V5_SCHEMA_VERSION,
        "attempt_version": V5_ATTEMPT_VERSION,
        "operation": STAGE_BINDINGS[stage]["operation"],
        "verdict_field": STAGE_BINDINGS[stage]["verdict_field"],
        "claim_contract_sha256": V5_CLAIM_CONTRACT_SHA256,
        "scheduler_contract_sha256": V1_SCHEDULER_CONTRACT_SHA256,
        "automatic_promotion": False,
    }


def validate_runtime_contract_bindings(
    evaluator: Mapping[str, Any], lock: Mapping[str, Any], *, object_sha256: Any
) -> dict[str, Any]:
    binding = build_v5_runtime_binding()
    claim = evaluator.get(binding.claim_contract_evaluator_key)
    scheduler = evaluator.get(binding.scheduler_contract_evaluator_key)
    if not isinstance(claim, Mapping) or not isinstance(scheduler, Mapping):
        raise V5RuntimeBindingError("v5 claim or scheduler contract is missing")
    observed_claim = str(object_sha256(claim)).lower()
    observed_scheduler = str(object_sha256(scheduler)).lower()
    if observed_claim != binding.claim_contract_sha256:
        raise V5RuntimeBindingError("v5 claim contract hash changed")
    if observed_scheduler != binding.scheduler_contract_sha256:
        raise V5RuntimeBindingError("v1 scheduler contract hash changed")
    if str(lock.get(binding.claim_contract_lock_key, "")).lower() != observed_claim:
        raise V5RuntimeBindingError("v5 claim contract lock binding changed")
    if str(lock.get(binding.scheduler_contract_lock_key, "")).lower() != observed_scheduler:
        raise V5RuntimeBindingError("v1 scheduler contract lock binding changed")
    return {"binding": binding.to_dict(), "claim_contract": dict(claim), "scheduler_contract": dict(scheduler)}


def apply_stage_identity(record: Mapping[str, Any], stage: str) -> dict[str, Any]:
    value = dict(record)
    identity = stage_identity(stage)
    forbidden_stage_fields = {
        f"{prefix}_{version}"
        for prefix in ("control_qualification", "readiness", "parser_canary")
        for version in ("v1", "v2", "v3", "v4")
    }
    leaked = sorted(forbidden_stage_fields & set(value))
    if leaked:
        raise V5RuntimeBindingError("v5 artifact retained predecessor stage verdict field: " + ", ".join(leaked))
    value.update({
        "schema_version": identity["schema_version"],
        "attempt_version": identity["attempt_version"],
        "operation": identity["operation"],
        "claim_contract_sha256": identity["claim_contract_sha256"],
        "scheduler_contract_sha256": identity["scheduler_contract_sha256"],
        "automatic_promotion": False,
    })
    verdict_field = identity["verdict_field"]
    value.setdefault(verdict_field, "inconclusive")
    for forbidden in ("catalytic_swarm_1", "catalytic_swarm_1_v2", "catalytic_swarm_1_v3", "catalytic_swarm_1_v4"):
        if forbidden in value:
            raise V5RuntimeBindingError(f"v5 artifact retained predecessor verdict field: {forbidden}")
    return value


def validate_persisted_v5_record(record: Mapping[str, Any], stage: str) -> None:
    if not isinstance(record, Mapping):
        raise V5RuntimeBindingError("v5 persisted record must be an object")
    identity = stage_identity(stage)
    checks = {
        "schema_version": record.get("schema_version") == identity["schema_version"],
        "attempt_version": record.get("attempt_version") == identity["attempt_version"],
        "operation": record.get("operation") == identity["operation"],
        "claim_contract_sha256": str(record.get("claim_contract_sha256", "")).lower() == identity["claim_contract_sha256"],
        "scheduler_contract_sha256": str(record.get("scheduler_contract_sha256", "")).lower() == identity["scheduler_contract_sha256"],
        "automatic_promotion": record.get("automatic_promotion") is False,
        "verdict_field": identity["verdict_field"] in record,
        "predecessor_verdict_absent": all(key not in record for key in ("catalytic_swarm_1", "catalytic_swarm_1_v2", "catalytic_swarm_1_v3", "catalytic_swarm_1_v4")),
        "predecessor_stage_verdict_absent": not any(
            key in record
            for key in (
                "control_qualification_v1", "control_qualification_v2", "control_qualification_v3", "control_qualification_v4",
                "readiness_v1", "readiness_v2", "readiness_v3", "readiness_v4",
                "parser_canary_v1", "parser_canary_v2", "parser_canary_v3", "parser_canary_v4",
            )
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise V5RuntimeBindingError("v5 persisted evidence identity failed: " + ", ".join(failed))


def rename_v5_result_after_persistence(*_: Any, **__: Any) -> None:
    raise V5RuntimeBindingError("post-persistence verdict renaming is forbidden; persist v5 identity directly")
