---
task_id: I2_BACKUP_LEGACY_STORAGE_V1
task_version: '1.3'
status: IN_PROGRESS
as_of: '2026-10-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3ff9df44331d8063274132c3da7022e46d859d92
  expected_upstream: origin/main
  expected_upstream_oid: 3ff9df44331d8063274132c3da7022e46d859d92
  expected_branch: codex/i2-backup-legacy-storage-v1
  dirty_mode: ALLOW_REPORTED
objective: Implement the complete I2 backup, legacy retirement, physical reclaim and bounded maintenance capability on existing owners; prove it on isolated stores, deliver reviewed exact-head CI and machine merge-readiness, and prepare one staged OPERATE packet without production mutations.
managed_write_set:
- docs/tasks/I2_BACKUP_LEGACY_STORAGE_V1.md
- docs/evidence/i2_backup_legacy_storage_v1/**
- docs/operator/FACTORY_REMOTE_HOST.md
- docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
- docs/contracts/system_operability_surface_v2.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- src/solana_alpha_lab/factory/remote_ops.py
- src/solana_alpha_lab/factory/offhost_backup.py
- src/solana_alpha_lab/factory/observation_schedule_retention.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/managed_collection.py
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/operability_watch.py
- src/solana_alpha_lab/factory/hot90_closed_day_loop.py
- scripts/observation_schedule_retention.py
- scripts/factory_offhost_backup_copy.py
- configs/factory_remote_operations_v1_1.yaml
- configs/factory_remote_ops/**
- catalog/schemas/factory_remote_operations_v1_1.schema.json
- tests/test_observation_schedule_remote_ops.py
- tests/test_factory_offhost_backup.py
- tests/test_factory_remote_operations.py
- tests/test_mutable_backup_zip64_repair_v1.py
- tests/test_collector_operability_retention_and_owner_pulse.py
- tests/test_i2_backup_legacy_storage_v1.py
- tests/test_i2_offhost_checkpoint_v1.py
- tests/test_i2_retention_maintenance_v1.py
- tests/test_i2_storage_consumers_v1.py
- tests/test_i2_pipeline_v1.py
- tests/test_managed_collection_continuity_v1.py
- tests/test_factory_operability_signal_calibration_v1.py
- tests/test_factory_operability_memory_collision_repair_v1.py
- catalog/assets/**
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
- docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
- STOP_MATERIAL_SCOPE_SAFETY_OR_TRUTH_CONFLICT
- STOP_PRODUCTION_DEPLOY_UPLOAD_DESTRUCTIVE_APPLY_RECLAIM_POLICY_ENABLE_OR_EFFECTIVE_FRESHNESS_RETENTION_CHANGE_WITHOUT_EXACT_OPERATE_AUTHORITY
- STOP_PROTECTED_A_B_PROFILE_SHARED_COUNTER_C1_C2_OR_SCIENTIFIC_SEMANTIC_CHANGE
- REPLAN_REPEATED_BLOCKER_IMPOSSIBLE_FALSIFIER_SECOND_ROUTE_PIVOT_OR_BUDGET_BREACH
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/evidence/i2_backup_legacy_storage_v1/source-contract.md
    DELIVERY_EVIDENCE:
    - docs/evidence/i2_backup_legacy_storage_v1/completion.json
    - docs/evidence/i2_backup_legacy_storage_v1/independent-review.json
    - docs/evidence/i2_backup_legacy_storage_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# I2_BACKUP_LEGACY_STORAGE_V1

Owner EXECUTE accepts the single PRD/SSD imported without semantic changes as
`docs/evidence/i2_backup_legacy_storage_v1/source-contract.md`. Its section 15
is the execution instruction; section 14 defines handback. The task is a Git
execution binding, not a replacement specification. All mandatory source
requirements remain in scope; an uncovered requirement is PARTIAL/BLOCKED.
Original owner input SHA256:
`a63241c261748dca5a271d0e3f99b7c22400fa72d786c934b6bf68e2989c6b80`.
The Git text projection uses LF and removes Markdown trailing hard-break spaces
on three header lines, following the repository whitespace gate; original owner
bytes are unchanged outside Git.

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH (owner-provided PRD/SSD).
Route/actor: DIRECT_CODEX_DELIVERY / CODEX.
MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
DECISION_DELTA: permit one consistent, economical, recoverable backup path and
one exact approved retirement/reclaim and maintenance policy on existing owners.
UNCERTAINTY_REMOVED: concurrent capture divergence, false chain verification,
retry recapture, unsafe age-only retention, physical identity drift, unbounded
maintenance and freshness-clock ambiguity.
CAPABILITY_OR_EVIDENCE: complete isolated snapshot/chain/restore,
provenance-preserving retirement and reclaim rehearsal; default-off policy and
existing caller; one staged OPERATE packet and compact OWNER_READOUT.
Named consumers: ordinary local/offhost backup, native retention CLI, existing
backup caller, managed readiness and OPERATE executor.
STOP: exact merge gate or material blocker.
NEXT: exact owner merge phrase, guarded merge/readback, then staged OPERATE.
REPLAN_TRIGGER: repeated blocker, preparatory-only output, impossible oracle,
second provider/route pivot, or material safety/resource conflict.

Tool Entry: existing delivery-harness, Git/gh, locked Python 3.13.14, stdlib
SQLite/zipfile and existing native owners. New plugin/connector/MCP/automation,
dependency, key or service: NONE. Reuse the existing I2 benchmark; its sample
ratio is not a whole-checkpoint measurement. No provider or production write.

## Owner review follow-up — same PR #407

The owner review imported as `docs/evidence/i2_backup_legacy_storage_v1/review-follow-up.md`
is an additional acceptance constraint, not a replacement for the original
PRD/SSD. Original attachment SHA256:
`778ca30b1be380455720fd4f7f80afb4bce77a0b0df0a2b7eeb14f093ebb91b3`.
It reviewed `b8ed4be809652714065b0db6c54fe454a8129ec7` against the frozen base.
All four findings must be reproduced on disposable native stores and either
minimally repaired in existing owners or disproved by a concrete production-path
trace and independent oracle before merge-readiness:

- P1-1: actual base-producer mutable-only full plus new daily delta; defer final
  recovery-control closure until the complete chain, retain every raw-link
  integrity check and refuse an incomplete standalone or final reconstruction.
- P1-2: ordinary scheduled caller automatically retries transient writer/backup
  contention within a finite cadence/RPO-derived budget, preserves pending
  bytes/identity, coalesces overlap and reports terminal exhaustion with exact
  resume; no force-unlock, collector stop, new daemon or live timer/RPO change.
- P1-3: fresh ordinary writable processes must refuse pending reclaim before
  SQLite creation/mutation in every process-death/rename window; exact durable
  recovery includes owned pre-intent staging, irreversible resume boundary and
  explicit disposition of rollback/staging bytes after successful acceptance.
- P1-4: installing an approved narrower policy revision or disable/enable
  reconciles stale active plans without applying their remainder, losing prior
  effects/provenance/cold pins, or hiding a genuine integrity/candidate conflict.

Extend existing native fixtures only at these seams; report each exact BEFORE
failure, owning repair, independent AFTER readback and remaining production gate.
Then refresh task/OPERATE/evidence bindings, isolated reviews, exact-head CI and
machine merge-readiness in #407. No merge phrase before all material findings
are closed. Original production and protected-state authority limits still hold.

## Implementation and verification plan

1. `remote_ops.py`: capture each SQLite once and freeze path membership;
   stream DEFLATE level 1 with ZIP64 from captured bytes. Prove concurrent
   writer/publication changes cannot alter the checkpoint. Independently hash
   extracted files, validate full and every delta and final expected inventory,
   reject malformed archive paths/entries, and add the unresolved restore marker
   only after final raw reconstruction and integrity verification. Preserve
   managed control/accounting and required publication/research dependencies.
2. `offhost_backup.py`: immutable pending operation and same-artifact retry,
   remote reconciliation, checkpoint-before-pointer commit, corrupt-state
   refusal, last-good separate from attempt, bounded lock contention and
   reference-aware pruning. Distinguish snapshot/start/upload/verify clocks;
   retain effective current policy until separately approved commissioning.
3. Native retention/store/CLI: true read-only status/plan; exact retired scope,
   cold proof and episode/dependency protections; bounded keyset rows/bytes/wall,
   candidate identity revalidation, idempotent resume and original source clocks.
   Physical reclaim uses final current state, preserves keys/ROWID/sequence and
   root identity, supports recoverable switch and next native writer. One narrow
   versioned policy remains disabled until approved; existing caller yields to
   collector/backup pressure. Prepare retained-checkpoint reachability pruning.
4. Integrate direct health/capacity consumers without changing A/B, APPLIED
   profile, grants/shared counters or science. Reuse relevant I1/I3 regressions.
   Record comparable isolated sizes, logical body removal, physical effect,
   resource/phase observations and honest live residuals; model 7/30/180d with
   explicit assumptions and I4 pins. Prepare exact staged OPERATE instructions.
5. Launch isolated CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC and
   OWNER_UX_CRITIC on the exact contract and delivery diff. Fix material findings,
   sync generated owners, bind evidence, preflight-push, PR/exact-head CI and
   merge-readiness. No pre-PR full local gate and no merge before owner phrase.

Independent oracles: filesystem path/size/SHA scan of extracted bytes; expected
semantic rows and stable identities/counters; directory/DB/WAL actual sizes;
native writer after reclaim; negative corruption, reordered/missing delta,
changed candidate, protected attempt and interrupted operation probes.

## Acceptance boundaries

Code stage can report CODE_READY_RUNTIME_PENDING only when all mandatory
capabilities and isolated proofs are ready. Full I2 remains pending until exact
approved production retirement/reclaim, compact new full baseline, ordinary
backup and commissioned ordinary maintenance cycles under the collector.
The OPERATE packet must preserve all source section 12 gates. No deploy,
upload, runtime compaction/reclaim, maintenance enable, remote deletion or
effective freshness/retention change follows from this EXECUTE.

FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW: NONE (I2 is
the elected capability). WATCH: I4 source/cold lifecycle only if surviving
scientific pins or RDP growth dominate measured 180d runway.

## Main integration and checkpoint-pipeline replan

The owner reported a changed main. Integrate PR #406 by ordinary forward merge,
freeze its exact main `3ff9df44331d8063274132c3da7022e46d859d92` as the new delivery base,
and preserve its scientific contracts, source, history and evidence bytes.
Historical legacy-producer pins remain bound to their original b3fb9d8 commit.
The independent outer refresh-outcome race requires one bounded repair across
checkpoint maintenance, refresh/register/release and final outcome authority.
Use current native owners and finite metadata comparisons; preserve committed
effects, pins, newer policy/plan/state/checkpoint identity and last-good truth.
Re-run the native race oracle and ordinary pipeline, then re-freeze all four
reviews and exact-head CI. Scope, review roles and production gates are unchanged.

The independent owner-UX review additionally reproduced explicit CLI OPERATE
accepting rehearsal retirement and subsequently compacting bodies without an
independent proof. Bind requested mode to the exact approved retirement and
downstream authority before mutation, including physical apply/recovery, in
the existing native owners. Preserve canonical document hashes and the valid
isolated rehearsal path; no new policy schema or production authority follows.
