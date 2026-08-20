---
task_id: ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7fd43e5f4bdeba147a6927e4cb1b19a4b7baa827
  expected_upstream: origin/main
  expected_upstream_oid: 7fd43e5f4bdeba147a6927e4cb1b19a4b7baa827
  expected_branch: cursor/ordinary-recent-early-path-h900-audition
  dirty_mode: ALLOW_REPORTED
objective: Run one fresh project-eligible early-path audition from frozen recent mints through a T+5m mcap snapshot, quote-only entry and H900 quote-only exit, preserving raw evidence outside Git and fail-closing scientific outcomes.
managed_write_set:
  - docs/tasks/ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1.md
  - configs/ordinary_recent_early_path_h900_audition_v1.yaml
  - src/solana_alpha_lab/ordinary_recent_early_path_h900_audition.py
  - src/solana_alpha_lab/ordinary_recent_organic_pressure_h900_audition.py
  - scripts/run_ordinary_recent_early_path_h900_audition.py
  - tests/test_ordinary_recent_early_path_h900_audition.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
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
  - RAW_BODY_CONTAINS_CREDENTIAL
  - UNSAFE_RESPONSE_HEADER_RETAINED
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - WALLET_SIGNER_TRANSACTION_OR_DEPLOYMENT
  - RETRY_OR_FALLBACK
  - CALL_CAP_EXCEEDED
  - PACE_BELOW_THREE_SECONDS
  - SECOND_PROVIDER_OR_PAID_PLAN
  - PRIOR_MINT_REUSED
  - UNKNOWN_AS_ZERO
  - T_PLUS_FIVE_SEASONING_OR_TIMESTAMP_FAILURE
  - DECISION_TIME_ELIGIBLE_BELOW_18
  - RANKABLE_H900_BELOW_14
  - THRESHOLD_OR_COHORT_RULE_DRIFT
  - ORGANIC_OR_FLOW_OR_TX_IMBALANCE_X
  - H3600_OR_H4_USED
  - MOVE_2_OR_STRATEGY_OR_SHADOW_CLAIM
  - ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
    - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
    - MODULE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
    - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v10.yaml
      - configs/ordinary_recent_organic_pressure_h900_audition_v1.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_ordinary_recent_organic_pressure_h900_audition_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1

## Owner authorization boundary

The implementation may be inspected, tested, committed and published to a
pull request under the bounded Delivery Harness route. Provider calls require
a separate exact owner phrase after the code contract and local checks are
ready:

`OK ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1: one bounded Jupiter Free-key read-only campaign using a local process-environment key only; Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; 24 fresh project-eligible recent candidates excluding all prior consumed mints including ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1; wait until pool age >=5m before the single bulk T0 resnapshot; X = (mcap_T5 / mcap_recent) - 1 from /recent freeze row and that T0 snapshot only; quote-only BUY at T0 and quote-only SELL at H900; UNKNOWN is never zero; organic-pressure, flow-pressure, TX_IMBALANCE, H3600/H4, Strategy, Bot, Shadow, alpha and NetReturn forbidden.`

No credential or raw provider body is requested, displayed or committed by the
contract itself. A failed capture, insufficient sample, or typed provider
terminal remains evidence and does not become a negative alpha claim.

This atom wraps the existing Tokens V2 recent/search/quote campaign. It does
not add a registry version, path store, second provider, or organic/flow X.

## Decision capsule

- `DECISION_DELTA:` replace the closed T+5 directional-flow family with one
  two-point early-path audition on the same recent→T+5 capture path.
- `UNCERTAINTY_REMOVED:` whether frozen recent-to-T+5 mcap change has a valid
  practical relation to quote-only H900 recovery on a fresh cohort.
- `CAPABILITY_OR_EVIDENCE:` mcap-path projector over the existing campaign,
  truthful quote terminals, and owner readout; transport and search adapter
  are wrapped.
- `STOP:` stop on a provider or capture safety violation, invalid evidence
  yield, or exact-head CI; merge only with the repository phrase bound to the
  final PR/head. Live capture waits for the exact owner phrase above.
- `NEXT:` `EARN_FRESH_OOS` permits a later exact OOS contract; valid rule
  failure closes this two-point path candidate; invalid evidence replans. No
  preparatory suffix atom is created.
- `SPEC_ROUTE=BOTH`
- `ROADMAP_VERDICT=PATCH`
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=ADOPT_EXISTING_RECENT_SEARCH_QUOTE_CAMPAIGN_WRAP_MCAP_PATH_PROJECTOR_BUILD_NO_PATH_STORE`
- `ADOPT=` existing credential-free preflight, bounded credentialed GET,
  search adapter, quote taxonomy, H900 clocks and Factory-adjacent runner.
- `WRAP=` organic-pressure campaign with a pluggable X projector.
- `BUILD=` only the early-path projector and its policy/phrase/terminals.
- `CHEAPEST_FALSIFIER=` missing or non-positive recent mcap, missing T+5 mcap,
  or mint mismatch must yield `INVALID_EVIDENCE_YIELD` / typed missing X
  without imputing zero and without quotes; no provider call is needed.
- `REPLAN_TRIGGER=` repeated measurement invalidation, second provider pivot,
  or a request to salvage via organic/flow/TX_IMBALANCE/H3600.

## Frozen estimand and rule

Population matches the organic audition: `launchpad == pump.fun` after
`/recent`, unique mints, explicit exclusion of previously consumed mints
including the organic-pressure cohort. Candidates freeze before the
five-minute wait. Decision-time T+5 is the one bulk `/tokens/v2/search`.

`X = (mcap_T5 / mcap_recent) - 1`. Both mcaps must be finite; `mcap_recent`
must be `> 0`; `mcap_t5` may be `>= 0`. Missing or invalid mcap is ineligible,
never zero. Organic volume, total volume, and trade-count imbalance are not X.

`Y` is `H900 quote outAmount / T0 buy input - 1` only when both quote
terminals are `QUOTE_OBSERVED`. Frozen rule: Kendall tau-b >= `0.20`,
upper-X quartile H900 median `> 0`, upper-quartile median greater than the
rest, leave-one-out positive tau-b share >= `0.75`, and no selected row has
`MARKET_EXECUTION_UNAVAILABLE` at H900.

## Definition of Done

1. Tests prove the mcap-path formula, missing-is-not-zero, exclusion of
   organic/flow X, credential ordering, raw/hash retention, T+5 seasoning,
   truthful terminals and the frozen decision rule.
2. One fresh bounded campaign is captured only after the exact owner phrase;
   raw bodies remain outside Git.
3. The owner readout states `EARN_FRESH_OOS`, `CLOSE_EARLY_PATH_CANDIDATE`
   or `INVALID_EVIDENCE_REPLAN`, plus explicit non-claims.
4. Catalog/navigation, independent review, Factory Fit and guarded PR/CI are
   reconciled for this exact atom.

## Rollback

Revert the early-path code, policy, Catalog and generated views together
through the same task branch/PR. Do not rewrite captured raw directories.
A later live attempt requires a new exact owner phrase and a new create-only
run directory.
