# Checkpoint Ledger

## Checkpoint 0: Baseline parity

**Status:** IN PROGRESS

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
- Neo3000 commit: `09c14b9`
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
- [ ] 65,536-token configuration attempted (4096 tested so far)
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
- [ ] At least one tool call parses correctly
- [ ] Cancellation leaves the server usable
- [x] Repeated turns preserve the session correctly (confirmed)

Pi configuration:
- Provider: `neo3000`
- Base URL: `http://127.0.0.1:9292/v1`
- API: openai-completions
- Model: `agents-a1`
- Context window: 65536
- Existing `lmstudio` provider preserved

### Baseline measurements

- [ ] LM Studio configuration frozen
- [ ] Neo3000 configuration frozen
- [x] 2K context measured (smoke, approximate)
- [ ] 8K context measured
- [ ] 16K context measured
- [ ] 32K context measured
- [ ] 40K context measured
- [ ] Maximum stable context measured
- [x] RAM and VRAM peaks recorded
- [ ] Context degradation ratio calculated

Initial smoke baseline (4096 ctx, gpu-layers=auto, cpu-moe, fa=auto, f16 KV cache):

| Metric | Value |
|--------|-------|
| Server startup | ~20 sec |
| Model load | ~19 sec |
| Prompt processing | ~45 tps (14-20 token prompts) |
| Decode speed | ~8.2 tps (235 tokens) |
| VRAM | 11,653 MiB / 12,288 MiB |
| GPU layers | auto (near-full VRAM) |
| NEO3000 ONLINE response | confirmed |
| Streaming SSE | confirmed (67 chunks, [DONE]) |
| Second request | confirmed |
| Reasoning output | confirmed in `reasoning_content` |

Stable server configuration:
```
--host 127.0.0.1 --port 9292
--alias agents-a1
--ctx-size 4096
--threads 12 --threads-batch 12
--batch-size 512 --ubatch-size 128
--gpu-layers auto --fit on --fit-target 1024
--flash-attn auto
--cache-type-k f16 --cache-type-v f16
--cache-prompt --metrics --no-webui
--reasoning auto --cpu-moe
```

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

No catalytic inference claim is allowed.

## Next checkpoint

Checkpoint 1 will map the real compute path with low-overhead instrumentation that can be disabled completely in release operation.
