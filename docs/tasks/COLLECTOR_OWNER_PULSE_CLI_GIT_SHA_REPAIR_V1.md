---
task_id: COLLECTOR_OWNER_PULSE_CLI_GIT_SHA_REPAIR_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ebb0a351cce2ce6ef0becd8b7025d5a4dfc99faa
  expected_upstream: origin/main
  expected_upstream_oid: ebb0a351cce2ce6ef0becd8b7025d5a4dfc99faa
  expected_branch: cursor/collector-owner-pulse-cli-git-sha-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair collector_owner_pulse CLI producer SHA binding to canonical
  git_sha(root, configured) so dry-run works on Git checkouts and sanctioned
  no-.git exact-SHA deploy roots without a second resolver.
managed_write_set:
- docs/tasks/COLLECTOR_OWNER_PULSE_CLI_GIT_SHA_REPAIR_V1.md
- scripts/collector_owner_pulse.py
- tests/test_collector_owner_pulse_cli_git_sha_repair.py
- docs/evidence/collector_owner_pulse_cli_git_sha_repair/a1_delivery_completion_evidence_v1.json
- docs/evidence/collector_owner_pulse_cli_git_sha_repair/a1_delivery_independent_review_v1.json
- docs/evidence/collector_owner_pulse_cli_git_sha_repair/a1_delivery_factory_fit_v1.json
- docs/reports/collector_owner_pulse_cli_git_sha_repair/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_VPS_OR_DEPLOY_REQUIRED
- STOP_AUTHORIZE_OR_ACTIVATE
- STOP_SSH_OR_DURABILITY_OR_JUPITER_SURFACE
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- WALLET_BUILD_EXECUTE_TRANSACTION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/collector_owner_pulse_cli_git_sha_repair/a1_delivery_completion_evidence_v1.json
    - docs/evidence/collector_owner_pulse_cli_git_sha_repair/a1_delivery_independent_review_v1.json
    - docs/evidence/collector_owner_pulse_cli_git_sha_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_OWNER_PULSE_CLI_GIT_SHA_REPAIR_V1

## SPEC_ROUTE

`NONE` — adapter binding only; reuse existing `git_sha(root, configured)`.

## DECISION_DELTA

Daily Owner Pulse CLI must resolve producer identity with the same precedence as
ObservationSchedule: runtime `producer_git_sha` → Git HEAD → `.factory_deploy_sha`.

## UNCERTAINTY_REMOVED

Whether commissioning preflight `REUSABLE_PRODUCT_DEFECT_FOUND` was a CLI adapter
miss versus a runtime API change.

## CAPABILITY_OR_EVIDENCE

Fixed CLI binding plus executable-surface regression covering Git checkout,
no-.git deploy pin, and fail-closed missing/malformed deploy SHA.

## STOP

Exact merge gate. No VPS deploy, SSH, durability, Jupiter, or campaign authority.

## NEXT

Re-run `FACTORY_LIVE_BASELINE_COMMISSIONING_PREFLIGHT_V1` from repaired main.
