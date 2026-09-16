# HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1 — Owner readout

Date: 2026-09-16 · Route: DIRECT_CURSOR_DELIVERY

Pinned real-state: `docs/evidence/hfic_forge_prior_context_capacity_repair/a1_active_rdp_preview_v1.json`

## Semantic patch (PR #312 follow-up)

1. Forge ranked priors use shared `latest_hypothesis_decisions(store)` (same walker as Critic).
2. HARD_CLOSE/PARK retain scope axes (`population` / `decision_timestamp` / `horizon_notional` / `negative_control`).
3. `NOT_SELECTED_IN_SESSION` stays thinner when a lean distinguisher remains.

## 60FB decision readback (store-resolved, not hardcoded)

| Candidate | reason_code | forge memory_status | scope retained |
| --- | --- | --- | --- |
| HFIC-CAND-992D6CF8407B | KILL_STATISTICALLY_UNIDENTIFIABLE | HARD_CLOSE | population+horizon |
| HFIC-CAND-52CC773188C7 | KILL_DATA_INFEASIBLE | HARD_CLOSE | population+horizon |
| HFIC-CAND-8EF7214122D7 | NOT_SELECTED_IN_SESSION | NOT_SELECTED_IN_SESSION | omitted (lean OK) |
| HFIC-CAND-985C6CF5B7CB | NOT_SELECTED_IN_SESSION | NOT_SELECTED_IN_SESSION | omitted |
| HFIC-CAND-FB105AA77240 | NOT_SELECTED_IN_SESSION | NOT_SELECTED_IN_SESSION | omitted |

## Capacity fence — STOP

With correct decisions + scientifically sufficient HARD_CLOSE scope:

| Metric | Value |
| --- | --- |
| ranked prior count | 8 (one-to-one) |
| ranked prior bytes | 5774 |
| unbounded total packet bytes | 18317 |
| MAX_PACKET_BYTES | 16384 |
| over_bytes | 1933 |
| bounded terminal | `MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND` |
| IDENTIFIABLE_NOW | not reachable without new owner architecture decision |

### Section bytes (unbounded, vision would be PASS)

See `section_bytes` in the pinned RDP preview (largest: ranked_prior_entries 5774, closed_family_ledger 3502, feature_grounding_entries 1416, capability_entries 1058, dataset_entries 1054, semantic_capability_entries 967).

## Explicit non-actions

- No packet-limit raise
- No ranked-prior drop
- No 60FB quarantine/reset
- No arbitrary string truncation
- No Critic prior-memory change
- No real `/hypothesis-forge IDENTIFIABLE_NOW`

## Required owner decision (outside this patch)

Choose one: raise bound / redesign packet / accept second-focus blocked under current 16KiB with full scientific Forge minimum.
