---
task_id: HFIC_PROVENANCE_CLOCK_CORRECTIVE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-27'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 05b5440ed96265e0a58117b5859998b36114b675
  expected_upstream: origin/main
  expected_upstream_oid: 05b5440ed96265e0a58117b5859998b36114b675
  expected_branch: cursor/hfic-provenance-clock-corrective-v1
  dirty_mode: ALLOW_REPORTED
objective: Replace the HFIC 1970 placeholder provenance clock with an injectable
  timezone-aware UTC stage clock, reject future placeholder timestamps, and
  cover already persisted HFIC records with an append-only hash-bound
  correction that does not rewrite immutable RDP bytes or reopen the live
  AUTO session.
managed_write_set:
- docs/tasks/HFIC_PROVENANCE_CLOCK_CORRECTIVE_V1.md
- src/solana_alpha_lab/factory/hfic_clock.py
- src/solana_alpha_lab/factory/hfic_provenance.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_session.py
- scripts/hypothesis_forge.py
- catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json
- catalog/schemas/hfic_provenance_time_correction_v1.schema.json
- schemas/research_memory_projection_v1.sql
- configs/hypothesis_forge_independent_critic_v1.yaml
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- .agents/skills/hypothesis-forge/SKILL.md
- .cursor/commands/hypothesis-forge.md
- tests/test_hfic_provenance_clock.py
- tests/test_hfic_session.py
- tests/test_hfic_preflight.py
- tests/test_hfic_cli.py
- tests/test_hfic_operational_closure_v1.py
- catalog/query_recipes.yaml
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/hfic_provenance_clock_corrective/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_provenance_clock_corrective/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_provenance_clock_corrective/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_API_RPC_WSS
- EXPERIMENT_EXECUTION
- GIT_REWRITE_OF_RDP_BYTES
- REOPEN_OR_REGENERATE_HFIC_SESS_C104
- TWO_RUNG
- WALLET_SIGNER_TX_OR_CASH
- HYPOTHESIS_FORGE_SLASH_INVOKE
- FABRICATED_HISTORICAL_TIMESTAMP
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
      - docs/evidence/hfic_provenance_clock_corrective/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_provenance_clock_corrective/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_provenance_clock_corrective/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_PROVENANCE_CLOCK_CORRECTIVE_V1

## Task Outcome Brief

- **Owner decision:** accept this exact message as the approved design.
  Preserve `HFIC-SESS-C104993AA68805A0`. Do not regenerate AUTO.
- **Product outcome:** future HFIC records carry truthful timezone-aware
  UTC stage times; historical placeholder envelopes are covered by an
  append-only hash-bound correction; slash Forge needs no mid-cycle owner
  intervention.
- **Named consumers:** Hypothesis Forge preflight/freeze/finalize,
  `show-session`, `prove-runtime`, and the later post-merge correction
  step authorized by the exact merge phrase.
- **Cheapest falsifier:** injected-clock tests prove placeholder denial,
  retry/idempotence, unchanged evidence epoch, uncovered-placeholder
  fail-closed, and fully bound correction acceptance without claiming a
  recovered exact time.
- **Evidence budget:** Git-only PRE-MERGE. Post-merge RDP correction is
  authorized only after the exact owner merge phrase.
- **Non-goals:** `/hypothesis-forge`; experiment; provider calls;
  TWO_RUNG; rewriting immutable RDP bytes; fabricating 1970 replacements.

## SPEC_ROUTE=BOTH

Clock, schema, append-only correction, and slash authority are one atom.

## DECISION_DELTA

HFIC provenance time is a trusted UTC stage clock, not Unix epoch.

## UNCERTAINTY_REMOVED

Whether 1970 can remain a legal HFIC envelope/receipt time: no.

## CAPABILITY_OR_EVIDENCE

Injectable clock + fail-closed validation + append-only correction.

## STOP

Exact-head CI, then owner merge gate. Do not apply production correction
before the merge phrase.

## NEXT

Owner merge phrase, then post-merge snapshot/inventory/correction/prove.
