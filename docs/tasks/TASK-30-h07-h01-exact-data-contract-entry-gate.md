# TASK-30 — H07/H01 exact data contract entry gate

## Objective

Turn the frozen H07/H01 evidence gap into one deterministic, offline decision:
which future data lane can reduce which uncertainty, and which claimed truth
remains unavailable.

## Consumer

The owner needs a short readout before approving any future external capture.
The readout must state whether a named partial PIT capture is worth preparing,
what it cannot prove, and the one next boundary.

## Scope

This atom binds the TASK-28 H07/H01 definition and the TASK-26B, TASK-27,
TASK-30 A6 and A7 receipts to `PIT_MARKET`, `ROUTE_FEASIBILITY` and
`OWNED_EXECUTION` lanes.  It returns exactly
`PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT`, `REDESIGN_DATA` or `CLOSE_ROUTE`.

## Non-claims

No provider selection, provider/API/RPC/WSS call, credential use, raw-data
capture, scheduler, R2/R3 access, wallet/signer/transaction, cash spend,
trial, strategy, fill, settlement, PnL, numeric NetReturn, TASK-30 acceptance
or Project Sources change is allowed.

`PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT` never admits a trial and never resolves
the independent owned-execution blocker.
