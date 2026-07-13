#!/usr/bin/env python3
"""Pure independent post-request evidence closure for Catalytic Swarm 1 v6.

The module performs no filesystem, process, Git, network, or model operation.
Callers provide four read-only observers and persistence callbacks.  Every
completed model response is represented by one ordered boundary group before
acceptance or interruption is enforced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Mapping, Sequence


BOUNDARY_ORDER = (
    "wddm",
    "stable_custody",
    "candidate_custody",
    "host_memory",
)
BOUNDARY_STATES = {
    "passed",
    "failed-invariant",
    "observation-error",
    "unavailable",
    "interrupted",
    "blocked",
}
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
GATE_REASON_CODES = {
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


class CatalyticSwarm1V6ClosureError(RuntimeError):
    """A v6 completed-response closure invariant was violated."""


class CompletedResponseRejected(CatalyticSwarm1V6ClosureError):
    """A completed response was durably closed and then rejected."""


class CompletedResponsePersistenceError(CatalyticSwarm1V6ClosureError):
    """Ledger persistence failed and the fallback became authoritative."""


class TerminalReconciliationError(CatalyticSwarm1V6ClosureError):
    """Persisted v6 groups do not satisfy terminal accounting."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CatalyticSwarm1V6ClosureError("value is not canonical JSON") from exc


def _bounded_exception(exc: BaseException) -> dict[str, str]:
    exception_type = type(exc).__name__[:128] or "BaseException"
    message_hash = hashlib.sha256(str(exc).encode("utf-8", errors="replace")).hexdigest()
    return {
        "exception_type": exception_type,
        "exception_message_sha256": message_hash,
    }


def _measurement(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result = {} if value is None else dict(value)
    encoded = _canonical_json(result)
    if len(encoded) > 16_384:
        raise CatalyticSwarm1V6ClosureError("boundary measurement exceeds 16384 bytes")
    return json.loads(encoded.decode("utf-8"))


def classify_gate_outcomes(kind: str, outcomes: Mapping[str, Any]) -> tuple[bool, str]:
    order = WARM_GATE_ORDER if kind == "warm" else COMPARISON_GATE_ORDER if kind == "comparison" else None
    if order is None:
        raise CatalyticSwarm1V6ClosureError(f"unknown completed-response kind: {kind}")
    if set(outcomes) != set(order):
        raise CatalyticSwarm1V6ClosureError(f"{kind} gate field set changed")
    for name in order:
        if type(outcomes[name]) is not bool:
            raise CatalyticSwarm1V6ClosureError(f"{kind} gate is not boolean: {name}")
    for name in order:
        if outcomes[name] is not True:
            return False, GATE_REASON_CODES[name]
    return True, "accepted"


@dataclass(frozen=True)
class BoundaryObservation:
    """A non-raising observer classification returned to the group runner."""

    state: str
    reason_code: str
    measurement: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.state not in {"passed", "failed-invariant", "unavailable"}:
            raise CatalyticSwarm1V6ClosureError("observer returned an invalid state")
        if not isinstance(self.reason_code, str) or not self.reason_code:
            raise CatalyticSwarm1V6ClosureError("observer reason code is invalid")
        _measurement(self.measurement)

    @classmethod
    def passed(cls, measurement: Mapping[str, Any] | None = None) -> "BoundaryObservation":
        return cls("passed", "passed", measurement or {})

    @classmethod
    def failed(
        cls, reason_code: str, measurement: Mapping[str, Any] | None = None
    ) -> "BoundaryObservation":
        return cls("failed-invariant", reason_code, measurement or {})

    @classmethod
    def unavailable(
        cls, reason_code: str, measurement: Mapping[str, Any] | None = None
    ) -> "BoundaryObservation":
        return cls("unavailable", reason_code, measurement or {})


def _empty_boundary(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "required": True,
        "attempted": False,
        "attempt_ordinal": None,
        "attempted_at": None,
        "observation_completed": False,
        "state": "blocked",
        "blocked": True,
        "passed": None,
        "reason_code": None,
        "blocked_by": None,
        "exception_type": None,
        "exception_message_sha256": None,
        "measurement": {},
    }


@dataclass
class PostRequestBoundaryGroup:
    request_label: str
    request_sequence_index: int
    kind: str
    group_started_at: str
    boundaries: list[dict[str, Any]] = field(
        default_factory=lambda: [_empty_boundary(name) for name in BOUNDARY_ORDER]
    )
    finalized: bool = False
    ordered_reason_codes: list[str] = field(default_factory=list)
    primary_reason_code: str = "accepted"
    _deferred_interruption: BaseException | None = field(default=None, repr=False)

    @classmethod
    def begin_after_model_completion(
        cls,
        *,
        request_label: str,
        request_sequence_index: int,
        kind: str,
        model_completed: bool,
        clock: Callable[[], str] = _utc_now,
    ) -> "PostRequestBoundaryGroup":
        if model_completed is not True:
            raise CatalyticSwarm1V6ClosureError("boundary group began before model completion")
        if not isinstance(request_label, str) or not request_label:
            raise CatalyticSwarm1V6ClosureError("request label is invalid")
        if type(request_sequence_index) is not int or request_sequence_index < 1:
            raise CatalyticSwarm1V6ClosureError("request sequence index is invalid")
        if kind not in {"warm", "comparison"}:
            raise CatalyticSwarm1V6ClosureError("completed-response kind is invalid")
        started_at = clock()
        if not isinstance(started_at, str) or not started_at:
            raise CatalyticSwarm1V6ClosureError("group timestamp is invalid")
        return cls(request_label, request_sequence_index, kind, started_at)

    @property
    def deferred_interruption(self) -> BaseException | None:
        return self._deferred_interruption

    def execute(
        self,
        observers: Mapping[str, Callable[[], BoundaryObservation]],
        *,
        clock: Callable[[], str] = _utc_now,
        before_callback: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        if self.finalized:
            raise CatalyticSwarm1V6ClosureError("boundary group executed more than once")
        if set(observers) != set(BOUNDARY_ORDER):
            raise CatalyticSwarm1V6ClosureError("post-request observer field set changed")

        interrupted_by: str | None = None
        attempt_ordinal = 0
        for entry in self.boundaries:
            name = entry["name"]
            if interrupted_by is not None:
                entry["state"] = "blocked"
                entry["blocked"] = True
                entry["reason_code"] = f"{name}-blocked-after-{interrupted_by}-interruption"
                entry["blocked_by"] = interrupted_by
                continue

            attempt_ordinal += 1
            entry["attempted"] = True
            entry["blocked"] = False
            entry["attempt_ordinal"] = attempt_ordinal
            try:
                entry["attempted_at"] = clock()
                if before_callback is not None:
                    before_callback(name, dict(entry))
                observation = observers[name]()
                if not isinstance(observation, BoundaryObservation):
                    raise CatalyticSwarm1V6ClosureError("observer did not return BoundaryObservation")
                entry["state"] = observation.state
                entry["reason_code"] = (
                    "passed" if observation.state == "passed" else f"{name}-{observation.reason_code}"
                )
                entry["measurement"] = _measurement(observation.measurement)
                entry["observation_completed"] = observation.state in {
                    "passed",
                    "failed-invariant",
                }
                entry["passed"] = (
                    True if observation.state == "passed"
                    else False if observation.state == "failed-invariant"
                    else None
                )
            except (KeyboardInterrupt, SystemExit) as exc:
                if entry["attempted_at"] is None:
                    entry["attempted_at"] = _utc_now()
                bounded = _bounded_exception(exc)
                entry.update(bounded)
                entry["state"] = "interrupted"
                entry["reason_code"] = f"{name}-interrupted"
                self._deferred_interruption = exc
                interrupted_by = name
            except Exception as exc:
                if entry["attempted_at"] is None:
                    entry["attempted_at"] = _utc_now()
                bounded = _bounded_exception(exc)
                entry.update(bounded)
                entry["state"] = "observation-error"
                entry["reason_code"] = f"{name}-observation-error"

        self.ordered_reason_codes = [
            str(entry["reason_code"])
            for entry in self.boundaries
            if entry["state"] != "passed"
        ]
        self.primary_reason_code = (
            self.ordered_reason_codes[0] if self.ordered_reason_codes else "accepted"
        )
        self.finalized = True
        return self.as_record()

    def as_record(self) -> dict[str, Any]:
        if not self.finalized:
            raise CatalyticSwarm1V6ClosureError("boundary group is not finalized")
        return {
            "schema_version": 1,
            "runtime_version": "v6",
            "request_label": self.request_label,
            "request_sequence_index": self.request_sequence_index,
            "kind": self.kind,
            "model_boundary_completed": True,
            "group_started_at": self.group_started_at,
            "sub_boundaries": json.loads(_canonical_json(self.boundaries).decode("utf-8")),
            "ordered_reason_codes": list(self.ordered_reason_codes),
            "primary_reason_code": self.primary_reason_code,
            "passed": not self.ordered_reason_codes,
        }


@dataclass
class CompletedResponseClosure:
    """V6 completion closure preserving V5 gate and persistence ordering."""

    request_label: str
    request_sequence_index: int
    kind: str
    model_completed: bool = False
    observation_captured: bool = False
    post_request_recorded: bool = False
    persisted: bool = False
    lease_released: bool = False
    gate_accepted: bool = False
    gate_reason_code: str = "request-not-completed"
    metadata: dict[str, Any] = field(default_factory=dict)
    gate_outcomes: dict[str, bool] = field(default_factory=dict)
    post_request_group: PostRequestBoundaryGroup | None = None
    persistence: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_label, str) or not self.request_label:
            raise CatalyticSwarm1V6ClosureError("request label is invalid")
        if type(self.request_sequence_index) is not int or self.request_sequence_index < 1:
            raise CatalyticSwarm1V6ClosureError("request sequence index is invalid")
        if self.kind not in {"warm", "comparison"}:
            raise CatalyticSwarm1V6ClosureError("completed-response kind is invalid")

    @property
    def completion_id(self) -> str:
        return hashlib.sha256(_canonical_json({
            "kind": self.kind,
            "request_label": self.request_label,
            "request_sequence_index": self.request_sequence_index,
            "runtime_version": "v6",
        })).hexdigest()

    @property
    def accepted(self) -> bool:
        return bool(
            self.gate_accepted
            and self.post_request_group is not None
            and self.post_request_group.finalized
            and not self.post_request_group.ordered_reason_codes
        )

    @property
    def all_reason_codes(self) -> list[str]:
        reasons: list[str] = []
        if self.gate_reason_code != "accepted":
            reasons.append(self.gate_reason_code)
        if self.post_request_group is not None and self.post_request_group.finalized:
            reasons.extend(self.post_request_group.ordered_reason_codes)
        return reasons

    @property
    def primary_reason_code(self) -> str:
        reasons = self.all_reason_codes
        return reasons[0] if reasons else "accepted"

    def mark_model_completed(self) -> None:
        if self.model_completed:
            raise CatalyticSwarm1V6ClosureError("model completion marked more than once")
        self.model_completed = True

    def capture(self, metadata: Mapping[str, Any], gate_outcomes: Mapping[str, Any]) -> None:
        if not self.model_completed:
            raise CatalyticSwarm1V6ClosureError("response observation preceded model completion")
        if self.observation_captured:
            raise CatalyticSwarm1V6ClosureError("response observation captured more than once")
        accepted, reason = classify_gate_outcomes(self.kind, gate_outcomes)
        self.metadata = dict(metadata)
        self.gate_outcomes = {name: bool(gate_outcomes[name]) for name in gate_outcomes}
        self.gate_accepted = accepted
        self.gate_reason_code = reason
        self.observation_captured = True

    def capture_instrumentation_failure(
        self, metadata: Mapping[str, Any], *, reason_code: str
    ) -> None:
        if not self.model_completed:
            raise CatalyticSwarm1V6ClosureError("instrumentation failure preceded model completion")
        if self.observation_captured:
            raise CatalyticSwarm1V6ClosureError("response observation captured more than once")
        if not isinstance(reason_code, str) or not reason_code:
            raise CatalyticSwarm1V6ClosureError("instrumentation reason code is invalid")
        self.metadata = dict(metadata)
        self.gate_accepted = False
        self.gate_reason_code = reason_code
        self.observation_captured = True

    def observe_post_request_boundaries(
        self,
        observers: Mapping[str, Callable[[], BoundaryObservation]],
        *,
        clock: Callable[[], str] = _utc_now,
        before_callback: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        if not self.model_completed or not self.observation_captured:
            raise CatalyticSwarm1V6ClosureError("post-request boundary preceded completed observation")
        if self.post_request_recorded:
            raise CatalyticSwarm1V6ClosureError("post-request boundary recorded more than once")
        try:
            group = PostRequestBoundaryGroup.begin_after_model_completion(
                request_label=self.request_label,
                request_sequence_index=self.request_sequence_index,
                kind=self.kind,
                model_completed=self.model_completed,
                clock=clock,
            )
        except (KeyboardInterrupt, SystemExit) as exc:
            group = PostRequestBoundaryGroup(
                self.request_label,
                self.request_sequence_index,
                self.kind,
                _utc_now(),
            )
            group._deferred_interruption = exc
            for entry in group.boundaries:
                entry["state"] = "blocked"
                entry["blocked"] = True
                entry["reason_code"] = "group-start-interrupted"
                entry["blocked_by"] = "group-start"
            group.ordered_reason_codes = [
                "group-start-interrupted" for _entry in group.boundaries
            ]
            group.primary_reason_code = "group-start-interrupted"
            group.finalized = True
            record = group.as_record()
        else:
            record = group.execute(
                observers, clock=clock, before_callback=before_callback
            )
        self.post_request_group = group
        self.post_request_recorded = True
        return record

    def final_metadata(self, *, persistence: str) -> dict[str, Any]:
        if not self.model_completed or not self.observation_captured or not self.post_request_recorded:
            raise CatalyticSwarm1V6ClosureError("completed response is not ready for persistence")
        assert self.post_request_group is not None
        value = dict(self.metadata)
        value.update({
            "schema_version": 1,
            "runtime_version": "v6",
            "completion_id": self.completion_id,
            "request_label": self.request_label,
            "request_sequence_index": self.request_sequence_index,
            "kind": self.kind,
            "model_boundary_completed": True,
            "response_disposition": "accepted" if self.accepted else "rejected",
            "response_reason_code": self.primary_reason_code,
            "gate_outcomes": dict(self.gate_outcomes),
            "response_gate_reason_codes": (
                [] if self.gate_reason_code == "accepted" else [self.gate_reason_code]
            ),
            "post_request_reason_codes": list(self.post_request_group.ordered_reason_codes),
            "all_reason_codes": self.all_reason_codes,
            "post_request_boundary": self.post_request_group.as_record(),
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
            raise CatalyticSwarm1V6ClosureError("completed response persisted more than once")
        primary = self.final_metadata(persistence="ledger")
        try:
            append_ledger(primary)
            sync_ledger()
        except BaseException as exc:
            if getattr(exc, "fallback_safe", False) is not True:
                raise CompletedResponsePersistenceError(
                    f"{self.request_label}: ledger durability is indeterminate; fallback forbidden"
                ) from exc
            original = getattr(exc, "original_exception", exc)
            bounded = _bounded_exception(original)
            fallback = self.final_metadata(persistence="result-fallback")
            fallback["ledger_persistence_failure"] = bounded
            safe_reason = (
                f"{bounded['exception_type']}:"
                f"{bounded['exception_message_sha256']}"
            )
            persist_result_fallback(fallback, safe_reason)
            self.persisted = True
            self.persistence = "result-fallback"
            if isinstance(original, (KeyboardInterrupt, SystemExit)):
                raise original
            raise CompletedResponsePersistenceError(
                f"{self.request_label}: ledger persistence failed after completed response"
            ) from exc
        self.persisted = True
        self.persistence = "ledger"
        return primary

    def mark_lease_released(self) -> None:
        if not self.persisted:
            raise CatalyticSwarm1V6ClosureError("lease released before persistence")
        if self.lease_released:
            raise CatalyticSwarm1V6ClosureError("lease release recorded more than once")
        self.lease_released = True

    def enforce(self) -> None:
        if not self.persisted:
            raise CatalyticSwarm1V6ClosureError("acceptance enforced before persistence")
        if not self.lease_released:
            raise CatalyticSwarm1V6ClosureError("acceptance enforced before lease release")
        assert self.post_request_group is not None
        if self.post_request_group.deferred_interruption is not None:
            raise self.post_request_group.deferred_interruption
        if not self.accepted:
            raise CompletedResponseRejected(
                f"{self.request_label}: completed response rejected: {self.primary_reason_code}"
            )


def _validate_boundary_record(entry: Mapping[str, Any], expected_name: str) -> None:
    if entry.get("name") != expected_name or entry.get("required") is not True:
        raise TerminalReconciliationError("boundary identity or requirement changed")
    state = entry.get("state")
    if state not in BOUNDARY_STATES:
        raise TerminalReconciliationError("boundary state is invalid")
    attempted = entry.get("attempted")
    observed = entry.get("observation_completed")
    passed = entry.get("passed")
    blocked = entry.get("blocked")
    if type(attempted) is not bool or type(observed) is not bool or type(blocked) is not bool:
        raise TerminalReconciliationError("boundary accounting is not boolean")
    if blocked is not (state == "blocked"):
        raise TerminalReconciliationError("boundary blocked flag is inconsistent")
    if state == "blocked":
        if (
            attempted
            or observed
            or passed is not None
            or not entry.get("blocked_by")
            or entry.get("attempt_ordinal") is not None
            or entry.get("attempted_at") is not None
        ):
            raise TerminalReconciliationError("blocked boundary representation is invalid")
    else:
        if (
            not attempted
            or not entry.get("attempted_at")
            or type(entry.get("attempt_ordinal")) is not int
            or int(entry["attempt_ordinal"]) < 1
        ):
            raise TerminalReconciliationError("attempted boundary lacks attempt evidence")
    reason_code = entry.get("reason_code")
    if not isinstance(reason_code, str) or not reason_code:
        raise TerminalReconciliationError("boundary reason code is invalid")
    if state == "passed" and reason_code != "passed":
        raise TerminalReconciliationError("passed boundary reason changed")
    if state != "passed" and state != "blocked" and not reason_code.startswith(
        expected_name + "-"
    ):
        raise TerminalReconciliationError("boundary reason is not namespaced")
    if observed and state not in {"passed", "failed-invariant"}:
        raise TerminalReconciliationError("non-observation state claims a completed observation")
    if state == "passed" and (not observed or passed is not True):
        raise TerminalReconciliationError("pass lacks a completed observation")
    if state == "failed-invariant" and (not observed or passed is not False):
        raise TerminalReconciliationError("failed invariant lacks a completed observation")
    if state in {"observation-error", "unavailable", "interrupted"} and passed is not None:
        raise TerminalReconciliationError("non-measured state has a boolean pass value")
    has_exception = entry.get("exception_type") is not None or entry.get("exception_message_sha256") is not None
    if state in {"observation-error", "interrupted"}:
        if not has_exception or len(str(entry.get("exception_message_sha256"))) != 64:
            raise TerminalReconciliationError("exception state lacks bounded evidence")
    elif has_exception:
        raise TerminalReconciliationError("non-exception state carries exception evidence")


def reconcile_terminal(
    *,
    completed_response_count: int,
    groups: Sequence[Mapping[str, Any]],
    ledger_records: Sequence[Mapping[str, Any]],
    fallback_records: Sequence[Mapping[str, Any]],
    lease_acquired_count: int,
    lease_released_count: int,
    runtime_counters: Mapping[str, Any] | None = None,
    expected_sequence_start: int = 1,
    expected_request_labels: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Validate exact representation, per-boundary accounting, and lease return."""

    if type(completed_response_count) is not int or completed_response_count < 0:
        raise TerminalReconciliationError("completed response count is invalid")
    if len(groups) != completed_response_count:
        raise TerminalReconciliationError("completed responses do not equal boundary groups")
    if len(ledger_records) + len(fallback_records) != completed_response_count:
        raise TerminalReconciliationError("ledger plus fallback does not equal completed responses")
    if lease_acquired_count != completed_response_count or lease_released_count != lease_acquired_count:
        raise TerminalReconciliationError("lease accounting does not close")
    if expected_request_labels is not None and len(expected_request_labels) != completed_response_count:
        raise TerminalReconciliationError("expected request schedule length changed")

    group_ids: list[str] = []
    attempts = {name: 0 for name in BOUNDARY_ORDER}
    blocked = {name: 0 for name in BOUNDARY_ORDER}
    observations = {name: 0 for name in BOUNDARY_ORDER}
    passes = {name: 0 for name in BOUNDARY_ORDER}
    interrupted = {name: 0 for name in BOUNDARY_ORDER}
    for expected_index, group in enumerate(groups, start=expected_sequence_start):
        completion_id = group.get("completion_id")
        if not isinstance(completion_id, str) or len(completion_id) != 64:
            raise TerminalReconciliationError("group completion identity is invalid")
        boundary_group = group.get("post_request_boundary")
        if not isinstance(boundary_group, Mapping):
            raise TerminalReconciliationError("post-request group is absent")
        request_label = group.get("request_label", boundary_group.get("request_label"))
        kind = group.get("kind", boundary_group.get("kind"))
        request_sequence_index = group.get(
            "request_sequence_index", boundary_group.get("request_sequence_index")
        )
        if (
            request_sequence_index != expected_index
            or not isinstance(request_label, str)
            or not request_label
            or kind not in {"warm", "comparison"}
        ):
            raise TerminalReconciliationError("group request identity or order is invalid")
        if (
            expected_request_labels is not None
            and request_label != expected_request_labels[expected_index - expected_sequence_start]
        ):
            raise TerminalReconciliationError("group request label differs from frozen schedule")
        recomputed_id = hashlib.sha256(_canonical_json({
            "kind": kind,
            "request_label": request_label,
            "request_sequence_index": expected_index,
            "runtime_version": "v6",
        })).hexdigest()
        if completion_id != recomputed_id:
            raise TerminalReconciliationError("group completion identity does not recompute")
        group_ids.append(completion_id)
        if (
            boundary_group.get("request_label") != request_label
            or boundary_group.get("request_sequence_index") != expected_index
            or boundary_group.get("kind") != kind
            or boundary_group.get("model_boundary_completed") is not True
        ):
            raise TerminalReconciliationError("post-request group identity changed")
        entries = boundary_group.get("sub_boundaries")
        if not isinstance(entries, list) or len(entries) != len(BOUNDARY_ORDER):
            raise TerminalReconciliationError("post-request boundary count changed")
        expected_attempt_ordinal = 0
        for name, entry in zip(BOUNDARY_ORDER, entries):
            if not isinstance(entry, Mapping):
                raise TerminalReconciliationError("post-request boundary is invalid")
            _validate_boundary_record(entry, name)
            if entry["attempted"]:
                expected_attempt_ordinal += 1
                if entry["attempt_ordinal"] != expected_attempt_ordinal:
                    raise TerminalReconciliationError("boundary attempt order changed")
            attempts[name] += int(entry["attempted"])
            blocked[name] += int(entry["state"] == "blocked")
            observations[name] += int(entry["observation_completed"])
            passes[name] += int(entry["passed"] is True)
            interrupted[name] += int(entry["state"] == "interrupted")
        derived_post_reasons = [
            str(entry["reason_code"])
            for entry in entries
            if entry["state"] != "passed"
        ]
        if (
            boundary_group.get("ordered_reason_codes") != derived_post_reasons
            or boundary_group.get("primary_reason_code")
            != (derived_post_reasons[0] if derived_post_reasons else "accepted")
            or boundary_group.get("passed") is not (not derived_post_reasons)
            or group.get("post_request_reason_codes") != derived_post_reasons
        ):
            raise TerminalReconciliationError("post-request reason projection changed")
        gate_reasons = group.get("response_gate_reason_codes")
        all_reasons = group.get("all_reason_codes")
        if not isinstance(gate_reasons, list) or not isinstance(all_reasons, list):
            raise TerminalReconciliationError("response reason lists are invalid")
        gate_outcomes = group.get("gate_outcomes")
        if not isinstance(gate_outcomes, Mapping):
            raise TerminalReconciliationError("gate outcomes are invalid")
        if gate_outcomes:
            gate_accepted, gate_reason = classify_gate_outcomes(kind, gate_outcomes)
            expected_gate_reasons = [] if gate_accepted else [gate_reason]
            if gate_reasons != expected_gate_reasons:
                raise TerminalReconciliationError("response gate reason projection changed")
        elif len(gate_reasons) != 1:
            raise TerminalReconciliationError("instrumentation failure reason is absent")
        derived_all = [*gate_reasons, *derived_post_reasons]
        if (
            all_reasons != derived_all
            or group.get("response_reason_code")
            != (derived_all[0] if derived_all else "accepted")
            or group.get("response_disposition")
            != ("rejected" if derived_all else "accepted")
        ):
            raise TerminalReconciliationError("response disposition projection changed")

    if len(set(group_ids)) != len(group_ids):
        raise TerminalReconciliationError("duplicate completed-response group")
    represented = [record.get("completion_id") for record in (*ledger_records, *fallback_records)]
    if any(not isinstance(value, str) for value in represented):
        raise TerminalReconciliationError("persisted completion identity is invalid")
    if len(set(represented)) != len(represented):
        raise TerminalReconciliationError("completion has duplicate ledger/fallback representation")
    if represented != group_ids:
        raise TerminalReconciliationError("persisted completion identities do not match groups")
    for record in ledger_records:
        if record.get("completion_persistence") != "ledger":
            raise TerminalReconciliationError("ledger record has the wrong persistence route")
    for record in fallback_records:
        if record.get("completion_persistence") != "result-fallback":
            raise TerminalReconciliationError("fallback record has the wrong persistence route")
    durable_records = [*ledger_records, *fallback_records]
    semantic_keys = (
        "completion_id",
        "model_boundary_completed",
        "response_disposition",
        "response_reason_code",
        "gate_outcomes",
        "response_gate_reason_codes",
        "post_request_reason_codes",
        "all_reason_codes",
        "post_request_boundary",
    )
    for group, durable in zip(groups, durable_records):
        if any(
            _canonical_json(group.get(key)) != _canonical_json(durable.get(key))
            for key in semantic_keys
        ):
            raise TerminalReconciliationError(
                "durable completion semantics differ from boundary group"
            )

    for name in BOUNDARY_ORDER:
        if attempts[name] + blocked[name] != completed_response_count:
            raise TerminalReconciliationError(f"{name} attempt-plus-blocked equation failed")
        if observations[name] > attempts[name]:
            raise TerminalReconciliationError(f"{name} observations exceed attempts")
        if passes[name] > observations[name]:
            raise TerminalReconciliationError(f"{name} passes exceed observations")

    if runtime_counters is not None:
        expected_runtime = {
            "post_request_groups_started": completed_response_count,
            "post_request_attempts": attempts,
            "post_request_observations_completed": observations,
            "post_request_passes": passes,
            "post_request_blocked": blocked,
        }
        for key, expected in expected_runtime.items():
            if runtime_counters.get(key) != expected:
                raise TerminalReconciliationError(
                    f"runtime counter differs from persisted evidence: {key}"
                )

    all_required_attempted = all(
        attempts[name] == completed_response_count for name in BOUNDARY_ORDER
    )
    all_required_passed = all(
        passes[name] == completed_response_count for name in BOUNDARY_ORDER
    )

    return {
        "completed_response_count": completed_response_count,
        "groups_started": len(groups),
        "ledger_count": len(ledger_records),
        "fallback_count": len(fallback_records),
        "lease_acquired_count": lease_acquired_count,
        "lease_released_count": lease_released_count,
        "attempts": attempts,
        "blocked": blocked,
        "observations_completed": observations,
        "passes": passes,
        "interrupted": interrupted,
        "all_required_attempted": all_required_attempted,
        "all_required_passed": all_required_passed,
        "normal_completion": all_required_attempted and all_required_passed,
    }
