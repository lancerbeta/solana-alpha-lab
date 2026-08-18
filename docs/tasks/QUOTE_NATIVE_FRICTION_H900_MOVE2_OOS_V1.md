---
task_id: QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1
task_version: '1.0'
status: DONE
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: fa3a64e39fefc0518ff43da02b12c190e35e2060
  expected_upstream: origin/main
  expected_upstream_oid: fa3a64e39fefc0518ff43da02b12c190e35e2060
  expected_branch: cursor/quote-native-friction-h900-move2-oos
  dirty_mode: ALLOW_REPORTED
objective: Replicate the frozen H900 ordinal sign test on one fresh Free-key 6+6 live cohort that excludes the 12 A1 frozen_cells mints, fail-closed on capture, and close the exact mechanism if concordant is not greater than discordant.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1.md
  - configs/quote_native_friction_h900_move2_oos_v1.yaml
  - src/solana_alpha_lab/quote_native_friction_h900_move2_oos.py
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - scripts/run_quote_native_friction_h900_move2_oos.py
  - tests/test_quote_native_friction_h900_move2_oos.py
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - docs/evidence/quote_native_friction_h900_move2_oos/a1_quote_native_friction_h900_move2_oos_runtime_receipt_v1.json
  - docs/evidence/quote_native_friction_h900_move2_oos/a1_quote_native_friction_h900_move2_oos_acceptance_v1.json
  - docs/reports/quote_native_friction_h900_move2_oos/a1_owner_readout_v1.md
  - docs/evidence/quote_native_friction_h900_move2_oos/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_friction_h900_move2_oos/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_friction_h900_move2_oos/a1_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - registries/decisions_negative_results.yaml
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION
  - CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT
  - DOTENV_READ
  - API_KEY_IN_URL_LOG_RECEIPT_OR_GIT
  - UNSAFE_RESPONSE_HEADER_RETAINED
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - WALLET_SIGNER_TRANSACTION_OR_DEPLOYMENT
  - RETRY_OR_FALLBACK
  - CALL_CAP_EXCEEDED
  - PACE_BELOW_THREE_SECONDS
  - SECOND_PROVIDER_OR_PAID_PLAN
  - THRESHOLD_OR_COHORT_RULE_DRIFT
  - CONCORDANCE_RATE_FLOOR_FIT_ON_A1
  - A1_RUNTIME_RECEIPT_REWRITE
  - A1_MINT_REUSED_IN_COHORT
  - H3600_USED_AS_SEARCHABLE_Y
  - H13_H11_H07_OR_H02_UNPARK
  - MOVE_3_OR_ALPHA_CLAIM
  - RECAPTURE_ONLY_SUFFIX
  - FAMILY_CLOSE_ON_SAMPLE_INVALID
  - MECHANISM_SCORE_ON_INVALID_CAPTURE
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-ACCEPTANCE-001
    - EVIDENCE-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_admissible_friction_audition_v1.yaml
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_acceptance_v1.json
      - docs/evidence/quote_native_friction_h900_move2_oos/a1_quote_native_friction_h900_move2_oos_runtime_receipt_v1.json
      - docs/evidence/quote_native_friction_h900_move2_oos/a1_quote_native_friction_h900_move2_oos_acceptance_v1.json
      - docs/evidence/quote_native_friction_h900_move2_oos/a1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_native_friction_h900_move2_oos/a1_delivery_independent_review_v1.json
      - docs/evidence/quote_native_friction_h900_move2_oos/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1

## Owner authorization

`OK QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1: one fresh Jupiter Free-key quote-native campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding the 12 A1 frozen_cells mints hash-bound to runtime receipt 75f60a155b7db6ddb8c801c9ff5060ce5e4e7fe641b836ff35edeb91534c308e; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; freeze the same QuotedRoundTripFriction(t0) to QuotedLiquidationRecovery(H900) ordinal sign test; do not fit a concordance threshold on the A1 31/14 sample; H3600 robustness only not searchable Y; capture FAIL pauses with no recapture-only retry; capture PASS plus sample invalid does not close the family; capture PASS plus sample valid plus concordant <= discordant closes the exact mechanism; capture PASS plus sample valid plus concordant > discordant is REPLICATED_SIGN_NOT_ALPHA not alpha and not MOVE 3; no H13/H11/H07/H02 unpark; no NetReturn/alpha.`

The owner selected one disjoint Free-key replication of the frozen H900 sign test. The key value is never requested, displayed, stored, or committed.

## Task Outcome Brief

- **OWNER_DECISION:** whether the frozen H900 sign replicates on a fresh untouched live cohort, or the exact mechanism closes as a non-replicated screening fluke.
- **PRODUCT_OUTCOME:** one admissible MOVE 2 campaign whose terminal is either `REPLICATED_SIGN_NOT_ALPHA` or `CLOSE_EXACT_QUOTE_FRICTION_MECHANISM`, unless capture or sample gates stop first.
- **NAMED_CONSUMER:** the goal owner deciding to leave a replicated sign unextended versus close the exact quote-friction mechanism versus leave the family open versus pause the route.
- **CHEAPEST_FALSIFIER:** on a valid sample, `concordant <= discordant` under the frozen ordinal sign test. No rate floor is fit on the A1 31/14 window.
- **TERMINAL_OUTCOMES:** `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE` | `SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY` | `SAMPLE_INVALID_TRADED_CONTROL_KILL` | `CLOSE_EXACT_QUOTE_FRICTION_MECHANISM` | `REPLICATED_SIGN_NOT_ALPHA` | `CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED` | `TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED`.
- **USER_VISIBLE_RESULT:** a Russian readout of capture, A1 exclusion, complete/missing cells, H900 sign versus A1, H3600 robustness, and explicit non-claims.
- **NON_GOALS:** recapture-only; A1 rewrite; threshold fit; H3600 as searchable Y; H13/H11/H07/H02; paid plan; second provider; `/build`/`/execute`; NetReturn; alpha; MOVE 3; PIT; confirmation-as-alpha.
- **EVIDENCE_BUDGET:** one campaign; at most 60 provider GETs; one credential read after reservation and credential-free preflight; no retry/fallback; global interval at least three seconds.
- **REPLAN_TRIGGER:** a second capture-bookkeeping failure; any new provider or paid tier; fitting a concordance threshold on A1; reusing an A1 mint; using H3600 as searchable Y; family close on sample-invalid; mechanism scoring despite invalid capture.

## Decision capsule

- `DECISION_DELTA:` KEEP the audition next-boundary and run the predeclared disjoint replication.
- `UNCERTAINTY_REMOVED:` whether `concordant > discordant` on the frozen H900 relation survives one fresh 6+6 that cannot reuse A1 mints.
- `CAPABILITY_OR_EVIDENCE:` WRAP the admissible audition runner with a hash-bound A1 mint exclusion set and remap `DIRECTIONAL_HINT_NOT_CONFIRMATION` to `REPLICATED_SIGN_NOT_ALPHA`.
- `STOP:` after exact-head CI; merge only with the repository phrase bound to this PR/head.
- `NEXT:` capture FAIL → pause, no recapture-only. Sample invalid → family open. Failed sign → close exact mechanism. Replicated sign → later owner contract only, not MOVE 3.
- `SPEC_ROUTE=BOTH`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative:` leave the A1 hint unextended without an OOS falsifier.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=WRAP_EXISTING_ADMISSIBLE_AUDITION_RUNNER_AND_H900_SCORER`

`ENTRY_VERDICT=START`

`OWNER_CAPTURE_PHRASE=OK QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1: one fresh Jupiter Free-key quote-native campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding the 12 A1 frozen_cells mints hash-bound to runtime receipt 75f60a155b7db6ddb8c801c9ff5060ce5e4e7fe641b836ff35edeb91534c308e; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; freeze the same QuotedRoundTripFriction(t0) to QuotedLiquidationRecovery(H900) ordinal sign test; do not fit a concordance threshold on the A1 31/14 sample; H3600 robustness only not searchable Y; capture FAIL pauses with no recapture-only retry; capture PASS plus sample invalid does not close the family; capture PASS plus sample valid plus concordant <= discordant closes the exact mechanism; capture PASS plus sample valid plus concordant > discordant is REPLICATED_SIGN_NOT_ALPHA not alpha and not MOVE 3; no H13/H11/H07/H02 unpark; no NetReturn/alpha.`

## Estimand (screening, frozen before first call)

Same as A1. X = `QuotedRoundTripFriction`. Y = `QuotedLiquidationRecovery` at H900. Direction: more negative X ranks with more negative Y. Comparable pairs use the existing ordinal sign test. No concordance rate floor. `SELL_H3600` is robustness only.

A1 runtime receipt `75f60a155b7db6ddb8c801c9ff5060ce5e4e7fe641b836ff35edeb91534c308e` is immutable. Its 12 `frozen_cells[].mint` values are the exclusion set.

## Capture gate (fail-closed, independent of market outcomes)

Capture PASS requires the wrapped audition reservation and hash-bound `observed_at` envelopes. Capture FAIL → `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE` and no mechanism conclusion.

## Definition of Done

1. Fresh 6 RECENT + 6 TRADED Tokens V2 cohort with empty intersection against the A1 exclusion set.
2. One process-environment `JUPITER_API_KEY` read after reservation and credential-free preflight; header-only; no `.env`.
3. Hash-bound capture envelopes and reservation in the canonical MOVE 2 runtime receipt.
4. Frozen H900 scorer runs only after capture PASS; no A1-fitted rate floor.
5. Four-way-plus-replication terminal is recorded; Russian readout names capture, exclusion, sample, mechanism, and non-claims.
6. Catalog, independent review, Factory Fit, and guarded PR/CI for this branch.

## Recorded unique-attempt terminal

The unique Free-key attempt capture-PASSed, excluded the 12 A1 mints, and
scored the same-run `SELL_H900` envelopes of that attempt. Canonical Git
terminal:

`REPLICATED_SIGN_NOT_ALPHA`.

Sample valid (10 complete X/Y, 9 time-separated; 21 concordant / 15
discordant). Family open. Recapture-only not executed. H3600 was not observed
and remains robustness only. Git `DONE` is technical closure of this exact
contract, not alpha, NetReturn, or MOVE 3. A later live run needs a new owner
phrase.
