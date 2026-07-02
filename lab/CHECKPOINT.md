# Checkpoint Ledger

## Checkpoint 0: Baseline parity

**Status:** OPEN

**Purpose:** Establish a correct, reproducible, Pi-connected Agents-A1 runtime before changing inference semantics.

### Source identity

- [x] Upstream repository selected: `ggml-org/llama.cpp`
- [x] Upstream commit pinned in `upstream/LLAMA_CPP_COMMIT`
- [x] Import manifest declared
- [ ] Pinned source imported on the target machine
- [ ] Upstream license preserved
- [ ] Imported tree matches the manifest

### Build

- [ ] CMake configure succeeds
- [ ] CUDA backend builds
- [ ] `llama-server` builds
- [ ] `llama-bench` builds
- [ ] Stable build location is recorded
- [ ] Build commit and compiler versions are recorded

### Model

- [ ] Exact Agents-A1 GGUF identified
- [ ] Model SHA-256 recorded
- [ ] Quantization recorded
- [ ] Architecture metadata recorded
- [ ] 65,536-token configuration attempted
- [ ] Model loads without silent fallback

### Pi runtime

- [ ] OpenAI-compatible endpoint available at `127.0.0.1:9292`
- [ ] Pi can list the model
- [ ] Pi receives streamed text
- [ ] Reasoning content is preserved as supported by the backend
- [ ] At least one tool call parses correctly
- [ ] Cancellation leaves the server usable
- [ ] Repeated turns preserve the session correctly

### Baseline measurements

- [ ] LM Studio configuration frozen
- [ ] Neo3000 configuration frozen
- [ ] 2K context measured
- [ ] 8K context measured
- [ ] 16K context measured
- [ ] 32K context measured
- [ ] 40K context measured
- [ ] Maximum stable context measured
- [ ] RAM and VRAM peaks recorded
- [ ] Context degradation ratio calculated

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