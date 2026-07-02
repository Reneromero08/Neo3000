# Neo3000 Roadmap

## Purpose

This document is the durable navigation spine for Neo3000. Any agent should be able to enter the repository, identify the current boundary, preserve the stable daily driver, and continue from the last proven result without reconstructing the project from chat history.

Neo3000 is a performance-first local inference engine for Agents-A1. It begins from a pinned `llama.cpp` source import and evolves the compute path toward catalytic, phase-native, recursively reusable inference.

The objective is not to wrap an ordinary runtime in governance or produce ceremonial restoration reports. The objective is to reduce the amount of fresh computation required per useful token while preserving model capability, Pi compatibility, and daily-driver stability.

---

# 1. Read order and sources of truth

Every new agent must read these files in this order:

```text
1. AGENTS.md
2. ROADMAP.md
3. lab/GOAL.md
4. lab/CHECKPOINT.md
5. lab/BASELINE_PROTOCOL.md
6. lab/results.jsonl
7. NEO3000.md
8. README.md
```

Their roles are different:

| File | Authority |
|---|---|
| `AGENTS.md` | Operating law, non-collapse protocol, engineering rules, stop conditions |
| `ROADMAP.md` | Long-range phase order, handoff cursor, entry and exit gates |
| `lab/GOAL.md` | The one active bounded objective |
| `lab/CHECKPOINT.md` | Evidence ledger for the active checkpoint |
| `lab/BASELINE_PROTOCOL.md` | Frozen measurement procedure that candidates may not rewrite |
| `lab/results.jsonl` | Compact experiment history |
| `NEO3000.md` | Architecture and hypothesis space |
| `README.md` | Bootstrap and normal user commands |

When documents disagree:

1. executed evidence outranks prose
2. `lab/CHECKPOINT.md` outranks an old status summary
3. `lab/GOAL.md` defines the current task
4. this roadmap defines phase order
5. architecture documents do not prove implementation status

---

# 2. Resume protocol

Before editing anything, run:

```powershell
git status --short
git branch --show-current
git log --oneline --decorate -15
git remote -v
git fetch origin
git log --oneline --left-right --graph HEAD...origin/main
```

Then establish:

```text
current branch
local-only commits
remote-only commits
uncommitted files
active checkpoint
last accepted experiment
stable server command
candidate worktree state
next exact boundary
```

Never assume `main` is synchronized merely because the working tree is clean.

If local and remote have diverged, preserve local work and rebase or merge deliberately. Do not reset, force-push, or discard a working runtime without explicit authorization.

---

# 3. Standing architecture

## Stable daily-driver path

```text
Pi
-> OpenAI-compatible endpoint
-> Neo3000 stable server
-> Agents-A1 GGUF
-> streamed reasoning, content, and tool calls
```

Default endpoint:

```text
http://127.0.0.1:9292/v1
```

Default model alias:

```text
agents-a1
```

## Experimental path

```text
stable source and binary
-> isolated candidate branch or worktree
-> one causal intervention
-> candidate build
-> frozen benchmark
-> quality and stability gates
-> accept, reject, or remain inconclusive
```

The stable server remains available while a candidate is built and tested. A candidate never replaces the active daily driver merely because it compiles.

## Catalytic compute primitive

```text
borrow existing compute state
-> transform through one or more trajectories
-> extract a surviving result or invariant
-> restore or close temporary state
-> retain only lawful durable state
```

Algorithms are local traces through a larger process-object. Do not reduce phase-native, topological, spectral, recurrent, or relational proposals to scalar candidate selection unless that reduction is the declared experiment.

---

# 4. Current handoff cursor

## Remote repository state

At the time this roadmap was created, GitHub `main` contained the foundation, runtime harness, baseline protocol, and context-matrix runner through:

```text
83194dc99d018222f0410afd3d201f95a939d578
```

## Reported local state, pending remote audit

A local agent reported the following completed work:

```text
CUDA Toolkit:
C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6

nvcc:
12.6, V12.6.85

GPU:
NVIDIA GeForce RTX 3060, 12 GB, SM 8.6

Build:
Visual Studio 2022 Build Tools
MSVC 19.44
llama-server and llama-bench built successfully

Model:
Agents-A1 GGUF
architecture: qwen35moe
quantization: Q4_K Medium
40 layers
256 experts, 8 active
Gated Delta Net hybrid state
SHA-256 reported as 31AEFA25B7...77C2

Stable server:
ctx-size 4096
gpu-layers auto
cpu-moe enabled
flash attention auto
f16 KV

Smoke result:
approximately 8.2 decode tokens/sec
approximately 45 prompt tokens/sec
approximately 11,653 MiB of 12,288 MiB VRAM

API:
health passed
model listing passed
non-streaming completion passed
SSE streaming passed
reasoning_content passed
second request passed

Pi:
neo3000 provider added
neo3000 selected as default
lmstudio provider preserved
```

The local agent reported commit `4ab05fa`, but that commit was not visible on GitHub when checked. Therefore the work is **reported and locally demonstrated, but not yet remotely auditable**.

## Exact next action

```text
safely synchronize the local setup commit with current origin/main
-> rebuild after synchronization
-> push the resulting commit
-> verify Pi round trip and tool call
-> verify cancellation recovery
-> characterize 8K through maximum stable context
-> freeze the LM Studio comparison
-> close or precisely map Checkpoint 0
```

No catalytic inference modification should begin before this cursor advances.

---

# 5. Phase roadmap

## Checkpoint 0: Baseline parity and context characterization

### Objective

Establish a correct, reproducible, directly Pi-compatible Agents-A1 runtime and locate the real performance boundary.

### Entrance state

- pinned upstream source identity exists
- importer exists
- CUDA build path exists
- no claim of catalytic compute

### Required work

1. synchronize local and remote repository state
2. reproduce the CUDA build after synchronization
3. prove the exact model identity
4. prove direct Pi routing to Neo3000
5. prove reasoning, content, and tool-call streaming
6. prove cancellation and immediate recovery
7. freeze the working 4K runtime configuration
8. test 8K, 16K, 32K, 40K, and 65,536 allocation
9. record prompt TPS, decode TPS, TTFT, RAM, VRAM, placement, and cached tokens
10. compare Neo3000 and LM Studio under matched conditions
11. determine source-custody strategy for the imported engine

### Exit gate

```text
Agents-A1 runs through Pi on Neo3000
and
streaming, tools, cancellation, and repeated turns are stable
and
context scaling is measured through the maximum stable point
and
Neo3000 versus LM Studio is reproducibly characterized
and
the dominant remaining performance loss is localized enough to choose instrumentation targets
```

### Claim ceiling

Before exit:

```text
NEO3000_FOUNDATION_INITIALIZED
```

After exit:

```text
NEO3000_BASELINE_OPERATIONAL
```

### Forbidden work

- inference-kernel modifications
- speculative decoding experiments
- KV compression experiments
- Delta Net state modification
- layer skipping
- automatic candidate promotion
- broad source pruning

---

## Checkpoint 1: Compute map

### Objective

Measure where time, bandwidth, memory, and state growth actually occur in Agents-A1.

Agents-A1 is a hybrid `qwen35moe` model. The compute map must distinguish at least:

```text
attention and KV traffic
Gated Delta Net recurrent state
MoE expert routing
expert weight residency and transfer
CPU-MoE execution
GPU layer or tensor displacement caused by context allocation
prompt-cache reuse
CUDA kernel occupancy
CPU and GPU synchronization
sampling and server overhead
```

### Design rule

Tracing must be optional and removable from release builds. Normal daily-driver performance must remain measurable without tracing overhead.

### Required instrumentation

- per-token and per-layer timing
- operator-family timing
- attention versus recurrent-block timing
- expert IDs selected per layer and token
- expert residency and transfer bytes
- CPU/GPU execution placement
- KV and recurrent-state allocation by context
- prompt-cache hit and reused-token counts
- CUDA synchronization and transfer events
- peak RAM and VRAM
- stable server-level timings

### Deliverables

```text
neo/trace/ or the narrowest viable upstream hooks
one fixed trace schema
one trace-disabled release build
one trace-enabled diagnostic build
one bottleneck report stored as a compact checkpoint update
```

### Exit gate

The top one or two causes of short-context cost and long-context degradation are causally localized, not merely correlated with context length.

### Claim ceiling

```text
NEO3000_COMPUTE_PATH_MAPPED
```

---

## Checkpoint 2: First catalytic compute intervention

### Objective

Remove or reuse one measured source of fresh computation while preserving Pi compatibility and model behavior.

The mechanism is selected from Checkpoint 1 evidence. Do not choose by fashion or prior roadmap order.

### Candidate families

#### A. Catalytic expert residency

Use repeated MoE routing structure to retain, prefetch, rotate, or share expert state rather than repeatedly transferring the same active experts.

Best fit when the map shows CPU-MoE bandwidth or expert movement dominates.

#### B. Recurrent-state catalysis

Treat Gated Delta Net state as an executable carrier that can be borrowed, forked, projected, or compacted without replaying equivalent history.

Best fit when recurrent-state update or context-state traffic dominates.

#### C. Single-model catalytic speculation

Use reduced-depth or alternate-path traversals of Agents-A1 to draft future tokens, then verify multiple tokens with the full model.

Best fit when serial full-model decode dominates and useful draft acceptance is plausible.

#### D. Holographic long-context side channel

Keep recent context exact while distant history is represented as an executable relational carrier queried by the current token.

Best fit when attention/KV cost or state displacement drives the long-context slope.

#### E. Layer-orbit closure

Detect relational stabilization before the final layer and skip or cheaply verify the remaining path.

Best fit when later layers often preserve an already stable token relation.

### Experiment requirements

Every intervention must declare:

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

### Exit gate

One bounded mechanism produces a repeatable improvement in the declared target metric without violating daily-driver quality, tools, stability, or memory limits.

### Claim ceiling

Use a mechanism-specific claim. Do not claim general catalytic inference from one local intervention.

---

## Checkpoint 3: Long-context catalytic state

### Objective

Flatten the decline in decode speed as context grows.

### Initial structure

```text
recent context
= exact token-level state

middle context
= structured relational blocks

distant context
= compressed executable phase, spectral, recurrent, or topological state
```

The distant representation must be executable, not a dead summary. A current query must be able to illuminate and reconstruct relevant relations.

### Required comparisons

- full exact context
- exact recent window plus side channel
- side channel disabled
- random or shuffled side channel
- equivalent memory-budget baseline

### Exit gate

The context degradation ratio improves at one or more long-context points while declared retrieval, reasoning, and tool-use gates remain within tolerance.

---

## Checkpoint 4: Layer-orbit closure and trajectory invariants

### Objective

Determine whether hidden-state evolution becomes predictively closed before the final layer.

### Candidate observables

- top-k relational ordering
- residual-direction rotation
- logit-subspace stability
- phase alignment across layer checkpoints
- branch agreement
- final-output agreement under continued evolution

Confidence alone is not a closure law.

### Exit gate

A declared relational closure condition permits measurable layer work to be skipped or replaced by a cheaper verification tail without unacceptable output divergence.

---

## Checkpoint 5: Bounded autonomous candidate loop

### Objective

Allow Agents-A1, running through stable Neo3000, to improve a candidate Neo3000 build through goals and checkpoints.

### Runtime structure

```text
stable server
serves the active Pi session

candidate worktree
receives one bounded source intervention

neo-loop
builds, launches, benchmarks, records, and tears down candidates
```

`neo-loop` is deterministic machinery. Agents-A1 remains the sole reasoning model.

### Minimal loop

```text
read GOAL and CHECKPOINT
-> inspect hot path
-> state one causal hypothesis
-> edit one mechanism
-> build candidate
-> run frozen benchmark
-> compare with stable
-> record result
-> revise or stop
```

### Mandatory stop conditions

- stable server mutation
- benchmark mutation
- output corruption
- malformed tools
- unexplained memory growth
- repeated crash
- branch-state contamination
- restoration or isolation failure
- three consecutive non-improving interventions unless the goal explicitly permits exploration

### Promotion

Automatic promotion remains disabled initially. Accepted candidates require explicit review and a meaningful architectural commit.

### Exit gate

Agents-A1 completes several bounded candidate cycles without manual command execution, benchmark drift, stable-server loss, or false success reporting.

---

## Checkpoint 6: Native catalytic kernels

### Objective

Move selected hot-path state transitions into exact borrow, transform, extract, and restore form.

Begin with operations where the inverse is exact and performance-relevant:

- permutations
- routing tables
- state reordering
- reversible cache transforms
- quantized rotations
- phase rotations
- expert-residency transitions
- speculative branch bookkeeping
- reusable dirty scratch arenas

Do not begin by claiming matrix multiplication or the complete transformer is thermodynamically reversible.

### Exit gate

At least one native kernel reduces allocation, copying, bandwidth, or fresh operator work and proves its declared restoration or closure property.

---

## Checkpoint 7: Recursive compute amplification

### Objective

Allow useful computational structure to return as substrate or operator for subsequent inference.

```text
compute
-> preserve surviving relational structure
-> re-enter that structure into later inference
-> reduce equivalent fresh computation
-> refine recursively
```

### Central metric

```text
compute amplification = equivalent baseline compute / fresh compute executed
```

This metric must be grounded in removed or reused operator work. Wall-clock speed alone is insufficient.

### Long-range target

Neo3000 should progressively make additional reasoning depth cheaper because prior computation survives as executable structure rather than being flattened into text and recomputed.

---

# 6. Source custody

The initial importer materializes pinned llama.cpp source locally. Before autonomous source modification begins, the project must choose and document one custody model:

## Option A: Track the imported runtime

Advantages:

- ordinary Git diffs
- candidate worktrees function naturally
- exact source history lives in Neo3000

Costs:

- large initial source commit
- future upstream refreshes produce broad diffs

## Option B: Preserve a generated import plus a tracked patch layer

Advantages:

- smaller repository
- clear upstream boundary

Costs:

- more complex candidate worktrees
- every experiment must reliably materialize the same source before patching
- agents may reason poorly across generated versus tracked code

The decision must prioritize reliable recursive source editing, not repository aesthetics. Do not leave the engine untracked once Agents-A1 begins modifying it.

---

# 7. Bloat boundary

Neo3000 earns complexity only when it removes more compute or operational friction than it adds.

Do not add during the early roadmap:

- MCP
- AGS governance import
- databases
- dashboards
- general plugin systems
- distributed serving
- orchestration frameworks
- report farms
- automatic stable promotion

The minimum durable control surface is:

```text
Git
AGENTS.md
ROADMAP.md
lab/GOAL.md
lab/CHECKPOINT.md
lab/BASELINE_PROTOCOL.md
lab/results.jsonl
stable and candidate builds
neo-loop when Checkpoint 5 begins
```

---

# 8. Handoff law

Before an agent stops, it must leave the repository resumable.

Update only what changed:

1. `lab/CHECKPOINT.md` with proven gates
2. `lab/GOAL.md` with the next exact action
3. `lab/results.jsonl` with one compact record when an experiment ran
4. this roadmap only when phase order, current cursor, or architecture materially changed

The final handoff must state:

```text
branch
HEAD commit
working-tree status
stable server command
candidate command, if any
model identity
checkpoint status
last executed test
result
failed or inconclusive mechanisms
files changed
next exact command
known risks
```

Never end with only a narrative report while the tracked checkpoint remains stale.

---

# 9. Commit law

Use meaningful architectural commits. Avoid micro-commit pellets.

Examples:

```text
Establish CUDA Agents-A1 baseline
Complete Neo3000 baseline characterization
Instrument hybrid inference compute path
Add catalytic expert residency prototype
Establish bounded candidate iteration loop
```

Never commit:

- model weights
- build products
- local absolute paths
- runtime logs
- benchmark caches
- temporary prompts
- secrets
- Pi credentials

A build is not proof of correctness. A faster run is not proof of a mechanism. A negative result is valid when it maps the Wall and leaves the stable runtime intact.
