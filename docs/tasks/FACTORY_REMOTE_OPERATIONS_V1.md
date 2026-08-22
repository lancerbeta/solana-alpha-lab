---
task_id: FACTORY_REMOTE_OPERATIONS_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 37f66155738432dcd19ac366c930cadcf65170e8
  expected_upstream: origin/main
  expected_upstream_oid: 37f66155738432dcd19ac366c930cadcf65170e8
  expected_branch: cursor/factory-remote-operations
  dirty_mode: ALLOW_REPORTED
objective: Make Factory and paper/shadow bots unattended-operable on one ordinary Linux VPS with Git-SHA deploy, doctor/status, bounded rollback, independent-domain backup plus isolated restore, composed health, Telegram owner alerts, and a security baseline that forbids password SSH, root login, secret defaults, and a public admin surface, without the owner performing Linux administration.
managed_write_set:
  - docs/tasks/FACTORY_REMOTE_OPERATIONS_V1.md
  - catalog/schemas/factory_remote_operations.schema.json
  - configs/factory_remote_operations_v1.yaml
  - configs/factory_remote_ops/sshd_factory.conf
  - configs/factory_remote_ops/nftables_factory.conf
  - configs/factory_remote_ops/fail2ban_sshd.local
  - configs/factory_remote_ops/factory-remote-health.service
  - configs/factory_remote_ops/factory-remote-backup.service
  - configs/factory_remote_ops/factory-remote-backup.timer
  - configs/factory_remote_ops/factory-paper-heartbeat.service
  - configs/factory_remote_ops/factory-paper-heartbeat.timer
  - configs/factory_remote_ops/secrets.env.example
  - src/solana_alpha_lab/factory/remote_ops.py
  - scripts/factory_remote_doctor.py
  - scripts/factory_remote_install.py
  - tests/test_factory_remote_operations.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/factory_remote_operations/a3_acceptance_v1.json
  - docs/evidence/factory_remote_operations/a3_runtime_receipt_v1.json
  - docs/evidence/factory_remote_operations/a3_delivery_completion_evidence_v1.json
  - docs/evidence/factory_remote_operations/a3_delivery_independent_review_v1.json
  - docs/evidence/factory_remote_operations/a3_delivery_factory_fit_v1.json
  - docs/reports/factory_remote_operations/a3_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - VPS_PURCHASE_OR_CASH_WITHOUT_OWNER_PACKET
  - SECRET_IN_GIT_OR_RECEIPT_OR_TEMPLATE
  - SECRET_DEFAULT_IN_CODE
  - PASSWORD_SSH_OR_ROOT_LOGIN_ENABLED
  - PUBLIC_ADMIN_OR_NON_LOOPBACK_BIND
  - BACKUP_ON_SAME_VOLUME_CLAIMED_INDEPENDENT
  - GOOGLE_DRIVE_AS_PRIMARY_BACKUP
  - POSTGRES_OR_REMOTE_OLTP_MIGRATION
  - KUBERNETES_HA_OR_SENTRY_INSTALL
  - WALLET_SIGNER_TX_OR_LIVE_FILL
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - FACTORY_CORE_RUNNER_CHANGE
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CTRL-FACTORY-V1-PRODUCTION-LITE-RUNTIME-001
    - CONFIG-FACTORY-V1-PRODUCTION-LITE-RUNTIME-001
    - EVIDENCE-FACTORY-V1-PRODUCTION-LITE-RUNTIME-ACCEPTANCE-001
    - EVIDENCE-EARLY-STATE-PAPER-ACCEPTANCE-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_v1_production_lite_runtime/a3_delivery_completion_evidence_v1.json
      - docs/evidence/early_state_paper/a1_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_REMOTE_OPERATIONS_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

Owner named `muv-5` ATOM 3 and asked to execute after the Habr incident
case. Predecessor on `main` is `LOCAL_LINUX_SHAPED_PROOF` with backup
`EXPLICIT_UNKNOWN` and purchase `LATER_EXTERNAL_AUTHORITY`. Paper/shadow
bots now exist as the named consumer.

PATCH versus the memo:

1. Security baseline is first-class DoD, not a later hardening pass.
   Password SSH, root login, shared secret defaults, public admin, and
   backup-on-the-same-volume are fail-closed rejects.
2. This atom delivers the Git-native remote-ops capability and offline
   fault-injection proofs first. Live VPS purchase, SSH, Telegram token
   and backup-sink credential remain **one** owner infrastructure packet,
   not five preparatory atoms. Buying a host before the doctor/install
   path exists would repeat infrastructure theatre.
3. SQLite stays. Postgres is a stop, not an upgrade. Headroom is VPS
   RAM/disk plus Cherry scale-up, not a database migration.
4. Google Drive 5TB is `OPTIONAL_COLD_COPY`, not the independent backup
   domain and not DoD. Primary backup is a content-addressed bundle on a
   sink that does not share a parent with the live stores.
5. Cherry Servers remains the selected provider: crypto payment still
   documented; `CLOUD_VPS_1` (1 GB / ~$3.51) is rejected; selected floor
   is `CLOUD_VPS_4_GEN2` (4 vCPU / 4 GB / 80 GB, scale RAM to 6 GB and
   disk to 100 GB). Upgrade path is Cherry in-place scale, then Cloud VDS,
   then rehost proof — not a second product architecture.

`strongest_rejected_alternative`: purchase-only atom, or a public Cockpit
with an auth service. Rejected: no consumer of a naked VM, and a public
admin surface is the Habr failure mode.

## PRD-lite

- **Outcome that must become true:** the owner can leave Factory and
  paper/shadow bots on one remote Linux host without opening an IDE, and
  be woken when the system is no longer safe or valid. The owner performs
  zero Linux administration after the one infrastructure packet.
- **Why now:** Atom 2 closed research-to-paper. Local Linux-shaped proof
  already covers restart/rollback/rehost. The remaining gap is unattended
  remote operation plus backup plus composed monitoring plus alerts.
- **Named consumer:** owner operating paper/shadow overnight; agent
  reading `factory_remote_doctor.py --json`.
- **Success observable:** offline
  `FACTORY_REMOTE_OPERATIONS_GIT_READY` with security templates, doctor,
  independent-domain backup restore, composed health, alert dedup, and a
  copy-exact owner packet. Live
  `FACTORY_REMOTE_OPERATIONS_PASS` only after that packet returns.
- **Cheapest falsifier:** health becomes HEALTHY from process_alive
  alone; a secret default exists in code; a unit binds 0.0.0.0; backup
  sink shares the live store parent and is labelled independent;
  duplicate incident sends two alerts.
- **Non-goals:** HA, Kubernetes, Postgres, ClickHouse, public admin,
  Sentry, metrics zoo, Drive-as-primary, wallet/signer/tx, micro-live,
  `FACTORY_V1_OPERATIONAL_READY`, owner clicking through Linux.

## SSD-lite

- **Baseline truth:** `origin/main` `37f66155738432dcd19ac366c930cadcf65170e8`.
  Production-lite runtime PASS. Paper plane PASS. Backup unknown.
- **Design:** ADOPT systemd, sshd, nftables, fail2ban. WRAP existing
  FactoryRuntime + SQLite snapshot + Task-18 content-addressed backup
  pattern + Telegram Bot API HTTP. FORK nothing. BUILD the composed
  health/doctor/alert-dedup contract.
- **Topology:** one VPS, loopback Workbench, SSH tunnel only, health
  loop, paper heartbeat, backup timer, independent sink.
- **Invariants:** Git remains scientific truth; SQLite is operational
  only; process_alive alone is never HEALTHY; secrets have no defaults
  and never enter Git/receipts; Cockpit/Workbench bind 127.0.0.1;
  independent backup is a different parent directory; one secret name
  per sink.
- **Failure modes:** `UNHEALTHY_NOT_RUNNING`;
  `UNHEALTHY_SECURITY_BASELINE`; `DEGRADED_STALE_DATA`;
  `DEGRADED_BOT_STALL`; `DEGRADED_BACKUP_AGE`;
  `UNHEALTHY_UNRESOLVED_POSITION`; `ALERT_SINK_UNCONFIGURED`;
  `BACKUP_SINK_NOT_INDEPENDENT`.
- **Validation:** fail-closed tests, zero network, zero credentials.
  Windows CI proves contracts without executing systemd. Live host
  proof is gated by the owner packet.
- **Rollback of this atom:** revert the branch. VPS bytes are not Git
  truth.

## Decision capsule

- `DECISION_DELTA:` remote operations become a Git-owned fail-closed
  capability with a security baseline taken from the Habr class of
  failures, and live hosting is one owner packet not a shopping trip.
- `UNCERTAINTY_REMOVED:` whether Factory can show agent-readable health,
  restore from an independent backup, dedup owner alerts, and refuse the
  textbook insecure defaults before a VPS exists.
- `CAPABILITY_OR_EVIDENCE:` `CAP-FACTORY-REMOTE-OPERATIONS-001`, doctor
  CLI, install dry-run, backup restore proof, alert dedup, owner packet.
- `STOP:` before any purchase, SSH, Telegram token read, or
  operational-ready claim. After Git-side proofs, at exact-head CI for
  the merge phrase, unless the owner packet has already returned and
  live proof is in-scope for the same contract.
- `NEXT:` owner completes the infrastructure packet; then live fault
  injection on the real host. Atom 4 commissioning stays blocked on
  remote ops being actually hosted.
- `ADOPTION_ROUTE=ADOPT_SYSTEMD_SSHD_NFT_FAIL2BAN_WRAP_RUNTIME_BACKUP_TELEGRAM`
- `REPLAN_TRIGGER:` second consecutive preparatory-only merge; cheapest
  falsifier cannot run; provider pivot away from Cherry after this
  freeze; Postgres/K8s pivot; evidence/time budget exceeded.

## Definition of Done

1. Config+schema freeze Cherry `CLOUD_VPS_4_GEN2` (not VPS 1), Git-SHA
   deploy, loopback bind, RPO 24h / RTO 12h, independent backup sink,
   Telegram env-name-only alert sink, `process_alive_alone_is_not_healthy`.
2. Security templates refuse password SSH, root login, 0.0.0.0 bind, and
   secret files in Git. Code refuses secret defaults.
3. Doctor CLI prints JSON: process, freshness, provider, bot progress,
   unresolved positions, reconciliation, backup age, disk, security,
   next_safe_action. Never HEALTHY from process_alive alone.
4. Backup packager writes a content-addressed bundle to an independent
   sink; isolated restore matches hashes; same-parent sink is rejected.
5. Alert emitter sends WHAT / WHY / SAFE STATE / ACTION once per
   incident_key.
6. Offline fault injection: kill process, stale heartbeat, stalled bot,
   restore, duplicate incident.
7. Owner packet names the exact Cherry SKU, Ubuntu 24.04, SSH key-only,
   Telegram bot, backup sink, and the phrase that returns authority.
   Owner does no Linux administration.
8. No operational-ready claim. No VPS purchase in this write set.

## Merge evidence

`exact_role_paths.DELIVERY_EVIDENCE` at merge must also list:

`docs/evidence/factory_remote_operations/a3_delivery_completion_evidence_v1.json`
`docs/evidence/factory_remote_operations/a3_delivery_independent_review_v1.json`
`docs/evidence/factory_remote_operations/a3_delivery_factory_fit_v1.json`
