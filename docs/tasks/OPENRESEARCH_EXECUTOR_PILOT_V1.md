---
task_id: OPENRESEARCH_EXECUTOR_PILOT_V1
task_version: '1.0'
status: READY
as_of: '2026-09-16'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 661229914718727e3208df2562ee8a69697e905f
  expected_upstream: origin/main
  expected_upstream_oid: 661229914718727e3208df2562ee8a69697e905f
  expected_branch: cursor/openresearch-executor-pilot-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  One-shot external executor pilot for alphaXiv/OpenResearch (orx) as a
  Forge-external execution/research worker after a ready ExperimentSpec.
  PILOT_REPLAY_ONLY: no new scientific attempt, no HFIC/prior memory writes,
  no provider/network, no live truth. Produces one durable pilot report and a
  single verdict ADOPT_EXECUTOR | KEEP_EXTERNAL_EXPERIMENTAL | DROP.

managed_write_set:
  - docs/tasks/OPENRESEARCH_EXECUTOR_PILOT_V1.md
  - docs/reports/openresearch_executor_pilot/a1_owner_readout_v1.md
  - docs/evidence/openresearch_executor_pilot/a1_delivery_completion_evidence_v1.json
  - docs/evidence/openresearch_executor_pilot/a1_delivery_independent_review_v1.json
  - docs/evidence/openresearch_executor_pilot/a1_delivery_factory_fit_v1.json

external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - CANONICAL_REPO_OR_REMOTE_CONTAMINATION
  - DATASET_OR_EVIDENCE_DRIFT
  - UNEXPECTED_LIVE_PROVIDER_DEPENDENCY
  - LINEAGE_NOT_RECOVERABLE
  - CLEAN_REPLAY_IMPOSSIBLE
  - SCIENTIFIC_AUTHORITY_LEAKED_TO_ORX
  - FORGE_HFIC_RDP_REWORK_REQUIRED
  - ORX_NEEDS_PARALLEL_ORCHESTRATION_FRAMEWORK

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/openresearch_executor_pilot/a1_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/openresearch_executor_pilot/a1_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# OPENRESEARCH_EXECUTOR_PILOT_V1

SPEC_ROUTE=NONE.

External caps scope: network = one-time public fetch of
github.com/alphaXiv/OpenResearch (clone at pinned SHA
325eb509dc8e4ca7074568cf0ae1f0f98704eac0) and its Windows CLI release zip;
no provider/API/RPC/WSS, no credentials, no canonical write transport.
external_system = local-only orx dashboard on 127.0.0.1:4791 in a disposable
workspace; telemetry off; no orx login, no managed compute.

## DECISION_DELTA

Whether alphaXiv/OpenResearch (orx) materially reduces orchestration burden
and improves reproducibility as a Forge-external experiment executor versus
the ordinary Codex/Cursor agent path, justifying a new dependency or not.

## UNCERTAINTY_REMOVED

Whether an off-the-shelf local-first executor (experiment tree, isolated
per-run snapshots, supervised runs, run logs/lineage) can execute
Git-canonical offline replay specs without contaminating the canonical
repo/remote and without changing Forge/HFIC semantics.

## CAPABILITY_OR_EVIDENCE

One disposable-workspace pilot: baseline + 2 meaningful siblings (three
sha-pinned offline archetype specs, method resolve_market_feature_snapshot,
budget 0) + one clean replay; durable pilot report + single verdict. No
production integration path is built in this atom.

## STOP

Report + verdict committed on one branch, at most one PR. No production
ORX seam, no second atom, no architecture cleanup, no Forge changes.

## NEXT

Owner decision on verdict; if ADOPT_EXECUTOR, a separate future atom may
design a minimal optional Forge->ORX path (explicitly not this atom).

## Pilot design (as executed)

- OpenResearch pinned: repo shallow clone at
  325eb509dc8e4ca7074568cf0ae1f0f98704eac0 (2026-09-15); CLI release
  `orx 0.2.3` (Windows x86_64 zip). Telemetry off (`orx telemetry off`).
- Disposable workspace `C:\Users\lance\Projects\orx_pilot`:
  bare canonical mirror clone (fetch-only), lab clone with no remotes on
  branch pilot/openresearch-executor-v1 @ 661229914718727e3208df2562ee8a69697e905f,
  immutable dataset snapshot (9 files, digests recorded and re-verified after runs).
- ORX project registered via loopback API (POST /api/projects, dashboard
  127.0.0.1:4791, --no-agent --no-browser). Experiment tree: baseline
  02fc2675-054d-47ce-9dc1-fc0372d6a541 (EXP-MARKET-FEATURE-PRICE-PATH-ARCHETYPE-001),
  sibling A 7db1fdf8-4d84-4e10-aa4e-44d151c981e5
  (EXP-MARKET-FEATURE-LIQUIDITY-ARCHETYPE-001), sibling B
  8763ecd0-2a9b-4545-8b5a-73b52e0063d1
  (EXP-MARKET-FEATURE-CREATOR-PRESSURE-ARCHETYPE-001).
- All three runs launched independently (orx exp run --backend local),
  each in its own run dir from one immutable content-addressed source
  snapshot tar e8ab4e2ef2aafe2f65840e442adf9791c4b64a9f273cde799008b94b80edd921
  (commit 6612299). Run ids: eff0915c (baseline), 64daedfc (A), 48c7162c (B).
- Clean replay of baseline from the saved snapshot tar in a fresh directory:
  deterministic outputs identical; only wall-clock fields differ
  (REPLAY_PASS).
