---
task_id: QUOTE_SURFACE_RETENTION_CLOCK_QUALIFY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0ebb6aa806d623d3c674d7976eaf3ebb1e921f4f
  expected_upstream: origin/main
  expected_upstream_oid: 0ebb6aa806d623d3c674d7976eaf3ebb1e921f4f
  expected_branch: cursor/quote-surface-retention-clock-qualify
  dirty_mode: ALLOW_REPORTED
objective: Qualify quote-surface retention clocks on consumed PR 156 as an engineering fixture, freeze clock_valid from due_at/observed_at/terminal only, and stop before any confirmatory Jupiter capture.
managed_write_set:
  - docs/tasks/QUOTE_SURFACE_RETENTION_CLOCK_QUALIFY_V1.md
  - src/solana_alpha_lab/factory/quote_surface_retention.py
  - src/solana_alpha_lab/factory/quote_surface_retention_clock.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/delivery_tracked_hash.py
  - tests/test_quote_surface_retention_clock.py
  - docs/evidence/quote_surface_retention_clock_qualify/q1_engineering_qualification_v1.json
  - docs/evidence/quote_surface_retention_clock_qualify/q1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_surface_retention_clock_qualify/q1_delivery_independent_review_v1.json
  - docs/evidence/quote_surface_retention_clock_qualify/q1_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_JUPITER_OR_CREDENTIAL_READ
  - SCIENTIFIC_RECLASSIFICATION_OF_PR_156
  - RECAPTURE_OF_PR_156
  - TRADED_ONLY_RESCUE
  - POST_HOC_THRESHOLD_SEARCH
  - CONFIRMATORY_CAPTURE_YAML_OR_PHRASE_WIRING_IN_THIS_PR
  - FULL_DELIVERY_EVIDENCE_PACKAGE_FOR_QUALIFICATION
  - CLOSED_T0_FRICTION_FAMILY_REOPENED
  - RC001_H07_H01_UNPARK_OR_MUTATION
  - ATOM_2_OR_ALPHA_OR_NETRETURN
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - KERNEL_PROVIDER_CALLS_TRUE
  - WALLET_SIGNER_TX_OR_CASH
context_requirements:
  catalog_asset_ids:
    - CTRL-QUOTE-SURFACE-RETENTION-FALSIFIER-001
    - EVIDENCE-QUOTE-SURFACE-RETENTION-FALSIFIER-RUNTIME-001
    - EVIDENCE-QUOTE-SURFACE-RETENTION-FALSIFIER-ACCEPTANCE-001
    - MODULE-FACTORY-V1-QUOTE-SURFACE-RETENTION-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_surface_retention_clock_qualify/q1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_surface_retention_falsifier/a1_quote_surface_retention_falsifier_runtime_receipt_v1.json
      - docs/evidence/quote_surface_retention_falsifier/a1_quote_surface_retention_falsifier_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_SURFACE_RETENTION_CLOCK_QUALIFY_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP`

Owner accepted the external REPLAN. This atom is Phase Q only: offline
clock qualification. It is not Atom 2, not a recapture, and not a
scientific rewrite of PR #156.

`го` is not the confirmatory Jupiter phrase.

`strongest_rejected_alternative`: full scientific atom with confirmatory
YAML, Factory Fit package and Catalog explosion before the six clock
tests pass. That is how the last cycle burned hours.

## PRD-lite

- **Outcome:** `clock_valid` is a PIT clock on `due_at` / `observed_at` /
  `terminal`, not an `outAmount` inequality. Consumed #156 is an
  engineering fixture. Equal `outAmount` on valid separated clocks is
  valid. HTTP 400 is `UNKNOWN`.
- **Consumer:** confirmatory capture (later, exact phrase) and the
  existing retention classifier (`time_separated` derived from
  `clock_status == CLOCK_VALID`).
- **Gap:** #156 classified five RECENT cells as not time-separated
  because reverse and sell `outAmount` were equal, while clocks differed
  by ~45 minutes.
- **Success:** six adversarial vectors pass; #156 replay is
  `ENGINEERING_QUALIFICATION_ONLY` with recent clock-valid 5, traded 6,
  unknown 1; #156 scientific terminal stays
  `SAMPLE_INVALID_REPLAN_REQUIRED`; 0 provider calls.
- **Invalidation:** a clock rule that still uses quote amounts, or any
  KEEP-vs-Y readout treated as a new scientific result.
- **Non-goals:** confirmatory capture, Atom 2, VPS, alpha, TRADED-only
  rescue, post-hoc threshold, new experiment spec, new Factory selector,
  delivery-completion/review/fit Catalog assets.

## SSD-lite

- **Design:** strip clock metadata; `evaluate_observation_clock` raises
  on Y/quote leak; projector derives `time_separated` from clocks;
  `sha256_tracked_path` hashes Git blob/index, not Windows CRLF.
- **Invariants:** KEEP/VETO/Y rules frozen. Qualification evidence is
  not selection/confirmation/promotion/holdout eligible.
- **Rollback:** revert this branch; #156 receipts remain create-only.

## Definition of Done

1. Six adversarial clock tests plus leak rejection.
2. #156 structural replay with recent clock-valid 5, traded 6, unknown 1
   on both the clock helper and `score_retention_observations`;
   qualification packet has no scientific classify fields.
3. Projector no longer uses amount inequality: equal amounts on valid
   clocks stay `time_separated`; different amounts on the same clock do
   not.
4. Naive `apply` of #156 must not be published as science. Compact
   qualification JSON only. No confirmatory YAML. No live calls.
5. Catalog monotonic vs 1223. Do not catalog review/fit/completion.

## Stop

Confirmatory 6+6 capture waits for a later exact Jupiter phrase after
this qualification is merged. This PR must not wire that phrase into a
new capture policy.
