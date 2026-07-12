#!/usr/bin/env python3
"""Pure version-aware runtime identity rules for CatalyticSwarm-1 v3.

This module performs no filesystem, network, Git, process, or model operation.
It prevents the v3 runner from persisting v1-labelled evidence while reusing
the immutable v1 evaluation scheduler.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

V1_SCHEDULER_CONTRACT_SHA256 = (
    "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e"
)
V3_CLAIM_CONTRACT_SHA256 = (
    "433b4d4e418614c2e9c2b177f46b68d24710921b11d8d7e848a226da22c1fd27"
)
V3_EVALUATOR_KEY = "catalytic_swarm_1_v3"
V3_LOCK_KEY = "catalytic_swarm_1_v3_sha256"
V1_SCHEDULER_EVALUATOR_KEY = "catalytic_swarm_1"
V1_SCHEDULER_LOCK_KEY = "catalytic_swarm_1_sha256"
V3_RUNTIME_VERSION = "v3"
V3_SCHEMA_VERSION = 3
V3_ATTEMPT_VERSION = 3
V3_OPERATION = "catalytic-swarm-1-v3"
V3_VERDICT_KEY = "catalytic_swarm_1_v3"
V3_STATE_ROOT = "state/catalytic_swarm_1_v3"

STAGE_BINDINGS = {
    "control": {
        "operation": "catalytic-swarm-1-v3-control-qualification-v3",
        "verdict_field": "control_qualification_v3",
    },
    "readiness": {
        "operation": "catalytic-swarm-1-v3-readiness-v3",
        "verdict_field": "readiness_v3",
    },
    "parser_canary": {
        "operation": "catalytic-swarm-1-v3-parser-canary-v3",
        "verdict_field": "parser_canary_v3",
    },
    "attempt": {
        "operation": V3_OPERATION,
        "verdict_field": V3_VERDICT_KEY,
    },
    "result": {
        "operation": V3_OPERATION,
        "verdict_field": V3_VERDICT_KEY,
    },
    "task_results": {
        "operation": "catalytic-swarm-1-v3-task-results",
        "verdict_field": V3_VERDICT_KEY,
    },
}


class V3RuntimeBindingError(RuntimeError):
    """The active v3 runtime or persisted evidence identity is malformed."""


@dataclass(frozen=True)
class V3RuntimeBinding:
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


def build_v3_runtime_binding() -> V3RuntimeBinding:
    return V3RuntimeBinding(
        runtime_version=V3_RUNTIME_VERSION,
        schema_version=V3_SCHEMA_VERSION,
        attempt_version=V3_ATTEMPT_VERSION,
        operation=V3_OPERATION,
        verdict_key=V3_VERDICT_KEY,
        state_root=V3_STATE_ROOT,
        claim_contract_evaluator_key=V3_EVALUATOR_KEY,
        claim_contract_lock_key=V3_LOCK_KEY,
        claim_contract_sha256=V3_CLAIM_CONTRACT_SHA256,
        scheduler_contract_evaluator_key=V1_SCHEDULER_EVALUATOR_KEY,
        scheduler_contract_lock_key=V1_SCHEDULER_LOCK_KEY,
        scheduler_contract_sha256=V1_SCHEDULER_CONTRACT_SHA256,
    )


def stage_identity(stage: str) -> dict[str, Any]:
    if stage not in STAGE_BINDINGS:
        raise V3RuntimeBindingError(f"unknown v3 artifact stage: {stage}")
    return {
        "schema_version": V3_SCHEMA_VERSION,
        "attempt_version": V3_ATTEMPT_VERSION,
        "operation": STAGE_BINDINGS[stage]["operation"],
        "verdict_field": STAGE_BINDINGS[stage]["verdict_field"],
        "claim_contract_sha256": V3_CLAIM_CONTRACT_SHA256,
        "scheduler_contract_sha256": V1_SCHEDULER_CONTRACT_SHA256,
        "automatic_promotion": False,
    }


def validate_runtime_contract_bindings(
    evaluator: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    object_sha256: Any,
) -> dict[str, Any]:
    """Return separate claim and scheduler contracts after exact hash checks."""
    binding = build_v3_runtime_binding()
    claim = evaluator.get(binding.claim_contract_evaluator_key)
    scheduler = evaluator.get(binding.scheduler_contract_evaluator_key)
    if not isinstance(claim, Mapping) or not isinstance(scheduler, Mapping):
        raise V3RuntimeBindingError("v3 claim or scheduler contract is missing")
    observed_claim = str(object_sha256(claim)).lower()
    observed_scheduler = str(object_sha256(scheduler)).lower()
    if observed_claim != binding.claim_contract_sha256:
        raise V3RuntimeBindingError("v3 claim contract hash changed")
    if observed_scheduler != binding.scheduler_contract_sha256:
        raise V3RuntimeBindingError("v1 scheduler contract hash changed")
    if str(lock.get(binding.claim_contract_lock_key, "")).lower() != observed_claim:
        raise V3RuntimeBindingError("v3 claim contract lock binding changed")
    if str(lock.get(binding.scheduler_contract_lock_key, "")).lower() != observed_scheduler:
        raise V3RuntimeBindingError("v1 scheduler contract lock binding changed")
    return {
        "binding": binding.to_dict(),
        "claim_contract": dict(claim),
        "scheduler_contract": dict(scheduler),
    }


def apply_stage_identity(record: Mapping[str, Any], stage: str) -> dict[str, Any]:
    """Overlay immutable v3 evidence identity before any artifact is persisted."""
    value = dict(record)
    identity = stage_identity(stage)
    value["schema_version"] = identity["schema_version"]
    value["attempt_version"] = identity["attempt_version"]
    value["operation"] = identity["operation"]
    value["claim_contract_sha256"] = identity["claim_contract_sha256"]
    value["scheduler_contract_sha256"] = identity["scheduler_contract_sha256"]
    value["automatic_promotion"] = False
    verdict_field = identity["verdict_field"]
    if verdict_field not in value:
        value[verdict_field] = "inconclusive"
    for forbidden in ("catalytic_swarm_1", "catalytic_swarm_1_v2"):
        if forbidden in value and forbidden != verdict_field:
            raise V3RuntimeBindingError(
                f"v3 artifact retained forbidden predecessor verdict field: {forbidden}"
            )
    return value


def validate_persisted_v3_record(record: Mapping[str, Any], stage: str) -> None:
    if not isinstance(record, Mapping):
        raise V3RuntimeBindingError("v3 persisted record must be an object")
    identity = stage_identity(stage)
    checks = {
        "schema_version": record.get("schema_version") == identity["schema_version"],
        "attempt_version": record.get("attempt_version") == identity["attempt_version"],
        "operation": record.get("operation") == identity["operation"],
        "claim_contract_sha256": (
            str(record.get("claim_contract_sha256", "")).lower()
            == identity["claim_contract_sha256"]
        ),
        "scheduler_contract_sha256": (
            str(record.get("scheduler_contract_sha256", "")).lower()
            == identity["scheduler_contract_sha256"]
        ),
        "automatic_promotion": record.get("automatic_promotion") is False,
        "verdict_field": identity["verdict_field"] in record,
        "predecessor_verdict_absent": (
            "catalytic_swarm_1" not in record
            and "catalytic_swarm_1_v2" not in record
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise V3RuntimeBindingError(
            "v3 persisted evidence identity failed: " + ", ".join(failed)
        )


def rename_v3_result_after_persistence(*_: Any, **__: Any) -> None:
    raise V3RuntimeBindingError(
        "post-persistence verdict renaming is forbidden; persist v3 identity directly"
    )
