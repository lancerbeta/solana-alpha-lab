---
task_id: EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7d0e5b958590070b9178b35104f54c6d84fe1134
  expected_upstream: origin/main
  expected_upstream_oid: 7d0e5b958590070b9178b35104f54c6d84fe1134
  expected_branch: cursor/early-structural-backing-pit-commissioning
  dirty_mode: ALLOW_REPORTED
objective: Run one prospective PIT commissioning of EARLY structural backing
  (liquidity/mcap at decision time vs H900 quoted liquidation recovery) through
  the existing wait-then-search quote campaign, with Window A then conditional
  Window B, Factory runner unchanged, and a typed CLOSE or EARN_SHADOW terminal.
managed_write_set:
- docs/tasks/EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1.md
- configs/early_structural_backing_pit_commissioning_v1.yaml
- src/solana_alpha_lab/early_structural_backing_pit_commissioning.py
- scripts/run_early_structural_backing_pit_commissioning.py
- tests/test_early_structural_backing_pit_commissioning.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/early_structural_backing_pit_commissioning/a1_window_a_runtime_receipt_v1.json
- docs/evidence/early_structural_backing_pit_commissioning/a1_window_b_runtime_receipt_v1.json
- docs/evidence/early_structural_backing_pit_commissioning/a1_family_decision_v1.json
- docs/evidence/early_structural_backing_pit_commissioning/a1_acceptance_v1.json
- docs/evidence/early_structural_backing_pit_commissioning/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_structural_backing_pit_commissioning/a1_delivery_independent_review_v1.json
- docs/evidence/early_structural_backing_pit_commissioning/a1_delivery_factory_fit_v1.json
- docs/reports/early_structural_backing_pit_commissioning/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
- CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION
- CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT
- DOTENV_READ
- API_KEY_IN_URL_LOG_RECEIPT_OR_GIT
- RAW_BODY_CONTAINS_CREDENTIAL
- JUPITER_EXECUTE_OR_BUILD
- TAKER_OR_SIGNER_SUPPLIED
- WALLET_SIGNER_TRANSACTION_OR_DEPLOYMENT
- RETRY_OR_FALLBACK
- CALL_CAP_EXCEEDED
- PACE_BELOW_THREE_SECONDS
- SECOND_PROVIDER_OR_PAID_PLAN
- PRIOR_MINT_REUSED
- UNKNOWN_AS_ZERO
- FDV_AS_MCAP_SUBSTITUTE
- FACTORY_RUNNER_CHANGE
- THRESHOLD_SEARCH_AFTER_Y
- THIRD_CAPTURE_WINDOW
- VPS_OR_SHADOW_OR_MICRO_LIVE
- ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-ICP-FREEZE-AND-MATURITY-BRANCH-CLOSE-001
  - MODULE-ORDINARY-MARKET-PIT-PRIMARY-X-001
  - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - EVIDENCE-ORDINARY-MARKET-PIT-OFFLINE-XY-ASSOCIATION-ACCEPTANCE-001
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
    - configs/early_icp_freeze_and_maturity_branch_close_v1.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/ordinary_market_pit_offline_xy_association/a1_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP` for the owner macro-plan Atom 1→6; this contract
executes only Atom 1. Atoms 2–6 remain non-authoritative conditional context.

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge after scientific terminal.

Offline predecessor
`ORDINARY_MARKET_PIT_OFFLINE_XY_ASSOCIATION_V1` ended
`DEFER_FRESH_PIT_CAPTURE` with `FORWARD_SNAPSHOT_NOT_PIT_READY`. This atom is
that deferred prospective capture plus decision — not a prep-only PR.

`strongest_rejected_alternative`: start Atom 2 unattended SHADOW first.
Rejected because the open market question is cheaper to kill/rehabilitate
with PIT evidence, and Atom 2 can still commission on
`COMMISSIONING_ONLY` after scientific FAIL.

`ADOPTION_ROUTE=ADOPT_ORGANIC_WAIT_THEN_SEARCH_AND_BIND_PRIMARY_X_WRAP_ICP_PROJECTOR_BUILD_NO_FACTORY_RUNNER`

## Owner authorization boundary

Implementation, zero-network tests, commit and PR may proceed under
`DIRECT_CURSOR_DELIVERY`. Provider calls require this exact phrase after
offline preflight is green:

```
OK EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1: one bounded Jupiter Free-key read-only PIT commissioning campaign using a local process-environment key only; Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 population; 24 fresh project-eligible recent candidates excluding all prior consumed mints; wait until pool age >=5m before the single bulk decision-time search snapshot; X = liquidity / mcap from that search snapshot only (mcap != fdv; UNKNOWN never zero); quote-only BUY at T0 and quote-only SELL at H900; Window A then conditional Window B only if A is not CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY; no third window; Factory runner unchanged; Strategy, Bot, Shadow, alpha and NetReturn forbidden.
```

## PRD-lite

- **Owner decision:** `CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY` or
  `EARN_SHADOW` (screening promotion only), else typed evidence failure.
- **Product outcome:** prospective PIT X coverage + H900 quote Y on
  `ICP-EARLY-PUMPFUN-V1` through existing campaign machinery; Factory core
  change target 0.
- **Named consumer:** Atom 2 unattended SHADOW (promotable or
  `COMMISSIONING_ONLY`).
- **Current gap:** offline join deferred fresh capture; `pit_ready_count=0`.
- **Success / cheapest falsifier:** Window A kill on non-positive/fragile
  direction; else Window B replication; both windows same positive direction
  for `EARN_SHADOW`; `fdv` never substitutes `mcap`; UNKNOWN ≠ 0;
  `factory/runner.py` hash unchanged.
- **Non-goals:** alpha, NetReturn, fill, SHADOW runtime, VPS, discovery,
  new provider, threshold search after Y, third window.
- **Evidence budget:** ≤2 live windows; call cap 60 each; cash $0.
- **Replan trigger:** Factory runner change required; ICP band cannot be
  composed without bespoke core runner; credential/phrase drift.

## SSD-lite

- **Baseline truth:** `origin/main` `7d0e5b958590070b9178b35104f54c6d84fe1134`.
- **Design:** ADOPT organic wait-then-search + H900 quotes + `bind_primary_x`.
  WRAP ICP age/liquidity filter and Window A/B family decision. FORK nothing
  in Factory Python. BUILD only the experiment projector + CLI.
- **Invariants:** X from search-row `liquidity`/`mcap` only; age ∈ [300,900);
  liquidity ≥ 1000; quote ≠ fill; no third window; runner unchanged.
- **Y:** campaign stores `sell_out/notional - 1` (rank-equivalent to recovery
  when buy `inAmount` equals frozen notional); receipts also expose typed
  quote terminals.
- **Tactical note:** organic campaign hard-waits ≥5m after `/recent` and
  freezes score floors at 18/14. ICP membership is enforced in `project_x`
  (`TOO_OLD` / liquidity). Yield shortfall is `INVALID_EVIDENCE_YIELD`, not
  silent promotion.
- **Validation:** zero-network unit tests before any credential read; mocked
  campaign; runner SHA pin; isolated critics after live terminal.
- **Rollback:** revert branch; consumed market observations stay historical.

## Decision capsule

- `DECISION_DELTA`: close the deferred fresh-PIT gap for structural backing
  before building unattended SHADOW.
- `UNCERTAINTY_REMOVED`: whether decision-time liquidity/mcap carries
  screening signal for H900 quoted recovery inside EARLY ICP.
- `CAPABILITY_OR_EVIDENCE`: Window A(+B) receipts + family decision; Factory
  composition proof without runner change.
- `STOP`: exact owner phrase before live capture; PR + exact-head CI before
  merge phrase.
- `NEXT`: Atom 2 with `SHADOW_CANDIDATE` or `COMMISSIONING_ONLY`.
- `REPLAN_TRIGGER`: runner change required; third window requested;
  threshold search after Y.

## Definition of Done

1. Exact contract + policy + projector + CLI + tests landed.
2. Zero-network tests prove: missing/zero mcap → UNKNOWN; fdv rejected;
   TOO_YOUNG/TOO_OLD; wrong phrase → 0 credential reads; runner SHA pin.
3. Live Window A after owner phrase; Window B only if A ≠ CLOSE.
4. Family terminal is one of `CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY`,
   `EARN_SHADOW`, or typed `INVALID_EVIDENCE_*` (no silent promote).
5. No `factory/runner.py` diff. No wallet/signer/execute.
6. Delivery trio + owner readout bound before merge context.
