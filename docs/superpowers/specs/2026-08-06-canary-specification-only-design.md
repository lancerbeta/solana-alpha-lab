# CANARY_SPECIFICATION_ONLY_V1 — Design

## Purpose and decision

This design prepares a versioned, offline specification for one possible future
technical micro-canary. Its only consumer is the goal owner before a separate
material canary decision. The specification turns the existing
OWNER_AUTHORITY_PACKET_BINDING_V1 safety contract into a concrete, reviewable
but still unexecuted preparation record.

The accepted cash-at-risk ceiling is USD 3.00. This design does not create or
connect a wallet, call a provider, obtain a quote, build/simulate/sign/send a
transaction, spend cash, read R3, calculate numeric NetReturn, or start
TASK-27.

## Chosen approach

Three approaches were considered:

1. Add a minimal tracked specification and use the existing offline
   owner-packet contract and evaluator. This is selected.
2. Reuse only the existing packet without a new specification. It leaves the
   future owner decision ambiguous and is rejected.
3. Build a generic encrypted canary manager. It adds an unnecessary execution
   platform and security surface and is rejected.

## Architecture

The repository will contain a small, versioned CANARY_SPECIFICATION_ONLY_V1
contract/configuration pair and deterministic static acceptance evidence. These
artifacts reference OWNER_AUTHORITY_PACKET_BINDING_V1 as the safety truth owner;
they do not replace its evaluator or create a second execution path.

Every real owner value remains absent from Git and Project Sources. The tracked
specification represents each future owner value as either OWNER_INPUT_REQUIRED
or OWNER_LOCAL_ONLY. A separate owner-local, ignored note may later contain a
technical-wallet alias and a local verification hash. Codex neither creates,
reads, requests nor records that file or the underlying public address.

The pre-existing `.gitignore` excludes `local/`, `private/` and `staging/`.
Those paths are not catalog assets and are never required inputs to validation.

## Data and state model

The specification has one allowed state:

`DRAFT_OWNER_INPUT_REQUIRED`

Its fixed fields are:

- flow: SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT;
- total cash-at-risk cap: 300 USD cents;
- technical wallet reference: OWNER_LOCAL_ONLY;
- token, program, route, proposed notional, separate fee cap, quote basis,
  expiry, monitoring reference, reconciliation reference, recovery procedure
  and exact approval phrase: OWNER_INPUT_REQUIRED;
- canary authority and TASK-27 authority: false;
- all external side-effect counters: zero.

The specification cannot become ready, quote-backed, signed, sent, settled or
profitable. A later task may evaluate a fresh, owner-supplied real-world
proposal only after a new exact owner authorization; it cannot reuse this
draft as authority.

## Validation and failure rules

Acceptance must deterministically reject:

- any real wallet address, signer material, seed, key, signature, quote,
  transaction or provider endpoint in tracked artifacts;
- any transition away from DRAFT_OWNER_INPUT_REQUIRED;
- a cash cap other than 300 cents;
- an authority flag other than false;
- a missing required owner-input label;
- any non-zero external side-effect counter;
- any statement that TASK-27 or execution is authorized.

The task reuses the existing owner-packet evaluator and its safety terms. A
small static test proves that the new contract/configuration/evidence preserve
those terms; no new Python execution component or dependency is warranted.

## Intended artifacts

- task brief and versioned contract;
- placeholder-only configuration;
- synthetic negative acceptance fixture and static test;
- offline acceptance and Factory Fit evidence;
- Catalog registration and generated navigation updates;
- an ignored owner-local note template, created only if the owner chooses to
  use it and never committed.

## Recovery and handoff

There is no external or financial rollback because the task makes no external
change. A malformed tracked draft fails validation and is repaired before any
commit. A user-local note remains owner-controlled; deleting or changing it
does not alter repository truth or create authority.

The only handoff after completion is a redacted owner decision: either keep
the draft unfilled, or explicitly request a separate future canary-authority
Entry Gate. Completion does not advance TASK-27.

## Scope boundaries

In scope: offline placeholders, deterministic validation, Catalog lineage and
owner-readable stop conditions.

Out of scope: real wallet identity, token selection, route selection, price or
quote collection, provider access, transaction lifecycle, reconciliation,
inventory, cash spending, alpha logic, numeric NetReturn and TASK-27.
