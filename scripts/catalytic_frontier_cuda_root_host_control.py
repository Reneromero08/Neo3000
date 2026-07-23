#!/usr/bin/env python3
"""Dedicated neo-exp-0067 same-runtime host-root control for neo-exp-0066.

The exact CUDA-capable nine-module runtime remains pinned, but root tensors use
the default host carrier. All strict-prefix utility, lifecycle, timing, direct
control, cleanup, and no-fanout geometry stays inherited.
"""
from __future__ import annotations

import catalytic_frontier_single_request_latency as latency


if __name__ == "__main__":
    raise SystemExit(
        latency.main(
            root_boundary="strict-prefix",
            root_storage="host",
            runtime_identity="cuda-bundle",
        )
    )
