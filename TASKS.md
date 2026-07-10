# Neo3000 Task Board

**Active checkpoint:** Checkpoint 2, First catalytic compute intervention
**Current RSI level:** Level 1, supervised bounded RSI available
**Baseline evidence through:** `dca929d3d6039e9355c95d34ae5d161309a67e80`
**Claim ceiling:** `NEO3000_BASELINE_OPERATIONAL`
**Mechanism status:** `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN`
**Active bounded objective:** Checkpoint 1A tracing remains active and paused. Checkpoint 2 remains active; qualify the minimum sufficient HoloState-v1 reasoning budget, then run one newly authorized two-root validation under that immutable budget.
**Next exact action:** run the one-shot `qualify-budget` operation only after the protected controller, complete HoloState contract, focused tests, evaluator lock, and preflight are committed and pushed

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

# Current queue: Checkpoint 1

**Unlock achieved:** `SUPERVISED_BOUNDED_RSI_AVAILABLE`

RSI-0 is closed. Level 1 permits bounded supervised candidates with human promotion review; automatic promotion remains forbidden.

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

## RSI-0B. Establish stable and candidate isolation [DONE]

- [x] Stable worktree: `D:\CCC 2.0\AI\Neo3000` on branch `main`, port 9292, `build/stable`.
- [x] Candidate worktree: `D:\CCC 2.0\AI\Neo3000-candidate` on branch `candidate`, port 9393, `build/candidate`.
- [x] Candidate build script: `scripts/build_candidate.ps1`.
- [x] Candidate server script: `scripts/run_candidate.ps1`.
- [x] Isolation design verified: separate builds, ports, and runtime state.
- [x] Verify stable remains responsive during a candidate configure/build attempt and rejected preflight.
- [x] Verify stable remains responsive while candidate serves inference.
- [x] Verify candidate teardown does not affect stable.

## RSI-0C. Freeze the evaluator [DONE]

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

## RSI-0E. Enforce stop and isolation gates [IMPLEMENTED AND LIVE-PROVEN]

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

## RSI-0G. Prove one supervised acceptance cycle [REVIEWABLE ACCEPT]

- [x] Started from a healthy stable server.
- [x] Applied an inert file only within the allowed candidate path `common/`.
- [x] Candidate configured and built only in candidate isolation after source-custody repair.
- [x] Candidate process launched and model loaded only on port 9393; health readiness passed after the timeout-handling repair.
- [x] Enforce the unchanged 6000 MiB ceiling with PID-filtered Windows WDDM dedicated-memory peak sampling; unavailable or lost telemetry rejects.
- [x] Fresh inert-fixture cycle configured, built, loaded, and listened with candidate PID/listener PID `45840`; WDDM sampled 17 times with a 2,301,497,344-byte (2,194.88 MiB) peak, then candidate teardown and stable-integrity checks passed.
- [x] First causal boundary recorded: the exact-text smoke request streamed 67 events but emitted no assistant content (`NEO3000 ONLINE`) within 64 tokens because it remained in reasoning; the text quality gate rejected the cycle before later gates.
- [x] Matched stable and clean-candidate diagnostics classify the text failure as shared completion-budget exhaustion: under `--reasoning auto`, both stop at 64/96/128/192 tokens with reasoning only and emit `NEO3000 ONLINE` at 256 tokens without a source or server change.
- [x] The pinned runtime documents request-level `chat_template_kwargs.enable_thinking=false`; stable returned exact final content in 8 completion tokens at the same 64-token cap. The final-content transport probe can disable thinking only if a separate auto-reasoning gate remains mandatory.
- [x] Matched candidate first/warm decode measurements (15.84, 16.23, 15.58 TPS) and stable repeated measurements (16.61, 16.11, 15.41 TPS) are above 10 TPS; the prior 9.509 TPS observation does not establish that the locked floor is a cold-performance threshold.
- [x] Split evaluator proof: 64-token transport and three-turn repeat use documented request-level reasoning-off with strict exact content; auto-reasoning requires nonempty `reasoning_content` and exact final content at its matched 768-token budget; one warmup is unscored and two 10-TPS counted warm runs are required.
- [x] Stable proof passed: transport 3/3 exact, reasoning 16.91 TPS, warm counted performance 16.33/17.03 TPS.
- [x] Clean candidate proof passed: transport exact, reasoning 15.98 TPS, warm counted performance 17.23/17.76 TPS; PID/listener `29180`, 67 valid WDDM samples, 2,194.88 MiB peak, and full teardown/stable-integrity checks passed.
- [x] Confirm every declared gate passes: transport, reasoning, tool, cancellation, repeat, warm performance, WDDM, cleanup, and stable integrity.
- [x] Mark it reviewable rather than promoting it; `neo-loop` performed no merge, push, or replacement.
- [x] Confirm exact inert diff and evidence are inspectable in `lab/results.jsonl`.
- [x] Confirm stable remains healthy and unchanged; listener PID remained `31188`.
- [x] Confirm result is recorded accurately with candidate PID/listener `38952` and independent WDDM retirement checks.
- [x] Preserve explicit human approval before any stable merge; no stable merge occurred.

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
- [x] Stable and candidate worktrees are proven isolated during candidate build and run.
- [x] Stable and candidate builds and ports are proven isolated during candidate run.
- [x] Evaluator and controller immutability are enforced by lockfile and mutation test.
- [x] Candidate teardown works after every result type.
- [x] One supervised rejection cycle completes safely.
- [x] One supervised acceptance cycle completes safely.
- [x] Stable survives both cycles.
- [x] Results and handoffs remain accurate.
- [x] Automatic promotion remains disabled.

After every item passes:

```text
Current RSI level: Level 1
Unlock: SUPERVISED_BOUNDED_RSI_AVAILABLE
```

---

# Checkpoint 1 queue: Compute map [ACTIVE]

Use the unlocked supervised substrate; stable remains untouched while instrumentation candidates are isolated and reviewable.

## Checkpoint 1A: Trace substrate [ACTIVE / PAUSED]

- [x] Create an isolated instrumentation candidate: candidate commit `3e3023fc389a608ec5a5806eb8e1a50a801486d5`.
- [x] Define fixed trace schema v1 with monotonic timestamps and stable event IDs in `ggml/include/neo-compute-trace.h`.
- [x] Keep trace disabled by default and compiled out of normal builds under `NEO_COMPUTE_TRACE`; the single locked normal cycle returned `reviewable-accept`.
- [x] Build the trace-enabled diagnostic separately in `build/candidate-trace` and keep raw local traces ignored.
- [x] Archive schema-v1 candidate provenance at remote `evidence/checkpoint1a-trace-v1` commit `3e3023fc389a608ec5a5806eb8e1a50a801486d5`.
- [x] Implement bounded schema-v2 aggregation and explicit placement reasons at candidate `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`, archived at `evidence/checkpoint1a-trace-v2`.
- [x] Focused aggregation, compile-out, limit, truncation, placement-reason, exact-PID, prefix-collision, listener-mismatch, grace, and telemetry-loss tests pass.
- [x] The single v2 trace-disabled cycle `neo-loop-20260710T021421` returned `reviewable-accept`; all immutable gates passed, normal binaries contained no trace-writer strings, and no promotion occurred.
- [x] Protect `scripts/neo_trace_diagnostic.py` and its CPU-only safety suite in the evaluator lock; the controller starts exact-PID WDDM sampling immediately after candidate launch and makes readiness depend on process, health, listener, attribution, and memory agreement.
- [ ] Measure instrumentation overhead.

First diagnostic evidence: the cold trace produced 2,407,857 events and 895,639,047 bytes over 449.13 seconds, reached only approximately 1.60 decode TPS versus 14.878 TPS trace-disabled, and did not complete the 768-token request. Overhead is classified `too high`, so matched warm measurements remain incomplete. PID telemetry was invalid because the sampler pattern matched 31-33 GPU-process instances instead of the exact candidate PID; no trace-enabled WDDM peak is claimable. The diagnostic stopped without a rerun.

Second diagnostic evidence: bounded schema-v2 initialization emitted 2,796 aggregate-delta records in 2,745,102 bytes with valid JSON, no truncation, no reported drops, and one writer open per module. Exact-PID telemetry produced no accepted row before inference, so the required pre-workload gate rejected candidate PID/listener `47792`. No cold or warm request ran, no trace-enabled WDDM peak or overhead is claimable, cleanup passed, and the diagnostic was not rerun.

Protected-controller diagnostic evidence: telemetry-only passed at PID/listener `7128` with exact `pid_7128_` WDDM attribution and a 2,168.88 MiB peak. The trace-disabled matched control completed every fixed phase at PID/listener `28696`, with 103 valid samples, a 2,194.88 MiB peak, and 12.747/18.624/15.745/16.097/15.783 TPS for cold reasoning, warm transport, warm reasoning, performance warmup, and counted performance. The single trace-enabled launch used PID/listener `9112`, retained exact attribution with a 2,194.88 MiB peak, then stopped during incomplete cold reasoning when one module reported truncation and up to 28,062 dropped events at its 24 MiB limit. The final artifact was 25,199,004 bytes and 25,554 valid JSON records, below the combined session ceilings; no trace workload phase completed, so overhead remains unmeasured. No retry, merge, or promotion occurred.

Checkpoint 1A remains open but is paused at this boundary. Proven: trace-disabled compile-out, bounded aggregation, exact-PID protected launch control, and explicit truncation/drop detection. Unproven: trace overhead, a completed workload compute map, and a model-runtime bottleneck.

## Immediate parallel boundary: HoloState-0 capability audit

- [x] Case A confirmed: current binary and source expose checkpoints, bounded RAM cache, cache reuse controls, and slot save/restore; no rebuild or source import was required.
- [x] Ran one isolated sidecar plus the single conditional restart-persistence launch on port 9494 with exact-PID WDDM control.
- [x] Audited 7,500-token canonical content / 7,519-token rendered prompts across full replay, identical A, branch B, A/B/A/B, save/erase/restore, and restart restore.
- [x] Process-local RAM/checkpoint reuse is exact: 7,387 tokens reused, 132 fresh, identical cleaned greedy token IDs and reasoning/final hashes, and correct A/B multiplexing.
- [x] Slot file saved/restored 8,069 tokens and 231,311,464 bytes; in-process behavior remained exact but is confounded by the live RAM/checkpoint cache. Restart restore read the file yet processed all 7,519 prompt tokens, so restart reuse failed.
- [x] Do not nominate a restart-persistent durable capsule; retain the exact process-local RAM/checkpoint result as the lawful carrier for HoloState-v1 Live Prefix Lattice.

HoloState-0 is a completed capability audit, not a source-integration candidate. Its exact process-local result supports the now-active Checkpoint 2 integration; its failed restart result does not support HoloState-v2.

## Checkpoint 1B: Backend placement and fallback

- [ ] Measure expected/actual backend, device, operator, tensor shape, and available CUDA rejection reason.
- [ ] Distinguish intentional CPU-MoE from accidental CPU fallback.
- [ ] Measure transfers caused by fallback.

## Checkpoint 1C: CUDA graph lifecycle and synchronization

- [ ] Measure capture, replay, reconstruction, shape signature, allocator growth, and stream identity.
- [ ] Measure explicit and device-to-host synchronization.
- [ ] Separate first-request initialization from warm steady state.

## Checkpoint 1D: MoE geometry

- [ ] Record active expert IDs, route rank, tokens per expert, and bucket-size distribution.
- [ ] Record `MUL_MAT_ID` backend and observable MMQ tile geometry.
- [ ] Estimate inactive/padded work, activation quantization cost, expert residency, and transfer.

## Checkpoint 1E: Gated Delta Net recurrent state

- [ ] Measure per-layer state bytes, allocation, update/copy duration, residence, transfers, and synchronization.
- [ ] Measure per-token recurrent cost and exact snapshot/restore cost.

## Checkpoint 1F: Causal bottleneck selection

- [ ] Identify one or two dominant short-context costs and one or two dominant long-context costs.
- [ ] Establish a measured causal mechanism rather than correlation alone.
- [ ] Select one bounded first intervention from evidence.

---

# Checkpoint 2 queue: First catalytic intervention [ACTIVE]

Current intervention: **HoloState-v1 Live Prefix Lattice**. This is exact process-local executable-prefix reuse, proven as a capability by HoloState-0 and now bounded for operational integration. It is not restart persistence.

Future intervention: **HoloState-v2 Durable Capsule**. Restart-persistent executable-state reuse remains unproven and outside the current task.

Catalytic declaration:

```text
expensive operation: canonical-prefix prompt evaluation
borrowed carrier: exact process-local hybrid prefix state
transformation: evaluate one divergent suffix or branch
extracted result: deterministic reasoning, final content, or tool call
restoration or closure: preserve the canonical checkpoint lattice for later branches
retained lawful state: model/configuration/prefix-identity-bound live cache entries
```

- [x] Declare the expensive operation.
- [x] Declare the borrowed carrier.
- [x] Declare transformation, extracted invariant, and closure law.
- [x] Declare rejection criteria and quality gates: immutable root identities, exact same-branch output, measured reuse, bounded RAM/WDDM, stable isolation, and no automatic promotion.
- [x] Implement one bounded candidate mechanism: protected `holostate_live.py` controller with immutable roots, metadata-only registry, exact process protection, and explicit admission/eviction policy.
- [x] Run the one declared validation under immutable evaluation. It warmed 7,150-token A and 4,879-token B roots, then stopped on the first A1 deterministic-output failure without retry.
- [ ] Quality gate remains incomplete and is not authorized for retry in this task: preserve Pi text, reasoning, tools, cancellation, and repeated turns.
- [x] Classify HoloState-v1 Live as `inconclusive`: A1 reused an inferred 7,017 of 7,165 logical prompt tokens and evaluated 148 fresh tokens in 3,685.92 ms, but consumed the full 768-token completion allowance without closing the deterministic gate. The remaining interleaving and extended proof did not run.
- [x] Separate mechanism from operational quality: HoloState-v1 process-local reuse succeeded; its operational quality gate is blocked by an unqualified shared reasoning budget.
- [x] Protect the repaired boundary with a complete-object evaluator hash, atomic versioned markers, persisted completion classifications, sidecar-compatible tool/cancellation probes, and 38 focused HoloState tests; all protected regression suites and preflight pass.
- [ ] Qualify exactly one ascending budget sequence `1024, 1280, 1536, 2048` on Root A/A1, stop at the first accepted result, and preserve every result without retry.
- [ ] If qualification passes, lock the smallest passing budget into the complete evaluator contract and push the regenerated lock before validation.
- [ ] Run exactly one versioned HoloState-v1 validation-v2 with two roots, the fixed interleaving, tool and cancellation/recovery probes, and 20 extended requests.

Integration evidence:

- [x] Exact binary/model/template identities passed; sidecar PID/listener `42076` had 139 exact-PID WDDM samples and a 2,252.88 MiB peak.
- [x] Stable PID `31188`, health, source status, and the archived trace candidate remained unchanged.
- [x] Cleanup passed: sidecar stopped, runtime removed, port 9494 free, and five WDDM retirement samples empty.
- [x] Confirm `PROCESS_LOCAL_HOLOSTATE_AVAILABLE` remains locked because two-root exact branch behavior and the extended proof did not complete.
- [x] Confirm `RESTART_PERSISTENT_HOLOSTATE_AVAILABLE` remains locked; no restart persistence work ran.

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
- [ ] Next task: execute the protected one-shot HoloState reasoning-budget qualification. HoloState-v2 Durable Capsule remains a separate future durability intervention and is not the current action.
