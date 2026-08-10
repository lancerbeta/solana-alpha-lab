# TASK-30 — Named partial PIT and route-capture contract

## Objective

Prepare one deterministic offline owner packet for a possible 24-hour technical
data-route pilot. It decides only whether a later, separately authorised
external-read packet is fully specified enough to be considered.

## Consumer

The owner needs a short Russian readout that separates a technical check of a
data route from a research trial, execution, or a claim about H07/H01.

## Scope

The reference subject is pool
`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`. Its only role here is
`TECHNICAL_DATA_ROUTE_PILOT`; representativeness is `NOT_ESTABLISHED`.

The future pilot may describe 96 closed 15-minute UTC slots over 24 hours. Each
slot must become an observation or an explicit typed gap. `PIT_MARKET` can only
test a bounded market-data route. `ROUTE_FEASIBILITY` stays conditional until a
later owner packet binds fixed named notionals.

## Non-claims

- No provider is selected or called, and no credential or raw data is used.
- No scheduler, collector, fallback, wallet, signer, transaction, cash action,
  trial, strategy, fill, settlement, PnL, or numeric NetReturn is created.
- The technical pilot does not establish pool representativeness, alpha,
  H07/H01 evidence, or execution truth.
- Missing data is never converted into zero, flat, no-trade, settled, or
  successful capture.

## Terminal decision

`OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED` means only that a later owner
packet can be reviewed. It grants no external authority.
