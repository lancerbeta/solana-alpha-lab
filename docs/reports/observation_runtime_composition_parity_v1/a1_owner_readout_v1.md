# OBSERVATION_RUNTIME_COMPOSITION_PARITY_V1 — owner readout

## Decision delta

Production ObservationSchedule `tick --once` now assembles opener/clock through
one composition seam. Deterministic parity injects complete process-local
`TickPhysicalOverrides` (fake opener + `AdvancingClock`) without any
CLI/config/env fake-mode switch. Historical composition classes #238/#240/#242
are represented in one golden vertical + restart continuation.

## Entry

- Base: `1de19ef378d9c08d3f4ebb4d3b81c9d0e99ab836` (post-A4 / PR #254)
- `ENTRY_VERDICT=COMPOSITION_PARITY_GAP_CONFIRMED`

## Capability

- `P0_STATIC_IDENTITY`: PASS (systemd ExecStart → tick --once + production runtime config)
- `P1_COMPOSITION_ASSEMBLY`: PASS (unit-locked: SEAM_MUST_RUN on override and
  production paths; sentinel override + WallClock production binding consumption;
  smoke alone is DETERMINISTIC_PARITY, not live production assembly)
- `P2_DETERMINISTIC_VERTICAL`: PASS (RECENT+SEARCH under process-local overrides;
  measured 3s spacing, restart, doctor — not live production assembly)

## Parity smoke

```text
uv run --locked --managed-python python -B scripts/observation_runtime_composition_parity.py --json
```

- terminal: `OBSERVATION_RUNTIME_COMPOSITION_PARITY_PASS`
- wall_time_seconds: ~3.1
- network_calls: 0 / credential_reads: 0
- minimum_simulated_spacing_seconds: 3.0 (measured AdvancingClock open deltas)
- restart_no_duplicate_completed_ids: true
- restart_proof_kind: FRESH_COMPOSITION_PLUS_REOPENED_SQLITE (not OS supervision)

## Anti-drift

- production override exposure: NONE
- scenario count: 1 golden + restart continuation
- incident promotion rule: present in smoke JSON
- fixture drift policy: present in smoke JSON
- failure taxonomy: present in smoke JSON

## Known limitations (non-claims)

- P3 live commissioning not proven
- external provider future drift not proven
- OS/systemd process supervision not simulated

## NEXT

`STOP_THIS_CHAIN` after guarded merge + post-merge read-back.
