# TASK-30 A10 Gecko interval-semantics discriminator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely run exactly two keyless public GeckoTerminal reads and retain a fail-closed technical decision about 15-minute OHLCV timestamp semantics.

**Architecture:** A pure Python evaluator validates a frozen two-request plan and compares direct trade USD prices with the two possible OHLCV label mappings.  A small stdlib-only runner is the sole network boundary; it requires `--execute`, rejects drift, writes raw bytes only under ignored `local/`, and emits a sanitized local receipt.  Tracked contract, runtime evidence, Catalog and generated navigation document the limited result.

**Tech Stack:** Python 3.12 stdlib, PyYAML, jsonschema, unittest, uv, Git-tracked YAML/JSON/Markdown.

## Global Constraints

- Pool is exactly `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` on `solana`.
- There are exactly two keyless HTTPS `GET` requests; no redirect, retry, fallback, scheduler, credential, R2/R3, wallet, signer, transaction, spend, trial, or TASK-30 acceptance action.
- Raw response bytes remain outside Git under ignored `local/`; missing or malformed evidence is never inferred as zero, no-trade, success, or settled.
- A selected label needs two usable trades in two slots, zero contradictions for that model, and at least one contradiction for the other model.
- A10 has `FULL_REVIEW`, `NO_CHANGE` Project Sources disposition, and cannot promote a panel or H07/H01 evidence.

---

### Task 1: Contract-first evaluator

**Files:**
- Create: `docs/tasks/TASK-30-gecko-interval-semantics-discriminator.md`
- Create: `docs/contracts/task30_gecko_interval_semantics_contract_v1.md`
- Create: `configs/task30_gecko_interval_semantics_v1.yaml`
- Create: `catalog/schemas/task30_gecko_interval_semantics.schema.json`
- Create: `tests/fixtures/task30/gecko_interval_semantics_v1.json`
- Create: `tests/test_task30_gecko_interval_semantics.py`
- Create: `src/solana_alpha_lab/task30_gecko_interval_semantics.py`

**Interfaces:**
- Consumes: frozen config and decoded OHLCV/trades JSON mappings.
- Produces: `build_request_plan(config, before_timestamp)` and `evaluate_interval_semantics(config, ohlcv_payload, trades_payload)`.

- [ ] **Step 1: Write failing tests**

```python
result = evaluate_interval_semantics(config, start_labelled_ohlcv, trades)
assert result["decision"] == "START_LABELED"
assert result["claims"]["continuous_panel"] is False
```

Add equivalent end-labelled, equal-plausibility, malformed-input, and
authority/allowlist tests.

- [ ] **Step 2: Run the tests to verify RED**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_gecko_interval_semantics.py`

Expected: import failure because `task30_gecko_interval_semantics` does not exist.

- [ ] **Step 3: Implement the minimal evaluator**

Implement strict config/request validation, ISO trade time parsing, base-token
USD price selection, two label mappings, contradiction counts and only the
three terminal decision families (`START_LABELED`, `END_LABELED`,
`INCONCLUSIVE_*`).

- [ ] **Step 4: Run the focused tests to verify GREEN**

Run: `uv run --locked --managed-python python -B -m unittest tests/test_task30_gecko_interval_semantics.py`

Expected: PASS with no provider call.

### Task 2: One-shot bounded transport

**Files:**
- Create: `scripts/run_task30_gecko_interval_semantics.py`
- Modify: `tests/test_task30_gecko_interval_semantics.py`

**Interfaces:**
- Consumes: `build_request_plan`, config, and `--execute`.
- Produces: printed zero-I/O dry-run plan or one ignored raw run directory with
  two exact response files, a raw manifest, and sanitized local receipt.

- [ ] **Step 1: Write failing runner tests**

```python
plan = build_request_plan(config, before_timestamp=1_800)
assert len(plan) == 2
assert all(item["method"] == "GET" for item in plan)
assert plan[0]["host"] == "api.geckoterminal.com"
```

Assert a third request, redirect, changed host/path, and execution without the
explicit flag are rejected before I/O.

- [ ] **Step 2: Run the tests to verify RED**

Run the focused unittest command and confirm the new runner-plan expectation
fails for a missing implementation.

- [ ] **Step 3: Implement the runner**

Use a no-redirect stdlib opener, increment the cap before each attempted GET,
capture HTTP errors once, never retry, preserve raw bytes with exclusive file
creation, and stop after exactly the bounded plan.  `--dry-run` prints the two
sanitized endpoints and creates nothing.

- [ ] **Step 4: Verify GREEN and zero-I/O dry run**

Run focused unittest and:

```text
uv run --locked --managed-python python -B scripts/run_task30_gecko_interval_semantics.py --dry-run
```

Expected: two planned GETs, `network_calls=0`, and no `local/task30_gecko_interval_semantics` directory.

### Task 3: Exact live evidence and delivery controls

**Files:**
- Create after the one execution: `docs/evidence/task30/a10_gecko_interval_semantics_runtime_receipt_v1.json`
- Create after review: `docs/evidence/task30/a10_gecko_interval_semantics_factory_fit_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml` only if validation requires it
- Modify generated only through: `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md`
- Test: `tests/test_task30_gecko_interval_semantics.py`

**Interfaces:**
- Consumes: immutable local raw manifest and sanitized result.
- Produces: traceable but non-sensitive external-read receipt and FULL_REVIEW.

- [ ] **Step 1: Review the exact dry-run plan against the owner envelope**

Confirm the host, pool, paths, query keys, method, two-call limit, raw root,
and exclusions before live execution.

- [ ] **Step 2: Run exactly once with `--execute`**

Run the runner once.  Do not rerun it for any HTTP, transport, payload, or
inconclusive result.  Preserve the local manifest and raw files.

- [ ] **Step 3: Write bounded tracked receipts and Catalog records**

Bind receipt fields to the config/contract hashes and the local manifest hash;
record the real decision, `STATE_CHANGE=NONE`, Full Factory Fit, `NO_CHANGE`
Sources disposition, and every non-claim.  Generate navigation; never edit it
by hand.

- [ ] **Step 4: Run targeted and delivery validation**

Run the focused unit tests, Catalog/navigation checks, then one
`--tracked-only-delivery` gate for the exact committed candidate.  Publish the
exact branch/PR only if all machine gates pass; CI is the remote read-back.
