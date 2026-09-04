# Owner readout — FACTORY_STORAGE_DATA_ECONOMY_AND_CONTEXT_CLOSURE_V1

## Entry / outcome

`ENTRY_VERDICT`: `START_WITH_PATCH`. Git `af1ad23ac4a97d4f63108abd8446ad3dc6b1960c`
and the post-reclaim machine readback support this semantic-closure scope.
No production-code defect was found.

- `DECISION_DELTA`: after live PASS, nonempty restore proof, and `legacy_full`
  reclaim, does Factory need a storage topology, retention, or capture-resolution
  change? **No.**
- `UNCERTAINTY_REMOVED`: post-reclaim byte breakdown; one-off migration/restore
  traffic vs plausible steady-state; 7d declared-budget vs 30d/90d UNKNOWN;
  reclaim FAIL is an acceptance false-negative; credential-less bare tick is
  not the production surface.
- `CAPABILITY_OR_EVIDENCE`: `DATA_RESOLUTION_ECONOMY` in
  `DATA_AND_RESEARCH_TRUTH`; compact storage baseline; Collector runbook no
  longer auto-routes restore/reclaim.
- `STOP`: exact merge gate. No merge without the owner phrase.
- `NEXT` (not this atom): commission existing `DAILY_COLLECTOR_OWNER_PULSE` on
  the VPS. Telegram incident alerts stay `WATCH`.

`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH` for this policy/contract atom.
`NEXT_MODEL_EFFORT`: `ROUTINE_NO_SWITCH` for merge read-back.

## Reclaim disposition (literal)

Machine terminal remains:

`LEGACY_FULL_RECLAIM_FAIL`

Interpretation: `RECLAIM_EFFECTIVE` /
`ACCEPTANCE_FALSE_NEGATIVE_CONCURRENT_PUBLICATION`.

Acceptance required exact scientific fingerprint equality while the collector
stayed `ACTIVE`. Live ticks legally appended publications. Exact pre-file
inventory was not saved, so no retrospective subset proof. Reclaim was not
repeated. Nothing else was deleted.

Concurrent append-only invariant: pre-existing scientific path+hash set must
be a subset of post-state. Full equality is valid only with a frozen writer.

Known outcome (true): `legacy_full` 379 / 10 560 999 561 B → 0 / 0; disk
~26.0% → ~15.7%; completed receipts preserved; collector `ACTIVE`; SQLite
integrity ok.

## Phase A — storage / data economics

Read-only observation `2026-09-04T14:17:55Z` on `factory-remote-ops`, deploy
`af1ad23ac4a97d4f63108abd8446ad3dc6b1960c`. Compact facts:
`docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_storage_baseline_v1.json`.

| Substrate | Measured |
|---|---|
| Filesystem used / free | ~16.2 GiB used (~16%) / ~80.7 GiB free |
| ObservationSchedule SQLite + WAL | 167 993 344 B + WAL 0 |
| Scientific RDP excluding journal | 612 857 483 B |
| `publication_jobs` open / completed / `legacy_full` | 0 / 456 (479 870 B) / **0 / 0** |
| Local backup sink | 11 114 155 120 B (pre-reclaim leftover, not steady-state) |
| Off-host 30d payload | 22 139 072 972 B, class `NORMAL` |
| `collector_storage_history.jsonl` | `HISTORY_ABSENT` |
| `raw_retention_days` | 31 (campaign/CLI default) |

Collector `ACT-619AE64E885E995E` remained `ACTIVE`. Packet verdict `DEGRADED`
only from `DISCOVERY_COVERAGE_UNKNOWN`.

One-off (do not treat as run-rate): ~10.56 GiB journal reclaim; ~22.1 G
restore-proof download (temp, cleaned); ~10.77 G off-host daily delta in the
30d ledger; local 11.1 G zip still pre-reclaim.

Plausible steady-state: scientific RDP ~0.61 G growing with publications;
SQLite ~168 MB; compact completed receipts ~480 KB; declared raw/day cap 1 GiB
used only as a conservative 7d budget.

Projections:

- 7d: `DECLARED_RAW_BYTES_PER_DAY` → ~30.35% used, `pass_70=true`. Not empirical.
- 30d / 90d: **UNKNOWN**. The observation that would measure them is daily pulse
  `--record-storage-history` over those windows. This atom does not add
  telemetry.

Owner question (change topology / retention / resolution now?):
`NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED`.

## Phase B — retention

Current software already supports 31d operational raw compaction. Status/dry-run
at observation: `eligible_call_compactions=0`, `eligible_call_payload_bytes=0`,
`eligible_poll_slot_compactions=0`. Protected payload is younger than 31d.

`RETENTION_NO_ACTION_YET`. No APPLY, no timer, no VACUUM, no archive tier, no
new store. First future APPLY still needs status/dry-run → eligible rows/bytes
→ bounded owner/destructive gate.

Scientific RDP stays immutable.

## Phase C — DATA_RESOLUTION_ECONOMY

Canonical owner `delivery-harness/policies/solana-alpha-lab.md` §
`DATA_AND_RESEARCH_TRUTH` now states `DATA_RESOLUTION_ECONOMY` once.
Historical/reusable cache first is unchanged. No universal “1m candles only”.
Tick / quote / microstructure remain possible only when all of: a named
non-reconstructable/material consumer; a concrete estimand/falsifier or
execution-truth question; and material information value relative to
incremental storage/cost. No named material consumer means no broader
high-resolution capture.

`BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1` remains a legitimate
decision-time quote consumer: coarsening that would destroy PIT, path order,
fillability, transient liquidity, or executable quote truth is forbidden by
the same paragraph.

Future richer capture is a named decision test, not a new platform.

## Phase D — runbook

`docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`:

- historical LIVE_PASS / restore PASS / reclaim FAIL-as-false-negative;
- no auto-NEXT to restore or reclaim;
- production tick is the existing systemd oneshot with
  `EnvironmentFile=-/etc/solana-alpha-lab/secrets.env` and an operator 90s
  `timeout` plus explicit service stop (`TICK_HARD_CUTOFF_90S`); the unit is
  unchanged;
- current health still requires a fresh machine readback.

No production/runtime mutation. No Telegram mutation. No new infra.

## Factory Fit / Product Horizon

`FULL_REVIEW`. `NOW`: commission existing `DAILY_COLLECTOR_OWNER_PULSE` on the
VPS after this merge. `WATCH`: incident/state-transition Telegram alerts only if
the daily pulse is useful and actionable. Neither is this atom.

## Non-claims

Not alpha. Not NetReturn. Not canonical DONE. Not current runtime health.
Not empirical 30d/90d storage growth. Not a Telegram install. Not a second
reclaim or restore.
