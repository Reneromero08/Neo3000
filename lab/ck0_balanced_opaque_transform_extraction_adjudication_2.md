# Balanced Opaque CK0 Transform/Extraction Adjudication 2

## Decision

- Protected main: `7f3254fd72c1b6a0ec637367fcc897dea8f227f1`
- Evidence scope: binding-1 full/delete-A/delete-B plus binding-2 full information
- Adjudication status: `ADJUDICATED_VERDICT_B_QUALIFIED`
- Custody verdict: `BYTE_ARTIFACT_COMMITMENT_VERIFIED_SERIALIZATION_UNRECOVERED`
- Custody qualifier: `EXECUTION_PREREGISTRATION_SEMANTIC_IDENTITY_VERIFIED_BYTE_SERIALIZATION_UNRECOVERED`
- Extraction-contract finding: `EXTRACTION_CONTRACT_UNDERSPECIFIED_RELATIVE_TO_ACCEPTANCE_LAW`
- Deterministic readout verdict: `DETERMINISTIC_RANK_HEAD_EXTRACTION_NO_SMUGGLE_PASS`
- Selected outcome: `IMPLEMENT_DETERMINISTIC_RANK_HEAD_EXTRACTION`
- Selected lane: Lane A — controller-native deterministic rank-head extraction
- Stage-specific status: `BALANCED_OPAQUE_TRANSFORM_STAGE_SINGLETON_RESOLUTION_REPLICATED_ACROSS_TWO_PRIVATE_BINDINGS_ON_FROZEN_GEOMETRY`, qualified by unrecovered byte serialization
- Extraction status: `MODEL_AUTHORED_EXTRACTION_CLOSURE_NOT_REPLICATED_ACROSS_PRIVATE_BINDINGS`
- Claim effect: only the bounded, qualified transform-stage status is unlocked; every broader claim remains locked

The evidence separates relational transform resolution from model-authored extraction/readout closure. Binding 2 reproduced the first stage and did not reproduce the second. Its historical terminal classification remains `BALANCED_OPAQUE_RELATIONAL_COLLAPSED`; this adjudication does not replace or rewrite that result.

## Protected evidence boundary

This is a static adjudication of already completed runs. It made zero model requests, launched zero sidecars, created no secret, created no authority, reserved no run, and changed no historical evidence. The stable repository began clean with `HEAD = main = origin/main = remote main` at the protected SHA. The candidate worktree remained clean at `14de9c71593e5aea4fcfcadeda47ba5c623fadcf`.

Both ignored private roots and creation receipts remain regular, unchanged, and undisclosed. Their secret, alias-map, branch-presentation, and creation-receipt commitments recompute. Binding independence remains `14/14`; the model-visible invariant projection contains no binding identity and no cross-binding correspondence table exists. Binding-2 full authority remains consumed. Binding-2 delete-A and delete-B remain reserved, unconsumed, and unauthorized.

The execution-era byte state is classified rather than reconstructed. The binding-2 manifest records preregistration raw artifact SHA-256 `FD9638323210829C5058F9F5A5E52D57252E8ABE5029A2CC099F20102E97BB5D`. The exact preregistration Git blob at execution commit `1eb4227219c78209ba487ab68339772887018722` hashes to `D85F36FC395D14C3187E9689180D93B1578123245F84A02726105BE382F84F05`. Forty-eight bounded serialization candidates, current index/worktree bytes, and all `3,139` Git blobs among `4,017` scanned objects produced no match. The exact execution bytes are therefore unrecovered and are not claimed reconstructed.

The byte commitment itself is authenticated. The consumed one-shot authority object contains `FD963…`; its private run-key HMAC verifies; manifest, result, and closure preserve the same authority evidence; and closure binds manifest `1E330CCFB2727E3273F298D976641E4DE4CEAD1C335FE48519025E760CB6B70F`. Exact execution-era source proves `BalancedOpaqueRuntime.from_repository()` loaded and exactly reconstructed the JSON before preflight, computed the raw artifact hash directly from `path.read_bytes()`, constructed and consumed the authority before runtime-root mutation, wrote the manifest before sidecar launch, and carried the authority through result and closure.

The manifest canonical document SHA-256 `1E542902555BBED73A82CEC80ADBFA3848823CB23D536974AB3709A1F985343B` exactly equals the execution-commit document's canonical hash. All model-visible carrier content, branch and transform projections, extraction input, schemas, seeds, implementation binding, model, binary, private commitments, scoring, classification, and restoration derive from parsed semantic fields rather than whitespace, line endings, BOM state, or JSON key formatting. The accepted custody verdict is therefore `BYTE_ARTIFACT_COMMITMENT_VERIFIED_SERIALIZATION_UNRECOVERED`, with qualifier `EXECUTION_PREREGISTRATION_SEMANTIC_IDENTITY_VERIFIED_BYTE_SERIALIZATION_UNRECOVERED` carried into the narrow claim.

The complete forensic record is `lab/ck0_binding2_preregistration_byte_forensics_1.json`, SHA-256 `015558B713D6D904E7BC0393FF3D3640119AF9435CE3DB3C8A449D69788DAE61`.

## Exact four-run custody

| Condition | Run | Manifest SHA-256 | Result SHA-256 | Closure SHA-256 |
|---|---|---|---|---|
| Binding-1 full | `ck0-balanced-v1-full-r1` | `A129BBD9BA9DEF0842144178B94A0269F66022EF82DB60D517CDD0C423CC2E1D` | `B57FE3598A03F7CBB2765F77CE702293F72BBF900424F9592D719CF02DA458F8` | `FE918337A82C7D9D2C59DE56514D284C736A239226F03C91E8025811E92E8DDA` |
| Binding-1 delete-A | `ck0-balanced-v1-delete-a-r1` | `03508F7AE5E5F4A812C43F02FD31A3EE4009530B1CB17E61056213AE1079E74E` | `7AE2578A6D48831B5335CE2826424EA375EB169A218502B404BD031507635846` | `4A2DD55ECC2DD03AE272F08FEB611F97E714EB587A28BD0660673E116286C873` |
| Binding-1 delete-B | `ck0-balanced-v1-delete-b-r1` | `EF2160E9CA719A4120FF7F7F226A1AD76F0BF08FE6A5C58CFFADCBCE2AB8B782` | `F0E24AAA61A2E8D0EC567F93444E08FD81EB8AFE36E2C01D7397A4D06FD46CB6` | `880E238B877602AE3A869E2071DBDF1B0D3EE0FAF3D0D019C2D133D05C57BF90` |
| Binding-2 full | `ck0-balanced-v1b2-full-r1` | `1E330CCFB2727E3273F298D976641E4DE4CEAD1C335FE48519025E760CB6B70F` | `17B5E36EDC0261B8D98D25F5F4F9E4884F86F6982C8F4D51EA3E54AAE90A88E5` | `24676B5E148E545BFF3339187C651791C2BC47273452F4705802AC515B95C06D` |

All twelve manifest/result/closure files rehash exactly. Every result is complete. Every closure binds its manifest and result, proves the run lock absent, and preserves terminal run custody. All branch, transform, extraction, and restoration artifacts verify against their original run-bound commitments. The binding-2 raw preregistration bytes remain unrecovered, but their hash is consistently authenticated across receipt, manifest, result, and closure; exact semantic identity is independently verified.

## Strongest coherent process-object

```text
borrow immutable process-local opaque carrier
  |
  +--> branch-a unresolved relation --\
  |                                  +--> model-authored ordered transform relation
  +--> branch-b unresolved relation --/                 |
                                                         v
                                           model-authored extraction choice
                                                         |
                                                         v
                                          private verification and score
                                                         |
                                                         v
                                             restore and close carrier
```

The controller constructs and privately verifies the branch relations from frozen public geometry and a private binding. The model authors the transform operator and ordered opaque ranking. The extraction stage receives only that committed ordered artifact and chooses one member. Private correspondence and public scoring occur after the choice. The terminal composite classifier requires both transform-stage resolution and extraction closure, so a collapsed terminal label does not identify which stage failed.

This remains bounded hybrid controller/model process-local prefix-carrier catalysis with lawful child closure. It is not pure model-internal catalysis or classical dirty-tape catalysis. CAT_CAS contributes the applicable discipline: preserve the process-object through transformation, extract only at an explicit boundary, do not truth-label or privately prioritize a branch, and restore the borrowed carrier under an exact declared tier.

## Stage-resolved evidence matrix

Every cell below was recomputed privately from the raw artifacts; no alias or ranking is persisted.

| Run | Full parents at transform? | Transform top singleton? | Historical extraction singleton? | Historical score | Historical terminal classification |
|---|---:|---:|---:|---:|---|
| Binding-1 full | yes | yes | yes | 5/5 | `BALANCED_OPAQUE_RELATIONAL_VISIBLE` |
| Binding-1 delete-A | no; A informative content withheld | no | no | 3/5 | `PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED` |
| Binding-1 delete-B | no; B informative content withheld | no | no | 3/5 | `PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED` |
| Binding-2 full | yes | yes | no | 3/5 | `BALANCED_OPAQUE_RELATIONAL_COLLAPSED` |

Binding-1 full and both deletion transforms used operator label `refine`; binding-2 full used `reconcile`. That label variation is observed and unresolved. It is neither proof of operator equivalence nor evidence that the transform mechanism failed.

## Extraction instruction, schema, parser, and classifier audit

The committed extraction assignment says: `Select one opaque candidate from the supplied ranking.` The response schema requires only `candidate_alias` drawn from the opaque alias vocabulary. The parser accepts that alias when it occurs anywhere in the supplied transform ranking. Neither interface encodes position-zero selection.

The terminal classifier requires more:

1. transform ranking position zero is the private singleton;
2. extraction selects that private singleton;
3. private mapping marks the selection as the full-public winner;
4. private public score is 5/5.

The answers to the frozen audit questions are therefore:

1. No, the instruction does not normatively require the first-ranked alias.
2. No, the schema does not encode rank-head selection.
3. No, the parser does not reject a non-head ranked alias.
4. Yes, a model can satisfy the instruction, schema, and parser while forcing terminal collapse.
5. Yes, binding-2 extraction is schema-valid, parser-valid, and instruction-admissible despite failing the acceptance law.
6. Yes, binding-1 extraction success depended on an otherwise unconstrained choice among ranked aliases.
7. Yes, the end-to-end classifier conflates transform failure with readout-choice failure.
8. The extraction stage adds no new relational information; it only selects from an already ordered committed transform artifact.

Exact finding: `EXTRACTION_CONTRACT_UNDERSPECIFIED_RELATIVE_TO_ACCEPTANCE_LAW`.

The binding-2 choice is not classified as malicious, random, or erroneous. It was admitted by the frozen model contract.

## Private deterministic rank-head counterfactual

The counterfactual verifies each transform artifact and commitment, freezes position zero before private lookup, privately maps only the frozen alias, recomputes the five-example score, and verifies an ephemeral deterministic extraction receipt. It is `STATIC_READOUT_COUNTERFACTUAL_ONLY`, not a historical result.

| Run | Rank-head singleton? | Rank-head score | Historical extraction singleton? | Historical classification changed? |
|---|---:|---:|---:|---:|
| Binding-1 full | yes | 5/5 | yes | no |
| Binding-1 delete-A | no | 3/5 | no | no |
| Binding-1 delete-B | no | 3/5 | no | no |
| Binding-2 full | yes | 5/5 | no | no |

The complete bounded record is `lab/ck0_balanced_opaque_rank_head_counterfactual_1.json`. It is not an executed experiment and is not entered into `lab/results.jsonl`.

## Deterministic extraction no-smuggle analysis

The audited order is fixed:

```text
verify transform artifact and commitment
freeze selected alias = ranking[0]
only then consult private mapping
score the frozen selection
bind the deterministic extraction receipt
```

No-smuggle passes because the model authored and committed the ranking order; the selection law is fixed independently of profile, binding, mode, alias identity, support, and score; the controller does not inspect private state before selecting; private mapping occurs only afterward; the same law preserves failures in both deletion controls; the transform commitment is consumed exactly; and deterministic extraction adds no hidden relation. A failed transform top remains a failed readout and cannot be privately converted into success.

Exact verdict: `DETERMINISTIC_RANK_HEAD_EXTRACTION_NO_SMUGGLE_PASS`.

## Three-lane comparison

| Lane | Scientific role | Verdict |
|---|---|---|
| A — controller-native deterministic rank-head extraction | Makes readout a fixed projection of the model-authored ordered relation; preserves full/control distinction without private selection | Selected under accepted Verdict B and its explicit custody qualifier |
| B — explicit model rank-head characterization | Useful only if deterministic projection fails no-smuggle or the counterfactual fails the frozen distinction; synthetic and non-catalytic | Not selected |
| C — unchanged end-to-end full replication | Repeats an architecture whose extraction contract admits terminal-failing non-head choices | Disqualified until extraction semantics are repaired |

## Frozen decision-law result

The extraction interface admits any ranked alias while acceptance requires the top/private winner, so Lane C is disqualified. The private counterfactual returns singleton/5-of-5 for both full-information runs and non-singleton/3-of-5 for both binding-1 deletion controls. Deterministic extraction passes no-smuggle. Verdict B receives `PASS / PASS / PASS`: exact byte commitment is authenticated, semantic identity is exact, and raw serialization is non-model-visible and scientifically inert. The frozen decision law therefore selects:

`IMPLEMENT_DETERMINISTIC_RANK_HEAD_EXTRACTION`

Lane A is selected for a later separately authorized static implementation/preregistration operation. This adjudication grants no live authority and reserves no run.

## Stage-specific claim adjudication

Both private roots were independently generated. Both full-information runs preserve the frozen task and relational geometry. Both transform artifacts verify and place their own private singleton first. Binding identity and correspondence were not model-visible. Transform-top success was part of the frozen preregistered acceptance pipeline.

The transform-stage matrix supports and unlocks the following bounded non-production status:

`BALANCED_OPAQUE_TRANSFORM_STAGE_SINGLETON_RESOLUTION_REPLICATED_ACROSS_TWO_PRIVATE_BINDINGS_ON_FROZEN_GEOMETRY`

Every use of that status carries the explicit custody qualifier `EXECUTION_PREREGISTRATION_SEMANTIC_IDENTITY_VERIFIED_BYTE_SERIALIZATION_UNRECOVERED`. It does not claim recovery of the exact binding-2 preregistration serialization.

The status is only about the ordered transform stage. It does not imply end-to-end replication, extraction closure replication, binding-2 deletion dependence, causal replication, general necessity, transfer, general catalytic inference, task advantage, superiority, SOTA, or broader HoloState.

The complementary stage finding is:

`MODEL_AUTHORED_EXTRACTION_CLOSURE_NOT_REPLICATED_ACROSS_PRIVATE_BINDINGS`

## Historical terminal classifications preserved

- Binding-1 full: `BALANCED_OPAQUE_RELATIONAL_VISIBLE`
- Binding-1 delete-A: `PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED`
- Binding-1 delete-B: `PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED`
- Binding-2 full: `BALANCED_OPAQUE_RELATIONAL_COLLAPSED`

No counterfactual replaces any historical classification.

## Scientific interpretation and remaining confounds

Supported at this boundary:

- binding-1 bilateral transform dependence under its exact two deletion controls;
- full-information transform-stage singleton resolution under each of two independent private bindings on frozen geometry;
- lawful restoration and process-local closure in all four runs;
- end-to-end binding invariance remains unestablished;
- model-authored extraction closure was not replicated.

Remaining confounds include fixed task geometry, fixed request seeds, fixed parent order, deterministic single observations per condition, commitment-token and payload-shape effects, and unresolved `refine` versus `reconcile` operator-label semantics. No formal p-value is assigned because no justified exchangeable sampling model is established.

Not supported: binding-2 parent dependence; causal dependence replicated across bindings; end-to-end cross-binding replication; general two-parent necessity; transfer; general catalytic inference; task advantage; superiority; SOTA; broader process-local HoloState; restart persistence; Deep; or automatic promotion.

## Read-only auditor outcomes

Exactly three new read-only custody audits were dispatched after the main forensic report and execution-chain reconstruction were frozen:

1. byte-forensic auditor: `PASS`; 5/5 tests passed, all 48 candidates reproduced, 4,017 Git objects containing 3,139 blobs were scanned, and no exact byte match was found or claimed;
2. cryptographic-chain auditor: `PASS`; `FD963…` is consistently HMAC-bound across receipt, manifest, result, and closure, canonical and implementation identities match, and exact semantic validation preceded sidecar launch;
3. scientific-materiality and no-smuggle auditor: `PASS`; raw serialization is non-model-visible and scientifically inert, canonical semantic custody is sufficient for the narrow transform-stage conclusion, and Verdict B may select Lane A under the required qualifier without smuggling or claim expansion.

No auditor edited files, invoked inference, launched a sidecar, exposed private values, created authority, or published work. No re-audit was required.

## Exact next separately authorizable static operation

`Statically implement and preregister balanced-opaque-relational-carrier-v2-deterministic-rank-head-extraction with no live execution.`

That later operation must preserve the custody qualifier, frozen carrier geometry, transform authorship, no-smuggle selection order, historical evidence, and all claim locks. No live run, reservation, authority, or historical rewrite is implied.

## Claims remaining locked

- end-to-end cross-binding replication;
- binding-2 parent dependence;
- causal dependence replicated across bindings;
- general two-parent necessity;
- transfer;
- general catalytic inference;
- task advantage;
- superiority;
- SOTA;
- broader process-local HoloState;
- restart persistence;
- Deep;
- automatic promotion.

The global production claim ceiling remains unchanged.
