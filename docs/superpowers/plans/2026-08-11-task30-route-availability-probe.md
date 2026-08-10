# TASK-30 A11A Route Availability Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, deterministic evaluator that proves whether a future three-boundary 15m availability probe is specified safely enough to request its own owner gate.

**Architecture:** The evaluator consumes only a versioned policy and synthetic per-offset records. It validates the frozen H07/H01 15m binding, classifies provider observations versus capture-health failures, derives one fixed publication delay only from stable evidence, and emits a non-promoting decision. A small CLI renders the tracked fixture as a Russian owner readout; neither module creates a request, scheduler, raw file nor runtime process.

**Tech Stack:** Python standard library, PyYAML, jsonschema, unittest, existing Catalog generator and validation scripts.

## Global Constraints

- Base: `db21ae7e88e0337cdc8f61c0fbf6c165320ce089`; branch: `task30/a11-route-availability-probe-design`.
- Bind only `RC001-H07-H01-LIQUIDITY-RETENTION`, `OBSERVATION_WINDOW_15M` and the A10 `START_LABELED` receipt; do not alter frozen hypothesis parameters.
- Offline authority is exact zero for provider/API/RPC/WSS calls, credentials, raw writes, scheduler/background process, R2/R3, wallet/signer/transaction, spend and TASK-30 acceptance.
- No SDK, provider adapter, generic collector, scheduler platform, database or dependency addition.
- A future provider probe remains only a proposed cap: three closed boundaries × offsets `0, 15, 30, 60` seconds = 12 OHLCV reads maximum; no retry or fallback.
- A health failure is never a provider/market gap: it must return `execution_disposition=STOP_RUN` and cannot be promoted into a ready decision.
- `READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE` means technical route readiness only. It never means PIT admissibility, H07/H01 evidence, trial, execution, settlement, PnL or NetReturn.
- The later 24-hour run is out of scope. It requires a separate owner packet after offline acceptance and a two-slot live shakedown.

---

## File map

| Path | Responsibility |
| --- | --- |
| `docs/tasks/TASK-30-route-availability-probe.md` | Bounded task statement, consumer, authority, terminal decisions and non-claims. |
| `docs/contracts/task30_route_availability_probe_contract_v1.md` | Human-readable policy and anti-one-shot activation ladder. |
| `configs/task30_route_availability_probe_v1.yaml` | Exact frozen bindings, offsets, caps, enums and zero-authority policy. |
| `catalog/schemas/task30_route_availability_probe.schema.json` | Structural validation for the YAML policy. |
| `tests/fixtures/task30/route_availability_probe_v1.json` | Synthetic happy-path records and expected deterministic result. |
| `src/solana_alpha_lab/task30_route_availability_probe.py` | Pure policy validator and evaluator; no I/O or network imports. |
| `scripts/show_task30_route_availability_probe.py` | Read-only CLI that renders the tracked fixture in JSON or Russian Markdown. |
| `docs/reports/task30/route_availability_probe_readout_v1.md` | Checked-in Markdown generated from the tracked fixture. |
| `tests/test_task30_route_availability_probe.py` | Adversarial policy, evaluator, CLI, hash-binding and Catalog tests. |
| `docs/evidence/task30/a11_route_availability_probe_acceptance_v1.json` | Hash-bound offline acceptance and FULL_REVIEW receipt. |
| `catalog/assets/core.yaml`, `catalog/assets/lifecycle.yaml`, `catalog/catalog_manifest.yaml`, `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md` | Catalog registration and generated navigation only. |

## Task 1: Freeze the offline policy surface

**Files:**
- Create: `docs/tasks/TASK-30-route-availability-probe.md`
- Create: `docs/contracts/task30_route_availability_probe_contract_v1.md`
- Create: `configs/task30_route_availability_probe_v1.yaml`
- Create: `catalog/schemas/task30_route_availability_probe.schema.json`
- Create: `tests/test_task30_route_availability_probe.py`

**Interfaces:**
- Consumes: `configs/task28_rc001_registry_freeze_v1.yaml`; `docs/evidence/task30/a10_gecko_interval_semantics_runtime_receipt_v1.json`.
- Produces: a schema-valid policy accepted by `validate_probe_policy(policy, frozen_group)`.

- [ ] **Step 1: Write the failing policy test**

```python
def test_tracked_policy_binds_frozen_15m_group_a10_and_zero_authority():
    policy = load_yaml(POLICY_PATH)
    jsonschema.validate(policy, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    validate_probe_policy(policy, frozen_group())
    assert policy["probe_shape"]["boundaries"] == 3
    assert policy["probe_shape"]["offset_seconds"] == [0, 15, 30, 60]
    assert policy["authority"]["provider_api_rpc_wss_calls"] == 0
```

- [ ] **Step 2: Run the test and observe the missing-module failure**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_route_availability_probe.Task30RouteAvailabilityProbeTests.test_tracked_policy_binds_frozen_15m_group_a10_and_zero_authority -v
```

Expected: FAIL because the policy evaluator does not exist yet.

- [ ] **Step 3: Write the task, contract, YAML policy and JSON schema**

The YAML must include these exact semantic fields:

```yaml
task_id: TASK-30
atom_id: T30-A11A_ROUTE_AVAILABILITY_PROBE_OFFLINE_V1
frozen_group_id: RC001-H07-H01-LIQUIDITY-RETENTION
interval_seconds: 900
upstream_a10_decision: START_LABELED
probe_shape:
  boundaries: 3
  offset_seconds: [0, 15, 30, 60]
  max_ohlcv_reads: 12
authority:
  provider_api_rpc_wss_calls: 0
  scheduler_or_background_processes: 0
  raw_data_writes: 0
  credential_use: 0
  cash_spend_usd_cents: 0
```

The contract must define `VALID_OBSERVATION`, `TYPED_GAP`,
`PROCESS_NOT_STARTED`, `RECEIPT_WRITE_FAILED`, `PRIOR_MANIFEST_UNREADABLE` and
`MONITORING_LOST`. It must distinguish a typed market/provider gap from every
capture-health failure and retain the two-slot live shakedown as a future,
separately authorised gate.

- [ ] **Step 4: Implement the smallest policy validator**

Create this public interface in `src/solana_alpha_lab/task30_route_availability_probe.py`:

```python
class RouteAvailabilityProbeError(ValueError):
    pass

def validate_probe_policy(policy: Mapping[str, Any], frozen_group: Mapping[str, Any]) -> None:
    """Fail closed unless the tracked offline probe policy is exact."""
```

Reject a changed group, interval, A10 decision, offsets, read cap, retry,
fallback, selected provider, non-zero authority or promoted claim with named
error codes. The function may import only `collections.abc` and `typing`.

- [ ] **Step 5: Run the focused policy test**

Run the Step 2 command again.

Expected: PASS.

- [ ] **Step 6: Commit the policy surface**

```powershell
git add docs/tasks/TASK-30-route-availability-probe.md docs/contracts/task30_route_availability_probe_contract_v1.md configs/task30_route_availability_probe_v1.yaml catalog/schemas/task30_route_availability_probe.schema.json src/solana_alpha_lab/task30_route_availability_probe.py tests/test_task30_route_availability_probe.py
git commit -m "feat: add task30 route availability policy"
```

## Task 2: Evaluate synthetic publication and health outcomes

**Files:**
- Modify: `src/solana_alpha_lab/task30_route_availability_probe.py`
- Create: `tests/fixtures/task30/route_availability_probe_v1.json`
- Modify: `tests/test_task30_route_availability_probe.py`

**Interfaces:**
- Consumes: validated policy and an exact list of synthetic `ProbeRecord` mappings.
- Produces: `evaluate_probe(policy, frozen_group, records) -> dict[str, Any]` and one stable result fixture.

- [ ] **Step 1: Write failing evaluator tests**

```python
def test_three_stable_boundaries_choose_the_latest_first_availability_as_fixed_delay():
    result = evaluate_probe(policy(), frozen_group(), stable_records(first_visible=[15, 30, 30]))
    assert result["decision"] == "READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE"
    assert result["recommended_fixed_delay_seconds"] == 30
    assert result["execution_disposition"] == "CONTINUE"

def test_process_or_monitoring_failure_stops_instead_of_becoming_a_gap():
    result = evaluate_probe(policy(), frozen_group(), records_with("MONITORING_LOST"))
    assert result["decision"] == "INCONCLUSIVE"
    assert result["execution_disposition"] == "STOP_RUN"
```

- [ ] **Step 2: Run the evaluator tests and observe failure**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_route_availability_probe -v
```

Expected: FAIL because `evaluate_probe` and the synthetic fixture are absent.

- [ ] **Step 3: Implement the pure evaluator**

Define records with these mandatory fields:

```python
{
    "slot_start": 1800,
    "offset_seconds": 30,
    "capture_state": "VALID_OBSERVATION",
    "expected_interval_start": 1800,
    "observed_interval_start": 1800,
    "candle_fingerprint": "sha256-like synthetic token",
}
```

Require exactly three 900-second-aligned distinct slots and exactly the four
declared offsets for each slot. A valid slot may first appear at any allowed
offset; derive the recommended fixed delay as the maximum first-valid offset
across all three slots. The candle fingerprint must remain identical at every
later valid offset for its slot.

Return exactly one availability decision:

```python
{
    "decision": "READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE" | "ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE" | "INCONCLUSIVE",
    "execution_disposition": "CONTINUE" | "STOP_RUN",
    "recommended_fixed_delay_seconds": int | None,
    "slots": list[dict[str, Any]],
    "claims": {
        "technical_route_only": True,
        "pit_admissible": False,
        "h07_h01_evidence": False,
        "task30_trial": False,
        "execution": False,
        "numeric_netreturn": False,
    },
}
```

Classify changed later fingerprints or wrong interval starts as
`ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE`; classify no valid candle or a typed
provider/market gap as `INCONCLUSIVE`; classify any health failure as
`INCONCLUSIVE` plus `STOP_RUN`. Reject duplicate slots, missing offsets,
out-of-grid records, retry/fallback flags and unknown enum values before a
result is emitted.

- [ ] **Step 4: Add the complete adversarial matrix**

Add tests for: ready at a 30-second fixed delay; ready at 60 seconds; a later
revision; a wrong candle interval start; one typed gap; duplicate slot; missing
offset; retry; fallback; `PROCESS_NOT_STARTED`; `RECEIPT_WRITE_FAILED`;
`PRIOR_MANIFEST_UNREADABLE`; and `MONITORING_LOST`. Assert that none of these
paths can set any research, execution or cashflow claim true.

- [ ] **Step 5: Create the canonical synthetic fixture and run tests**

The fixture must contain only synthetic values and the expected ready result
with a 30-second fixed delay. Run the Step 2 command again.

Expected: all focused tests PASS.

- [ ] **Step 6: Commit the evaluator**

```powershell
git add src/solana_alpha_lab/task30_route_availability_probe.py tests/fixtures/task30/route_availability_probe_v1.json tests/test_task30_route_availability_probe.py
git commit -m "feat: evaluate task30 route availability"
```

## Task 3: Owner readout, acceptance receipt and Catalog transaction

**Files:**
- Create: `scripts/show_task30_route_availability_probe.py`
- Create: `docs/reports/task30/route_availability_probe_readout_v1.md`
- Create: `docs/evidence/task30/a11_route_availability_probe_acceptance_v1.json`
- Modify: `tests/test_task30_route_availability_probe.py`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`

**Interfaces:**
- Consumes: the tracked policy, frozen group and synthetic fixture.
- Produces: deterministic JSON/Markdown readout, hash-bound acceptance and Catalog asset/edge records.

- [ ] **Step 1: Write failing readout and receipt tests**

```python
def test_cli_and_checked_in_russian_readout_are_deterministic():
    completed = subprocess.run(
        [sys.executable, "-B", str(SCRIPT_PATH), "--format", "markdown"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0
    assert REPORT_PATH.read_text(encoding="utf-8") == completed.stdout
    assert "не разрешает внешний запрос" in completed.stdout

def test_acceptance_is_hash_bound_and_cannot_promote_external_authority():
    receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert_acceptance(receipt)
```

- [ ] **Step 2: Implement the readout script and report**

The script loads only tracked YAML/JSON inputs and supports `--format json` and
`--format markdown`. The Markdown must state the fixed delay, the future
two-slot live shakedown, the immediate health stop rule and the exact
non-claims. It must never contain a provider URL, credential value, raw path,
request execution code or scheduler action.

- [ ] **Step 3: Create the acceptance receipt**

Bind SHA-256 values for every A11 artifact; record `FULL_REVIEW`,
`PASS_WITH_LIMITATIONS`, `STATE_CHANGE=NONE`, zero side-effect counters and
`project_sources_disposition.kind=NO_CHANGE`. The Factory Fit must explicitly
state that the artifact reduces a capture-safety ambiguity without creating a
collector, a panel, alpha evidence or execution truth.

- [ ] **Step 4: Register assets and regenerate navigation**

Add stable IDs for the contract, config, schema, fixture, module, script,
report, test and evidence. Record the frozen H07/H01 and A10 receipt as
dependencies; add the test and evidence validation relations. Regenerate, do
not hand-edit, `catalog/generated/asset_edges.json` and `docs/PROJECT_MAP.md`.

- [ ] **Step 5: Run targeted acceptance**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_route_availability_probe -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: PASS; zero provider calls, raw writes, scheduler actions and secrets.

- [ ] **Step 6: Commit semantic acceptance**

```powershell
git add scripts/show_task30_route_availability_probe.py docs/reports/task30/route_availability_probe_readout_v1.md docs/evidence/task30/a11_route_availability_probe_acceptance_v1.json tests/test_task30_route_availability_probe.py catalog/assets/core.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md
git commit -m "feat: record task30 route availability acceptance"
```

## Task 4: Deliver the offline atom

**Files:** all Task 1–3 outputs and this validated plan/spec.

**Interfaces:**
- Consumes: clean committed branch with targeted validation.
- Produces: one tracked-only receipt, one PR, exact-head CI, ordinary merge only if `OWNER_ATTENTION_GATE=AUTONOMOUS`, and exact-main push-CI read-back.

- [ ] **Step 1: Verify final scope before delivery**

Run:

```powershell
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
```

Expected: only the File map paths plus Catalog-generated outputs; no raw data,
machine path, provider response, credential, scheduler registration or
dependency lock change.

- [ ] **Step 2: Run the exact tracked-only delivery gate once**

Run:

```powershell
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: `TRACKED_ONLY_DELIVERY_PREFLIGHT: PASS`. Do not rerun a local full
gate unless the candidate bytes or validation policy change.

- [ ] **Step 3: Publish and bind exact-head CI**

Run:

```powershell
git push -u origin task30/a11-route-availability-probe-design
gh pr create --draft --base main --head task30/a11-route-availability-probe-design
gh pr view --json headRefOid,statusCheckRollup,mergeStateStatus,reviews
```

Expected: PR head equals the committed candidate and every required exact-head
check passes.

- [ ] **Step 4: Apply the merge and post-merge gates**

Evaluate `OWNER_ATTENTION_GATE` for `LOCAL_WORK_CODEX` only after exact-head
CI, tracked-only preflight, Factory Fit, write-set, secret scan, review,
mergeability, standard merge, preserved branch and unchanged settings pass.
If its result is `AUTONOMOUS`, ordinary-merge without deleting the branch, then
read exact `origin/main` and its push-CI. Otherwise stop at the returned gate.

## Plan self-review

- Spec coverage: Task 1 binds the frozen 15m/A10/zero-authority surface; Task
  2 covers publication, revision, gaps and health-stop semantics; Task 3 adds
  operator readout, Factory Fit and Catalog; Task 4 covers isolated delivery.
- Placeholder scan: no `TODO`, `TBD` or deferred implementation instruction is
  used; future live work is deliberately excluded rather than left undefined.
- Type consistency: the policy validator, evaluator, record schema, decision
  enum, execution disposition and readout paths are defined before later tasks
  consume them.
