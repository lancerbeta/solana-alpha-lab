# TASK-23: bounded R2 cohort diagnostics

- Evidence as of: `2026-08-01T22:10:00Z`
- Atom: `T23-A4_BOUNDED_ANALYSIS_AND_ADVERSARIAL_ACCEPTANCE_V1`
- Decision: `DIAGNOSTICS_READY_WITH_LIMITATIONS`

## Owner decision

R2 diagnostics are reproducible enough to register and use for bounded next-step design. This permits only A5 registration and Factory Fit review. It does **not** establish alpha, execution capacity, fillability, realized VWAP, NetReturn, market-wide validity, or authority to inspect R3/outcomes.

## What was actually observed

- Frozen population: 3 members, 9 planned/observed panels, 36 planned/observed buy legs, and 36 eligible/observed dependent sell legs.
- Quote availability: buy 36/36 planned and 36/36 observed; dependent sell 36/36 eligible and 36/36 observed.
- Actual elapsed seconds from each member's reliable P0: P0 0.0–0.0; P1 2347.843352–2347.885847; P2 5042.775573–5042.839916. P0/P1/P2 are labels, not substituted nominal horizons.
- Quote-notional capacity proxy reached the tested ceiling of $100 in every panel. This is right-censored at the largest tested size; it is not measured market depth or fillable size.
- Quote-only round-trip retention across 36 pairs: min 8528.697 bps, median 9586.8422 bps, max 10061.125 bps. Values above 10,000 bps are still quote ratios, not profit after costs or execution evidence.

## Effective sample and dependence

All rows belong to one capture cluster. Therefore the effective independent cluster count is at most 1. The 3 members, 9 panels, and 36 quote pairs are repeated descriptive observations—not independent sample size. No p-values, confidence intervals, IID assumption, or population generalization are valid here.

## Negative results and limitations

- No `NO_ROUTE`, provider error, invalid response, timeout, or missing panel/leg appeared. Typed missing/failure states were retained, but zero observed failures does not mean zero future failure probability.
- No validation population was used: R3 path discovery/read = 0; outcome paths outside R2 opened = 0. There is no OOS or outcome claim.
- A3 did not materialize route IDs or route-continuity diagnostics. This report makes no route-continuity claim; repair would require separately authorized raw-R2 reprojection.
- Catalog registration of A3/A4 evidence IDs and the append-only trial-ledger hash refresh are deferred to A5. Until then, full Catalog-integrity validation must fail closed; this A4 acceptance applies only to the bounded analysis and its adversarial checks.
- The provider `priceImpactPct` field is reported only as the raw provider field. Its units were not reinterpreted.
- All capacity and retention findings are quote-only: neither `Touch`, `Fillable`, `RealizedVWAP`, nor `NetReturn` was measured.

## Denominator contract

Missing is never coerced to zero. Every rate above publishes its planned, observed, or eligibility denominator. The retained typed states are: CAPTURE_DEAD, CAPTURE_STOPPED, INVALID_RESPONSE, NO_ROUTE, PANEL_MISSING, PROVIDER_ERROR, QUOTE_AVAILABLE, SELL_NOT_ATTEMPTED, TIMEOUT, TIMESTAMP_INVALID.

## Stop boundary

Next candidate atom: `T23-A5_REGISTER_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1`. A4 does not authorize it and does not authorize R3, provider, wallet, transaction, deployment, merge, or release actions.
