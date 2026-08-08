# T27 Exact Owner External-Read Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a synthetic-only owner review packet that can prepare a later exact public-history read decision without granting, performing or retaining any external read.

**Architecture:** The A6 packet is declarative. Markdown describes the owner decision and its non-claims; YAML freezes inherited A4 limits and placeholder rules; JSON Schema validates the review-packet shape; and one `unittest` module runs the fixture through both Schema and semantic fail-closed checks. The acceptance receipt content-binds the durable assets and declares that Project Sources do not change.

**Tech Stack:** Python 3.13, `unittest`, PyYAML, JSON Schema Draft 2020-12, JSON and YAML; no new dependencies.

## Global Constraints

- Base commit: `4d1c7577e193f5e2f6504a734061f6eb97787a6a`; branch: `task27/external-read-review`.
- Atom: `T27-A0-A6_EXACT_OWNER_EXTERNAL_READ_REVIEW_V1`.
- The only candidate source remains `GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`; no fallback provider.
- Inherited A4 maximums are 6 discovery reads, 24 OHLCV reads, 900-second interval, 24-hour panels and 12 complete panels minimum.
- A6 makes zero provider/API/RPC/WSS calls, reads zero R2/R3 values, retains zero raw provider responses, uses no credential, creates no wallet/signer/transaction and spends zero cash.
- A successful A6 review result keeps `provider_read_authority=false`; only a new exact owner instruction may later authorise a read.
- The current real pool, selection snapshot and raw-evidence manifest remain `OWNER_INPUT_REQUIRED`; a synthetic fixture never becomes a market target.
- No Catalog-root registration, Project Source/release mutation, dependency change, strategy, execution, PnL, NetReturn or cashflow claim belongs in this atom.

---

### Task 1: Add the failing behavioral contract test

**Files:**

- Create: `tests/test_task27_exact_owner_external_read_review_contract.py`

**Interfaces:**

- Consumes: four absent A6 durable artifacts and the later acceptance receipt.
- Produces: `semantic_errors(packet: dict[str, Any], policy: dict[str, Any]) -> set[str]`, used only within the test module to enforce observable review-packet behavior.

- [ ] **Step 1: Write the focused test before the artifacts exist**

Create a test module with these concrete path constants and an artifact-existence assertion:

```python
REQUIRED_PATHS = (
    ROOT / "docs/contracts/task27_exact_owner_external_read_review_contract_v1.md",
    ROOT / "configs/task27_exact_owner_external_read_review_contract_v1.yaml",
    ROOT / "catalog/schemas/task27_exact_owner_external_read_review.schema.json",
    ROOT / "tests/fixtures/task27/exact_owner_external_read_review_v1.json",
)

def test_required_review_assets_exist(self) -> None:
    for path in REQUIRED_PATHS:
        with self.subTest(path=path):
            self.assertTrue(path.is_file(), path)
```

The mutation table must use hand-derived expected errors:

```python
EXPECTED_ERRORS = {
    "AUTHORITY_PROMOTION_FORBIDDEN",
    "EXTERNAL_ACTION_IN_A6_FORBIDDEN",
    "RAW_RETENTION_IN_A6_FORBIDDEN",
    "SOURCE_SMOKE_BINDING_REQUIRED",
    "UNBOUND_FUTURE_REQUEST_FORBIDDEN",
    "ACTUAL_EVIDENCE_CLAIM_FORBIDDEN",
    "FALLBACK_PROVIDER_FORBIDDEN",
    "INHERITED_CAP_BREACH",
    "FORBIDDEN_DECISION_CLAIM",
    "PREMATURE_APPROVAL_PHRASE_FORBIDDEN",
}
```

- [ ] **Step 2: Prove RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_exact_owner_external_read_review_contract
```

Expected: `FAIL` because A6 contract/config/schema/fixture assets do not exist. Do not add implementation assets before this failure is observed.

- [ ] **Step 3: Commit the red test**

```text
git add tests/test_task27_exact_owner_external_read_review_contract.py
git commit -m "test: specify task27 external-read review guards"
```

### Task 2: Implement the smallest offline review contract

**Files:**

- Create: `docs/contracts/task27_exact_owner_external_read_review_contract_v1.md`
- Create: `configs/task27_exact_owner_external_read_review_contract_v1.yaml`
- Create: `catalog/schemas/task27_exact_owner_external_read_review.schema.json`
- Create: `tests/fixtures/task27/exact_owner_external_read_review_v1.json`
- Modify: `tests/test_task27_exact_owner_external_read_review_contract.py`

**Interfaces:**

- Consumes: A4 candidate source and its caps; A5R1 activation receipt binding; the red test from Task 1.
- Produces: a synthetic review packet with one valid result `READY_FOR_OWNER_EXTERNAL_READ_DECISION` and semantic evaluator `semantic_errors(packet, policy)`.

- [ ] **Step 1: Write the policy and human contract**

The YAML must freeze these values exactly:

```yaml
source_candidate: GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE
source_smoke:
  required_state: ACTIVATION_CONFIRMED_USER_SMOKE
  receipt_path: docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json
inherited_capture_caps:
  discovery_requests_max: 6
  ohlcv_requests_max: 24
  interval_seconds: 900
  panel_duration_hours: 24
  complete_panels_min: 12
authority:
  provider_api_rpc_wss_calls: 0
  provider_read_authority: false
  raw_provider_responses_retained: 0
review_outcomes:
  - READY_FOR_OWNER_EXTERNAL_READ_DECISION
  - REDESIGN_EXTERNAL_READ_PACKET
  - CLOSE_PUBLIC_HISTORY_ROUTE
```

The Markdown contract must state that `pool_identity`,
`selection_snapshot_id`, `selection_snapshot_sha256`, `selection_time`,
`universe_description` and `raw_evidence_manifest_id` are
`OWNER_INPUT_REQUIRED` before a later owner request; it must also state that a
future approval phrase is invalid until those values are exact and separately
owner-approved.

- [ ] **Step 2: Define a structural Schema and synthetic fixture**

The schema must require these packet blocks:

```json
["fixture_kind", "review", "inherited_capture", "authority", "claims", "future_owner_approval"]
```

The sole valid fixture packet must contain:

```json
{
  "fixture_kind": "SYNTHETIC_GOLDEN_ONLY",
  "review": {
    "outcome": "READY_FOR_OWNER_EXTERNAL_READ_DECISION",
    "source_smoke_state": "ACTIVATION_CONFIRMED_USER_SMOKE",
    "source_smoke_receipt_path": "docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json",
    "pool_identity": "OWNER_INPUT_REQUIRED"
  },
  "authority": {
    "provider_read_authority": false,
    "provider_api_rpc_wss_calls": 0,
    "raw_provider_responses_retained": 0
  },
  "claims": {"scope": "HISTORICAL_FEASIBILITY_ONLY"},
  "future_owner_approval": {"state": "TEMPLATE_INVALID_UNTIL_EXACT_OWNER_APPROVAL"}
}
```

All identifiers, hashes and examples must remain synthetic. The fixture must
not include a real pool address, endpoint, raw response, wallet or credential.

- [ ] **Step 3: Complete the real behavioral evaluator**

Implement `semantic_errors` in the focused test module. It must return each
literal Task 1 error when its corresponding fixture mutation occurs and an
empty set for the valid packet. Validate the fixture against the actual JSON
Schema before semantic evaluation. Use deep-copied fixture mutations, not
mocks or source-text assertions.

The evaluator must reject `provider_read_authority is True`; non-zero external
action or raw-retention counters; non-activation Source state or receipt path;
anything other than `OWNER_INPUT_REQUIRED` for the six future inputs; a
fallback source; caps larger than the YAML values; claim scopes other than
`HISTORICAL_FEASIBILITY_ONLY`; and an approval state other than
`TEMPLATE_INVALID_UNTIL_EXACT_OWNER_APPROVAL`.

- [ ] **Step 4: Prove GREEN**

Run the Task 1 command again.

Expected: the valid packet passes Schema and semantic checks, every one of the
ten adversarial mutations is rejected, and no test accesses a network or real
market datum.

- [ ] **Step 5: Review and commit the contract slice**

```text
git diff --check
git add docs/contracts/task27_exact_owner_external_read_review_contract_v1.md configs/task27_exact_owner_external_read_review_contract_v1.yaml catalog/schemas/task27_exact_owner_external_read_review.schema.json tests/fixtures/task27/exact_owner_external_read_review_v1.json tests/test_task27_exact_owner_external_read_review_contract.py
git commit -m "feat: add task27 external-read review packet"
```

### Task 3: Bind receipt, compatibility and delivery evidence

**Files:**

- Create: `docs/evidence/task27/a0a6_exact_owner_external_read_review_acceptance_v1.json`
- Modify: `tests/test_task27_exact_owner_external_read_review_contract.py`

**Interfaces:**

- Consumes: Task 2 files, their SHA-256 bindings and the repository Project Sources disposition policy.
- Produces: an acceptance receipt consumed by delivery review; it reports `STATE_CHANGE=NONE` and cannot confer external authority.

- [ ] **Step 1: Add the missing-receipt test and observe RED**

Add a test that verifies the receipt binds the four durable assets by path and
SHA-256, contains `project_sources_disposition.kind == "NO_CHANGE"`, reports
all zero external counters and leaves:

```python
self.assertFalse(receipt["next_boundary"]["provider_read_authority_granted"])
self.assertEqual(receipt["state_change"], "NONE")
```

Run the focused suite. Expected: `FAIL` because the receipt does not exist.

- [ ] **Step 2: Create the receipt from actual bytes**

Compute SHA-256 only after Task 2 is committed. The receipt must record the
focused command, actual test counts, the ten adversarial rejections and:

```json
"project_sources_disposition": {
  "kind": "NO_CHANGE",
  "reason": "A6 creates an offline review template only; no Project Source role or release payload changes."
}
```

It must have zero values for provider/API/RPC/WSS calls, R2/R3 reads,
wallet/signer/transaction actions, cash spend, raw retained responses,
dependency changes, Catalog/registry mutations and Project Source changes.

- [ ] **Step 3: Prove GREEN and predecessor compatibility**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_price_volume_research_screen_contract tests.test_task27_historical_collection_authority_contract tests.test_task27_bounded_public_history_feasibility_authority_contract tests.test_task27_exact_owner_external_read_review_contract tests.test_project_sources_release_registry
```

Expected: every suite passes; the new receipt satisfies the current
Project-Sources disposition invariant without changing Sources or the registry.

- [ ] **Step 4: Commit the evidence slice**

```text
git add docs/evidence/task27/a0a6_exact_owner_external_read_review_acceptance_v1.json tests/test_task27_exact_owner_external_read_review_contract.py
git commit -m "test: bind task27 external-read review receipt"
```

- [ ] **Step 5: Run the single tracked-only delivery gate**

Ensure the committed worktree is clean, then run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: an isolated full gate succeeds for this exact candidate. Its ignored
local receipt must not enter the delivery diff.

- [ ] **Step 6: Inspect, push and stop at the PR gate**

Inspect:

```text
git status --short
git diff --check 4d1c7577e193f5e2f6504a734061f6eb97787a6a..HEAD
git diff --name-only 4d1c7577e193f5e2f6504a734061f6eb97787a6a..HEAD
```

Then non-force push `task27/external-read-review`, create one Draft PR with
the zero-side-effect boundary in its description, and read CI for the exact
head. Stop before Ready/merge; only an explicit owner confirmation for that
exact PR and head may permit merge.

## Plan self-review

- **Spec coverage:** Task 1 establishes test-first behavior. Task 2 covers
  Source binding, inherited caps, placeholders, no-authority semantics,
  non-claims and adversarial checks. Task 3 binds real artifact hashes,
  Project Sources disposition, compatibility and delivery.
- **No placeholder scan:** every required future value is explicitly the
  product state `OWNER_INPUT_REQUIRED`, not an unfinished implementation
  marker; no engineering step contains a deferred action.
- **Type consistency:** every test uses `semantic_errors(packet, policy)`;
  the fixture names and receipt paths match the managed write set; the receipt
  uses the same `provider_read_authority_granted` boundary asserted by the
  test.
