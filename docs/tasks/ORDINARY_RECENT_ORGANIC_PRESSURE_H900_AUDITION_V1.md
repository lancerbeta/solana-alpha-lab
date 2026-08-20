---
task_id: ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 97030e71f2a2f0348327a1b996c2f2efa5d03f5e
  expected_upstream: origin/main
  expected_upstream_oid: 97030e71f2a2f0348327a1b996c2f2efa5d03f5e
  expected_branch: codex/ordinary-recent-organic-pressure-h900-audition
  dirty_mode: ALLOW_REPORTED
objective: Run one fresh project-eligible organic-pressure audition from frozen recent mints through a T+5m decision snapshot, quote-only entry and H900 quote-only exit, preserving raw evidence outside Git and fail-closing scientific outcomes.
managed_write_set:
  - docs/tasks/ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1.md
  - configs/ordinary_recent_organic_pressure_h900_audition_v1.yaml
  - configs/provider_route_capability_registry_v10.yaml
  - catalog/schemas/provider_route_capability_registry_v10.schema.json
  - src/solana_alpha_lab/ordinary_recent_organic_pressure_h900_audition.py
  - src/solana_alpha_lab/quote_native_evidence_channel_qualification.py
  - src/solana_alpha_lab/quote_native_evidence_fit_panel.py
  - src/solana_alpha_lab/provider_route_capability_registry_v10.py
  - scripts/run_ordinary_recent_organic_pressure_h900_audition.py
  - tests/test_ordinary_recent_organic_pressure_h900_audition.py
  - tests/test_provider_route_capability_registry_v10.py
  - tests/test_quote_native_evidence_channel_qualification.py
  - tests/test_quote_native_evidence_fit_panel.py
  - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_ordinary_recent_organic_pressure_h900_audition_runtime_receipt_v1.json
  - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_ordinary_recent_organic_pressure_h900_audition_acceptance_v1.json
  - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_delivery_completion_evidence_v1.json
  - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_delivery_independent_review_v1.json
  - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_delivery_factory_fit_v1.json
  - docs/reports/ordinary_recent_organic_pressure_h900_audition/a1_owner_readout_v1.md
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
  - H3600_OR_H4_USED
  - MOVE_2_OR_STRATEGY_OR_SHADOW_CLAIM
  - ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
    - MODULE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001
    - MODULE-FACTORY-V1-RUNNER-001
    - EVIDENCE-ORDINARY-MARKET-PIT-OFFLINE-XY-ASSOCIATION-ACCEPTANCE-001
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
    - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v9.yaml
      - configs/provider_route_capability_registry_v10.yaml
      - configs/quote_native_evidence_channel_qualification_v1.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_delivery_completion_evidence_v1.json
      - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_delivery_independent_review_v1.json
      - docs/evidence/ordinary_recent_organic_pressure_h900_audition/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1

## Owner authorization boundary

The implementation may be inspected, tested, committed and published to a
pull request under the bounded Delivery Harness route. Provider calls require
a separate exact owner phrase after the code contract and local checks are
ready:

`OK ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1: one bounded Jupiter Free-key read-only campaign using a local process-environment key only; Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; 24 fresh project-eligible recent candidates excluding all prior consumed mints; wait until pool age >=5m before the single bulk T0 resnapshot; X = (stats5m.buyOrganicVolume - stats5m.sellOrganicVolume) / top-level liquidity from that T0 snapshot only; quote-only BUY at T0 and quote-only SELL at H900; UNKNOWN is never zero; H3600/H4, Strategy, Bot, Shadow, alpha and NetReturn forbidden.`

No credential or raw provider body is requested, displayed or committed by the
contract itself. A failed capture, insufficient sample, or typed provider
terminal remains evidence and does not become a negative alpha claim.

The repository-wide v3/v1 provider-registry binding remains an inherited
precondition; this atom does not rewrite `context-map.yaml` or grant route
authority. Its scoped v10 successor pins the exact v9 bytes, preserves the v9
route objects, and adds only the `AUTHORIZED_UNOBSERVED` bulk-search route;
the v9 `supersedes` chain remains the registry's lineage evidence.

## Decision capsule

- `DECISION_DELTA:` replace the deferred liquidity/mcap follow-up with one
  fresh organic-pressure audition, only after the preflight already passed.
- `UNCERTAINTY_REMOVED:` whether the frozen 5m organic-pressure X has a valid
  practical relation to quote-only H900 recovery on a fresh cohort.
- `CAPABILITY_OR_EVIDENCE:` one narrow `/tokens/v2/search` adapter, truthful
  quote terminal taxonomy, deterministic X/Y projection and owner readout;
  existing transport, raw envelopes, clocks and Factory runner are wrapped.
- `STOP:` stop on a provider or capture safety violation, invalid evidence
  yield, or exact-head CI; merge only with the repository phrase bound to the
  final PR/head.
- `NEXT:` `EARN_FRESH_OOS` permits a later exact OOS contract; valid rule
  failure closes this candidate; invalid evidence replans. No preparatory
  suffix atom is created.
- `SPEC_ROUTE=BOTH`
- `ROADMAP_VERDICT=REPLACE_DEFERRED_LIQUIDITY_ROUTE`
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=ADOPT_EXISTING_TRANSPORT_AND_RAW_RECEIPTS_WRAP_NEW_SEARCH_AND_SCORER_BUILD_NO_FACTORY_CORE`
- `ADOPT=` existing credential-free preflight, bounded credentialed GET transport,
  safe response-header view, raw envelope writer, monotonic pace and Factory
  runner seams already used by the quote-native panels.
- `WRAP=` the existing `/swap/v2/order` quote projection and route-registry
  lineage; the new adapter is limited to one allowlisted bulk
  `/tokens/v2/search` request for the frozen mint set.
- `BUILD=` only the search adapter, explicit response-row fingerprint binding,
  organic-pressure projector, typed terminal classifier and H900 scorer; no
  Factory core, wallet, execution or strategy surface.
- `CHEAPEST_FALSIFIER=` a deterministic fixture with a malformed, duplicate or
  mint-mismatched bulk row must produce `INVALID_EVIDENCE_REPLAN` or an
  ineligible row before any quote contributes to Y; no provider call is needed.

## Frozen estimand and rule

The population predicate is `launchpad == pump.fun` after `/recent` discovery,
with unique mints and an explicit exclusion set of previously consumed mints.
Candidate mints are frozen before the five-minute seasoning wait. The only
decision-time snapshot is the one bulk `/tokens/v2/search` response after the
wait; missing organic fields, missing liquidity, invalid timestamps and
future-dated updates remain ineligible rather than being imputed.

For eligible rows, `Y` is `H900 quote outAmount / T0 buy input - 1`, only when
both quote terminals are `QUOTE_OBSERVED`. Every other exit is a typed terminal,
not numeric zero. The practical rule is frozen before the first provider byte:
Kendall tau-b >= `0.20`, upper-X quartile H900 median > `0`, upper-quartile
median > the remaining median, leave-one-out positive tau-b share >= `0.75`,
and no selected row has `MARKET_EXECUTION_UNAVAILABLE` at H900. This 0.75
operationalizes the plan's “overwhelming majority” wording and is not tuned
after capture.

## Definition of Done

1. The named route is present in an append-only v10 registry successor without
   changing v9 bytes or authority.
2. Tests prove endpoint/query allowlists, credential ordering, raw/hash
   retention, T+5 seasoning, X/Y missingness, truthful terminals and the
   frozen decision rule.
3. One fresh bounded campaign is captured only after the exact owner phrase;
   raw bodies remain outside Git and the Git receipt contains hashes/times.
4. The owner readout states `EARN_FRESH_OOS`, `CLOSE_ORGANIC_PRESSURE_CANDIDATE`
   or `INVALID_EVIDENCE_REPLAN`, plus explicit non-claims.
5. Catalog/navigation, independent review, Factory Fit and guarded PR/CI are
   reconciled for this exact atom.

## Rollback

Revert the ordinary code, policy, registry, schema, Catalog and generated-view
changes together through the same task branch/PR if the implementation is
rejected. Never delete or rewrite any captured raw directory or runtime
receipt: a completed attempt is append-only evidence outside Git. A failed
provider/capture attempt is retained with its typed terminal and is not replayed
by retry or fallback; a later attempt requires a new exact owner authorization
and a new create-only run directory.
