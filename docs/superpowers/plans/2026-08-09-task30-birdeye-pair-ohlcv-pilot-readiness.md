# TASK-30 Birdeye pair OHLCV pilot readiness boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository deterministically reject a Birdeye historical OHLCV proof call until the REST `15m` enum, exact pair identity, local key-presence attestation, and a new owner one-call authority are independently established.

**Architecture:** A versioned offline policy records REST and WebSocket evidence separately and returns one fail-closed readiness decision. A thin Python evaluator validates that policy and the absence of external authority or credential material. Hash-bound receipts and Catalog records make the boundary discoverable without adding a provider adapter.

**Tech Stack:** Python 3.13, PyYAML, JSON Schema Draft 2020-12, `unittest`, existing Catalog generator.

## Global Constraints

- Atom is `T30-A3_BIRDEYE_PAIR_OHLCV_PILOT_READINESS_BOUNDARY_V1`.
- No provider/API/RPC/WSS calls, credential use, raw-data retention, R2/R3, dependencies, wallet/signer/transactions, cash, TASK-30 trial/acceptance, or Project Sources changes.
- A WebSocket `15m` statement cannot prove a historical REST request enum.
- A GeckoTerminal pool is not a Birdeye pair without a separately bound identity proof.
- No policy, fixture, receipt, test, or log may contain credential material.
- The only valid decision is `NOT_READY_FOR_PROVIDER_PILOT`; no continuous-panel, PIT, alpha, trial, execution, PnL, or NetReturn claim is allowed.
- Generated Catalog navigation is written only by `uv run --locked --managed-python python -B scripts/generate_navigation.py --write`.
- Project Sources disposition is `NO_CHANGE`; canonical task status remains with the Project control plane.

---

### Task 1: Encode the offline readiness policy and evaluator

**Files:**
- Create: `docs/contracts/task30_birdeye_pair_ohlcv_pilot_readiness_contract_v1.md`
- Create: `configs/task30_birdeye_pair_ohlcv_pilot_readiness_v1.yaml`
- Create: `catalog/schemas/task30_birdeye_pair_ohlcv_pilot_readiness.schema.json`
- Create: `tests/fixtures/task30/birdeye_pair_ohlcv_pilot_readiness_v1.json`
- Create: `src/solana_alpha_lab/task30_birdeye_pair_ohlcv_pilot_readiness.py`
- Create: `tests/test_task30_birdeye_pair_ohlcv_pilot_readiness.py`

**Interfaces:**
- Consumes: a mapping conforming to `smial.task30.birdeye-pair-ohlcv-pilot-readiness.policy` v1.0.
- Produces: `evaluate_pilot_readiness(config: Mapping[str, Any]) -> dict[str, Any]`.
- Raises: `PilotReadinessError` with one stable machine error code on any safety or scope violation.
- Returns:

  ```python
  {
      "decision": "NOT_READY_FOR_PROVIDER_PILOT",
      "blockers": [
          "BIRDEYE_REST_15M_ENUM_UNPROVEN",
          "BIRDEYE_PAIR_IDENTITY_UNPROVEN",
          "BIRDEYE_API_KEY_LOCAL_PRESENCE_UNATTESTED",
          "OWNER_ONE_CALL_AUTHORITY_NOT_GRANTED",
      ],
      "project_sources_disposition": "NO_CHANGE",
  }
  ```

- [x] **Step 1: Write the failing deterministic test**

  Add a `unittest` module that loads the YAML policy, JSON Schema, and synthetic fixture. Require the exact return value above. Test these adversarial replacements one at a time:

  ```python
  cases = (
      ("evidence.rest_15m_enum", "PROVEN", "REST_15M_ENUM_UNPROVEN"),
      ("evidence.websocket_15m", "REST_ADMISSIBLE", "WEBSOCKET_NOT_REST_EVIDENCE"),
      ("pair_identity.status", "PROVEN", "PAIR_IDENTITY_UNPROVEN"),
      ("authority.provider_api_rpc_wss_calls", 1, "EXTERNAL_AUTHORITY_FORBIDDEN"),
      ("authority.credential_use", True, "EXTERNAL_AUTHORITY_FORBIDDEN"),
      ("decision", "SURFACE_FEASIBLE_NOT_ACCEPTED", "DECISION_PROMOTION_FORBIDDEN"),
      ("credential_probe.api_key", "not-a-real-key", "CREDENTIAL_DISCLOSURE_FORBIDDEN"),
  )
  ```

  Also reject a raw-data path, retry count above zero, fallback provider, non-`NO_CHANGE` Project Sources disposition, and true `continuous_panel_claim`, `pit_admissible_claim`, `task30_trial_claim`, or `numeric_netreturn_claim`.

  Run:

  ```text
  uv run --locked --managed-python python -m unittest tests.test_task30_birdeye_pair_ohlcv_pilot_readiness -q
  ```

  Expected: FAIL because the policy, schema, fixture, and evaluator do not yet exist.

- [x] **Step 2: Add the minimum fail-closed implementation**

  Write the contract and YAML policy with these immutable values:

  ```yaml
  schema: smial.task30.birdeye-pair-ohlcv-pilot-readiness.policy
  schema_version: '1.0'
  task_id: TASK-30
  atom_id: T30-A3_BIRDEYE_PAIR_OHLCV_PILOT_READINESS_BOUNDARY_V1
  contract_id: TASK30-BIRDEYE-PAIR-OHLCV-PILOT-READINESS-V1
  decision: NOT_READY_FOR_PROVIDER_PILOT
  project_sources_disposition: NO_CHANGE
  ```

  Record only documentation facts: pair OHLCV uses Unix `time_from`/`time_to`, needs an API key, and documents `padding`. Set `rest_15m_enum: UNPROVEN`, `websocket_15m: OBSERVED_NOT_REST_ADMISSIBLE`, pair identity `UNPROVEN`, and key presence `UNATTESTED`.

  Implement `_require`, a recursive key scan for `api_key`, `api_key_value`, `authorization`, `token`, `secret`, and `password`, and `evaluate_pilot_readiness`. First reject non-zero/true external counters, then credential material and each attempted resolution of the four frozen prerequisites. Import no HTTP client and issue no request.

  Make the schema closed (`additionalProperties: false`) at all policy objects, require every authority and non-claim field, and constrain them to the offline state. The fixture is `SYNTHETIC_GOLDEN_ONLY` and has no provider response or credential.

- [x] **Step 3: Prove the core boundary**

  Run:

  ```text
  uv run --locked --managed-python python -m unittest tests.test_task30_birdeye_pair_ohlcv_pilot_readiness -q
  git diff --check
  ```

  Expected: focused test PASS and no whitespace error.

### Task 2: Bind acceptance evidence and register the boundary

**Files:**
- Create: `docs/evidence/task30/a3_birdeye_pair_ohlcv_pilot_readiness_acceptance_v1.json`
- Create: `docs/evidence/task30/a4_birdeye_pair_ohlcv_pilot_readiness_factory_fit_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify (generated): `catalog/catalog_manifest.yaml`
- Modify (generated): `catalog/generated/asset_edges.json`
- Modify (generated): `docs/PROJECT_MAP.md`
- Modify: `tests/test_task30_birdeye_pair_ohlcv_pilot_readiness.py`

**Interfaces:**
- Consumes: Task 1 paths and calculated SHA-256 digests.
- Produces: zero-side-effect acceptance evidence and stable Catalog IDs for the contract, policy, schema, fixture, evaluator, test, and two receipts.

- [x] **Step 1: Extend the test for receipts and Catalog**

  Add a hash-binding assertion for all six Task 1 artifacts. Require zero counters and `project_sources_disposition.kind == "NO_CHANGE"`. Require this Factory Fit evidence:

  ```python
  self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
  self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
  self.assertEqual(factory_fit["reuse_first"]["outcome"], "STOP")
  self.assertEqual(factory_fit["product_horizon"]["now"]["candidate"], "NO_PROVIDER_PILOT_UNTIL_EXACT_PROOFS")
  ```

  Require these asset IDs:

  ```python
  {
      "CONTRACT-T30-BIRDEYE-PILOT-READINESS-001",
      "CONFIG-T30-BIRDEYE-PILOT-READINESS-001",
      "SCHEMA-T30-BIRDEYE-PILOT-READINESS-001",
      "FIXTURE-T30-BIRDEYE-PILOT-READINESS-001",
      "MODULE-T30-BIRDEYE-PILOT-READINESS-001",
      "TEST-T30-BIRDEYE-PILOT-READINESS-001",
      "EVIDENCE-T30-A3-BIRDEYE-PILOT-READINESS-001",
      "EVIDENCE-T30-A4-BIRDEYE-PILOT-FACTORY-FIT-001",
  }
  ```

  Run the focused test. Expected: FAIL because receipts and records do not yet exist.

- [x] **Step 2: Create receipts and Catalog records**

  Calculate hashes only after Task 1 bytes are final. The A3 receipt binds the six artifacts and records zero for provider calls, credential uses, raw-data writes, R2/R3 reads, wallet/signer/transactions, cash spend, dependencies, and Project Sources changes. It lists every forbidden promotion.

  The A4 `FULL_REVIEW` records `STOP`: no current candidate is admissible for the historical REST 15-minute surface. Its `NOW` is the readiness boundary. Its sole `WATCH` trigger is independently bound REST-15m enum plus exact pair identity, followed by a separate owner authority decision.

  Append the eight Catalog records using the existing Task 30 record shape, `status: IMPLEMENTED_UNVERIFIED`, `truth_owner: TASK-30`, repository paths, and calculated SHA-256 values. Do not manually edit generated files.

- [x] **Step 3: Regenerate and validate**

  Run:

  ```text
  uv run --locked --managed-python python -B scripts/generate_navigation.py --write
  uv run --locked --managed-python python -m unittest tests.test_task30_birdeye_pair_ohlcv_pilot_readiness -q
  uv run --locked --managed-python python -B scripts/validate_catalog.py
  ```

  Expected: all PASS; generated navigation describes only the eight new records and their existing consumers.

### Task 3: Deliver the exact offline candidate

**Files:**
- Modify: `docs/superpowers/plans/2026-08-09-task30-birdeye-pair-ohlcv-pilot-readiness.md` (mark a step complete only after its stated check passes)
- Verify: only the files from Tasks 1–2, the generated Catalog outputs, this plan, and the already committed design document.

**Interfaces:**
- Consumes: committed implementation bytes with focused and Catalog checks passing.
- Produces: a task-branch delivery candidate; it does not produce provider authority or canonical TASK-30 acceptance.

- [ ] **Step 1: Inspect scope and commit**

  Require `git diff --check`, the existing pre-commit secret scan, and the exact file inventory above. Commit the implementation as:

  ```text
  feat: add Birdeye pilot readiness boundary
  ```

- [ ] **Step 2: Run the one full local delivery owner**

  Run after committing the exact candidate:

  ```text
  uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
  ```

  Expected: isolated tracked-only checkout PASS. Do not run a duplicate ordinary full gate on unchanged bytes.

- [ ] **Step 3: Transport and independent validation**

  Non-force push the exact branch, create one Draft PR, and read back GitHub CI for the exact head. Apply `control/owner_attention_gate_v1.yaml` before merge. On the `LOCAL_WORK_CODEX` route, merge only when that machine gate returns `AUTONOMOUS` and CI succeeds; then read back the exact `main` commit and its push CI. Never infer canonical acceptance or provider authority from delivery.

## Plan self-review

- **Spec coverage:** Task 1 implements all four frozen prerequisites, offline authority, non-claims, and adversarial rejection. Task 2 supplies acceptance, `FULL_REVIEW`, Product Horizon, and discoverability. Task 3 applies repository delivery policy without widening scope.
- **Scope:** one policy/evaluator boundary plus evidence and Catalog consumers; no adapter, provider client, key probe, or data pipeline.
- **Type consistency:** `evaluate_pilot_readiness` and `PilotReadinessError` are the only module interface; returned decision and blocker strings stay identical across policy, fixture, test, receipts, and Catalog.
- **Placeholder scan:** no unresolved implementation placeholder or deferred behavior.
