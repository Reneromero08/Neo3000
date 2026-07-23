#!/usr/bin/env python3
"""Dedicated neo-exp-0065 entrypoint for strict-prefix plus ngram-cache reuse.

The frozen 689-token RAM root, submitted 690-token request, output contract,
T=4 trial geometry, and checkpoint-zero lifecycle remain unchanged. The only
scientific intervention is launch speculative type none -> ngram-cache. The
process-local n-gram history is a declared second carrier; learning warmup is
charged and process retirement is its closure boundary.
"""
from __future__ import annotations

import catalytic_frontier_single_request_latency as latency


if __name__ == "__main__":
    raise SystemExit(
        latency.main(root_boundary="strict-prefix", speculative_mode="ngram-cache")
    )
