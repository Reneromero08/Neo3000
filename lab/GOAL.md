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

RSI-0E is implemented and RSI-0F has passed. The shared-budget boundary is repaired in the evaluator without weakening content, reasoning, WDDM, or warm-performance requirements. Stable and a clean candidate proved the split transport, reasoning, and warm-performance gates. The next objective is **authorize one fresh RSI-0G acceptance cycle under the locked repaired gates**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The transport request now uses only documented `chat_template_kwargs: {"enable_thinking": false}` with the unchanged 64-token exact response; stable passed 3/3 and the clean candidate passed, each with eight completion tokens and no reasoning. The auto-reasoning request now has its matched 768-token shared budget and requires both nonempty reasoning plus `NEO3000 REASONING OK`; stable and candidate passed. Warm performance uses that long deterministic request as one unscored warmup plus two counted runs, preserving the 10 TPS floor; stable counted 16.33/17.03 TPS and candidate counted 17.23/17.76 TPS. Candidate PID/listener `29180` remained below the WDDM ceiling at 2,194.88 MiB across 67 valid samples, then tore down cleanly while stable PID `31188` stayed healthy.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Reapply only the inert `common/` fixture in the candidate worktree.
3. Verify preflight and every locked split gate, including WDDM and counted warm performance.
4. Authorize exactly one new RSI-0G cycle; do not retry or promote automatically.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
