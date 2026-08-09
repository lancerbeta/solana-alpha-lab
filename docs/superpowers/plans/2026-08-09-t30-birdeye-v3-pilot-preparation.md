# T30 Birdeye V3 Pair History Pilot Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, offline-only owner packet that specifies at most two future Birdeye V3 reads without performing, authorizing, or simulating either read.

**Architecture:** A versioned YAML policy is validated by a closed JSON Schema and evaluated by a pure Python function. The function returns only an offline-packet readiness result; it contains no HTTP client, credential value, raw-data path, or retry logic. A synthetic fixture, hash-bound acceptance receipt, and FULL_REVIEW receipt make the packet discoverable through the Catalog.

**Tech Stack:** Python 3.13, `unittest`, PyYAML, JSON Schema Draft 2020-12, existing Catalog generator.

## Global Constraints

- `T30-A5` performs zero provider/API/RPC/WSS calls, credential uses, raw-data writes, R2/R3 reads, dependency changes, wallet/signer/transaction actions, cash spend, trials, acceptance actions, or Project Sources changes.
- The future external stage is at most two credentialed `GET` reads, ordered identity before OHLCV; a failed first read blocks the second and neither has retry or fallback.
- `15m`, pair response fields, price unit, empty-interval meaning, completeness, PIT admissibility, alpha, PnL, and NetReturn remain unproven until a separately authorized result is reviewed.
- No credential value, authorization header value, local path, or request URL containing sensitive material may enter a tracked artifact.
- Generated Catalog views are produced only by `scripts/generate_navigation.py --write`.

---

### Task 1: Establish the fail-closed offline packet boundary

**Files:**
- Create: `tests/test_task30_birdeye_v3_pair_history_pilot.py`
- Create: `src/solana_alpha_lab/task30_birdeye_v3_pair_history_pilot.py`
- Create: `configs/task30_birdeye_v3_pair_history_pilot_v1.yaml`
- Create: `catalog/schemas/task30_birdeye_v3_pair_history_pilot.schema.json`
- Create: `tests/fixtures/task30/birdeye_v3_pair_history_pilot_v1.json`

**Interfaces:**
- Consumes: `Mapping[str, Any]` policy loaded from the versioned YAML.
- Produces: `evaluate_birdeye_v3_pair_history_pilot(policy) -> dict[str, Any]` with the sole decision `OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE`.

- [ ] **Step 1: Write the failing test**

```python
result = evaluate_birdeye_v3_pair_history_pilot(policy)
self.assertEqual(result["decision"], "OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE")
```

The test names the protected break: any future code that silently turns the offline packet into permission for a provider call.

- [ ] **Step 2: Run the focused test and verify it fails because the evaluator is missing**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_birdeye_v3_pair_history_pilot.py -v`

Expected: an import failure for `task30_birdeye_v3_pair_history_pilot`, not a fixture or environment error.

- [ ] **Step 3: Write the minimal evaluator and policy artifacts**

```python
def evaluate_birdeye_v3_pair_history_pilot(policy: Mapping[str, Any]) -> dict[str, Any]:
    # Validate exact two-stage, no-authority policy; never construct or send HTTP.
    return {
        "decision": "OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE",
        "future_external_authority": "NOT_GRANTED",
        "project_sources_disposition": "NO_CHANGE",
    }
```

The policy fixes the only permissible future order: `PAIR_OVERVIEW_IDENTITY_READ`, then `PAIR_OHLCV_RANGE_READ`, with candidate `type=15m`, `mode=range`, `padding=true`, exact historical bounds, and no factual claim that the request will be accepted or return a usable panel.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_birdeye_v3_pair_history_pilot.py -v`

Expected: PASS for schema validity, golden output, two-read ordering, and zero-authority state.

- [ ] **Step 5: Commit the independently testable packet core**

```bash
git add tests/test_task30_birdeye_v3_pair_history_pilot.py src/solana_alpha_lab/task30_birdeye_v3_pair_history_pilot.py configs/task30_birdeye_v3_pair_history_pilot_v1.yaml catalog/schemas/task30_birdeye_v3_pair_history_pilot.schema.json tests/fixtures/task30/birdeye_v3_pair_history_pilot_v1.json
git commit -m "feat: prepare offline Birdeye pair history pilot"
```

### Task 2: Add adversarial guards, evidence, and discovery

**Files:**
- Create: `docs/contracts/task30_birdeye_v3_pair_history_pilot_contract_v1.md`
- Create: `docs/evidence/task30/a5_birdeye_v3_pair_history_pilot_preparation_acceptance_v1.json`
- Create: `docs/evidence/task30/a5_birdeye_v3_pair_history_pilot_preparation_factory_fit_v1.json`
- Modify: `tests/test_task30_birdeye_v3_pair_history_pilot.py`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`
- Modify: `docs/OPERATOR_NAVIGATION.md`

**Interfaces:**
- Consumes: Task 1 policy, schema, fixture, evaluator, and existing A3/A4 receipts.
- Produces: a hash-bound `A5` offline-preparation receipt and Catalog assets that point only to tracked, non-secret files.

- [ ] **Step 1: Write failing adversarial tests**

```python
for pointer, replacement, error in (
    ("future_reads.1.query.type", "1m", "REQUEST_SHAPE_DRIFT"),
    ("authority.provider_api_rpc_wss_calls", 1, "EXTERNAL_AUTHORITY_FORBIDDEN"),
    ("semantic_claims.price_unit", "USD_PROVEN", "SEMANTIC_PROMOTION_FORBIDDEN"),
):
    with self.assertRaisesRegex(BirdeyeV3PairHistoryPilotError, error):
        evaluate_birdeye_v3_pair_history_pilot(mutated_policy)
```

The tests catch request-shape drift, authority widening, retry/fallback, tracked raw storage, credential-like material, and any promotion of missing/empty/PIT/price-unit semantics.

- [ ] **Step 2: Run the adversarial test and verify it fails for the missing guards**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_birdeye_v3_pair_history_pilot.py -v`

Expected: FAIL because the minimal core has not yet rejected at least one mutation.

- [ ] **Step 3: Implement only the guards and receipts needed for those tests**

```python
_require(policy["authority"]["provider_api_rpc_wss_calls"] == 0, "EXTERNAL_AUTHORITY_FORBIDDEN")
_require(policy["future_reads"][0]["stop_chain_on_non_200"] is True, "SEQUENCE_GUARD_DRIFT")
_require(policy["semantic_claims"]["pit_admissible"] is False, "SEMANTIC_PROMOTION_FORBIDDEN")
```

The human contract states the exact later approval boundary, raw-retention reference without a local path, stop conditions, and non-claims. Acceptance binds implementation artifacts by SHA-256 and records all external counters as zero. Catalog records use stable A5 IDs; generated views are regenerated rather than edited manually.

- [ ] **Step 4: Run targeted validation and Catalog generation**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_birdeye_v3_pair_history_pilot.py tests/test_task30_birdeye_pair_ohlcv_pilot_readiness.py tests/test_task30_reuse_first_pit_history_route_decision.py -v`

Run: `uv run --locked --managed-python python -B scripts/validate_catalog.py`

Run: `uv run --locked --managed-python python -B scripts/generate_navigation.py --write`

Expected: all targeted tests and Catalog validation PASS; only generated navigation files change after the generator runs.

- [ ] **Step 5: Commit the complete A5 offline package**

```bash
git add docs/contracts/task30_birdeye_v3_pair_history_pilot_contract_v1.md docs/evidence/task30/a5_birdeye_v3_pair_history_pilot_preparation_acceptance_v1.json docs/evidence/task30/a5_birdeye_v3_pair_history_pilot_preparation_factory_fit_v1.json tests/test_task30_birdeye_v3_pair_history_pilot.py catalog/assets/core.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md docs/OPERATOR_NAVIGATION.md
git commit -m "feat: bind Birdeye V3 history pilot packet"
```

### Task 3: Delivery verification

**Files:**
- Modify: no additional product artifacts expected.

**Interfaces:**
- Consumes: the exact committed candidate from Tasks 1–2.
- Produces: a tracked-only delivery receipt, a Draft PR, exact-head CI read-back, and a stop before the separately authorized provider reads.

- [ ] **Step 1: Inspect the committed changed-file inventory**

Run: `git diff --name-only origin/main...HEAD`

Expected: only plan, contract, config, schema, fixture, evaluator, test, evidence, Catalog source, and generated navigation files.

- [ ] **Step 2: Run the single delivery full gate**

Run: `uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

Expected: PASS with no skip added to hide absent raw data.

- [ ] **Step 3: Publish and independently read back CI**

Run: `git push --set-upstream origin task30/birdeye-v3-pilot-preparation`

Run: GitHub Draft PR creation and exact-head CI read-back.

Expected: non-force transport only; CI binds the published head.

- [ ] **Step 4: Stop at the external-material boundary**

The A5 result may prepare the owner’s future two-GET approval text but must not read `BIRDEYE_API_KEY`, make an HTTP request, or claim task acceptance.

## Self-Review

- Spec coverage: Tasks 1–2 cover the offline policy, exact future request shape, semantic non-claims, synthetic tests, receipts, Factory Fit, and Catalog; Task 3 covers scoped delivery only.
- Placeholder scan: no TBD/TODO steps; every code-bearing task defines its exact evaluator name, expected decision, primary failure classes, and commands.
- Type consistency: every later task consumes `evaluate_birdeye_v3_pair_history_pilot(policy)` from Task 1 and the same `OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE` decision.

## Execution Handoff

The goal owner’s standing preference selects inline execution. Proceed task-by-task in this session, preserving the red-green test cycle and stopping only before the separately authorized external two-GET stage.
