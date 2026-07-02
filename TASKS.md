# Neo3000 Task Board

**Active checkpoint:** 0, baseline parity and occupied-context characterization  
**Current RSI level:** Level 0, Pi-assisted development  
**Baseline evidence through:** `432e8f773cde782cab6d478ad5afccb15816cbb4`  
**Claim ceiling:** `NEO3000_FOUNDATION_INITIALIZED`  
**Next exact boundary:** user completes Pi UI verification, rolling-minimum measurement, and matched LM Studio comparison; then close Checkpoint 0 and begin RSI-0

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
- [x] Deterministic occupied-context measurements succeed at 2,053, 8,191, 32,773, 40,956, and 59,996 raw content tokens.
- [x] Occupied-context decode throughput is approximately flat: 22.3 TPS at 2K versus 20.9 TPS at 60K, ratio 0.94.
- [x] Auto-fit is optimal at 4K among tested placements: 17.6 TPS versus 10.0 TPS at explicit `ngl=20`.
- [x] The conservative-auto-fit hypothesis is rejected.
- [x] CPU-MoE comparison is measured: enabled 19.1 TPS at 2,725 MiB VRAM; disabled 30.8 TPS at 10,604 MiB VRAM.
- [x] CPU-MoE is documented as a memory and speed tradeoff.
- [x] The 40,960 matrix failure is localized to client-side timeout during long uncached inference, not tokenizer failure.
- [x] Direct `/tokenize` succeeds at 197K and 599K tokens.
- [x] Allocation capacity and occupied-context performance are documented separately.
- [x] TPS discrepancy is explained by cold versus warm state, completion length, and reasoning overhead.
- [x] Source custody recommendation is Option A: track the imported pinned runtime.
- [x] Imported source remains reproducible from the pinned upstream commit.

## Evidence boundary

- A 65,536 configured context proves allocation capacity, not 65,536 occupied prompt tokens.
- Actual `usage.prompt_tokens` is authoritative for occupied-context measurements.
- The strongest proven occupied-context result is 59,996 prompt tokens at 20.9 decode TPS.

---

# Active queue: Checkpoint 0

## 0A. Verify the real Pi user path

**Blocked on user interaction.** API-level streaming, tools, cancellation, and repeated requests already pass.

- [ ] Launch Pi normally with provider `neo3000` selected.
- [ ] Send `Reply with exactly: NEO3000 PI ONLINE` from Pi.
- [ ] Confirm text appears incrementally in Pi.
- [ ] Confirm the request appears in the Neo3000 server log.
- [ ] Confirm LM Studio does not receive the request.
- [ ] Execute one harmless real Pi tool round trip, such as reading `README.md`.
- [ ] Confirm Pi executes the tool and returns its result to Agents-A1.
- [ ] Confirm Agents-A1 continues with a final response.
- [ ] Cancel a long generation from Pi.
- [ ] Immediately verify `NEO3000 RECOVERED` through Pi.
- [ ] Record the exact Pi command, tool, and visible result in `lab/CHECKPOINT.md`.

## 0B. Occupied-context and tokenizer characterization

- [x] 40K occupied: 40,956 prompt tokens, 22.4 decode TPS cached.
- [x] 60K occupied: 59,996 prompt tokens, 20.9 decode TPS cached.
- [x] Occupied-context degradation ratio: 20.9 / 22.3 = 0.94.
- [x] Allocation and occupancy are stored in separate tables.
- [x] The previous 40,960 failure was a client-side timeout during long uncached inference.
- [x] Server remains healthy after direct tokenize tests.

## 0C. Auto-fit and CPU-MoE audits

- [x] GPU placement sweep completed.
- [x] Auto-fit outperformed every tested explicit layer count.
- [x] CPU-MoE enabled and disabled comparison completed.
- [x] GPU MoE is 62% faster in the measured 4K workload but consumes 89% of VRAM.
- [x] CPU-MoE remains necessary when larger context state must coexist within 12 GB.

## 0D. Record rolling minimum decode speed

- [ ] Define the rolling window in generated tokens or seconds.
- [ ] Record rolling minimum decode TPS for the matched 2K workload.
- [ ] Record rolling minimum decode TPS for the matched 32K workload.
- [ ] Record rolling minimum decode TPS for the matched 40K workload.
- [ ] Record rolling minimum decode TPS for the matched 60K workload.
- [ ] State whether long reasoning introduces sustained slow regions hidden by average TPS.

## 0E. Matched LM Studio comparison

**Blocked on user launching LM Studio with the same GGUF.** Neo3000-side data is ready.

- [ ] Confirm the exact GGUF SHA-256 in LM Studio matches Neo3000.
- [ ] Match actual prompt-token count, output length, sampler, reasoning mode, KV type, cache state, and warm or cold state.
- [ ] Compare approximately 4K occupied context with one warmup and at least three counted runs.
- [ ] Compare approximately 8K occupied context with one warmup and at least three counted runs.
- [ ] Compare the largest mutually stable occupied context with one warmup and at least three counted runs.
- [ ] Record prompt TPS, decode TPS, TTFT, rolling minimum TPS, RAM, and VRAM.
- [ ] State whether Neo3000 matches, exceeds, or trails LM Studio for each workload.

## 0F. Close Checkpoint 0

- [x] `lab/CHECKPOINT.md` separates allocation from occupied context.
- [x] Unsupported 64K over 4K occupancy claim was replaced with measured 60K over 2K ratio.
- [x] TPS discrepancy is explained.
- [x] Auto-fit and CPU-MoE audits are recorded.
- [x] `lab/GOAL.md` reflects the current boundary.
- [x] Experiment record `neo-exp-0003` is appended.
- [x] Source custody Option A is recommended.
- [x] Stable daily-driver command is confirmed working.
- [x] Characterization evidence is pushed through `432e8f7`.
- [ ] Mark Pi UI gates only after visible user verification.
- [ ] Add matched LM Studio results.
- [ ] Add rolling-minimum decode results.
- [ ] Update `lab/GOAL.md` from Checkpoint 0 to RSI-0.
- [ ] Update `lab/CHECKPOINT.md` to `CLOSED`.
- [ ] Change claim ceiling to `NEO3000_BASELINE_OPERATIONAL`.
- [ ] Commit and push one final Checkpoint 0 closure chunk.

### Checkpoint 0 exit gate

- [ ] Real Pi UI streaming passes.
- [ ] Real Pi tool round trip passes.
- [ ] Pi cancellation and immediate recovery pass.
- [x] Occupied-context behavior is measured through 60K.
- [ ] Matched LM Studio comparison is complete.
- [ ] Rolling minimum decode speed is recorded.
- [x] Allocation and occupied-context evidence are separate.
- [x] Source custody model is selected.

---

# Next queue: Checkpoint RSI-0

**Unlock target:** `SUPERVISED_BOUNDED_RSI_AVAILABLE`

Do not begin candidate self-improvement until Checkpoint 0 closes. RSI-0 creates the substrate required to prompt Pi to begin supervised recursive self-improvement safely.

## RSI-0A. Put engine source under Git custody

Selected approach: **Option A, track the pinned imported runtime as one deliberate baseline commit.**

- [ ] Materialize the exact pinned runtime from the existing import manifest.
- [ ] Verify pinned upstream commit and license files.
- [ ] Inventory imported paths and generated exclusions.
- [ ] Commit the imported runtime as one deliberate source-baseline chunk.
- [ ] Confirm a one-line source edit appears as an ordinary Git diff.
- [ ] Confirm a new worktree contains the complete buildable engine.
- [ ] Confirm clean rollback restores the exact source baseline.
- [ ] Document the future upstream-refresh procedure.

### Custody exit gate

- [ ] Branching, diffing, rollback, worktrees, and exact reconstruction work.
- [ ] The engine is no longer an opaque untracked tree during candidate work.

## RSI-0B. Establish stable and candidate isolation

- [ ] Create or document the stable worktree.
- [ ] Create a separate candidate worktree.
- [ ] Reserve `build/stable` for stable only.
- [ ] Use a separate candidate build directory.
- [ ] Keep stable on port 9292.
- [ ] Assign candidate a separate port, default 9393.
- [ ] Use separate runtime-state directories.
- [ ] Prevent candidate scripts from stopping stable.
- [ ] Verify stable remains responsive while candidate builds.
- [ ] Verify stable remains responsive while candidate serves inference.
- [ ] Verify candidate teardown and worktree deletion do not affect stable.

## RSI-0C. Freeze the evaluator

- [ ] Create a tracked evaluator manifest.
- [ ] Hash benchmark prompts.
- [ ] Hash protocol and quality checks.
- [ ] Hash controller scripts.
- [ ] Record model identity, baseline commit, and stable launch configuration.
- [ ] Declare candidate-editable paths.
- [ ] Exclude evaluator, controller, stable worktree, promotion law, and task ledger from candidate-editable paths.
- [ ] Verify protected hashes before every cycle.
- [ ] Verify protected hashes after every cycle.
- [ ] Reject a candidate immediately when a protected hash changes.
- [ ] Add a deliberate protected-file mutation test and prove rejection.

## RSI-0D. Build deterministic `neo-loop`

`neo-loop` is machinery, not a second reasoning model.

- [ ] Read `TASKS.md`, `lab/GOAL.md`, and `lab/CHECKPOINT.md`.
- [ ] Verify stable health before starting.
- [ ] Verify the candidate worktree is clean.
- [ ] Record baseline commit and evaluator hashes.
- [ ] Accept exactly one declared causal hypothesis.
- [ ] Permit changes only in candidate-editable paths.
- [ ] Build candidate separately.
- [ ] Launch candidate on its separate port.
- [ ] Wait for health with timeout.
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
- [ ] Leave the candidate diff available for human review.

## RSI-0E. Enforce stop and isolation gates

- [ ] Enforce build timeout.
- [ ] Enforce server-health timeout.
- [ ] Enforce benchmark timeout.
- [ ] Enforce memory ceiling.
- [ ] Enforce repeated-crash ceiling.
- [ ] Reject malformed text, reasoning, or tools.
- [ ] Reject cancellation or repeated-turn regression.
- [ ] Reject benchmark mutation.
- [ ] Reject model-weight or model-identity changes.
- [ ] Reject stable worktree mutation.
- [ ] Reject stable process termination.
- [ ] Reject port collision.
- [ ] Reject overlapping build or runtime directories.
- [ ] Prevent candidate push or self-promotion.
- [ ] Confirm cleanup on success, failure, timeout, and interruption.

## RSI-0F. Prove one supervised rejection cycle

- [ ] Start from a healthy stable server.
- [ ] Have Agents-A1 propose one bounded candidate change.
- [ ] Build and launch it only in candidate isolation.
- [ ] Cause or observe failure of one declared gate.
- [ ] Confirm the candidate is rejected.
- [ ] Confirm candidate process and runtime state are removed.
- [ ] Confirm stable remains healthy.
- [ ] Confirm stable files and evaluator hashes are unchanged.
- [ ] Confirm failure is recorded accurately.
- [ ] Confirm the next task remains resumable.

## RSI-0G. Prove one supervised acceptance cycle

- [ ] Start from a healthy stable server.
- [ ] Have Agents-A1 propose one bounded candidate change.
- [ ] Build and launch it only in candidate isolation.
- [ ] Confirm every declared gate passes.
- [ ] Mark it reviewable rather than promoting it.
- [ ] Confirm exact diff and evidence are inspectable.
- [ ] Confirm stable remains healthy and unchanged.
- [ ] Confirm result is recorded accurately.
- [ ] Require explicit human approval before stable merge.

A small safe change may exercise the full cycle before a performance intervention is ready.

## RSI-0H. Add the supervised RSI operator prompt

- [ ] Add a tracked prompt or command template for one bounded cycle.
- [ ] Require one causal hypothesis.
- [ ] Require candidate-only edits.
- [ ] Require immutable evaluation through `neo-loop`.
- [ ] Limit cycle count.
- [ ] Forbid automatic promotion.
- [ ] Require a final handoff with exact diff, evidence, verdict, and next action.

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

At that point Pi may be prompted to begin supervised RSI.

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
- [ ] Measure cold-start CUDA initialization, graph construction, and first-request overhead.
- [ ] Quantify tracing overhead.
- [ ] Identify one or two causal bottlenecks.
- [ ] Select the first catalytic intervention from evidence.

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

- [ ] cold-start state reuse or pre-initialization
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

- [ ] Permit several candidate cycles from one declared goal.
- [ ] Require no manual command execution between cycles.
- [ ] Enforce cycle and wall-clock budgets.
- [ ] Stop after repeated non-improvement.
- [ ] Detect false success reporting through evaluator evidence.
- [ ] Preserve resumable state after interruption.
- [ ] Prove candidate crashes do not interrupt stable inference.
- [ ] Prevent goal, evaluator, controller, or promotion-law mutation.
- [ ] Keep promotion manual.

### Checkpoint 5 unlock

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

- [x] Task board reflects the latest pushed baseline evidence.
- [x] `lab/CHECKPOINT.md` contains only executed evidence.
- [x] `lab/GOAL.md` names the current user-interaction boundary.
- [x] Stable server command is recorded.
- [x] Characterization failures and rejected hypotheses are recorded.
- [x] Claim-bearing baseline work is pushed.
- [ ] After user tests, update the Pi and LM Studio gates.
- [ ] After Checkpoint 0 closure, set the next unchecked task to RSI-0A.

A handoff is incomplete when the narrative report and task board disagree.
