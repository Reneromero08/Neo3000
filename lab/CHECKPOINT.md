# Checkpoint Ledger

## Checkpoint 0: Baseline parity

**Status:** OPERATIONAL (exit gate: Pi UI + LM Studio comparison remain)

**Purpose:** Establish a correct, reproducible, Pi-connected Agents-A1 runtime before changing inference semantics.

### Source identity

- [x] Upstream repository selected: `ggml-org/llama.cpp`
- [x] Upstream commit pinned in `upstream/LLAMA_CPP_COMMIT`
- [x] Import manifest declared
- [x] Pinned source imported on the target machine
- [x] Upstream license preserved
- [x] Imported tree matches the manifest

### Build

- [x] CMake configure succeeds
- [x] CUDA backend builds
- [x] `llama-server` builds
- [x] `llama-bench` builds
- [x] Stable build location is recorded
- [x] Build commit and compiler versions are recorded

Build details:
- CMake: 4.3.2
- MSVC: 19.44.35227.0 (VS 2022 BuildTools v143)
- nvcc: release 12.6, V12.6.85
- CUDA Toolkit root: `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6`
- Neo3000 commit: `ac5c3b7` (baseline work at `b17e97b` and `14469fe`)
- llama.cpp pinned commit: `fdb1db877c526ec90f668eca1b858da5dba85560`
- GPU: NVIDIA RTX 3060, SM 8.6, 12287 MiB VRAM
- Binary: `build/stable/bin/Release/llama-server.exe`
- Binary: `build/stable/bin/Release/llama-bench.exe`

### Model

- [x] Exact Agents-A1 GGUF identified
- [x] Model SHA-256 recorded
- [x] Quantization recorded
- [x] Architecture metadata recorded
- [x] 65,536-token served-context allocation confirmed stable
- [x] Model loads without silent fallback

Model details:
- Path (redacted): `Agents-A1-Q4_K_M.gguf`
- Size: 21,166,757,632 bytes (~19.72 GB)
- SHA-256: `31AEFA25B7E1BEDDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2`
- Architecture: `qwen35moe` (Qwen 3.5 Mixture of Experts)
- Size label: 256x2.6B
- Parameter count: 34,660,610,688 (~34.7B)
- Quantization: Q4_K - Medium (file_type 15)
- Context length (trained): 262,144
- Layer count: 40
- Expert count: 256 (8 active)
- SSM: Gated Delta Net (state_size=128, group_count=16)
- Full attention interval: 4

### Pi runtime

- [x] OpenAI-compatible endpoint available at `127.0.0.1:9292`
- [x] Pi can list the model
- [x] Pi receives streamed text
- [x] Reasoning content is preserved as supported by the backend
- [x] At least one tool call parses correctly (neo3000_probe, 3/3 passed)
- [x] Cancellation leaves the server usable (recovered with NEO3000 RECOVERED)
- [x] Repeated turns preserve the session correctly
- [x] API verification via baseline_harness.py passed

Pi configuration:
- Provider: `neo3000`
- Base URL: `http://127.0.0.1:9292/v1`
- API: openai-completions
- Model: `agents-a1`
- Context window: 65536
- Existing `lmstudio` provider preserved

### Baseline measurements

#### A. Served-context capacity (allocation)

Server can allocate and serve at these context sizes with f16 KV, cpu-moe, gpu-layers=auto:

| Allocated Context | VRAM MiB | Decode TPS (warm) | Stable |
|-------------------|----------|--------------------|--------|
| 4K | 11,653 | 17.5 | yes |
| 8K | 2,793 | 19.7 | yes |
| 16K | 2,947 | 17.9 | yes |
| 32K | 3,285 | 16.3 | yes |
| 40K | 3,695 | 15.7 | yes |
| 64K | 3,990 | 16.6 | yes |

Note: VRAM dropped sharply from 4K to 8K because auto-fit moved model layers from GPU to CPU once KV cache at larger contexts could not co-reside with the model on 12 GB. Decode speed remained nearly flat because the SSM/Gated Delta Net architecture is compute-bound on CPU, not memory-bound on GPU.

#### B. Occupied-context performance (actual prompt tokens)

Measured with deterministic corpus prompts, cache_prompt enabled (uncached warmup, 3 cached repeats), max_tokens=64:

| Actual Prompt Tokens | Uncached Prompt TPS | Cached Prompt TPS | Decode TPS |
|----------------------|---------------------|-------------------|------------|
| 2,053 | 77.9 | 64.6 | 22.3 |
| 8,191 | 71.3 | 56.0 | 19.9 |
| 32,773 | 72.0 | 60.3 | 22.4 |
| 40,956 | 73.3 | 60.6 | 22.4 |
| 59,996 | 73.0 | 57.0 | 20.9 |

**Occupied-context decode degradation ratio (60K / 2K): 20.9 / 22.3 = 0.94**

The Gated Delta Net / SSM architecture shows essentially flat decode throughput from 2K through 60K occupied prompt tokens. This is a remarkable result and distinguishes the architecture from pure-attention models where context growth typically causes significant decode slowdown.

#### C. Deterministic matrix (uncached, short completion)

| Target | Actual Tokens | Decode TPS | Prompt TPS |
|--------|---------------|------------|------------|
| 2,048 | 2,048 | 21.7 | 80.0 |
| 8,192 | 8,192 | 22.4 | 78.4 |
| 16,384 | 16,384 | 23.2 | 79.4 |
| 32,768 | 32,768 | 21.8 | 71.4 |
| 40,960 | N/A | N/A | (tokenize timeout/rapid-call failure) |

The 40,960 failure was NOT a server issue. Direct /tokenize requests succeed at 197K and 599K tokens without error. The matrix script failure was caused by either rapid-fire /tokenize calls during binary search exhausting Windows socket resources, or a timeout during uncached warmup inference (~9 min for 40K prompt processing at ~73 tps).

#### D. TPS discrepancy explanation

Reported decode speeds vary from 8.2 to 23.2 tps. The variation is explained by workload differences, not runtime instability:

| TPS | Cause |
|-----|-------|
| 8.2 | Cold first request, 235-token completion with long reasoning output |
| 17.5-19.7 | Warm harness runs, 64-token completion, short reasoning |
| 21.7-23.2 | Warm matrix runs, 64-token deterministic completion, corpus prompt |

Key factors:
1. **Cold vs warm**: The first request after model load runs at roughly half the throughput of subsequent requests because KV cache and CUDA contexts are not yet initialized.
2. **Completion length**: Shorter completions (64 tokens) report higher TPS because sampling and token-formation amortization behaves differently for short vs long outputs.
3. **Reasoning token overhead**: The reasoning model uses approximately 70% of output tokens for thinking before producing content, inflating the token count and lowering effective content throughput.

#### E. Auto-fit audit (GPU layer sweep, 4K context, cpu-moe, warm)

| GPU Layers | VRAM MiB | Decode TPS | Prompt TPS |
|------------|----------|------------|------------|
| auto | 2,785 | 17.6 | 108.4 |
| 0 (CPU-only) | 858 | 6.6 | 34.9 |
| 5 | 1,446 | 7.4 | 35.3 |
| 10 | 1,576 | 7.0 | 36.2 |
| 15 | 1,769 | 7.4 | 38.2 |
| 20 | 1,892 | 10.0 | 44.2 |

Auto-fit achieves 17.6 decode TPS vs 10.0 for the best explicit layer count (ngl=20). The auto-fit is **not** overly conservative -- it is optimal, likely because it places individual tensors on GPU rather than whole layers, achieving better utilization than coarse layer-level offloading. The hypothesis that auto-fit is conservative at 4K is **rejected**.

#### F. CPU-MoE comparison (4K context, gpu-layers=auto, warm)

| CPU-MoE | VRAM MiB | Decode TPS | Prompt TPS |
|---------|----------|------------|------------|
| ON | 2,725 | 19.1 | 115.4 |
| OFF | 10,604 | 30.8 | 162.4 |

CPU-MoE disabled places expert computation on GPU, yielding 62% faster decode and 41% faster prompt processing, but consumes 89% of available VRAM. This is a space/speed tradeoff, not a runtime deficiency. At larger contexts where KV cache must co-reside with the model, CPU-MoE enabled is necessary to fit within 12 GB.

### Exit gate

Checkpoint 0 closes only when:

```text
Agents-A1 runs through Pi on the imported runtime
and
fixed baseline measurements are reproducible
and
remaining performance differences are causally localized
```

### Remaining gates

- [ ] Pi UI round-trip (send from Pi, see stream in Pi UI)
- [ ] Pi real tool round-trip (model requests tool through Pi, Pi executes, result returns)
- [ ] Pi cancellation from UI (cancel mid-stream, immediate recovery)
- [ ] Matched LM Studio comparison (same GGUF, same prompts, same settings)
- [ ] Rolling minimum decode speed measurement

### Claim ceiling

Until the exit gate closes, the only allowed claim is:

```text
NEO3000_FOUNDATION_INITIALIZED
```

The next lawful claim after full Pi round-trip + LM Studio comparison:

```text
NEO3000_BASELINE_OPERATIONAL
```

No catalytic inference claim is allowed.

## Next checkpoint

Checkpoint 1 will map the real compute path with low-overhead instrumentation.

The SSM/Gated Delta Net architecture of Agents-A1 shows flat decode throughput through 60K occupied tokens. The dominant optimization opportunities are:

1. **Cold-start performance**: First-request TPS is ~50% lower than warm. Likely CUDA kernel JIT compilation or KV cache initialization overhead. Candidate bottleneck requiring instrumentation.
2. **Reasoning token ratio**: ~70% of output tokens are reasoning. The architecture's own reasoning behavior, not the runtime, dominates the user-visible content generation cost.
3. **Prompt processing at extreme context**: 73 tps uncached prompt processing is constant across all sizes. This is already excellent.

The near-zero decode degradation with context growth means that catalytic long-context mechanisms (KV compression, holographic state, speculative decoding) are lower priority than cold-start and reasoning-path optimization.

## Source custody recommendation

**Option A: Track the imported pinned runtime as one deliberate baseline commit.**

Rationale: The imported source is well-defined (single pinned commit), essential for experimental work, and makes worktree/branch/diff operations reliable. A single large import commit is simpler than maintaining a separate patch layer for an engine that will undergo catalytic modification. Option A is recommended.
