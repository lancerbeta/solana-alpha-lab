---
task_id: HFIC_DISCOVERY_PROSPECT_MEMORY_AND_NEXT_ACTION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-27'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: dd6692edf9cbfa44c9535695aa23751403052ca1
  expected_upstream: origin/main
  expected_upstream_oid: dd6692edf9cbfa44c9535695aa23751403052ca1
  expected_branch: cursor/hfic-discovery-prospect-memory-next-action-v1
  dirty_mode: ALLOW_REPORTED
objective: Persist the 23-direction HFIC scientific-discovery research as a
  discoverable non-authoritative prospect portfolio and bind one typed
  epistemic next action into ordinary no-worthy freeze without changing
  HFIC-V1.1 candidate generation.
managed_write_set:
- docs/tasks/HFIC_DISCOVERY_PROSPECT_MEMORY_AND_NEXT_ACTION_V1.md
- .gitattributes
- docs/architecture/prospects/HFIC_SCIENTIFIC_DISCOVERY_ENGINE_RESEARCH_V1.md
- docs/architecture/prospects/hfic_scientific_discovery_prospects_v1.yaml
- docs/architecture/intents/ARCH-INTENT-006-hypothesis-discovery-and-opportunity-surface.md
- catalog/schemas/hfic_scientific_discovery_prospects_v1.schema.json
- catalog/schemas/hfic_next_epistemic_action_draft_v1.schema.json
- catalog/schemas/hfic_next_epistemic_action_v1.schema.json
- catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json
- src/solana_alpha_lab/factory/hfic_prospects.py
- src/solana_alpha_lab/factory/hfic_session.py
- scripts/hypothesis_forge.py
- .agents/skills/hypothesis-forge/SKILL.md
- .cursor/commands/hypothesis-forge.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- configs/hypothesis_forge_independent_critic_v1.yaml
- tests/fixtures/hypothesis_forge/next_action_wait_valid_v1.json
- tests/fixtures/hypothesis_forge/next_action_forward_valid_v1.json
- tests/fixtures/hypothesis_forge/next_action_capability_valid_v1.json
- tests/fixtures/hypothesis_forge/next_action_invalid_v1.json
- tests/test_hfic_discovery_prospects_and_next_action.py
- tests/test_hfic_session.py
- tests/test_hfic_cli.py
- tests/test_hfic_forge_context_and_no_worthy.py
- tests/test_arch_intent_006_hypothesis_discovery_surface.py
- catalog/assets/lifecycle.yaml
- catalog/query_recipes.yaml
- catalog/assets/architecture.yaml
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_temp_e2e_receipt_v1.json
- docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- AUTONOMOUS_HYPOTHESIS_GENERATOR
- PROVIDER_API_RPC_WSS
- EXPERIMENT_EXECUTION
- WALLET_SIGNER_TX_OR_CASH
- PRODUCTION_RDP_MUTATION
- V2_BRANCH_OR_PR_MIX
- HFIC_V1_1_SEARCH_IDENTITY_CHANGE
- ARCH_INTENT_006_TRIGGER_CLAIM
- MAP_ELITES_OR_RANKER_IMPLEMENTATION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-006-hypothesis-discovery-and-opportunity-surface.md
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_discovery_prospect_memory_and_next_action/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_DISCOVERY_PROSPECT_MEMORY_AND_NEXT_ACTION_V1

## Task Outcome Brief

- **Owner decision:** execute the attached PRD+SSD after V2 persisted
  terminal. Isolated branch/PR. No V2 mix.
- **Predecessor terminal:** `STOP_BEFORE_QUOTES_ELIGIBLE_BELOW_FLOOR`
  (COMPLETE sha256 `396035155d16ba13e2164335e453dfacb0371725cd8f572af71e001f2a11bdaa`).
- **Research bind:** UTF-8 LF no BOM, 36074 bytes, SHA-256
  `1a2ac80b02e0a77a892d7ea27b2cff8a03ca99c3a1805c95c5d2611423cabf67`.
- **Product outcome:** 23-record advisory portfolio + same-slash typed
  next action after `NO_WORTHY_HYPOTHESIS`. Prompt A stays `HFIC-V1.1`.
  Next-action prompt identity is `HFIC-NEXT-V1.0`.
- **Named consumer:** `HFIC-POST-NO-WORTHY-ROUTER`.
- **Cheapest falsifier:** TEMP-root tests for atomic persist, replay,
  historical LEGACY_NOT_RECORDED, selected-path denial, max-3 query,
  epoch unchanged, Git/provider/experiment/wallet=0.
- **Non-goals:** MAP-Elites, ranker, RAG, generator, provider, V2
  capture, production RDP mutation, Forge production invoke.

## DECISION_DELTA

Ordinary `/hypothesis-forge` no longer ends a valid `NO_WORTHY` at bare
`STOP`. Research is Catalog-discoverable without contaminating Prompt A.

## UNCERTAINTY_REMOVED

Whether a bounded post-no-worthy action can be hash-bound into the same
append-only transaction without changing candidate search identity.

## CAPABILITY_OR_EVIDENCE

`query_prospects` + `bind_next_epistemic_action` + freeze `--next-action`.

## STOP

Exact-head CI green. Owner merge phrase. No production Forge invoke.

## NEXT

After merge: read-only closure
`HFIC_DISCOVERY_PROSPECT_MEMORY_AND_NEXT_ACTION_READY`. Owner's next
ordinary action is `/hypothesis-forge` in a new thread.

## REPLAN_TRIGGER

V2 file mix; HFIC-V1.1 identity bump; ARCH-INTENT-006 trigger claim;
production RDP write.

## Definition of Done

All are mandatory:

1. V2 predecessor has a persisted terminal and is not mixed into this branch.
2. Research bytes in Git match the supplied SHA and are Catalog-discoverable.
3. Exactly 23 machine-readable prospect records validate and reflect current §6 dispositions.
4. ARCH-INTENT-006 remains WATCH-only and does not claim trigger proof.
5. Prospect portfolio is absent from ordinary preflight/Prompt A context.
6. After no-worthy, same slash produces exactly one typed next action or deterministic safe wait without owner intervention.
7. New no-worthy session and action are atomically persisted and hash-bound.
8. Replay returns the same session/action and creates no new search.
9. Historical no-worthy sessions remain readable/provable without backfill.
10. Selected candidate/Critic/classifier path is unchanged.
11. Missing/corrupt/mismatched referenced action fails closed.
12. Prospect/action self-events do not change evidence epoch.
13. TEMP E2E proves Git unchanged, provider/API/RPC/WSS 0, experiment 0, credentials 0, wallet/transaction 0.
14. Catalog/navigation/harness converge without manual hash edits.
15. Three isolated reviews pass after findings are resolved.
16. One exact-head PR has green CI.
17. Post-merge read-only closure returns `HFIC_DISCOVERY_PROSPECT_MEMORY_AND_NEXT_ACTION_READY`.
