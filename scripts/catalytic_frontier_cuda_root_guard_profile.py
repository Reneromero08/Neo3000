#!/usr/bin/env python3
"""Dedicated neo-exp-0071 observation-only guard-phase profile.

The exact neo-exp-0070 all-CPU-MoE CUDA-root configuration and every custody
check remain unchanged.  The only intervention records wall time for the
existing pre/request/post guard phases so controller overhead can be localized
before any safety check is moved or removed.
"""
from __future__ import annotations

import catalytic_frontier_checkpoint_control as checkpoint
import catalytic_frontier_single_request_latency as latency


if __name__ == "__main__":
    raise SystemExit(
        latency.main(
            root_boundary="strict-prefix",
            speculative_mode="none",
            root_storage="device",
            runtime_identity="cuda-bundle",
            moe_server_args=checkpoint.DEFAULT_MOE_SERVER_ARGS,
            guard_phase_profiling=True,
        )
    )
