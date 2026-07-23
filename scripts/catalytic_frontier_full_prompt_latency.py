#!/usr/bin/env python3
"""Dedicated neo-exp-0063 entrypoint for the 690-token full-prompt RAM root.

All trial geometry, direct controls, timing, lifecycle accounting, identity
custody, and cleanup are inherited from the accepted neo-exp-0062 controller.
Only the reusable root boundary changes from 543 Task-A prompt tokens to the
exact 690-token submitted branch prompt.
"""
from __future__ import annotations

import catalytic_frontier_single_request_latency as latency


if __name__ == "__main__":
    raise SystemExit(latency.main(root_boundary="full-prompt"))
