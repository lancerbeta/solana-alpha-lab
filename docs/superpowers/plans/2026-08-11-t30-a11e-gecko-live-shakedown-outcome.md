# Gecko 15m live-shakedown outcome Implementation Plan

> **For agentic workers:** Inline execution selected for this bounded evidence patch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the observed T30-A11C GeckoTerminal shakedown result and close only the route for ≤60-second 15m freshness without another provider read.

**Architecture:** Reuse the accepted A11C runtime contract and immutable A4 receipts. Add one hash-bound runtime outcome and one Factory Fit decision, then make their route-specific non-claims and reuse-first `STOP` disposition deterministic through a focused test and Catalog registration.

**Tech Stack:** JSON evidence, Python `unittest`, PyYAML, existing Catalog generator.

## Global Constraints

- No provider/API/RPC/WSS call, credential access, raw write, scheduler, R2/R3, wallet, transaction, spend, trial, acceptance or Project Sources change.
- A4 raw remains outside Git under `local/task30_two_slot_live_shakedown/`; tracked records contain only relative paths, digests and bounded observations.
- Preserve `TYPED_GAP` as unknown, never zero, flat price, absence of trading, or a general provider conclusion.
- Close only `GECKOTERMINAL_PUBLIC_KEYLESS` for the frozen pool, `aggregate=15`, `token=base`, `currency=usd`, and first-visible offset ≤60 seconds.
- Reuse-first outcome is `STOP`; any other provider requires a future named consumer, contract and exact owner external-read authority.

---

### Task 1: Prove the intended outcome record is absent

**Files:**

- Create: `tests/test_task30_gecko_15m_live_shakedown_runtime_receipt.py`
- Create: `docs/evidence/task30/a11e_gecko_15m_live_shakedown_runtime_receipt_v1.json`
- Create: `docs/evidence/task30/a11e_gecko_15m_live_shakedown_factory_fit_v1.json`

**Interfaces:**

- Consumes: A11C contract hash, the local A4 retry run's receipt/manifest hashes, and its four `TYPED_GAP` classifications.
- Produces: route-specific runtime outcome and Factory Fit records; neither invokes nor replays transport.

- [x] **Step 1: Write the failing test**

```python
def test_live_typed_gap_closes_only_the_fast_freshness_route(self) -> None:
    receipt = load_json(RUNTIME_RECEIPT)
    self.assertEqual(receipt["requests_completed"], 4)
    self.assertEqual(receipt["terminal_state"], "SLOT_TECHNICAL_INCONCLUSIVE")
    self.assertEqual(receipt["route_disposition"], "CLOSE_CURRENT_15M_FAST_FRESHNESS_ROUTE")
    self.assertFalse(receipt["claims"]["pit_admissible"])
```

- [x] **Step 2: Run the focused test and verify it fails because the receipt is absent**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_gecko_15m_live_shakedown_runtime_receipt -v
```

- [x] **Step 3: Add the two append-only records**

Record four successful transport calls, expected interval start `1786440600`, returned interval start `1786438800` at every allowed offset, `TYPED_GAP`, `SLOT_TECHNICAL_INCONCLUSIVE`, no second slot, and every non-claim. Bind the exact A11C contract and A4 slot receipt/manifest hashes. The Factory Fit record must choose `STOP` and require a future named-provider gate rather than a retry, fallback or custom client.

- [x] **Step 4: Re-run the focused test and verify it passes**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_gecko_15m_live_shakedown_runtime_receipt -v
```

### Task 2: Register the durable decision without expanding the platform

**Files:**

- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify (generated): `catalog/generated/asset_edges.json`
- Modify (generated): `docs/PROJECT_MAP.md`

**Interfaces:**

- Consumes: the two evidence records and focused test from Task 1.
- Produces: three discoverable Catalog IDs for the runtime record, test, and Factory Fit decision.

- [x] **Step 1: Add exactly three Catalog records**

```text
EVIDENCE-T30-A11E-GECKO-LIVE-SHAKEDOWN-RUNTIME-001
TEST-T30-A11E-GECKO-LIVE-SHAKEDOWN-RUNTIME-001
EVIDENCE-T30-A11E-GECKO-LIVE-SHAKEDOWN-FACTORY-FIT-001
```

All records have `truth_owner: TASK-30`, `contains_secrets: false`, `contains_raw_data: false`, a `TASK-30` consumer, and explicit relations to the A11C runtime evidence they consume.

- [x] **Step 2: Regenerate and validate Catalog views**

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
```

### Task 3: Validate the exact candidate and deliver it

**Files:**

- Modify: `docs/superpowers/plans/2026-08-11-t30-a11e-gecko-live-shakedown-outcome.md`

- [x] **Step 1: Run direct consumers and diff checks**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime tests.test_task30_gecko_15m_live_shakedown_runtime_receipt -v
git diff --check
```

- [ ] **Step 2: Run one tracked-only delivery preflight for the committed candidate**

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

- [ ] **Step 3: Commit, push, create PR, and use exact-head CI as the remote full-gate read-back**

```text
git commit -m "feat: record Gecko 15m shakedown outcome"
git push --set-upstream origin task30/a11e-gecko-live-outcome
```

## Plan self-review

- Spec coverage: Task 1 preserves the exact observed negative result and non-claims; Task 2 keeps it discoverable; Task 3 proves the delivered bytes.
- Scope: no new source, client, collector, scheduler, schema, provider comparison, or Project Source artifact.
- Placeholder scan: no deferred implementation markers; every file and validation command is named.
- Type consistency: the test reads static evidence only, so no new production interface is introduced.
