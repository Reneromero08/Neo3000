# Neo3000 Roadmap

## Purpose

This is the durable navigation spine for Neo3000. Any agent should be able to enter the repository, identify the current boundary, preserve the stable daily driver, and continue without reconstructing the project from chat history.

Neo3000 is a performance-first local inference engine for Agents-A1. It began from a pinned `llama.cpp` runtime and is evolving toward catalytic, phase-native, recursively reusable inference.

The objective is to reduce fresh computation per useful token while preserving model capability, Pi compatibility, reproducibility, and daily-driver stability.

---

# 1. Read order and authority

Every agent must read:

```text
1. AGENTS.md
2. TASKS.md
3. ROADMAP.md
4. docs/CATALYTIC_RUNTIME_ROADMAP.md
5. lab/GOAL.md
6. lab/CHECKPOINT.md
7. lab/EVALUATOR.json, when present
8. lab/BASELINE_PROTOCOL.md
9. lab/results.jsonl
10. NEO3000.md
11. README.md
```

| File | Authority |
|---|---|
| `AGENTS.md` | Operating law, non-collapse protocol, engineering rules, stop conditions |
| `TASKS.md` | Executable queue and exact next action |
| `ROADMAP.md` | Phase order, unlock gates, long-range architecture |
| `docs/CATALYTIC_RUNTIME_ROADMAP.md` | Authoritative detailed catalytic architecture, carrier hierarchy, swarm phase order, metrics, and claim discipline |
| `lab/GOAL.md` | One active bounded objective |
| `lab/CHECKPOINT.md` | Evidence ledger for the active checkpoint |
| `lab/EVALUATOR.json` | Candidate-cycle evaluation contract |
| `lab/BASELINE_PROTOCOL.md` | Baseline measurement procedure |
| `lab/results.jsonl` | Compact experiment history |

When documents disagree:

1. executed evidence outranks prose
2. `TASKS.md` determines the next operation
3. `lab/CHECKPOINT.md` determines what is proven
4. `lab/GOAL.md` determines the current bounded objective
5. this roadmap determines phase order and RSI unlock level
6. `docs/CATALYTIC_RUNTIME_ROADMAP.md` determines detailed catalytic architecture within that phase order
7. architecture documents do not prove implementation status

---

# 2. Current state

## Checkpoint 0: CLOSED

Claim:

```text
NEO3000_BASELINE_OPERATIONAL
```

Proven foundation:

```text
CUDA 12.6 build on RTX 3060
Agents-A1 GGUF identity and full hash
OpenAI-compatible health, model, and chat endpoints
incremental SSE streaming
reasoning_content preservation
tool-call probe validity
real Pi UI stream
real Pi tool round trip
Pi-side cancellation and immediate recovery
server allocation through 65,536 context capacity
occupied-context inference through 59,996 prompt tokens
rolling minimum decode speed with no significant transient stalls
```

The strongest occupied-context result is:

```text
2,053 prompt tokens: 22.3 decode TPS
59,996 prompt tokens: 20.9 decode TPS
occupied-context degradation ratio: 0.94
```

Allocation capacity and occupied prompt length are separate evidence types. A configured `--ctx-size 65536` proves allocation capacity; `usage.prompt_tokens` proves occupied context.

LM Studio is **not** an unlock dependency. It may be used as optional historical characterization, but Neo3000 acceptance and RSI decisions are measured against prior accepted Neo3000 commits.

## Current exact boundary

```text
RSI-0: CLOSED
-> SUPERVISED_BOUNDED_RSI_AVAILABLE unlocked for Level 1 supervised work
-> Checkpoint 1A: trace substrate remains active and paused
-> Checkpoint 2: ACTIVE; v4 executed once, Fast reviewable-accept, Deep reject
-> First catalytic intervention: HoloState-v1 Live Prefix Lattice
-> HoloState worker v1: instrumentation reject; Fast/Deep capability untested
-> HoloState worker v2: executed once; inconclusive at readiness before canary
-> HoloState worker v3: readiness pass; canary instrumentation reject; Fast/Deep untested
-> HoloState worker v4: reviewable-accept; process-local micro-worker unlocked
-> CatalyticSwarm-0: executed once; control qualification pass, readiness inconclusive on exact-PID WDDM telemetry loss before canary
-> CatalyticSwarm-0 v2: separately authorized telemetry successor; not yet executed
```

The global claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`. The separate mechanism status `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` records what HoloState-0 demonstrated without claiming restart persistence.

No autonomous RSI. No automatic promotion. No stable inference modification outside declared candidate cycles.

## Catalytic runtime architecture summary

`docs/CATALYTIC_RUNTIME_ROADMAP.md` is the authoritative detailed architecture;
this section is only its navigation capsule.

- **Experiment 08:** carry forward the bounded lease-pool law: a logical worker population may exceed physical residency by acquiring, using, closing, and releasing a fixed slot pool. The experiment did not prove 1,000 simultaneously resident independent models or restoration of arbitrary unknown state.
- **Experiment 13:** carry forward logical phase, worker, channel, and root-routing identities. Its models occupied different physical tape regions, so it did not prove that opaque KV or recurrent states can overlap in the same bytes and be recovered independently.
- **HoloState carrier hierarchy:** exact live prefix state is proven process-locally; a bounded logical swarm over live leases is the current control boundary; expert residency, recurrent trajectory state, executable CUDA-graph/warm-runtime state, and verified blackboard state are later carriers. Only exact identity-bound state may survive closure.
- **Current boundary:** CatalyticSwarm-0 v1 executed exactly once. Generation-free control qualification passed; readiness stopped `inconclusive` on exact-PID WDDM telemetry loss before the parser canary, capability attempt, lease, ledger, blackboard, or any worker request. V1 is immutable and no-retry; structured-micro-worker and swarm-control availability remain locked.
- **Authorized successor:** `catalytic_swarm_0_v2` is authorized but not executed. Its sole causal intervention is bounded transient exact-PID WDDM query resilience plus fresh-sample admission. The 32-worker plan, prompts, seeds, parent graph, one-slot lease law, parser, verifier, blackboard, and 64-token Fast budget remain unchanged.

| Swarm stage | Architectural purpose | Unlock boundary |
|---|---|---|
| CatalyticSwarm-0 | Prove the bounded 32-logical-worker, one-physical-lease control plane | Structured micro-worker and swarm-control availability |
| CatalyticSwarm-1 | Compare single, best-of-N, sparse swarm, and verified swarm under equal total budgets | Verified task advantage, not ordinary speed alone |
| CatalyticSwarm-2 | Expand and stop the logical population from verified marginal value | Adaptive population and verifier allocation |
| CatalyticSwarm-3 | Preserve logical agents across restart only after durable capsules pass | Restart-persistent identity-bound state |
| CatalyticSwarm-4 | Add heterogeneous models, quantizations, adapters, and specialist verifiers | Role-specific capability with declared boundaries |

- **Durable HoloState:** v2 must persist KV/recurrent state plus checkpoint-selection metadata, token history, complete identities, nearest-checkpoint recovery, and exact restart A/B validation. V3 tiers live/pinned-host/host/disk state; v4 forms a content-addressed branching execution tree. None is currently proven.
- **Native carrier lanes:** MoE work must first measure expert routes, buckets, padding, transfer, and residency; Gated Delta Net work must measure state identity, update/copy/restore cost, location, and exact fidelity; CUDA-graph work must measure capture signatures, replay, reconstruction, synchronization, and reuse across prefix boundaries. A low-level speedup is catalytic only when it lawfully retains and reuses executable structure.
- **True orthogonal state:** a later experiment must encode independent channels in the same physical cells, decode them reversibly with bounded cross-talk, restore the substrate, and beat a disjoint-region control after encoding overhead. Until then, orthogonality is a logical routing device only.
- **Metrics and claims:** report compute amplification, fresh-compute ratio, state-reuse yield, closure cost, carrier reuse count, prefix-hit depth, holographic branch density, expert-residency yield, and blackboard yield. Separate observed from quality-accepted reuse, live from durable state, and task advantage from speedup. No restart-persistence, task-advantage, SOTA, physical-infinity, v2-execution, or automatic-promotion claim is currently allowed.

---

# 3. Standing architecture

## Stable daily-driver path

```text
Pi
-> http://127.0.0.1:9292/v1
-> stable Neo3000 server
-> Agents-A1 GGUF
-> streamed reasoning, content, and tools
```

The stable server is the control intelligence for candidate work. It must remain available while candidates are built and tested.

## Candidate path

```text
stable source identity
-> isolated candidate worktree
-> one causal intervention
-> candidate build directory
-> candidate server on separate port, default 9393
-> immutable evaluator
-> quality, stability, memory, timeout, hash, path, and performance gates
-> reject, accept for review, or remain inconclusive
-> candidate teardown
-> stable health verification
```

A candidate never replaces the stable runtime merely because it compiles or runs faster once.

## Catalytic compute primitive

```text
borrow existing compute state
-> transform through one or more trajectories
-> extract a surviving result or invariant
-> restore or close temporary state
-> retain only lawful durable state
```

Algorithms are local traces through a larger process-object. Do not collapse phase-native, topological, spectral, recurrent, or relational proposals into scalar candidate ranking unless that reduction is the declared experiment.

## Performance substrate and catalytic compute

Both lanes belong to Neo3000, but they prove different things:

```text
Performance substrate:
  reduce the cost of ordinary inference

Catalytic compute:
  reduce how much fresh ordinary inference is required
```

A conventional CUDA optimization may be accepted during Level 1 when it passes the immutable evaluator. It does not satisfy a catalytic checkpoint unless it explicitly implements `borrow`, `transform`, `extract`, `restore or close`, and retention of only lawful durable state.

## Future runtime profiles

These profiles are architectural directions, not implemented or measured claims.

### Fast profile

Purpose: maximum short-context interactive speed.

Direction: one active server, GPU-heavy MoE placement, context sized to available VRAM, and no reserved candidate capacity. The maximum stable context for this profile is unknown until measured.

### Long profile

Purpose: large occupied context.

Direction: CPU-MoE or mixed expert placement, a larger context-state allowance, and lower VRAM pressure.

### RSI profile

Purpose: stable and candidate coexistence.

Direction: stable remains resident, candidate stays below the locked WDDM ceiling, CPU-MoE placement remains conservative, and ports, builds, and runtime state remain isolated.

---

# 4. RSI levels

## Level 0: Pi-assisted development [COMPLETED OPERATING LEVEL]

Pi can inspect files, write code, build, and run commands, but the human still defines and supervises each development step.

This operating level is complete. Its baseline and Pi gates remain protected foundations for later work.

## Level 1: Supervised bounded RSI [CURRENT OPERATING LEVEL]

Agents-A1 may improve a candidate Neo3000 through a deterministic loop, but:

```text
stable server remains untouched
one candidate mechanism is tested at a time
benchmark and controller hashes are immutable
candidate edit paths are enforced
failed candidates are torn down
promotion requires human review
cycle count is bounded
```

This level is unlocked because Checkpoint RSI-0 is closed.

## Level 2: Autonomous bounded RSI [LOCKED]

Agents-A1 may execute several candidate cycles from a declared goal without manual command execution. It may revise or stop based on measured results, but may not automatically replace stable.

This level unlocks when Checkpoint 5 closes.

## Level 3: Recursive compute amplification [LONG-RANGE TARGET]

Useful computation survives as executable state and reduces equivalent future compute, rather than only improving source code between runs.

This is the long-range target of Checkpoint 7.

---

# 5. Phase roadmap

## Checkpoint 0: Baseline parity and occupied-context characterization

Status: **CLOSED**

Exit gate met:

```text
Agents-A1 runs through Pi on Neo3000
and
streaming, tools, cancellation, and repeated turns are stable
and
occupied-context behavior is characterized through 60K
and
allocation capacity is documented separately from occupied context
and
rolling minimum decode speed is recorded
and
source custody model is selected
```

LM Studio comparison is optional characterization and not a gate.

---

## Checkpoint RSI-0: Self-improvement substrate

### Objective

Create the minimum safe substrate required for Pi to perform supervised recursive self-improvement on Neo3000.

This checkpoint does not require the compute map or a successful catalytic mechanism. It creates the machinery through which later checkpoints can be investigated recursively.

### RSI-0A: Source custody

Status: **DONE**

Selected model: track the pinned imported runtime as one deliberate source-baseline commit.

Required properties:

```text
ordinary Git diffs
candidate worktrees
clean rollback
exact source identity
upstream license preserved
```

### RSI-0B: Stable and candidate isolation

Status: **DONE**

Required structure:

```text
stable worktree
stable build directory
stable server port 9292

candidate worktree
candidate build directory
candidate server port 9393

separate runtime-state directories
immutable evaluator outside candidate-editable paths
```

Live rejection and reviewable-acceptance cycles proved stable health through candidate build, run, failure, acceptance, and teardown.

### RSI-0C: Immutable evaluator

Status: **DONE**

Required:

```text
EVALUATOR.json
EVALUATOR.lock.json or equivalent protected-hash lock
benchmark prompt hashes
quality-gate hashes
controller hashes
protected path list
candidate-editable path list
model identity
baseline commit
stable launch configuration
```

Before and after every candidate cycle, `neo-loop` verifies protected hashes. Mutation invalidates the candidate.

### RSI-0D: Deterministic neo-loop

Status: **DONE**

`neo-loop` must perform:

```text
read TASKS, GOAL, and CHECKPOINT
-> verify stable health
-> verify clean candidate worktree
-> record baseline commit and evaluator hashes
-> receive one causal hypothesis
-> enforce candidate-editable paths
-> build candidate separately
-> launch candidate on separate port
-> wait for health with timeout
-> run immutable quality gates
-> run immutable performance and memory gates
-> record all results
-> stop candidate
-> remove candidate runtime state
-> verify stable health again
-> classify reject, reviewable accept, or inconclusive
```

### RSI-0E: Stop and isolation gates

Status: **DONE**

Required gates:

- stable worktree cannot be modified by the candidate cycle
- stable server cannot be stopped by the candidate cycle
- stable and candidate ports cannot collide
- stable and candidate build directories cannot overlap
- candidate cannot rewrite evaluator or controller files
- candidate cannot change model weights or model identity
- candidate cannot push or promote itself
- process timeout is enforced
- memory ceiling is enforced
- repeated crash ceiling is enforced
- benchmark mutation causes immediate rejection
- malformed text, reasoning, or tools cause rejection
- cancellation or repeated-turn regression causes rejection
- unexplained memory growth causes rejection
- candidate process is torn down after every result
- stable health is checked before and after every cycle

### RSI-0F: Supervised rejection cycle

Status: **DONE**

Agents-A1 makes one bounded candidate change that deliberately or naturally fails a declared gate.

Pass conditions:

```text
candidate is rejected
candidate process is removed
stable server remains healthy
stable files remain unchanged
failure is recorded accurately
next task remains resumable
```

### RSI-0G: Supervised acceptance cycle

Status: **REVIEWABLE ACCEPT**

Agents-A1 makes one bounded candidate change that passes all declared gates.

Pass conditions:

```text
candidate is marked reviewable
stable is not automatically replaced
human can inspect exact diff and evidence
stable server remains healthy
accepted result is recorded
```

The acceptance cycle may use a small non-performance change if no safe performance intervention is ready, but it must exercise the complete source, build, launch, evaluate, and teardown path.

### RSI-0H: Operator prompt

Status: **DONE**

Tracked prompt:

```text
prompts/supervised_rsi_cycle.md
```

### RSI-0 exit gate

Status: **CLOSED**

```text
engine source is Git-diffable
and
stable and candidate are proven isolated during build and run
and
benchmark and controller immutability are enforced
and
one supervised rejection cycle succeeds safely
and
one supervised acceptance cycle succeeds safely
and
stable survives both cycles
and
results and handoffs remain accurate
```

### Unlock [ACHIEVED]

Closed RSI-0 evidence unlocked:

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

Pi may then be prompted to run one bounded supervised candidate cycle with human promotion review.

Automatic stable promotion remains forbidden.

---

## Checkpoint 1: Compute map

Status: **ACTIVE**

Active bounded objective:

```text
Checkpoint 1A:
Create and validate one optional compute-map trace substrate, then use it to localize actual backend placement and the first measurable execution costs.
```

Checkpoint 1 uses the unlocked supervised RSI substrate while stable remains untouched.

The compute map must distinguish:

```text
cold-start initialization
reasoning-token overhead
attention and KV traffic
Gated Delta Net recurrent state
MoE expert routing
expert residency and transfer
CPU-MoE execution
GPU placement changes caused by configured context capacity
occupied-context state growth
prompt-cache reuse
CUDA kernel occupancy
CPU and GPU synchronization
sampling and server overhead
```

Exit gate: the top one or two causes of short-context cost and long-context cost are causally localized rather than inferred from correlation.

### Checkpoint 1A: Trace substrate [ACTIVE / PAUSED]

Create one fixed, versioned trace schema. Trace is disabled by default, normal builds compile trace calls out, the trace-enabled build is separate, local trace artifacts remain ignored, timestamps are monotonic, event IDs are stable, and instrumentation overhead is measured.

The current pause preserves proven trace-disabled compile-out, bounded aggregation, protected exact-PID launch control, and explicit truncation/drop detection. Trace overhead, a completed workload compute map, and causal model-runtime bottleneck selection remain unproven.

### Checkpoint 1B: Backend placement and fallback

Measure expected and actual backend, device ID, operator identity, tensor shape, any available CUDA-rejection reason, intentional CPU-MoE versus accidental CPU fallback, and host/device transfer caused by fallback.

### Checkpoint 1C: CUDA graph lifecycle and synchronization

Measure graph capture, replay, reconstruction, shape signature, allocator growth, CUDA stream, explicit and device-to-host synchronization, first-request initialization, and steady-state execution.

### Checkpoint 1D: MoE geometry

Measure active expert IDs, route rank, tokens per expert, largest/mean/distribution of expert buckets, `MUL_MAT_ID` backend, selected MMQ tile geometry, estimated inactive or padded MAC work, activation quantization cost, and expert-weight residency and transfer.

### Checkpoint 1E: Gated Delta Net recurrent state

Measure state bytes per layer, allocation, update and copy duration, CPU/GPU residence, host/device transfers, synchronization, cost per token, and exact snapshot/restore cost.

### Checkpoint 1F: Causal bottleneck selection

Exit only after identifying one or two dominant short-context costs, one or two dominant long-context costs, a measured causal mechanism, and one bounded first intervention. Correlation alone cannot select the intervention.

### Immediate parallel boundary: HoloState-0 capability audit

HoloState-0 asks whether already-available server facilities can preserve and reuse an exact Agents-A1 executable prefix without reevaluating the full prefix. It audits bounded host-RAM reuse, context checkpoints, branch multiplexing, slot save/restore, and conditional process-restart restore through one isolated sidecar. It does not integrate upstream source, alter stable, activate Checkpoint 2, or prove Gated DeltaNet hybrid-state persistence from KV behavior alone.

If deterministic output agreement and measured prompt-token reuse prove exact executable hybrid-state reuse, HoloState-0 may nominate HoloState-v1 Live Prefix Lattice as the first Checkpoint 2 intervention. Otherwise it records the narrower capability or failure boundary without changing the claim ceiling.

HoloState-0 result: the existing hybrid runtime exactly reused 7,387 of 7,519 rendered prompt tokens across identical and A/B/A/B process-local branches, with identical greedy token IDs and raw pre-final/final output per branch. The legacy pre-final hash is not `reasoning_content` channel proof. A 231,311,464-byte slot file restored 8,069 tokens in-process, but live RAM/checkpoint state confounds attribution to the file. After process restart the same file was read successfully yet all 7,519 prompt tokens were reevaluated. Therefore exact process-local RAM/checkpoint reuse is proven and may be operationalized as HoloState-v1 Live Prefix Lattice.

Restart-persistent executable-state reuse remains unproven and is separated as HoloState-v2 Durable Capsule.

### External architecture leads, not dependencies

Source: `alesha-pro/llama.cpp`, `ds4-longctx` branch. Use: provenance and candidate hypotheses only. Prohibition: no wholesale merge, source replacement, or DeepSeek-specific code assumption.

- **Actual-bucket MoE MMQ sizing:** worst-case expert tile sizing may execute padded or inactive CUDA work. Measure expert bucket geometry and selected tiles before any port.
- **Silent CPU fallback detection:** an unsupported tensor shape may silently move a hot operator to CPU. Expose intentional and accidental CPU execution separately.
- **Constant-shape CUDA graph replay:** some reconstruction may be removable when exact state growth can be separated from executable graph shape. Do not change fidelity or truncate effective context.
- **Mixed-quant expert residency:** lower-bit experts may allow more MoE compute to remain on GPU while preserving higher precision for attention and recurrent state. This requires full tool, reasoning, quality, and model-behavior evaluation.
- **Recurrent-state shadows and speculation:** future catalytic form is `borrow` an exact Gated Delta Net snapshot; `transform` through draft and verification trajectories; `extract` accepted tokens or an invariant; `restore` exact recurrent state after rejection; `retain` only accepted state transitions. This remains locked until state size, copy cost, location, and restoration feasibility are measured.
- **Fused MoE operations:** lower priority until profiling shows grouping, quantization, or repeated activation work is material.

---

## Checkpoint 2: First catalytic compute intervention

Status: **ACTIVE**

First intervention: **HoloState-v1 Live Prefix Lattice**

```text
expensive operation:
  canonical-prefix prompt evaluation

borrowed carrier:
  exact process-local hybrid prefix state

transformation:
  evaluate one divergent suffix or branch

extracted result:
  deterministic reasoning, final content, or tool call

restoration or closure:
  preserve the canonical checkpoint lattice for later branches

retained lawful state:
  model/configuration/prefix-identity-bound live cache entries
```

HoloState-v1 is the current process-local integration. It keeps multiple immutable canonical roots available inside one exact long-lived sidecar and revisits them through identity-bound checkpoint/RAM reuse. It does not modify llama.cpp inference kernels and does not claim survival across a process restart.

HoloState-v2 Durable Capsule is the future restart-persistence intervention. Its carrier and recovery law remain unproven.

### HoloState-v1 integration result: INCONCLUSIVE

The protected controller warmed two immutable roots on one exact sidecar: A at 7,150 rendered tokens and B at 4,879. The first A1 branch evaluated only 148 fresh tokens in 3,685.92 ms after its 159,051.535 ms full warm, an observed 43.151x prompt-time amplification. The server log supports 7,165 logical prompt tokens and 7,017 reused tokens for that request.

The A1 request then consumed all 768 allowed completion tokens without closing the declared deterministic output gate. Stop-on-first-failure ended the sequence before B1/A2/B2, same-branch hash comparison, eviction observation, or the extended proof. No retry occurred. HoloState-v1 Live is therefore `inconclusive`, `PROCESS_LOCAL_HOLOSTATE_AVAILABLE` remains locked, and the HoloState-0 mechanism status `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` remains the narrower supported claim.

The causal boundary is split correctly: the HoloState-v1 reuse mechanism succeeded, while the legacy raw-output quality gate did not close. The one-shot qualification tested `1024, 1280, 1536, 2048` in ascending order on one Root A/A1 sidecar. Every raw `/completion` stream reused 7,878 of 8,026 logical prompt tokens, consumed its exact limit, and ended without `HOLOSTATE A1 EXACT`. Because `/completion` exposed one raw content stream and the legacy parser labeled all raw output as reasoning when the marker was absent, those runs do not prove that every token belonged to `reasoning_content`. No budget qualified, no budget was selected, and validation-v2 did not run.

### HoloState-v1.1 message-boundary protocol: EXECUTED

Protocol commit `3fb00fe93d0fb22e203d8e26d86173f5e3d2ee32` locked `/v1/chat/completions`, a canonical system/reference root plus separate user assignment, 64-token thinking-disabled Fast workers, and one 768-token reasoning-auto Deep probe. Internal reasoning remained opaque.

The authorized one-shot audit ran once and stopped at Root A warm. Root A rendered 7,806 tokens and returned exact visible content `HOLOSTATE ROOT WARM`, empty reasoning metadata, `finish_reason=stop`, and matching prompt identity. The required complete generated-token array was not retained by the parser, so `completion-token-evidence-missing` rejected the warm before Fast A1. Root B and Deep were not attempted.

Pinned source establishes the instrumentation diagnosis: streaming partial results carry token IDs, while the final streaming result carries an empty array. The executed parser replaced each observed array, so the final empty value erased prior token evidence. Raw SSE events were not persisted; this is therefore a source-based diagnosis, not direct event replay. Result SHA-256 is `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2`.

The ignored result preserves its original locked fields (`FAST=reject`, `DEEP=inconclusive`). Later adjudication classifies v1 itself as an instrumentation reject; Fast capability is untested/inconclusive and Deep capability is untested/inconclusive because neither lane ran. Sidecar PID `34580` peaked at 2,252.88 MiB over 73 exact-PID samples and retired cleanly. All availability locks remain intact.

Do not retry v1. Separately authorized v2 changed only token-array accumulation and bounded stream provenance, placed a parser canary before warming roots, and used new attempt/result/ledger paths. Its fixed sequence was canary, warm A/B, A1/B1/A2/B2, A1/B1 repeats, Deep A1, stop; no automatic retry or extended proof.

### HoloState worker protocol v2: EXECUTED / INCONCLUSIVE

Protocol commit `b2559f7c0c06e35a3e360b71ed13b69c4eb1eb7c` passed the protected pre-audit suite and was pushed before the one-shot marker was claimed. The live controller launched sidecar PID `37804`, then a protected query for stable listener ownership timed out during readiness. Admission failed before the parser canary, so no root warm and no Fast or Deep request was attempted. This is a readiness-control boundary, not evidence about the repaired parser or model capability.

The empty stream ledger is itself bounded evidence: 0 records, 0 bytes, SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`. Cleanup passed, port 9494 retired, five exact-PID WDDM retirement samples were empty, stable PID `32684` remained healthy, and all historical evidence remained exact. V2 is no-retry. Every HoloState availability state, CatalyticSwarm-0, and automatic promotion remain locked.

### CatalyticSwarm-0 bounded control: EXECUTED ONCE / READINESS INCONCLUSIVE

The executed v4 boundary unlocked only bounded thinking-disabled process-local micro-workers. CatalyticSwarm-0 froze a deterministic control proof over that carrier: 32 logical workers in proposal/evidence/critique/synthesis phases, one physical HoloState slot, exact assigned-parent communication through compact append-only objects, deterministic verifier receipts, 64-token maximum, and no automatic promotion.

Exact integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280` was pushed as protected `main` and passed protected preflight before the one authorized invocation. Generation-free control qualification passed. Readiness then stopped as `inconclusive` when an exact-PID WDDM counter query timed out after 6 valid samples and a 92.84 MiB peak for sidecar PID `44748`; the failure classification is `candidate-vram-telemetry-lost`.

The parser canary and capability attempt were not attempted. No 32-worker request, physical lease, bounded-ledger record, or blackboard entry exists. Lifecycle teardown and retirement passed: PID `44748` stopped, port 9494 retired, and stable PID `32684` remained healthy. The composite cleanup/resource gate is false because exact-PID WDDM telemetry was lost. Readiness, structured-micro-worker capability, and swarm-control capability are each `inconclusive`; both new availability states remain locked. The existing process-local micro-worker unlock survives, while broader process-local HoloState, restart persistence, task advantage, and SOTA remain locked. V4 evidence is preserved and automatic promotion remains false.

This invocation is no-retry. Its exact early-stop evidence is bound as `neo-exp-0019` in the protected evaluator/result/lock for the evidence commit. No further CatalyticSwarm live work is authorized: preserve v1 and await explicit authorization for any separately versioned successor addressing exact-PID WDDM telemetry loss. Deep, persistence, CUDA/kernel/model/Pi/stable changes, and promotion remain excluded.

### HoloState-v2 persistence boundary

The built-in slot file persists active KV/recurrent state and token history, but does not persist the server prompt-checkpoint list required for hybrid recurrent prefix selection after restart.

Upstream provenance is recorded without cherry-pick or port:

```text
ggml-org/llama.cpp PR 20819
ggml-org/llama.cpp PR 20955
ggml-org/llama.cpp PR 24028
```

The future persistence candidate should combine:

```text
checkpoint-list sidecar persistence
identity/version checks
nearest-checkpoint recovery when recurrent truncation is unsupported
exact restart A/B validation
```

HoloState-v2 persistence remains a separate future intervention. It is not the current next action and is not a prerequisite for the repaired HoloState-v1 quality proof.

Remove or reuse one measured source of fresh computation while preserving Pi compatibility and model behavior.

Checkpoint 2 remains the first catalytic intervention checkpoint. Conventional instrumentation and CUDA substrate improvements may be accepted during Checkpoint 1, but a conventional speedup does not close Checkpoint 2 without a declared borrow, transform, extract, and restoration law.

Every intervention must name:

```text
expensive operation
borrowed carrier
transformation
extracted output or invariant
restoration or closure law
expected speed mechanism
quality gates
measurement that rejects the hypothesis
```

Possible families, selected only from evidence:

- cold-start state reuse or pre-initialization
- catalytic expert residency
- recurrent-state catalysis
- single-model catalytic speculation
- holographic long-context side channel
- layer-orbit closure

---

## Checkpoint 3: Long-context catalytic state

Flatten occupied-context cost while preserving executable relational structure.

Controls:

- full exact context
- exact recent window plus side channel
- side channel disabled
- side channel shuffled
- equivalent-memory baseline

---

## Checkpoint 4: Layer-orbit closure and trajectory invariants

Determine whether hidden-state evolution becomes predictively closed before the final layer.

Confidence alone is not a closure law.

---

## Checkpoint 5: Autonomous bounded RSI

Advance from supervised candidate cycles to several autonomous candidate cycles from one declared goal.

Additional gates beyond RSI-0:

- several cycles complete without manual command execution
- cycle budget and wall-clock budget are enforced
- repeated non-improvement stops the run
- false success reporting is detected by evaluator evidence
- branch and result state remain resumable after interruption
- candidate crashes do not interrupt stable inference
- model cannot modify its own goal, evaluator, controller, or promotion law during a run

Automatic promotion remains disabled.

Unlock:

```text
AUTONOMOUS_BOUNDED_RSI_AVAILABLE
```

---

## Checkpoint 6: Native catalytic kernels

Move selected hot-path transitions into exact borrow, transform, extract, and restore form.

Start with operations whose inverse or closure is exact and performance-relevant.

---

## Checkpoint 7: Recursive compute amplification

Allow useful computation to return as substrate or operator for later inference.

Central metric:

```text
compute amplification = equivalent baseline compute / fresh compute executed
```

This metric must be grounded in removed or reused operator work. Wall-clock speed alone is insufficient.

---

# 6. Handoff law

Before an agent stops, it must leave the repository resumable.

Update only what changed:

1. `TASKS.md` so the next unchecked item is real
2. `lab/CHECKPOINT.md` with proven gates
3. `lab/GOAL.md` with the next exact action
4. `lab/results.jsonl` when an experiment ran
5. this roadmap only when phase order, unlock law, or architecture changed

The final handoff must state:

```text
branch
full HEAD commit
working-tree status
stable server command
candidate command, if any
stable and candidate ports
model identity
checkpoint and RSI level
last executed test
result
failed or inconclusive mechanisms
files changed
next exact command
known risks
```

Never end with only a narrative report while the task board remains stale.

---

# 7. Commit law

Use meaningful architectural commits. Avoid micro-commit pellets.

Never commit:

- model weights
- build products
- local absolute paths
- runtime logs
- benchmark caches
- temporary prompts
- secrets
- Pi credentials

A build is not proof of correctness. A faster run is not proof of a mechanism. A negative result is valid when it maps the Wall and leaves stable intact.
