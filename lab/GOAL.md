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

RSI-0E is implemented and RSI-0F has passed. Candidate source custody, evaluator model identity, health-probe handling, and Windows WDDM VRAM accounting are repaired. The next objective is **run one fresh RSI-0G acceptance cycle under the locked WDDM VRAM gate**.

Do not begin autonomous RSI. Do not modify stable inference logic. Do not promote candidates automatically.

## Next exact action

Windows WDDM `GPU Process Memory(*)\\Dedicated Usage` now supplies candidate-PID-specific dedicated-memory attribution. The manual lifecycle proof observed candidate PID `36216`, listener PID `36216`, and only `pid_36216_luid_0x00000000_0x000115ae_phys_0` at a 2,288,914,432-byte peak across five samples. The value may conservatively include allocations shared with other processes; that is safe because it remains tied to the candidate PID and can only cause safe rejection.

Minimum required work:

```text
1. Keep the stable server and stable worktree unchanged.
2. Reapply only the inert `common/` fixture in the candidate worktree.
3. Verify preflight and the locked WDDM memory gate.
4. Authorize exactly one new `python scripts/neo_loop.py --hypothesis "..."` cycle.
5. Require every quality, WDDM peak-memory, cleanup, and stable-integrity gate before reviewable acceptance.
```

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

This unlock is not available until RSI-0E, RSI-0F, and RSI-0G all pass.
