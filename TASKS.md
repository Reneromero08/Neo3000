# Neo3000 Task Board

**Active checkpoint:** 0, baseline parity and context characterization  
**Current state:** local baseline work was reported complete at 4K, but the reported local commit is not yet visible on GitHub  
**Claim ceiling:** `NEO3000_FOUNDATION_INITIALIZED`  
**Next exact boundary:** reconcile the local baseline commit with `origin/main`, rebuild, push it, then finish Pi and context verification

This is the operational queue. `ROADMAP.md` explains the architecture and phase order. This file says what to do next.

## Status law

- `[x]` means the result is present in the repository or supported by pushed evidence.
- `[ ]` means incomplete, unverified, or only reported from an unpushed local state.
- A task reported by an agent remains unchecked until its evidence is pushed and inspected.
- Work from top to bottom unless a task is explicitly blocked.
- Do not begin a later checkpoint while an earlier exit gate remains open.

---

# Current execution queue

## 0A. Reconcile the local baseline work with GitHub

The local agent reported commit `4ab05fa`, but GitHub could not resolve that commit. The remote also advanced while the local build was being completed.

- [ ] Run `git status --short` and preserve all local modifications.
- [ ] Run `git show --stat --oneline 4ab05fa` and confirm whether the reported commit exists locally.
- [ ] Run `git fetch origin`.
- [ ] Run `git log --oneline --left-right --graph HEAD...origin/main`.
- [ ] Rebase the local baseline commit onto current `origin/main`.
- [ ] Resolve `scripts/build_cuda.ps1` without losing either the local syntax fix or remote CUDA discovery support.
- [ ] Run `git diff --check`.
- [ ] Rebuild with `powershell -ExecutionPolicy Bypass -File scripts/build_cuda.ps1 -Clean`.
- [ ] Confirm `llama-server.exe --list-devices` reports the RTX 3060 CUDA device.
- [ ] Push the synchronized commit to `origin/main`.
- [ ] Record the resulting full commit SHA in `lab/CHECKPOINT.md`.
- [ ] Confirm the pushed commit can be fetched from GitHub.

### Reported local evidence to preserve during reconciliation

These results were reported by the local agent but remain unchecked until pushed and audited:

- [ ] CUDA Toolkit root: `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6`.
- [ ] `nvcc` 12.6, V12.6.85.
- [ ] Visual Studio 2022 and MSVC 19.44 CUDA build succeeds.
- [ ] `build/stable/bin/Release/llama-server.exe` exists.
- [ ] `build/stable/bin/Release/llama-bench.exe` exists.
- [ ] RTX 3060 is visible as CUDA device 0.
- [ ] Agents-A1 model identity and complete SHA-256 are recorded.
- [ ] 4K server starts with CPU MoE and F16 KV.
- [ ] 4K smoke performance is approximately 8.2 decode tokens/sec and 45 prompt tokens/sec.

## 0B. Close the 4K daily-driver gates

Preserve the working 4K server as the fallback configuration while testing everything else.

Reported working configuration:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_server.ps1 `
  -Context 4096 `
  -CpuMoe
```

- [ ] Launch the synchronized 4K stable server.
- [ ] Confirm `GET /health` returns HTTP 200.
- [ ] Confirm `GET /v1/models` contains `agents-a1`.
- [ ] Run `python scripts/baseline_harness.py`.
- [ ] Confirm normal output streams through multiple SSE events.
- [ ] Confirm `reasoning_content` remains distinct from final content.
- [ ] Confirm authoritative server prompt and decode timings are present.
- [ ] Run `python scripts/baseline_harness.py --tool-test --output lab/tool-test.local.json`.
- [ ] Confirm the emitted tool name is correct.
- [ ] Confirm tool arguments parse as valid JSON.
- [ ] Start Pi with provider `neo3000` selected.
- [ ] Send `Reply with exactly: NEO3000 PI ONLINE` through Pi.
- [ ] Confirm the request appears in the Neo3000 server log.
- [ ] Confirm LM Studio does not receive the request.
- [ ] Execute one harmless Pi tool call from model request through tool result and continued model response.
- [ ] Cancel one long Pi generation while it is streaming.
- [ ] Immediately send `Reply with exactly: NEO3000 RECOVERED`.
- [ ] Confirm cancellation does not corrupt the next request or slot state.
- [ ] Complete at least three repeated Pi turns without restarting the server.
- [ ] Freeze the exact 4K server arguments in `lab/CHECKPOINT.md` without committing the absolute model path.

## 0C. Characterize context scaling

Change one runtime variable at a time. Stop the previous server cleanly before each new context allocation.

### 8K

- [ ] Launch 8K with CPU MoE and F16 KV.
- [ ] Record whether auto-fit changes GPU placement.
- [ ] Record VRAM, RAM, prompt TPS, decode TPS, TTFT, and cached prompt tokens.
- [ ] Run the normal harness.
- [ ] Verify one Pi response and one tool call.
- [ ] If F16 KV fails or displaces too much compute, test Q8 KV as a separate configuration.
- [ ] Select and record the best stable 8K configuration.

### 16K

- [ ] Launch 16K using the best 8K configuration.
- [ ] Record allocation, placement, VRAM, RAM, prompt TPS, decode TPS, and TTFT.
- [ ] Verify normal Pi response and tool parsing.
- [ ] Select and record the best stable 16K configuration.

### 32K

- [ ] Launch 32K using the best prior configuration.
- [ ] Record allocation, placement, VRAM, RAM, prompt TPS, decode TPS, and TTFT.
- [ ] Verify normal Pi response and tool parsing.
- [ ] Select and record the best stable 32K configuration.

### 40K

- [ ] Launch 40K using the best prior configuration.
- [ ] Reproduce or reject the reported LM Studio slowdown toward approximately 3 tokens/sec.
- [ ] Record allocation, placement, VRAM, RAM, prompt TPS, decode TPS, and TTFT.
- [ ] Verify normal Pi response and tool parsing.
- [ ] Select and record the best stable 40K configuration.

### 65,536 attempt

- [ ] Attempt a 65,536-token server allocation.
- [ ] Record whether failure occurs during load, context allocation, prompt processing, or generation.
- [ ] Record last successful GPU placement, VRAM, RAM, and paging behavior.
- [ ] If it succeeds, verify normal Pi response and tool parsing.
- [ ] Record the maximum stable context.

## 0D. Run reproducible context matrices

Run only targets that fit inside the server context currently allocated.

- [ ] Run a bounded matrix at 8K.
- [ ] Run a bounded matrix at 16K.
- [ ] Run a matrix through 40K or the maximum stable context.
- [ ] Preserve all three counted repetitions for every point.
- [ ] Confirm prompt-cache reuse is disabled for uncached comparison runs.
- [ ] Record medians, not best runs.
- [ ] Calculate the context degradation ratio relative to the 2K point.
- [ ] Separate prompt-processing degradation from token-decode degradation.
- [ ] Record whether GPU displacement changes at the same point as the speed decline.

## 0E. Compare Neo3000 with LM Studio

Use the exact same GGUF and matched settings wherever both runtimes expose them.

- [ ] Freeze the LM Studio model, context, sampler, reasoning, KV, and placement configuration.
- [ ] Compare 4K using at least three counted repetitions.
- [ ] Compare 8K using at least three counted repetitions.
- [ ] Compare the largest mutually stable context using at least three counted repetitions.
- [ ] Record prompt TPS, decode TPS, TTFT, VRAM, RAM, and cached or warm state.
- [ ] State whether Neo3000 matches, exceeds, or trails LM Studio at each point.
- [ ] Do not infer a mechanism from wall-clock speed alone.

## 0F. Close Checkpoint 0

- [ ] Update every proven checkbox in `lab/CHECKPOINT.md`.
- [ ] Replace the stale boundary in `lab/GOAL.md` with the next exact compute-mapping goal.
- [ ] Append one compact final Checkpoint 0 record to `lab/results.jsonl`.
- [ ] Inventory which imported source paths are tracked and which remain generated.
- [ ] Choose a source-custody model before autonomous code modification begins.
- [ ] Identify the top one or two likely causes of long-context degradation from evidence.
- [ ] Confirm the stable 4K daily-driver command still works after all tests.
- [ ] Commit the completed evidence as one meaningful architectural chunk.
- [ ] Push the commit and record its full SHA here.
- [ ] Change the claim ceiling to `NEO3000_BASELINE_OPERATIONAL` only after the exit gate is met.

### Checkpoint 0 exit gate

- [ ] Agents-A1 runs through Pi on Neo3000.
- [ ] Streaming reasoning and final content are stable.
- [ ] A real Pi tool round trip succeeds.
- [ ] Cancellation followed by immediate recovery succeeds.
- [ ] Repeated turns remain stable.
- [ ] Context scaling is measured through the maximum stable point.
- [ ] Neo3000 and LM Studio are reproducibly compared.
- [ ] The next instrumentation target is selected from measured evidence.

---

# Checkpoint 1 queue: Compute map

Do not begin until every Checkpoint 0 exit-gate item above is checked or explicitly marked blocked with evidence.

- [ ] Create an isolated instrumentation branch or worktree.
- [ ] Define one fixed trace schema.
- [ ] Add a trace-disabled release configuration.
- [ ] Add a trace-enabled diagnostic configuration.
- [ ] Measure per-token and per-layer time.
- [ ] Separate attention-block time from Gated Delta Net recurrent-block time.
- [ ] Record active MoE expert IDs per layer and token.
- [ ] Measure expert transfer and residency behavior.
- [ ] Measure CPU-MoE execution time and bandwidth.
- [ ] Measure CPU to GPU transfers and synchronization.
- [ ] Measure KV allocation and traffic by context.
- [ ] Measure recurrent-state allocation and traffic by context.
- [ ] Measure GPU displacement caused by context growth.
- [ ] Measure prompt-cache hits and reused tokens.
- [ ] Run the frozen context matrix with tracing disabled.
- [ ] Run diagnostic points with tracing enabled.
- [ ] Quantify tracing overhead.
- [ ] Identify the top one or two causal bottlenecks.
- [ ] Update `lab/GOAL.md` with one selected catalytic mechanism.
- [ ] Update `lab/CHECKPOINT.md` and `lab/results.jsonl`.

### Checkpoint 1 exit gate

- [ ] The dominant short-context compute cost is causally localized.
- [ ] The dominant long-context degradation source is causally localized.
- [ ] The selected first intervention names its carrier, transformation, output, and closure law.
- [ ] Release performance remains unchanged when tracing is disabled.

---

# Checkpoint 2 queue: First catalytic intervention

Select only one family after Checkpoint 1 evidence exists.

- [ ] Declare the exact expensive operation.
- [ ] Declare the borrowed or reusable carrier.
- [ ] Declare the transformation.
- [ ] Declare the extracted output or invariant.
- [ ] Declare the restoration or closure law.
- [ ] Declare the expected speed mechanism.
- [ ] Declare quality and stability gates.
- [ ] Declare the measurement that rejects the hypothesis.
- [ ] Implement one bounded candidate intervention.
- [ ] Build stable and candidate separately.
- [ ] Run the frozen benchmark without changing it.
- [ ] Run Pi text, reasoning, tool, cancellation, and repeated-turn gates.
- [ ] Accept, reject, or mark the result inconclusive.
- [ ] Preserve the stable daily driver.
- [ ] Record the result in one compact experiment entry.

Possible mechanism families, chosen only from evidence:

- [ ] catalytic expert residency
- [ ] recurrent-state catalysis
- [ ] single-model catalytic speculation
- [ ] holographic long-context side channel
- [ ] layer-orbit closure

---

# Later checkpoint queue

## Checkpoint 3: Long-context catalytic state

- [ ] Establish exact recent context plus an experimental distant-state side channel.
- [ ] Compare full exact context against side-channel variants.
- [ ] Run shuffled and disabled side-channel controls.
- [ ] Improve context degradation ratio without violating quality gates.

## Checkpoint 4: Layer-orbit closure

- [ ] Define relational closure observables.
- [ ] Measure stability across layer checkpoints.
- [ ] Test cheap-tail verification or bounded layer skipping.
- [ ] Reject confidence-only closure claims.

## Checkpoint 5: Bounded autonomous candidate loop

- [ ] Establish stable and candidate worktrees.
- [ ] Implement deterministic `neo-loop` mechanics.
- [ ] Keep Agents-A1 as the sole reasoning model.
- [ ] Enforce benchmark immutability and stop conditions.
- [ ] Complete several candidate cycles without stable-server loss.
- [ ] Keep promotion manual until explicitly authorized.

## Checkpoint 6: Native catalytic kernels

- [ ] Select one measured hot-path state transition with an exact inverse or closure.
- [ ] Implement borrow, transform, extract, and restore semantics.
- [ ] Prove restoration or closure.
- [ ] Measure allocation, copying, bandwidth, and operator reduction.

## Checkpoint 7: Recursive compute amplification

- [ ] Preserve useful computational structure as executable state.
- [ ] Re-enter that state into later inference.
- [ ] Quantify equivalent baseline compute versus fresh compute executed.
- [ ] Demonstrate repeated amplification without hidden quality collapse.

---

# Mandatory handoff checklist

Before any agent stops:

- [ ] Update this file so the next unchecked item is the actual next task.
- [ ] Update `lab/CHECKPOINT.md` only from executed evidence.
- [ ] Update `lab/GOAL.md` with one exact active objective.
- [ ] Append to `lab/results.jsonl` only if an experiment actually ran.
- [ ] Record current branch and full HEAD SHA.
- [ ] Record whether the working tree is clean.
- [ ] Record the stable server command.
- [ ] Record the last command executed and its result.
- [ ] Record failures and inconclusive mechanisms.
- [ ] Record the next exact command.
- [ ] Push claim-bearing work or state clearly that it remains local.

A handoff is incomplete when the narrative report and tracked task board disagree.
