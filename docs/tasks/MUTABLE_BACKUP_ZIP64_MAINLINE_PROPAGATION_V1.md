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
  expected_base: e9933b0b3ea3bbc9dea05dc11f669caaa68398bc
  expected_upstream: origin/main
  expected_upstream_oid: e9933b0b3ea3bbc9dea05dc11f669caaa68398bc
  expected_branch: cursor/mutable-backup-zip64-repair-v1
  dirty_mode: FORBIDDEN

objective: >-
  Bind the already-on-branch ZIP64 backup repair at f8e6d173 to the
  current Delivery Harness so PR 322 can enter merge-readiness. Versus
  origin/main the candidate includes archive.open(..., force_zip64=True)
  because a streamed ZIP entry larger than ZIP64_LIMIT failed without it.
  Scope is remote_ops.py, the ZIP64 regression test, and the deterministic
  MODULE-FACTORY-REMOTE-OPS-001 catalog hash. Live ba7f3b72 recovery and
  the manual >2 GiB backup PASS are external evidence, not a capability of
  this head. This PR does not deploy. Do not rewrite f8e6d173.

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
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

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

SPEC_ROUTE=NONE for this atom: do not rewrite `f8e6d173`. Versus
`origin/main` (`f0425162`) the candidate still contains that one-line ZIP64
flag land plus this harness bind. Semantic impact is operational ZIP
serialization, not a scientific estimand. Live `ba7f3b72` recovery is
external evidence, not a capability of this head. This PR does not deploy.

## Outcome versus origin/main

- **Root cause:** streamed backup ZIP entry larger than `ZIP64_LIMIT` failed
  unless `archive.open(..., force_zip64=True)`.
- **Mainline implementation already on this branch:** `force_zip64=True` in
  `_stream_zip_entry` (`f8e6d173`). Do not change that runtime meaning.
- **This atom:** add the canonical task contract and DELIVERY_EVIDENCE so
  current harness merge-readiness can run.
- **Scope:** `remote_ops.py` + ZIP64 regression test + deterministic
  `MODULE-FACTORY-REMOTE-OPS-001` catalog hash.
- **In-repo falsifier:** `Zip64RequiredFile` plus source pin of
  `force_zip64=True`. This head does not claim a `>ZIP64_LIMIT` write.
- **External evidence, not this head:** live production recovery on
  `ba7f3b72`; one manual `>2 GiB` backup PASS.
- **Rollback:** revert the exact implementation commit.
- **Semantic impact:** operational packaging / ZIP write-flag only.
- **Production deployment is not part of this PR.**

## Non-goals

No timer, config, backup-architecture, VPS, or C2 changes. No new provider
or atom. No wallet, signer, or transaction. No 2 GiB fixture. No deploy.

## Decision packet

- **DECISION_DELTA:** versus main, streamed backup writes request ZIP64;
  this atom only binds harness evidence around that already-on-branch land.
- **UNCERTAINTY_REMOVED:** whether PR 322 can enter merge-readiness without
  changing `f8e6d173` semantics.
- **CAPABILITY_OR_EVIDENCE:** force_zip64 streaming + in-repo ZIP64
  regression test + catalog hash. Live `ba7f3b72` backup remains external.
- **STOP:** merge-readiness; no owner merge phrase in this atom; no deploy.
- **NEXT:** owner merge gate for PR 322, then a separately authorized deploy
  if live pin still needs mainline.
- **REPLAN_TRIGGER:** any need to change runtime meaning, timer/config, VPS,
  C2, or to treat this PR as a production deploy.
