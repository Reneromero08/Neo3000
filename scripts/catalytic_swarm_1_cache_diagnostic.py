#!/usr/bin/env python3
"""Pure cache-admission analysis for the CatalyticSwarm-1 successor.

This module performs no model, network, Git, process, or filesystem operation.
It classifies exact measurements captured by a separately wired live diagnostic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

DIAGNOSTIC_ID = "catalytic-swarm-1-cache-admission-v1"
PROBE_LABELS = ("minimal-branch", "realistic-first-turn")
MAX_MODEL_REQUESTS = 3


class CacheDiagnosticError(RuntimeError):
    """The diagnostic observation or frozen law is malformed."""


@dataclass(frozen=True)
class CacheProbeObservation:
    label: str
    request_sequence_index: int
    warm_prompt_tokens: int
    branch_prompt_tokens: int
    public_root_terminal_token_index: int
    common_prefix_tokens: int
    required_cached_prompt_tokens: int
    actual_cached_prompt_tokens: int
    fresh_prompt_tokens: int
    completion_tokens: int
    cache_checkpoint_min_step: int
    response_completed: bool
    transport_passed: bool
    token_evidence_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CacheProbeVerdict:
    label: str
    classification: str
    root_reuse_proven: bool
    shortfall_tokens: int
    proof_overreach_tokens: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


@dataclass(frozen=True)
class CacheDiagnosticVerdict:
    diagnostic_id: str
    verdict: str
    cache_admission: str
    observations: tuple[CacheProbeVerdict, ...]
    automatic_promotion: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "verdict": self.verdict,
            "cache_admission": self.cache_admission,
            "observations": [item.to_dict() for item in self.observations],
            "automatic_promotion": self.automatic_promotion,
            "reasons": list(self.reasons),
        }


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CacheDiagnosticError(f"{label} must be a nonnegative integer")
    return value


def validate_observation(observation: CacheProbeObservation) -> None:
    if not isinstance(observation, CacheProbeObservation):
        raise CacheDiagnosticError("observation has the wrong type")
    if observation.label not in PROBE_LABELS:
        raise CacheDiagnosticError("observation label is not frozen")
    if observation.request_sequence_index not in (2, 3):
        raise CacheDiagnosticError("probe request sequence must be 2 or 3")
    for name in (
        "warm_prompt_tokens",
        "branch_prompt_tokens",
        "public_root_terminal_token_index",
        "common_prefix_tokens",
        "required_cached_prompt_tokens",
        "actual_cached_prompt_tokens",
        "fresh_prompt_tokens",
        "completion_tokens",
        "cache_checkpoint_min_step",
    ):
        _require_nonnegative_int(getattr(observation, name), name)
    if observation.warm_prompt_tokens <= 0 or observation.branch_prompt_tokens <= 0:
        raise CacheDiagnosticError("prompt token counts must be positive")
    if observation.public_root_terminal_token_index <= 0:
        raise CacheDiagnosticError("public-root terminal token index must be positive")
    if observation.public_root_terminal_token_index > min(
        observation.warm_prompt_tokens, observation.branch_prompt_tokens
    ):
        raise CacheDiagnosticError("public root extends beyond a rendered prompt")
    if observation.common_prefix_tokens > min(
        observation.warm_prompt_tokens, observation.branch_prompt_tokens
    ):
        raise CacheDiagnosticError("common prefix exceeds a rendered prompt")
    if observation.required_cached_prompt_tokens > observation.common_prefix_tokens:
        raise CacheDiagnosticError("required cache exceeds the proven common prefix")
    if observation.actual_cached_prompt_tokens > observation.branch_prompt_tokens:
        raise CacheDiagnosticError("actual cache exceeds branch prompt length")
    if observation.actual_cached_prompt_tokens > observation.common_prefix_tokens:
        raise CacheDiagnosticError("actual cache exceeds the exact common token prefix")
    if observation.fresh_prompt_tokens != (
        observation.branch_prompt_tokens - observation.actual_cached_prompt_tokens
    ):
        raise CacheDiagnosticError("fresh prompt accounting is inconsistent")
    if observation.cache_checkpoint_min_step <= 0:
        raise CacheDiagnosticError("checkpoint minimum step must be positive")
    if type(observation.response_completed) is not bool:
        raise CacheDiagnosticError("response_completed must be boolean")
    if type(observation.transport_passed) is not bool:
        raise CacheDiagnosticError("transport_passed must be boolean")
    if type(observation.token_evidence_passed) is not bool:
        raise CacheDiagnosticError("token_evidence_passed must be boolean")


def classify_probe(observation: CacheProbeObservation) -> CacheProbeVerdict:
    validate_observation(observation)
    reasons: list[str] = []
    shortfall = max(
        0,
        observation.public_root_terminal_token_index
        - observation.actual_cached_prompt_tokens,
    )
    overreach = max(
        0,
        observation.required_cached_prompt_tokens
        - observation.public_root_terminal_token_index,
    )

    if not observation.response_completed:
        classification = "response-incomplete"
        reasons.append("model response did not complete")
    elif not observation.transport_passed or not observation.token_evidence_passed:
        classification = "transport-or-token-evidence-failed"
        reasons.append("cache geometry cannot be adjudicated without accepted transport")
    elif observation.common_prefix_tokens < observation.public_root_terminal_token_index:
        classification = "prompt-prefix-diverged-before-root-end"
        reasons.append("warm and branch token streams diverged before the public root ended")
    elif observation.actual_cached_prompt_tokens == 0:
        classification = "cache-session-reuse-failed"
        reasons.append("server reported zero cached prompt tokens")
    elif observation.actual_cached_prompt_tokens >= observation.public_root_terminal_token_index:
        if observation.actual_cached_prompt_tokens < observation.required_cached_prompt_tokens:
            classification = "proof-threshold-overextended"
            reasons.append("actual cache covers the root but not the stronger computed threshold")
        else:
            classification = "exact-root-reuse-proven"
            reasons.append("actual cache covers the complete public root")
    else:
        classification = "checkpoint-shortfall"
        reasons.append("cache hit stops before the public root terminal token")
        if shortfall < observation.cache_checkpoint_min_step:
            reasons.append("shortfall is smaller than one configured checkpoint step")

    return CacheProbeVerdict(
        label=observation.label,
        classification=classification,
        root_reuse_proven=classification in {
            "exact-root-reuse-proven",
            "proof-threshold-overextended",
        },
        shortfall_tokens=shortfall,
        proof_overreach_tokens=overreach,
        reasons=tuple(reasons),
    )


def classify_diagnostic(
    observations: Sequence[CacheProbeObservation],
) -> CacheDiagnosticVerdict:
    if len(observations) != 2:
        raise CacheDiagnosticError("diagnostic requires exactly two branch probes")
    if tuple(item.label for item in observations) != PROBE_LABELS:
        raise CacheDiagnosticError("probe order differs from the frozen diagnostic")
    if tuple(item.request_sequence_index for item in observations) != (2, 3):
        raise CacheDiagnosticError("request sequence differs from the frozen diagnostic")

    probe_verdicts = tuple(classify_probe(item) for item in observations)
    classes = tuple(item.classification for item in probe_verdicts)
    reasons: list[str] = []

    if any(name == "prompt-prefix-diverged-before-root-end" for name in classes):
        verdict = "reject"
        cache_admission = "prompt-geometry-mismatch"
        reasons.append("at least one branch did not preserve the token-identical public root")
    elif all(item.root_reuse_proven for item in probe_verdicts):
        if "proof-threshold-overextended" in classes:
            verdict = "reviewable-accept"
            cache_admission = "root-reuse-proven-proof-law-repair-required"
            reasons.append("both probes cover the public root; the old threshold was too strong")
        else:
            verdict = "reviewable-accept"
            cache_admission = "exact-root-reuse-proven"
            reasons.append("both probes prove complete public-root reuse")
    elif len(set(classes)) > 1 and all(
        item.response_completed and item.transport_passed and item.token_evidence_passed
        for item in observations
    ):
        verdict = "inconclusive"
        cache_admission = "unstable-or-geometry-dependent-reuse"
        reasons.append("the two probes produced different cache-admission classes")
    elif all(name == "checkpoint-shortfall" for name in classes):
        checkpoints = {
            item.actual_cached_prompt_tokens for item in observations
        }
        if len(checkpoints) == 1:
            verdict = "reviewable-accept"
            cache_admission = "stable-checkpoint-shortfall"
            reasons.append("both probes hit the same checkpoint before the public-root boundary")
        else:
            verdict = "inconclusive"
            cache_admission = "unstable-or-geometry-dependent-reuse"
            reasons.append("the two probes stopped at different cached checkpoints")
    elif all(name == "cache-session-reuse-failed" for name in classes):
        verdict = "reject"
        cache_admission = "cache-session-reuse-failed"
        reasons.append("neither probe observed any reusable prompt cache")
    elif any(name == "transport-or-token-evidence-failed" for name in classes):
        verdict = "instrumentation-reject"
        cache_admission = "unadjudicated"
        reasons.append("transport or token evidence failed")
    else:
        verdict = "inconclusive"
        cache_admission = "unadjudicated"
        reasons.append("cache behavior did not satisfy a complete causal class")

    return CacheDiagnosticVerdict(
        diagnostic_id=DIAGNOSTIC_ID,
        verdict=verdict,
        cache_admission=cache_admission,
        observations=probe_verdicts,
        automatic_promotion=False,
        reasons=tuple(reasons),
    )


def validate_persisted_observation(value: Mapping[str, Any]) -> CacheProbeObservation:
    if not isinstance(value, Mapping):
        raise CacheDiagnosticError("persisted observation must be an object")
    expected = set(CacheProbeObservation.__dataclass_fields__)
    if set(value) != expected:
        raise CacheDiagnosticError("persisted observation key set changed")
    observation = CacheProbeObservation(**{name: value[name] for name in expected})
    validate_observation(observation)
    return observation
