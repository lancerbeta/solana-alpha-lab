# Project Sources Release Control v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the A5 source candidate the first registered, discoverable and
CI-validated Project Sources release without implying cloud activation.

**Architecture:** A small YAML registry is the only discovery surface for
repository-authored Project Sources releases.  The existing full-text A5
snapshot moves into its first immutable release directory.  A deterministic
unittest validates registry-to-payload bindings, lifecycle/pointer invariants,
and the explicit source-disposition field for acceptance receipts changed by a
pull request.

**Tech Stack:** Markdown, YAML, JSON Schema Draft 2020-12, Python `unittest`,
PyYAML, jsonschema, Git merge-base/diff, SHA-256, uv.

## Global Constraints

- Release ID is `PSR-0001-T27-A0-A5`; its status is
  `VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING`, never active.
- `active_ui_release_id` is `null`; prior cloud truth is
  `PRE_REGISTRY_EXTERNAL_STATE`, not a fabricated historical bundle.
- There may be at most one candidate and at most one repository-tracked active
  release.
- The moved bundle retains exactly five mutable roles and binds two immutable
  roles by their existing SHA-256 values.
- Changed task acceptance receipts declare exactly one of `NO_CHANGE`,
  `RELEASE_CANDIDATE`, or `ACTIVATION_RECEIPT`.
- No Project Sources UI action, provider/API/RPC/WSS call, credential, R2/R3
  value read, wallet, signer, transaction, cash, dependency or Catalog-root
  action is allowed.
- Existing historical receipts remain compatible; only receipts changed after
  `enforcement_start_commit` are subject to the new field. On normal future
  pull requests this resolves to the pull-request merge base.

---

### Task 1: Write the failing release-registry invariant test

**Files:**
- Create: `tests/test_project_sources_release_registry.py`

**Interfaces:**
- Consumes: repository root, the A5 bundle path, its acceptance receipt and
  the Git merge base against `origin/main`.
- Produces: deterministic failures for absent registry, unregistered release,
  invalid pointers/lifecycle, hash drift and a changed acceptance receipt
  without a source disposition.

- [ ] **Step 1: Add a test that requires a registry-backed A5 release**

```python
def test_first_release_is_registered_and_pending_not_active(self) -> None:
    registry = load_yaml(REGISTRY_PATH)
    release = release_by_id(registry, "PSR-0001-T27-A0-A5")
    self.assertIsNone(registry["active_ui_release_id"])
    self.assertEqual(registry["latest_candidate_release_id"], release["release_id"])
    self.assertEqual(release["status"], "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING")
    self.assertTrue((ROOT / release["bundle_path"] / "canonical_manifest.yaml").exists())
```

- [ ] **Step 2: Run the test before creating the registry**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_project_sources_release_registry
```

Expected: `FAIL` because `docs/project_sources/release_registry_v1.yaml` and
the registered `PSR-0001-T27-A0-A5` payload do not yet exist.

- [ ] **Step 3: Add adversarial invariants to the same test module**

```python
def test_registry_rejects_unregistered_payload_and_two_candidates(self) -> None:
    self.assertIn("UNREGISTERED_RELEASE_PAYLOAD", semantic_errors(unregistered_registry()))
    self.assertIn("MULTIPLE_CANDIDATES", semantic_errors(two_candidate_registry()))

def test_changed_acceptance_requires_explicit_disposition(self) -> None:
    receipt = load_json(A5_RECEIPT_PATH)
    del receipt["project_sources_disposition"]
    self.assertIn("SOURCE_DISPOSITION_REQUIRED", acceptance_errors(receipt))
```

- [ ] **Step 4: Re-run the focused test and confirm it remains red for the
missing first release**

Expected: fail from the absent registry/release, rather than an import or
syntax error.

### Task 2: Implement the first release and authoritative discovery surface

**Files:**
- Create: `docs/project_sources/RELEASES.md`
- Create: `docs/project_sources/release_registry_v1.yaml`
- Create: `catalog/schemas/project_sources_release_registry.schema.json`
- Rename: `docs/source_bundles/task27_a0a5_permanent_sources_v1/` to
  `docs/project_sources/releases/PSR-0001-T27-A0-A5/`
- Modify: `docs/contracts/task27_permanent_sources_reconciliation_contract_v1.md`
- Modify: `configs/task27_permanent_sources_reconciliation_contract_v1.yaml`
- Modify: `docs/evidence/task27/a0a5_permanent_sources_reconciliation_acceptance_v1.json`
- Modify: `tests/test_task27_permanent_sources_reconciliation_contract.py`

**Interfaces:**
- Consumes: the existing five-role A5 payload and checksums.
- Produces: one registry entry binding the release path, manifest, checksums,
  release status, source-role set and next owner action.

- [ ] **Step 1: Move the exact A5 bytes with Git history preserved**

Use `git mv` for the full directory.  Do not edit the five Source role files,
checksums or smoke prompt while moving them.

- [ ] **Step 2: Create the registry and reader guide**

The registry must contain `registry_version: 1`,
`active_ui_release_id: null`,
`active_ui_state: PRE_REGISTRY_EXTERNAL_STATE`,
`latest_candidate_release_id: PSR-0001-T27-A0-A5`, the 50 MiB review trigger,
and one release entry whose manifest/checksum SHA-256 values match the moved
bytes.  The guide must state that cloud activation requires a separate owner
smoke and that the registry is the only starting point for discovery.

- [ ] **Step 3: Bind the existing A5 contract and receipt to the release ID**

Add `project_sources_disposition` to the A5 receipt with:

```json
{
  "kind": "RELEASE_CANDIDATE",
  "release_id": "PSR-0001-T27-A0-A5",
  "registry_path": "docs/project_sources/release_registry_v1.yaml"
}
```

Update every affected path/hash binding after the `git mv`; retain
`UI_ACTIVATION_PENDING` and all zero-side-effect claims.

- [ ] **Step 4: Run focused tests to verify green**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_project_sources_release_registry tests.test_task27_permanent_sources_reconciliation_contract
```

Expected: both modules pass; release and A5 receipt hashes bind to the moved
files, and the candidate is not claimed active.

### Task 3: Make release disposition unavoidable at the delivery gate

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`
- Modify: `catalog/assets/core.yaml`, `catalog/assets/lifecycle.yaml`
- Regenerate/check: `docs/PROJECT_MAP.md`, `catalog/generated/asset_edges.json`
- Modify: `tests/test_project_sources_release_registry.py`
- Modify: `docs/superpowers/plans/2026-08-08-task27-sources-reconciliation-and-smoke.md`

**Interfaces:**
- Consumes: registry lifecycle rules and PR merge-base diff.
- Produces: a fail-closed validation rule for changed acceptance receipts and
  unambiguous operating instructions for future tasks.

- [ ] **Step 1: Add the failing changed-receipt and release-diff cases**

The test must reject a changed receipt with no disposition, a `NO_CHANGE`
receipt paired with a release-directory/registry change, and a
`RELEASE_CANDIDATE` receipt whose ID is absent or not the registry candidate.

- [ ] **Step 2: Implement the minimal merge-base diff validator in the test**

Resolve the merge base against `origin/main`. When the policy commit predates
that base, use the PR merge base; otherwise use the registry's
`enforcement_start_commit`. If neither is reachable, fail with
`MERGE_BASE_UNAVAILABLE` or `ENFORCEMENT_START_UNREACHABLE`. Only acceptance
receipts changed after that baseline are evaluated; compare the working tree
to that baseline so the rule is also exercised before commit.

- [ ] **Step 3: Replace the obsolete outside-Git rule and add Entry/Finish
Gate instructions**

`AGENTS.md` must distinguish repository-tracked release candidates from cloud
UI activation.  The router protocol must require a registry read at Entry Gate
and one explicit disposition at Finish Gate.  Update the earlier A5 plan so
its recorded path is no longer stale. Propagate the changed control-document
hashes, versions and purposes to their existing Catalog asset records, then
regenerate the Catalog navigation views.

- [ ] **Step 4: Run the complete release-control and T27 compatibility set**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_project_sources_release_registry tests.test_task27_price_volume_research_screen_contract tests.test_task27_historical_collection_authority_contract tests.test_task27_bounded_public_history_feasibility_authority_contract tests.test_task27_permanent_sources_reconciliation_contract
```

Expected: all tests pass and no external authority becomes true.

- [ ] **Step 5: Commit the bounded patch and execute delivery evidence**

Run `git diff --check`, the tracked-only delivery preflight and the repository
full validation gate on the exact commit.  Non-force push the existing branch,
read back the exact PR head and CI, and stop before Ready or merge.

## Plan self-review

- Spec coverage: registry discovery, first-release move, distinct active versus
  candidate pointers, legacy non-fabrication, explicit disposition, CI
  invariants, no-delete/50 MiB trigger, protocol repair and A5 hash rebinding
  map to Tasks 1–3.
- Placeholder scan: no unfinished markers, generic validation instructions or
  cross-task references remain.
- Interface consistency: every test and operating rule uses the same release
  ID, three disposition kinds and pending-candidate status.

## Execution route

The owner already selected inline execution for this bounded PR and approved
the release-control design.  Execute Tasks 1–3 in this worktree; do not create
subagents, a new PR or a merge action.
