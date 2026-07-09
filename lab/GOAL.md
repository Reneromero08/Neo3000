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

RSI-0E is implemented and RSI-0F has passed. The fresh RSI-0G inert-fixture cycle reached the locked WDDM gate successfully, then rejected at the first text-quality boundary. Matched stable and clean-candidate diagnostics show that `max_tokens` is a shared completion budget under reasoning auto: both emit reasoning only through 192 tokens and final content at 256. The next objective is **review a narrow transport-versus-reasoning evaluator repair before authorizing another RSI-0G cycle**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The stable control and clean manual candidate both stop at 64/96/128/192 completion tokens with `finish_reason=length`, reasoning present, and empty final content; both produce `NEO3000 ONLINE` at 256 with `finish_reason=stop`. The runtime documents request-level `chat_template_kwargs: {"enable_thinking": false}`, and a stable 64-token diagnostic using that field returned final content in 8 completion tokens with no reasoning. This proves final-content transport can be isolated without discarding the separate auto-reasoning requirement. Matched candidate first/warm decode was 15.84/16.23/15.58 TPS and stable repeated decode was 16.61/16.11/15.41 TPS, so the 10 TPS floor is not presently shown to be cold-state invalid.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Review a narrow evaluator repair: the exact-content transport request may use documented request-level `enable_thinking=false`, while the separate reasoning request remains auto and requires nonempty `reasoning_content`.
3. Prove that repair against stable and a clean candidate; do not reduce the exact-content, WDDM, or warm-performance requirements.
4. Authorize exactly one new RSI-0G cycle only after the repaired two-gate behavior is independently evidenced.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
