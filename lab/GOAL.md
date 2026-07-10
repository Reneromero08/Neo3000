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

The schema-v2 diagnostic stopped before inference because no exact candidate-PID WDDM attribution row was available after model readiness. Its initialization artifact was bounded and explicit, but no matched cold or warm workload ran; overhead and model-runtime bottleneck selection remain unmeasured. Do not rerun this candidate in the current task.

The stable-side diagnostic controller now reuses the proven in-process exact-PID sampler and rejects readiness unless candidate process, health, listener PID, attributed WDDM instances, and the 6000 MiB ceiling agree. Its controller and CPU-only safety suite are protected by the evaluator lock. The next action is one telemetry-only trace-binary launch; matched workloads remain conditional on that launch passing. This is not authorization for optimization, speculative or catalytic inference, autonomous RSI, merging, or automatic promotion.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Preserve schema-v2 bounded aggregation, explicit placement reasons, and proven trace-disabled compile-out behavior.
3. Use the protected diagnostic controller and require its telemetry-only trace-binary launch to pass before inference.
4. Complete matched cold and warm workloads only after exact attribution is live and stable.
```

## Unlock state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

Unlocked: RSI-0E, RSI-0F, and RSI-0G are all supported by executed evidence. Automatic promotion remains disabled.
