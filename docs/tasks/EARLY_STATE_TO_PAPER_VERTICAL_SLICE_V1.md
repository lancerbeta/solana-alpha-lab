---
task_id: EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6ba592634d26a2880b4084341c9de8711e1f0d3b
  expected_upstream: origin/main
  expected_upstream_oid: 6ba592634d26a2880b4084341c9de8711e1f0d3b
  expected_branch: cursor/early-state-to-paper-vertical-slice
  dirty_mode: ALLOW_REPORTED
objective: One bounded EARLY decision-time state hypothesis evaluated offline over Atom-1-pinned retained bytes, then a generic research-to-paper vertical slice - minimal StrategyVersion truth contract, data-driven signal/fill/position engine, COMMISSIONING_ONLY paper bot instance, and an OPERATIONS projection - with Factory core Python unchanged.
managed_write_set:
  - docs/tasks/EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1.md
  - configs/early_state_to_paper_vertical_slice_v1.yaml
  - configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml
  - configs/strategies/STRAT-V-EARLY-NETFLOW-TILT-COMMISSIONING-V1.yaml
  - catalog/schemas/strategy_version.schema.json
  - src/solana_alpha_lab/early_state_hypothesis.py
  - src/solana_alpha_lab/factory/paper_plane.py
  - scripts/run_early_state_hypothesis.py
  - tests/test_early_state_to_paper_vertical_slice.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/early_state_paper/a1_runtime_receipt_v1.json
  - docs/evidence/early_state_paper/a1_acceptance_v1.json
  - docs/evidence/early_state_paper/a1_delivery_completion_evidence_v1.json
  - docs/evidence/early_state_paper/a1_delivery_independent_review_v1.json
  - docs/evidence/early_state_paper/a1_delivery_factory_fit_v1.json
  - docs/reports/early_state_paper/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PROVIDER_OR_NETWORK_CALL_IN_THIS_WRITE_SET
  - CREDENTIAL_OR_API_KEY_READ
  - FACTORY_CORE_PYTHON_CHANGE
  - FEATURE_TOURNAMENT_OR_THRESHOLD_SEARCH
  - FOURTH_X_OR_POST_HOC_RULE
  - ML_MODEL_ANY_KIND
  - SIMULATED_FILL_AS_REAL_FILL
  - MICRO_LIVE_ACTIVATION_PATH
  - WALLET_SIGNER_TX_OR_CASH
  - ALPHA_OR_NETRETURN_CLAIM
  - POST_HOC_RESCUE_OF_SCIENTIFIC_FAIL
  - ARCHITECTURE_INTENT_OR_ROADMAP_EDIT
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-EARLY-ICP-FREEZE-RUNTIME-001
    - EVIDENCE-EARLY-ICP-FREEZE-ACCEPTANCE-001
    - CTRL-EARLY-ICP-FREEZE-AND-MATURITY-BRANCH-CLOSE-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/early_state_paper/a1_delivery_completion_evidence_v1.json
      - docs/evidence/early_state_paper/a1_delivery_independent_review_v1.json
      - docs/evidence/early_state_paper/a1_delivery_factory_fit_v1.json
      - docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json
      - docs/evidence/early_icp_freeze/a1_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=PRD_LITE`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

Owner direction: `muv-5.md` ATOM 2 - the main atom of the chain. This Git
contract is the bounded write set.

## Entry patches against live Git

1. The common market feature surface honestly carries `pit_ready_count: 0`
   and forbids PIT_READY on the retrospective surface. Therefore the honest
   decision-time X source is NOT the retrospective surface but the retained
   Atom-1 live capture bytes (decision-time snapshot at 2026-08-21T12:23:26Z
   plus the one maturity-probe later-search at T+76m), which are
   point-in-time by construction and hash-pinned in the Atom-1 config.
2. Legacy `registries/strategies.yaml` / `bot_instances.yaml` are TASK-03
   skeletons with closed schemas (`unevaluatedProperties: false`) too thin
   for operation, exactly as the memo states. They stay untouched and empty.
   The minimal new truth contracts are: a `strategy_version.schema.json`
   contract with versions as Git-tracked config, and a dedicated paper-plane
   SQLite store for bot/position runtime state. No second incompatible
   position model: the lifecycle enum is copied verbatim from
   ARCH-INTENT-005 section 7.
3. Factory core Python (`runner.py`, `capabilities.py`, `read_model.py`,
   `workbench.py`, `market_feature_surface.py`, `application.py`) must have
   zero diff versus `6ba5926`. Any required edit there is
   `REPLAN_BESPOKE_PIPELINE_REQUIRED`, not a silent core change.

## Decision capsule

- `DECISION_DELTA:` EARLY gets one frozen decision-time state hypothesis
  evaluated honestly offline, and the missing product path
  `decision -> StrategyVersion -> BotInstance -> PAPER -> position -> exit ->
  reconciliation` exists as a generic data-driven engine exercised by two
  config-only strategy versions.
- `UNCERTAINTY_REMOVED:` whether a research decision can reach a paper bot
  without bespoke pipeline Python, and what the one frozen EARLY state rule
  honestly says on retained evidence.
- `CAPABILITY_OR_EVIDENCE:` one scientific decision receipt over pinned
  bytes; one `strategy_version` schema contract; two config-only
  StrategyVersions (COMMISSIONING_ONLY); one generic paper-plane engine;
  one OPERATIONS projection with the nine owner fields.
- `STOP:` after targeted tests, PR and exact-head CI; exact owner merge
  phrase on unchanged head.
- `NEXT:` ATOM 3 `FACTORY_REMOTE_OPERATIONS_V1` under a new owner contract.
- `CHEAPEST_FALSIFIER:` adding a third strategy requires engine Python
  (leverage fail); SIMULATED_FILL reachable from a REAL_FILL state; a
  scientific PASS manufactured from degenerate outcome variance.
- `REPLAN_TRIGGER:` Factory core change; second preparatory-only atom;
  engine cannot express the second strategy as config.
- `strongest_rejected_alternative:` run a fresh live capture campaign for a
  bigger cohort. Rejected: this atom's falsifier is product-shape, not
  sample size; retained n=27 answers the frozen question honestly or
  returns NO_DECISION_VALUE without blocking commissioning.

## Scientific hypothesis (pre-declared before looking at outcomes)

Population: the exact 27-mint EARLY cohort from the Atom-1 freeze
(decision-time snapshot). Outcome window: the one retained later-search
observation (T+76m). Zero variance in binary survival (27/27 alive) is a
legitimate finding, not a bug to rescue.

Frozen X features (max 2, both decision-time, PIT by construction):

- `X_LIQUIDITY_USD`: pool liquidity at decision time (market/liquidity
  state).
- `X_NETFLOW_SHARE`: (stats5m.buyOrganicVolume - stats5m.sellOrganicVolume)
  / (buyOrganicVolume + sellOrganicVolume), typed UNKNOWN when the
  denominator is 0 (price/path/flow state).

Frozen rule bins (round thresholds declared here, not fitted):

- LIQ bin: `X_LIQUIDITY_USD >= 2000` vs `< 2000`.
- FLOW bin: `X_NETFLOW_SHARE > 0` vs `<= 0` (UNKNOWN excluded, counted).

Outcome: `Y_LIQUIDITY_RATIO` = later liquidity / decision-time liquidity
(both pump.fun, >= $1000 at decision time), plus coverage
(alive-and->=$1000 count).

Pre-declared promotion gate (all required, no post-hoc rescue):

1. both bins of the winning X have n >= 8 and non-degenerate Y spread;
2. higher-X bin strictly better on Y;
3. coverage >= 70% per bin.

Terminals: `EARLY_STATE_SIGNAL_PROMOTION_CANDIDATE`,
`EARLY_STATE_NO_DECISION_VALUE`. `EXECUTION_SURFACE_TOO_SPARSE` replaces the
terminal when fewer than 12 joined cohort rows survive the hash-pinned
replay. `PIT_STATE_SURFACE_NOT_READY` cannot fire here because honest
decision-time states exist; if the retained bytes were lost the atom
returns the Atom-1 gap terminal instead.

Scientific FAIL does not block product commissioning: the StrategyVersions
are born COMMISSIONING_ONLY either way (memo decoupling).

## StrategyVersion truth contract (minimal, first named consumer)

Fields per version (schema `smial.strategy-version.v1`): strategy_id,
strategy_version, title, source_decision_asset_id, hypothesis_ids,
evidence_class, population_id, icp_binding, signal_rule (declarative:
field/op/threshold over decision-time fields), entry_rule, exit_rule,
notional_policy (notional_usd, fee_bps, fill_basis),
risk_policy (max_open_positions), data_requirements,
execution_requirements, mode_eligibility {paper, shadow, micro_live},
commissioning_only, created_at, spec_sha256.

Invariants enforced by the engine, not by prose: `micro_live: true` is
rejected at load; `REAL_FILL` is not a producible signal kind; every
version carries `spec_sha256` at publish time.

## BotInstance and position runtime (SQLite, not Git)

PaperPlaneStore (new SQLite file `local/factory_v1/paper_plane_state.sqlite`)
owns bot_instances and positions tables: bot_instance_id, strategy_id,
strategy_version, mode (PAPER|SHADOW), status, started_at, stopped_at;
positions carry the ARCH-INTENT-005 lifecycle states WATCHED, SIGNALLED,
INTENT_CREATED, ATTEMPTING, OPEN, PARTIAL, UNKNOWN, EXIT_REQUIRED, EXITING,
CLOSED, UNRESOLVED, RECONCILED with a fail-closed transition table. Signal
kinds: NO_SIGNAL, NO_ROUTE, QUOTE_UNAVAILABLE, UNKNOWN, SIMULATED_FILL,
SHADOW_EXECUTABLE, REAL_FILL. `SIMULATED_FILL` never transitions a position
to any live-filled state; SHADOW mode in this atom evaluates executability
over retained evidence only and never opens positions.

## Leverage test (required by memo)

A second StrategyVersion differing ONLY in config (different signal rule)
must produce different paper behaviour through the identical engine with
zero engine diff. If it cannot, `REPLAN_BESPOKE_PIPELINE_REQUIRED`.

## OPERATIONS owner view (minimal)

One projection exposing exactly: Strategy, Bot, Mode, Signal, Position,
Exit readiness, Reconciliation, Blocker, Next safe action. Delivered as a
CLI/JSON projection in this atom; Workbench HTML wiring stays out of scope.

## PRD-lite non-goals

No live/provider calls; no quotes execution; no micro-live path; no ML; no
threshold search beyond the two declared bins; no Postgres; no Cockpit
roadmap; no alpha/NetReturn claims; legacy registries untouched; Factory
core untouched.

## DoD

1. Scientific decision receipt over hash-pinned retained bytes with the
   frozen gate applied verbatim.
2. `strategy_version.schema.json` + two valid config-only StrategyVersions,
   both COMMISSIONING_ONLY, micro_live rejected at load.
3. PaperPlaneStore bot + full position lifecycle exercised to RECONCILED on
   simulated fills; illegal transitions raise; SIMULATED_FILL can never
   become REAL_FILL.
4. Leverage test passes: strategy #2 behaves differently via config only.
5. OPERATIONS projection exposes the nine fields.
6. Catalog/generated propagation + owner readout + delivery evidence trio
   bound in DELIVERY_EVIDENCE before merge context.
