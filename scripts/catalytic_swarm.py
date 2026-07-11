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
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "logical_workers": [worker.to_dict() for worker in self.logical_workers],
            "physical_slots": self.physical_slots,
            "max_worker_tokens": self.max_worker_tokens,
            "fail_fast": self.fail_fast,
            "automatic_promotion": self.automatic_promotion,
            "plan_sha256": self.plan_sha256,
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "contribution": self.contribution.to_dict(),
            "entry_id": self.entry_id,
            "receipt": self.receipt.to_dict(),
            "lease_id": self.lease_id,
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
    worker_id = f"cs0-{ordinal:02d}-{phase}-{role}"
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


def build_catalytic_swarm_0_plan(*, physical_slots: int = 1) -> SwarmPlan:
    """Build the fixed 32-worker CatalyticSwarm-0 population."""
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

    if len(workers) != 32:
        raise AssertionError(f"unexpected CatalyticSwarm-0 size: {len(workers)}")

    payload = {
        "schema_version": 1,
        "plan_id": "catalytic-swarm-0",
        "logical_workers": [worker.to_dict() for worker in workers],
        "physical_slots": physical_slots,
        "max_worker_tokens": 64,
        "fail_fast": True,
        "automatic_promotion": False,
    }
    return SwarmPlan(
        schema_version=1,
        plan_id="catalytic-swarm-0",
        logical_workers=tuple(workers),
        physical_slots=physical_slots,
        max_worker_tokens=64,
        fail_fast=True,
        automatic_promotion=False,
        plan_sha256=sha256_bytes(canonical_json_bytes(payload)),
    )


_ALLOWED_KINDS = {
    "proposal": {"proposal"},
    "evidence": {"evidence"},
    "critique": {"critique"},
    "synthesis": {"selection"},
}
_ALLOWED_DECISIONS = {None, "support", "reject", "revise", "select", "abstain"}


def parse_contribution(value: Mapping[str, Any], spec: WorkerSpec) -> WorkerContribution:
    if not isinstance(value, Mapping):
        raise SwarmError("worker contribution must be an object")
    allowed_keys = {
        "kind", "claim", "target_ids", "references", "artifact_refs", "decision",
    }
    unknown = set(value) - allowed_keys
    if unknown:
        raise SwarmError(f"worker contribution contains unknown keys: {sorted(unknown)}")

    kind = value.get("kind")
    claim = value.get("claim")
    target_ids = value.get("target_ids", [])
    references = value.get("references", [])
    artifact_refs = value.get("artifact_refs", [])
    decision = value.get("decision")

    if kind not in _ALLOWED_KINDS[spec.phase]:
        raise SwarmError(f"invalid {spec.phase} contribution kind: {kind}")
    if not isinstance(claim, str) or not claim.strip() or len(claim) > 280:
        raise SwarmError("claim must be 1..280 characters")
    for name, items, ceiling in (
        ("target_ids", target_ids, 8),
        ("references", references, 6),
        ("artifact_refs", artifact_refs, 6),
    ):
        if not isinstance(items, list) or len(items) > ceiling:
            raise SwarmError(f"{name} must be a list with at most {ceiling} entries")
        if any(not isinstance(item, str) or not item for item in items):
            raise SwarmError(f"{name} contains an invalid item")
    if decision not in _ALLOWED_DECISIONS:
        raise SwarmError(f"invalid contribution decision: {decision}")

    parent_set = set(spec.parent_worker_ids)
    if spec.phase != "proposal" and not set(target_ids).issubset(parent_set):
        raise SwarmError("worker targeted an unassigned logical parent")
    if spec.phase == "proposal" and target_ids:
        raise SwarmError("independent proposal workers may not target prior workers")
    if spec.phase == "synthesis" and decision not in {"select", "abstain"}:
        raise SwarmError("synthesis must select or abstain")

    return WorkerContribution(
        kind=str(kind),
        claim=claim.strip(),
        target_ids=tuple(target_ids),
        references=tuple(references),
        artifact_refs=tuple(artifact_refs),
        decision=decision,
    )


def contribution_payload_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "claim", "target_ids", "references", "artifact_refs", "decision"],
        "properties": {
            "kind": {"type": "string"},
            "claim": {"type": "string", "minLength": 1, "maxLength": 280},
            "target_ids": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
            "references": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
            "artifact_refs": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
            "decision": {
                "type": ["string", "null"],
                "enum": [None, "support", "reject", "revise", "select", "abstain"],
            },
        },
    }


WorkerRunner = Callable[[WorkerSpec, tuple[BlackboardEntry, ...]], Mapping[str, Any]]
Verifier = Callable[
    [WorkerSpec, WorkerContribution, tuple[BlackboardEntry, ...]],
    VerificationReceipt,
]


def _worker_entry_ids_by_worker(executions: Sequence[WorkerExecution]) -> dict[str, str]:
    return {item.spec.worker_id: item.entry_id for item in executions}


def run_swarm(
    plan: SwarmPlan,
    *,
    worker_runner: WorkerRunner,
    verifier: Verifier,
    blackboard: AppendOnlyBlackboard | None = None,
) -> SwarmRunResult:
    """Execute a deterministic bounded swarm through callback interfaces."""
    if plan.plan_id != "catalytic-swarm-0":
        raise SwarmError("unsupported swarm plan")
    if len(plan.logical_workers) != 32:
        raise SwarmError("CatalyticSwarm-0 requires exactly 32 logical workers")
    if plan.max_worker_tokens != 64:
        raise SwarmError("CatalyticSwarm-0 exceeds the proven Fast token budget")
    if not all(worker.thinking_disabled for worker in plan.logical_workers):
        raise SwarmError("CatalyticSwarm-0 may use only thinking-disabled workers")
    if plan.automatic_promotion:
        raise SwarmError("automatic promotion must remain disabled")

    board = blackboard or AppendOnlyBlackboard(max_entries=128)
    leases = PhysicalLeasePool(plan.physical_slots)
    executions: list[WorkerExecution] = []
    verified_entry_ids: set[str] = set()
    reasons: list[str] = []
    stopped_worker_id: str | None = None

    for phase in PHASES:
        phase_workers = [worker for worker in plan.logical_workers if worker.phase == phase]
        worker_entry_ids = _worker_entry_ids_by_worker(executions)
        board.entries_before_phase(phase)  # freeze the prior-phase boundary

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

            try:
                with leases.lease() as lease_id:
                    contribution = parse_contribution(worker_runner(spec, context), spec)
                    receipt = verifier(spec, contribution, context)
                    if receipt.worker_id != spec.worker_id:
                        raise SwarmError("verifier receipt worker identity mismatch")
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
                    ))
                    if receipt.passed:
                        verified_entry_ids.add(entry.entry_id)
                    elif plan.fail_fast:
                        raise SwarmError(receipt.reason or "verification failed")
            except Exception as exc:
                stopped_worker_id = spec.worker_id
                reasons.append(str(exc))
                if plan.fail_fast:
                    break
        if stopped_worker_id is not None and plan.fail_fast:
            break

    synthesis_entry_ids = tuple(
        item.entry_id
        for item in executions
        if item.spec.phase == "synthesis" and item.receipt.passed
    )
    passed = (
        stopped_worker_id is None
        and len(executions) == len(plan.logical_workers)
        and bool(synthesis_entry_ids)
        and board.verify_chain()
        and leases.active_count == 0
        and leases.max_concurrent <= plan.physical_slots
    )
    if not board.verify_chain():
        reasons.append("blackboard hash chain failed")
    if not synthesis_entry_ids and stopped_worker_id is None:
        reasons.append("no verified synthesis contribution")

    return SwarmRunResult(
        plan_sha256=plan.plan_sha256,
        verdict="reviewable-accept" if passed else "reject",
        stopped_worker_id=stopped_worker_id,
        executions=tuple(executions),
        verified_entry_ids=tuple(sorted(verified_entry_ids)),
        synthesis_entry_ids=synthesis_entry_ids,
        blackboard_head_hash=board.head_hash,
        blackboard_entry_count=len(board),
        physical_slots=plan.physical_slots,
        max_concurrent_leases=leases.max_concurrent,
        lease_count=leases.lease_count,
        automatic_promotion=False,
        reasons=tuple(reasons),
    )
