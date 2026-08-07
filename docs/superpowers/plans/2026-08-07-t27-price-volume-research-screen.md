# T27-A0-A2 Historical Price/Volume Research-Screen Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic offline contract and synthetic test matrix for a PIT-safe 15-minute pool price/volume research screen with a one-hour forward-close label.

**Architecture:** The package is declarative: Markdown contract, YAML policy, Draft 2020-12 JSON Schema, synthetic fixture, Python test module, and acceptance receipt. The test module interprets tracked synthetic records only; it has no provider, database, or service dependency.

**Tech Stack:** Python 3.13, `unittest`, PyYAML, `jsonschema` Draft 2020-12, JSON, YAML, Markdown.

## Global Constraints

- Offline only: `provider_api_rpc_wss_calls=0`, no credentials, wallet, signer, transaction, cash, R3, Catalog, Sources, or dependency changes.
- Unit: Solana `pool_interval`, not a token-level bar; interval length is exactly 900 seconds.
- Primary label: one-hour forward close return from a 15-minute entry-bar close; incomplete successor window becomes `UNKNOWN`.
- Missingness never becomes zero volume, flat price, carried-forward OHLC, fill, PnL, NetReturn, or alpha.
- No raw provider response enters Git. Text is UTF-8, LF-only, trailing-newline, BOM-free.

---

### Task 1: Create the failing contract-package test

**Files:**
- Create: `tests/test_task27_price_volume_research_screen_contract.py`
- Test: `tests/test_task27_price_volume_research_screen_contract.py`

**Interfaces:**
- Consumes: six future artifact paths under `docs/`, `configs/`, `catalog/`, and `tests/fixtures/`.
- Produces: `semantic_errors(panel: dict[str, Any]) -> set[str]`, used only by this test module.

- [ ] **Step 1: Write the existence assertion**

```python
def test_all_required_artifacts_exist(self) -> None:
    for path in REQUIRED_PATHS:
        with self.subTest(path=path):
            self.assertTrue(path.exists(), path)
```

This catches an incomplete offline package.

- [ ] **Step 2: Verify RED**

Run `uv run --locked --managed-python python -B -m unittest tests.test_task27_price_volume_research_screen_contract.Task27PriceVolumeResearchScreenContractTests.test_all_required_artifacts_exist`.

Expected: assertion failure naming a missing Task-27 artifact, not a missing-import error.

- [ ] **Step 3: Add the test-only semantic interpreter**

```python
def semantic_errors(panel: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    if panel["data_state"] == "MISSING_UNKNOWN" and panel["volume"] == "0":
        errors.add("MISSING_IS_NOT_ZERO")
    if panel["data_state"] != "OBSERVED" and panel["close"] is not None:
        errors.add("UNOBSERVED_CLOSE_FORBIDDEN")
    return errors
```

Extend this function with literal checks for `CARRIED_FORWARD_PRICE_FORBIDDEN`, `NONCONTIGUOUS_FORWARD_WINDOW`, `PIT_AVAILABILITY_UNKNOWN`, `POOL_TOKEN_IDENTITY_MISMATCH`, `PRICE_LABEL_IS_NOT_EXECUTION`, and `INCOMPLETE_FORWARD_WINDOW_UNKNOWN`.

- [ ] **Step 4: Re-run RED**

Repeat the Step 2 command. It must still fail only because declarative artifacts do not yet exist; do not create any provider adapter or fetch data.

### Task 2: Build the declarative offline contract package

**Files:**
- Create: `docs/contracts/task27_price_volume_research_screen_contract_v1.md`
- Create: `configs/task27_price_volume_research_screen_contract_v1.yaml`
- Create: `catalog/schemas/task27_price_volume_research_screen.schema.json`
- Create: `tests/fixtures/task27/price_volume_research_screen_v1.json`
- Modify: `tests/test_task27_price_volume_research_screen_contract.py`

**Interfaces:**
- Consumes: test-only semantic interpreter and literal synthetic cases.
- Produces: a Draft 2020-12-valid fixture with valid panels, a valid one-hour label, and named adversarial cases.

- [ ] **Step 1: Write contract and frozen policy**

```yaml
interval_seconds: 900
primary_label: FORWARD_CLOSE_RETURN_1H
successor_intervals_required: 4
missing_result: UNKNOWN
provider_api_rpc_wss_calls: 0
catalog_or_registry_mutation: false
```

Require `network`, `pool_id`, token identities, `dex_id`, `interval_start_at`, OHLCV, data state, and provenance timestamps for every pool interval.

- [ ] **Step 2: Write schema and synthetic fixture**

The fixture contains five contiguous observed 15-minute bars. The entry and terminal closes yield hand-derived `0.050000`. It contains one adversarial case for each error: `MISSING_IS_NOT_ZERO`, `CARRIED_FORWARD_PRICE_FORBIDDEN`, `NONCONTIGUOUS_FORWARD_WINDOW`, `PIT_AVAILABILITY_UNKNOWN`, `POOL_TOKEN_IDENTITY_MISMATCH`, `PRICE_LABEL_IS_NOT_EXECUTION`, and `INCOMPLETE_FORWARD_WINDOW_UNKNOWN`.

- [ ] **Step 3: Complete behavior assertions**

```python
def test_complete_observed_window_yields_hand_derived_label(self) -> None:
    panel = self.fixture["valid_panels"][0]
    self.assertEqual(panel["label"]["state"], "KNOWN")
    self.assertEqual(panel["label"]["value_decimal"], "0.050000")
    self.assertEqual(semantic_errors(panel), set())
```

Use one `subTest` per adversarial case. Assert real JSON/YAML/Schema behavior; never use mocks or prose-grep assertions.

- [ ] **Step 4: Verify GREEN**

Run `uv run --locked --managed-python python -B -m unittest tests.test_task27_price_volume_research_screen_contract`.

Expected: all Task-27 synthetic tests pass with zero network calls.

### Task 3: Bind acceptance evidence and validate delivery

**Files:**
- Create: `docs/evidence/task27/a0a2_price_volume_research_screen_contract_acceptance_v1.json`
- Modify: `tests/test_task27_price_volume_research_screen_contract.py`

**Interfaces:**
- Consumes: SHA-256 values and test counts of the five completed contract artifacts.
- Produces: an offline receipt binding the exact six-file write set, semantic acceptance, and zero-side-effect counters.

- [ ] **Step 1: Add the failing receipt assertion**

```python
def test_receipt_binds_current_artifacts_and_zero_external_actions(self) -> None:
    self.assertEqual(self.receipt["measured_boundary"]["provider_api_rpc_wss_calls"], 0)
    self.assertEqual(self.receipt["measured_boundary"]["wallet_signer_transaction_actions"], 0)
    self.assertEqual(self.receipt["state_change"], "NONE")
```

Run the single test. Expected: failure because the receipt is absent.

- [ ] **Step 2: Write the receipt**

Bind the exact six-file managed write set, current SHA-256 values, targeted test count, seven rejected adversarial cases, and zero external-action fields. It makes no claim about data collection, provider coverage, alpha, PnL, NetReturn, or canonical acceptance.

- [ ] **Step 3: Validate target behavior and diff**

Run `uv run --locked --managed-python python -B -m unittest tests.test_task27_price_volume_research_screen_contract`, then `git diff --check` and `git diff --name-only`.

Expected: tests PASS and exactly the six implementation files are present, excluding already-committed design and plan documents.

- [ ] **Step 4: Commit and run tracked-only delivery preflight**

After the implementation commit is clean, run `uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`.

Expected: PASS in an isolated tracked-only checkout; do not introduce a skip for absent raw data.
