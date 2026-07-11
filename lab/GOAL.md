# Active Goal

## Checkpoint 2: CatalyticSwarm-0 bounded control preparation

Checkpoint 0 and RSI-0 are closed; Checkpoint 1A is paused. Exact process-local prefix reuse and the bounded process-local HoloState micro-worker are proven; broader process-local and restart-persistent availability remain locked.

## Preserved boundary

- Legacy `/completion` exhausted 768, 1024, 1280, 1536, and 2048 tokens without the required literal final. Its single raw stream does not prove `reasoning_content` attribution. Those files are immutable and cannot be rerun.
- Worker protocol v1 stopped at Root A warm on missing complete token evidence. Its ignored result retains the original Fast=`reject` / Deep=`inconclusive` fields and exact hashes `F634CA2732CEBBE424D4634F8EFAD035C6E11EAABB0D34E40A0F1EC09A2DF975` (attempt) and `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2` (result).
- Later adjudication: v1 is an instrumentation reject; Fast and Deep capability are each untested/inconclusive because neither lane ran. V1 cannot be retried.

## Preserved v2 result

`holostate_worker_protocol_v2` was implemented, pushed at `b2559f7c0c06e35a3e360b71ed13b69c4eb1eb7c`, and invoked exactly once. Its only intervention was request-local token-array accumulation plus an 8 MiB/50,000-record reasoning-redacted stream ledger. The controller stopped during sidecar readiness on `stable-listener-query-timeout`, before the thinking-disabled parser canary and before any root, Fast, or Deep request.

```text
canary -> warm A -> warm B -> A1 -> B1 -> A2 -> B2 -> A1 repeat -> B1 repeat -> Deep A1 -> stop
```

Fast remains thinking-disabled at 64 tokens; Deep remains reasoning-auto at 768. A1/A2 and B1/B2 remain distinct assignments; determinism compares only A1 and B1 repeats. None of those assignments ran. Reasoning text was never persisted. Do not run v1, v2, `qualify-budget`, validation-v2, persistence, an extended proof, or any automatic retry.

## Executed v3 result

V3 ran once. Readiness passed; the exact, normal-stop canary exposed zero token IDs against five completion tokens, so instrumentation rejected before all roots and capability lanes. Preserve this no-retry boundary.

## Executed v4 result

V4 ran exactly once with no retry. Readiness, tokenizer, canary, both roots, and all six Fast requests passed; A1/B1 repeats and cross-root isolation were exact. Deep A1 independently rejected on a 768-token length stop, so its failure does not erase the completed Fast proof. Do not rerun v4.

## Active separately scoped protocol

Integrate the draft PR #3 control substrate as one architectural commit, freeze one deterministic 32-worker/one-slot plan, and execute one protected `CatalyticSwarm-0` control proof only after exact pushed `main` and protected preflight. The proof is limited to structured Fast micro-workers, assigned prior-phase blackboard communication, exact verifier receipts, one physical lease, bounded resource evidence, and clean teardown.

Do not run Deep workers, exceed 64 completion tokens, add restart persistence, alter CUDA/kernels/model/Pi/stable behavior, touch the archived trace candidate, rerun worker protocols v1-v4, retry the swarm, or promote automatically. Before the live command, control qualification, readiness, and the parser canary are separate one-shot boundaries; no capability attempt may exist unless all three freeze as passes.

## Claim state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE: UNLOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
CatalyticSwarm-0: PREPARED_NOT_EXECUTED
STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE: LOCKED
CATALYTIC_SWARM_CONTROL_AVAILABLE: LOCKED
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN: LOCKED
SOTA_SWARM_CLAIM: LOCKED
automatic promotion: disabled
global claim ceiling: NEO3000_BASELINE_OPERATIONAL
```
