# Active Goal

## RSI-0: Supervised recursive self-improvement substrate

Checkpoint 0 is closed. Neo3000 is baseline-operational. The runtime serves Agents-A1 to Pi correctly, context scales through 60K occupied tokens with a 0.94 degradation ratio, rolling minimum decode is smooth, tools and cancellation are verified, and LM Studio is no longer an unlock dependency.

RSI-0A through RSI-0D are partially or fully complete:

```text
RSI-0A source custody: done
RSI-0B stable/candidate worktrees: design done, live isolation proof still needed
RSI-0C evaluator lockfile and protected mutation preflight: done
RSI-0D neo-loop machinery and enforcement gates: implemented; live cycle evidence still needed
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

RSI-0E is implemented. The next objective is **RSI-0F: prove a live supervised rejection cycle**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

With the stable server running on port 9292 and `NEO3000_MODEL` set to the verified Agents-A1 GGUF, run one protected-path rejection cycle through `neo-loop`. Confirm stable health before and after candidate cleanup, then proceed to the harmless acceptance cycle.

Minimum required work:

```text
1. Start the known stable launch profile on port 9292.
2. Set `NEO3000_MODEL` to the verified Agents-A1 GGUF.
3. Make one deliberate protected-path change only in the candidate worktree.
4. Run `python scripts/neo_loop.py --hypothesis "..."` from stable.
5. Confirm the rejection record, candidate cleanup, and unchanged stable health/hashes.
6. Restore the candidate worktree, then perform the harmless allowed-path acceptance cycle.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
