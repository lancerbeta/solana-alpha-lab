# T27 bounded public-history feasibility authority design

## Purpose

`T27-A0-A4_BOUNDED_PUBLIC_HISTORY_FEASIBILITY_AUTHORITY_PACKET_V1` defines
the offline decision packet that must exist before the owner can consider one
small public historical price/volume feasibility capture. It turns the already
frozen T27 data shape and collection caps into an auditable authority request;
it does not make that request and does not collect data.

The packet answers only: **is the proposed future capture sufficiently
specified to ask the owner for a separate, exact external-read approval?** It
does not answer whether the source will work, whether history is
point-in-time admissible, or whether a price pattern is alpha.

## Context and decision

The current Git tree contains two accepted offline T27 layers:

- the research-screen contract freezes 15-minute pool bars and the
  `FORWARD_CLOSE_RETURN_1H` label;
- the historical-collection authority contract freezes a candidate source,
  caps, raw-evidence rules, retention and the outcomes `AUTHORIZE_FEASIBILITY_CAPTURE`,
  `REDESIGN` and `CLOSE_DATA_ROUTE`.

The available Project Source candidate ends at
`OWNER_AUTHORITY_PACKET_BINDING_V1` and explicitly marks T27 as unauthorised.
It is a valid candidate bundle but is not an activation receipt for the
newer T27 repository work. A4 therefore must preserve that conflict instead
of inferring an external-read right.

## Chosen approach

Create one versioned, synthetic-only authority-packet contract with a JSON
Schema, fixture, deterministic semantic validator and acceptance receipt.
The packet has three terminal outcomes:

- `READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW`;
- `REDESIGN`;
- `CLOSE_DATA_ROUTE`.

`READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW` is deliberately not external
authority. It can be emitted only for a complete proposed capture and says
that the next owner decision may be formulated. It never changes
`provider_read_authority` from `false`.

## Required packet content

Each packet must bind:

1. one candidate source identifier,
   `GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`;
2. a frozen selection-snapshot identity and SHA-256, selection time and
   declared universe description;
3. at most six proposed discovery reads and 24 proposed OHLCV reads;
4. the 15-minute interval, 24 consecutive hours per panel and a requirement
   for at least 12 complete retained panels;
5. a retained raw-evidence manifest location/identity and the existing
   failed-versus-decision-supporting retention policy;
6. a named owner decision, a single named consumer and explicit non-claims;
7. a Project Sources binding state.

The Source binding state is either `ACTIVATION_CONFIRMED_USER_SMOKE` with an
exact seven-role receipt reference, or `SOURCE_ALIGNMENT_REQUIRED`. The latter
is valid evidence of a control-plane gap, but it cannot produce the `READY`
outcome.

## Fail-closed semantics

The validator must reject:

- a provider request, credential, raw response or other external side effect;
- any source other than the one frozen candidate, or an automatic fallback;
- a missing or non-matching selection snapshot/hash;
- read-count, interval, panel-duration or minimum-panel-cap violations;
- a missing raw manifest or ambiguous retention treatment;
- a PIT-admissible claim without source-backed availability proof;
- a `READY` outcome when Project Sources are not activation-confirmed;
- a claim of alpha, execution, fill, PnL, NetReturn or owner cashflow.

History with no availability proof remains `DESCRIPTIVE_ONLY`; it is not
discarded or relabelled as zero. A later real capture must return `REDESIGN` or
`CLOSE_DATA_ROUTE` on incomplete panels, identity ambiguity, raw-evidence
loss or incompatible source behaviour. No threshold is relaxed after values
are read.

## Files and responsibilities

- `docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md`:
  human-readable decision and non-authority boundary.
- `configs/task27_bounded_public_history_feasibility_authority_contract_v1.yaml`:
  machine-readable caps, states and required fields.
- `catalog/schemas/task27_bounded_public_history_feasibility_authority.schema.json`:
  structural packet contract; no Catalog-root registration in this atom.
- `tests/fixtures/task27/bounded_public_history_feasibility_authority_v1.json`:
  synthetic valid and adversarial cases only.
- `tests/test_task27_bounded_public_history_feasibility_authority_contract.py`:
  structural and semantic acceptance.
- `docs/evidence/task27/a0a4_bounded_public_history_feasibility_authority_acceptance_v1.json`:
  exact artifacts, test counts and zero-side-effect receipt.

The design and implementation plan live under `docs/superpowers/` and are
not a project Source, Catalog asset or authority record.

## Validation strategy

Tests use only synthetic packets. They must demonstrate one complete review
packet can become `READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW` while keeping
provider authority false, and that every fail-closed condition above is
rejected. The focused test is the implementation loop. The tracked-only full
delivery gate is run once for the exact committed candidate before push.

## Authority, safety and rollback

This atom allows only tracked local documents/configuration/schema/test/receipt
writes, tests, normal Git delivery and CI read-back under the repository's
standing autonomy. It performs zero provider/API/RPC/WSS calls, uses no
credentials, creates no wallet or signer, reads no R2/R3 values, retains no
external raw data and spends no money.

Rollback is an ordinary revert of the isolated branch before merge. If the
design proves too restrictive or incomplete, the allowed result is
`REDESIGN`; no external request is made to test the ambiguity away.

## Out of scope

The atom does not activate Project Sources, resolve the cloud/local product
surface split, collect public OHLCV data, establish source availability,
build a data pipeline, create a strategy, or alter the owner-canary route.
