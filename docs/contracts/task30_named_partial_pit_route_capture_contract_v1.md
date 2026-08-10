# TASK-30 A9 — Named partial PIT and route-capture contract v1

## Frozen binding

| Field | Required value |
| --- | --- |
| Frozen group | `RC001-H07-H01-LIQUIDITY-RETENTION` |
| Frozen definition SHA-256 | `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7` |
| Upstream A8 decision | `PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT` |
| A9 decision | `OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED` |

## Technical-pilot boundary

The named pool is a technical data-route subject only. The policy fixes a
24-hour interval with 96 closed 15-minute slots. A slot is valid only as one
observed closed interval or one explicit typed gap; missingness has no numeric
or trading interpretation.

`PIT_MARKET` may establish only `BOUNDED_MARKET_DATA_ROUTE_CAPABILITY`.
`ROUTE_FEASIBILITY` is `CONDITIONAL_OWNER_PACKET` and cannot be assessed until
the owner later supplies fixed named notionals. Neither lane establishes a
fill, settlement, inventory, PnL, NetReturn, or H07/H01 result.

## Future external owner packet

Before any external read, the owner packet must bind: provider and endpoint;
verified pool/mint/DEX identity; exact UTC window; named lanes and notionals;
request, quota and credential caps; no fallback; raw-retention location and
hash procedure; backup or explicit tracked waiver; monitoring owner; recovery
path; and non-claims.

Until every value is bound by that separate authority, its state is
`OWNER_INPUT_REQUIRED`. A9 cannot select a provider or turn any blank field
into approval.

## Recovery and stop conditions

Any irrecoverable decision-critical capture requires a backup/restore route or
an explicit tracked waiver before capture. Stop a future attempt on stale or
unverified identity, unresolved prior capture, missing monitoring, unbound
notionals, quota or fee cap breach, fallback request, or a data result that
cannot retain typed gaps.
