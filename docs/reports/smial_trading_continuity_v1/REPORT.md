# Trading continuity: проверяемый результат и границы

`AUDIT_VALIDITY=VALID_WITH_LIMITATIONS`; `CAPABILITY_OUTCOME=REPAIR_PARTIAL_BLOCKED`.
Обычный V1 PAPER mixed/list-only и SHADOW mixed проходят от source-shaped
данных через scientific handoff, definition, отдельную activation, decision,
admission, attempt/result, originating exit до RECONCILED и свежего readback.
Полный `OFFLINE_CHAIN_VERIFIED` **не установлен**: S08/S13 требуют активную V2
рядом с открытой V1, а canonical scientific handoff принимает только V1.
Отказ V2 проверен, guard сохранён. Это product/version authority boundary,
не доказательство положительной continuity V2.

Base: `d244af69bfd7ddc2850b9e5e5823323956e325c4`.
Exact task: `docs/tasks/SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1.md`.
Source MD: `docs/evidence/smial_trading_continuity_v1/source-contract.md`,
SHA256 `fa27010cd06336d7e962798ce29cf04427ba8a3a23b420a3878357094fc6274c`.
Final candidate hashes/reviews live in completion.json / independent-review.json;
delivery is not DONE or merged until the existing machine gates and owner phrase.
External commissioning: `NOT_ASSESSED_NO_AUTHORITY`.

| Область | Исходный риск | Сделано и доказано | Остаток |
|---|---|---|---|
| Handoff/population/decisions | Missing ordinary source→decision caller; recipe/list/time meaning lost | Real CHECK→RENDER→VERIFY V1; canonical membership/prefix/recipe owners; O1–O8; resolvable frozen provenance | V2 handoff BLOCKED; nondefault cohort selection typed unsupported |
| Execution/positions/recovery | Missing ordinary result caller, pause race, duplicate fill, lost UNKNOWN/close | Durable attempt before modeled result; exact callbacks, rollback/restart/restore, pending-close recovery, explicit drain recovery | No partial EXIT model; inactive scientific exit stays operator/reconcile; admission policy fork unchanged |
| Accounting/readback | Mixed scopes and additional costs could present fictitious headline PnL | Literal 2.87 and .065→.07 tie; costs/UNKNOWN separate; independent source/action/admitted/terminal sets | No equity/total-risk/live/FCF or scientific profitability claim |
| Verification/cleanup | Self-report cleanup; instrumentation could disturb Windows file replacement | Owned roots, external-egress canary, fresh reproduction, actual process/path and non-target hashes | Windows symlink creation unavailable in one existing test; measured bytes are a lower bound, not absolute maximum |

## Ordinary seams and truth owners

| Seam | Actual caller / input | Durable output and consumer | Oracle |
|---|---|---|---|
| Synthetic observation→episode | Existing EpisodeScenario collector tick; fake vendor response bytes | observation_schedule_state SQLite + outbox/publication; episode_decision reads one WAL-aware snapshot | Literal admission/point/deadline grid, late and missing refusal |
| Research→handoff→definition | FactoryApplication research_detail / record_research_decision; synthetic ResearchStore evidence only | Exact PROMOTE manifest/execution binding; materialize_strategy_candidate CHECK/RENDER/VERIFY | Missing/legacy/hash/size/fee guards and valid neighbor |
| Definition→activation | trading_continuity load then explicit activate | Existing PaperPlane bot plus exact activation event; loading does not create bot/store | Actual empty-store assertion before activation; LIVE refusal |
| Episode→decision | TradingContinuityRunner.episode / CLI episode | SOURCE_DECISION_PRODUCED with complete packet; closed SignalDecision evidence_refs resolves actual event/hash | O1–O8, duplicate replay and four independent source/action identities, including denied ENTER |
| Decision→admission | PaperPlane accept_signal_decision_outcome, skip_fill=True, one immediate transaction with source event | WATCHED reservation or durable SIGNAL_ADMISSION_DENIED with reason/scope/policy; runner attempt/readback reads it | Real SQLite race, pause, frozen-notional, refusal/re-evaluation and actual-error rollback probes |
| Attempt→result | CLI attempt commits identity before fake external result; CLI result resolves attempt and originating packet | MODELED_ATTEMPT_STARTED / MODELED_RESULT_ACCEPTED + existing position accounting | Literal state/qty/fee/outcomes; UNKNOWN reconciliation before resend |
| Position→exit | Runner.exit reads originating recipe and its observable target; operator close for inactive/unresolved path | SOURCE_EXIT_PRODUCED + existing ExitDecision consumer; modeled EXIT result | Later list removal retains V1 exit; no-route retains inventory |
| Reconcile→readback | Runner.result invokes existing maybe_finish_drain after committed result; CLI readback readonly snapshot | Existing SQLite owners; derived Russian operations view, no new status store | After-commit fault then fresh replay; mixed scopes and costs; raw persistent sets |

No final SignalDecision is injected into the whole-chain tests. Fake external
responses, synthetic physical clock and fault points are explicit test inputs.
The engine baseline probes inject signals and are labelled supplemental only.
The fixture uses the current source schema. No provider, real science trial,
holdout, wallet, deployment, real activation or repository settings were used.

## Confirmed repairs and evidence strength

`baseline.json` is the original aggregate pre-change failure; `baseline-projection.json`
separately records mixed-money failure. `baseline-replay.json` repeats **five**
baseline probes on the exact base Git blobs of paper_plane, trading_operations
and paper_shadow_operations, with unchanged dependency owners. Its five FAILs
are expected before-states; it is not a passing repair run or an entire old-tree
commissioning. `failure_boundaries` preserves compact actual assertions.

| Finding | Before / earliest boundary | Repair / after | Strength and rollback |
|---|---|---|---|
| F01 count | Admission owner count 1, operator count 0 | Use existing OPEN_RISK_STATES owner; count 1 | Dynamic frozen-base FAIL → current PASS; restore projection only |
| F02 pause | Real second connection pauses after reservation; automatic fill still OPEN | Transactional pre-fill recheck cancels before modeled effect | Controlled interleaving, one trial per run, not a race-frequency estimate |
| F03 duplicate fill | Identical fill adds an accounting event | Exact replay has no new effect; legacy missing derived fields recover explicitly | Dynamic before/after; keep durable history on rollback |
| F04 conflicting fill | Conflicting entry price accepted | ENTRY_FILL_CONTENT_CONFLICT, previous inventory unchanged | Dynamic before/after; no accepted evidence rewrite |
| F05 mixed money | PAPER+SHADOW headline -0.40 | MIXED_SCOPE suppresses combined money/streak/drawdown; per-scope economics | Dynamic before/after; no change to actual position arithmetic |
| F06 source caller | Static base graph has no timely source-bound ordinary producer | episode_decision reuses canonical list/feature/recipe/prefix owners; ordinary runner calls it | Static absence + dynamic positive chain; remove adapter without changing retained sources |
| F07 result caller | Static base graph has no ordinary modeled attempt/result callback caller | Generic durable engine seam + CLI/runner; no route/provider implementation | Static absence + all supported outcome probes; retained events never fabricated on rollback |
| F08 visibility | Review found deleting timely outbox then late publication could change replay | First ingestion visibility preserved by source owner and publication; identical replay after flush | Review hypothesis → dynamic publication-after-decision PASS |
| F09 pending close | UNKNOWN then close could strand delayed positive/non-fill | Definitive positive records known entry while keeping EXIT_REQUIRED; negative clears pending entry | Real callback/restart states; no invented UNKNOWN resolution |
| F10 path/origin | Writable store links, rooted paths or unavailable origin could escape/refabricate | Strict root/ancestor/file/hardlink guards, exact packet/hash lookup, typed unavailable | Real NTFS hardlink canary and actual corruption/missing-store probes; symlink variant explicit skip |
| F11 honest failure/UX | Additional attempt costs omitted from headline; DRAINING implied a background exit | Cost components and UNKNOWN visible; explicit operator/reconcile next action | Dynamic modeled failure/mixed-cost/drain probes + independent owner navigation review |
| F13 cumulative cost/clock | Review found .01→0/missing could erase confirmed cost; observation clock could regress | Known total regression and reverse clock refused; UNKNOWN total retains .01 lower bound; .02 final + dynamic partial EXIT refusal | Static review → frozen previous-head cost-before FAIL → current literal probe; no historical event rewrite |
| F14 decision eligibility | Semantic review found missing/late decision PRICE could ENTER outside scientific eligibility; three frozen 5db1b820 probes reproduce ENTER instead of UNKNOWN | Shared scientific PRICE cell precedes entry features, including list-only; typed UNKNOWN and no admission; originating exit retains its own target arithmetic | Dynamic price-before 3 FAIL → fresh 3 PASS with valid neighbors; membership UNKNOWN still reads no values |
| F15 transaction/outcome | Native ordinary episode on content head 3f619f92: disabled-policy refusal loses source packet (0 instead of 1); stale WATCHED replay rolls cancellation back to WATCHED | Existing admission owner returns normal DENIED; source, risk refusal and unattempted cancellation commit together; actual errors retain rollback | transaction-before.json: two actual FAILs; transaction-after.json: eight PASS probes A–D; no risk-policy or successor lifecycle change |
| F12 version gap | Existing _science_lineage_matches requires V1 although schema admits Vn | Preserved guard; V2 VERIFY refuses, V1 originating exit still works after list removal | Dynamic denial, **unrepaired owner boundary**; no automatic V2 materialization claim |

Compatibility: historical manifests 1.0 are not filled from current data;
legacy release-binding hashes preserved; additive first-visibility field uses
conservative publication time for historical rows without it. Existing store
schema and v1.0 commissioning suites remain relevant regression evidence.
Primary blast radius is PAPER/SHADOW admission/result accounting and the new
offline adapters. Rollback uses an ordinary follow-up revert of product/docs;
keep accepted event/position history and use existing reconciliation rather
than deleting a store or rewriting historical science.

## Original scenario denominator

All S00–S23 remain planned. PASS means executed/evidenced in the named offline
scope, not live commissioning. PARTIAL is not counted as restored required
outcome. Evidence files list exact test case names/statuses/output hashes.

| Scenario | Result | Executed evidence |
|---|---|---|
| S00 | PASS | Network sacrificial canary on every proof run; LIVE/unowned/rooted/hardlink refusal |
| S01 | PASS | Existing science_to_strategy_handoff and execution_evidence_seam deny/valid-neighbor tests |
| S02 | PASS | Same suites plus raw ExperimentSpec tamper/missing ResearchStore probes |
| S03 | PASS | Real materialize/load/no-store → explicit PAPER/SHADOW activation; LIVE denied |
| S04 | PASS | List-only/mixed full chain; literal exactly2/atLeast2/UNKNOWN/INVALID; aliases in existing scope suite |
| S05 | PASS | Same mint, independent real episodes, source/action sets, duplicate arrival |
| S06 | PASS | Ordinary CLI PAPER mixed, ordinary PAPER list-only and SHADOW mixed, all RECONCILED |
| S07 | PASS | O5–O8, explicit prefix readset {E300,E1800}, future/late and post-publication replay |
| S08 | PARTIAL_BLOCKED | Same identity/body replay, conflict and origin guards PASS; required active V2 neighbor blocked by scientific handoff |
| S09 | PASS | Existing admission_concurrency real SQLite barriers/scopes; ordinary frozen admission under policy revision |
| S10 | PASS | Controlled pause-after-reservation, pause-before-attempt, stop and idempotent commands |
| S11 | PASS | All declared modeled classes, fee/cost UNKNOWN, unsupported payload/partial EXIT refusal |
| S12 | PASS | UNKNOWN restart without resend; delayed positive/negative exact-once and conflicting callback refusal |
| S13 | PARTIAL_BLOCKED | List removal and no-route/recovered V1 exit PASS; active V2+open V1 unavailable without version policy decision |
| S14 | PASS | Pre-commit rollback plus committed RECONCILED/DRAINING crash window → fresh exact replay → STOPPED |
| S15 | PASS | Existing vertical store snapshot/WAL/concurrent-read isolation and native failures; source snapshot owner reused |
| S16 | PASS | Literal Decimal 2.87/.065→.07/2.37, failed attempt costs, independent full identity sets, mixed scope refusal |
| S17 | PASS | Actual missing/corrupt state, native existing OS failure probes, SQLite backup restore with policy+pending UNKNOWN |
| S18 | PASS_WITH_POLICY_LIMIT | Commands/count/readback actual states verified; existing admission versus remaining-inventory policy fork retained |
| S19 | PASS_WITH_SKIP | Existing v1.0/schema/store commissioning; one Windows symlink-creation skip explicitly retained |
| S20 | PASS | Mixed duplicate/pause/resume/revision/no-route/restart stream and four independent source identities with one retained denied ENTER |
| S21 | PASS_REVIEW_BOUND | Canonical SEM-OWNER-LIFECYCLE root document → new runbook; independent cold reader and final Catalog checks required |
| S22 | PASS | cleanup.json owns/deletes roots, records actual PIDs and before/after non-target fingerprints; fresh.json proves no old DB |
| S23 | PASS | Synthetic roots only; protected source/config fingerprints, no real science/holdout/provider/deploy authority |

O1 ENTER once; O2 same mint in another episode NO_ENTER without numeric reads;
O3 flat delta NO_ENTER; O4 missing holders UNKNOWN; O5 list coverage UNKNOWN
before value loader; O6 late point UNKNOWN without healing; O7 restart and
O8 changed future target preserve identical decision/provenance. UNKNOWN-list
fixture uses an actually registered late LOCAL snapshot: a failed nomination
frame would prevent source admission earlier and cannot serve the same seam.

Metrics retain raw denominators: COC required P0=21, fully restored at most
19/21, S08/S13 partial; RJC 3/3 named V1 positive ordinary journeys (PAPER mixed,
PAPER list-only, SHADOW mixed), plus operator-drain recovery; this does not
erase the separate required version journey. ARC attacks cover 24/24 named
scenario hypotheses, with S21/S22 review/machine final binding. PEF 24 planned,
24 attempted, 22 fully executed at most and 2 partial; static-before missing
callers remain explicit. DER 15/15 finding conclusions have direct evidence:
13 behavioral before/after or post-review probes, two missing base callers
established statically and exercised dynamically after repair. FR baseline
five deterministic frozen-base failures → five current passes; other repairs
are review/static-discovered with dynamic after-probes, not invented historical
reproductions. Critical evidence gap: one version continuity boundary affects
two P0 scenarios S08/S13. No 100% full-scope closure or threshold shortcut.

## Reproduction, failures and cleanup

Use the preexisting locked environment; no install is part of this result:

```powershell
$env:UV_PYTHON_DOWNLOADS='never'
$env:UV_OFFLINE='true'
$env:PYTHONIOENCODING='utf-8'
uv run --locked --managed-python python -B scripts/prove_trading_continuity.py --phase fresh
uv run --locked --managed-python python -B scripts/prove_trading_continuity.py --phase clean
```

`fresh` requires absent campaign root/manifest, creates a new owned root and
rebuilds collector, ResearchStore, strategy, runtime and callbacks from compact
fixtures. Fixture seed/version and raw code hashes are in fresh.json; all
source-shaped fixtures are generated by tests/test_trading_continuity_v1.py
and existing EpisodeScenario helpers. `regression.json` covers 12 impacted
neighbor modules. `baseline-replay` intentionally exits 1 with five failures.

Failed experiments are retained honestly: original baseline defects;
instrumentation-failure.json contains actual Windows Access denied during
atomic replacement. Active filesystem sampling was removed; causal attribution
to the sampler is INFERRED, not proven. A follow-up fixture expectation used
the wrong missing-store code, corrected to existing SOURCE_NOT_PRESENT. A
new conservation fixture used +00:00 rather than canonical Z timestamp and
was corrected; this was a test-input fault, not a product fix. Historical
31/32/37-case receipts are not substituted for final candidate evidence.

Resource allocation is recorded before creation; roots/markers/realpaths,
reparse and shared-use checks precede deletion. Peak method is
PRE_TEMP_ROOT_CLEANUP_MAX_NOT_ABSOLUTE_MAXIMUM: observed fixture bytes before
cleanup, lower bound only, with measurement count. cleanup.json records exact
deleted allocations, remaining owned bytes=0, root+manifest absence, process
exit/absence and non-target before/after hashes. No images, containers, services
or volumes were created. Existing .venv/uv/shared caches are retained.

Authority next decision: define how a later StrategyVersion binds an exact
scientific PROMOTE and remains distinguishable from a changed hypothesis,
recipe or execution regime. Current V1 guard may not be loosened merely to
make S13 green. Admission veto for EXIT_*/UNRESOLVED versus residual inventory
and automatic scientific exit after deactivation remain separate existing
policy questions. Safe operator/reconciliation continues to work.

Final proof is fresh.json after cost/clock and shared PRICE eligibility repairs. pre-cost-verify.json and earlier 37/38-case receipts are historical only. cost-before.json repeats the new regression probe against previous candidate 160866d6 and records the missing cost-regression refusal; clocks were independently static-discovered and dynamically checked after repair. price-before.json freezes 5db1b820 and reproduces three actual ENTER/UNKNOWN mismatches. Two initial frozen-fixture dependency errors and a first-after provenance serialization error are recorded in run-history.json; they are not substituted for final evidence. Canonical SEM-OWNER-LIFECYCLE resolve-route succeeded after incremental generator PASS_IMPACTED_CLOSURE_NOOP; root document links directly to the runbook, which states V1-only support and links this report. Final independent review is separately hash-bound.

Pre-transaction-patch fresh 42/42 PASS, output SHA256 5cdd55bf22266bcb9f35eaf45484c01a71ffe41282cfbff45da34f8a570f8af5, is historical and does not validate F15. Literal cumulative .01→0 and reverse-clock observations are refused without events; .01→UNKNOWN preserves confirmed lower bound; definitive .02 plus exit produces modeled net 2.85. PARTIAL EXIT is dynamically refused with unchanged positions/results. Missing PRICE for mixed/list-only and late PRICE for list-only refuse without future healing; research and runtime reuse the same eligibility cell. Reported V2 partial boundary remains unchanged.

First Linux CI execution job (run 38152447297, head 37e1285e) reported 34 fixture errors among 228 cases: PRODUCER_GIT_SHA_UNAVAILABLE. In-repository Windows temporary roots had inherited the parent Git HEAD; Linux temporary roots had no repository. Native GIT_CEILING_DIRECTORIES counterfactual reproduced the same refusal locally (git-boundary-before.json). The fixture now creates its own disposable Git commit of exact ExperimentSpec bytes; production application/identity guards are unchanged. The repaired counterfactual verifies the actual research decision producer SHA and committed spec bytes (historical git-boundary.json); current fresh includes that same native Git-ceiling case with new candidate bindings. Per-command synthetic author/autocrlf/signing options apply only to disposable fixture commands, with no host/repository configuration mutation. Git objects are inside recorded disposable roots and removed with them. Earlier 41/42-case proofs are historical; final exact-head CI remains mandatory.

## PR #396 transaction/outcome PATCH: A–D

The owner explicitly authorized the exact review handoff retained in
review-handoff.md (SHA256 00f9589bcecac9e12d83ec8837be6b4398448c8f234d6851a4110cc8a23505d7).
The finding was tested first on the existing source-shaped OrdinarySourceTests /
EpisodeScenario with actual SQLite, without injecting a final SignalDecision.
Two actual red probes were recorded before any production edit. The nested
immediate_write owner only yields inside an outer transaction; a legacy normal
refusal exception therefore triggered the runner's outer ROLLBACK. The store's
rollback semantics remain unchanged. The runner now consumes the explicit
outcome API, while legacy engine callers retain their exception API.

| Proof | Before/after result on normal caller, read from new connection |
|---|---|
| A | Disabled policy: source ENTER remains exact; one risk BLOCK and one DENIED evaluation retain reason, scope and policy hash; zero positions/attempts/results; identical API, CLI and legacy replay add no events. A policy revision allows a distinct evaluation/reservation while retaining the denial. |
| B | Unattempted WATCHED stale replay leaves CANCELLED/SIGNAL_EXPIRED and zero open-entry count. Pause and disabled-policy replay leave their own cancellation reasons. Repeats cannot revive the reservation or duplicate cancellation. ATTEMPTING/UNKNOWN are preserved and require existing reconciliation. |
| C | Independently expected four valid sources: two ENTER, one NO_ENTER, one UNKNOWN. Exactly one ENTER is admitted and one is denied by policy. The difference is fully explained by a retained refusal; one position, exact {(episode, ENTRY, SET-ENTRY), (episode, EXIT, SET-EXIT)} attempt identities, literal ENTRY-RESULT-1/SET-FINAL links and one reconciled terminal belong only to the admitted source. |
| D | Unexpected RuntimeError, genuine typed PaperPlaneError and a native SQLite RAISE(ABORT) trigger all leave the pre-call source/risk/reservation state unchanged. Successful neighbor commits source, reservation and frozen fingerprint/amount/fee together. Conflicting source identity/body remains an error with no new effects. Existing real-SQLite concurrency and consumer suites remain the serialization oracle. |

transaction-before.json retains the actual pre-edit two FAILs and output SHA256
c51f33bc687ffe30ede7795bdc6d52cf15daf531e752553cea95a26c4a4eadbf.
For a native reproduction on the frozen production owners, run
`scripts/prove_trading_continuity.py --phase transaction-before` (expected exit 1).
`--phase transaction-after` executes eight A–D probes (expected exit 0).
These bounded phases share the existing ownership journal/egress guard and
cleanup. Reproduction does not authorize operational policy mutation.
The original S00–S23/O1–O8 denominator and REPAIR_PARTIAL_BLOCKED remain; S08/S13
are still open. V2/successor lifecycle and risk-policy changes were excluded.

Pre-CI-oracle-alignment PATCH fresh: 49/49 PASS, then-exact inputs unchanged; historical output SHA256 750ea457837a0867f401698f748ed8ea0fbeb5c19e5d010eac1e8ebb0e79a8ce. Eight A-D probes PASS; impacted regression 198 PASS plus one explicit Windows symlink skip. Cleanup CLEAN, zero remaining owned bytes, campaign root/manifest absent and five non-target fingerprints preserved. Those receipts validated the then-current transaction PATCH and are now historical input bindings; no older PASS is carried forward after the CI oracle alignment.

Goal/DoD review on content head 6aa402c1 returned NOT_READY for a verification gap: attempt/result counts and shared position ID did not exclude a missing-plus-duplicate pair. Production was unchanged; the oracle now checks independent literal episode/side/key sets, unique raw event/payload identities, exact result-id-to-attempt links, modeled class and origin. Current eight A-D probes and fresh49 were rerun with the strengthened test bytes; previous 49-case PASS remains historical.


## Exact-head CI dispatch recovery oracle alignment

Run 38158563737 at 22bda7783c889894214e051cea106cca265b3e12 passed core, execution, resources and five general shards. Shard 3 ran 1140 cases with one failure and nine skips; the final aggregator failed. This was an assertion failure, not the 60-minute job timeout. The native original dispatch test reproduced the failure with unchanged production (visibility-before.json, output SHA256 0fc35c1ff099f23f909af2f554c6e9e11a94637aaaa7225ee291c68af21dbe5e). Read-only assertion instrumentation confirmed the entire difference was ingested_visible_at: 2026-10-05T00:11:00Z in normal completion versus 2026-10-05T00:11:05Z after recovery.

The row first enters the committed canonical outbox at different times in these two histories. The directly affected legacy test now independently asserts both exact first-ingestion clocks, compares every reconstructed source-gap field and requires the complete published row, including its ingestion clock, to remain unchanged on same-history replay. Production semantics are unchanged; no late row is backdated to satisfy byte equality. This is a verification-oracle alignment within the existing first-visibility contract, not a new scientific or lifecycle policy. The source-visibility phase runs all 16 existing dispatch-window tests under the same owned-root/egress controls and adds the affected test file to current proof input bindings. The original S00-S23/O1-O8 and DER denominator remain unchanged. New exact-head CI is still required; the failed run is retained as history.

Current proofs after the CI oracle alignment all bind the same 13 unchanged code/test inputs:

| Receipt | Executed result | Output SHA256 |
|---|---|---|
| fresh.json | 49/49 PASS | 9f8cd538d6280b0cab5da6af9a62ef237ac1ac87f0aecb95d14a5dd312915cb8 |
| transaction-after.json | A-D 8/8 PASS | f118fd0fa8679d550fc4792d9b4aef43e51a56457e0fd4577ed25c314e9d31f1 |
| source-visibility.json | Dispatch-window 16/16 PASS | 9f732565cb5ed15f73d97cf40b3cea84d1ddeb6b0e63cce6629b595e8d8948ec |
| regression.json | 198 PASS plus one explicit Windows symlink skip | 7f562fd9341777f02ee5ef16c761b742d5be27d651d3f6ca8d9cecaa59a1596e |

Run `scripts/prove_trading_continuity.py --phase source-visibility` for the directly affected consumer. CLEAN confirms zero scoped owned bytes, absent root/manifest, exited/absent processes and five preserved non-target fingerprints. REPAIR_PARTIAL_BLOCKED and open S08/S13 remain unchanged. The owner subsequently authorized machine-phrase substitution and one guarded merge after full exact-head CI and readiness; that direct request grants no scientific acceptance or machine-check override.
