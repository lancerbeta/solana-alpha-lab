---
task_id: HOT90_ARCHIVE_SLOT_SHIFT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 81aca3994a302a5771c7311651fc3e38d0d67b15
  expected_upstream: origin/main
  expected_upstream_oid: 81aca3994a302a5771c7311651fc3e38d0d67b15
  expected_branch: claude/hot90-archive-slot-shift-v1
  dirty_mode: ALLOW_REPORTED
objective: Move the closed-day archive timer slots from 01:15/07:15/13:15/19:15 UTC to 04:15/10:15/16:15/22:15 UTC so the first daily archive and cohort-closure upload no longer shares the Drive uplink with the off-host backups.
managed_write_set:
- docs/tasks/HOT90_ARCHIVE_SLOT_SHIFT_V1.md
- src/solana_alpha_lab/factory/hot90_closed_day_loop.py
- configs/factory_remote_ops/factory-hot90-closed-day-archive.timer
- configs/factory_remote_operations_v1_1.yaml
- catalog/schemas/factory_remote_operations_v1_1.schema.json
- docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
- tests/test_factory_unattended_operability_closure_v1.py
- docs/evidence/hot90_archive_slot_shift_v1/**
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- EXACT_HEAD_CI_AND_MERGE_READINESS_THEN_OWNER_PHRASE_BEFORE_MERGE
- NO_DEPLOY_OR_UNIT_INSTALL_IN_THIS_PR
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
    DELIVERY_EVIDENCE:
    - docs/evidence/hot90_archive_slot_shift_v1/completion.json
    - docs/evidence/hot90_archive_slot_shift_v1/independent-review.json
    - docs/evidence/hot90_archive_slot_shift_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# Closed-day archive slot shift

Owner request (2026-10-22): recommend and make the change after the 01:15Z
archive run timed out.

DECISION_DELTA: the first daily archive run starts after the Drive backups
instead of during them. UNCERTAINTY_REMOVED: why the 2026-10-22 01:15Z run was
killed. CAPABILITY_OR_EVIDENCE: one schedule owner moved in all pinned places,
plus the read-only production timeline below. STOP: exact-head CI, merge
readiness, owner phrase. NEXT: separate OPERATE to deploy, install the timer
unit and reload systemd. REPLAN_TRIGGER: a run at a new slot times out again.

Cause, read-only on the producer journal: the daily delta backup
(`00:45 UTC`) uploaded 1.16 GB from 00:48:57Z to 01:24:35Z. The archive run
started at 01:15Z, made no progress for 15 minutes (10 s CPU) and systemd
killed it at `TimeoutStartSec=900` before it wrote any receipt. A manual
run of the same unit at 05:32Z, with no backup running, finished in 134 s and
uploaded and verified day 20261021 and cohort REL-20261018T000000Z-20261019T000000Z.
Delta run time with the same 1.16 GB payload was 5–39 min over 17–22.10, so how much it overlaps the 01:15Z slot depends on Drive throughput.

Fix: slots move by +3 h. Worst case before the first slot: weekly full
Sun 00:30 up to 110 min (`offhost_backup` comment), then the delta waits for
the shared lock and runs about 40 min, so the backups end around 03:10Z. 04:15Z leaves
about one hour of margin. Nothing else is scheduled near the new slots: local backup 00:15/12:15,
owner pulse 06:20, renewal 06:40. The 24 h archive RPO (`IMMUTABLE_ARCHIVE_STALE`)
and the 6 h catch-up spacing do not change. A mature cohort reaches Drive about 3 h later.
`TimeoutStartSec=900` stays as is.

Non-goals: no change to backup code, the delta payload, rclone timeouts or the runtime budget.
Rollback: revert, then reinstall the previous timer unit.
