#!/usr/bin/env python3
"""Deterministic bounded control plane for CatalyticSwarm-0.

This module contains no network, Git, model, or filesystem mutation. It plans
and schedules 32 logical Fast workers over a bounded physical lease pool,
communicates through an append-only blackboard, and requires an external
verifier receipt before a contribution can influence synthesis.

The default plan is deliberately compatible with the proven HoloState Fast
lane: thinking disabled, max 64 completion tokens, one physical execution slot.
Deep workers are excluded from CatalyticSwarm-0 because worker protocol v4
rejected the Deep lane independently.
"""

from __future__ import annotations

import hashlib
import json
import queue
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterator, Mapping, Sequence

from catalytic_blackboard import (
    AppendOnlyBlackboard,
    BlackboardEntry,
    PHASES,
    PHASE_CODES,
    canonical_json_bytes,
    sha256_bytes,
)

PLAN_SCHEMA_VERSION = 1
PLAN_ID = "catalytic-swarm-0"
LOGICAL_WORKER_COUNT = 32
PHYSICAL_SLOT_COUNT = 1
MAX_WORKER_TOKENS = 64
PHASE_COUNTS = {
    "proposal": 16,
    "evidence": 8,
    "critique": 6,
    "synthesis": 2,
}
VERIFIER_ID = "catalytic-swarm-0-verifier-v1"
REQUIRED_VERIFICATION_CHECKS = (
    "structured-contribution",
    "worker-identity",
    "phase-role",
    "exact-parent-targets",
    "same-phase-isolation",
    "transport-evidence",
)


class SwarmError(RuntimeError):
    """A swarm plan, worker, verifier, or bounded-resource law failed."""


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    ordinal: int
    phase: str
    role: str
    root_name: str
    assignment: str
    parent_worker_ids: tuple[str, ...]
    context_limit: int
    max_tokens: int
    thinking_disabled: bool
    seed: int
    phase_code: tuple[int, int, int, int]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parent_worker_ids"] = list(self.parent_worker_ids)
        value["phase_code"] = list(self.phase_code)
        return value


@dataclass(frozen=True)
class SwarmPlan:
    schema_version: int
    plan_id: str
    logical_workers: tuple[WorkerSpec, ...]
    physical_slots: int
    max_worker_tokens: int
    fail_fast: bool
    automatic_promotion: bool
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        value = _plan_payload(self)
        value["plan_sha256"] = self.plan_sha256
        return value


@dataclass(frozen=True)
class WorkerContribution:
    kind: str
    claim: str
    target_ids: tuple[str, ...]
    references: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    decision: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "claim": self.claim,
            "target_ids": list(self.target_ids),
            "references": list(self.references),
            "artifact_refs": list(self.artifact_refs),
            "decision": self.decision,
        }


@dataclass(frozen=True)
class VerificationReceipt:
    worker_id: str
    passed: bool
    checks: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    verifier: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "passed": self.passed,
            "checks": list(self.checks),
            "artifact_refs": list(self.artifact_refs),
            "verifier": self.verifier,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class WorkerExecution:
    spec: WorkerSpec
    contribution: WorkerContribution
    entry_id: str
    receipt: VerificationReceipt
    lease_id: int
    visible_entry_ids: tuple[str, ...]
    blackboard_head_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "contribution": self.contribution.to_dict(),
            "entry_id": self.entry_id,
            "receipt": self.receipt.to_dict(),
            "lease_id": self.lease_id,
            "visible_entry_ids": list(self.visible_entry_ids),
            "blackboard_head_hash": self.blackboard_head_hash,
        }


@dataclass(frozen=True)
class SwarmRunResult:
    plan_sha256: str
    verdict: str
    stopped_worker_id: str | None
    executions: tuple[WorkerExecution, ...]
    verified_entry_ids: tuple[str, ...]
    synthesis_entry_ids: tuple[str, ...]
    blackboard_head_hash: str
    blackboard_entry_count: int
    physical_slots: int
    max_concurrent_leases: int
    lease_count: int
    active_leases_after: int
    verified_execution_count: int
    phase_execution_counts: tuple[tuple[str, int], ...]
    blackboard_chain_valid: bool
    automatic_promotion: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_sha256": self.plan_sha256,
            "verdict": self.verdict,
            "stopped_worker_id": self.stopped_worker_id,
            "executions": [item.to_dict() for item in self.executions],
            "verified_entry_ids": list(self.verified_entry_ids),
            "synthesis_entry_ids": list(self.synthesis_entry_ids),
            "blackboard_head_hash": self.blackboard_head_hash,
            "blackboard_entry_count": self.blackboard_entry_count,
            "physical_slots": self.physical_slots,
            "max_concurrent_leases": self.max_concurrent_leases,
            "lease_count": self.lease_count,
            "active_leases_after": self.active_leases_after,
            "verified_execution_count": self.verified_execution_count,
            "phase_execution_counts": dict(self.phase_execution_counts),
            "blackboard_chain_valid": self.blackboard_chain_valid,
            "automatic_promotion": self.automatic_promotion,
            "reasons": list(self.reasons),
        }


class PhysicalLeasePool:
    """Exp-08-style logical-to-physical lease allocator."""

    def __init__(self, physical_slots: int) -> None:
        if physical_slots <= 0:
            raise ValueError("physical_slots must be positive")
        self.physical_slots = physical_slots
        self._queue: queue.Queue[int] = queue.Queue()
        for lease_id in range(physical_slots):
            self._queue.put(lease_id)
        self._lock = threading.Lock()
        self._active: set[int] = set()
        self._max_active = 0
        self._lease_count = 0

    @contextmanager
    def lease(self) -> Iterator[int]:
        lease_id = self._queue.get(block=True)
        with self._lock:
            if lease_id in self._active:
                raise SwarmError("physical lease was acquired twice")
            self._active.add(lease_id)
            self._max_active = max(self._max_active, len(self._active))
            self._lease_count += 1
        try:
            yield lease_id
        finally:
            with self._lock:
                if lease_id not in self._active:
                    raise SwarmError("physical lease release without ownership")
                self._active.remove(lease_id)
            self._queue.put(lease_id)

    @property
    def max_concurrent(self) -> int:
        with self._lock:
            return self._max_active

    @property
    def lease_count(self) -> int:
        with self._lock:
            return self._lease_count

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)


def deterministic_seed(label: str) -> int:
    return int.from_bytes(hashlib.sha256(label.encode("utf-8")).digest()[:4], "big")


def _worker(
    ordinal: int,
    phase: str,
    role: str,
    assignment: str,
    parents: Sequence[str],
    context_limit: int,
) -> WorkerSpec:
    worker_id = f"cs0-w{ordinal:02d}"
    return WorkerSpec(
        worker_id=worker_id,
        ordinal=ordinal,
        phase=phase,
        role=role,
        root_name="A",
        assignment=assignment,
        parent_worker_ids=tuple(parents),
        context_limit=context_limit,
        max_tokens=64,
        thinking_disabled=True,
        seed=deterministic_seed(worker_id),
        phase_code=PHASE_CODES[phase],
    )


def _canonical_worker_specs() -> tuple[WorkerSpec, ...]:
    workers: list[WorkerSpec] = []
    ordinal = 1

    proposal_roles = ("hypothesis", "implementation", "counterexample", "measurement")
    proposal_ids: list[str] = []
    for _cycle in range(4):
        for role in proposal_roles:
            spec = _worker(
                ordinal,
                "proposal",
                role,
                (
                    f"Produce one compact {role} contribution for objective {{objective}}. "
                    "Do not read or imitate another proposal."
                ),
                (),
                0,
            )
            workers.append(spec)
            proposal_ids.append(spec.worker_id)
            ordinal += 1

    evidence_ids: list[str] = []
    for index in range(8):
        parents = (
            proposal_ids[(index * 2) % len(proposal_ids)],
            proposal_ids[(index * 2 + 1) % len(proposal_ids)],
        )
        spec = _worker(
            ordinal,
            "evidence",
            "evidence-check",
            "Check the assigned proposals against supplied evidence and artifacts.",
            parents,
            2,
        )
        workers.append(spec)
        evidence_ids.append(spec.worker_id)
        ordinal += 1

    critique_ids: list[str] = []
    for index in range(6):
        parents = (
            evidence_ids[index % len(evidence_ids)],
            evidence_ids[(index + 3) % len(evidence_ids)],
        )
        spec = _worker(
            ordinal,
            "critique",
            "adversarial-critic",
            "Find one decisive flaw, missing test, or disconfirming observation.",
            parents,
            2,
        )
        workers.append(spec)
        critique_ids.append(spec.worker_id)
        ordinal += 1

    for index in range(2):
        parents = tuple(critique_ids[index::2])
        workers.append(_worker(
            ordinal,
            "synthesis",
            "selector",
            "Select verified contribution IDs only; return a compact decision.",
            parents,
            6,
        ))
        ordinal += 1

    if len(workers) != LOGICAL_WORKER_COUNT:
        raise AssertionError(f"unexpected CatalyticSwarm-0 size: {len(workers)}")
    return tuple(workers)


def _plan_payload(plan: SwarmPlan) -> dict[str, Any]:
    return {
        "schema_version": plan.schema_version,
        "plan_id": plan.plan_id,
        "phase_order": list(PHASES),
        "phase_counts": dict(PHASE_COUNTS),
        "phase_codes": {phase: list(PHASE_CODES[phase]) for phase in PHASES},
        "logical_worker_count": len(plan.logical_workers),
        "logical_workers": [worker.to_dict() for worker in plan.logical_workers],
        "physical_slots": plan.physical_slots,
        "max_worker_tokens": plan.max_worker_tokens,
        "fail_fast": plan.fail_fast,
        "automatic_promotion": plan.automatic_promotion,
    }


def build_catalytic_swarm_0_plan(*, physical_slots: int = 1) -> SwarmPlan:
    """Build the one exact 32-worker CatalyticSwarm-0 population."""
    if (
        isinstance(physical_slots, bool)
        or not isinstance(physical_slots, int)
        or physical_slots != PHYSICAL_SLOT_COUNT
    ):
        raise ValueError("CatalyticSwarm-0 requires exactly one physical slot")
    workers = _canonical_worker_specs()
    provisional = SwarmPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        plan_id=PLAN_ID,
        logical_workers=workers,
        physical_slots=PHYSICAL_SLOT_COUNT,
        max_worker_tokens=MAX_WORKER_TOKENS,
        fail_fast=True,
        automatic_promotion=False,
        plan_sha256="",
    )
    digest = sha256_bytes(canonical_json_bytes(_plan_payload(provisional)))
    return SwarmPlan(
        schema_version=provisional.schema_version,
        plan_id=provisional.plan_id,
        logical_workers=provisional.logical_workers,
        physical_slots=provisional.physical_slots,
        max_worker_tokens=provisional.max_worker_tokens,
        fail_fast=provisional.fail_fast,
        automatic_promotion=provisional.automatic_promotion,
        plan_sha256=digest,
    )


def validate_catalytic_swarm_0_plan(plan: SwarmPlan) -> None:
    """Reject any drift from the complete canonical CatalyticSwarm-0 plan."""
    if not isinstance(plan, SwarmPlan):
        raise SwarmError("CatalyticSwarm-0 plan has the wrong type")
    expected = build_catalytic_swarm_0_plan()
    if plan.schema_version != PLAN_SCHEMA_VERSION:
        raise SwarmError("CatalyticSwarm-0 schema version drift")
    if plan.plan_id != PLAN_ID:
        raise SwarmError("unsupported swarm plan")
    if plan.physical_slots != PHYSICAL_SLOT_COUNT:
        raise SwarmError("CatalyticSwarm-0 requires exactly one physical slot")
    if plan.max_worker_tokens != MAX_WORKER_TOKENS:
        raise SwarmError("CatalyticSwarm-0 exceeds the proven Fast token budget")
    if plan.fail_fast is not True:
        raise SwarmError("CatalyticSwarm-0 fail-fast law changed")
    if plan.automatic_promotion is not False:
        raise SwarmError("automatic promotion must remain disabled")
    if plan.logical_workers != expected.logical_workers:
        raise SwarmError("CatalyticSwarm-0 worker population or graph drift")
    recomputed = sha256_bytes(canonical_json_bytes(_plan_payload(plan)))
    if plan.plan_sha256 != recomputed or plan.plan_sha256 != expected.plan_sha256:
        raise SwarmError("CatalyticSwarm-0 plan hash mismatch")


_CONTRIBUTION_KEYS = {
    "kind", "claim", "target_ids", "references", "artifact_refs", "decision",
}
_PHASE_KINDS = {
    "proposal": "proposal",
    "evidence": "evidence",
    "critique": "critique",
    "synthesis": "selection",
}
_PHASE_DECISIONS = {
    "proposal": None,
    "evidence": "support",
    "critique": "revise",
    "synthesis": "select",
}


def expected_control_contribution(spec: WorkerSpec) -> WorkerContribution:
    """Return the one exact control contribution permitted for a worker."""
    if spec.phase not in _PHASE_KINDS:
        raise SwarmError(f"unknown CatalyticSwarm-0 phase: {spec.phase}")
    return WorkerContribution(
        kind=_PHASE_KINDS[spec.phase],
        claim=f"ACK:{spec.ordinal}",
        target_ids=spec.parent_worker_ids,
        references=(),
        artifact_refs=(),
        decision=_PHASE_DECISIONS[spec.phase],
    )


def expected_control_content(spec: WorkerSpec) -> str:
    return json.dumps(
        expected_control_contribution(spec).to_dict(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def parse_contribution(value: Mapping[str, Any], spec: WorkerSpec) -> WorkerContribution:
    if not isinstance(value, Mapping):
        raise SwarmError("worker contribution must be an object")
    if set(value) != _CONTRIBUTION_KEYS:
        missing = sorted(_CONTRIBUTION_KEYS - set(value))
        extra = sorted(str(key) for key in set(value) - _CONTRIBUTION_KEYS)
        raise SwarmError(
            f"worker contribution key set mismatch; missing={missing}, extra={extra}"
        )
    for name in ("target_ids", "references", "artifact_refs"):
        items = value[name]
        if not isinstance(items, list):
            raise SwarmError(f"{name} must be an array")
        if any(not isinstance(item, str) or not item for item in items):
            raise SwarmError(f"{name} contains an invalid item")
        if len(set(items)) != len(items):
            raise SwarmError(f"{name} contains duplicates")
    parsed = WorkerContribution(
        kind=value["kind"] if isinstance(value["kind"], str) else "",
        claim=value["claim"] if isinstance(value["claim"], str) else "",
        target_ids=tuple(value["target_ids"]),
        references=tuple(value["references"]),
        artifact_refs=tuple(value["artifact_refs"]),
        decision=value["decision"] if value["decision"] is None or isinstance(value["decision"], str) else "",
    )
    expected = expected_control_contribution(spec)
    if parsed != expected:
        raise SwarmError("worker contribution differs from the exact control law")
    return parsed


def contribution_payload_schema(spec: WorkerSpec | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "claim", "target_ids", "references", "artifact_refs", "decision"],
        "properties": {
            "kind": {"type": "string", "enum": list(_PHASE_KINDS.values())},
            "claim": {"type": "string", "pattern": "^ACK:[1-9][0-9]*$"},
            "target_ids": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
            "references": {"type": "array", "maxItems": 0},
            "artifact_refs": {"type": "array", "maxItems": 0},
            "decision": {
                "type": ["string", "null"],
                "enum": [None, "support", "revise", "select"],
            },
        },
    }
    if spec is not None:
        expected = expected_control_contribution(spec).to_dict()
        schema["properties"] = {
            key: {"const": value}
            for key, value in expected.items()
        }
    return schema


WorkerRunner = Callable[[WorkerSpec, tuple[BlackboardEntry, ...]], Mapping[str, Any]]
Verifier = Callable[
    [WorkerSpec, WorkerContribution, tuple[BlackboardEntry, ...]],
    VerificationReceipt,
]
ExecutionObserver = Callable[[str, Mapping[str, Any]], None]


def _worker_entry_ids_by_worker(executions: Sequence[WorkerExecution]) -> dict[str, str]:
    return {item.spec.worker_id: item.entry_id for item in executions}


def _notify(
    observer: ExecutionObserver | None,
    event: str,
    payload: Mapping[str, Any],
) -> None:
    if observer is not None:
        observer(event, dict(payload))


def _validate_context(
    spec: WorkerSpec,
    context: tuple[BlackboardEntry, ...],
    verified_entry_ids: set[str],
) -> None:
    if tuple(entry.author_worker_id for entry in context) != spec.parent_worker_ids:
        raise SwarmError(f"{spec.worker_id} received the wrong parent context")
    if len(context) != len(spec.parent_worker_ids) or len(context) > spec.context_limit:
        raise SwarmError(f"{spec.worker_id} context count differs from the locked plan")
    if any(entry.phase == spec.phase for entry in context):
        raise SwarmError(f"{spec.worker_id} received same-phase context")
    if any(entry.entry_id not in verified_entry_ids for entry in context):
        raise SwarmError(f"{spec.worker_id} received an unverified parent")


def _validate_receipt(spec: WorkerSpec, receipt: VerificationReceipt) -> None:
    if not isinstance(receipt, VerificationReceipt):
        raise SwarmError("verifier returned the wrong receipt type")
    if receipt.worker_id != spec.worker_id:
        raise SwarmError("verifier receipt worker identity mismatch")
    if not isinstance(receipt.passed, bool):
        raise SwarmError("verifier receipt passed flag is not boolean")
    if receipt.checks != REQUIRED_VERIFICATION_CHECKS:
        raise SwarmError("verifier receipt check set mismatch")
    if receipt.verifier != VERIFIER_ID:
        raise SwarmError("verifier identity mismatch")
    if (
        not isinstance(receipt.artifact_refs, tuple)
        or len(receipt.artifact_refs) > 8
        or any(not isinstance(item, str) or not item for item in receipt.artifact_refs)
        or len(set(receipt.artifact_refs)) != len(receipt.artifact_refs)
    ):
        raise SwarmError("verifier artifact references are malformed")
    if receipt.passed and receipt.reason is not None:
        raise SwarmError("passing verifier receipt carries a failure reason")
    if not receipt.passed and (not isinstance(receipt.reason, str) or not receipt.reason):
        raise SwarmError("failed verifier receipt omits its reason")


def run_swarm(
    plan: SwarmPlan,
    *,
    worker_runner: WorkerRunner,
    verifier: Verifier,
    blackboard: AppendOnlyBlackboard | None = None,
    execution_observer: ExecutionObserver | None = None,
) -> SwarmRunResult:
    """Execute a deterministic bounded swarm through callback interfaces."""
    validate_catalytic_swarm_0_plan(plan)
    board = blackboard if blackboard is not None else AppendOnlyBlackboard(max_entries=128)
    if len(board) != 0:
        raise SwarmError("CatalyticSwarm-0 requires a fresh empty blackboard")
    if not board.verify_chain():
        raise SwarmError("initial blackboard hash chain failed")
    leases = PhysicalLeasePool(plan.physical_slots)
    executions: list[WorkerExecution] = []
    verified_entry_ids: set[str] = set()
    reasons: list[str] = []
    stopped_worker_id: str | None = None

    for phase in PHASES:
        phase_workers = [worker for worker in plan.logical_workers if worker.phase == phase]
        worker_entry_ids = _worker_entry_ids_by_worker(executions)
        for spec in phase_workers:
            parent_entry_ids = []
            for parent_worker_id in spec.parent_worker_ids:
                parent_entry_id = worker_entry_ids.get(parent_worker_id)
                if parent_entry_id is None:
                    raise SwarmError(
                        f"{spec.worker_id} dependency did not execute: {parent_worker_id}"
                    )
                parent_entry_ids.append(parent_entry_id)

            context = board.select_entries(
                phase=phase,
                parent_ids=parent_entry_ids,
                limit=spec.context_limit,
                include_verified_only=phase == "synthesis",
                verified_entry_ids=verified_entry_ids,
            )
            _validate_context(spec, context, verified_entry_ids)

            try:
                with leases.lease() as lease_id:
                    _notify(execution_observer, "worker-start", {
                        "worker_id": spec.worker_id,
                        "ordinal": spec.ordinal,
                        "phase": spec.phase,
                        "role": spec.role,
                        "lease_id": lease_id,
                        "visible_entry_ids": [entry.entry_id for entry in context],
                    })
                    contribution = parse_contribution(worker_runner(spec, context), spec)
                    receipt = verifier(spec, contribution, context)
                    _validate_receipt(spec, receipt)
                    _notify(execution_observer, "worker-verified", {
                        "worker_id": spec.worker_id,
                        "lease_id": lease_id,
                        "receipt": receipt.to_dict(),
                    })
                    if receipt.passed is not True:
                        raise SwarmError(receipt.reason or "verification failed")
                    entry = board.append(
                        phase=spec.phase,
                        kind=contribution.kind,
                        author_worker_id=spec.worker_id,
                        body=contribution.to_dict(),
                        references=contribution.references,
                        parent_ids=tuple(item.entry_id for item in context),
                        artifact_refs=contribution.artifact_refs,
                    )
                    executions.append(WorkerExecution(
                        spec=spec,
                        contribution=contribution,
                        entry_id=entry.entry_id,
                        receipt=receipt,
                        lease_id=lease_id,
                        visible_entry_ids=tuple(item.entry_id for item in context),
                        blackboard_head_hash=entry.entry_hash,
                    ))
                    verified_entry_ids.add(entry.entry_id)
                    _notify(execution_observer, "worker-published", {
                        "worker_id": spec.worker_id,
                        "lease_id": lease_id,
                        "entry_id": entry.entry_id,
                        "blackboard_head_hash": entry.entry_hash,
                    })
                _notify(execution_observer, "worker-complete", {
                    "worker_id": spec.worker_id,
                    "lease_id": lease_id,
                    "active_leases": leases.active_count,
                })
            except Exception as exc:
                stopped_worker_id = spec.worker_id
                reasons.append(str(exc))
                try:
                    _notify(execution_observer, "worker-failed", {
                        "worker_id": spec.worker_id,
                        "phase": spec.phase,
                        "reason": str(exc),
                    })
                except Exception as observer_exc:
                    reasons.append(f"failure observer error: {observer_exc}")
                break
        if stopped_worker_id is not None:
            break

    synthesis_entry_ids = tuple(
        item.entry_id
        for item in executions
        if item.spec.phase == "synthesis" and item.receipt.passed
    )
    phase_execution_counts = tuple(
        (phase, sum(item.spec.phase == phase for item in executions))
        for phase in PHASES
    )
    board_phase_counts = {
        phase: sum(entry.phase == phase for entry in board.entries())
        for phase in PHASES
    }
    blackboard_chain_valid = board.verify_chain()
    passed = (
        stopped_worker_id is None
        and len(executions) == LOGICAL_WORKER_COUNT
        and len(verified_entry_ids) == LOGICAL_WORKER_COUNT
        and len(synthesis_entry_ids) == PHASE_COUNTS["synthesis"]
        and blackboard_chain_valid
        and len(board) == LOGICAL_WORKER_COUNT
        and dict(phase_execution_counts) == PHASE_COUNTS
        and board_phase_counts == PHASE_COUNTS
        and leases.physical_slots == PHYSICAL_SLOT_COUNT
        and leases.active_count == 0
        and leases.max_concurrent == PHYSICAL_SLOT_COUNT
        and leases.lease_count == LOGICAL_WORKER_COUNT
        and all(item.lease_id == 0 for item in executions)
    )
    if not blackboard_chain_valid:
        reasons.append("blackboard hash chain failed")
    if not passed and stopped_worker_id is None:
        reasons.append("final CatalyticSwarm-0 acceptance invariants failed")

    return SwarmRunResult(
        plan_sha256=plan.plan_sha256,
        verdict="reviewable-accept" if passed else "reject",
        stopped_worker_id=stopped_worker_id,
        executions=tuple(executions),
        verified_entry_ids=tuple(
            item.entry_id for item in executions if item.entry_id in verified_entry_ids
        ),
        synthesis_entry_ids=synthesis_entry_ids,
        blackboard_head_hash=board.head_hash,
        blackboard_entry_count=len(board),
        physical_slots=plan.physical_slots,
        max_concurrent_leases=leases.max_concurrent,
        lease_count=leases.lease_count,
        active_leases_after=leases.active_count,
        verified_execution_count=len(verified_entry_ids),
        phase_execution_counts=phase_execution_counts,
        blackboard_chain_valid=blackboard_chain_valid,
        automatic_promotion=False,
        reasons=tuple(reasons),
    )
