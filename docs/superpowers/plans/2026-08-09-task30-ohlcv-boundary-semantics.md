# TASK-30 OHLCV boundary semantics decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the Task30 A0 timestamp-boundary ambiguity as a deterministic offline decision instead of silently accepting a continuous 15-minute panel.

**Architecture:** A versioned policy binds the retained raw response through its SHA-256 and declares both start-labelled and end-labelled candle models. A thin evaluator validates the fail-closed decision against a synthetic fixture; the Catalog makes the contract discoverable without adding a data platform.

**Tech Stack:** Python 3.13, PyYAML, JSON Schema Draft 2020-12, unittest, existing Catalog generator.

## Global Constraints

- The atom is offline: provider/API/RPC/WSS calls, credentials, R2/R3 and dependency changes are forbidden.
- Raw JSON stays outside Git; only the A0 raw SHA-256 is tracked.
- Missing, zero volume, and continuous/PIT claims remain distinct.
- Generated Catalog navigation is regenerated only by `scripts/generate_navigation.py --write`.
- Project Sources disposition is `NO_CHANGE`.

---

### Task 1: Encode and test the fail-closed boundary decision

**Files:**
- Create: `docs/contracts/task30_ohlcv_boundary_semantics_decision_contract_v1.md`
- Create: `configs/task30_ohlcv_boundary_semantics_decision_v1.yaml`
- Create: `catalog/schemas/task30_ohlcv_boundary_semantics_decision.schema.json`
- Create: `tests/fixtures/task30/ohlcv_boundary_semantics_decision_v1.json`
- Create: `src/solana_alpha_lab/task30_ohlcv_boundary_semantics.py`
- Create: `tests/test_task30_ohlcv_boundary_semantics_decision.py`

**Interfaces:**
- Consumes: a mapping matching the task-owned YAML policy.
- Produces: `evaluate_boundary_semantics(config) -> {"decision", "candidate_models", "required_next_evidence"}`.

- [ ] **Step 1: Write the failing test**

Require the missing evaluator module, validate the YAML against its schema,
and assert that the synthetic A0 shape returns
`UNRESOLVED_INTERVAL_LABEL_SEMANTICS` with exactly two incompatible models.
Add negative cases for selected model, a continuous/PIT claim, an
`EXPLICIT_NO_TRADE` promotion, and non-zero external/trial authority.

Run: `uv run --locked --managed-python python -m unittest tests.test_task30_ohlcv_boundary_semantics_decision -q`

Expected: FAIL because the contract artifacts and evaluator do not yet exist.

- [ ] **Step 2: Add the minimal task-owned artifacts and evaluator**

Create only the policy, schema, fixture, contract and evaluator required to
make the test pass. The evaluator must reject any configuration where the
observed response shape selects a label model or changes the blocked decision.

- [ ] **Step 3: Re-run the targeted test**

Run: `uv run --locked --managed-python python -m unittest tests.test_task30_ohlcv_boundary_semantics_decision -q`

Expected: PASS.

### Task 2: Register the decision and validate delivery

**Files:**
- Create: `docs/evidence/task30/a1_ohlcv_boundary_semantics_decision_acceptance_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify (generated): `catalog/catalog_manifest.yaml`, `docs/PROJECT_MAP.md`, `catalog/generated/asset_edges.json`

**Interfaces:**
- Consumes: the validated Task 1 files and their SHA-256 values.
- Produces: stable Catalog IDs for the contract, policy, schema, fixture,
  evaluator, test and acceptance receipt.

- [ ] **Step 1: Add a targeted acceptance receipt and Catalog records**

The receipt must bind the A0 raw SHA-256, record zero external actions, state
`NO_CHANGE` for Project Sources, and prohibit Task30 trial acceptance.

- [ ] **Step 2: Regenerate Catalog navigation**

Run: `uv run --locked --managed-python python -B scripts/generate_navigation.py --write`

- [ ] **Step 3: Validate changed behavior and Catalog integrity**

Run:
`uv run --locked --managed-python python -m unittest tests.test_task30_ohlcv_boundary_semantics_decision -q`

Run:
`uv run --locked --managed-python python -B scripts/validate_catalog.py`

Expected: both PASS.

- [ ] **Step 4: Commit and run the delivery gate**

Commit the exact inventory, then run:
`uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

Expected: isolated clean-checkout PASS; afterwards push the exact commit,
read exact-head CI, apply `OWNER_ATTENTION_GATE`, merge only when its machine
decision is `AUTONOMOUS`, and verify post-merge `main` CI.
