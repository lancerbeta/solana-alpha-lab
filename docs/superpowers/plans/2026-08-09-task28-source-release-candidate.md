# TASK-28 A3 Project Sources Release Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare one hash-bound TASK-28 Source release candidate from the active TASK-27 release without changing cloud Sources or granting research authority.

**Architecture:** `PSR-0002-T27-CLOSE` is the immutable active-base reference. `PSR-0003-T28-RC001-FREEZE` carries five new mutable Source roles and two retained immutable role hashes. The release registry continues to declare PSR-0002 active and points `latest_candidate_release_id` only to PSR-0003 until a separate owner smoke is reported.

**Tech Stack:** Repository Markdown/YAML/JSON, SHA-256, existing Project Sources release-registry validator, locked Python unittest and Catalog generator.

## Global Constraints

- Base: `origin/main` `3c51f02babc072cc5e202a8b15de49e874e9a529`.
- Keep Operating System v8.5 and Research Blueprint v2.3 byte-for-byte unchanged.
- Do not overwrite, delete, or alter PSR-0001 or PSR-0002 release bytes.
- Do not call a provider/API/RPC/WSS endpoint, use credentials, touch R2/R3, create/connect a wallet, build/sign/send a transaction, spend cash, change dependencies, deploy, alter repository settings, or replace cloud Sources.
- Candidate status is `VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING`; activation occurs only after owner UI replacement plus the exact seven-role smoke.
- Preserve TASK-28 truth: all RC-001 groups remain `BLOCKED_DATA`; trials and holdouts remain zero; no alpha, fill, fee, settlement or numeric NetReturn claim is introduced.

---

### Task 1: Lock the candidate/activation boundary in a failing test

**Files:**
- Create: `tests/test_task28_permanent_sources_release.py`
- Read only: `docs/project_sources/release_registry_v1.yaml`
- Read only: `docs/project_sources/releases/PSR-0002-T27-CLOSE/`

**Interfaces:**
- Consumes: release-registry semantic rules and PSR-0002 active-source bindings.
- Produces: deterministic assertions for one PSR-0003 candidate, five mutable files, two immutable hashes, receipt bindings and the smoke contract.

- [ ] **Step 1: Write the failing candidate test**

```python
def test_task28_candidate_is_registered_without_replacing_active_psr0002() -> None:
    registry = load_yaml(REGISTRY_PATH)
    candidate = release_by_id(registry, "PSR-0003-T28-RC001-FREEZE")
    assert registry["active_ui_release_id"] == "PSR-0002-T27-CLOSE"
    assert registry["latest_candidate_release_id"] == candidate["release_id"]
    assert candidate["status"] == "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_permanent_sources_release
```

Expected: FAIL because PSR-0003 and its receipt do not exist.

### Task 2: Build the candidate and its hash-bound receipt

**Files:**
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/canonical_manifest.yaml`
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/roadmap.md`
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/current_system_state.md`
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/task_archive_P0_P1_v39.md`
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/task_28_rc001_registry_freeze.md`
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/CHECKSUMS_SHA256.txt`
- Create: `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/FRESH_CHAT_SMOKE.md`
- Create: `docs/evidence/task28/a3_permanent_sources_release_candidate_acceptance_v1.json`
- Modify: `docs/project_sources/release_registry_v1.yaml`
- Modify: `tests/test_task28_permanent_sources_release.py`

**Interfaces:**
- Consumes: PSR-0002 exact five-role contents, TASK-28 merge commit/tree/main CI, immutable Source hashes and TASK‑28 A1/A2 receipts.
- Produces: exactly one unactivated PSR-0003 release candidate and a receipt whose `project_sources_disposition` is `RELEASE_CANDIDATE`.

- [ ] **Step 1: Copy the active five-role source baseline without altering it**

Copy only the five mutable PSR-0002 files into the new release directory, then make forward-only edits in the copies. Do not copy or modify the two immutable cloud Sources; their known SHA-256 values remain manifest/registry bindings.

- [ ] **Step 2: Write the TASK-28 source delta**

Set manifest/roadmap to `4.9`, state to `4.5`, archive to `39.0`, and active task to `TASK-28 / 1.0`. Record the exact repository delivery:

```text
feature_head=7be75652ebe8ec9d867148ad42bae2320acc067d
main_commit=3c51f02babc072cc5e202a8b15de49e874e9a529
main_tree=5e15f19ae2b5ed1f33dc900c140c80771015e643
main_ci_run=31284090722 SUCCESS
```

The only decision is a frozen offline RC-001 register: `BLOCKED_DATA=3`,
`trial_records_created=0`, `holdouts_consumed=0`, external authority false.

- [ ] **Step 3: Generate immutable checksums and the owner smoke prompt**

`CHECKSUMS_SHA256.txt` contains exactly five candidate file hashes plus the manifest hash. `FRESH_CHAT_SMOKE.md` directs replacement of only five roles, preservation of the two immutable roles, role/version/header/hash reporting, and exact terminal lines:

```text
TASK28_SOURCE_SMOKE=PASS|FAIL;
provider_read_authority=false;
wallet/signer/transaction/cash_authority=false;
next_task_selected=false;
STATE_CHANGE=NONE;
side_effects=0.
```

- [ ] **Step 4: Add the registry record and receipt**

Keep PSR-0002 `ACTIVATED_BY_OWNER_SMOKE`; set only
`latest_candidate_release_id: PSR-0003-T28-RC001-FREEZE`. New PSR-0003 has no
activation receipt, supersedes PSR-0002 conceptually but does not mark it
superseded before future owner smoke. Bind manifest/checksum hashes and create
a TASK-28 A3 receipt with zero external side-effect counters.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_permanent_sources_release tests.test_project_sources_release_registry
```

Expected: PASS; one active PSR-0002, one candidate PSR-0003, exact files and hashes, no cloud-activation claim.

### Task 3: Register, validate and deliver the closure candidate

**Files:**
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`
- Modify: `tests/test_task28_permanent_sources_release.py`

**Interfaces:**
- Consumes: A3 receipt and PSR-0003 release bindings.
- Produces: Catalog discoverability for the finalization receipt and exact generated views.

- [ ] **Step 1: Add the failing Catalog receipt assertion**

```python
def test_catalog_binds_task28_source_candidate_receipt() -> None:
    asset = catalog_assets()["EVIDENCE-T28-A3-SOURCES-RELEASE-001"]
    assert asset["location"]["repository_path"] == "docs/evidence/task28/a3_permanent_sources_release_candidate_acceptance_v1.json"
    assert asset["integrity"]["sha256"] == sha256(A3_RECEIPT_PATH)
```

- [ ] **Step 2: Run the assertion and verify RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_permanent_sources_release.Task28PermanentSourcesReleaseTests.test_catalog_binds_task28_source_candidate_receipt
```

Expected: FAIL because the A3 Catalog asset does not exist.

- [ ] **Step 3: Add the one Catalog asset and reconcile generated views**

Register only `EVIDENCE-T28-A3-SOURCES-RELEASE-001`, with TASK-28 ownership,
the receipt SHA-256, a relation to `EVIDENCE-T28-A2-CATALOG-FACTORY-FIT-001`,
and consumers `TASK-28`, `FACTORY-001`, and `CHATGPT-PROJECT-CONTROL-PLANE`.
Increment actual Catalog counts, update generated-file hashes in lifecycle
metadata, and run:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

- [ ] **Step 4: Run full validation, inspect scope and deliver**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task28_permanent_sources_release tests.test_project_sources_release_registry tests.test_task28_rc001_registry_freeze
uv run --locked --managed-python python -B -m unittest discover -s tests -p test_*.py
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Commit only the listed TASK-28 A3 files, non-force push, create a Draft PR,
read back exact-head CI, apply `OWNER_ATTENTION_GATE`, merge only if it returns
`AUTONOMOUS`, then verify exact main and main CI. Do not delete the feature
branch. Stop before cloud UI replacement.

## Plan self-review

- Coverage: candidate base, mutable/immutable boundary, registry semantics,
  receipt, smoke, Catalog, tests, delivery and owner-only activation are each
  assigned.
- Placeholder scan: no deferred implementation or unbound file path remains.
- Consistency: all source paths use PSR-0003 and all activation claims remain
  outside this implementation.
