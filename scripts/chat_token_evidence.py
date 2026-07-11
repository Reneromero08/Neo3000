#!/usr/bin/env python3
"""Deterministic token evidence for Chat Completions worker lanes.

The pinned Neo3000 Chat Completions stream reports exact visible content and
usage counts but does not serialize per-token IDs for OpenAI-compatible chat
chunks.  The server also increments ``n_decoded`` before stop handling, so an
end-of-generation token is included in ``completion_tokens`` even when it
produces no visible text.

This module keeps server-native token arrays authoritative when present.  When
native arrays are absent, it permits narrowly bounded visible-content
retokenization only for thinking-disabled, text-only responses.  A one-token
usage surplus may be reconciled as an unknown terminal control token only when
the caller explicitly authorizes the pinned server accounting law and supplies
direct final metadata proving ``stop_type == \"eos\"`` with no stopping word or
request-configured stop sequence.

It never invents the terminal token ID and never reconstructs hidden reasoning
or tool-call token sequences.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable


class ChatTokenEvidenceError(RuntimeError):
    """The available transport evidence cannot support the requested claim."""


def token_ids_sha256(token_ids: list[int]) -> str:
    encoded = json.dumps(token_ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


@dataclass(frozen=True)
class ChatTokenEvidence:
    accepted: bool
    source: str
    claim_scope: str
    token_ids: list[int]
    token_count: int
    token_sha256: str
    completion_tokens: int | None
    count_match: bool | None
    usage_delta: int | None
    usage_reconciled: bool
    terminal_control_token_count: int
    terminal_control_token_id_known: bool
    terminal_stop_type: str | None
    terminal_stopping_word: str | None
    full_generated_sequence_known: bool
    native_array_present: bool
    reconstructed: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_ids(value: Any, *, label: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ChatTokenEvidenceError(f"{label} token evidence is not an array")
    parsed: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ChatTokenEvidenceError(f"{label} token evidence contains a non-integer token")
        parsed.append(item)
    return parsed


def build_chat_token_evidence(
    *,
    native_token_ids: Any,
    completion_tokens: int | None,
    visible_content: str,
    reasoning_content: str,
    tool_calls: list[dict[str, Any]],
    thinking_disabled: bool,
    tokenize_visible_content: Callable[[str], list[int]],
    finish_reason: str | None = None,
    terminal_stop_type: str | None = None,
    terminal_stopping_word: str | None = None,
    stop_sequences_configured: bool = False,
    allow_terminal_control_accounting: bool = False,
) -> ChatTokenEvidence:
    """Return fail-closed token evidence for one Chat Completions response."""

    if completion_tokens is not None:
        if isinstance(completion_tokens, bool) or not isinstance(completion_tokens, int):
            raise ChatTokenEvidenceError("completion token count is not an integer")
        if completion_tokens < 0:
            raise ChatTokenEvidenceError("completion token count is negative")

    native_ids = _normalize_ids(native_token_ids, label="native")
    if native_ids:
        usage_delta = completion_tokens - len(native_ids) if completion_tokens is not None else None
        count_match = usage_delta == 0 if usage_delta is not None else None
        accepted = count_match is not False
        return ChatTokenEvidence(
            accepted=accepted,
            source="server-native",
            claim_scope="exact-generated-token-sequence" if accepted else "none",
            token_ids=native_ids,
            token_count=len(native_ids),
            token_sha256=token_ids_sha256(native_ids),
            completion_tokens=completion_tokens,
            count_match=count_match,
            usage_delta=usage_delta,
            usage_reconciled=accepted,
            terminal_control_token_count=0,
            terminal_control_token_id_known=True,
            terminal_stop_type=terminal_stop_type,
            terminal_stopping_word=terminal_stopping_word,
            full_generated_sequence_known=accepted,
            native_array_present=True,
            reconstructed=False,
            reason=None if accepted else "native-token-count-mismatch",
        )

    reconstruction_allowed = thinking_disabled and reasoning_content == "" and not tool_calls
    if not reconstruction_allowed:
        return ChatTokenEvidence(
            accepted=False,
            source="unavailable",
            claim_scope="none",
            token_ids=[],
            token_count=0,
            token_sha256=token_ids_sha256([]),
            completion_tokens=completion_tokens,
            count_match=False if completion_tokens not in (None, 0) else None,
            usage_delta=completion_tokens if completion_tokens is not None else None,
            usage_reconciled=False,
            terminal_control_token_count=0,
            terminal_control_token_id_known=False,
            terminal_stop_type=terminal_stop_type,
            terminal_stopping_word=terminal_stopping_word,
            full_generated_sequence_known=False,
            native_array_present=False,
            reconstructed=False,
            reason="reconstruction-forbidden-for-reasoning-or-tools",
        )

    reconstructed_ids = _normalize_ids(
        tokenize_visible_content(visible_content),
        label="reconstructed",
    )
    if completion_tokens is None:
        return ChatTokenEvidence(
            accepted=False,
            source="visible-content-retokenization",
            claim_scope="none",
            token_ids=reconstructed_ids,
            token_count=len(reconstructed_ids),
            token_sha256=token_ids_sha256(reconstructed_ids),
            completion_tokens=None,
            count_match=None,
            usage_delta=None,
            usage_reconciled=False,
            terminal_control_token_count=0,
            terminal_control_token_id_known=False,
            terminal_stop_type=terminal_stop_type,
            terminal_stopping_word=terminal_stopping_word,
            full_generated_sequence_known=False,
            native_array_present=False,
            reconstructed=True,
            reason="completion-count-unavailable",
        )

    usage_delta = completion_tokens - len(reconstructed_ids)
    exact_visible_only = usage_delta == 0
    terminal_control_reconciled = (
        usage_delta == 1
        and allow_terminal_control_accounting
        and finish_reason == "stop"
        and terminal_stop_type == "eos"
        and terminal_stopping_word == ""
        and not stop_sequences_configured
    )
    accepted = bool(reconstructed_ids or completion_tokens == 0) and (
        exact_visible_only or terminal_control_reconciled
    )

    if exact_visible_only:
        source = "visible-content-retokenization"
        claim_scope = "exact-visible-content-tokenization"
        reason = None
        terminal_count = 0
    elif terminal_control_reconciled:
        source = "visible-content-retokenization-plus-terminal-control"
        claim_scope = "exact-visible-content-tokenization-plus-one-terminal-eos-token"
        reason = None
        terminal_count = 1
    else:
        source = "visible-content-retokenization"
        claim_scope = "none"
        terminal_count = 0
        if usage_delta == 1:
            reason = "terminal-eos-accounting-not-proven"
        else:
            reason = "reconstructed-token-count-mismatch"

    return ChatTokenEvidence(
        accepted=accepted,
        source=source,
        claim_scope=claim_scope,
        token_ids=reconstructed_ids,
        token_count=len(reconstructed_ids),
        token_sha256=token_ids_sha256(reconstructed_ids),
        completion_tokens=completion_tokens,
        count_match=exact_visible_only,
        usage_delta=usage_delta,
        usage_reconciled=accepted,
        terminal_control_token_count=terminal_count,
        terminal_control_token_id_known=False,
        terminal_stop_type=terminal_stop_type,
        terminal_stopping_word=terminal_stopping_word,
        full_generated_sequence_known=False,
        native_array_present=False,
        reconstructed=True,
        reason=reason,
    )
