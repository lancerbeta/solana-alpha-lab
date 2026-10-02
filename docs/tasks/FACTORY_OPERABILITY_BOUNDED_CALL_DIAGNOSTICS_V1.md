---
task_id: FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1
task_version: "1.0"
status: READY
as_of: "2026-10-02"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CODEX_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5263abdd327455f239767c0c31855909f90435b7
  expected_upstream: origin/main
  expected_upstream_oid: 5263abdd327455f239767c0c31855909f90435b7
  expected_branch: cursor/factory-operability-bounded-call-diagnostics-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Deliver one offline Git PR that removes unbounded historical call payload
  materialization from collector operability, preserves monitoring truth,
  bounds watch/pulse damage, makes heartbeat conditional on fresh watch
  evidence, and gives the owner a precise deploy/rollback procedure.
managed_write_set:
  - docs/tasks/FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1.md
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - src/solana_alpha_lab/factory/collector_read_model.py
  - src/solana_alpha_lab/factory/due_pressure.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/collector_owner_pulse.py
  - src/solana_alpha_lab/factory/external_heartbeat.py
  - scripts/factory_operability_watch.py
  - scripts/collector_owner_pulse.py
  - scripts/factory_external_heartbeat.py
  - configs/factory_remote_ops/factory-operability-watch.service
  - configs/factory_remote_ops/factory-collector-owner-pulse.service
  - tests/test_factory_operability_bounded_call_diagnostics_v1.py
  - tests/test_factory_unattended_operability_closure_v1.py
  - tests/test_factory_operability_signal_calibration_v1.py
  - tests/test_factory_operability_memory_collision_repair_v1.py
  - tests/test_collector_operability_retention_and_owner_pulse.py
  - tests/test_observation_schedule_store.py
  - tests/test_collector_owner_pulse_cli_git_sha_repair.py
  - tests/operability_bounded_call_profile.py
  - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - docs/evidence/factory_operability_bounded_call_diagnostics/a1_resource_profile_v1.json
  - docs/evidence/factory_operability_bounded_call_diagnostics/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_operability_bounded_call_diagnostics/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_operability_bounded_call_diagnostics/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/factory_operability_bounded_call_diagnostics/a1_owner_readout_v1.md
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - MACHINE_ENTRY_GATE_REJECTED_OWNER_NAMED_CONTRACT
  - PROVIDER_API_RPC_OR_REAL_TELEGRAM_CALL_REQUIRED
  - LIVE_SQLITE_OR_SCIENTIFIC_DATA_MUTATION
  - RETENTION_DELETE_OR_CAMPAIGN_AUTHORITY_CHANGE
  - NEW_MONITORING_SERVICE_OR_DEPENDENCY_REQUIRED
  - LIVE_DEPLOY_OR_VPS_MUTATION
  - UNRESOLVED_MONITORING_TRUTH_CONFLICT
  - EXACT_OWNER_MERGE_PHRASE_AFTER_CI_AND_MERGE_READINESS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
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
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/tasks/FACTORY_OPERABILITY_MEMORY_COLLISION_REPAIR_V1.md
      - docs/tasks/FACTORY_OPERABILITY_SIGNAL_CALIBRATION_V1.md
      - src/solana_alpha_lab/factory/observation_schedule_store.py
      - src/solana_alpha_lab/factory/collector_read_model.py
      - src/solana_alpha_lab/factory/collector_operational_packet.py
      - src/solana_alpha_lab/factory/operability_watch.py
      - src/solana_alpha_lab/factory/external_heartbeat.py
      - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_operability_bounded_call_diagnostics/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_operability_bounded_call_diagnostics/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_operability_bounded_call_diagnostics/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1

## SPEC_ROUTE

`BOTH`: PRD-lite and the bounded design below live in this exact contract.
Client: Codex; route `DIRECT_CODEX_DELIVERY`; branch name follows owner input.
No new skill/plugin/connector/MCP/automation. Existing Delivery Harness,
git/gh, uv, SQLite, Catalog, snapshots and fake transports suffice.

## ENTRY VERDICT

`START_WITH_PATCH`: executing client selects CODEX; the requested branch is
preserved. Include the direct due-pressure helper for bounded read-model
iteration. Preflight found a SEPARATE Catalog shadow pin in the named TASK-21
evidence: include that exact file solely for mechanical SHA/bytes re-binding
to the changed Catalog blob. Historical acceptance and scientific fields remain
frozen. All provider/live/external exclusions remain frozen.

## Task Outcome Brief

- Owner decision: accept a Git capability ready for separate live commissioning.
- Named consumers: 15-minute watch, daily Telegram pulse, existing external heartbeat,
  and the operator diagnosing an operability OOM in one minute.
- Cheapest falsifier: patch `list_calls` to fail and run read model, full packet,
  watch and pulse; then double old large-payload history with the recent window fixed.
- Product outcome: collector monitoring can report without materializing historical
  call payloads; report death suppresses heartbeat; operator has exact recovery steps.
- Evidence budget: local synthetic stores only; four consumer profiles BEFORE/AFTER,
  edge parity, scale profiles, fake delivery/retry/recovery and four isolated critics.
- Replan trigger: an exclusion is needed, semantics cannot be preserved with bounded
  memory, or another full-packet hotspot prevents the resource thresholds.
- Terminal outcomes: `GIT_READY_FOR_OWNER_PHRASE` or an exact typed blocker;
  no live resource/Telegram/continuity claim from local fixture evidence.

## Bounded design and DoD

1. Read diagnostics via bounded SQL projection and streaming aggregation: no all-call
   list, historical payload decode, `fetchall` or full fallback in the operational path.
   Keep 24h counts, campaign scope, source-poll freshness, STARTED, per-primitive
   recovery, equal/invalid/future timestamp handling; unprovable truth is UNKNOWN.
2. Profile read model, full packet, watch dry-run and pulse dry-run in isolated
   processes: wall time, peak RSS, rows read and payloads decoded. Record fixture
   bytes and construction. Double old history without changing recent observations;
   memory must not scale with historical payload bytes. Before recommending timer
   enablement, both watch and pulse must be <512 MiB and <120s on representative
   local fixtures. These results never prove live MemoryPeak.
3. Preserve the previous source-snapshot/RDP memory repair and provider recovery
   calibration. Do not change retention, science or collector/provider behavior.
   Add no index without copy-side build/time/space/lock evidence; any migration
   belongs in a separate gated deployment step.
4. Both oneshot service templates gain `MemoryMax=768M`, `TimeoutStartSec=180s`;
   watch cadence stays 15 minutes. Heartbeat reads at most the established bounded
   watch snapshot size, imports no operational packet, and never pings for
   stale/missing/invalid snapshots (`NO_PING` plus typed reason). Snapshot validity
   proves watch work, not Telegram delivery. Preserve incident/recovery dedupe/retry.
5. Canonical runbooks distinguish collector writes / watch reports / external
   observation configured, include cheap read-only checks, staged deploy/rollback,
   disabled-timer consequences, TICK_COMPLETE/source-poll/due/RDP semantics,
   and short checks after 7/30 days. No second Git source of current VPS state.
   The direct read-model helper `due_pressure.py` is included solely to replace
   its all-due list with the existing scoped iterator; no scheduler behavior changes.
6. Catalog assets/relations/hashes and generated navigation propagate normally.
   Verify SEM-REMOTE-OPS-RECOVERY and SEM-LIVE-COLLECTION for OOM, watch,
   campaign successor and collector writes. Semantic config changes only for
   a demonstrated route gap; generated files are never hand-edited.
7. Targeted tests, four independent reviews, Catalog/Harness checks, exact-head CI
   and merge-readiness pass. Return PR/head, diff, BEFORE/AFTER, evidence,
   UNKNOWNs and precise separate operational steps. Stop at rendered merge phrase.

## DECISION_DELTA

Make operational reads and liveness evidence resource-safe without building
another monitoring platform or widening live authority.

## UNCERTAINTY_REMOVED

Measured call-ledger/full-packet resource cause and bounded consumer behavior;
fresh watch evidence as a precondition for an external liveness ping.

## CAPABILITY_OR_EVIDENCE

One offline Git PR with reproducible profiles, semantic parity and operator recovery.

## STOP

Exact owner phrase after exact-head CI and merge-readiness; no merge/deploy here.
If machine Entry rejects this owner-named first-change contract, report and stop.

## NEXT

Separate owner-gated exact-SHA deploy, followed by two watch cycles and an
independent pulse run. External receiver/URL/Telegram route requires its own decision.
Read-only successor check is due after renewal on 2026-10-03 09:40 Moscow;
verify same family, window through 2026-10-05 13:00 UTC, authority and rollover.
No autonomous campaign authorization, scheduler or automation creation.

## PRODUCT_HORIZON_RADAR

NOW: NONE. WATCH: live MemoryPeak and same-family successor continuity at the
explicit commissioning/renewal boundaries. No adjacent infrastructure work.
