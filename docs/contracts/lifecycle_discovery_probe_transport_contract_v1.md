# Lifecycle discovery probe transport contract v1.1 — TASK-08 Atoms 4–5U

## Status and authority

T08-A4 froze and tested the transport boundary offline. T08-A5 binds that
boundary to concrete no-redirect/no-retry adapters and the TASK-06 immutable
raw-envelope/Parquet store, then permits one bounded external probe after local
dashboard read-back and hidden credential input.

The first T08-A5 run reached 512 buffered evidence records, then failed the
combined received-plus-stored byte gate while encoding the uncompressed
TASK-06 Parquet partition. No raw partition survived the writer rollback.
T08-A5R repairs this as an admission-control defect without another provider
call or a larger budget.

The bounded T08-A5R replacement run then retained and finalized all three
attempted Tracker records, but its unparameterized opening snapshots exhausted
the 900,000-byte admission cap before Helius. T08-A5S repairs that source-shape
defect offline: the probe uses the provider-documented combined overview with
an exact per-category limit, gives each Tracker response a smaller local cap,
and treats a retained Tracker failure as an auxiliary audit gap rather than a
reason to skip the primary Helius spine.

The one approved T08-A5S probe
`run=t08a5-20260725T075056Z` finalized a complete 15-record partition with
59,994 stored bytes, zero omitted records, zero retries and zero cash spend.
It retained one oversized Tracker response, one Helius acknowledgement and
thirteen Helius notifications. Twelve notifications were structurally
complete; the thirteenth ended with the exact provider marker
`Log truncated`. The old parser classified its residual invocation stack as
`program_invocation_unclosed` and stopped after durable finalization.

T08-A5T repairs only that offline classification and the stopped-run usage
receipt. It performs no provider call and does not mutate the existing raw
run. The approved T08-A5S external authority is consumed; another execution
requires a new explicit external-action authorization.

T08-A5U repairs a second offline defect before any new probe: the WSS adapter
previously buffered only frame bodies, so the runner assigned `observed_at`
later while draining that buffer. This preserved body order but could collapse
or distort the actual frame-receipt timeline. Contract version 1.1 stamps the
acknowledgement and every notification immediately after the corresponding
`recv` returns, carries those timestamps through the closed capture and uses
them as raw-envelope `observed_at`. The existing contract-1.0 raw runs remain
immutable and their WSS `observed_at` values are not retroactively repaired.

The exact non-secret tripwire is
`TASK08_A5_CHEAPEST_PROBE_EXTERNAL_ACCOUNT_API_RPC_WSS_RAW_WRITE`. It is a
code guard, not independent authority. The approved T08-A5 envelope is one
local run with `LOCAL_WRITE (runtime + bounded data/raw)` and
`EXTERNAL_ACCOUNT_API_RPC_WSS`.

This atom excludes dependency changes, Catalog/status changes, staging,
commit, push, provider settings, purchase, deployment, transaction
construction, simulation, signing, sending, wallet and real-money actions.
Cash remains USD 0.

## Result

The accepted A2 discovery plan and A3 Pump event decoder become one sequential
probe:

1. an opening Solana Tracker combined overview with an exact category limit;
2. one non-reconnecting Helius WebSocket `logsSubscribe` capture;
3. a post-capture Solana Tracker combined overview with the same limit;
4. at most 20 read-only Helius `getTransaction` follow-ups, only for a
   successful notification containing an attributed pinned Pump
   `CreateEvent`;
5. controlled finalization of all accepted success or failure evidence into
   one TASK-06-compatible immutable partition;
6. sanitized receipts containing counts and hashes, never bodies, secrets,
   full URLs or absolute paths.

The default launcher remains offline. `--execute` first validates the frozen
fixtures, exact authority phrase and provider-dashboard headroom; only then
does it request both API keys through hidden local input and create a unique
run directory.

## Exact endpoints and methods

### Helius primary chain spine

- host: `mainnet.helius-rpc.com`;
- WSS scheme/path: `wss`, `/`;
- RPC scheme/path: `https`, `/`;
- authentication: `api-key` query value, memory only;
- one `logsSubscribe` request;
- filter:
  `{"mentions":["6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"]}`;
- commitment: `confirmed`;
- capture window: at most 540 seconds inside the 600-second total cap;
- no proxy, redirect, reconnect or retry;
- follow-up method: `getTransaction`;
- follow-up encoding: `json`;
- follow-up commitment: `confirmed`;
- maximum supported transaction version: `0`.

Current Helius documentation groups standard Solana WebSocket methods under
its LaserStream WebSocket documentation, while retaining the same endpoint
and `logsSubscribe` method. This naming drift does not change the frozen
request semantics.

### Solana Tracker fallback/audit

- scheme/host: `https`, `data.solanatracker.io`;
- method: `GET`;
- header authentication: `x-api-key`, memory only;
- exact path: `/tokens/multi/all`;
- exact query: `limit=10`;
- the limit applies to each returned category: `latest`, `graduating` and
  `graduated`;
- two phases: `OPEN`, then `CLOSE`;
- two planned requests, below the unchanged hard cap of eight;
- maximum accepted body per Tracker response: 200,000 bytes, plus one
  measured sentinel byte when the response is larger;
- maximum pace: one request per second;
- no redirect and no retry.

The combined overview is the transport-specific bounded representation of the
three lifecycle views already named by the A2 discovery contract. It does not
change their audit semantics or promote Solana Tracker to cohort truth.
Official source as of 2026-07-25:
`https://docs.solanatracker.io/data-api/tokens/get-token-overview`.

The provider currently publishes conflicting free-plan monthly totals on its
documentation and product page. The runtime therefore trusts neither number:
it requires a local dashboard read-back proving at least eight requests remain.
Solana Tracker never owns cohort membership; it measures overlap, lag and
disagreement only.

A Tracker timeout, redirect, oversize response, non-200 status or overview
schema/limit drift is retained with its typed `RawResponseStatus` and counted
as `solana_tracker_failures`. It does not block the Helius capture or eligible
Helius follow-ups. Endpoint, authentication or durable-evidence invariant
drift still fails closed.

## Notification and event boundary

The acknowledgement must be JSON-RPC 2.0, match the exact request ID and
contain one non-negative integer subscription ID. Every frame must be the
matching `logsNotification`, with a non-negative slot, base58 signature,
explicit transaction success/error and ordered log strings.

Every non-empty acknowledgement and notification also carries one UTC-aware
receive timestamp captured at the transport boundary. Timestamp count must
match frame count exactly, and acknowledgement/notification timestamps must be
non-decreasing in receive order. A missing, naive, non-UTC, extra, reordered or
unpaired timestamp is transport-contract drift and stops before durable write.
Later parsing, redaction or Parquet finalization may not replace these values
with processing time.

Pump `Program data:` is attributed through the Solana invocation stack.
Missing, reordered, unclosed or mismatched frames stop. Data emitted while
another program is on top of the stack cannot become a Pump event.

One exact `Log truncated` line is recognized only when it is the final log
line and occurs exactly once. The preceding log prefix still undergoes strict
invocation, attribution and pinned-layout validation, but a residual stack at
that terminal marker is typed as incomplete provider evidence rather than
protocol drift. The notification is retained as
`INVALID_RESPONSE/program_logs_truncated`, increments
`truncated_notifications`, produces no decoded or unsupported event, cannot
become a follow-up candidate, and does not stop later buffered notifications
from being processed. A non-terminal or duplicate marker stops as
`program_log_truncation_marker_invalid`; an unclosed stack without the exact
marker remains `program_invocation_unclosed`.

Only the four A3-pinned layouts may decode: `CreateEvent`, `TradeEvent`,
`CompleteEvent` and `CompletePumpAmmMigrationEvent`. A known discriminator
with an invalid layout is schema drift. Unknown Pump program data is retained
and counted but cannot create lifecycle state. Failed transactions are
retained and never promoted.

Duplicate notifications remain evidence. Follow-ups are limited to successful
`CreateEvent` candidates, deduplicated by signature in first-observed order.
More than 20 candidates stops before excess calls. With no accepted
`CreateEvent`, the result is `NOT_TESTABLE_IN_WINDOW`; it authorizes neither a
retry nor the 24-hour pilot.

## Concrete transport boundary

The HTTP adapter uses the standard library with redirects disabled, a
1.5-second per-request timeout, bounded body reads and no retry. It returns
typed terminal classes without exposing provider bodies or targets in errors.

The WebSocket adapter uses the already locked `websockets` dependency. It
opens exactly one connection, disables proxying and compression, limits each
frame to 100,000 bytes, keeps the connection alive with protocol pings, never
reconnects and closes in `finally`. It stops on elapsed, notification or
conservative stream guard. Its effective stream allowance is dynamically
reduced by bytes already received from the opening Tracker snapshot and
reserves 200,001 admission bytes for the post-capture Tracker attempt.

Frame receipt time is recorded immediately after synchronous `recv` returns
and before UTF-8 conversion, notification parsing or buffer insertion. The
adapter returns bodies and timestamps as one validated closed capture. The
runner persists the captured timestamp even if later parsing classifies that
frame as invalid or truncated.

Primary Helius HTTP errors, timeouts, redirects, oversize responses, WSS
termination and schema drift are retained with a TASK-06
`RawResponseStatus` before the run stops. A controlled stop attempts to
finalize already accepted evidence. Tracker failures follow the narrower
auxiliary-gap rule above. There is no retry or fallback escalation.

After a controlled stop, the runner also exposes one sanitized usage receipt
after the finalization attempt. It distinguishes actual HTTP bytes, all bytes
already captured by the WSS adapter, evidence bytes admitted to the sink and
final stored bytes. It includes connection, subscription, notification,
follow-up, Tracker, retry, credit, elapsed-time and cash counters plus typed
stop/finalization error classes. It contains no body, credential, endpoint,
full URL or absolute path. This closes the earlier observability gap where
buffered WSS bytes and modeled Helius credits disappeared when parsing stopped
before a success summary was returned.

## Durable evidence boundary

One run writes only beneath:

```text
data/raw/task08_lifecycle_discovery_probe_v1/
  run=t08a5-YYYYMMDDTHHMMSSZ/
    partitions/probe.parquet
    receipts/probe.manifest.json
    receipts/probe.receipt.json
```

The dataset identity is
`SMIAL_TASK08_LIFECYCLE_DISCOVERY_PROBE_RAW@1.0`. Provider bodies are passed
through the TASK-06 redacting raw-envelope builder with both explicit
credential values. The partition writer is immutable; an existing run ID
fails closed. Read-back verifies the exact partition before receipts publish.

Received bytes and final stored bytes share the same 5,000,000-byte budget.
A 65,536-byte reserve covers the two canonical JSON receipts. Receipts expose
only logical locations, run identity, counts, statuses, hashes and byte
totals—never secrets, response bodies or machine-specific paths.

T08-A5R admits at most 900,000 response bytes across all HTTP and WSS
operations. This is a strict sub-cap, not an expansion of the accepted outer
budget. HTTP bounded reads reserve one extra byte so an oversized response is
measured and classified without crossing the sub-cap. The WSS adapter receives
only the admission allowance remaining after the opening REST calls.

The admission proof reserves:

```text
900,000 received bytes
+ 2,700,000 redacted-body bytes (3x expansion shield)
+ 1,081,344 Parquet row bytes (528 x 2,048)
+ 65,536 Parquet container bytes
+ 65,536 manifest/receipt bytes
= 4,812,416 worst-case combined bytes
```

This leaves 187,584 bytes of safety inside the unchanged 5,000,000-byte cap.
The 528-row ceiling covers six Tracker responses, one WSS acknowledgement,
500 notifications, 20 follow-ups and one typed WSS terminal record.

If the full uncompressed TASK-06 Parquet partition cannot fit the remaining
combined-byte allowance, the sink deterministically halves the
first-observed event prefix until one immutable partition fits. The receipt
then records received, stored and omitted event counts plus the exact storage
error class, and the runner returns
`durable_evidence_partial_due_storage_budget`. This is explicit failure
evidence, not successful probe completion. If even one event cannot fit, only
the bounded failure receipt is written.

The raw output is ignored by Git. It is candidate probe evidence, not a
Catalog registration or canonical acceptance. Reconciliation is a later
authority boundary.

## Frozen caps

| Dimension | Hard cap / exact rule |
|---|---:|
| Total elapsed time | 600 seconds |
| WSS capture | 540 seconds |
| WSS connections / subscriptions | 1 / 1 |
| Notifications | 500 |
| Uncompressed WSS bytes | 1,000,000 |
| `getTransaction` follow-ups | 20 |
| Helius credits | 41 |
| Solana Tracker requests | 8; two planned |
| Received plus stored bytes | 5,000,000 |
| Admitted HTTP plus WSS response bytes | 900,000 |
| HTTP response body | 1,000,000 bytes and remaining total cap |
| Tracker overview response body | 200,000 bytes plus one sentinel |
| WSS frame | 100,000 bytes |
| Concurrency | exactly 1 |
| Retries / reconnects | 0 / 0 |
| Cash | USD 0 |

Helius credits retain the A2 formula:

```text
ceil(uncompressed_wss_bytes / 100,000) * 2
+ getTransaction_calls
+ WSS_connections
```

The external path requires dashboard read-back proving at least 41 Helius
credits and eight Solana Tracker requests remain. Lower headroom, missing
read-back or non-zero cash stops before credential input and the first request.

## Immediate stop conditions

- authority, fixture, access-headroom or credential validation failure;
- secret, full URL or absolute path entering durable metadata or a receipt;
- unexpected scheme, host, port, path, method, header set or query key;
- primary redirect, response-target drift, typed provider failure or
  malformed body;
- Tracker endpoint/query/authentication drift or failure to retain a typed
  auxiliary error;
- state-changing RPC method, transaction, webhook, payment or signer path;
- WebSocket acknowledgement, subscription, notification or invocation-stack
  drift;
- pinned event decode failure;
- any time, notification, byte, request, credit, concurrency, retry or cash
  breach;
- durable write or read-back mismatch.

## Definition of Done

T08-A5 implementation passes only when:

1. the exact two Helius methods and bounded Tracker overview bind;
2. concrete adapters enforce redirect/retry/reconnect/concurrency bounds;
3. request representations and receipts redact credentials and full URLs;
4. default launcher performs zero network, prompt and write activity;
5. the external launcher validates authority and dashboard headroom before
   hidden credential input or raw-directory creation;
6. mocked success and typed partial failures finalize to one verified
   TASK-06 partition and two sanitized receipts;
7. notification parsing, invocation attribution and event promotion remain
   strict;
8. the one approved live probe stays within every frozen cap;
9. targeted, full, security and file-hygiene validation passes;
10. only the four authorized A4/A5 managed files change, plus the ignored
    bounded raw run output.

T08-A5R additionally requires:

1. the 900,000-byte admission sub-cap to apply before durable finalization;
2. HTTP oversize accounting to include the sentinel byte actually read;
3. WSS allowance to subtract opening HTTP bytes;
4. a max-row, expanding-redaction pressure fixture to fit the unchanged
   5,000,000-byte combined cap with positive safety;
5. no network, credential prompt, quota use or mutation of the failed A5 raw
   receipt during repair validation.

T08-A5S additionally requires:

1. the exact Tracker request to bind `/tokens/multi/all?limit=10`;
2. the overview to contain only `latest`, `graduating` and `graduated`, with
   at most ten items in each category;
3. one opening and one post-capture Tracker request to replace six bulk
   requests without changing the hard request allowance;
4. each Tracker response to stop at 200,000 body bytes plus one sentinel;
5. a retained Tracker transport/schema/limit failure to increment the
   sanitized failure count without preventing the Helius WSS capture;
6. WSS admission to reserve capacity for the post-capture Tracker attempt;
7. no network, credential prompt, quota use or `data/raw` mutation during the
   A5S local repair.

T08-A5T additionally requires:

1. only one exact terminal `Log truncated` marker may relax the residual-stack
   check;
2. its full notification remains typed raw evidence, while every decoded,
   unsupported and follow-up output from that incomplete log is suppressed;
3. later buffered notifications continue through the unchanged strict parser;
4. non-terminal/duplicate truncation markers and unmarked stack drift still
   fail closed;
5. every controlled stop returns a sanitized usage receipt with WSS capture
   bytes and modeled Helius credits even when no success summary exists;
6. a read-only replay of the existing T08-A5S raw notification classifies it
   as truncated without promoting an event;
7. no network, credential prompt, quota use or `data/raw` mutation occurs
   during the A5T local repair.

T08-A5U additionally requires:

1. transport contract version 1.1 to distinguish corrected future runs from
   contract-1.0 raw evidence;
2. one UTC receive timestamp to be captured for every non-empty WSS
   acknowledgement and notification immediately after `recv`;
3. missing, extra, naive, non-UTC or decreasing timestamps to fail closed;
4. the runner to preserve frame receipt time through success, truncated and
   invalid-response evidence paths instead of substituting drain time;
5. deterministic buffering tests to prove distinct frame times survive later
   parsing and durable storage;
6. no network, credential prompt, quota use or `data/raw` mutation during the
   A5U local repair, and no rewrite of existing contract-1.0 raw runs.

Passing this implementation or one bounded capture does not authorize or prove
Catalog acceptance, lifecycle coverage, a 24-hour pilot, production SLA,
fillability, alpha or NetReturn.

## T08-A5U live evidence disposition

The one authorized transport-contract-1.1 run
`t08a5-20260725T084127Z` finalized 388 of 388 evidence records beneath the
ignored logical raw root. Its exact partition SHA-256 is
`079dc1401b4da3cf0e1d63d2b20210e017252f26d93c4dd2afd8af7d950fcb6a`.

The run passes the bounded transport, redaction, durability and budget
boundary. It does not pass lifecycle coverage:

- 385 Helius notifications arrived in seven seconds;
- 101 pinned Pump events decoded, but accepted `CreateEvent` count was zero;
- no follow-up candidate or RPC follow-up was created;
- the stream ended at the frozen `STREAM_GUARD`;
- both Solana Tracker observations remained
  `HTTP_ERROR/http_status_not_success:401`;
- actual usage was 15 modeled Helius credits, two Tracker requests, 600,292
  received bytes, 799,765 stored bytes, retries zero and cash spend USD 0.

The accepted classification is `NOT_TESTABLE_IN_WINDOW`. The Tracker failures
remain access-failure evidence, not empty results, zero, `NO_ROUTE` or
lifecycle observations. The run is an explicit coverage-blocker candidate;
neither retry nor a 24-hour pilot is authorized by this disposition.

Sanitized tracked evidence is frozen in:

- `tests/fixtures/task08/lifecycle_discovery_probe_live_evidence_v1.json`;
- `docs/evidence/task08/lifecycle_discovery_probe_execution_receipt_v1.json`;
- `docs/evidence/task08/lifecycle_discovery_probe_execution_summary_v1.md`.
