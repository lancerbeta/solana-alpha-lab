---
task_id: FACTORY_V1_PRODUCTION_LITE_LINUX_RUNTIME_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9bf0a6f7f0f77b8af783e30d187f329d61b094dd
  expected_upstream: origin/main
  expected_upstream_oid: 9bf0a6f7f0f77b8af783e30d187f329d61b094dd
  expected_branch: cursor/factory-v1-production-lite-runtime
  dirty_mode: ALLOW_REPORTED
objective: Prove a VPS-shaped production-lite Linux runtime for Factory so restart recovery, deploy version, rollback, and clean rehost are owner-visible without buying a provider, deploying, or claiming operational-ready.
managed_write_set:
  - docs/tasks/FACTORY_V1_PRODUCTION_LITE_LINUX_RUNTIME_V1.md
  - catalog/schemas/factory_v1_production_lite_runtime.schema.json
  - configs/factory_v1_production_lite_runtime_v1.yaml
  - configs/factory_v1_linux_runtime/factory-v1-workbench.service
  - src/solana_alpha_lab/factory/operational_store.py
  - src/solana_alpha_lab/factory/runtime.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/read_model.py
  - src/solana_alpha_lab/factory/workbench.py
  - scripts/run_factory_runtime.py
  - tests/test_factory_v1_production_lite_runtime.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_v1_production_lite_runtime/a3_factory_v1_runtime_acceptance_v1.json
  - docs/evidence/factory_v1_production_lite_runtime/a3_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_production_lite_runtime/a3_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_production_lite_runtime/a3_delivery_factory_fit_v1.json
  - docs/reports/factory_v1_production_lite_runtime/a3_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - LIVE_JUPITER_OR_CREDENTIAL_READ
  - MARKET_CAPTURE_OR_RECAPTURE
  - MOVE_3_OR_NEW_RESEARCH_LADDER
  - PRODUCTION_REGISTRY_SEED
  - NEW_UI_PACKAGE_ADOPTION
  - KUBERNETES_OR_MICROSERVICES
  - POSTGRES_OR_REMOTE_OLTP_MIGRATION
  - WALLET_SIGNER_TX_OR_CASH
  - SENTRY_OR_COCKPIT_BREADTH
  - TASK35A_PARALLEL_CHAIN
  - SECOND_TRUTH_STORE
  - BACKUP_STATUS_FALSIFIED_AS_DRIVE_PASS
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
    - CONFIG-FACTORY-V1-PRODUCT-KERNEL-001
    - EVIDENCE-FACTORY-V1-COMMISSIONING-ACCEPTANCE-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_v1_production_lite_runtime/a3_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_V1_PRODUCTION_LITE_LINUX_RUNTIME_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=PATCH`

ATOM 2 NEXT named "ATOM 3 VPS". Readiness runtime wants reproducible remote
runtime, restart recovery, deploy version, rollback, clean rehost, RPO 24h
and RTO 12h on one ordinary supported Linux VPS. The same contract sets
`actual_vps_provider_purchase: LATER_EXTERNAL_AUTHORITY`. ARCH-INTENT-005
`authority.deployment: false`. Buying or SSHing a VPS now would trip the
owner-attention gate, spend cash, and still leave Factory unproved on
restart/rollback.

PATCH: this atom is the VPS-shaped Linux runtime proof, not a provider
purchase. A later exact owner gate may host the same unit on a real VPS.

Owner trigger: `го след атом` plus write PRD+SSD and execute. That is not a
Jupiter phrase, not a VPS purchase, and not `FACTORY_V1_OPERATIONAL_READY`.

## PRD-lite

- **Outcome that must become true:** the owner can see deploy version, prove
  restart recovery, prove rollback, and prove clean rehost of Factory on a
  Linux-shaped runtime, and health is never "process is alive".
- **Why now:** commissioning live cycle is on `main`. The named NEXT is the
  production-lite runtime objective. Cockpit breadth without runtime still
  leaves unattended recovery unproved. A purchase-only atom would be
  preparatory-only.
- **Downstream consumer:** later real VPS host / ATOM 4 Cockpit remain
  horizon. This atom's consumer is the owner operating Factory after a
  process death or machine replacement without Git archaeology.
- **Current gap:** SQLite job restart exists, but there is no version pin,
  no rollback snapshot, no rehost allowlist, no systemd-shaped unit, and no
  health projection that refuses process-alive-only.
- **Success observable:** isolated tests plus one owner readout showing
  `PRODUCTION_LITE_LINUX_RUNTIME_PROOF_PASS` with backup still
  `EXPLICIT_UNKNOWN`.
- **Invalidation / cheapest falsifier:** health becomes HEALTHY from
  process_alive alone; rollback mutates Git science; rehost requires a
  credential or Jupiter call; implementation buys/deploys a VPS; milestone
  is claimed ready.
- **Non-goals:** `FACTORY_V1_OPERATIONAL_READY`, actual VPS purchase, SSH,
  DNS, deploy credentials, Kubernetes, Cockpit breadth, Sentry install,
  Drive backup, Postgres, alpha, MOVE 3, live Jupiter, production registry
  seed, NiceGUI/Streamlit/FastAPI, kernel `provider_calls: true`.

Frozen runtime hypothesis (product, not market):

- ID: `HYP-FACTORY-V1-PRODUCTION-LITE-LINUX-RUNTIME-V1`
- Experiment: `EXP-FACTORY-V1-PRODUCTION-LITE-LINUX-RUNTIME-001`
- Capability: `CAP-FACTORY-V1-LINUX-SHAPED-RUNTIME-PROOF-001`
- Product question: can Factory recover on a VPS-shaped Linux runtime
  without a new scientific byte?
- Estimand: recovery of Git-bound commissioning COMPLETE plus visible
  deploy version after restart, rollback, and rehost; not PnL.
- Population: one ordinary Linux process model (systemd unit template +
  local stdlib proof). Windows CI proves the same contracts without
  executing systemd.

## SSD-lite

- **Baseline truth:** `origin/main`
  `9bf0a6f7f0f77b8af783e30d187f329d61b094dd`. ATOM 1 golden replay PASS.
  ATOM 2 commissioning PASS. MOVE 3 not earned. Production registries
  empty. Kernel `provider_calls: false`. Purchase later.
- **Design:** ADOPT existing FactoryApplication, SQLite ops store, Git
  receipts, and a later-host systemd unit template. WRAP them with a
  stdlib runtime supervisor: sqlite backup snapshot, restart reopen,
  version pin in operational events, rehost allowlist copy. FORK nothing
  in capture. BUILD no new scientific pipeline and no UI package.
- **Invariants:** Git/Catalog/receipts remain scientific truth; SQLite/UI
  remain projection; process_alive alone is not healthy; backup stays
  `EXPLICIT_UNKNOWN` unless a later exact backup atom proves Drive
  read-back; localhost bind only; no `.env`; no provider calls.
- **Affected surfaces:** runtime config+schema, systemd unit template,
  operational_store runtime events, runtime supervisor, read-model
  `runtime` projection, Workbench rows, CLI proof entry. Kernel schema
  stays ATOM 1. Commissioning receipts stay hash-bound.
- **Failure modes:** `UNHEALTHY_NOT_RUNNING`;
  `DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN` when the process is up but
  proofs/backup are missing; `UNHEALTHY_EVIDENCE_MISSING` on Git mismatch;
  `UNHEALTHY_VERSION_MISSING`; rollback without a snapshot is
  `ROLLBACK_SNAPSHOT_MISSING`.
- **Validation:** fail-closed tests with zero network; restart keeps
  COMPLETE without recapture; rollback restores a snapshot after a wiped
  store; rehost isolated root starts without phrase and projects Git
  COMPLETE; systemd unit parser rejects public bind and secret files.
- **Rollback of this atom:** revert the branch. SQLite under `local/` is
  not Git truth.

## Decision capsule

- `DECISION_DELTA`: treat ATOM 3 as a Linux-shaped runtime proof, not a
  VPS purchase, and not Cockpit.
- `UNCERTAINTY_REMOVED`: whether Factory can show version, recover from
  process death, roll back operational state, and rehost from Git bytes
  without a provider.
- `CAPABILITY_OR_EVIDENCE`: `CAP-FACTORY-V1-LINUX-SHAPED-RUNTIME-PROOF-001`,
  systemd unit template, supervisor proofs, owner runtime packet.
- `STOP`: before any purchase, SSH, deploy credential, Jupiter, or
  operational-ready claim. After proofs, at exact-head CI for the merge
  phrase.
- `NEXT`: real VPS host only under a later exact owner gate, or ATOM 4
  Cockpit if the owner prefers the operating surface next. Not MOVE 3.
- `ADOPTION_ROUTE=WRAP_EXISTING_FACTORY_AND_SQLITE_ADOPT_SYSTEMD_UNIT_TEMPLATE`
- `REPLAN_TRIGGER`: second consecutive preparatory-only merge; cheapest
  falsifier cannot run; purchase/deploy pivot; Sentry/Cockpit install
  without a named incident consumer; evidence/time budget exceeded.

## Definition of Done

1. Runtime config+schema freeze VPS-shaped target, purchase later,
   localhost bind, deploy version, previous version, RPO/RTO, rehost
   allowlist, and `process_alive_alone_is_not_healthy: true`.
2. systemd unit template is parseable, binds loopback, restarts on
   failure, and carries no secrets.
3. Operational store records runtime events; sqlite backup snapshot is
   the rollback primitive.
4. Restart recovers a COMPLETE commissioning job from Git+SQLite with
   zero provider calls.
5. Clean rehost from the allowlist, empty SQLite, no phrase, projects
   COMPLETE from Git receipts.
6. Read model/Workbench show runtime health that cannot be HEALTHY from
   process_alive alone; backup remains `EXPLICIT_UNKNOWN`.
7. No production registry seed. No operational-ready claim. No VPS.

## Merge evidence

`exact_role_paths.DELIVERY_EVIDENCE` at merge must list exactly one
`smial.delivery-completion-evidence` for this atom:

`docs/evidence/factory_v1_production_lite_runtime/a3_delivery_completion_evidence_v1.json`
