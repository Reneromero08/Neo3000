# Neo3000 Task Board

**Active checkpoint:** RSI-0, supervised RSI substrate  
**Remote HEAD:** `432e8f7`  
**Claim ceiling:** `NEO3000_BASELINE_OPERATIONAL`  
**Next exact boundary:** commit imported engine source under Git custody (RSI-0A)

`ROADMAP.md` defines the architecture and phase order. This file is the executable queue.

## Status law

- `[x]` means supported by pushed repository evidence.
- `[ ]` means incomplete, ambiguous, or unsupported by the current evidence.
- Work from top to bottom unless a task is explicitly blocked.

---

# Checkpoint 0: CLOSED

All Checkpoint 0 gates are met and verified.

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
- [x] Server allocation succeeds at 4K, 8K, 16K, 32K, 40K, and 65,536 context sizes.
- [x] Deterministic occupied-context measurements at 2K, 8K, 32K, 40K, and 60K raw content tokens.
- [x] Occupied-context decode throughput approximately flat: 22.3 tps (2K) to 20.9 tps (60K), ratio 0.94.
- [x] Auto-fit is proven optimal. The conservative-auto-fit hypothesis is rejected.
- [x] CPU-MoE comparison complete (62% decode gain disabled, 89% VRAM cost).
- [x] 40,960 target failure root cause identified (client timeout, not server bug).
- [x] Allocation capacity and occupied-context performance are in separate tables.
- [x] TPS discrepancy explained (cold vs warm, completion length, reasoning overhead).
- [x] Rolling minimum decode speed recorded (min/avg 0.92-0.96, no transient stalls).
- [x] Pi UI text stream verified ("NEO3000 PI ONLINE" appeared incrementally).
- [x] Pi real tool round trip verified (read README.md, returned "Neo3000").
- [x] Pi cancellation and recovery verified (cancel mid-stream, "NEO3000 RECOVERED").
- [x] LM Studio comparison deferred to optional characterization (not an unlock dependency).
- [x] Source custody recommendation: Option A (track imported runtime).
- [x] Claim ceiling advanced to `NEO3000_BASELINE_OPERATIONAL`.

### Checkpoint 0 exit gate: MET

```text
Agents-A1 runs through Pi on Neo3000: YES
Streaming reasoning and content are stable: YES
A real Pi tool round trip succeeds: YES
Cancellation followed by immediate recovery succeeds: YES
Repeated turns remain stable: YES
Context scaling is measured through the maximum stable point: YES
Rolling minimum decode speed is recorded: YES
Allocation and occupancy are documented separately: YES
Next instrumentation target selected from evidence: YES
```

---

# Current queue: Checkpoint RSI-0

**Unlock target:** `SUPERVISED_BOUNDED_RSI_AVAILABLE`

Do not begin candidate self-improvement until this checkpoint closes. RSI-0 creates the substrate to prompt Pi to begin supervised recursive self-improvement safely.

## RSI-0A. Put engine source under Git custody [CURRENT]

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

---

# Checkpoint 1 queue: Compute map

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

---

# Handoff

- [x] Checkpoint 0 closed.
- [x] All Pi gates verified by user.
- [x] Rolling minimum decode speed recorded (no transient stalls).
- [x] Claim ceiling: `NEO3000_BASELINE_OPERATIONAL`.
- [x] LM Studio deferred to optional characterization.
- [ ] Next task: RSI-0A, commit engine source under Git custody.
