# TASK-30 A25 frozen H07/H01 limited diagnostic and measurability contract v1

## Decision

Decide the fate of the named consumer `RC001-H07-H01-LIQUIDITY-RETENTION` with
exactly one terminal outcome. The question is **measurability**, not effect: can
the frozen H07/H01 estimand be computed honestly from the A24 96-slot panel, at
what precision, and what exact data scale would a decisive test require. A
number without that decision is not success, and a number that pretends to
precision the design cannot carry is worse than no number.

## Frozen estimand ownership

The estimand is read, never restated. Two frozen owners must agree:

- `configs/task28_rc001_registry_freeze_v1.yaml`, group
  `RC001-H07-H01-LIQUIDITY-RETENTION`, owns `definition_inputs`, `falsifier`,
  `target_metrics` and `parameter_policy`. The bound hash is the in-YAML
  `definition_sha256`
  `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7`, not the
  hash of the freeze file bytes, and it must also equal
  `canonical_definition_hash(group)`.
- `configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml` owns the lane
  contracts: which lane each requirement belongs to and the exact
  `required_fields` of `PIT_MARKET`, `ROUTE_FEASIBILITY` and `OWNED_EXECUTION`,
  plus the `required_context_fields` of `post_migration_continuation_context`.

Each frozen `definition_inputs` entry is bound to its entry-gate requirement by
normalising the phrase to the requirement key. Any disagreement between the two
owners, or a lane whose declared field set differs from the frozen one, is
`STOP_INTEGRITY_CONFLICT`. If the frozen definition is ambiguous for this
computation, the ambiguity is reported as a finding; it is never resolved by
guessing.

## Frozen inputs and reproduction

The atom is fully offline over already-retained bytes. It calls the A24 module
`src/solana_alpha_lab/task30_raw_to_pit_admissibility.py` to recompute the panel
from the immutable A22 response and the A23 terminal page; it does not fork the
decoder, the attribution or the slot projection. The upstream terminal decision
must be `LIMITED_DIAGNOSTIC_PANEL_READY` and the reproduced batch must match the
frozen orientation exactly: 520 successful transactions, 163 attributed PumpSwap
events, 153 decoded Buy/Sell, 149 target-pool trades split 96 buy and 53 sell, 4
other-pool trades, 10 `CloseUserVolumeAccumulatorEvent`, 14 truncated-log
transactions, and 96 slots split 35 `OBSERVED_TARGET_TRADES`, 1
`PROVEN_NO_TARGET_TRADE`, 60 `STATE_PERSISTENCE_PROVEN`, 0 `UNKNOWN_COVERAGE`.
Any drift is `STOP_INTEGRITY_CONFLICT`. Zero provider, credential, network or
cash side effects are authorized.

## Proving supply and proving absence

Every frozen lane field is classified exactly once against the reproduced panel:

- `PANEL_CONSTANT` and `PIT_FIELD` resolve to a non-empty value in the frozen
  subject or the PIT block.
- `ROW_FIELD` resolves in every one of the 96 rows; the field is `SUPPLIED` only
  when all rows are non-null, `PARTIAL_TYPED_GAP` when some are, `NOT_SUPPLIED`
  when none are.
- `ROW_FIELD_FRESH_ONLY` counts only rows whose staleness flag is false, so a
  carried-forward reserve is never a fresh liquidity observation.
- `IDENTIFIER_ONLY_NOT_AN_OBSERVATION` marks a subject identifier that exists but
  is not an observation record of that lane; it does not count as supplied.
- `ABSENT` is **proved**: the union of leaf names across the panel rows, the PIT
  block and the reference subject must contain none of the field's declared
  equivalents. A declared-absent field that turns up in the panel is
  `STOP_INTEGRITY_CONFLICT`.

A target metric is `NOT_COMPUTABLE` when any field of a required lane is
unsupplied, `COMPUTABLE_WITH_TYPED_GAPS` when only typed gaps remain, and
`COMPUTABLE` otherwise. Each metric-to-lane mapping is justified against an exact
path in the frozen entry gate, not asserted here.

## Statistical honesty

Statistics declare which slot states they consume. `STATE_PERSISTENCE_PROVEN`
slots are typed gaps, never observed trades. `UNKNOWN_COVERAGE` anywhere is
`STOP_INTEGRITY_CONFLICT`. Missing is never zero, flat, filled or settled, and
no forward fill produces a price.

The cluster unit is the pool-day. One pool on one day is one cluster, not 96
independent observations: slots inside a pool-day are serially dependent. With a
single cluster the between-cluster variance is unidentified, the degrees of
freedom are zero, and there is therefore **no** valid standard error and **no**
confidence interval. The naive binomial standard error is emitted only carrying
`INVALID_SLOTS_ARE_NOT_INDEPENDENT_REPLICATES`, so that nobody recomputes it and
mistakes it for precision. Any policy claiming independent slot replicates is
`STOP_INTEGRITY_CONFLICT`.

PIT discipline is inherited from A24 and must not regress: `event_at` is
on-chain, retrieval is never backdated to `blockTime`, retrospective usability is
separate from prospective, and the prospective PIT route stays unusable.

## Required data specification

Because a single cluster yields zero degrees of freedom, the decisive sample size
is **not** derivable from this panel; saying otherwise would be an invented
number. The specification therefore names what is structurally required: the
exact absent fields, the cluster unit, the minimum cluster counts for the
between-cluster variance to be defined at all and for a two-group cluster-level
comparison to exist, the 96 × 900-second slot grid with typed gaps and no
imputation, and route evaluations per cluster as slots times the notional bucket
count. The next measurement is a variance-calibration pilot, not a hypothesis
test.

`NOTIONAL_BUCKET_SET_V1` is a registered frozen parameter with no definition
anywhere in the repository, so the bucket count stays null. The four-notional
convention used by TASK-21 belongs to a different task parameter and is
explicitly not adopted.

## Terminal decisions

- `ESTIMAND_MEASURABLE_AND_DECISIVE_ON_FROZEN_PANEL`: every frozen target metric
  is computable, no frozen parameter is unresolved, and the cluster count reaches
  the minimum for a defined cluster-level comparison.
- `ESTIMAND_MEASURABLE_UNDERPOWERED_WITH_EXACT_DATA_SPEC`: computable, but the
  frozen panel cannot distinguish the hypothesis; the exact data scale is
  emitted.
- `ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN`: at least one frozen
  target metric needs a lane the panel provably lacks; the missing capability is
  named.
- `STOP_INTEGRITY_CONFLICT`: hash drift, an unknown discriminator, coverage that
  cannot be reconciled, or a coercion the policy forbids.

Whatever the outcome, `TASK-30` remains `BLOCKED_DATA` and RC001 is not promoted.
This atom does not establish an effect, route persistence, fillability,
settlement, PnL, NetReturn, continuous price, alpha or strategy promotion.
