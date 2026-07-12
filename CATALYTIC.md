# Neo3000 Catalytic Chat Architecture

## Status and authority

This document defines the target architecture and experiment law for making
Neo3000 a catalytic chat runtime. It synthesizes the CAT_CAS laboratory's
reversible-computing mechanisms with Neo3000's executed HoloState and
CatalyticSwarm evidence.

It is an architecture contract, not a new evidence claim, execution authority,
or replacement for the repository task board.

When files disagree, use this precedence:

1. immutable executed artifacts and their bound records in `lab/results.jsonl`;
2. `TASKS.md`, which defines the executable queue and next exact action;
3. `lab/GOAL.md` and `lab/CHECKPOINT.md`, interpreted in favor of the latest
   executed evidence;
4. `ROADMAP.md`, which defines phase order and RSI unlock levels;
5. `docs/CATALYTIC_RUNTIME_ROADMAP.md`, which defines the detailed carrier and
   swarm architecture;
6. this document, which explains the integrated catalytic-chat design.

Historical evidence remains immutable. A stale narrative paragraph does not
overrule a later executed result.

### Current reconciliation note

The CS1 cache-admission diagnostic executed exactly once and returned
`reviewable-accept`. The authoritative compact record is `neo-exp-0022` in
`lab/results.jsonl`:

```text
diagnostic contract:
  be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b
diagnostic evidence:
  a32b0b08e67e3e219a709c9493bddb31aa195392a92714f8f0be99ed48555031
requests: 3
public-root terminal token index: 4820
actual cached prompt tokens: 4822
legacy threshold: 4825
verdict: reviewable-accept
```

Older paragraphs that call this diagnostic `INTEGRATED / NOT EXECUTED` are
superseded by the executed record, the current `TASKS.md` boundary, and the
later checkpoint/goal entries. The diagnostic is immutable and no-retry.

---

## 1. Objective

Neo3000 should reduce how much fresh ordinary inference is required for each
useful chat result while preserving:

- Agents-A1 output quality;
- incremental OpenAI-compatible SSE streaming;
- separate reasoning and final-content channels;
- valid Pi tool calls;
- cancellation followed by immediate recovery;
- repeated-turn stability;
- bounded RAM and VRAM;
- exact state identity, isolation, and closure;
- stable-server availability;
- independently auditable evidence.

The system is catalytic only when useful computation survives as lawful,
identity-bound reusable state or verified structure. Merely making a kernel
faster, compressing a cache, launching many requests, or restoring a synthetic
file does not satisfy this objective.

---

## 2. Catalytic compute law

Let `W` be clean workspace and `U` be a borrowed carrier whose initial state is
`tau`. A catalytic operation must produce its result while returning the
borrowed carrier to its required closure state:

```text
f(input, W_initial, tau)
    -> (output, W_final, tau)
```

For Neo3000, the operational form is:

```text
borrow an exact identity-bound carrier
-> transform through one or more bounded trajectories
-> extract content, a tool action, an artifact, or a verified invariant
-> restore the parent state or close the child state lawfully
-> retain only verified reusable state and provenance
```

Every proposed intervention must name:

1. the expensive operation;
2. the borrowed carrier;
3. the transformation;
4. the extracted result or invariant;
5. the restoration or closure law;
6. the lawful retained state;
7. the mechanism that reduces fresh computation;
8. the output, Pi, resource, identity, and isolation gates;
9. the measurement or null that would reject the hypothesis.

Logical restoration is not a claim of zero physical energy. Regenerating a
known seed is not restoration of arbitrary unknown state. Metadata-only
eviction is not proof that server-resident state was evicted.

---

## 3. What “basically infinite compute” means

Neo3000 does not claim infinite instantaneous FLOPs, infinite VRAM, infinite
simultaneously resident models, or a free complexity-class crossing.

Define:

```text
M(t)       resident volatile hardware state at time t
R(t)       reusable state retained across all storage tiers at time t
Finst(t)   instantaneous fresh operator/FLOP rate
C(T)       cumulative verified logical work completed through time T
Wfresh(T)  fresh computation physically executed through time T
```

The target is:

```text
M(t) <= finite hardware envelope
R(t) <= finite admitted storage envelope
Finst(t) <= physical hardware throughput
C(T) may grow across bounded epochs
compute amplification = equivalent baseline compute / Wfresh(T)
```

“Unbounded” therefore means cumulative, temporal, recursively reusable, and
logically addressable. A finite physical lease pool can serve a much larger
logical population over time, while exact state and verified results prevent
the system from paying the full computation cost again.

The long-range architecture is:

```text
finite resident substrate
+ exact executable-state reuse
+ verified memoization
+ phase-native recursive decomposition
+ bounded background scheduling
+ dependency-aware tiering and eviction
= unbounded cumulative verified work with a bounded retained working set
```

The central measurement remains:

```text
compute amplification = equivalent baseline compute / fresh compute executed
```

Compute amplification, wall-clock speed, resident memory, logical population,
and physical concurrency must always be reported separately.

---

## 4. Current evidence boundary

### Proven or currently available

```text
NEO3000_BASELINE_OPERATIONAL
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE
STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE
CATALYTIC_SWARM_CONTROL_AVAILABLE
```

The current evidence supports:

- exact process-local reuse of long canonical prompt state;
- two-root A/B multiplexing without cross-root contamination;
- bounded Fast micro-workers with exact output/token evidence;
- 32 logical workers over one physical lease;
- a fixed `16 proposal / 8 evidence / 6 critique / 2 synthesis` phase graph;
- 32 verifier receipts and a 32-entry append-only hash-chained blackboard;
- exact root-terminal cache admission for the two diagnostic probes;
- bounded WDDM and host-memory evidence for the accepted control proof;
- stable/candidate isolation and complete teardown.

### Executed but not claim-advancing

- CatalyticSwarm-1 v1 executed once and stopped after two model requests before
  a task comparison completed. It is `INCONCLUSIVE / NO RETRY`.
- The CS1 cache diagnostic executed once and proved the complete public root was
  reused for its two probes. It did not test task advantage.
- CS1-v2 consumed its command attempt before artifact claim and made zero model
  requests. It is `PRECLAIM FAIL-CLOSED / NO RETRY`.
- CS1-v3 consumed its one authorized invocation preclaim fail-closed with one
  exact control artifact and zero model requests or sidecars. Its canonical
  consumed-boundary identity is
  `fb8d4270320f73e9307da5b67325cc30edeaab04e7e1ac4a01068a5a94107e14`.
- CS1-v4 is statically integrated only. Its semantic mapping repair, claim
  contract, immutable v1 scheduler, and runtime-evidence identities are
  separately bound before every prospective persistence operation.

### Locked

```text
PROCESS_LOCAL_HOLOSTATE_AVAILABLE
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN
SOTA_SWARM_CLAIM
PHYSICAL_ORTHOGONAL_STATE_SHARING_PROVEN
AUTOMATIC_PROMOTION
```

The current exact action remains preservation of CS1-v4 static custody without
invoking it. No consumed command may be rerun. A live CS1-v4 invocation requires
new explicit authority bound to the then-exact pushed protected `main` and exact
model path.

---

## 5. The catalytic chat process-object

Neo3000 treats chat computation as a local trace through a larger process-object,
not as a flat list of scalar-ranked answers.

Represent a catalytic chat state as:

```text
P = (R, V, E, Phi, C, O, I, U, B)
```

| Component | Meaning |
|---|---|
| `R` | Exact canonical root identity: model, runtime, template, configuration, token prefix, and session |
| `V` | Typed nodes: root, trajectory, observation, invariant, contradiction, unresolved obligation, closure |
| `E` | Relations: borrows, transforms, supports, contradicts, depends-on, refines, routes-to, restores |
| `Phi` | Phase: proposal, evidence, critique, synthesis |
| `C` | Carriers: live prefix state, KV/recurrent state, bounded leases, blackboard entries, artifact references |
| `O` | Observables: hashes, parent graph, lease occupancy, fresh/reused work, resource peaks, closure cost |
| `I` | Invariants: identity, phase order, root immutability, no cross-talk, bounded resources, deterministic replay |
| `U` | Unresolved claims, contradictions, missing evidence, and open restoration obligations |
| `B` | Explicit experiment and authority boundaries |

An unresolved obligation is a lawful state. It must not be silently deleted
because it lowers a score or complicates synthesis.

A synthesis object emits:

```text
verified relational bundle
+ preserved contradictions
+ unresolved frontier
+ closure receipt
+ next lawful boundary
```

It does not have to emit a winner. Scalar ranking, model confidence, AUC, or
argmax selection may be studied only when that reduction is explicitly the
declared object under test.

---

## 6. Target runtime architecture

```text
immutable task and conversation root
-> content-addressed executable-prefix lattice
-> bounded physical lease scheduler
-> branch-local KV/recurrent copy-on-write state
-> transactional typed SSE turn
-> deterministic or external verifier
-> append-only phase-native blackboard
-> verified recombination or unresolved frontier
-> exact restoration/closure
-> identity-bound retention, tiering, or eviction
```

### 6.1 Exact canonical root

Every reusable root must bind at least:

- model SHA-256;
- binary and runtime identities;
- tokenizer and chat-template identities;
- quantization, KV, adapter, and context configuration;
- sampler, reasoning, cache, and tool schema configuration;
- exact rendered token IDs and prefix hash;
- root-terminal token index;
- state-schema version;
- process/session epoch;
- parent/root identity.

A root hit is valid only when all required identity fields match.

Exact cache admission requires:

```text
common_prefix_tokens >= public_root_terminal_token_index
actual_cached_prompt_tokens >= public_root_terminal_token_index
fresh_prompt_tokens = logical_prompt_tokens - actual_cached_prompt_tokens
transport evidence accepted
token evidence accepted
model/runtime/template/config identities unchanged
```

A one-token root shortfall, tokenizer drift, template drift, stale process epoch,
or missing cache evidence is a miss or rejection, never inferred reuse.

### 6.2 Content-addressed prefix lattice

The canonical root is immutable. Branches extend it without mutating the parent.

```text
borrow:  acquire exact root R under lease L
transform: evaluate divergent suffix S in child branch B
extract: typed content, reasoning metadata, tool action, or verified artifact
restore: discard/reverse B and prove R unchanged
accept:  bind B as a new identity-bound child while retaining R
```

The lattice should track:

- exact prefix identity and hit depth;
- branch parentage;
- retained bytes;
- reuse count;
- avoided fresh tokens/operators;
- closure cost;
- current residency tier;
- last verified use;
- pin and dependency state.

All live state expires with its process session until restart persistence is
separately proven.

### 6.3 Physical leases and logical workers

Logical population may exceed physical residency. Every worker must acquire a
bounded physical lease carrying:

```text
lease_id
generation
worker_id
phase
root_id
parent_entry_ids
plan/contract identity
resource ceiling
```

Lease conservation is mandatory:

```text
leases_acquired = leases_active + leases_released + lawfully_expired
```

No lease may be double-owned, abandoned, or released before closure. Final
reconciliation requires `active_leases_after = 0`.

Cancellation increments or revokes the lease generation. Events from an older
generation cannot append a blackboard entry or commit output. Cleanup runs in a
`finally` path and targets only the owned candidate process and state.

### 6.4 Native KV and recurrent branch state

The preferred branch primitive is parent-preserving sequence aliasing or
copy-on-write rather than a full state duplicate.

```text
borrow:  parent sequence and exact recurrent/KV identity
transform: alias metadata or allocate a child cell on first write
extract: child output and state transition evidence
reject:  remove the child and restore the parent exactly
accept:  commit one identity-bound child; keep the parent immutable
```

Before this becomes an inference intervention, measure:

- attention KV bytes copied or aliased;
- recurrent-state bytes per layer;
- allocation and first-write cost;
- update, copy, snapshot, and restore duration;
- CPU/GPU residence and transfer volume;
- synchronization boundaries;
- parent hash before and after child rejection;
- child equivalence with a full-copy reference;
- rollback and closure cost.

Floating-point neural state is not assumed reversible. Exact snapshot/restore or
copy-on-write fidelity must be demonstrated.

### 6.5 Transactional typed SSE turn

Each response is a request-local transaction.

Separate accumulators must be maintained for:

- visible content;
- `reasoning_content` metadata and channel state;
- token arrays and terminal token evidence;
- indexed tool-call fragments;
- usage and completion metadata;
- cancellation and terminal state.

A tool call commits only after its fragments form valid JSON and satisfy the
declared schema. Partial tool arguments never survive into a later turn.

On `[DONE]`, successful commit, cancellation, malformed SSE, token-count
mismatch, or invalid tool JSON, the response is closed and all request-local
scratch is cleared. Persist only bounded redacted metadata; do not persist raw
reasoning text.

The old raw `/completion` stream cannot establish reasoning-channel attribution
and is not an acceptable proof path for catalytic chat quality.

### 6.6 Verified phase-native blackboard

Workers communicate through assigned, verified prior-phase entries rather than
full transcripts or unrestricted peer messaging.

```text
proposal -> evidence -> critique -> synthesis
```

Each entry binds:

- entry and sequence identity;
- phase and orthogonal logical routing code;
- worker and lease identity;
- exact assigned parents;
- compact structured claim or artifact reference;
- verifier receipt;
- previous-entry hash and new head hash;
- root, contract, model, and runtime provenance.

Same-phase parents, forged receipts, hidden-answer leakage, unverified parent
context, and chain discontinuities fail closed.

Orthogonal or phase codes are logical routing identities only. They do not prove
that opaque KV or recurrent states share the same physical bytes without
cross-talk.

### 6.7 Tiered exact state residency

The target hierarchy is:

```text
GPU live
-> pinned-host hot
-> ordinary-host warm
-> disk durable
```

Movement between tiers must preserve exact identity and integrity. A durable
receipt must exist before the only exact restoration path is evicted.

Eviction should optimize verified reuse yield rather than recency alone:

```text
verified reuse yield
    = avoided fresh computation / retained bytes and closure cost
```

Never evict:

- an active lease;
- a pinned canonical root;
- an unresolved dependency;
- state being committed;
- the only exact restoration path.

The current host cache consumes or loads entries according to existing server
semantics; it does not yet implement a persistent branch tree or cross-process
shared-memory state tier.

### 6.8 Shadow invariant sensors

CAT_CAS decoder experiments suggest that bounded global spectral readouts can
sometimes recover invariants that local lookup statistics miss. Neo3000 may test
such readouts only as shadow instrumentation for retention, routing, loop
detection, or cache invalidation.

A shadow invariant must:

- have a preregistered observable and tolerance;
- include no-op, shuffled/permuted, local-statistics, and cospectral controls;
- include construction and closure cost;
- restore the borrowed state exactly;
- never override output/tool safety gates;
- return `unknown` on gap closure, degeneracy, instability, or collision.

An extractive invariant is not automatically semantically sufficient. No
halting-oracle, topology-oracle, lattice-wall crossing, or complexity-class claim
is authorized by a finite runtime sensor.

---

## 7. Elastic cumulative-compute scheduler

The scheduler maintains separate foreground and background frontiers.

### Foreground

- Pi/user requests have priority.
- Streaming latency, cancellation, and tool safety remain interactive.
- Background work may be preempted only at a verified lease/checkpoint boundary.

### Background

- Receives bounded quanta only during measured idle capacity.
- May extend unresolved evidence, precompute verified invariants, warm lawful
  roots, or validate durable receipts.
- Must resume from a verified checkpoint or be discarded safely.
- Cannot mutate stable inference or promote a candidate.

### Recursive decomposition

Each task may open phase-native children with:

- deterministic child IDs;
- disjoint scopes;
- exact parent and root references;
- bounded request/token/resource budgets;
- explicit verifier and closure laws;
- an unresolved frontier when completeness is not established.

Children are scheduled only after the decomposition object passes validation.
Recombination requires parentage, phase order, identity, non-interference, and
deterministic verification. Conflicts remain explicit objects for critique.

### Scheduler laws

1. **Residency:** active state never exceeds the declared hardware envelope.
2. **Lease conservation:** every lease is active, released, or lawfully expired.
3. **Identity:** memo/cache hits require complete exact identity.
4. **Verification:** only verified objects become reusable state.
5. **Phase isolation:** communication follows declared prior-phase edges.
6. **Recombination:** only compatible verified objects merge.
7. **Eviction:** dependencies and exact restoration paths remain protected.
8. **Foreground fairness:** interactive work can preempt background work safely.
9. **Cumulative accounting:** retained logical work is reported separately from
   fresh physical work and wall-clock speed.
10. **Fail closed:** corruption, telemetry loss, identity mismatch, malformed
    output, or restoration failure yields miss/reject/inconclusive.

---

## 8. Source-level insertion points

These are candidate surfaces, not permissions to edit or execute them.

| Mechanism | Current source surface | Purpose |
|---|---|---|
| Physical leases | `scripts/catalytic_swarm.py` — `PhysicalLeasePool` and worker settlement | Lease ownership, generation fencing, cleanup, verifier-gated append |
| Root warming and branching | `scripts/holostate_live.py` — `completion_request`, `warm_state`, `branch_state` | Exact root identity, cache evidence, branch lifecycle |
| Root admission | `scripts/catalytic_swarm_1_v2_root_law.py` | Exact public-root terminal admission and persist-before-gate classification |
| Blackboard | `scripts/catalytic_blackboard.py` | Phase routing, append-only hash chain, independent verification |
| KV sequence branching | `src/llama-kv-cache.h`, `src/llama-kv-cache.cpp` — sequence API and `seq_cp` | Parent/child KV aliasing, deferred copies, rollback boundary |
| Recurrent state | `src/llama-memory-recurrent.cpp` | Sequence aliasing, copy-on-write cells, state sizing, read/write, snapshot/restore |
| Gated Delta Net | `src/models/delta-net-base.cpp` — `build_recurrent_attn` | Recurrent update boundary and future measurement hook |
| Graph lifecycle | `src/llama-context.cpp` | Graph reuse, scheduler reset, state save/load, future timing boundaries |
| Host state cache | `tools/server/server-task.h`, `tools/server/server-task.cpp` | Host allocation, load, eviction, and future tiering boundary |
| Pinned host buffers | `ggml/include/ggml-backend.h`, `ggml/src/ggml-cuda/ggml-cuda.cu` | Exact host/device state transfer experiments |
| SSE/tool quality | `scripts/baseline_harness.py`, `scripts/holostate_swarm_adapter.py` | Channel separation, token reconciliation, tool JSON and Pi gates |

Tracing and measurement must remain optional and compiled out of normal builds.

---

## 9. Ranked experiment program

No experiment in this section is authorized merely by being listed here.

### Stage 0 — Preserve current custody

Current exact action:

- verify the consumed CS1-v3 boundary and raw control artifact;
- verify the CS1-v4 claim contract;
- verify the immutable v1 scheduler contract;
- verify the runtime-evidence binding;
- verify evaluator locks and exact repository identity;
- verify only the consumed v3 control artifact exists and all six later v3 paths remain absent;
- verify the v4 state root remains absent;
- make zero model requests and launch zero sidecars.

Any mismatch stops the task. Do not repair and invoke under the same authority.

### Stage 1 — Complete the causal compute map

Under a new candidate-only diagnostic version, change only bounded tracing or
aggregation behavior and measure:

- backend selection and fallback reasons;
- CUDA graph capture, replay, rebuild, allocator growth, and synchronization;
- MoE expert routes, bucket geometry, padding, residency, and transfers;
- Gated Delta Net state size, allocation, update, copy, snapshot, restore,
  residence, transfer, and synchronization;
- first-request initialization versus warm steady state;
- exact-PID WDDM and host-memory behavior.

Reject or classify inconclusive on:

- missing exact-PID telemetry;
- any trace drop or truncation;
- an incomplete workload phase;
- trace residue in a normal build;
- output/tool/cancellation regression;
- stable-server mutation;
- cleanup or isolation failure.

No bottleneck may be selected from incomplete evidence.

### Stage 2 — CPU/offline closure prototypes

These can validate control laws without model inference:

1. **Prefix admission replay:** full hit, one-token shortfall, wrong root,
   tokenizer/template drift, cache-off, and retired-threshold controls.
2. **Lease/cancellation simulation:** 32 logical workers over 1, 2, and 4
   physical slots with cancellation before start, mid-stream, before commit,
   and during restore.
3. **Transactional SSE replay:** split tool fragments, interleaved reasoning and
   content, empty terminal token arrays, malformed events, and cancellation at
   every event boundary.
4. **Phase-native process graph:** deterministic typed graph transitions over
   roots, trajectories, observations, contradictions, unresolved obligations,
   and closures; include parent-phase checks, root restoration, and replay
   digest equality.
5. **Eviction simulation:** verified-yield eviction versus LRU and random under
   pinned roots and unresolved dependencies.

These tests may prove controller correctness only. They do not prove model
quality, runtime speedup, task advantage, or server-resident state behavior.

### Stage 3 — One map-selected carrier

Choose exactly one intervention after Stage 1:

- exact native prefix/KV/recurrent copy-on-write if copy/restore dominates;
- expert residency if MoE transfer, padding, or reloading dominates;
- executable graph/warm-state reuse if graph rebuild or synchronization
  dominates;
- exact Gated Delta Net state shadow/prefill if recurrent state movement or
  replay dominates.

Declare its complete catalytic law before editing. Do not blend interventions.

### Stage 4 — Separately authorized live evaluation

Compare the candidate with an identical baseline using:

- fixed model, prompts, context, sampler, template, and hardware;
- cache-off/full-replay and identity-mismatch nulls;
- at least one warmup plus three counted repetitions for every performance or
  compute-amplification claim;
- retained individual run results and median/dispersion reporting;
- warm-root cost both excluded and amortized/included;
- exact output/token/tool equivalence where required;
- cancellation and repeated-turn isolation;
- exact restoration and closure evidence;
- WDDM, host-memory, cleanup, and stable-integrity gates.

No speedup may be inferred from one run.

---

## 10. Metrics

### Fresh-compute reduction

- logical prompt tokens;
- cached and fresh prompt tokens;
- fresh operators/FLOPs per emitted token;
- avoided prompt evaluations;
- prefix-hit depth;
- carrier reuse count;
- accepted state-reuse yield;
- compute amplification.

### Performance

- prompt processing TPS;
- decode TPS;
- time to first event and first visible content;
- p50/p95 branch and queue latency;
- rolling minimum decode speed;
- graph rebuild, synchronization, copy, snapshot, restore, and closure time;
- foreground latency under background load.

### Quality and Pi compatibility

- exact visible output where required;
- nonempty and correctly separated reasoning;
- valid tool name and JSON arguments;
- incremental SSE delivery;
- completion-token reconciliation;
- cancellation followed by immediate recovery;
- repeated A/B/A/B isolation;
- no partial or duplicate tool commit.

### Resource and restoration

- physical slots and maximum active leases;
- logical worker count;
- unique resident state count;
- RAM, pinned RAM, VRAM, and disk bytes by tier;
- exact-PID WDDM peak and sample freshness;
- CPU/GPU transfer volume;
- state hash before/after restore;
- parent immutability;
- cross-branch contamination count;
- closure and eviction cost;
- active leases after completion.

### Provenance

- exact `HEAD = main = origin/main = remote main` where required;
- clean stable and candidate worktrees;
- model, binary, template, tokenizer, contract, suite, plan, and runtime hashes;
- separate claim and scheduler identities;
- artifact inventory and hash chain;
- completed request and ledger reconciliation.

---

## 11. Decisive nulls and false-positive controls

### Cache and prefix reuse

- cache disabled/full replay;
- empty or fresh session cache;
- wrong root;
- same visible text with different tokenization;
- one-token-short root coverage;
- stale model/template/config/process identity;
- report root-warm cost both excluded and amortized.

### Branch restoration

- full state clone reference;
- fresh recomputation reference;
- destructive/no-restore control;
- parent mutation after child write;
- cross-root child state;
- corruption and stale-checkpoint controls.

### Swarm and communication

- serial chain;
- best-of-N;
- sparse swarm without verifier scores;
- verified sparse swarm;
- sham verifier;
- parent-graph or phase-code permutation;
- full-transcript/all-to-all communication;
- hidden-data leakage probes.

Equal-budget task claims additionally require all frozen tasks and arms to
complete under fresh-prompt, completion-token, and total-model-token parity.

### Spectral and phase sensors

- no-op transform;
- phase/code sign shuffle or permutation;
- local-window and statistics-matched controls;
- random orthogonal basis;
- disjoint-region control;
- cospectral collision anchor;
- preregistered tolerances and `unknown` on instability.

### “Infinite compute”

Always report separately:

- logical workers;
- physical slots;
- maximum concurrent leases;
- unique resident states;
- total requests and tokens;
- retained storage;
- verification and closure cost;
- instantaneous throughput;
- cumulative retained computation;
- fresh physical computation.

---

## 12. Deferred or prohibited claims

Do not attempt or claim the following at the current boundary:

- rerunning HoloState worker protocols v1, v2, v3, or v4;
- rerunning CatalyticSwarm-0 v1 or CatalyticSwarm-0 v2;
- rerunning CS1-v1, the CS1 cache diagnostic, or CS1-v2;
- invoking CS1-v3 again;
- invoking CS1-v4 without new exact-main and exact-model authority;
- running Deep;
- task advantage or SOTA;
- automatic promotion;
- restart-persistent HoloState;
- lossy H2O/SVD KV compression as an exact carrier;
- same-byte physical superposition of opaque KV/recurrent states;
- infinite instantaneous compute or infinite resident agents;
- zero physical heat from logical reversibility;
- a halting, topology, lattice, or complexity-class oracle;
- a speedup from synthetic restoration without real model-quality gates.

The CAT_CAS real-model KV-compression result reported strong byte compression
but only approximately 2% token match and degraded generation. It is a lossy
memory null until a separately scoped quality experiment proves otherwise.

The existing restart test read a slot file but reevaluated the full prefix. A
future durable capsule must persist exact KV and recurrent state, checkpoint
metadata, token history, and complete runtime identity, then prove exact
post-restart A/B behavior with corruption and stale-identity controls.

---

## 13. Stop conditions

Stop a candidate immediately on:

- unrelated build-system drift;
- model-output corruption;
- malformed or duplicated Pi tool calls;
- reasoning/content channel contamination;
- unexplained RAM or VRAM growth;
- benchmark or evaluator mutation;
- stable-server mutation or listener replacement;
- repeated crashes;
- exact-PID telemetry loss;
- trace drop, truncation, or incomplete workload phases;
- stale or mismatched carrier identity;
- cross-root or cross-worker contamination;
- failed restoration, closure, or lease reconciliation;
- branch/worktree isolation failure;
- provenance or artifact-count mismatch.

A stop may produce a useful mapped boundary. It does not authorize a retry or a
broader claim.

---

## 14. Claim advancement ladder

### Broader process-local HoloState

Requires a separately versioned operational experiment proving multiple lawful
chat roots and branches, exact output/tool behavior, bounded resources, explicit
eviction behavior, and repeated deterministic isolation.

### Restart-persistent HoloState

Requires a new process and exact durable state restoration without full-prefix
replay masquerading as reuse. Corruption, stale identity, and nearest-checkpoint
fallback must fail safely.

### CatalyticSwarm task advantage

Requires a separately authorized equal-total-budget evaluation that completes
every frozen task and arm, preserves hidden-data isolation, satisfies token
parity, and beats all declared controls under the predeclared acceptance law.

### Recursive compute amplification

Requires multiple bounded epochs showing that verified retained state reduces
fresh computation for later useful work after including construction,
verification, closure, storage, eviction, and replay costs.

None of these unlocks imply automatic promotion.

---

## 15. Source map

- `AGENTS.md` — non-collapse protocol, experiment law, stop conditions.
- `TASKS.md` — current executable queue and exact authority boundary.
- `ROADMAP.md` — phase order and RSI unlock levels.
- `NEO3000.md` — top-level runtime mission and compute-amplification metric.
- `lab/GOAL.md` — active goal and preserved one-shot boundaries.
- `lab/CHECKPOINT.md` — executed evidence narrative.
- `lab/results.jsonl` — compact executed experiment records.
- `lab/BASELINE_PROTOCOL.md` — matched benchmark, repetition, Pi, and quality
  gates.
- `docs/CATALYTIC_RUNTIME_ROADMAP.md` — detailed carrier hierarchy, swarm
  architecture, tiering, metrics, and claim discipline.
- `scripts/holostate_live.py` — current HoloState, cache-diagnostic, and one-shot
  controller implementation.
- `scripts/catalytic_swarm.py` — physical lease and worker lifecycle.
- `scripts/catalytic_blackboard.py` — phase-native append-only blackboard.
- `src/llama-kv-cache.cpp` — native KV sequence state and branching surface.
- `src/llama-memory-recurrent.cpp` — recurrent-state aliasing, copy-on-write,
  sizing, read/write, and snapshot/restore surface.
- `src/models/delta-net-base.cpp` — Gated Delta Net recurrent update surface.
- `tools/server/server-task.cpp` — host state cache and tiering boundary.
- `CAT_CAS/MASTER_REPORT.md` at read-only reference commit
  `0fdd9fba3f3d5f37d44c2c9db94f90517b780d98` — CAT_CAS coverage and audit
  ledger summary.

Neo3000 earns catalytic complexity only when it removes more fresh computation
or operational friction than it adds, preserves the complete interactive
contract, and leaves an independently checkable restoration trail.
