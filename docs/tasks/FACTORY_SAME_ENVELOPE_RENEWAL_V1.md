---
task_id: FACTORY_SAME_ENVELOPE_RENEWAL_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-29"
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
  expected_base: 06924bc6878dbd2116acfbb4fb8aed21a10ee045
  expected_upstream: origin/main
  expected_upstream_oid: 06924bc6878dbd2116acfbb4fb8aed21a10ee045
  expected_branch: cursor/factory-same-envelope-renewal-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Renew an unchanged observation envelope by shifting its admission window
  forward with the existing register, authorize, and rollover commands.
  Do not admit the successor before the boundary and do not ask the owner
  for a weekly phrase when nothing but the dates changed.
managed_write_set:
  - docs/tasks/FACTORY_SAME_ENVELOPE_RENEWAL_V1.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/evidence/factory_same_envelope_renewal/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_same_envelope_renewal/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_same_envelope_renewal/a1_delivery_factory_fit_v1.json
  - src/solana_alpha_lab/factory/same_envelope_renewal.py
  - scripts/renew_same_observation_envelope.py
  - tests/test_same_envelope_renewal.py
  - configs/factory_remote_ops/factory-same-envelope-renewal.service
  - configs/factory_remote_ops/factory-same-envelope-renewal.timer
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_VPS_DEPLOY_OR_MUTATION_REQUIRED
  - PROVIDER_API_RPC_WSS_OR_NON_GITHUB_CREDENTIAL_REQUIRED
  - CALL_LEDGER_DIAGNOSTICS_REQUIRED
  - CAMPAIGN_WINDOW_LENGTH_CHANGE_REQUIRED
  - APPEND_ONLY_LIFECYCLE_HISTORY_REWRITE_REQUIRED
context_requirements:
  catalog_asset_ids:
    - DOC-FACTORY-LIFECYCLE-COLLECTOR-001
  l2_roles:
    - LIFECYCLE
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
      - src/solana_alpha_lab/factory/same_envelope_renewal.py
      - scripts/renew_same_observation_envelope.py
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_same_envelope_renewal/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_same_envelope_renewal/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_same_envelope_renewal/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_SAME_ENVELOPE_RENEWAL_V1

## DECISION_DELTA

An unchanged next week is the same grant. A daily oneshot may register,
authorize, and roll it over inside 72 hours of the boundary. The owner phrase
remains required only when the envelope is not a pure time shift, the boundary
has passed, or more than one activation is currently admitting.

## UNCERTAINTY_REMOVED

Whether removing the weekly paste requires a new authority product. It does
not. `rollover_schedule` already schedules the successor at the boundary.

## CAPABILITY_OR_EVIDENCE

`scripts/renew_same_observation_envelope.py` and
`factory-same-envelope-renewal.timer`. Focused tests show a pure shift rolls
over at the boundary, a past boundary and an early clock do not write, two
projected ACTIVE rows refuse, and a changed seed is not a pure shift.

## ACCEPTANCE

- Successor `transition_effective_at` is the predecessor `stops_admitting_at`.
- `activate_schedule` is not called.
- Historical DRAINING does not count as a second admitting activation.
- The authorize phrase is not printed.
- Code deploy does not enable the timer.

## NON-GOALS

No live deploy in this change. No call_ledger work. No longer campaign window.
No new Telegram channel.

## STOP

Stop after review, exact-head CI, and merge. Do not deploy to the factory host
in this task. Host enable of the timer is a later operate step.

## NEXT

After merge, deploy the exact main SHA with canonical-forward as root, then
enable `factory-same-envelope-renewal.timer` beside the owner-pulse timer.
Before 2026-10-02T13:00:00Z a live run must return TOO_EARLY.
