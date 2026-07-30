# AUDIO/CATVM INFERENCE INTEGRATION DRIFT

## 1. Status and time window

This is an append-only scientific interpretation correction. The complete
Linux live-boundary and integration window is:

```text
e1b174791ee3ecf24c3d90cb6dd8296e6828a318
through
ffcb9719d97cf6ec7280026097bfae32fbed7857
```

The inference-carrier drift begins with the `neo-exp-0094` preregistration at
`238f87dd95a97c61d47ba5a5f889704f16b2505f`, enters source at
`ed5d3af4110968855e9ab64afd21da8a63d95acf`, spans consumed
`neo-exp-0094` through `neo-exp-0101`, and ends at the unconsumed static
`neo-exp-0102` checkpoint `ffcb9719d97cf6ec7280026097bfae32fbed7857`.
The last accepted live-boundary result before that drift is `neo-exp-0093` at
`07298c46e5c8f8d81e3c19e26f9c75ecfb920c90`.

No `neo-exp-0102` completion request, prompt evaluation, model callback, or
scientific contact occurred. Its only server contact was the already recorded
tokenizer/template derivation.

## 2. What drifted

- A reversible encoding of four already classical softmax scores was treated
  as progress toward phase-relational inference. The four twin-rail pairs do
  not interact, and the useful answer is already complete in the input logits.
- Reuse of a numerically restored 128-byte complex-cell workspace was discussed
  too closely to reuse of restored inference knowledge. The model, CUDA/KV
  state, host logits, metadata, counters, identities, strings, allocator state,
  and complete object are not restored.
- Public request strings and integers checked for equality were called
  `owner-bound` despite having no server-issued capability, peer credential,
  MAC, signature, protected process, or protected mapping.
- Controls that directly assigned four equal output scores were called
  `dephased`; no state-level dephasing channel was applied.
- Source-text and source-order checks were counted beside behavioral custody
  and lifecycle evidence. A cancellation source check passed while the
  underlying release path could retain a captured live boundary.
- Nested predecessor imports, `.parent` chains, and global monkey-patching
  turned controller and audit repairs into scientific successor pellets.
- Two closely related frozen four-choice prompt instances were framed too
  strongly as task-family breadth.
- The precontact `0102` design did not require both live evidence rows to be
  causally necessary or require F-off and G-off live ablations.
- The `0102` exact oracle proved a one-lane identity while its separate
  four-lane product tuple was not realizable by normalized nonnegative
  probability vectors: its products sum to one, so
  `sum(sqrt(p_i*q_i)) > 1`, violating the necessary condition.
- The active architecture was optimizing a reversible argmax wrapper. Its
  carrier remained resident while model inference proceeded, but did not drive
  suffix model computation.

## 3. Why it happened

No individual agent is assigned blame. The failure was systemic:

- autonomous continuation optimized for the next frozen acceptance gate;
- experiment identities and documentation rewarded incremental packets;
- individually cautious claim ceilings accumulated into stronger framing;
- summaries and source-shape checks were trusted before full path audits;
- audio mechanisms transferred by formal resemblance without proving inference
  necessity on the Agents-A1 path;
- no permanent anti-pellet or carrier-causality gate existed in mandatory
  repository instructions.

## 4. What remains valid

- Native Linux CUDA toolchain qualification and the 139 configured-unit closure.
- The live CUDA KV/recurrent plus exact terminal-logit boundary.
- Exact one-use live continuation with zero fresh consumer prompt tokens.
- The split-decode seam: exact first row, resident suffix decode, exact second
  row, final-response withholding, and cleanup before release.
- Numerical forward/inverse and eight-cell restoration machinery as a
  calibration backend.
- Seed zeroing and staged cleanup paths that actually execute.
- Accepted bounded measurements under their corrected narrow interpretations.
- Every historical experiment identity, raw result, attempt, hash, and commit.

## 5. Reclassified terminology

| Historical wording | Correct active wording |
|---|---|
| owner-bound | structurally contract-bound |
| dephased control | forced-equal-score sham |
| phase-relational inference | reversible scalar-score encoding calibration |
| restored carrier/fiber | numerical restoration of the eight-cell array, with separately stated scope |
| restored inference-state reuse | restored numerical workspace backing reuse |
| two unrelated task families | two closely related frozen four-choice task instances |
| public-descriptor inverse rematerialization | public-topology inversion with retained private evidence parameters |
| open unresolved intermediate | externally withheld staged numerical state with a duplicate classical seed |

Historical raw logs and consumed result lines retain their original bytes.
These aliases govern current interpretation and future active code.

## 6. Verified defects and preventive actions

| Finding | Prevention or repair authority |
|---|---|
| Captured live boundary could survive cancellation/release while `terminal_logits_pending_use == false` | `tools/server/neo3000-live-terminal-lifecycle.h`, `scripts/catalytic_frontier_live_terminal_lifecycle_selftest.cpp`, and the `AGENTS.md` behavioral-evidence law |
| Sleep destroyed model/context without first poisoning resident custody | `tools/server/server-context.cpp` poison-before-destroy paths plus the live lifecycle selftest |
| `A1 -> B1 -> A1` identity replay remained admissible | `tools/server/neo3000-twin-rail-fiber.*` server epoch/tombstones plus `scripts/catalytic_frontier_twin_rail_runtime_selftest.cpp` |
| ownership metadata advanced before transaction success | staged metadata implementation and rollback tests in both native twin-rail selftests |
| equal-score assignment mislabeled as dephasing | density-level numerical decoherence in `neo3000-twin-rail-fiber.cpp` and native/oracle controls |
| invalid detached four-lane oracle products | `scripts/catalytic_frontier_two_evidence_exact_oracle.py` normalized near-tie, peaked, and order-sensitive fixtures |
| ignored sidecar `guarded(timeout=...)` argument | `scripts/catalytic_frontier_linux_sidecar.py` and `scripts/test_catalytic_frontier_linux_sidecar.py` |
| nested controller inheritance and monkey-patching | `scripts/catalytic_runner.py`, immutable `scripts/experiment_specs/*.json`, and `scripts/test_catalytic_runner.py` |
| source checks counted as lifecycle proof | `AGENTS.md` plus `scripts/TEST_EVIDENCE_CLASSIFICATION.md` |
| missing carrier necessity gates | carrier-causality and necessity-ablation laws in `AGENTS.md`, represented as blocking controls in the `0102` declarative spec |

## 7. Historical integrity law

No consumed experiment, raw result, attempt record or commit is deleted or
rewritten to conceal the drift. Corrections are append-only and supersede
interpretation, not history.

## 8. Resolution

The realignment implementation is verified at
`9a1aaaf79d0ef3d23ae971ca2247afaee67edf54`. The native/CUDA build,
behavioral tests, exact oracle, declarative specs, and zero model-contact counts
are bound in `lab/realignment-2026-07-29-verification.json`.

This closes the incident’s active repair phase. It does not close the
scientific frontier: no inference-bearing phase carrier or catalytic inference
claim was produced. The repository is paused for a new user-authorized goal.
