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
    expected_control_content,
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
    completion_tokens: int | None
    token_evidence_source: str | None
    token_claim_scope: str | None
    terminal_stop_type: str | None
    content_sha256: str
    request_contract_valid: bool
    reasons: tuple[str, ...]

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
            "completion_tokens": self.completion_tokens,
            "token_evidence_source": self.token_evidence_source,
            "token_claim_scope": self.token_claim_scope,
            "terminal_stop_type": self.terminal_stop_type,
            "content_sha256": self.content_sha256,
            "request_contract_valid": self.request_contract_valid,
            "reasons": list(self.reasons),
        }


def _strict_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _validate_request_contract(
    result: Mapping[str, Any],
    spec: WorkerSpec | None,
    reasons: list[str],
) -> bool:
    contract = result.get("request_contract")
    required = {
        "worker_id", "root_name", "max_tokens", "thinking_disabled",
        "temperature", "seed", "cache_prompt", "stop_sequences_configured",
    }
    if not isinstance(contract, Mapping) or set(contract) != required:
        reasons.append("request-contract-key-set-mismatch")
        return False
    temperature = contract.get("temperature")
    seed = _strict_int(contract.get("seed"))
    maximum = _strict_int(contract.get("max_tokens"))
    if (
        contract.get("root_name") != "A"
        or maximum is None
        or maximum != 64
        or contract.get("thinking_disabled") is not True
        or isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or float(temperature) != 0.0
        or seed is None
        or contract.get("cache_prompt") is not True
        or contract.get("stop_sequences_configured") is not False
    ):
        reasons.append("request-contract-value-mismatch")
    if spec is not None and (
        contract.get("worker_id") != spec.worker_id
        or contract.get("root_name") != spec.root_name
        or maximum != spec.max_tokens
        or seed != spec.seed
    ):
        reasons.append("request-contract-worker-mismatch")
    if (
        result.get("root_name") != "A"
        or result.get("lane") != "F"
        or _strict_int(result.get("configured_max_tokens")) != 64
    ):
        reasons.append("result-request-identity-mismatch")
    return not any(reason.startswith("request-") or reason.startswith("result-request") for reason in reasons)


def _validate_token_evidence(
    evidence: Any,
    completion_tokens: int | None,
    reasons: list[str],
) -> tuple[str | None, str | None, str | None]:
    if not isinstance(evidence, Mapping):
        reasons.append("visible-token-evidence-missing")
        return None, None, None
    source = evidence.get("source") if isinstance(evidence.get("source"), str) else None
    scope = evidence.get("claim_scope") if isinstance(evidence.get("claim_scope"), str) else None
    terminal_type = (
        evidence.get("terminal_stop_type")
        if isinstance(evidence.get("terminal_stop_type"), str)
        else None
    )
    token_ids = evidence.get("token_ids")
    token_count = _strict_int(evidence.get("token_count"))
    evidence_completion = _strict_int(evidence.get("completion_tokens"))
    if (
        evidence.get("accepted") is not True
        or evidence.get("classification") != "accepted"
        or evidence.get("usage_reconciled") is not True
        or evidence.get("reason") is not None
        or not isinstance(token_ids, list)
        or any(_strict_int(item) is None for item in token_ids)
        or token_count != len(token_ids)
        or evidence.get("token_sha256") != sha256_bytes(canonical_json_bytes(token_ids))
        or evidence_completion != completion_tokens
    ):
        reasons.append("visible-token-evidence-core-mismatch")
        return source, scope, terminal_type
    repeat = evidence.get("tokenizer_repeat")
    if evidence.get("reconstructed") is True and (
        not isinstance(repeat, Mapping)
        or repeat.get("performed") is not True
        or repeat.get("equal") is not True
        or repeat.get("first") != token_ids
        or repeat.get("second") != token_ids
    ):
        reasons.append("visible-tokenizer-repeat-mismatch")

    if (source, scope) == ("server-native", "exact-generated-token-sequence"):
        valid = (
            evidence.get("native_array_present") is True
            and evidence.get("reconstructed") is False
            and evidence.get("count_match") is True
            and evidence.get("usage_delta") == 0
            and evidence.get("terminal_control_token_count") == 0
            and evidence.get("terminal_control_token_id_known") is True
            and evidence.get("full_generated_sequence_known") is True
            and token_count == completion_tokens
        )
    elif (source, scope) == (
        "visible-content-retokenization",
        "exact-visible-content-tokenization",
    ):
        valid = (
            evidence.get("native_array_present") is False
            and evidence.get("reconstructed") is True
            and evidence.get("count_match") is True
            and evidence.get("usage_delta") == 0
            and evidence.get("terminal_control_token_count") == 0
            and evidence.get("terminal_control_token_id_known") is False
            and evidence.get("full_generated_sequence_known") is False
            and token_count == completion_tokens
        )
    elif (source, scope) == (
        "visible-content-retokenization-plus-terminal-control",
        "exact-visible-content-tokenization-plus-one-terminal-eos-token",
    ):
        gate = evidence.get("terminal_eos_gate")
        direct = gate.get("evidence") if isinstance(gate, Mapping) else None
        valid = (
            evidence.get("native_array_present") is False
            and evidence.get("reconstructed") is True
            and evidence.get("count_match") is False
            and evidence.get("usage_delta") == 1
            and evidence.get("terminal_control_token_count") == 1
            and evidence.get("terminal_control_token_id_known") is False
            and evidence.get("terminal_eos_id_known") is False
            and evidence.get("full_generated_sequence_known") is False
            and terminal_type == "eos"
            and evidence.get("terminal_stopping_word") == ""
            and token_count is not None
            and completion_tokens == token_count + 1
            and isinstance(gate, Mapping)
            and gate.get("passed") is True
            and gate.get("reasons") == []
            and isinstance(direct, Mapping)
            and direct.get("observed") is True
            and direct.get("stop") is True
            and direct.get("stop_type") == "eos"
            and direct.get("stopping_word") == ""
            and direct.get("verbose_token_array_length") == 0
        )
    else:
        valid = False
    if not valid:
        reasons.append("visible-token-evidence-claim-mismatch")
    return source, scope, terminal_type


def validate_fast_transport(
    result: Any,
    spec: WorkerSpec | None = None,
) -> FastTransportEvidence:
    """Validate one exact protected v4 thinking-disabled Fast result."""
    reasons: list[str] = []
    if not isinstance(result, Mapping):
        result = {}
        reasons.append("transport-result-not-object")
    request_valid = _validate_request_contract(result, spec, reasons)

    content_obj = result.get("assistant_content")
    content = content_obj.get("text", "") if isinstance(content_obj, Mapping) else ""
    if not isinstance(content, str) or not content:
        content = ""
        reasons.append("assistant-content-missing")
    elif (
        content_obj.get("characters") != len(content)
        or content_obj.get("sha256") != sha256_bytes(content.encode("utf-8"))
        or content_obj.get("first_256") != content[:256]
        or content_obj.get("last_256") != (content[-256:] if content else "")
    ):
        reasons.append("assistant-content-metadata-mismatch")

    reasoning_obj = result.get("reasoning_content")
    reasoning_present = True
    if isinstance(reasoning_obj, Mapping):
        reasoning_present = (
            reasoning_obj.get("present") is not False
            or reasoning_obj.get("characters") != 0
            or reasoning_obj.get("sha256") != sha256_bytes(b"")
            or any(reasoning_obj.get(key) not in (None, "") for key in ("text", "content"))
        )
    if reasoning_present:
        reasons.append("reasoning-channel-not-empty")

    tool_calls = result.get("tool_calls")
    tool_count = len(tool_calls) if isinstance(tool_calls, list) else -1
    explicit_tool_count = result.get("tool_call_count", tool_count)
    if (
        not isinstance(tool_calls, list)
        or tool_calls
        or _strict_int(explicit_tool_count) != 0
        or result.get("tool_calls_sha256") != sha256_bytes(canonical_json_bytes([]))
    ):
        reasons.append("tool-channel-not-empty")
    finish_reason = result.get("finish_reason")
    if finish_reason != "stop":
        reasons.append("finish-reason-not-stop")

    prompt_tokens = _strict_int(result.get("logical_prompt_tokens"))
    cached_tokens = _strict_int(result.get("cached_prompt_tokens"))
    fresh_tokens = _strict_int(result.get("fresh_prompt_tokens"))
    completion_tokens = _strict_int(result.get("completion_tokens"))
    if (
        prompt_tokens is None
        or cached_tokens is None
        or fresh_tokens is None
        or prompt_tokens <= 0
        or not 0 < cached_tokens < prompt_tokens
        or not 0 <= fresh_tokens < prompt_tokens
        or cached_tokens + fresh_tokens != prompt_tokens
        or result.get("prompt_token_identity_matches") is not True
    ):
        reasons.append("prompt-reuse-evidence-invalid")
    if completion_tokens is None or not 0 < completion_tokens <= 64:
        reasons.append("completion-budget-invalid")
    if result.get("accepted") is not True or result.get("http_status") != 200:
        reasons.append("top-level-transport-not-accepted")

    source, claim_scope, terminal_stop_type = _validate_token_evidence(
        result.get("visible_token_evidence"), completion_tokens, reasons
    )
    if spec is not None:
        expected = expected_control_content(spec)
        if content != expected or result.get("expected_content") != expected:
            reasons.append("exact-control-content-mismatch")

    accepted = not reasons and request_valid
    return FastTransportEvidence(
        accepted=accepted,
        content=content,
        reasoning_present=reasoning_present,
        tool_call_count=tool_count,
        finish_reason=finish_reason,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        cached_prompt_tokens=cached_tokens if isinstance(cached_tokens, int) else None,
        fresh_prompt_tokens=fresh_tokens if isinstance(fresh_tokens, int) else None,
        completion_tokens=completion_tokens,
        token_evidence_source=source,
        token_claim_scope=claim_scope,
        terminal_stop_type=terminal_stop_type,
        content_sha256=sha256_bytes(content.encode("utf-8")),
        request_contract_valid=request_valid,
        reasons=tuple(reasons),
    )


def parse_structured_fast_result(
    result: Any,
    spec: WorkerSpec,
) -> tuple[FastTransportEvidence, WorkerContribution]:
    transport = validate_fast_transport(result, spec)
    if not transport.accepted:
        raise HoloStateSwarmAdapterError("Fast transport evidence failed")
    try:
        def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError(f"duplicate JSON key: {key}")
                value[key] = item
            return value

        payload = json.loads(transport.content, object_pairs_hook=strict_object)
    except (json.JSONDecodeError, ValueError) as exc:
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
            "body": entry.to_dict()["body"],
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
        contribution_payload_schema(spec),
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
        f"OUTPUT_SCHEMA:\n{schema}\n\n"
        f"EXPECTED_OUTPUT_JSON:\n{expected_control_content(spec)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
