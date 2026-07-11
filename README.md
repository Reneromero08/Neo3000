# Neo3000

Neo3000 is a performance-first local LLM inference engine built to make computation itself catalytic.

The immediate objective is simple: replace the current LM Studio path with a fast, inspectable, OpenAI-compatible runtime that serves Agents-A1 to Pi. Once baseline parity is established, Neo3000 will evolve inside its own repository through bounded self-improvement loops.

## Start here

Agents and contributors should read:

```text
AGENTS.md
TASKS.md
ROADMAP.md
lab/GOAL.md
lab/CHECKPOINT.md
```

`TASKS.md` is the executable queue. `ROADMAP.md` explains the longer architecture and checkpoint sequence.

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

## Current protected boundary

Checkpoint 0 and the supervised RSI substrate are closed. Checkpoint 1A tracing is paused, and Checkpoint 2 is active. CatalyticSwarm-0 v2 proved the bounded 32-worker, one-slot control plane at `reviewable-accept`; it did not prove task advantage.

CatalyticSwarm-1 is **REPAIRED / INTEGRATED / NOT EXECUTED**. The safety-repaired runner preserves the frozen eight-task suite and equal-budget four-arm comparison while adding per-request repository custody, host/resource enforcement, per-task parity stops, guarded cleanup transfer, and terminal boundary-count reconciliation.

```text
prior live authorization: UNCONSUMED BUT SUPERSEDED BY NEW MAIN IDENTITY
live model requests: 0
sidecar launches: 0
one-shot artifacts: absent
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN: LOCKED
SOTA_SWARM_CLAIM: LOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
automatic promotion: disabled
```

Do not invoke `audit-catalytic-swarm-1` without new separate explicit authorization bound to the repaired protected main.

## Bootstrap

```powershell
python scripts/import_upstream.py
powershell -ExecutionPolicy Bypass -File scripts/build_cuda.ps1
$env:NEO3000_MODEL = "D:\path\to\Agents-A1.gguf"
powershell -ExecutionPolicy Bypass -File scripts/run_server.ps1
```

The server endpoint defaults to `http://127.0.0.1:9292/v1`.

## Verify the runtime

With the server running in another terminal:

```powershell
python scripts/baseline_harness.py
python scripts/baseline_harness.py --tool-test --output lab/tool-test.local.json
```

The harness verifies health, model identity, incremental SSE streaming, reasoning fields, authoritative server timings, cached prompt tokens, and optional OpenAI-compatible tool calls. Local result files are ignored by Git.

After smoke verification passes, run the deterministic long-context matrix:

```powershell
python scripts/context_matrix.py
```

Its default points are 2K, 8K, 16K, 32K, 40K, and 60K raw content tokens. Prompt-cache reuse is disabled unless `--cache-prompt` is explicitly supplied.

The fixed measurement and acceptance procedure is in `lab/BASELINE_PROTOCOL.md`.

## Repository map

- `AGENTS.md`: operating law for Agents-A1 and other coding agents
- `TASKS.md`: current checkbox queue and exact handoff cursor
- `ROADMAP.md`: architecture, checkpoints, and long-range phase order
- `NEO3000.md`: research direction and catalytic hypothesis space
- `lab/GOAL.md`: the active bounded objective
- `lab/CHECKPOINT.md`: evidence ledger and acceptance gates
- `lab/BASELINE_PROTOCOL.md`: frozen verification and comparison protocol
- `upstream/`: pinned source identity and import manifest
- `scripts/`: reproducible import, build, launch, and verification commands

The imported runtime source is intentionally absent from the initial commit. `scripts/import_upstream.py` materializes it from the exact pinned commit.
