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

RSI-0E is implemented and RSI-0F has passed. Candidate source custody is repaired. The next objective is **review the corrected Agents-A1 SHA-256, then authorize one fresh RSI-0G acceptance cycle**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The harmless allowed-path acceptance attempt configured and built after source-custody repair, then correctly rejected the stale evaluator SHA-256 before launch. The refreshed full SHA-256 is `31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2`; it replaces the prior transposed recorded value. Do not retry the cycle in this boundary.

Minimum required work:

```text
1. Review the measured correction to the evaluator model SHA-256.
2. Keep the stable server and stable worktree unchanged.
3. Reapply only the inert `common/` fixture in the candidate worktree.
4. Authorize one new `python scripts/neo_loop.py --hypothesis "..."` cycle from stable.
5. Require every text, reasoning, tool, cancellation, repeat, memory, performance, cleanup, and stable-integrity gate before reviewable acceptance.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
