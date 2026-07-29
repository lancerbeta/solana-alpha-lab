---
contract_id: CONTRACT-T18-NARROW-DATA-QUALITY-001
contract_version: "1.0"
task_id: TASK-18
atom_id: T18-A2_FROZEN_NARROW_QUALITY_CONTRACT_V1
status: FROZEN_OFFLINE_CONTRACT
as_of: "2026-07-29"
hypothesis_version_id: HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1
provider_calls_in_atom: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# TASK-18 narrow data-quality contract v1

## 1. Owner decision and frozen estimand

The read-only Entry Gate returned `START_AS_WRITTEN`.

TASK-18 answers one decision:

```text
can the exact TASK-17A raw evidence support a trustworthy replay of the
one-member, three-window, quote-only size-curvature estimand
→ FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND
→ FIT_WITH_LIMITATIONS
→ NOT_FIT
→ EVIDENCE_UNAVAILABLE
```

The accepted estimand contains `T17A-WINDOW-01`, `T17A-WINDOW-03` and
`T17A-WINDOW-04-REPAIR-01`: 24 provider calls and 12 complete BUY/reverse-SELL
quote pairs. `T17A-WINDOW-02` and its eight calls remain immutable audit
evidence but stay excluded because the frozen trigger separation missed the
minimum by exactly 0.007854 seconds.

TASK-18 audits all 32 attempts. It cannot reclassify the excluded window,
expand the watchlist, turn quotes into fills or generalize beyond the frozen
member and windows.

## 2. Frozen inputs

Tracked inputs:

- TASK-17A audit:
  `docs/evidence/task17a/execution_capacity_quote_panel_audit_v1.json`,
  SHA-256
  `15c9ba7641c15c5511b308485cc230d3bff977f6529c6b86019673e91ee8a0a2`;
- TASK-17A panel contract:
  `tests/fixtures/task17a/bounded_execution_capacity_quote_panel_contract_v1.json`,
  SHA-256
  `ac7a191f4a5888681fa2b90ea33261271d0d7d4a44c81653dbfc6d902fa6871f`;
- accepted repository base:
  `67fdb73127cd837174e9e20a057c413928c3628a`, tree
  `d74d3fa8e32192a492576938332832228fa5d7ce`;
- Catalog checkpoint: `0.22.0 / 303 / 4 / 4 / 8`.

The raw inventory has two logical roots, four window directories, 12 files,
32 JSONL attempts and 179,208 stored bytes. Exact relative paths, byte counts,
row counts and SHA-256 values are frozen in
`tests/fixtures/task18/narrow_data_quality_contract_v1.json`.

Raw bytes stay outside Git and are immutable inputs. Missing bytes are not
regenerated, fetched, repaired, copied from another provider or inferred from
the tracked aggregate.

## 3. Fail-closed evidence availability

Before evaluating quality, the auditor must resolve every frozen file from the
repository workspace and verify its exact size and SHA-256.

Return `EVIDENCE_UNAVAILABLE` immediately when any required file:

- is missing, unreadable or outside the frozen relative root;
- differs in bytes, size or SHA-256;
- fails JSON/JSONL parsing;
- contains a different number of attempts than frozen;
- cannot be linked to its manifest and receipt.

The tracked TASK-17A aggregate proves historical identity, not current raw
availability. Aggregate values cannot substitute for missing raw bytes.

## 4. Attempt completeness and stable identity

Each of the four windows must contain exactly eight attempted provider calls.
The accepted set must contain exactly 24 calls; the retained excluded set must
contain exactly eight; the full audit denominator is exactly 32.

The stable composite attempt identity is:

```text
hypothesis_version_id
+ watchlist_id
+ watchlist_version
+ window_id
+ member_id
+ call_ordinal
+ request_hash
+ idempotency_key
```

Every component is required and the composite must be unique across all 32
rows. Each row must also bind a unique `quote_attempt.quote_attempt_id` and
`raw_event.raw_event_id`, and its top-level raw-content hash must reconcile
with the nested raw-event content hash.

Missing is never zero. Duplicate identity with equal bytes is still a
duplicate attempt; duplicate identity with different bytes is an observed
revision/overwrite conflict.

## 5. Point-in-time and latency rules

For every attempt, the following ordering is mandatory:

```text
requested_at
<= response_at
<= first_reliable_available_at
<= available_to_strategy_at
<= ingested_at
```

The same order must hold in both the top-level envelope and the nested
`quote_attempt`/`raw_event` records where the fields exist. Backfilling an
earlier availability timestamp is forbidden.

`latency_ms` and `quote_attempt.provider_latency_ms` must match
`response_at - requested_at` within 1 millisecond. Negative latency,
availability lag or ingest lag is a hard failure.

Within a window, consecutive requests must preserve the frozen 2.2-second
pacing floor. Accepted windows must preserve at least 1,800 seconds between
their frozen triggers. The excluded window remains excluded; no post-hoc
tolerance or rescheduling is allowed.

## 6. Provider, response and route consistency

Every row must preserve:

- schema `solana_alpha_lab.task17a_quote_panel_raw` version `1.0`;
- provider `JUPITER_METIS`;
- provider and endpoint version `legacy_metis_v1_quote`;
- response status and terminal class as typed fields;
- route ID, route count and context slot for `QUOTE_AVAILABLE`;
- null error class only when the terminal class is successful;
- exact atomic input/output amounts and side semantics from the frozen panel.

HTTP, provider, timeout, invalid-response and no-route states must remain
distinct. A typed failure cannot be coerced to `NO_ROUTE`, zero output or a
successful quote. A dependent SELL that was not attempted cannot be counted as
a provider call.

## 7. Byte, revision and retention checks

For each window:

- manifest file identities must match the physical files;
- receipt call counts and terminal counts must reconcile with JSONL rows;
- received bytes and stored bytes must reconcile with the TASK-17A audit;
- the original per-window and total call/byte caps must remain satisfied.

The nested `quote_attempt` and `raw_event` revision fields must be present.
The expected first revision is `revision_number = 1` with `revision_of = null`.
Any conflicting later revision, duplicate identity with changed content or
unsealed file replacement is a hard quality failure.

Current local availability proves neither durable backup nor successful
restore. Therefore:

- `local_retention_available = true` may support a bounded replay;
- absent backup inventory or restore evidence is a declared limitation;
- no auditor may claim overwrite prevention merely because current hashes
  match;
- no file is deleted, moved, normalized or rewritten by TASK-18.

## 8. Verdict precedence

Verdicts are evaluated in this order:

1. `EVIDENCE_UNAVAILABLE` — any frozen raw/manifest/receipt byte is missing,
   unreadable, unparseable or hash/size/row-count mismatched.
2. `NOT_FIT` — evidence is available but a hard completeness, identity, PIT,
   latency, pacing, provider/schema, typed-failure, byte-cap, revision or
   accepted/excluded-membership invariant fails.
3. `FIT_WITH_LIMITATIONS` — all hard invariants pass and the narrow replay is
   reconstructable, but backup/restore, overwrite prevention or another
   explicitly enumerated non-critical durability property is unproven.
4. `FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND` — all hard invariants pass and no
   declared limitation remains.

The verdict cannot depend on whether the hypothesis result is attractive.
There is no majority vote and no silent downgrade of failed checks to warnings.

## 9. Reuse and Catalog boundary

TASK-18 uses `ADOPT → WRAP → BUILD`:

- `ADOPT` existing PIT and identity semantics;
- `WRAP` the TASK-17A contract, audit and raw envelopes without changing them;
- `BUILD` only a thin task-specific offline auditor in A3;
- no fork, dependency adoption or general data-quality framework.

A2 creates only the contract, fixture and targeted contract tests. Catalog
registration and generated navigation are deferred to
`T18-A4_CATALOG_REPOSITORY_FINALIZATION_V1`; this deferral does not permit
TASK-18 to become DONE without that transaction.

## 10. Authority, non-claims and next boundary

`T18-A2_FROZEN_NARROW_QUALITY_CONTRACT_V1` is `LOCAL_WRITE_ONLY`.
It authorizes no provider/API/RPC/WSS call, network fallback, collection,
raw-data write, credential, account, dependency, purchase, deployment,
wallet, signer, transaction, signal, strategy, position, fill, PnL,
NetReturn, alpha or production-readiness claim.

The next atom is `T18-A3_DETERMINISTIC_OFFLINE_QUALITY_AUDIT_V1`. It may read
the frozen raw files and create task-specific code, audit evidence and tests,
but it remains offline and requires its own explicit continuation.
