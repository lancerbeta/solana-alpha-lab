# TASK-21 bounded live shakedown contract v1

## Purpose

`T21-A5_BOUNDED_LIVE_SHAKEDOWN_V1` asks one narrow question: can the
provider-neutral TASK-21 collector complete one current, capped, recoverability-
guarded quote window without contract drift or unsafe persistence?

This is a transport and durability compatibility check. It is not the start of
the 30–45-day collection, a real TASK-21 watchlist admission, a forward dataset
partition, or evidence for or against the execution-capacity hypothesis.

## Technical-probe isolation

The shakedown reuses the exact mint and provenance already accepted in the
TASK-17A transport probe. It does not discover or rank a token and does not
carry the old member into the TASK-21 forward watchlist. The new live bytes are
stored only in the ignored `local/task21_collector/live_shakedown` namespace.
No outcome, ranking, PnL, fill, strategy or alpha claim is allowed.

This isolation prevents a plumbing test from silently selecting the first
research subject or contaminating the later effective sample.

## Frozen provider surface and caps

Official Jupiter documentation read back on 2026-07-30 still exposes
`GET https://api.jup.ag/swap/v1/quote`, while describing Metis Swap v1 as
superseded by Swap V2 and no longer actively maintained. Keyless access is
allowed at 0.5 requests per second.

One foreground window may make at most eight sequential quote requests:
USD 10/25/50/100 BUY and, only after an accepted BUY, an exact dependent
reverse SELL. The exact BUY output atomic amount becomes the SELL input.

- retries: 0;
- concurrency: 1;
- minimum interval: 2.2 seconds;
- request timeout: 20 seconds;
- wall time: 300 seconds;
- received bytes: 1 MiB;
- durable bytes: 5 MiB;
- modeled credits: at most 8; provider billing claim unavailable for keyless;
- API keys, accounts, credentials, cash, wallet/signer/transaction actions: 0;
- scheduler, deployment and background process: forbidden.

## Recovery and persistence

Before the first request, the wrapper verifies the exact A3 receipt, `PASS`,
`HEALTHY`, backup age no more than 24 hours, restore proof age no more than
seven days, disk reserve and an absent create-only output target. It performs
no Google Drive operation in A5 and makes no claim that the new shakedown bytes
have themselves been backed up.

The accepted TASK-10 HTTPS transport retains the exact host/path, rejects
redirects, paces calls and caps responses. The accepted TASK-17A single-window
runner preserves raw and normalized evidence plus content-addressed manifests.

## Stop and authority

Local contract code and offline tests are covered by repository standing
autonomy. The first live request additionally requires the exact phrase
`T21-A5_BOUNDED_LIVE_SHAKEDOWN_V1` and explicit authority for:

- at most eight provider/API/RPC/WSS calls;
- one create-only local live-evidence window, at most 5 MiB.

The authority does not include credentials, Drive, purchase, real admissions,
forward dataset writes, scheduler, deployment, commit, push, PR, merge, wallet,
signer, transaction or destructive actions.

Authentication requirements, endpoint/schema drift, stale recovery, output
collision, cap exhaustion, redirect, transaction payload or any broader
authority requirement stops the run. There is no fallback host, retry or
automatic transition to `T21-A6_SUSTAINED_FORWARD_COLLECTION_AND_MONITORING_V1`.
