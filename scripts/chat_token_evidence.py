#!/usr/bin/env python3
"""Deterministic token evidence for Chat Completions worker lanes.

The pinned Neo3000 Chat Completions stream reports exact visible content and
usage counts but may omit native generated-token arrays entirely.  This module
keeps server-native evidence authoritative when present and permits a narrowly
bounded tokenizer reconstruction only for thinking-disabled, text-only
responses whose visible content is complete and whose reconstructed token count
matches the server-reported completion count exactly.

It does not infer or reconstruct hidden reasoning tokens, tool-call tokens, or
mixed-channel generations.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable


class ChatTokenEvidenceError(RuntimeError):
    """The available transport evidence cannot support a token-sequence claim."""


def token_ids_sha256(token_ids: list[int]) -> str:
    encoded = json.dumps(token_ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


@dataclass(frozen=True)
class ChatTokenEvidence:
    accepted: bool
    source: str
    token_ids: list[int]
    token_count: int
    token_sha256: str
    completion_tokens: int | None
    count_match: bool | None
    native_array_present: bool
    reconstructed: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_native_ids(value: Any) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ChatTokenEvidenceError("native token evidence is not an array")
    parsed: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ChatTokenEvidenceError("native token evidence contains a non-integer token")
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
) -> ChatTokenEvidence:
    """Return fail-closed token evidence for one Chat Completions response.

    Evidence priority:

    1. A non-empty server-native token array whose length exactly matches usage.
    2. Exact tokenizer reconstruction of the visible assistant content, but only
       for thinking-disabled responses with an empty reasoning channel and no
       tool calls.  The reconstructed length must exactly match usage.

    An empty native array is treated as unavailable, not as proof of an empty
    generation.  Reconstruction is forbidden for reasoning or tool responses
    because their hidden/control tokens are not recoverable from visible text.
    """

    if completion_tokens is not None:
        if isinstance(completion_tokens, bool) or not isinstance(completion_tokens, int):
            raise ChatTokenEvidenceError("completion token count is not an integer")
        if completion_tokens < 0:
            raise ChatTokenEvidenceError("completion token count is negative")

    native_ids = _normalize_native_ids(native_token_ids)
    if native_ids:
        count_match = (
            len(native_ids) == completion_tokens
            if completion_tokens is not None
            else None
        )
        return ChatTokenEvidence(
            accepted=count_match is not False,
            source="server-native",
            token_ids=native_ids,
            token_count=len(native_ids),
            token_sha256=token_ids_sha256(native_ids),
            completion_tokens=completion_tokens,
            count_match=count_match,
            native_array_present=True,
            reconstructed=False,
            reason=None if count_match is not False else "native-token-count-mismatch",
        )

    reconstruction_allowed = (
        thinking_disabled
        and reasoning_content == ""
        and not tool_calls
    )
    if not reconstruction_allowed:
        reason = "reconstruction-forbidden-for-reasoning-or-tools"
        return ChatTokenEvidence(
            accepted=False,
            source="unavailable",
            token_ids=[],
            token_count=0,
            token_sha256=token_ids_sha256([]),
            completion_tokens=completion_tokens,
            count_match=False if completion_tokens not in (None, 0) else None,
            native_array_present=False,
            reconstructed=False,
            reason=reason,
        )

    reconstructed_ids = tokenize_visible_content(visible_content)
    if not isinstance(reconstructed_ids, list):
        raise ChatTokenEvidenceError("tokenizer reconstruction did not return an array")
    parsed_reconstructed: list[int] = []
    for item in reconstructed_ids:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ChatTokenEvidenceError("tokenizer reconstruction contains a non-integer token")
        parsed_reconstructed.append(item)

    count_match = (
        len(parsed_reconstructed) == completion_tokens
        if completion_tokens is not None
        else None
    )
    accepted = count_match is not False and bool(parsed_reconstructed or completion_tokens == 0)
    reason: str | None = None
    if not accepted:
        reason = "reconstructed-token-count-mismatch"
    elif completion_tokens is None:
        reason = "completion-count-unavailable"

    return ChatTokenEvidence(
        accepted=accepted,
        source="visible-content-retokenization",
        token_ids=parsed_reconstructed,
        token_count=len(parsed_reconstructed),
        token_sha256=token_ids_sha256(parsed_reconstructed),
        completion_tokens=completion_tokens,
        count_match=count_match,
        native_array_present=False,
        reconstructed=True,
        reason=reason,
    )
