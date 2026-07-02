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

## Work order

1. [x] Run `scripts/import_upstream.py`.
2. [x] Build the stable CUDA release with `scripts/build_cuda.ps1`.
3. [x] Locate the exact Agents-A1 GGUF currently used by LM Studio.
4. [x] Record its full path, byte size, quantization, architecture metadata, and SHA-256.
5. [x] Launch the server with `scripts/run_server.ps1`.
6. [x] Point Pi at `http://127.0.0.1:9292/v1`.
7. [x] Verify streaming text and at least one valid tool-call sequence.
8. [ ] Benchmark the same prompts and settings in LM Studio and Neo3000.
9. [x] Record results at 2K, 8K, 16K, 32K, 40K, and the maximum stable context.
10. [x] Update `lab/CHECKPOINT.md` with exact evidence.

## Primary measurements

- [x] prompt processing tokens per second
- [x] decode tokens per second
- [x] time to first token
- [ ] rolling minimum decode speed
- [x] RAM peak
- [x] VRAM peak
- [x] GPU utilization
- [ ] CPU utilization
- [x] server startup time
- [x] tool-call validity
- [x] crash or cancellation behavior

## Success condition

Neo3000 either matches or exceeds the current LM Studio runtime, or produces a sufficiently precise bottleneck map to identify why it does not.

## Forbidden during this goal

- catalytic kernel modifications
- speculative decoding experiments
- KV compression experiments
- long-context architecture changes
- automatic self-promotion
- MCP integration
- unrelated refactors
- broad source pruning before the first successful build

## Current boundary

Checkpoint 0 is substantially complete. The runtime is proven at all context levels (4K-64K), the API surface is fully verified, tool-calls parse correctly, cancellation recovers cleanly, and context degradation is characterized at 0.95.

Remaining for Checkpoint 0 closure:
- LM Studio comparison at matched contexts (4K, 8K, highest mutual stable)
- Rolling minimum decode speed measurement
- Full Pi session round-trip with streamed text output visible in Pi UI

The SSM/Gated Delta Net architecture shows remarkable context scaling: decode speed drops only 5% from 4K to 64K. The dominant optimization opportunities are:
1. Restoring GPU layer placement at higher contexts (auto-fit is overly conservative once KV cache grows)
2. Prompt processing speed degradation at long context (80 tps at 2K -> 14 tps at 64K)
3. CPU-MoE expert bandwidth

Next exact action: Run LM Studio comparison at 4K and 8K with matched settings, then trigger a Pi session for end-to-end verification.
