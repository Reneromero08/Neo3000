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

The schema-v1 candidate is archived at `evidence/checkpoint1a-trace-v1` commit `3e3023fc389a608ec5a5806eb8e1a50a801486d5`. The bounded schema-v2 repair is archived at `evidence/checkpoint1a-trace-v2` commit `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`. Its only trace-disabled cycle returned `reviewable-accept` with every immutable gate passing and normal binaries free of trace-writer strings.

The protected in-process control repair succeeded. Telemetry-only established exact PID/listener/WDDM agreement, and the trace-disabled matched control completed all fixed phases. The single trace-enabled launch then stopped during incomplete cold reasoning when the unchanged v2 candidate explicitly reported truncation/drops at a per-module 24 MiB ceiling. The final artifact remained below the 64 MiB/200,000-record combined ceilings, but no trace-enabled workload phase completed; overhead and model-runtime bottleneck selection therefore remain unmeasured. Do not rerun this candidate in the current task.

The next future supervised objective is one bounded trace-output candidate that prevents per-module limit pressure from truncating cold reasoning while preserving schema v2, explicit drop accounting, trace-disabled compile-out, combined session ceilings, exact-PID control, and all immutable model/runtime gates. This is not authorization for a model optimization, speculative or catalytic inference, autonomous RSI, merging, or automatic promotion.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Preserve schema-v2 bounded aggregation, explicit placement reasons, and proven trace-disabled compile-out behavior.
3. Keep the protected in-process exact-PID diagnostic controller unchanged as the launch authority.
4. Complete matched cold and warm workloads only after exact attribution is live and trace output remains untruncated with zero drops.
```

## Unlock state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

Unlocked: RSI-0E, RSI-0F, and RSI-0G are all supported by executed evidence. Automatic promotion remains disabled.
