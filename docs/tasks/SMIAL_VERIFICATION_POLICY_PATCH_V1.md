---
task_id: SMIAL_VERIFICATION_POLICY_PATCH_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-10-09'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0f89ffd8018c05fbafaf79ef609c7dadf888807f
  expected_upstream: origin/main
  expected_upstream_oid: 0f89ffd8018c05fbafaf79ef609c7dadf888807f
  expected_branch: codex/smial-verification-policy-v1
  dirty_mode: ALLOW_REPORTED
objective: Replace unconditional test-first with sufficient risk-based verification in the existing elected-agent skill and domain policy while preserving agreed outcomes, exact contracts and all mandatory gates.
managed_write_set:
  - .agents/skills/delivery-harness/SKILL.md
  - delivery-harness/policies/solana-alpha-lab.md
  - docs/tasks/SMIAL_VERIFICATION_POLICY_PATCH_V1.md
  - docs/evidence/control/smial_verification_policy_patch_v1/**
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - docs/PROJECT_MAP.md
  - catalog/generated/asset_edges.json
  - docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - Exact-head CI and merge-readiness must pass before requesting the exact owner merge phrase.
  - Stop on a currently applicable freeze, authority conflict or expansion outside this write set; the brief grants no exception.
  - No implementation Python, schema, CI architecture, validation command, machine-gate, review-role or global-skill changes.
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC]
context_requirements:
  catalog_asset_ids: [SKILL-DELIVERY-HARNESS-001]
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/control/smial_verification_policy_patch_v1/completion.json
      - docs/evidence/control/smial_verification_policy_patch_v1/independent_review.json
      - docs/evidence/control/smial_verification_policy_patch_v1/factory_fit.json
    HISTORICAL_CONTEXT: []
---

# SMIAL verification policy patch

Owner scope: `SMIAL_Verification_Policy_Patch_Brief_2026-10-09.md`, explicitly
accepted for execution by the owner's subsequent `делай :)` command.
Route: `DIRECT_CODEX_DELIVERY`; actor: `CODEX`; SPEC_ROUTE: `PRD_LITE`.

DECISION_DELTA: verification follows the material risk; test-first is optional
unless the exact task contract requires it. New tests must fill a useful gap.
UNCERTAINTY_REMOVED: the elected coding agent's universal test-first instruction
is replaced without weakening the existing gates or agreed functionality.
CAPABILITY_OR_EVIDENCE: one small policy patch, existing targeted checks,
four explicitly labelled SIMULATION_ONLY applicability cases and isolated review.
STOP: exact-head CI plus merge-readiness, then the exact owner phrase.
NEXT: guarded merge and exact main readback after that phrase; three future
natural low-risk observations use ordinary handbacks, without instrumentation.

## Entry and outcome

Consumer: elected coding agent. Entry verdict: START_AS_WRITTEN.
Cheapest falsifier: existing skill/authority contract checks plus independent
review of the risk-policy boundaries and four applicability simulations.
Oracle: owner brief, frozen base authority and independently specified expected
outcomes; policy delivery does not measure defect-rate or cost reduction.
Material risk: discretion misread as zero verification, self-confirming tests,
loss of a mandatory gate, or retries misread as permission to reroll to green.
Evidence budget: one focused local test batch, scoped generated sync, three
isolated critics and ordinary exact-head CI; no pre-PR local full gate.
REPLAN_TRIGGER: repeated blocker, new runtime/framework or evidence-budget breach.

Non-goals: runtime/provider/science/live actions, global skills/settings,
historical evidence/contracts rewrite, test-suite audit or test removal,
new registry/schema/critic/dependency and Project Instruction activation.
Capability radar NOW: NONE. WATCH: a named risk missed in a natural follow-up
atom; PATCH the concrete gap under a new exact scope if observed.

## Freeze applicability

The 2026-08-22 freeze was finite: five substantive product/research atoms after
the harness-sync sprint, not a permanent ban. Sprint merge:
`8b4b80c1446e0ce102ea9cbcd8302671e7d1e21b`; guardrail merge:
`37f66155738432dcd19ac366c930cadcf65170e8`.
Five subsequent distinct merged atoms with product/research evidence:

- `3d8a3762575507fa6bb9fc6032dedab8a1c65005` (PR #180, structural backing PIT).
- `22fbcdd23573c5d751b16462c41413f71a32152f` (PR #181, unattended shadow).
- `0cba257da5240057df4bb8ff91cf3a7f3c0feb9f` (PR #182, operational readiness).
- `4c46dae3a9fe8f7ed172f34675c18afac2e6d8f8` (PR #183, PIT truth).
- `b785dd13860572b5509cd9a9a0bd5f05babc7ed9` (PR #184, live ops hardening).

All active time-gate records are terminal; historical optional-export prose
selects no work. GitHub task transport is routine base-policy authority only.
No unrelated external authority is granted by the external_caps block.

## Definition of done

- Only the two primary instruction owners change; generated integrity state
  changes through existing sync only where impacted.
- Entry names behavior/risk/oracle/check using existing outcome text.
- Existing checks first; useful durable regressions remain, suitable TDD remains
  allowed, zero new tests requires sufficient evidence, full outcome remains.
- Reproducer/trace then same-path check for defects; real binding/readback and
  independent expected results protect against shared test/implementation errors.
- Mandatory gates and scientific/provider budgets remain unchanged; declared
  reproducibility probes preserve truthful failures/retries/skips.
- Four SIMULATION_ONLY cases and independent review establish applicability,
  not measured defect-rate, development-cost or agent-behavior improvement.
- Existing checks, bound evidence, exact-head CI and machine readiness pass.

Rollback: an ordinary inverse patch to these two instruction owners, regenerate
impacted Catalog integrity and use the same owner gate. Keep regression evidence.
