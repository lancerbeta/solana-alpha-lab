---
task_id: HFIC_MANAGED_RUNTIME_ENTRYPOINT_CORRECTIVE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-28'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 988aa98f1678a390b2c421ce54cd4559e26df317
  expected_upstream: origin/main
  expected_upstream_oid: 988aa98f1678a390b2c421ce54cd4559e26df317
  expected_branch: cursor/hfic-managed-runtime-entrypoint-corrective-v1
  dirty_mode: ALLOW_REPORTED
objective: Bind operator-executable Hypothesis Forge commands to the canonical uv managed-python 3.13.14 launch prefix and fail closed before any project import, RDP write or Git mutation when the interpreter is not that exact release.
managed_write_set:
  - docs/tasks/HFIC_MANAGED_RUNTIME_ENTRYPOINT_CORRECTIVE_V1.md
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - scripts/hypothesis_forge.py
  - tests/test_hfic_cli.py
  - tests/test_hfic_operational_closure_v1.py
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/hypothesis_forge_operational_closure/a1_managed_runtime_entrypoint_completion_v1.json
  - docs/evidence/hypothesis_forge_operational_closure/a1_managed_runtime_entrypoint_review_v1.json
  - docs/evidence/hypothesis_forge_operational_closure/a1_managed_runtime_entrypoint_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PYTHON_310_COMPATIBILITY_SHIM
  - UTC_MASS_REPLACE
  - HFIC_LOGIC_OR_CATALOG_REDESIGN
  - NESTED_UV_IN_HFIC_TESTS
  - PRODUCTION_FORGE_BEFORE_MERGE
  - PROVIDER_OR_NETWORK_CALL
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/hypothesis_forge_operational_closure/a1_managed_runtime_entrypoint_completion_v1.json
      - docs/evidence/hypothesis_forge_operational_closure/a1_managed_runtime_entrypoint_review_v1.json
      - docs/evidence/hypothesis_forge_operational_closure/a1_managed_runtime_entrypoint_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_MANAGED_RUNTIME_ENTRYPOINT_CORRECTIVE_V1

## Task Outcome Brief

- **Owner decision:** Hypothesis Forge operator commands must launch through
  the repository canonical CPython 3.13.14 runtime, not a workstation PATH
  `python`.
- **Product outcome:** one slash/skill/operator command prefix
  `uv run --locked --managed-python python -B scripts/hypothesis_forge.py ...`
  plus a fail-closed CLI gate that returns
  `HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE` before project imports.
- **Named consumers:** `/hypothesis-forge` operator path and
  `scripts/hypothesis_forge.py`.
- **Cheapest falsifier:** skill/command still contain a bare
  `python -B scripts/hypothesis_forge.py` invocation, or the CLI imports
  factory modules before the version gate, or pins disagree.
- **Terminal outcome:** `PROCEED` after targeted tests, isolated review,
  exact-head CI and guarded merge. Production Forge stays stopped until merge.
- **User-visible result:** the same production smoke that previously died on
  Python 3.10 can be re-run only after merge.
- **Non-goals:** HFIC logic, prospects, Critic, V2, Catalog redesign, CI
  optimization, Python 3.10 compatibility, `datetime.UTC` rewrites.
- **Evidence budget:** pin alignment, no bare operator invocation, CLI tests
  keep `sys.executable`, TEMP-root managed-python preflight, Git unchanged,
  provider calls 0.
- **Replan trigger:** a second runtime/provider pivot or a need to change
  HFIC session semantics.

## Decision capsule

- `DECISION_DELTA`: operator launch is uv managed-python 3.13.14; any other
  interpreter is a typed stop before RDP/Git mutation.
- `UNCERTAINTY_REMOVED`: PATH `python` 3.10 can no longer look like a valid
  Forge entrypoint.
- `CAPABILITY_OR_EVIDENCE`: skill/command/operator prefix, CLI gate, regression
  tests.
- `STOP`: merge gate; no production Forge before merge.
- `NEXT`: post-merge same-focus AUTO production smoke.
- `SPEC_ROUTE`: `NONE`
- `REPLAN_TRIGGER`: pin disagreement or a request to widen HFIC behavior.
