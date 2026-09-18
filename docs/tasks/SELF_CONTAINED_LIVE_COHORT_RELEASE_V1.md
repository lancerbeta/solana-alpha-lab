---
task_id: SELF_CONTAINED_LIVE_COHORT_RELEASE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-18'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 5baca80892aebdfc7d415191bf7d85744070d46f
  expected_upstream: origin/main
  expected_upstream_oid: 5baca80892aebdfc7d415191bf7d85744070d46f
  expected_branch: cursor/self-contained-live-cohort-release-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Make every future sealed and imported LIVE cohort self-contained by carrying
  the exact ObservationSchedule document across source, seal, verify, transport
  and import so canonical local consume-time can resolve it without VPS or a
  manual bind step.

managed_write_set:
  - docs/tasks/SELF_CONTAINED_LIVE_COHORT_RELEASE_V1.md
  - src/solana_alpha_lab/factory/live_cohort_schedule_artifact.py
  - src/solana_alpha_lab/factory/live_cohort_source_bundle.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
  - scripts/discovery_evidence_release.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - tests/test_self_contained_live_cohort_release_v1.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/self_contained_live_cohort_release/a1_owner_readout_v1.md
  - docs/evidence/self_contained_live_cohort_release/a1_delivery_completion_evidence_v1.json
  - docs/evidence/self_contained_live_cohort_release/a1_delivery_independent_review_v1.json
  - docs/evidence/self_contained_live_cohort_release/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - VPS_DEPLOY
  - COLLECTOR_RUNTIME_MUTATION
  - PROVIDER_CALL
  - FORGE_EXECUTION
  - C2_OPERATION
  - HISTORICAL_PARQUET_REWRITE
  - PER_COHORT_REPAIR_LOGIC
  - GIT_FIXTURE_SCHEDULE_FALLBACK
  - REMOTE_VPS_SCHEDULE_LOOKUP
  - Y_TYPED_VALUE_READ
  - WEAKEN_CANONICAL_SCHEDULE_UNBOUND

context_requirements:
  catalog_asset_ids:
    - MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001
    - MODULE-LIVE-COHORT-TO-FORGE-001
    - MODULE-LIVE-COHORT-SOURCE-BUNDLE-001
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
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
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/self_contained_live_cohort_release/a1_delivery_completion_evidence_v1.json
      - docs/evidence/self_contained_live_cohort_release/a1_delivery_independent_review_v1.json
      - docs/evidence/self_contained_live_cohort_release/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SELF_CONTAINED_LIVE_COHORT_RELEASE_V1

SPEC_ROUTE=BOTH.

Owner EXECUTE. One PR. Stop at merge-readiness. C2_OPERATION_PENDING.

## Task Outcome Brief

- **Owner decision:** A sealed LIVE cohort is not scientifically self-contained
  if it carries only `schedule_sha256` without the exact ObservationSchedule
  document whose canonical hash equals that SHA.
- **Product outcome:** every new live-cohort release automatically carries,
  verifies, transports and locally binds that exact document. Ordinary
  list → build → seal → verify → transport → import → forge-control-ready
  needs no extra schedule command.
- **Named consumer:** ScientificEligibilityProjection / CONTROL on the
  canonical local data plane.
- **Cheapest falsifier:** hermetic source→seal→verify→transport→import plus
  shared-schedule multi-cohort and legacy 1.0 trees.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase.
  Do not merge. Do not operate C2. Do not run Forge.
- **Non-goals:** VPS deploy; collector/scheduler semantics; provider; Forge;
  per-cohort repair; historical parquet rewrite; Git-fixture schedule truth.

## PRD

A future imported sealed corpus must carry or deterministically resolve the
exact ObservationSchedule its census SHA references.

Truth flow (one owner):

authoritative ObservationSchedule at source/build
→ source bundle `observation_schedule.json`
→ sealed release `observation_schedule.json`
→ verify (parser + semantic SHA + artifact byte SHA)
→ transport (byte-equal tree)
→ import persists into existing ResearchStore `OBSERVATION_SCHEDULE`
→ ScientificEligibilityProjection resolver (unchanged consume contract)

Distinguish:

- **A. semantic identity:** `schedule_sha256(document)` via
  `collection_projection` (excludes `schedule_key` / `schedule_sha256`).
- **B. transport integrity:** SHA-256 of the artifact bytes.

Do not conflate them. Do not weaken `CANONICAL_SCHEDULE_UNBOUND`.

Schedule truth is keyed by immutable schedule SHA, not cohort ID. Importing
a later cohort with the same SHA makes that document resolvable for every
already-imported cohort that cites it, without rewriting their parquet.

Legacy schema 1.0 remains verifiable. Absence of the artifact must never be
promoted to SCHEDULE_BOUND.

## SSD

- **ADOPT** `validate_observation_schedule` / `schedule_sha256` and
  `persist_observation_schedule` (ResearchStore).
- **WRAP** source bundle, seal, verify, `RELEASE_FILES` transport, import.
- **FORK/BUILD** none: no second schedule DB, no collector runtime change.
- New release `schema_version=1.1` adds `observation_schedule.json` plus
  `observation_schedule_sha256` (byte) beside existing `schedule_sha256`.
- Source-time ops sqlite may confirm identity; it is not a Forge dependency.
- RDP vs ops disagreement at build is typed STOP.
- Resolver stays `resolve_canonical_release_schedule` on local data_root.

## Frozen rules

1. No C1/C2 IDs in product code.
2. No `--schedule-document` operator argument.
3. No Git fixture / common_panel / reconstructed YAML fallback.
4. No VPS lookup after import.
5. No historical census/obs rewrite.
6. Tamper / mismatch / missing artifact fail closed.
7. PR #319 eligibility semantics unchanged.

## Delivery notes

- `DECISION_DELTA`: sealed LIVE release is self-contained for schedule truth.
- `UNCERTAINTY_REMOVED`: CANONICAL_SCHEDULE_UNBOUND is no longer caused by
  dropping the document at the publication boundary.
- `CAPABILITY_OR_EVIDENCE`: 1.1 release member + import persist + tests.
- `STOP`: merge-readiness / owner phrase. Do not merge. C2_OPERATION_PENDING.
- `NEXT`: owner-paced C2 list→build→seal→verify→transport→import.
- `REPLAN_TRIGGER`: need a second schedule store; need collector runtime
  mutation; need historical parquet rewrite.
- `SPEC_ROUTE=BOTH`
- `MODEL_EFFORT_RECOMMENDATION`: SOL_XHIGH for the contract seam; LUNA_MAX
  for implementation.
