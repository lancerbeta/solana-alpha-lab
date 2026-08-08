# T27-A1S3 Gap Classification and Owner Route Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the A1S2 incomplete-panel result deterministic, non-causal, and
safe to use for one owner decision about the current history route.

**Architecture:** A static Markdown contract, YAML policy, JSON Schema, and
synthetic golden fixture describe one decision packet.  One Python unittest
module binds that packet to tracked A1/A1S2 evidence and rejects every route
that turns missing data into a conclusion or external authority.

**Tech Stack:** Python 3.13 `unittest`, PyYAML, jsonschema, JSON, YAML, and
Markdown; no new dependencies or runtime/provider component.

## Global Constraints

- Atom: `T27-A1S3_OFFLINE_GAP_CLASSIFICATION_AND_OWNER_ROUTE_DECISION_PACKET_V1`.
- Read only tracked A1/A1S2 receipts and Stage B config.  Local raw JSON is
  neither read nor copied and remains outside Git.
- Provider/API/RPC/WSS, credentials, R2/R3, wallet, signer, transaction, cash,
  and TASK-27 acceptance are exactly zero.
- The only route conclusion is
  `CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE` for the
  frozen 96-bar requirement.
- No explanation is `PROVEN_CAUSE`; no provider is selected or authorized.
- `MISSING_UNKNOWN` is not zero volume, a flat bar, a no-trade fact, or a
  continuous/PIT path.
- No Catalog manifest/generated update or Project Source release is in scope.

---

### Task 1: Build the static decision contract with test-first validation

**Files:**
- Create: `docs/contracts/task27_gap_classification_and_owner_route_decision_contract_v1.md`
- Create: `configs/task27_gap_classification_and_owner_route_decision_v1.yaml`
- Create: `catalog/schemas/task27_gap_classification_and_owner_route_decision.schema.json`
- Create: `tests/fixtures/task27/gap_classification_and_owner_route_decision_v1.json`
- Create: `tests/test_task27_gap_classification_and_owner_route_decision.py`

**Interfaces:**
- Consumes: the A1S2 receipt, A1 receipt, and Stage B config by tracked path
  and SHA-256.
- Produces: one schema-valid `valid_packets[0]` fixture and
  `semantic_errors(packet: dict[str, Any]) -> set[str]`.

- [ ] **Step 1: Write the failing validator test**

  Create the test module with these constants and no artifact fallback:

  ```python
  ROOT = Path(__file__).resolve().parents[1]
  STAGE_B_RECEIPT = ROOT / "docs/evidence/task27/a1s2_stage_b_pool_history_runtime_receipt_v1.json"
  CONFIG = ROOT / "configs/task27_gap_classification_and_owner_route_decision_v1.yaml"
  SCHEMA = ROOT / "catalog/schemas/task27_gap_classification_and_owner_route_decision.schema.json"
  FIXTURE = ROOT / "tests/fixtures/task27/gap_classification_and_owner_route_decision_v1.json"

  EXPECTED_OBSERVATION = {
      "expected_natural_bars": 96,
      "observed_bars": 33,
      "missing_natural_bars": 63,
      "returned_zero_volume_bars": 18,
      "internal_gap_regions": 21,
      "largest_gap_seconds": 8100,
  }
  ```

  Define one positive test for `valid_packets[0]` and six mutation cases that
  must return exactly these codes:

  ```python
  {
      "missing-to-zero": "MISSING_TO_ZERO_FORBIDDEN",
      "trade-only-cause": "TRADE_ONLY_CAUSAL_OVERCLAIM",
      "proven-cause": "UNPROVEN_CAUSAL_ATTRIBUTION",
      "pit-promotion": "PIT_PROMOTION_FORBIDDEN",
      "automatic-provider": "EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN",
      "task-close-promotion": "TASK27_CLOSURE_PROMOTION_FORBIDDEN",
  }
  ```

- [ ] **Step 2: Run the test before contract artifacts exist**

  Run:

  ```powershell
  uv run --locked --managed-python python -B -m unittest tests.test_task27_gap_classification_and_owner_route_decision
  ```

  Expected result: `FAIL` because the policy, schema, and fixture do not yet
  exist.  Do not add a skip or make an external read.

- [ ] **Step 3: Write the contract, policy, schema, fixture, and pure checker**

  The Markdown contract defines four layers: observed facts, explanation
  classifications, current-route disposition, and future owner boundary.  It
  must state that `PROVEN_CAUSE` is invalid and that closing this endpoint does
  not close TASK-27 or all public-history routes.

  The YAML policy contains the exact A1S2 evidence facts and this decision
  surface:

  ```yaml
  current_route_disposition: CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE
  future_boundary: SEPARATE_OWNER_EXTERNAL_READ_DECISION_REQUIRED
  task27_status: IN_PROGRESS_NO_ACCEPTANCE
  provider_selected: null
  provider_read_authority: false
  external_actions: 0
  raw_provider_responses_retained: 0
  ```

  Its claims are all false for PIT/alpha/execution/PnL/NetReturn/cashflow, with
  `state_change: NONE` and `project_sources_disposition: NO_CHANGE`.

  The JSON Schema requires `source_bindings`, `observation`, `explanations`,
  `decision`, and `claims`, disallows additional top-level fields, and pins the
  route disposition, future boundary, task status, and false claims with
  `const`.

  The valid fixture has exactly four explanations:

  ```json
  [
    {"id": "trade_only_endpoint_emission", "classification": "NARROW_FORM_FALSIFIED"},
    {"id": "low_activity_correlated_missingness", "classification": "POSSIBLE_NOT_PROVEN"},
    {"id": "provider_aggregation_or_coverage", "classification": "POSSIBLE_NOT_PROVEN"},
    {"id": "market_label_difference", "classification": "NOT_TESTED"}
  ]
  ```

  Implement the checker with these exact control branches; also validate JSON
  Schema, tracked binding hashes, and forbidden secret markers:

  ```python
  def semantic_errors(packet: dict[str, Any]) -> set[str]:
      errors: set[str] = set()
      observation = packet["observation"]
      explanations = {item["id"]: item for item in packet["explanations"]}
      decision = packet["decision"]
      claims = packet["claims"]

      if observation["missing_data_state"] != "MISSING_UNKNOWN" or observation["missing_as_zero"]:
          errors.add("MISSING_TO_ZERO_FORBIDDEN")
      if explanations["trade_only_endpoint_emission"]["classification"] != "NARROW_FORM_FALSIFIED":
          errors.add("TRADE_ONLY_CAUSAL_OVERCLAIM")
      if any(item["classification"] == "PROVEN_CAUSE" for item in explanations.values()):
          errors.add("UNPROVEN_CAUSAL_ATTRIBUTION")
      if claims["pit_admissible"] or any(claims[name] for name in ("alpha", "execution", "pnl", "netreturn", "cashflow")):
          errors.add("PIT_PROMOTION_FORBIDDEN")
      if decision["provider_selected"] is not None or decision["provider_read_authority"]:
          errors.add("EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN")
      if decision["task27_status"] != "IN_PROGRESS_NO_ACCEPTANCE":
          errors.add("TASK27_CLOSURE_PROMOTION_FORBIDDEN")
      return errors
  ```

  Each adversarial fixture mutation changes one JSON-pointer target only and
  maps to one of the six declared errors.

- [ ] **Step 4: Run the target test and inspect scope**

  Run the command from Step 2.  Expected result: `PASS`, with all six
  adversarial rejections observed.  Then run:

  ```powershell
  git diff --check
  git status --short
  ```

  Expected result: only the five Task 1 paths above are changed.

- [ ] **Step 5: Commit the self-contained contract**

  ```powershell
  git add docs/contracts/task27_gap_classification_and_owner_route_decision_contract_v1.md configs/task27_gap_classification_and_owner_route_decision_v1.yaml catalog/schemas/task27_gap_classification_and_owner_route_decision.schema.json tests/fixtures/task27/gap_classification_and_owner_route_decision_v1.json tests/test_task27_gap_classification_and_owner_route_decision.py
  git commit -m "feat: define Task27 gap route decision contract"
  ```

### Task 2: Bind acceptance evidence and run delivery gates

**Files:**
- Create: `docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json`
- Modify: `tests/test_task27_gap_classification_and_owner_route_decision.py`

**Interfaces:**
- Consumes: the five Task 1 artifacts and A1/A1S2 tracked evidence.
- Produces: a machine-readable offline acceptance receipt.  It creates no
  Catalog manifest or Project Source transaction.

- [ ] **Step 1: Write the acceptance receipt**

  Bind the Task 1 contract/config/schema/fixture and A1S2 receipt by
  path/SHA-256.  Record one valid fixture and the six adversarial rejections.
  Its decision must be exactly:

  ```json
  {
    "current_route_disposition": "CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE",
    "future_boundary": "SEPARATE_OWNER_EXTERNAL_READ_DECISION_REQUIRED",
    "state_change": "NONE",
    "task27_acceptance": false,
    "provider_api_rpc_wss_calls": 0,
    "credential_use": false,
    "raw_provider_responses_retained": 0
  }
  ```

  `factory_fit` states only that the result preserves a cheap falsifier and
  prevents accidental data-source/procurement choice; it must not claim a cause
  of missing bars.

- [ ] **Step 2: Extend the test to bind the receipt**

  Add `ACCEPTANCE` to the test module.  Recompute every receipt path/SHA-256,
  assert the six rejection codes, all zero external/credential/raw/wallet/
  transaction/spend counts, `task27_acceptance is False`, and
  `state_change == "NONE"`.

- [ ] **Step 3: Run targeted and Task-27 validation**

  Run:

  ```powershell
  uv run --locked --managed-python python -B -m unittest tests.test_task27_gap_classification_and_owner_route_decision
  uv run --locked --managed-python python -B -m unittest discover -s tests -p 'test_task27*.py'
  ```

  Expected result: all tests pass.  A prior Task-27 failure blocks delivery;
  do not reduce coverage or skip it.

- [ ] **Step 4: Run the tracked-only delivery preflight**

  Run:

  ```powershell
  uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
  ```

  Expected result: PASS.  Verify the staged set contains neither an ignored A1S2
  raw path nor a provider key nor `.worktrees` content.

- [ ] **Step 5: Final review and commit**

  Run `git diff --check`, inspect the exact changed-file inventory, then:

  ```powershell
  git add docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json tests/test_task27_gap_classification_and_owner_route_decision.py
  git commit -m "docs: record Task27 gap route decision"
  ```

  Request repository review/PR under standing autonomy.  Passing PR and CI are
  implementation evidence only; they do not accept or close TASK-27.

## Self-review

- **Spec coverage:** Task 1 implements all packet semantics and false-positive
  guards; Task 2 binds durable evidence and delivery.  Every design requirement
  has a task.
- **Placeholder scan:** no TBD/TODO, unspecified validation, or “similar to”
  instruction remains.  Future external action is explicitly absent.
- **Type consistency:** the six error strings, explanation IDs, and decision
  literals are defined once and used consistently in policy, schema, fixture,
  test, and receipt.

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-08-08-t27-a1s3-gap-classification-and-route-decision.md`.

1. **Subagent-Driven** — fresh implementation worker per task and a review
   between tasks.
2. **Inline Execution** — execute the two tightly coupled tasks in this
   session with a compact delivery checkpoint.

Inline Execution is recommended for this small, offline packet.
