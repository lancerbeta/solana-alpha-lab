# TASK-27 A1S3 — Gap classification and owner route decision contract v1

## Purpose and consumer

`T27-A1S3_OFFLINE_GAP_CLASSIFICATION_AND_OWNER_ROUTE_DECISION_PACKET_V1`
turns the bounded A1S2 result into one machine-checkable owner decision:
whether the *current* Solana Tracker 15-minute pool-history route meets the
already frozen 96-bar contiguous-panel requirement.

Its consumer is `OWNER_PUBLIC_HISTORY_ROUTE_DECISION`.  It is not a history
collector, a provider evaluation, a strategy result, or TASK-27 acceptance.

## Evidence boundary

The packet binds the tracked A1 and A1S2 receipts by path and SHA-256.  It also
retains the existing A1S2 raw-manifest and panel-projection hashes as audit
references.  It does not read, copy, or commit local raw JSON.

The admissible observation is exactly:

- expected natural 15-minute bars: `96`;
- observed bars: `33`;
- missing natural bars: `63`;
- returned zero-volume bars: `18`;
- internal gap regions: `21`;
- longest observed gap: `8100` seconds;
- state of every absent interval: `MISSING_UNKNOWN`.

The first three counts and the incomplete-panel disposition are tracked A1S2
facts.  The supplementary gap/zero-volume counts are bound to the retained A1S2
panel-projection hash; they constrain inference but do not create a new data
claim.

## Classification rules

Each explanation has one permitted classification:

- `POSSIBLE_NOT_PROVEN` — compatible with this observation, but not established;
- `NARROW_FORM_FALSIFIED` — its exact narrow form contradicts the observation;
- `NOT_TESTED` — this atom contains no evidence either way.

`PROVEN_CAUSE` is invalid.  In particular, returned zero-volume bars falsify
only the narrow assertion that the endpoint emits a bar *only* when a trade
occurred.  They do not prove that liquidity, aggregation, coverage, or a
provider defect caused the missing intervals.

## Current-route decision

The only valid route conclusion is:

`CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE`

It applies only to this provider route, the frozen base mint/pool/window, and
the requirement for a complete 96-bar natural panel.  It does not close
TASK-27, reject all public-history sources, determine token tradability, or
establish an alpha result.

The only permitted continuation boundary is:

`SEPARATE_OWNER_EXTERNAL_READ_DECISION_REQUIRED`

It names no provider, URL, key, call budget, or automatic fallback.  Any future
external test requires a new exact owner authorization and must independently
establish identity, missingness semantics, retention, and its own stop rule.

## Non-claims and authority

`MISSING_UNKNOWN` is never converted to zero volume, a flat candle, a no-trade
fact, a carried-forward price, or a continuous/PIT path.  The packet keeps
PIT-admissible, alpha, execution, PnL, NetReturn, and cashflow claims false.

Provider/API/RPC/WSS calls, credentials, raw-response retention, R2/R3, wallet,
signer, transaction, cash spend, and TASK-27 acceptance are outside this atom
and remain zero or false.  `state_change` is `NONE`; Project Sources and
Catalog-generated consumers do not change.

## Acceptance

The contract passes only when its synthetic packet validates against the schema,
binds the exact A1/A1S2 evidence, and rejects every adversarial promotion
defined in the fixture.  Failure to bind the inputs or an attempt to infer a
cause fails closed and cannot trigger a fallback read.
