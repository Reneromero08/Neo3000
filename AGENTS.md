# AGENTS.md

## Mission

Build Neo3000 into the fastest trustworthy daily-driver runtime for Agents-A1, then push its compute architecture toward catalytic, phase-native, recursively reusable inference.

## Mandatory entry sequence

Every agent must begin by reading:

```text
1. AGENTS.md
2. TASKS.md
3. ROADMAP.md
4. lab/GOAL.md
5. lab/CHECKPOINT.md
6. lab/BASELINE_PROTOCOL.md
7. lab/results.jsonl
```

`TASKS.md` is the operational queue. The next unchecked item in its current execution queue is the default next task unless it is blocked by newer executed evidence.

An agent must not rely on chat history when the repository task board says something different. Reconcile the repository state first.

## Current mode

Checkpoint 0 is verification mode.

Do not add novel catalytic mechanisms before the imported baseline:

- builds successfully with CUDA
- loads the exact Agents-A1 GGUF
- streams through the OpenAI-compatible server
- works from Pi
- produces fixed baseline measurements

During later exploration, enter the hypothesis fully and use delusional optimism as a generative engine. Assume a proposal may be right long enough to break every removable barrier. This stance generates mechanisms and experiments. It is not itself proof.

## Anti-Median Non-Collapse Protocol

Treat every Neo3000 or CAT_CAS proposal first as a potentially valid higher-dimensional object, not as a malformed version of an existing algorithm.

Reconstruct it in its strongest coherent form. Preserve:

- relational geometry
- unresolved state
- phase-native structure
- borrow -> transform -> extract -> restore
- explicit boundaries
- mechanisms, carriers, observables, invariants, and restoration laws

Distinguish actual mathematical, physical, informational, and evidentiary blockers from unfamiliarity, cost, convention, or absence of precedent.

Do not collapse a proposal into scalar candidate ranking, winner selection, AUC-first scoring, backpropagation, conventional search, or a forward verifier loop unless that reduction is the declared object under test.

The algorithm is a local trace through a larger process-object. Negative results map the Wall.

## Engineering rules

1. Speed and correctness come before architectural ornament.
2. Keep the server directly compatible with Pi.
3. Make one causal intervention per experiment.
4. Benchmark before and after using identical model, prompts, context, sampler, and hardware settings.
5. Never infer a speedup from one run.
6. Do not trade away tool-call validity or output quality without declaring the trade.
7. Keep tracing optional and compiled out in normal builds.
8. Preserve the pinned upstream identity and license.
9. Avoid broad rewrites while a narrow hook can test the mechanism.
10. Keep commits as meaningful architectural chunks. Do not create micro-commit pellets.
11. Do not generate report farms. Update `lab/CHECKPOINT.md` and append one compact result record.
12. Never promote a candidate merely because it builds.
13. Keep `TASKS.md` synchronized with reality. A narrative handoff does not replace the task board.
14. Check off tasks only from executed or remotely auditable evidence.
15. Before stopping, ensure the next unchecked task is the actual next action.

## Repository discipline

The stable branch must remain runnable.

Experimental work should use a branch or worktree. The stable server may continue serving Pi while a candidate build is compiled and benchmarked separately.

Do not commit:

- model weights
- build outputs
- benchmark caches
- runtime logs
- temporary prompts
- local machine paths
- generated upstream clone directories

## Experiment record

Each experiment should record:

```json
{
  "id": "neo-exp-0001",
  "checkpoint": "2",
  "hypothesis": "one causal sentence",
  "intervention": "one bounded change",
  "baseline_commit": "sha",
  "candidate_commit": "sha",
  "model_hash": "sha256",
  "configuration": {},
  "metrics_before": {},
  "metrics_after": {},
  "quality_gates": {},
  "verdict": "accept|reject|inconclusive",
  "next_boundary": "one sentence"
}
```

Append compact JSON objects to `lab/results.jsonl` only after measurements exist.

## Self-improvement loop

Once Checkpoint 0 and the benchmark harness are complete, a bounded Agents-A1 loop may:

1. read `TASKS.md`
2. read `lab/GOAL.md`
3. read `lab/CHECKPOINT.md`
4. inspect the current hot path
5. state one causal hypothesis
6. modify one mechanism in a candidate worktree
7. build the candidate
8. run the fixed benchmark
9. compare it with stable
10. append one result
11. update the checkpoint and task board only when an acceptance gate is actually closed

Stop immediately on:

- build-system drift unrelated to the hypothesis
- model-output corruption
- malformed Pi tool calls
- unexplained memory growth
- benchmark mutation
- stable-server mutation
- repeated crashes
- restoration or branch-isolation failure

Automatic promotion is forbidden until a later checkpoint explicitly authorizes it.
