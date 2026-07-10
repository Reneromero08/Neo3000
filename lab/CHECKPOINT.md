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
- All A trajectories had the same 598 cleaned greedy token IDs (`0F23FD3C...AEF5`), raw output hash, reasoning hash, and exact `HOLOSTATE BRANCH A`. All B trajectories had the same 551 tokens (`A08485E8...1A72`) and exact `HOLOSTATE BRANCH B`. Prompt-progress zero sentinels were excluded from generation-token identity. Direct client TTFT fields were contaminated by those progress frames; reconstructed pre-generation times were 206.973 seconds full replay and 2.822 seconds identical reuse.
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
- [ ] Exact same-branch greedy-token/reasoning hashes and cross-root isolation were not established. The failed A1 stream hashes were not retained by the local result.
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
HoloState-v1 operational quality gate: blocked by unqualified shared reasoning budget
Current action: qualify the minimum passing A1 budget, then run one immutable-budget validation-v2 if qualification passes
HoloState-v2 persistence: separate future intervention
```

The prior 768-token failure is executed lower-bound evidence and will not be rerun. The protected contract declares ascending candidates `1024, 1280, 1536, 2048`, keeps reasoning `auto`, requires nonempty reasoning, exact branch finals, normal generation stop, and process-local reuse, and permits only one versioned qualification plus one versioned validation-v2. The global claim ceiling and both availability locks remain unchanged until executed evidence closes every gate.

The repaired controller/contract passed Python compilation, 38 focused HoloState tests, 11 trace-controller tests, 9 evaluator-gate tests, and 5 WDDM tests. Complete-object contract hashing, ordered root-source hashing, stale-lock rejection, atomic one-shot claims, persisted failed-result fields, bounded worker settlement, and cleanup integrity are covered. Protected preflight passed before any live qualification launch.

### Durable persistence boundary

The built-in slot file persists active KV/recurrent state and token history, but does not persist the server prompt-checkpoint list required for hybrid recurrent prefix selection after restart.

Upstream provenance only; no patch was ported:

```text
ggml-org/llama.cpp PR 20819
ggml-org/llama.cpp PR 20955
ggml-org/llama.cpp PR 24028
```

The future persistence candidate combines checkpoint-list sidecar persistence, identity/version checks, nearest-checkpoint recovery when recurrent truncation is unsupported, and exact restart A/B validation. It is not the current next action.
