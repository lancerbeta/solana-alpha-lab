---
task_id: ORDINARY_RECENT_EARLY_PATH_H900_FAILED_QUOTES_MEU_REPROJECT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 18fe269525b7d73d44eaffa4aec0900448edfd5d
  expected_upstream: origin/main
  expected_upstream_oid: 18fe269525b7d73d44eaffa4aec0900448edfd5d
  expected_branch: cursor/ordinary-recent-early-path-failed-quotes-meu-reproject
  dirty_mode: ALLOW_REPORTED
objective: Bind Jupiter Failed-to-get-quotes H900 bodies as MARKET_EXECUTION_UNAVAILABLE and offline-reproject the frozen early-path receipt to a rule-decidable CLOSE without a second live capture.
managed_write_set:
  - docs/tasks/ORDINARY_RECENT_EARLY_PATH_H900_FAILED_QUOTES_MEU_REPROJECT_V1.md
  - configs/ordinary_recent_early_path_h900_failed_quotes_meu_reproject_v1.yaml
  - src/solana_alpha_lab/quote_native_evidence_fit_panel.py
  - src/solana_alpha_lab/ordinary_recent_early_path_h900_failed_quotes_meu_reproject.py
  - scripts/run_ordinary_recent_early_path_h900_failed_quotes_meu_reproject.py
  - tests/test_ordinary_recent_early_path_h900_failed_quotes_meu_reproject.py
  - tests/test_quote_native_evidence_fit_panel.py
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/fixtures/index.json
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/fixtures/50ef83cfc5f72edd191f39c4a3ce5a6b7a90ec48456a82d92af35c976c0ba3b1.body
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/fixtures/839d8c8a933f4dced65a9b4afed09169436bf21cd24161d78ff731e5303535ea.body
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/fixtures/788e47d2a69a3d8563fce09928f7285e9a9aec6a13c75f62062cb67205680ca1.body
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/fixtures/4f39d14ee53b98d4e5a351591232d2280fcee6e26ff65eb012b042d08a8a2090.body
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_ordinary_recent_early_path_h900_failed_quotes_meu_reproject_runtime_receipt_v1.json
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_ordinary_recent_early_path_h900_failed_quotes_meu_reproject_acceptance_v1.json
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_delivery_independent_review_v1.json
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_delivery_factory_fit_v1.json
  - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_delivery_completion_evidence_v1.json
  - docs/reports/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_owner_readout_v1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - NEW_PROVIDER_OR_CREDENTIAL_CALL
  - DOTENV_READ
  - SOURCE_RECEIPT_REWRITTEN
  - UNKNOWN_AS_ZERO
  - ORGANIC_OR_FLOW_OR_TX_IMBALANCE_X
  - SECOND_LIVE_EARLY_PATH_CAMPAIGN
  - STRATEGY_BOT_SHADOW_CLAIM
  - ALPHA_OR_NETRETURN
  - H3600_OR_H4
  - EARN_CLAIM_FROM_INCOMPLETE_SELECTED_QUARTILE
context_requirements:
  catalog_asset_ids:
    - MODULE-ORDINARY-RECENT-EARLY-PATH-H900-AUDITION-001
    - MODULE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_delivery_completion_evidence_v1.json
      - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_delivery_independent_review_v1.json
      - docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# ORDINARY_RECENT_EARLY_PATH_H900_FAILED_QUOTES_MEU_REPROJECT_V1

## Task Outcome Brief

Offline taxonomy repair and scientific close for the already-captured early-path
H900 audition. Jupiter `Failed to get quotes` on H900 SELL was mis-typed as
`UNKNOWN_TYPED_FAILURE`, which blocked the frozen selected-quartile rule and
produced `INVALID_EVIDENCE_YIELD`. Binding that exact message to
`MARKET_EXECUTION_UNAVAILABLE` and reprojecting the frozen receipt yields
`CLOSE_EARLY_PATH_CANDIDATE` with zero provider calls.

## Decision capsule

- `DECISION_DELTA`: early-path mcap X stays measurable; the open gap was exit-quote
  taxonomy, not a new estimand or a second live campaign.
- `UNCERTAINTY_REMOVED`: whether selected-quartile H900 `Failed to get quotes`
  is measurement incompleteness or market-execution unavailability under the
  frozen rule.
- `CAPABILITY_OR_EVIDENCE`: shared `project_quote` MEU bind + hash-pinned offline
  reproject over the early-path runtime receipt and four Git fixtures.
- `STOP`: no new Jupiter capture; no rewrite of the historical
  `INVALID_EVIDENCE_REPLAN` acceptance; no EARN/alpha/Strategy claims.
- `NEXT`: after merge, choose a new simple market-state estimand; do not re-open
  organic/flow/`TX_IMBALANCE` or early-path live capture.

## SPEC_ROUTE

`BOTH` — PRD_LITE + DESIGN_SPEC inside this exact contract (no parallel memo).

## PRD_LITE

- **Outcome**: `CLOSE_EARLY_PATH_CANDIDATE` from frozen evidence after MEU bind.
- **Product link**: T0 market-state → executable H900 audition family (Muv-3 /
  early-path branch).
- **Downstream consumer**: owner replan after early-path close; future auditions
  consuming `project_quote` taxonomy.
- **Current gap**: historical yield blocked scientific close despite measurable X
  and negative observed Y on all rankable exits.
- **Success observable**: remapped selected top-quartile MEU true; terminal
  `CLOSE_EARLY_PATH_CANDIDATE`; provider_requests = 0.
- **Invalidation**: fixture/hash drift; remapped count ≠ 4; terminal not CLOSE;
  any new provider/credential call.
- **Non-goals**: live campaign; organic/flow/`TX_IMBALANCE`; Strategy/Bot/Shadow;
  alpha/NetReturn; H3600/H4; rewriting source acceptance bytes.

## SSD_LITE

- **Baseline**: `origin/main` `18fe269525b7d73d44eaffa4aec0900448edfd5d`; source
  receipt SHA `0acdc847…786b`.
- **Design**: exact Jupiter prose `Failed to get quotes` ∈ MEU codes in
  `project_quote`; offline reproject loads fixture bodies by response SHA;
  reuse early-path `score_audition` with `CLOSE_EARLY_PATH_CANDIDATE`.
- **Invariants**: UNKNOWN never zero; historical yield receipt immutable;
  capture_authorized false; cash $0.
- **Affected surfaces**: quote panel taxonomy; early-path evidence family;
  catalog/nav.
- **Failure modes**: hash drift; missing fixture; unexpected error message;
  selected MEU false after remap.
- **Validation**: targeted unittest + catalog/nav/secret scan; no provider.
- **Rollback**: revert branch; taxonomy bind and evidence leave main untouched.

## REPLAN_TRIGGER

Same selected-quartile incompleteness after MEU bind; need for a second live
campaign; desire to salvage organic/flow/`TX_IMBALANCE` as X.

## Definition of Done

- Taxonomy pin + offline reproject PASS locally.
- Acceptance records `CLOSE_EARLY_PATH_CANDIDATE` and preserves historical
  `INVALID_EVIDENCE_REPLAN` as source decision.
- Catalog/nav generated; PR green; merge only after exact owner phrase.

## Owner gates

No provider phrase. Exact merge phrase only after CI on unchanged head.
