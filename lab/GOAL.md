# Active Goal

## Checkpoint 2: HoloState worker protocol v2

Checkpoint 0 and RSI-0 are closed; Checkpoint 1A is paused. Exact process-local prefix reuse is proven, while operational HoloState availability remains locked.

## Preserved boundary

- Legacy `/completion` exhausted 768, 1024, 1280, 1536, and 2048 tokens without the required literal final. Its single raw stream does not prove `reasoning_content` attribution. Those files are immutable and cannot be rerun.
- Worker protocol v1 stopped at Root A warm on missing complete token evidence. Its ignored result retains the original Fast=`reject` / Deep=`inconclusive` fields and exact hashes `F634CA2732CEBBE424D4634F8EFAD035C6E11EAABB0D34E40A0F1EC09A2DF975` (attempt) and `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2` (result).
- Later adjudication: v1 is an instrumentation reject; Fast and Deep capability are each untested/inconclusive because neither lane ran. V1 cannot be retried.

## Active bounded objective

Implement, push, and execute exactly one `holostate_worker_protocol_v2`. The only intervention is request-local token-array accumulation plus an 8 MiB/50,000-record reasoning-redacted stream ledger. A thinking-disabled parser canary must prove exact content, empty reasoning, normal stop, nonempty generated IDs, and completion-count agreement before root warming.

```text
canary -> warm A -> warm B -> A1 -> B1 -> A2 -> B2 -> A1 repeat -> B1 repeat -> Deep A1 -> stop
```

Fast remains thinking-disabled at 64 tokens; Deep remains reasoning-auto at 768. A1/A2 and B1/B2 are distinct assignments; determinism compares only A1 and B1 repeats. Reasoning text is never persisted. Do not run v1, `qualify-budget`, validation-v2, persistence, an extended proof, or any automatic retry.

## Claim state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE: LOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
CatalyticSwarm-0: LOCKED
automatic promotion: disabled
global claim ceiling: NEO3000_BASELINE_OPERATIONAL
```
