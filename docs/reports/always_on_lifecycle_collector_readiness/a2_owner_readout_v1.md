# ALWAYS_ON_LIFECYCLE_COLLECTOR_READINESS_V1 — owner readout

## Envelope (supported Free-tier campaign)

- Terminal: `SCHEDULABLE_WITH_HEADROOM`
- X point: **X300** (`INSUFFICIENT_TIMING_EVIDENCE_KEEP_X300`)
- Y points: 900, 1800, 3600, 7200, 14400, 43200, 86400 (search-only)
- Proven operating point in zero-network preflight: **50 members/day**, inclusion **0.1** at 2000 candidate launches/day
- Oracle max supported members/day (worst-case unbatched, material headroom): **200**
- Predicted calls/day @50 members: **1840**; lifetime 21d: **38640**
- Pace bound: 28800 calls/day (3s); headroom_pct ≈ **93%**
- Source poll: `/tokens/v2/recent` period 60s; timer cadence 60s
- Credential: sanctioned env **`JUPITER_FREE_API_KEY`** (optional compat alias `JUPITER_API_KEY` only when sanctioned unset)
- Live authority: **not granted** (`PROPOSED_NOT_AUTHORITY`)

## False roadmap assumptions discovered

1. Design-time main SHA in the desktop roadmap is stale relative to frozen A2 base `main@9b0c4b57…`.
2. Continuous due-work starvation of `/recent` was real on the merged scheduler (`not due_work_waiting`); fairness is a one-line policy, not a second scheduler.
3. `http_status`/`http_class` already existed in primitives/PathRisk but schedule call-ledger payloads dropped them — persistence gap, not missing classification.
4. Credential naming divergence (`JUPITER_FREE_API_KEY` vs `JUPITER_API_KEY`) is operational ambiguity, not a second provider.
5. Without timing evidence, X300 is retained; discovery coverage defaults to `GAP_SUSPECTED` / `DISCOVERY_COVERAGE_UNKNOWN` (not a hard doctor fail).

## A3/A4 product-code readiness

- **A3 (historical bind):** can proceed with **zero additional product code** from A2 (uses A1 release bridge).
- **A4 (VPS preflight/activate):** campaign packet + oracle + doctor/read model exist; remaining work is **operations** (host preflight, authority phrase, activate) — no additional product PR required on the happy path unless measured gaps appear.

## Non-claims

No providers, credential values, VPS deploy, spend, live authority, Forge run, or alpha.
