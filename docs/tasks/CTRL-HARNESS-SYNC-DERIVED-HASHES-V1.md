---
task_id: CTRL-HARNESS-SYNC-DERIVED-HASHES-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: d9f364666426eea25f4bcf41fd07a6a7e11f2f59
  expected_upstream: origin/main
  expected_upstream_oid: d9f364666426eea25f4bcf41fd07a6a7e11f2f59
  expected_branch: ctrl-harness-sync-derived-hashes-v1
  dirty_mode: ALLOW_REPORTED
objective: One idempotent command that recomputes derived catalog integrity hashes, generated navigation views, and manifest checkpoints so atoms stop failing CI on manual hash drift.
managed_write_set:
  - docs/tasks/CTRL-HARNESS-SYNC-DERIVED-HASHES-V1.md
  - scripts/harness_sync.py
  - tests/test_harness_sync.py
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - delivery-harness/harness.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PRIMARY_FILE_MUTATION
  - GENERATED_STATE_OUTSIDE_GIT
  - SILENT_PRIMARY_REWRITE
  - NON_IDEMPOTENT_APPLY
  - LF_CANONIZATION_DRIFT_VS_GUARD
  - SECRET_IN_RECEIPTS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/control/a1_harness_sync_derived_hashes_acceptance_v1.json
      - docs/evidence/control/a1_harness_sync_derived_hashes_review_v1.json
      - docs/evidence/control/a1_harness_sync_derived_hashes_factory_fit_v1.json
      - docs/evidence/control/a1_harness_sync_derived_hashes_completion_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-HARNESS-SYNC-DERIVED-HASHES-V1

## Task Outcome Brief

One deterministic command (`scripts/harness_sync.py`) recomputes every derived
integrity hash in the Catalog (asset `integrity.sha256` fields), regenerates the
navigation projections, and updates the manifest checkpoint counters. Running
it twice in a row changes zero bytes. This removes the dominant source of red
CI runs: manual, multi-step hash rebinding that already produced two failures
on 2026-08-21 (LF/CRLF blob drift, unpinned fixture index).

## Decision capsule

- `DECISION_DELTA`: derived-hash maintenance moves from manual per-atom Python
  snippets to one owned, tested command; the guard keeps its semantics.
- `UNCERTAINTY_REMOVED`: whether derived-hash drift can be repaired
  deterministically without hand-editing catalog blocks.
- `CAPABILITY_OR_EVIDENCE`: LF-canonical hashing aligned with what the guard
  reads from Git blobs; block-scoped sha256 field rewrite; existing nav
  generator reused.
- `STOP`: sync never mutates primary files (src/tests/configs/docs evidence);
  never invents asset records; never writes outside Git.
- `NEXT`: atom 2 binds delivery-evidence chains on top of this core.

## SPEC_ROUTE

`BOTH` — PRD + SSD inside this contract.

## PRD

- **Outcome**: seeded derived-hash drift is repaired by one command; a second
  run is a no-op; `--check` exits non-zero when drift exists.
- **Product link**: factory throughput (42 atoms shipped; 2 of last 3 full-gate
  runs failed on derived-hash drift, not science).
- **Downstream consumer**: agent FINISH phase; guarded merge reads the same
  hashes and stops seeing cryptic `canonical_catalog_hash_mismatch`.
- **Success observable**: `--check` PASS after `--apply` on a drifted tree;
  byte-identical second apply.
- **Invalidation**: any drift class the command cannot repair deterministically.
- **Non-goals**: delivery-evidence bindings (atom 2); schema changes; new
  catalog assets; runtime/provider work.

## SSD

- **Baseline**: origin/main `d9f364666426eea25f4bcf41fd07a6a7e11f2f59`.
- **Design**: `scripts/harness_sync.py` with `--apply` and `--check`:
  1. Load catalog assets via existing `validate_catalog` loader.
  2. For every asset with `integrity.kind == "sha256"` and
     `location.kind == "git_path"`, hash the target file as **LF-canonical
     bytes** (matches what the guard reads from Git blobs on this platform).
  3. Rewrite only the `sha256:` value inside the exact asset block in
     `catalog/assets/core.yaml` / `catalog/assets/lifecycle.yaml`; ambiguity
     (duplicate asset blocks) fails closed.
  4. Run the existing navigation generator in write mode.
  5. Recompute `catalog_manifest.current_checkpoint` counters from the loader
     snapshot.
- **Invariants**: primary sources are read-only to sync; writes limited to
  derived fields/views/counters; LF canonization constant is the single source
  of truth shared with the guard's read path; idempotency is a test.
- **Affected surfaces**: scripts/harness_sync.py, tests/test_harness_sync.py,
  catalog generated views, manifest counters, protocol doc.
- **Failure modes**: duplicate asset block → `AMBIGUOUS_ASSET_BLOCK`;
  missing target file → `TARGET_MISSING` (field untouched, drift reported).
- **Validation**: golden fixture test with three drift classes (CRLF bytes,
  stale sha, counter drift); idempotency test; `--check` exit-code test.
- **Rollback**: revert branch; sync holds no state outside Git.

## REPLAN_TRIGGER

A drift class appears that requires judgment (not recomputation) to repair;
guard read-path diverges from LF canonization.

## Definition of Done

- Golden tests green; idempotency proven; `--check` wired semantics documented.
- Protocol doc names the command as the only sanctioned derived-hash repair.
- PR green on exact head.

## Owner gates

No provider phrase. Exact merge phrase only after CI on unchanged head.
