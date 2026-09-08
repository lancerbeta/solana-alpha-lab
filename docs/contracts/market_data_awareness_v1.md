# Market Data Awareness v1

Derived owner Market Context. Not a market platform. Not a regime predictor.

## Owner question

What context is observed in my traded slice of the market, how it differs
from recent comparable history, how that is covered, and what may not be
concluded.

## Planes

| Plane | Owns |
| --- | --- |
| Git | definition, field bindings, aggregation, compatibility, display thresholds, Catalog |
| Immutable Observation RDP | observed values, PIT availability, missingness, lineage |
| System Operability | collector/runtime health, deploy identity |
| Market projection | nothing durable |
| Operations | bots, positions, commands |
| Economics | PAPER/SHADOW evidence |
| Research | scientific conclusions |

Git capability is not current market state. Runtime health is not market
state. Market context is not a scientific result and not trading authority.

## Loops

1. **OBSERVE** — PIT-filtered current slice even if reference is absent.
2. **COMPARE** — relative bands only when `context_compatibility_sha256` matches.
3. **INTERPRET** — coverage, gaps, non-claims; links to other surfaces.

## Compatibility

Do not use whole `schedule_sha256` as the sole comparability key. Derive
`context_compatibility_sha256` from the scientific subset: definition
identity, Tokens V2 projection identity, population predicates, lifecycle
landmarks/offsets, sampling policy that changes representativeness, and
Market Context field ids. Keep `schedule_sha256` and `activation_id` as
provenance. Different fingerprint → `REFERENCE_SCOPE_MISMATCH`.

## PIT

For `as_of`, use only observations with
`first_reliable_available_at <= as_of`. Missing PIT clock is typed missing
in the coverage denominator and excluded from numeric calculation.
No backdating from event_time, mtime, Git, or request start.
Quantile method is Git-owned (`ROUND_FLOOR`); it is not a projector default.

## Population

Not all Solana, not all memecoins, not all pump.fun. Exact tracked/sampled
early pump.fun lifecycle population under the accepted collection contract.
`market_wide_claim = false`. Coverage keeps source-native states.

## Axes

Five V1 axes from `configs/market_context_definition_v1.yaml`. No composite
score. No BULL/BEAR/RISK_ON. Conflicting axes stay conflicting.

## GET purity

`GET /market` issues zero provider calls and zero writes to Research/RDP,
ObservationSchedule, PaperPlane, OperationalStore, Git, manifests or
lineage. No store creation or migration.

## Non-claims

No expected return, no trade/no-trade, no all-market claim, no tested
strategy-context binding (`TESTED_CONTEXT_BINDING = NOT_AVAILABLE`), no
bot authority, no ORCH-001, no discovery ranker.
