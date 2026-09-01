# A1 owner readout — DISCOVERY_EVIDENCE_RELEASE_BRIDGE_V1

## Verdict

Vertical zero-network bridge is implemented on
`main@2597104aed0fd372ac756af84a497ad7b2705235`:

hash-bound Tokens V2 raw → one typed projection → sealed discovery release →
RDP import → HFIC sees structured feature families → evidence epoch changes.

## What landed

- Shared `tokens_v2_typed_projection` used by historical replay and
  ObservationSchedule `_row_field`.
- Compact seal/verify/import path (`discovery_evidence_release`).
- HFIC current capability enumeration on registry v2; v1 kept as predecessor.
- Feature families exposed in Forge context without a second data platform.

## Roadmap assumptions that were false

1. Design-time base `4cf01ec…` was already superseded; freeze used
   `2597104…` (PR #230 merged).
2. Git `VAL_R0` / `DISCOVERY_SEARCH_R0` fixture is **not** rich: no
   `holderCount`, organic score, or multi-window trader stats — only
   `usdPrice` / `mcap` / `liquidity` / `stats5m.buyVolume|sellVolume`.
   Missing fields are typed `MISSING_TYPED` / excluded when ambiguous.
3. Literal symbol `VAL_R0` does not exist in-repo; the bound fixture is
   `DISCOVERY_SEARCH_R0`.

## Non-claims

No provider calls, credentials, VPS deploy, A2 collector readiness, weekly
live seal automation, or confirmation authority for hypotheses discovered
from the imported release.
