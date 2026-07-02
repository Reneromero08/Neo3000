# Neo3000

Neo3000 is a performance-first local LLM inference engine built to make computation itself catalytic.

The immediate objective is simple: replace the current LM Studio path with a fast, inspectable, OpenAI-compatible runtime that serves Agents-A1 to Pi. Once baseline parity is established, Neo3000 will evolve inside its own repository through bounded self-improvement loops.

## Direction

```text
load Agents-A1 correctly
-> stream it to Pi
-> match or beat the current runtime
-> measure the real compute wall
-> borrow, transform, extract, and restore compute state
-> compound useful computation across tokens and sessions
```

Neo3000 starts from a pinned source import of the runtime portions of `llama.cpp`. It is not an AGS governance port, an MCP framework, or a general agent platform. Speed, compute efficiency, inference quality, and experimental clarity come first.

## Current checkpoint

Checkpoint 0 is baseline establishment:

1. Import the pinned upstream runtime.
2. Build CUDA release binaries on Windows.
3. Load the exact Agents-A1 GGUF.
4. expose the OpenAI-compatible streaming endpoint.
5. Connect Pi.
6. Record short-context and long-context performance.

See `NEO3000.md`, `AGENTS.md`, and `lab/CHECKPOINT.md` after the foundation scaffold is installed.
