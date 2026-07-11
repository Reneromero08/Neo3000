#!/usr/bin/env python3
"""Extract bounded terminal-stop metadata from Neo3000 chat SSE events.

The pinned server attaches its non-OAI final result under ``__verbose`` on a
final Chat Completions chunk.  In stream mode that object intentionally carries
an empty token array, but it still exposes ``stop_type`` and ``stopping_word``.
This module captures only those non-sensitive control fields and rejects
conflicting or malformed terminal evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class TerminalEvidenceError(RuntimeError):
    """Terminal stream metadata is malformed or contradictory."""


@dataclass(frozen=True)
class TerminalStopEvidence:
    observed: bool
    stop: bool
    stop_type: str
    stopping_word: str
    verbose_token_array_length: int | None
    event_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_terminal_stop_evidence(
    event: dict[str, Any],
    *,
    event_index: int,
) -> TerminalStopEvidence | None:
    """Extract one final ``__verbose`` stop record when present."""

    verbose = event.get("__verbose")
    if not isinstance(verbose, dict):
        return None
    if not any(key in verbose for key in ("stop", "stop_type", "stopping_word")):
        return None

    stop = verbose.get("stop")
    stop_type = verbose.get("stop_type")
    stopping_word = verbose.get("stopping_word")
    if not isinstance(stop, bool):
        raise TerminalEvidenceError("verbose terminal stop flag is not boolean")
    if not isinstance(stop_type, str):
        raise TerminalEvidenceError("verbose terminal stop_type is not text")
    if stop_type not in {"eos", "word", "limit", "none"}:
        raise TerminalEvidenceError(f"unsupported verbose terminal stop_type: {stop_type}")
    if not isinstance(stopping_word, str):
        raise TerminalEvidenceError("verbose terminal stopping_word is not text")

    tokens = verbose.get("tokens")
    token_length: int | None = None
    if tokens is not None:
        if not isinstance(tokens, list):
            raise TerminalEvidenceError("verbose terminal token field is not an array")
        token_length = len(tokens)

    return TerminalStopEvidence(
        observed=True,
        stop=stop,
        stop_type=stop_type,
        stopping_word=stopping_word,
        verbose_token_array_length=token_length,
        event_index=event_index,
    )


def merge_terminal_stop_evidence(
    current: TerminalStopEvidence | None,
    incoming: TerminalStopEvidence | None,
) -> TerminalStopEvidence | None:
    """Keep one exact terminal record and reject contradictory duplicates."""

    if incoming is None:
        return current
    if current is None:
        return incoming
    comparable_current = (
        current.stop,
        current.stop_type,
        current.stopping_word,
        current.verbose_token_array_length,
    )
    comparable_incoming = (
        incoming.stop,
        incoming.stop_type,
        incoming.stopping_word,
        incoming.verbose_token_array_length,
    )
    if comparable_current != comparable_incoming:
        raise TerminalEvidenceError("conflicting terminal stop evidence")
    return current


def terminal_eos_gate(evidence: TerminalStopEvidence | None) -> dict[str, Any]:
    """Require the exact stream-mode EOS shape used for terminal reconciliation."""

    reasons: list[str] = []
    if evidence is None or not evidence.observed:
        reasons.append("terminal-stop-evidence-missing")
    else:
        if evidence.stop is not True:
            reasons.append("terminal-stop-flag-not-true")
        if evidence.stop_type != "eos":
            reasons.append("terminal-stop-type-not-eos")
        if evidence.stopping_word != "":
            reasons.append("terminal-stopping-word-not-empty")
        if evidence.verbose_token_array_length != 0:
            reasons.append("terminal-stream-token-array-not-empty")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "evidence": evidence.to_dict() if evidence is not None else None,
    }
