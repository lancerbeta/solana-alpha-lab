# T30-A8 H07/H01 Exact Data Contract Entry Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one deterministic offline decision that states which future
data lane can reduce each frozen H07/H01 uncertainty, without promoting price
history or quotes into a trial or settlement claim.

**Architecture:** A versioned YAML policy binds TASK-28's frozen H07/H01 group
and the TASK-26B/TASK-27/T30-A6/A7 receipts to three explicit evidence lanes.
A pure evaluator validates the binding, enforces fail-closed field and
authority rules, then renders a Russian owner readout.  The acceptance receipt
binds the final artifacts and preserves the decision-relevant audit triggers.

**Tech Stack:** Python 3.13 standard library, PyYAML, JSON Schema, `unittest`,
existing Catalog generator and locked `uv` validation commands.  No dependency
is added.

## Global Constraints

- Atom: `T30-A8_H07_H01_EXACT_DATA_CONTRACT_ENTRY_GATE_V1` on branch
  `task30/a8-h07-h01-exact-data-contract-entry-gate`.
- Bind group `RC001-H07-H01-LIQUIDITY-RETENTION` and definition SHA-256
  `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7`.
- Terminal decisions are exactly `PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT`,
  `REDESIGN_DATA`, and `CLOSE_ROUTE`.
- Lanes are exactly `PIT_MARKET`, `ROUTE_FEASIBILITY`, and `OWNED_EXECUTION`.
- `PIT_MARKET` and `ROUTE_FEASIBILITY` are never settlement; only the future,
  canary-only `OWNED_EXECUTION` lane may establish owner settlement truth.
- Missing/UNKNOWN is never zero, no-trade, flat, fill or settled.
- No provider/API/RPC/WSS call, credential use, raw capture/retention write,
  R2/R3 access, scheduler, dependency, wallet/signer/transaction, cash,
  numeric NetReturn, trial, strategy promotion, TASK-30 acceptance or Project
  Sources change is permitted.
- A future decision-critical irrecoverable capture requires a registered
  backup/restore route or an explicit tracked waiver before external authority.
- A capture framework assessment is required before copying more than 150
  orchestration-specific lines or adding a second new capture consumer.
- External audit input is bound only by SHA-256
  `9ef775756f35199b073acfea0e52db228da9b4d08c30b1194e3d7b1b88886da1`;
  do not import its full interview narrative.

---

## File structure

- Create: `docs/tasks/TASK-30-h07-h01-exact-data-contract-entry-gate.md` —
  owner-facing task boundary and non-claims.
- Create: `docs/contracts/task30_h07_h01_exact_data_contract_entry_gate_contract_v1.md` —
  versioned semantic contract.
- Create: `configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml` —
  frozen binding, lane matrix, current states, audit triggers and zero counters.
- Create: `catalog/schemas/task30_h07_h01_exact_data_contract_entry_gate.schema.json` —
  closed structural policy schema.
- Create: `tests/fixtures/task30/h07_h01_exact_data_contract_entry_gate_v1.json` —
  synthetic golden evaluation result.
- Create: `src/solana_alpha_lab/task30_h07_h01_exact_data_contract_entry_gate.py` —
  pure validator, evaluator and readout renderer.
- Create: `scripts/show_task30_h07_h01_data_contract_readout.py` —
  read-only JSON/Markdown CLI.
- Create: `docs/reports/task30/h07_h01_exact_data_contract_readout_v1.md` —
  tracked renderer output.
- Create: `tests/test_task30_h07_h01_exact_data_contract_entry_gate.py` —
  deterministic, adversarial and receipt/Catalog tests.
- Create: `docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json` —
  hash-bound FULL Factory Fit receipt.
- Modify: `catalog/assets/core.yaml` — add the nine stable A8 artifact IDs.
- Modify: `catalog/assets/lifecycle.yaml` — add the TASK-30 A8 lifecycle link
  only if its schema requires it.
- Modify via generator only: `catalog/catalog_manifest.yaml`,
  `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md`.

Stable IDs are:

```text
CONTRACT-T30-H07-H01-DATA-CONTRACT-GATE-001
CONFIG-T30-H07-H01-DATA-CONTRACT-GATE-001
SCHEMA-T30-H07-H01-DATA-CONTRACT-GATE-001
FIXTURE-T30-H07-H01-DATA-CONTRACT-GATE-001
MODULE-T30-H07-H01-DATA-CONTRACT-GATE-001
SCRIPT-T30-H07-H01-DATA-CONTRACT-GATE-001
REPORT-T30-H07-H01-DATA-CONTRACT-GATE-001
TEST-T30-H07-H01-DATA-CONTRACT-GATE-001
EVIDENCE-T30-A8-H07-H01-DATA-CONTRACT-GATE-001
```

## Task 1: Contract matrix and adversarial test boundary

**Files:**

- Create: `tests/test_task30_h07_h01_exact_data_contract_entry_gate.py`
- Create: `docs/tasks/TASK-30-h07-h01-exact-data-contract-entry-gate.md`
- Create: `docs/contracts/task30_h07_h01_exact_data_contract_entry_gate_contract_v1.md`
- Create: `configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml`
- Create: `catalog/schemas/task30_h07_h01_exact_data_contract_entry_gate.schema.json`
- Create: `tests/fixtures/task30/h07_h01_exact_data_contract_entry_gate_v1.json`

**Interfaces:**

- Consumes: A7 `FROZEN_GROUP_ID`, definition hash and four hash-bound prior
  receipts.
- Produces: `validate_data_contract(config, frozen_group) -> None` contract
  required by Tasks 2–4.

- [ ] **Step 1: Write the failing contract tests**

```python
from solana_alpha_lab.task30_h07_h01_exact_data_contract_entry_gate import (
    evaluate_data_contract,
    validate_data_contract,
)

class Task30H07H01ExactDataContractTests(unittest.TestCase):
    def test_partial_pit_capture_retains_execution_blocker(self) -> None:
        result = evaluate_data_contract(load_yaml(CONFIG_PATH), h07_h01_group())
        self.assertEqual(result["decision"], "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT")
        self.assertIs(result["trial_admissible"], False)
        self.assertEqual(
            result["requirements"]["settled_execution_truth"]["state"], "UNSUPPORTED"
        )

    def test_false_promotions_and_missing_recovery_are_rejected(self) -> None:
        for mutation in (
            ("requirements", "settled_execution_truth", "state", "SUPPORTED"),
            ("lanes", "PIT_MARKET", "may_establish", "SETTLEMENT"),
            ("requirements", "multi_notional_route_persistence", "lane", "PIT_MARKET"),
            ("capture_safety", "backup_or_waiver", "required", False),
        ):
            candidate = mutate(copy.deepcopy(config), mutation)
            with self.assertRaises(ValueError):
                validate_data_contract(candidate, h07_h01_group())
```

Use `unittest.TestCase`, `copy.deepcopy` and `self.assertRaises`, matching the
existing A7 test style; the project test runner remains `unittest`.

- [ ] **Step 2: Run the test to verify it fails for the missing module**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_h07_h01_exact_data_contract_entry_gate
```

Expected: `ModuleNotFoundError` for
`task30_h07_h01_exact_data_contract_entry_gate`.

- [ ] **Step 3: Add the closed policy surfaces**

The YAML and JSON Schema must bind the A7 input hashes and declare each
requirement exactly once:

```yaml
requirements:
  pit_liquidity_retention_state:
    lane: PIT_MARKET
    state: MISSING_UNKNOWN
  multi_notional_route_persistence:
    lane: ROUTE_FEASIBILITY
    state: MISSING_UNKNOWN
  post_migration_continuation_context:
    lane: PIT_MARKET
    state: MISSING_UNKNOWN
  settled_execution_truth:
    lane: OWNED_EXECUTION
    state: UNSUPPORTED
```

For both capture-capable lanes require `observed_at`, `available_at`,
`ingested_at`, `source_or_raw_sha256`, and typed gap/failure semantics.  For
`OWNED_EXECUTION`, require the Task-26B witness fields but set
`future_canary_only: true` and `available_in_this_atom: false`.  Set all
authority and side-effect counters to zero and every promotion non-claim to
`false`.

- [ ] **Step 4: Add the synthetic golden result**

The fixture must contain the exact partial decision, four requirement states,
the retained `UNSUPPORTED` execution blocker, `trial_admissible: false`, and
one owner explanation.  It must contain no provider name, URL, credential,
raw body or real observation.

- [ ] **Step 5: Run the structural test path**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_h07_h01_exact_data_contract_entry_gate
```

Expected: still fails only because the evaluator module is absent; file/schema
paths and fixture load successfully once the test helper is reached.

- [ ] **Step 6: Commit the contract boundary**

```text
git add docs/tasks/TASK-30-h07-h01-exact-data-contract-entry-gate.md docs/contracts/task30_h07_h01_exact_data_contract_entry_gate_contract_v1.md configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml catalog/schemas/task30_h07_h01_exact_data_contract_entry_gate.schema.json tests/fixtures/task30/h07_h01_exact_data_contract_entry_gate_v1.json tests/test_task30_h07_h01_exact_data_contract_entry_gate.py
git commit -m "feat: define task30 a8 data contract"
```

## Task 2: Pure evaluator and fail-closed decisions

**Files:**

- Create: `src/solana_alpha_lab/task30_h07_h01_exact_data_contract_entry_gate.py`
- Modify: `tests/test_task30_h07_h01_exact_data_contract_entry_gate.py`

**Interfaces:**

- Consumes: the Task 1 YAML mapping and frozen TASK-28 group mapping.
- Produces:

```python
def validate_data_contract(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> None: ...

def evaluate_data_contract(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> dict[str, Any]: ...

def render_data_contract_readout(result: Mapping[str, Any]) -> str: ...
```

- [ ] **Step 1: Extend failing tests for exact failure modes**

Add independent cases for `SOURCE_BINDING_CONFLICT`, `UNMAPPED_REQUIREMENT`,
`AMBIGUOUS_PIT_SEMANTICS`, `FALSE_PROMOTION`,
`UNRECOVERABLE_CAPTURE_WITHOUT_COVERAGE` and `REUSE_TRIGGER_UNRESOLVED`.
Each case changes one field in a deep copy and expects `ValueError` with the
named code.

- [ ] **Step 2: Run the extended test file and observe the red state**

Run the same command as Task 1.  Expected: import failure; no network or
external counter is observed.

- [ ] **Step 3: Implement the minimal evaluator**

Follow A7's `Mapping[str, Any]` helpers.  Freeze these constants:

```python
FROZEN_GROUP_ID = "RC001-H07-H01-LIQUIDITY-RETENTION"
TERMINAL_DECISIONS = (
    "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT",
    "REDESIGN_DATA",
    "CLOSE_ROUTE",
)
LANES = ("PIT_MARKET", "ROUTE_FEASIBILITY", "OWNED_EXECUTION")
```

`validate_data_contract` verifies group/hash inputs, receipt hash bindings,
exact requirement and lane sets, PIT field/timestamp requirements, zero
counters, false non-claims, backup-or-waiver and reuse trigger definitions.
`evaluate_data_contract` returns the first terminal value only when
`PIT_MARKET` and `ROUTE_FEASIBILITY` have a named future-capture contract
shape; it always retains the execution requirement as `UNSUPPORTED` and
`trial_admissible: false`.

- [ ] **Step 4: Run the focused evaluator tests**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_h07_h01_exact_data_contract_entry_gate
```

Expected: all current tests pass; synthetic data only.

- [ ] **Step 5: Commit the evaluator**

```text
git add src/solana_alpha_lab/task30_h07_h01_exact_data_contract_entry_gate.py tests/test_task30_h07_h01_exact_data_contract_entry_gate.py
git commit -m "feat: evaluate task30 a8 data contract"
```

## Task 3: Owner readout and hash-bound acceptance evidence

**Files:**

- Create: `scripts/show_task30_h07_h01_data_contract_readout.py`
- Create: `docs/reports/task30/h07_h01_exact_data_contract_readout_v1.md`
- Create: `docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json`
- Modify: `tests/test_task30_h07_h01_exact_data_contract_entry_gate.py`

**Interfaces:**

- Consumes: Task 2 evaluator output and every new artifact byte path.
- Produces: CLI `--format json|markdown`, deterministic report and acceptance
  receipt with `state_change: NONE`.

- [ ] **Step 1: Write the failing CLI/receipt tests**

Use the A7 subprocess pattern.  Assert that JSON contains:

```python
assert payload["decision"] == "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT"
assert payload["trial_admissible"] is False
assert payload["requirements"]["settled_execution_truth"]["state"] == "UNSUPPORTED"
```

Assert Markdown explains, in Russian, that a future PIT capture can reduce
only named market/route uncertainty and cannot prove execution.  Mutate every
receipt artifact hash, `provider_api_rpc_wss_calls`, `task30_acceptance` and
`audit_assimilation.input_sha256` in deep copies; each must fail validation.

- [ ] **Step 2: Run the CLI/receipt test and verify it fails**

Run the focused test file.  Expected: missing script/report/receipt path.

- [ ] **Step 3: Implement the read-only CLI and tracked report**

Mirror A7's CLI shape:

```python
parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
config = load_yaml(ROOT / "configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml")
result = evaluate_data_contract(config, h07_h01_group(frozen_config))
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
```

The Markdown report must show: question, decision, lane-by-lane answer,
retained blocker, future capture safety requirement, non-claims and exactly
one next owner boundary.  It must be byte-identical to
`render_data_contract_readout(result) + "\n"`.

- [ ] **Step 4: Create the acceptance receipt**

Bind task, contract, config, schema, fixture, module, script, report and test
by SHA-256.  Include A7's three input receipts plus the frozen definition;
record `FULL_REVIEW`, `PASS_WITH_LIMITATIONS`, zero authorities, zero side
effects, `NO_CHANGE` Project Sources disposition, `STATE_CHANGE=NONE`, and:

```json
"audit_assimilation": {
  "input_sha256": "9ef775756f35199b073acfea0e52db228da9b4d08c30b1194e3d7b1b88886da1",
  "accepted_now": ["PROSPECTIVE_CAPTURE_REUSE_TRIGGER", "BACKUP_OR_WAIVER_BEFORE_IRRECOVERABLE_CAPTURE"],
  "deferred_trigger": "FAST_PATH_REPAIR_RECURRENCE_OR_MATERIAL_BASELINE_TOUCH"
}
```

- [ ] **Step 5: Run the focused tests to green**

Run the focused test file.  Expected: all tests pass and no provider/credential
counter is non-zero.

- [ ] **Step 6: Commit the owner-visible evidence**

```text
git add scripts/show_task30_h07_h01_data_contract_readout.py docs/reports/task30/h07_h01_exact_data_contract_readout_v1.md docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json tests/test_task30_h07_h01_exact_data_contract_entry_gate.py
git commit -m "feat: add task30 a8 owner data readout"
```

## Task 4: Catalog propagation, full review and delivery checks

**Files:**

- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml` only if required by its schema
- Modify by generator: `catalog/catalog_manifest.yaml`,
  `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md`
- Modify: `docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json`
- Modify: `tests/test_task30_h07_h01_exact_data_contract_entry_gate.py`

**Interfaces:**

- Consumes: all Task 1–3 paths and SHA-256 values.
- Produces: discoverable Catalog records and a final acceptance receipt whose
  artifact bindings include the Catalog-aware test.

- [ ] **Step 1: Add the failing Catalog discovery assertion**

Add a test that loads `catalog/assets/core.yaml`, finds all nine stable IDs,
checks their repository paths and verifies that the evidence asset is
`validated_by` the A8 test asset.  It must reject a generated-view edit that
is not regenerated from the Catalog owner.

- [ ] **Step 2: Run the focused test and verify the missing Catalog IDs fail**

Run the A8 test file.  Expected: assertion identifying the first absent stable
ID.

- [ ] **Step 3: Register source artifacts and regenerate views**

Add the nine assets to `catalog/assets/core.yaml`, using `TASK-30` as truth
owner and relations mirroring A6: configuration governed by contract, fixture
derived from configuration, module governed by configuration, script/report
derived from module, test depends on module/schema/fixture/evidence, evidence
derived from module and validated by test.  Do not edit generated files by
hand.  Run:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

Update receipt hashes only after the final source, test and generated bytes are
stable; then re-run its hash-binding test.

- [ ] **Step 4: Run the targeted validation set**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_h07_h01_exact_data_contract_entry_gate tests.test_catalog tests.test_ci
```

Expected: PASS.  A8 must have zero external authority counters and no new
skip, provider, raw-data, wallet or cash side effect.

- [ ] **Step 5: Run the required delivery validation once on the exact candidate**

Run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: PASS receipt under `local/delivery_preflight/`; do not repeat the
ordinary full local gate for unchanged bytes.

- [ ] **Step 6: Inspect scope, commit and prepare one draft PR**

```text
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git add catalog/assets/core.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json tests/test_task30_h07_h01_exact_data_contract_entry_gate.py
git commit -m "chore: register task30 a8 data contract"
```

Push non-force, open one draft PR and read back exact-head CI.  Stop before
merge; PR/CI remains implementation evidence, not TASK-30 acceptance.

## Plan self-review

- Spec coverage: three lanes, frozen binding, partial decision, false-promotion
  rejection, backup/waiver, reuse trigger, audit trace, owner readout, receipt,
  Catalog, FULL review and zero-authority boundary are each assigned to a task.
- Placeholder scan: no unresolved marker, generic validation instruction or
  unspecified interface remains.
- Type consistency: all later tasks use the Task 2 names
  `validate_data_contract`, `evaluate_data_contract` and
  `render_data_contract_readout`.
- Scope check: one offline evaluator/readout slice; provider selection,
  capture execution and owned canary remain separate future owner gates.
