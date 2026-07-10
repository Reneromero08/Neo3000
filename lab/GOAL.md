# Active Goal

## Checkpoint 1: Compute map

Checkpoint 0 is closed. Neo3000 is baseline-operational. The runtime serves Agents-A1 to Pi correctly, context scales through 60K occupied tokens with a 0.94 degradation ratio, rolling minimum decode is smooth, tools and cancellation are verified, and LM Studio is no longer an unlock dependency.

RSI-0 is closed with the supervised substrate proven:

```text
RSI-0A source custody: done
RSI-0B stable/candidate worktrees: live isolation proven
RSI-0C evaluator lockfile and protected mutation preflight: proven
RSI-0D neo-loop machinery and enforcement gates: proven
RSI-0F live rejection cycle: passed
RSI-0G live reviewable acceptance cycle: passed
```

## Active bounded objective

```text
Checkpoint 1A:
Create and validate one optional compute-map trace substrate, then use it to localize actual backend placement and the first measurable execution costs.
```

## Current boundary

The authorized RSI-0G cycle returned `reviewable-accept`: the inert candidate fixture passed transport, reasoning, tool, cancellation, repeat, warm-performance, WDDM, cleanup, and stable-integrity gates. Stable PID `31188` was unchanged; candidate PID/listener `38952` tore down and its WDDM instances retired. **RSI-0 is closed; `SUPERVISED_BOUNDED_RSI_AVAILABLE` is unlocked for Level 1 supervised work.**

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The first Checkpoint 1A candidate is retained for review at `3e3023fc389a608ec5a5806eb8e1a50a801486d5`. Its trace-disabled normal cycle passed every immutable gate, but its trace-enabled diagnostic stopped: synchronous per-node writes generated 2.41 million events and about 896 MB before the cold request could complete, and the local telemetry sampler failed exact-PID attribution. Do not rerun this candidate in the current task.

The next future supervised objective is to replace per-node synchronous writes with bounded aggregation, tag intentional CPU-MoE separately from fallback, and validate exact-PID telemetry before any matched diagnostic. This is not authorization for optimization, speculative or catalytic inference, autonomous RSI, merging, or automatic promotion.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Preserve trace schema v1 and the proven trace-disabled compile-out behavior.
3. Bound trace volume and I/O sufficiently to complete matched cold and warm workloads.
4. Add explicit placement reasons and exact-PID telemetry validation without modifying stable inference.
```

## Unlock state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

Unlocked: RSI-0E, RSI-0F, and RSI-0G are all supported by executed evidence. Automatic promotion remains disabled.
