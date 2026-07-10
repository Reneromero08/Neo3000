# Active Goal

## Checkpoint 2: HoloState-v1 reasoning-budget qualification boundary

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

Checkpoint 1A remains active and paused. Its proven trace-disabled compile-out, bounded aggregation, exact-PID control, and drop detection are preserved; overhead, a completed workload map, and causal bottleneck selection remain unproven.

Checkpoint 2 remains active. Its original HoloState-v1 integration attempt is complete and inconclusive: process-local reuse succeeded, while the operational quality gate stopped at the unqualified shared 768-token reasoning budget.

## Active bounded objective

```text
Qualify the minimum sufficient HoloState-v1 reasoning budget from 1024, 1280, 1536, and 2048.
If qualification passes, lock the smallest passing budget and run one newly authorized two-root validation under that immutable contract.
```

## Current boundary

The authorized RSI-0G cycle returned `reviewable-accept`: the inert candidate fixture passed transport, reasoning, tool, cancellation, repeat, warm-performance, WDDM, cleanup, and stable-integrity gates. Stable PID `31188` was unchanged; candidate PID/listener `38952` tore down and its WDDM instances retired. **RSI-0 is closed; `SUPERVISED_BOUNDED_RSI_AVAILABLE` is unlocked for Level 1 supervised work.**

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

Commit and push the protected controller/contract repair, then run the one-shot `qualify-budget` operation. Do not retry qualification. Do not begin HoloState-v2 persistence, port upstream patches, weaken reasoning, or alter the exact-final/reuse gates.

The schema-v1 candidate is archived at `evidence/checkpoint1a-trace-v1` commit `3e3023fc389a608ec5a5806eb8e1a50a801486d5`. The bounded schema-v2 repair is archived at `evidence/checkpoint1a-trace-v2` commit `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`. Its only trace-disabled cycle returned `reviewable-accept` with every immutable gate passing and normal binaries free of trace-writer strings.

The protected in-process control repair succeeded. Telemetry-only established exact PID/listener/WDDM agreement, and the trace-disabled matched control completed all fixed phases. The single trace-enabled launch then stopped during incomplete cold reasoning when the unchanged v2 candidate explicitly reported truncation/drops at a per-module 24 MiB ceiling. The final artifact remained below the 64 MiB/200,000-record combined ceilings, but no trace-enabled workload phase completed; overhead and model-runtime bottleneck selection therefore remain unmeasured. Do not rerun this candidate in the current task.

Checkpoint 1A preserves proven trace-disabled compile-out, bounded aggregation, exact-PID protected launch control, and explicit truncation/drop detection. Trace overhead, a completed workload compute map, and model-runtime bottleneck selection remain unproven.

HoloState-0 proved the current carrier. Process-local RAM/checkpoint reuse avoided 7,387 of 7,519 rendered prompt evaluations while preserving exact cleaned greedy token IDs, reasoning hashes, final content, and A/B/A/B branch behavior. That capability is now the first Checkpoint 2 intervention under the name **HoloState-v1 Live Prefix Lattice**.

Restart persistence remains separate. Save/erase/restore stayed exact in-process, but the live RAM/checkpoint cache makes the slot-file carrier ambiguous. Across restart, the same identity-bound 231,311,464-byte file reported 8,069 restored tokens but avoided zero prompt evaluations. The future restart-persistence intervention is **HoloState-v2 Durable Capsule**, and it remains unproven.

Catalytic declaration:

```text
expensive operation: canonical-prefix prompt evaluation
borrowed carrier: exact process-local hybrid prefix state
transformation: evaluate one divergent suffix or branch
extracted result: deterministic reasoning, final content, or tool call
restoration or closure: preserve the canonical checkpoint lattice for later branches
retained lawful state: model/configuration/prefix-identity-bound live cache entries
```

Minimum required work:

```text
1. Preserve the original 768-token attempt marker/result byte-for-byte as lower-bound evidence.
2. Qualify Root A/A1 once in ascending order and stop at the first accepted budget or after 2048.
3. If a budget passes, lock the smallest passing value in the complete evaluator contract before validation.
4. Run exactly one versioned two-root validation only after qualification, with tool and cancellation/recovery probes and 20 extended requests.
5. Keep HoloState-v2 Durable Capsule as a separate future durability intervention.
```

## Executed HoloState-v1 boundary

- Protected controller and 15-test CPU-only safety suite are implemented and evaluator-locked.
- Root A warmed at 7,150 rendered tokens in 159,051.535 ms; root B warmed at 4,879 tokens in 101,519.304 ms.
- A1 showed process-local performance reuse: 7,165 logical, 148 fresh, inferred 7,017 reused, 3,685.92 ms prompt time, and 43.151x warm/reuse prompt-time amplification.
- A1 consumed the full 768-token completion allowance and failed the combined deterministic output gate. Exact failed-branch token/reasoning hashes were not retained by the validation result.
- Stop-on-first-failure prevented B1/A2/B2, full interleaving, cache eviction observation, and the extended proof. No retry or restart occurred.
- Sidecar PID/listener `42076` peaked at 2,252.88 MiB over 139 exact-PID WDDM samples and retired cleanly. Stable PID `31188` remained healthy and unchanged.

## Unlock state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
```

The global claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`. Automatic promotion remains disabled. `PROCESS_LOCAL_HOLOSTATE_AVAILABLE` is locked. `RESTART_PERSISTENT_HOLOSTATE_AVAILABLE` is locked.
