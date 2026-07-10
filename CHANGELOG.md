# Neo3000 Changelog

This changelog records the architectural history of Neo3000: what became operational, what was measured, what hypotheses were rejected, what safety boundaries were added, and which claims are actually supported by pushed evidence.

It is intentionally not a raw dump of every administrative commit. Small documentation and pointer updates are compressed into the milestone they served.

## Current state

Current state is defined by the pushed task board, checkpoint ledger, evaluator lock, and evidence records rather than a fragile changelog commit pointer.

```text
Checkpoint 0: CLOSED
Claim ceiling: NEO3000_BASELINE_OPERATIONAL
Current RSI level: Level 1, supervised bounded RSI available
Checkpoint 1A: ACTIVE / PAUSED
Checkpoint 2: ACTIVE
First catalytic intervention: HoloState-v1 Live Prefix Lattice
HoloState-v1 integration verdict: INCONCLUSIVE
HoloState-v1 budget qualification: NO PASS THROUGH 2048
HoloState-v1.1 worker audit: FAST REJECT / DEEP INCONCLUSIVE / NO RETRY
Mechanism status: EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE: LOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
RSI-0F supervised rejection cycle: PASSED
RSI-0G supervised acceptance cycle: REVIEWABLE ACCEPT
Automatic promotion: DISABLED
SUPERVISED_BOUNDED_RSI_AVAILABLE: UNLOCKED
Stable server: port 9292
Candidate server: port 9393
```

The authorized inert-fixture RSI-0G cycle returned `reviewable-accept`. Candidate PID/listener `38952` passed transport, reasoning, tool, cancellation, repeat, and warm-performance gates; PID-filtered WDDM recorded a 2,196.88 MiB peak across 88 valid samples. One pre-first-valid counter miss remained within the locked grace period; telemetry was not lost after attribution began. Candidate teardown, runtime removal, port retirement, and five independent WDDM retirement checks passed. Stable PID `31188`, health, worktree, and protected hashes remained unchanged. No promotion or merge occurred. RSI-0 is closed; Checkpoint 1 is active.

---

## Unreleased

### Pending

- Checkpoint 1A remains active but paused. Compile-out, bounded aggregation, protected exact-PID control, and explicit truncation/drop detection are proven; overhead, a completed workload map, and model-runtime bottleneck selection remain unproven.
- Checkpoint 2 is active for HoloState-v1 Live Prefix Lattice, the protected operational integration of exact process-local executable-prefix reuse already proven by HoloState-0.
- The one-shot HoloState-v1 raw `/completion` qualification is complete: `1024, 1280, 1536, 2048` all exhausted without the exact final marker. This does not prove `reasoning_content` attribution. No budget was selected and validation-v2 remains unattempted.
- HoloState-v1.1 executed its protected Chat Completions audit once and stopped at Root A warm on missing complete generated-token evidence. Fast is `reject`; Deep is `inconclusive`; no retry is authorized.
- HoloState-v2 Durable Capsule remains the separate, unproven restart-persistence intervention. The current integration must not claim restart persistence.
- Preserve human review and the automatic-promotion prohibition throughout Level 1.

### HoloState-v1.1 message-boundary protocol prepared

- Corrected the historical claim boundary: legacy `/completion` supplied one raw content stream, and `parse_final_structure` treated the entire raw string as reasoning when the literal final marker was absent. The old runs prove limit exhaustion and missing final markers, not `reasoning_content` attribution; their files and hashes remain unchanged.
- Added evaluator-locked `holostate_worker_protocol_v1` with exact binary/model/template identities, unchanged A/B source order, a hash-bound immutable-reference system envelope, separate user assignments, one-shot paths, memory ceilings, stable isolation, and independent fast/deep verdict law.
- Added a protected, non-executed `audit-worker-protocol` controller path through `/v1/chat/completions`. The fixed sequence stops after `deep A1`; fast failure stops immediately, while deep failure preserves a completed fast proof.
- Lane F is thinking-disabled at 64 tokens and requires exact visible A/B content, an empty reasoning channel, normal stop, and cache reuse. Lane D is reasoning-auto at 768 tokens and requires nonempty reasoning metadata, exact deep-A content, normal stop, and cache reuse.
- Extended the shared `baseline_harness.stream_completion` parser to retain server-returned generated-token arrays and prompt-progress events while preserving its separate reasoning, visible-content, and tool-call channels. Worker results store reasoning only as presence, length, and SHA-256.
- Pre-audit verification passed 60 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus protected preflight. Template/tokenizer-only rendering measured Root A at 7,806 tokens and Root B at 4,630, inside the unchanged 4K-8K bounds without generating output or claiming the audit.
- The one-shot audit, old qualification, validation-v2, extended proof, and persistence work were not executed by the pre-audit protocol change.

### HoloState-v1.1 worker audit executed once

- Protocol commit `3fb00fe93d0fb22e203d8e26d86173f5e3d2ee32` was clean, pushed, and preflight-exact before the one-shot marker was claimed.
- Root A rendered 7,806 tokens and returned exact `HOLOSTATE ROOT WARM`, empty reasoning metadata, `finish_reason=stop`, and matching prompt identity. Prompt time was 145,519.789 ms at 53.642 TPS; 7 completion tokens decoded at 18.981 TPS.
- The parser retained zero generated-token IDs and rejected the warm as `completion-token-evidence-missing`, stopping before Fast A1/A2, Root B, or Deep A1.
- Pinned-source inspection diagnoses the instrumentation defect: partial streaming results carry per-token arrays, the final streaming result carries an empty array, and the executed parser replaced rather than accumulated arrays. Raw SSE events were not persisted, so this explanation is source-based rather than direct event replay.
- `FAST_PROCESS_LOCAL_HOLOSTATE=reject`; `DEEP_PROCESS_LOCAL_HOLOSTATE=inconclusive`. All HoloState availability states, CatalyticSwarm-0, and automatic promotion remain locked.
- Sidecar PID `34580` recorded 73 exact-PID WDDM samples at a 2,252.88 MiB peak and retired cleanly. Stable PID `32684`, archived-candidate isolation, cleanup, and all historical evidence hashes passed.
- Attempt SHA-256 is `F634CA2732CEBBE424D4634F8EFAD035C6E11EAABB0D34E40A0F1EC09A2DF975`; result SHA-256 is `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2`. Worker protocol v1 must not be retried.
- Post-audit evidence binding passed 61 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus compilation and protected preflight.

### Checkpoint 2 activated: HoloState-v1 Live Prefix Lattice

- The expensive operation is canonical-prefix prompt evaluation; the borrowed carrier is exact process-local hybrid prefix state.
- Each transformation evaluates one divergent suffix or branch and extracts deterministic reasoning, final content, or a tool call.
- Closure preserves the canonical checkpoint lattice, retaining only model/configuration/prefix-identity-bound live cache entries.
- The global claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`; `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` is recorded separately.
- HoloState-v1 is process-local and uses the Live Prefix Lattice name.
- HoloState-v2 Durable Capsule is reserved for future restart-persistent state work.

### HoloState-v1 live integration attempt: inconclusive

- Added protected `scripts/holostate_live.py` and its CPU-only safety suite. The controller exposes only the declared live-state operations, confines writes to ignored runtime state, binds roots to exact binary/model/template/prefix/token identities, and treats registry entries as metadata until reusable cached tokens and exact output are observed.
- The single allowed validation used exact sidecar PID/listener `42076`, stable PID `31188`, the locked Agents-A1 model, and binary version `13 (417e1d6)` / SHA-256 `5D0C...541B`.
- Root A warmed at 7,150 rendered tokens in 159,051.535 ms; Root B warmed at 4,879 tokens in 101,519.304 ms. Both immutable identities were inside the declared 4K-8K band.
- A1 reused an inferred 7,017 of 7,165 logical prompt tokens, evaluated 148 fresh tokens in 3,685.92 ms, and produced an observed 43.151x warm/reuse prompt-time ratio.
- A1 then consumed all 768 completion tokens and failed the combined deterministic output gate. The controller stopped immediately; B1/A2/B2, same-branch hash equality, eviction observation, and the 20-request/60-minute-bounded extended proof were not run. No retry occurred.
- Exact-PID WDDM produced 139 valid samples with a 2,252.88 MiB peak and no telemetry loss. Cleanup removed the exact sidecar and runtime; port 9494 and all five retirement samples were empty; stable remained unchanged.
- `HoloState-v1 Live Prefix Lattice` is `inconclusive`. `PROCESS_LOCAL_HOLOSTATE_AVAILABLE` and `RESTART_PERSISTENT_HOLOSTATE_AVAILABLE` remain locked. The narrower HoloState-0 status `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` remains valid.
- After the stopped run, the controller was narrowed to preserve future failed-branch metrics and prefer prompt-progress cache counts over ambiguous zero-generation completion totals. This was a non-runtime evidence repair; the validation was not rerun.

### HoloState-v1 reasoning-budget contract repair

- The causal boundary is explicit: process-local prefix reuse succeeded, while the operational quality proof was blocked by an unqualified shared reasoning budget.
- The original ignored attempt/result remain immutable lower-bound evidence; new one-shot qualification and validation-v2 files are versioned separately.
- A complete evaluator-locked HoloState contract now owns roots, ordered source sets, branches, prompts, exact finals, reasoning/reuse requirements, candidate and selected budgets, sequences, request limits, memory ceilings, and binary/model/template identity.
- Completion budget exhaustion, wrong final content, missing reasoning, reuse failure, and acceptance are distinct persisted classifications.
- The repair and post-run prompt-progress interpretation fix passed 40 focused HoloState tests plus the protected trace, evaluator, and WDDM regression suites; evaluator preflight passed before and after the live launch.
- HoloState-v2 persistence remains a separate future intervention; the global claim ceiling and both availability locks are unchanged pending executed evidence.

### HoloState-v1 reasoning-budget qualification: no pass through 2048

- One sidecar, one Root A warm, and exactly four ascending A1 requests ran. Root B, fixed interleaving, tool/cancellation probes, extended proof, validation-v2, and retries did not run.
- Root A identity was `holostate-27f565ae760cdf96aa958ec9`; it contained 8,010 rendered tokens and warmed in 172,069.162 ms.
- Every A1 request exposed 8,026 logical prompt tokens and 7,878 cached tokens, yielding an inferred 148-token fresh delta. The raw server field `processed=8026` is cumulative when cache is present; the controller now records that raw field separately and derives fresh as `logical - cache` for future requests. The completed one-shot result was not rewritten or rerun.
- Budgets 1024, 1280, 1536, and 2048 produced exactly 1024, 1280, 1536, and 2048 raw completion tokens respectively, each with `stop_type=limit`, no final marker, and classification `completion-budget-exhausted`. Channel attribution was not available from this endpoint.
- Qualification result SHA-256 is `1AE79511E6C0E3C928989912A24CCDC64C5B918D6B74B1A364ACDB0A34044D94`. No minimum budget passed, so `selected_max_tokens` remains null and no locked-budget commit exists.
- Sidecar PID/listener `44652` recorded 239 exact-PID WDDM samples at a 2,252.88 MiB peak with no telemetry loss. Full cleanup, five empty retirement samples, stable PID `31188`, free port 9494, and preservation of the original v1 evidence all passed.

### HoloState-0 capability boundary opened

- Authorized one isolated port-9494 sidecar audit using the exact locked model, one slot, bounded host RAM, and protected exact-PID WDDM control.
- The audit separates repeated-prefix RAM reuse, branch multiplexing, in-process slot restore, and restart restore. Deterministic output plus prompt-token reuse evidence is required for an exact classification.
- Ordinary KV save/restore cannot establish Gated DeltaNet hybrid-state persistence by itself. Stable, CUDA, inference kernels, model files, and the archived trace candidate remain outside scope.
- Case A was present in the existing binary/source. A 7,519-token rendered prompt replayed fully once, then exact process-local A/B branches reused 7,387 tokens and evaluated only a 132-token checkpoint gap with identical per-branch greedy token and raw pre-final/output hashes. The legacy pre-final hash is not channel attribution.
- A 231,311,464-byte slot file saved and restored 8,069 tokens. In-process behavior stayed exact but cannot be attributed to the file separately from live RAM/checkpoint entries. After the declared restart, the same file restored successfully at the endpoint but the model reevaluated all 7,519 prompt tokens.
- At the HoloState-0 audit boundary, the retained result was exact process-local RAM/checkpoint reuse, not a restart-persistent hybrid capsule. No 40K audit, source integration, stable change, Checkpoint 2 activation, or automatic promotion occurred in that audit.

### Checkpoint 1A first instrumentation candidate

- Candidate `3e3023fc389a608ec5a5806eb8e1a50a801486d5` added schema-v1 optional compute tracing under `NEO_COMPUTE_TRACE`; normal builds compile trace calls out.
- The only trace-disabled cycle, `neo-loop-20260710T012311`, returned `reviewable-accept`. All immutable gates passed, warm median was 16.978 TPS, exact-PID WDDM peak was 2,196.88 MiB, cleanup passed, and stable PID `31188` remained healthy.
- The separate trace-enabled cold diagnostic stopped before completion. Synchronous per-node writes produced 2,407,857 events and 895,639,047 bytes over 449.13 seconds; partial decode was approximately 1.60 TPS versus 14.878 TPS trace-disabled. Overhead is `too high` and matched warm measurements were not run.
- The partial compute map observed CUDA/CPU placement, graph capture/replay, synchronization, transfers, and 502.50 MiB of CUDA-resident recurrent state. Explicit fallback reasons, fast-path MoE buckets, MMQ tiles, recurrent update/copy cost, and matched warm structure remain unresolved.
- Trace-enabled WDDM attribution was invalid because the local sampler matched 31-33 GPU process instances instead of the exact candidate PID. Aggregate values are discarded; cleanup and five exact-PID retirement checks passed. No rerun, merge, or promotion occurred.

### Checkpoint 1A bounded aggregation candidate

- Archived v1 and v2 evidence refs resolve exactly to `3e3023fc389a608ec5a5806eb8e1a50a801486d5` and `14de9c71593e5aea4fcfcadeda47ba5c623fadcf` respectively; neither is a merge proposal.
- Schema v2 replaces synchronous per-event file operations with fixed-capacity thread-local aggregation, bounded batched merges, persistent writers, explicit limits/truncation/drop accounting, and enumerated placement reasons.
- Focused compile-out, aggregation, totals, limit, writer, placement, exact-PID, collision, and telemetry-loss tests passed.
- The single normal cycle `neo-loop-20260710T021421` returned `reviewable-accept`; every immutable gate passed, warm median was 12.823 TPS, exact-PID WDDM peak was 2,196.88 MiB, and normal binaries contained no trace-writer strings.
- The trace-enabled launch used candidate/listener PID `47792`, but produced no accepted exact-PID WDDM row before inference. The diagnostic stopped before cold or warm workloads and was not rerun. Its 2.75 MB initialization-only artifact was bounded, valid, untruncated, and reported no drops, but it cannot measure overhead or support a runtime bottleneck claim.
- Candidate and telemetry retirement checks passed; stable PID `31188` remained healthy. No merge or promotion occurred.

### Checkpoint 1A protected diagnostic control

- Added a stable-side controller that can write only ignored candidate-local diagnostic artifacts and can stop only the exact candidate process object it launches.
- Candidate readiness is the conjunction of process liveness, health, exact listener ownership, exact-PID WDDM attribution, and the existing 6000 MiB ceiling; sampling begins immediately after launch and remains active through teardown.
- Added monotonic, non-overlapping startup/workload/teardown windows, candidate CPU-time capture, incremental schema-v2 trace bounds, and post-teardown stable/listener/telemetry retirement evidence.
- Protected the controller and its CPU-only safety suite in `lab/EVALUATOR.json` and the evaluator lock. No candidate source, stable inference logic, promotion path, or evaluator gate value changed.
- Telemetry-only passed with exact candidate PID/listener/WDDM agreement. The trace-disabled control completed every fixed phase, but the single trace-enabled run stopped during cold reasoning when an unchanged v2 module reported truncation and up to 28,062 dropped events at its 24 MiB ceiling.
- The final stopped artifact contained 25,554 valid JSON records and 25,199,004 bytes, below the combined session ceilings. Because cold reasoning was incomplete, no matched trace-enabled workload phase or overhead ratio is claimable; no model-runtime bottleneck was selected.
- Candidate and port retirement, five exact-PID WDDM retirement checks, protected preflight, and stable PID `31188` passed. The trace launch was not retried, and no merge or promotion occurred.

### Level 1 architecture integrated

- Level 0 is the completed operating level; Level 1 is current; Level 2 remains locked; Level 3 remains the long-range target.
- `SUPERVISED_BOUNDED_RSI_AVAILABLE` is achieved. The claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`.
- Performance substrate and catalytic compute are separate standing lanes. Conventional CUDA improvements do not satisfy a catalytic checkpoint without borrow, transform, extract, restore/close, and lawful retained state.
- Fast, Long, and RSI future runtime profiles are recorded without implementation or unmeasured capacity claims.
- Checkpoint 1 is divided into trace substrate, backend/fallback, CUDA graph/synchronization, MoE geometry, recurrent-state, and causal-selection subphases.
- External CUDA leads are provenance and hypotheses only; no external fork merge or source replacement is authorized.

---

## 2026-07-09 — RSI-0 safety enforcement and live proof work

### Repository state aligned

The task board, roadmap, active goal, and checkpoint ledger were reconciled with the actual pushed state.

- Checkpoint 0 was kept closed with claim `NEO3000_BASELINE_OPERATIONAL`.
- LM Studio was removed as an RSI unlock dependency and retained only as optional historical characterization.
- The active boundary was advanced from already-completed source custody work to RSI-0 enforcement and proof cycles.
- `prompts/supervised_rsi_cycle.md` was added as the tracked operator contract for one bounded, non-promoting candidate cycle.
- The prompt requires one causal hypothesis, candidate-only edits, immutable evaluation, a single cycle limit, exact evidence, and manual promotion.

Representative commits:

- `f55e5116eb27209a69ad3aa065471df238f7dc1c` — add supervised RSI operator prompt.
- `a186d5911ab3d7ff856fe356019ee7893dc6a9f7` — align roadmap with closed Checkpoint 0 and RSI-0E.

### RSI-0E safety gates implemented

The evaluator and controller were hardened so a candidate cannot rewrite the rules, corrupt stable, or silently pass by changing its own scoreboard.

Added or enforced:

- `lab/EVALUATOR.lock.json` with precomputed hashes for evaluator, controller, benchmark identities, protected documents, launch configuration, and model identity.
- Candidate path allowlist enforcement against the candidate diff.
- Protected-path rejection with exact offending paths.
- Hash verification before and after every cycle.
- Build timeout.
- Candidate health timeout.
- Benchmark timeout.
- One-crash-per-cycle ceiling.
- Candidate-only VRAM ceiling of 6000 MiB for the RTX 3060 12GB safety profile.
- Model size and SHA-256 verification before candidate launch.
- Port collision rejection.
- Stable/candidate build-directory separation.
- Stable/candidate runtime-directory separation.
- Stable health and listener-PID verification before and after candidate activity.
- Stable worktree integrity verification.
- Candidate-owned teardown by tracked PID rather than killing every `llama-server` process.
- Cleanup on success, rejection, timeout, and interruption.
- No merge, push, rebase, self-promotion, or automatic replacement operation inside `neo_loop.py`.
- Compact result recording in `lab/results.jsonl`.

Representative commit:

- `cac80b0e8ce3f323c2beca942b43cef4e0b97f1b` — enforce candidate safety gates.

### RSI-0F supervised rejection cycle proved

A deliberate candidate mutation to protected `TASKS.md` was rejected before build or launch.

Proved:

- Candidate edit allowlist rejected the exact protected path.
- No candidate process remained.
- Candidate runtime state was removed.
- Stable remained healthy on port 9292.
- Stable listener PID remained unchanged at `31188` during the recorded run.
- Stable worktree remained unchanged.
- Protected hashes remained valid.
- The rejection was accurately recorded.
- Candidate state was restored cleanly and remained resumable.

Representative commit:

- `9e510795de7ad843bb49c3b32a3a0e23ed6cd027` — prove supervised rejection cycle.

### Candidate CMake blocker isolated and source custody repaired

The first RSI-0G attempt failed during CMake generation. The original compact evidence retained only the generic final line, so build diagnostics were improved to preserve the first causal CMake error block, diagnostic lines, longer stdout/stderr tails, and an ignored local full log.

First causal error:

```text
tools/mtmd/models/models.h was missing from the candidate worktree
```

Root cause:

- The broad `.gitignore` rule `models/` ignored every directory named `models` anywhere in the tree.
- It silently excluded 171 legitimate source files under `src/models/` and `tools/mtmd/models/`.
- Initial source custody was therefore incomplete even though the imported runtime appeared broadly tracked.

Repair:

- Anchored the weight directory ignore as `/models/`.
- Added the omitted source files to Git custody.
- Added `.gitignore` to protected evaluator paths.
- Improved compact CMake failure evidence in `scripts/neo_loop.py`.
- Confirmed clean candidate CMake configure succeeds after repair.
- Confirmed the shared candidate builder and candidate-specific builder had failed for the same missing-source reason; script drift was not causal.

Representative commit:

- `16286951e54ded4de59062f4a85bb3ea134fca4d` — repair candidate source custody and diagnostics.

### Agents-A1 model identity corrected and locked

After the candidate built successfully, the next acceptance attempt stopped before launch because the evaluator contained a transposed SHA-256 sequence.

Correct identity:

```text
File: Agents-A1-Q4_K_M.gguf
Size: 21,166,757,632 bytes
SHA-256: 31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2
```

The corrected identity was written consistently into:

- `lab/EVALUATOR.json`
- `lab/EVALUATOR.lock.json`
- `lab/CHECKPOINT.md`
- `TASKS.md`
- active goal evidence

The candidate was not launched during the mismatched-identity run. Stable health, listener identity, and cleanup remained intact.

Representative commit:

- `816f6e978c848a8cd59c5826d7aeaaa8c4d4eb7d` — correct Agents-A1 evaluator identity.

### Candidate health-probe timeout handling repaired

A fresh authorized acceptance cycle then configured and built successfully and began candidate model loading. During loading, a socket read timeout escaped the health probe and aborted the controller before the declared candidate readiness deadline.

Root cause:

- A temporary socket/read timeout during model loading was treated as an uncaught terminal exception.
- It should have meant only “candidate not healthy yet” while the readiness deadline remained open.

Repair:

- `request_json()` now catches HTTP, URL, JSON, timeout, and OS-level socket errors and converts them to `NeoLoopError`.
- `health_ok()` converts those request failures to `False`.
- The existing readiness loop can now continue polling until success, candidate crash, or the declared deadline.
- A stalled-health local test passed.

The run stopped safely without retry:

- Candidate process removed.
- Candidate runtime directory removed.
- Candidate port 9393 free.
- Stable health passed before and after.
- Stable listener PID remained `31188`.
- Stable worktree remained clean.
- Automatic promotion remained disabled.

Representative commit:

- `d911f932be997b764a74235bba8ef2b9279a2c04` — handle candidate health-probe timeouts.

---

## 2026-07-03 — RSI-0 substrate established

### RSI-0A: engine source placed under Git custody

Neo3000 stopped treating the imported runtime as an opaque local tree and adopted source-custody Option A: track the pinned runtime directly as a deliberate baseline.

Established:

- Pinned upstream repository: `ggml-org/llama.cpp`.
- Pinned upstream commit: `fdb1db877c526ec90f668eca1b858da5dba85560`.
- Upstream licenses and attribution preserved.
- Imported engine placed under ordinary Git diff, branch, rollback, and worktree control.
- 2103 files initially entered the tracked source baseline.
- One-line source edits became ordinary inspectable Git diffs.
- Clean rollback restored the exact baseline.
- A separate worktree could materialize the complete tracked engine.

Later CMake proof discovered that 171 additional source files had been hidden by the broad `models/` ignore rule; that custody defect was repaired on July 9 in `1628695`.

Representative commit:

- `7ea6ffddc599814dce4a0c2218cac420025739ae` — track imported llama.cpp engine as Git-diffable baseline.

### RSI-0B: stable and candidate worktrees isolated

Established the dual-runtime topology:

```text
Stable worktree: D:\CCC 2.0\AI\Neo3000
Stable branch: main
Stable build: build/stable
Stable port: 9292

Candidate worktree: D:\CCC 2.0\AI\Neo3000-candidate
Candidate branch: candidate
Candidate build: build/candidate
Candidate port: 9393
```

Added:

- `scripts/build_candidate.ps1`
- `scripts/run_candidate.ps1`
- Separate build paths.
- Separate ports.
- Separate runtime-state paths.
- Candidate model alias.
- CPU-MoE-compatible candidate launch profile for shared 12GB VRAM constraints.

Representative commit:

- `1c1bfe69ecf08e91b4632552612691b57484a5e8` — establish candidate worktree and isolated build/run scripts.

### RSI-0C and RSI-0D: evaluator and deterministic neo-loop created

Added the first immutable evaluator manifest and deterministic candidate lifecycle.

The initial `lab/EVALUATOR.json` recorded:

- Exact model identity.
- Baseline Neo3000 and upstream identities.
- Stable launch configuration.
- Candidate-editable paths.
- Protected paths.
- Smoke, tool, cancellation, memory, repeat, and context gates.

The initial `scripts/neo_loop.py` implemented:

```text
verify stable
verify candidate state
record baseline identity
build candidate separately
launch candidate separately
wait for health
run immutable probes
verify protected state
tear down candidate
verify stable again
record reject / reviewable-accept / inconclusive
never promote automatically
```

The task board was advanced from substrate construction to RSI-0E enforcement.

Representative commits:

- `d2c9ad4429a137299c2a0b89e809a1e6ef5a1b0d` — implement immutable evaluator and neo-loop machinery.
- `809932fb0d54fe6934fb7e2cd19d67865be774d0` — update task board with RSI-0 progress.

---

## 2026-07-02 — Checkpoint 0 baseline established and closed

### Standalone Neo3000 runtime foundation

Neo3000 was established as its own tracked repository and runtime rather than a traditional fork dependency or LM Studio wrapper.

Foundation work included:

- Pinned llama.cpp import manifest and upstream identity.
- Reproducible source import tooling.
- Windows CUDA build scripts.
- Stable server launch scripts.
- Baseline benchmark harness.
- Context-scaling harness.
- Rolling decode instrumentation.
- Task board, roadmap, active goal, checkpoint ledger, baseline protocol, and JSONL experiment log.
- Ignored local weights, builds, logs, runtime state, and benchmark outputs.

Verified build environment:

```text
CUDA Toolkit: 12.6
nvcc: 12.6.85
MSVC: 19.44.35227
CMake: 4.3.2
GPU: NVIDIA RTX 3060 12GB
CUDA architecture: SM 8.6
```

Built successfully:

- `build/stable/bin/Release/llama-server.exe`
- `build/stable/bin/Release/llama-bench.exe`

Stable API topology:

```text
Pi
-> http://127.0.0.1:9292/v1
-> Neo3000 stable server
-> Agents-A1 GGUF
```

### Agents-A1 serving and Pi compatibility proved

Verified:

- `/health`
- `/v1/models`
- OpenAI-compatible chat completions.
- Incremental SSE streaming.
- `reasoning_content` preservation.
- `neo3000_probe` tool calls with valid JSON arguments.
- Cancellation followed by immediate API recovery.
- Repeated turns without server degradation.

User-visible Pi proof completed:

- Exact streamed response: `NEO3000 PI ONLINE`.
- Real Pi tool round trip: Pi read `README.md`, returned its first heading, and Agents-A1 answered `Neo3000`.
- Pi-side cancellation during a long generation.
- Immediate post-cancellation recovery: `NEO3000 RECOVERED`.

### Context allocation and occupied-context behavior separated

Neo3000 established a strict evidence distinction:

```text
configured context capacity != actual occupied prompt tokens
```

Served-context allocation succeeded at:

- 4K
- 8K
- 16K
- 32K
- 40K
- 65,536 tokens

Measured occupied-context decode:

| Actual prompt tokens | Cached prompt TPS | Decode TPS |
|---:|---:|---:|
| 2,053 | 64.6 | 22.3 |
| 8,191 | 56.0 | 19.9 |
| 32,773 | 60.3 | 22.4 |
| 40,956 | 60.6 | 22.4 |
| 59,996 | 57.0 | 20.9 |

Result:

```text
60K / 2K decode ratio: 0.94
Observed degradation across ~60K occupied tokens: about 6%
```

This established that Agents-A1’s hybrid Qwen 3.5 MoE plus Gated Delta Net architecture maintained approximately flat decode throughput across the measured occupied-context range.

### Rolling minimum decode added

A 384-token decode with a 16-token rolling window showed no hidden sustained stalls:

| Occupied tokens | Average TPS | Minimum 16-token TPS | Min/avg |
|---:|---:|---:|---:|
| 2,053 | 19.1 | 18.4 | 0.96 |
| 32,773 | 18.3 | 16.9 | 0.92 |
| 59,996 | 18.6 | 17.1 | 0.92 |

The slowest rolling windows were only 4–8% below average, so average decode speed was not concealing severe transient collapse.

### Auto-fit hypothesis tested and rejected

Hypothesis:

```text
Automatic GPU placement is overly conservative and explicit layer counts can improve throughput.
```

Measured at 4K:

| Placement | Decode TPS | VRAM MiB |
|---|---:|---:|
| auto | 17.6 | 2,785 |
| explicit 20 layers | 10.0 | 1,892 |
| CPU only | 6.6 | 858 |

Verdict:

- Auto-fit was best among tested placements.
- The conservative-auto-fit hypothesis was rejected.
- Explicit layer forcing was not selected as an optimization direction.

### CPU-MoE tradeoff characterized

Measured at 4K with automatic placement:

| CPU-MoE | Decode TPS | VRAM MiB |
|---|---:|---:|
| enabled | 19.1 | 2,725 |
| disabled | 30.8 | 10,604 |

Result:

- Moving MoE work to GPU improved decode by about 62%.
- It consumed about 89% of total VRAM.
- CPU-MoE was retained as a space/speed control, especially when stable and candidate runtimes or larger context state must coexist.

### 40,960-token failure localized

An apparent tokenizer/context failure at the 40,960 target was investigated.

Findings:

- Direct `/tokenize` succeeded at approximately 197K and 599K tokens.
- The server remained healthy.
- The earlier matrix failure came from client-side timeout during a long uncached warmup, not a tokenizer or server defect.
- Rapid repeated binary-search tokenization calls could also exhaust Windows socket resources.
- The uncached 40K warmup took roughly nine minutes at about 73 prompt tokens per second, exceeding the former five-minute client timeout.

The harness timeout and evidence language were corrected rather than modifying the inference runtime for a nonexistent tokenizer bug.

### Throughput discrepancy explained

Different reported numbers were reconciled:

- About 8.2 TPS: cold first request, long reasoning-heavy completion.
- About 17.5–19.7 TPS: warm shorter completions.
- About 21.7–23.2 TPS: warm deterministic benchmark corpus.

The discrepancy was attributed to cold state, completion length, and reasoning-token overhead rather than contradictory runtime behavior.

### Checkpoint 0 closed

Checkpoint 0 closed only after build, model identity, API, Pi UI, tools, cancellation, repeated-turn, context, rolling-minimum, and characterization evidence were complete.

LM Studio was explicitly removed as an unlock gate. It may be used for optional historical comparison, but Neo3000 acceptance decisions compare a candidate against the previous accepted Neo3000 baseline under immutable evaluation.

Claim advanced to:

```text
NEO3000_BASELINE_OPERATIONAL
```

No catalytic inference claim was made.

Representative commits:

- `a5bef72de0c7b727abfed0b62cb6753beff8bbf8` — complete occupied-context baseline with auto-fit and CPU-MoE audits.
- `432e8f773cde782cab6d478ad5afccb15816cbb4` — align task board with the completed characterization head.
- `82c227037aea78dbaaa0f40ab403787106ac5b91` — close Checkpoint 0 with Pi UI evidence and rolling minimum decode.

---

## Architectural decisions retained

### Neo3000 judges Neo3000

LM Studio is not part of the RSI decision loop. Candidate acceptance is determined against the previous accepted Neo3000 state using the same hardware, model, evaluator, prompts, quality gates, and measurement law.

### Stable is never the experiment surface

Stable remains the daily-driver control intelligence. Every intervention belongs in an isolated candidate worktree, build directory, runtime directory, and port.

### The evaluator is outside candidate control

Candidates may not edit:

- Evaluator manifest.
- Evaluator lockfile.
- Controller.
- Task board.
- Roadmap.
- Checkpoint ledger.
- Active goal.
- Results ledger.
- Stable launch scripts.
- Model files or model identity.
- Promotion rules.

### Promotion remains human-controlled

A passing candidate may become `reviewable-accept`. It does not merge, push, replace stable, or promote itself.

### Meaningful architectural commits over pellet history

The Git history is intended to preserve Neo3000’s engineering memory. Source custody, isolation, evaluator construction, safety enforcement, proof cycles, and causal repairs are committed as coherent architectural chunks rather than fragmented administrative pellets.

---

## Rejected hypotheses and corrected assumptions

| Hypothesis or assumption | Result |
|---|---|
| Auto GPU placement was overly conservative | Rejected; auto-fit outperformed tested explicit layer counts. |
| The 40,960 target exposed a tokenizer/server limit | Rejected; the causal boundary was client timeout during long uncached inference. |
| Configuring 65,536 context proves 65,536 occupied prompt tokens | Rejected; allocation and occupancy are separate evidence. |
| LM Studio parity must gate RSI | Rejected; external comparison is optional characterization. |
| Initial tracked import contained all required source | Rejected; broad `models/` ignore omitted 171 legitimate source files. |
| Candidate builder drift caused CMake failure | Rejected; both build routes failed on the same missing source. |
| Original recorded model SHA-256 was exact | Rejected; a transposed sequence was corrected against measured bytes. |
| A read timeout during candidate model load means terminal health failure | Rejected; it means not-yet-healthy until the readiness deadline expires. |
| NVIDIA per-process memory telemetry is usable under this Windows WDDM driver | Rejected; NVML returns `[N/A]`, while PID-filtered WDDM dedicated-memory counters provide the required safety attribution. |

---

## Milestone commit index

| Commit | Milestone |
|---|---|
| `a5bef72` | Occupied-context baseline, auto-fit audit, CPU-MoE audit, timeout localization. |
| `432e8f7` | Characterization head reconciled in task board. |
| `82c2270` | Checkpoint 0 closed with Pi UI and rolling-minimum evidence. |
| `7ea6ffd` | Imported llama.cpp runtime entered direct Git custody. |
| `1c1bfe6` | Stable/candidate worktree and build/run isolation created. |
| `d2c9ad4` | Evaluator manifest and deterministic neo-loop core created. |
| `809932f` | RSI-0 progress recorded and RSI-0E opened. |
| `f55e511` | Tracked supervised RSI operator prompt added. |
| `a186d59` | Roadmap, task board, and active boundary aligned. |
| `cac80b0` | Candidate safety, lock, allowlist, timeout, memory, and isolation gates enforced. |
| `9e51079` | Live supervised rejection cycle proved. |
| `1628695` | Source-custody omission repaired; CMake diagnostics improved. |
| `816f6e9` | Agents-A1 evaluator identity corrected and locked. |
| `d911f93` | Candidate health-probe timeout handling repaired. |
| `a94d973` | Unavailable NVML telemetry became an explicit hard rejection. |

---

## Changelog maintenance law

Add an entry when pushed evidence changes one of the following:

- Supported claim ceiling.
- Checkpoint state.
- Runtime architecture.
- Evaluator or promotion law.
- Stable/candidate isolation.
- Model or source identity.
- Reproducible performance evidence.
- Accepted or rejected causal hypothesis.
- Safety boundary.
- Proven rejection or acceptance cycle.
- Exact next boundary.

Do not record an item as completed merely because it was proposed, described, or attempted. Failed cycles belong here when they expose and repair a real architectural boundary.
