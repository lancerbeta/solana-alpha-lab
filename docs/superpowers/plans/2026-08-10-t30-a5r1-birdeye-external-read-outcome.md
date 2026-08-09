# Birdeye V3 external-read outcome capture Implementation Plan

> **For agentic workers:** execute inline in this isolated worktree. Do not dispatch subagents; the task is one bounded evidence receipt.

**Goal:** Preserve the exact two-read Birdeye observation as a fail-closed
TASK-30 evidence record without reissuing a provider request or claiming a
historical panel.

**Architecture:** Reuse the merged A5 contract as the only request authority.
Add a hash-bound runtime receipt that points to A4-retained raw bytes and a
FULL_REVIEW receipt that turns HTTP 429 into an explicit unavailable outcome,
not into `NO_ROUTE` or no-trade. A deterministic test binds these receipts and
their Catalog registrations; no new collector, client, schema, or data model
is introduced.

**Tech Stack:** JSON evidence, Python `unittest`, existing Catalog generator.

## Global Constraints

- No more Birdeye/provider/API/RPC/WSS calls; the authorized cap of two was consumed.
- Retained raw stays only under `local/task30_birdeye_v3_pair_history_pilot/` outside Git.
- No key value, raw response body, R2/R3 data, wallet, transaction, spend, trial, or canonical TASK-30 acceptance.
- Preserve `429` as `RATE_OR_QUOTA_LIMITED`, not missing history, no trade, or unsupported pair.
- Reuse the merged A5 contract; do not create a generic provider component.

---

### Task 1: Bind the observed outcome and Factory Fit decision

**Files:**
- Create: `tests/test_task30_birdeye_v3_external_read_runtime_receipt.py`
- Create: `docs/evidence/task30/a5r1_birdeye_v3_external_read_runtime_receipt_v1.json`
- Create: `docs/evidence/task30/a5r1_birdeye_v3_external_read_factory_fit_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify (generated): `catalog/generated/asset_edges.json`
- Modify (generated): `docs/PROJECT_MAP.md`

**Interfaces:**
- Consumes: the A5 contract SHA-256 `298b140843ffb9c519db853aa7f48bdc098567f3e564db058ff2e0b2ecac3b33` and A4 raw-manifest SHA-256 `4a8877e957dd43d5fa10e738c9c5af9c2a4cfd3ae619d0f357b002af04c2a7d3`.
- Produces: append-only runtime evidence with `PAIR_IDENTITY_ACCEPTED_OHLCV_RATE_OR_QUOTA_LIMITED` and a `FULL_REVIEW` decision that forbids retry/fallback.

- [x] **Step 1: Write the failing test**

```python
def test_two_read_outcome_is_bound_and_does_not_promote_history():
    receipt = load_json(RUNTIME_RECEIPT)
    assert receipt["provider_calls_attempted"] == 2
    assert receipt["reads"][0]["http_status"] == 200
    assert receipt["reads"][1]["http_status"] == 429
    assert receipt["decision"] == "PAIR_IDENTITY_ACCEPTED_OHLCV_RATE_OR_QUOTA_LIMITED"
    assert receipt["claims"]["historical_panel"] is False
```

- [x] **Step 2: Run the test to verify it fails**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_birdeye_v3_external_read_runtime_receipt.py -v`

Expected: `FAIL` because the runtime receipt does not yet exist.

- [x] **Step 3: Add the minimum evidence and Catalog records**

Create the runtime and Factory Fit receipts. Register exactly the runtime
receipt, its test, and the Factory Fit receipt; then regenerate Catalog
navigation. Do not edit the raw A4 manifest or any historical receipt.

- [x] **Step 4: Run the test and Catalog validation**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests/test_task30_birdeye_v3_external_read_runtime_receipt.py -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```text
git add docs/evidence/task30/a5r1_birdeye_v3_external_read_runtime_receipt_v1.json docs/evidence/task30/a5r1_birdeye_v3_external_read_factory_fit_v1.json tests/test_task30_birdeye_v3_external_read_runtime_receipt.py catalog/assets/core.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md docs/superpowers/plans/2026-08-10-t30-a5r1-birdeye-external-read-outcome.md
git commit -m "feat: capture Birdeye external read outcome"
```
