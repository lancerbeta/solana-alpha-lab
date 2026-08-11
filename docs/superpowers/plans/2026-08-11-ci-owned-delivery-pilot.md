# CI-Owned Delivery Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the duplicate local full-suite run from three eligible deliveries while preserving fail-closed local checks and making GitHub PR CI the sole clean-checkout/full-suite owner.

**Architecture:** Add one explicit `--ci-owned-delivery` mode to the existing validator. It inspects the exact committed candidate, rejects objectively high-risk validation/dependency/schema changes, enforces the existing new-test skip rule, and runs only focused security, Catalog, generated-view, architecture and hook checks. The unchanged GitHub pull-request workflow remains the only full clean-checkout/full-suite gate. This control patch is itself ineligible for the pilot and therefore ships once through the legacy tracked-only full gate.

**Tech Stack:** Python 3.13, `unittest`, existing repository validation scripts, Markdown policy, Catalog integrity bindings, GitHub Actions.

## Global Constraints

- Base: `origin/main` at `ccae84e369246a2d230ff6ee5c42d34cb6f07de8`.
- TASK-30 remains paused; no task status, hypothesis, data contract, provider route, Project Sources release or permanent-memory bundle changes.
- No provider/API/RPC/WSS call, credential, wallet, signer, transaction, cash, scheduler, deployment, dependency or workflow change.
- Pilot population: the next three eligible bounded offline/routine delivery candidates.
- Success: 3/3 first pushed heads pass PR CI and no clean-checkout/local-data repair is needed, with at least seven minutes saved per eligible delivery relative to the last tracked-only receipt.
- Roll back immediately to `--tracked-only-delivery` on any false admission, missed clean-checkout/local-data defect, first-head CI failure attributable to omitted local coverage, or local focused-gate wall time above 120 seconds.
- User-only reminders remain outside code: request authentication only if GitHub credentials fail; remind the owner about any Project Sources replacement/smoke only at the TASK-30 Finish Gate.

---

### Task 1: Specify the fail-closed CI-owned route in tests

**Files:**

- Modify: `tests/test_ci.py`
- Test: `tests/test_ci.py`

**Interfaces:**

- New CLI: `scripts/validate_ci.py --ci-owned-delivery --base-ref origin/main`
- New pure policy surface: candidate-path eligibility and focused child-command inventory.
- Existing invariant reused unchanged: `validate_new_test_skip_policy`.

- [ ] **Step 1: Add failing policy and parser tests**

Add tests that require:

1. an explicit mutually exclusive `--ci-owned-delivery` parser mode;
2. a repository policy section naming `GITHUB_PR_EXACT_HEAD_CI` as the sole full-suite owner, the three-delivery pilot, 120-second cap, success and rollback triggers;
3. ordinary TASK/config/test/Catalog/generated files to be eligible;
4. workflow, dependency/lock, validator/control-policy, schema/migration and validation-test changes to fail closed;
5. the focused command set to retain secret, baton, Catalog, generated navigation, pre-git import, TASK-04 architecture and hook checks while excluding the full `REPOSITORY_POLICY` suite.

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_ci -v
```

Expected: the new tests fail because the mode and policy do not exist; the 27 pre-existing tests remain green.

- [ ] **Step 2: Preserve exact negative evidence**

Record the failing test names/output in the implementation checkpoint. Do not weaken assertions to make the baseline pass.

---

### Task 2: Implement the focused exact-candidate preflight

**Files:**

- Modify: `scripts/validate_ci.py`
- Test: `tests/test_ci.py`

**Interfaces:**

- Receipt schema: `solana-alpha-lab.ci-owned-delivery-preflight.v1`.
- Receipt path: ignored `local/delivery_preflight/<candidate>.ci-owned.json`.
- Full validation owner: `GITHUB_PR_EXACT_HEAD_CI`, state `DELEGATED_PENDING` before push.

- [ ] **Step 1: Add constants and objective path exclusions**

Define the pilot ID, 120-second local cap, receipt schema/command, and a narrow denylist covering validation/workflow/dependency/schema/migration owners. The explicit CLI mode is the semantic assertion that the candidate is bounded offline/routine; ambiguous candidates fall back to the legacy route.

- [ ] **Step 2: Add focused command inventory**

Reuse existing scripts for secret rejection, baton policy, Catalog validation/resolution, generated navigation, pre-git import, TASK-04 architecture and hook configuration. Do not invoke `scripts/validate_baseline.py` or a full test discovery from this local mode.

The baton command uses its focused mode: it retains schemas, adversarial
fixtures, routing/templates, owner attention and offline/no-network checks, and
omits only the duplicate canonical Catalog hash sweep. Profiling measured that
sweep at 160.438 seconds while the existing optimized Catalog validator already
owns the same integrity invariant; after the split the complete focused gate
measured 20.999 seconds.

- [ ] **Step 3: Add exact-candidate execution and receipt**

Require a clean tracked worktree, resolve candidate commit/tree/base merge-base, enumerate changed paths, apply eligibility and new-test-skip checks, run focused commands with the existing runtime/lock/workflow static contracts, enforce the wall-time cap, and write a compact PASS/FAIL receipt in `finally`. Make no clean-checkout claim: PR CI owns that evidence.

- [ ] **Step 4: Make the mode explicit and exclusive**

Add `--ci-owned-delivery` to the existing mutually exclusive delivery-mode group and route it from `main()`.

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_ci -v
```

Expected: all CI policy tests pass.

---

### Task 3: Make the pilot unavoidable in existing policy owners

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`
- Modify: `catalog/assets/core.yaml`
- Modify via generator only: `catalog/catalog_manifest.yaml`
- Modify via generator only: `catalog/generated/asset_edges.json`
- Modify via generator only: `docs/PROJECT_MAP.md`
- Modify if its existing generated binding changes: `catalog/assets/lifecycle.yaml`
- Test: `tests/test_ci.py`

**Interfaces:**

- Entry condition: explicit bounded offline/routine classification plus machine eligibility PASS.
- Local owner: focused controls only.
- Full owner: exact-head pull-request CI.
- Fallback: `--tracked-only-delivery`.

- [ ] **Step 1: Update `AGENTS.md`**

Add the command and one `CI_OWNED_DELIVERY_PILOT` section adjacent to the current delivery policy. State the exact eligible population, deny/fallback rule, single full-gate ownership, PR-head and post-merge CI requirements, three-observation success rule and immediate rollback triggers. Amend `TRACKED_ONLY_DELIVERY_PREFLIGHT` and `VALIDATION_ECONOMY` only enough to route eligible candidates without ambiguity.

- [ ] **Step 2: Update the execution router consumer**

Mirror only the route choice and evidence ownership in `EXECUTION_ROUTER_PROTOCOL.md`; do not create another registry, status owner or owner prompt.

- [ ] **Step 3: Refresh existing Catalog bindings**

Bump only the existing records for changed durable files, bind their exact SHA-256 values, regenerate Catalog navigation, and stabilize the generated-view binding. Do not create a new asset ID.

Run:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
uv run --locked --managed-python python -B -m unittest tests.test_ci -v
git diff --check
```

Expected: Catalog and generated views are stable, the focused route is discoverable in both policy owners, and no workflow/dependency/Project Sources file changed.

---

### Task 4: Verify and deliver the control patch through the legacy gate

**Files:**

- Inspect: exact branch inventory only.
- Receipt outside Git: `local/delivery_preflight/<candidate>.json`.

- [ ] **Step 1: Run proportional targeted validation**

Run the changed policy suite plus direct Catalog and baton consumers. If broad baton tests exceed the targeted budget, run the exact CI/baton documentation-policy tests and let the one legacy full gate own complete discovery.

- [ ] **Step 2: Commit the exact bounded inventory**

Commit only the plan, validator, its tests, two policy owners and necessary existing Catalog/generated bindings.

- [ ] **Step 3: Run the legacy tracked-only gate once**

Because this patch changes the validator and validation policy, it is deliberately ineligible for its own new route.

Run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: exact committed clean clone, complete locked suite, compact ignored receipt, PASS within the existing 15-minute cap.

- [ ] **Step 4: Publish and read back**

Use the standing LOCAL_WORK_CODEX routine authority for non-force push, one Draft PR, exact-head CI read-back, review and merge only if the repository `OWNER_ATTENTION_GATE` returns `AUTONOMOUS`; otherwise stop at the exact owner-only action. Verify post-merge exact `main` and main CI. Do not claim TASK-30 DONE.

- [ ] **Step 5: Start prospective observation**

The next eligible delivery is observation 1/3. Each observation must retain the CI-owned receipt and PR/main CI evidence; no separate recurring report is created. The third successful Finish Radar keeps the path, while any rollback trigger immediately restores the legacy gate.
