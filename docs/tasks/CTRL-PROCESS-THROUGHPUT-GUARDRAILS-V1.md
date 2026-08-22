---
task_id: CTRL-PROCESS-THROUGHPUT-GUARDRAILS-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 8b4b80c1446e0ce102ea9cbcd8302671e7d1e21b
  expected_upstream: origin/main
  expected_upstream_oid: 8b4b80c1446e0ce102ea9cbcd8302671e7d1e21b
  expected_branch: ctrl-process-throughput-guardrails-v1
  dirty_mode: ALLOW_REPORTED
objective: Freeze control-plane churn, measure ceremony tax on delivery close, add a cheap static Python gate for active Factory code, and register an optional owner-UX critic for manual operator surfaces.
managed_write_set:
  - docs/tasks/CTRL-PROCESS-THROUGHPUT-GUARDRAILS-V1.md
  - delivery-harness/policies/solana-alpha-lab.md
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - AGENTS.md
  - .agents/skills/delivery-harness/SKILL.md
  - .cursor/agents/owner-ux-critic.md
  - delivery-harness/templates/portable-core/dot-cursor/commands/delivery-review.md
  - catalog/schemas/delivery_harness_completion_evidence.schema.json
  - scripts/delivery_efficiency.py
  - scripts/validate_factory_static.py
  - scripts/validate_baseline.py
  - scripts/validate_ci.py
  - src/solana_alpha_lab/factory/runtime.py
  - tests/test_process_throughput_guardrails.py
  - tests/test_delivery_harness_adapters.py
  - pyproject.toml
  - uv.lock
  - delivery-harness/harness.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - HARNESS_SEMANTICS_CHANGE
  - FULL_REPO_LINT_SCOPE
  - RETROACTIVE_EVIDENCE_REWRITE
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
      - docs/evidence/control/a1_harness_sync_ci_fail_closed_messages_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-PROCESS-THROUGHPUT-GUARDRAILS-V1

## Task Outcome Brief

After the harness-sync control sprint (#174–176), protect product/research
throughput with three lightweight guardrails: an explicit control-plane freeze
policy, optional `delivery_efficiency` ceremony metrics on completion evidence,
and a scoped `ruff` gate for `src/solana_alpha_lab/factory/`.

## PRD

- **Outcome:** next product atoms spend time on market truth, not self-inflicted
  process work; ceremony tax becomes measurable; Factory Python gets a cheap
  independent static critic.
- **Product link:** hypothesis throughput toward paper/shadow; fewer wasted agent
  cycles on opaque or preventable defects.
- **Downstream consumer:** owner and direct agents selecting/replanning work;
  FINISH phase completion evidence.
- **Success observable:** policy names freeze + kill-switch; completion schema
  accepts efficiency block; `validate_ci.py` runs factory ruff PASS; helper
  script emits counts for a sample PR range.
- **Cheapest falsifier:** if the next 3 product atoms still need ≥2 repair
  commits each despite #174–176, freeze alone failed and `finish` orchestration
  becomes the next atom — not more policy text.
- **Non-goals:** no harness redesign; no archival CI split; no full-repo typing;
  no retroactive rewrite of historical completion JSON; owner-UX critic does not
  run on pure backend/control atoms with no owner-operable surface.

## SSD (tail — owner-UX critic)

- **Design:** read-only `.cursor/agents/owner-ux-critic.md`; trigger-routed like
  goal/DoD and architecture; mandatory isolated context; same
  `SINGLE_AGENT_REVIEW_FALLBACK` semantics.
- **Triggers:** CLI/console entrypoints, manual operator flows, readouts,
  cockpit/workbench interaction, owner-facing error/next-action copy.
- **Invariants:** optional by trigger only; never replaces code review; no
  product scope expansion from critic output alone.

## SSD

- **Design:** policy section in domain policy; optional schema extension;
  `scripts/delivery_efficiency.py` classifies `base..head` commits by path
  heuristics; `scripts/validate_factory_static.py` wraps pinned `ruff check`
  on factory only; wired into existing `validate_ci.py` child commands.
- **Invariants:** harness semantics unchanged; historical completion evidence
  remains valid without `delivery_efficiency`; ruff scope limited to factory.
- **Kill-switch:** if 3 consecutive substantive product/research atoms each have
  `repair_commits >= 2` or `repair_ratio > 0.30`, stop and replan process
  (likely `finish` orchestration atom) before more control work.
- **Validation:** schema unit test; delivery_efficiency classification test;
  factory ruff gate test; existing CI green.

## Decision capsule

- `DECISION_DELTA`: process improvement shifts from building more harness to
  measuring throughput and guarding Factory code cheaply.
- `UNCERTAINTY_REMOVED`: whether ceremony tax can be tracked without a new
  dashboard or harness feature.
- `CAPABILITY_OR_EVIDENCE`: freeze policy, schema field, git helper, ruff gate.

## STOP

Open PR with green CI; await owner merge phrase.

## NEXT

Return capital to product/research atoms under the freeze.
