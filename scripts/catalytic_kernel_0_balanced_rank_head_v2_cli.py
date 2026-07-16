#!/usr/bin/env python3
"""Canonical CLI bootstrap for deterministic-rank-head CK0 v2.

Executing the historical entrypoint file directly loads it as ``__main__`` and
creates a second function object. The protected live core intentionally accepts
only the canonical imported entrypoint function. This bootstrap imports that
canonical module first, then delegates to its ``main`` function so the caller
identity remains stable without weakening the live-core gate.
"""
from __future__ import annotations

from pathlib import Path

import catalytic_kernel_0_balanced_rank_head_v2_entrypoint as entrypoint
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


def main(*, repository_root: Path, state_root: Path) -> int:
    return entrypoint.main(
        repository_root=repository_root,
        state_root=state_root,
    )


if __name__ == "__main__":
    repository = Path(__file__).resolve().parents[1]
    raise SystemExit(
        main(
            repository_root=repository,
            state_root=repository / run_design.STATE_ROOT,
        )
    )
