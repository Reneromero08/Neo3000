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

## Checkpoint 1: Compute map [ACTIVE / CHECKPOINT 1A PAUSED]

Claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`. Level 1 is an operational capability unlock, not evidence of faster or catalytic inference.

### Checkpoint 1A: Trace substrate [ACTIVE / PAUSED]

- [x] Fixed schema v1 exists in allowed path `ggml/include/neo-compute-trace.h`; required envelope fields are always present and unknown optional semantics remain null/omitted.
- [x] Trace-disabled normal build compiles calls out under undefined `NEO_COMPUTE_TRACE` and preserves behavior: the only supervised cycle, `neo-loop-20260710T012311`, returned `reviewable-accept` at candidate `3e3023fc389a608ec5a5806eb8e1a50a801486d5`.
- [x] Separate `build/candidate-trace` diagnostic build emitted monotonic schema-v1 events to ignored local artifacts.
- [x] Exactly one supervised candidate cycle ran; transport, reasoning, tool, cancellation, repeat, warm-performance, WDDM, cleanup, stable listener, and protected-hash gates passed. Trace-disabled warm median was 16.978 TPS and exact-PID WDDM peak was 2,196.88 MiB across 84 samples.
- [x] Stable-side diagnostic control is protected: exact-PID WDDM sampling starts immediately after launch, readiness is a strict process/health/listener/attribution/memory conjunction, phase windows are monotonic, and cleanup can target only the launched candidate PID. CPU-only safety tests cover delayed attribution, misses, grace expiry, listener mismatch, process exit, telemetry loss, memory ceiling, cleanup ownership, stable mismatch, and phase ordering.
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

#### Protected matched diagnostic: TELEMETRY PASSED / CONTROL ACCEPT / TRACE STOPPED

- Protected telemetry-only launch passed: trace candidate PID/listener `7128`, readiness 25.219 seconds, first exact-PID WDDM sample at 2.859 seconds, 9 valid samples, 2,168.88 MiB peak, clean teardown, and stable PID `31188` unchanged. No inference request ran.
- The trace-disabled matched control completed every fixed phase at PID/listener `28696`: cold reasoning 12.747 TPS, warm transport 18.624 TPS, warm reasoning 15.745 TPS, performance warmup 16.097 TPS, and counted performance median 15.783 TPS. Exact-PID WDDM produced 103 valid samples, no pre-first-valid misses or post-attribution failures, and a 2,194.88 MiB peak.
- The one trace-enabled matched launch used PID/listener `9112`, readiness 27.547 seconds, first exact WDDM sample at 1.937 seconds, 16 valid samples, no pre-first-valid misses or post-attribution failures, and a 2,194.88 MiB peak. It stopped during incomplete cold reasoning on explicit `trace_truncated`/drop evidence and was not retried.
- Final trace audit: 25,199,004 bytes, 25,554 valid schema-v2 JSON records, zero JSON errors, 10 truncated header records, maximum reported dropped-event count 28,062, and writer-open count 1. The combined 64 MiB and 200,000-record ceilings were not crossed; the unchanged per-module 24 MiB ceiling was the active boundary.
- Only startup completed with valid telemetry before the stopped cold phase. Startup contained 7,128 CUDA and 326 CPU operator events; CPU operators were `GET_ROWS`, `VIEW`, `MUL_MAT_ID`, and `GLU`. Placement reasons were 7,452 `scheduler_policy` and 2 `unsupported_cuda`, with no declared-CPU-MoE, host-only, explicit-user, or unknown placement record in that completed window. It also contained 41 CUDA capture starts, 41 capture completions, 41 replays, 349 stream waits, 2 scheduler waits, 1,986,560 device-to-host bytes, and 60 recurrent allocation events totaling 526,909,440 bytes.
- No trace-enabled workload phase completed, so no phase overhead ratio is valid and Checkpoint 1A overhead remains unmeasured. Startup counts do not support a model-runtime bottleneck claim. Candidate/runtime/port retirement, five empty exact-PID WDDM checks, protected preflight, stable health/PID, and both worktree identities passed. No merge or promotion occurred.

Later subphases map backend placement/fallback, CUDA graph lifecycle and synchronization, MoE geometry, Gated Delta Net recurrent state, and finally causal bottleneck selection. No bottleneck or optimization is claimed from correlation alone.

### Immediate parallel boundary: HoloState-0 [CAPABILITY AUDIT]

Checkpoint 1A is not closed. Proven trace properties are trace-disabled compile-out, bounded aggregation, exact-PID protected launch control, and explicit truncation/drop detection. Trace overhead, a completed workload compute map, and a model-runtime bottleneck remain unproven.

HoloState-0 is authorized to inspect existing `llama-server` capabilities and run at most one isolated sidecar launch on port 9494. It will test whether a frozen canonical prefix can avoid reevaluation through bounded RAM cache/checkpoint reuse and slot save/restore while preserving deterministic Agents-A1 output. Exact RAM reuse, in-process restore, and process-restart restore must be classified separately. This audit may nominate a first Checkpoint 2 catalytic candidate; it does not activate or complete Checkpoint 2 and does not prove recurrent hybrid-state persistence from ordinary KV restoration.

#### HoloState-0 result: EXACT PROCESS-LOCAL REUSE / PERSISTENCE BOUNDARY

- Case A: stable binary version `13 (417e1d6)`, SHA-256 `5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B`, and tracked source contain `ctx-checkpoints`, `checkpoint-min-step`, bounded `cache-ram`, `cache-idle-slots`, `cache-reuse`, and `slot-save-path`/restore. The hybrid context reported `cache_reuse is not supported` and disabled that specific KV-shift feature; checkpoint/RAM reuse remained available.
- Canonical content combined `ROADMAP.md`, `AGENTS.md`, `lab/GOAL.md`, and `README.md`: 33,695 bytes, SHA-256 `8D0C83AFF791E7D6F077F2A2F9BB8B393D0E14C5AA7F5FFE42F638814FB04A68`, 7,500 content tokens, token-ID SHA-256 `69D9D993B4376037F7206266C899F2CEED858D3B89973CDE36CAAD1A521E3910`, and 7,519 rendered prompt tokens. Chat-template SHA-256 was `A4AEE8AFCF2E0711942CF848899BE66016F8D14A889FF9EDE07BCA099C28F715`.
- Full replay processed all 7,519 tokens in 206,932.648 ms at 36.335 TPS; total time was 248.026 seconds and decode was 14.567 TPS. Reuse processed 132 fresh tokens and reported 7,387 cached tokens in 2,603.962-3,207.468 ms. Identical A amplification was 74.843x; mean across seven correct reuse requests was 72.653x, with a 1.756% fresh fraction.
- All A trajectories had the same 598 cleaned greedy token IDs (`0F23FD3C...AEF5`), raw output hash, legacy pre-final-segment hash, and exact `HOLOSTATE BRANCH A`. All B trajectories had the same 551 tokens (`A08485E8...1A72`) and exact `HOLOSTATE BRANCH B`. The pre-final hash does not prove a `reasoning_content` channel. Prompt-progress zero sentinels were excluded from generation-token identity. Direct client TTFT fields were contaminated by those progress frames; reconstructed pre-generation times were 206.973 seconds full replay and 2.822 seconds identical reuse.
- Interleaved A/B/A/B served every correct branch with 7,387 cached and 132 fresh tokens. Carrier reuse count was 7 including identical, branch, multiplexed, and post-restore requests.
- Slot save wrote 8,069 tokens / 231,311,464 bytes in 296.004 ms (745.246 MiB/s), SHA-256 `A81509419942EED3C57647E7C0BDE64880EBF6AF9391CC62A25D1124F22D0870`. In-process restore read/restored the same bytes/tokens in 104.682 ms and the following A remained exact with 7,387 cached tokens. Because process-local RAM/checkpoint entries remained live, attribution to the slot file alone is inconclusive.
- Restart restore used the same binary, model, configuration, prefix, and slot hash; it reported 8,069 restored tokens / 231,311,464 bytes in 485.950 ms, but prompt progress then reported cache 0 and reevaluated all 7,519 tokens in 165,385.384 ms. Output remained exact, but process-restart state reuse failed.
- Catalytic metrics: 7,387 avoided tokens, 132 fresh, 72.653x mean prompt compute amplification, 33.487 avoided tokens per MiB of slot file, and 0.196% in-process save-plus-restore closure cost relative to avoided replay. Configured RAM-cache ceiling was 4,096 MiB; measured sidecar private-memory growth was 206,774,272 bytes. Working-set growth was 15,671,939,072 bytes and includes mapped model residency, not just cache.
- Initial/restart sidecar PIDs were `34500`/`36404`; exact WDDM peaks were 2,252.88 MiB with zero telemetry failures. Both launches retired, port 9494 is free, five retirement samples per launch were empty, stable PID `31188` remained healthy, and both worktrees remained clean. The identity-bound slot file is retained only in ignored runtime state.
- Classification: process-local RAM/checkpoint reuse `exact`; in-process slot restore `inconclusive` as a file-specific carrier; process-restart slot restore `failed`. The 40K optional test was not authorized because every 8K persistence mode did not succeed exactly. Exact restart-persistent Gated DeltaNet hybrid state is not proven, so no durable capsule is nominated. The exact process-local carrier is now the basis for the separately bounded HoloState-v1 Live Prefix Lattice integration below.

## Checkpoint 2: First catalytic compute intervention [ACTIVE]

The phase classification is corrected from capability audit to operational integration without raising the global claim ceiling.

```text
Global claim ceiling: NEO3000_BASELINE_OPERATIONAL
Mechanism status: EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
Current intervention: HoloState-v1 Live Prefix Lattice
Future intervention: HoloState-v2 Durable Capsule
```

HoloState-v1 is exact process-local executable-prefix reuse. HoloState-0 directly proved its carrier through repeated and interleaved deterministic branch reuse. Checkpoint 2 now tests a protected, identity-bound, long-lived multi-root integration of that carrier.

HoloState-v2 is restart-persistent executable-state reuse. It is unproven and outside the current intervention.

### Catalytic declaration

```text
expensive operation: canonical-prefix prompt evaluation
borrowed carrier: exact process-local hybrid prefix state
transformation: evaluate one divergent suffix or branch
extracted result: deterministic reasoning, final content, or tool call
restoration or closure: preserve the canonical checkpoint lattice for later branches
retained lawful state: model/configuration/prefix-identity-bound live cache entries
```

### HoloState-v1 integration attempt [INCONCLUSIVE]

- [x] The original protected controller could not commit, push, merge, promote, terminate stable, modify stable source, or mutate the model; its CPU-only safety suite passed 15 tests.
- [x] Two immutable canonical root identities warmed within the 4K-8K band. Root A: 32,164 bytes, SHA-256 `F28DB3E15EA34510432B7367C621ABE15B5A9DA9B0A1F8189556F4ACE86FDBAA`, token-ID SHA-256 `71363A1309DC5692AF1DB8BE99E3F0EE031C966A58A8BAE49F6CE7096E7C7CC2`, 7,150 rendered tokens. Root B: 21,714 bytes, SHA-256 `0EF151D9DD57D176E92E393686A548FBED01967AF6E4F0B5070F5B6F002D7CB8`, token-ID SHA-256 `CE5A629803ACA104F2C2FE869422E34554FE1663B724496EA4B15EA92526C728`, 4,879 rendered tokens. Both used chat-template SHA-256 `A4AEE8AFCF2E0711942CF848899BE66016F8D14A889FF9EDE07BCA099C28F715`.
- [ ] The fixed `A1, B1, A2, B2, A1, B1` sequence did not complete. A1 stopped the sequence on its deterministic output gate; B1/A2/B2 were not attempted.
- [ ] Exact same-branch greedy-token/pre-final raw-segment hashes and cross-root isolation were not established. The failed A1 stream hashes were not retained by the local result.
- [x] A1 demonstrated performance reuse before the quality stop. Server log: 7,165 logical prompt tokens, 148 fresh, inferred 7,017 reused, 3,685.92 ms prompt time at 40.15 prompt TPS, 768 completion tokens at 13.91 decode TPS, and 58,884.30 ms total. Against Root A's 159,051.535 ms warm, observed prompt-time amplification was 43.151x and fresh prompt ratio was 2.066%.
- [ ] A1 did not become an accepted catalytic branch. It consumed all 768 allowed completion tokens and failed the combined exact-final/reasoning gate, so accepted cumulative avoided evaluations remain zero. The 7,017 avoided evaluations are performance-only evidence with the quality gate open.
- [x] Sidecar PID, listener PID, and exact WDDM PID were all `42076`; 139 valid samples peaked at 2,362,318,848 bytes (2,252.88 MiB) with no telemetry failure. Warm private-memory deltas were 194,699,264 bytes for A and 287,465,472 bytes for B, below the 4,096 MiB host-cache bound.
- [x] Stable PID `31188` and health remained unchanged. The archived trace candidate stayed clean at `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`.
- [ ] The non-restarted extended proof did not run because the fixed sequence failed first. Duration and request count are both zero.
- [x] Cleanup passed: sidecar stopped, runtime removed, port 9494 free, and five exact-PID WDDM retirement samples were empty.
- [x] Automatic promotion remained disabled. No stable, Pi, model, CUDA, kernel, candidate, or upstream source change occurred.

### Classification

```text
HoloState-v1 Live Prefix Lattice: inconclusive
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN: retained from HoloState-0
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
```

No literal infinity claim is made. Accepted cumulative avoided evaluations, accepted state reuse yield, and accepted holographic branch density are all zero because no branch closed the deterministic gate. The A1 performance-only observation corresponds to 7,017 avoided evaluations, 2.882 avoided tokens per MiB of Root A's conservative 2,552,915,136-byte cache-budget estimate, and 43.151x prompt-time amplification.

### Active repaired-contract boundary

```text
HoloState-v1 reuse mechanism: succeeded
HoloState-v1 raw /completion gate: no literal final marker through 2048
Current action: preserve the completed CatalyticSwarm-0 v2 control boundary; no further live work is authorized without separate explicit authorization
HoloState-v2 persistence: separate future intervention
```

The prior 768-token failure is executed lower-bound evidence and was not rerun. The one-shot protected qualification then tested ascending candidates `1024, 1280, 1536, 2048` through legacy `/completion`. All four raw streams exhausted their exact limits without the A1 final marker. `/completion` exposed one raw content stream; when the marker was absent, `parse_final_structure` labeled the whole stream as reasoning. Therefore limit exhaustion and missing final are proven, while `reasoning_content` attribution is not. The selected budget remains unset and validation-v2 remains unattempted.

The repaired controller/contract and post-run prompt-progress interpretation repair passed Python compilation, 40 focused HoloState tests, 11 trace-controller tests, 9 evaluator-gate tests, and 5 WDDM tests. Complete-object contract hashing, ordered root-source hashing, stale-lock rejection, atomic one-shot claims, persisted failed-result fields, bounded worker settlement, cleanup integrity, and cached/fresh derivation are covered. Protected preflight passed before and after the live qualification.

### Reasoning-budget qualification result [NO PASS THROUGH 2048]

Root A warmed once as state `holostate-27f565ae760cdf96aa958ec9`: canonical prefix SHA-256 `58EAB1360FD2B56B86F12A903BB5C9AE081E8A437FB5B8AE04C40C8D1B663CEF`, token-ID SHA-256 `C8A5DA13ED1C396AA4F6BA756EEA2865AFD379E8BF8E4A950FCBABB6EC43C087`, chat-template SHA-256 `A4AEE8AFCF2E0711942CF848899BE66016F8D14A889FF9EDE07BCA099C28F715`, 8,010 rendered tokens, and 172,069.162 ms warm prompt time.

| Budget | Completion | Stop | Exact final | Raw stream nonempty | Logical / cached / inferred fresh | Prompt ms | Decode TPS | Total s | Classification |
|---:|---:|---|---|---|---:|---:|---:|---:|---|
| 1024 | 1024 | limit | no | yes | 8026 / 7878 / 148 | 3598.417 | 14.544 | 74.029 | completion-budget-exhausted |
| 1280 | 1280 | limit | no | yes | 8026 / 7878 / 148 | 4043.371 | 14.650 | 91.433 | completion-budget-exhausted |
| 1536 | 1536 | limit | no | yes | 8026 / 7878 / 148 | 3465.535 | 14.414 | 110.051 | completion-budget-exhausted |
| 2048 | 2048 | limit | no | yes | 8026 / 7878 / 148 | 3072.167 | 15.092 | 138.788 | completion-budget-exhausted |

The versioned qualification result SHA-256 is `1AE79511E6C0E3C928989912A24CCDC64C5B918D6B74B1A364ACDB0A34044D94`. Its raw prompt-progress records expose `cache=7878`, `processed=8026`, and `total=8026`; because this server reports `processed` cumulatively when cache is present, the reusable fresh delta is `total - cache = 148`. This interpretation repair was tested without changing or rerunning the completed one-shot evidence.

Qualification sidecar PID/listener `44652` produced 239 exact-PID WDDM samples, peaked at 2,362,318,848 bytes / 2,252.88 MiB, and had no telemetry loss. The process stopped, runtime was removed, port 9494 became free, five retirement samples were empty, stable PID `31188` was unchanged, and the original v1 marker/result hashes remained exact. No Root B, tool, cancellation, fixed, extended, or v2 request ran.

### HoloState-v1.1 message-boundary protocol [EXECUTED]

- Protocol commit `3fb00fe93d0fb22e203d8e26d86173f5e3d2ee32` passed 60 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus compilation and protected preflight before push. The complete protocol SHA-256 was `767d85744467902bfc89a77dade270d261164533742694f9aeac1b26f28ae50b`.
- The one-shot marker was claimed only after clean `HEAD = main = origin/main`, exact binary/model/template identities, stable PID `32684`, free port 9494, absent v2 files, and all three historical hashes passed.
- Sidecar PID/listener `34580` launched on port 9494. Root A identity was `holostate-worker-6ff8940c6c7d72ae0a39eb78`, canonical prefix SHA-256 `93B508DC5B2028DFF04158A3CE26FD8D80F5B00711D3A5BF1FF2C7131CA096F8`, system-message SHA-256 `1D5A88F572F5C06C75CF179018FFFD656D66267EF2519B01A60FDA670DCEC172`, and 7,806 rendered warm tokens.
- Root A warm returned byte-exact `HOLOSTATE ROOT WARM` (SHA-256 `84C0CFD85D4774E2BD67BC8FAE1C756ECB15C0E3CF58DD69891DD6B69FCD649B`), empty reasoning metadata, `finish_reason=stop`, 7 completion tokens, and exact prompt-token identity. Prompt processing was 145,519.789 ms at 53.642 TPS; decode was 18.981 TPS and total time 145.939 seconds.
- The parser observed zero complete generated-token IDs and classified the warm `completion-token-evidence-missing`. The fast-failure law stopped the audit before Fast A1/A2, Root B, or Deep A1.
- Pinned source inspection diagnoses an instrumentation defect: partial streaming responses assign one token ID, while the final streaming response assigns an empty token array. The executed parser replaced its array on every event, so the final empty array erased the preceding token evidence. Raw SSE events were not persisted, so the run itself proves only that the parser retained zero IDs; the overwrite explanation is source-based.
- `FAST_PROCESS_LOCAL_HOLOSTATE=reject`; `DEEP_PROCESS_LOCAL_HOLOSTATE=inconclusive`. `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE`, broader process-local, restart-persistent, and CatalyticSwarm-0 states remain locked. Automatic promotion remains disabled.
- Sidecar PID `34580` produced 73 exact-PID WDDM samples with a 2,362,318,848-byte / 2,252.88 MiB peak. Cleanup, runtime removal, free port 9494, five empty retirement samples, stable PID `32684`, archived-candidate isolation, and prior evidence preservation all passed.
- Attempt SHA-256 is `F634CA2732CEBBE424D4634F8EFAD035C6E11EAABB0D34E40A0F1EC09A2DF975`; result SHA-256 is `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2`. This attempt must not be rerun.
- A future separately authorized protocol version may accumulate partial token arrays and use new versioned evidence paths. No repair is promoted from this rejected audit.
- Post-audit evidence binding passed 61 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus compilation and protected preflight.

#### Later v1 adjudication

The ignored v1 result and its original Fast=`reject` / Deep=`inconclusive` fields remain byte-identical. The later evidence interpretation is narrower: worker protocol v1 is an `instrumentation-reject`; Fast capability is untested/inconclusive because zero Fast requests ran; Deep capability is untested/inconclusive because zero Deep requests ran.

### HoloState worker protocol v2 [EXECUTED / INCONCLUSIVE]

- The only causal intervention is request-local merging of delta/cumulative token arrays plus bounded stream provenance; a final empty array cannot clear prior evidence.
- The v2 contract binds all five historical hashes, exact binary/model/template/envelope/root identities, unchanged Fast/Deep lane budgets, an 8 MiB/50,000-record reasoning-redacted ledger, and new v2 paths.
- A thinking-disabled `TOKEN ARRAY CANARY` must prove exact visible content, empty reasoning, normal stop, nonempty generated IDs, completion-count agreement, and a valid ledger before Root A warm.
- The one-shot sequence is canary, warm A, warm B, A1, B1, A2, B2, A1 repeat, B1 repeat, Deep A1, stop. Warm failures never reject Fast capability; Deep is independent of a completed Fast proof.
- Pre-audit protection passed 85 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus compilation; stable tokenization measured Root A/B at 7,715/4,302 rendered warm tokens.
- Protocol v1, qualification, validation-v2, persistence, extended proof, automatic retry, and automatic promotion remain forbidden.
- Protocol commit `b2559f7c0c06e35a3e360b71ed13b69c4eb1eb7c` was clean, pushed, and exact before the single v2 marker was claimed. Complete protocol SHA-256 was `c043d3084efefcbc9b369e1b770d36aef0dafcf89896d6105586564b204a0379`.
- The one authorized invocation launched sidecar PID `37804` but stopped during readiness when the protected stable-listener ownership query timed out. No listener was admitted, the parser canary was not attempted, and root warm, Fast, repeat, and Deep request counts all remained zero.
- No streaming token array was observed. The exclusive ledger contains 0 records and 0 bytes; its empty SHA-256 is `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`. No token merge mode or completion-count agreement is claimable.
- Exact-PID WDDM captured 7 samples with a 97,349,632-byte / 92.84 MiB peak before cleanup. Sidecar retirement, runtime removal, free port 9494, five empty retirement samples, stable PID `32684`, candidate isolation, and all five historical hashes passed.
- Attempt SHA-256 is `09A849AC35692A49DCC349110426FBD5ED9EF4BD146E723C8E750445916DE8F9`; result SHA-256 is `D08C4638179D6A2F0BFABE22DA2C8879377BDC6306E41ED22816FB95F45A84A7`. Fast and Deep are untested/inconclusive, all availability states remain locked, and v2 must not be retried.
- Post-audit evidence binding passed 86 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus Python compilation.

### HoloState worker protocol v3 [EXECUTED / INSTRUMENTATION REJECT]

- Connector branch `codex/holostate-listener-readiness-v3` at `60defbb2ffd1dfc54d40374fd529554ba0acf287` is exactly four commits ahead of protected main and adds only `listener_probe.py`, `holostate_readiness.py`, and their two CPU-only test files. Draft PR #1 remains the connector review context.
- The integrated architecture retains the connector substrate and corrects only demonstrated defects: runtime-mockable subprocess execution, malformed relevant-row rejection, hard total retry windows, exact empty-port checks, structured failure evidence, a shared stable/sidecar boundary, and non-listener rechecks after ownership queries.
- V3 inherits the complete v2 endpoint, identities, roots/order, token accumulation, bounded reasoning-redacted ledger, parser canary, warm/Fast/repeat/Deep sequence, capture restrictions, memory ceilings, isolation, verdicts, and availability law.
- Its only intervention is readiness control: distinct readiness and capability one-shot paths, a single marker-to-pass deadline, no listener query in the 250 ms model-load poll loop, fresh exact ownership at admission and request boundaries, and checked teardown/retirement.
- A readiness non-pass creates only readiness-v3 evidence, leaves Fast/Deep untested and inconclusive, and stops without retry. A pass freezes readiness evidence and binds its hash before any capability artifact is claimed.
- V3 binds the exact v1 protocol/evidence/adjudication objects, v2 protocol/evidence objects, all eight ignored prior files, and the continued absence of validation-v2 paths. Historical files and objects remain immutable.
- CPU-only protection passes compilation; 18 listener, 10 readiness, 102 HoloState, 11 trace, 9 evaluator, and 5 WDDM tests. Stable tokenizer-only rendering measures Root A/B at 8,131/4,408 tokens inside unchanged bounds; no output was generated.
- Exact integration commit `b45249c6620c2645232883c5035b260683706dcd` was pushed and passed protected preflight before the one authorized invocation. No retry occurred.
- Readiness passed in 29.61 seconds after 106 non-listener model-load polls. Sixteen checked listener queries all passed on their first attempt in 0.015-0.032 seconds, with zero timeouts, unavailable samples, wrong owners, or other failures. Stable PID `32684` and sidecar PID `42236` were exact throughout.
- The parser canary executed and returned exact visible `TOKEN ARRAY CANARY`, empty reasoning, `finish_reason=stop`, 5 completion tokens, and matching prompt identity. Its 10 ledger events exposed no nonempty token arrays: 9 were absent and the final one was empty. Generated token count was therefore 0, and completion-count agreement failed as `stream-token-count-mismatch`.
- The canary is an instrumentation reject. Root A/B warm, all six Fast requests, repeats, and Deep A1 were not attempted; Fast and Deep capability remain untested/inconclusive.
- The 5,173-byte ledger contains 10 bounded reasoning-redacted records and passed. Final WDDM evidence contains 14 exact-PID samples, a 2,360,221,696-byte / 2,250.88 MiB peak, no telemetry failure, and 153,636,864 bytes host-private growth.
- Every required ownership boundary, cleanup, isolation, frozen readiness hash, and prior-evidence check passed. PID `42236` stopped, runtime was removed, port 9494 was empty, five retirement samples were empty, stable PID `32684` remained healthy, and candidate `14de9c71593e5aea4fcfcadeda47ba5c623fadcf` remained clean.
- Readiness/attempt/result/ledger SHA-256 values are `6C761F40E6EBCD43B608218CC84D0AA1F75D2E1FDCEB15EB9DC103168E6EFCBF`, `4D70D8E53056A2BB2A00320051855B4D612547150A5FC68C068D17DEC66EFBFE`, `387E82B02BA8F6992111722595AEE05055A979A54A8D2EE6D9F5A1EE38C645E3`, and `26D65B9F474EF84B3F9483D6DDB1838280F1D54D476FDF14B5595A624EA5A583`.
- `readiness_v3=pass`; `worker_protocol_v3=instrumentation-reject`; Fast/Deep=`inconclusive`. Every HoloState availability state and CatalyticSwarm-0 remain locked; automatic promotion remains disabled.

### HoloState worker protocol v4 [HISTORICAL PRE-EXECUTION SNAPSHOT]

The following preparation boundary is preserved as the state immediately before the single executed invocation recorded below.

The v4 prequalification correctly stopped under its declared exact-count law.

Subsequent pinned-source inspection demonstrated that the law omitted the
server-counted terminal EOS token.

The observed 4-visible / 5-completion relationship is therefore causally
reconciled, but no worker capability request has yet executed.

- Connector substrate is imported from `codex/holostate-chat-token-evidence-v4` at `168fb4d0e666cbc058a59826ff9e97359889d835`; the sixteen connector commits are not imported into final history.
- V4 is separately protected and preserves v3 readiness, roots, lanes, budgets, sequence, memory, isolation, cleanup, and availability laws. Its only intervention is bounded terminal-EOS accounting for thinking-disabled, text-only Chat Completions responses when native arrays are unavailable.
- The no-generation tokenizer qualification requires two exact `[60738, 30094, 18916, 8378]` arrays and exact detokenization to `TOKEN ARRAY CANARY`. Capability artifacts cannot be claimed unless readiness and tokenizer evidence are frozen passes.
- The terminal EOS token ID remains unknown. The complete generated sequence remains unknown. Deep hidden reasoning and tool-call token sequences are not reconstructed.
- At that boundary all five v4 evidence paths were absent. No readiness, tokenizer, parser canary, root warm, Fast, repeat, or Deep request had executed.
- Compilation and 232 CPU-only tests pass without contacting a live inference endpoint. Protected lock/preflight and exact pushed-main admission remain prerequisites to the single authorized invocation.
- At that boundary every HoloState availability state and CatalyticSwarm-0 remained locked; automatic promotion was disabled.

### HoloState worker protocol v4 [EXECUTED / REVIEWABLE ACCEPT]

- Exact integration commit `da04c5bf388c3d091da4e2f1aee33bf852377517` was pushed as protected `main` and passed preflight before the single invocation. No retry occurred.
- Readiness passed in 33.015 seconds with stable PID `32684` and sidecar PID `38452`. The tokenizer-v4 artifact records two exact `[60738, 30094, 18916, 8378]` arrays, exact round-trip text, no generation, and a passed resource gate.
- The canary accepted exact `TOKEN ARRAY CANARY`: four visible tokens, five completion tokens, usage delta one, `finish_reason=stop`, direct `stop=true` / `stop_type=eos` / empty stopping word / empty final verbose array, empty reasoning, and no tools. The terminal EOS ID and complete generated sequence remain unknown.
- Root A/B warmed at 8,173/4,436 rendered tokens. Fast A1/B1/A2/B2 and A1/B1 repeats all accepted with direct terminal-EOS accounting; A and B retained 8,144/4,407 cached tokens and evaluated 21 fresh tokens per Fast request.
- A1 and B1 repeat fields were exact, A1/A2 and B1/B2 remained distinct, and cross-root identity isolation passed. The unknown terminal EOS token ID was never compared.
- Deep A1 evaluated 27 fresh tokens over 8,144 cached tokens and retained opaque reasoning evidence, but exhausted all 768 completion tokens with `finish_reason=length` and no final assistant content. Deep is `reject`; the completed Fast proof remains `reviewable-accept`.
- The bounded reasoning-redacted ledger contains 907 records and 618,838 bytes. WDDM recorded 136 exact-PID samples with a 2,362,318,848-byte / 2,252.88 MiB peak; maximum observed host-private growth was 1,158,742,016 bytes.
- All 29 ownership boundaries, resources, ledger limits, cleanup, isolation, frozen readiness/tokenizer/source authority, historical hashes, stable PID, clean candidate `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`, runtime removal, free port 9494, and five empty retirement samples passed.
- Readiness/tokenizer/attempt/result/ledger SHA-256 values are `4B8A44B4CB3DE9355B8A3D4E3FC945DD685EA35B98F5BF0C0160DAA090249BA7`, `EB10127666CDADE0D6A8E7EF59CA7D4310B64B89619800DF245BD769666A587D`, `6197D986FD3ED030340A82300245AE0EF1249229E21162BF6796F7F614A7EA19`, `396C1E76EC07EB64E8FF700E49F45A931638BD071A7955941712314CADDF59CF`, and `CD96EE1F41F15E9953705F7DDA762D1111D60E04C828F9B157D314D789F0F104`.
- Tracked v4 evidence and `neo-exp-0018` are bound; 232 post-audit CPU-only tests, compilation, and JSON/JSONL validation pass.
- At the v4 boundary, `worker_protocol_v4=reviewable-accept`; Fast=`reviewable-accept`; Deep=`reject`. `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE` was unlocked, broader process-local and restart-persistent availability remained locked, and `CatalyticSwarm-0` was authorized but not yet executed. Automatic promotion remained disabled.

### CatalyticSwarm-0 bounded control [HISTORICAL PRE-EXECUTION SNAPSHOT]

- Draft PR #3 is inspected at connector head `c73a684b0d83ba9f59d11396a579f5e9a3478c2b`: four linear commits from protected `f17caefa41527f910e1039e70b33c8035c418ea9`, adding only the declared blackboard, scheduler, adapter, and test files.
- The integrated substrate remains callback-driven. Static review demonstrated and repairs close forged-plan, multi-slot, over-budget, partial-receipt, missing-key, subset-parent, wrong-decision, fail-open transport, mutable/unbounded entry, and silent unverified-synthesis gaps.
- The protected protocol locks 32 logical Fast workers over one physical slot, exact phase counts/order/codes, deterministic identities/seeds/assignments/parent graph, compact assigned-parent context, exact structured contributions, append-only chain evidence, resource ceilings, cleanup, and no promotion.
- Control qualification, readiness, and parser canary are separate one-shot gates. At this snapshot none of the seven `state/catalytic_swarm/*-v1` artifacts exists and no CatalyticSwarm worker request has executed.
- At this snapshot, the live sequence was authorized to start only from exact pushed protected `main` after protected preflight. It would warm current Root A once, run the exact structured parser canary, and claim the swarm attempt only after the canary froze as a pass. Any failure would stop without retry.
- `STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE`, `CATALYTIC_SWARM_CONTROL_AVAILABLE`, task-advantage, and SOTA claims remain locked. Existing process-local micro-worker availability stays unlocked; broader process-local and restart-persistent HoloState remain locked; automatic promotion remains disabled.

### CatalyticSwarm-0 bounded control [EXECUTED ONCE / READINESS INCONCLUSIVE]

- Exact integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280` was pushed as protected `main` and passed protected preflight before the single authorized invocation. No retry occurred.
- Generation-free control qualification passed. This is a control-contract result, not a swarm-capability pass.
- Readiness launched sidecar PID `44748` and admitted 6 exact-PID WDDM samples with a 92.84 MiB peak. A subsequent exact-PID counter query timed out; the sampler classified `candidate-vram-telemetry-lost`, so readiness stopped as `inconclusive`.
- The structured parser canary and capability attempt were not attempted. `parser-canary-v1.json`, `attempt-v1.json`, `result-v1.json`, `ledger-v1.jsonl`, and `blackboard-v1.json` are absent. No logical worker request, physical lease, ledger record, or blackboard entry was created.
- Lifecycle cleanup succeeded despite the resource-gate stop: PID `44748` exited, runtime state was removed, port 9494 is free, and stable PID `32684` remains healthy. The composite cleanup/resource gate remained non-pass only because exact-PID WDDM telemetry was lost.
- `readiness_v1=inconclusive`; `STRUCTURED_HOLOSTATE_MICROWORKER=inconclusive`; `CATALYTIC_SWARM_CONTROL=inconclusive`. `STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE` and `CATALYTIC_SWARM_CONTROL_AVAILABLE` remain locked.
- `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE` remains unlocked from v4. Broader process-local HoloState, restart-persistent HoloState, task advantage, and SOTA claims remain locked. V4 evidence is preserved and automatic promotion remains false.
- The exact early-stop evidence is bound as `neo-exp-0019`: control qualification SHA-256 `864F74F58792E120422BB4078439E40AAE96546D58282DED38BB7665678A3E53` and readiness SHA-256 `76351D413785D6E239F1E20FB152EDF78DF312EEBE85D86FC343C6B25D7C1CCC` are recorded in the protected evaluator/result/lock for the evidence commit.
- This version is no-retry. At the v1 evidence boundary no further live work was authorized; the separately versioned v2 successor below is the later explicit authorization and must not alter or retry v1.

### CatalyticSwarm-0 v2 WDDM successor [REVIEWABLE ACCEPT]

- Draft PR #5 was inspected at exact connector head `428edaaa2772d6805c4733a9d629a7812838a932`: two commits from protected `3fcef46c4863814f3396d1466269d4a3ef0f8c9a` and only the two declared new WDDM policy/test files. All 14 connector tests pass.
- The optional sampler policy preserves legacy behavior when absent. When present, one or two unavailable queries are bounded transient gaps; the third, a valid-sample gap over 30 seconds, or memory over 6000 MiB fails closed. A fresh admission sample is at most 5 seconds old, exact-PID only, and has a zero failure streak.
- Fresh-sample boundaries are implemented at readiness, before/after the parser canary, before capability claim, before/after every worker request, and before teardown. While awaiting recovery, the controller keeps process, stable/sidecar health, listener ownership, deadline, and hard WDDM failure checks active.
- Complete-object `catalytic_swarm_0_v2` hash is `eadea6e1c6d66e50d85803c4cc96ad6a703b4964799251977ff1288eabc24cf1`. It binds v1 contract/evidence hashes `ca8987fd5d8f1d3043a2c78147e2ec6f2ab8006cccfc4c958398ba8f7d0a9cd4` / `1e8bc8416e1a772f14cfebd39ce98850c61b2ff3cc8ed57a1953c4521445a426` and exact v1 control/readiness artifact hashes `864F74F58792E120422BB4078439E40AAE96546D58282DED38BB7665678A3E53` / `76351D413785D6E239F1E20FB152EDF78DF312EEBE85D86FC343C6B25D7C1CCC`.
- Before live execution, the seven v2 one-shot paths were distinct and absent. V1 control/readiness remained exact and its five downstream paths remained absent. The v1 command was hard-retired.
- Root A prompt bytes are read from exact v1 integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280`, preserving the inherited canonical/system/rendered identities while `docs/CATALYTIC_RUNTIME_ROADMAP.md` becomes authoritative.
- Compilation and 338 CPU-only tests passed before execution. The architectural integration was committed and pushed at exact protected `main` commit `cf61f90ff5544f2f8bc546e5d661ea72cdda8666`, then protected preflight passed.
- The first controller command was refused before claim because the model path was absent; it created zero artifacts, made zero model requests, and left all seven v2 paths absent. That refusal is not a v2 execution. One subsequent artifact-claiming live invocation ran with explicit pinned paths, and no retry occurred after claim.
- Control qualification, readiness, and the structured parser canary passed. All 32 thinking-disabled workers executed through exactly one physical slot with 32 leases, 32 verifier receipts, 32 valid hash-chained blackboard entries, exact phase counts 16 proposal / 8 evidence / 6 critique / 2 synthesis, 1,319 bounded stream-ledger records, and two verified synthesis entries.
- Exact-PID WDDM remained fully available: 177 valid samples, 0 unavailable samples, 0 recoveries, maximum failure streak 0, maximum valid-sample gap 2.938 seconds, 107 passed freshness boundaries, and a 2,395,889,664-byte / 2,284.9 MiB peak. Maximum host-private growth was 727,982,080 bytes.
- Cleanup, stable/candidate isolation, sampler retirement, runtime removal, free port 9494, five empty retirement samples, exact v1 evidence preservation, and exact worker-v4 evidence preservation all passed. No Deep, persistence, CUDA/kernel/model/Pi/stable change, retry, or automatic promotion occurred.
- V2 is `reviewable-accept`: `STRUCTURED_HOLOSTATE_MICROWORKER=reviewable-accept` and `CATALYTIC_SWARM_CONTROL=reviewable-accept`. `STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE` and `CATALYTIC_SWARM_CONTROL_AVAILABLE` are unlocked. Broader process-local HoloState, restart persistence, task advantage, and SOTA remain locked; automatic promotion remains false.
- Exact SHA-256 bindings are control `1FC67796F436E69B1B2C2F132345C0335FADF6D1452E7F98D8A92D78CB616CE3`; readiness `129FD883FD03BBEF8B216AC67F77CBE854CA798A86BBC18A11D4DCDF010E7124`; parser canary `9282D7F8AE195C866E767A7F0D3BCB0A366E3FC3C1509A7DB1F99F1C541191B5`; attempt `0E9A839B7AD9D50AE6FD82DD3C63A93D23596C4A32FAF515BAC67A68EFEE8866`; result `AF491153D98877CAACAF5ED89F3446A80AD8ED12D3FAD2CDE22C2AF77CE5BEC7`; ledger `C523EF77C80CDD4783D2E41103FCD72490A4C837DA2B3988B29F8D7A97E1F7F9`; blackboard `197929DF8DF62A24480A64C071651CED43E16D82F0B6DA5A9AB740C6C1236964`.
- Next boundary: preserve v2 without retry. The CatalyticSwarm-1 equal-budget successor executed once below under separate authority; its inconclusive result does not establish task advantage.

### CatalyticSwarm-1 equal-budget evaluation [EXECUTED ONCE / INCONCLUSIVE]

- Draft PR #6 was inspected at exact head `aaeb3fe8cc906121fdfcb8ed41d9420b2849d8b6`: twelve linear commits from protected `7cad4a9d8181c160da712c3474d66a4fbf8a1ba3`, adding exactly the five declared connector files and no evaluator or evidence mutation. The commits were not imported individually.
- The real-repository connector passed its original 25 CPU-only tests. Static review then demonstrated and repaired fail-open defects in scoring timing, complete-root cached-prefix proof, token-evidence scope, outcome/classification revalidation, task/root observation binding, sparse-versus-verified prompt parity, exact-success semantics, protected state naming, and hidden-data serialization. The repaired connector passes its expanded negative regression suite.
- The frozen task suite is `catalytic-swarm-1-dsl-selection-v1`: 8 tasks, 64 candidates per task, 5-instruction programs, 5 public examples, 16 hidden examples, SHA-256 `4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92`.
- The complete protected contract SHA-256 is `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`. Plan SHA-256 values are serial-chain `99FE4402A487EEAF07FAEE7A64CAB241A888E1CB916D09C62BDA493AB08EEF53`, best-of-N `E989ECB8A53E9AD24885759627D3E3BA9A16E76A41A770E70784644A9A96696A`, sparse swarm `9289DE195D12AB93A9A9DD70949C92FC55D40E0D930CAD521605FC1707E116DE`, and verified swarm `46A2CEADA66217AC2DD3E0BD6D1C20A052EFE9D76EE236887AF18428409A772C`.
- Every task prepares one exact common public-root warm outside comparison budgets. Every arm request must report a cached-token prefix at least as long as the exact tokenized warm/request common prefix that contains the complete public root. The four arms then run in the frozen Latin-square order. Each arm has 32 requests, one physical slot, 32 maximum completion tokens per request, 1,024 maximum completion tokens, 8,192 maximum fresh prompt tokens, and 1.10 maximum fresh/completion/total-model token ratios.
- Hidden examples and answer keys are forbidden from roots, assignments, model requests, arm-local context, later task context, and ledger records. Hidden scoring is deferred until all four arms for a task complete. Arm outputs are arm-local and task outputs are task-local.
- The protected runner reuses v4 terminal-EOS token evidence, one physical lease, v2 exact-PID WDDM resilience and fresh-sample admission, stable/candidate isolation, and bounded cleanup. The exclusive metadata-only ledger is capped at 80,000 records and 67,108,864 bytes.
- Seven ignored one-shot paths were prepared under `state/catalytic_swarm_1`: control qualification, readiness, parser canary, attempt, result, ledger, and task results. All seven were absent before the authorized invocation.
- The new authorization was bound to exact protected commit `556bb4d57a05bb81fa101a98092472170b50c0dd` and consumed by one invocation of `audit-catalytic-swarm-1`. No retry, Deep request, or automatic promotion occurred. CatalyticSwarm-0 v2 remained hard-retired.
- The safety repair requires exact stable/candidate custody before and after all 1,032 prospective model requests, host/resource enforcement after each request, a hard parity stop after each of eight completed tasks, cleanup coverage across parser success and attempt/result preparation, and terminal count reconciliation at `2064 / 1032 / 8`. The retained helper and its direct regression suite are protected controller sources.
- The task suite, complete contract, four plans, prompts, candidate programs, hidden data, Latin-square order, request/token budgets, and advantage thresholds remained unchanged.
- Control qualification passed without generation. Readiness passed for sidecar PID `30848`. The parser canary passed without a model request, then the first task's common-root warm completed with 4,846 prompt/fresh tokens, 0 cached tokens, and 4 completion tokens.
- The first serial-chain comparison response completed, but `cs1-task-01/serial-chain/cs1-chain-t01` did not prove reuse of the complete public root. This is the primary fail-fast stop. The run ended `inconclusive` after exactly 2 completed model requests: 1 common-root warm, 1 comparison, and 0 completed task comparisons. No best-of-N, sparse-swarm, verified-swarm, hidden scoring, parity comparison, later task, or advantage adjudication completed.
- Six artifacts are preserved with exact SHA-256 values: control `F9C8032340655EBBE5E41867D8C4C426940E6B7D2236ACDA9019EE9E24F8733D`; readiness `F6DF670C7CE1659E78D4B51F5CD45FAF4087DD46ABE87D8AD529AB45F6FE9C95`; parser canary `0B2749F3F864CB93FB003EA68A41AD364C56360C270506DB3684C1738E221680`; attempt `593D013494064F10FF9ECF732942EE114E1DC91E14A3290210C8801684A48A40`; result `D37CBF79BC867D927C01C7977D4432A29B2CA40E59ED5C10CCF6EF9A5F3AACAB`; ledger `5E016B7554E57564833BAA3B5B1250C6EE6FB73CFE204BDCBC4EEB902C1E40B8`. `state/catalytic_swarm_1/task-results-v1.json` is absent.
- Runtime boundary accounting is exact at the stop: 2 completed requests, 4 custody checks, 2 host-memory checks, 0 task-parity checks, and 318,357,504 bytes maximum host-private growth. These observed request boundaries passed; the full-schedule `2064 / 1032 / 8` reconciliation correctly remains non-pass because execution stopped after request 2 of 1,032.
- The 741-byte bounded ledger contains one metadata-only warm record and no raw SSE or hidden material. The first comparison stopped before ledger persistence, so 2 completed responses versus 1 ledger record correctly yields terminal reason `ledger-request-count`.
- Exact-PID WDDM recorded 44 valid samples, one initial unavailable query, maximum valid-sample gap 2.875 seconds, 12 passed observed freshness admissions, and a 2,362,318,848-byte / 2,252.88 MiB peak. A separate inherited terminal-label incompatibility remains: the CatalyticSwarm-0 v2 terminal WDDM reconciler expects v2 worker-boundary labels rather than CS1 request-boundary labels, so it reports `wddm-required-freshness-boundary-order`. This secondary terminal finding did not cause the earlier complete-root-cache stop and is not repaired by rerunning v1.
- Cleanup, isolation, frozen control/readiness/parser evidence, and predecessor preservation passed. PID `30848` stopped, runtime state was removed, port 9494 became free, five retirement samples were empty, stable PID `32684` remained healthy, and candidate `14de9c71593e5aea4fcfcadeda47ba5c623fadcf` remained clean and unchanged.
- `CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN`, `SOTA_SWARM_CLAIM`, broader process-local HoloState, restart persistence, and automatic promotion remain locked. CatalyticSwarm-1 v1 is no-retry; any successor requires a separately versioned contract, evidence paths, and new explicit authority.

### CatalyticSwarm-1 cache-admission diagnostic [INTEGRATED / NOT EXECUTED]

- CatalyticSwarm-1 v1 remains `EXECUTED ONCE / INCONCLUSIVE / NO RETRY`.
- The separately versioned diagnostic contract is integrated at canonical SHA-256 `be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b`. Its connector source, protocol, CPU-only tests, controller, and complete evaluator object are protected by the evaluator lock.
- No diagnostic evidence object exists. `state/catalytic_swarm_1_cache_diagnostic/` and its five paths for control qualification, readiness, attempt, result, and ledger remain absent. No diagnostic sidecar launched and no diagnostic model request executed during integration.
- The fixed prospective sequence contains exactly 3 requests on one physical slot: `common-root-warm`, `minimal-branch` constrained to exact `{"candidate_id":"C00"}`, and the unchanged `serial-chain / cs1-chain-t01` realistic first turn. Thinking is disabled, temperature is zero, and Deep request count is zero.
- The common root preserves the exact v1 public task projection and reference envelope. The task suite, public data, programs, hidden examples, answer key, chat template, model, binary, cache controls, and checkpoint minimum step remain unchanged.
- The measurement law persists every completed branch response before cache-admission classification. It records the exact public-root terminal token index, exact common-token prefix, inherited v1 required threshold, actual cached tokens, fresh tokens, completion tokens, and transport/token-evidence state. A negative first cache class does not stop the second probe unless a separate safety gate fails.
- The diagnostic terminal reconciler is CS1-native and does not call the CatalyticSwarm-0-v2 worker-boundary reconciler. A complete diagnostic requires 3 completed requests, 6 custody checks, 3 host/resource checks, 3 `pre-request:cs1-cache-diagnostic-*` and 3 `post-request:cs1-cache-diagnostic-*` freshness boundaries, one warm ledger record, and two branch observations. A lawful early safety stop reconciles the exact observed completed-request count.
- All six CatalyticSwarm-1 v1 artifacts remain bound to their published hashes and `state/catalytic_swarm_1/task-results-v1.json` remains absent. `audit-catalytic-swarm-1` remains hard-retired. Static integration does not identify the cache root cause.
- A future live diagnostic invocation requires new explicit authorization bound to the then-exact pushed protected `main` and exact Agents-A1 model path. `CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN`, `SOTA_SWARM_CLAIM`, broader process-local HoloState, restart persistence, and automatic promotion remain locked.

### Durable persistence boundary

The built-in slot file persists active KV/recurrent state and token history, but does not persist the server prompt-checkpoint list required for hybrid recurrent prefix selection after restart.

Upstream provenance only; no patch was ported:

```text
ggml-org/llama.cpp PR 20819
ggml-org/llama.cpp PR 20955
ggml-org/llama.cpp PR 24028
```

The future persistence candidate combines checkpoint-list sidecar persistence, identity/version checks, nearest-checkpoint recovery when recurrent truncation is unsupported, and exact restart A/B validation. It is not the current next action.
