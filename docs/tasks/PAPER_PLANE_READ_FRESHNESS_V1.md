---
task_id: PAPER_PLANE_READ_FRESHNESS_V1
task_version: '1.3'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-10-09'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: fb65d69f6e48c49b26937bb6caf324b3417b094e
  expected_upstream: origin/main
  expected_upstream_oid: fb65d69f6e48c49b26937bb6caf324b3417b094e
  expected_branch: codex/paper-plane-read-freshness-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Restore fresh, truthful readonly PaperPlane owner projections of committed
  position and current runtime policy while a writer remains open; fail closed
  when a trustworthy read is unavailable, without bootstrap, migration,
  checkpoint, repair or business-state writes. Close audit F02 only.
managed_write_set:
  - docs/tasks/PAPER_PLANE_READ_FRESHNESS_V1.md
  - docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/lifecycle_projection.py
  - tests/test_paper_shadow_execution_integrity_vertical_v1.py
  - tests/test_trading_operations_workbench_v2.py
  - tests/test_risk_and_economics_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/paper_plane_read_freshness/a1_owner_readout_v1.md
  - docs/evidence/paper_plane_read_freshness/a1_vertical_acceptance_v1.json
  - docs/evidence/paper_plane_read_freshness/a1_delivery_completion_evidence_v1.json
  - docs/evidence/paper_plane_read_freshness/a1_delivery_independent_review_v1.json
  - docs/evidence/paper_plane_read_freshness/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - MARKET_PROVIDER_API_RPC_WSS_OR_LIVE_STORAGE_REQUIRED
  - CREDENTIAL_SIGNER_WALLET_OR_SPEND_REQUIRED
  - NEW_DEPENDENCY_FRAMEWORK_SERVICE_REQUIRED
  - HARNESS_OR_CI_LIMIT_CHANGE_REQUIRED
  - ADMISSION_EXIT_RISK_SCIENCE_SEMANTICS_CHANGE_REQUIRED
  - F01_F03_A5_IMPLEMENTATION_REQUIRED
  - UNRESOLVED_AUTHORITY_OR_MEANING_CONFLICT
  - MERGE_BEFORE_EXACT_HEAD_CI_AND_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [MODULE-PAPER-PLANE-ENGINE-001, MODULE-TRADING-OPERATIONS-001, DOC-PAPER-SHADOW-EXECUTION-INTEGRITY-PRD-SSD-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md]
    DELIVERY_EVIDENCE:
      - docs/evidence/paper_plane_read_freshness/a1_delivery_completion_evidence_v1.json
      - docs/evidence/paper_plane_read_freshness/a1_delivery_independent_review_v1.json
      - docs/evidence/paper_plane_read_freshness/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---
# PAPER_PLANE_READ_FRESHNESS_V1

`SPEC_ROUTE=BOTH`: outcome brief here; existing design §8 in
`docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md` is amended
in this atom. Route/actor: `DIRECT_CODEX_DELIVERY` / `CODEX`.

## DECISION_DELTA
Owner projections may rely on committed PaperPlane position/current-policy
truth rather than an immutable view which omits live WAL. Unreadable source
remains explicitly unavailable. This closes F02, not the Post-Forge chain.

## UNCERTAINTY_REMOVED
Whether owner reads see commits before their read snapshot, whether an
independent later read sees the next commit, and whether failed reads create
or repair state or present stale/empty runtime as healthy.

## CAPABILITY_OR_EVIDENCE
Public P6 before/after, two disposable repetitions with held-open writer,
actual source-bound assertions, next-read freshness, honest source failures,
compatibility/purity and direct-consumer regressions.

## STOP
`READ_FRESHNESS_PASS_READY_FOR_MERGE_GATE`: exact-head CI and machine
merge-readiness precede the single exact owner phrase. No deploy.

## NEXT
One evidence-backed `NEXT_SCOPE` for F01 in the owner readout; no adjacent
implementation in this atom.

## Task Outcome Brief
- Owner authorization: 2026-10-09 direct command selects A4 and authorizes
  contract, engineering, tests, reviews and routine GitHub delivery.
- Owner clarification (2026-10-09, direct reply): SQLite may create native
  `-wal/-shm` coordination sidecars on readonly GET. Data-root/DB/tables,
  migration/checkpoint/repair and business writes remain forbidden. This
  replaces the earlier blanket no-created-files interpretation, not the
  freshness/error/business-purity requirements.
- Named consumers: `FactoryApplication.trading_operations_projection`,
  operations/economics, lifecycle/read-model and their existing HTTP adapter.
- Cheapest falsifier: public P6 reads OPEN/cap30 instead of committed
  UNRESOLVED/cap20 with writer open and no post-commit checkpoint.
- User-visible result: position and current-policy hash are fresh, or source
  status/error is typed unavailable; no stale success or inferred all-clear.
- Terminal outcomes: PASS ready for merge gate; ALREADY_FIXED_VERIFIED;
  explicit blocker at a listed authority/meaning boundary.
- Non-goals: F01/F03/A5, F04/OPEN_RISK_STATES, scientific acceptance, activation,
  provider/network trading calls, LIVE, deployment, second read model.
- Evidence budget: one public root-class reproducer (2 repetitions), focused
  failure/compatibility/consumer tests, isolated risk-routed reviews and exact
  PR CI. Re-run only after relevant bytes/root cause change.
- Replan trigger: repeated material blocker, impossible falsifier, required
  subsystem/dependency change, incompatible relevant main drift or write-set
  expansion. Resolve routine engineering inside this granted outcome.
- Entry verdict: START_AS_WRITTEN. Capability radar NOW=NONE: existing SQLite
  and PaperPlane owners suffice; no install/adoption authority is required.

## DoD
1. Baseline public defect is reproduced on the exact base; candidate gives
   UNRESOLVED, policy revision2/cap20 and matching committed policy hash 2/2.
   Writer stays open; no checkpoint, copy or WAL removal after tested commit.
2. A further commit is visible to the next independent owner read on the same
   application. No old snapshot is retained between requests. Commits during
   a read do not imply a promise of the latest concurrent value.
3. Missing root/DB, corrupt/unreadable source and read failure yield existing
   typed missing/unavailable/error vocabulary, not stale or all-clear values.
   No bootstrap/migration/checkpoint/repair/business writes; no new files other
   than explicitly permitted SQLite WAL/SHM sidecars. Business-state changes
   and forbidden created files are measured. Real OS permission behavior
   is exercised on the applicable Windows/Linux path, not chmod-only fiction.
4. Admissible non-WAL storage and direct consumers work; immutable fallback
   and absence-of-WAL correctness assumptions are removed from A4 design.
   Frozen admission30 is preserved while current cap20 is displayed. Existing
   mode/admission/exit guards retain their semantics.
5. Catalog/generated propagation uses harness_sync; required isolated critics
   review the final exact inventory; bound evidence and preflight pass before
   ordinary push, PR, exact-head CI and merge-readiness.
6. Two overlapping public HTTP GETs own separate readers and source status,
   both return coherent PRESENT snapshots, close their own handles and allow
   the next request to see the next commit. HTTP uses materialized results.

## Risks and recovery
SQLite's readonly WAL access may need native coordination through sidecars;
low-level lock/SHM byte immutability is not promised. Inability to read
trustworthily must not trigger immutable fallback or repair on GET.
Rollback is code revert, with no data migration: it restores the old stale
readback defect and must not be described as a fresh-reading solution.
Parallel generator dirty work remains outside this worktree and write set.

## In-scope replan
Version 1.2 adds only `tests/test_risk_and_economics_v1.py`: its existing GET
purity assertion needs the same explicitly approved two-sidecar exception as
the workbench test. All other file hashes and the database hash remain checked;
no business oracle, outcome, dependency or authority changes.
Version 1.3 resolves architecture finding A4-ARCH-01: request-thread ownership
and bounded concurrent HTTP proof, inside the same application/test/design
write set. INV-11 and the owner readout now state snapshot/sidecar limits and
explain residual F04. No new subsystem or writable semantics.
