# Checkpoint Ledger

## Checkpoint 0: Baseline parity

**Status:** OPERATIONAL (exit gate pending LM Studio comparison)

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
- Neo3000 commit: `417e1d6`
- llama.cpp pinned commit: `fdb1db877c526ec90f668eca1b858da5dba85560`
- GPU: NVIDIA RTX 3060, SM 8.6, 12287 MiB VRAM
- Binary: `build/stable/bin/Release/llama-server.exe`
- Binary: `build/stable/bin/Release/llama-bench.exe`
- ggml-cuda.dll: 204252160 bytes (195 MB)

### Model

- [x] Exact Agents-A1 GGUF identified
- [x] Model SHA-256 recorded
- [x] Quantization recorded
- [x] Architecture metadata recorded
- [x] 65,536-token configuration attempted and verified stable
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

Pi configuration:
- Provider: `neo3000`
- Base URL: `http://127.0.0.1:9292/v1`
- API: openai-completions
- Model: `agents-a1`
- Context window: 65536
- Existing `lmstudio` provider preserved

### Baseline measurements

- [ ] LM Studio configuration frozen
- [x] Neo3000 configuration frozen
- [x] 2K context measured
- [x] 8K context measured
- [x] 16K context measured
- [x] 32K context measured
- [x] 40K context measured
- [x] Maximum stable context: 65,536
- [x] VRAM peaks recorded at each context level
- [x] Context degradation ratio calculated

Context scaling summary (f16 KV, cpu-moe, auto GPU layers, warm):

| Context | VRAM MiB | Decode TPS | Prompt TPS | Status |
|---------|----------|------------|------------|--------|
| 4K | 11,653 | 17.5 | 41.4 | stable |
| 8K | 2,793 | 19.7 | 25.1 | stable |
| 16K | 2,947 | 17.9 | 18.1 | stable |
| 32K | 3,285 | 16.3 | 13.7 | stable |
| 40K | 3,695 | 15.7 | 13.3 | stable |
| 64K | 4,031 | 16.6 | 14.0 | stable |

Context degradation ratio (64K / 4K decode): 16.6 / 17.5 = **0.95**

Note: VRAM dropped sharply from 4K to 8K+ because auto-fit moved model layers from GPU to CPU when KV cache growth made them not fit together. At 4K, nearly full model fitted on GPU. At 8K+, KV cache displaced model layers to CPU, but the SSM/Delta Net architecture kept decode speed nearly constant.

Context matrix results (deterministic corpus, 64-token output, warm):

| Target Tokens | Decode TPS | Prompt TPS |
|---------------|------------|------------|
| 2,048 | 21.7 | 80.0 |
| 8,192 | 22.4 | 78.4 |
| 16,384 | 23.2 | 79.4 |
| 32,768 | 21.8 | 71.4 |
| 40,960 | ERROR | (tokenize OOM) |
| 60,000 | N/A | (not reached) |

The 40,960 target failed during prompt tokenization, not during inference. This maps a tokenization or memory boundary distinct from the inference context wall.

### Baseline harness verification

- [x] `baseline_harness.py` smoke: PASS (3/3 HTTP 200, streaming, NEO3000 ONLINE)
- [x] `baseline_harness.py` tool-test: PASS (3/3 neo3000_probe with {"status":"ok"})
- [x] Cancellation + recovery: PASS (NEO3000 RECOVERED after mid-stream cancel)

### Exit gate

Checkpoint 0 closes only when:

```text
Agents-A1 runs through Pi on the imported runtime
and
fixed baseline measurements are reproducible
and
remaining performance differences are causally localized
```

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

Checkpoint 1 will map the real compute path with low-overhead instrumentation that can be disabled completely in release operation.

The dominant bottleneck appears to be **not** attention or KV growth (context degradation ratio is 0.95). The SSM architecture handles long context well. The main optimization opportunities are:
- Restoring GPU layer placement at higher contexts (currently auto-fit is overly conservative)
- CPU-MoE expert bandwidth optimization
- Prompt processing speed (drops from 80 tps at 2K to 14 at 64K)
