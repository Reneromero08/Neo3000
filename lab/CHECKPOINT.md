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

## Checkpoint RSI-0: CLOSED (Supervised RSI Substrate)

The repository now supports bounded supervised candidates with human promotion review; automatic promotion remains forbidden.

### RSI-0E stop and isolation gates

**Status:** IMPLEMENTED AND LIVE-PROVEN

- [x] Evaluator lockfile records hashes for the evaluator, controller, quality scripts, and fixed prompt identities without local model paths.
- [x] Candidate diff allowlist rejects paths outside the declared experiment surface.
- [x] A deliberate candidate edit to `TASKS.md` was rejected before build or launch; the exact path was recorded in `lab/results.jsonl`.
- [x] Candidate build, health, benchmark, VRAM, crash, port, build/runtime separation, model-identity, and stable-integrity gates are implemented in `scripts/neo_loop.py`.
- [x] Candidate teardown tracks only the launched candidate PID; it does not terminate the stable process by name.
- [x] RSI-0F live rejection cycle: a candidate `TASKS.md` mutation was rejected before build; stable health, listener PID, worktree, and protected hashes were unchanged after cleanup.
- [x] Candidate CMake generation failure isolated: the broad `models/` ignore pattern omitted 171 source files in `src/models/` and `tools/mtmd/models/`; source custody is repaired and clean candidate configure succeeds.
- [x] Windows WDDM telemetry proof: `GPU Process Memory(*)\\Dedicated Usage`, filtered only by exact `pid_<candidate PID>_` instance names, measured candidate PID/listener PID `36216` at a 2,288,914,432-byte (2,182.88 MiB) five-sample peak while stable PID `31188` stayed separate at 2,305,691,648 bytes. Candidate instances disappeared after teardown.
- [x] Controller samples PID-filtered WDDM dedicated usage from launch through teardown, retains a compact peak, enforces the existing 6000 MiB ceiling, and rejects unavailable or lost telemetry.
- [x] RSI-0G fresh inert-fixture rejection cycle: candidate PID/listener PID `45840` built and became healthy; the WDDM sampler recorded 17 valid samples, no failures, and a 2,301,497,344-byte (2,194.88 MiB) peak below 6000 MiB. The exact-text smoke request streamed 67 events but emitted empty assistant content after using its 64-token budget for reasoning, so the text quality gate rejected before later quality gates. Teardown, runtime removal, counter disappearance, stable health/listener PID, worktree integrity, and protected hashes passed.
- [x] Reasoning-budget diagnostic: stable and a clean candidate each ended 64/96/128/192-token exact-text probes by length with reasoning only, then emitted `NEO3000 ONLINE` at 256 tokens. Stable also returned the same final content at 64 tokens when the documented request-level `chat_template_kwargs.enable_thinking=false` was supplied. This is shared completion-budget exhaustion, not candidate-specific text regression.
- [x] Matched performance diagnostic: clean candidate first/warm decode measured 15.84/16.23/15.58 TPS; stable repeated decode measured 16.61/16.11/15.41 TPS. The prior 9.509 TPS run does not prove the 10 TPS gate is cold-state invalid.
- [x] Evaluator split proof: the immutable transport gate uses documented request-level reasoning-off and passed stable 3/3 plus clean candidate; the immutable auto-reasoning gate uses the matched 768-token allowance and passed both with nonempty reasoning plus exact final content; the separate warm-performance gate excludes one warmup, retains 10 TPS, and passed stable 16.33/17.03 TPS and candidate 17.23/17.76 TPS. Candidate PID/listener `29180` remained at 2,194.88 MiB across 67 WDDM samples and tore down cleanly.
- [x] RSI-0G reviewable acceptance: inert candidate fixture passed the locked transport, reasoning, tool, cancellation, repeat, and warm-performance gates; candidate PID/listener `38952` used exact-PID WDDM at a 2,301,497,344-byte (2,194.88 MiB) peak with valid telemetry, then tore down. Stable PID `31188`, health, protected hashes, worktree, and independent five-sample counter retirement checks remained valid. No promotion or merge occurred.

## Checkpoint 1: Compute map [ACTIVE]

Claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`. Level 1 is an operational capability unlock, not evidence of faster or catalytic inference.

### Checkpoint 1A: Trace substrate [ACTIVE]

- [x] Fixed schema v1 exists in allowed path `ggml/include/neo-compute-trace.h`; required envelope fields are always present and unknown optional semantics remain null/omitted.
- [x] Trace-disabled normal build compiles calls out under undefined `NEO_COMPUTE_TRACE` and preserves behavior: the only supervised cycle, `neo-loop-20260710T012311`, returned `reviewable-accept` at candidate `3e3023fc389a608ec5a5806eb8e1a50a801486d5`.
- [x] Separate `build/candidate-trace` diagnostic build emitted monotonic schema-v1 events to ignored local artifacts.
- [x] Exactly one supervised candidate cycle ran; transport, reasoning, tool, cancellation, repeat, warm-performance, WDDM, cleanup, stable listener, and protected-hash gates passed. Trace-disabled warm median was 16.978 TPS and exact-PID WDDM peak was 2,196.88 MiB across 84 samples.
- [ ] Matched cold and warm diagnostics quantify trace overhead and produce an observed/inferred/not-yet-instrumented compute map.

#### First trace diagnostic: STOPPED / INCONCLUSIVE

The trace-enabled cold reasoning request did not complete its 768-token budget. At teardown it had reached 602 decoded tokens at approximately 1.60 TPS, versus 14.878 TPS for the complete trace-disabled reasoning gate. The partial trace contains 2,407,857 valid JSON events, 895,639,047 bytes, and 449.13 seconds of monotonic coverage. Per-node synchronous file opens/writes are a causally supported instrumentation bottleneck; they are not evidence of a Neo3000 inference bottleneck. Warm transport, warm reasoning, and warm-performance diagnostics were not run after the stop condition.

Observed in the partial cold trace:

- CUDA operators: `ADD`, `ARGSORT`, `CLAMP`, `CONCAT`, `CONT`, `CPY`, `DIV`, `FLASH_ATTN_EXT`, `GATED_DELTA_NET`, `GET_ROWS`, `GLU`, `L2_NORM`, `MUL`, `MUL_MAT`, `PERMUTE`, `RESHAPE`, `RMS_NORM`, `ROPE`, `SCALE`, `SET_ROWS`, `SOFT_MAX`, `SSM_CONV`, `SUM_ROWS`, `TRANSPOSE`, `UNARY`, and `VIEW`.
- CPU operators: `GET_ROWS`, `GLU`, `MUL_MAT_ID`, and `VIEW`. `MUL_MAT_ID` remained on CPU under the declared CPU-MoE profile. The schema did not yet tag placement reasons, so the accompanying CPU `GLU`/`VIEW` operations cannot be classified confidently as intentional continuation versus accidental fallback.
- Host graph lifecycle: 6 rebuilds and 603 reuses. CUDA graph lifecycle: 102 capture starts, 102 completed captures, and 24,751 replays; no CUDA executable rebuild event was observed.
- Synchronization: 107,642 CUDA stream waits averaging 0.495 ms and 3,633 scheduler waits averaging 2.625 ms. Observed device-to-host transfer volume was 602,920,960 bytes; other transfer hooks were incomplete.
- Gated Delta Net recurrent state: 60 CUDA-resident layers, 8,781,824 bytes per layer, 526,909,440 bytes (502.50 MiB) total. Update, copy, snapshot, and restore cost remain uninstrumented.
- MoE bucket distribution and MMQ tile geometry were not observed because the declared CPU-MoE path did not enter the instrumented CUDA fallback bucket path.

Trace-enabled WDDM telemetry is invalid: the sampler interpolated `pid_` without bracing the PID before `_`, matched 31-33 process instances, and therefore lost candidate-only attribution. The apparent aggregate values are not candidate peaks and must not be used. Candidate PID `41688` was stopped, port 9393 retired, runtime absent, five exact-PID retirement samples were empty, and stable PID `31188` remained healthy. No rerun, merge, or promotion occurred.

#### Bounded schema-v2 candidate: NORMAL ACCEPT / DIAGNOSTIC STOPPED

- Original v1 provenance is preserved remotely at `evidence/checkpoint1a-trace-v1` → `3e3023fc389a608ec5a5806eb8e1a50a801486d5`.
- Bounded v2 candidate is preserved remotely at `evidence/checkpoint1a-trace-v2` → `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`.
- Schema v2 uses a 4,096-slot fixed-capacity thread-local aggregate table, bounded merge points, one persistent writer per instrumented module, batched/periodic output, 64 MiB and 200,000-record session ceilings, stricter per-module ceilings, explicit truncation, and dropped-event accounting.
- Placement reason is enumerated as `declared_cpu_moe`, `unsupported_cuda`, `host_only_operator`, `scheduler_policy`, `explicit_user_placement`, or `unknown`. The implementation emits only reasons proven by the declared CPU-MoE profile or backend support/scheduler decisions; unknown remains explicit.
- Candidate-local C++/Python and PowerShell tests passed for compile-out, aggregation, distinct keys, exact totals, flush boundaries, hard limits, truncation/drops, single writer open, explicit/unknown placement, exact PID, PID-prefix collisions, listener mismatch, grace expiry, and telemetry loss.
- Normal cycle `neo-loop-20260710T021421` returned `reviewable-accept`: all immutable quality, performance, exact-PID WDDM, cleanup, stable-listener, worktree, and protected-hash gates passed. Candidate PID `25412` peaked at 2,196.88 MiB over 99 exact-PID samples; warm median was 12.823 TPS. Binary scanning found no active trace-writer strings in the normal build.
- Trace-enabled candidate PID and listener PID were both `47792`. The pre-inference controller found no accepted exact-PID telemetry row, rejected the diagnostic before any workload, and did not relaunch it.
- The initialization-only artifact contained 2,796 aggregate-delta records, 2,745,102 bytes, valid schema-v2 JSON, no truncation, no reported drops, and one writer open per module. It is not a completed workload trace and supports no placement, overhead, or model-runtime bottleneck claim.
- Candidate cleanup passed: PID `47792` exited, port 9393 is free, runtime is absent, five exact-PID retirement samples were empty, and stable PID `31188` remained healthy. No merge or promotion occurred.

Later subphases map backend placement/fallback, CUDA graph lifecycle and synchronization, MoE geometry, Gated Delta Net recurrent state, and finally causal bottleneck selection. No bottleneck or optimization is claimed from correlation alone.
