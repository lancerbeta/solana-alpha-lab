# TASK-30 route hold and forward price capture decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic, offline decision that holds the rate-limited Birdeye historical route and defines the exact boundary for one future 24-hour, single-pool, 15-minute observation pilot.

**Architecture:** A small YAML policy is the source of truth. A JSON Schema protects its shape and a pure-Python evaluator accepts only the sole bounded decision. A synthetic fixture, receipt and Catalog records make the decision discoverable without contacting a provider or constructing a scheduler.

**Tech Stack:** Python 3.13, PyYAML, jsonschema, unittest, repository Catalog generator and locked `uv` environment.

## Global Constraints

- Atom ID is `T30-A6_BIRDEYE_ROUTE_HOLD_AND_FORWARD_PRICE_CAPTURE_DECISION_V1`.
- The only candidate pool is `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.
- The candidate horizon is exactly 86,400 seconds with 900-second slots and at most 96 observations.
- Provider/API/RPC/WSS calls, credentials, raw writes, scheduler activation, dependencies, R2/R3, wallet, signer, transaction, cash spend, TASK-30 trial/acceptance and Project Sources changes remain zero or false.
- Birdeye is `HOLD_NO_AUTORETRY`; HTTP 429 is never interpreted as no history, provider incompatibility, or a successful panel.
- A source candle label remains `RETAIN_AS_RECEIVED_NO_START_END_PROMOTION`; a missing slot remains a typed gap.
- Adopt existing storage, idempotency, cap, gap and recovery concepts; do not adopt Jupiter quote values, a TASK-21 technical probe, a provider endpoint, or the 30–45-day execution-capacity run plan.
- No generic collector, provider adapter, dashboard, background service or source release is created.

---

## File map

| File | Responsibility |
| --- | --- |
| `docs/contracts/task30_birdeye_route_hold_forward_capture_decision_contract_v1.md` | Human-readable scope, non-claims, route state and future external gate. |
| `configs/task30_birdeye_route_hold_forward_capture_decision_v1.yaml` | Frozen machine-readable policy. |
| `catalog/schemas/task30_birdeye_route_hold_forward_capture_decision.schema.json` | Closed JSON Schema for the policy. |
| `tests/fixtures/task30/birdeye_route_hold_forward_capture_decision_v1.json` | Sole expected evaluator result. |
| `src/solana_alpha_lab/task30_birdeye_route_hold_forward_capture_decision.py` | Pure fail-closed policy evaluator. |
| `tests/test_task30_birdeye_route_hold_forward_capture_decision.py` | Schema, evaluator, adversarial, evidence and Catalog checks. |
| `docs/evidence/task30/a6_birdeye_route_hold_forward_capture_decision_acceptance_v1.json` | Hash-bound offline acceptance and Factory Fit receipt. |
| `catalog/assets/core.yaml` | Stable records for all A6 outputs. |
| `catalog/assets/lifecycle.yaml` | Exact hashes and record versions for regenerated Catalog navigation views. |
| `catalog/catalog_manifest.yaml` | Updated counts and registered A6 schema. |
| `catalog/generated/asset_edges.json` and `docs/PROJECT_MAP.md` | Generated navigation projections. |

### Task 1: Freeze the offline policy surface

**Files:**
- Create: `docs/contracts/task30_birdeye_route_hold_forward_capture_decision_contract_v1.md`
- Create: `configs/task30_birdeye_route_hold_forward_capture_decision_v1.yaml`
- Create: `catalog/schemas/task30_birdeye_route_hold_forward_capture_decision.schema.json`
- Create: `tests/fixtures/task30/birdeye_route_hold_forward_capture_decision_v1.json`
- Create: `tests/test_task30_birdeye_route_hold_forward_capture_decision.py`

**Consumes:** A5R1 runtime receipt and Factory Fit evidence, T20 collection specification, and T21 sustained-collection safety controls.

**Produces:** One closed policy that a pure evaluator can load and reject if any future-external authority, pool expansion or cadence rewrite appears.

- [ ] **Step 1: Write the failing policy-contract test**

```python
def test_evaluates_only_one_offline_hold_and_forward_capture_decision(self) -> None:
    policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    self.assertFalse(list(Draft202012Validator(schema).iter_errors(policy)))
    self.assertEqual(
        evaluate_birdeye_route_hold_forward_capture(policy),
        fixture["expected_result"],
    )
```

- [ ] **Step 2: Run the new test and verify the expected failure**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_birdeye_route_hold_forward_capture_decision.Task30BirdeyeRouteHoldForwardCaptureDecisionTests.test_evaluates_only_one_offline_hold_and_forward_capture_decision -v
```

Expected: `ModuleNotFoundError` because the evaluator does not yet exist.

- [ ] **Step 3: Write the contract, policy, schema and expected fixture**

The YAML policy must contain the following exact top-level shape:

```yaml
schema: smial.task30.birdeye-route-hold-forward-capture.policy
schema_version: '1.0'
task_id: TASK-30
atom_id: T30-A6_BIRDEYE_ROUTE_HOLD_AND_FORWARD_PRICE_CAPTURE_DECISION_V1
contract_id: TASK30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-DECISION-V1
consumer: FUTURE_TASK30_FORWARD_PRICE_CAPTURE_ENTRY_GATE
evidence_as_of: '2026-08-10'
birdeye_route:
  state: HOLD_NO_AUTORETRY
  observed_ohlcv_http_status: 429
  historical_panel_claim: false
  provider_or_pair_unsupported_claim: false
  reopen_requires:
    - DOCUMENTED_QUOTA_OR_ACCESS_RECOVERY
    - NEW_EXACT_OWNER_EXTERNAL_AUTHORIZATION
forward_capture_candidate:
  pool_address: URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
  slot_seconds: 900
  initial_horizon_seconds: 86400
  max_observation_slots: 96
  provider_selection: NOT_SELECTED
  scheduler_state: PLANNED_NOT_BUILT
  candle_label_policy: RETAIN_AS_RECEIVED_NO_START_END_PROMOTION
  missing_slot_policy: RETAIN_TYPED_GAP_NO_BACKFILL
  observation_time_fields:
    - slot_open_at
    - slot_close_at
    - observed_at
    - ingested_at
    - request_identity
    - response_hash
    - provider_response_timestamp_if_present
    - terminal_state
reuse_boundary:
  adopt:
    - CONTENT_ADDRESSED_RAW_MANIFESTS
    - IDEMPOTENT_SLOT_IDENTITY
    - PHYSICAL_CAPS
    - TYPED_GAPS
    - RECOVERY_AND_DAILY_HEALTH
  forbidden_reuse:
    - JUPITER_QUOTE_VALUES
    - TASK21_TECHNICAL_PROBE_AS_ADMISSION
    - TASK21_PROVIDER_ENDPOINT
    - TASK21_EXECUTION_CAPACITY_RUN_PLAN
authority:
  provider_api_rpc_wss_calls: 0
  credential_use: false
  raw_data_write: false
  scheduler_or_background_process: false
  dependency_changes: false
  wallet_signer_transaction_actions: false
  cash_spend_usd_cents: 0
  task30_trial_or_acceptance: false
  project_sources_changes: false
non_claims:
  continuous_panel_claim: false
  pit_admissible_claim: false
  explicit_no_trade_claim: false
  provider_selected_claim: false
  scheduler_running_claim: false
  alpha_claim: false
  numeric_netreturn_claim: false
decision: HOLD_BIRDEYE_ROUTE_PREPARE_FORWARD_CAPTURE_CANDIDATE
next_boundary: EXACT_PROVIDER_SELECTION_AND_24H_CAPTURE_GATE_REQUIRED
project_sources_disposition: NO_CHANGE
```

The Markdown contract must restate the same values, explain that the route hold
is reversible but not self-retrying, and explicitly forbid using the decision
as a live collection or TASK-30 acceptance authorization. The JSON Schema must
use `additionalProperties: false` at every nested object and `const` values for
the frozen fields above. The fixture must contain the exact evaluator result
defined in Task 2.

### Task 2: Implement the fail-closed evaluator and adversarial checks

**Files:**
- Create: `docs/contracts/task30_birdeye_route_hold_forward_capture_decision_contract_v1.md`
- Create: `configs/task30_birdeye_route_hold_forward_capture_decision_v1.yaml`
- Create: `catalog/schemas/task30_birdeye_route_hold_forward_capture_decision.schema.json`
- Create: `tests/fixtures/task30/birdeye_route_hold_forward_capture_decision_v1.json`
- Create: `src/solana_alpha_lab/task30_birdeye_route_hold_forward_capture_decision.py`
- Create: `tests/test_task30_birdeye_route_hold_forward_capture_decision.py`

**Consumes:** The policy and fixture from Task 1.

**Produces:** `evaluate_birdeye_route_hold_forward_capture(config: Mapping[str, Any]) -> dict[str, Any]`, returning only the frozen decision result or raising `BirdeyeRouteHoldForwardCaptureError`.

- [ ] **Step 1: Add adversarial test cases before implementation**

```python
cases = (
    ("birdeye_route.state", "RETRY_NOW", "BIRDEYE_AUTORETRY_FORBIDDEN"),
    ("forward_capture_candidate.pool_address", "another-pool", "POOL_EXPANSION_FORBIDDEN"),
    ("forward_capture_candidate.slot_seconds", 60, "CADENCE_DRIFT"),
    ("forward_capture_candidate.max_observation_slots", 97, "SLOT_CAP_DRIFT"),
    ("forward_capture_candidate.provider_selection", "BIRDEYE", "PROVIDER_PROMOTION_FORBIDDEN"),
    ("authority.provider_api_rpc_wss_calls", 1, "EXTERNAL_AUTHORITY_FORBIDDEN"),
    ("authority.scheduler_or_background_process", True, "SCHEDULER_ACTIVATION_FORBIDDEN"),
    ("non_claims.explicit_no_trade_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
    ("decision", "START_CAPTURE_NOW", "DECISION_PROMOTION_FORBIDDEN"),
)
```

For every case, copy the policy, replace the dotted pointer, and assert the
specified error code. Add a separate test that adds an `api_key` field under
`birdeye_route` and expects `CREDENTIAL_DISCLOSURE_FORBIDDEN`.

- [ ] **Step 2: Run the adversarial test and verify the expected failure**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_birdeye_route_hold_forward_capture_decision -v
```

Expected: failure because `BirdeyeRouteHoldForwardCaptureError` and the
evaluator are not yet defined.

- [ ] **Step 3: Implement the minimal evaluator**

Use this public surface:

```python
class BirdeyeRouteHoldForwardCaptureError(ValueError):
    """Raised when the offline route-hold decision is widened or contradicted."""


def evaluate_birdeye_route_hold_forward_capture(
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the sole permitted offline hold-and-forward-capture decision."""
```

Implement private `_require`, `_mapping`, `_contains_credential_key` and a
dotted-pointer-free validation flow. Require the exact top-level constants,
the frozen pool, 900-second cadence, 86,400-second horizon, 96-slot maximum,
the full eight-field observation-time list, the exact reuse lists, all-zero
authority, all-false non-claims, `NO_CHANGE` source disposition and the sole
decision/next-boundary strings. Return:

```python
{
    "decision": "HOLD_BIRDEYE_ROUTE_PREPARE_FORWARD_CAPTURE_CANDIDATE",
    "birdeye_route_state": "HOLD_NO_AUTORETRY",
    "forward_capture_candidate": {
        "pool_address": "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        "slot_seconds": 900,
        "initial_horizon_seconds": 86400,
        "max_observation_slots": 96,
        "provider_selection": "NOT_SELECTED",
        "scheduler_state": "PLANNED_NOT_BUILT",
    },
    "next_boundary": "EXACT_PROVIDER_SELECTION_AND_24H_CAPTURE_GATE_REQUIRED",
    "project_sources_disposition": "NO_CHANGE",
}
```

- [ ] **Step 4: Run targeted tests and verify they pass**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_birdeye_route_hold_forward_capture_decision -v
```

Expected: all policy-schema, evaluator, credential, authority, pool, cadence,
slot-cap and non-claim tests pass.

- [ ] **Step 5: Commit the evaluator**

```powershell
git add src/solana_alpha_lab/task30_birdeye_route_hold_forward_capture_decision.py tests/test_task30_birdeye_route_hold_forward_capture_decision.py
git add docs/contracts/task30_birdeye_route_hold_forward_capture_decision_contract_v1.md configs/task30_birdeye_route_hold_forward_capture_decision_v1.yaml catalog/schemas/task30_birdeye_route_hold_forward_capture_decision.schema.json tests/fixtures/task30/birdeye_route_hold_forward_capture_decision_v1.json
git commit -m "feat: freeze task30 forward capture decision"
```

### Task 3: Bind acceptance evidence and Catalog navigation

**Files:**
- Create: `docs/evidence/task30/a6_birdeye_route_hold_forward_capture_decision_acceptance_v1.json`
- Modify: `tests/test_task30_birdeye_route_hold_forward_capture_decision.py`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`

**Consumes:** Validated Task 1 and Task 2 artifacts plus the A5R1 rate-limit receipt.

**Produces:** Hash-bound evidence and seven discoverable A6 assets:

```text
CONTRACT-T30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
CONFIG-T30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
SCHEMA-T30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
FIXTURE-T30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
MODULE-T30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
TEST-T30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
EVIDENCE-T30-A6-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-001
```

- [ ] **Step 1: Add the failing evidence and Catalog assertions**

```python
def test_acceptance_binds_artifacts_and_reports_zero_external_effects(self) -> None:
    receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    for binding in receipt["artifact_bindings"].values():
        self.assertEqual(binding["sha256"], sha256(ROOT / binding["path"]))
    self.assertTrue(all(value == 0 for value in receipt["side_effect_counters"].values()))
    self.assertEqual(receipt["factory_fit"]["review_scope"], "FULL_REVIEW")
    self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
```

Also load `catalog/assets/core.yaml` and assert that all seven IDs in the
produced list exist.

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_birdeye_route_hold_forward_capture_decision.Task30BirdeyeRouteHoldForwardCaptureDecisionTests.test_acceptance_binds_artifacts_and_reports_zero_external_effects -v
```

Expected: failure because the acceptance receipt does not yet exist.

- [ ] **Step 3: Create the receipt and Catalog transaction**

The receipt must bind the contract, configuration, schema, fixture, module and
test hashes, cite the A5R1 decision
`PAIR_IDENTITY_ACCEPTED_OHLCV_RATE_OR_QUOTA_LIMITED`, report all side-effect
counters as zero and set:

```json
{
  "status": "VALIDATED_OFFLINE_ROUTE_HOLD_AND_FORWARD_CAPTURE_DECISION",
  "decision": "HOLD_BIRDEYE_ROUTE_PREPARE_FORWARD_CAPTURE_CANDIDATE",
  "factory_fit": {
    "review_scope": "FULL_REVIEW",
    "verdict": "PASS_WITH_LIMITATIONS"
  },
  "project_sources_disposition": {
    "kind": "NO_CHANGE"
  }
}
```

Add the seven core Catalog records with `truth_owner: TASK-30`,
`consumers: [TASK-30, FACTORY-001]`, SHA-256 integrity and relations between
the policy artifacts, test and receipt. The A6 evidence record derives from
`EVIDENCE-T30-A5R1-BIRDEYE-EXTERNAL-READ-RUNTIME-001`; do not add an invented
lifecycle relation. Register the new schema, increase the exact manifest
counts and regenerate navigation using:

```powershell
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
```

Then refresh the two generated-view SHA-256 bindings in
`catalog/assets/lifecycle.yaml` and rerun the generator/check sequence until
the validated Catalog and generated views agree.

- [ ] **Step 4: Run targeted and Catalog validation**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_birdeye_route_hold_forward_capture_decision tests.test_catalog -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

Expected: all tests pass, the Catalog validates, and generated navigation is
unchanged after its explicit regeneration.

- [ ] **Step 5: Commit evidence and Catalog records**

```powershell
git add docs/evidence/task30/a6_birdeye_route_hold_forward_capture_decision_acceptance_v1.json tests/test_task30_birdeye_route_hold_forward_capture_decision.py catalog/assets/core.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md
git commit -m "feat: record task30 forward capture decision"
```

### Task 4: Deliver the bounded offline atom

**Files:** all files above.

**Consumes:** A clean, committed candidate with targeted checks passing.

**Produces:** One delivery branch, tracked-only preflight receipt, pushed pull request, exact-head CI read-back and, if the machine owner-attention gate returns `AUTONOMOUS`, ordinary merge and post-merge main CI read-back.

- [ ] **Step 1: Run the complete targeted acceptance suite**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_birdeye_route_hold_forward_capture_decision tests.test_task30_birdeye_v3_external_read_runtime_receipt tests.test_task20_collection_spec_contract tests.test_task21_sustained_collection -v
```

Expected: all tests pass with no provider, credential, scheduler, raw-data or cash side effects.

- [ ] **Step 2: Run the tracked-only delivery preflight for the exact committed candidate**

Run:

```powershell
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: the locked full gate passes in an isolated tracked-only checkout and
writes an ignored local receipt.

- [ ] **Step 3: Inspect delivery scope and publish**

Run:

```powershell
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git push -u origin task30/route-hold-forward-capture-decision
```

Expected: the changed-file list equals the plan inventory; no secret, local
raw data or absolute machine path appears. Open one pull request and read back
its exact head and CI result.

- [ ] **Step 4: Apply the repository owner-attention gate before merge**

Run the committed repository gate for the exact pull-request head. Merge only
if it returns `AUTONOMOUS` and all exact-head, review, secret-scan,
mergeability and CI checks pass. Then read back the exact `main` commit and
post-merge main CI. Do not claim TASK-30 acceptance or canonical Source
activation; the receipt remains `NO_CHANGE`.
