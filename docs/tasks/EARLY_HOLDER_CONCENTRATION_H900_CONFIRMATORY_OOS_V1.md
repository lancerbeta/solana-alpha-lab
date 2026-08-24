---
task_id: EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: bc744d6f66273165f42df1bb23b467cdaf16532a
  expected_upstream: origin/main
  expected_upstream_oid: bc744d6f66273165f42df1bb23b467cdaf16532a
  expected_branch: cursor/early-holder-concentration-h900-confirmatory-oos
  dirty_mode: ALLOW_REPORTED
objective: "One fresh confirmatory OOS replication of HOLDER_CONCENTRATION_RISK using the PR 190 implementation; scientific X/Y/scorer/campaign unchanged; no new campaign orchestration."
managed_write_set:
- docs/tasks/EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1.md
- configs/early_holder_concentration_h900_confirmatory_oos_v1.yaml
- src/solana_alpha_lab/early_holder_concentration_h900_falsifier.py
- scripts/run_early_holder_concentration_h900_falsifier.py
- tests/test_early_holder_concentration_h900_confirmatory_oos.py
- tests/test_early_holder_concentration_h900_falsifier.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_acceptance_v1.json
- docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_runtime_receipt_v1.json
- docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_delivery_independent_review_v1.json
- docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_delivery_factory_fit_v1.json
- docs/reports/early_holder_concentration_h900_confirmatory_oos/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
- FACTORY_LEVERAGE_FAIL_CONFIRMATORY_REPLAN
- CAMPAIGN_ORCHESTRATION_DELTA
- X_Y_SCORER_OR_PIT_CHANGE
- DOTENV_READ
- API_KEY_IN_URL_LOG_RECEIPT_OR_GIT
- JUPITER_EXECUTE_OR_BUILD
- TAKER_OR_SIGNER_SUPPLIED
- WALLET_SIGNER_TRANSACTION_OR_DEPLOYMENT
- RETRY_OR_FALLBACK
- SECOND_PROVIDER_OR_PAID_PLAN
- PRIOR_MINT_REUSED
- ABSENT_AS_ZERO
- THRESHOLD_QUARTILE_LOO_OR_SMOOTHING_RESCUE
- SECOND_CAPTURE_WINDOW
- AUTOMATIC_THIRD_SAMPLE
- STRATEGY_BOT_SHADOW_ALPHA_OR_NETRETURN
- HARNESS_OR_PROCESS_ATOM
- RESEARCH_SCREEN_SCHEMA_OR_LEDGER
- CAUSAL_TRANSFORM_OR_SMA_EWMA
- DISCOVERY_OR_A7_ACTIVATION
- PREPARATORY_ONLY_READY_FOR_LIVE_PR
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-FALSIFIER-001
  - MODULE-EARLY-HOLDER-CONCENTRATION-H900-FALSIFIER-001
  - EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-RUNTIME-001
  - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v10.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/early_holder_concentration_h900_falsifier/a1_runtime_receipt_v1.json
    - docs/evidence/early_holder_concentration_h900_falsifier/a1_acceptance_v1.json
    - docs/evidence/early_holder_concentration_h900_falsifier/a1_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1

## Entry Gate

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`MODEL_EFFORT_RECOMMENDATION=ROUTINE_NO_SWITCH` — frozen science; identity
binding only. `NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at the live-phrase
checkpoint.

`ROADMAP_VERDICT=KEEP`

Owner-selected confirmatory after PR #190 merge + post-merge read-back.
Do not hunt a new hypothesis. Do not open Strategy/Shadow.

## Atom identity

```text
DECISION_DELTA: closed two-atom identity allowlist so confirmatory can bind
  a new phrase/terminals/receipt path without cloning campaign/X/Y/scorer
UNCERTAINTY_REMOVED: whether the frozen negative tau_b(X=topHoldersPercentage,
  Y=H900 quote recovery) replicates on a fresh non-overlapping EARLY sample
CAPABILITY_OR_EVIDENCE: one confirmatory PIT scientific/data terminal
STOP: exact owner provider phrase before first live byte; exact merge phrase
  after exact-head CI
NEXT: CLOSE_HOLDER_CONCENTRATION_AFTER_FAILED_CONFIRMATION |
  INVALID_EVIDENCE_REPLAN | HOLDER_CONCENTRATION_MECHANISM_REPLICATED
REPLAN_TRIGGER: any change to run_campaign / Kendall / X projector / quote
  orchestration / PIT; preparatory-only READY_FOR_LIVE; post-Y rescue
```

Allowed wrapper delta: read atom_id / owner_phrase / close / earn terminals
from the policy through a closed allowlist of the initial falsifier and this
confirmatory. Forbidden: new `run_*` campaign, search/BUY/H900/SELL loops,
second provider, X/Y/floor/sign change.

`ordinary_recent_organic_pressure_h900_audition.py` and
`factory/runner.py` must remain byte-identical to `origin/main`.

## Frozen scientific contract

Population `ICP-EARLY-PUMPFUN-V1`. 24 fresh mints. Exclude every previously
consumed research mint, including the PR #190 holder cohort and #189.

X = `audit.topHoldersPercentage` from one decision-time bulk search.
ABSENT = MISSING, never zero. Scale 0–100.

Y = quote-only BUY@decision → SELL@H900 recovery.

Expected: `tau_b < 0`. Floors: eligible 18, rankable 14.

Limitation: `jupiter_top_holders_pool_exclusion = UNKNOWN`.

## Terminals

- below floor / invalid X / degenerate tau / typed stop → `INVALID_EVIDENCE_REPLAN`
- valid and `tau_b >= 0` → `CLOSE_HOLDER_CONCENTRATION_AFTER_FAILED_CONFIRMATION`
- valid and `tau_b < 0` → `HOLDER_CONCENTRATION_MECHANISM_REPLICATED`

First replication is not alpha. No Strategy/Shadow. No third sample.

## Delivery ordering

```text
identity binding + tests + reviews
→ STOP for exact owner provider phrase
→ one fresh confirmatory window
→ scientific/data terminal
→ FINISH / PR / exact-head CI / merge / read-back
```

Do not start live without the phrase. Do not create a preparatory-only PR.

## Frozen owner provider phrase

Prepare, do not consume, until PRE_LIVE_HEAD. PowerShell: single-quoted
`--owner-phrase` so `$0` and `;` do not expand. `--config` is required for
this atom; omitting it binds the completed falsifier policy.

```
OK EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1: one bounded Jupiter Free-key read-only confirmatory campaign using a local process-environment key only; Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 population; 24 fresh project-eligible recent candidates excluding all prior consumed mints including EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1; wait until pool age >=5m before the single bulk decision-time search snapshot; X = audit.topHoldersPercentage from that search snapshot only (ABSENT never zero; scale 0-100); quote-only BUY at decision and quote-only SELL at H900; one confirmatory window only; sign-only Kendall tau_b < 0; no threshold, quartile, LOO, smoothing or second snapshot; Factory runner unchanged; Strategy, Bot, Shadow, alpha and NetReturn forbidden.
```

```
uv run --locked --managed-python python -B scripts/run_early_holder_concentration_h900_falsifier.py --config configs/early_holder_concentration_h900_confirmatory_oos_v1.yaml --owner-phrase '<PHRASE>' --excluded-mints-file local/early_holder_concentration_h900_confirmatory_oos/excluded_mints.json
```

## DoD

1. fresh non-overlapping confirmatory cohort;
2. campaign orchestration file unchanged vs origin/main;
3. X/Y/floors/sign unchanged;
4. one live confirmatory window → typed terminal;
5. no rescue;
6. Delivery Harness closeout only after the scientific terminal.
