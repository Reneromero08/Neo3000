#!/usr/bin/env python3
"""Scoped context-checkpoint launch control for catalytic frontier sidecars."""
from __future__ import annotations

import time
from typing import Any, Sequence

import catalytic_frontier_harness as harness


FROZEN_CONTEXT_CHECKPOINTS = 8
NGRAM_CACHE_SERVER_ARGS = ("--spec-type", "ngram-cache")


def normalize_server_launch_args(values: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(values)
    harness.require(
        normalized in ((), NGRAM_CACHE_SERVER_ARGS),
        "scoped server launch arguments must be empty or exact ngram-cache",
    )
    return normalized


class ScopedCheckpointDiscoverySidecar(harness.DiscoverySidecar):
    """Apply one checkpoint-count launch intervention and always restore the controller global."""

    def __init__(
        self,
        *args: Any,
        context_checkpoints: int,
        readiness_deadline_seconds_after_identity: float | None = None,
        server_launch_args: Sequence[str] = (),
        **kwargs: Any,
    ):
        harness.require(
            context_checkpoints in (0, FROZEN_CONTEXT_CHECKPOINTS),
            "context checkpoint override must be exactly 0 or 8",
        )
        if readiness_deadline_seconds_after_identity is not None:
            harness.require(
                readiness_deadline_seconds_after_identity > 0,
                "deferred readiness deadline must be positive",
            )
        super().__init__(*args, **kwargs)
        self.context_checkpoints = context_checkpoints
        self.readiness_deadline_seconds_after_identity = readiness_deadline_seconds_after_identity
        self.scoped_server_launch_args = normalize_server_launch_args(server_launch_args)

    def server_launch_args(self) -> list[str]:
        return list(getattr(self, "scoped_server_launch_args", ()))

    def runtime_identities(self) -> tuple[dict[str, Any], dict[str, Any]]:
        identities = super().runtime_identities()
        if self.readiness_deadline_seconds_after_identity is not None:
            harness.require(
                self.readiness_control is not None,
                "deferred readiness deadline requires controlled readiness",
            )
            harness.require(self.readiness_deadline_at is None, "readiness deadline already started")
            self.readiness_deadline_at = (
                time.monotonic() + self.readiness_deadline_seconds_after_identity
            )
        return identities

    def launch(self) -> dict[str, Any]:
        previous = int(harness.live_runtime.CTX_CHECKPOINTS)
        harness.require(
            previous == FROZEN_CONTEXT_CHECKPOINTS,
            "LiveSidecar checkpoint baseline drifted from 8",
        )
        harness.live_runtime.CTX_CHECKPOINTS = self.context_checkpoints
        try:
            readiness = dict(super().launch())
        finally:
            harness.live_runtime.CTX_CHECKPOINTS = previous
        readiness["launch_configuration"] = {
            "n_batch": 512,
            "n_ubatch": 128,
            "context_checkpoints": self.context_checkpoints,
            "checkpoint_min_step": int(harness.live_runtime.CHECKPOINT_MIN_STEP),
            "global_restored_after_launch": harness.live_runtime.CTX_CHECKPOINTS == previous,
            "server_launch_args": self.server_launch_args(),
            "speculative_type": "ngram-cache" if tuple(self.server_launch_args()) == NGRAM_CACHE_SERVER_ARGS else "none",
        }
        return readiness
