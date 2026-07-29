---
contract_id: CONTRACT-T19-POINT-IN-TIME-REPLAY-001
contract_version: "1.0"
task_id: TASK-19
atom_id: T19-A2_FROZEN_POINT_IN_TIME_REPLAY_CONTRACT_V1
status: FROZEN_OFFLINE_CONTRACT
as_of: "2026-07-29"
hypothesis_version_id: HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1
provider_calls_in_atom: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# TASK-19 point-in-time replay and leakage contract v1

## 1. Owner decision and narrow scope

The TASK-19 read-only Entry Gate returned `START_AS_WRITTEN`.

TASK-19 answers one decision:

```text
can the exact TASK-18-accepted quote evidence reproduce the frozen
TASK-17A result using only rows eligible at literal decision cutoffs
without future-row leakage
→ REPLAY_SAFE
→ REPLAY_SAFE_WITH_LIMITATIONS
→ LEAKAGE_DETECTED
→ EVIDENCE_UNAVAILABLE
```

The replay remains limited to
`HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1`, one watchlist member,
three accepted windows, four BUY/reverse-SELL pairs per window and the
quote-only size-curvature estimand.

`T17A-WINDOW-02` remains excluded-retained. Its eight rows are required
evidence, but they cannot become eligible merely because their availability
timestamps precede the final replay cutoff.

## 2. Frozen inputs

The machine fixture binds:

- accepted repository main
  `7daa7702895f90844a488337dd74ddf26dbfa00b`, tree
  `43b4c493396114ff075723fc54496e3d5f920ed7`;
- Catalog `0.23.0 / 321 / 4 / 4 / 8`;
- TASK-17A contract and accepted quote-panel audit;
- TASK-18 quality contract, deterministic audit, content-addressed
  backup/restore receipt and Catalog/repository finalization receipt;
- the exact 12-file, 32-attempt, 179,208-byte raw inventory already frozen by
  TASK-18.

Raw bytes stay immutable and outside Git. The local raw inventory and local
content-addressed backup are currently available, but the replay must fail
closed if any required byte, size, hash, row count or JSON shape drifts.

No network or Google Drive read is required while exact local raw is
available. The tracked recovery receipt remains evidence, not a runtime data
source.

## 3. Literal decision cutoffs

Cutoffs use `FROZEN_LITERAL_NOT_RUNTIME_MAXIMUM`. Runtime code must not derive
or extend a cutoff from the latest row because an injected future row could
then move the boundary.

The three accepted window cutoffs are the exact last `ingested_at` values in
their frozen eight-row inventories:

| Window | `decision_at` |
|---|---|
| `T17A-WINDOW-01` | `2026-07-29T14:17:06.203260Z` |
| `T17A-WINDOW-03` | `2026-07-29T15:17:10.046218Z` |
| `T17A-WINDOW-04-REPAIR-01` | `2026-07-29T15:47:24.921906Z` |

The final evaluation cutoff is
`2026-07-29T15:47:24.921906Z`. The excluded-retained window has a frozen
audit cutoff of `2026-07-29T14:47:06.200169Z`, but no decision eligibility.

A row is eligible for one accepted window only when all three values are no
later than that window's literal cutoff:

```text
first_reliable_available_at
available_to_strategy_at
ingested_at
```

`event_time`, `requested_at` or `response_at` alone never grants eligibility.
A backfilled row with an old event/request time but a later reliable
availability or ingestion time is future evidence and must not affect the
earlier replay.

The source ordering invariant remains:

```text
requested_at
<= response_at
<= first_reliable_available_at
<= available_to_strategy_at
<= ingested_at
```

## 4. Membership before evaluation

Eligibility requires both:

1. exact membership in the frozen accepted-window set; and
2. all availability gates at or before the matching literal cutoff.

The accepted window order is:

```text
T17A-WINDOW-01
T17A-WINDOW-03
T17A-WINDOW-04-REPAIR-01
```

`T17A-WINDOW-02` remains excluded for the exact 0.007854-second trigger
separation shortfall. Availability cannot override membership. Post-hoc
tolerance, reclassification and unknown windows are forbidden.

Each accepted window must contain exactly eight eligible attempts. An
incomplete pair or any additional production row is evidence drift, not an
implicit partial replay.

## 5. Deterministic ordering and pairing

Input file order is not authority. After integrity and eligibility checks,
accepted rows are ordered by:

```text
frozen accepted-window rank
+ call_ordinal
+ quote_attempt.quote_attempt_id
+ raw_event.raw_event_id
+ request_hash
+ idempotency_key
```

Every identity component is mandatory. Duplicate equal bytes and duplicate
changed bytes both fail closed; silent deduplication is forbidden.

Within every accepted window, call ordinals map to notionals:

```text
1,2 → USD 10 BUY/reverse-SELL
3,4 → USD 25 BUY/reverse-SELL
5,6 → USD 50 BUY/reverse-SELL
7,8 → USD 100 BUY/reverse-SELL
```

The SELL input must equal the preceding BUY quoted output. Quote-only
round-trip cost is computed with exact integers and `Decimal`, then serialized
as a four-decimal string using `ROUND_HALF_EVEN`.

## 6. Frozen expected result

The replay must reproduce:

| Window | USD 10 | USD 25 | USD 50 | USD 100 | USD100−USD10 |
|---|---:|---:|---:|---:|---:|
| `T17A-WINDOW-01` | `345.2850` | `495.1112` | `734.1092` | `1174.2551` | `828.9701` |
| `T17A-WINDOW-03` | `348.2840` | `497.1640` | `735.6348` | `1181.6128` | `833.3288` |
| `T17A-WINDOW-04-REPAIR-01` | `348.8440` | `497.5428` | `737.8010` | `1181.4146` | `832.5706` |

Required aggregate:

- 24 eligible accepted rows;
- 8 excluded-retained rows;
- 12 complete quote pairs;
- 3/3 strictly increasing cost panels;
- median USD100-minus-USD10 delta `832.5706 bps`;
- result
  `SUPPORTED_WITHIN_ONE_MEMBER_THREE_WINDOWS_QUOTE_ONLY`;
- hypothesis state remains `PAUSED`;
- promotion remains unauthorized.

Deterministic output is UTF-8 JSON with sorted keys, compact separators and one
final LF. Repeated runs over identical bytes and contract must produce the same
semantic result and output SHA-256.

## 7. Adversarial leakage vectors

Synthetic vectors are permitted only in tests after the exact base inventory
passes integrity. They never become production evidence.

The implementation must prove:

1. a synthetic accepted-window row whose availability and ingestion are after
   the literal cutoff is excluded and cannot change the earlier output;
2. a row with an old event/request time but future reliable availability is
   excluded;
3. shuffled base input produces byte-identical deterministic output;
4. the excluded-retained window remains excluded even though its rows precede
   the final evaluation cutoff;
5. duplicate identity, changed content under the same identity, missing
   availability, impossible timestamp order and incomplete BUY/SELL pairs
   fail closed;
6. a physical extra row or changed frozen raw byte returns
   `EVIDENCE_UNAVAILABLE` before replay rather than being silently filtered.

The future-row tests demonstrate invariance of an earlier decision. They do
not authorize accepting a changed production inventory.

## 8. Verdict precedence

Verdicts are evaluated in this order:

1. `EVIDENCE_UNAVAILABLE` — frozen evidence is missing, unreadable,
   unparseable, hash/size/count drifted, identity-ambiguous or incomplete.
2. `LEAKAGE_DETECTED` — evidence is available but a row ineligible at the
   literal cutoff changes an earlier output, membership changes post hoc, or
   repeat/shuffle invariance fails.
3. `REPLAY_SAFE_WITH_LIMITATIONS` — all hard replay and leakage invariants
   pass, but an explicitly enumerated non-critical replay limitation remains.
4. `REPLAY_SAFE` — exact expected output, fail-closed vectors and deterministic
   invariance all pass with no declared replay limitation.

An attractive hypothesis result cannot select or soften the verdict. There is
no majority vote, silent warning downgrade or cutoff derived from observed
future rows.

## 9. Reuse and Catalog boundary

TASK-19 uses `ADOPT → WRAP → BUILD`:

- `ADOPT` TASK-05 decision-as-of semantics and TASK-16 deterministic
  point-in-time ordering;
- `WRAP` TASK-17A pairing/cost calculation and TASK-18 exact
  integrity/availability primitives;
- `BUILD` in A3 only a thin TASK-specific replay projector and adversarial
  harness;
- no fork, new dependency, generic backtester, general event platform or
  all-token replay engine.

A2 creates only this contract, its machine fixture and targeted contract
tests. Catalog registration and generated navigation remain owned by
`T19-A4_ACCEPTANCE_CATALOG_FACTORY_FIT_V1`.

## 10. Authority, non-claims and next boundary

`T19-A2_FROZEN_POINT_IN_TIME_REPLAY_CONTRACT_V1` is `LOCAL_WRITE_ONLY`.
It authorizes no provider/API/RPC/WSS call, Drive write/read fallback, new
collection, raw mutation, credential, dependency, purchase, deployment,
wallet, signer, transaction, signal, strategy, execution, fill, position,
risk, PnL, NetReturn, owner-cashflow, alpha or production-readiness claim.

The next atom is
`T19-A3_DETERMINISTIC_OFFLINE_REPLAY_AND_LEAKAGE_TESTS_V1`. It may read the
frozen local raw bytes and create bounded TASK-19 code, evidence and tests.
It remains offline, preserves raw bytes and requires a separate continuation.
