# HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1 — Owner readout

Date: 2026-09-16 · Route: DIRECT_CURSOR_DELIVERY

Pinned real-state: `docs/evidence/hfic_forge_prior_context_capacity_repair/a1_active_rdp_preview_v1.json`

## Architecture decision (mode-scoped budgets)

| Mode | Bound | Constant |
| --- | --- | --- |
| Ordinary `/hypothesis-forge` | **20480** | `ORDINARY_FORGE_MAX_PACKET_BYTES` |
| `CURRENT_REPRESENTATION_CONTROL_V1` | **16384** | `CONTROL_FORGE_MAX_PACKET_BYTES` / `MAX_PACKET_BYTES` |
| Representation challenger / `NORMALIZED_TRAJECTORY_V1` | **16384** | imports frozen `MAX_PACKET_BYTES` |

Resolver: `forge_context_packet_max_bytes(evidence_surface_mode)` — ordinary/absent → 20480; CONTROL evidence surface → 16384. Not inferred from `owner_focus` text.

The ordinary enlargement is not alpha, extra data authority, or representation permission. CONTROL↔challenger packet-budget comparability stays frozen.

## Semantic patch retained

1. Forge ranked priors use shared `latest_hypothesis_decisions(store)`.
2. HARD_CLOSE/PARK retain scope axes.
3. `NOT_SELECTED_IN_SESSION` stays thinner when a lean distinguisher remains.
4. Scientifically minimal packet that still exceeds the active mode bound → typed capacity terminal (`MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND`).

## ORDINARY IDENTIFIABLE_NOW readback (exact real state, read-only)

Release `REL-20260902T111900Z-20260909T111900Z` · epoch `ba884414…` · prior CONTROL `HFIC-SESS-60FB3DA7C8EB33FC` · focus `IDENTIFIABLE_NOW`.

| Metric | Value |
| --- | --- |
| effective bound | 20480 |
| actual bytes | 18312 |
| vision | PASS |
| material_information_loss | 0 |
| unknown_omission | 0 |
| material grounding rows | 6 |
| ranked_prior_count | 8 (one-to-one) |
| C1 | `KILL_STATISTICALLY_UNIDENTIFIABLE` + scientific scope |
| C2 | `KILL_DATA_INFEASIBLE` + scientific scope |
| remaining 60FB | `NOT_SELECTED_IN_SESSION` |
| 60FB quarantine | unchanged / not quarantined |
| expected action | `START_NEW_SESSION` |

## CONTROL / representation acceptance

| Surface | Bound | Result |
| --- | --- | --- |
| CONTROL | 16384 | unit/regression: bound + fences unchanged |
| `NORMALIZED_TRAJECTORY_V1` / challenger | 16384 | preregistration + representation-probe suites PASS |

## Explicit non-actions

- No CONTROL/challenger bound raise
- No ranked-prior drop / ranker / `MAX_RANKED_PRIORS` change
- No Critic prior-memory change
- No 60FB quarantine/reset
- No real `/hypothesis-forge IDENTIFIABLE_NOW`
- No merge in this atom
