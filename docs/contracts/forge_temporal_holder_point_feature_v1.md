# Temporal holder point feature V1

Owner: `FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1`.
Consumer: `EARLY_HOLDER_STATE_TO_PRICE_PATH_15M_TO_4H`.
This document grants no scientific, provider or merge authority.

## Feature policy

`FIELD-HOLDER-COUNT-001` is the existing typed Tokens V2 observation. Ordinary
temporal Forge originally accepted it under `point_value` at or before the decision.
Current fresh raw recipe policy is owned by
`docs/contracts/forge_composite_feature_recipes_v1.md`: it also permits holder
`delta` and `return_ratio`. This historical consumer retains its exact point query.
PRICE and LIQUIDITY keep their existing operator policy. The holder check is
explicit and precedes the legacy allowlist, so widening that list cannot
authorize holder generic ratio, drawdown or rebound. Target remains PRICE.
Historical hashes/results, the preregistered point consumer and prior exposure
below are unchanged; the fresh universe guard grants no re-execution of it.

Use the existing `FEATURE_OP_UNSUPPORTED`, `TARGET_INVALID` /
`FIELD_NOT_IN_ALLOWLIST` and `FEATURE_AFTER_DECISION` errors. No new evaluator,
raw-provider loader, clock, zero fallback, schema version, CALC version or
capability identity is introduced. V5 output and V1–V5 readers remain current.

The generic temporal cell selection owns availability, acquisition clocks,
snapshot occurrence/request lineage, duplicate conflicts and missingness.
OBSERVED zero is numeric; FIELD_ABSENT / typed missing remains unknown. Late or
uninterpretable cells cannot match. Same-snapshot holder and price retain their
own typed rows and shared occurrence/availability; no raw Jupiter read exists.

Old canonical spec/digest and frozen synthetic result regressions are pinned
in `tests/fixtures/forge_holder_point_v1/old_price.json` and `old_liquidity.json`
from base `94b284534b6ad55a95002d51b9d04b4a5ced6bde`. Holder enters the
`decision_fields` projection only when the actual query uses it.

## Preview and exact scientific binding

The public `discovery-preview` accepts a full temporal query and derives a
feature-only view. Its Arrow loader selects points at or before the decision;
the target never enters the returned value rows. Full-query and feature-only
forms share pre-values validation, so forbidden operators or future points
cannot reach the loader. Null/empty default clock spellings use the canonical
EVENT_TIME_V1 normalization. Feature-point deadline may not exceed decision
deadline, matching the common evaluator's fail-closed boundary. Optional point features are
read through the common cell owner with explicit value/status pairs. A missing
holder remains visible alongside a present price. Traditional previews retain
their existing identity when optional features/policy are absent.

The immutable result recipe owns the scientific identity. For holder queries,
`temporal_holder_claim_identity()` derives exact `primary_x_family`, `primary_y`,
`horizon_notional`, decision and target labels from that recipe and verifies its
digest. Numeric thresholds use lossless canonical float text: `3.0` differs
from `3.0000001`. `descriptive_readout.scientific_identity` carries them through Prompt A,
Critic and owner projection. Selected cards must carry those exact machine
labels; mismatch fails with `LOOK_SCOPE_CONTRADICTION`. This is a closed
display/binding function, not an expression parser. Complex canonical recipes
retain their feature/predicate JSON identity. Legacy PRICE/LIQ cards are unchanged.

Saved recipe → `_public_query_from_recipe()` → existing
`CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001` uses the same evaluator and frozen input.
It labels PRICE_RELATIVE_PROXY and ESTIMATED_NET_PROXY; never NetReturn.

## Preregistered consumer and prior exposure

The exact owner contract, prior exposure and future decision taxonomy are
preserved in `docs/tasks/FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1.md`.
The frozen future question is BASE_X, decision Y900, holder point Y900 >=3,
PRICE_RELATIVE_PROXY Y900→Y14400, exactly one MAIN after separate authorization.
No alternative threshold, price/liquidity condition, interaction or adaptation.
The synthetic candidate explicitly uses PREDICTIVE, declares known confounds
and the frozen taxonomy. Its complement is baseline-minus-matched after subset
proof, retaining V5 UNKNOWN semantics; it never substitutes a known-holder sample.

The idea is outcome-exposed: prior D2 on the same C1–C4 showed that the apparent
downside difference substantially tracked whether price moved. Activity and
price staleness are known confounds. C1–C4 results stay EXPLORATORY; distribution
difference alone is not entry edge. C5 remains untouched and unassigned.

The task freezes `HOLDER_NO_POSITIVE_ENTRY_EDGE`, `HOLDER_ACTIVITY_ONLY`,
`HOLDER_DIRECTIONAL_EDGE_COHORT_UNSTABLE`, `HOLDER_DIRECTIONAL_EDGE_OOS_WORTHY`
and `HOLDER_RESULT_INCONCLUSIVE` exactly as supplied by the owner. Complement
derivation is limited to additive V5 quantities after a subset proof; no
complement median/quantiles/ES/concentration. Activity decomposition is
descriptive, not another look. Equal medians alone do not kill. Worse downside
is a tradeoff to report; threshold stays fixed. The BASE haircut remains
ASSUMPTION_STRESS_ONLY / ASSUMPTION_NOT_CALIBRATED. A surviving gross signal
merely reaches a later economic/execution gate; it is not strategy or promotion.

## Verification and rollback

`tests/test_forge_temporal_holder_point_feature_v1.py` publishes disposable
typed C1–C4 through the production seal/import/schedule owners, then consumes
their binding through public preview, ordinary MAIN, interrupted reply, cold
replay, Prompt A, freeze, Critic packet, owner and registered replay. No binding
is manually reconstructed. Real compatibility reads holder Y900 and metadata
only, after the synthetic loop; inventory must remain unchanged.

Rollback before any real holder look is a separately authorized ordinary Git
revert. After real holder evidence exists, preserve a reader for that recipe
and prefer forward repair; never delete or rewrite saved scientific evidence.
