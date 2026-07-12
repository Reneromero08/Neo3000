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

CS1-v1 is immutable (`EXECUTED ONCE / INCONCLUSIVE / NO RETRY`). Its separately versioned cache diagnostic executed once and returned `reviewable-accept`: both probes reused the complete public root (4,822 cached tokens covering terminal 4,820), while the former 4,825-token threshold was overextended. CS1-v2 is integrated but unexecuted at contract `911242c74509f1d2d8c6a3c8aa82948c452dac5f4646dd97d70d7b27b750e984`; it changes only cache admission to the exact root-terminal law. Task advantage, SOTA, broader HoloState, restart persistence, and automatic promotion remain locked.

Checkpoint 0 and the supervised RSI substrate are closed. Checkpoint 1A tracing is paused, and Checkpoint 2 is active. CatalyticSwarm-0 v2 proved the bounded 32-worker, one-slot control plane at `reviewable-accept`; it did not prove task advantage.

CatalyticSwarm-1 v1 is **EXECUTED ONCE / INCONCLUSIVE**. Control, readiness, the generation-free parser canary, and one common-root warm passed. The first serial-chain comparison then stopped because its response did not prove reuse of the complete public root. The audit ended after 2 model requests: 1 warm, 1 comparison, and 0 completed tasks. Equal-budget advantage was not completed.

```text
authorization: CONSUMED / NO RETRY
live model requests: 2
common-root warm requests: 1
comparison requests: 1
completed task comparisons: 0
sidecar launches: 1
one-shot artifacts: 6 present / task-results-v1.json absent
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN: LOCKED
SOTA_SWARM_CLAIM: LOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
automatic promotion: disabled
```

CatalyticSwarm-1 v1 remains **EXECUTED ONCE / INCONCLUSIVE / NO RETRY**. The separately versioned CS1 cache-admission diagnostic is **INTEGRATED / NOT EXECUTED**. Its fixed prospective sequence contains exactly 3 model requests: the exact common-root warm, a minimal exact `{"candidate_id":"C00"}` branch, and the unchanged `serial-chain / cs1-chain-t01` realistic first turn. It uses separate one-shot paths, and all five diagnostic paths plus their state directory remain absent.

The diagnostic persists completed branch measurements before cache-admission classification and uses a CS1-native terminal reconciler. Static integration does not identify the root cause. A live invocation requires new explicit authorization bound to the then-exact pushed protected `main` and exact Agents-A1 model path. Task advantage and SOTA remain locked; automatic promotion remains disabled.

The partial metadata ledger records the warm only; the failed comparison stopped before ledger persistence, leaving exact 2-response/1-record partial accounting. A separate inherited CatalyticSwarm-0 v2 terminal-WDDM label mismatch remains non-pass even though all 12 observed freshness admissions passed. It did not cause the primary cache-proof stop. Cleanup passed: sidecar PID `30848` stopped, runtime state was removed, port 9494 became free, and stable PID `32684` remained healthy.

Do not invoke `audit-catalytic-swarm-1` again. Do not invoke `audit-catalytic-swarm-1-cache-diagnostic` without that future exact-main and exact-model authorization.

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
