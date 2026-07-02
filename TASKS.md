# Neo3000 Task Board

**Active checkpoint:** 0, baseline parity and occupied-context characterization  
**Current RSI level:** Level 0, Pi-assisted development  
**Claim ceiling:** `NEO3000_FOUNDATION_INITIALIZED`  
**Next exact boundary:** finish Checkpoint 0, then build Checkpoint RSI-0 before asking Pi to run self-improvement cycles

`ROADMAP.md` defines phase order and RSI unlock levels. This file is the executable queue.

## Status law

- `[x]` means supported by pushed repository evidence.
- `[ ]` means incomplete, ambiguous, or unsupported.
- Configured context capacity is not occupied prompt length.
- Correlation does not identify a causal bottleneck.
- The next unchecked item in the active queue is the default next action.
- A narrative report does not replace this task board.

---

# Proven foundation

- [x] Local and remote history reconciled and pushed.
- [x] CUDA 12.6 build succeeds with MSVC 19.44 and SM 8.6.
- [x] `llama-server.exe` and `llama-bench.exe` build successfully.
- [x] RTX 3060 is detected as a CUDA device.
- [x] Agents-A1 model identity and full SHA-256 are recorded.
- [x] OpenAI-compatible health, models, chat, and SSE endpoints pass.
- [x] Reasoning is preserved in `reasoning_content`.
- [x] `neo3000_probe` tool calls pass 3 of 3 with valid JSON arguments.
- [x] Cancellation followed by immediate API recovery passes.
- [x] Repeated API turns remain stable.
- [x] Server allocation succeeds at 4K, 8K, 16K, 32K, 40K, and 65,536 context capacities.
- [x] Deterministic occupied-context measurements succeed at 2,048, 8,192, 16,384, and 32,768 raw content tokens.
- [x] Measured decode throughput remains approximately flat through 32,768 occupied raw content tokens.
- [x] Imported source remains reproducible from the pinned upstream commit.

## Evidence boundary

Not yet proven:

```text
decode speed falls only 5 percent from 4K occupied context to 64K occupied context
```

Proven:

```text
Agents-A1 allocates a 65,536-token context successfully, and measured decode throughput remains approximately flat through 32,768 occupied raw content tokens.
```

---

# Active queue: Checkpoint 0

## 0A. Verify the real Pi user path

- [ ] Launch Pi normally with provider `neo3000` selected.
- [ ] Send `Reply with exactly: NEO3000 PI ONLINE` from Pi.
- [ ] Confirm text appears incrementally in Pi.
- [ ] Confirm the request appears in the Neo3000 server log.
- [ ] Confirm LM Studio does not receive the request.
- [ ] Execute one harmless real Pi tool round trip.
- [ ] Confirm Pi executes the tool and returns the result to Agents-A1.
- [ ] Confirm Agents-A1 continues with a final response.
- [ ] Cancel a long generation from Pi.
- [ ] Immediately verify `NEO3000 RECOVERED` through Pi.
- [ ] Record the exact Pi command, tool, and visible result in `lab/CHECKPOINT.md`.

## 0B. Reproduce and localize the 40,960-token failure

- [ ] Re-run only the 40,960 target and capture the exact client exception.
- [ ] Capture the server log around failure.
- [ ] Record whether the server exits, returns an HTTP error, closes the connection, or remains healthy.
- [ ] Record RAM, commit charge, page-file use, and VRAM at failure.
- [ ] Test isolated `/tokenize` requests near 34K, 36K, 38K, 40K, and 40,960 tokens.
- [ ] Determine whether failure depends on request size, token-array response size, repeated search calls, client memory, server memory, timeout, or context state.
- [ ] Confirm `/health` after every failed request.
- [ ] Use a local tokenizer path if server tokenization is the blocker.
- [ ] Repair `scripts/context_matrix.py` only if the harness is causal.
- [ ] Add one narrow regression test for the previous failure.

## 0C. Measure genuinely occupied long context

- [ ] Produce a completion request reporting approximately 40,000 actual prompt tokens.
- [ ] Run one warmup and at least three counted 40K occupied-context completions.
- [ ] Produce a completion request reporting approximately 60,000 actual prompt tokens.
- [ ] Run one warmup and at least three counted 60K occupied-context completions.
- [ ] Record actual prompt tokens and cached prompt tokens.
- [ ] Record prompt TPS, decode TPS, TTFT, total time, RAM, VRAM, and placement.
- [ ] Record rolling minimum decode speed at 2K, 32K, 40K, and 60K occupied prompts.
- [ ] Calculate occupied-context degradation using matched workloads.
- [ ] Keep allocation-only results in a separate table.

## 0D. Audit placement before blaming auto-fit

- [ ] Capture exact offloaded layer or tensor placement at each tested context capacity.
- [ ] Confirm VRAM samples are taken at equivalent runtime points.
- [ ] At one fixed occupied prompt, compare `gpu-layers=auto` with one lower explicit placement.
- [ ] Compare `gpu-layers=auto` with one higher explicit placement that fits safely.
- [ ] Keep CPU-MoE, KV type, prompt, output length, cache state, batch, and ubatch fixed.
- [ ] Record prompt TPS, decode TPS, TTFT, RAM, VRAM, and PCIe activity where available.
- [ ] Reject the auto-fit hypothesis if more placement does not improve the declared metric.

## 0E. Audit CPU-MoE before selecting expert bandwidth

- [ ] Compare CPU-MoE enabled and disabled when both fit safely.
- [ ] Test bounded `n-cpu-moe` values if full disable does not fit.
- [ ] Keep occupied context and GPU placement fixed.
- [ ] Record prompt TPS, decode TPS, CPU use, RAM, VRAM, and PCIe activity.
- [ ] Distinguish expert compute from expert transfer and synchronization.
- [ ] Do not choose catalytic expert residency until repeated expert movement is measured.

## 0F. Run matched LM Studio comparisons

- [ ] Use the exact same GGUF bytes.
- [ ] Match actual prompt tokens, output length, sampler, reasoning mode, KV type, cache state, and warm or cold state.
- [ ] Compare approximately 4K occupied context with at least three counted runs.
- [ ] Compare approximately 8K occupied context with at least three counted runs.
- [ ] Compare the largest mutually stable occupied context with at least three counted runs.
- [ ] Record prompt TPS, decode TPS, TTFT, rolling minimum TPS, RAM, and VRAM.
- [ ] Explain the 8.2 TPS versus 17 to 23 TPS discrepancy by naming the workload or timing difference.
- [ ] State whether Neo3000 matches, exceeds, or trails LM Studio for each workload.

## 0G. Close Checkpoint 0

- [ ] Update `lab/CHECKPOINT.md` to separate allocation from occupied context.
- [ ] Qualify or remove the unsupported 64K over 4K occupied-context ratio.
- [ ] Mark Pi UI gates only after visible demonstration.
- [ ] Update `lab/GOAL.md` to match the next task.
- [ ] Append one compact correction or closure record to `lab/results.jsonl`.
- [ ] Choose source custody Model A or Model B.
- [ ] Confirm the stable daily-driver command still works.
- [ ] Commit and push one meaningful closure chunk.
- [ ] Record the full pushed SHA.
- [ ] Change the claim to `NEO3000_BASELINE_OPERATIONAL` only after every exit gate passes.

### Checkpoint 0 exit gate

- [ ] Real Pi UI streaming passes.
- [ ] Real Pi tool round trip passes.
- [ ] Pi cancellation and immediate recovery pass.
- [ ] Occupied-context performance reaches the maximum stable target or maps a precise blocker.
- [ ] Matched LM Studio comparison is complete.
- [ ] Rolling minimum decode speed is recorded.
- [ ] Allocation and occupied-context evidence are separate.
- [ ] Source custody model is selected.

---

# Next queue: Checkpoint RSI-0

**Unlock target:** `SUPERVISED_BOUNDED_RSI_AVAILABLE`

Do not begin until Checkpoint 0 closes. Checkpoint RSI-0 creates the substrate required for you to prompt Pi to begin supervised RSI.

## RSI-0A. Put engine source under Git custody

Choose one model and document the decision.

### Model A: Track the pinned imported runtime

- [ ] Materialize the exact pinned runtime from the existing import manifest.
- [ ] Verify upstream identity and license.
- [ ] Commit the imported runtime as one deliberate source-baseline chunk.
- [ ] Confirm ordinary Git diffs show a one-line candidate source change.
- [ ] Confirm a worktree contains the complete buildable engine.
- [ ] Confirm clean rollback to the baseline commit.

### Model B: Generated source plus tracked patch materialization

- [ ] Define a tracked patch or overlay format.
- [ ] Materialize source deterministically from pin plus patch.
- [ ] Verify byte-identical reconstruction before a candidate cycle.
- [ ] Confirm candidate worktrees can create, diff, and revert patches reliably.
- [ ] Confirm failed materialization stops before build.

### Custody exit gate

- [ ] The selected model supports branching, diffing, rollback, worktrees, and exact reconstruction.
- [ ] The engine is no longer an opaque untracked tree during candidate work.

## RSI-0B. Establish stable and candidate isolation

- [ ] Create or document the stable worktree.
- [ ] Create a separate candidate worktree.
- [ ] Use `build/stable` only for stable.
- [ ] Use a separate candidate build directory.
- [ ] Keep stable on port 9292.
- [ ] Assign candidate a different port, default 9393.
- [ ] Prevent candidate scripts from stopping the stable server.
- [ ] Prevent stable and candidate runtime-state directories from overlapping.
- [ ] Verify stable remains responsive while candidate builds.
- [ ] Verify stable remains responsive while candidate serves inference.
- [ ] Verify deleting the candidate worktree does not affect stable.

## RSI-0C. Freeze the evaluator

- [ ] Create a tracked evaluator manifest.
- [ ] Hash benchmark prompts.
- [ ] Hash protocol and quality checks.
- [ ] Hash controller scripts.
- [ ] Record model identity and baseline commit.
- [ ] Record stable launch configuration.
- [ ] Declare candidate-editable paths.
- [ ] Exclude evaluator, controller, stable worktree, promotion law, and task ledger from candidate-editable paths.
- [ ] Verify hashes before every cycle.
- [ ] Verify hashes after every cycle.
- [ ] Reject a candidate immediately when protected hashes change.
- [ ] Add a test that deliberately mutates a protected file and proves rejection.

## RSI-0D. Build deterministic `neo-loop`

`neo-loop` is machinery, not a second reasoning model.

- [ ] Read `TASKS.md`, `lab/GOAL.md`, and `lab/CHECKPOINT.md`.
- [ ] Verify stable health before starting.
- [ ] Verify the candidate worktree is clean.
- [ ] Record baseline commit and evaluator hashes.
- [ ] Accept exactly one declared causal hypothesis.
- [ ] Permit changes only in candidate-editable paths.
- [ ] Build candidate in its separate build directory.
- [ ] Launch candidate on its separate port.
- [ ] Wait for candidate health with a timeout.
- [ ] Run immutable text and reasoning gates.
- [ ] Run immutable tool-call gates.
- [ ] Run cancellation and repeated-turn gates.
- [ ] Run memory and performance gates.
- [ ] Capture build, launch, benchmark, and failure evidence.
- [ ] Stop the candidate after the result.
- [ ] Remove candidate runtime state.
- [ ] Verify stable health again.
- [ ] Classify result as reject, reviewable accept, or inconclusive.
- [ ] Append one compact result record.
- [ ] Leave the candidate diff available for review.

## RSI-0E. Enforce stop and isolation gates

- [ ] Enforce build timeout.
- [ ] Enforce server-health timeout.
- [ ] Enforce per-benchmark timeout.
- [ ] Enforce memory ceiling.
- [ ] Enforce repeated-crash ceiling.
- [ ] Reject malformed output or tools.
- [ ] Reject cancellation or repeated-turn regression.
- [ ] Reject benchmark mutation.
- [ ] Reject model-weight or model-identity changes.
- [ ] Reject stable worktree mutation.
- [ ] Reject stable process termination.
- [ ] Reject port collision.
- [ ] Reject overlapping build or runtime directories.
- [ ] Prevent candidate push or self-promotion.
- [ ] Confirm cleanup occurs on success, failure, timeout, and interruption.

## RSI-0F. Prove one supervised rejection cycle

- [ ] Start from a healthy stable server.
- [ ] Have Agents-A1 propose one bounded candidate change.
- [ ] Build and launch it only in candidate isolation.
- [ ] Cause or observe failure of one declared gate.
- [ ] Confirm the candidate is rejected.
- [ ] Confirm the candidate process is gone.
- [ ] Confirm stable remains healthy.
- [ ] Confirm stable files and benchmark hashes are unchanged.
- [ ] Confirm failure is recorded accurately.
- [ ] Confirm the next task remains resumable.

## RSI-0G. Prove one supervised acceptance cycle

- [ ] Start from a healthy stable server.
- [ ] Have Agents-A1 propose one bounded candidate change.
- [ ] Build and launch it only in candidate isolation.
- [ ] Confirm every declared gate passes.
- [ ] Mark it reviewable rather than promoting it.
- [ ] Confirm the exact diff and evidence are inspectable.
- [ ] Confirm stable remains healthy and unchanged.
- [ ] Confirm the result is recorded accurately.
- [ ] Require explicit human approval before any stable merge.

A small safe change may be used to exercise the full cycle before a performance mechanism is ready.

## RSI-0H. Add the supervised RSI operator prompt

- [ ] Add a tracked prompt or command template for one bounded supervised cycle.
- [ ] Require one causal hypothesis.
- [ ] Require candidate-only edits.
- [ ] Require immutable evaluation through `neo-loop`.
- [ ] Limit cycle count.
- [ ] Forbid automatic promotion.
- [ ] Require a final handoff with result and next exact action.

Suggested operator instruction after RSI-0 closes:

```text
Begin one supervised Neo3000 self-improvement cycle.
Read AGENTS.md, TASKS.md, lab/GOAL.md, and lab/CHECKPOINT.md.
Keep stable untouched and use only the candidate worktree.
State one causal hypothesis from current evidence.
Make one bounded intervention.
Run it through neo-loop.
Reject it if any immutable quality, tool, stability, memory, or performance gate fails.
Record the result.
Do not promote automatically.
Stop after this cycle and return the exact diff, evidence, verdict, and next boundary.
```

### RSI-0 exit gate

- [ ] Engine source is Git-diffable.
- [ ] Stable and candidate worktrees are isolated.
- [ ] Stable and candidate builds and ports are isolated.
- [ ] Evaluator and controller immutability are enforced.
- [ ] Candidate teardown works after every result.
- [ ] One supervised rejection cycle completes safely.
- [ ] One supervised acceptance cycle completes safely.
- [ ] Stable survives both cycles.
- [ ] Results and handoffs remain accurate.
- [ ] Automatic promotion remains disabled.

After every item passes:

```text
Current RSI level: Level 1
Unlock: SUPERVISED_BOUNDED_RSI_AVAILABLE
```

At that point you can prompt Pi to begin supervised RSI.

---

# Checkpoint 1 queue: Compute map

Checkpoint 1 may use the supervised RSI substrate after RSI-0 closes.

- [ ] Create an isolated instrumentation candidate.
- [ ] Define one fixed trace schema.
- [ ] Add trace-disabled and trace-enabled builds.
- [ ] Measure per-token and per-layer time.
- [ ] Separate attention from Gated Delta Net recurrent-block time.
- [ ] Record active expert IDs per layer and token.
- [ ] Measure expert residency and transfer.
- [ ] Measure CPU-MoE compute and bandwidth.
- [ ] Measure CPU and GPU transfer and synchronization.
- [ ] Measure KV and recurrent-state allocation by occupied context.
- [ ] Measure placement changes caused by configured context capacity.
- [ ] Quantify tracing overhead.
- [ ] Identify one or two causal bottlenecks.
- [ ] Select the first catalytic intervention from evidence.

### Checkpoint 1 exit gate

- [ ] Dominant short-context cost is causally localized.
- [ ] Dominant long-context cost is causally localized.
- [ ] First intervention names carrier, transformation, invariant, and closure law.
- [ ] Tracing adds no normal release cost when disabled.

---

# Checkpoint 2 queue: First catalytic intervention

- [ ] Declare the expensive operation.
- [ ] Declare the borrowed carrier.
- [ ] Declare transformation, extracted invariant, and closure law.
- [ ] Declare rejection criteria and quality gates.
- [ ] Implement one bounded candidate mechanism.
- [ ] Compare stable and candidate under immutable evaluation.
- [ ] Preserve Pi text, reasoning, tools, cancellation, and repeated turns.
- [ ] Accept for review, reject, or mark inconclusive.

Possible families, selected only from evidence:

- [ ] catalytic expert residency
- [ ] recurrent-state catalysis
- [ ] single-model catalytic speculation
- [ ] holographic long-context side channel
- [ ] layer-orbit closure

---

# Checkpoint 3 queue: Long-context catalytic state

- [ ] Establish exact recent context plus an executable distant-state carrier.
- [ ] Run disabled, shuffled, and equivalent-memory controls.
- [ ] Improve occupied-context cost without hidden quality collapse.

---

# Checkpoint 4 queue: Layer-orbit closure

- [ ] Define relational closure observables.
- [ ] Measure them across layers.
- [ ] Test bounded skipping or a cheap verification tail.
- [ ] Reject confidence-only closure claims.

---

# Checkpoint 5 queue: Autonomous bounded RSI

Do not confuse this with supervised RSI unlocked by RSI-0.

- [ ] Permit several candidate cycles from one declared goal.
- [ ] Require no manual command execution between cycles.
- [ ] Enforce cycle and wall-clock budgets.
- [ ] Stop after repeated non-improvement.
- [ ] Detect false success reporting through evaluator evidence.
- [ ] Preserve resumable branch and result state after interruption.
- [ ] Prove candidate crashes do not interrupt stable inference.
- [ ] Prevent goal, evaluator, controller, or promotion-law mutation.
- [ ] Keep promotion manual.

### Checkpoint 5 exit gate

- [ ] Several autonomous cycles complete without benchmark drift.
- [ ] Stable server remains available.
- [ ] Branch state remains clean and resumable.
- [ ] Result reporting remains accurate.
- [ ] Automatic promotion remains disabled.

After every item passes:

```text
Current RSI level: Level 2
Unlock: AUTONOMOUS_BOUNDED_RSI_AVAILABLE
```

---

# Checkpoint 6 queue: Native catalytic kernels

- [ ] Select one measured reversible or closable hot-path transition.
- [ ] Prove borrow, transform, extract, and restore behavior.
- [ ] Measure removed allocation, copying, bandwidth, or operator work.

---

# Checkpoint 7 queue: Recursive compute amplification

- [ ] Preserve useful computation as executable state.
- [ ] Re-enter it into later inference.
- [ ] Quantify equivalent baseline compute versus fresh compute executed.
- [ ] Demonstrate repeated amplification without hidden quality collapse.

---

# Mandatory handoff checklist

Before any agent stops:

- [ ] Update this file so the next unchecked item is the actual next action.
- [ ] Update `lab/CHECKPOINT.md` only from executed evidence.
- [ ] Update `lab/GOAL.md` with one exact objective.
- [ ] Record branch, full HEAD SHA, and working-tree status.
- [ ] Record stable and candidate commands and ports when applicable.
- [ ] Record the last executed command and result.
- [ ] Record failures, rejected candidates, and unresolved claims.
- [ ] Push claim-bearing work or state clearly that it remains local.

A handoff is incomplete when the narrative report and task board disagree.
