#!/usr/bin/env python3
"""Dedicated neo-exp-0070 all-CPU-MoE CUDA-root control for neo-exp-0069.

The exact CUDA-resident strict-prefix root, nine-module runtime, checkpoint-zero
T=4 geometry, utility, lifecycle, direct controls, and cleanup stay inherited.
Only MoE placement returns from seven GPU expert layers to the default all-CPU
profile, supplying the missing local causal control without rerunning 0069.
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
        )
    )
