# Neo3000 Baseline Protocol

## Purpose

This protocol freezes the minimum runtime surface and measurement procedure required to close Checkpoint 0. It exists to prevent the benchmark from changing while the engine is being tuned.

The protocol is not a model-quality benchmark and does not authorize catalytic claims.

## Fixed identities

Every claim-bearing baseline record must identify:

- Neo3000 Git commit
- pinned llama.cpp commit
- exact model filename
- model byte size
- model SHA-256
- model architecture and quantization
- CUDA Toolkit root and `nvcc` version
- compiler and CMake versions
- GPU identity and driver version
- complete server launch arguments
- benchmark command

Absolute local paths may appear in ignored local artifacts, but must not enter tracked files.

## Runtime contract

The stable server must expose:

```text
http://127.0.0.1:9292/health
http://127.0.0.1:9292/v1/models
http://127.0.0.1:9292/v1/chat/completions
```

The model ID visible to clients must be:

```text
agents-a1
```

The runtime must preserve:

- incremental SSE streaming
- ordinary assistant content
- reasoning content when supported
- OpenAI-compatible tool calls
- cancellation without permanent slot corruption
- repeated requests without server restart

## Smoke verification

After the server is healthy, run from the repository root:

```powershell
python scripts/baseline_harness.py
```

This performs three streamed requests using the exact-response probe and writes:

```text
lab/results.local.json
```

Then run the tool-call probe:

```powershell
python scripts/baseline_harness.py --tool-test --output lab/tool-test.local.json
```

A smoke pass requires:

- HTTP 200 for health, model listing, and completion requests
- `agents-a1` present in `/v1/models`
- more than one SSE event per completion
- expected text emitted by the normal probe
- valid JSON arguments for the tool probe
- server still usable after all requests

A smoke pass proves protocol compatibility only. It does not prove speed parity.

## Measurement conditions

Neo3000 and LM Studio comparisons must use the same:

- GGUF bytes
- chat template
- context target
- prompt text
- requested output length
- sampler parameters
- reasoning mode
- CPU thread count where configurable
- GPU offload intent
- KV cache types
- warm or cold classification

Do not compare a cold first request from one runtime against a warm cached request from another.

## Repetition

For each measured point:

1. run one uncounted warmup unless cold-start behavior is the declared measurement
2. run at least three counted repetitions
3. report the median
4. retain individual run values in the ignored local result
5. record crashes, retries, and outliers rather than silently deleting them

No speed claim may rest on one run.

## Context matrix

Checkpoint 0 targets:

```text
2K
8K
16K
32K
40K
maximum stable context up to 64K
```

The full matrix begins only after the smoke verification passes.

For each context point record:

- actual prompt tokens reported by the runtime
- prompt-processing tokens per second
- time to first streamed event
- time to first content token
- decode tokens per second
- minimum rolling decode speed where available
- completion tokens
- RAM peak
- VRAM peak
- GPU utilization
- CPU utilization
- whether prompt state was reused
- whether the run was cold or warm

## Derived metrics

### Context degradation ratio

```text
long-context decode TPS / short-context decode TPS
```

The selected short and long context points must be named beside the value.

### Compute amplification

This metric remains reserved until Neo3000 removes or reuses an identified operator path:

```text
equivalent baseline compute / fresh compute executed
```

Do not estimate it from wall-clock speed alone.

## Output quality gates

Before accepting a runtime configuration:

- the exact-response probe must remain coherent
- the tool-call probe must remain valid
- no silent model substitution is allowed
- no unexplained truncation is allowed
- reasoning parsing must not swallow final content
- repeated requests must not cross-contaminate state

A faster configuration that fails one of these gates is rejected for daily-driver use.

## Checkpoint update law

`lab/CHECKPOINT.md` may be marked only from executed evidence.

Use these states:

- unchecked: not run
- checked: directly demonstrated
- blocked: attempted and prevented by a named dependency
- partial: some but not all declared conditions demonstrated

Do not check a parent gate because a related command succeeded.

## Current claim ceiling

Until the complete Checkpoint 0 exit gate closes:

```text
NEO3000_FOUNDATION_INITIALIZED
```

The next lawful claim is:

```text
NEO3000_BASELINE_OPERATIONAL
```

That claim requires a working Pi-connected runtime plus reproducible measurements.