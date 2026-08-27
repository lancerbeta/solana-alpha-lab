---
task_id: HFIC_NEXT_EVIDENCE_BIND_AND_CONTEXT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-27'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 240843deef71835b60c04a1dfa371e767ec0af30
  expected_upstream: origin/main
  expected_upstream_oid: 240843deef71835b60c04a1dfa371e767ec0af30
  expected_branch: cursor/hfic-next-evidence-bind-and-context-v1
  dirty_mode: ALLOW_REPORTED
objective: PRE-MERGE hash-verified offline bind of the existing 2026-08-24
  valuation-window capture as a DISCOVERY_ONLY_SECOND_LOOK panel, plus
  FORGE_CONTEXT_PACKET visibility, relevance-ranked prior, hash-bound context
  artifact, and canonical NO_WORTHY_HYPOTHESIS without a dummy Critic.
managed_write_set:
- docs/tasks/HFIC_NEXT_EVIDENCE_BIND_AND_CONTEXT_V1.md
- src/solana_alpha_lab/factory/early_market_panel_field_semantics.py
- src/solana_alpha_lab/factory/early_market_panel_importer.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_session.py
- scripts/import_early_market_panel.py
- catalog/schemas/hypothesis_forge_draft_v1.schema.json
- catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json
- tests/fixtures/early_market_panel/temp_capture_v1/DISCOVERY_SEARCH_R0.body
- tests/fixtures/early_market_panel/temp_capture_v1/DISCOVERY_SEARCH_R0.envelope.json
- tests/fixtures/early_market_panel/temp_capture_v1/source_receipt.json
- tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json
- tests/test_early_market_panel_importer.py
- tests/test_hfic_forge_context_and_no_worthy.py
- tests/test_hfic_session.py
- tests/test_hfic_preflight.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/hfic_next_evidence_bind_and_context/a1_field_semantics_proof_v1.json
- docs/evidence/hfic_next_evidence_bind_and_context/a1_temp_e2e_receipt_v1.json
- docs/evidence/hfic_next_evidence_bind_and_context/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_next_evidence_bind_and_context/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_next_evidence_bind_and_context/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_API_RPC_WSS
- FIELD_SEMANTICS_UNPROVEN_WITH_DATASET_BIND
- CONFIRMATORY_REUSE_OF_VALUATION_WINDOW
- X_Y_SCORE_OR_EXPERIMENT
- HYPOTHESIS_FORGE_SLASH_INVOKE
- TWO_RUNG
- CLOSED_FAMILY_REOPEN
- RAW_BODY_COMMITTED_TO_GIT
- HYP_EARLY_TAKER_VOLUME_MIX_REGISTERED
- POST_MERGE_BIND_BEFORE_OWNER_PHRASE
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
      - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_acceptance_v1.json
      - docs/evidence/hfic_next_evidence_bind_and_context/a1_field_semantics_proof_v1.json
      - docs/evidence/hfic_next_evidence_bind_and_context/a1_temp_e2e_receipt_v1.json
      - docs/evidence/hfic_next_evidence_bind_and_context/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_next_evidence_bind_and_context/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_next_evidence_bind_and_context/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_NEXT_EVIDENCE_BIND_AND_CONTEXT_V1

## Task Outcome Brief

- **Owner decision:** accept DESIGN_ONLY `EXISTING_CAPTURE_REUSE_PROVEN`.
  New provider collection is not the first step. Bind the existing
  2026-08-24 valuation-window raw panel as
  `DATASET-MANIFEST-EARLY-MARKET-PANEL-VALUATION-WINDOW-001` with
  scientific fence `DISCOVERY_ONLY_SECOND_LOOK`.
- **Product outcome:** hash-verified offline importer, proven
  `R0_TAKER_VOLUME_MIX` field semantics (ratio only), Forge context
  packet with datasets/capabilities/features/closed ledger and
  relevance-ranked prior, hash-bound RDP context artifact, and
  canonical `NO_WORTHY_HYPOTHESIS` without a dummy Critic.
- **Named consumers:** Hypothesis Forge preflight; later owner-invoked
  `/hypothesis-forge` after POST-MERGE bind. This atom does not run Forge.
- **Cheapest falsifier:** TEMP E2E import → fail-closed commit-point
  publication; yield below 10 is `SAMPLE_INVALID` and not a usable hint;
  yield of 10 or more advertises the hint; strict envelope `observed_at`;
  enumerated context (second registered dataset/capability without
  editing `hfic_preflight.py`); content-addressed context artifact
  required by load/show/prove; idempotent retry; `provider_calls=0`;
  runtime Git unchanged; no X↔Y score.
- **Evidence budget:** offline only. `provider_calls_for_bind=0`.
- **Non-goals:** provider collection; X↔Y scoring; experiment;
  `/hypothesis-forge`; TWO_RUNG; reopening closed families; registering
  `HYP-EARLY-TAKER-VOLUME-MIX-H900-V1`; POST-MERGE production bind
  before the exact owner bind phrase.

## Scientific fence

The 2026-08-24 valuation-window panel is `DISCOVERY_ONLY_SECOND_LOOK`.

It may:

- create a new `evidence_epoch`;
- show Forge a new multi-token PIT surface;
- expose discovery hint `R0_TAKER_VOLUME_MIX`.

It must not:

- be a confirmatory/independent falsifier for
  `HYP-EARLY-TAKER-VOLUME-MIX-H900-V1`;
- give PASS/PROMOTE on X↔stored Y;
- support a new alpha claim.

If Forge later forms that hypothesis and Critic passes it, the only
allowed falsifier is a new pre-registered forward window with unchanged
X, Y, population, missingness and kill rules.

Required dataset labels:

- `evidence_role=DISCOVERY_ONLY_SECOND_LOOK`
- `outcome_previously_consumed=true`
- `confirmatory_reuse_forbidden=true`
- `provider_calls_for_bind=0`

## Stages

PRE-MERGE (this PR): code + TEMP proof + isolated review + one PR +
exact-head CI + stop at owner merge gate.

POST-MERGE: only after the exact owner bind phrase, hash-verified bind
on the active production-local RDP. Do not auto-run `/hypothesis-forge`.

## DECISION_DELTA

Existing capture reuse is the next evidence step. The panel is a second
look, not a confirmatory sample.

## UNCERTAINTY_REMOVED

Whether `stats5m.buyVolume`/`sellVolume` can be bound as a dimensionless
R0-only mix ratio, and whether Forge can see that surface without
first-five iteration order or a forced selected candidate.

## CAPABILITY_OR_EVIDENCE

Offline hash-verified importer + discovery-only dataset + corrected
`FORGE_CONTEXT_PACKET` + `NO_WORTHY_HYPOTHESIS`.

## STOP

Exact-head CI green. Owner merge phrase. Separate post-merge bind phrase.
No production bind and no Forge in this stage.

## NEXT

Owner merge, then the post-merge bind phrase. Then stop.

## REPLAN_TRIGGER

`FIELD_SEMANTICS_UNPROVEN`, hash/schema mismatch that cannot fail closed
honestly, or any need for a new provider collection.
