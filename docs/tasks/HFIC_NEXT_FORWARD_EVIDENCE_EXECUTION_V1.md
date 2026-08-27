---
task_id: HFIC_NEXT_FORWARD_EVIDENCE_EXECUTION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-27'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 259314e07e7097c3ba9d685e4a9a4a11eea1b3db
  expected_upstream: origin/main
  expected_upstream_oid: 259314e07e7097c3ba9d685e4a9a4a11eea1b3db
  expected_branch: cursor/hfic-next-forward-evidence-execution-v1
  dirty_mode: ALLOW_REPORTED
objective: One bounded reusable Jupiter free-key capture capability
  recent → one R0 search → eligibility/floor gate → R0 BUY quote →
  absolute H900 SELL, plus a pure offline mix classifier over the frozen
  dataset. Not a hypothesis-specific provider runner and not a platform.
managed_write_set:
- docs/tasks/HFIC_NEXT_FORWARD_EVIDENCE_EXECUTION_V1.md
- configs/forward_h900_quote_capture_v1.yaml
- configs/experiment_capability_registry_v1.yaml
- src/solana_alpha_lab/factory/forward_h900_quote_capture.py
- src/solana_alpha_lab/factory/forward_mix_offline.py
- src/solana_alpha_lab/factory/capabilities.py
- scripts/run_forward_h900_quote_capture.py
- tests/test_forward_h900_quote_capture.py
- tests/test_factory_ordinary_market_hypothesis.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/hfic_next_forward_evidence_execution/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_next_forward_evidence_execution/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_next_forward_evidence_execution/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- HYPOTHESIS_SPECIFIC_PROVIDER_RUNNER
- UNIVERSAL_CAPTURE_PLATFORM
- SECOND_LIVE_WINDOW
- CONFIRMATORY_WINDOW
- HYPOTHESIS_FORGE_SLASH_INVOKE
- FACTORY_RUNNER_BYTES_CHANGED
- WALLET_BUILD_EXECUTE_TRANSACTION
- RETRY_OR_FALLBACK
- R1_SEARCH
- CLOSED_FAMILY_REOPEN
- RAW_A4_COMMITTED_TO_GIT
- LIVE_PROVIDER_CALL_BEFORE_MERGE
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
      - docs/evidence/hfic_next_forward_evidence_execution/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_next_forward_evidence_execution/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_next_forward_evidence_execution/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_NEXT_FORWARD_EVIDENCE_EXECUTION_V1

## Task Outcome Brief

- **Owner decision:** execute accepted V2 DATA_OPTION_READY. One live
  window is already authorized; do not re-ask. This PR is code and
  zero-network proof only. Live capture runs after merge on clean main.
- **Product outcome:** reusable capture
  `recent → one R0 search → eligibility/floor → R0 BUY → absolute H900
  SELL → immutable RDP dataset/receipts`. `classify_r0_mix` is offline
  only over that frozen dataset.
- **Named consumers:** post-merge one authorized live window; offline
  mix scorer; later confirmatory window is forbidden in this atom.
- **Cheapest falsifier:** zero-network tests for call cap 60, pace ≥3s,
  retries/fallback=0, stop before quotes if n<10, absolute H900,
  crash/resume without repeat calls, wallet/build/execute/tx=0, secret
  redaction, raw A4 outside Git, one window, idempotence.
- **Evidence budget:** this PR `provider_calls=0`. Post-merge live cap 60.
- **Non-goals:** `/hypothesis-forge`; confirmatory second window;
  hypothesis-specific provider runner; universal platform; Factory
  runner mutation; widening
  `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`.

## DECISION_DELTA

Forward evidence is a narrow reusable quote capture plus an offline
mix score, not a mix-aware HTTP scheduler.

## UNCERTAINTY_REMOVED

Whether one R0 search plus absolute create_at+H900 quotes can be
implemented with the accepted call/pace/floor/resume/window fences
without a mix-specific provider path.

## CAPABILITY_OR_EVIDENCE

`CAP-JUPITER-FREE-KEY-FORWARD-H900-QUOTE-CAPTURE-001` plus offline
`score_frozen_mix_dataset`. Hypothesis freeze lives in RDP, not Git.

## STOP

Exact-head CI green. Owner merge phrase bound to PR and unchanged
40-hex head. No live provider call before merge.

## NEXT

After merge: clean main → preflight → the already-authorized one live
window → persist dataset/terminal/epoch in RDP. Git unchanged. No
Forge. No confirmatory window.

## REPLAN_TRIGGER

Any contract mismatch before a provider call; Factory runner hash
drift; second window; mix classifier entering the HTTP path.

## Owner live phrase (already granted; do not re-request)

```
OK HFIC_NEXT_FORWARD_EVIDENCE_OPTION_V2: one bounded Jupiter Free-key read-only PIT capture using a local process-environment key only; Tokens V2 /recent plus one bulk /tokens/v2/search R0 snapshot plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 fresh mints only excluding all prior consumed mints including the 2026-08-24 valuation window; X = R0_TAKER_VOLUME_MIX from stats5m buyVolume/(buyVolume+sellVolume) at one prospective search snapshot (dimensionless; UNKNOWN never zero; no USD volume claim; no R1 search); stop before quotes if valid-mix eligible < 10; quote-only BUY at R0 and quote-only SELL at H900; Y previously unconsumed; no ln(R1/R0), no closed-family threshold, window, quartile or LOO reopen; one window only; Factory runner unchanged; Discovery, A7, Strategy, Bot, Shadow, alpha, NetReturn, micro-live and /hypothesis-forge forbidden.
```
