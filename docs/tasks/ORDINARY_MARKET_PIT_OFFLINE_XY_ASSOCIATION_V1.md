---
task_id: ORDINARY_MARKET_PIT_OFFLINE_XY_ASSOCIATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7a4e5a5b01681718b0323409cbea64b131bf4da8
  expected_upstream: origin/main
  expected_upstream_oid: 7a4e5a5b01681718b0323409cbea64b131bf4da8
  expected_branch: cursor/ordinary-market-pit-offline-xy-association
  dirty_mode: ALLOW_REPORTED
objective: Join bound liquidity/mcap X to already-captured forward quote Y on the
  quoted subset, without live Jupiter, Factory Python, or a family CLOSE/EARN claim.
managed_write_set:
- docs/tasks/ORDINARY_MARKET_PIT_OFFLINE_XY_ASSOCIATION_V1.md
- configs/ordinary_market_pit_offline_xy_association_v1.yaml
- src/solana_alpha_lab/ordinary_market_pit_offline_xy_association.py
- scripts/run_ordinary_market_pit_offline_xy_association.py
- tests/test_ordinary_market_pit_offline_xy_association.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/ordinary_market_pit_offline_xy_association/a1_runtime_receipt_v1.json
- docs/evidence/ordinary_market_pit_offline_xy_association/a1_acceptance_v1.json
- docs/evidence/ordinary_market_pit_offline_xy_association/a1_delivery_completion_evidence_v1.json
- docs/evidence/ordinary_market_pit_offline_xy_association/a1_delivery_independent_review_v1.json
- docs/evidence/ordinary_market_pit_offline_xy_association/a1_delivery_factory_fit_v1.json
- docs/reports/ordinary_market_pit_offline_xy_association/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_OR_NETWORK_CALL
- CREDENTIAL_OR_API_KEY_READ
- FACTORY_PYTHON_CHANGE
- NUMERIC_UNKNOWN_AS_ZERO
- PIT_READY_CLAIM
- FAMILY_CLOSE_OR_EARN_REPLICATION
- QUOTE_KEEP_AS_PREDICTOR
- LIVE_JUPITER_CAPTURE
- SKIPTEST_WITHOUT_PROOF
- THIRD_ORDINARY_YAML
- TASK28_SKELETON_REGISTRY_REWRITE
- VPS_OR_DEPLOYMENT
- ALPHA_OR_NETRETURN
- MUV3_SHADOW_EXECUTION
context_requirements:
  catalog_asset_ids:
  - CTRL-ORDINARY-MARKET-PIT-LOCAL-RAW-ENVELOPE-BIND-001
  - EVIDENCE-ORDINARY-MARKET-PIT-LOCAL-RAW-ENVELOPE-BIND-RUNTIME-001
  - EVIDENCE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001
  - MODULE-FACTORY-V1-RUNNER-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_runtime_receipt_v1.json
    - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json
    - docs/evidence/ordinary_market_pit_offline_xy_association/a1_delivery_completion_evidence_v1.json
    - docs/evidence/ordinary_market_pit_offline_xy_association/a1_delivery_independent_review_v1.json
    - docs/evidence/ordinary_market_pit_offline_xy_association/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# ORDINARY_MARKET_PIT_OFFLINE_XY_ASSOCIATION_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=PATCH`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge.

Muv-2 Move 3 is shadow execution after Move 1 PASS and Move 2 OOS PASS.
Neither happened. PR #164 bound X from local A4 and left a Git receipt;
qualification already holds forward quote Y on a subset. The cheapest
falsifier now is that join, not Muv-3 and not live Jupiter.

This is still Move 1: exploratory rank of liquidity/mcap vs
`y_quoted_liquidation_recovery` on the quoted subset. It cannot CLOSE or
EARN_REPLICATION. Quote is Y only, never the predictor.

`strongest_rejected_alternative`: start Muv-3 / live shadow execution.
Rejected because Move 1 audition never ran; Y was not outcome-blind for this
X; RECENT complete n=4 < min_stratum_n=6.

`ADOPTION_ROUTE=ADOPT_GIT_BIND_AND_QUALIFICATION_RECEIPTS_WRAP_JOIN_BUILD_NO_FACTORY_PYTHON`

## PRD-lite

- **Owner decision:** family stays open; next material step is a later bounded
  fresh PIT capture, not Muv-3 and not another YAML.
- **Product outcome:** `EXPLORATORY_ASSOCIATION_NOT_PIT` +
  `DEFER_FRESH_PIT_CAPTURE`. Honest n, missing Y, stratum ranks.
- **Named consumer:** owner writing the first fresh ordinary-market capture
  phrase for `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1`.
- **Current gap:** X is bound in Git; forward Y exists on a subset; they were
  not joined, so sample constraints for the next capture were still implicit.
- **Success / cheapest falsifier:** complete_xy=10; RECENT_1 and RECENT_4 Y
  MISSING not 0; RECENT INCONCLUSIVE_STRATUM; TRADED rank computed; family
  not CLOSE/EARN; 0 provider calls. Treating n=12 as a clean panel is replan.
- **Invalidation:** PIT_READY; using t0 friction as Y; filling missing Y with
  0; Factory Python change; live capture in this atom.
- **Non-goals:** Muv-3, live Jupiter, VPS, Cockpit, third YAML, TASK-28
  unfreeze, alpha, `/execute`.
- **Evidence budget:** two Git receipts; 0 provider calls.
- **Replan trigger:** X/Y hash mismatch; Y field drift; Factory Python change.

## SSD-lite

- **Baseline truth:** `origin/main` after PR #164.
- **Design:** ADOPT Git bind + qualification receipts. WRAP a fail-closed join
  and Kendall comparable-pairs rank. FORK nothing in Factory Python. BUILD
  tests that always run on Git receipts (no skipTest).
- **Invariants:** Y = `y_quoted_liquidation_recovery` only; UNKNOWN != 0;
  min_stratum_n=6 frozen a priori; `y_equals_x` rows are excluded from rank;
  `FORWARD_SNAPSHOT_NOT_PIT_READY`; TASK-28 empty; 0 provider calls.
- **Affected surfaces:** association config, projector, CLI, tests, receipts.
  Not Factory Python, not A4, not quote scorers.
- **Failure modes:** hash drift; skipTest without proof (forbidden here);
  claiming family CLOSE/EARN.
- **Validation:** unit tests on Git receipts + fixtures; isolated critics;
  exact-head CI. Run `--ci-owned-delivery` before MERGE_READY.
- **Rollback:** revert this branch.

## Decision capsule

- `DECISION_DELTA`: PATCH Move 1 to join already-bound X with already-captured
  forward Y instead of jumping to Muv-3 or live capture.
- `UNCERTAINTY_REMOVED`: whether this cohort is a clean n=12 panel (no;
  quoted subset n=10, RECENT n=4 inconclusive) and whether missing Y is typed.
- `CAPABILITY_OR_EVIDENCE`: Git-only association receipt; TRADED exploratory
  rank; family deferred.
- `STOP`: PR + exact-head CI; wait for owner merge phrase.
- `NEXT`: owner phrase for bounded fresh PIT capture. Not Muv-3. Not VPS.
- `REPLAN_TRIGGER`: hash mismatch; Y-field drift; Factory Python change;
  this atom used to claim PIT_READY or CLOSE.

## Definition of Done

1. Same frozen hypothesis id `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1`.
2. Join 12 bind rows to qualification campaign cells by identity_id.
3. complete_xy=10; RECENT_1 and RECENT_4 remain Y MISSING, not 0.
4. RECENT stratum INCONCLUSIVE because n<6; TRADED rank may compute.
5. family_decision=`DEFER_FRESH_PIT_CAPTURE`; no PIT_READY/CLOSE/EARN.
6. No Factory Python in the diff; runner.py hash unchanged.
7. 0 provider calls. No skipTest. Tests always run on Git receipts.
8. Delivery trio bound in `DELIVERY_EVIDENCE` before merge context.
