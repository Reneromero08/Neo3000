# Neo3000 Roadmap

## Purpose

This is the durable navigation spine for Neo3000. Any agent should be able to enter the repository, identify the current boundary, preserve the stable daily driver, and continue without reconstructing the project from chat history.

Neo3000 is a performance-first local inference engine for Agents-A1. It begins from a pinned `llama.cpp` runtime and evolves toward catalytic, phase-native, recursively reusable inference.

The objective is not to wrap ordinary inference in governance or produce ceremonial reports. The objective is to reduce fresh computation per useful token while preserving model capability, Pi compatibility, reproducibility, and daily-driver stability.

---

# 1. Read order and authority

Every agent must read:

```text
1. AGENTS.md
2. TASKS.md
3. ROADMAP.md
4. lab/GOAL.md
5. lab/CHECKPOINT.md
6. lab/BASELINE_PROTOCOL.md
7. lab/results.jsonl
8. NEO3000.md
9. README.md
```

| File | Authority |
|---|---|
| `AGENTS.md` | Operating law, non-collapse protocol, engineering rules, stop conditions |
| `TASKS.md` | Executable queue and exact next action |
| `ROADMAP.md` | Phase order, unlock gates, long-range architecture |
| `lab/GOAL.md` | One active bounded objective |
| `lab/CHECKPOINT.md` | Evidence ledger for the active checkpoint |
| `lab/BASELINE_PROTOCOL.md` | Frozen evaluation procedure |
| `lab/results.jsonl` | Compact experiment history |
| `NEO3000.md` | Architecture and hypothesis space |
| `README.md` | Normal build, launch, and verification commands |

When documents disagree:

1. executed evidence outranks prose
2. `TASKS.md` determines the next operation
3. `lab/CHECKPOINT.md` determines what is proven
4. `lab/GOAL.md` determines the current bounded objective
5. this roadmap determines phase order and RSI unlock level
6. architecture documents do not prove implementation status

---

# 2. Resume protocol

Before editing:

```powershell
git status --short
git branch --show-current
git log --oneline --decorate -15
git remote -v
git fetch origin
git log --oneline --left-right --graph HEAD...origin/main
```

Establish:

```text
current branch
local-only commits
remote-only commits
uncommitted files
active checkpoint
last accepted experiment
stable server command
candidate worktree state
next unchecked task
```

Never assume `main` is synchronized because the working tree is clean.

Never reset, force-push, or discard a functioning stable runtime without explicit authorization.

---

# 3. Current boundary

## Proven foundation

The repository has demonstrated:

```text
CUDA 12.6 build on RTX 3060
Agents-A1 GGUF identity and full hash
OpenAI-compatible health, model, and chat endpoints
incremental SSE streaming
reasoning_content preservation
tool-call probe validity
cancellation and immediate API recovery
server allocation through 65,536 context capacity
deterministic occupied-context inference through 32,768 raw content tokens
```

## Current evidence limit

A server configured with `--ctx-size 65536` is not proof that 65,536 prompt tokens were occupied during measured decoding.

The current supported long-context statement is:

```text
Agents-A1 allocates a 65,536-token context successfully, and measured decode throughput remains approximately flat through 32,768 occupied raw content tokens.
```

The 40,960-token matrix target failed during tokenization and must be localized before stronger long-context claims are made.

## Current exact boundary

```text
finish real Pi UI verification
-> localize the 40,960 tokenizer failure
-> measure genuinely occupied 40K and 60K prompts or map a precise blocker
-> run matched LM Studio comparisons
-> separate allocation capacity from occupied-context performance
-> close Checkpoint 0
-> establish RSI-0 substrate
```

No catalytic inference change should enter the stable path before Checkpoint 0 closes.

---

# 4. Standing architecture

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
-> candidate server on separate port
-> immutable evaluator
-> quality, stability, memory, and performance gates
-> reject, accept for review, or remain inconclusive
-> candidate teardown
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

---

# 5. RSI levels

Neo3000 uses three distinct meanings that must not be conflated.

## Level 0: Pi-assisted development

Pi can inspect files, write code, build, and run commands, but the human still defines and supervises every development step.

This is available now.

It is not yet RSI because the system does not own a closed modify, evaluate, preserve, and continue cycle.

## Level 1: Supervised bounded RSI

Agents-A1 may improve a candidate Neo3000 through a deterministic loop, but:

```text
stable server remains untouched
one candidate mechanism is tested at a time
benchmark and controller hashes are immutable
failed candidates are automatically torn down
promotion requires human review
cycle count is bounded
```

This level unlocks when **Checkpoint RSI-0** closes.

## Level 2: Autonomous bounded RSI

Agents-A1 may execute several candidate cycles from a declared goal without manual command execution. It may revise or stop based on measured results, but may not automatically replace stable.

This level unlocks when **Checkpoint 5** closes.

## Level 3: Recursive compute amplification

Useful computation survives as executable state and reduces equivalent future compute, rather than only improving source code between runs.

This is the long-range target of Checkpoint 7.

---

# 6. Phase roadmap

## Checkpoint 0: Baseline parity and occupied-context characterization

### Objective

Establish a correct, reproducible, directly Pi-compatible Agents-A1 runtime and locate the real performance boundary.

### Required work

- synchronize local and remote state
- reproduce the CUDA build
- prove model identity
- prove real Pi UI text and tool round trips
- prove cancellation and immediate recovery from Pi
- freeze the stable runtime configuration
- separate configured context capacity from occupied prompt length
- measure occupied-context behavior through the maximum stable target or map a precise blocker
- compare Neo3000 and LM Studio under matched conditions
- record rolling minimum decode speed
- choose an engine source-custody model

### Exit gate

```text
Agents-A1 runs through Pi on Neo3000
and
streaming, tools, cancellation, and repeated turns are stable
and
occupied-context behavior is reproducibly characterized
and
Neo3000 versus LM Studio is reproducibly compared
and
allocation capacity is documented separately from occupied context
and
source custody is selected
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

- stable inference-kernel modification
- speculative decoding experiments
- KV compression experiments
- Delta Net state modification
- layer skipping
- automatic candidate promotion
- broad source pruning

---

## Checkpoint RSI-0: Self-improvement substrate

### Objective

Create the minimum safe substrate required for Pi to perform supervised recursive self-improvement on Neo3000.

This checkpoint comes immediately after Checkpoint 0. It does not require the compute map or a successful catalytic mechanism. It creates the machinery through which those later checkpoints can be investigated recursively.

### Source custody

The engine must be Git-diffable before Agents-A1 modifies it.

Choose and implement one model:

#### Model A: Track the pinned imported runtime

```text
one deliberate source-baseline commit
ordinary branches and worktrees
native Git diffs and rollback
explicit future upstream-refresh commits
```

#### Model B: Generated source plus tracked patch materialization

```text
exact deterministic import
tracked patch layer
candidate materialization from pin plus patch
verified clean reconstruction before every cycle
```

The selected model must support reliable branching, diffing, rollback, worktrees, and candidate reconstruction. Repository aesthetics are secondary.

### Stable and candidate isolation

Required structure:

```text
stable worktree
stable build directory
stable server port 9292

candidate worktree
candidate build directory
candidate server on a separate port, default 9393

immutable evaluator and controller outside candidate-editable paths
```

The running stable model must never edit or overwrite the executable producing its current turn.

### Immutable evaluator

Create a tracked benchmark manifest that records hashes for:

```text
benchmark prompts
expected protocol checks
quality gates
performance metrics
controller scripts
model identity
baseline commit
stable launch configuration
```

Before and after every candidate cycle, `neo-loop` verifies those hashes. Mutation invalidates the candidate.

Candidate-editable paths must be explicitly declared. The evaluator, task ledger, stable worktree, stable build, and promotion logic are outside that set.

### Deterministic candidate lifecycle

`neo-loop` must perform:

```text
read TASKS, GOAL, and CHECKPOINT
-> verify stable health
-> verify clean candidate worktree
-> record baseline commit and benchmark hashes
-> receive one causal hypothesis
-> permit one bounded intervention
-> build candidate separately
-> launch candidate on separate port
-> wait for health with timeout
-> run immutable quality gates
-> run immutable performance gates
-> record all results
-> stop candidate
-> remove candidate runtime state
-> verify stable health again
-> classify reject, reviewable accept, or inconclusive
```

### Mandatory safety gates

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
- malformed text, reasoning, or tools causes rejection
- cancellation or repeated-turn regression causes rejection
- unexplained memory growth causes rejection
- candidate process is torn down after every result
- stable health is checked before and after every cycle

### Required proof cycles

#### Supervised rejection cycle

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

#### Supervised acceptance cycle

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

### Exit gate

```text
engine source is Git-diffable
and
stable and candidate are isolated
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

### Unlock

After exit:

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

Pi may then be prompted to run one or a small bounded number of candidate cycles with human promotion review.

Automatic stable promotion remains forbidden.

---

## Checkpoint 1: Compute map

### Objective

Measure where time, bandwidth, memory, and state growth occur in Agents-A1.

Checkpoint 1 may be performed through the supervised RSI substrate. Agents-A1 can propose and implement instrumentation candidates while stable remains intact.

The compute map must distinguish:

```text
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

### Design rule

Tracing must be optional and absent from normal release cost when disabled.

### Required instrumentation

- per-token and per-layer timing
- operator-family timing
- attention versus recurrent-block timing
- expert IDs selected per layer and token
- expert residency and transfer bytes
- CPU and GPU execution placement
- KV and recurrent-state allocation by occupied context
- prompt-cache hit and reused-token counts
- CUDA synchronization and transfer events
- peak RAM and VRAM
- stable server timings

### Deliverables

```text
one fixed trace schema
one trace-disabled release build
one trace-enabled diagnostic build
one causal bottleneck map
```

### Exit gate

The top one or two causes of short-context cost and long-context degradation are causally localized rather than inferred from correlation.

### Claim ceiling

```text
NEO3000_COMPUTE_PATH_MAPPED
```

---

## Checkpoint 2: First catalytic compute intervention

### Objective

Remove or reuse one measured source of fresh computation while preserving Pi compatibility and model behavior.

The mechanism is selected from Checkpoint 1 evidence.

### Candidate families

#### Catalytic expert residency

Retain, prefetch, rotate, or share repeatedly selected expert state when measured expert movement dominates.

#### Recurrent-state catalysis

Treat Gated Delta Net state as an executable carrier that can be borrowed, forked, projected, or compacted without replaying equivalent history.

#### Single-model catalytic speculation

Use reduced-depth or alternate-path trajectories of Agents-A1 to draft future tokens, then verify several positions with the full model.

#### Holographic long-context side channel

Keep recent context exact while distant history remains an executable relational carrier queried by the current token.

#### Layer-orbit closure

Detect relational stabilization before the final layer and skip or cheaply verify the remaining trajectory.

### Experiment declaration

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

### Exit gate

One bounded mechanism produces a repeatable improvement without violating daily-driver quality, tools, stability, or memory limits.

Do not claim general catalytic inference from one local intervention.

---

## Checkpoint 3: Long-context catalytic state

### Objective

Flatten occupied-context cost while preserving executable relational structure.

```text
recent context = exact token-level state
middle context = structured relational blocks
distant context = executable phase, spectral, recurrent, or topological state
```

The distant representation must be executable, not a dead summary.

### Required controls

- full exact context
- exact recent window plus side channel
- side channel disabled
- side channel shuffled
- equivalent-memory baseline

### Exit gate

Occupied-context degradation improves while retrieval, reasoning, tools, and stability remain within declared tolerance.

---

## Checkpoint 4: Layer-orbit closure and trajectory invariants

### Objective

Determine whether hidden-state evolution becomes predictively closed before the final layer.

Candidate observables:

- top-k relational ordering
- residual-direction rotation
- logit-subspace stability
- phase alignment across layer checkpoints
- branch agreement
- final-output agreement under continued evolution

Confidence alone is not a closure law.

### Exit gate

A declared relational closure condition permits measurable layer work to be skipped or replaced by a cheaper verification tail without unacceptable divergence.

---

## Checkpoint 5: Autonomous bounded RSI

### Objective

Advance from supervised candidate cycles to several autonomous candidate cycles from one declared goal.

### Runtime structure

```text
stable Agents-A1 through Neo3000
-> reads TASKS, GOAL, and CHECKPOINT
-> formulates one causal hypothesis
-> modifies only the candidate worktree
-> invokes deterministic neo-loop
-> receives measured result
-> revises, stops, or tries the next bounded intervention
```

`neo-loop` remains deterministic machinery. Agents-A1 remains the sole reasoning model.

### Additional gates beyond RSI-0

- several cycles complete without manual command execution
- cycle budget and wall-clock budget are enforced
- three consecutive non-improving interventions stop the run unless exploration is explicitly authorized
- false success reporting is detected by evaluator evidence
- branch and result state remain resumable after interruption
- candidate crashes do not interrupt stable inference
- the model does not modify its own goal, evaluator, controller, or promotion law during a run

### Promotion

Automatic promotion remains disabled. Reviewable candidates require explicit human approval and a meaningful architectural commit.

### Exit gate

Agents-A1 completes several bounded candidate cycles without benchmark drift, stable-server loss, branch contamination, or false success reporting.

### Unlock

```text
AUTONOMOUS_BOUNDED_RSI_AVAILABLE
```

---

## Checkpoint 6: Native catalytic kernels

### Objective

Move selected hot-path transitions into exact borrow, transform, extract, and restore form.

Start with operations whose inverse or closure is exact and performance-relevant:

- permutations
- routing tables
- state reordering
- reversible cache transforms
- quantized rotations
- phase rotations
- expert-residency transitions
- speculative branch bookkeeping
- reusable dirty scratch arenas

Do not begin by claiming matrix multiplication or the whole transformer is thermodynamically reversible.

### Exit gate

At least one native kernel reduces allocation, copying, bandwidth, or fresh operator work and proves its declared restoration or closure property.

---

## Checkpoint 7: Recursive compute amplification

### Objective

Allow useful computational structure to return as substrate or operator for later inference.

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

Additional reasoning depth becomes cheaper because prior computation survives as executable structure rather than being flattened into text and recomputed.

---

# 7. Source custody law

The engine must not remain untracked once Agents-A1 begins modifying it.

The custody decision must prioritize:

```text
reliable Git diffs
candidate worktrees
clean rollback
exact reconstruction
upstream identity
licensing
agent comprehension
```

A large deliberate source-baseline commit is preferable to a smaller repository that cannot safely express candidate changes.

---

# 8. Bloat boundary

Neo3000 earns complexity only when it removes more compute or operational friction than it adds.

Do not add during the early roadmap:

- MCP
- AGS governance imports
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
TASKS.md
ROADMAP.md
lab/GOAL.md
lab/CHECKPOINT.md
lab/BASELINE_PROTOCOL.md
lab/results.jsonl
stable and candidate worktrees
stable and candidate builds
immutable evaluator manifest
neo-loop
```

---

# 9. Handoff law

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

# 10. Commit law

Use meaningful architectural commits. Avoid micro-commit pellets.

Examples:

```text
Establish CUDA Agents-A1 baseline
Complete occupied-context baseline
Establish Neo3000 source custody
Build supervised RSI substrate
Instrument hybrid inference compute path
Add catalytic expert residency prototype
Enable autonomous bounded candidate cycles
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

A build is not proof of correctness. A faster run is not proof of a mechanism. A negative result is valid when it maps the Wall and leaves stable intact.
