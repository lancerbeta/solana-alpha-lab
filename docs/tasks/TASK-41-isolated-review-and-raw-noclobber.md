---
task_id: TASK-41
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6089e1d011562de43068a26a8f5feb17c4c2abcf
  expected_upstream: origin/main
  expected_upstream_oid: 6089e1d011562de43068a26a8f5feb17c4c2abcf
  expected_branch: cursor/task41-isolated-review-and-raw-noclobber
  dirty_mode: ALLOW_REPORTED
objective: Make guarded merge deny SINGLE_AGENT_REVIEW_FALLBACK and persist H11 live raw pages with exclusive no-clobber writes.
managed_write_set:
  - docs/tasks/TASK-41-isolated-review-and-raw-noclobber.md
  - src/solana_alpha_lab/storage/exclusive.py
  - tests/test_storage_exclusive_write.py
  - src/solana_alpha_lab/task39_h11_named_mint_gta_clock_capture.py
  - tests/test_task39_rc002_h11_named_mint_gta_clock_capture.py
  - scripts/owner_attention_gate.py
  - tests/test_delivery_harness_merge_guard.py
  - AGENTS.md
  - .agents/skills/delivery-harness/SKILL.md
  - .agents/skills/autonomous-delivery/SKILL.md
  - .cursor/agents/architecture-critic.md
  - .cursor/agents/code-reviewer.md
  - .cursor/agents/goal-dod-critic.md
  - .cursor/agents/refactor-critic.md
  - .cursor/commands/delivery-review.md
  - delivery-harness/templates/portable-core/dot-cursor/commands/delivery-review.md
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - .github/pull_request_template.md
  - tests/test_delivery_harness_adapters.py
  - docs/evidence/task41/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task41/a1_delivery_independent_review_v1.json
  - docs/evidence/task41/a1_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - delivery-harness/templates/portable-bundle-manifest.json
  - docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - NEW_CONTROL_PRIMITIVE_BEYOND_FALLBACK_DENY
  - GLOBAL_TASK_MODULE_EXTRACTION
  - RUFF_OR_TYPECHECKER_GATE
  - PROVIDER_OR_NETWORK_CALL
  - CATALOG_OR_HARNESS_REWRITE
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/task41/a1_delivery_completion_evidence_v1.json
      - docs/evidence/task41/a1_delivery_independent_review_v1.json
      - docs/evidence/task41/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-41 — Isolated review merge deny and exclusive raw pages

## Task Outcome Brief

- **Owner decision:** isolated critics must run as part of acceptance, not
  because the owner remembers to reject fallback; H11 live raw pages must not
  clobber existing bytes.
- **Product outcome:** a PR whose independent-review evidence records
  `SINGLE_AGENT_REVIEW_FALLBACK` cannot pass the guarded merge; identical raw
  page bytes replay, different bytes conflict and leave the old file unchanged.
- **Named consumers:** `OWNER_ATTENTION_GATE_V2` guarded merge, TASK-39
  `write_raw_page`, later live-capture atoms, and the owner who does not read
  Python.
- **Cheapest falsifier:** review JSON with `SINGLE_AGENT_REVIEW_FALLBACK` still
  grounds merge evidence, or `write_raw_page` overwrites different bytes.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated critics
  run, exact-head CI is green, and this review evidence itself has no fallback.
- **User-visible result:** owner merge phrase is no longer a memory check for
  self-review; raw evidence stays byte-identical after a retry.
- **Non-goals:** no Ruff/type gate, no TASK-N domain extraction, no Docker,
  no new critic role YAML, no catalog rewrite, no provider calls, no rewrite of
  historical review receipts.
- **Evidence budget:** offline repository work only; no local full gate before
  PR; no new control primitive beyond fail-closed fallback deny.
- **Replan trigger:** catalog/hash cascade, inability to keep TASK-06 storage
  API hash stable, or a requirement to prove critic identity cryptographically.

## Decision capsule

- `DECISION_DELTA`: merge-PASS independent review forbids fallback; H11 raw
  pages adopt create-only write with identical replay.
- `UNCERTAINTY_REMOVED`: owner forgetfulness can no longer bless author=reviewer;
  same run/page cannot silently change bytes.
- `CAPABILITY_OR_EVIDENCE`: gate test plus exclusive-write tests.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: owner exact phrase, then guarded merge.
- `SPEC_ROUTE=NONE`
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_TASK30_OPEN_XB_AND_EXISTING_CRITIC_AGENTS`

## Definition of Done

1. `bound_delivery_evidence` rejects `SINGLE_AGENT_REVIEW_FALLBACK` in
   `non_claims` or findings.
2. Critic prompts and delivery-review require isolated launch; fallback is
   `NOT_READY` for merge.
3. Shared exclusive writer: identical bytes → `REPLAY_IDENTICAL`; different
   bytes → conflict; existing file unchanged.
4. TASK-39 `write_raw_page` uses that writer for body and manifest. Later
   live-capture atoms must call the same helper.
5. Targeted tests pass. This atom's own review evidence has no fallback.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Control-plane merge semantics plus raw
evidence integrity. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
`NO_CRYPTOGRAPHIC_REVIEWER_IDENTITY` remains: isolation is fail-closed on the
recorded fallback admission, not a proof of a second human.
