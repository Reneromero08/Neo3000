# Active Goal

## RSI-0: Supervised recursive self-improvement substrate

Checkpoint 0 is closed. Neo3000 is baseline-operational. The runtime serves Agents-A1 to Pi correctly, context scales through 60K occupied tokens with 0.94 degradation ratio, rolling minimum decode is smooth, tools and cancellation are verified.

The next objective is to build the infrastructure that allows Pi to perform supervised recursive self-improvement on Neo3000 safely. No autonomous modifications yet. No inference kernel changes yet.

## Required result

```text
Stable worktree running Neo3000
+ isolated candidate worktree
+ immutable evaluator with hashed benchmarks
+ deterministic neo-loop machinery
+ supervised rejection and acceptance cycle demonstrated
+ stable survives all candidate activity
```

## RSI-0 work order

1. RSI-0A: Put engine source under Git custody (track imported runtime)
2. RSI-0B: Establish stable and candidate worktrees with isolated builds and ports
3. RSI-0C: Freeze the evaluator with hashed benchmarks and quality gates
4. RSI-0D: Build deterministic neo-loop (machinery, not a second model)
5. RSI-0E: Enforce stop and isolation gates
6. RSI-0F: Prove one supervised rejection cycle
7. RSI-0G: Prove one supervised acceptance cycle
8. RSI-0H: Add the supervised RSI operator prompt

## Unlock target

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

## Current boundary

Checkpoint 0 just closed. RSI-0 begins immediately with source custody (RSI-0A).

## Next exact action

Commit the imported pinned runtime as one deliberate baseline commit, then verify branching, diffing, and worktree creation work normally.
