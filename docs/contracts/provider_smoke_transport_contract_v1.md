# TASK-07 provider smoke transport contract v1

## Purpose

This contract binds the accepted offline TASK-07 smoke plan to a transport
that can be exercised only by a later, separately authorized external-action
atom. Atom 4A creates and tests the boundary without contacting DNS, HTTP,
WebSocket, provider, RPC or API endpoints.

The transport consumes the exact plan compiled by
`provider_smoke_runtime_contract_v1.md`. It cannot add, omit, reorder or retry
an attempt. The frozen inventory remains:

- 34 cases and 35 attempts;
- concurrency one and zero retries;
- hard attempt cap 50 with five attempts retained as stop headroom;
- response cap 2,000,000 bytes per attempt and 20,000,000 bytes per run;
- combined Helius credit cap 25;
- cash cap USD 0.

## Authority and execution gate

Importing the module, constructing requests and running the command without
`--execute` are offline operations. They do not resolve hosts or open sockets.

Live execution requires all of the following:

1. a separate Work approval for
   `TASK07_A4B_EXTERNAL_ACCOUNT_API_RPC_WSS`;
2. the explicit `--execute` switch;
3. interactive entry of the same non-secret authority phrase;
4. hidden interactive entry of both provider keys;
5. a new, absent run directory below `data/raw/task07_provider_smoke_v1/`.

The phrase is a tripwire, not authority by itself. The human approval remains
the authority. A boolean, environment variable, command-line key, `.env` file
or stored endpoint cannot substitute for it.

The R5 repair adds a second, narrower tripwire
`TASK07_A4B_R6_RAPTOR_TAIL_EXTERNAL`. It can authorize only a child run
containing `R04#1` and `R05#1` after the parent prefix has passed the offline
recovery verifier. It cannot authorize the original 35-attempt runner,
Helius, Solana Tracker, Jupiter, WSS, retries or arbitrary attempt skipping.
The R5 local-write atom does not exercise this tripwire.

## Endpoint allowlist

Only the following exact public hosts and path families may be bound:

| Provider | Scheme / host | Allowed path |
|---|---|---|
| Helius RPC | `https://mainnet.helius-rpc.com` | `/` |
| Helius WSS | `wss://mainnet.helius-rpc.com` | `/` |
| Solana Tracker Data API | `https://data.solanatracker.io` | frozen relative path |
| Jupiter Swap v2 | `https://api.jup.ag` | `/swap/v2/order` |
| Raptor hosted beta | `https://raptor-beta.solanatracker.io` | `/health` or `/quote` |

Redirects, userinfo, fragments, non-TLS schemes, absolute paths from the
frozen file, additional hosts and additional request fields fail closed.
Transaction, execute, submit, send, wallet, signer, webhook, x402 and payment
paths remain prohibited.

## Credential boundary

The launcher reads `HELIUS_API_KEY` and `SOLANA_TRACKER_API_KEY` with a hidden
terminal prompt. Values exist only in process memory for the bounded run.
They are never accepted through command-line arguments, process environment,
files, fixtures, logs, exception text or chat.

Helius authentication is bound only to the in-memory `api-key` query value.
Solana Tracker authentication is bound only to the in-memory `x-api-key`
header. Safe request receipts contain the provider, case, attempt, method,
host, path, non-secret query key names and body hash; they never contain a
complete URL, request headers or query values.

Provider responses are passed through the TASK-06 redaction boundary with
both explicit key values before any durable write. A quote-only response with
transaction or payment material is rejected and only a sanitized failure
record may be retained.

Raptor and Jupiter remain keyless in this bounded plan. The exact Raptor tail
runner therefore has no credential input at all. Conversely, a Helius or
Solana Tracker request without its in-memory credential fails before binding;
keyless recovery cannot be widened into an authenticated-provider rerun.

## Provider-specific response shapes

The initial R4 observation established two Raptor-specific wire shapes:

- `R01 /health` returns the exact two-byte plaintext body `OK`;
- `R02` and `R03 /quote` return a JSON mapping whose output atomic amount is
  the digit string `amountOut`.

The classifier accepts plaintext only for the exact Raptor `R01` health case.
Whitespace variants and non-JSON bodies for any other case fail closed.
`amountOut` is accepted only for `RAPTOR_HOSTED`; Jupiter continues to require
one of its existing output-amount keys. A shared permissive alias set is
prohibited because it would hide provider schema drift.

## HTTP and WebSocket behavior

HTTP uses the Python standard library with redirects disabled, TLS-only
allowlisting, bounded timeouts and a `limit + 1` read used to detect oversized
responses. HTTP errors are retained without retry.

The only WebSocket flow is Helius `H12`. One connection performs exactly:

1. `accountSubscribe`;
2. at most one data notification within the ten-second open window;
3. `accountUnsubscribe` using the returned public subscription ID;
4. close.

The two protocol steps map to the two frozen attempts. No second connection,
reconnect or retry is allowed. The implementation uses the `websockets`
package already locked by the direct `solana==0.40.1` dependency; Atom 4A
does not change `pyproject.toml` or `uv.lock`.

## Durable output boundary for the later live atom

The future live runner writes only under the ignored raw root
`data/raw/task07_provider_smoke_v1/run=<run_id>/`.

Each completed attempt is persisted before the next attempt as:

- one immutable, budget-checked Parquet partition through the accepted
  TASK-06 writer;
- one immutable sanitized JSON receipt containing no response body or secret.

The run uses these local limits:

- maximum partition file: 3,000,000 bytes;
- maximum TASK-07 raw dataset: 32,000,000 bytes;
- minimum filesystem reserve: 1 GiB;
- forecast partition count: 35.

A partial run is evidence, not success. Existing bytes are never overwritten
or deleted automatically. Dataset-root reconciliation and tracked sanitized
fixtures belong to a later local-write atom.

## Stop and recovery

The runner stops without retry when any of these occurs:

- missing or malformed credential;
- authority phrase mismatch;
- unexpected host, path, method, query or request field;
- redirect, timeout, DNS/TLS error, authentication failure or rate limit;
- three consecutive failures in one provider group;
- response, total-byte, credit, cash, pacing or attempt cap breach;
- required dynamic binding cannot be extracted;
- malformed, transaction-bearing, payment-bearing or unredactable response;
- raw output collision, budget failure or immutable-write failure.

General recovery is diagnostic only: preserve the sanitized partial run,
revoke a key if exposure is suspected, and return the exact blocker. No
rerun, repair call, account change, paid upgrade or cleanup is implicit.

The sole bounded exception prepared by R5 is immutable-prefix Raptor-tail
recovery. Offline preparation must:

1. receive one explicit parent run ID, never discover a "latest" run;
2. verify the parent contains exactly the first 33 frozen attempts and is
   missing only `R04#1` and `R05#1`;
3. require exactly 33 Parquet partitions, 33 canonical manifests and 33
   canonical receipts, with no extra files;
4. verify every partition hash, row contract, receipt/body hash, provider,
   case, request identity and dynamic binding;
5. reclassify the immutable stored `R01`-`R03` bodies as `SUCCESS` under the
   repaired provider-specific classifier without changing their original
   receipts;
6. materialize both missing requests from verified `ST03` and `ST06` outputs;
   if redaction removed `token.decimals`, accept `pools[].decimals` only when
   every valid observed pool value agrees;
7. perform zero network calls, prompts, writes or credential reads.

A later separately authorized execution may create one new child run and make
only the two keyless Raptor GET requests in frozen order, concurrency one,
zero retries and USD 0 cash cost. The parent remains read-only. Any prefix,
inventory, hash, lineage, binding, authority-scope or request-scope mismatch
fails before the child run is eligible for execution.

## Atom 4A Definition of Done

Atom 4A passes only when:

1. the default launcher path performs zero prompt, write and network actions;
2. exact request binding and host/path allowlists pass;
3. secrets are absent from representations and safe receipts;
4. HTTP redirect, oversize, retry and unauthorized execution paths fail;
5. H12 is limited to one connection and the subscribe/unsubscribe sequence;
6. mocked 35-attempt orchestration preserves order, pacing and caps;
7. targeted, full, secret, Catalog and generated-view validation pass;
8. the change inventory is exactly the four Work-authorized Atom 4A files.

## Atom 4B-R5 repair checkpoint

R5 is accepted only when provider-specific classification, the exact
33-attempt immutable-prefix verifier, the two-attempt keyless runner boundary,
adversarial inventory tests, offline replay against the preserved R4 run and
the full repository validation pass. R5 itself permits no provider/API/RPC/WSS
call, raw write, credential read, staging, commit or push.
