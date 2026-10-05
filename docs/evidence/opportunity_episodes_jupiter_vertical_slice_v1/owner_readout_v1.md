# OPPORTUNITY_EPISODES Jupiter vertical slice — owner readout

**Кратко (для владельца).** Появилась новая коллекция OPPORTUNITY_EPISODES: эпизод
— это допуск монеты, которую выдвинул Jupiter; его момент T0 — момент записи
допуска (не рождение пула). Весь путь — от сбора до обычного Forge и холодной
численной проверки — доказан на синтетических данных в трёх отдельных процессах.
Ничего live не включено: сбор, хост ресурсов и настоящая наука = NOT_RUN. Сегодня
владельцу ничего запускать не нужно; включение — отдельное решение OPERATE.
Несколько пунктов приёмки покрыты частично (ниже честно отмечены PARTIAL), и есть
решения, которые остаются за владельцем.

Task `OPPORTUNITY_EPISODES_JUPITER_VERTICAL_SLICE_V1`. Evidence class: synthetic,
local workstation. Nothing here is alpha, a promotion or a live acceptance.

## What exists now

An *episode* is one committed admission of a Jupiter-nominated mint. Its anchor
`T0` is the admission commit instant (`NOMINATION_T0`). Each episode carries a
frozen 139-point schedule (`E0` precommit witness, 5-minute grid to 6 h, hourly
to 72 h). Every admission stays in the base for counts and decision
eligibility; gaps stay explicit states and never become zero.

The slice wraps existing owners; there is no new importer, evaluator, database
or service: the `smial.opportunity-episode-schedule` kind inside the ordinary
`scripts/observation_schedule.py tick --once` lane; the release 1.2 strategy on
the split-host vanilla path (`capture-freeze-export`, `unpack-next-live-cohort
--collection OPPORTUNITY_EPISODES`); the episode corpus with a generated
population card; `smial.hfic-temporal-query` 1.1 with
`population=OPPORTUNITY_EPISODES` through the ordinary Forge lifecycle and the
registered replay.

Runbook `docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md`; contract
`docs/contracts/opportunity_episodes_jupiter_v1.md` (section 9 lists accepted
limits). Discovery: `catalog_cli.py search-routes` reaches
`SEM-LIVE-EVIDENCE-TO-FORGE` (gold queries RU/EN pinned); the runbook itself is
reached with `catalog_cli.py search-assets` (for example «как забрать когорту
эпизодов» or "opportunity episodes runbook"). The route overview is at its
existing 16 KiB bound, so the runbook is not a route root.

## Three-process proof

`tests/test_opportunity_episodes_vertical_v1.py`; numbers, report hashes and the
reproduce command are in `vertical_proof_summary_v1.json`.

- **P1 capture host.** Production ticks at rounds and the needed points only
  (every other obligation terminalises as an explicit gap); 25 admissions over
  three UTC days; one mint admitted in two weekly cycles as two episodes; a
  one-episode Sunday cohort; activation `COMPLETE`; the ops store keeps no
  published outbox rows. Before the first capture, the admission-time protection
  assignment is substituted, deleted and damaged in turn: each refuses the
  export (`FROZEN_PROTECTION_HASH_MISMATCH` / `_MISSING` / `_UNREADABLE`) and
  writes nothing; the exact pinned file then exports normally.
- **P2 workstation.** Legacy newborn import alongside; genuine consume; exact
  repeat `PASS_ALREADY_PRESENT_EXACT` with 0 transferred files; tampered sealed
  release refused (`RELEASE_HASH_MISMATCH`); a sealed release whose manifest was
  made self-consistent without its pinned assignment, with a substituted one or
  with an extra one is refused by verify (`FROZEN_PROTECTION_SET_MISMATCH` /
  `_HASH_MISMATCH`), the exact pinned release passes; import worker killed after labels
  and before lineage → preflight fails closed, the same command repaired it with
  a different `--as-of`; mixed PRICE+LIQUIDITY+HOLDERS+TIME question equals the
  literal oracle (12/12/6/5, mean 0.10, baseline 0.2/11) with target attrition
  reported per group; controlled null exiting at E21600 equals its literal 0.025
  and the baseline; exact repeat loads no values and spends no look; grounded
  candidate → freeze → invalid and missing Critic refused → Critic result →
  finalize → owner `forge-run` `COMPLETED`; next cohorts rotate the epoch and
  the next question spends one normal look (25/24/12/11, 24 distinct mints,
  1 repeated).
- **P3 cold relocated root.** Original roots and network blocked by an audit
  hook; 3 releases verified from the copy, each carrying exactly the pinned
  assignment bytes and semantics; a 72 h point (E259200) present in the
  cold corpus for the 4 episodes whose hourly slot was ticked; saved readback
  loads no values and leaves the store unchanged; registered replay equals the
  saved result and the literal counts and baseline. Replay is a determinism
  check of the same calculation, not an independent implementation.

The Critic result is produced by the test at the model boundary
(`SCRIPTED_CRITIC_MECHANICAL`) and the candidate card text is test-authored;
the lifecycle, packet, refusal paths and persistence are the real ones.

## Operator stop-intake (safe drain)

`scripts/observation_schedule.py stop-intake` closes new admissions early
through the existing ACTIVE → DRAINING owner (producer tests through the
production entry): with a committed episode and the scheduled boundary hours
away, intake is 0 after the command, the committed trajectory keeps observing
and publishing, and the activation reaches `COMPLETE`; the drained cohort
exports as an ordinary mature cohort. A repeat is idempotent; a crash between
the committed transition and its evidence event leaves intake closed (completion
is refused rather than guessed) and the same command repairs it; `pause`
semantics are unchanged and a paused activation cannot be drained. The drain is
proven in producer tests through the production entry, not as a step of the
three-process vertical. It refuses a pending rollover and a clock earlier than an
existing admission.

## D1–D12

| Row | Status | Evidence | Not exercised |
| --- | --- | --- | --- |
| D1 Protection | PASS | producer: protected/unknown never admitted or published, including every raw body a published row names; contract: inventory fail-closed, no value projection; frozen assignment pins enforced at export, seal, verify and the Forge reader (substituted/deleted/damaged/extra all refused; vertical + contract tests) | symlinked assignment verified only on platforms that allow symlinks (skipped on Windows); no seal-time refusal test of its own (the seal check is exercised through verify variants and the consume flow) |
| D2 Frame/sample | PASS | producer frame tests; contract tickets/quotas | no explicit "no backfill of a dropped admitted mint" assertion |
| D3 Admission crash | PARTIAL | producer: before/after commit, before publish, after publish before mark, call start/complete | crash at a UTC day, weekly cycle or profile boundary |
| D4 Time/core | PARTIAL | contract literal clocks, E0 witness, >8 points refused; vertical E300/E1800/E14400/E21600 through import, reader and evaluator; E259200 in the cold corpus | different batch receipts for one point; E259200 inside a query |
| D5 Missing/decline | PASS | producer decline/gap states, unknown call outcome, recovered call; vertical tiny cohort `DISAPPEARED` | — |
| D6 Public delivery | PARTIAL | vertical genuine capture/transfer/seal/verify/import, small cohort, exact repeat, tampered release, torn import repaired | same-window collision with another collection; conflict paths through consume |
| D7 Ordinary context | PARTIAL | vertical generated card and packet alongside legacy; absent universe policy reported | native policy/operation block at discovery without a policy or operation (preflight only reports the policy absent); oversized packet; caps unchanged; legacy dataset visibility next to episodes |
| D8 Mixed numerical + lifecycle | PASS | vertical oracle signal + controlled null; invalid/missing Critic; finalize; forge-run; contract wrong anchor / future feature | wrong anchor and future feature checked by the validator, not in the vertical run |
| D9 Cold and next run | PASS | P3 + exact repeat 0 values / 0 look + next-run budget | — |
| D10 Legacy | PARTIAL | legacy hash pins; grounded BASE_X refuses E-points and episode bindings; 128 consumer modules re-run (see below) | old scoped negative vs the new population; release 1.0/1.1 byte preservation relies on the suite run |
| D11 Resource/recovery | PARTIAL | budgets per tick/day, active cap, operator stop-intake → drain → COMPLETE (idempotent, crash-safe), obligations survive, measured RSS/wall/bytes, outbox bounded | restart at budget boundary, host envelope, low reserve, aged history, non-empty restore, live shared burst |
| D12 Semantic/owner path | PASS | gold route queries RU/EN; runbook via asset search | runbook is not a route root (size bound) |

Legacy suite: 2126 tests in 128 consumer modules; two failures reproduce
identically on base `de20465e` (`test_forge_input_truth_and_visibility_v1`,
`test_forge_representation_ladder_v1`). The final head re-run is recorded in the
completion evidence.

## Resource model (MODEL, not a host envelope)

Template profile: 100 admissions/UTC day × 138 obligations, 672 modeled
provider calls/day; per-unit costs measured in P1/P2.

| Horizon | Admissions | Modeled calls | Ops SQLite | Publication parquet | Workstation corpus | Workstation mirror |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30 d | 3 000 | 20 160 | ≈ 1.0 GB | ≈ 0.5 GB | ≈ 60 MB | ≈ 0.65 GB |
| 97 d | 9 700 | 65 184 | ≈ 3.2 GB | ≈ 1.7 GB | ≈ 190 MB | ≈ 2.1 GB |
| 365 d | 36 500 | 245 280 | ≈ 12.1 GB | ≈ 6.3 GB | ≈ 720 MB | ≈ 7.9 GB |

Measured peaks on this workstation: P1 RSS ≈ 120 MB, P2 ≈ 510 MB, P3 ≈ 280 MB.

Found and fixed: the ops store kept a full copy of every published row
(≈ 120 MB/day at the template rate); published rows are now deleted in the
publication transaction.

## Remaining runtime gates before OPERATE

1. `TICK_COST_LINEAR_IN_PUBLICATION_HISTORY` — the shared ResearchStore append
   verifies every committed partition of a dataset, so tick wall grows about
   17 ms per prior publication on this workstation (≈ 5 s after one day,
   ≈ 150 s after 30 days at 288 publications/day). Owner: shared
   publisher/ResearchStore (also the legacy lane); outside this write set.
2. Due-ledger, raw and publication retention: obligations are never pruned
   (≈ 2.4 KB ops store per obligation).
3. Category 5m routes remain `PROVIDER_ROUTE_REGISTRY_GAP`; the protection
   source is a placeholder, so every admission stays `UNRESOLVED_SCOPE` until
   real assignment documents exist.

## Accepted limits of the protection pin and the drain flag

- A protection assignment edited on the capture host after registration makes
  both admission and export refuse (fail closed); adding a late holdout inside a
  running activation needs a new schedule or a workstation-current assignment.
- The drain proof honours `operator_stop_intake` from the immutable committed
  event; it is written only by the episode-only command and is not additionally
  schedule-scoped in the proof function.

## Owner decisions left open

- **Market epoch scope.** The epoch stays data-root global, as before this
  slice: an episode import rotates it like any dataset publication, and with it
  per-epoch session and focus budgets for every collection. A per-collection
  epoch is a separate design decision.
- **Target attrition.** Effect means use target-available episodes; missing
  targets are reported by reason for matched and baseline, never adjusted. A
  mint that vanishes at exit may be a rug; any imputation or sensitivity rule is
  an estimand decision.

## Owner next action

Review the PR; the merge phrase is issued only by the machine merge-readiness
gate. Activation is a separate OPERATE commissioning decision.
