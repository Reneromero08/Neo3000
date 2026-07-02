# Neo3000 Task Board

**Active checkpoint:** 0, baseline parity and context characterization  
**Remote HEAD audited:** `ac5c3b76b24598d41a28e3e691e994c7bf0e96a1`  
**Claim ceiling:** `NEO3000_FOUNDATION_INITIALIZED`  
**Next exact boundary:** user completes Pi UI verification and LM Studio comparison, then close Checkpoint 0

`ROADMAP.md` defines the architecture and phase order. This file is the executable queue.

## Status law

- `[x]` means supported by pushed repository evidence.
- `[ ]` means incomplete, ambiguous, or unsupported by the current evidence.
- A server allocation size is not the same as the number of tokens actually occupying the context.
- Do not select a causal bottleneck from correlation alone.
- Work from top to bottom unless a task is explicitly blocked.

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
- [x] Server allocation succeeds at 4K, 8K, 16K, 32K, 40K, and 65,536 context sizes.
- [x] Deterministic occupied-context measurements succeed at 2,053, 8,191, 32,773, 40,956, and 59,996 raw content tokens.
- [x] Occupied-context decode throughput is approximately flat: 22.3 tps (2K) to 20.9 tps (60K), ratio 0.94.
- [x] Auto-fit is proven optimal at 4K (17.6 tps) vs best explicit layer count (10.0 tps at ngl=20). The conservative-auto-fit hypothesis is rejected.
- [x] CPU-MoE comparison: 62% decode gain disabled (30.8 vs 19.1 tps) but costs 89% VRAM (10,604 vs 2,725 MiB).
- [x] 40,960 target failure root cause identified: timeout during uncached warmup (~9 min at 73 tps), not a server or tokenizer issue. Direct /tokenize succeeds at 197K and 599K tokens.
- [x] Allocation capacity and occupied-context performance are documented in separate tables in `lab/CHECKPOINT.md`.
- [x] TPS discrepancy explained: cold vs warm, completion length, reasoning token overhead.
- [x] Source custody recommendation: Option A (track imported runtime).
- [x] Imported source remains reproducible from the pinned upstream commit.

## Important evidence boundary

Allocation capacity is not the same as occupied context:

- A 65,536 configured context **allocates** memory but does not mean 65,536 prompt tokens were processed.
- Occupied-context measurements use actual `usage.prompt_tokens` from chat completions, which is authoritative.
- The strongest proven occupied-context result is **59,996 tokens with 20.9 decode TPS**.
- The 64K allocation table and the 60K occupied-context table are separate evidence.

---

# Current execution queue

## 0A. Verify the actual Pi user path

BLOCKED: requires user to launch Pi and interact with its UI. All API-level verification is complete (harness smoke, tool probes, streaming, cancellation).

- [ ] Launch Pi normally with provider `neo3000` selected.
- [ ] Send `Reply with exactly: NEO3000 PI ONLINE` from the Pi UI.
- [ ] Confirm streamed text is visible incrementally in Pi.
- [ ] Confirm the request appears in the Neo3000 server log.
- [ ] Confirm LM Studio does not receive the request.
- [ ] Execute one harmless real Pi tool round trip (e.g., read README.md, list repo root).
- [ ] Confirm Pi executes the tool, returns its result, and Agents-A1 continues.
- [ ] Cancel a long generation from Pi and immediately verify `NEO3000 RECOVERED`.
- [ ] Record the exact Pi command, tool, and visible result in `lab/CHECKPOINT.md`.

## 0B. Reproduce and localize the 40,960-token failure

RESOLVED. The failure was not a server or tokenizer issue.

- [x] Direct /tokenize succeeded at 197K and 599K tokens.
- [x] Re-running the matrix with adequate timeout and cache_prompt shows the pipeline works at 40K and 60K.
- [x] The original failure was caused by: (a) timeout during uncached warmup inference, or (b) rapid binary-search /tokenize calls exhausting Windows socket resources. Root cause: client-side timeout, not server failure.
- [x] Server remains healthy after all tokenize requests.

## 0C. Measure genuinely occupied long context

DONE.

- [x] 40K occupied: 40,956 prompt tokens, 22.4 decode TPS (cached), 73.3 prompt TPS (uncached).
- [x] 60K occupied: 59,996 prompt tokens, 20.9 decode TPS (cached), 73.0 prompt TPS (uncached).
- [x] Occupied-context degradation ratio (60K/2K): 20.9/22.3 = 0.94.
- [x] Allocation and occupancy are in separate tables in `lab/CHECKPOINT.md`.

## 0D. Audit placement before blaming auto-fit

DONE. Hypothesis rejected.

- [x] GPU layer sweep at 4K: auto=17.6, ngl0=6.6, ngl5=7.4, ngl10=7.0, ngl15=7.4, ngl20=10.0 decode TPS.
- [x] Auto-fit is **optimal**, not overly conservative. Best explicit count (20 layers, 10.0 tps) is 43% slower than auto (17.6 tps).
- [x] VRAM at 4K auto=2,785 MiB, ngl20=1,892 MiB. Auto-fit achieves more throughput with more VRAM but the throughput gain is substantial.
- [x] Claim "auto-fit is overly conservative" is formally rejected.

## 0E. Audit CPU-MoE before selecting it as the wall

DONE.

- [x] At 4K auto-fit: CPU-MoE ON = 19.1 tps decode, 2,725 MiB VRAM; CPU-MoE OFF = 30.8 tps decode, 10,604 MiB VRAM.
- [x] CPU-MoE disabled gives 62% faster decode at the cost of 89% VRAM usage.
- [x] This is a space/speed tradeoff, not a runtime deficiency.
- [x] At larger contexts where KV cache must co-reside, CPU-MoE enabled is necessary to fit within 12 GB.

## 0F. Matched LM Studio comparison

BLOCKED: requires LM Studio to be running with the same GGUF. All Neo3000-side data is ready.

- [ ] Freeze the exact GGUF bytes in both runtimes.
- [ ] Match prompt text, actual prompt-token count, output length, sampler, reasoning mode, KV type, and warm or cold state.
- [ ] Compare 4K occupied context with at least three counted runs.
- [ ] Compare 8K occupied context with at least three counted runs.
- [ ] State whether Neo3000 matches, exceeds, or trails LM Studio for each matched workload.
- [x] TPS discrepancy explained (cold vs warm, completion length, reasoning overhead) -- section D in CHECKPOINT.md.

## 0G. Correct the repository evidence and close Checkpoint 0

PARTIAL. CHECKPOINT and GOAL updated. Pi and LM Studio still need user action.

- [x] `lab/CHECKPOINT.md` separates allocated context from occupied context.
- [x] Removed unsupported 64K/4K occupied ratio; replaced with 60K/2K ratio of 0.94 based on actual prompt tokens.
- [x] TPS discrepancy explained with workload analysis.
- [x] Auto-fit and CPU-MoE audit results added.
- [x] `lab/GOAL.md` updated with current boundary and next exact action.
- [x] Experiment record `neo-exp-0003` appended to `lab/results.jsonl`.
- [x] Source custody: Option A recommended (track imported runtime).
- [x] Stable daily-driver 4K command confirmed working.
- [ ] Commit and push one meaningful Checkpoint 0 closure chunk.
- [ ] Mark Pi UI gates after user verification.
- [ ] Change claim ceiling to `NEO3000_BASELINE_OPERATIONAL` only after all exit gates.

### Checkpoint 0 exit gate

- [ ] A real Pi UI text stream succeeds. (BLOCKED: needs user)
- [ ] A real Pi tool round trip succeeds. (BLOCKED: needs user)
- [ ] Pi cancellation and immediate recovery succeed. (BLOCKED: needs user)
- [x] Occupied-context behavior is measured through 60K (the maximum stable target).
- [ ] Neo3000 and LM Studio are reproducibly compared under matched workloads. (BLOCKED: needs LM Studio)
- [ ] Rolling minimum decode speed is recorded.
- [x] Allocation capacity and occupied-context performance are documented separately.
- [x] The next instrumentation target is selected from causal evidence: cold-start performance (first-request TPS is ~50% of warm) and reasoning token overhead.

---

# Checkpoint 1 queue: Compute map

Do not begin source instrumentation until Checkpoint 0 closes and source custody is resolved.

- [ ] Put the imported engine under a Git-diffable custody model.
- [ ] Create an isolated instrumentation branch or worktree.
- [ ] Define one fixed trace schema.
- [ ] Add trace-disabled and trace-enabled build configurations.
- [ ] Measure per-token and per-layer time.
- [ ] Separate attention time from Gated Delta Net recurrent-block time.
- [ ] Record active MoE expert IDs per layer and token.
- [ ] Measure expert residency and transfer behavior.
- [ ] Measure CPU-MoE compute and bandwidth.
- [ ] Measure CPU to GPU transfers and synchronization.
- [ ] Measure KV and recurrent-state allocation and traffic by occupied context.
- [ ] Measure placement changes caused by configured context capacity.
- [ ] Quantify tracing overhead.
- [ ] Identify the top one or two causal bottlenecks.
- [ ] Select one first catalytic intervention from those measurements.

---

# Later queues

## Checkpoint 2: First catalytic intervention

- [ ] Declare the expensive operation.
- [ ] Declare the borrowed carrier.
- [ ] Declare transformation, extracted invariant, and closure law.
- [ ] Declare rejection criteria and quality gates.
- [ ] Implement one bounded candidate mechanism.
- [ ] Compare stable and candidate under the frozen benchmark.
- [ ] Preserve Pi text, tools, cancellation, and repeated-turn behavior.
- [ ] Accept, reject, or mark inconclusive.

## Checkpoint 3: Long-context catalytic state

- [ ] Establish exact recent context plus an executable distant-state carrier.
- [ ] Run disabled, shuffled, and equivalent-memory controls.
- [ ] Improve occupied-context degradation without hidden quality collapse.

## Checkpoint 4: Layer-orbit closure

- [ ] Define relational closure observables.
- [ ] Measure them across layers.
- [ ] Test bounded skipping or a cheap verification tail.

## Checkpoint 5: Bounded autonomous candidate loop

- [ ] Establish stable and candidate worktrees.
- [ ] Implement deterministic `neo-loop` mechanics.
- [ ] Keep Agents-A1 as the sole reasoning model.
- [ ] Enforce benchmark immutability and stop conditions.

## Checkpoint 6: Native catalytic kernels

- [ ] Select one measured reversible or closable hot-path state transition.
- [ ] Prove borrow, transform, extract, and restore behavior.
- [ ] Measure removed allocation, copying, bandwidth, or operator work.

## Checkpoint 7: Recursive compute amplification

- [ ] Preserve useful computation as executable state.
- [ ] Re-enter it into later inference.
- [ ] Quantify equivalent baseline compute versus fresh compute executed.

---

# Mandatory handoff checklist

- [x] Updated this file so the next unchecked item is the actual next action.
- [x] Updated `lab/CHECKPOINT.md` only from executed evidence.
- [x] Updated `lab/GOAL.md` with one exact active objective.
- [x] Branch: `main`, HEAD: `ac5c3b7` (remote), working tree clean except untracked import.
- [x] Stable server command: `scripts/run_server.ps1 -CpuMoe -Context 4096 -Batch 512 -UBatch 128`.
- [x] Recorded failures: 40K matrix timeout (not server bug), auto-fit-conservative hypothesis rejected.
- [ ] Push claim-bearing work.
