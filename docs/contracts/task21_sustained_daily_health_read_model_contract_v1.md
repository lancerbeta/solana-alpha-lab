# TASK-21 sustained collection daily health read model contract v1

`T21-P6_SUSTAINED_COLLECTION_DAILY_HEALTH_READ_MODEL_V1` prepares the daily
owner view required by TASK-21 without starting or impersonating the future
30–45-day collection. The accepted result is an offline projection over a
synthetic sustained-collection state receipt.

## Product decision

The view answers one question: **may the frozen collection continue, or what
exactly must the owner do first?** It reports operational evidence only:

- terminal coverage, explicit gaps and unaccounted due panels;
- age of the last collection event;
- provider requests/credits, response/stored/dataset bytes and cash against
  frozen caps;
- backup and restore-proof age;
- retained incidents;
- one fail-closed operating state and one exact owner action.

It never owns collection, recovery or budget truth. It consumes their receipts
and remains replaceable by a future web/Owner Pulse projection over the same
contract.

## Input and missingness

The synthetic daily envelope points to the tracked TASK-21 sustained offline
acceptance receipt and adds only observation-time metadata that the older
receipt does not contain: `observed_at_utc`, `last_collection_event_at_utc`,
expected terminal panels to date and exact retained gap/incident IDs.

`missing != 0`. A due panel that is neither complete nor explicitly missed is
reported as unaccounted and blocks new windows. Every missed panel requires one
exact gap ID. Future timestamps, duplicate IDs, inconsistent recovery health,
non-zero synthetic side effects and outcome fields fail closed.

## Decision precedence

The projection uses one deterministic priority:

1. cap breach or unhealthy recovery → `SAFE_STOP`;
2. open incident → `DEGRADED_NO_NEW_WINDOWS`;
3. stale collection → `DEGRADED_NO_NEW_WINDOWS`;
4. unaccounted due panel → `DEGRADED_NO_NEW_WINDOWS`;
5. day-45 stop → `COLLECTION_STOPPED`;
6. retained gap → `DEGRADED_CONTINUE_NO_BACKFILL`;
7. sufficient day-30 evidence → `REVIEW_REQUIRED`, with separate A7 authority;
8. cap warning → `WATCH_BUDGET`;
9. otherwise → `HEALTHY`.

The read model never repairs, backfills, starts, freezes or extends collection.
Its action is guidance; it grants no runtime authority.

## Owner output

Canonical JSON preserves exact source hashes, calculations and reason codes.
The default CLI renders a compact Russian view with an explicit
`OFFLINE SYNTHETIC — НЕ LIVE-МОНИТОРИНГ` banner, collection day/lifecycle,
coverage, freshness, quota/storage, recovery, incidents and the exact owner
action.

## Scope and non-actions

This atom changes only its seven named local files. It does not modify H24
configuration, `control/active_time_gates.json`, raw evidence, the sustained
collector or Catalog. It performs zero network/provider/API/RPC/WSS/Drive
calls, collection actions, raw/dataset writes, cash spend, scheduler work,
credential use, wallet/signer/transaction actions, commit, push, PR or merge.

Catalog registration is intentionally deferred to TASK-21 A7. Binding this
projection to the common Owner Pulse is a future trigger: the first accepted
real sustained daily receipt. Until then no live-health claim is permitted.
