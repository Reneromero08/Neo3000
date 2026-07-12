#!/usr/bin/env python3
"""Pre-persistence runtime identity rules for CatalyticSwarm-1 v4."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


V1_SCHEDULER_CONTRACT_SHA256 = "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e"
V4_CLAIM_CONTRACT_SHA256 = "2ba862a097da4b3c6bb2e2fbececa49296b38a8c9b5b047f6c281b84c3111ece"
V4_RUNTIME_VERSION = "v4"
V4_SCHEMA_VERSION = 4
V4_ATTEMPT_VERSION = 4
V4_OPERATION = "catalytic-swarm-1-v4"
V4_VERDICT_KEY = "catalytic_swarm_1_v4"
V4_STATE_ROOT = "state/catalytic_swarm_1_v4"

STAGE_BINDINGS = {
    "control": {"operation": "catalytic-swarm-1-v4-control-qualification-v4", "verdict_field": "control_qualification_v4"},
    "readiness": {"operation": "catalytic-swarm-1-v4-readiness-v4", "verdict_field": "readiness_v4"},
    "parser_canary": {"operation": "catalytic-swarm-1-v4-parser-canary-v4", "verdict_field": "parser_canary_v4"},
    "attempt": {"operation": V4_OPERATION, "verdict_field": V4_VERDICT_KEY},
    "result": {"operation": V4_OPERATION, "verdict_field": V4_VERDICT_KEY},
    "task_results": {"operation": "catalytic-swarm-1-v4-task-results", "verdict_field": V4_VERDICT_KEY},
}


class V4RuntimeBindingError(RuntimeError):
    """The active v4 runtime or persisted evidence identity is malformed."""


@dataclass(frozen=True)
class V4RuntimeBinding:
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


def build_v4_runtime_binding() -> V4RuntimeBinding:
    return V4RuntimeBinding(
        runtime_version=V4_RUNTIME_VERSION,
        schema_version=V4_SCHEMA_VERSION,
        attempt_version=V4_ATTEMPT_VERSION,
        operation=V4_OPERATION,
        verdict_key=V4_VERDICT_KEY,
        state_root=V4_STATE_ROOT,
        claim_contract_evaluator_key="catalytic_swarm_1_v4",
        claim_contract_lock_key="catalytic_swarm_1_v4_sha256",
        claim_contract_sha256=V4_CLAIM_CONTRACT_SHA256,
        scheduler_contract_evaluator_key="catalytic_swarm_1",
        scheduler_contract_lock_key="catalytic_swarm_1_sha256",
        scheduler_contract_sha256=V1_SCHEDULER_CONTRACT_SHA256,
    )


def stage_identity(stage: str) -> dict[str, Any]:
    if stage not in STAGE_BINDINGS:
        raise V4RuntimeBindingError(f"unknown v4 artifact stage: {stage}")
    return {
        "schema_version": V4_SCHEMA_VERSION,
        "attempt_version": V4_ATTEMPT_VERSION,
        "operation": STAGE_BINDINGS[stage]["operation"],
        "verdict_field": STAGE_BINDINGS[stage]["verdict_field"],
        "claim_contract_sha256": V4_CLAIM_CONTRACT_SHA256,
        "scheduler_contract_sha256": V1_SCHEDULER_CONTRACT_SHA256,
        "automatic_promotion": False,
    }


def validate_runtime_contract_bindings(
    evaluator: Mapping[str, Any], lock: Mapping[str, Any], *, object_sha256: Any
) -> dict[str, Any]:
    binding = build_v4_runtime_binding()
    claim = evaluator.get(binding.claim_contract_evaluator_key)
    scheduler = evaluator.get(binding.scheduler_contract_evaluator_key)
    if not isinstance(claim, Mapping) or not isinstance(scheduler, Mapping):
        raise V4RuntimeBindingError("v4 claim or scheduler contract is missing")
    observed_claim = str(object_sha256(claim)).lower()
    observed_scheduler = str(object_sha256(scheduler)).lower()
    if observed_claim != binding.claim_contract_sha256:
        raise V4RuntimeBindingError("v4 claim contract hash changed")
    if observed_scheduler != binding.scheduler_contract_sha256:
        raise V4RuntimeBindingError("v1 scheduler contract hash changed")
    if str(lock.get(binding.claim_contract_lock_key, "")).lower() != observed_claim:
        raise V4RuntimeBindingError("v4 claim contract lock binding changed")
    if str(lock.get(binding.scheduler_contract_lock_key, "")).lower() != observed_scheduler:
        raise V4RuntimeBindingError("v1 scheduler contract lock binding changed")
    return {"binding": binding.to_dict(), "claim_contract": dict(claim), "scheduler_contract": dict(scheduler)}


def apply_stage_identity(record: Mapping[str, Any], stage: str) -> dict[str, Any]:
    value = dict(record)
    identity = stage_identity(stage)
    predecessor_stage_fields = {
        f"{prefix}_{version}"
        for prefix in ("control_qualification", "readiness", "parser_canary")
        for version in ("v1", "v2", "v3")
    }
    leaked_stage_fields = sorted(predecessor_stage_fields & set(value))
    if leaked_stage_fields:
        raise V4RuntimeBindingError(
            "v4 artifact retained forbidden predecessor stage verdict field: "
            + ", ".join(leaked_stage_fields)
        )
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
    for forbidden in ("catalytic_swarm_1", "catalytic_swarm_1_v2", "catalytic_swarm_1_v3"):
        if forbidden in value and forbidden != verdict_field:
            raise V4RuntimeBindingError(f"v4 artifact retained forbidden predecessor verdict field: {forbidden}")
    return value


def validate_persisted_v4_record(record: Mapping[str, Any], stage: str) -> None:
    if not isinstance(record, Mapping):
        raise V4RuntimeBindingError("v4 persisted record must be an object")
    identity = stage_identity(stage)
    checks = {
        "schema_version": record.get("schema_version") == identity["schema_version"],
        "attempt_version": record.get("attempt_version") == identity["attempt_version"],
        "operation": record.get("operation") == identity["operation"],
        "claim_contract_sha256": str(record.get("claim_contract_sha256", "")).lower() == identity["claim_contract_sha256"],
        "scheduler_contract_sha256": str(record.get("scheduler_contract_sha256", "")).lower() == identity["scheduler_contract_sha256"],
        "automatic_promotion": record.get("automatic_promotion") is False,
        "verdict_field": identity["verdict_field"] in record,
        "predecessor_verdict_absent": all(key not in record for key in ("catalytic_swarm_1", "catalytic_swarm_1_v2", "catalytic_swarm_1_v3")),
        "predecessor_stage_verdict_absent": not any(
            key in record
            for key in (
                "control_qualification_v1", "control_qualification_v2", "control_qualification_v3",
                "readiness_v1", "readiness_v2", "readiness_v3",
                "parser_canary_v1", "parser_canary_v2", "parser_canary_v3",
            )
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise V4RuntimeBindingError("v4 persisted evidence identity failed: " + ", ".join(failed))


def rename_v4_result_after_persistence(*_: Any, **__: Any) -> None:
    raise V4RuntimeBindingError("post-persistence verdict renaming is forbidden; persist v4 identity directly")
