# Neo3000 Task Board

**Active checkpoint:** RSI-0, supervised RSI substrate  
**Current RSI level:** Level 0, Pi-assisted development  
**Baseline evidence through:** `432e8f773cde782cab6d478ad5afccb15816cbb4`  
**Claim ceiling:** `NEO3000_BASELINE_OPERATIONAL`  
**Next exact boundary:** resolve the candidate CMake-generation failure, then rerun RSI-0G acceptance

`ROADMAP.md` defines phase order and RSI unlock levels. This file is the executable queue.

## Status law

- `[x]` means supported by pushed repository evidence.
- `[ ]` means incomplete, ambiguous, or unsupported by current evidence.
- Configured context capacity is not occupied prompt length.
- Correlation does not identify a causal bottleneck.
- The next unchecked item in the active queue is the default next action.
- A narrative report does not replace this task board.

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
- [x] Server allocation succeeds at 4K, 8K, 16K, 32K, 40K, and 65,536 context capacities.
- [x] Deterministic occupied-context measurements at 2K, 8K, 32K, 40K, and 60K raw content tokens.
- [x] Occupied-context decode throughput is approximately flat: 22.3 TPS at 2K versus 20.9 TPS at 60K, ratio 0.94.
- [x] Auto-fit is optimal among tested placements. The conservative-auto-fit hypothesis is rejected.
- [x] CPU-MoE comparison complete: 62% decode gain disabled, 89% VRAM cost.
- [x] The 40,960 matrix failure root cause is client timeout during long uncached inference, not a server or tokenizer bug.
- [x] Allocation capacity and occupied-context performance are documented separately.
- [x] TPS discrepancy is explained by cold versus warm state, completion length, and reasoning overhead.
- [x] Rolling minimum decode speed recorded: min/avg 0.92-0.96, no significant transient stalls.
- [x] Pi UI text stream verified: `NEO3000 PI ONLINE` appeared incrementally.
- [x] Pi real tool round trip verified: read `README.md`, returned `Neo3000`.
- [x] Pi cancellation and recovery verified: cancel mid-stream, then `NEO3000 RECOVERED`.
- [x] LM Studio comparison deferred to optional characterization, not an unlock dependency.
- [x] Source custody recommendation: Option A, track imported runtime.
- [x] Claim advanced to `NEO3000_BASELINE_OPERATIONAL`.

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

## RSI-0A. Put engine source under Git custody [DONE]

Selected approach: **Option A, track the pinned imported runtime as one deliberate baseline commit.**

- [x] Materialize the exact pinned runtime from the existing import manifest.
- [x] Verify pinned upstream commit and license files.
- [x] Inventory imported paths and generated exclusions.
- [x] Commit the imported runtime as one deliberate source-baseline chunk: `7ea6ffd`.
- [x] Confirm a one-line source edit appears as an ordinary Git diff.
- [x] Confirm a new worktree contains the complete buildable engine.
- [x] Confirm clean rollback restores the exact source baseline.
- [x] Engine tracked: 2103 files. Candidate worktree created and verified.

### Custody exit gate: MET

## RSI-0B. Establish stable and candidate isolation [PARTIAL]

- [x] Stable worktree: `D:\CCC 2.0\AI\Neo3000` on branch `main`, port 9292, `build/stable`.
- [x] Candidate worktree: `D:\CCC 2.0\AI\Neo3000-candidate` on branch `candidate`, port 9393, `build/candidate`.
- [x] Candidate build script: `scripts/build_candidate.ps1`.
- [x] Candidate server script: `scripts/run_candidate.ps1`.
- [x] Isolation design verified: separate builds, ports, and runtime state.
- [x] Verify stable remains responsive during a candidate configure/build attempt and rejected preflight.
- [ ] Verify stable remains responsive while candidate serves inference.
- [ ] Verify candidate teardown does not affect stable.

## RSI-0C. Freeze the evaluator [PARTIAL]

- [x] Created tracked evaluator manifest: `lab/EVALUATOR.json`.
- [x] Recorded model identity, baseline commit, and stable launch configuration.
- [x] Declared candidate-editable paths and protected paths.
- [x] Excluded evaluator, controller, stable worktree, and task ledger from candidate-editable paths.
- [x] Hash verification integrated into neo-loop before and after a cycle.
- [x] Added `lab/EVALUATOR.lock.json` with precomputed hashes for the evaluator, controller, quality-gate scripts, and prompt identities.
- [x] Hashed benchmark prompt identities as immutable inputs.
- [x] Deliberate protected-file mutation preflight rejects the exact path (`TASKS.md`) before build or launch.

## RSI-0D. Build deterministic `neo-loop` [CORE DONE]

- [x] Verifies stable health before starting.
- [x] Verifies candidate worktree is clean.
- [x] Records baseline commit and evaluator hashes.
- [x] Builds candidate separately.
- [x] Launches candidate on port 9393.
- [x] Waits for health with timeout.
- [x] Runs text/reasoning smoke and tool-call gates.
- [x] Verifies protected hashes after cycle.
- [x] Stops candidate after result.
- [x] Verifies stable health after teardown.
- [x] Classifies as reject, reviewable-accept, or inconclusive.
- [x] Appends compact result record to `lab/results.jsonl`.
- [x] Enforce candidate-only edits with path allowlist checking.
- [x] Implement cancellation, repeated-turn, memory, and performance gates for candidate runs; live proof remains RSI-0G.
- [x] Implement candidate-owned cleanup in a `finally` path; live proof remains RSI-0F/G.

## RSI-0E. Enforce stop and isolation gates [IMPLEMENTED; live proof pending]

- [x] Enforce build timeout.
- [x] Enforce server-health timeout.
- [x] Enforce benchmark timeout.
- [x] Enforce a 6000 MiB candidate-only VRAM ceiling for the RTX 3060 12GB safe profile.
- [x] Enforce a one-crash-per-cycle ceiling.
- [x] Reject malformed text, reasoning, or tools through immutable stream and tool probes.
- [x] Reject cancellation or repeated-turn regression.
- [x] Reject benchmark mutation through lockfile hashes.
- [x] Reject model-weight or model-identity changes through the locked model identity and fixed candidate launch profile.
- [x] Reject stable worktree mutation and stable listener replacement after every live cycle.
- [x] Candidate teardown targets only its tracked process, never every `llama-server` process.
- [x] Reject port collision.
- [x] Reject overlapping build or runtime directories.
- [x] The controller contains no push, merge, rebase, or promotion operation; reviewable acceptance remains non-promoting.
- [x] Implement cleanup on success, failure, timeout, and interruption; live execution evidence remains pending.

## RSI-0F. Prove one supervised rejection cycle

- [x] Started from a healthy stable server on port 9292.
- [x] Applied one deliberate protected-path candidate change.
- [x] Kept the rejection entirely inside candidate isolation; preflight correctly prevented build and launch.
- [x] Observed the candidate-edit allowlist gate fail on `TASKS.md`.
- [x] Confirmed the candidate is rejected.
- [x] Confirmed no candidate process remained and candidate runtime state was removed.
- [x] Confirmed stable health and listener PID remain unchanged.
- [x] Confirmed stable worktree and protected hashes remain unchanged.
- [x] Confirmed the compact failure record is accurate in `lab/results.jsonl`.
- [x] Restored the candidate worktree cleanly; the next task is resumable.

## RSI-0G. Prove one supervised acceptance cycle [BLOCKED: candidate CMake generation]

- [x] Started from a healthy stable server.
- [x] Applied an inert file only within the allowed candidate path `common/`.
- [ ] Build and launch it only in candidate isolation (blocked: candidate CMake configure/generate failed before build).
- [ ] Confirm every declared gate passes.
- [ ] Mark it reviewable rather than promoting it.
- [ ] Confirm exact diff and evidence are inspectable.
- [ ] Confirm stable remains healthy and unchanged.
- [ ] Confirm result is recorded accurately.
- [ ] Require explicit human approval before stable merge.

## RSI-0H. Add the supervised RSI operator prompt [DONE]

- [x] Added tracked prompt template: `prompts/supervised_rsi_cycle.md`.
- [x] Requires one causal hypothesis.
- [x] Requires candidate-only edits.
- [x] Requires immutable evaluation through `neo-loop`.
- [x] Limits cycle count.
- [x] Forbids automatic promotion.
- [x] Requires final handoff with exact diff, evidence, verdict, and next action.

### RSI-0 exit gate

- [x] Engine source is Git-diffable.
- [ ] Stable and candidate worktrees are proven isolated during candidate build and run.
- [ ] Stable and candidate builds and ports are proven isolated during candidate run.
- [ ] Evaluator and controller immutability are enforced by lockfile and mutation test.
- [ ] Candidate teardown works after every result type.
- [ ] One supervised rejection cycle completes safely.
- [ ] One supervised acceptance cycle completes safely.
- [ ] Stable survives both cycles.
- [ ] Results and handoffs remain accurate.
- [x] Automatic promotion remains disabled.

After every item passes:

```text
Current RSI level: Level 1
Unlock: SUPERVISED_BOUNDED_RSI_AVAILABLE
```

---

# Checkpoint 1 queue: Compute map

Do not begin until RSI-0 closes.

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
- [x] Rolling minimum decode speed recorded with no significant transient stalls.
- [x] Claim ceiling: `NEO3000_BASELINE_OPERATIONAL`.
- [x] LM Studio deferred to optional characterization.
- [x] Engine source custody baseline committed.
- [x] Stable/candidate worktree design created.
- [x] Evaluator manifest and neo-loop core created.
- [x] Supervised RSI prompt template added.
- [ ] Next task: isolate the candidate CMake generation failure, then retry RSI-0G with the same inert allowed-path fixture.
