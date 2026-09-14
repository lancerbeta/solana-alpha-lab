---
task_id: M1_EXECUTION_REALITY_CALIBRATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-14'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5e36ef349f85d741c140c418af2de136d99521b7
  expected_upstream: origin/main
  expected_upstream_oid: 5e36ef349f85d741c140c418af2de136d99521b7
  expected_branch: cursor/m1-execution-reality-calibration-v1
  dirty_mode: ALLOW_REPORTED
objective: "Materialize the minimum reusable M1 capability so the Factory can later measure, through its existing ObservationSchedule collector spine, the Jupiter execution surface (TWO_WAY / ENTRY_ONLY / NO_ENTRY / UNKNOWN) and quote-implied roundtrip friction for canonical fresh EARLY pump.fun candidates at fixed $10 and $100 USDC notionals at decision time. M1 is execution calibration only - not alpha, not LIVE trading."
managed_write_set:
- docs/tasks/M1_EXECUTION_REALITY_CALIBRATION_V1.md
- configs/observation_primitive_registry_v1.yaml
- src/solana_alpha_lab/factory/observation_primitives.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_schedule_runtime.py
- src/solana_alpha_lab/factory/m1_execution_reality.py
- src/solana_alpha_lab/factory/m1_successor_preflight.py
- src/solana_alpha_lab/factory/m1_calibration_report.py
- scripts/m1_successor_preflight.py
- scripts/build_m1_calibration_report.py
- tests/test_m1_execution_reality.py
- tests/fixtures/observation_schedule/m1_quote_surface.yaml
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- NO_MERGE_AUTHORITY_STOP_BEFORE_MERGE
- TYPED_NO_ROUTE_PARITY_REQUIRES_TRANSPORT_REDESIGN
- SECOND_DISCOVERY_LOOP_OR_NEW_DAEMON_REQUIRED
- SOL_QUOTE_SEMANTICS_MUST_CHANGE
- LIVE_PROVIDER_CALL_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# M1_EXECUTION_REALITY_CALIBRATION_V1 — Execution reality calibration capability

## Objective

Add the minimum reusable capability to the existing Factory collector spine so
that a later commissioned M1 campaign can answer, for canonical fresh EARLY
pump.fun candidates at decision time (age [300,900)s, liquidity_usd >= 1000),
what execution surface Jupiter exposes at fixed $10/$100 USDC notionals:
TWO_WAY, ENTRY_ONLY, NO_ENTRY or UNKNOWN, plus quote-implied roundtrip
friction for TWO_WAY pairs.

## Deliverables

1. Typed quote terminal classification parity (§9): Jupiter typed
   `errorCode` no-route responses must be distinguishable from transport /
   provider / schema failures inside the ObservationSchedule quote path,
   reusing the canonical typed-error-code semantics already proven by the
   quote-native panel (exact match on normalized known route-unavailable
   codes, never substring heuristics, never mapping generic HTTP errors to
   NO_ROUTE).
2. USDC fixed-notional registered primitives/bundles: $10 and $100 ENTRY
   (USDC→token) plus DEPENDENT REVERSE (exact entry outAmount → USDC), with
   the reverse leg contractually bound to the same-notional entry bundle.
   Existing SOL primitives/bundles remain byte-identical in semantics.
3. M1 outcome classification + denominator invariant
   (population_n = two_way_n + entry_only_n + no_entry_n + unknown_n per
   notional) and deterministic QUOTE_IMPLIED_ROUNDTRIP_FRICTION pairing for
   TWO_WAY, $10/$100 kept separate, plus cross-notional transition and
   normalized entry size-linearity diagnostics (EXECUTION_DIAGNOSTIC only).
4. Zero-network M1 successor preflight composer/checker that, given a
   predecessor readback + immutable predecessor schedule + M1 campaign
   request, returns compatible/blocked, proposed successor identity, semantic
   diff, added M1 bundles, sampling proposal, incremental provider-call
   envelope, resulting total budget, cutover proposal and exact
   authority-request material. No provider calls, no runtime mutation, no
   second discovery loop.
5. Deterministic M1 calibration projection/report builder that reads only
   immutable/snapshot/sealed Observation RDP lineage (never moving SQLite)
   and emits the M1-specific minimal calibration report (counts, friction
   summaries, transitions, covariate summaries, diagnostics, source hashes,
   limitations). No automatic ExecutionEvidenceBindingV1, no fabricated
   experiment identity.
6. Minimal M1 operability projection inside the existing collector
   read-model surface (active/not-active, sampled count, complete dual-notional
   count, provisional outcome counts, provider calls used, last progress time,
   exact blocker).
7. Runbook operator flow (§29) and Catalog/semantic propagation.

## Non-goals

- No campaign commissioning, deployment, VPS/runtime mutation, schedule
  registration/authorization/activation/rollover in this atom.
- No live provider calls, credentials, wallet/signer/transaction, real money.
- No merge. No second probe/discovery system, daemon or database.
- No changes to existing SOL/lamport quote primitive semantics.
- No alpha claim, no admission rule, no strategy, no Trigger/LIVE work.

## DoD

- Typed no-route parity proven by tests: known Jupiter route error codes →
  NO_ENTRY/ENTRY_ONLY classification; timeout/transport/5xx/schema/unrecognized
  provider error → UNKNOWN; generic provider failure never classified NO_ROUTE;
  Jupiter known route error never collapsed into generic UNKNOWN.
- Denominator closes exactly per notional; UNKNOWN never coerced.
- Existing SOL primitives unchanged (identity + semantics regression-tested);
  existing registered schedules still compile; timer/store/recovery path
  unchanged.
- Reverse legs consume the exact same-notional entry outAmount; $10/$100
  cross-wiring impossible (tested).
- Safety: taker omitted, no build/execute, no transaction material,
  retry=false, fallback=false, cash=$0, zero live provider calls in tests.
- Successor preflight: zero network, fails closed on incompatible predecessor,
  preserves unrelated predecessor semantics, explicit M1_BUNDLE_CAPACITY_GAP /
  M1_PROVIDER_BUDGET_GAP gaps, proposes no second discovery loop.
- Report builder: moving SQLite rejected as source; frozen projection requires
  immutable lineage hashes; $10/$100 regimes separate; friction labeled
  quote-implied, never realized; no Experiment identity fabrication.
- Ordinary harness verification green; CI green at exact head; STOP BEFORE
  MERGE.

## Rollback

Ordinary Git revert. No runtime consequence (nothing commissioned).
