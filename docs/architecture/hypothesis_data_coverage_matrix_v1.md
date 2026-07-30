# Hypothesis data coverage matrix v1

Policy: `RETENTION-RECOVERY-T20-001` version `1.0`

Collection spec: `COLLECTION-SPEC-T20-001` version `1.0`

This human-readable index mirrors the authoritative typed field mappings in
`configs/task20_retention_recovery_policy_v1.yaml`. The YAML owns the complete
metadata. This page makes scope and intended use inspectable without hiding
fields behind a broad category.

| Tier | Field ID | What it proves or enables | Retention |
|---|---|---|---|
| T0 | `evaluated_at` | When the candidate decision occurred | Decision lineage |
| T0 | `hypothesis_id` | Which hypothesis owned the evaluation | Decision lineage |
| T0 | `hypothesis_version` | Which immutable hypothesis logic ran | Decision lineage |
| T0 | `trial_id_or_activation_epoch` | Which trial or forward epoch owned state | Decision lineage |
| T0 | `policy_version` | Which membership policy produced the result | Decision lineage |
| T0 | `mint` | Exact evaluated token identity | Decision lineage |
| T0 | `pool_identity_if_applicable` | Exact pool when the decision is pool-scoped | Decision lineage |
| T0 | `exact_rule_input_values` | Values actually consumed by rules | Decision lineage |
| T0 | `input_feature_and_source_versions` | Feature and source lineage | Decision lineage |
| T0 | `evaluation_result` | Reject, not-evaluable, admit, or exit result | Decision lineage |
| T0 | `reason_codes` | Machine-readable decision reasons | Decision lineage |
| T0 | `missingness_codes` | Typed absence of required inputs | Decision lineage |
| T0 | `coverage_gap_codes` | Known source or time gaps | Decision lineage |
| T0 | `membership_transition` | Append-only watchlist state change | Decision lineage |
| T0 | `first_reliable_available_at` | PIT-safe decision availability | Decision lineage |
| T0 | `evidence_checkpoint` | Content-bound evidence reference | Decision lineage |
| T0 | `quote_or_liquidity_snapshot_sha256` | Exact snapshot used by a rule, when used | Decision lineage |
| T1 | `bar_event_minute` | UTC minute bucket identity | Reconstructible cache |
| T1 | `bar_open` | First price in the minute | Reconstructible cache |
| T1 | `bar_high` | Maximum price in the minute | Reconstructible cache |
| T1 | `bar_low` | Minimum price in the minute | Reconstructible cache |
| T1 | `bar_close` | Last price in the minute | Reconstructible cache |
| T1 | `bar_volume` | Traded volume in the minute | Reconstructible cache |
| T1 | `bar_source_revision` | Immutable source revision | Reconstructible cache |
| T1 | `bar_first_reliable_available_at` | When the bar became decision-safe | Reconstructible cache |
| T1 | `lifecycle_event_type` | Pool or token lifecycle event class | Unique raw evidence |
| T1 | `lifecycle_event_at` | When the lifecycle event occurred | Unique raw evidence |
| T1 | `lifecycle_first_reliable_available_at` | When the event became decision-safe | Unique raw evidence |
| T2 | `quote_side` | Buy or sell direction | Unique raw evidence |
| T2 | `quote_notional_usd` | Reference notional tested | Unique raw evidence |
| T2 | `quote_input_atomic` | Exact atomic input | Unique raw evidence |
| T2 | `quote_output_atomic` | Exact quoted atomic output | Unique raw evidence |
| T2 | `quote_route_identity` | Exact route or pool sequence | Unique raw evidence |
| T2 | `quote_requested_at` | Local request time | Unique raw evidence |
| T2 | `quote_response_at` | Local response receipt time | Unique raw evidence |
| T2 | `quote_first_reliable_available_at` | When the validated quote was usable | Unique raw evidence |
| T2 | `quote_provider_status` | Success, timeout, error, or unavailable | Unique raw evidence |
| T2 | `quote_raw_content_sha256` | Exact raw response identity | Unique raw evidence |
| T2 | `quote_cost_credits` | Physical provider-credit attribution | Unique raw evidence |
| T2 | `quote_response_bytes` | Physical response-byte attribution | Unique raw evidence |

## Consumer map

- T0: `FACTORY-001` and `TASK-21`.
- T1: `FACTORY-001`, `TASK-21`, and `REG-RESEARCH-001`.
- T2: `HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1`, `TASK-21`, and
  `FACTORY-001`.

The T2 consumer list does not authorize a request. Live capture additionally
requires every A2 admission condition, exact active membership, immutable
physical caps, and a separate external atom.

## Availability model

Event time is not strategy availability. Each field records or defines event,
observation, ingestion, and first reliable availability semantics. Historical
hydration cannot backdate what a strategy could have known. Late revisions and
typed missingness remain evidence instead of disappearing during cleanup.

## Change rule

This matrix is exhaustive for the frozen collection-spec version. A new field,
consumer, availability class, cadence, or decision use is a semantic change and
requires a new version plus deterministic acceptance. UI filename suffixes and
mutable aliases never select the active meaning.
