#!/usr/bin/env python3
"""Pure exactly-once completion closure for CS1-v5 model responses.

This module performs no filesystem, process, network, Git, or model operation.
The live controller supplies callbacks for durable ledger and result writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


WARM_GATE_ORDER = (
    "result_accepted",
    "resource_gate_passed",
    "finish_reason_stop",
    "reasoning_absent",
    "tool_calls_empty",
    "token_evidence_accepted",
    "logical_prompt_count_matches",
)
COMPARISON_GATE_ORDER = (
    "candidate_parse_passed",
    "transport_accepted",
    "finish_reason_stop",
    "reasoning_absent",
    "tool_calls_empty",
    "token_evidence_accepted",
    "prompt_token_identity_matches",
    "root_terminal_admitted",
)
REASON_CODES = {
    "result_accepted": "response-not-accepted",
    "resource_gate_passed": "inline-resource-gate-failed",
    "finish_reason_stop": "finish-reason-not-stop",
    "reasoning_absent": "reasoning-content-present",
    "tool_calls_empty": "tool-calls-present",
    "token_evidence_accepted": "visible-token-evidence-rejected",
    "logical_prompt_count_matches": "logical-prompt-count-mismatch",
    "candidate_parse_passed": "candidate-parse-rejected",
    "transport_accepted": "candidate-transport-rejected",
    "prompt_token_identity_matches": "prompt-token-identity-mismatch",
    "root_terminal_admitted": "root-terminal-cache-admission-rejected",
}


class CatalyticSwarm1V5ClosureError(RuntimeError):
    """A v5 completion observation violated exactly-once closure."""


class CompletedResponseRejected(CatalyticSwarm1V5ClosureError):
    """A completed response was durably closed and then rejected."""


class CompletedResponsePersistenceError(CatalyticSwarm1V5ClosureError):
    """Primary ledger persistence failed after a completed response."""


def classify_gate_outcomes(kind: str, outcomes: Mapping[str, Any]) -> tuple[bool, str]:
    order = WARM_GATE_ORDER if kind == "warm" else COMPARISON_GATE_ORDER if kind == "comparison" else None
    if order is None:
        raise CatalyticSwarm1V5ClosureError(f"unknown completed-response kind: {kind}")
    if set(outcomes) != set(order):
        raise CatalyticSwarm1V5ClosureError(f"{kind} gate field set changed")
    normalized: dict[str, bool] = {}
    for name in order:
        value = outcomes[name]
        if type(value) is not bool:
            raise CatalyticSwarm1V5ClosureError(f"{kind} gate is not boolean: {name}")
        normalized[name] = value
    for name in order:
        if normalized[name] is not True:
            return False, REASON_CODES[name]
    return True, "accepted"


@dataclass
class CompletedResponseClosure:
    request_label: str
    request_sequence_index: int
    kind: str
    model_completed: bool = False
    observation_captured: bool = False
    post_request_recorded: bool = False
    persisted: bool = False
    lease_released: bool = False
    accepted: bool = False
    reason_code: str = "request-not-completed"
    metadata: dict[str, Any] = field(default_factory=dict)
    gate_outcomes: dict[str, bool] = field(default_factory=dict)
    post_request_boundary: dict[str, Any] = field(default_factory=dict)
    persistence: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_label, str) or not self.request_label:
            raise CatalyticSwarm1V5ClosureError("request label is invalid")
        if type(self.request_sequence_index) is not int or self.request_sequence_index < 1:
            raise CatalyticSwarm1V5ClosureError("request sequence index is invalid")
        if self.kind not in {"warm", "comparison"}:
            raise CatalyticSwarm1V5ClosureError("completed-response kind is invalid")

    def mark_model_completed(self) -> None:
        if self.model_completed:
            raise CatalyticSwarm1V5ClosureError("model completion marked more than once")
        self.model_completed = True

    def capture(self, metadata: Mapping[str, Any], gate_outcomes: Mapping[str, Any]) -> None:
        if not self.model_completed:
            raise CatalyticSwarm1V5ClosureError("response observation preceded model completion")
        if self.observation_captured:
            raise CatalyticSwarm1V5ClosureError("response observation captured more than once")
        accepted, reason_code = classify_gate_outcomes(self.kind, gate_outcomes)
        self.metadata = dict(metadata)
        self.gate_outcomes = {name: bool(gate_outcomes[name]) for name in gate_outcomes}
        self.accepted = accepted
        self.reason_code = reason_code
        self.observation_captured = True

    def capture_instrumentation_failure(
        self, metadata: Mapping[str, Any], *, reason_code: str
    ) -> None:
        if not self.model_completed:
            raise CatalyticSwarm1V5ClosureError("instrumentation failure preceded model completion")
        if self.observation_captured:
            raise CatalyticSwarm1V5ClosureError("response observation captured more than once")
        if not isinstance(reason_code, str) or not reason_code:
            raise CatalyticSwarm1V5ClosureError("instrumentation reason code is invalid")
        self.metadata = dict(metadata)
        self.gate_outcomes = {}
        self.accepted = False
        self.reason_code = reason_code
        self.observation_captured = True

    def record_post_request_boundary(
        self,
        *,
        wddm_passed: bool,
        custody_passed: bool,
        host_memory_passed: bool,
        reason_code: str | None = None,
    ) -> None:
        if not self.model_completed or not self.observation_captured:
            raise CatalyticSwarm1V5ClosureError("post-request boundary preceded completed observation")
        if self.post_request_recorded:
            raise CatalyticSwarm1V5ClosureError("post-request boundary recorded more than once")
        for name, value in (
            ("wddm_passed", wddm_passed),
            ("custody_passed", custody_passed),
            ("host_memory_passed", host_memory_passed),
        ):
            if type(value) is not bool:
                raise CatalyticSwarm1V5ClosureError(f"post-request boundary is not boolean: {name}")
        passed = wddm_passed and custody_passed and host_memory_passed
        if not passed:
            self.accepted = False
            self.reason_code = reason_code or "post-request-resource-boundary-failed"
        self.post_request_boundary = {
            "passed": passed,
            "wddm_passed": wddm_passed,
            "custody_passed": custody_passed,
            "host_memory_passed": host_memory_passed,
        }
        self.post_request_recorded = True

    def final_metadata(self, *, persistence: str) -> dict[str, Any]:
        if not self.model_completed or not self.observation_captured or not self.post_request_recorded:
            raise CatalyticSwarm1V5ClosureError("completed response is not ready for persistence")
        value = dict(self.metadata)
        value.update({
            "model_boundary_completed": True,
            "response_disposition": "accepted" if self.accepted else "rejected",
            "response_reason_code": self.reason_code,
            "gate_outcomes": dict(self.gate_outcomes),
            "post_request_boundary": dict(self.post_request_boundary),
            "completion_persistence": persistence,
        })
        return value

    def persist(
        self,
        *,
        append_ledger: Callable[[dict[str, Any]], None],
        sync_ledger: Callable[[], None],
        persist_result_fallback: Callable[[dict[str, Any], str], None],
    ) -> dict[str, Any]:
        if self.persisted:
            raise CatalyticSwarm1V5ClosureError("completed response persisted more than once")
        primary = self.final_metadata(persistence="ledger")
        try:
            append_ledger(primary)
            sync_ledger()
        except BaseException as exc:
            fallback = self.final_metadata(persistence="result-fallback")
            persist_result_fallback(fallback, f"{type(exc).__name__}: {exc}")
            self.persisted = True
            self.persistence = "result-fallback"
            raise CompletedResponsePersistenceError(
                f"{self.request_label}: ledger persistence failed after completed response"
            ) from exc
        self.persisted = True
        self.persistence = "ledger"
        return primary

    def mark_lease_released(self) -> None:
        if self.lease_released:
            raise CatalyticSwarm1V5ClosureError("lease release recorded more than once")
        self.lease_released = True

    def enforce(self) -> None:
        if not self.persisted:
            raise CatalyticSwarm1V5ClosureError("acceptance enforced before persistence")
        if not self.lease_released:
            raise CatalyticSwarm1V5ClosureError("acceptance enforced before lease release")
        if self.accepted is not True:
            raise CompletedResponseRejected(
                f"{self.request_label}: completed response rejected: {self.reason_code}"
            )
