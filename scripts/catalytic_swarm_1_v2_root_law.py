#!/usr/bin/env python3
"""Pure exact-public-root cache-admission law for CatalyticSwarm-1 v2.

This module performs no model, network, Git, process, or filesystem operation.
It replaces the disproven legacy common-prefix threshold with the exact
public-root terminal token threshold established by the cache diagnostic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class RootCacheLawError(RuntimeError):
    """The cache observation is malformed or cannot support an admission claim."""


@dataclass(frozen=True)
class RootCacheObservation:
    public_root_terminal_token_index: int
    common_prefix_tokens: int
    legacy_required_cached_prompt_tokens: int
    actual_cached_prompt_tokens: int
    branch_prompt_tokens: int
    fresh_prompt_tokens: int
    completion_tokens: int
    response_completed: bool
    transport_passed: bool
    token_evidence_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RootCacheAdmission:
    classification: str
    admitted: bool
    root_margin_tokens: int
    legacy_threshold_delta_tokens: int
    legacy_threshold_overreach_tokens: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RootCacheLawError(f"{label} must be a nonnegative integer")
    return value


def validate_root_cache_observation(observation: RootCacheObservation) -> None:
    if not isinstance(observation, RootCacheObservation):
        raise RootCacheLawError("observation has the wrong type")
    for name in (
        "public_root_terminal_token_index",
        "common_prefix_tokens",
        "legacy_required_cached_prompt_tokens",
        "actual_cached_prompt_tokens",
        "branch_prompt_tokens",
        "fresh_prompt_tokens",
        "completion_tokens",
    ):
        _require_nonnegative_int(getattr(observation, name), name)
    if observation.public_root_terminal_token_index <= 0:
        raise RootCacheLawError("public-root terminal token index must be positive")
    if observation.branch_prompt_tokens <= 0:
        raise RootCacheLawError("branch prompt token count must be positive")
    if observation.public_root_terminal_token_index > observation.branch_prompt_tokens:
        raise RootCacheLawError("public root extends beyond the branch prompt")
    if observation.common_prefix_tokens > observation.branch_prompt_tokens:
        raise RootCacheLawError("common token prefix exceeds the branch prompt")
    if observation.legacy_required_cached_prompt_tokens > observation.common_prefix_tokens:
        raise RootCacheLawError("legacy threshold exceeds the exact common token prefix")
    if observation.actual_cached_prompt_tokens > observation.branch_prompt_tokens:
        raise RootCacheLawError("actual cached tokens exceed the branch prompt")
    if observation.fresh_prompt_tokens != (
        observation.branch_prompt_tokens - observation.actual_cached_prompt_tokens
    ):
        raise RootCacheLawError("fresh prompt accounting is inconsistent")
    for name in ("response_completed", "transport_passed", "token_evidence_passed"):
        if type(getattr(observation, name)) is not bool:
            raise RootCacheLawError(f"{name} must be boolean")


def adjudicate_root_cache(observation: RootCacheObservation) -> RootCacheAdmission:
    """Admit only when exact prompt geometry and actual cache cover the public root."""
    validate_root_cache_observation(observation)
    root_margin = (
        observation.actual_cached_prompt_tokens
        - observation.public_root_terminal_token_index
    )
    legacy_delta = (
        observation.actual_cached_prompt_tokens
        - observation.legacy_required_cached_prompt_tokens
    )
    legacy_overreach = max(
        0,
        observation.legacy_required_cached_prompt_tokens
        - observation.public_root_terminal_token_index,
    )
    reasons: list[str] = []

    if not observation.response_completed:
        classification = "instrumentation-reject-response-incomplete"
        admitted = False
        reasons.append("the model response did not complete")
    elif not observation.transport_passed or not observation.token_evidence_passed:
        classification = "instrumentation-reject-transport-or-token-evidence"
        admitted = False
        reasons.append("accepted transport and token evidence are required")
    elif observation.common_prefix_tokens < observation.public_root_terminal_token_index:
        classification = "reject-prompt-prefix-diverged-before-root-end"
        admitted = False
        reasons.append("warm and branch token streams diverged before the root ended")
    elif observation.actual_cached_prompt_tokens < observation.public_root_terminal_token_index:
        classification = "reject-public-root-cache-shortfall"
        admitted = False
        reasons.append("actual cache did not cover the complete public root")
    else:
        admitted = True
        if observation.actual_cached_prompt_tokens < observation.legacy_required_cached_prompt_tokens:
            classification = "admit-root-covered-legacy-threshold-overextended"
            reasons.append(
                "actual cache covers the complete root; the legacy threshold is provenance only"
            )
        else:
            classification = "admit-exact-public-root-covered"
            reasons.append("actual cache covers the complete public root")

    return RootCacheAdmission(
        classification=classification,
        admitted=admitted,
        root_margin_tokens=root_margin,
        legacy_threshold_delta_tokens=legacy_delta,
        legacy_threshold_overreach_tokens=legacy_overreach,
        reasons=tuple(reasons),
    )
