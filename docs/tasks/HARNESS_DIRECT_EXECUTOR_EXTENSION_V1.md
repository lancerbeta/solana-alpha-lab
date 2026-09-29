---
task_id: HARNESS_DIRECT_EXECUTOR_EXTENSION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-29'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a372f81376a7d77fe2500201739a46a736f2d986
  expected_upstream: origin/main
  expected_upstream_oid: a372f81376a7d77fe2500201739a46a736f2d986
  expected_branch: cursor/harness-direct-executor-extension-v1
  dirty_mode: FORBIDDEN
objective: Add Claude Code and an explicitly named OTHER coding client to the existing Git-native Delivery Harness with the same grants and denials as Cursor and Codex, without letting the candidate policy authorize its own merge.
managed_write_set:
- docs/tasks/HARNESS_DIRECT_EXECUTOR_EXTENSION_V1.md
- CLAUDE.md
- AGENTS.md
- .cursor/rules/00-authority.mdc
- .agents/skills/delivery-harness/SKILL.md
- .cursor/commands/delivery-start.md
- docs/agent/DELIVERY_HARNESS_PROTOCOL.md
- docs/agent/EXECUTION_ROUTER_PROTOCOL.md
- control/owner_attention_gate_v2.yaml
- delivery-harness/harness.yaml
- catalog/schemas/delivery_harness.schema.json
- catalog/schemas/delivery_harness_task_contract.schema.json
- catalog/schemas/delivery_harness_context_receipt.schema.json
- catalog/schemas/owner_attention_gate_v2.schema.json
- scripts/owner_attention_gate.py
- scripts/delivery_harness.py
- scripts/validate_baton.py
- tests/test_delivery_harness_authority.py
- tests/test_delivery_harness_contract.py
- tests/test_delivery_harness_executor_extension.py
- delivery-harness/templates/portable-bundle-manifest.json
- catalog/assets/core.yaml
- docs/evidence/control/delivery_harness_acceptance_v1.json
- docs/evidence/control/owner_attention_gate_acceptance_v1.json
- docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
- docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json
- docs/evidence/control/a1_harness_direct_executor_extension_completion_v1.json
- docs/evidence/control/a1_harness_direct_executor_extension_review_v1.json
- docs/evidence/control/a1_harness_direct_executor_extension_factory_fit_v1.json
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
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
- NEW_ROUTE_SELF_AUTHORIZATION
- UNKNOWN_ACTOR_MAPPED_TO_OTHER
- DORMANT_ROUTE_ACTIVATION
- CLIENT_INSTALL_OR_PROVIDER_PURCHASE
- UNSCOPED_POLICY_DRIFT
- SECRET_IN_RECEIPTS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/control/a1_harness_direct_executor_extension_completion_v1.json
    - docs/evidence/control/a1_harness_direct_executor_extension_review_v1.json
    - docs/evidence/control/a1_harness_direct_executor_extension_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HARNESS_DIRECT_EXECUTOR_EXTENSION_V1

`SPEC_ROUTE=NONE`. Git contract is execution authority. Design anchor and
expected base are `a372f81376a7d77fe2500201739a46a736f2d986`.

## Executor provenance

Declared, not a grant.

- coding_client: Cursor Agent
- model: Grok 4.7
- route: DIRECT_CURSOR_DELIVERY
- actor: CURSOR

## DECISION_DELTA

Claude Code and an explicitly named OTHER client join the existing direct
delivery path. The frozen expected-base policy remains the authority for the
PR that introduces them.

## UNCERTAINTY_REMOVED

Whether a policy-changing candidate can admit its own new route before that
policy is on the default branch. It cannot.

## CAPABILITY_OR_EVIDENCE

Four direct route/actor pairs share routine and transport admission. Legacy
documents still parse. Scoped policy edits return the base policy.

## STOP

Stop for the exact owner merge phrase after merge-readiness PASS. Do not merge
in this atom without that phrase.

## NEXT

After the phrase, one guarded merge and post-merge readback. No client install.

## Rollback

Stop using the new routes and continue with Cursor or Codex. That needs no
code deletion. A reviewed revert is a separate atom on the previous direct
route. Do not rewrite history or delete receipts.

## Non-goals

No new harness, client registry, provider purchase, dormant-baton activation,
or claim that a specific Claude, Kimi or GLM client was launched.
