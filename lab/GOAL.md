# Active Goal

## RSI-0: Supervised recursive self-improvement substrate

Checkpoint 0 is closed. Neo3000 is baseline-operational. The runtime serves Agents-A1 to Pi correctly, context scales through 60K occupied tokens with a 0.94 degradation ratio, rolling minimum decode is smooth, tools and cancellation are verified, and LM Studio is no longer an unlock dependency.

RSI-0A through RSI-0D are partially or fully complete:

```text
RSI-0A source custody: done
RSI-0B stable/candidate worktrees: design done, live isolation proof still needed
RSI-0C evaluator lockfile and protected mutation preflight: done
RSI-0D neo-loop machinery and enforcement gates: implemented
RSI-0F live rejection cycle: passed
```

## Required result

```text
Stable worktree running Neo3000
+ isolated candidate worktree
+ immutable evaluator with lockfile-protected hashes
+ deterministic neo-loop machinery
+ enforced candidate edit allowlist
+ enforced stop, timeout, memory, port, and cleanup gates
+ supervised rejection cycle demonstrated
+ supervised acceptance cycle demonstrated
+ stable survives all candidate activity
```

## Current boundary

RSI-0E is implemented and RSI-0F has passed. The fresh RSI-0G inert-fixture cycle reached the locked WDDM gate successfully, then rejected at the first text-quality boundary: the exact response streamed reasoning only and no assistant content within 64 tokens. The next objective is **localize that behavior without weakening the evaluator before authorizing another RSI-0G cycle**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The recorded RSI-0G run used candidate PID/listener PID `45840` and only `pid_45840_luid_0x00000000_0x000115ae_phys_0`, with 17 valid WDDM samples, no telemetry failures, and a 2,301,497,344-byte (2,194.88 MiB) peak below the unchanged 6000 MiB ceiling. It built and became healthy, then the smoke request streamed 67 events but left assistant content empty while reasoning consumed the 64-token budget. The controller rejected before reasoning, tool, cancellation, repeated-turn, or performance gates; PID instances disappeared after teardown and stable PID `31188` remained healthy.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Diagnose the exact-text probe's reasoning-only, zero-content response under the locked configuration.
3. Do not weaken the exact-response, 64-token, WDDM, or performance thresholds to obtain a pass.
4. Authorize exactly one new RSI-0G cycle only after a causal remedy is separately evidenced.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
