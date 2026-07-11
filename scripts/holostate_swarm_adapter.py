#!/usr/bin/env python3
"""Pure adapter between HoloState Fast transport evidence and CatalyticSwarm.

This module does not perform HTTP requests. The local integration supplies a
callback that has already executed one HoloState Fast request under the
protected v4 transport laws. The adapter validates the transport evidence and
parses the bounded structured contribution.

CatalyticSwarm-0 does not assume that arbitrary structured Fast output is
already proven. A separately versioned live protocol must first qualify this
adapter with a parser canary before the 32-worker population is admitted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from catalytic_blackboard import BlackboardEntry, canonical_json_bytes, sha256_bytes
from catalytic_swarm import (
    SwarmError,
    WorkerContribution,
    WorkerSpec,
    contribution_payload_schema,
    parse_contribution,
)


class HoloStateSwarmAdapterError(RuntimeError):
    """The transport or structured contribution failed closed."""


@dataclass(frozen=True)
class FastTransportEvidence:
    accepted: bool
    content: str
    reasoning_present: bool
    tool_call_count: int
    finish_reason: str | None
    prompt_tokens: int | None
    cached_prompt_tokens: int | None
    fresh_prompt_tokens: int | None
    token_evidence_source: str | None
    token_claim_scope: str | None
    terminal_stop_type: str | None
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "content": self.content,
            "reasoning_present": self.reasoning_present,
            "tool_call_count": self.tool_call_count,
            "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens,
            "cached_prompt_tokens": self.cached_prompt_tokens,
            "fresh_prompt_tokens": self.fresh_prompt_tokens,
            "token_evidence_source": self.token_evidence_source,
            "token_claim_scope": self.token_claim_scope,
            "terminal_stop_type": self.terminal_stop_type,
            "content_sha256": self.content_sha256,
        }


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def validate_fast_transport(result: Any) -> FastTransportEvidence:
    """Validate a v4-like thinking-disabled Fast transport result."""
    content_obj = _read(result, "assistant_content", {})
    content = (
        str(content_obj.get("text", ""))
        if isinstance(content_obj, Mapping)
        else str(_read(result, "content", ""))
    )

    reasoning_obj = _read(result, "reasoning_content", {})
    reasoning_present = (
        bool(reasoning_obj.get("present"))
        if isinstance(reasoning_obj, Mapping)
        else bool(_read(result, "reasoning_content", ""))
    )

    tool_calls = _read(result, "tool_calls", [])
    tool_count = (
        int(_read(result, "tool_call_count", len(tool_calls or [])))
        if isinstance(tool_calls, Sequence)
        else int(_read(result, "tool_call_count", 0))
    )
    finish_reason = _read(result, "finish_reason")
    prompt_tokens = _read(result, "prompt_tokens")
    cached_tokens = _read(result, "cached_prompt_tokens")
    fresh_tokens = _read(result, "fresh_prompt_tokens")

    token_evidence = _read(result, "token_evidence", {})
    source = (
        str(token_evidence.get("source"))
        if isinstance(token_evidence, Mapping) and token_evidence.get("source") is not None
        else None
    )
    claim_scope = (
        str(token_evidence.get("claim_scope"))
        if isinstance(token_evidence, Mapping) and token_evidence.get("claim_scope") is not None
        else None
    )
    terminal_stop_type = (
        str(token_evidence.get("terminal_stop_type"))
        if isinstance(token_evidence, Mapping) and token_evidence.get("terminal_stop_type") is not None
        else None
    )
    token_accepted = bool(
        isinstance(token_evidence, Mapping) and token_evidence.get("accepted") is True
    )

    accepted = (
        bool(content)
        and not reasoning_present
        and tool_count == 0
        and finish_reason == "stop"
        and isinstance(prompt_tokens, int)
        and prompt_tokens > 0
        and isinstance(cached_tokens, int)
        and 0 < cached_tokens < prompt_tokens
        and isinstance(fresh_tokens, int)
        and fresh_tokens == prompt_tokens - cached_tokens
        and token_accepted
        and claim_scope in {
            "exact-generated-token-sequence",
            "exact-visible-content-tokenization",
            "exact-visible-content-tokenization-plus-one-terminal-eos-token",
        }
    )
    return FastTransportEvidence(
        accepted=accepted,
        content=content,
        reasoning_present=reasoning_present,
        tool_call_count=tool_count,
        finish_reason=finish_reason,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        cached_prompt_tokens=cached_tokens if isinstance(cached_tokens, int) else None,
        fresh_prompt_tokens=fresh_tokens if isinstance(fresh_tokens, int) else None,
        token_evidence_source=source,
        token_claim_scope=claim_scope,
        terminal_stop_type=terminal_stop_type,
        content_sha256=sha256_bytes(content.encode("utf-8")),
    )


def parse_structured_fast_result(
    result: Any,
    spec: WorkerSpec,
) -> tuple[FastTransportEvidence, WorkerContribution]:
    transport = validate_fast_transport(result)
    if not transport.accepted:
        raise HoloStateSwarmAdapterError("Fast transport evidence failed")
    try:
        payload = json.loads(transport.content)
    except json.JSONDecodeError as exc:
        raise HoloStateSwarmAdapterError("Fast contribution was not valid JSON") from exc
    try:
        contribution = parse_contribution(payload, spec)
    except SwarmError as exc:
        raise HoloStateSwarmAdapterError(str(exc)) from exc
    return transport, contribution


def compact_blackboard_context(
    entries: Sequence[BlackboardEntry],
    *,
    max_bytes: int = 4096,
) -> str:
    """Render bounded prior-phase entries without full transcripts."""
    payload = [
        {
            "entry_id": entry.entry_id,
            "phase": entry.phase,
            "kind": entry.kind,
            "author_worker_id": entry.author_worker_id,
            "body": entry.body,
            "artifact_refs": list(entry.artifact_refs),
        }
        for entry in entries
    ]
    encoded = canonical_json_bytes(payload)
    if len(encoded) > max_bytes:
        raise HoloStateSwarmAdapterError(
            f"blackboard context exceeds {max_bytes} bytes"
        )
    return encoded.decode("utf-8")


def build_worker_messages(
    *,
    objective: str,
    spec: WorkerSpec,
    context_entries: Sequence[BlackboardEntry],
) -> list[dict[str, str]]:
    if not objective.strip():
        raise HoloStateSwarmAdapterError("objective is required")
    context = compact_blackboard_context(context_entries)
    schema = json.dumps(
        contribution_payload_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    system = (
        "You are one CatalyticSwarm-0 micro-worker. "
        "Use only the current assignment and bounded prior-phase blackboard. "
        "Do not emit reasoning. Do not address other workers directly. "
        "Return exactly one compact JSON object matching the supplied schema."
    )
    user = (
        f"OBJECTIVE:\n{objective}\n\n"
        f"WORKER_ID:\n{spec.worker_id}\n\n"
        f"PHASE:\n{spec.phase}\n\n"
        f"ROLE:\n{spec.role}\n\n"
        f"ASSIGNMENT:\n{spec.assignment.format(objective=objective)}\n\n"
        f"ALLOWED_TARGET_WORKER_IDS:\n{json.dumps(list(spec.parent_worker_ids))}\n\n"
        f"PRIOR_PHASE_BLACKBOARD:\n{context}\n\n"
        f"OUTPUT_SCHEMA:\n{schema}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
