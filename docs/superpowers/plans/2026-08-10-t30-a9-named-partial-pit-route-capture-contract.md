# T30-A9 Named Partial PIT and Route-Capture Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one deterministic offline owner packet that specifies a future 24-hour technical data-route pilot without selecting a provider, making an external call, or promoting the pilot into H07/H01 research evidence.

**Architecture:** A pure TASK-30 A9 evaluator consumes the frozen H07/H01 definition and the A8 decision. A closed YAML policy declares the reference pool, technical-pilot role, 96 closed 15-minute slots, conditional route-feasibility lane, required future owner inputs, and the recovery boundary. A small CLI renders a Russian owner packet; synthetic fixtures and hash-bound evidence make all claims fail closed.

**Tech Stack:** Python 3.13 standard library, PyYAML, JSON Schema, `unittest`, existing Catalog generator, and locked `uv`. No dependency is added.

## Global Constraints

- Implement only `T30-A9_NAMED_PARTIAL_PIT_AND_ROUTE_CAPTURE_CONTRACT_V1` from branch `task30/a9-partial-pit-route-capture-contract`, based on `a9cb7b1e4e9f1444e33029085170dd99bc211ab2`.
- The reference pool is `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`; its exclusive role is `TECHNICAL_DATA_ROUTE_PILOT` and its representativeness is `NOT_ESTABLISHED`.
- The future technical pilot describes exactly 96 closed 15-minute UTC slots over 24 hours. Every slot must resolve to an observation or an explicit typed gap. Missing data can never become zero, flat, success, or evidence of tradability.
- `PIT_MARKET` can prove only a future data-route capability. `ROUTE_FEASIBILITY` remains conditional on a later owner packet containing fixed named notionals. H07/H01 trial, alpha, execution, settlement, PnL, and economic claims remain forbidden.
- A later external owner packet must bind provider and endpoint, exact identity, UTC window, lanes or notional buckets, request and quota caps, credentials, no-fallback rule, raw-retention location and hashes, backup or tracked waiver, monitoring owner, recovery path, and non-claims.
- A9 itself must not select or call a provider; use credentials; retain raw data; add a scheduler, collector, provider adapter, fallback, wallet, signer, RPC, transaction, cash action, or execution-capture path.
- The source decision is `OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED`. It never grants the external authority it describes.
- Reuse the existing Catalog generator and frozen A8/H07/H01 artifacts. Do not edit generated Catalog output by hand.

## Files and Stable IDs

Create:

- `docs/tasks/TASK-30-named-partial-pit-route-capture-contract.md`
- `docs/contracts/task30_named_partial_pit_route_capture_contract_v1.md`
- `configs/task30_named_partial_pit_route_capture_contract_v1.yaml`
- `catalog/schemas/task30_named_partial_pit_route_capture_contract.schema.json`
- `tests/fixtures/task30/named_partial_pit_route_capture_contract_v1.json`
- `src/solana_alpha_lab/task30_named_partial_pit_route_capture_contract.py`
- `scripts/show_task30_named_partial_pit_route_capture_contract.py`
- `docs/reports/task30/named_partial_pit_route_capture_contract_readout_v1.md`
- `tests/test_task30_named_partial_pit_route_capture_contract.py`
- `docs/evidence/task30/a9_named_partial_pit_route_capture_contract_acceptance_v1.json`

Modify only the Catalog sources and their generated output required by the repository generator:

- Catalog core, manifest, lifecycle, and generated project map.

Use these stable IDs:

```text
CONTRACT-T30-NAMED-PARTIAL-CAPTURE-001
CONFIG-T30-NAMED-PARTIAL-CAPTURE-001
SCHEMA-T30-NAMED-PARTIAL-CAPTURE-001
FIXTURE-T30-NAMED-PARTIAL-CAPTURE-001
MODULE-T30-NAMED-PARTIAL-CAPTURE-001
SCRIPT-T30-NAMED-PARTIAL-CAPTURE-001
REPORT-T30-NAMED-PARTIAL-CAPTURE-001
TEST-T30-NAMED-PARTIAL-CAPTURE-001
EVIDENCE-T30-A9-NAMED-PARTIAL-CAPTURE-001
```

## Implementation Tasks

### 1. Define the closed offline policy and adversarial boundary

**Files:**

- Create: `docs/tasks/TASK-30-named-partial-pit-route-capture-contract.md`
- Create: `docs/contracts/task30_named_partial_pit_route_capture_contract_v1.md`
- Create: `configs/task30_named_partial_pit_route_capture_contract_v1.yaml`
- Create: `catalog/schemas/task30_named_partial_pit_route_capture_contract.schema.json`
- Create: `tests/fixtures/task30/named_partial_pit_route_capture_contract_v1.json`
- Create: `tests/test_task30_named_partial_pit_route_capture_contract.py`

- [ ] Write the task and contract around one narrow owner decision: whether a future named external read may be considered. State the non-claims in one conspicuous block: no provider is selected, no data was collected, no technical result establishes representativeness, and no H07/H01 or execution conclusion was reached.
- [ ] Define the configuration schema and an intentionally complete synthetic fixture. It must require the exact reference subject, `TECHNICAL_DATA_ROUTE_PILOT`, `NOT_ESTABLISHED`, a 24-hour 15-minute window, 96 expected slots, `OBSERVATION_OR_TYPED_GAP_REQUIRED`, a conditional route-feasibility lane, and explicit future owner inputs.
- [ ] Bind the frozen upstream group `RC001-H07-H01-LIQUIDITY-RETENTION` and its definition SHA-256 `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7` in the contract and fixture. Treat a mismatch as a hard failure.
- [ ] Make the later external packet a declarative requirement, not an authorization. It must include provider/endpoint, identity, UTC window, fixed lanes or notionals, request/quota cap, credential cap, explicit no-fallback, raw retention and hash plan, backup-or-waiver, monitoring owner, recovery procedure, and non-claims.
- [ ] Write red tests before the evaluator exists. Tests must assert `OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED`, `technical_pilot_only=true`, `trial=false`, and `external_capture_authorized=false` for the valid fixture.
- [ ] Add mutation tests which fail closed with stable diagnostic codes:
  - `PILOT_PROMOTION` for `representativeness=ESTABLISHED`;
  - `UNNAMED_NOTIONALS` for route notionals such as `[100, 1000]` before owner binding;
  - `PROVIDER_PRESELECTION` for any named provider such as `BIRDEYE`;
  - `RECOVERY_PROTECTION_REQUIRED` when backup-or-waiver is absent;
  - `AUTHORITY_PROMOTION` when the contract claims one provider call or external authority.

Required policy shape:

```yaml
reference_subject:
  pool_address: URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
  target_role: TECHNICAL_DATA_ROUTE_PILOT
  representativeness: NOT_ESTABLISHED
  identity_verification: REQUIRED_AT_LATER_OWNER_GATE
pilot_window:
  interval: 15m
  expected_closed_intervals: 96
  duration_seconds: 86400
  slot_outcome_policy: OBSERVATION_OR_TYPED_GAP_REQUIRED
route_feasibility:
  state: CONDITIONAL_OWNER_PACKET
  notional_buckets: OWNER_INPUT_REQUIRED
external_owner_packet:
  provider_selection: OWNER_INPUT_REQUIRED
  provider_api_rpc_wss_calls_authorized: false
  credential_use_authorized: false
```

Target interface to test:

```python
def validate_capture_contract(config: Mapping[str, Any], frozen_group: Mapping[str, Any]) -> None: ...
```

Red-test command:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_named_partial_pit_route_capture_contract
```

Example assertion style:

```python
with self.assertRaisesRegex(ValueError, "PILOT_PROMOTION"):
    validate_capture_contract(mutated_config, frozen_group)
```

Checkpoint commit:

```text
feat: define task30 a9 capture contract
```

### 2. Implement the pure evaluator and Russian owner readout

**Files:**

- Create: `src/solana_alpha_lab/task30_named_partial_pit_route_capture_contract.py`
- Create: `scripts/show_task30_named_partial_pit_route_capture_contract.py`
- Create: `docs/reports/task30/named_partial_pit_route_capture_contract_readout_v1.md`
- Modify: `tests/test_task30_named_partial_pit_route_capture_contract.py`

- [ ] Implement only deterministic local functions. The module must have no environment-variable reads, filesystem writes, subprocesses, network code, provider SDK imports, or runtime scheduler.

```python
def validate_capture_contract(config: Mapping[str, Any], frozen_group: Mapping[str, Any]) -> None: ...
def evaluate_capture_contract(config: Mapping[str, Any], frozen_group: Mapping[str, Any]) -> dict[str, Any]: ...
def render_capture_contract_readout(result: Mapping[str, Any]) -> str: ...
```

- [ ] Freeze implementation constants:

```python
FROZEN_GROUP_ID = "RC001-H07-H01-LIQUIDITY-RETENTION"
REFERENCE_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_INTERVALS = 96
DECISION = "OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED"
```

- [ ] Return a compact machine-readable decision, reason codes, fixed subject, scope, required later owner inputs, prohibited actions, recovery precondition, and exact non-claims. The reader must be able to distinguish `PIT_MARKET` from the conditional `ROUTE_FEASIBILITY` lane without interpreting an unfilled input as consent.
- [ ] Render a Russian Markdown packet. It should say plainly: “готово к рассмотрению внешнего owner gate”, not “готово к сбору” or “можно выполнять”. It must display the missing future owner inputs and the stop conditions.
- [ ] Add adversarial tests for each bypass:
  - 95 expected intervals yields `PANEL_SHAPE_MISMATCH`;
  - an observation-only outcome policy yields `MISSINGNESS_COERCION`;
  - any allowed fallback yields `FALLBACK_FORBIDDEN`;
  - removal of the technical-pilot non-claim yields `PILOT_PROMOTION`;
  - positive raw-write or provider-call counts yield `AUTHORITY_PROMOTION`.
- [ ] Test CLI `--format json` and `--format markdown` against the checked-in readout. The CLI receives configuration and frozen-definition paths only; it has no provider or credential flags.

Green-test command:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_named_partial_pit_route_capture_contract
```

Checkpoint commit:

```text
feat: render task30 a9 capture packet
```

### 3. Bind evidence, register the asset, and prepare a delivery candidate

**Files:**

- Create: `docs/evidence/task30/a9_named_partial_pit_route_capture_contract_acceptance_v1.json`
- Modify: Catalog sources and their generated output only as required by the generator.
- Modify: `tests/test_task30_named_partial_pit_route_capture_contract.py`

- [ ] Create an acceptance receipt that hash-binds the nine A9 artifacts and the upstream A8 acceptance/decision references. It must record the exact frozen group binding, decision, `FULL_REVIEW`, owner packet inputs still missing, zero external authority, zero side effects, and the non-claims.
- [ ] Add receipt mutation tests for a changed config SHA-256, a changed frozen A8 SHA-256, provider calls above zero, external authority set true, or any hypothesis-evidence promotion. All must fail deterministically.
- [ ] Apply the Catalog transaction only after the receipt is stable: add asset records, manifest entries, schema record, mandatory-consumer bindings, lifecycle record, and generated map in the repository-prescribed order. Run the generator rather than hand-editing its output.
- [ ] Run targeted and integration checks:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_named_partial_pit_route_capture_contract tests.test_catalog tests.test_ci
git diff --check
```

- [ ] Verify the changed-file list against this plan before staging. No provider, raw data, secret, wallet, transaction, scheduler, or unrelated Source file may appear.

Checkpoint commit:

```text
chore: register task30 a9 capture contract
```

### 4. Run the single delivery gate and stop at the owner boundary

**Files:**

- Verify all files from Tasks 1–3; do not create a runtime collector.

- [ ] Run one tracked-only delivery validation in the exact repository-prescribed mode:

```powershell
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
```

- [ ] Commit only if all validations pass, push non-force to `task30/a9-partial-pit-route-capture-contract`, create one Draft PR, and read back the exact head and CI state.
- [ ] Stop before merge and before any external read. The proposed next action must be a separate explicit owner gate containing the later packet’s actual selections and caps; it must not infer consent from A9 readiness.

## Completion Evidence

- The policy validator rejects all promotion, authority, missingness, route-notional, fallback, and recovery bypasses above.
- The evaluator and CLI produce the same deterministic decision and owner-facing Russian readout from synthetic inputs only.
- Receipt hashes bind A9 artifacts, upstream A8, and frozen H07/H01 definition; mutation tests prove binding failure.
- Catalog generation, targeted suite, repository CI test, diff hygiene, and tracked-only delivery validation pass.
- Draft PR exists with an exact head and observed CI; no merge, provider call, raw retention, credential use, wallet, transaction, cash action, trial, or H07/H01 acceptance has occurred.

## Plan Self-Review

- **Spec coverage:** includes technical-pilot-only role, 96 closed slots, typed gaps, conditional route lane, owner-required inputs, recovery protection, explicit zero authority, non-claims, Russian operator packet, upstream bindings, receipt, Catalog, tests, and delivery stop.
- **Completeness scan:** no implementation stand-in, undefined endpoint, provider choice, monetary amount, or silent authority is present. `OWNER_INPUT_REQUIRED` is an intentional, fail-closed contract value.
- **Consistency:** the same frozen group, pool, interval count, decision enum, authority boundary, and module interface appear in every task. The plan uses `unittest` consistently.
