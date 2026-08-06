# CANARY_SPECIFICATION_ONLY_V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add a versioned, deterministic, offline-only draft specification for one possible future USD 3 technical canary without recording real owner values or creating execution authority.

**Architecture:** Reuse OWNER_AUTHORITY_PACKET_BINDING_V1 as the only evaluator and safety truth owner. Add declarative task/contract/configuration, a schema and synthetic negative fixture; tests inspect those tracked bytes directly. The task creates no runtime execution module, dependency, provider client, wallet material or real packet.

**Tech Stack:** Markdown, YAML, JSON Schema Draft 2020-12, JSON, Python standard-library unittest, existing PyYAML and jsonschema, existing Catalog generator and validators.

## Global Constraints

- Cash cap is exactly 300 USD cents.
- State is exactly DRAFT_OWNER_INPUT_REQUIRED; no ready or execution state is legal.
- canary_authority=false, task27_authority=false, numeric NetReturn is forbidden.
- Real wallet address, alias hash, token, program, route, quote, signature, provider endpoint and owner approval phrase never enter tracked files.
- Reuse OWNER_AUTHORITY_PACKET_BINDING_V1; add no execution module, dependency, provider/API/RPC/WSS, wallet, signer, transaction, simulation, send, cash or R3 action.
- local/, private/ and staging/ remain owner-only ignored paths and are not validation inputs.
- Generated Catalog files are updated only by the existing generator.

---

### Task 1: Tracked offline draft contract and deterministic safety test

**Files:**

- Create: docs/tasks/CANARY_SPECIFICATION_ONLY_V1.md
- Create: docs/contracts/canary_specification_only_contract_v1.md
- Create: configs/canary_specification_only_v1.yaml
- Create: catalog/schemas/canary_specification_only.schema.json
- Create: tests/fixtures/canary_specification_only/specification_negative_matrix_v1.json
- Create: tests/test_canary_specification_only.py

**Consumes:**

- docs/contracts/owner_authority_packet_binding_contract_v1.md
- configs/owner_authority_packet_binding_v1.yaml
- src/solana_alpha_lab/owner_authority_packet_binding.py

**Produces:** A declarative DRAFT_OWNER_INPUT_REQUIRED specification and one
static test that proves all safety invariants without real owner or market data.

- [ ] **Step 1: Write the failing static test**

Create the test using unittest, yaml and Draft202012Validator. It loads task,
contract, configuration, schema and fixture. It must assert:

    config["specification_state"] == "DRAFT_OWNER_INPUT_REQUIRED"
    config["cash_cap"]["total_cash_at_risk_usd_cents"] == 300
    config["authority"]["canary_authority"] is False
    config["authority"]["task27_authority"] is False
    config["authority"]["execution_action"] == "NONE"
    config["technical_wallet"]["public_address"] == "OWNER_LOCAL_ONLY"
    set(config["owner_input_required"]) == REQUIRED_OWNER_INPUTS

It also rejects secret/key/seed/signature patterns and concrete https://
provider endpoints while allowing the literal OWNER_LOCAL_ONLY.

- [ ] **Step 2: Verify the initial expected failure**

Run:

    uv run --locked --managed-python python -B tests/test_canary_specification_only.py

Expected: FAIL because the task/config/schema/fixture paths do not exist.

- [ ] **Step 3: Create the minimal declarative artifacts**

Write the task and contract to reference OWNER_AUTHORITY_PACKET_BINDING_V1 as
the safety truth owner and list all twelve required fields. Write configuration
with these exact values:

    specification_state: DRAFT_OWNER_INPUT_REQUIRED
    flow: SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT
    cash_cap.total_cash_at_risk_usd_cents: 300
    technical_wallet.alias: OWNER_LOCAL_ONLY
    technical_wallet.public_address: OWNER_LOCAL_ONLY
    technical_wallet.verification_hash: OWNER_LOCAL_ONLY
    authority.canary_authority: false
    authority.task27_authority: false
    authority.execution_action: NONE
    authority.numeric_netreturn: FORBIDDEN

All other owner fields appear only by name in owner_input_required. Create a
schema for A1 evidence with constants for task ID, state, flow, cap, authority
flags and zero side-effect counters. Create a fixture with six negative cases:
non-draft state, non-300 cap, missing owner field, true authority, non-zero
provider count and real wallet/endpoint text.

- [ ] **Step 4: Complete and run the static test**

Assert that fixture cases name exactly the six failure classes, task/contract
retain all non-claims and the schema validates the A1 receipt shape. Run the
Step 2 command again. Expected: PASS with no network, wallet, signer,
transaction or local-owner-file access.

- [ ] **Step 5: Commit the contract slice**

Stage exactly the six Task 1 files and commit with:

    git commit -m "feat: add offline canary specification contract"

### Task 2: Acceptance evidence, Catalog registration and Factory Fit

**Files:**

- Create: docs/evidence/canary_specification_only/a1_offline_specification_acceptance_v1.json
- Create: docs/evidence/canary_specification_only/a2_catalog_factory_fit_v1.json
- Create: tests/test_canary_specification_only_catalog_factory_fit.py
- Modify: tests/test_catalog.py
- Modify: catalog/assets/core.yaml
- Modify: catalog/assets/lifecycle.yaml
- Modify: catalog/catalog_manifest.yaml
- Modify: registries/decisions_negative_results.yaml
- Modify: catalog/generated/asset_edges.json
- Modify: docs/PROJECT_MAP.md

**Consumes:** Task 1 plus the existing Catalog generator and
DECISION-OWNER-AUTHORITY-PACKET-001.

**Produces:** Hash-bound A1 and A2 receipts, nine registered assets, one
lifecycle decision, Catalog 0.36.0, 553 assets, 14 schemas and 58 lifecycle
records.

- [ ] **Step 1: Write the failing Catalog/Factory Fit test**

Create a static test with this exact asset-ID set:

    DOC-CANARY-SPECIFICATION-ONLY-001
    CONTRACT-CANARY-SPECIFICATION-ONLY-001
    CONFIG-CANARY-SPECIFICATION-ONLY-001
    SCHEMA-CANARY-SPECIFICATION-ONLY-001
    FIXTURE-CANARY-SPECIFICATION-ONLY-001
    TEST-CANARY-SPECIFICATION-ONLY-001
    EVIDENCE-CANARY-SPECIFICATION-ONLY-A1-001
    EVIDENCE-CANARY-SPECIFICATION-ONLY-A2-001
    TEST-CANARY-SPECIFICATION-ONLY-A2-001

The test verifies A2 self-hash, FULL_REVIEW / PASS_WITH_FOLLOWUP, false/zero
authority counters, Catalog registrations, generated edges and Project Map.

- [ ] **Step 2: Verify the initial expected failure**

Run:

    uv run --locked --managed-python python -B tests/test_canary_specification_only_catalog_factory_fit.py

Expected: FAIL because receipts and asset records do not yet exist.

- [ ] **Step 3: Add deterministic receipts and lifecycle decision**

Write A1 with final SHA-256 bindings for Task 1 and the six negative cases.
Write A2 with FULL_REVIEW / PASS_WITH_FOLLOWUP, a NOW candidate limited to
owner-local input preparation and WATCH limited to a separate canary gate.
Both receipts record zero provider, wallet, signer, transaction, cash, R3 and
dependency counters.

Add DECISION-CANARY-SPECIFICATION-ONLY-001 with summary
OFFLINE_SPECIFICATION_READY_NO_EXECUTION_AUTHORITY.
Update tests/test_catalog.py so its exact expected
decisions_negative_results list also contains
DECISION-CANARY-SPECIFICATION-ONLY-001 after
DECISION-OWNER-AUTHORITY-PACKET-001.

- [ ] **Step 4: Register assets and regenerate navigation**

Add all nine asset records with final hashes, parent/validation relations and
CANARY-SPECIFICATION-ONLY-V1 plus FACTORY-001 consumers. Register the schema
and set Catalog checkpoint to version 0.36.0, assets 553, schemas 14 and
lifecycle records 58. Then run:

    uv run --locked --managed-python python -B scripts/generate_navigation.py --write
    uv run --locked --managed-python python -B scripts/validate_catalog.py

Expected: generated edges, Project Map and Catalog validate.

- [ ] **Step 5: Run both focused tests and commit**

Run both Task 1 and Task 2 test commands. Expected: PASS with no external
side effect. Stage Task 2 artifacts and generated outputs, then commit:

    git commit -m "feat: register offline canary specification"

### Task 3: Delivery validation and bounded review

**Files:**

- Modify only generated outputs from Task 2.
- Create ignored receipt only under local/delivery_preflight/.

**Consumes:** the two commits from Tasks 1–2.

**Produces:** exact tracked inventory, one tracked-only delivery preflight,
non-force branch push, one Draft PR and CI read-back.

- [ ] **Step 1: Verify the inventory**

Run:

    git status --short
    git diff --check origin/main...HEAD
    git diff --name-only origin/main...HEAD

Expected: only plan-listed tracked files and generated outputs; no local note,
real owner value or secret is staged.

- [ ] **Step 2: Run the delivery gate once**

Run:

    uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery

Expected: PASS in an isolated tracked-only checkout. Do not run a duplicate
ordinary full gate for unchanged bytes.

- [ ] **Step 3: Deliver and stop before merge**

Push the task branch non-force, open one Draft PR and read CI for the exact
head. Record changed files and zero-side-effect receipt. Do not merge.

- [ ] **Step 4: Finish only after semantic acceptance**

Run the Full Factory Fit review against the exact candidate. If it passes,
prepare a Source completion bundle. User UI replacement and final owner
acceptance remain separate and do not grant canary authority.

## Plan self-review

Task 1 enforces draft-only safety; Task 2 preserves Catalog, decision and
Factory Fit truth; Task 3 validates exact bytes and transport. No real owner
value, provider route or execution component is created. Every task names its
files, test command, expected result and delivery boundary.
