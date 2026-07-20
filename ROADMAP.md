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
-> CatalyticSwarm-0 v2: structured micro-worker and bounded swarm control reviewable-accept
-> CatalyticSwarm-1: executed once; inconclusive on the first serial-chain comparison before any task completed
-> CatalyticSwarm-1 cache-admission diagnostic: executed once / reviewable-accept / no retry; exact public-root reuse proven for both probes
-> CatalyticSwarm-1 v2: command attempt consumed / preclaim fail-closed / zero requests / no retry
-> CatalyticSwarm-1 v3: command invocation consumed / preclaim fail-closed / one control artifact / no retry
-> CatalyticSwarm-1 v4: executed once / partial 775 requests / inconclusive / consumed / no retry
-> CatalyticSwarm-1 v5: executed once / 775 completed and durably represented / record 775 rejected / consumed / no retry
-> CatalyticSwarm-1 v6: consumed at runtime-preclaim / harness self-contamination / zero requests / no retry
-> Track A claim verification: PAUSED; no CS1-v7 authorized or planned
-> Track B mechanism discovery: deterministic rank-head CK0 v2 replicated across two private bindings; the executed position-seed crossover supports a matched-binding presentation-position effect; the completed AB/BA probe supports a unique-intersection-like transform under one binding and seed; a frozen four-request hard out-of-sample successor now jointly changes one private binding and one commit-derived seed, while separate seed/binding invariance and all broad claims remain locked
```

The global claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`. The separate mechanism status `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` records what HoloState-0 demonstrated without claiming restart persistence.

No autonomous RSI. No automatic promotion. No stable inference modification outside declared candidate cycles.

## Catalytic runtime architecture summary

`docs/CATALYTIC_RUNTIME_ROADMAP.md` is the authoritative detailed architecture;
this section is only its navigation capsule.

- **Experiment 08:** carry forward the bounded lease-pool law: a logical worker population may exceed physical residency by acquiring, using, closing, and releasing a fixed slot pool. The experiment did not prove 1,000 simultaneously resident independent models or restoration of arbitrary unknown state.
- **Experiment 13:** carry forward logical phase, worker, channel, and root-routing identities. Its models occupied different physical tape regions, so it did not prove that opaque KV or recurrent states can overlap in the same bytes and be recovered independently.
- **HoloState carrier hierarchy:** exact live prefix state is proven process-locally; a bounded logical swarm over live leases and a verified append-only blackboard are proven at the 32-worker control boundary; expert residency, recurrent trajectory state, and executable CUDA-graph/warm-runtime state are later carriers. Only exact identity-bound state may survive closure.
- **Preserved predecessor:** CatalyticSwarm-0 v1 executed exactly once. Generation-free control qualification passed; readiness stopped `inconclusive` on exact-PID WDDM telemetry loss before the parser canary, capability attempt, lease, ledger, blackboard, or any worker request. V1 is immutable and no-retry.
- **Current boundary:** `catalytic_swarm_0_v2` completed one artifact-claiming live execution from protected integration commit `cf61f90ff5544f2f8bc546e5d661ea72cdda8666`. No retry occurred after claim; one earlier pre-claim command refusal created zero artifacts and made zero model requests. Its sole causal intervention was bounded transient exact-PID WDDM query resilience plus fresh-sample admission; the inherited 32-worker plan, prompts, seeds, parent graph, one-slot lease law, parser, verifier, blackboard, and 64-token Fast budget remained unchanged. All 32 workers and the 16/8/6/2 control sequence passed, so structured-micro-worker and bounded swarm-control availability are unlocked at `reviewable-accept`.
- **Executed successor:** CatalyticSwarm-1 ran exactly once from protected commit `556bb4d57a05bb81fa101a98092472170b50c0dd` at unchanged complete-contract SHA-256 `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`. Control, readiness, the generation-free parser canary, and the first common-root warm passed. The first serial-chain comparison completed a response but did not prove reuse of the complete public root, so the fail-fast law stopped after 2 model requests: 1 warm, 1 comparison, and 0 completed tasks.
- **Executed diagnostic:** the separately versioned cache diagnostic executed exactly once: 3 requests, `reviewable-accept`, cache 4,822 covering root terminal 4,820 for both probes, and legacy threshold 4,825 overextended by five tokens. It is diagnostic-only and cannot unlock task advantage or SOTA.
- **Consumed boundary:** CS1-v2 stopped before artifact claim because inherited v1 qualification compared its v2 tuple against v1 paths. It made zero model requests, launched zero sidecars, claimed zero artifacts, and is no-retry.
- **Consumed v3 boundary:** the one authorized CS1-v3 invocation persisted its 960-byte control marker, then failed closed before network or inference because sorted evaluator key order did not equal the helper's runtime-stage tuple. Canonical tracked boundary SHA-256 is `fb8d4270320f73e9307da5b67325cc30edeaab04e7e1ac4a01068a5a94107e14`; task advantage was not adjudicated.
- **Consumed v4 boundary:** v4 completed 775 model responses and all four arms for six tasks, then stopped on task 7's common-root warm after model completion but before its metadata ledger and host-memory records. The exact failed member of the compound warm predicate is unavailable. Canonical boundary SHA-256 is `5305192d4509028dbf4cf71d42af04d9703e3320d47cf1000cd60358f8a5044a`; all seven raw artifacts are immutable and v4 is hard-retired.
- **Consumed v5 boundary:** V5 ran exactly once from protected `241d99e403926b8ef7814c894808922b7cb8cd8e`, closed 775 completed responses into 775 ledger records with zero fallback, and rejected record 775. Host success accounting is 774 / 775, but every measured host value remained below the 4,096 MiB ceiling; the exact compound live cause is unavailable. Canonical boundary `897148680e426caf58b9581f06224f904cb8ff5cd1a389b83c1ceedfc427f9d9` is consumed and hard-retired. No task advantage was established.
- **Consumed v6 boundary:** V6 authority was consumed from protected `ef8caa5c0132d1581321d8ba9fd9643a8d246fbb`, but its unignored control marker invalidated the later clean-worktree gate. The sole artifact is 1,577 bytes at SHA-256 `9172468FB5D102C36BC78E553C8FD804394C4BE5FFE98E94CA18314F1E2BC9A4`; six later artifacts are absent; zero sidecars and zero model requests occurred. Canonical tracked boundary `64c296f8332afc2fd224fc9d3510c2d12395d5d4c9cdc7955b659fadaa2f8eb3` classifies it as `HARNESS SELF-CONTAMINATION / PRE-INFERENCE / SCIENTIFICALLY NON-ADJUDICATING`. V6 and all predecessors are hard-retired.
- **Current boundary:** Track A claim verification is paused; CIB0 a1-a6 and CK0 a1-a6 are frozen. Tier-1 `complementary-unresolved-public-v1` discovery a3 and exact replication a4 recovered `C42` at 5 / 5 through the six-request kernel. Directional causal controls are asymmetric: withholding Branch-A informative content in a5 changed the transform to `C09,C34,C42` and extraction to `C09` at 4 / 5, supporting only `BRANCH_A_INFORMATION_DEPENDENCE_SUPPORTED_ON_FROZEN_CARRIER`; withholding Branch-B informative content in a6 still produced transform `C42,C56,C00` and extracted `C42` at 5 / 5, so Branch-B information was not shown necessary. No Branch-B or bilateral dependence status is unlocked. Task advantage, superiority, SOTA, general catalytic inference, broader HoloState, restart persistence, Deep, and automatic promotion remain locked.

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
- **Metrics and claims:** report compute amplification, fresh-compute ratio, state-reuse yield, closure cost, carrier reuse count, prefix-hit depth, holographic branch density, expert-residency yield, and blackboard yield. Separate observed from quality-accepted reuse, live from durable state, and task advantage from speedup. No restart-persistence, task-advantage, SOTA, physical-infinity, or automatic-promotion claim is currently allowed.

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

### Current relational-synthesis frontier

Published `neo-exp-0045` supports `THREE_PARENT_GLOBAL_RELATIONAL_INVARIANT_EXTRACTION_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES`, with bounded interpretation `TRANSFORM_SELECTS_AN_INVARIANT_IDENTIFIABLE_ONLY_FROM_THE_COMPLETE_THREE_PARENT_RELATION_AND_NOT_FROM_ANY_SINGLE_PARENT_OR_PARENT_PAIR`. All six rank-zero selections matched the frozen unique three-way commitment across T0/T1 and cyclic orders `ABC`, `BCA`, and `CAB`; first-listed, lexical-first, first-parent, last-parent, and first-presented-pair decoy predictions were false throughout.

The evidence progression is now: joint-parent information matters → pairwise unique-intersection-like operation identified → operation reproduced under a combined new binding-and-seed condition → complete three-parent relation resolves an invariant unavailable to any parent pair. This is stronger than pairwise intersection recovery but remains a transform-only synthetic relational probe. It does not establish full commutativity, associativity, arbitrary n-parent generalization, formal algebra, independent seed or binding invariance, transfer, worker synthesis, general catalytic inference, a complete borrow → transform → extract → restore cycle, task advantage, reduced fresh computation, compute amplification, superiority, SOTA, or promotion.

The authorized public-only scan for `balanced-opaque-three-worker-to-synthesis-mini-swarm-v1` stopped at `EXISTING_CORPUS_THREE_WORKER_GEOMETRY_UNAVAILABLE`. Across the frozen eight-task suite, locally eligible three-example shard counts are `[2,2,0,0,2,1,1,0]`; no task supplies the three distinct shards required before pair/triple geometry, prompt matching, hidden utility, or private binding can lawfully be considered. No worker carrier, request, synthesis surface, preregistration, controller, authority, or live state was created.

The separately authorized public-only decision then tested the smallest requested two-worker geometry as `balanced-opaque-two-worker-to-synthesis-mini-swarm-v1`. It also stopped at corpus admission: the six ordered pairs of distinct locally eligible shards cover at most four of five public examples, overlap on at least two examples, and share all three support candidates. Therefore no pair instantiates two individually ambiguous, decoy-disjoint supports whose unique intersection is the full-public singleton. Diagnostic artifact SHA-256 is `493B8E7CD2591E4BCDD27C224693C8DA890AE885433C3BEA07528683C1D69264`.

Those two failures remain exact for their requested cardinality-three support law. A separate static compatibility decision found that the same frozen corpus already contains a different, previously protected bilateral geometry: internal task index 2 with public shards `012` and `234`, two locally exact five-member supports, one-example shard overlap, singleton support intersection, and singleton full-public support. Because this is the existing cardinality-five profile rather than a weakened cardinality-three scan, both prior diagnostics remain unchanged.

`balanced-opaque-five-support-two-worker-synthesis-probe-v1` was statically preregistered as the minimum worker-relation capability test. It froze exactly three generations: isolated `worker-A`, isolated `worker-B`, then `synthesis-AB`. Each worker had to model-generate its complete five-member relation in the shared opaque namespace; the controller could validate and outcome-independently normalize an exact set but could not replace, add, or remove members. Synthesis received only the two authenticated relation artifacts and the generic rank-head-v2 transform carrier. The hidden-exact candidate was consulted only after public profile freeze, and live scoring occurred only after all three generations completed.

The probe executed once from protected main `563cbf5a72a763af8a2cde2394a5ea5beb008bad`. Both isolated worker generations authored exactly the frozen five-member supports, preserving their original order in authenticated captures. The synthesis generation used only those validated artifacts, emitted `reconcile` with ranking length three, froze rank zero before private mapping, selected the unique intersection, and scored `5/5` public and `16/16` hidden. All three generations completed with zero retries; cleanup and postflight passed.

Canonical artifact `lab/ck0_balanced_opaque_five_support_two_worker_synthesis_probe_adjudication_1.json`, SHA-256 `EBF0FA07A7B31C72EC19B9C74400C27C01943DDA8247CD02FC81DCC0EC5B228F`, and `neo-exp-0046` at line 59, SHA-256 `BC3FD349EAE13AC6B35659D6FECDEDC00751BB41CBEB33D9F7DF5D29F3F6000A`, publish only `FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_SUPPORTED_ON_ONE_FROZEN_TASK` and its bounded interpretation. General worker synthesis, transfer, equal-budget advantage, reduced fresh computation, compute amplification, a complete catalytic lifecycle, general catalytic inference, superiority, SOTA, and promotion remain locked. The next action is independent static review before any new experimental authorization.

That independent static review is complete. It accepts `neo-exp-0046` as valid capability evidence but classifies the current DSL carrier `CURRENT_DSL_WORKER_SYNTHESIS_IS_CAPABILITY_ONLY_NOT_A_FRESH_INFERENCE_ADVANTAGE_TEST`. Before model contact, the controller can execute every candidate on both public shards, derive both exact five-member supports, intersect them to the singleton, and score it on the protected evaluator; preregistration also constructs exact placeholder worker artifacts for the synthesis request. The observed model route used three serial generations, 10,401 logical prompt tokens, and 10,383 fresh prompt tokens, while the same frozen task is solvable controller-only with zero model generations. This is not negative evidence against relational synthesis; it means this carrier cannot adjudicate reduced fresh inference.

Repository-only search found no suitable successor family. The CatalyticSwarm-1/CIB0/CK0 tasks expose executable candidate programs and public examples and enforce one publicly exact candidate, making them controller-enumerable; baseline probes lack protected relational utility. Decision artifact `lab/ck0_balanced_opaque_five_support_two_worker_synthesis_task_suitability_decision_1.json`, SHA-256 `EE2C89131B581EE5B0300CDD6EAEAC636AAF31C37CA2C5AC72E8D159CDD56F2F`, binds `NON_CONTROLLER_RECONSTRUCTIBLE_WORKER_SYNTHESIS_TASK_NOT_AVAILABLE_IN_CURRENT_REPOSITORY`. The next bounded action is static design only of one deliberately easy Agents-A1 35B-calibrated task family with short evidence shards, a small structured schema, one simple synthesis relation, and bounded output ceilings. Its worker information must not be controller-reconstructible, its partials must be individually insufficient, its synthesis must not be literal intersection over controller-known sets, and its protected evaluator and same-evidence direct baseline must be frozen without hidden-answer route selection.

That design boundary is complete as `two-shard-semantic-xor-worker-synthesis-family-v1`, classified `TWO_SHARD_SEMANTIC_XOR_TASK_FAMILY_STATICALLY_ADMISSIBLE`. Each of four future manually authored tasks will contain two short independently decidable natural-language microcases. Isolated workers emit only one model-authored bit each; synthesis receives only those captured bits, authenticated source commitments, and fixed XOR, then emits `SAME` or `DIFFERENT`. The controller receives no structured passage facts, expected bits, answer, generation variables, derivation tree, parser, or evaluator data.

The same frozen evidence will also go to one ordinary direct-baseline request under the same model, temperature, tokenizer, sidecar, admission, capture, and eight-token output ceiling. A future inference-advantage claim requires at least equal final accuracy and fewer fresh prompt-plus-completion tokens per correct label across all four retained tasks, with cached tokens and request count reported separately. Canonical design artifact `lab/two_shard_semantic_xor_worker_synthesis_family_v1_design.json`, SHA-256 `ED63ED4C75F9D6CE8DB4177E1137D02CFED7B385E20B2D29B434206DAD5C7B1F`, contains no task text, answers, prompts, seeds, requests, runtime, or live authorization. The next boundary is `SEPARATELY_AUTHOR_CORPUS_AND_PROTECTED_EVALUATOR_FOR_TWO_SHARD_SEMANTIC_XOR_FAMILY`.

Corpus authoring is now complete under `TWO_SHARD_SEMANTIC_XOR_CORPUS_AND_PROTECTED_EVALUATOR_FROZEN`. Four public task pairs contain eight independently authored 35B-calibrated microcases using balanced comparison, ownership, location, and temporal relations. Opaque task IDs derive only from canonical public bodies, and the array is ID-sorted. The protected evaluator covers all four bit cells exactly once, balances worker A, worker B, and final labels `2/2`, and contains the only salt, expected bits, labels, and task-to-cell mapping.

Public corpus `lab/two_shard_semantic_xor_worker_synthesis_family_v1_public_tasks.json` is 3,704 bytes at SHA-256 `DE4D822424EFE5B6B5FAB1A65F5D2A1E5A87FC60D64A2DD84812BC300A246C41`. The ignored protected evaluator is 968 bytes at SHA-256 `437112DC9A06E4CB3CF1824A738BB13887212B23A38E2AF12A94374A9259D163`. Tracked binding artifact `lab/two_shard_semantic_xor_worker_synthesis_family_v1_corpus_binding_1.json`, SHA-256 `5EBFF4979CD8E60E814F05C8B5E8413523DFB244E4396548A4A595253020EF5F`, freezes both identities before model contact without disclosing answers. The next boundary is `SEPARATELY_IMPLEMENT_AND_PREREGISTER_TWO_SHARD_SEMANTIC_XOR_WORKER_AND_BASELINE_EVALUATION`.

That implementation boundary is complete as `two-shard-semantic-xor-worker-baseline-evaluation-v1`. The static controller freezes 16 request positions across all four tasks, uniformly disables prompt caching, binds 16 outcome-independent seeds, and exact-hash binds eight isolated worker requests plus four direct baselines. The four synthesis hashes are intentionally not precomputed: the frozen derivation law `9974D9F209059F57B0A716D6187F9C4DEF9354608051037BB3CB6A1C30386B8D` requires cryptographic re-verification of both worker captures, exact bit parsing, domain-separated source commitments, and journal binding before each synthesis contact.

Canonical preregistration `lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1.json` has artifact SHA-256 `41AA06744924D4705A4EC03FC418FA6F2A407BACD007E96988AF29CBEE49BEA2`. Protected scoring cannot open the evaluator until all 16 captures exist and cleanup/postflight pass; resource comparison uses exact integer cross-products over fresh prompt-plus-completion tokens per correct label. No authority, sidecar, model request, generation, capture, result, archive, ledger record, or follow-on exists. The next boundary is `SEPARATELY_AUTHORIZE_AND_EXECUTE_TWO_SHARD_SEMANTIC_XOR_WORKER_BASELINE_EVALUATION_V1`.

That first attempt is now consumed and terminal `INCONCLUSIVE`. It executed from `5605c5d28a6fdbc7e1e7ee855c0515f88ad50997`, captured only the first direct baseline, and stopped without retry because the HTTP 200 response exhausted the frozen eight-token ceiling before strict JSON closure. Archive `4447C61747E89084EE9882B238575AF1BF8E21589CDAB78532BD381A1C5741D8` preserves the result; no worker or synthesis request started and protected scoring remained unopened.

Attempt 2 is a bounded execution amendment, not a retry or redesign. It changes only the shared worker/synthesis/baseline completion ceiling from 8 to 16 after the pinned tokenizer measured observed pretty valid schemas at 10–13 tokens. Corpus, protected evaluator, tasks, request order, seeds, schemas, scoring, resource comparison, and claim locks remain fixed. Canonical successor preregistration `lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_2.json` has artifact SHA-256 `1BF0EEF30D0EE71993F02C12ADC7D58ADF01624BD410B36797CDE4E41A5FDA42`; one fresh authority bound to the published successor commit is required before execution.

Attempt 2 is consumed and terminal `INCONCLUSIVE`. Its first baseline response contained complete valid JSON at exactly 16 completion tokens, but the server returned `finish_reason=length` before the required stop marker. No other request started and no retry occurred; archive `9E5F9D89B5FAAA71B550B465CF5EDAF99399FEEF3D56786A733527C9CEF74628` preserves the exact evidence.

Attempt 3 is the final bounded output-budget correction in this lineage. It changes only the uniform completion ceiling from 16 to 32, preserves both consumed predecessors and every task, request, seed, schema, evaluator, scoring, resource, and claim boundary, and uses distinct attempt-3 state and authority paths. Canonical preregistration `lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_3.json` has artifact SHA-256 `650B72BD09ED153505B867AD33FAF6F1D7EE96FA2C76F2A84189975440CB8A66`; one fresh authority bound to the published Attempt-3 commit is required before execution.

Attempt 3 then completed all 16 frozen generations and captures exactly once with zero retry, clean shutdown, and passing postflight. The live controller remained terminal `INCONCLUSIVE` only because the protected scorer compared the frozen evaluator's exact sorted `00 / 01 / 10 / 11` coverage array to boolean `true`. Immutable archive `9FE208E22A0810E84B24AF495D9694C832A2CF1FB3BB3F9EB3545BE0E7371173` contains 21 verified members.

Zero-contact authenticated replay after correcting only that predicate supports bounded semantic-XOR worker synthesis: all eight worker bits, all four XOR relations, and all four worker-route final labels are correct, versus three of four direct baselines. Fresh-inference advantage is not supported: worker route uses `3005/4` fresh tokens per correct label versus direct baseline `1430/3`. Static repair artifact `lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_4.json`, SHA-256 `3C0D97B767C4B426FB6D919A4DC2A867EC977809B38F1856175E5ED884979D01`, authorizes no new run.

Canonical zero-contact adjudication artifact `lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_3_adjudication_1.json`, SHA-256 `2CFA45DE2FDF6E904C341115F7DB63B1D0707C5AF5D88616B2A992D3063D1C1B`, and `neo-exp-0047` at line 60, SHA-256 `B253E5AD9C4861CCCBF05AD1F67F5ED28E097A06418F113A4F123E220E0D21D4`, preserve the source terminal `INCONCLUSIVE` while separately supporting `NON_CONTROLLER_RECONSTRUCTIBLE_SEMANTIC_XOR_WORKER_SYNTHESIS_SUPPORTED` and `SEMANTIC_XOR_WORKER_SYNTHESIS_ADVANTAGE_NOT_SUPPORTED`.

The bounded post hoc worker-plus-controller diagnostic is complete with zero model contact and no new ledger record. Excluding all four model-synthesis requests, the worker-plus-controller route used 1,668 fresh prompt tokens plus 83 completion tokens across eight generations and produced four correct labels: `1751/4`. The direct route used 1,373 plus 57 across four generations and produced three correct labels: `1430/3`. Exact cross-products are `1751 × 3 = 5253` and `1430 × 4 = 5720`, so the worker-plus-controller route is lower on this post hoc accounting only. The result is non-confirmatory and the semantic-XOR line is closed.

The first integrated successor is now statically prepared as `holostate-v1-warm-trajectory-related-task-evaluation-v1`. Four manually frozen 500–1000-word related task pairs each share one Task-A generation and exact process-local checkpoint. Catalytic Task B continues from that checkpoint without replaying the evidence; ordinary Task B receives the same evidence and captured Task-A JSON with prompt caching disabled. Route order is counterbalanced, Task-B seeds are identical within each pair, raw generation responses are authenticated before parsing, and protected scoring waits until cleanup/postflight. The ceiling remains 12 model generations.

The current controller also performs eight inference-bearing zero-output operations: four fresh checkpoint materializations and four immediate post-catalytic closure/readdresses. These operations are no longer treated as free. Their exact payload hash, checkpoint identity, operation order, cache mode, terminal HTTP/stop evidence, and logical/reused/fresh/completion token counts are bound in the authenticated journal. Shared Task A is reported once and separately. The primary comparison is complete catalytic marginal work—materialize, continue Task B, and close/readdress—against fresh direct Task-B replay. Catalytic suffix savings remain diagnostic-only and cannot support the catalytic classification.

Closure is scoped to `immediate-post-catalytic-readdress`; no claim is made that direct replay preserved the root. Generic cleanup and postflight remain separate terminal gates. The protected-evaluator delayed-access repair remains intact: precontact custody observes metadata and ignored/untracked status only, while terminal scoring performs the sole evaluator read and exact size/SHA-256/duplicate-key-safe JSON verification after all 12 captures, cleanup, and postflight pass.

Attempt 1 consumed one authority and then failed before runtime-root creation because its receipt verifier searched serialized text for `raw_authority_id`, which necessarily matched the legitimate `raw_authority_id_persisted` field. Its HMAC-valid receipt SHA-256 `88E7AEA3486FEC2CF4996393A48AB301D78A6CAE241FD006D5D5C2CE4DD6AF12` is preserved unchanged. Attempt 1 performed zero sidecar launches, model requests, carrier operations, generations, or captures and produced no scientific result.

Attempt 2 preserves the complete scientific surface while replacing substring matching with recursive exact-key rejection, adding positive and disclosure-negative receipt regressions, binding Attempt-1 custody, and using isolated receipt/runtime/archive paths. Preregistration artifact/file are `581E27ECC3C4C2FA9A98C16B7E89F22E316324B64D077D2F3CEB266C792A4E00` / `11AB06992B8222F8D1AAEFA10709957FA602003C54D19AFE06FE3AAEAB0E40D5`; controller is `A3929E21BACFEEBA5DEE5A78B74D95E9D6D3B154E1658B4E66AF30EF64A793C1`; resource evidence is `31000085A4FB5C1741C69D12FF64412FD5D14E9BF22FC259935936A3CEC41BB7`; closure is `71947163A74622DCA8C82068E4E75388E4B4E6A051C8862C5B4ED6774E7DC389`. Frozen scientific binding remains `EB8A386E6453DB0B1948C4542F35AEFDEF58D5EB1CBFAB46FEC4D309101BC6C7`.

Attempt 2 then consumed one authority and captured one valid Task-A response before stopping on a controller-only accounting defect. The chat adapter omitted top-level token totals even though the authenticated terminal SSE event contained exact `prompt_n=901`, `cache_n=0`, `predicted_n=108`, and `finish_reason=stop`. Cleanup and postflight passed; the terminal result remains `INCONCLUSIVE`. Receipt, manifest, journal, result, closure, capture, and archive are preserved at exact SHA-256 values `01744A976F84F57DEE2C91EF3817DB6ED2794BBA32AB6AE612D0498E6BE100F3`, `168FB5C680EA47DF1CF469570E04E33EE82A0BEEC5C046225577DC2851D3AEAA`, `8F7E8AF68AF91763BA96339A5BB102709A339B564CFE8C1A28582E64E6B443BB`, `B00234F96CF61FB6C7298FD3B39C52A2CB3745A1D8833E77AF3C45CEDDB2FBBA`, `5E61DAF6F8EE56F2A1C60DEA0899325D63F2C7493FD214BB7F3C11946C187981`, `8D26BDCC61FDFF16A6CCBC609D560EB61DB47CA8CCD26E2033AC73AD6679D92C`, and `E7B7EB7FB097C5A2BEDE1602FBFC74D650E064D54E6C8DCDD832AD6F9EFFACC4`.

Attempt 3 changes only accounting admission and attempt isolation. Missing chat token fields are recovered from authenticated terminal SSE timings and normalized before future capture authentication; complete Attempt-2 custody is bound. Preregistration artifact/file are `9BF5E2AA8F6D1ADE87C5BCCAE5E50DBB4C394A59BD8BDA48984A896464BE2938` / `2C22CC6E1B6163B3C248477CA0E619110EB84B06F1B55CCBD75C281EEB200FAC`; controller is `15951D73D0BEDED504CCCE0A33130F055157CAB8C58FBC478648CB9F89D20D7D`; resource accounting is `9B19875C750EFC7D3583EB473FEC46D9697C676142FEBB3B884DF247FC7DBEEB`; frozen scientific and protected scorer remain unchanged.

Attempt 3 executed once from `f74529479bbdef386d70a666a9c4ae36b600075f` and proved the SSE accounting repair by passing the prior failure point. It then terminated `INCONCLUSIVE` after the same first Task-A capture because checkpoint admission searched the detokenized token prefix for byte-identical raw JSON. The full live Task-B prompt contains that JSON exactly once and full tokenizer detokenization is exact, but the standalone-checkpoint/full-prompt common-token boundary omitted the terminal representation. Cleanup/postflight passed. Receipt/result/closure/capture/archive hashes are `352B9EAE0CFBD13E009928EED4A9E300E6C114B2A205F7AC4C9B3C10D34C721A`, `B4D3F6C08586A4233A16BD5951A3F10E90414F1B200801A0EB14AE70F5E60AA1`, `EBF5EBC86DE64F23F9B7EB0117D747DF0C52370422CCA69711673719D7D508B9`, `9FB12220C9B7E061BDE22640BF038AFF6A6A30594D33C5204386B4051B9E4815`, and `EBDDE88262BA24D0659988BB69051101CA99E584EDF1CBFBD8647E092D403B13`.

Attempt 4 removes only that brittle boundary construction. It locates the minimal exact full-prompt token prefix reaching the end of captured Task A and verifies exact full/prefix detokenization. A zero-generation live tokenizer check passes at terminal token `1004` with `176` suffix tokens. All Attempt-3 evidence is bound. Preregistration artifact/file are `FD2FB5B2460D084CCB4354A1C6B2D2FD86B317B611A313B001455DC01814CD1A` / `2FBEAC65F601A5E572B63EBA82EB8D17CFBEC37F136849FF589F4156616BA910`; controller is `26BB86B5589BBF74DF8DE85767A30FBA4D70ABDD0FFC62C2BCE2AC2FEEE3AD8E`; frozen scientific, scorer, and resource accounting remain unchanged.

The next boundary is the explicitly authorized one-shot execution of `holostate-v1-warm-trajectory-related-task-evaluation-v1-attempt-4` from its final pushed repair commit. General catalytic inference, transfer, restart persistence, superiority, SOTA, and automatic promotion remain locked until executed evidence closes the frozen decision law.

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

This invocation is no-retry. Its exact early-stop evidence is bound as `neo-exp-0019` in the protected evaluator/result/lock for the evidence commit. V1 remains immutable; the only later continuation was the separately authorized and separately versioned v2 successor below. Deep, persistence, CUDA/kernel/model/Pi/stable changes, and promotion remained excluded.

### CatalyticSwarm-0 v2 WDDM successor: REVIEWABLE ACCEPT

Exact integration commit `cf61f90ff5544f2f8bc546e5d661ea72cdda8666` preserved the v1 plan and prompt bytes while adding only bounded exact-PID WDDM transient-query resilience and fresh-sample admission. Protected preflight passed before one artifact-claiming live invocation with explicit pinned paths. No retry occurred after claim, no Deep request ran, and automatic promotion remained false. One earlier pre-claim command refusal created zero artifacts and made zero model requests.

Control qualification, readiness, parser canary, all 32 worker requests, 32 one-slot leases, 32 verifier receipts, the 32-entry append-only blackboard, exact 16/8/6/2 phase counts, the 1,319-record bounded ledger, and both synthesis entries passed. Exact-PID WDDM recorded 177 valid and zero unavailable samples, zero recoveries, maximum failure streak 0, maximum valid-sample gap 2.938 seconds, 107 passed freshness boundaries, and a 2,284.9 MiB peak. Maximum host-private growth was 727,982,080 bytes. Cleanup, isolation, v1 preservation, and v4 preservation passed.

V2 is `reviewable-accept`. `STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE` and `CATALYTIC_SWARM_CONTROL_AVAILABLE` are unlocked. Broader process-local HoloState, restart persistence, task advantage, and SOTA remain locked; automatic promotion remains false. Exact result SHA-256 is `AF491153D98877CAACAF5ED89F3446A80AD8ED12D3FAD2CDE22C2AF77CE5BEC7`; the full artifact bindings are recorded in `lab/CHECKPOINT.md`.

No CatalyticSwarm-0 rerun is authorized. The CatalyticSwarm-1 equal-budget successor executed once below under its separate authority; its result is inconclusive and does not establish task advantage.

### CatalyticSwarm-1 equal-budget evaluation: EXECUTED ONCE / INCONCLUSIVE

Draft PR #6 supplied the five-file pure connector at exact head `aaeb3fe8cc906121fdfcb8ed41d9420b2849d8b6`. Its twelve commits were not imported individually. The protected integration retains the frozen eight-task DSL suite at SHA-256 `4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92` and complete contract at `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`.

The four plan hashes are serial-chain `99FE4402A487EEAF07FAEE7A64CAB241A888E1CB916D09C62BDA493AB08EEF53`, best-of-N `E989ECB8A53E9AD24885759627D3E3BA9A16E76A41A770E70784644A9A96696A`, sparse swarm `9289DE195D12AB93A9A9DD70949C92FC55D40E0D930CAD521605FC1707E116DE`, and verified swarm `46A2CEADA66217AC2DD3E0BD6D1C20A052EFE9D76EE236887AF18428409A772C`. Every task prepares one common public-root warm outside the four comparison budgets, and every arm request must prove its cached token prefix covers that complete root before the exact four-position Latin square continues. Each arm has 32 requests, one physical slot, 32 maximum completion tokens per request, 1,024 maximum completion tokens, and 8,192 maximum fresh prompt tokens. Actual fresh, completion, and total-model token ratios must each remain at or below 1.10.

Hidden examples and answer keys are excluded from roots, assignments, requests, ledger records, arm context, and later task context. Arm outputs stay arm-local; task outputs stay task-local. Hidden scoring is deferred until all four arms for a task finish. The exclusive ledger is capped at 80,000 records and 67,108,864 bytes and retains bounded metadata only.

The repaired runner inherits the v2 exact-PID WDDM resilience/freshness policy, v4 token evidence, strict candidate JSON, one physical lease, stable/candidate isolation, and bounded cleanup. It adds exact stable/candidate custody checks before and after every prospective model request, post-request host/resource checks, an immediate parity stop after every completed task, guarded cleanup across the parser-to-attempt boundary, and terminal reconciliation of `2064 / 1032 / 8` custody, host-memory, and task-parity checks.

The single authorization was consumed in one no-retry invocation. Control qualification, readiness, and the generation-free parser canary passed. The first task's common root warmed with 4,846 fresh prompt tokens, 0 cached prompt tokens, and 4 completion tokens. The first serial-chain comparison response then failed the complete-public-root cache proof, which is the primary stop. The run ended `inconclusive` after exactly 2 completed model requests: 1 common-root warm, 1 comparison, and 0 completed task comparisons. Equal-budget task advantage was therefore not completed or adjudicated.

Six one-shot artifacts exist and are bound: control `F9C8032340655EBBE5E41867D8C4C426940E6B7D2236ACDA9019EE9E24F8733D`; readiness `F6DF670C7CE1659E78D4B51F5CD45FAF4087DD46ABE87D8AD529AB45F6FE9C95`; parser canary `0B2749F3F864CB93FB003EA68A41AD364C56360C270506DB3684C1738E221680`; attempt `593D013494064F10FF9ECF732942EE114E1DC91E14A3290210C8801684A48A40`; result `D37CBF79BC867D927C01C7977D4432A29B2CA40E59ED5C10CCF6EF9A5F3AACAB`; and ledger `5E016B7554E57564833BAA3B5B1250C6EE6FB73CFE204BDCBC4EEB902C1E40B8`. `task-results-v1.json` is absent.

The metadata-only ledger contains the warm record only: 2 responses completed but the failed comparison stopped before its ledger entry, so terminal ledger reconciliation correctly reports `ledger-request-count`. A separate inherited-control incompatibility also remains: the CatalyticSwarm-0 v2 terminal WDDM reconciler expects v2 worker-boundary labels rather than the CS1 request-boundary labels and reports `wddm-required-freshness-boundary-order`. All 12 observed freshness admissions passed; this secondary terminal label incompatibility did not cause the earlier complete-root-cache stop and was not repaired through a retry.

Cleanup and observed runtime integrity passed. Sidecar PID `30848` stopped, runtime state was removed, port 9494 became free, five exact-PID retirement samples were empty, stable PID `32684` remained healthy, and candidate custody remained intact. Full-schedule custody, host, parity, request, ledger, and terminal-WDDM gates remain non-pass after the early stop rather than being rewritten as successful completion. `CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN`, SOTA, broader process-local HoloState, restart persistence, and automatic promotion remain locked. CatalyticSwarm-1 v1 must not be rerun.

### CatalyticSwarm-1 cache-admission diagnostic [HISTORICAL PRE-EXECUTION SNAPSHOT]

This section preserves the diagnostic's static integration boundary before its separately authorized execution. It is superseded for current status by the executed diagnostic, consumed CS1-v2/v3 boundaries, and static CS1-v4 custody recorded in the architecture summary above and `lab/CHECKPOINT.md`.

CatalyticSwarm-1 v1 remains `EXECUTED ONCE / INCONCLUSIVE / NO RETRY`. The separately versioned cache diagnostic is statically integrated under complete-contract SHA-256 `be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b`. No diagnostic evidence object or runtime artifact exists, and no live request was made during integration.

Its prospective sequence is exactly three model requests on one physical slot with thinking disabled, temperature zero, and no Deep request: the exact CS1-v1 public-root warm, a minimal branch constrained to `{"candidate_id":"C00"}`, and the unchanged `serial-chain / cs1-chain-t01` assignment and grammar. The public task projection, reference envelope, task suite, programs, hidden data, answer key, chat template, model, binary, cache controls, and checkpoint minimum step remain frozen.

For each completed branch response, the controller must persist bounded measurements before applying any cache-admission class or threshold. The diagnostic separately records the exact public-root terminal token index, exact warm/branch common-token prefix, inherited v1 required threshold, actual cached tokens, fresh tokens, completion tokens, and transport/token-evidence state. A negative first cache class does not stop the second probe unless an independent safety gate fails.

The terminal controller is CS1-native. It reconciles `pre-request:cs1-cache-diagnostic-*` and `post-request:cs1-cache-diagnostic-*` labels rather than CatalyticSwarm-0-v2 worker labels. A complete diagnostic requires 3 completed requests, 6 custody checks, 3 host/resource checks, 3 pre-request and 3 post-request freshness boundaries, one warm ledger record, and two branch observation records. Lawful early safety stops reconcile the exact observed completed-request count.

This integration does not identify the root cause. A future live invocation requires new explicit authorization bound to the then-exact pushed protected `main` and exact Agents-A1 model path. `CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN`, `SOTA_SWARM_CLAIM`, broader process-local HoloState, restart persistence, and automatic promotion remain locked.

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
