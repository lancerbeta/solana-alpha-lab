# Owner readout — COLLECTOR_ORACLE_P99_SCIENTIFIC_DEADLINE_CLOSURE_V1

`COLLECTOR_ORACLE_P99_SCIENTIFIC_DEADLINE_CLOSURE_READY_FOR_MERGE`

## Old inconsistency (must not remain accepted)

| Field | Value |
| --- | --- |
| Geometry | 102 members / 17 usable due calls per tick |
| p95_due_lateness_seconds | 300 |
| p99_due_lateness_seconds | 360 |
| allowed_x_lateness_seconds | 300 |
| Terminal (broken) | `SCHEDULABLE_WITH_HEADROOM` while p99 > X |
| Forbidden proposal | `50b2d070361b04be0f983c4bb801be5bf3b01e06783e45b9e0a9fb04a9facc19` |

Root: member fitting admitted on `p95 <= allowed`; p99 was reported but ignored.

## Repaired envelope (oracle-derived, not hard-coded)

| Field | Value |
| --- | --- |
| usable_due_calls/tick | 17 |
| max_members_per_utc_day | 85 |
| inclusion_probability | 0.0425 |
| predicted_provider_calls_per_day | 2120 |
| predicted_provider_calls_lifetime_21d | 44520 |
| provider_calls_per_utc_day_max | 2650 |
| provider_calls_lifetime_max | 55650 |
| p95_due_lateness_seconds | 240 |
| p99_due_lateness_seconds | 300 |
| x_deadline_headroom_seconds | 0 |

## Non-claims

- No VPS mutation, no provider calls, no register/authorize/activate
- Forbidden proposal not authorized
- No scheduler/pacing knob / X300 / Y / population / route change
- No alpha / canonical DONE
