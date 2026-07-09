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

RSI-0E is implemented and RSI-0F has passed. The next objective is **resolve the candidate CMake generation failure, then rerun RSI-0G acceptance**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The harmless allowed-path acceptance attempt was rejected at candidate CMake configure/generate before launch. This is unrelated build-system drift, so do not change inference behavior or claim acceptance. Isolate the build-generation cause, restore the inert candidate fixture, and rerun the immutable acceptance cycle only after that separate boundary is resolved.

Minimum required work:

```text
1. Inspect the candidate CMake generation failure as a separate build-environment boundary.
2. Keep the stable server and stable worktree unchanged.
3. Once candidate configuration succeeds, restore the inert `common/` fixture in the candidate worktree.
4. Run `python scripts/neo_loop.py --hypothesis "..."` from stable.
5. Require every text, reasoning, tool, cancellation, repeat, memory, performance, cleanup, and stable-integrity gate before reviewable acceptance.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
