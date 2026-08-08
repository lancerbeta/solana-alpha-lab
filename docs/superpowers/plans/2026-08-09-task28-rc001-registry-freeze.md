# TASK-28 RC-001 Registry Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the three RC-001 experiment families with deterministic
admissibility checks so later trials cannot silently broaden their search or
claim unavailable evidence.

**Architecture:** A task-owned YAML configuration records the immutable RC-001
definitions, allowed search degrees, evidence requirements and non-claims. A
small offline Python validator checks the configuration and the specialized
lifecycle registries, emits a deterministic admissibility result, and is
exercised by golden and adversarial fixtures. The existing Catalog remains the
navigation layer; it receives additive records and regenerates its views.

**Tech Stack:** Python 3.13, `PyYAML`, `jsonschema`, `unittest`, existing
SMIAL Catalog generator and lifecycle YAML registries.

## Global Constraints

- Base branch: `origin/main` at `e93b651dd6d63987bb1fa2e128d322c3ac291c23`.
- Reuse TASK-16 lifecycle identities and existing YAML registries; no second
  research-memory service, database, notebook platform or generic experiment
  engine.
- No provider/API/RPC/WSS calls, credentials, R2/R3 access, raw-data retention,
  holdout consumption, execution simulation, wallet, signer, transaction,
  spend, dependency, deployment, Project Sources or UI action.
- `MISSING_UNKNOWN` is never zero, flat, continuous, fillable or settled.
- Numeric `NetReturn`, actual fills, fee completeness and settlement are not
  claims TASK-28 may create.
- Frozen definition is distinct from trial admissibility; only a deterministic
  requirement/evidence check may return `READY`.
- Every production behavior begins with a failing `unittest`; generated Catalog
  files are produced only by `scripts/generate_navigation.py --write`.
- Delivery full gate is exactly one tracked-only preflight after the committed
  candidate; do not weaken feature-branch topology validation.

---

### Task 1: Define and test the RC-001 contract surface

**Files:**
- Create: `docs/tasks/TASK-28-rc001-registry-freeze.md`
- Create: `docs/contracts/task28_rc001_registry_freeze_contract_v1.md`
- Create: `configs/task28_rc001_registry_freeze_v1.yaml`
- Create: `catalog/schemas/task28_rc001_registry_freeze.schema.json`
- Create: `tests/fixtures/task28/rc001_registry_freeze_v1.json`
- Create: `tests/test_task28_rc001_registry_freeze.py`

**Interfaces:**
- Consumes: TASK-16 lifecycle identity rules, TASK-24 entity-route decision,
  TASK-25 outcome limitations, TASK-26 execution-evidence limitations and
  TASK-27 route-close decision.
- Produces: a schema-valid config with `research_cycle`, exactly three
  `hypothesis_groups`, `global_search_policy`, `authority`, `non_claims` and
  `admissibility_expectations`.
- Required group identifiers:
  `RC001-H13-COMPOSITE-VETO`, `RC001-H07-H01-LIQUIDITY-RETENTION`, and
  `RC001-H02-H10-H14-PULLBACK-RECLAIM`.

- [ ] **Step 1: Write the failing contract test**

```python
def test_rc001_fixture_matches_the_frozen_three_group_contract() -> None:
    config = load_yaml(CONFIG_PATH)
    fixture = load_json(FIXTURE_PATH)
    validate_schema(config, SCHEMA_PATH)
    self.assertEqual(
        [group["group_id"] for group in config["hypothesis_groups"]],
        fixture["expected_group_ids"],
    )
    self.assertEqual(config["global_search_policy"]["trial_record_creation"], "FORBIDDEN")
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_rc001_registry_freeze.Task28Rc001ContractTests.test_rc001_fixture_matches_the_frozen_three_group_contract
```

Expected: FAIL because the TASK-28 configuration and fixture do not exist.

- [ ] **Step 3: Add the minimal versioned contract/config/schema/fixture**

The YAML must contain one `RESEARCH-CYCLE-RC001-001` record, the exact three
group IDs above, per-group provenance labels, definition inputs, falsifier,
target metrics, required evidence asset IDs, unavailable requirements and an
expected admissibility state. The schema must reject extra root keys and
missing identities. The contract must state that a frozen plan creates no trial
and consumes no holdout.

- [ ] **Step 4: Run the contract test and verify GREEN**

Run the exact command from Step 2. Expected: PASS.

- [ ] **Step 5: Add direct boundary tests**

```python
def test_contract_rejects_numeric_netreturn_and_external_authority() -> None:
    candidate = copy.deepcopy(load_yaml(CONFIG_PATH))
    candidate["non_claims"]["numeric_netreturn"] = False
    with self.assertRaisesRegex(ValueError, "numeric_netreturn"):
        validate_contract(candidate)
```

Add equivalent cases for provider authority, R3 access and a missing
`MISSING_UNKNOWN` preservation rule.

- [ ] **Step 6: Run the TASK-28 test module**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_rc001_registry_freeze
```

Expected: PASS with every new contract-boundary case.

### Task 2: Implement deterministic admissibility and registry bindings

**Files:**
- Create: `src/solana_alpha_lab/task28_rc001_registry_freeze.py`
- Modify: `tests/test_task28_rc001_registry_freeze.py`
- Modify: `registries/research_cycles.yaml`
- Modify: `registries/hypotheses.yaml`
- Modify: `registries/feature_catalog.yaml`
- Read-only invariant: `registries/global_trial_ledger.yaml` must remain
  unchanged; the test proves that RC-001 created no trial record.
- Create: `docs/evidence/task28/a1_rc001_registry_freeze_acceptance_v1.json`

**Interfaces:**
- Consumes: `configs/task28_rc001_registry_freeze_v1.yaml` and the four
  specialized registries.
- Produces:
  `canonical_definition_hash(group: Mapping[str, Any]) -> str`,
  `evaluate_admissibility(group: Mapping[str, Any]) -> Mapping[str, Any]`, and
  `validate_rc001_snapshot(config: Mapping[str, Any], registries: Mapping[str, Any]) -> None`.
- A successful evaluation returns only
  `READY`, `LIMITED_DIAGNOSTIC_ONLY`, `BLOCKED_DATA`, or
  `BLOCKED_EXECUTION_TRUTH`, together with stable blocker codes.

- [ ] **Step 1: Write the failing golden-admissibility test**

```python
def test_frozen_group_with_known_missing_history_is_blocked_data() -> None:
    group = load_config()["hypothesis_groups"][1]
    result = evaluate_admissibility(group)
    self.assertEqual(result["state"], "BLOCKED_DATA")
    self.assertIn("CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE", result["blocker_codes"])
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_rc001_registry_freeze.Task28Rc001AdmissibilityTests.test_frozen_group_with_known_missing_history_is_blocked_data
```

Expected: FAIL because the validator function does not exist.

- [ ] **Step 3: Implement the smallest offline validator**

Implement only the three published functions. Canonical definition hashing
uses deterministic UTF-8 JSON with sorted keys and sorted set-valued arrays.
`evaluate_admissibility` returns `BLOCKED_DATA` whenever a required data input
is explicitly unavailable, `BLOCKED_EXECUTION_TRUTH` whenever a planned claim
requires unsupported execution truth, and `READY` only when no requirement is
unavailable or unsupported. It must never read a network resource.

- [ ] **Step 4: Run the golden test and verify GREEN**

Run the exact command from Step 2. Expected: PASS.

- [ ] **Step 5: Write and run adversarial registry tests**

```python
def test_validator_rejects_ready_state_without_required_entity_evidence() -> None:
    candidate = deep_copy(load_config())
    candidate["hypothesis_groups"][0]["expected_admissibility"] = "READY"
    with self.assertRaisesRegex(ValueError, "ENTITY_ROUTE_NOT_ADMISSIBLE"):
        validate_rc001_snapshot(candidate, load_registries())
```

Add one separate test each for an unregistered parameter, duplicate immutable
definition ID, a foreign feature without a versioned link, a trial-like entry
in the RC-001 ledger, and `MISSING_UNKNOWN` coercion. Run the full TASK-28 test
module after each repair.

- [ ] **Step 6: Add only forward registry records and acceptance evidence**

Append one RC-001 research-cycle record, three frozen hypothesis records and
only their declared features. Do not create a trial record. Preserve the three
existing TASK-23 ledger records unchanged. The acceptance receipt binds the
config, schema, fixture, validator, all registries and known evidence by SHA-256
and records zero external side effects.

- [ ] **Step 7: Verify deterministic behavior and registry preservation**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_rc001_registry_freeze
uv run --locked --managed-python python -B scripts/validate_catalog.py
```

Expected: PASS; the global ledger retains its three historical records and zero
new RC-001 trial records.

### Task 3: Register Catalog outputs, perform Factory Fit and deliver

**Files:**
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`
- Create: `docs/evidence/task28/a2_catalog_factory_fit_v1.json`
- Modify: `tests/test_task28_rc001_registry_freeze.py`

**Interfaces:**
- Consumes: every accepted Task 1 and Task 2 artifact.
- Produces: Catalog records for the TASK-28 contract/config/schema/fixture/
  module/test/registry evidence and a `FULL_REVIEW` Factory Fit receipt.
- Catalog relations must point only to stable existing asset IDs or new
  TASK-28 asset IDs registered in the same transaction.

- [ ] **Step 1: Write the failing Catalog/Factory-Fit test**

```python
def test_catalog_registers_all_task28_outputs_and_factory_fit_stays_offline() -> None:
    catalog = load_catalog_assets()
    for asset_id in TASK28_REQUIRED_ASSET_IDS:
        self.assertIn(asset_id, catalog)
    receipt = load_json(FACTORY_FIT_RECEIPT)
    self.assertEqual(receipt["factory_fit"]["mode"], "FULL_REVIEW")
    self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_rc001_registry_freeze.Task28CatalogFactoryFitTests.test_catalog_registers_all_task28_outputs_and_factory_fit_stays_offline
```

Expected: FAIL because TASK-28 Catalog records and Factory Fit receipt do not
yet exist.

- [ ] **Step 3: Add the additive Catalog transaction and Factory Fit receipt**

Register every Task-28 output with owner, purpose, hash/fingerprint, consumer,
retention, sensitivity and relations. Increment the Catalog version/counts
only from validated actual content. The Factory Fit receipt must cover mission,
research truth, owner operability, reuse, economics, monitoring/recovery,
migration/rollback and red-team rejection cases; it must preserve the decision
that blocked families are not failed market hypotheses.

- [ ] **Step 4: Regenerate and validate Catalog views**

Run:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

Expected: all three commands PASS; only the two declared generated files change.

- [ ] **Step 5: Run targeted and full unit validation**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_rc001_registry_freeze
uv run --locked --managed-python python -B -m unittest discover -s tests -p test_*.py
```

Expected: every TASK-28 test and the baseline suite PASS.

- [ ] **Step 6: Inspect scope, commit and run the exact delivery gate**

Run:

```text
git diff --check
git status --short
git diff --name-only origin/main...HEAD
git add <only validated TASK-28 paths>
git commit -m "feat: freeze RC-001 research registry"
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: the candidate has only the plan-approved paths, a clean tracked-only
delivery receipt, and no copied local raw inputs. Then use ordinary non-force
push, PR, exact-head CI read-back and the repository merge policy. Do not claim
canonical TASK‑28 `DONE` until acceptance, Catalog reconciliation and the
required post-merge evidence exist.

## Plan Self-Review

- Spec coverage: the three frozen families, admissibility, explicit
  non-claims, rejection cases, existing registry reuse, Catalog registration,
  Factory Fit, rollback and tracked-only delivery are each assigned above.
- Scope: the plan creates one control layer and does not begin TASK-29/30/31,
  provider collection, a generic experiment platform or a strategy engine.
- Type consistency: Task 2 owns all named Python interfaces; Tasks 1 and 3 use
  only config/registry documents and stable asset IDs that those interfaces
  consume or produce.
- Placeholder scan: no deferred implementation step or unspecified error path
  remains; every validation command is concrete.
