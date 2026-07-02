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

1. Run `scripts/import_upstream.py`.
2. Build the stable CUDA release with `scripts/build_cuda.ps1`.
3. Locate the exact Agents-A1 GGUF currently used by LM Studio.
4. Record its full path, byte size, quantization, architecture metadata, and SHA-256 outside the repository or in a redacted local checkpoint artifact.
5. Launch the server with `scripts/run_server.ps1`.
6. Point Pi at `http://127.0.0.1:9292/v1`.
7. Verify streaming text and at least one valid tool-call sequence.
8. Benchmark the same prompts and settings in LM Studio and Neo3000.
9. Record results at 2K, 8K, 16K, 32K, 40K, and the maximum stable context.
10. Update `lab/CHECKPOINT.md` with exact evidence.

## Primary measurements

- prompt processing tokens per second
- decode tokens per second
- time to first token
- rolling minimum decode speed
- RAM peak
- VRAM peak
- GPU utilization
- CPU utilization
- server startup time
- tool-call validity
- crash or cancellation behavior

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

The imported source has been materialized and built. The CUDA-enabled server is running and accessible to Pi. The foundation endpoints (/health, /v1/models, /v1/chat/completions) are verified. Streaming works. Reasoning content is preserved. At 4K context, decode speed matches the LM Studio baseline (~8 tps).

Remaining before Checkpoint 0 closure:
- Pi request round-trip verification (Pi sends to Neo3000, receives stream)
- Tool-call parsing verification
- Cancellation behavior
- Full context scaling: 8K, 16K, 32K, 40K, max stable
- LM Studio comparison benchmarks at each context length
- Context degradation ratio calculation

Next exact action: Run a Pi session targeting Neo3000, verify the round-trip, then scale context upward stepwise.