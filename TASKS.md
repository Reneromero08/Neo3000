# Neo3000 Task Board

**Active checkpoint:** Checkpoint 2, First catalytic compute intervention
**Current RSI level:** Level 1, supervised bounded RSI available
**Baseline evidence through:** CatalyticSwarm-0 v2 integration commit `cf61f90ff5544f2f8bc546e5d661ea72cdda8666`; bound `reviewable-accept` result `AF491153D98877CAACAF5ED89F3446A80AD8ED12D3FAD2CDE22C2AF77CE5BEC7`
**Prepared evaluation:** `catalytic_swarm_1` equal-budget task-advantage contract `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`; repaired, integrated, not executed
**Claim ceiling:** `NEO3000_BASELINE_OPERATIONAL`
**Mechanism status:** `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN`
**Active bounded objective:** Checkpoint 1A tracing remains active and paused. `CatalyticSwarm-0` v1 and v2 are immutable at their executed boundaries. The protected CatalyticSwarm-1 runner is repaired and integrated but has made zero live requests, launched zero sidecars, and created no one-shot artifact.
**Next exact action:** preserve the repaired CatalyticSwarm-1 boundary. The prior live authorization is unconsumed but superseded by the new protected-main identity; any invocation now requires new separate explicit authorization. Do not invoke it, rerun CatalyticSwarm-0 v1/v2, run Deep, claim task advantage, or promote automatically.

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
- **Paused:** Measure instrumentation overhead.

First diagnostic evidence: the cold trace produced 2,407,857 events and 895,639,047 bytes over 449.13 seconds, reached only approximately 1.60 decode TPS versus 14.878 TPS trace-disabled, and did not complete the 768-token request. Overhead is classified `too high`, so matched warm measurements remain incomplete. PID telemetry was invalid because the sampler pattern matched 31-33 GPU-process instances instead of the exact candidate PID; no trace-enabled WDDM peak is claimable. The diagnostic stopped without a rerun.

Second diagnostic evidence: bounded schema-v2 initialization emitted 2,796 aggregate-delta records in 2,745,102 bytes with valid JSON, no truncation, no reported drops, and one writer open per module. Exact-PID telemetry produced no accepted row before inference, so the required pre-workload gate rejected candidate PID/listener `47792`. No cold or warm request ran, no trace-enabled WDDM peak or overhead is claimable, cleanup passed, and the diagnostic was not rerun.

Protected-controller diagnostic evidence: telemetry-only passed at PID/listener `7128` with exact `pid_7128_` WDDM attribution and a 2,168.88 MiB peak. The trace-disabled matched control completed every fixed phase at PID/listener `28696`, with 103 valid samples, a 2,194.88 MiB peak, and 12.747/18.624/15.745/16.097/15.783 TPS for cold reasoning, warm transport, warm reasoning, performance warmup, and counted performance. The single trace-enabled launch used PID/listener `9112`, retained exact attribution with a 2,194.88 MiB peak, then stopped during incomplete cold reasoning when one module reported truncation and up to 28,062 dropped events at its 24 MiB limit. The final artifact was 25,199,004 bytes and 25,554 valid JSON records, below the combined session ceilings; no trace workload phase completed, so overhead remains unmeasured. No retry, merge, or promotion occurred.

Checkpoint 1A remains open but is paused at this boundary. Proven: trace-disabled compile-out, bounded aggregation, exact-PID protected launch control, and explicit truncation/drop detection. Unproven: trace overhead, a completed workload compute map, and a model-runtime bottleneck.

## Immediate parallel boundary: HoloState-0 capability audit

- [x] Case A confirmed: current binary and source expose checkpoints, bounded RAM cache, cache reuse controls, and slot save/restore; no rebuild or source import was required.
- [x] Ran one isolated sidecar plus the single conditional restart-persistence launch on port 9494 with exact-PID WDDM control.
- [x] Audited 7,500-token canonical content / 7,519-token rendered prompts across full replay, identical A, branch B, A/B/A/B, save/erase/restore, and restart restore.
- [x] Process-local RAM/checkpoint reuse is exact: 7,387 tokens reused, 132 fresh, identical cleaned greedy token IDs and raw pre-final/final hashes, and correct A/B multiplexing. The legacy pre-final hash is not `reasoning_content` channel proof.
- [x] Slot file saved/restored 8,069 tokens and 231,311,464 bytes; in-process behavior remained exact but is confounded by the live RAM/checkpoint cache. Restart restore read the file yet processed all 7,519 prompt tokens, so restart reuse failed.
- [x] Do not nominate a restart-persistent durable capsule; retain the exact process-local RAM/checkpoint result as the lawful carrier for HoloState-v1 Live Prefix Lattice.

HoloState-0 is a completed capability audit, not a source-integration candidate. Its exact process-local result supports the now-active Checkpoint 2 integration; its failed restart result does not support HoloState-v2.

## Checkpoint 1B: Backend placement and fallback

- **Paused:** Measure expected/actual backend, device, operator, tensor shape, and available CUDA rejection reason.
- **Paused:** Distinguish intentional CPU-MoE from accidental CPU fallback.
- **Paused:** Measure transfers caused by fallback.

## Checkpoint 1C: CUDA graph lifecycle and synchronization

- **Paused:** Measure capture, replay, reconstruction, shape signature, allocator growth, and stream identity.
- **Paused:** Measure explicit and device-to-host synchronization.
- **Paused:** Separate first-request initialization from warm steady state.

## Checkpoint 1D: MoE geometry

- **Paused:** Record active expert IDs, route rank, tokens per expert, and bucket-size distribution.
- **Paused:** Record `MUL_MAT_ID` backend and observable MMQ tile geometry.
- **Paused:** Estimate inactive/padded work, activation quantization cost, expert residency, and transfer.

## Checkpoint 1E: Gated Delta Net recurrent state

- **Paused:** Measure per-layer state bytes, allocation, update/copy duration, residence, transfers, and synchronization.
- **Paused:** Measure per-token recurrent cost and exact snapshot/restore cost.

## Checkpoint 1F: Causal bottleneck selection

- **Paused:** Identify one or two dominant short-context costs and one or two dominant long-context costs.
- **Paused:** Establish a measured causal mechanism rather than correlation alone.
- **Paused:** Select one bounded first intervention from evidence.

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
- **Locked:** Quality gate remains incomplete and is not authorized for retry in this task: preserve Pi text, reasoning, tools, cancellation, and repeated turns.
- [x] Classify HoloState-v1 Live as `inconclusive`: A1 reused an inferred 7,017 of 7,165 logical prompt tokens and evaluated 148 fresh tokens in 3,685.92 ms, but consumed the full 768-token completion allowance without closing the deterministic gate. The remaining interleaving and extended proof did not run.
- [x] Separate mechanism from operational quality: HoloState-v1 process-local reuse succeeded; its legacy raw-output gate exhausted the tested range without the literal marker.
- [x] Protect the repaired boundary with a complete-object evaluator hash, atomic versioned markers, persisted completion classifications, sidecar-compatible tool/cancellation probes, and 40 focused HoloState tests; all protected regression suites and preflight pass.
- [x] Qualify exactly one ascending budget sequence `1024, 1280, 1536, 2048` on Root A/A1. Every raw `/completion` stream reused 7,878 of 8,026 logical prompt tokens, consumed its exact configured limit, and ended without the final marker. The legacy endpoint/parser did not prove `reasoning_content` channel attribution.
- [x] Reach the declared no-pass stop after 2048. No selected budget was written, no prompt or quality gate was changed, and no qualification retry occurred.
- [x] Correctly skip the conditional locked-budget rotation and validation-v2 because qualification did not pass; their versioned v2 marker/result remain absent.

### HoloState-v1.1 message-boundary protocol [EXECUTED]

Evidence correction:

```text
Proven: raw /completion exhausted each configured limit without the literal marker.
Not proven: every raw token belonged to reasoning_content.
```

The legacy endpoint exposed one raw content stream, and `parse_final_structure` labeled the whole raw string as reasoning when the marker was absent. Historical evidence remains byte-identical.

- [x] Published evaluator-locked protocol commit `3fb00fe93d0fb22e203d8e26d86173f5e3d2ee32` before claiming the marker.
- [x] Confirmed both versioned worker paths and both validation-v2 paths were absent before the atomic one-shot claim.
- [x] Executed the audit exactly once. It stopped at `warm A` on `completion-token-evidence-missing`; no Fast, Root B, or Deep request ran.
- [x] Preserved the ignored v1 result's original locked fields: `FAST_PROCESS_LOCAL_HOLOSTATE=reject`; `DEEP_PROCESS_LOCAL_HOLOSTATE=inconclusive`.
- [x] Added a later adjudication: protocol v1 is an instrumentation reject; Fast capability is untested/inconclusive because no Fast request ran; Deep capability is untested/inconclusive because no Deep request ran.
- [x] Kept `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE`, broader process-local, restart-persistent, and CatalyticSwarm-0 states locked.

Lane F remains thinking-disabled at 64 tokens. Lane D remains reasoning-auto at 768 tokens. Both use separate system/reference and user-assignment messages through `/v1/chat/completions`; old budget qualification, validation-v2, extended proof, persistence, and automatic promotion remain forbidden here.

### HoloState worker protocol v2 [EXECUTED / INCONCLUSIVE]

- [x] Version the parser/ledger/canary contract and bind all five historical evidence hashes.
- [x] Accumulate delta- and cumulative-style token arrays without allowing a final empty array to erase prior evidence.
- [x] Add an 8 MiB / 50,000-record reasoning-redacted stream ledger and a thinking-disabled token-array canary.
- [x] Pass 85 HoloState, 11 trace, 9 evaluator, and 5 WDDM tests plus compilation, root bounds, and protected preflight.
- [x] Committed and pushed exact protected protocol `b2559f7c0c06e35a3e360b71ed13b69c4eb1eb7c`, then invoked the fixed audit exactly once with no retry.
- [x] Classified the stop as `stable-listener-query-timeout` during sidecar readiness before the parser canary. No warm, Fast, or Deep request was attempted.
- [x] Preserved cleanup, stable PID `32684`, candidate isolation, all five historical hashes, every availability lock, and the automatic-promotion prohibition.

### HoloState worker protocol v3 [EXECUTED / INSTRUMENTATION REJECT]

- [x] Inspected connector branch `codex/holostate-listener-readiness-v3` at `60defbb2ffd1dfc54d40374fd529554ba0acf287`: exactly four commits ahead of protected main and exactly four new listener/readiness files under draft PR #1.
- [x] Retained the connector parser, checked query/retry primitive, no-query-storm readiness state machine, and CPU-only tests; repaired only concrete test/review defects in runtime mocking, malformed rows, hard total windows, empty-port qualification, partial failure evidence, and post-query rechecks.
- [x] Added complete-object `holostate_worker_protocol_v3` with exact v2 endpoint, identities, roots, parser, ledger, canary, warm/Fast/Deep sequence, capture, memory, isolation, and availability semantics. Only versioned evidence paths, expanded immutable prior bindings, and readiness control differ.
- [x] Separate the atomic readiness marker from capability attempt/result/ledger creation. A readiness non-pass creates no capability artifact and leaves Fast/Deep untested and inconclusive.
- [x] Require one marker-to-pass deadline, bounded checked ownership after the readiness claim, no listener subprocesses in the 250 ms model-load loop, fresh pre/post request ownership, checked pre/post teardown, exact-PID WDDM attribution, and fail-closed frozen-evidence/final-safety gates.
- [x] Hard-retire v1/v2/qualification/validation-v2 command paths; preserve all prior ignored bytes and all five prior complete-object hashes.
- [x] Pass compilation; 18 listener, 10 readiness, 102 HoloState, 11 trace, 9 evaluator, and 5 WDDM tests; and stable tokenizer-only Root A/B bounds at 8,131/4,408 tokens without generating output.
- [x] Pushed exact integration commit `b45249c6620c2645232883c5035b260683706dcd`, passed protected main preflight, and invoked `audit-worker-protocol-v3` exactly once with no retry.
- [x] Readiness passed in 29.61 seconds. Sixteen checked `netstat` queries each passed on the first attempt with zero timeout, unavailable, or wrong-owner samples; stable PID `32684` and sidecar PID `42236` remained exact.
- [x] Executed the parser canary: exact visible `TOKEN ARRAY CANARY`, empty reasoning, and `finish_reason=stop`, but five reported completion tokens versus zero generated token IDs. Ten ledger events contained nine absent arrays and one ignored empty array, so the canary instrumentation rejected as `stream-token-count-mismatch`.
- [x] Stopped before Root A/B warm, Fast, repeats, or Deep. All request counts for those stages remain zero and both capability verdicts remain inconclusive.
- [x] Preserved all ownership boundaries, frozen readiness and prior evidence, clean candidate `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`, 14 exact-PID WDDM samples with a 2,250.88 MiB peak, 153,636,864 bytes host growth, clean teardown, five empty retirement samples, stable PID `32684`, and free port 9494.
- [x] Recorded readiness/attempt/result/ledger SHA-256 values `6C761F40E6EBCD43B608218CC84D0AA1F75D2E1FDCEB15EB9DC103168E6EFCBF`, `4D70D8E53056A2BB2A00320051855B4D612547150A5FC68C068D17DEC66EFBFE`, `387E82B02BA8F6992111722595AEE05055A979A54A8D2EE6D9F5A1EE38C645E3`, and `26D65B9F474EF84B3F9483D6DDB1838280F1D54D476FDF14B5595A624EA5A583`.
- [x] Preserve the v3 no-retry instrumentation boundary under the separately authorized, versioned v4 successor. Do not run v1, v2, v3, qualification, validation-v2, persistence, or promotion.

### HoloState worker protocol v4 [EXECUTED / REVIEWABLE ACCEPT]

- [x] Import the seven-file PR #2 connector substrate from `codex/holostate-chat-token-evidence-v4` at `168fb4d0e666cbc058a59826ff9e97359889d835` without importing its sixteen connector commits.
- [x] Repair the connector fail-closed boundary: native IDs require an available exact completion-count match; visible retokenization is repeated deterministically; and one-terminal-token reconciliation requires complete direct EOS metadata.
- [x] Capture bounded terminal stop metadata in the shared stream parser without persisting reasoning text, including when terminal metadata precedes a later usage-only event.
- [x] Add separately protected readiness, no-generation tokenizer, capability-attempt, result, and bounded-ledger v4 paths. Bind all v1/v2/v3 objects and ignored evidence plus pinned source and source-test identities.
- [x] Preserve the exact v3 boundary and record that its declared exact-count law stopped correctly; pinned source later reconciled four visible tokens plus one server-counted terminal EOS token without establishing the EOS ID or a complete generated sequence.
- [x] Before execution, pass 232 CPU-only tests plus compilation. At that boundary no live inference endpoint, readiness marker, tokenizer artifact, capability attempt, result, or v4 stream ledger had been created.
- [x] Pushed exact integration commit `da04c5bf388c3d091da4e2f1aee33bf852377517`, passed protected main preflight, and invoked `audit-worker-protocol-v4` exactly once. No retry occurred.
- [x] Passed readiness in 33.015 seconds and the no-generation tokenizer qualification with repeated exact IDs `[60738, 30094, 18916, 8378]` plus exact detokenization.
- [x] Passed the parser canary with four visible tokens, five completion tokens, usage delta one, direct terminal `eos` metadata, unknown EOS token ID, and no full-sequence claim.
- [x] Warmed Root A/B at 8,173/4,436 tokens, then accepted Fast A1/B1/A2/B2 and exact A1/B1 repeats with 8,144/4,407 cached tokens and 21 fresh tokens per Fast request.
- [x] Passed repeat determinism, distinct-branch, cross-root isolation, resource, ledger, ownership, cleanup, frozen-evidence, source-authority, historical-evidence, stable, and candidate gates.
- [x] Classified Deep A1 independently as `reject`: reasoning was present, but the request exhausted 768 tokens with `finish_reason=length` and no final assistant content. The completed Fast proof survived.
- [x] Recorded readiness/tokenizer/attempt/result/ledger SHA-256 values `4B8A44B4CB3DE9355B8A3D4E3FC945DD685EA35B98F5BF0C0160DAA090249BA7`, `EB10127666CDADE0D6A8E7EF59CA7D4310B64B89619800DF245BD769666A587D`, `6197D986FD3ED030340A82300245AE0EF1249229E21162BF6796F7F614A7EA19`, `396C1E76EC07EB64E8FF700E49F45A931638BD071A7955941712314CADDF59CF`, and `CD96EE1F41F15E9953705F7DDA762D1111D60E04C828F9B157D314D789F0F104`.
- [x] Bind tracked v4 evidence and `neo-exp-0018`; pass 232 post-audit CPU-only tests plus compilation and JSON/JSONL validation.
- [x] Unlock only `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE`; keep broader process-local and restart-persistent availability locked, authorize but do not execute `CatalyticSwarm-0`, and keep automatic promotion disabled.
- [x] Preserve this no-retry evidence boundary. The separately scoped `CatalyticSwarm-0` control protocol below does not rerun v1-v4 or infer execution from prior authorization.

### CatalyticSwarm-0 bounded control proof [EXECUTED ONCE / READINESS INCONCLUSIVE]

- [x] Inspect draft PR #3 at connector head `c73a684b0d83ba9f59d11396a579f5e9a3478c2b`: exactly four commits from protected `f17caefa41527f910e1039e70b33c8035c418ea9`, adding only the declared blackboard, scheduler, adapter, and CPU-only test files.
- [x] Retain the callback-driven connector substrate without importing its four commits individually; repair only demonstrated fail-open plan, contribution, adapter, blackboard, lease, and 64-token defects with negative tests.
- [x] Lock one exact 32-worker plan: 16 proposal, 8 evidence, 6 critique, 2 synthesis; one physical HoloState slot; thinking disabled; maximum 64 completion tokens; deterministic identities, seeds, parent graph, phase routing, and fixed execution order.
- [x] Add separately versioned control qualification, readiness, structured parser canary, capability attempt/result, bounded ledger, and append-only blackboard artifacts under ignored `state/catalytic_swarm`.
- [x] Reuse the protected HoloState v4 sidecar, ownership, WDDM, terminal-EOS, tokenizer, and cleanup infrastructure. Deep, persistence, CUDA, kernels, model, Pi, stable behavior, archived trace candidate, retry, and promotion remain outside scope.
- [x] Pushed exact integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280` as protected `main`, passed protected preflight, and invoked `audit-catalytic-swarm-0` exactly once. No retry occurred.
- [x] Passed generation-free control qualification, then stopped readiness as `inconclusive` when the exact-PID WDDM counter query timed out and the controller classified `candidate-vram-telemetry-lost`.
- [x] Recorded sidecar PID `44748`, 6 valid exact-PID WDDM samples, and a 92.84 MiB peak before telemetry was lost. The structured parser canary, capability attempt, all 32 workers, physical leases, bounded ledger, and blackboard remained unattempted or absent.
- [x] Completed lifecycle cleanup: PID `44748` stopped, runtime state retired, port 9494 became free, and stable PID `32684` remained healthy. The composite resource gate remained non-pass because telemetry was lost.
- [x] Classified readiness, `STRUCTURED_HOLOSTATE_MICROWORKER`, and `CATALYTIC_SWARM_CONTROL` as `inconclusive`. Their new availability states remain locked; the existing process-local micro-worker unlock remains intact. Broader process-local HoloState, restart persistence, task advantage, and SOTA claims remain locked; automatic promotion remains false and v4 evidence is preserved.
- [x] Bound the exact early-stop evidence as `neo-exp-0019` in the protected evaluator/result/lock for this evidence commit without another live invocation.
- [x] Preserve v1 without retry. No further v1 live work is authorized.

### CatalyticSwarm-0 v2 WDDM telemetry successor [REVIEWABLE ACCEPT]

- [x] Inspect draft PR #5 at exact connector head `428edaaa2772d6805c4733a9d629a7812838a932`: exactly two commits from protected `3fcef46c4863814f3396d1466269d4a3ef0f8c9a`, adding only the declared WDDM resilience module and its CPU-only tests.
- [x] Pass all 14 connector tests before controller integration.
- [x] Preserve legacy `CandidateVramSampler` behavior when no policy is supplied; add a separately activated policy that tolerates at most two consecutive unavailable queries, fails on the third or a valid-sample gap over 30 seconds, requires a sample no older than 5 seconds for admission, and retains the immediate 6000 MiB hard ceiling.
- [x] Add fresh exact-PID WDDM admission at readiness, parser-canary, capability-attempt, every worker request, and teardown boundaries while process, health, listener, deadline, and hard-failure checks remain live.
- [x] Add complete-object `catalytic_swarm_0_v2` with exact v1 inheritance, exact predecessor evidence bindings, seven new v2 one-shot paths, connector source protection, and no retry, Deep, persistence, or promotion authority.
- [x] Preserve the exact v1 Root A prompt bytes from integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280` even though the authoritative catalytic roadmap is published before v2 execution.
- [x] Import and reconcile `docs/CATALYTIC_RUNTIME_ROADMAP.md` from source commit `87fea7a5c51b0915a2cc1fb63dbbbdd306dff445`; make it authoritative without duplicating the full architecture in this task board.
- [x] Pass compilation and 338 CPU-only regression tests without contacting a live inference endpoint; all v1 artifacts remain exact and all seven v2 artifacts remain absent.
- [x] Commit and push the architectural integration at `cf61f90ff5544f2f8bc546e5d661ea72cdda8666`, fast-forward exact protected `main`, and pass protected preflight. One artifact-claiming live `audit-catalytic-swarm-0-v2` invocation ran; no retry occurred after claim. One earlier pre-claim command refusal created zero artifacts and made zero model requests. No Deep request or automatic promotion occurred.
- [x] Pass control qualification, readiness, parser canary, all 32 thinking-disabled worker requests, 32 one-slot leases, 32 verifier receipts, the append-only blackboard chain, 1,319 bounded ledger records, and two synthesis entries. Phase execution was exactly 16 proposal / 8 evidence / 6 critique / 2 synthesis.
- [x] Classify v2 as `reviewable-accept`. Exact-PID WDDM produced 177 valid samples, zero unavailable samples, zero recoveries, maximum failure streak 0, maximum valid-sample gap 2.938 seconds, 107 passed freshness boundaries, and a 2,284.9 MiB peak. Maximum host-private growth was 727,982,080 bytes.
- [x] Pass cleanup, stable/candidate isolation, exact v1 preservation, worker-v4 preservation, sampler retirement, runtime removal, free port 9494, and five empty post-teardown WDDM samples.
- [x] Bind exact v2 SHA-256 values: control `1FC67796F436E69B1B2C2F132345C0335FADF6D1452E7F98D8A92D78CB616CE3`; readiness `129FD883FD03BBEF8B216AC67F77CBE854CA798A86BBC18A11D4DCDF010E7124`; parser canary `9282D7F8AE195C866E767A7F0D3BCB0A366E3FC3C1509A7DB1F99F1C541191B5`; attempt `0E9A839B7AD9D50AE6FD82DD3C63A93D23596C4A32FAF515BAC67A68EFEE8866`; result `AF491153D98877CAACAF5ED89F3446A80AD8ED12D3FAD2CDE22C2AF77CE5BEC7`; ledger `C523EF77C80CDD4783D2E41103FCD72490A4C837DA2B3988B29F8D7A97E1F7F9`; blackboard `197929DF8DF62A24480A64C071651CED43E16D82F0B6DA5A9AB740C6C1236964`.
- [x] Unlock only `STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE` and `CATALYTIC_SWARM_CONTROL_AVAILABLE`. Keep broader process-local HoloState, restart persistence, task advantage, SOTA, and automatic promotion locked.

### CatalyticSwarm-1 equal-budget task advantage [REPAIRED / INTEGRATED / NOT EXECUTED]

- [x] Integrate draft PR #6 at exact connector head `aaeb3fe8cc906121fdfcb8ed41d9420b2849d8b6` as one architectural change without importing its twelve connector commits.
- [x] Freeze the eight-task DSL suite at SHA-256 `4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92` and the complete contract at `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`.
- [x] Freeze four 32-request, one-slot arms: serial-chain `99FE4402A487EEAF07FAEE7A64CAB241A888E1CB916D09C62BDA493AB08EEF53`; best-of-N `E989ECB8A53E9AD24885759627D3E3BA9A16E76A41A770E70784644A9A96696A`; sparse swarm `9289DE195D12AB93A9A9DD70949C92FC55D40E0D930CAD521605FC1707E116DE`; verified swarm `46A2CEADA66217AC2DD3E0BD6D1C20A052EFE9D76EE236887AF18428409A772C`.
- [x] Repair only demonstrated connector defects: defer hidden and best-of-N scoring to their protected boundaries; require the cached token prefix to cover the complete common public root plus accepted v4 token-evidence scopes; bind and revalidate canonical task/root/arm observations, totals, selections, and scores; keep sparse/verified model-visible prompts identical except for public-score visibility; require public plus hidden exact success; and redact hidden suite material from public serialization.
- [x] Prepare one common public-root warm per task outside arm budgets, exact Latin-square arm order, strict hidden/arm/task isolation, 1,024 comparison requests plus 8 warm requests, 32-token request ceilings, per-arm 1,024 completion / 8,192 fresh-prompt ceilings, 1.10 parity gates, and a 64 MiB / 80,000-record metadata-only ledger.
- [x] Protect the complete contract, connector/controller sources, predecessor bindings, and seven ignored one-shot paths. No `catalytic_swarm_1_evidence` object exists.
- [x] Add the protected `audit-catalytic-swarm-1` command and hard-retire CatalyticSwarm-0 v2 against rerun. Integration and tests make no model request and launch no sidecar.
- [x] Keep all seven `state/catalytic_swarm_1/*-v1` paths absent; live requests remain zero; task advantage, SOTA, broader process-local HoloState, restart persistence, and automatic promotion remain locked.
- [x] Harden the protected runner without changing the frozen experiment: exact stable/candidate custody before and after every prospective model request, host/resource enforcement after every request, hard per-task parity stops, guarded parser-to-attempt cleanup transfer, and terminal reconciliation of `2064 / 1032 / 8` custody, host-memory, and task-parity boundaries.
- [x] Protect the retained runtime-safety helper and its direct CPU-only regression suite. The task suite, complete contract, four plan hashes, prompts, programs, hidden data, Latin-square order, budgets, and advantage thresholds remain exact.
- [x] Record the prior live authorization as unconsumed but superseded by the repaired protected-main identity. This repair launched zero sidecars, made zero live model requests, claimed no one-shot artifact, and added no evidence object.
- [ ] After new separate explicit authorization bound to the repaired protected main, invoke `audit-catalytic-swarm-1` once. This unchecked item is execution authority, not permission under the current repair task.

Preserved v1 executed boundary:

- Root A rendered 7,806 tokens and returned exact visible content `HOLOSTATE ROOT WARM`, empty reasoning metadata, `finish_reason=stop`, and 7 completion tokens. Prompt processing was 145,519.789 ms at 53.642 TPS.
- The parser recorded zero complete generated-token IDs, so the locked token-evidence gate rejected the warm before reuse could be measured.
- Pinned-source inspection explains the instrumentation defect: partial streaming responses carry per-token arrays, the final streaming response carries an empty array, and the executed parser replaced rather than accumulated arrays. Raw SSE events were not persisted, so this diagnosis is source-based rather than direct event replay.
- Result SHA-256 is `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2`; attempt SHA-256 is `F634CA2732CEBBE424D4634F8EFAD035C6E11EAABB0D34E40A0F1EC09A2DF975`.
- Sidecar PID `34580` peaked at 2,252.88 MiB over 73 exact-PID WDDM samples. Cleanup, five retirement samples, stable PID `32684`, isolation, and all three historical evidence hashes passed.

Preserved HoloState-v1 integration evidence:

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
Next task: preserve the repaired, integrated, unexecuted CatalyticSwarm-1 boundary. The prior authorization is unconsumed but superseded; a live invocation requires new separate explicit authorization bound to the repaired protected main. No task advantage is yet proven. CatalyticSwarm-0 v1/v2 and worker protocols v1-v4 remain immutable.
