# TASK-27 exact owner external-read review contract v1

## Purpose

`T27-A0-A6_EXACT_OWNER_EXTERNAL_READ_REVIEW_V1` creates one deterministic,
offline review packet for a future owner decision about a bounded public
price/volume history read. It does not select a real pool, contact a provider,
retain a provider response or grant a request.

The only positive review result is
`READY_FOR_OWNER_EXTERNAL_READ_DECISION`. It means that a later request has a
safe shape to present to the owner. It keeps
`provider_read_authority=false`; it is not a GET, an approval, a source-fitness
claim or a data-collection result.

## Inherited limits and Source binding

The sole source candidate remains
`GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`. There is no fallback-provider
right. The review inherits A4's limits: at most six discovery reads, at most
24 OHLCV reads, a 15-minute interval, 24-hour panels and at least 12 complete
panels. A lower requested read count is permissible only in the later exact
owner request; this A6 template freezes the ceiling and cannot widen it.

The review binds only to `ACTIVATION_CONFIRMED_USER_SMOKE` through the exact
A5R1 activation receipt. A missing state, a different receipt or a changed
receipt hash produces `SOURCE_SMOKE_BINDING_REQUIRED`, never the positive
review result.

## Future request boundary

No actual target exists in this atom. The later owner request must supply
exact values for all of these fields:

- `request_id`;
- `pool_identity`;
- `selection_snapshot_id`;
- `selection_snapshot_sha256`;
- `selection_time`;
- `universe_description`; and
- `raw_evidence_manifest_id`.

Until then every field is literally `OWNER_INPUT_REQUIRED`. Replacing a
placeholder with a value in this offline packet is a forbidden actual-evidence
claim, even if that value looks synthetic. It cannot create a market target by
accident.

The packet contains an approval phrase template solely to show the future
owner decision shape. Its state is
`TEMPLATE_INVALID_UNTIL_EXACT_OWNER_APPROVAL`; it is invalid and has no effect
until every required value is exact and a new owner instruction separately
authorises that request.

## Non-claims and fail-closed behaviour

This atom makes zero provider/API/RPC/WSS calls, uses no credential, reads no
R2/R3 value or path, creates no wallet/signer/transaction, spends no cash and
retains zero raw provider responses. It does not change a Project Source,
release, Catalog record or dependency.

It establishes no historical availability proof, PIT-admissible history,
representative universe, alpha, strategy, quote, fill, execution, inventory,
PnL, NetReturn or owner cashflow. Its only permitted claim scope is
`HISTORICAL_FEASIBILITY_ONLY`, and any future history remains
`DESCRIPTIVE_ONLY` until independent availability evidence exists.

Any authority promotion, external action, raw retention, incomplete Source
binding, fallback source, cap breach, placeholder replacement, forbidden claim
or premature approval phrase fails closed to
`REDESIGN_EXTERNAL_READ_PACKET` or `CLOSE_PUBLIC_HISTORY_ROUTE`. No external
read is used to resolve the ambiguity.
