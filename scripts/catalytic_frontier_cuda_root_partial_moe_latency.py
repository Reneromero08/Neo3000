#!/usr/bin/env python3
"""Dedicated neo-exp-0068 CUDA-root plus partial-GPU-MoE latency entrypoint."""
from __future__ import annotations

import catalytic_frontier_checkpoint_control as checkpoint
import catalytic_frontier_single_request_latency as latency


if __name__ == "__main__":
    raise SystemExit(
        latency.main(
            root_boundary="strict-prefix",
            root_storage="device",
            runtime_identity="cuda-bundle",
            moe_server_args=checkpoint.PARTIAL_MOE_26_SERVER_ARGS,
        )
    )
