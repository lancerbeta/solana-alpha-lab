# Owner Authority Packet Binding v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, deterministic validator that turns the owner-agreed USD 3.00 technical-canary shape into a fail-closed review packet without granting wallet, signer, transaction, provider, cash, or TASK-27 authority.

**Architecture:** A new `owner_authority_packet_binding` module reads only tracked YAML/JSON fixtures, classifies a packet as an incomplete owner draft or a complete review packet, and emits deterministic acceptance evidence. A JSON Schema validates the evidence, while a second test suite binds the new assets to the existing Catalog and runs the existing navigation generator.

**Tech Stack:** Python 3 standard library, PyYAML, jsonschema, unittest, JSON Schema Draft 2020-12, YAML/JSON/Markdown, existing Catalog generator.

## Global Constraints

- The future flow is exactly `SOL -> one exact memecoin -> SOL`; the exit is immediate after first-leg terminal observation and inventory reconciliation.
- `total_cash_at_risk_cap_usd_cents` is exactly `300`; input notional, network, relay/priority, ATA rent, and all separate fees must be accounted for before a packet can be review-ready.
- Missing token, program, route, wallet public address, notional, fee cap, quote basis, expiry, monitoring/reconciliation references, or recovery procedure is `OWNER_INPUT_REQUIRED`, never a default or zero.
- `DRAFT_OWNER_INPUT_REQUIRED` and `READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION` are both non-executable states: `canary_authority=false`, `task27_authority=false`, and numeric NetReturn is forbidden.
- No wallet creation, funding, seed/private key, signed bytes, transaction, simulation, provider/API/RPC/WSS call, cash spend, R3 read, dependency, deployment, or strategy logic.
- `UNKNOWN`, first-leg reconciliation failure, monitoring loss, inventory mismatch, route/program mismatch, or cap breach blocks the planned exit and every retry.
- Reuse `TASK-26C` contracts as hash-bound inputs; do not modify `TASK-26C` artifacts or build a generic execution platform.

---

## File Map

| Path | Role |
|---|---|
| `docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md` | Human-readable scope, owner decision, non-claims, lifecycle and Definition of Done. |
| `docs/contracts/owner_authority_packet_binding_contract_v1.md` | Versioned offline packet contract and exact state/field semantics. |
| `configs/owner_authority_packet_binding_v1.yaml` | Machine-readable constants, owner-agreed cap, required fields, health blocks and TASK-26C hash bindings. |
| `catalog/schemas/owner_authority_packet_binding.schema.json` | JSON Schema for deterministic acceptance evidence. |
| `tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json` | Synthetic draft, complete-review, cap-breach, unknown, monitoring, inventory and route-negative cases. |
| `src/solana_alpha_lab/owner_authority_packet_binding.py` | Pure parser/evaluator/evidence writer; no network or signer imports. |
| `tests/test_owner_authority_packet_binding.py` | Contract, fixture, schema, evaluator and deterministic-evidence tests. |
| `docs/evidence/owner_authority_packet_binding/a1_offline_packet_binding_acceptance_v1.json` | Generated deterministic acceptance receipt. |
| `tests/test_owner_authority_packet_binding_catalog_factory_fit.py` | Hash-bound Catalog/Factory-Fit receipt tests. |
| `docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json` | Full Factory Fit, Product Horizon and zero-side-effect receipt. |
| `catalog/assets/core.yaml` | Catalog records and relations for the new task outputs. |
| `catalog/assets/lifecycle.yaml` | Lifecycle record identifying this as an authority-preparation task with no execution authority. |
| `catalog/catalog_manifest.yaml` | Version/checkpoint/schema registration. |
| `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md` | Generated Catalog projections; regenerate, never hand-edit. |

## Task 1: Offline packet evaluator, contract, schema and adversarial matrix

**Files:**
- Create: `docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md`
- Create: `docs/contracts/owner_authority_packet_binding_contract_v1.md`
- Create: `configs/owner_authority_packet_binding_v1.yaml`
- Create: `catalog/schemas/owner_authority_packet_binding.schema.json`
- Create: `tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json`
- Create: `src/solana_alpha_lab/owner_authority_packet_binding.py`
- Create: `tests/test_owner_authority_packet_binding.py`

**Interfaces:**
- Consumes: `CONTRACT-T26C-OWNED-CANARY-READINESS-001` and `EVIDENCE-T26C-A3-CATALOG-FACTORY-FIT-001` by exact SHA-256 from the config.
- Produces: `PacketBindingError`, `evaluate_packet(packet) -> dict[str, object]`, `evaluate_exit_precondition(first_leg) -> dict[str, str]`, `build_binding_evidence(repo_root) -> dict[str, object]`, and `write_outputs(repo_root) -> str`.
- Invariant: every return value is an offline classification, never an execution command.

- [ ] **Step 1: Write the failing evaluator/schema tests**

```python
import unittest

from solana_alpha_lab.owner_authority_packet_binding import (
    PacketBindingError,
    build_binding_evidence,
    evaluate_exit_precondition,
    evaluate_packet,
)

class OwnerAuthorityPacketBindingTests(unittest.TestCase):
    def test_draft_keeps_missing_values_visible(self) -> None:
        result = evaluate_packet({
            "packet_state": "DRAFT_OWNER_INPUT_REQUIRED",
            "flow": "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT",
            "total_cash_at_risk_cap_usd_cents": 300,
            "owner_input_fields": REQUIRED_OWNER_INPUTS,
        })
        self.assertEqual(result["decision"], "OWNER_INPUT_REQUIRED")
        self.assertFalse(result["canary_authority"])
        self.assertFalse(result["task27_authority"])

    def test_complete_packet_is_review_only(self) -> None:
        result = evaluate_packet(COMPLETE_PACKET)
        self.assertEqual(result["packet_state"], "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION")
        self.assertEqual(result["next_action"], "OWNER_EXACT_APPROVAL_REQUIRED")
        self.assertFalse(result["canary_authority"])

    def test_exit_requires_reconciled_first_leg(self) -> None:
        with self.assertRaisesRegex(PacketBindingError, "exit_before_first_leg_reconciliation"):
            evaluate_exit_precondition({"terminal_state": "LANDED_SUCCESS", "reconciled": False})
```

Add tests that reject: cap `301`, zero-substituted fees, a missing exact token/program/route, a duplicate/ambiguous owner input list, `UNKNOWN_REQUIRES_RECONCILIATION`, `NO_MONITORING`, `INVENTORY_MISMATCH`, and `ROUTE_PROGRAM_MISMATCH`. Validate the generated evidence with `Draft202012Validator` and prove all side-effect counters equal zero.

- [ ] **Step 2: Run the tests before implementation**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding -v
```

Expected: FAIL because `solana_alpha_lab.owner_authority_packet_binding` and the named contract files do not yet exist.

- [ ] **Step 3: Implement the minimal pure evaluator**

Create `src/solana_alpha_lab/owner_authority_packet_binding.py` with no imports beyond `hashlib`, `json`, `pathlib`, `typing`, and `yaml`. Define exact constants:

```python
TASK_ID = "OWNER_AUTHORITY_PACKET_BINDING_V1"
FLOW = "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT"
CAP_USD_CENTS = 300
DRAFT_STATE = "DRAFT_OWNER_INPUT_REQUIRED"
READY_STATE = "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION"

class PacketBindingError(ValueError):
    pass

def evaluate_packet(packet: Mapping[str, Any]) -> dict[str, object]:
    state = str(packet["packet_state"])
    _require(packet["flow"] == FLOW, "wrong_canary_flow")
    _require(packet["total_cash_at_risk_cap_usd_cents"] == CAP_USD_CENTS, "cash_cap_must_equal_300")
    if state == DRAFT_STATE:
        _require(set(packet["owner_input_fields"]) == REQUIRED_OWNER_INPUTS, "draft_owner_inputs_mismatch")
        return _decision(state, "OWNER_INPUT_REQUIRED")
    _require(state == READY_STATE, "invalid_packet_state")
    _require(not packet.get("owner_input_fields"), "ready_packet_has_unbound_owner_inputs")
    _require(packet["estimated_total_cost_usd_cents"] <= CAP_USD_CENTS, "cash_cap_breach")
    _require(packet["maximum_separate_fees_usd_cents"] > 0, "separate_fee_cap_missing_or_zero")
    return _decision(state, "OWNER_EXACT_APPROVAL_REQUIRED")
```

`_decision` must always set `canary_authority=False`, `task27_authority=False`, `numeric_netreturn="FORBIDDEN"`, and `execution_action="NONE"`. `evaluate_exit_precondition` must accept only `LANDED_SUCCESS` with `reconciled=True`, `monitoring_healthy=True`, `inventory_match=True`, `allowlist_match=True`, and `fee_cap_ok=True`; it returns `EXIT_LEG_SHAPE_VALIDATED_NOT_AUTHORIZED`.

Model the config and contract around those constants. The fixture must be synthetic and include no public wallet address, token mint, real route, quote, signature, or secret. The schema must require `side_effect_counters` with six zero-valued counters matching TASK-26C.

- [ ] **Step 4: Generate and validate deterministic evidence**

Run:

```powershell
uv run --locked --managed-python python -c "from pathlib import Path; from solana_alpha_lab.owner_authority_packet_binding import write_outputs; print(write_outputs(Path('.')))"
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding -v
```

Expected: the receipt is canonical JSON, validates against the new schema, all synthetic cases match, and every authority counter is zero.

- [ ] **Step 5: Commit the self-contained offline contract slice**

```powershell
git add docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md docs/contracts/owner_authority_packet_binding_contract_v1.md configs/owner_authority_packet_binding_v1.yaml catalog/schemas/owner_authority_packet_binding.schema.json tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json src/solana_alpha_lab/owner_authority_packet_binding.py tests/test_owner_authority_packet_binding.py docs/evidence/owner_authority_packet_binding/a1_offline_packet_binding_acceptance_v1.json
git commit -m "feat: add owner authority packet binding contract"
```

## Task 2: Full Factory Fit receipt and Catalog transaction

**Files:**
- Create: `docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json`
- Create: `tests/test_owner_authority_packet_binding_catalog_factory_fit.py`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Regenerate: `catalog/generated/asset_edges.json`
- Regenerate: `docs/PROJECT_MAP.md`

**Interfaces:**
- Consumes: Task 1 receipt, config, schema, fixture, module and test hashes; TASK-26C Factory Fit receipt.
- Produces: ten registered assets: task doc, contract, config, schema, fixture, module, evaluator test, A1 evidence, A2 evidence, and A2 Catalog/Factory-Fit test.
- Invariant: the receipt verdict may be `PASS_WITH_FOLLOWUP`, but `canary_authority` and `task27_authority` remain false.

- [ ] **Step 1: Write failing Catalog/Factory-Fit tests**

```python
NEW_IDS = {
    "DOC-OWNER-AUTHORITY-PACKET-001",
    "CONTRACT-OWNER-AUTHORITY-PACKET-001",
    "CONFIG-OWNER-AUTHORITY-PACKET-001",
    "SCHEMA-OWNER-AUTHORITY-PACKET-001",
    "FIXTURE-OWNER-AUTHORITY-PACKET-001",
    "MODULE-OWNER-AUTHORITY-PACKET-001",
    "TEST-OWNER-AUTHORITY-PACKET-001",
    "EVIDENCE-OWNER-AUTHORITY-PACKET-A1-001",
    "EVIDENCE-OWNER-AUTHORITY-PACKET-A2-001",
    "TEST-OWNER-AUTHORITY-PACKET-A2-001",
}

def test_full_factory_fit_keeps_execution_forbidden() -> None:
    assert receipt["factory_fit"]["mode"] == "FULL_REVIEW"
    assert receipt["accepted_result"]["canary_authority"] is False
    assert receipt["accepted_result"]["task27_authority"] is False
    assert receipt["owner_packet"]["all_in_cash_at_risk_cap_usd_cents"] == 300
    assert receipt["owner_packet"]["status"] == "DRAFT_OWNER_INPUT_REQUIRED"
```

The test must recompute the receipt SHA-256 after removing `receipt_sha256`, assert every registered asset hash matches its physical file, require the generated navigation to list every new ID, and require a Product Horizon with exactly `now` and `watch`.

- [ ] **Step 2: Run the Catalog test before adding records**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding_catalog_factory_fit -v
```

Expected: FAIL because the receipt, registered IDs, and Catalog records do not exist.

- [ ] **Step 3: Add the deterministic Catalog and Factory-Fit receipt**

Create A2 with `FULL_REVIEW`, one durable NOW follow-up named
`EXACT_OWNER_PACKET_INPUT_AND_SEPARATE_CANARY_GATE`, and one WATCH item
`TASK-27_EXECUTION_TRUTH_EVALUATION`. State explicitly that the first item
requires owner inputs and a later separate authority; it is not an execution
task. Set all side-effect counters to zero.

In `core.yaml`, create the ten IDs above with `record_version: '1.0'`, exact
file SHA-256 values, `consumers: [OWNER_AUTHORITY_PACKET_BINDING_V1, FACTORY-001]`,
and these relations:

```yaml
- {relation_type: derived_from, target_asset_id: CONTRACT-T26C-OWNED-CANARY-READINESS-001}
- {relation_type: governed_by, target_asset_id: CONTRACT-OWNER-AUTHORITY-PACKET-001}
- {relation_type: validated_by, target_asset_id: TEST-OWNER-AUTHORITY-PACKET-001}
- {relation_type: produces, target_asset_id: EVIDENCE-OWNER-AUTHORITY-PACKET-A1-001}
```

Register the schema in `catalog_manifest.yaml`, increment the version and
checkpoint counts monotonically, add one lifecycle record with decision
`OFFLINE_OWNER_PACKET_READY_NO_EXECUTION_AUTHORITY`, then regenerate views:

```powershell
uv run --locked --managed-python python scripts/generate_navigation.py --write
```

- [ ] **Step 4: Validate the Catalog transaction**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding tests.test_owner_authority_packet_binding_catalog_factory_fit -v
uv run --locked --managed-python python scripts/generate_navigation.py --check
```

Expected: both suites pass; navigation is current; every receipt hash and asset hash agrees.

- [ ] **Step 5: Commit Catalog closure**

```powershell
git add docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json tests/test_owner_authority_packet_binding_catalog_factory_fit.py catalog/assets/core.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md
git commit -m "feat: register owner authority packet binding"
```

## Task 3: Bounded delivery and semantic acceptance

**Files:**
- Modify only if validation identifies a directly affected defect: files from Tasks 1–2.
- Do not create: wallet, signer, route provider, deployment, UI, Source bundle, or TASK-27 artifact.

**Interfaces:**
- Consumes: both local commits and deterministic receipts from Tasks 1–2.
- Produces: a clean, validated delivery candidate plus an exact no-side-effect report.
- Stop boundary: before any external provider, wallet, funding, transaction, merge, or Project Sources action.

- [ ] **Step 1: Inspect exact change scope**

Run:

```powershell
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --porcelain
```

Expected: only the design, plan, and Task 1–2 paths are changed; no local secret, wallet, or raw-data path appears.

- [ ] **Step 2: Run targeted and full delivery validation once**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding tests.test_owner_authority_packet_binding_catalog_factory_fit -v
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: targeted tests pass; tracked-only gate copies no ignored/local inputs and reports no new skip used to hide missing evidence.

- [ ] **Step 3: Produce the semantic acceptance checklist**

Verify all of the following against actual bytes before any push:

```text
packet states are draft/review only
cash cap is exactly USD 3.00 / 300 cents
all unknown input fields remain explicit
UNKNOWN blocks retry and exit
monitoring/inventory/route/cap failures block action
all side-effect counters are zero
canary_authority=false
task27_authority=false
no seed/private key/signed bytes/provider path exists
```

If any line fails, repair only the directly responsible Task 1–2 file, rerun its targeted test, then rerun the unchanged delivery gate only if the candidate fingerprint changed.

- [ ] **Step 4: Commit any validation repair, then push and open a draft PR**

Run only after the semantic checklist passes:

```powershell
git status --porcelain
git push -u origin owner-authority-packet-binding
gh pr create --draft --base main --head owner-authority-packet-binding --title "feat: bind owner authority packet offline" --body-file docs/superpowers/plans/2026-08-05-owner-authority-packet-binding.md
```

Expected: one draft PR with the exact head; stop before Ready/merge. The pull request description must state that the implementation grants no canary, wallet, signer, transaction, provider, cash, or TASK-27 authority.

## Plan self-review

- **Spec coverage:** Task 1 implements both packet states, the USD 3.00 cap, immediate-exit precondition, explicit missing inputs, schema, and adversarial cases. Task 2 implements Catalog, Factory Fit, Product Horizon, and durable no-authority evidence. Task 3 verifies exact scope and delivery without widening to external execution.
- **Placeholder scan:** no `TODO`, `TBD`, undefined interface, or implicit external action is present. `OWNER_INPUT_REQUIRED` is a deliberate runtime value, not a placeholder.
- **Type consistency:** Task 1 defines every module symbol used by its tests. Task 2 reads Task 1 hashes and receipt. Task 3 invokes only the two test modules and the repository’s existing validation commands.
