---
task_id: FAST_LANE_REGISTER_JUPITER_BOUNDED_CAPTURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-26'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: fdf707ceb3d76c80680645853459d71d071380ab
  expected_upstream: origin/main
  expected_upstream_oid: fdf707ceb3d76c80680645853459d71d071380ab
  expected_branch: cursor/fast-lane-register-jupiter-bounded-capture
  dirty_mode: ALLOW_REPORTED
objective: Register CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001 in the Fast Lane capability registry for the Factory commissioning / TWO_RUNG 60-call path so classify reaches FAST_LANE_OWNER_GATE_REQUIRED with zero provider calls.
managed_write_set:
  - docs/tasks/FAST_LANE_REGISTER_JUPITER_BOUNDED_CAPTURE_V1.md
  - configs/experiment_capability_registry_v1.yaml
  - tests/test_fast_lane_classifier.py
  - tests/fixtures/fast_lane/two_rung_live_h900_classify_packet_v1.json
  - catalog/assets/core.yaml
  - docs/evidence/fast_lane_register_jupiter/a1_delivery_completion_evidence_v1.json
  - docs/evidence/fast_lane_register_jupiter/a1_delivery_independent_review_v1.json
  - docs/evidence/fast_lane_register_jupiter/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - TWO_RUNG_LIVE_EXECUTION
  - PROVIDER_API_RPC_WSS
  - MAX_PROVIDER_CALLS_RAISE_TO_62
  - WALLET_SIGNER_TX_OR_CASH
  - AUTOMATIC_PROMOTION
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/fast_lane_register_jupiter/a1_delivery_completion_evidence_v1.json
      - docs/evidence/fast_lane_register_jupiter/a1_delivery_independent_review_v1.json
      - docs/evidence/fast_lane_register_jupiter/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FAST_LANE_REGISTER_JUPITER_BOUNDED_CAPTURE_V1

## Task Outcome Brief

- **Owner decision:** after Fast Lane foundation + offline commission, TWO_RUNG
  classify reported `CHANGE_LANE_CAPABILITY_GAP` / `CAPABILITY_NOT_REGISTERED`.
  Authorize one narrow registry PR for the Factory free-key capture capability
  already implemented in Git.
- **Product outcome:** `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`
  is `ACCEPTED` in `configs/experiment_capability_registry_v1.yaml` with
  `PROVIDER_READ_ONLY_BOUNDED`, `max_provider_calls: 60`, provider policy
  `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009`, output zone `DATA_ROOT_ONLY`.
  Classify of the TWO_RUNG / Factory commissioning v1.1 packet returns
  `FAST_LANE_OWNER_GATE_REQUIRED` with zero provider calls.
- **Named consumers:** Fast Lane classifier; owner live-authority gate for a
  later TWO_RUNG execution atom (not this PR).
- **Cheapest falsifier:** classify of the committed TWO_RUNG packet still
  returns `CAPABILITY_NOT_REGISTERED`, or requested calls above 60 pass the
  descriptor without `GUARDRAIL_CHANGE_REQUIRED`.
- **Terminal outcome:** green exact-head CI + product context receipt; stop
  before merge for exact owner phrase.
- **Non-goals:** no live capture; no TWO_RUNG execution; no raise of
  `max_provider_calls` to 62 for retention specs; no provider/network/credential
  reads; no wallet/signer/tx; no harness control-runtime mutation beyond Catalog
  integrity hashes for touched assets.
- **Evidence budget:** offline only; targeted classifier tests + catalog
  validate; exact-head CI at merge.
- **Replan trigger:** descriptor cannot bind the existing Factory entrypoint, or
  classify of the commissioning packet cannot reach owner gate without live
  calls.

## Decision capsule

- `DECISION_DELTA`: register one already-built Factory capability into the Fast
  Lane registry for the 60-call commissioning path.
- `UNCERTAINTY_REMOVED`: TWO_RUNG classify lane is Fast Lane owner-gated, not a
  capability gap, once this PR is on `main`.
- `CAPABILITY_OR_EVIDENCE`: registry row + classifier/fixture tests + Catalog
  hashes.
- `STOP`: after green CI; do not merge; do not execute live capture.
- `NEXT`: owner exact phrase → guarded merge → re-classify on `main` → separate
  owner authority for any live TWO_RUNG capture.
- `SPEC_ROUTE=NONE`

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`. Retention ExperimentSpecs that request 62 calls
remain out of scope and correctly hit `GUARDRAIL_CHANGE_REQUIRED` until a
separate atom.
