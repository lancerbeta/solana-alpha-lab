---
task_id: ORDINARY_MARKET_PIT_LOCAL_RAW_ENVELOPE_BIND_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 06702dc8e5a6e5ff01b07a0959baa005c46192fe
  expected_upstream: origin/main
  expected_upstream_oid: 06702dc8e5a6e5ff01b07a0959baa005c46192fe
  expected_branch: cursor/ordinary-market-pit-local-raw-envelope
  dirty_mode: ALLOW_REPORTED
objective: Bind ordinary-market primary X as liquidity/mcap from hash-verified
  local Tokens V2 discovery envelopes for the frozen 12-mint qualification
  cohort, without live Jupiter, Git raw bodies, or Factory Python.
managed_write_set:
- docs/tasks/ORDINARY_MARKET_PIT_LOCAL_RAW_ENVELOPE_BIND_V1.md
- configs/ordinary_market_pit_local_raw_envelope_bind_v1.yaml
- src/solana_alpha_lab/ordinary_market_pit_local_raw_envelope.py
- scripts/run_ordinary_market_pit_local_raw_envelope_bind.py
- tests/test_ordinary_market_pit_local_raw_envelope_bind.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_runtime_receipt_v1.json
- docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_acceptance_v1.json
- docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_delivery_completion_evidence_v1.json
- docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_delivery_independent_review_v1.json
- docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_delivery_factory_fit_v1.json
- docs/reports/ordinary_market_pit_local_raw_envelope_bind/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_OR_NETWORK_CALL
- CREDENTIAL_OR_API_KEY_READ
- FACTORY_PYTHON_CHANGE
- FDV_USED_AS_MCAP
- NUMERIC_UNKNOWN_AS_ZERO
- PIT_READY_CLAIM
- LIVE_MARKET_SCORING
- LIVE_JUPITER_CAPTURE
- RAW_ENVELOPE_COMMITTED_TO_GIT
- THIRD_ORDINARY_YAML
- QUOTE_KEEP_AS_PREDICTOR
- TASK28_SKELETON_REGISTRY_REWRITE
- VPS_OR_DEPLOYMENT
- ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
  - CTRL-ORDINARY-MARKET-PIT-PRIMARY-X-BIND-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009
  - MODULE-FACTORY-V1-RUNNER-001
  - EVIDENCE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json
    - docs/evidence/ordinary_market_pit_primary_x_bind/a1_runtime_receipt_v1.json
    - docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_delivery_completion_evidence_v1.json
    - docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_delivery_independent_review_v1.json
    - docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# ORDINARY_MARKET_PIT_LOCAL_RAW_ENVELOPE_BIND_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=PATCH`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge.

Muv-2 Move 1 remains the right sequence: ordinary-market PIT, not a third YAML
and not VPS. PR #163 proved Git-retained cells cannot bind `liquidity/mcap`.
Its recorded next step (`OWNER_BOUNDED_JUPITER_CAPTURE_WITH_RAW_RETENTION`) is
now the wrong cheapest atom. Historical/reusable cache first: qualification
raw Tokens V2 envelopes already exist under A4, hash-match the Git manifests,
and contain `mcap`. All 12 frozen cohort mints bind from those envelopes
without a provider call.

This atom is still Move 1: project X from local hash-verified envelopes onto
the Git cohort. It is not a live audition, not PIT_READY, and not n=12
association with quote outcomes.

`strongest_rejected_alternative`: start live Jupiter capture now. Rejected
because the field gap is reconstructable from local A4; live calls need a
later owner phrase and would not change the already-answered question.

`ADOPTION_ROUTE=ADOPT_LOCAL_A4_AND_EXISTING_BIND_PRIMARY_X_WRAP_JOIN_PROJECTOR_BUILD_NO_FACTORY_PYTHON`

## PRD-lite

- **Owner decision:** live recapture is not required to obtain `mcap` for this
  cohort. After this bind, choose offline n=12 association versus a fresh
  sample.
- **Product outcome:** `LOCAL_RAW_ENVELOPES_BIND_PRIMARY_X` for the 12 Git
  qualification cells; envelope sha256 matches Git manifests; raw bodies stay
  A4 and out of Git; `fdv` unused; UNKNOWN never coerced to 0.
- **Named consumer:** the owner choosing the first ordinary-market trial
  shape for `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1`.
- **Current gap:** Git cells lack `mcap`, but local raw envelopes have it and
  were not projected.
- **Success / cheapest falsifier:** 12/12 finite `liquidity/mcap`; Git still
  has 0 `mcap` keys on frozen cells; local files hash-match; 0 provider calls.
  Local hash mismatch or committing raw bodies is replan.
- **Invalidation:** treating this as PIT_READY or alpha; scoring Y in this
  atom; calling Jupiter; using `fdv` as `mcap`; copying raw envelopes into Git.
- **Non-goals:** live capture, quote association, VPS, Cockpit, third YAML,
  TASK-28 unfreeze, Factory Python, `/execute`, alpha.
- **Evidence budget:** local A4 + Git receipts; 0 provider calls.
- **Replan trigger:** local A4 absent or hash mismatch; envelopes lack `mcap`
  for the cohort; Factory Python must change.

## SSD-lite

- **Baseline truth:** `origin/main` after PR #163.
- **Design:** ADOPT qualification raw_sink A4 and `bind_primary_x`. WRAP a
  fail-closed join projector. FORK nothing in `src/solana_alpha_lab/factory/*`.
  BUILD tests + Catalog/evidence. Do not git raw bodies.
- **Invariants:** `mcap` only, never `fdv`; UNKNOWN != 0; Git cells unchanged;
  `FORWARD_SNAPSHOT_NOT_PIT_READY`; TASK-28 empty; 0 provider calls;
  liquidity on Git cell must match envelope liquidity.
- **Affected surfaces:** new bind config, projector, CLI, tests, receipts.
  Not Factory Python, not quote scorers, not A4 files.
- **Failure modes:** missing local A4; hash drift; catalog hash drift;
  claiming PIT_READY.
- **Validation:** unit tests (CI uses fixtures; optional local A4 recompute);
  isolated critics; exact-head CI.
- **Rollback:** revert this branch.

## Decision capsule

- `DECISION_DELTA`: PATCH Move 1 away from live capture; bind X from hash-verified
  local Tokens V2 envelopes that Git cells stripped.
- `UNCERTAINTY_REMOVED`: whether historical A4 discovery bodies contain `mcap`
  for the frozen 12-mint cohort (they do; 12/12 bind).
- `CAPABILITY_OR_EVIDENCE`: join projector; Git receipt of bound ratios +
  envelope hashes; raw bodies remain A4_OUTSIDE_GIT.
- `STOP`: PR + exact-head CI; wait for owner merge phrase.
- `NEXT`: owner chooses offline n=12 association on already-quoted cells, or a
  later fresh sample. Not VPS. Not another YAML. Not live capture for mcap.
- `REPLAN_TRIGGER`: local hash mismatch; raw body leaked to Git; Factory Python
  change; live calls leak into this atom.

## Definition of Done

1. Same frozen hypothesis id `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1`.
2. Local DISCOVERY recent/traded envelopes hash-match Git manifests.
3. 12/12 cohort cells bind finite `liquidity/mcap`; Git frozen cells still have
   0 `mcap` keys.
4. Raw token-list bodies are not added to Git.
5. No Factory Python in the diff; `runner.py` hash unchanged.
6. 0 provider calls. No PIT_READY/alpha/VPS/KEEP-as-X/live capture.
7. TASK-28 skeletons empty.
8. Delivery trio bound in `DELIVERY_EVIDENCE` before merge context.
