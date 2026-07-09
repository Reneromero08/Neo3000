# Active Goal

## RSI-0: Supervised recursive self-improvement substrate

Checkpoint 0 is closed. Neo3000 is baseline-operational. The runtime serves Agents-A1 to Pi correctly, context scales through 60K occupied tokens with a 0.94 degradation ratio, rolling minimum decode is smooth, tools and cancellation are verified, and LM Studio is no longer an unlock dependency.

RSI-0A through RSI-0D are partially or fully complete:

```text
RSI-0A source custody: done
RSI-0B stable/candidate worktrees: design done, live isolation proof still needed
RSI-0C evaluator manifest: core done, lockfile and mutation test still needed
RSI-0D neo-loop machinery: core done, enforcement gates still needed
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

The next objective is **RSI-0E: enforce stop and isolation gates**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

Harden `neo-loop` so a candidate cannot corrupt the evaluator, task board, stable worktree, stable server, model identity, build directories, runtime directories, or promotion rules.

Minimum required work:

```text
1. Add evaluator lockfile or equivalent precomputed protected-hash manifest.
2. Enforce candidate diff allowlist.
3. Enforce protected-path rejection.
4. Enforce build, health, benchmark, and process timeouts.
5. Enforce memory ceiling for candidate runs.
6. Enforce port and build-directory separation.
7. Enforce candidate cleanup on success, failure, timeout, and interruption.
8. Add deliberate protected-file mutation test.
9. Prove stable health before and after a rejected candidate.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
