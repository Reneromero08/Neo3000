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
4. Expose the OpenAI-compatible streaming endpoint.
5. Connect Pi.
6. Record short-context and long-context performance.

No catalytic feature should enter the hot path until this checkpoint is closed.

## Bootstrap

```powershell
python scripts/import_upstream.py
powershell -ExecutionPolicy Bypass -File scripts/build_cuda.ps1
$env:NEO3000_MODEL = "D:\path\to\Agents-A1.gguf"
powershell -ExecutionPolicy Bypass -File scripts/run_server.ps1
```

The server endpoint defaults to `http://127.0.0.1:9292/v1`.

## Repository map

- `NEO3000.md`: architecture and research direction
- `AGENTS.md`: operating law for Agents-A1 and other coding agents
- `lab/GOAL.md`: the active objective
- `lab/CHECKPOINT.md`: acceptance gates and current boundary
- `upstream/`: pinned source identity and import manifest
- `scripts/`: reproducible import, build, and launch commands

The imported runtime source is intentionally absent from the initial commit. `scripts/import_upstream.py` materializes it from the exact pinned commit.