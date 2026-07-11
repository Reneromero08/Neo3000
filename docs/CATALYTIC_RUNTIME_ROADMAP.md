# Neo3000 Catalytic Runtime Roadmap

## Status and purpose

This document integrates the catalytic architecture that emerged from:

- Neo3000 HoloState experiments;
- CAT_CAS substrate-expansion experiment 08, catalytic GPT and the swarm multiplexer;
- CAT_CAS substrate-expansion experiment 13, orthogonal multi-model routing;
- upstream and external runtime research on prompt checkpoints, host cache, recurrent state, expert residency, CUDA graph reuse, and hybrid-model persistence;
- worker protocol v4, which proved exact process-local HoloState Fast micro-workers for Agents-A1.

It is an architecture and phase-order document. Executed evidence in `lab/CHECKPOINT.md` and `lab/results.jsonl` remains authoritative.

The central objective is not merely to make ordinary inference cheaper. It is to reduce the amount of fresh ordinary inference required by allowing useful computation to remain available as reusable executable state, shared substrate, routing identity, or verified blackboard structure.

---

# 1. Current proven boundary

The strongest supported mechanism claims are:

```text
NEO3000_BASELINE_OPERATIONAL
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE
STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE
CATALYTIC_SWARM_CONTROL_AVAILABLE
```

Worker protocol v4 proved:

- one long-lived Agents-A1 sidecar;
- two immutable canonical roots;
- exact process-local prompt-state reuse;
- six thinking-disabled Fast branches;
- deterministic A1 and B1 repeats;
- exact visible token sequences plus one directly evidenced terminal EOS token;
- 21 fresh prompt tokens per Fast branch after reusing approximately 4.4K or 8.1K prompt tokens;
- bounded WDDM and host memory;
- stable/candidate isolation and clean teardown.

CatalyticSwarm-0 v1 then executed exactly once. Its generation-free control
qualification passed, but readiness stopped as `inconclusive` after an
exact-PID WDDM counter query timed out and was classified
`candidate-vram-telemetry-lost`, before the structured parser canary,
capability attempt, physical lease, blackboard, or any logical worker request.
This is not a swarm-capability result. V1 is immutable and may not be retried.

The separately versioned v2 successor then completed one artifact-claiming live
execution from protected integration commit
`cf61f90ff5544f2f8bc546e5d661ea72cdda8666`. No retry occurred after claim;
one earlier pre-claim command refusal created zero artifacts and made zero model
requests. Its sole
intervention was bounded exact-PID WDDM transient-query resilience plus fresh
admission. Control qualification, readiness, parser canary, all 32 workers,
32 one-slot leases and verifier receipts, the exact 16/8/6/2 phase sequence,
the 32-entry append-only blackboard, 1,319 ledger records, and two synthesis
entries passed. V2 is `reviewable-accept` for structured micro-workers and
bounded swarm control. This is not evidence of task advantage.

Not proven:

```text
PROCESS_LOCAL_HOLOSTATE_AVAILABLE
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN
SOTA_SWARM_CLAIM
```

The Deep lane independently failed its 768-token quality contract. Deep workers are not part of the first swarm control proof.

---

# 2. Correct interpretation of the original catalytic experiments

## 2.1 Experiment 08: catalytic GPT and swarm multiplexer

The operational mechanism is a bounded physical allocator serving a much larger logical population:

```text
fixed physical substrate
-> partition into reusable execution slots
-> logical request acquires one slot
-> execute bounded transformation
-> restore or close the slot
-> release it
-> another logical request reuses the same substrate
```

The experiment launched 1,000 logical requests over one model and one fixed tape. It demonstrated:

- logical population can exceed physical residency;
- activation/scratch memory can be reused through explicit leases;
- memory remains bounded by the physical slot pool rather than logical population;
- temporal and statistical multiplexing can produce swarm-scale logical concurrency.

The exact source does not prove 1,000 fully resident independent models. Tape restoration regenerates known seeded state rather than restoring arbitrary unknown state. Neo3000 therefore carries forward the lease-pool law, not the inflated simultaneous-residency claim.

Neo3000 mapping:

```text
Exp 08 tape slot = HoloState executable-prefix lease
Exp 08 logical request = logical Agents-A1 micro-worker
Exp 08 TapeManager = CatalyticSwarm physical lease pool
```

## 2.2 Experiment 13: orthogonal multi-model routing

The useful architectural contribution is logical channel separation:

```text
logical state families
-> distinct phase or orthogonal routing signatures
-> one shared physical substrate
-> controlled selection, decoding, and closure
```

The existing experiment uses QR-orthogonal projections but places the two models in different physical tape regions. Floating projection, clipping, quantization, and XOR also do not preserve a general exact orthogonal-state superposition law.

Neo3000 therefore uses orthogonality initially for:

- worker identities;
- phase identities;
- routing signatures;
- blackboard channels;
- root-selection indexes;
- anti-collision and anti-contamination checks.

It does not yet claim that opaque KV or Gated Delta Net state blobs can occupy the same bytes and be independently recovered. A true overlapping-state experiment remains a later checkpoint.

---

# 3. Catalytic compute law

Every catalytic intervention must declare:

```text
expensive operation
borrowed carrier
transformation
extracted result or invariant
restoration or closure law
lawful retained state
fresh-compute reduction mechanism
quality and identity gates
measurement that rejects the hypothesis
```

Performance and catalytic compute remain separate lanes:

```text
performance substrate: reduce ordinary inference cost
catalytic compute: reduce how much fresh ordinary inference is required
```

CUDA optimization, quantization, backend placement, and kernel fusion may support catalytic compute, but they do not themselves prove catalysis.

---

# 4. Reusable carrier hierarchy

## Carrier 1: exact live prefix state

Components may include attention KV, Gated Delta Net recurrent state, convolution or short recurrent buffers, token position and sequence metadata, exact token IDs, chat-template identity, and full model/runtime/configuration identity.

Status:

```text
process-local reuse: proven
restart persistence: not proven
```

## Carrier 2: logical swarm population over bounded live state

Many logical workers share one or a small number of physical HoloState leases.

```text
Fast worker primitive: proven
CatalyticSwarm-0 v1 control qualification: passed
CatalyticSwarm-0 v1 readiness: inconclusive before canary or worker request
CatalyticSwarm-0 v2 telemetry successor: reviewable-accept control proof
32-worker control capability: proven at the bounded control layer; availability unlocked
task advantage: untested; availability locked
```

## Carrier 3: expert residency state

Possible retained state:

- expert residency map;
- route-frequency estimates;
- hot-expert cache;
- pinned staging buffers;
- prefetch schedule.

This must be selected from measured route and transfer evidence rather than assumed.

## Carrier 4: recurrent trajectory state

Candidate forms:

- exact recurrent checkpoints;
- sparse recurrent checkpoints;
- accepted-state shadows for speculation;
- state-delta or low-rank transition representations;
- algebraic prefill or one-pass recurrent update where exact.

This remains locked until state identity, copy cost, location, and exact restoration are measured.

## Carrier 5: executable graph and warm runtime state

Possible retained state includes CUDA graph captures, allocator state, compiled shape signatures, initialized server/sampling state, and pinned host buffers.

Graph reuse is catalytic only when executable structure is retained and lawfully reused, not merely when a kernel runs faster.

## Carrier 6: verified blackboard state

Compact verified claims, artifacts, counterexamples, and tool results become reusable coordination state for later workers. This is not hidden chain-of-thought persistence.

```text
claim
phase
worker identity
parent identities
references
artifact hashes
verifier receipt
decision
```

Status: the v2 control proof produced a valid 32-entry append-only hash chain
with 32 verifier receipts and two synthesis entries. Cross-task reuse and
restart-durable blackboard state remain unproven.

---

# 5. Holographic runtime architecture

The near-term holographic architecture is:

```text
phase / orthogonal logical index
+
exact executable-prefix cache
+
bounded physical lease pool
+
time-multiplexed Agents-A1 inference
+
append-only verified blackboard
```

The term holographic refers to a system in which a large logical computation population is addressable through compact identities and reusable partial state while only a bounded physical working set is resident.

It does not mean infinite instantaneous FLOPs. The correct claim target is:

```text
unbounded cumulative retained computation
subject to finite storage, admission, eviction, and verification laws
```

---

# 6. CatalyticSwarm architecture

## Physical layer

```text
one Agents-A1 model
one long-lived HoloState sidecar
one physical execution lease
bounded host cache
bounded WDDM
32 logical Fast workers
```

Logical population may later exceed 32, but physical residency remains bounded.

## Logical worker phases

```text
16 proposal workers
8 evidence workers
6 critique workers
2 synthesis / selection workers
```

All first-control workers are thinking-disabled, capped at 64 completion tokens, compactly structured, identity-bound, and external-verifier gated.

## Communication topology

```text
independent proposals first
-> evidence workers inspect assigned proposals
-> critics inspect assigned evidence
-> selectors inspect only verifier-accepted critiques
```

Prohibited in the first control proof:

- all-to-all transcript sharing;
- same-phase communication;
- complete reasoning transcript broadcast;
- unrestricted peer messaging;
- model self-confidence as verifier;
- hidden promotion of unverified entries.

## Orthogonal and phase-native routing

Hadamard or other orthogonal codes may provide exact logical routing identities for proposal, evidence, critique, and synthesis. They do not establish physical state superposition.

## Verifier layer

Preferred verifier order:

```text
compiler / unit tests / integration tests
formal or symbolic checks
numerical counterexample search
source and citation verification
artifact hashes and provenance
bounded deterministic schemas
model judge only as a lower-trust supplement
```

---

# 7. Swarm scaling path

## CatalyticSwarm-0: bounded control proof

Objective:

- 32 logical workers;
- one physical lease;
- exact structured contributions;
- append-only hash-chained blackboard;
- sparse assigned parent graph;
- deterministic verifier receipts;
- two verified synthesis entries;
- bounded resources and exact teardown.

This proves orchestration and communication mechanics only.

Status: v1 executed exactly once and stopped at readiness after its
generation-free control qualification passed. No parser canary, capability
attempt, worker request, lease, ledger record, or blackboard entry executed;
v1 remains immutable and no-retry.

The separately versioned `catalytic_swarm_0_v2` successor completed one
artifact-claiming live execution. No retry occurred after claim; one earlier
pre-claim command refusal created zero artifacts and made zero model requests.
Its only causal intervention was bounded resilience to
transient exact-PID WDDM counter-query failures plus fresh-sample admission at
every protected boundary. The plan, prompts, seeds, parent graph, parser,
verifier, blackboard, one-slot lease law, and 64-token Fast budget remained
unchanged. All 32 workers, leases, receipts, blackboard entries, exact 16/8/6/2
phase counts, 1,319 ledger records, and two synthesis entries passed. WDDM
recorded 177 valid and zero unavailable samples, zero recoveries, maximum
failure streak 0, maximum valid-sample gap 2.938 seconds, 107 passed freshness
boundaries, and a 2,284.9 MiB peak. Cleanup, isolation, v1 preservation, and v4
preservation passed. The control proof is `reviewable-accept`.
No Deep request, retry, or automatic promotion occurred.

Unlock target:

```text
STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE
CATALYTIC_SWARM_CONTROL_AVAILABLE
```

Both control-layer availability targets are now unlocked. Task advantage,
broader process-local availability, restart persistence, SOTA, and automatic
promotion remain locked.

## CatalyticSwarm-1: equal-budget task advantage

The protected design and safety-repaired runner are integrated but not
executed. The prior live authorization is unconsumed but superseded by the new
protected-main identity. New separate explicit authorization is required before
`audit-catalytic-swarm-1` may run.

Frozen identity:

```text
task suite: catalytic-swarm-1-dsl-selection-v1
tasks: 8
candidates per task: 64
program length: 5
public examples: 5
hidden examples: 16
suite SHA-256: 4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92
contract SHA-256: fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e
```

Compare:

```text
serial-chain: one 32-turn trajectory; each turn sees only its predecessor
best-of-n: 32 independent candidates; public verifier selects after completion
sparse-swarm: exact 16/8/6/2 parent graph without verifier scores in context
verified-swarm: identical graph with assigned-parent public scores in context
```

Every arm receives 32 requests, one physical slot, at most 32 completion tokens
per request, at most 1,024 completion tokens, and at most 8,192 fresh prompt
tokens per task. Fresh-prompt, completion, and total-model token ratios must each
remain at or below 1.10. Each task warms one exact public root once before any
arm; the warm is recorded separately and excluded from every arm budget. Every
arm request must prove its cached-token prefix covers that complete root. The
exact four-position Latin square is repeated over tasks five through eight.

Hidden examples and answer keys never enter requests, assignments, arm context,
later task context, or the ledger. Hidden scoring occurs only after all four arms
for one task finish. Arm state and task state are isolated. The exclusive
metadata-only ledger is capped at 80,000 records and 67,108,864 bytes.

The safety repair leaves that experiment geometry unchanged. It requires exact
stable and candidate custody before and after every prospective model request,
checks the inherited host/resource ceiling after every request, stops on each
task's parity result before the next task, guards cleanup across the
parser-to-attempt transition, and requires terminal counts of 2,064 custody,
1,032 host-memory, and 8 task-parity boundaries.

Prepared state:

```text
status: REPAIRED / INTEGRATED / NOT EXECUTED
prior authorization: UNCONSUMED BUT SUPERSEDED BY NEW MAIN IDENTITY
live model requests: 0
sidecar launches: 0
one-shot artifacts: absent
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN: LOCKED
SOTA_SWARM_CLAIM: LOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
automatic promotion: disabled
```

Unlock target:

```text
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN
```

## CatalyticSwarm-2: adaptive population

Start small and expand only when disagreement, failure, or marginal candidate gain justifies more workers.

```text
easy task: 8 workers
moderate task: 32 workers
hard task: 128 workers
high-value executable task: up to 1,000 logical workers
```

Stop when a candidate passes every deterministic gate, independent derivations converge, verified marginal gain flattens, or the compute budget is exhausted.

## CatalyticSwarm-3: persistent logical agents

Add restart-persistent state only after HoloState durable capsules are proven. Persistent state may include canonical root identity, verified blackboard history, compact task state, exact durable checkpoint identity, and tool/artifact provenance.

## CatalyticSwarm-4: heterogeneous swarms

Possible later forms include different local models by role, different quantizations or adapters, specialist verifiers, CPU-side routing models, and remote frontier synthesis only at declared boundaries.

---

# 8. Durable HoloState path

## HoloState-v1 Live Prefix Lattice

```text
exact process-local carrier proven
Fast micro-worker available
broader live operational availability locked
```

## HoloState-v2 Durable Capsule

Required:

- raw KV and recurrent state;
- recurrent checkpoint-list persistence;
- exact token history;
- model/source/template/quantization/KV/adapter/context identity;
- nearest-checkpoint recovery where recurrent truncation is unsupported;
- exact A/B restart validation;
- corruption and stale-identity rejection.

The existing slot file is insufficient because it does not restore the recurrent checkpoint-selection metadata needed to avoid replay after restart.

## HoloState-v3 Tiered state store

```text
GPU live state
pinned-host hot state
ordinary-host warm state
disk durable state
```

Admission and eviction should optimize verified reuse yield, not recency alone.

## HoloState-v4 Branching state tree

Represent canonical roots, checkpoints, and divergent branches as a content-addressed execution tree keyed by model identity, runtime identity, template identity, exact token prefix, context configuration, adapter/cache types, and state schema version.

---

# 9. Native runtime and CUDA path

## Backend placement and fallback

Distinguish declared CPU-MoE from accidental fallback, identify unsupported CUDA shapes, measure host/device traffic, and preserve operator/tensor provenance.

## MoE geometry and expert cache

Measure active experts, tokens per expert, bucket distribution, actual MMQ tile geometry, padded work, expert transfer cost, and residency yield before testing actual-bucket tile sizing, mixed-quant hot experts, partial GPU expert cache, or predictive prefetch.

## Gated Delta Net recurrent path

Measure state bytes per layer, update cost, copy/restore cost, residency, transfer, synchronization, and snapshot fidelity.

Candidate interventions:

```text
GdnOnePass-v1
SparseCapsule-v1
StateShadow-v1
recurrent prefill algebra
recurrent write factorization
```

## CUDA graph and warm state

Measure shape signatures, capture/replay, reconstruction causes, synchronization, D2H stalls, allocator growth, and graph reuse across reusable prefix boundaries.

---

# 10. True orthogonal-state experiment

A later experiment must test actual overlapping physical state, not disjoint tape regions.

Required:

- same physical cells;
- independently encoded state channels;
- exact or bounded reversible decoding;
- collision and cross-talk measurement;
- quantization-aware orthogonality law;
- restoration of the original substrate;
- comparison against disjoint-region control;
- capacity gain exceeding encoding overhead.

Candidate representations include complex or phase-coded state, signed integer reversible transforms, error-correcting subspaces, low-rank state deltas, spectral/eigenbasis routing, and exact finite-field encodings.

Opaque recurrent-state superposition remains locked until this succeeds.

---

# 11. Catalytic metrics

```text
compute amplification = equivalent baseline compute / fresh compute executed
fresh compute ratio = fresh transitions / logical transitions
state reuse yield = avoided evaluations / retained-state bytes
closure cost = save + restore + verification cost / avoided replay cost
carrier reuse count = correct uses of retained state
prefix hit depth = reusable prefix tokens / logical prefix tokens
holographic branch density = verified branches / resident state GiB
expert residency yield = avoided transfer or execution / expert-cache bytes
blackboard yield = verified downstream decisions / retained blackboard bytes
```

Metrics must distinguish observed versus accepted reuse, process-local versus durable state, visible-token identity versus full hidden-sequence identity, task advantage versus ordinary speedup, and quality-closed versus quality-open compute savings.

---

# 12. Phase order from the current boundary

```text
completed: CatalyticSwarm-0 v2 bounded control proof
completed: repair and integrate the CatalyticSwarm-1 equal-total-budget runner without execution
1. obtain new explicit authorization bound to repaired protected main, then execute CatalyticSwarm-1 exactly once
2. adjudicate and bind its evidence without broadening the exact suite scope
3. Adaptive population and verifier allocation
4. HoloState multi-root admission and eviction policy
5. HoloState-v2 durable checkpoint-list persistence
6. Expert residency and routing cache, if compute-map evidence selects it
7. Exact recurrent-state snapshot and restore experiments
8. Sparse recurrent checkpoints and state shadows
9. True overlapping orthogonal-state experiment
10. Native catalytic kernels selected from measured carriers
11. Recursive compute amplification across tasks and sessions
```

Checkpoint 1 tracing remains available as a diagnostic lane, but instrumentation work should not displace a proven catalytic boundary unless the next intervention requires a causally localized low-level bottleneck.

---

# 13. Claim discipline

Allowed current description:

```text
Agents-A1 can serve exact thinking-disabled process-local HoloState micro-workers
from reused executable prefixes on one bounded sidecar.

CatalyticSwarm-0 v1 passed generation-free control qualification and stopped
readiness inconclusively before any canary or capability request.

CatalyticSwarm-0 v2 then completed its 32-worker, one-slot control proof.
Structured micro-workers and bounded swarm control are reviewable-accept and
available; task advantage remains untested and locked.

CatalyticSwarm-1 equal-budget evaluation is repaired and integrated but not
executed. Its prior authorization is unconsumed but superseded by the repaired
protected-main identity. It has made zero live model requests, launched zero
sidecars, and created no one-shot artifact.
```

Not yet allowed:

```text
1,000 persistent independent Agents-A1 minds are resident simultaneously
restart-persistent hybrid state reuse is operational
orthogonal recurrent states share the same physical bytes
CatalyticSwarm improves task quality
Neo3000 is SOTA
compute is physically infinite
```

Long-range target:

```text
many logical workers and tasks
+
finite physical execution substrate
+
reusable executable state
+
sparse verified communication
+
adaptive compute allocation
+
exact durable carriers
=
unbounded cumulative retained computation under bounded physical residency
```
