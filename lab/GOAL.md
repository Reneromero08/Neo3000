# Active Goal

## Checkpoint 0: Establish the Neo3000 baseline

Create a reproducible, directly Pi-compatible CUDA runtime for the exact Agents-A1 GGUF using the pinned `llama.cpp` source import.

## Required result

```text
Pi
-> OpenAI-compatible local endpoint
-> Neo3000 baseline server
-> Agents-A1 GGUF
-> streamed text, reasoning, and tool calls
```

## Completed work

- [x] CUDA build with MSVC 19.44, nvcc 12.6, SM 8.6
- [x] Model SHA-256 recorded: `31AEFA25B7...77C2`
- [x] API verified: health, models, streaming, non-streaming, reasoning, tool calls
- [x] Cancellation recovery: PASS (NEO3000 RECOVERED)
- [x] Context allocation stable through 64K
- [x] Occupied-context decode flat through 60K (degradation ratio 0.94)
- [x] Auto-fit audit: optimal at 4K (17.6 tps vs best explicit 10.0 tps)
- [x] CPU-MoE audit: 62% decode gain disabled, but cost is 89% VRAM
- [x] Baseline protocol and matrix runner exist
- [x] Pi configuration: neo3000 provider, model agents-a1
- [x] Source custody recommendation: Option A (track imported runtime)

## Remaining gates

- [ ] Pi UI round-trip (requires user action: launch Pi, send prompt, observe stream)
- [ ] Pi tool round-trip (requires user action: Pi executes tool, returns result)
- [ ] Pi cancellation from UI (requires user action: cancel mid-stream)
- [ ] LM Studio matched comparison (requires LM Studio running with same GGUF)

## Current boundary

The runtime is proven correct and performant. Auto-fit is not overly conservative -- it is optimal. The SSM architecture shows essentially zero decode degradation from 2K to 60K occupied tokens. CPU-MoE is a deliberate space/speed tradeoff, not a bug.

The remaining Checkpoint 0 gates require either Pi user interaction or LM Studio availability. All automated API-level verification is complete.

## Next exact action

1. User launches Pi, selects neo3000 provider, sends a prompt, confirms stream appears in Pi UI
2. User tests a Pi tool round-trip
3. User tests Pi cancellation
4. User runs LM Studio comparison at 4K and 8K with same GGUF

After Pi evidence exists: close Checkpoint 0, begin Checkpoint 1 instrumentation targeting cold-start performance and reasoning token overhead.
