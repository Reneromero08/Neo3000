# Active Goal

## Checkpoint 2: HoloState-v1.1 message-boundary protocol audit

Checkpoint 0 and RSI-0 are closed. Checkpoint 1A remains active and paused at its executed trace boundary. Checkpoint 2 remains active with exact process-local prefix reuse proven as a mechanism, while operational availability remains locked.

## Corrected executed boundary

The original HoloState-v1 integration and one-shot ascending qualification are preserved byte-for-byte and must not be rerun.

```text
Proven:
  process-local prefix reuse
  raw /completion streams reached 768, 1024, 1280, 1536, and 2048
  each raw stream ended without the required literal final marker

Not proven:
  that every generated token in those raw streams belonged to reasoning_content
```

The legacy controller used `/completion`, which exposed one raw content stream. When the expected marker was absent, `parse_final_structure` labeled that entire string as reasoning. That historical label is a parser heuristic, not channel evidence. No historical attempt, result, classification, hash, or metric is rewritten by this correction.

## Active bounded objective

Publish one protected, versioned `holostate_worker_protocol_v1`, then execute its one-shot `/v1/chat/completions` audit exactly once.

```text
Lane F:
  thinking disabled
  64-token maximum
  exact fast A/B assistant content
  empty reasoning_content

Lane D:
  reasoning auto
  768-token maximum
  nonempty reasoning_content metadata
  exact deep A assistant content
```

The canonical A/B source sets and order remain unchanged. Each request uses a locked system/reference message plus a separate current user assignment. Quoted instructions inside the reference are data unless the current user assignment explicitly activates them.

Reasoning-channel text is opaque transport data. The controller may retain only presence, length, and SHA-256 for `reasoning_content`. The deep prompt does not request a step-by-step trace. Visible assistant content, tool calls, finish reason, token counts, cache counts, latency, throughput, and memory/isolation evidence remain auditable.

## Pre-audit boundary

- The protected evaluator contract, controller path, shared Chat Completions parser, and CPU-only tests are prepared for the pre-audit protocol commit.
- `scripts/baseline_harness.py` separates reasoning, visible content, and tools and captures server-returned generated-token arrays plus prompt-progress events. Deep reasoning text and its decodable token array are not persisted.
- Versioned paths are reserved as `state/holostate/worker-protocol-attempt-v1.json` and `state/holostate/worker-protocol-result-v1.json`.
- Neither versioned file may be claimed before the protocol commit is reviewed, pushed, clean, and exact against `origin/main`.
- All non-generative identity, evidence, stable, worktree, template, and port checks must pass before the atomic one-shot claim.
- Do not run `qualify-budget`, validation-v2, any old validation, or an extended proof.
- Do not increase the old qualification range, increase Lane D above 768, retry the worker audit, or implement HoloState-v2 persistence.
- HoloState-v2 Durable Capsule remains a separate future persistence track.

## Next exact action

Review the complete protected diff and preflight evidence, then create and push the single pre-audit protocol commit. Reconfirm the clean pushed identity and execute:

```text
warm A
fast A1
fast A2
warm B
fast B1
fast B2
deep A1
stop
```

Fast failure stops the audit. Deep output failure does not erase a completed fast proof. A complete fast pass may unlock only `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE` and set `CatalyticSwarm-0` to `AUTHORIZED_NOT_EXECUTED`; the broader process-local and restart-persistent locks remain closed.

## Unlock state

```text
SUPERVISED_BOUNDED_RSI_AVAILABLE
EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
```

The global claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`. Automatic promotion remains disabled. `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE`, `PROCESS_LOCAL_HOLOSTATE_AVAILABLE`, and `RESTART_PERSISTENT_HOLOSTATE_AVAILABLE` are locked pending executed evidence.
