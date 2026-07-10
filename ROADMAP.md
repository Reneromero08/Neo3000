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
4. lab/GOAL.md
5. lab/CHECKPOINT.md
6. lab/EVALUATOR.json, when present
7. lab/BASELINE_PROTOCOL.md
8. lab/results.jsonl
9. NEO3000.md
10. README.md
```

| File | Authority |
|---|---|
| `AGENTS.md` | Operating law, non-collapse protocol, engineering rules, stop conditions |
| `TASKS.md` | Executable queue and exact next action |
| `ROADMAP.md` | Phase order, unlock gates, long-range architecture |
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
6. architecture documents do not prove implementation status

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
-> Checkpoint 1: compute map is active
```

No autonomous RSI. No automatic promotion. No stable inference modification outside declared candidate cycles.

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

---

# 4. RSI levels

## Level 0: Pi-assisted development

Pi can inspect files, write code, build, and run commands, but the human still defines and supervises each development step.

This is the current level.

It is not yet RSI because the system does not own a closed modify, evaluate, preserve, and continue cycle.

## Level 1: Supervised bounded RSI

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

This level unlocks when Checkpoint RSI-0 closes.

## Level 2: Autonomous bounded RSI

Agents-A1 may execute several candidate cycles from a declared goal without manual command execution. It may revise or stop based on measured results, but may not automatically replace stable.

This level unlocks when Checkpoint 5 closes.

## Level 3: Recursive compute amplification

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

### Unlock

After exit:

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
```

Pi may then be prompted to run one bounded supervised candidate cycle with human promotion review.

Automatic stable promotion remains forbidden.

---

## Checkpoint 1: Compute map

Checkpoint 1 may use the supervised RSI substrate after RSI-0 closes.

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

---

## Checkpoint 2: First catalytic compute intervention

Remove or reuse one measured source of fresh computation while preserving Pi compatibility and model behavior.

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
