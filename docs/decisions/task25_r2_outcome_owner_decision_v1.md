# TASK-25 R2 outcome owner decision v1

## Decision header

- Task: `TASK-25`
- Atom: `T25-A5_ADVERSARIAL_ACCEPTANCE_AND_OWNER_DECISION_V1`
- Decision ID: `T25-OWNER-DECISION-001`
- Status: `ACCEPTED_BY_BOUNDED_A5_EVIDENCE`
- Decision: `REDESIGN_TRACKED_R2_OUTCOME_SURFACE_BEFORE_OWNER_COMPARISON`
- R3 authority: `DENY`

## One owner decision

Do not use the current three-table TASK-23 tracked projection for a strategy
comparison, promotion, R3 opening or any execution/return claim. Preserve A4 as an
accepted negative result, then create one bounded R2-only reprojection that retains the
exact quote identity and PIT fields already validated in the sealed raw R2 records.

This is a redesign of the tracked derivation surface, not a request for new collection.
It does not claim that the underlying R2 data are decision-ready until the redesigned
projection is produced and independently accepted.

## Facts

1. A4 emitted 108/108 records: 99 `UNKNOWN` and nine supported
   `DISCRETE_PATH_GRID` records. All 36 buy and 36 dependent-sell observations retained
   `QUOTE_AVAILABLE`, but zero `FILLABLE` and zero `QUOTE_EXIT` records were supported.
2. The tracked quote-pair table omits the exact output mint, buy output atomic amount,
   dependent sell input atomic amount, quote attempt IDs, request/response timestamps,
   strategy-availability timestamp, ingest timestamp, quote age and provider latency.
3. The frozen TASK-23 raw parser validates those exact fields through `QuoteAttempt`,
   verifies raw/normalized mint and amount equality, and binds dependent sells to the
   exact buy output. Therefore the observed gap is a lossy tracked projection boundary,
   not evidence that those fields were absent from the sealed R2 records.
4. A4 reopened zero raw R2 value files and read zero R3 paths or values. A5 preserves
   both boundaries.

## Required redesign contract

The next reprojection may consume only the nine content-addressed R2 raw files already
sealed by the TASK-23 receipt. Its tracked output must preserve, for every quote attempt:

- `quote_attempt_id`, `raw_event_id`, `request_hash` and response content SHA-256;
- side, exact input/output mints, atomic amounts and decimals;
- buy-to-dependent-sell link using the exact buy output inventory;
- `requested_at`, `response_at`, `first_reliable_available_at`,
  `available_to_strategy_at`, `ingested_at`, `quote_age_ms` and
  `provider_latency_ms`;
- terminal quote state, error class, route identity/count and fee provenance;
- actual `P0/P1/P2` observation labels plus actual elapsed time, without nominal
  horizon claims;
- the existing R2 split/member/raw-content lineage and immutable content hashes.

`FILLABLE` or `QUOTE_EXIT` may become `SUPPORTED` only after the redesigned surface
satisfies the frozen A2 exact-notional, freshness, latency and PIT contract. A quote must
still never imply an order, fill, settlement, flat inventory, `REALIZED_VWAP`, `NET`,
owner cashflow or continuous path coverage.

## Rejected alternatives

- `ACCEPT_CURRENT_TRACKED_PROJECTION_FOR_OWNER_COMPARISON`: rejected because it would
  promote incomplete quote identity and PIT evidence.
- `STOP_UNDERLYING_R2_AS_INFEASIBLE`: rejected because the validated upstream schema
  and parser contain the missing fields; the cheapest falsifier is a bounded derivation
  repair, not new acquisition.
- `OPEN_R3_OR_COLLECT_MORE_DATA`: rejected because neither action repairs a lossy R2
  projection and neither is authorized.

## Activation and stop conditions

Candidate repair atom:
`T25-A5R1_EXACT_R2_OUTCOME_SURFACE_REPROJECTION_V1`.

It is not authorized by this decision. It starts only after direct owner approval. It
must stop without opening raw values if any sealed raw hash, member set, split identity,
or pre-read ordering check drifts. It must also stop before R3, provider calls, new data
collection, dependencies, Catalog registration, commit or push unless separately covered
by the active atom and repository authority.

If a faithful tracked reprojection cannot retain the required fields without changing
the estimand or source data, return `STOP_R2_OUTCOME_ROUTE_AS_NOT_DECISION_GRADE` rather
than weakening the A2 contract.

## Evidence bindings

- A4 projection: `docs/evidence/task25/a4_r2_outcome_projection_v1.json`, SHA-256
  `59cbb0bdeea6a80d184ea3c3fdbb3827ff2b23951d2a93a483198374d85da075`.
- A4 read receipt:
  `docs/evidence/task25/a4_bounded_r2_outcome_projection_and_read_receipt_v1.json`,
  SHA-256 `ec2ef9425911e116271b94ee65371ef88bdf52db9e5ba732b6fe2ffc97a358df`.
- TASK-23 raw parser: `src/solana_alpha_lab/task23_diagnostic_projection.py`,
  SHA-256 `728fa77fc82a3e27245a908cfecc2a50e7df82c5813e6b90d4ad8ff0870e57f9`.
- Quote contract model: `src/solana_alpha_lab/contracts/schema_v1.py`, SHA-256
  `ef9435fc0aa6df1d880714e97d3312e068dc82806a8c6ba1ed2d74c9929684ad`.

## Managed write set

1. `docs/decisions/task25_r2_outcome_owner_decision_v1.md`
2. `tests/fixtures/task25/a5_r2_outcome_adversarial_matrix_v1.json`
3. `src/solana_alpha_lab/task25_adversarial_acceptance.py`
4. `tests/test_task25_adversarial_acceptance_and_owner_decision.py`
5. `docs/evidence/task25/a5_adversarial_acceptance_and_owner_decision_v1.json`

Catalog registration and full Factory Fit review remain deferred. This atom performs no
provider/API/RPC/WSS, wallet/signer/transaction, spend, dependency, Source, Catalog,
commit, push, PR or merge action.
