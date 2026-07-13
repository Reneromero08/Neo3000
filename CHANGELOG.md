# Neo3000 Changelog

This changelog records the architectural history of Neo3000: what became operational, what was measured, what hypotheses were rejected, what safety boundaries were added, and which claims are actually supported by pushed evidence.

It is intentionally not a raw dump of every administrative commit. Small documentation and pointer updates are compressed into the milestone they served.

## Current state

### CatalyticSwarm-1 independent post-request closure successor

The CS1 cache diagnostic executed once with `reviewable-accept`, proving complete public-root reuse for both probes and retiring the legacy common-prefix threshold as admission authority. Evidence binding is `a32b0b08e67e3e219a709c9493bddb31aa195392a92714f8f0be99ed48555031`. CS1-v2 and CS1-v3 are consumed preclaim fail-closed boundaries. V3 persisted one exact control marker and stopped before live work because mapping insertion order was treated as contract identity; canonical boundary SHA-256 is `fb8d4270320f73e9307da5b67325cc30edeaab04e7e1ac4a01068a5a94107e14`.

CS1-v4 executed exactly once and is permanently consumed. It completed 775 model responses and six equal-budget tasks, then stopped on task 7's common-root warm before the 775th ledger and host-memory records. The exact failed compound-predicate member is unavailable. All seven artifacts are immutable; canonical boundary SHA-256 is `5305192d4509028dbf4cf71d42af04d9703e3320d47cf1000cd60358f8a5044a`; the public v4 command is hard-retired.

CS1-v5 executed exactly once from protected `241d99e403926b8ef7814c894808922b7cb8cd8e`. It completed 775 responses, persisted 775 ledger records, used zero fallback records, and rejected record 775. Host success accounting is 774 / 775, but all measured host values remained below the 4,096 MiB ceiling. The exact failed member of the compound live boundary is unavailable and no task advantage was established. Canonical consumed boundary is `897148680e426caf58b9581f06224f904cb8ff5cd1a389b83c1ceedfc427f9d9`; V5 is hard-retired.

CS1-v6 is statically integrated and unexecuted. It independently records WDDM, stable custody, candidate custody, and host-memory attempts, observations, outcomes, bounded exceptions, and measurements without allowing an earlier non-pass to erase later safe evidence. Its states are `passed`, `failed-invariant`, `observation-error`, `unavailable`, `interrupted`, and `blocked`; counters distinguish groups, attempts, completed observations, passes, and blocked-before-attempt cases. Exactly one identity-bound ledger-or-fallback representation is fsynced before lease release and enforcement. Claim `8136be5c402497b539595eeccf1329807eba59fab9813891f0293fd1d271acd8` and runtime binding `3ccb810684824a5935c89150e0f84ca820f8402f7650d3fdcf027e84ac9f9ad3` remain separate from immutable scheduler `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`. All seven V6 runtime paths are absent; no V6 authority or execution exists. Claims remain unchanged.

The final static audit removed hidden warm/final compound resource observations, revalidates all consumed V5 artifacts at terminal, binds expected runtime identity in the consumed control marker, and closes ledger/fallback ambiguity with rollback-before-fallback plus fail-closed indeterminate durability. The complete 723-test CPU suite, changed-file compilation, evaluator lock, JSON/JSONL validation, protected diff checks, and protected preflight pass without a model request or sidecar launch.

Static CS1-v3 preauthorization review repaired controller-only custody defects without changing the frozen experiment: active v3 path reuse at live control; durable invocation consumption before every fallible preclaim check; identity-bearing first-ledger creation; root-terminal transport projection into the immutable scheduler schema; completed-response-aware CS1-native terminal WDDM and exact partial-count reconciliation; and final model/binary rehashing under Windows leaf and directory-chain locks with stable file IDs held through model readiness. Protected preflight failures are read-only. No live command, model request, sidecar, artifact claim, Deep request, or promotion occurred.

Current state is defined by the pushed task board, checkpoint ledger, evaluator lock, and evidence records rather than a fragile changelog commit pointer.

```text
Checkpoint 0: CLOSED
Claim ceiling: NEO3000_BASELINE_OPERATIONAL
Current RSI level: Level 1, supervised bounded RSI available
Checkpoint 1A: ACTIVE / PAUSED
Checkpoint 2: ACTIVE
First catalytic intervention: HoloState-v1 Live Prefix Lattice
HoloState-v1 integration verdict: INCONCLUSIVE
HoloState-v1 budget qualification: NO PASS THROUGH 2048
HoloState worker v1: INSTRUMENTATION REJECT; FAST/DEEP CAPABILITY UNTESTED
HoloState worker v2: EXECUTED ONCE / INCONCLUSIVE BEFORE CANARY
HoloState worker v3: READINESS PASS / CANARY INSTRUMENTATION REJECT / FAST-DEEP UNTESTED
HoloState worker v4: REVIEWABLE ACCEPT / FAST ACCEPT / DEEP REJECT
Mechanism status: EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN
PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE: UNLOCKED
PROCESS_LOCAL_HOLOSTATE_AVAILABLE: LOCKED
RESTART_PERSISTENT_HOLOSTATE_AVAILABLE: LOCKED
CatalyticSwarm-0: EXECUTED ONCE / CONTROL QUALIFICATION PASS / READINESS INCONCLUSIVE
CatalyticSwarm-0 v2: REVIEWABLE ACCEPT
CatalyticSwarm-1: EXECUTED ONCE / INCONCLUSIVE
CatalyticSwarm-1 authorization: CONSUMED / NO RETRY
CatalyticSwarm-1 boundary: EXECUTED ONCE / INCONCLUSIVE / NO RETRY
CatalyticSwarm-1 live model requests: 2
CatalyticSwarm-1 common-root warm / comparison / completed tasks: 1 / 1 / 0
CatalyticSwarm-1 sidecar launches: 1
CatalyticSwarm-1 one-shot artifacts: 6 PRESENT / TASK RESULTS ABSENT
CS1 cache-admission diagnostic: EXECUTED ONCE / REVIEWABLE ACCEPT / NO RETRY
CS1 cache-admission diagnostic completed model requests: 3
CS1 cache-admission diagnostic artifacts: 5 PRESENT / IMMUTABLE
CS1-v2: COMMAND ATTEMPT CONSUMED / PRECLAIM FAIL-CLOSED / ZERO REQUESTS / ZERO ARTIFACTS / NO RETRY
CS1-v3: COMMAND INVOCATION CONSUMED / PRECLAIM FAIL-CLOSED / ZERO REQUESTS / ONE CONTROL ARTIFACT / NO RETRY
CS1-v4: EXECUTED ONCE / PARTIAL 775 REQUESTS / INCONCLUSIVE / NO RETRY
CS1-v5: EXECUTED ONCE / 775 LEDGER RECORDS / INCONCLUSIVE / NO RETRY
CS1-v6: STATICALLY INTEGRATED / NOT EXECUTED / INDEPENDENT POST-REQUEST CLOSURE
STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE: UNLOCKED
CATALYTIC_SWARM_CONTROL_AVAILABLE: UNLOCKED
CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN: LOCKED
SOTA_SWARM_CLAIM: LOCKED
RSI-0F supervised rejection cycle: PASSED
RSI-0G supervised acceptance cycle: REVIEWABLE ACCEPT
Automatic promotion: DISABLED
SUPERVISED_BOUNDED_RSI_AVAILABLE: UNLOCKED
Stable server: port 9292
Candidate server: port 9393
```

The authorized inert-fixture RSI-0G cycle returned `reviewable-accept`. Candidate PID/listener `38952` passed transport, reasoning, tool, cancellation, repeat, and warm-performance gates; PID-filtered WDDM recorded a 2,196.88 MiB peak across 88 valid samples. One pre-first-valid counter miss remained within the locked grace period; telemetry was not lost after attribution began. Candidate teardown, runtime removal, port retirement, and five independent WDDM retirement checks passed. Stable PID `31188`, health, worktree, and protected hashes remained unchanged. No promotion or merge occurred. RSI-0 is closed; Checkpoint 1 is active.

---

## Unreleased

### Pending

- Checkpoint 1A remains active but paused. Compile-out, bounded aggregation, protected exact-PID control, and explicit truncation/drop detection are proven; overhead, a completed workload map, and model-runtime bottleneck selection remain unproven.
- Checkpoint 2 is active for HoloState-v1 Live Prefix Lattice, the protected operational integration of exact process-local executable-prefix reuse already proven by HoloState-0.
- The one-shot HoloState-v1 raw `/completion` qualification is complete: `1024, 1280, 1536, 2048` all exhausted without the exact final marker. This does not prove `reasoning_content` attribution. No budget was selected and validation-v2 remains unattempted.
- HoloState-v1.1 executed once and stopped at Root A warm on missing token instrumentation. Its original result fields remain Fast=`reject` / Deep=`inconclusive`; later adjudication is protocol instrumentation-reject with both capabilities untested/inconclusive. V1 cannot be retried.
- Worker protocol v2 ran exactly once and stopped during sidecar readiness on `stable-listener-query-timeout`, before its canary. It cannot be retried; no parser or model-capability conclusion is supported.
- Worker protocol v3 ran once: checked readiness passed, then its parser canary instrumentation rejected on missing nonempty token arrays and completion-count mismatch. It cannot be retried; Fast and Deep remain untested/inconclusive.
- Worker protocol v4 ran exactly once with no retry. Readiness, tokenizer, canary, both roots, all Fast requests, repeats, and isolation passed; Deep independently rejected on a 768-token length stop.
- CatalyticSwarm-0 ran exactly once from protected integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280`. Control qualification passed, then readiness stopped inconclusively on exact-PID WDDM telemetry loss before the parser canary or any worker request. This version cannot be retried.
- The separately versioned CatalyticSwarm-0 v2 successor completed one artifact-claiming live execution and returned `reviewable-accept` for structured micro-workers and bounded swarm control. No retry occurred after claim; one earlier pre-claim command refusal created zero artifacts and made zero model requests. V2 changed only exact-PID WDDM transient-gap resilience plus fresh-sample admission and preserved the exact v1 plan and prompt bytes.
- CatalyticSwarm-1 v1 executed exactly once and stopped `inconclusive` on the first serial-chain comparison's complete-public-root cache proof. Exactly 2 model requests completed: 1 common-root warm, 1 comparison, and 0 completed tasks. Its authority is consumed and v1 is no-retry. Equal-budget task advantage, Deep, persistence, SOTA, and promotion claims remain locked.
- The separately versioned CS1 cache-admission diagnostic executed exactly once and returned `reviewable-accept` after 3 requests; all five artifacts are immutable. CS1-v2 and v3 are consumed preclaim boundaries. CS1-v4 and CS1-v5 each executed once, stopped inconclusively after 775 completed responses, and are hard-retired. CS1-v6 is static-only; a live V6 run requires separate exact-main/model one-shot authority from final pushed protected `main`.
- HoloState-v2 Durable Capsule remains the separate, unproven restart-persistence intervention. The current integration must not claim restart persistence.
- Preserve human review and the automatic-promotion prohibition throughout Level 1.

### CatalyticSwarm-1 cache-admission diagnostic integrated (historical milestone)

- Integrated the separately versioned diagnostic contract at canonical SHA-256 `be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b` without changing the CatalyticSwarm-1 v1 contract, evidence object, artifacts, or absent task-results path.
- Added the separate `audit-catalytic-swarm-1-cache-diagnostic` command and five isolated one-shot paths under `state/catalytic_swarm_1_cache_diagnostic/`. The v1 command remains hard-retired. The diagnostic directory and every diagnostic path remained absent throughout integration.
- Froze exactly three prospective model requests: the exact common-root warm, a minimal exact `{"candidate_id":"C00"}` branch, and the unchanged `serial-chain / cs1-chain-t01` realistic first turn. Thinking remains disabled, temperature is zero, one physical slot is used, and Deep request count is zero.
- Added exact public-root terminal-index and exact common-token-prefix measurement, persist-before-gate branch observations, both-probe classification after negative cache observations, and CS1-native request-boundary reconciliation. Full completion requires 3 requests, 6 custody checks, 3 host/resource checks, 3 pre-request and 3 post-request freshness boundaries, one warm ledger record, and two branch observations; lawful early safety stops use exact observed counts.
- No diagnostic evidence object, sidecar launch, model request, cache classification, or root-cause conclusion was produced during static integration. Task advantage, SOTA, broader process-local HoloState, restart persistence, and automatic promotion remain locked. A future run requires new exact-main and exact-model explicit authority.

### HoloState worker protocol v4 terminal-EOS integration prepared (historical snapshot)

- Imported the seven connector files from `codex/holostate-chat-token-evidence-v4` at `168fb4d0e666cbc058a59826ff9e97359889d835` without importing its sixteen intermediate commits.
- Added fail-closed native-token, deterministic visible-retokenization, and direct terminal-EOS evidence laws. The one-token usage reconciliation never claims the unknown EOS token ID or a complete generated sequence.
- Added bounded terminal-stop provenance to the shared stream parser, a separate no-generation tokenizer qualification, five versioned v4 evidence paths, and exact prior/source authority bindings.
- The v3 exact-count gate was preserved as correctly followed. Pinned source reconciled four visible tokens plus one server-counted terminal EOS token; at this preparation boundary no worker capability request had executed under v4.
- Before execution, compilation and 232 CPU-only tests passed without live generation. No v4 readiness, tokenizer, attempt, result, or stream artifact existed at that boundary; all availability locks, CatalyticSwarm-0, and automatic-promotion prohibitions were unchanged.

### HoloState worker protocol v4 executed once

- Exact integration commit `da04c5bf388c3d091da4e2f1aee33bf852377517` passed protected main preflight before the single invocation. Readiness and no-generation tokenizer qualification passed before capability artifacts were claimed.
- The parser canary reconciled exact visible IDs `[60738, 30094, 18916, 8378]` with five completion tokens only through the complete direct terminal-EOS gate. The EOS ID and complete generated sequence remain unknown.
- Root A/B warmed at 8,173/4,436 tokens. Fast A1/B1/A2/B2 and exact A1/B1 repeats all passed; distinct branches and cross-root isolation passed.
- Deep A1 retained opaque reasoning evidence but exhausted 768 tokens with `finish_reason=length` and no final content, so Deep is `reject` without invalidating Fast=`reviewable-accept`.
- The 907-record, 618,838-byte ledger, 136-sample 2,252.88 MiB WDDM evidence, host-memory ceiling, 29 ownership boundaries, cleanup, isolation, frozen evidence/source authority, historical hashes, stable PID `32684`, and candidate integrity all passed.
- At the v4 boundary, v4 was `reviewable-accept`, `PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE` was unlocked, broader process-local and restart-persistent availability remained locked, and `CatalyticSwarm-0` was authorized but not yet executed. Automatic promotion remained disabled.
- Readiness/tokenizer/attempt/result/ledger SHA-256 values are `4B8A44B4CB3DE9355B8A3D4E3FC945DD685EA35B98F5BF0C0160DAA090249BA7`, `EB10127666CDADE0D6A8E7EF59CA7D4310B64B89619800DF245BD769666A587D`, `6197D986FD3ED030340A82300245AE0EF1249229E21162BF6796F7F614A7EA19`, `396C1E76EC07EB64E8FF700E49F45A931638BD071A7955941712314CADDF59CF`, and `CD96EE1F41F15E9953705F7DDA762D1111D60E04C828F9B157D314D789F0F104`.
- Tracked v4 evidence and `neo-exp-0018` are bound; 232 post-audit CPU-only tests, compilation, and JSON/JSONL validation pass.

### CatalyticSwarm-0 bounded control integration prepared (historical snapshot)

- Integrated the four-file draft PR #3 substrate as a callback-driven blackboard/scheduler/adapter boundary without importing its four connector commits.
- Repaired only demonstrated fail-open behavior: complete-plan validation, exact one-slot and 32-worker acceptance, per-worker 64-token enforcement, exact structured ACK/parent/decision law, strict real-v4 transport evidence, immutable full-entry bounds, hard verified-parent synthesis, and fresh genesis blackboard requirements.
- Added a complete-object evaluator contract and seven ignored one-shot artifacts for control qualification, readiness, parser canary, attempt, result, bounded ledger, and blackboard snapshot.
- The protected runner reuses the v4 sidecar, checked ownership, WDDM, tokenizer, terminal-EOS, resource, isolation, and teardown machinery. It contains no Deep, persistence, CUDA/kernel/model/Pi/stable, retry, promotion, task-advantage, or SOTA claim path.
- At this historical preparation boundary no CatalyticSwarm-0 artifact or worker request existed. The then-next operation was exact pushed protected `main`, protected preflight, then one `audit-catalytic-swarm-0` invocation.

### CatalyticSwarm-0 bounded control executed once

- Exact integration commit `8e2a14cc11be31c29d75c5738a3cd0dc9e2ab280` was pushed as protected `main` and passed protected preflight before the single invocation. No retry occurred.
- Generation-free control qualification passed. Readiness launched sidecar PID `44748`, recorded 6 exact-PID WDDM samples and a 92.84 MiB peak, then stopped as `inconclusive` when a counter query timed out and telemetry was classified `candidate-vram-telemetry-lost`.
- The parser canary, capability attempt, all 32 worker requests, physical leases, bounded ledger, and blackboard remained unattempted or absent. The qualification pass therefore does not establish structured-micro-worker or swarm-control capability.
- Lifecycle cleanup succeeded: PID `44748` stopped, runtime state retired, port 9494 became free, and stable PID `32684` remained healthy. The composite resource gate remained non-pass because telemetry was lost.
- Readiness, `STRUCTURED_HOLOSTATE_MICROWORKER`, and `CATALYTIC_SWARM_CONTROL` are `inconclusive`; both new availability states remain locked. The existing process-local micro-worker unlock remains intact, while broader process-local HoloState, restart persistence, task advantage, and SOTA remain locked. V4 evidence is preserved and automatic promotion remains false.
- The exact early-stop evidence is bound as `neo-exp-0019` in the protected evaluator/result/lock for the evidence commit. Control qualification SHA-256 is `864F74F58792E120422BB4078439E40AAE96546D58282DED38BB7665678A3E53`; readiness SHA-256 is `76351D413785D6E239F1E20FB152EDF78DF312EEBE85D86FC343C6B25D7C1CCC`.
- Preserve this no-retry boundary. At the v1 evidence boundary no further CatalyticSwarm live work was authorized; the later separately versioned v2 authorization below did not alter or retry v1.

### CatalyticSwarm-0 v2 WDDM successor executed evidence

- Exact integration commit `cf61f90ff5544f2f8bc546e5d661ea72cdda8666` passed protected main preflight before one artifact-claiming live invocation with pinned paths. No retry occurred after claim, no Deep request ran, and automatic promotion remained false. One earlier pre-claim command refusal created zero artifacts and made zero model requests.
- Control qualification, readiness, parser canary, all 32 thinking-disabled worker requests, 32 one-slot leases, 32 verifier receipts, the 32-entry hash-chained blackboard, exact 16/8/6/2 phase counts, 1,319 bounded ledger records, and two verified synthesis entries passed.
- Exact-PID WDDM recorded 177 valid and zero unavailable samples, zero recoveries, maximum failure streak 0, maximum valid-sample gap 2.938 seconds, 107 passed freshness boundaries, and a 2,284.9 MiB peak. Maximum host-private growth was 727,982,080 bytes.
- Cleanup, sampler retirement, runtime removal, port retirement, stable/candidate isolation, v1 preservation, and worker-v4 preservation passed. V2 is `reviewable-accept`; structured-micro-worker and bounded swarm-control availability are unlocked.
- Exact SHA-256 values are control `1FC67796F436E69B1B2C2F132345C0335FADF6D1452E7F98D8A92D78CB616CE3`; readiness `129FD883FD03BBEF8B216AC67F77CBE854CA798A86BBC18A11D4DCDF010E7124`; parser canary `9282D7F8AE195C866E767A7F0D3BCB0A366E3FC3C1509A7DB1F99F1C541191B5`; attempt `0E9A839B7AD9D50AE6FD82DD3C63A93D23596C4A32FAF515BAC67A68EFEE8866`; result `AF491153D98877CAACAF5ED89F3446A80AD8ED12D3FAD2CDE22C2AF77CE5BEC7`; ledger `C523EF77C80CDD4783D2E41103FCD72490A4C837DA2B3988B29F8D7A97E1F7F9`; blackboard `197929DF8DF62A24480A64C071651CED43E16D82F0B6DA5A9AB740C6C1236964`.
- Broader process-local HoloState, restart persistence, task advantage, and SOTA remain locked; automatic promotion remains false. CatalyticSwarm-1 later executed once under separate authority and stopped before completing an equal-budget task, so neither control proof establishes task advantage.

### CatalyticSwarm-1 v1 executed evidence

- Exact protected commit `556bb4d57a05bb81fa101a98092472170b50c0dd` and unchanged contract `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e` were authorized for one invocation. No retry, Deep request, or automatic promotion occurred.
- Control qualification, readiness, and the generation-free parser canary passed. The first task common root warmed with 4,846 fresh prompt tokens, 0 cached prompt tokens, and 4 completion tokens. The first serial-chain response then failed to prove complete-public-root reuse, so execution stopped after 2 model requests with 0 completed task comparisons.
- Six artifacts are preserved: control `F9C8032340655EBBE5E41867D8C4C426940E6B7D2236ACDA9019EE9E24F8733D`; readiness `F6DF670C7CE1659E78D4B51F5CD45FAF4087DD46ABE87D8AD529AB45F6FE9C95`; parser canary `0B2749F3F864CB93FB003EA68A41AD364C56360C270506DB3684C1738E221680`; attempt `593D013494064F10FF9ECF732942EE114E1DC91E14A3290210C8801684A48A40`; result `D37CBF79BC867D927C01C7977D4432A29B2CA40E59ED5C10CCF6EF9A5F3AACAB`; ledger `5E016B7554E57564833BAA3B5B1250C6EE6FB73CFE204BDCBC4EEB902C1E40B8`. `task-results-v1.json` is absent.
- The ledger contains one bounded metadata-only warm record for 2 completed responses because the failed comparison stopped before ledger persistence. Terminal reconciliation therefore records `ledger-request-count`; raw SSE and hidden material were not persisted.
- All 12 observed WDDM freshness admissions passed, but the inherited CatalyticSwarm-0 v2 terminal reconciler expects v2 worker-boundary labels instead of CS1 request-boundary labels and separately reports `wddm-required-freshness-boundary-order`. This unrepaired label incompatibility did not cause the primary cache-proof stop.
- Cleanup and observed runtime integrity passed: sidecar PID `30848` stopped, runtime state was removed, port 9494 became free, five WDDM retirement samples were empty, stable PID `32684` remained healthy, and candidate custody remained intact. Full-schedule `2064 / 1032 / 8` reconciliation remains non-pass after the early stop.
- CatalyticSwarm-1 v1 is `inconclusive` and no-retry. Equal-budget advantage was not completed; task advantage, SOTA, broader process-local HoloState, restart persistence, and automatic promotion remain locked.

### CatalyticSwarm-1 equal-budget integration prepared

- Integrated the five-file PR #6 connector from exact head `aaeb3fe8cc906121fdfcb8ed41d9420b2849d8b6` as one architectural change without importing its twelve intermediate commits.
- Froze the eight-task DSL suite at SHA-256 `4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92`, complete contract at `fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e`, and the four declared arm plan hashes.
- Repaired only demonstrated connector defects: hidden scoring waits for all four arms and best-of-N scoring waits for all 32 responses; complete public-root cached-prefix reuse and accepted v4 token evidence fail closed; task/root/arm observations, totals, selections, and scores are canonically revalidated; sparse/verified model-visible prompts differ only by public-score visibility; exact success requires public plus hidden success; public suite serialization excludes hidden material; and the result uses the protected task-advantage state name.
- Added one common public-root warm per task outside arm budgets, exact Latin-square order, strict arm/task/hidden-data isolation, 1,024 comparison plus 8 warm prospective requests, 32-token request ceilings, per-arm 1,024 completion / 8,192 fresh-prompt ceilings, and 1.10 parity gates.
- Added an exclusive metadata-only ledger capped at 80,000 records and 67,108,864 bytes, seven ignored one-shot paths, complete predecessor bindings, protected exact-PID WDDM/ownership/cleanup reuse, and the separately gated `audit-catalytic-swarm-1` command. CatalyticSwarm-0 v2 is hard-retired against rerun.
- This integration launched no sidecar, made zero live model requests, claimed no one-shot attempt, created no evidence object or runtime artifact, and did not unlock task advantage, SOTA, broader HoloState, restart persistence, or automatic promotion.

### CatalyticSwarm-1 live stop-law repair prepared

- Retained a pure protected runtime-safety helper and direct CPU-only regression suite. The repair does not change the frozen task suite, complete contract, plan hashes, prompts, candidate programs, hidden data, Latin-square order, request/token budgets, or advantage thresholds.
- Added exact stable/candidate custody checks before and after every prospective model request, post-request inherited host/resource enforcement, an immediate parity stop after each completed four-arm task, and guarded cleanup ownership across parser success and attempt/result preparation.
- Terminal safety now requires exactly 2,064 custody checks, 1,032 host-memory checks, and 8 task-parity checks before any completed verdict can survive.
- The repair launched zero sidecars, made zero live model requests, and created no one-shot artifact or evidence object. The prior authorization is unconsumed but superseded by the new protected-main identity. Task advantage, SOTA, broader process-local HoloState, restart persistence, and automatic promotion remain locked.

### HoloState worker protocol v3 readiness integration prepared

- Retained and integrated the connector-authored native listener probe, no-query-storm readiness state machine, and CPU-only tests; corrections are limited to concrete defects demonstrated by tests or direct review.
- Added checked bounded listener ownership, one marker-to-pass readiness deadline, independent process/health/WDDM polling, fresh pre/post request ownership, and checked teardown/retirement without modifying stable inference.
- Added complete-object `holostate_worker_protocol_v3`, which inherits v2 capability behavior exactly and introduces only readiness-control fields, expanded immutable prior bindings, and distinct readiness/capability paths.
- Readiness failure can create only readiness evidence. Capability attempt/result/ledger creation requires a frozen readiness pass; failed ownership, restoration, ledger, evidence-preservation, or repository-isolation gates cannot unlock availability.
- Integration protection passes compilation; 18 listener, 10 readiness, 102 HoloState, 11 trace, 9 evaluator, and 5 WDDM tests. Tokenizer-only Root A/B rendering is 8,131/4,408 tokens inside unchanged bounds.
- No v3 live command ran during integration. No readiness, canary, root, Fast, repeat, Deep, PID, query, memory, or verdict outcome is claimed here.

### HoloState worker protocol v3 executed once

- Exact protocol commit `b45249c6620c2645232883c5035b260683706dcd` passed protected main preflight before the single invocation; complete protocol SHA-256 is `f89c0151d5d27f142ab3caf73f164fa5d9eab6a50ef5e8e65c575d3bca0dcc7c`.
- Readiness passed in 29.61 seconds after 106 non-listener polls. All 16 checked listener queries passed first attempt in 0.015-0.032 seconds with stable PID `32684`, sidecar PID `42236`, and zero query failures.
- The canary returned exact `TOKEN ARRAY CANARY`, empty reasoning, normal stop, and five completion tokens. Ten bounded ledger events contained nine absent token arrays and one empty final array, so generated token count was zero and the canary rejected as `stream-token-count-mismatch`.
- No root warm, Fast, repeat, or Deep request ran. Fast/Deep remain inconclusive; every HoloState availability state and CatalyticSwarm-0 remain locked; automatic promotion is disabled.
- WDDM recorded 14 exact-PID samples with a 2,250.88 MiB peak and no telemetry loss. All ownership, resource, ledger, cleanup, frozen-evidence, prior-evidence, stable, and candidate-isolation gates passed; five retirement samples were empty and port 9494 retired.
- Readiness/attempt/result/ledger SHA-256 values are `6C761F40E6EBCD43B608218CC84D0AA1F75D2E1FDCEB15EB9DC103168E6EFCBF`, `4D70D8E53056A2BB2A00320051855B4D612547150A5FC68C068D17DEC66EFBFE`, `387E82B02BA8F6992111722595AEE05055A979A54A8D2EE6D9F5A1EE38C645E3`, and `26D65B9F474EF84B3F9483D6DDB1838280F1D54D476FDF14B5595A624EA5A583`. V3 is no-retry.

### HoloState-v1.1 message-boundary protocol prepared

- Corrected the historical claim boundary: legacy `/completion` supplied one raw content stream, and `parse_final_structure` treated the entire raw string as reasoning when the literal final marker was absent. The old runs prove limit exhaustion and missing final markers, not `reasoning_content` attribution; their files and hashes remain unchanged.
- Added evaluator-locked `holostate_worker_protocol_v1` with exact binary/model/template identities, unchanged A/B source order, a hash-bound immutable-reference system envelope, separate user assignments, one-shot paths, memory ceilings, stable isolation, and independent fast/deep verdict law.
- Added a protected, non-executed `audit-worker-protocol` controller path through `/v1/chat/completions`. The fixed sequence stops after `deep A1`; fast failure stops immediately, while deep failure preserves a completed fast proof.
- Lane F is thinking-disabled at 64 tokens and requires exact visible A/B content, an empty reasoning channel, normal stop, and cache reuse. Lane D is reasoning-auto at 768 tokens and requires nonempty reasoning metadata, exact deep-A content, normal stop, and cache reuse.
- Extended the shared `baseline_harness.stream_completion` parser to retain server-returned generated-token arrays and prompt-progress events while preserving its separate reasoning, visible-content, and tool-call channels. Worker results store reasoning only as presence, length, and SHA-256.
- Pre-audit verification passed 60 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus protected preflight. Template/tokenizer-only rendering measured Root A at 7,806 tokens and Root B at 4,630, inside the unchanged 4K-8K bounds without generating output or claiming the audit.
- The one-shot audit, old qualification, validation-v2, extended proof, and persistence work were not executed by the pre-audit protocol change.

### HoloState worker protocol v2 prepared

- Added request-local delta/cumulative token-array merging, completion-count agreement, and an ignored 8 MiB/50,000-record stream ledger that stores fragment lengths/hashes but never reasoning text.
- Added a thinking-disabled parser canary before root warming, distinct A1/A2/B1/B2 Fast assignments, A1/B1 repeat determinism, independent Deep classification, and exclusive v2 attempt/result/ledger paths.
- Added a separate v1 adjudication object without changing the v1 protocol, evidence object, ignored evidence bytes, or `neo-exp-0015`.
- Pre-audit protection passed 85 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus compilation, root-bound checks, and protected preflight.

### HoloState worker protocol v2 executed once

- Protocol commit `b2559f7c0c06e35a3e360b71ed13b69c4eb1eb7c` was pushed before the one-shot v2 marker was claimed; complete protocol SHA-256 is `c043d3084efefcbc9b369e1b770d36aef0dafcf89896d6105586564b204a0379`.
- Sidecar PID `37804` launched, but the protected stable-listener ownership query timed out during readiness. Admission stopped before the parser canary; no root warm, Fast, repeat, or Deep request ran.
- The exclusive stream ledger is empty: 0 records, 0 bytes, SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`. No merge mode or completion-count agreement was observed.
- Seven exact-PID WDDM samples peaked at 92.84 MiB. Cleanup, free port 9494, five empty retirement samples, stable PID `32684`, candidate isolation, and all five historical hashes passed.
- Attempt SHA-256 is `09A849AC35692A49DCC349110426FBD5ED9EF4BD146E723C8E750445916DE8F9`; result SHA-256 is `D08C4638179D6A2F0BFABE22DA2C8879377BDC6306E41ED22816FB95F45A84A7`. V2 is no-retry; Fast and Deep are untested/inconclusive, all availability states remain locked, and automatic promotion remains disabled.
- Post-audit evidence binding passed 86 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus Python compilation and protected preflight.

### HoloState-v1.1 worker audit executed once

- Protocol commit `3fb00fe93d0fb22e203d8e26d86173f5e3d2ee32` was clean, pushed, and preflight-exact before the one-shot marker was claimed.
- Root A rendered 7,806 tokens and returned exact `HOLOSTATE ROOT WARM`, empty reasoning metadata, `finish_reason=stop`, and matching prompt identity. Prompt time was 145,519.789 ms at 53.642 TPS; 7 completion tokens decoded at 18.981 TPS.
- The parser retained zero generated-token IDs and rejected the warm as `completion-token-evidence-missing`, stopping before Fast A1/A2, Root B, or Deep A1.
- Pinned-source inspection diagnoses the instrumentation defect: partial streaming results carry per-token arrays, the final streaming result carries an empty array, and the executed parser replaced rather than accumulated arrays. Raw SSE events were not persisted, so this explanation is source-based rather than direct event replay.
- `FAST_PROCESS_LOCAL_HOLOSTATE=reject`; `DEEP_PROCESS_LOCAL_HOLOSTATE=inconclusive`. All HoloState availability states, CatalyticSwarm-0, and automatic promotion remain locked.
- Sidecar PID `34580` recorded 73 exact-PID WDDM samples at a 2,252.88 MiB peak and retired cleanly. Stable PID `32684`, archived-candidate isolation, cleanup, and all historical evidence hashes passed.
- Attempt SHA-256 is `F634CA2732CEBBE424D4634F8EFAD035C6E11EAABB0D34E40A0F1EC09A2DF975`; result SHA-256 is `72F4BA4FA256836456B5ACA47FBD4CD5DE7789EB59F222B687B677010B7869A2`. Worker protocol v1 must not be retried.
- Post-audit evidence binding passed 61 HoloState, 11 trace-controller, 9 evaluator-gate, and 5 WDDM tests plus compilation and protected preflight.

### Checkpoint 2 activated: HoloState-v1 Live Prefix Lattice

- The expensive operation is canonical-prefix prompt evaluation; the borrowed carrier is exact process-local hybrid prefix state.
- Each transformation evaluates one divergent suffix or branch and extracts deterministic reasoning, final content, or a tool call.
- Closure preserves the canonical checkpoint lattice, retaining only model/configuration/prefix-identity-bound live cache entries.
- The global claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`; `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` is recorded separately.
- HoloState-v1 is process-local and uses the Live Prefix Lattice name.
- HoloState-v2 Durable Capsule is reserved for future restart-persistent state work.

### HoloState-v1 live integration attempt: inconclusive

- Added protected `scripts/holostate_live.py` and its CPU-only safety suite. The controller exposes only the declared live-state operations, confines writes to ignored runtime state, binds roots to exact binary/model/template/prefix/token identities, and treats registry entries as metadata until reusable cached tokens and exact output are observed.
- The single allowed validation used exact sidecar PID/listener `42076`, stable PID `31188`, the locked Agents-A1 model, and binary version `13 (417e1d6)` / SHA-256 `5D0C...541B`.
- Root A warmed at 7,150 rendered tokens in 159,051.535 ms; Root B warmed at 4,879 tokens in 101,519.304 ms. Both immutable identities were inside the declared 4K-8K band.
- A1 reused an inferred 7,017 of 7,165 logical prompt tokens, evaluated 148 fresh tokens in 3,685.92 ms, and produced an observed 43.151x warm/reuse prompt-time ratio.
- A1 then consumed all 768 completion tokens and failed the combined deterministic output gate. The controller stopped immediately; B1/A2/B2, same-branch hash equality, eviction observation, and the 20-request/60-minute-bounded extended proof were not run. No retry occurred.
- Exact-PID WDDM produced 139 valid samples with a 2,252.88 MiB peak and no telemetry loss. Cleanup removed the exact sidecar and runtime; port 9494 and all five retirement samples were empty; stable remained unchanged.
- `HoloState-v1 Live Prefix Lattice` is `inconclusive`. `PROCESS_LOCAL_HOLOSTATE_AVAILABLE` and `RESTART_PERSISTENT_HOLOSTATE_AVAILABLE` remain locked. The narrower HoloState-0 status `EXACT_PROCESS_LOCAL_HOLOSTATE_REUSE_PROVEN` remains valid.
- After the stopped run, the controller was narrowed to preserve future failed-branch metrics and prefer prompt-progress cache counts over ambiguous zero-generation completion totals. This was a non-runtime evidence repair; the validation was not rerun.

### HoloState-v1 reasoning-budget contract repair

- The causal boundary is explicit: process-local prefix reuse succeeded, while the operational quality proof was blocked by an unqualified shared reasoning budget.
- The original ignored attempt/result remain immutable lower-bound evidence; new one-shot qualification and validation-v2 files are versioned separately.
- A complete evaluator-locked HoloState contract now owns roots, ordered source sets, branches, prompts, exact finals, reasoning/reuse requirements, candidate and selected budgets, sequences, request limits, memory ceilings, and binary/model/template identity.
- Completion budget exhaustion, wrong final content, missing reasoning, reuse failure, and acceptance are distinct persisted classifications.
- The repair and post-run prompt-progress interpretation fix passed 40 focused HoloState tests plus the protected trace, evaluator, and WDDM regression suites; evaluator preflight passed before and after the live launch.
- HoloState-v2 persistence remains a separate future intervention; the global claim ceiling and both availability locks are unchanged pending executed evidence.

### HoloState-v1 reasoning-budget qualification: no pass through 2048

- One sidecar, one Root A warm, and exactly four ascending A1 requests ran. Root B, fixed interleaving, tool/cancellation probes, extended proof, validation-v2, and retries did not run.
- Root A identity was `holostate-27f565ae760cdf96aa958ec9`; it contained 8,010 rendered tokens and warmed in 172,069.162 ms.
- Every A1 request exposed 8,026 logical prompt tokens and 7,878 cached tokens, yielding an inferred 148-token fresh delta. The raw server field `processed=8026` is cumulative when cache is present; the controller now records that raw field separately and derives fresh as `logical - cache` for future requests. The completed one-shot result was not rewritten or rerun.
- Budgets 1024, 1280, 1536, and 2048 produced exactly 1024, 1280, 1536, and 2048 raw completion tokens respectively, each with `stop_type=limit`, no final marker, and classification `completion-budget-exhausted`. Channel attribution was not available from this endpoint.
- Qualification result SHA-256 is `1AE79511E6C0E3C928989912A24CCDC64C5B918D6B74B1A364ACDB0A34044D94`. No minimum budget passed, so `selected_max_tokens` remains null and no locked-budget commit exists.
- Sidecar PID/listener `44652` recorded 239 exact-PID WDDM samples at a 2,252.88 MiB peak with no telemetry loss. Full cleanup, five empty retirement samples, stable PID `31188`, free port 9494, and preservation of the original v1 evidence all passed.

### HoloState-0 capability boundary opened

- Authorized one isolated port-9494 sidecar audit using the exact locked model, one slot, bounded host RAM, and protected exact-PID WDDM control.
- The audit separates repeated-prefix RAM reuse, branch multiplexing, in-process slot restore, and restart restore. Deterministic output plus prompt-token reuse evidence is required for an exact classification.
- Ordinary KV save/restore cannot establish Gated DeltaNet hybrid-state persistence by itself. Stable, CUDA, inference kernels, model files, and the archived trace candidate remain outside scope.
- Case A was present in the existing binary/source. A 7,519-token rendered prompt replayed fully once, then exact process-local A/B branches reused 7,387 tokens and evaluated only a 132-token checkpoint gap with identical per-branch greedy token and raw pre-final/output hashes. The legacy pre-final hash is not channel attribution.
- A 231,311,464-byte slot file saved and restored 8,069 tokens. In-process behavior stayed exact but cannot be attributed to the file separately from live RAM/checkpoint entries. After the declared restart, the same file restored successfully at the endpoint but the model reevaluated all 7,519 prompt tokens.
- At the HoloState-0 audit boundary, the retained result was exact process-local RAM/checkpoint reuse, not a restart-persistent hybrid capsule. No 40K audit, source integration, stable change, Checkpoint 2 activation, or automatic promotion occurred in that audit.

### Checkpoint 1A first instrumentation candidate

- Candidate `3e3023fc389a608ec5a5806eb8e1a50a801486d5` added schema-v1 optional compute tracing under `NEO_COMPUTE_TRACE`; normal builds compile trace calls out.
- The only trace-disabled cycle, `neo-loop-20260710T012311`, returned `reviewable-accept`. All immutable gates passed, warm median was 16.978 TPS, exact-PID WDDM peak was 2,196.88 MiB, cleanup passed, and stable PID `31188` remained healthy.
- The separate trace-enabled cold diagnostic stopped before completion. Synchronous per-node writes produced 2,407,857 events and 895,639,047 bytes over 449.13 seconds; partial decode was approximately 1.60 TPS versus 14.878 TPS trace-disabled. Overhead is `too high` and matched warm measurements were not run.
- The partial compute map observed CUDA/CPU placement, graph capture/replay, synchronization, transfers, and 502.50 MiB of CUDA-resident recurrent state. Explicit fallback reasons, fast-path MoE buckets, MMQ tiles, recurrent update/copy cost, and matched warm structure remain unresolved.
- Trace-enabled WDDM attribution was invalid because the local sampler matched 31-33 GPU process instances instead of the exact candidate PID. Aggregate values are discarded; cleanup and five exact-PID retirement checks passed. No rerun, merge, or promotion occurred.

### Checkpoint 1A bounded aggregation candidate

- Archived v1 and v2 evidence refs resolve exactly to `3e3023fc389a608ec5a5806eb8e1a50a801486d5` and `14de9c71593e5aea4fcfcadeda47ba5c623fadcf` respectively; neither is a merge proposal.
- Schema v2 replaces synchronous per-event file operations with fixed-capacity thread-local aggregation, bounded batched merges, persistent writers, explicit limits/truncation/drop accounting, and enumerated placement reasons.
- Focused compile-out, aggregation, totals, limit, writer, placement, exact-PID, collision, and telemetry-loss tests passed.
- The single normal cycle `neo-loop-20260710T021421` returned `reviewable-accept`; every immutable gate passed, warm median was 12.823 TPS, exact-PID WDDM peak was 2,196.88 MiB, and normal binaries contained no trace-writer strings.
- The trace-enabled launch used candidate/listener PID `47792`, but produced no accepted exact-PID WDDM row before inference. The diagnostic stopped before cold or warm workloads and was not rerun. Its 2.75 MB initialization-only artifact was bounded, valid, untruncated, and reported no drops, but it cannot measure overhead or support a runtime bottleneck claim.
- Candidate and telemetry retirement checks passed; stable PID `31188` remained healthy. No merge or promotion occurred.

### Checkpoint 1A protected diagnostic control

- Added a stable-side controller that can write only ignored candidate-local diagnostic artifacts and can stop only the exact candidate process object it launches.
- Candidate readiness is the conjunction of process liveness, health, exact listener ownership, exact-PID WDDM attribution, and the existing 6000 MiB ceiling; sampling begins immediately after launch and remains active through teardown.
- Added monotonic, non-overlapping startup/workload/teardown windows, candidate CPU-time capture, incremental schema-v2 trace bounds, and post-teardown stable/listener/telemetry retirement evidence.
- Protected the controller and its CPU-only safety suite in `lab/EVALUATOR.json` and the evaluator lock. No candidate source, stable inference logic, promotion path, or evaluator gate value changed.
- Telemetry-only passed with exact candidate PID/listener/WDDM agreement. The trace-disabled control completed every fixed phase, but the single trace-enabled run stopped during cold reasoning when an unchanged v2 module reported truncation and up to 28,062 dropped events at its 24 MiB ceiling.
- The final stopped artifact contained 25,554 valid JSON records and 25,199,004 bytes, below the combined session ceilings. Because cold reasoning was incomplete, no matched trace-enabled workload phase or overhead ratio is claimable; no model-runtime bottleneck was selected.
- Candidate and port retirement, five exact-PID WDDM retirement checks, protected preflight, and stable PID `31188` passed. The trace launch was not retried, and no merge or promotion occurred.

### Level 1 architecture integrated

- Level 0 is the completed operating level; Level 1 is current; Level 2 remains locked; Level 3 remains the long-range target.
- `SUPERVISED_BOUNDED_RSI_AVAILABLE` is achieved. The claim ceiling remains `NEO3000_BASELINE_OPERATIONAL`.
- Performance substrate and catalytic compute are separate standing lanes. Conventional CUDA improvements do not satisfy a catalytic checkpoint without borrow, transform, extract, restore/close, and lawful retained state.
- Fast, Long, and RSI future runtime profiles are recorded without implementation or unmeasured capacity claims.
- Checkpoint 1 is divided into trace substrate, backend/fallback, CUDA graph/synchronization, MoE geometry, recurrent-state, and causal-selection subphases.
- External CUDA leads are provenance and hypotheses only; no external fork merge or source replacement is authorized.

---

## 2026-07-09 — RSI-0 safety enforcement and live proof work

### Repository state aligned

The task board, roadmap, active goal, and checkpoint ledger were reconciled with the actual pushed state.

- Checkpoint 0 was kept closed with claim `NEO3000_BASELINE_OPERATIONAL`.
- LM Studio was removed as an RSI unlock dependency and retained only as optional historical characterization.
- The active boundary was advanced from already-completed source custody work to RSI-0 enforcement and proof cycles.
- `prompts/supervised_rsi_cycle.md` was added as the tracked operator contract for one bounded, non-promoting candidate cycle.
- The prompt requires one causal hypothesis, candidate-only edits, immutable evaluation, a single cycle limit, exact evidence, and manual promotion.

Representative commits:

- `f55e5116eb27209a69ad3aa065471df238f7dc1c` — add supervised RSI operator prompt.
- `a186d5911ab3d7ff856fe356019ee7893dc6a9f7` — align roadmap with closed Checkpoint 0 and RSI-0E.

### RSI-0E safety gates implemented

The evaluator and controller were hardened so a candidate cannot rewrite the rules, corrupt stable, or silently pass by changing its own scoreboard.

Added or enforced:

- `lab/EVALUATOR.lock.json` with precomputed hashes for evaluator, controller, benchmark identities, protected documents, launch configuration, and model identity.
- Candidate path allowlist enforcement against the candidate diff.
- Protected-path rejection with exact offending paths.
- Hash verification before and after every cycle.
- Build timeout.
- Candidate health timeout.
- Benchmark timeout.
- One-crash-per-cycle ceiling.
- Candidate-only VRAM ceiling of 6000 MiB for the RTX 3060 12GB safety profile.
- Model size and SHA-256 verification before candidate launch.
- Port collision rejection.
- Stable/candidate build-directory separation.
- Stable/candidate runtime-directory separation.
- Stable health and listener-PID verification before and after candidate activity.
- Stable worktree integrity verification.
- Candidate-owned teardown by tracked PID rather than killing every `llama-server` process.
- Cleanup on success, rejection, timeout, and interruption.
- No merge, push, rebase, self-promotion, or automatic replacement operation inside `neo_loop.py`.
- Compact result recording in `lab/results.jsonl`.

Representative commit:

- `cac80b0e8ce3f323c2beca942b43cef4e0b97f1b` — enforce candidate safety gates.

### RSI-0F supervised rejection cycle proved

A deliberate candidate mutation to protected `TASKS.md` was rejected before build or launch.

Proved:

- Candidate edit allowlist rejected the exact protected path.
- No candidate process remained.
- Candidate runtime state was removed.
- Stable remained healthy on port 9292.
- Stable listener PID remained unchanged at `31188` during the recorded run.
- Stable worktree remained unchanged.
- Protected hashes remained valid.
- The rejection was accurately recorded.
- Candidate state was restored cleanly and remained resumable.

Representative commit:

- `9e510795de7ad843bb49c3b32a3a0e23ed6cd027` — prove supervised rejection cycle.

### Candidate CMake blocker isolated and source custody repaired

The first RSI-0G attempt failed during CMake generation. The original compact evidence retained only the generic final line, so build diagnostics were improved to preserve the first causal CMake error block, diagnostic lines, longer stdout/stderr tails, and an ignored local full log.

First causal error:

```text
tools/mtmd/models/models.h was missing from the candidate worktree
```

Root cause:

- The broad `.gitignore` rule `models/` ignored every directory named `models` anywhere in the tree.
- It silently excluded 171 legitimate source files under `src/models/` and `tools/mtmd/models/`.
- Initial source custody was therefore incomplete even though the imported runtime appeared broadly tracked.

Repair:

- Anchored the weight directory ignore as `/models/`.
- Added the omitted source files to Git custody.
- Added `.gitignore` to protected evaluator paths.
- Improved compact CMake failure evidence in `scripts/neo_loop.py`.
- Confirmed clean candidate CMake configure succeeds after repair.
- Confirmed the shared candidate builder and candidate-specific builder had failed for the same missing-source reason; script drift was not causal.

Representative commit:

- `16286951e54ded4de59062f4a85bb3ea134fca4d` — repair candidate source custody and diagnostics.

### Agents-A1 model identity corrected and locked

After the candidate built successfully, the next acceptance attempt stopped before launch because the evaluator contained a transposed SHA-256 sequence.

Correct identity:

```text
File: Agents-A1-Q4_K_M.gguf
Size: 21,166,757,632 bytes
SHA-256: 31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2
```

The corrected identity was written consistently into:

- `lab/EVALUATOR.json`
- `lab/EVALUATOR.lock.json`
- `lab/CHECKPOINT.md`
- `TASKS.md`
- active goal evidence

The candidate was not launched during the mismatched-identity run. Stable health, listener identity, and cleanup remained intact.

Representative commit:

- `816f6e978c848a8cd59c5826d7aeaaa8c4d4eb7d` — correct Agents-A1 evaluator identity.

### Candidate health-probe timeout handling repaired

A fresh authorized acceptance cycle then configured and built successfully and began candidate model loading. During loading, a socket read timeout escaped the health probe and aborted the controller before the declared candidate readiness deadline.

Root cause:

- A temporary socket/read timeout during model loading was treated as an uncaught terminal exception.
- It should have meant only “candidate not healthy yet” while the readiness deadline remained open.

Repair:

- `request_json()` now catches HTTP, URL, JSON, timeout, and OS-level socket errors and converts them to `NeoLoopError`.
- `health_ok()` converts those request failures to `False`.
- The existing readiness loop can now continue polling until success, candidate crash, or the declared deadline.
- A stalled-health local test passed.

The run stopped safely without retry:

- Candidate process removed.
- Candidate runtime directory removed.
- Candidate port 9393 free.
- Stable health passed before and after.
- Stable listener PID remained `31188`.
- Stable worktree remained clean.
- Automatic promotion remained disabled.

Representative commit:

- `d911f932be997b764a74235bba8ef2b9279a2c04` — handle candidate health-probe timeouts.

---

## 2026-07-03 — RSI-0 substrate established

### RSI-0A: engine source placed under Git custody

Neo3000 stopped treating the imported runtime as an opaque local tree and adopted source-custody Option A: track the pinned runtime directly as a deliberate baseline.

Established:

- Pinned upstream repository: `ggml-org/llama.cpp`.
- Pinned upstream commit: `fdb1db877c526ec90f668eca1b858da5dba85560`.
- Upstream licenses and attribution preserved.
- Imported engine placed under ordinary Git diff, branch, rollback, and worktree control.
- 2103 files initially entered the tracked source baseline.
- One-line source edits became ordinary inspectable Git diffs.
- Clean rollback restored the exact baseline.
- A separate worktree could materialize the complete tracked engine.

Later CMake proof discovered that 171 additional source files had been hidden by the broad `models/` ignore rule; that custody defect was repaired on July 9 in `1628695`.

Representative commit:

- `7ea6ffddc599814dce4a0c2218cac420025739ae` — track imported llama.cpp engine as Git-diffable baseline.

### RSI-0B: stable and candidate worktrees isolated

Established the dual-runtime topology:

```text
Stable worktree: D:\CCC 2.0\AI\Neo3000
Stable branch: main
Stable build: build/stable
Stable port: 9292

Candidate worktree: D:\CCC 2.0\AI\Neo3000-candidate
Candidate branch: candidate
Candidate build: build/candidate
Candidate port: 9393
```

Added:

- `scripts/build_candidate.ps1`
- `scripts/run_candidate.ps1`
- Separate build paths.
- Separate ports.
- Separate runtime-state paths.
- Candidate model alias.
- CPU-MoE-compatible candidate launch profile for shared 12GB VRAM constraints.

Representative commit:

- `1c1bfe69ecf08e91b4632552612691b57484a5e8` — establish candidate worktree and isolated build/run scripts.

### RSI-0C and RSI-0D: evaluator and deterministic neo-loop created

Added the first immutable evaluator manifest and deterministic candidate lifecycle.

The initial `lab/EVALUATOR.json` recorded:

- Exact model identity.
- Baseline Neo3000 and upstream identities.
- Stable launch configuration.
- Candidate-editable paths.
- Protected paths.
- Smoke, tool, cancellation, memory, repeat, and context gates.

The initial `scripts/neo_loop.py` implemented:

```text
verify stable
verify candidate state
record baseline identity
build candidate separately
launch candidate separately
wait for health
run immutable probes
verify protected state
tear down candidate
verify stable again
record reject / reviewable-accept / inconclusive
never promote automatically
```

The task board was advanced from substrate construction to RSI-0E enforcement.

Representative commits:

- `d2c9ad4429a137299c2a0b89e809a1e6ef5a1b0d` — implement immutable evaluator and neo-loop machinery.
- `809932fb0d54fe6934fb7e2cd19d67865be774d0` — update task board with RSI-0 progress.

---

## 2026-07-02 — Checkpoint 0 baseline established and closed

### Standalone Neo3000 runtime foundation

Neo3000 was established as its own tracked repository and runtime rather than a traditional fork dependency or LM Studio wrapper.

Foundation work included:

- Pinned llama.cpp import manifest and upstream identity.
- Reproducible source import tooling.
- Windows CUDA build scripts.
- Stable server launch scripts.
- Baseline benchmark harness.
- Context-scaling harness.
- Rolling decode instrumentation.
- Task board, roadmap, active goal, checkpoint ledger, baseline protocol, and JSONL experiment log.
- Ignored local weights, builds, logs, runtime state, and benchmark outputs.

Verified build environment:

```text
CUDA Toolkit: 12.6
nvcc: 12.6.85
MSVC: 19.44.35227
CMake: 4.3.2
GPU: NVIDIA RTX 3060 12GB
CUDA architecture: SM 8.6
```

Built successfully:

- `build/stable/bin/Release/llama-server.exe`
- `build/stable/bin/Release/llama-bench.exe`

Stable API topology:

```text
Pi
-> http://127.0.0.1:9292/v1
-> Neo3000 stable server
-> Agents-A1 GGUF
```

### Agents-A1 serving and Pi compatibility proved

Verified:

- `/health`
- `/v1/models`
- OpenAI-compatible chat completions.
- Incremental SSE streaming.
- `reasoning_content` preservation.
- `neo3000_probe` tool calls with valid JSON arguments.
- Cancellation followed by immediate API recovery.
- Repeated turns without server degradation.

User-visible Pi proof completed:

- Exact streamed response: `NEO3000 PI ONLINE`.
- Real Pi tool round trip: Pi read `README.md`, returned its first heading, and Agents-A1 answered `Neo3000`.
- Pi-side cancellation during a long generation.
- Immediate post-cancellation recovery: `NEO3000 RECOVERED`.

### Context allocation and occupied-context behavior separated

Neo3000 established a strict evidence distinction:

```text
configured context capacity != actual occupied prompt tokens
```

Served-context allocation succeeded at:

- 4K
- 8K
- 16K
- 32K
- 40K
- 65,536 tokens

Measured occupied-context decode:

| Actual prompt tokens | Cached prompt TPS | Decode TPS |
|---:|---:|---:|
| 2,053 | 64.6 | 22.3 |
| 8,191 | 56.0 | 19.9 |
| 32,773 | 60.3 | 22.4 |
| 40,956 | 60.6 | 22.4 |
| 59,996 | 57.0 | 20.9 |

Result:

```text
60K / 2K decode ratio: 0.94
Observed degradation across ~60K occupied tokens: about 6%
```

This established that Agents-A1’s hybrid Qwen 3.5 MoE plus Gated Delta Net architecture maintained approximately flat decode throughput across the measured occupied-context range.

### Rolling minimum decode added

A 384-token decode with a 16-token rolling window showed no hidden sustained stalls:

| Occupied tokens | Average TPS | Minimum 16-token TPS | Min/avg |
|---:|---:|---:|---:|
| 2,053 | 19.1 | 18.4 | 0.96 |
| 32,773 | 18.3 | 16.9 | 0.92 |
| 59,996 | 18.6 | 17.1 | 0.92 |

The slowest rolling windows were only 4–8% below average, so average decode speed was not concealing severe transient collapse.

### Auto-fit hypothesis tested and rejected

Hypothesis:

```text
Automatic GPU placement is overly conservative and explicit layer counts can improve throughput.
```

Measured at 4K:

| Placement | Decode TPS | VRAM MiB |
|---|---:|---:|
| auto | 17.6 | 2,785 |
| explicit 20 layers | 10.0 | 1,892 |
| CPU only | 6.6 | 858 |

Verdict:

- Auto-fit was best among tested placements.
- The conservative-auto-fit hypothesis was rejected.
- Explicit layer forcing was not selected as an optimization direction.

### CPU-MoE tradeoff characterized

Measured at 4K with automatic placement:

| CPU-MoE | Decode TPS | VRAM MiB |
|---|---:|---:|
| enabled | 19.1 | 2,725 |
| disabled | 30.8 | 10,604 |

Result:

- Moving MoE work to GPU improved decode by about 62%.
- It consumed about 89% of total VRAM.
- CPU-MoE was retained as a space/speed control, especially when stable and candidate runtimes or larger context state must coexist.

### 40,960-token failure localized

An apparent tokenizer/context failure at the 40,960 target was investigated.

Findings:

- Direct `/tokenize` succeeded at approximately 197K and 599K tokens.
- The server remained healthy.
- The earlier matrix failure came from client-side timeout during a long uncached warmup, not a tokenizer or server defect.
- Rapid repeated binary-search tokenization calls could also exhaust Windows socket resources.
- The uncached 40K warmup took roughly nine minutes at about 73 prompt tokens per second, exceeding the former five-minute client timeout.

The harness timeout and evidence language were corrected rather than modifying the inference runtime for a nonexistent tokenizer bug.

### Throughput discrepancy explained

Different reported numbers were reconciled:

- About 8.2 TPS: cold first request, long reasoning-heavy completion.
- About 17.5–19.7 TPS: warm shorter completions.
- About 21.7–23.2 TPS: warm deterministic benchmark corpus.

The discrepancy was attributed to cold state, completion length, and reasoning-token overhead rather than contradictory runtime behavior.

### Checkpoint 0 closed

Checkpoint 0 closed only after build, model identity, API, Pi UI, tools, cancellation, repeated-turn, context, rolling-minimum, and characterization evidence were complete.

LM Studio was explicitly removed as an unlock gate. It may be used for optional historical comparison, but Neo3000 acceptance decisions compare a candidate against the previous accepted Neo3000 baseline under immutable evaluation.

Claim advanced to:

```text
NEO3000_BASELINE_OPERATIONAL
```

No catalytic inference claim was made.

Representative commits:

- `a5bef72de0c7b727abfed0b62cb6753beff8bbf8` — complete occupied-context baseline with auto-fit and CPU-MoE audits.
- `432e8f773cde782cab6d478ad5afccb15816cbb4` — align task board with the completed characterization head.
- `82c227037aea78dbaaa0f40ab403787106ac5b91` — close Checkpoint 0 with Pi UI evidence and rolling minimum decode.

---

## Architectural decisions retained

### Neo3000 judges Neo3000

LM Studio is not part of the RSI decision loop. Candidate acceptance is determined against the previous accepted Neo3000 state using the same hardware, model, evaluator, prompts, quality gates, and measurement law.

### Stable is never the experiment surface

Stable remains the daily-driver control intelligence. Every intervention belongs in an isolated candidate worktree, build directory, runtime directory, and port.

### The evaluator is outside candidate control

Candidates may not edit:

- Evaluator manifest.
- Evaluator lockfile.
- Controller.
- Task board.
- Roadmap.
- Checkpoint ledger.
- Active goal.
- Results ledger.
- Stable launch scripts.
- Model files or model identity.
- Promotion rules.

### Promotion remains human-controlled

A passing candidate may become `reviewable-accept`. It does not merge, push, replace stable, or promote itself.

### Meaningful architectural commits over pellet history

The Git history is intended to preserve Neo3000’s engineering memory. Source custody, isolation, evaluator construction, safety enforcement, proof cycles, and causal repairs are committed as coherent architectural chunks rather than fragmented administrative pellets.

---

## Rejected hypotheses and corrected assumptions

| Hypothesis or assumption | Result |
|---|---|
| Auto GPU placement was overly conservative | Rejected; auto-fit outperformed tested explicit layer counts. |
| The 40,960 target exposed a tokenizer/server limit | Rejected; the causal boundary was client timeout during long uncached inference. |
| Configuring 65,536 context proves 65,536 occupied prompt tokens | Rejected; allocation and occupancy are separate evidence. |
| LM Studio parity must gate RSI | Rejected; external comparison is optional characterization. |
| Initial tracked import contained all required source | Rejected; broad `models/` ignore omitted 171 legitimate source files. |
| Candidate builder drift caused CMake failure | Rejected; both build routes failed on the same missing source. |
| Original recorded model SHA-256 was exact | Rejected; a transposed sequence was corrected against measured bytes. |
| A read timeout during candidate model load means terminal health failure | Rejected; it means not-yet-healthy until the readiness deadline expires. |
| NVIDIA per-process memory telemetry is usable under this Windows WDDM driver | Rejected; NVML returns `[N/A]`, while PID-filtered WDDM dedicated-memory counters provide the required safety attribution. |

---

## Milestone commit index

| Commit | Milestone |
|---|---|
| `a5bef72` | Occupied-context baseline, auto-fit audit, CPU-MoE audit, timeout localization. |
| `432e8f7` | Characterization head reconciled in task board. |
| `82c2270` | Checkpoint 0 closed with Pi UI and rolling-minimum evidence. |
| `7ea6ffd` | Imported llama.cpp runtime entered direct Git custody. |
| `1c1bfe6` | Stable/candidate worktree and build/run isolation created. |
| `d2c9ad4` | Evaluator manifest and deterministic neo-loop core created. |
| `809932f` | RSI-0 progress recorded and RSI-0E opened. |
| `f55e511` | Tracked supervised RSI operator prompt added. |
| `a186d59` | Roadmap, task board, and active boundary aligned. |
| `cac80b0` | Candidate safety, lock, allowlist, timeout, memory, and isolation gates enforced. |
| `9e51079` | Live supervised rejection cycle proved. |
| `1628695` | Source-custody omission repaired; CMake diagnostics improved. |
| `816f6e9` | Agents-A1 evaluator identity corrected and locked. |
| `d911f93` | Candidate health-probe timeout handling repaired. |
| `a94d973` | Unavailable NVML telemetry became an explicit hard rejection. |

---

## Changelog maintenance law

Add an entry when pushed evidence changes one of the following:

- Supported claim ceiling.
- Checkpoint state.
- Runtime architecture.
- Evaluator or promotion law.
- Stable/candidate isolation.
- Model or source identity.
- Reproducible performance evidence.
- Accepted or rejected causal hypothesis.
- Safety boundary.
- Proven rejection or acceptance cycle.
- Exact next boundary.

Do not record an item as completed merely because it was proposed, described, or attempted. Failed cycles belong here when they expose and repair a real architectural boundary.
