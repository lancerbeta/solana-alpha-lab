# Forge composite feature recipes V1

Current owner: `FORGE_COMPOSITE_FEATURE_RECIPES_V1`, RAW_ONLY. Consumer: ordinary
Forge pre-search agent, preview, MAIN and registered fixed-time proxy replay.
Executor Brief V4 (2026-10-04) is execution authority; Blueprint V4 is design.
This document grants no market-data, experiment, profile, operation or merge authority.

## Closed vocabulary and identity

`FIELD-HOLDER-COUNT-001` accepts `point_value`, `delta` and `return_ratio`.
Delta is `H(end)-H(start)` in holders. Return is `H(end)/H(start)-1` as a
dimensionless fraction: 1 means +100%, -0.5 means -50%. Return requires a
strictly positive denominator; zero remains usable for delta. No epsilon,
zero fallback, interpolation, smoothing, EWM, generic holder ratio or holder
target. PRICE/LIQUIDITY retain their existing operators. Target remains
`PRICE_RELATIVE_PROXY`; costs remain assumption proxies, never NetReturn.

The two new holder transforms require exactly `name`, `op`, `field_id`, `start`
and `end`. Their text and bound schedule offsets satisfy start < end <= decision.
Unknown parameters, equal/reversed/future windows and incompatible schedules
refuse before values. The common temporal cell owner enforces PIT (information
available by the decision), snapshot occurrence/request lineage, point lateness,
typed finite values and conflicts. Boolean/NaN/Inf, missing and late sources
are unavailable. Negative growth is valid; nonpositive return base is unavailable.

```json
{
  "features": [
    {"name":"holders","op":"delta","field_id":"FIELD-HOLDER-COUNT-001","start":"X300","end":"Y900"},
    {"name":"price","op":"return_ratio","field_id":"FIELD-USD-PRICE-001","start":"X300","end":"Y900"},
    {"name":"liquidity","op":"ratio","field_id":"FIELD-LIQUIDITY-USD-001","numerator":"Y900","denominator":"X300"}
  ],
  "all": [
    {"feature":"holders","op":"gt","value":0},
    {"feature":"price","op":"gte","value":0},
    {"feature":"liquidity","op":"gte","value":1}
  ]
}
```

This fragment is composed inside the existing full temporal query and frozen
schedule/target/cost envelope. `COMPOUND_FIRST` is available for a natural
compound; a holder-only condition can use SIMPLE. Neither changes the ladder.
Field/operator/window/threshold/decision/target enter canonical identity.
`temporal_holder_claim_identity()` carries complex recipes as canonical JSON
through grounded input, candidate, freeze, Critic and owner. No date-pair FEAT,
new CAP, expression parser or ritual CALC/schema bump is introduced. Old
PRICE/LIQUIDITY/holder-point specs, hashes and numerical outputs stay frozen.

## Common prefix population and full support

For a new holder transform, `_project_temporal_members` is the common preview
and evaluator owner. Membership depends on X300 eligibility/liquidity, the
bound decision universe and decision price, independently of future targets.
The identity is (mint, decision timestamp); a repeated mint at another decision
is not independent replication. Overlap with a disagreement in a declared
feature makes that feature unavailable and preserves the eligible denominator.
Disagreement in membership cells excludes that identity. A future target-copy
disagreement keeps prefix support but makes the raw MAIN target unavailable
(`TARGET_DELIVERY_CONFLICT`), independent of delivery order. Undeclared cells
cannot change prefix support. Legacy queries keep their accepted conflict policy.

Public `discovery-preview` retains every declared feature and loads only its
pre-decision points plus the mandatory membership cells. No target values are
loaded. Full counts precede the 24-example sample: BASE_X; universe PASS/FAIL/
UNKNOWN; decision eligibility, which additionally needs decision price; each
feature and joint calculable/unavailable counts on decision eligibility.
Pooled reason counts explain unavailable features; cohorts carry eligibility
and joint counts. Marginal coverage is never multiplied into joint support.
Unique mint/decision counts and duplicate/integrity diagnostics retain their
grain. Cohort sums need disjointness proof; independence remains UNKNOWN.
Counts are seed-independent. Output cap remains 64 KiB; excess returns typed
`PREVIEW_TOO_LARGE`, not a truncated population presented as complete.

## Persistence and fresh admission

The existing `DISCOVERY_FEATURE_PREVIEW` artifact stores the full support,
canonical feature recipe, frozen file/release/schedule input and policy snapshot.
Exact cold readback verifies committed/wrapper/payload/recipe hashes and current
input identity without scientific value loading or another reservation. Legacy
artifacts without detail report `LEGACY_PREVIEW_DETAIL_UNAVAILABLE`; they are
never silently reconstructed. A new seed is another exposure, not free sampling.

Only fresh compute applies the static bound-universe guard. It understands
direct point values of the same universe field at the same decision and its
closed predicate operators. For H>=50: only H>=3 (or only proven tautologies)
refuses as `UNIVERSE_NON_DISCRIMINATING_QUESTION`; required H<50 refuses as
`UNIVERSE_IMPOSSIBLE_QUESTION`. H>=50 AND delta(H)>0 warns
`REDUNDANT_UNIVERSE_CONJUNCT` and retains the exact recipe/hash. H>=100, H>50,
earlier points, transforms and unknown equivalence are not vetoed by dominance.
No predicate is deleted and no baseline bypass flag exists.

Integrity checks and verified saved readback, pending resume or exact calculation
correction precede this fresh guard. Replay keeps frozen policy rather than
today's minima. Existing authority/state/profile compare-and-recheck remains
effective before actual execution. STOPPED/COMPLETED never allow a new look.
Syntax/refusal/missingness/cap are not scientific negatives or quota refunds.

Recovery follows the typed failure; none of these actions grants a new look:

| Failure or warning | Next action |
| --- | --- |
| `FEATURE_WINDOW_INVALID` | Check the bound point offsets. Prepare a compatible exact recipe only within current operation authority; never edit a frozen binding or refund quota. |
| `UNIVERSE_NON_DISCRIMINATING_QUESTION`, `UNIVERSE_IMPOSSIBLE_QUESTION` | Replace the question with a meaningful supported recipe within current authority and exposure accounting; never bypass the bound universe. |
| `REDUNDANT_UNIVERSE_CONJUNCT` | Keep the admitted exact recipe/hash and proceed once. Do not repeat MAIN to remove the warning. |
| Saved preview integrity, input, policy or recipe mismatch | Stop readback; inspect and restore the exact source/artifact through its owner. Never replay stale support or rebind to bypass verification. |
| `PREVIEW_TOO_LARGE` | Stop this preview. Do not repeat unchanged input, increase the cap or use a truncated sample as full support. A smaller question requires its existing authority and exposure accounting. |
| `LEGACY_PREVIEW_DETAIL_UNAVAILABLE` | Read the historical receipt as recorded. A new detailed preview requires current allowance; do not reconstruct it silently. |

## Agent and lifecycle consumers

Actual ordinary preflight carries `temporal_recipe_capabilities`, derived from
the current field/operator owner, including parameters, units and PIT/missing
constraints. It is absent from frozen CONTROL/challenger input. Mechanism ->
smallest supported recipe -> optional authorized support -> exact question.
Support proves computability only; it does not prove variance, precision or alpha.
After an outcome, operator/window/threshold/component changes retain existing
adaptive/new-question accounting. Prior exposure, applicable prior conclusion
and resource permission remain distinct; no focus or memory reset is granted.

Public MAIN persists grounded output; the same output binds persist-draft/freeze,
isolated Critic and required finalize/classify, then owner-final `forge-run
--persist`. Crash after commit uses zero-evaluation saved readback. Registered
`CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001` numerical replay really evaluates the
frozen input and reproduces the saved result without spending a new look.
Cold stage discovery also retains validated completed ordinary `KILL_*`
sessions that are not reusable scientific evidence. Their existing terminal
and `NON_SCIENTIFIC_STOP` meaning remain intact; they do not fall back to a
pre-freeze draft, unlock a new look or gain `REUSED_VALID` status.
Nested canonical JSON identity is decoded before physical-path screening;
real paths in decoded leaves/keys still refuse. No path-safety bypass is added.

Verification: `tests/test_forge_composite_feature_recipes_v1.py` uses production
seal/import/public CLI with explicit disposable data roots; fixtures never
hand-write production bindings or final state. Existing lifecycle #373 and
universe/revision/point suites preserve negative, technical and stale-state
behavior. Native isolated acceptance and final delivery evidence are recorded
under `docs/evidence/forge_composite_feature_recipes_v1/`.
Synthetic evidence grants no real holder MAIN/adaptive, C5/holdout read, live
ResearchStore/profile/operation change, budget/estimand expansion or alpha claim.
