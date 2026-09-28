---
task_id: COLLECTOR_CAMPAIGN_CUTOVER_TRUTH_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-28"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CODEX_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 86b24cb1abe5867becc1ead16efb3754044550df
  expected_upstream: origin/main
  expected_upstream_oid: 86b24cb1abe5867becc1ead16efb3754044550df
  expected_branch: codex/collector-campaign-cutover-truth-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Correct the bounded first atom for campaign continuity truth and future
  cutover ticks: only proven same-family cutover clears the owner alert, missed
  windows remain explicit gaps, and tick candidates use one captured UTC time
  projected through project_activation_as_of. Add focused tests, update the
  existing alert and operator runbook, and propagate the capability through
  Catalog. No live commissioning or call_ledger optimization.
managed_write_set:
  - docs/tasks/COLLECTOR_CAMPAIGN_CUTOVER_TRUTH_V1.md
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - scripts/observation_schedule.py
  - tests/test_collector_campaign_continuity_repair_v1.py
  - tests/test_observation_scheduler.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/collector_campaign_cutover_truth/a1_delivery_completion_evidence_v1.json
  - docs/evidence/collector_campaign_cutover_truth/a1_delivery_independent_review_v1.json
  - docs/evidence/collector_campaign_cutover_truth/a1_delivery_factory_fit_v1.json
  - docs/reports/collector_campaign_cutover_truth/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_VPS_DEPLOY_OR_MUTATION_REQUIRED
  - PROVIDER_API_RPC_WSS_OR_CREDENTIAL_REQUIRED
  - LIVE_ACTIVATION_REGISTRATION_OR_AUTHORIZATION_REQUIRED
  - SQLITE_SCHEMA_RETENTION_OR_CAMPAIGN_LIMIT_CHANGE_REQUIRED
  - APPEND_ONLY_LIFECYCLE_HISTORY_REWRITE_REQUIRED
  - CALL_LEDGER_DIAGNOSTICS_OR_LIVE_COMMISSIONING_SCOPE_REQUIRED
  - SCIENTIFIC_OR_SOURCE_DATA_STALE_SEMANTICS_CHANGE_REQUIRED
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - WRITE_OUTSIDE_MANAGED_WRITE_SET_REQUIRED
context_requirements:
  catalog_asset_ids:
    - DOC-FACTORY-LIFECYCLE-COLLECTOR-001
    - MODULE-COLLECTOR-OPERATIONAL-PACKET-001
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
      - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
      - src/solana_alpha_lab/factory/collector_operational_packet.py
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - src/solana_alpha_lab/factory/collector_read_model.py
      - src/solana_alpha_lab/factory/collector_operational_packet.py
      - scripts/observation_schedule.py
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_CAMPAIGN_CUTOVER_TRUTH_V1

## SPEC_ROUTE

PRD_LITE — exact bounded task contract based on the owner-supplied PRD + SSD.

## ENTRY VERDICT

START_AS_WRITTEN. The fresh default-branch base is
86b24cb1abe5867becc1ead16efb3754044550df; the named contract did not exist
on main, so this file establishes it without editing prior contracts.

## DECISION_DELTA

A same-family registration or unbound authority is preparation only. Owner
continuity is complete only when a boundary-covering rollover is bound to live
authority and its linked append-only predecessor and successor transition
events are proven, or a same-family successor is already ACTIVE with valid
lifecycle proof. Historical registrations are shown as out-of-window. A missed
predecessor window stays an actionable gap through DRAINING until forward
recovery is proven. Tick selects state as of its single captured UTC now, not
the mutable stored state.

## UNCERTAINTY_REMOVED

Whether a REGISTERED/AUTHORIZED document can falsely clear the campaign alert,
whether an expired DRAINING predecessor can look recovered without a proven
successor, and whether a future stored ACTIVE transition can make a tick refuse
before its cutover boundary.

## CAPABILITY_OR_EVIDENCE

A single truthful operational continuity projection, deterministic future-
cutover candidate selection, owner-facing alert and forward-only runbook
instructions, focused boundary tests, and Catalog relations to the exact
implementation and tests.

## ACCEPTANCE

- Historical same-family registrations outside the predecessor boundary are
  labeled HISTORICAL_OUT_OF_WINDOW and do not count as a usable successor.
- AUTHORIZED without a committed rollover and linked immutable transition
  proof does not clear the warning.
- An expired predecessor with no proven active successor remains an explicit
  actionable gap; it is never labeled RECOVERED merely because it is
  DRAINING.
- Tick candidates are selected by project_activation_as_of(row, now) using
  one captured UTC now; preserve all existing authority and append-only proof
  checks.
- Boundary tests cover a tick beginning just before cutover and completing
  after it, followed by a tick started after cutover, without false refusal or
  two accepting activations.
- Expired continuity gaps render as explicit recovery actions, not as an
  upcoming expiry or an implicit RECOVERED state.
- Existing alert, canonical operator runbook, and Catalog projections describe
  the same continuity semantics.

## NON-GOALS

No live VPS work, provider calls, credential reads, activation/authority
operations, SQLite schema, retention, campaign-limit or scientific-parameter
changes; no append-only history rewrite; no call_ledger optimization or live
commissioning; no replacement of previous task contracts.

## STOP

Stop after independent CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC and
OWNER_UX_CRITIC reviews, exact-head CI, and machine merge-readiness. Do not
proceed to the owner merge phrase or merge. Stop earlier if any listed stop
condition is reached.

## NEXT

After this checkpoint, propose separate contract
FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1 for call_ledger memory bounds.

## REPLAN_TRIGGER

Replan if truthful continuity requires changing immutable event semantics,
rewriting lifecycle history, changing scientific/source-data semantics, or
expanding beyond the managed write set.
