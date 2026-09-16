# HFIC_SEARCH_BUDGET_EPOCH_GUARD_V1 — Owner readout

Date: 2026-09-16 · Route: DIRECT_CURSOR_DELIVERY

## Defect

`decide_preflight_action()` counted AUTO / distinct-focus budget only among
sessions sharing both `evidence_epoch_sha256` and `memory_eligibility_sha256`.
Quarantine/restore therefore reset epoch budget while the evidence epoch was
unchanged.

## Fix

Budget accounting uses all HFIC sessions with the same `evidence_epoch_sha256`.
`memory_eligibility_sha256` remains inside `search_key_sha256` and same-focus /
exact replay identity.

## Real-state IDENTIFIABLE_NOW (read-only)

| Metric | Value |
| --- | --- |
| HEAD | `6f144de9…` |
| action | `START_NEW_SESSION` |
| AUTO used | 1 / 1 (60FB counts) |
| distinct used / remaining | 1 / 2 |
| packet | 18313 ≤ 20480 |
| vision | PASS |
| C1/C2 + scope | present |
| RDP / provider | 0 / 0 |

## Non-claims

No live Forge synthesis · no packet-bound change · no quarantine mutation.
