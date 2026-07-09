# Checkpoint Ledger

## Checkpoint 0: Baseline parity

**Status:** CLOSED

**Purpose:** Establish a correct, reproducible, Pi-connected Agents-A1 runtime before changing inference semantics.

All gates are met. Evidence follows.

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
- GPU: NVIDIA RTX 3060, SM 8.6, 12287 MiB VRAM
- Binary: `build/stable/bin/Release/llama-server.exe`
- Binary: `build/stable/bin/Release/llama-bench.exe`

### Model

- [x] Exact Agents-A1 GGUF identified
- [x] Model SHA-256 recorded
- [x] Quantization recorded
- [x] Architecture metadata recorded
- [x] 65,536-token served-context allocation confirmed stable
- [x] Model loads without silent fallback

Model: Agents-A1-Q4_K_M.gguf, Qwen 3.5 MoE + Gated Delta Net SSM, 256x2.6B, 40 layers.
SHA-256: `31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2`

### Pi runtime (all verified)

- [x] OpenAI-compatible endpoint available at `127.0.0.1:9292`
- [x] Pi can list the model
- [x] Pi receives streamed text -- Pi UI verified: "NEO3000 PI ONLINE" appeared incrementally
- [x] Reasoning content is preserved
- [x] Tool calls parse correctly -- neo3000_probe 3/3, real Pi tool round trip (read README.md, returned "Neo3000")
- [x] Cancellation leaves the server usable -- Pi-side cancellation, immediate "NEO3000 RECOVERED"
- [x] Repeated turns preserve the session correctly

### Baseline measurements

#### A. Served-context capacity (allocation)

| Allocated Context | VRAM MiB | Decode TPS (warm) | Stable |
|-------------------|----------|--------------------|--------|
| 4K | 11,653 | 17.5 | yes |
| 8K | 2,793 | 19.7 | yes |
| 16K | 2,947 | 17.9 | yes |
| 32K | 3,285 | 16.3 | yes |
| 40K | 3,695 | 15.7 | yes |
| 64K | 3,990 | 16.6 | yes |

#### B. Occupied-context performance (actual prompt tokens, cached, warm)

| Actual Prompt Tokens | Uncached Prompt TPS | Cached Prompt TPS | Decode TPS |
|----------------------|---------------------|-------------------|------------|
| 2,053 | 77.9 | 64.6 | 22.3 |
| 8,191 | 71.3 | 56.0 | 19.9 |
| 32,773 | 72.0 | 60.3 | 22.4 |
| 40,956 | 73.3 | 60.6 | 22.4 |
| 59,996 | 73.0 | 57.0 | 20.9 |

Occupied-context decode degradation ratio (60K / 2K): 20.9 / 22.3 = **0.94** (6% drop across 60K tokens).

#### C. Rolling minimum decode speed (384 tokens, 16-token window, cached)

| Occupied Tokens | Avg TPS | Min16 TPS | Min/Avg | TTFT |
|----------------|---------|-----------|---------|------|
| 2,053 | 19.1 | 18.4 | 0.96 | 2.2s |
| 32,773 | 18.3 | 16.9 | 0.92 | 2.4s |
| 59,996 | 18.6 | 17.1 | 0.92 | 2.5s |

No significant transient stalls exist. The slowest 16-token window is 4-8% below average. Averages accurately represent sustained decode behavior.

#### D. Auto-fit audit (4K, warm)

| GPU Layers | VRAM MiB | Decode TPS | Prompt TPS |
|------------|----------|------------|------------|
| auto | 2,785 | **17.6** | 108.4 |
| ngl=20 | 1,892 | 10.0 | 44.2 |
| ngl=0 | 858 | 6.6 | 34.9 |

Auto-fit is optimal. The conservative-auto-fit hypothesis is rejected.

#### E. CPU-MoE comparison (4K, auto-fit, warm)

| CPU-MoE | VRAM MiB | Decode TPS |
|---------|----------|------------|
| ON | 2,725 | 19.1 |
| OFF | 10,604 | 30.8 |

62% faster with MoE on GPU, 89% VRAM cost. Space/speed tradeoff.

#### F. LM Studio comparison (optional characterization)

Deferred. Checkpoint 0 does not require another application's performance as an unlock gate. Neo3000's operational readiness is self-contained. A matched comparison remains valuable for characterization and will be added when LM Studio is available.

### Exit gate: CLOSED

```text
Agents-A1 runs through Pi on Neo3000: YES ("NEO3000 PI ONLINE" in Pi UI)
Streaming reasoning and content are stable: YES
A real Pi tool round trip succeeds: YES (read README.md, returned "Neo3000")
Cancellation followed by immediate recovery succeeds: YES (Pi cancel, "NEO3000 RECOVERED")
Repeated turns remain stable: YES
Context scaling is measured through the maximum stable point: YES (60K occupied, 64K allocation)
Rolling minimum decode speed is recorded: YES (no transient stalls)
Allocation and occupancy are documented separately: YES
The next instrumentation target is selected from evidence: YES (cold-start, reasoning overhead)
```

### Claim ceiling

```text
NEO3000_BASELINE_OPERATIONAL
```

No catalytic inference claim is allowed.

### Source custody recommendation

Option A: Track the imported pinned runtime as one deliberate baseline commit.

## Next checkpoint: RSI-0 (Supervised RSI Substrate)

Prepare the repository for Pi-supervised recursive self-improvement before modifying inference kernels.

### RSI-0E stop and isolation gates

**Status:** IMPLEMENTED, awaiting live candidate-cycle proof

- [x] Evaluator lockfile records hashes for the evaluator, controller, quality scripts, and fixed prompt identities without local model paths.
- [x] Candidate diff allowlist rejects paths outside the declared experiment surface.
- [x] A deliberate candidate edit to `TASKS.md` was rejected before build or launch; the exact path was recorded in `lab/results.jsonl`.
- [x] Candidate build, health, benchmark, VRAM, crash, port, build/runtime separation, model-identity, and stable-integrity gates are implemented in `scripts/neo_loop.py`.
- [x] Candidate teardown tracks only the launched candidate PID; it does not terminate the stable process by name.
- [x] RSI-0F live rejection cycle: a candidate `TASKS.md` mutation was rejected before build; stable health, listener PID, worktree, and protected hashes were unchanged after cleanup.
- [x] Candidate CMake generation failure isolated: the broad `models/` ignore pattern omitted 171 source files in `src/models/` and `tools/mtmd/models/`; source custody is repaired and clean candidate configure succeeds.
- [ ] RSI-0G acceptance attempt: the inert allowed-path candidate built, loaded, and listened on port 9393, then stopped at the VRAM gate because Windows NVIDIA per-process memory telemetry returned `[N/A]`. Candidate runtime state was removed; stable health and listener PID remained unchanged; acceptance remains unproven.
- [ ] A trustworthy Windows-safe candidate VRAM measurement must enforce the existing 6000 MiB ceiling before a newly authorized RSI-0G cycle may run once.

## Checkpoint 1: Compute map (RSI-0 required first)

Cold-start performance (first-request TPS ~50% of warm) and reasoning token overhead (~70% of output) are the identified targets. The SSM architecture shows flat decode through 60K, lowering the priority of long-context catalytic mechanisms.
