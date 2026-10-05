# OPPORTUNITY_EPISODES Jupiter vertical slice — owner readout

Task `OPPORTUNITY_EPISODES_JUPITER_VERTICAL_SLICE_V1`. Evidence class:
synthetic, local workstation. Live collection, resource host and real science
are **NOT_RUN**; nothing here is alpha, a promotion or a live acceptance.

## What exists now

An *episode* is one committed admission of a Jupiter-nominated mint. Its anchor
`T0` is the admission commit instant (`NOMINATION_T0`), not birth or pool
creation. Each episode carries a frozen 139-point schedule (`E0` precommit
witness, 5-minute grid to 6 h, hourly to 72 h). Every admission stays in the
denominator; gaps stay explicit and never become zero.

The slice wraps the existing owners; there is no new importer, evaluator,
database or service:

- producer: the `smial.opportunity-episode-schedule` kind inside the ordinary
  `scripts/observation_schedule.py tick --once` lane (protected closed frame,
  deterministic tickets and quotas, atomic admission + slots + outbox, existing
  call ledger, HOT raw plane and publisher);
- capture/workstation: release 1.2 collection strategy on the existing split-host
  vanilla path (`capture-freeze-export`, `unpack-next-live-cohort --collection
  OPPORTUNITY_EPISODES`), episode corpus and a generated population card;
- Forge: `smial.hfic-temporal-query` 1.1 with `population=OPPORTUNITY_EPISODES`
  through the ordinary preflight / discovery / draft / freeze / Critic /
  finalize / forge-run lifecycle and the registered numerical replay.

Runbook: `docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md`. Semantic contract:
`docs/contracts/opportunity_episodes_jupiter_v1.md`. A fresh agent reaches both
from the root route `SEM-LIVE-EVIDENCE-TO-FORGE` (`catalog_cli.py search-routes`)
and `catalog_cli.py search-assets --text "opportunity episodes runbook"`.

## Three-process proof

`tests/test_opportunity_episodes_vertical_v1.py` runs three separate processes;
key numbers, report hashes and the reproduce command are in
`vertical_proof_summary_v1.json`.

- **P1 capture host.** 112 production ticks (rounds and the decision/target
  points only; every other obligation terminalises as an explicit gap), 25
  admissions over three UTC days, one mint admitted in two weekly cycles as two
  episodes, a one-episode Sunday cohort, activation `COMPLETE`, three capture
  packets.
- **P2 workstation.** Legacy newborn import alongside; genuine consume of the
  first cohort; exact repeat `PASS_ALREADY_PRESENT_EXACT` with 0 transferred
  files; tampered sealed release refused (`RELEASE_HASH_MISMATCH`); import
  worker killed after labels and before lineage → preflight fails closed, the
  same command repairs it; mixed PRICE+LIQUIDITY+HOLDERS+TIME question equals
  the independent oracle (12/12/6/5, mean 0.10, baseline 0.2/11); controlled
  null equals the baseline exactly; grounded candidate → freeze → invalid and
  missing Critic refused → Critic result → finalize → owner `forge-run`
  `COMPLETED`; next cohorts change the market epoch and the next question spends
  one normal look (25/24/12/11, 24 distinct mints, 1 repeated).
- **P3 cold relocated root.** Original roots and network blocked by an audit
  hook (0 blocked events during the proof); 3 releases verified from the copy;
  saved readback loads no values and leaves the store unchanged (the
  superseded-epoch focus correctly shows `START_BASE`); numerical replay calls
  the evaluator once and equals the saved result.

## D1–D12

| Row | Status | Evidence |
| --- | --- | --- |
| D1 Protection | PASS | producer: protected/unknown scope never admitted or published; contract: inventory fail-closed, protected values never reach projection |
| D2 Frame/sample | PASS | producer: missing source blocks round, fresh FAIL not healed and later PASS gets real T0, order/duplicates invariant, incomplete round, quota edge |
| D3 Admission crash | PASS | producer: before/after commit, before publish, after publish before mark |
| D4 Time/core | PASS | contract: literal clocks, E0 witness, >8 points refused, exit after cutoff; vertical: E300/E1800/E14400 through reader and replay |
| D5 Missing/decline | PASS | producer: decline and gap states, send without result → `ATTEMPT_OUTCOME_UNKNOWN`, completed call recovered; vertical: torn import |
| D6 Public delivery | PASS | vertical: genuine capture/transfer/seal/verify/import, small cohort, exact repeat, tampered release |
| D7 Ordinary context | PASS | vertical: generated card and packet with episode capabilities alongside legacy |
| D8 Mixed numerical + lifecycle | PASS | vertical: oracle signal + controlled null, invalid/missing Critic, finalize, forge-run |
| D9 Cold and next run | PASS | vertical P3 + next run budget |
| D10 Legacy | PASS (2 pre-existing) | 2126 legacy tests in 128 consumer modules; 2 failures reproduce identically on base `de20465e` (`test_forge_input_truth_and_visibility_v1`, `test_forge_representation_ladder_v1`); legacy hash pins in contract tests |
| D11 Resource/recovery | PARTIAL | bounded calls/tick/day, active cap, stop intake, obligations survive, measured RSS/wall/bytes; published outbox rows deleted; open gates below |
| D12 Semantic/owner path | PASS | gold route queries (RU/EN) pinned; runbook found by asset search |

## Resource model (MODEL, not a host envelope)

Template profile: 100 admissions/UTC day × 138 obligations, 672 modeled
provider calls/day. Per-unit costs measured in P1/P2 and 30/97/365-day
projections are in `vertical_proof_summary_v1.json`.

Found and fixed: the ops store kept a full copy of every published row
(about 8.8 KB per obligation, ~120 MB/day at the template rate). Published rows
are now deleted in the publication transaction.

## Remaining runtime gates before OPERATE

1. `TICK_COST_LINEAR_IN_PUBLICATION_HISTORY` — the shared ResearchStore append
   verifies every committed partition of a dataset, so tick wall grows about
   17 ms per prior publication on this workstation (≈ 5 s after one day, ≈ 150 s
   after 30 days at 288 publications/day). Owner: shared publisher/ResearchStore
   (also the legacy lane); outside this write set.
2. Due-ledger and raw/publication retention: obligations are never pruned
   (about 2.4 KB ops store per obligation); retention/eviction is out of scope.
3. Category 5m routes remain `PROVIDER_ROUTE_REGISTRY_GAP` until commissioning
   records evidence; the protection source is a placeholder, so every admission
   stays `UNRESOLVED_SCOPE` until real assignment documents exist.
4. Not measured: Linux host envelope, low disk/export reserve, aged unrelated
   history, non-empty local restore, live shared legacy+new account burst.

## Owner next action

Review the PR; the merge phrase is issued only by the machine merge-readiness
gate. Activation is a separate OPERATE commissioning decision.
