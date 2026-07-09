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

RSI-0E is implemented and RSI-0F has passed. Candidate source custody, evaluator model identity, and health-probe handling are repaired. The next objective is **establish a Windows-safe candidate VRAM measurement before authorizing another RSI-0G acceptance cycle**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

The harmless allowed-path acceptance attempt configured, built, loaded the candidate model, and reached port 9393. It then stopped at the VRAM gate because Windows NVIDIA per-process telemetry returned `[N/A]` for every process. Do not bypass the 6000 MiB candidate ceiling: establish a trustworthy Windows-safe measurement before another cycle.

Minimum required work:

```text
1. Identify a Windows-safe, candidate-specific VRAM measurement or declare the memory gate blocked.
2. Keep the stable server and stable worktree unchanged.
3. Do not reduce the 6000 MiB ceiling or substitute unverified system-wide memory for candidate memory.
4. Reapply only the inert `common/` fixture after the memory gate is trustworthy.
5. Authorize one new `python scripts/neo_loop.py --hypothesis "..."` cycle only then.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
