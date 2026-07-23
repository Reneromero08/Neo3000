#!/usr/bin/env python3
"""Dedicated neo-exp-0066 CUDA-resident strict-prefix root discriminator.

The accepted 689-token RAM root, submitted 690-token request, output contract,
checkpoint-zero T=4 geometry, and no-speculation control remain unchanged. The
only scientific intervention moves exact polymorphic tensor snapshots from host
serialization to retained CUDA buffers with explicit byte accounting and erase.
"""
from __future__ import annotations

import catalytic_frontier_single_request_latency as latency


if __name__ == "__main__":
    raise SystemExit(
        latency.main(root_boundary="strict-prefix", speculative_mode="none", root_storage="device")
    )
