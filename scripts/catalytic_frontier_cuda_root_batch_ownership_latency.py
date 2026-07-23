#!/usr/bin/env python3
"""Dedicated neo-exp-0072 batch-boundary exact-ownership discriminator.

The exact neo-exp-0071 all-CPU-MoE CUDA-root configuration is preserved.
Only exact listener ownership cadence changes from before and after every
timed request to one exact boundary before and after the bounded timed batch.
Process and stable/candidate health remain checked on every request and while
waiting for model completion.
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
            batch_owned_timed_requests=True,
        )
    )
