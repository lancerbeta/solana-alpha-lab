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
| Episode→decision | TradingContinuityRunner.episode / CLI episode | SOURCE_DECISION_PRODUCED with complete packet; closed SignalDecision evidence_refs resolves actual event/hash | O1–O8, duplicate replay and three expected source/action sets |
| Decision→admission | Existing accept_signal_decision, skip_fill=True, one immediate transaction with source event | WATCHED reservation with version/epoch/mode/policy amount/fee; runner attempt reads it | Real SQLite race, pause and frozen-notional probes |
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
| S20 | PASS | Mixed duplicate/pause/resume/revision/no-route/restart stream and three independent source outcome sets |
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
callers remain explicit. DER 12/12 finding conclusions have direct evidence:
10 behavioral before/after or post-review probes, two missing base callers
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
31/32-case receipts are not substituted for final candidate evidence.

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

Current compact verification: verify.json 37/37 PASS; fresh.json 37/37 PASS, input bytes unchanged, output SHA256 c776a75f204a474fa5e095060699d90ef6ed3246147010feebd55f851d13f065; observed fixture bytes 2,396,462 across 36 measurements. Final cleanup remaining owned bytes zero and non-target preservation PASS. Canonical SEM-OWNER-LIFECYCLE resolve-route succeeded after incremental generator PASS_IMPACTED_CLOSURE_NOOP; root document links directly to the runbook. Independent final review remains separately hash-bound.
