# COLLECTOR_SAMPLING_ORACLE_APPLIED_PROBABILITY_REPAIR — owner readout

## Defect

Post-launchpad-repair preflight proposed `recommended_inclusion_probability=0.228`
while `recommended_max_members_per_utc_day=114`. The oracle divided the **capacity
ceiling** (`max_supported_members_per_day=456`) by candidate launches, not the
**applied** member cap.

Proposal `02152e3136ad…` MUST NOT be authorized.

## Repair

`recommended_inclusion_probability` now follows:

`min(requested_max_members, max_supported) / candidate_launches_per_utc_day`

Capacity ceiling (`max_supported_members_per_day`) is unchanged.

## Commissioning envelope (114 members, p=0.057)

Frozen replacement preflight at `2026-09-01T21:50:00Z` resolves to
`inclusion_probability=0.057`, provider caps 2940/61740, headroom 91%,
predicate `FIELD-LAUNCHPAD-001 EQ pump.fun`.
