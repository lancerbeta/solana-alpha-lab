# T27-A0-A3 — Historical collection authority: design

## Decision

Create one offline, versioned authority-and-evidence contract for a possible
future historical Solana pool price/volume capture.  The contract decides
whether the future capture may be proposed to the owner; it does not retrieve
data, adopt a provider, build a downloader, or begin TASK-27 research.

The only owner decision produced by a future conforming capture is one of:

- `AUTHORIZE_FEASIBILITY_CAPTURE`;
- `REDESIGN`;
- `CLOSE_DATA_ROUTE`.

It cannot authorize a strategy, execution, wallet, transaction, cash spend,
or a claim of alpha.

## Why this boundary

T27-A0-A2 froze a synthetic 15-minute price/volume research-screen contract.
The next uncertainty is not a model: it is whether a public historical source
can provide a sufficiently complete and retained evidence panel without
silently converting retrospective history into point-in-time (PIT) truth.

This contract deliberately separates two evidence grades:

- `DESCRIPTIVE_ONLY`: a historical response obtained today can describe a past
  price/volume path, but does not prove when those bars were available to a
  historical decision;
- `PIT_ADMISSIBLE`: the source and retained evidence establish the applicable
  `available_at` boundary for each decision-relevant observation.

Most ordinary historical OHLCV retrieval is, at first, only
`DESCRIPTIVE_ONLY`.  It must not be presented as PIT-safe merely because its
timestamps are old or its bars are complete.

## Chosen approach

Implement a contract package, not a collection component:

1. A Markdown contract freezes authority, the evidence grades, the future
   sampling plan, caps, retention, falsifiers, and explicit non-claims.
2. A YAML configuration supplies machine-readable constants and enums only;
   no credentials, URL, pool identifier, raw response, or active provider
   integration is stored.
3. A JSON Schema describes synthetic authority/evidence packets.  It validates
   a proposed future capture receipt but cannot make any network request.
4. A synthetic fixture and adversarial test module prove valid and rejected
   packets deterministically.
5. A machine-readable acceptance receipt records that the offline contract,
   rather than external data, was accepted.

No provider call, storage of raw market data, wallet/signer action, RPC/WSS,
transaction activity, cash action, strategy logic, database migration,
Catalog propagation, or Project Source change is part of A3.

## Future source and sampling boundary

`GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE` is only a candidate source based
on the already-completed bounded public probe.  A later task must re-confirm
the public surface and its terms at the time of action.  This contract creates
no standing source authorization and no automatic fallback provider.

The recommended future feasibility proposal is intentionally small:

- at most 6 public discovery requests, used only to inspect the current
  discovery surface;
- at most 24 OHLCV requests for a frozen candidate panel;
- 15-minute bars only; target at least 24 consecutive hours per candidate;
- success threshold: at least 12 complete, retained, identity-bound panels.

Discovery is not a market universe, an unbiased sample, a watchlist, or alpha
evidence.  It may only demonstrate that the source surface can expose a pool
candidate.  Each chosen panel requires an immutable discovery/selection
snapshot, selection timestamp, request count, and later raw/source hashes.

Fewer than 12 valid panels out of the proposed 24-request limit, an
unrecoverable gap, ambiguous pool/token identity, or missing retained raw
evidence yields `REDESIGN` or `CLOSE_DATA_ROUTE`; it never permits relaxed
coverage or substituted data.

## Availability, retention, and escalation

Each candidate capture must declare its evidence grade before collection.
Absent source-backed availability proof, collected history remains
`DESCRIPTIVE_ONLY`; it cannot support a claim that the price/volume condition
was known at a past entry time.  A missing or stale `available_at` is unknown,
not implied by `event_time`, fetch time, or a complete panel.

Retain evidence in two tiers:

- raw from a failed or unusable feasibility probe: 30 days with its failure
  receipt, unless a stronger legal/security retention rule applies;
- raw that underlies an accepted dataset, trial, or owner decision: retain it
  together with that dependent research and its hashes; never delete it merely
  because 30 days elapsed.

Any future collection needs a new owner-approved authority packet that names
the exact source, date range, frozen selection method, call and storage caps,
retention location, consumer decision, evidence grade sought, and stop/recovery
path.  No automatic expansion, retry after an ambiguous external response, or
provider substitution is allowed.

## Deterministic adversarial acceptance

The tests must accept a bounded `DESCRIPTIVE_ONLY` proposal and reject or
classify correctly:

- a PIT claim without explicit availability proof;
- calls above 6 discovery or 24 OHLCV requests;
- a target below 12 complete panels or a success conclusion from incomplete
  panels;
- an unfrozen or unhashed selection snapshot;
- a fallback-provider substitution;
- an unretained raw/evidence manifest;
- an attempt to turn the outcome into alpha, execution, PnL, NetReturn, or
  cashflow;
- any implication that this offline contract grants provider, wallet, signer,
  transaction, cash, R3, Catalog, or Source authority.

The fixture must remain wholly synthetic: no real pool ID, response, API URL,
credential, wallet material, signed bytes, or market value.

## Planned files and validation

After this written design is reviewed, the implementation write set is:

- `docs/contracts/task27_historical_collection_authority_contract_v1.md`
- `configs/task27_historical_collection_authority_contract_v1.yaml`
- `catalog/schemas/task27_historical_collection_authority.schema.json`
- `tests/fixtures/task27/historical_collection_authority_v1.json`
- `tests/test_task27_historical_collection_authority_contract.py`
- `docs/evidence/task27/a0a3_historical_collection_authority_acceptance_v1.json`

The implementation will encode adversarial rejections before the happy path.
It will use targeted tests during development and the repository tracked-only
delivery preflight after its final commit.  CI remains a later independent
read-back.

## Acceptance and recovery

Success means a future owner can see precisely what evidence collection would
prove, what it cannot prove, when it must stop, and what must be approved
before even one request occurs.  It does not mean that market data exists,
that it is complete, that it is PIT-admissible, or that any hypothesis is
promising.

If the future bounded capture fails, record the negative evidence and return
`REDESIGN` or `CLOSE_DATA_ROUTE`.  Do not repair the result by loosening the
selection, coverage, availability, or retention rules.
