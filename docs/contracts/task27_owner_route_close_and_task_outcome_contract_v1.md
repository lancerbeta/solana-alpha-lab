# TASK-27 A1S4 — Owner route-close and task-outcome contract v1

## Purpose and consumer

`T27-A1S4_OWNER_ROUTE_CLOSE_BINDING_AND_TASK_OUTCOME_DECISION_V1` preserves
the owner's exact decision after the A1S3 route review:

```text
ROUTE_CLOSE_ACCEPTED; NO_NEW_PROVIDER_READ
```

Its consumer is the TASK-27 terminal-reconciliation decision. It is an offline
control/evidence record, not a public-history collector, provider comparison,
strategy result, or TASK-27 acceptance.

## Bound inputs

The packet binds these A1S3 artifacts by repository-relative path and SHA-256:

- `configs/task27_gap_classification_and_owner_route_decision_v1.yaml`;
- `docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json`.

Any byte drift fails validation. The record neither opens nor rereads raw
evidence.

## Exact decision and limited outcome

The only valid decision keeps the current disposition:

`CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE`.

It records `ROUTE_CLOSE_ACCEPTED`, `NO_NEW_PROVIDER_READ`, zero external
actions, and the sole allowed proposal
`CLOSE_WITH_LIMITED_NEGATIVE_RESULT`. The proposal means that a feasible
public-history route was not demonstrated within the frozen, owner-authorized
scope. It does not conclude that public history generally, another provider,
alpha, execution, PnL, NetReturn, or cashflow is impossible or negative.

`MISSING_UNKNOWN` remains missing. It cannot become zero, flat, continuous,
settled, or PIT-admissible.

## Authority and non-claims

Provider/API/RPC/WSS calls, credentials, raw retention, R2/R3 reads,
wallet/signer/transaction actions, cash spend, and UI activation remain zero or
false. A1S4 does not select another provider, explain the A1S2 gaps, alter a
Project Source role, update generated Catalog files, or claim TASK-27 is
complete.

## Acceptance

Acceptance requires one schema-valid synthetic packet, exact A1S3 bindings,
and deterministic rejection of binding drift, provider-read promotion,
market-wide conclusion, missing-to-zero conversion, research/execution/economic
claim promotion, and premature TASK-27 completion. The acceptance receipt
records `state_change: NONE` and `task27_acceptance: false`.
