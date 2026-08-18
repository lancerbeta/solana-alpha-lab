---
task_id: QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1
task_version: '1.1'
status: DONE
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6c0a23fb37877032ba4add21d65bed643396bfbb
  expected_upstream: origin/main
  expected_upstream_oid: 6c0a23fb37877032ba4add21d65bed643396bfbb
  expected_branch: cursor/quote-native-admissible-friction-audition
  dirty_mode: ALLOW_REPORTED
objective: Run one fresh Jupiter Free-key quote-native campaign that fail-closed proves capture integrity and, only if capture PASSes, scores the frozen QuotedRoundTripFriction(t0) to QuotedLiquidationRecovery(H900) audition without a recapture-only suffix.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1.md
  - configs/quote_native_admissible_friction_audition_v1.yaml
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - scripts/run_quote_native_admissible_friction_audition.py
  - tests/test_quote_native_admissible_friction_audition.py
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json
  - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_acceptance_v1.json
  - docs/reports/quote_native_admissible_friction_audition/a1_owner_readout_v1.md
  - docs/evidence/quote_native_admissible_friction_audition/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_admissible_friction_audition/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_admissible_friction_audition/a1_delivery_factory_fit_v1.json
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
  - H3600_USED_AS_SEARCHABLE_Y
  - H13_H11_H07_OR_H02_UNPARK
  - MOVE_2_OR_ALPHA_CLAIM
  - RECAPTURE_ONLY_SUFFIX
  - FAMILY_CLOSE_ON_SAMPLE_INVALID
  - MECHANISM_SCORE_ON_INVALID_CAPTURE
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-ACCEPTANCE-001
    - EVIDENCE-QUOTE-NATIVE-FRICTION-H900-FALSIFIER-ACCEPTANCE-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_evidence_channel_qualification_v1.yaml
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_acceptance_v1.json
      - docs/evidence/quote_native_friction_h900_falsifier/a1_quote_native_friction_h900_falsifier_acceptance_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_acceptance_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_delivery_independent_review_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1

## Owner authorization

`OK QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1: one fresh Jupiter Free-key quote-native campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; freeze QuotedRoundTripFriction(t0) to QuotedLiquidationRecovery(H900) before first call; H3600 collected as predeclared robustness not a second searchable Y; capture FAIL pauses the route with no recapture-only retry; capture PASS plus sample invalid does not close the family; capture PASS plus sample valid plus no direction closes the exact mechanism; directional hint stops and leaves MOVE 2 as a later contract; no H13/H11/H07/H02 unpark; no NetReturn/alpha.`

The owner selected this bounded dual-purpose campaign. The key value is never requested, displayed, stored, or committed.

## Task Outcome Brief

- **OWNER_DECISION:** whether the quote-native friction family deserves a later MOVE 2, must close the exact H900 mechanism, remain open after sample-invalid, or stay paused because capture failed again.
- **PRODUCT_OUTCOME:** one fresh admissible capture plus, only if capture PASSes, one frozen screening result for `QuotedRoundTripFriction(t0)` → `QuotedLiquidationRecovery(H900)`.
- **NAMED_CONSUMER:** the goal owner deciding EXTEND_TO_FRESH_OOS versus CLOSE_EXACT_QUOTE_FRICTION_MECHANISM versus leave the family open versus leave the route paused.
- **CHEAPEST_FALSIFIER:** capture envelope/reservation fail-closed; then frozen concordance of t0 friction versus H900 recovery on the same 6+6 live cohort; H3600 is robustness only.
- **TERMINAL_OUTCOMES:** `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE` | `SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY` | `SAMPLE_INVALID_TRADED_CONTROL_KILL` | `CLOSE_EXACT_QUOTE_FRICTION_MECHANISM` | `DIRECTIONAL_HINT_NOT_CONFIRMATION` | `CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED` | `TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED`.
- **USER_VISIBLE_RESULT:** a Russian readout of capture gate, complete/missing cells, H900 direction, H3600 robustness, and explicit non-claims.
- **NON_GOALS:** recapture-only campaign; MOVE 2; H13/H11/H07/H02; paid plan; second provider; `/build`/`/execute`; NetReturn; alpha; threshold sweep; H3600 as searchable Y.
- **EVIDENCE_BUDGET:** one campaign; at most 60 provider GETs; one credential read after reservation and credential-free preflight; no retry/fallback; global interval at least three seconds.
- **REPLAN_TRIGGER:** a second capture-bookkeeping failure; any new provider or paid tier; using H3600 as a second searchable Y; family close on sample-invalid; mechanism scoring despite invalid capture.

## Decision capsule

- `DECISION_DELTA:` REORDER the paused quote-native next boundary from recapture-only into one dual-purpose admissible friction audition.
- `UNCERTAINTY_REMOVED:` whether capture can be proven hash-bound on a fresh run, and if so whether the frozen H900 friction relation has a directional screening hint.
- `CAPABILITY_OR_EVIDENCE:` WRAP the Free-key qualification runner, Tokens V2 cohort, and existing H900 friction scorer; add attempt-reservation and row capture envelopes.
- `STOP:` after exact-head CI; merge only with the repository phrase bound to this PR/head.
- `NEXT:` capture FAIL → pause, no recapture-only retry. Sample invalid → family remains open. No direction → close exact mechanism. Directional hint → later MOVE 2 contract only.
- `SPEC_ROUTE=BOTH`
- `ROADMAP_VERDICT=REORDER`
- `strongest_rejected_alternative:` a pure hardened recapture that still leaves the mechanism question unasked.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=WRAP_EXISTING_FREE_KEY_CAMPAIGN_AND_H900_SCORER`

`ENTRY_VERDICT=START`

`OWNER_CAPTURE_PHRASE=OK QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1: one fresh Jupiter Free-key quote-native campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; freeze QuotedRoundTripFriction(t0) to QuotedLiquidationRecovery(H900) before first call; H3600 collected as predeclared robustness not a second searchable Y; capture FAIL pauses the route with no recapture-only retry; capture PASS plus sample invalid does not close the family; capture PASS plus sample valid plus no direction closes the exact mechanism; directional hint stops and leaves MOVE 2 as a later contract; no H13/H11/H07/H02 unpark; no NetReturn/alpha.`

## Estimand (screening, frozen before first call)

X = `QuotedRoundTripFriction` = t0 reverse `outAmount` / t0 buy input − 1, only if buy and reverse are `QUOTE_OBSERVED`. Missing stays missing.

Y = `QuotedLiquidationRecovery` = H900 sell `outAmount` / t0 buy input − 1, only if buy and H900 sell are `QUOTE_OBSERVED`. Typed `NO_ROUTE` / failure is a survival tail, not a numeric Y.

Predeclared direction: more negative X ranks with more negative Y. Concordance is a hint. No threshold is chosen on this sample. `SELL_H3600` is collected and reported as robustness (`h3600_moved_count`) and is not a second searchable Y.

## Capture gate (fail-closed, independent of market outcomes)

Capture PASS requires:

1. Attempt reservation written with `credential_reads=0` before the credential is read, with a canonical SHA-256 in the Git receipt.
2. Every consumed observation has `observed_at` bound into `capture_envelope_sha256` computed at raw write from `{observation_id, observed_at, body_sha256}`.

Capture FAIL → `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE` and no mechanism conclusion.

## Definition of Done

1. Fresh 6 RECENT + 6 TRADED Tokens V2 cohort, notional `10000000`, horizons 900/3600, gap 14400.
2. One process-environment `JUPITER_API_KEY` read after reservation and credential-free preflight; header-only; no `.env`.
3. Hash-bound capture envelopes and reservation in the canonical runtime receipt.
4. Frozen H900 scorer runs only after capture PASS.
5. Four-way terminal is recorded; Russian readout names capture, sample, mechanism, and non-claims.
6. Catalog, independent review, Factory Fit, and guarded PR/CI for this branch.
