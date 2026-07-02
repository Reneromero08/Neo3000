# Neo3000 Task Board

**Active checkpoint:** 0, baseline parity and context characterization  
**Remote HEAD audited:** `120ae2af23a4a8b396ab5251174228835054de0c`  
**Claim ceiling:** `NEO3000_FOUNDATION_INITIALIZED`  
**Next exact boundary:** prove occupied-context behavior beyond 32K, complete the Pi UI and LM Studio comparisons, then close Checkpoint 0

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
- [x] Deterministic occupied-context measurements succeed at 2,048, 8,192, 16,384, and 32,768 raw content tokens.
- [x] The deterministic matrix shows approximately flat decode throughput through 32,768 occupied tokens.
- [x] Imported source remains reproducible from the pinned upstream commit.

## Important evidence boundary

The following statement is **not yet proven**:

```text
decode speed drops only 5 percent from 4K occupied context to 64K occupied context
```

The reported 64K row proves that a server configured for 65,536 tokens can load and answer a short request. The deterministic prompt-filled matrix reached 32,768 tokens and then failed during tokenization at 40,960. Keep allocation capacity and occupied-context performance separate in every report.

The current supported long-context statement is:

```text
Agents-A1 allocates a 65,536-token context successfully, and measured decode throughput remains approximately flat through 32,768 occupied raw content tokens.
```

---

# Current execution queue

## 0A. Verify the actual Pi user path

- [ ] Launch Pi normally with provider `neo3000` selected.
- [ ] Send `Reply with exactly: NEO3000 PI ONLINE` from the Pi UI.
- [ ] Confirm streamed text is visible incrementally in Pi.
- [ ] Confirm the request appears in the Neo3000 server log.
- [ ] Confirm LM Studio does not receive the request.
- [ ] Execute one harmless real Pi tool round trip.
- [ ] Confirm Pi executes the tool, returns its result, and Agents-A1 continues.
- [ ] Cancel a long generation from Pi and immediately verify `NEO3000 RECOVERED`.
- [ ] Record the exact Pi command, tool, and visible result in `lab/CHECKPOINT.md`.

## 0B. Reproduce and localize the 40,960-token failure

Do not label this an inference wall until the failing layer is known.

- [ ] Re-run only the 40,960 target and capture the exact client exception.
- [ ] Capture the server log from immediately before the failure through process exit or recovery.
- [ ] Record whether the server process exits, returns HTTP error, closes the connection, or remains healthy.
- [ ] Record system RAM, commit charge, page-file use, and VRAM at failure.
- [ ] Test direct `/tokenize` requests at 34K, 36K, 38K, 40K, and 40,960 target sizes.
- [ ] Determine whether failure depends on request body size, returned token-array size, repeated binary-search calls, or model context state.
- [ ] Confirm `/health` immediately after each failed request.
- [ ] If the server tokenizer is the problem, build or use a local tokenizer path and keep inference measurement separate from token-count construction.
- [ ] Repair `scripts/context_matrix.py` only if the harness itself causes the failure.
- [ ] Add a regression test that reproduces the previous failure without running the full matrix.

## 0C. Measure genuinely occupied long context

- [ ] Produce a prompt whose actual chat-completion usage reports approximately 40,000 prompt tokens.
- [ ] Run one warmup and at least three counted 40K occupied-context completions.
- [ ] Produce a prompt whose actual usage reports approximately 60,000 prompt tokens.
- [ ] Run one warmup and at least three counted 60K occupied-context completions.
- [ ] Record actual prompt tokens, cached tokens, prompt TPS, decode TPS, TTFT, total time, RAM, VRAM, and server placement.
- [ ] Calculate occupied-context degradation ratios relative to the same 2K workload.
- [ ] Keep allocation-only results in a separate table.
- [ ] Measure rolling minimum decode speed for the 2K, 32K, 40K, and 60K runs.

## 0D. Audit placement before blaming auto-fit

The current evidence shows a large VRAM difference between the 4K and 8K server configurations, but does not yet prove that restoring GPU placement improves performance.

- [ ] Capture the exact `offloaded X/Y layers` or equivalent placement log at each tested context.
- [ ] Record which tensors or model components remain on GPU.
- [ ] Confirm whether the reported VRAM figures were sampled at equivalent points in server lifetime.
- [ ] At one fixed occupied context, compare `gpu-layers=auto` against at least two explicit placement levels that fit safely.
- [ ] Keep CPU-MoE, KV type, prompt, output length, and cache state fixed.
- [ ] Record prompt TPS, decode TPS, PCIe activity where available, RAM, and VRAM.
- [ ] Reject the claim that auto-fit is overly conservative if more GPU placement does not improve the declared metric.

## 0E. Audit CPU-MoE before selecting it as the wall

- [ ] At one fixed context and placement, compare CPU-MoE enabled and disabled when both configurations fit.
- [ ] If full comparison cannot fit, test bounded `n-cpu-moe` placements where supported.
- [ ] Record decode TPS, prompt TPS, CPU utilization, memory bandwidth indicators, PCIe activity, RAM, and VRAM.
- [ ] Distinguish expert compute time from expert-transfer time.
- [ ] Do not select catalytic expert residency until repeated expert movement is measured.

## 0F. Matched LM Studio comparison

- [ ] Freeze the exact GGUF bytes in both runtimes.
- [ ] Match prompt text, actual prompt-token count, output length, sampler, reasoning mode, KV type, and warm or cold state.
- [ ] Compare 4K occupied context with at least three counted runs.
- [ ] Compare 8K occupied context with at least three counted runs.
- [ ] Compare the largest mutually stable occupied context with at least three counted runs.
- [ ] Record prompt TPS, decode TPS, TTFT, rolling minimum decode speed, RAM, and VRAM.
- [ ] Explain the earlier 8.2 TPS versus later 17.5 to 23 TPS measurements by identifying the workload or timing difference.
- [ ] State whether Neo3000 matches, exceeds, or trails LM Studio for each matched workload.

## 0G. Correct the repository evidence and close Checkpoint 0

- [ ] Update `lab/CHECKPOINT.md` to separate allocated context from occupied context.
- [ ] Remove or qualify the unsupported 64K over 4K occupied-context ratio.
- [ ] Mark the Pi UI round trip only after it is visibly demonstrated.
- [ ] Update `lab/GOAL.md` so the next action matches this task board.
- [ ] Append one compact correction or closure record to `lab/results.jsonl`.
- [ ] Choose the imported-source custody model.
- [ ] Confirm the stable daily-driver command still works.
- [ ] Commit and push one meaningful Checkpoint 0 closure chunk.
- [ ] Record the full pushed SHA here.
- [ ] Change the claim ceiling to `NEO3000_BASELINE_OPERATIONAL` only after every exit gate below is met.

### Checkpoint 0 exit gate

- [ ] A real Pi UI text stream succeeds.
- [ ] A real Pi tool round trip succeeds.
- [ ] Pi cancellation and immediate recovery succeed.
- [ ] Occupied-context behavior is measured through the maximum stable target, or a precise blocker is mapped.
- [ ] Neo3000 and LM Studio are reproducibly compared under matched workloads.
- [ ] Rolling minimum decode speed is recorded.
- [ ] Allocation capacity and occupied-context performance are documented separately.
- [ ] The next instrumentation target is selected from causal evidence rather than inference.

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

Before any agent stops:

- [ ] Update this file so the next unchecked item is the actual next action.
- [ ] Update `lab/CHECKPOINT.md` only from executed evidence.
- [ ] Update `lab/GOAL.md` with one exact active objective.
- [ ] Record branch, full HEAD SHA, and working-tree status.
- [ ] Record stable server command and last executed command.
- [ ] Record exact failures and inconclusive claims.
- [ ] Push claim-bearing work or state clearly that it remains local.

A narrative report does not complete a handoff when this task board remains stale.
