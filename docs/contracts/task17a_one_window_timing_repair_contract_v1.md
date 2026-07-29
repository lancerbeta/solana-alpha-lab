---
contract_id: CONTRACT-T17A-ONE-WINDOW-TIMING-REPAIR-001
contract_version: "1.0"
task_id: TASK-17A
atom_id: T17A-A3R_ONE_WINDOW_TIMING_REPAIR_V1
status: FROZEN_OFFLINE_REPAIR_CONTRACT
as_of: "2026-07-29"
cash_cap_usd: 0
provider_calls_max: 8
contains_secrets: false
---

# TASK-17A one-window timing repair contract v1

## Defect

The original A3 panel produced three complete eight-call windows, but the
persisted UTC trigger separation between `T17A-WINDOW-01` and
`T17A-WINDOW-02` is `1799.992146` seconds. This is `0.007854` seconds below
the frozen `1800`-second minimum. The runner paced with a monotonic clock
without a wall-clock safety margin. A4 therefore fails closed rather than
changing the rule after observing quotes.

## Minimal repair

Retain immutable `T17A-WINDOW-01` and `T17A-WINDOW-03`. Exclude
`T17A-WINDOW-02` from the accepted matched-window estimand while retaining it
as audit evidence. Collect exactly one replacement window named
`T17A-WINDOW-04-REPAIR-01` under a new immutable logical root.

The replacement reuses the same hypothesis version, watchlist version,
member, mint, provider/version, four USD notionals, dependent exact
reverse-sell rule, sequential pacing, typed failures and zero-effect
boundaries. It does not add a member, token, provider, notional, retry,
parallelism, credential, account, paid quota or trading action.

The first replacement request must be at least `1801` wall-clock seconds after
the persisted `T17A-WINDOW-03` trigger. The extra second is a safety margin,
not part of the estimand.

## Caps and authority

- provider calls: maximum `8`;
- concurrency: `1`;
- retries: `0`;
- timeout: `20` seconds per request;
- received bytes: maximum `1 MiB`;
- durable bytes: maximum `5 MiB`;
- API keys/accounts/cash: `0`;
- wallet/signer/transaction actions: `0`;
- scheduler/background process: forbidden;
- raw write: only the new ignored repair root;
- commit/push/PR/merge: not authorized by this external atom.

The exact runtime phrase is
`T17A-A3R_ONE_WINDOW_TIMING_REPAIR_V1`. It requires a separate owner gate.

After the replacement, A4 may accept only the ordered window set
`T17A-WINDOW-01`, `T17A-WINDOW-03`, `T17A-WINDOW-04-REPAIR-01` if all
identities, hashes, timing, request pairs and caps pass. Otherwise it retains
an honest early close. No post-hoc tolerance is allowed.
