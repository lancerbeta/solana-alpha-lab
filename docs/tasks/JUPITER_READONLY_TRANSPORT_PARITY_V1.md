---
task_id: JUPITER_READONLY_TRANSPORT_PARITY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6024c09528877915d31df68f6ecd359ed15106ae
  expected_upstream: origin/main
  expected_upstream_oid: 6024c09528877915d31df68f6ecd359ed15106ae
  expected_branch: cursor/jupiter-readonly-transport-parity-v1
  dirty_mode: ALLOW_REPORTED
objective: "Bring JupiterReadonlyOpener to the already proven readonly request profile (explicit User-Agent, Accept, x-api-key header-only, no-redirect) without changing provider, credential contract, science, retry, fallback or PathRisk semantics. Zero provider calls and zero real credential reads in this PR."
managed_write_set:
- docs/tasks/JUPITER_READONLY_TRANSPORT_PARITY_V1.md
- src/solana_alpha_lab/factory/observation_schedule_runtime.py
- tests/test_jupiter_readonly_transport_parity.py
- tests/test_observation_primitives.py
- tests/test_pathrisk_recent_http_class.py
- tests/test_pathrisk_wallclock_live.py
- docs/evidence/jupiter_readonly_transport_parity/a1_delivery_completion_evidence_v1.json
- docs/evidence/jupiter_readonly_transport_parity/a1_delivery_independent_review_v1.json
- docs/evidence/jupiter_readonly_transport_parity/a1_delivery_factory_fit_v1.json
- docs/reports/jupiter_readonly_transport_parity/a1_owner_readout_v1.md
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
- LIVE_PROVIDER_CALL_IN_THIS_PR
- REAL_CREDENTIAL_VALUE_READ
- SECOND_LIVE_WINDOW
- REOPEN_ACT_PATHRISK_LIVE_001
- RETRY_OR_FALLBACK
- NEW_PROVIDER_OR_ENDPOINT
- NEW_HTTP_ARCHITECTURE
- PATHRISK_SCIENCE_CHANGE
- SECRET_REDACTION_NOT_PROVEN
- CLAIM_USER_AGENT_ALONE_CAUSAL
- WALLET_SIGNER_TX
context_requirements:
  catalog_asset_ids:
  - CTRL-JUPITER-READONLY-TRANSPORT-PARITY-001
  - CTRL-PATHRISK-LIVE-RECENT-HTTP-CLASS-001
  - MODULE-OBSERVATION-SCHEDULE-RUNTIME-001
  - MODULE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v10.yaml
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-007-declarative-observation-schedule-bridge.md
    DELIVERY_EVIDENCE:
    - docs/evidence/jupiter_readonly_transport_parity/a1_delivery_completion_evidence_v1.json
    - docs/evidence/jupiter_readonly_transport_parity/a1_delivery_independent_review_v1.json
    - docs/evidence/jupiter_readonly_transport_parity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# JUPITER_READONLY_TRANSPORT_PARITY_V1

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Decision capsule

- `DECISION_DELTA:` Production `JupiterReadonlyOpener` reproduces the proven readonly request profile: `Accept: application/json`, `User-Agent: solana-alpha-lab/quote-native-evidence-qualification-v1`, `x-api-key` header-only, explicit no-redirect opener. PR #226 HTTP diagnostics stay intact.
- `UNCERTAINTY_REMOVED:` PathRisk opener no longer uses implicit `Python-urllib/...` User-Agent plus default redirect `urlopen`. This atom does not claim User-Agent alone was causal; the repair target is request-profile parity.
- `CAPABILITY_OR_EVIDENCE:` Zero-network T1–T20. No provider call and no real credential read in this PR.
- `STOP:` exact merge gate. `JUPITER_READONLY_TRANSPORT_PARITY_PASS_READY_FOR_MERGE_GATE`
- `NEXT:` owner may later authorize one transport probe or PathRisk live; neither is this atom.
- `CHEAPEST_FALSIFIER:` opener still calls `urlopen`, omits the proven User-Agent, or tests pass while the live Request headers differ from `perform_credentialed_get`.
- `REPLAN_TRIGGER:` new HTTP stack/provider, science change, secret leak, claim that UA alone is proven causal.

## Non-goals

- PathRisk scientific window, replacement window, `ACT-PATHRISK-LIVE-001` mutation
- new key, paid plan, other Jupiter product/provider
- retry/fallback, call-cap, estimand, Factory runner, Hypothesis Forge
- importing private helpers from the qualification module
