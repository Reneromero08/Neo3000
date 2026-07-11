#!/usr/bin/env python3
"""Fast-lane HoloState token evidence adapter.

This module bridges a Chat Completions measurement to the evidence law in
:mod:`chat_token_evidence`.  It is intentionally limited to thinking-disabled,
text-only Fast workers.  Deep/reasoning and tool-call lanes must continue to use
server-native evidence or remain explicit about unavailable full sequences.
"""

from __future__ import annotations

from typing import Any, Callable

from chat_token_evidence import ChatTokenEvidenceError, build_chat_token_evidence


class FastTokenEvidenceError(RuntimeError):
    """A Fast worker cannot support the requested token-evidence claim."""


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def resolve_fast_token_evidence(
    measurement: Any,
    *,
    tokenize_visible_content: Callable[[str], list[int]],
    thinking_disabled: bool,
    allow_terminal_control_accounting: bool = False,
    stop_sequences_configured: bool = False,
) -> dict[str, Any]:
    """Resolve native or bounded reconstructed evidence for one response."""

    try:
        evidence = build_chat_token_evidence(
            native_token_ids=_read(measurement, "generated_token_ids", []),
            completion_tokens=_read(measurement, "completion_tokens"),
            visible_content=str(_read(measurement, "content", "")),
            reasoning_content=str(_read(measurement, "reasoning_content", "")),
            tool_calls=list(_read(measurement, "tool_calls", []) or []),
            thinking_disabled=thinking_disabled,
            tokenize_visible_content=tokenize_visible_content,
            finish_reason=_read(measurement, "finish_reason"),
            stop_sequences_configured=stop_sequences_configured,
            allow_terminal_control_accounting=allow_terminal_control_accounting,
        )
    except ChatTokenEvidenceError as exc:
        raise FastTokenEvidenceError(str(exc)) from exc

    result = evidence.to_dict()
    result["classification"] = "accepted" if evidence.accepted else "instrumentation-reject"
    return result


def evaluate_fast_worker(
    measurement: Any,
    *,
    expected_content: str,
    logical_prompt_tokens: int,
    tokenize_visible_content: Callable[[str], list[int]],
    thinking_disabled: bool = True,
    allow_terminal_control_accounting: bool = False,
    stop_sequences_configured: bool = False,
) -> dict[str, Any]:
    """Apply the complete Fast gate without overstating token provenance."""

    content = str(_read(measurement, "content", ""))
    reasoning = str(_read(measurement, "reasoning_content", ""))
    tool_calls = list(_read(measurement, "tool_calls", []) or [])
    finish_reason = _read(measurement, "finish_reason")
    cached_tokens = _read(measurement, "cached_prompt_tokens")
    prompt_tokens = _read(measurement, "prompt_tokens")

    token_evidence = resolve_fast_token_evidence(
        measurement,
        tokenize_visible_content=tokenize_visible_content,
        thinking_disabled=thinking_disabled,
        allow_terminal_control_accounting=allow_terminal_control_accounting,
        stop_sequences_configured=stop_sequences_configured,
    )

    reasons: list[str] = []
    if content != expected_content:
        reasons.append("exact-content-failed")
    if reasoning:
        reasons.append("reasoning-channel-not-empty")
    if tool_calls:
        reasons.append("unexpected-tool-call")
    if finish_reason != "stop":
        reasons.append("finish-reason-not-stop")
    if not isinstance(cached_tokens, int) or cached_tokens <= 0:
        reasons.append("cached-prompt-tokens-not-positive")
    if not isinstance(prompt_tokens, int) or prompt_tokens <= 0:
        reasons.append("logical-prompt-token-count-unavailable")
    elif not isinstance(cached_tokens, int) or cached_tokens >= prompt_tokens:
        reasons.append("fresh-prompt-work-not-demonstrated")
    if logical_prompt_tokens > 0 and isinstance(prompt_tokens, int) and prompt_tokens != logical_prompt_tokens:
        reasons.append("logical-prompt-token-count-mismatch")
    if not token_evidence["accepted"]:
        reasons.append(token_evidence.get("reason") or "token-evidence-failed")

    accepted = not reasons
    instrumentation_prefixes = (
        "token-",
        "reconstructed-",
        "native-",
        "terminal-control-",
        "completion-count-",
    )
    classification = "accepted"
    if not accepted:
        classification = (
            "instrumentation-reject"
            if any(
                reason.startswith(instrumentation_prefixes)
                or "token-count" in reason
                for reason in reasons
            )
            else "capability-reject"
        )

    return {
        "accepted": accepted,
        "classification": classification,
        "reasons": reasons,
        "expected_content": expected_content,
        "visible_content": content,
        "reasoning_present": bool(reasoning),
        "tool_call_count": len(tool_calls),
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": cached_tokens,
        "fresh_prompt_tokens": (
            prompt_tokens - cached_tokens
            if isinstance(prompt_tokens, int) and isinstance(cached_tokens, int)
            else None
        ),
        "token_evidence": token_evidence,
    }
