# T27-A1S3 — Gap classification and owner route decision: design

## Decision

Create one offline, versioned decision packet that classifies what the exact
Stage B observation can and cannot establish about the incomplete 15-minute
OHLCV panel.  The packet closes the *current Solana Tracker pool-history
route* as not feasible for the frozen panel contract.  It does not diagnose
the cause of the gaps, select a replacement provider, or authorize an external
read.

## Why this boundary

The exact Stage B run established a valid pool/base/quote identity and returned
33 of 96 required 15-minute bars, leaving 63 intervals `MISSING_UNKNOWN`.
Returned bars are grid-aligned and internally valid, but the panel has 21
internal gap regions.  Eighteen returned bars have zero volume.  This falsifies
the narrow statement that the endpoint emits a bar only when a trade occurred;
it does not prove or disprove broader explanations such as low activity,
aggregation policy, or incomplete provider coverage.

Choosing another provider from that single observation would turn an evidence
gap into a procurement decision.  A small offline classifier is the cheapest
way to preserve the negative result, make the remaining uncertainty explicit,
and state what a future *separately approved* read would have to discriminate.

## Exact inputs

The implementation binds, by path and SHA-256, only to tracked evidence:

- `docs/evidence/task27/a1s2_stage_b_pool_history_runtime_receipt_v1.json`;
- `configs/task27_stage_b_exact_owner_packet_v1.yaml`;
- `docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json`.

The packet may repeat the already tracked raw-manifest and projection hashes,
but it must not read, copy, or commit their local raw JSON.  The retained raw
files remain outside Git under their existing A4 retention policy.

## Chosen model

The decision packet has four independent layers.

1. **Observed facts** — 33/96 bars, 63 missing intervals, strict ordering and
   grid alignment, no invalid OHLCV rows, and zero-volume returned bars.
2. **Explanations** — each candidate explanation is `POSSIBLE_NOT_PROVEN`,
   `NARROW_FORM_FALSIFIED`, or `NOT_TESTED`; none may be `PROVEN_CAUSE` from
   this one panel.
3. **Route disposition** —
   `CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE` for the
   frozen contiguous-panel requirement.  This is a finding about one endpoint,
   pool, window, and contract; it is not a statement about all Solana history
   sources or the token's tradability.
4. **Future-decision boundary** — the only continuation state is
   `SEPARATE_OWNER_EXTERNAL_READ_DECISION_REQUIRED`.  It may list abstract
   discriminator requirements (same frozen identity/window/grid, explicit
   missingness semantics, raw retention, and no automatic fallback), but it
   must contain no provider name, URL, key, call count, or authorization.

## Semantic invariants and non-claims

- `MISSING_UNKNOWN` is never converted to zero volume, a flat candle, carried
  price, no trade, or a complete path.
- A complete 96-bar panel is not inferred from a successful HTTP response.
- `PIT_ADMISSIBLE`, alpha, execution, PnL, NetReturn, cashflow, representative
  sample, and provider equivalence remain false or unavailable.
- The Stage A `pumpswap` / Stage B `pumpfun-amm` market-label difference remains
  unresolved and is not used to alter the frozen pool identity.
- No automatic provider fallback, fresh query, raw retention, wallet, signer,
  transaction, R2/R3, spending, or TASK-27 acceptance is allowed.

## Planned implementation

The atom follows the existing Task-27 contract pattern and creates exactly:

- `docs/contracts/task27_gap_classification_and_owner_route_decision_contract_v1.md`
- `configs/task27_gap_classification_and_owner_route_decision_v1.yaml`
- `catalog/schemas/task27_gap_classification_and_owner_route_decision.schema.json`
- `tests/fixtures/task27/gap_classification_and_owner_route_decision_v1.json`
- `tests/test_task27_gap_classification_and_owner_route_decision.py`
- `docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json`

The schema is a local validation contract only.  It does not create a new
catalog asset transaction, generated Catalog update, Project Source release, or
runtime provider component.

The deterministic test starts with a rejected synthetic packet and validates a
single admissible fixture.  Its adversarial cases must reject: missing-to-zero
conversion, a trade-only causal overclaim, any `PROVEN_CAUSE` classification,
PIT promotion, automatic provider selection or external authority, and a
claim that closing this route closes TASK-27.

## Acceptance and recovery

Success means the negative result is machine-checkable and the next choice is
honest: close this route now, or later submit one new exact owner packet for a
test that can actually distinguish a named explanation.  It does not mean that
the explanation is known or that a new provider is warranted.

If the packet cannot bind the prior receipt hashes or its fixture permits an
overclaim, it fails closed.  No fallback read is attempted; the current route
remains closed for the frozen 96-bar feasibility requirement until a distinct
owner decision changes that boundary.
