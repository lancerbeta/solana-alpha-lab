---
task_id: QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1
task_version: '1.1'
status: DONE
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: c0346b7ddfa87cc44d2319d3996ac0a5ac7f8f02
  expected_upstream: origin/main
  expected_upstream_oid: c0346b7ddfa87cc44d2319d3996ac0a5ac7f8f02
  expected_branch: cursor/quote-native-evidence-channel-qualification
  dirty_mode: ALLOW_REPORTED
objective: Qualify the quote-native evidence channel exactly once with a locally supplied Jupiter Free API key, preserving the existing live Tokens V2 cohort semantics and returning either sufficient executable baseline evidence or a terminal pause/close of the current quote-native alpha route.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1.md
  - docs/tasks/QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1.md
  - docs/superpowers/plans/2026-08-18-quote-native-evidence-channel-qualification.md
  - configs/quote_native_evidence_channel_qualification_v1.yaml
  - src/solana_alpha_lab/quote_native_evidence_channel_qualification.py
  - scripts/run_quote_native_evidence_channel_qualification.py
  - tests/test_quote_native_evidence_channel_qualification.py
  - src/solana_alpha_lab/quote_native_evidence_timing_recovery.py
  - scripts/recover_quote_native_evidence_timing.py
  - tests/test_quote_native_evidence_timing_recovery.py
  - configs/provider_route_capability_registry_v9.yaml
  - catalog/schemas/provider_route_capability_registry_v9.schema.json
  - src/solana_alpha_lab/provider_route_capability_registry_v9.py
  - tests/test_provider_route_capability_registry_v9.py
  - docs/evidence/quote_native_live_variation_campaign/a2_replan_closure_v1.json
  - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json
  - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_timing_recovery_v1.json
  - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_portal_reconciliation_v1.json
  - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_acceptance_v1.json
  - docs/reports/quote_native_evidence_channel_qualification/a1_owner_readout_v1.md
  - docs/evidence/quote_native_evidence_channel_qualification/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_evidence_channel_qualification/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_evidence_channel_qualification/a1_delivery_factory_fit_v1.json
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
  - H13_H11_H07_OR_H02_UNPARK
  - MOVE_2_OR_ALPHA_CLAIM
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-QUOTE-NATIVE-FRICTION-H900-FALSIFIER-ACCEPTANCE-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-007
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_live_variation_campaign_v1.yaml
      - configs/provider_route_capability_registry_v8.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_live_variation_campaign/a1_quote_native_live_variation_campaign_runtime_receipt_v1.json
      - docs/evidence/quote_native_live_variation_campaign/a1_quote_native_live_variation_campaign_acceptance_v1.json
      - docs/evidence/quote_native_live_variation_campaign/a1_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1

## Owner authorization

`OK QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1: one fresh Jupiter Free-key quote-native evidence campaign using a local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; preserve the existing 6 RECENT + 6 TRADED cohort and success/control-kill thresholds; any 429 or insufficient Free-key sample closes or pauses the current quote-native alpha route.`

The owner selected this bounded route with an already locally available key. The key value is never requested, displayed, stored, or committed.

## Task Outcome Brief

- **OWNER_DECISION:** whether quote-native has a usable prospective evidence substrate now, or must be paused/closed as the current alpha route.
- **PRODUCT_OUTCOME:** one new fresh, outcome-blind executable baseline with either qualified evidence or a terminal negative route decision.
- **NAMED_CONSUMER:** the goal owner deciding whether to leave the current quote-native alpha route paused or to authorize a new recapture contract. The unique-run runtime scorer token does not nominate a mechanism audition.
- **CHEAPEST_FALSIFIER:** one Jupiter Free-key campaign under the unchanged 6 RECENT + 6 TRADED contour, `>=10` complete X/Y cells, `>=6` time-separated cells, both strata represented, and the existing TRADED control kill.
- **TERMINAL_OUTCOMES:** `QUOTE_NATIVE_EVIDENCE_FIT_PASS` | `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE` | `CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED` | `TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED`.
- **USER_VISIBLE_RESULT:** a Russian readout of complete/missing cells, time separation, route survival, safe rate-limit telemetry, terminal decision, and explicit non-claims.
- **NON_GOALS:** a new provider, Developer plan, H13/H11/H07/H02 work, a causal trial, alpha/NetReturn claim, `/build`, `/execute`, a signer, transaction, UI, scheduler, or generic platform.
- **EVIDENCE_BUDGET:** one campaign; at most 60 provider GETs across discovery and quotes; one credential read after a credential-free preflight; no retry/fallback; global call interval at least three seconds.
- **REPLAN_TRIGGER:** any new provider, paid tier, second campaign, changed frozen threshold, credential exposure, 429, insufficient Free-key sample, or control kill ends this route rather than creating a suffix atom.

## Replan and compatibility

`QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1` is technically complete with
`SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY`, not alpha or MOVE 2. Its runtime,
acceptance, review, and Factory Fit evidence remain immutable. This task records
the owner-approved `REPLAN` closure in a new receipt; it never rewrites those
historical bytes.

`SPEC_ROUTE=BOTH`: the Outcome Brief above resolves product intent, and this
design resolves the credential, provider-route, transport-telemetry, and
recovery boundary. No second generic provider layer is allowed.

## Canonical closure

`FINISH_GATE=TECHNICALLY_COMPLETE_EVIDENCE_FIT_NOT_ACCEPTED`: the unique
Free-key campaign met the frozen numeric floors (`10` complete X/Y, `8`
time-separated, both strata, no `429`, TRADED control kill not triggered)
and is recorded as `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE` because
the capture contract of that same unique run is `INVALID_CAPTURE_CONTRACT`.
The runtime scorer field `QUOTE_NATIVE_EVIDENCE_FIT_PASS` is numeric-only.
No mechanism audition is nominated. A replacement campaign requires a new
owner-authorized contract. This is not alpha, NetReturn, or canonical
semantic DONE.

## Design

1. Create registry v9 as an append-only successor to v8. Preserve every v8
   route byte-for-byte and add exactly three `LOCAL_ENV_CREDENTIAL` bindings:
   Tokens V2 `recent`, Tokens V2 `toptraded/1h`, and Swap V2 `order`. Their
   endpoint families remain Jupiter HTTPS GET; the new bindings do not grant a
   call by themselves.
2. Add one bounded campaign runner that reuses the existing fresh-cohort,
   scheduling, and scorer semantics. Its credential-aware transport reads one
   local process-environment value only after DNS/TCP/TLS preflight and an
   attempt-start marker; it transmits the value only as `x-api-key`.
3. Preserve raw response bodies outside Git and retain only safe response
   telemetry in receipts: HTTP status, body hash/size, `x-api-gateway-request-id`
   when present, and `retry-after` when present. Do not retain unallowlisted
   headers, request headers, or credential-bearing URLs.
4. Enforce a single global provider clock of at least three seconds across
   discovery, t0 buy/reverse, and H900/H3600 sells. A `429` stops immediately;
   no later cells, retry, fallback, alternate provider, or paid-tier escalation
   is allowed.
5. Reuse the prior 6 RECENT + 6 TRADED selection, liquidity floor, notional,
   t0/H900/H3600 definitions, missingness semantics, `>=10` complete X/Y and
   `>=6` time-separated success floors, and TRADED control kill. The runner
   scorer token `QUOTE_NATIVE_EVIDENCE_FIT_PASS` records numeric floors only.
   Accepted evidence-fit is a separate acceptance decision. This unique run's
   capture contract is invalid, so no mechanism audition is nominated. Every
   accepted fail, invalid capture, 429, or insufficient sample pauses/closes
   the current quote-native alpha route.

## Validation and delivery

- Offline tests prove that the key can appear only in the outbound header, never
  in a URL, exception, receipt, raw manifest, or generated artifact; they also
  prove preflight-before-read, one-read budget, header allowlisting, global
  pacing, 429 stop, no retry/fallback, immutable v8 semantics, and unchanged
  success/kill thresholds.
- Targeted tests and direct consumers run before the one live campaign.
- The campaign result produces typed runtime/acceptance/readout evidence,
  Catalog propagation, independent code + goal/DoD + architecture review, and
  a proportional Factory Fit review.
- The exact task branch is delivered through the repository’s guarded PR/CI
  route. No merge, canonical DONE, or mechanism continuation is implied by a
  passing local test.

## Chain contract

- **DECISION_DELTA:** distinguish a keyless quota artifact from a structurally
  unfit quote-native evidence channel.
- **UNCERTAINTY_REMOVED:** whether one bounded credentialed official route can
  supply enough comparable prospective executable observations.
- **CAPABILITY_OR_EVIDENCE:** credential-safe, telemetry-bounded reuse of the
  existing quote-native campaign surface, or a durable pause/close decision.
- **STOP:** the first external credential/API boundary is now explicitly bound;
  stop again on every listed stop condition or terminal campaign outcome.
- **NEXT:** accepted evidence-fit (`evidence_fit` accepted and
  `acceptance_allowed=true`) would be required before any separately
  contracted mechanism audition. The unique-run runtime token
  `QUOTE_NATIVE_EVIDENCE_FIT_PASS` is numeric-only and does not nominate
  audition. This atom's recorded next boundary is
  `OWNER_DECISION_NEW_RECAPTURE_CONTRACT_OR_LEAVE_QUOTE_NATIVE_PAUSED`.
- **MODEL_EFFORT_RECOMMENDATION:** `SOL_XHIGH`, because the task changes a
  credentialed provider boundary while preserving research-validity invariants.

## Spec review gate

No implementation, provider call, or credential read may begin until the owner
reviews and approves this exact task-contract design.
