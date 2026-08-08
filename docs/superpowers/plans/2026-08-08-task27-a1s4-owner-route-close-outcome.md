# TASK-27 A1S4 Owner Route-Close Outcome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind the owner's accepted closure of the failed Solana Tracker route into a deterministic, offline TASK-27 outcome proposal without granting another provider read or prematurely closing the task.

**Architecture:** A static policy packet binds the A1S3 policy and acceptance receipt by path and SHA-256. A JSON Schema constrains the packet, while a synthetic golden fixture and a `unittest` semantic checker reject authority, market-wide, missingness, and completion promotion. The acceptance receipt binds only the newly created static artifacts and records `state_change: NONE`.

**Tech Stack:** Python 3.13.14, standard-library `unittest`, PyYAML, JSON Schema Draft 2020-12; no new dependencies, network calls, or provider clients.

## Global Constraints

- Exact owner decision: `ROUTE_CLOSE_ACCEPTED; NO_NEW_PROVIDER_READ`.
- Provider/API/RPC/WSS calls, credentials, raw retention, R2/R3 reads, wallet/signer/transaction actions, spend, and UI activation remain zero or false.
- A1S4 closes only the named current route. It must not claim public-history, all providers, alpha, execution, PnL, NetReturn, or cashflow are negative or impossible.
- `MISSING_UNKNOWN` never becomes zero, flat, continuous, settled, or PIT-admissible.
- A1S4 does not claim TASK-27 completion, change a Project Source role, edit generated Catalog files, or rewrite A1S3.
- Managed write set: the six A1S4 artifacts named in the approved design plus this plan; no other tracked file changes.

---

### Task 1: Deterministic owner-route-close policy packet

**Files:**

- Create: `docs/contracts/task27_owner_route_close_and_task_outcome_contract_v1.md`
- Create: `configs/task27_owner_route_close_and_task_outcome_v1.yaml`
- Create: `catalog/schemas/task27_owner_route_close_and_task_outcome.schema.json`
- Create: `tests/fixtures/task27/owner_route_close_and_task_outcome_v1.json`
- Create: `tests/test_task27_owner_route_close_and_task_outcome.py`
- Create: `docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json`
- Test: `tests/test_task27_owner_route_close_and_task_outcome.py`

**Interfaces:**

- Consumes: `configs/task27_gap_classification_and_owner_route_decision_v1.yaml` and `docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json`, each by repository-relative path and computed SHA-256.
- Produces: a synthetic packet whose `decision` has `current_route_disposition`, `owner_route_close`, `new_provider_read_authority`, `task27_outcome_proposal`, and `task27_status`; whose `authority` has all external counters at zero; and whose `claims` keeps every research/execution/economic claim false.

- [x] **Step 1: Write the failing contract test.**

Create `tests/test_task27_owner_route_close_and_task_outcome.py`. Mirror A1S3's SHA-256, JSON/YAML, and JSON-pointer helpers. Define this exact adversarial mapping:

```python
EXPECTED_ADVERSARIAL_ERRORS = {
    "binding-drift": "SOURCE_BINDING_DRIFT",
    "provider-read": "UNAUTHORIZED_PROVIDER_READ",
    "market-wide-close": "MARKET_WIDE_CONCLUSION_FORBIDDEN",
    "task-done": "PREMATURE_TASK27_DONE_FORBIDDEN",
    "missing-to-zero": "MISSING_TO_ZERO_FORBIDDEN",
    "claim-promotion": "RESEARCH_EXECUTION_ECONOMIC_PROMOTION_FORBIDDEN",
}
```

The golden-packet assertion must compare both A1S3 bindings to computed hashes, require both exact owner-decision tokens, require `CLOSE_WITH_LIMITED_NEGATIVE_RESULT`, and assert every forbidden authority/claim field is false or zero.

- [x] **Step 2: Run the new test before artifacts exist.**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest discover -s tests -p 'test_task27_owner_route_close_and_task_outcome.py'
```

Expected: failure reporting missing required A1S4 artifacts. Do not add a dependency, skip, or fallback.

- [x] **Step 3: Create the six static artifacts.**

The contract must state that A1S4 records a route-specific owner decision, not TASK-27 acceptance. The YAML policy and golden fixture must contain these exact values:

```yaml
owner_decision:
  route_close: ROUTE_CLOSE_ACCEPTED
  new_provider_read: NO_NEW_PROVIDER_READ
decision:
  current_route_disposition: CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE
  owner_route_close: ACCEPTED
  new_provider_read_authority: false
  task27_outcome_proposal: CLOSE_WITH_LIMITED_NEGATIVE_RESULT
  task27_status: IN_PROGRESS_PENDING_TERMINAL_RECONCILIATION
authority:
  provider_api_rpc_wss_calls: 0
  credential_use: false
  raw_provider_responses_retained: 0
  r2_value_reads: 0
  r3_value_or_path_reads: 0
  wallet_signer_transaction_actions: 0
  cash_spend_usd_cents: 0
claims:
  pit_admissible: false
  public_history_globally_infeasible: false
  alpha: false
  execution: false
  pnl: false
  netreturn: false
  cashflow: false
```

The Draft 2020-12 schema must use `additionalProperties: false`, require every field above, require a null provider selection, and constrain the constants. The fixture must include one valid packet plus one pointer mutation for every named adversarial error. The acceptance receipt binds final SHA-256 values for contract, config, schema, and fixture; binds the exact A1S3 policy and acceptance receipt; records six rejected adversarial cases; and declares `state_change: NONE`, `task27_acceptance: false`, and `project_sources_disposition.kind: NO_CHANGE`.

- [x] **Step 4: Run focused validation.**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest discover -s tests -p 'test_task27_owner_route_close_and_task_outcome.py'
git diff --check
```

Expected: all focused tests pass; no whitespace error; receipt hashes match final bytes.

- [x] **Step 5: Run the complete TASK-27 offline suite.**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest discover -s tests -p 'test_task27_*.py'
```

Expected: all TASK-27 contract, authority, runtime-receipt, A1S3, and A1S4 tests pass with no provider call.

- [x] **Step 6: Commit the bounded atom.**

Stage only the six A1S4 artifacts and this plan, then commit:

```text
feat: bind TASK-27 owner route-close outcome
```

Expected: repository pre-commit passes and no tracked file outside the managed write set changed.

## Plan Self-Review

- **Spec coverage:** Task 1 binds both decision tokens and A1S3 hashes; preserves route scope and missingness; rejects external authority, causal/market-wide/economic promotion, and premature task completion.
- **Placeholder scan:** no deferred marker, unnamed test, or undefined function remains.
- **Type consistency:** packets are JSON/YAML mappings; SHA-256 values are lower-case 64-character strings; fixture and test use identical adversarial identifiers.
- **Scope decision:** one task is correct because policy, schema, fixture, test, and receipt have one consumer and one acceptance boundary. Catalog transaction, Sources candidate, and TASK-27 closure remain later atoms.
