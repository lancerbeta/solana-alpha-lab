---
task_id: MUTABLE_BACKUP_ZIP64_MAINLINE_PROPAGATION_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-19'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: f0425162af393b790d6f6fb4c3006c7669778d29
  expected_upstream: origin/main
  expected_upstream_oid: f0425162af393b790d6f6fb4c3006c7669778d29
  expected_branch: cursor/mutable-backup-zip64-repair-v1
  dirty_mode: FORBIDDEN

objective: >-
  Bind the already-landed mainline ZIP64 backup repair to the current
  Delivery Harness so PR 322 can enter merge-readiness. Root cause: a
  streamed ZIP entry larger than ZIP64_LIMIT failed unless
  archive.open(..., force_zip64=True). Scope is remote_ops.py, the
  ZIP64 regression test, and the deterministic MODULE-FACTORY-REMOTE-OPS-001
  catalog hash. Live production already recovered on ba7f3b72 after one
  manual >2 GiB backup PASS. This PR does not deploy.

managed_write_set:
  - docs/tasks/MUTABLE_BACKUP_ZIP64_MAINLINE_PROPAGATION_V1.md
  - src/solana_alpha_lab/factory/remote_ops.py
  - tests/test_mutable_backup_zip64_repair_v1.py
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/mutable_backup_zip64_mainline_propagation/a1_delivery_completion_evidence_v1.json
  - docs/evidence/mutable_backup_zip64_mainline_propagation/a1_delivery_independent_review_v1.json
  - docs/evidence/mutable_backup_zip64_mainline_propagation/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - RUNTIME_SEMANTICS_CHANGE_BEYOND_FORCE_ZIP64
  - TIMER_OR_BACKUP_ARCHITECTURE_CHANGE
  - VPS_OR_C2_CHANGE
  - PRODUCTION_DEPLOYMENT_IN_THIS_PR
  - PROVIDER_CALL
  - REAL_MONEY_OR_WALLET
  - NEW_PROVIDER_OR_ATOM

context_requirements:
  catalog_asset_ids:
    - MODULE-FACTORY-REMOTE-OPS-001
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/mutable_backup_zip64_mainline_propagation/a1_delivery_completion_evidence_v1.json
      - docs/evidence/mutable_backup_zip64_mainline_propagation/a1_delivery_independent_review_v1.json
      - docs/evidence/mutable_backup_zip64_mainline_propagation/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# MUTABLE_BACKUP_ZIP64_MAINLINE_PROPAGATION_V1

SPEC_ROUTE=NONE. This contract describes an already executed operational
packaging outcome. It does not authorize a new implementation.

## Already-executed outcome

- **Root cause:** streamed backup ZIP entry larger than `ZIP64_LIMIT` failed
  unless `archive.open(..., force_zip64=True)`.
- **Mainline implementation:** `force_zip64=True` in `_stream_zip_entry`
  (`f8e6d173`). Do not change that runtime meaning.
- **Scope:** `remote_ops.py` + ZIP64 regression test + deterministic
  `MODULE-FACTORY-REMOTE-OPS-001` catalog hash.
- **Evidence:** live production recovery on `ba7f3b72`; one manual `>2 GiB`
  backup PASS.
- **Rollback:** revert the exact implementation commit.
- **Semantic impact:** operational packaging only.
- **Production deployment is not part of this PR.**

## Non-goals

No timer, config, backup-architecture, VPS, or C2 changes. No new provider
or atom. No wallet, signer, or transaction.

## Decision packet

- **DECISION_DELTA:** mainline backup streaming always requests ZIP64-safe
  writes; harness binding is documentation/evidence only.
- **UNCERTAINTY_REMOVED:** whether the already-proven ZIP64 repair can enter
  merge-readiness without changing `f8e6d173` semantics.
- **CAPABILITY_OR_EVIDENCE:** force_zip64 streaming + regression test +
  catalog hash + live `ba7f3b72` backup PASS.
- **STOP:** merge-readiness; no owner merge phrase in this atom; no deploy.
- **NEXT:** owner merge gate for PR 322, then a separately authorized deploy
  if live pin still needs mainline.
- **REPLAN_TRIGGER:** any need to change runtime meaning, timer/config, VPS,
  C2, or to treat this PR as a production deploy.
