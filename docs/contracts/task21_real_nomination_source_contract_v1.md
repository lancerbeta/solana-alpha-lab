# TASK-21 real nomination source and Token-2022 replay contract v1.1

`T21-A6S_T1_TOKEN2022_REPLAY_AND_BACKUP_V1` repairs the overly narrow
legacy-only validation used by source atom
`T21-A6S_T1_SOURCE_RESELECTION_V1`. It replays the already retained DEX
Screener and Solana RPC responses. It makes no source, provider, API, RPC,
Jupiter or WSS request.

## Why replay is required

The source atom successfully captured 30 DEX Screener profiles and validated
23 Solana accounts in one ordered `getMultipleAccounts` response. One account
was owned by the legacy SPL Token Program and 22 by Token-2022. The
legacy-only implementation therefore froze one nomination instead of the
required three and did not establish a T1 anchor.

The retained 47,195-byte source partition and its private Drive copy both have
exact SHA-256
`b334eac617fefdfcd6b6f51e41697c7e1c56daff873b6a8587328c66dcfa759d`.
The source partition remains immutable. Replay creates a separate derived
partition.

## Mint validation

DEX Screener still contributes only `chainId` and `tokenAddress`. Marketing
text, links, icons, paid state, response order and market/route fields remain
sealed. Distinct Solana addresses are sorted by mint identity ascending.

An RPC account is eligible only when:

- its owner is the legacy SPL Token Program or Token-2022;
- it is non-executable and has at least 82 bytes of account space;
- a legacy account has exactly 82 bytes of account space;
- the retained 82-byte data slice has valid Mint authority and freeze
  authority `COption` tags;
- `is_initialized` equals one;
- decimals are between zero and thirty.

This joint check uses the common base Mint layout and the exact program owner.
It does not interpret an arbitrary Token-2022 token account through byte 44.
The first three valid mint accounts become the bounded T1 nominations.

## Availability and lineage

Replay does not backdate knowledge. Source capture times remain lineage only.
Every nomination receives `observed_at`, `first_reliable_available_at` and the
T1 anchor equal to replay completion time, when Token-2022 validation first
became executable and accepted. T1 closes exactly seven days later.

The derived partition copies the complete retained source observation,
including exact request/response bytes and capture timestamps, and references
the immutable source partition by local path, Drive ID, byte count and
SHA-256.

## Exact authority and backup

The atom permits:

- one exact old Drive raw read-back, already used to prove the retained
  partition;
- one local create-only derived partition;
- one new create-only Drive object;
- one metadata read-back and one inline raw read-back of that new object.

It permits zero source/API/RPC/Jupiter/WSS calls, zero retries, zero
credentials, cash, scheduler, wallet, signer, transaction, commit, push, PR,
merge, update, deletion or sharing action.

Acceptance requires three nomination events, zero admissions, a
content-addressed filename, exact remote name/parent/size/private-state and
remote raw SHA-256 equal to the local derived partition.

The next separately gated action is
`T21-A6S_T1_CLOSE_EVALUATION_AND_BOUNDED_PANEL_CAPTURE_V1`, no earlier than the
recorded T1 close. Until then there are no watchlist admissions, Jupiter
quotes, panels, trades, positions or background collection.
