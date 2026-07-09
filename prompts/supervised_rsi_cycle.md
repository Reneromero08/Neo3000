# Supervised RSI Cycle Prompt

Use this prompt only after Checkpoint RSI-0 closes and `SUPERVISED_BOUNDED_RSI_AVAILABLE` is recorded in `TASKS.md`.

```text
Begin one supervised Neo3000 self-improvement cycle.

Read:
AGENTS.md
TASKS.md
ROADMAP.md
lab/GOAL.md
lab/CHECKPOINT.md
lab/EVALUATOR.json

Keep the stable server and stable worktree untouched.
Use only the candidate worktree.
Do not modify the evaluator, task board, checkpoint ledger, roadmap, model files, stable launch scripts, or promotion rules.
Do not promote automatically.
Do not run more than one candidate cycle.

State one causal hypothesis from current evidence.
Make one bounded intervention in an allowed candidate-editable path.
Run the candidate through neo-loop.
Reject the candidate if any immutable quality, reasoning, tool, cancellation, stability, memory, timeout, path, hash, or performance gate fails.
After evaluation, stop the candidate and verify stable health.
Record the result.

Return:
- exact candidate diff
- commands run
- evaluator hashes before and after
- quality-gate results
- performance results
- stability and cleanup results
- verdict: reject, reviewable accept, or inconclusive
- next exact boundary
```

Automatic stable promotion remains forbidden.
