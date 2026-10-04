# Forge research-universe policy V1

Owner: `FORGE_RESEARCH_UNIVERSE_POLICY_V1`.
This document grants no scientific, provider, activation, or merge authority.

Git owns this validator and the field names. ResearchStore owns the active
profile as an append-only `FORGE_RESEARCH_UNIVERSE_POLICY` research artifact.
A frozen experiment recipe owns the snapshot that was applied.

The only mutable settings are `min_holders` and `min_liquidity_usd`. Both are
required at the decision time of a new Forge operation:

`existing BASE_X eligibility AND holder_count >= min_holders AND liquidity_usd >= min_liquidity_usd`.

Fields are `FIELD-HOLDER-COUNT-001` (`holderCount`) and
`FIELD-LIQUIDITY-USD-001` (`liquidity` / `liquidityUsd`). Market cap, volume,
and a later or missing cell are not substitutes. Observed zero is a number.
`PASS`, `FAIL`, and `UNKNOWN` are one status. Only `PASS` enters the target
search. `FAIL` and `UNKNOWN` stay in the admission denominator.

No active profile, a stale proposal, or a hash mismatch does not drop the
filter. A new public run stops with `UNIVERSE_POLICY_REQUIRED` or
`UNIVERSE_POLICY_BINDING_MISMATCH`. An open Forge operation blocks apply.
The same semantic profile applied again is a readback, not a new look and
not a new quota. A saved recipe replays its own snapshot when the active
profile later changes.

Changing 5000 to 20000 uses the same commands. It does not reset MAIN,
adaptive, or focus budgets and does not start a search.
