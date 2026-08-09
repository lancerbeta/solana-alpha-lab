# CONTROL_ONLY_TASK_CLOSE_FAST_PATH_V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed local fast path for a prospective combined Project Sources activation-and-task-close transaction while retaining full exact-head PR CI and post-main CI.

**Architecture:** A versioned YAML policy defines one receipt-path pattern and a closed set of mutable Catalog/registry paths. A focused Python module classifies the Git diff and validates the combined owner terminal, active release binding, DONE semantics, zero-authority fields, and Factory Fit. `scripts/validate_ci.py` exposes the mode; any ineligible diff exits non-zero and explicitly routes to the existing tracked-only preflight.

**Tech Stack:** Python 3.13 stdlib, PyYAML, unittest, existing Catalog and navigation validators.

## Global Constraints

- Work only in branch `ctrl/task-close-fast-path-v1` based on exact main `0f7d4325e30b4b58929433af2d3d06b70b988b8b`.
- Do not modify existing receipts, Project Sources release payloads, task contracts, research modules, dependencies, hooks, or GitHub workflows.
- No provider/API/RPC/WSS, credential, R2/R3, wallet, signer, transaction, deployment, release, or cash action.
- The new path is prospective; TASK-28 remains immutable historical evidence.
- A fast-path failure is not waived: the operator must use `--tracked-only-delivery`.
- Exact-head PR CI is the only full-suite owner for an eligible fast-path candidate; exact-main post-merge CI remains mandatory.

---

### Task 1: Freeze policy and RED classification/receipt tests

**Files:**
- Create: `control/control_only_task_close_fast_path_v1.yaml`
- Create: `tests/test_control_only_task_close_fast_path.py`
- Test: `tests/test_control_only_task_close_fast_path.py`

**Interfaces:**
- Produces: policy keys `eligible_change_set`, `combined_receipt`, `validation`, `observation_window`, and `rollback_triggers`.
- Consumes later: `classify_change_set(changes, policy) -> Classification`, `validate_combined_receipt(receipt, registry, policy) -> set[str]`.

- [ ] **Step 1: Write the policy fixture**

Define the exact receipt regex `^docs/evidence/task(?P<task_key>[0-9]+[a-z]?)/[a-z0-9_]*project_sources_activation_and_task_close_acceptance_v[0-9]+\.json$`, exact mutable paths for registry/Catalog/generated consumers, one added receipt, no deletes/renames, the owner-terminal template `TASK{task_label}_SOURCE_SMOKE=PASS; OWNER_DONE_ACCEPTANCE`, zero-authority keys, PR/full-CI ownership, three-close observation window, and rollback triggers.

- [ ] **Step 2: Write failing tests before the module exists**

The tests import `scripts/control_only_task_close_fast_path.py` and assert:

```python
eligible = [
    ("A", "docs/evidence/task29/a4_project_sources_activation_and_task_close_acceptance_v1.json"),
    ("M", "docs/project_sources/release_registry_v1.yaml"),
    ("M", "catalog/assets/core.yaml"),
    ("M", "catalog/assets/lifecycle.yaml"),
    ("M", "catalog/catalog_manifest.yaml"),
    ("M", "catalog/generated/asset_edges.json"),
    ("M", "docs/PROJECT_MAP.md"),
]
self.assertTrue(module.classify_change_set(eligible, policy).eligible)
```

Add adversarial cases for product code, tests, schemas, workflows, release bytes, a second receipt, deletion, rename, missing registry, and an unexpected Catalog path. Add a synthetic TASK-29 receipt/registry pair that passes, then mutations that remove either owner clause, change manifest SHA, keep the release candidate-only, claim a next task, omit a zero-authority key, or use Factory Fit `FAIL`.

- [ ] **Step 3: Run RED and verify the expected failure**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_control_only_task_close_fast_path
```

Expected: import/file failure because `scripts/control_only_task_close_fast_path.py` does not exist. This is the required RED signal.

---

### Task 2: Implement the fail-closed classifier and focused local gate

**Files:**
- Create: `scripts/control_only_task_close_fast_path.py`
- Modify: `tests/test_control_only_task_close_fast_path.py`

**Interfaces:**
- Produces: immutable `Classification(eligible: bool, receipt_path: str | None, errors: tuple[str, ...])`.
- Produces: `classify_change_set`, `validate_combined_receipt`, `run_fast_path(base_ref="origin/main")`, and `main()`.
- Consumes: the versioned policy and current release registry.

- [ ] **Step 1: Implement the smallest pure classification surface**

Normalize paths to `/`, require status `A` only for exactly one matching receipt, require `M` for all other changed paths, and require registry plus every exact Catalog/generated path. Return stable error enums such as `FAST_PATH_CHANGED_PATH_FORBIDDEN`, `FAST_PATH_RECEIPT_COUNT_MISMATCH`, and `FAST_PATH_REQUIRED_PATH_MISSING`.

- [ ] **Step 2: Implement combined-receipt semantics**

Require exact task/release/manifest binding, active registry pointer, `OWNER_ATTESTATION`, smoke `PASS`, exact `owner_terminal` clauses, `task_status=DONE`, `canonical_task_done=true`, `next_task_selected=false`, all policy-named authority counters equal to zero, Factory Fit `PASS` or `PASS_WITH_LIMITATIONS`, and exact `ACTIVATION_RECEIPT` disposition.

- [ ] **Step 3: Run GREEN for pure tests**

Run the Task 1 unittest command. Expected: all cases PASS with no skips.

- [ ] **Step 4: Add and test the repository runner**

`run_fast_path` must require a clean tracked worktree, derive `merge-base <base-ref> HEAD`, parse `git diff --name-status`, classify before running checks, validate the discovered receipt/registry, then run:

```text
git diff --check <merge-base>..HEAD
python -B scripts/secret_scan.py --self-test --scan-repository
python -B scripts/validate_catalog.py
python -B scripts/generate_navigation.py --check
python -B -m unittest tests.test_project_sources_release_registry tests.test_control_only_task_close_fast_path
```

Extend tests with injected Git/command runners so a forbidden diff proves that no child validation command runs, while an eligible diff runs the exact ordered check set.

- [ ] **Step 5: Re-run GREEN**

Run the focused unittest module again. Expected: all cases PASS.

---

### Task 3: Wire the central CLI and make the workflow unavoidable

**Files:**
- Modify: `scripts/validate_ci.py`
- Modify: `tests/test_ci.py`
- Modify: `tests/test_project_sources_release_registry.py`
- Modify if the full gate proves checkpoint coupling: `tests/test_task28_permanent_sources_release.py`
- Modify: `AGENTS.md`
- Modify: `docs/project_sources/RELEASES.md`

**Interfaces:**
- Produces: `validate_ci.py --control-only-task-close --base-ref origin/main`.
- Preserves: `validate_ci.py` full gate and `--tracked-only-delivery` behavior.

- [ ] **Step 1: Add failing CLI and documentation tests**

Before production edits, assert `parse_args(["--control-only-task-close"])` selects the new mode, combining it with `--tracked-only-delivery` raises `SystemExit`, and AGENTS/RELEASES contain the exact command, closed-scope rule, CI ownership, fallback, combined terminal, and three-close observation rule. Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_ci tests.test_control_only_task_close_fast_path
```

Expected: FAIL because the option and documentation do not exist.

- [ ] **Step 2: Wire the CLI minimally**

Use an argparse mutually exclusive group. Import `run_fast_path` lazily only when the new mode is selected so ordinary full CI remains unchanged. Route `--base-ref` to both delivery modes.

- [ ] **Step 3: Remove current-active-release hard-coding**

Refactor `tests/test_project_sources_release_registry.py` to derive the current active release from `active_ui_release_id` and validate its receipt/Catalog hash generically. Keep explicit historical TASK-27/TASK-28 immutable-receipt assertions. Future fast-path closes must not require test edits.

If the full gate exposes an older task test that requires the global Catalog to remain at its historical exact version/count, retain the task's exact receipts and minimum checkpoint while replacing equality with a monotonic lower bound. This is a direct-consumer repair, not a waiver.

- [ ] **Step 4: Update operator contracts**

AGENTS must place the fast path immediately beside `TRACKED_ONLY_DELIVERY_PREFLIGHT` and state that classification failure falls back to the full preflight. RELEASES must make the combined terminal prospective and keep smoke and DONE as two separately validated facts.

- [ ] **Step 5: Run GREEN**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_ci tests.test_project_sources_release_registry tests.test_control_only_task_close_fast_path
```

Expected: all tests PASS with no new skips.

---

### Task 4: Register durable assets and validate the patch

**Files:**
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Regenerate: `catalog/generated/asset_edges.json`
- Regenerate: `docs/PROJECT_MAP.md`

**Interfaces:**
- Produces assets: `POLICY-TASK-CLOSE-FAST-PATH-001`, `SCRIPT-TASK-CLOSE-FAST-PATH-001`, `TEST-TASK-CLOSE-FAST-PATH-001`.
- Updates integrity bindings: `CTRL-AGENTS-001` and `CI-VALIDATOR-001`.

- [ ] **Step 1: Add Catalog and lifecycle records**

Register the policy, script, and test with truth owner `CTRL-TASK-CLOSE-FAST-PATH`, relationships `policy contains script`, `policy validated_by test`, and consumers `FACTORY-001` plus `LOCAL-WORK-CODEX`. Do not add a lifecycle record: the patch changes control plumbing, not a hypothesis, trial, strategy, bot, or decision lifecycle. Bump Catalog from `0.43.0 / 581 / 59` to `0.44.0 / 584 / 59`; schemas and queries stay unchanged.

- [ ] **Step 2: Regenerate navigation and refresh exact hashes**

Compute SHA-256 for changed/new durable assets, update Catalog bindings, run `scripts/generate_navigation.py --write`, refresh the generated-view hashes, and rerun until `--check` is stable.

- [ ] **Step 3: Run focused validation**

Run:

```text
git diff --check
uv run --locked --managed-python python -B -m unittest tests.test_ci tests.test_project_sources_release_registry tests.test_control_only_task_close_fast_path tests.test_catalog
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

Expected: all commands PASS with no new skips.

- [ ] **Step 4: Commit the exact implementation candidate**

Commit only the approved design/plan, policy, validator, focused tests/docs, and required Catalog/generated consumers. Inspect `git diff --name-status origin/main...HEAD` and reject any unrelated path.

- [ ] **Step 5: Run the normal tracked-only delivery preflight once**

This patch changes validation policy, so it is intentionally ineligible for its own fast path. Run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: exact-candidate PASS in an isolated tracked-only checkout. Do not run a duplicate ordinary full gate.

- [ ] **Step 6: Deliver and verify**

Non-force push the branch, create one PR, bind exact-head CI, apply `OWNER_ATTENTION_GATE`, ordinary-merge only on `AUTONOMOUS`, preserve the branch, then verify exact-main SHA/tree and post-merge CI. Factory Fit is `FULL_REVIEW`; the patch remains `PASS_WITH_LIMITATIONS` until three eligible closes pass the observation window.
