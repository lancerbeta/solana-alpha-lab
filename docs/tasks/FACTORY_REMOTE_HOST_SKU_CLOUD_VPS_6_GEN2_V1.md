---
task_id: FACTORY_REMOTE_HOST_SKU_CLOUD_VPS_6_GEN2_V1
task_version: '1.0'
status: READY
as_of: '2026-09-02'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 077a1f9d508683a3f9341cc5de15f4411f2b6130
  expected_upstream: origin/main
  expected_upstream_oid: 077a1f9d508683a3f9341cc5de15f4411f2b6130
  expected_branch: cursor/factory-remote-host-sku-cloud-vps-6-gen2
  dirty_mode: ALLOW_REPORTED

objective: >-
  Locator-only update of factory-remote-ops live operator SKU from
  CLOUD_VPS_4_GEN2 to CLOUD_VPS_6_GEN2 after Cherry same-region Upgrade,
  with harness evidence ceremony for guarded merge. Keep ipv4, hostname,
  SSH, deploy root, instance id 973818, and collector protocol unchanged.
  Do not unfreeze purchase-floor configs/schemas.

managed_write_set:
  - docs/tasks/FACTORY_REMOTE_HOST_SKU_CLOUD_VPS_6_GEN2_V1.md
  - docs/operator/factory_remote_host_v1.yaml
  - docs/operator/FACTORY_REMOTE_HOST.md
  - catalog/assets/core.yaml
  - docs/evidence/factory_remote_host_sku_cloud_vps_6_gen2/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_remote_host_sku_cloud_vps_6_gen2/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_remote_host_sku_cloud_vps_6_gen2/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_remote_host_sku_cloud_vps_6_gen2/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - PURCHASE_FLOOR_CONFIG_OR_SCHEMA_MUTATION
  - IPV4_OR_HOSTNAME_OR_SSH_CHANGE
  - COLLECTOR_PROTOCOL_CHANGE
  - CHERRY_INSTANCE_ID_CHANGE_WITHOUT_PORTAL_PROOF
  - PROVIDER_API_RPC_WSS_REQUIRED
  - WALLET_SIGNER_OR_CASH_SPEND

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
      - docs/evidence/factory_remote_host_sku_cloud_vps_6_gen2/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_remote_host_sku_cloud_vps_6_gen2/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_remote_host_sku_cloud_vps_6_gen2/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_REMOTE_HOST_SKU_CLOUD_VPS_6_GEN2_V1

## Entry / outcome

- `DECISION_DELTA`: live operator locator SKU reflects post-Upgrade `CLOUD_VPS_6_GEN2`
- `UNCERTAINTY_REMOVED`: Git locator no longer claims stale `CLOUD_VPS_4_GEN2` after measured host proof
- `CAPABILITY_OR_EVIDENCE`: hash-bound delivery receipt for locator-only bytes
- `STOP`: exact-head CI + ordinary merge gate
- `NEXT`: none from this atom; doctor JSON may still emit purchase-floor `CLOUD_VPS_4_GEN2` until later schema unfreeze

## Live proof (2026-09-02, SSH read-only)

- hostname=`factory-remote-ops`
- nproc=`6`
- Mem=`5.8Gi`
- `/dev/vda`=`100G`, `/`=`96G`
- ipv4 unchanged `5.199.174.153`
- `cherry_instance_id` kept `973818`

## Non-claims

- No purchase-floor config/schema unfreeze
- No collector protocol / deploy root / SSH identity change
- No secrets, wallet, provider spend, or deployment mutation in this atom
