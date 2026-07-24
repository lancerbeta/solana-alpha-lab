# Provider smoke runtime contract v1 — TASK-07 Atom 2

## Status and purpose

This contract defines the offline runtime boundary for the frozen TASK-01
provider smoke design. It does not authorize or perform a provider, API, RPC or
WSS request. It compiles the accepted design into one deterministic plan,
materializes only explicitly produced dynamic bindings, enforces request and
response safety, and prepares TASK-06 raw envelopes for later storage.

The frozen source remains:

`docs/evidence/pre_git/task01/provider_smoke_spec_v1.yaml`

Its exact SHA-256 is:

`a42c8a20dc31101ce134e277e1a612539f7161411ea8261bb109e5cc64d24ddc`

TASK-07 adds a runtime overlay. It does not rewrite historical TASK-01
evidence.

## Fixed execution inventory

The compiler must produce exactly:

- 34 cases;
- 35 planned attempts because `H12` has two planned protocol steps;
- hard attempt cap 50 with five attempts retained as stop headroom;
- concurrency 1;
- zero retries;
- zero paid requests and cash cap USD 0;
- maximum 2,000,000 response bytes per attempt;
- maximum 20,000,000 response bytes per run;
- one WSS connection, open for at most 10 seconds and one data message.

Unknown, duplicate, omitted or reordered cases fail compilation. A second
execution of a planned attempt is a retry and fails closed.

## Runtime overlay frozen by the TASK-07 Entry Gate

Official product contracts were rechecked at
`2026-07-24T03:42:09.018Z`. The overlay is deliberately smaller than a
production provider configuration.

| Case provider | Runtime group | Account/auth state | Minimum interval | Additional cap |
|---|---|---|---:|---|
| `HELIUS_RPC` | `HELIUS` | local API key required later | 0.2 s | combined run credit cap 25 |
| `HELIUS_WSS` | `HELIUS` | local API key required later | 0.2 s | one bounded connection |
| `SOLANA_TRACKER_DATA` | `SOLANA_TRACKER` | local `x-api-key` required later | 0.4 s | free-plan only |
| `JUPITER_SWAP` | `JUPITER` | keyless | 2.2 s | quote-only `/swap/v2/order` |
| `RAPTOR_HOSTED` | `RAPTOR` | keyless contract must still be observed | 1.0 s | comparator only |

The module contains no HTTP or WSS client. `network_authorized=False` is the
default, and even `True` is only a local runtime guard input; it is not
authority. A later Work-approved external-action atom must still bind the
transport, credentials, exact request inventory and output directory.

## Deterministic dependencies

Frozen public constants are loaded from `safe_samples`. Dynamic values must
come from their declared producer:

- `RAPTOR_RECENT_SIGNATURE` from `H08`;
- `RECENT_PUMP_MINT` from `ST03`;
- `RECENT_PUMP_DECIMALS` from `ST06`;
- `RECENT_PUMP_SELL_AMOUNT_ATOMIC` derived only after validated decimals as
  `max(1, 10 ** decimals)`.

No dynamic value may be guessed, fetched during compilation, read from a wallet
or backdated. Missing, malformed or out-of-order bindings stop materialization.

## Request safety

Only `GET` and `POST_JSON_RPC_READ_ONLY` are valid method classes. Request
templates are scanned recursively. The forbidden fields from the frozen design
remain forbidden, including taker/payer/receiver, fee or referral accounts,
transaction bytes, signer material and priority/tip overrides.

The runtime also rejects:

- unplanned cases or attempts;
- undeclared providers;
- absolute provider URLs in persisted request identity;
- credentials in request templates or durable evidence;
- rate-limit probing, retries or concurrency greater than one;
- account, webhook, payment, transaction build/simulate/sign/send or swap
  execution paths.

## Response safety

Every response is size-checked before redaction or storage.

For quote-only cases:

- `transaction` absent or `null` is allowed;
- an empty transaction string is allowed only with a non-empty typed
  `errorCode`;
- any non-empty transaction or signed-transaction payload stops the run;
- payment recipient, payment signature, x402 or payment-challenge material
  stops the run.

Every success, timeout, authentication failure, provider failure, rate limit,
no-route, malformed payload and prohibited payload remains a typed observation.
Provider failure is never converted to market no-route, and missing is never
converted to zero.

Payloads that pass the safety gate are processed through TASK-06
`canonical_redacted_bytes`. Durable raw-event preparation uses TASK-06
`build_raw_api_event`; therefore request identity, content hash, revision,
four-time/availability fields and redaction version remain governed by the
accepted raw-storage contract.

## Pacing and run caps

The run guard is a deterministic state machine. It does not sleep or perform
I/O. Before an attempt it checks:

- explicit runtime network flag;
- planned attempt identity and no duplicate/retry;
- provider stop state;
- minimum interval from the previous start in the same runtime group;
- effective attempt ceiling of 45, preserving five attempts of headroom.

After an attempt it checks:

- non-negative response bytes and credits;
- per-attempt and total response-byte caps;
- cash remains exactly zero;
- combined Helius credits remain at or below 25;
- three consecutive failures for one provider group stop that provider.

## Atom 2 Definition of Done

Atom 2 is accepted only when:

1. the frozen source hash, 34-case inventory and 35-attempt order agree;
2. dynamic producer and derived-value rules fail closed;
3. network remains disabled by default and the module has no transport client;
4. method, field, transaction/payment and response-size gates pass adversarial
   tests;
5. pacing, attempt, byte, credit, cash and consecutive-failure caps pass;
6. TASK-06 redaction and raw-event construction are reused;
7. targeted and full repository validation pass;
8. the unstaged diff contains only the four Work-authorized Atom 2 files.

## Stop, rollback and authority

Any contract drift, unknown case, non-zero cash path, secret persistence,
transaction/payment path or cap breach yields `FAIL_REPAIR_REQUIRED`. No
provider call may be used to repair Atom 2.

Before staging or commit, rollback is deletion of the four new uncommitted
Atom 2 files. Staging, commit, push, accounts, credentials, provider calls,
storage allocation and Project Sources changes require separate authority.
