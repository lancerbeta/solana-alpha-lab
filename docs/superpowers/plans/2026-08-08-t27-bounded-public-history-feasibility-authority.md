# T27 Bounded Public-History Feasibility Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate an offline-only authority packet that can prepare, but never grant, a future owner review of a capped public historical price/volume feasibility capture.

**Architecture:** The packet is declarative: a Markdown contract explains the decision boundary, YAML freezes the machine-readable policy, JSON Schema rejects malformed synthetic packets, and one focused Python test module enforces semantic invariants that Schema cannot express. An acceptance receipt content-binds the four durable artifacts and records only zero external side effects.

**Tech Stack:** Python 3.13, `unittest`, PyYAML, JSON Schema Draft 2020-12, JSON and YAML; no new dependencies.

## Global Constraints

- Base commit: `1703a991a7b3a1ab2ef456a17cc04fe27bdb2429`; branch: `task27/bounded-history-authority`.
- Atom: `T27-A0-A4_BOUNDED_PUBLIC_HISTORY_FEASIBILITY_AUTHORITY_PACKET_V1`.
- Exactly one source candidate: `GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`; no fallback provider.
- Future caps: discovery reads `<= 6`, OHLCV reads `<= 24`, interval `900` seconds, `24` hours per panel, at least `12` complete panels.
- The packet makes zero provider/API/RPC/WSS calls, reads zero R2/R3 values, creates no wallet/signer/transaction, spends zero cash and retains zero real raw response.
- `READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW` means only that a separate owner request may be formulated; `provider_read_authority=false` remains mandatory.
- A missing availability proof makes history `DESCRIPTIVE_ONLY`, never PIT-admissible, zero or flat.
- A missing Project Sources activation receipt yields `SOURCE_ALIGNMENT_REQUIRED`; it cannot yield `READY`.
- No Catalog-root registration, Project Source mutation, dependency change or strategy/execution/NetReturn claim belongs in this atom.

---

### Task 1: Freeze the packet contract with synthetic adversarial acceptance

**Files:**

- Create: `docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md`
- Create: `configs/task27_bounded_public_history_feasibility_authority_contract_v1.yaml`
- Create: `catalog/schemas/task27_bounded_public_history_feasibility_authority.schema.json`
- Create: `tests/fixtures/task27/bounded_public_history_feasibility_authority_v1.json`
- Create: `tests/test_task27_bounded_public_history_feasibility_authority_contract.py`

**Interfaces:**

- Consumes: T27 A2 research-screen and A3 collection-authority contracts.
- Produces: `semantic_errors(packet: dict[str, Any]) -> set[str]`, a synthetic fixture whose valid packet has `source_binding.state = ACTIVATION_CONFIRMED_USER_SMOKE`, and contract/config/schema files consumed by the final receipt.

- [ ] **Step 1: Write the failing focused test**

Create `tests/test_task27_bounded_public_history_feasibility_authority_contract.py` with path constants for the four new durable artifacts and a first test that requires all four to exist:

```python
def test_all_required_contract_artifacts_exist(self) -> None:
    for path in REQUIRED_PATHS:
        with self.subTest(path=path):
            self.assertTrue(path.exists(), path)
```

Add test cases whose expected semantic errors are exactly:

```python
EXPECTED_ADVERSARIAL_ERRORS = {
    "SOURCE_ALIGNMENT_REQUIRED",
    "DISCOVERY_CAP_EXCEEDED",
    "OHLCV_CAP_EXCEEDED",
    "INSUFFICIENT_COMPLETE_PANELS",
    "UNFROZEN_SELECTION_SNAPSHOT",
    "AUTO_FALLBACK_PROVIDER_FORBIDDEN",
    "RAW_EVIDENCE_MANIFEST_REQUIRED",
    "PIT_CLAIM_WITHOUT_AVAILABILITY_PROOF",
    "FORBIDDEN_CLAIM_SCOPE",
    "EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN",
}
```

- [ ] **Step 2: Run the test and observe the expected RED failure**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_bounded_public_history_feasibility_authority_contract
```

Expected: `FAIL` because the new contract/config/schema/fixture paths do not yet exist. Do not continue if the test passes before the artifacts exist.

- [ ] **Step 3: Create the Markdown and YAML policy**

Write the contract and config with these exact semantic elements:

```yaml
source_candidate: GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE
decision_outcomes:
  - READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW
  - REDESIGN
  - CLOSE_DATA_ROUTE
source_binding:
  required_ready_state: ACTIVATION_CONFIRMED_USER_SMOKE
  nonready_state: SOURCE_ALIGNMENT_REQUIRED
authority:
  provider_api_rpc_wss_calls: 0
  provider_read_authority: false
  credential_use: false
  raw_provider_responses_retained: 0
```

The Markdown contract must state: `READY` is a review-readiness result only;
no GET request is made or authorised; any subsequent capture needs a new exact
owner instruction.

- [ ] **Step 4: Create Schema and fixture**

Define a Draft 2020-12 fixture schema with `fixture_kind` fixed to
`SYNTHETIC_GOLDEN_ONLY`, at least one valid packet and an adversarial-case
array. Require the packet blocks `proposal`, `evidence`, `retention`,
`source_binding` and `decision`.

The valid synthetic packet must have:

```json
{
  "source_binding": {
    "state": "ACTIVATION_CONFIRMED_USER_SMOKE",
    "receipt_reference": "synthetic-seven-role-source-smoke-001"
  },
  "evidence": {
    "grade": "DESCRIPTIVE_ONLY",
    "availability_proof": null,
    "raw_evidence_manifest_id": "synthetic-raw-manifest-001"
  },
  "decision": {
    "outcome": "READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW",
    "claim_scope": "HISTORICAL_FEASIBILITY_ONLY",
    "provider_read_authority": false
  }
}
```

The fixture's ten mutations must each target exactly one listed expected error.
All IDs, hashes and receipt references remain synthetic; do not use a real
pool, URL, wallet, provider response or Source smoke value.

- [ ] **Step 5: Implement only the semantic checker required by the tests**

Implement `apply_json_pointer`, `sha256`, and `semantic_errors` inside the
test module. The semantic checker must add `SOURCE_ALIGNMENT_REQUIRED` when
the source state is not `ACTIVATION_CONFIRMED_USER_SMOKE`; add
`EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN` whenever
`decision.provider_read_authority` is true; and enforce the nine remaining
errors listed above.

Keep the checker local to the test module: A4 creates a frozen contract, not
a reusable runtime service.

- [ ] **Step 6: Run the focused test and observe GREEN**

Run the Step 2 command again.

Expected: all structural, synthetic-only and semantic tests pass. Confirm
that every adversarial mutation is rejected and no test touches network,
credentials, files outside the managed write set or real market data.

- [ ] **Step 7: Review only the Task 1 diff**

Run:

```text
git diff --check
git diff -- docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md configs/task27_bounded_public_history_feasibility_authority_contract_v1.yaml catalog/schemas/task27_bounded_public_history_feasibility_authority.schema.json tests/fixtures/task27/bounded_public_history_feasibility_authority_v1.json tests/test_task27_bounded_public_history_feasibility_authority_contract.py
```

Expected: no whitespace errors; no external URL, credentials, wallet material,
real Source smoke binding or authority promotion.

- [ ] **Step 8: Commit the contract slice**

```text
git add docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md configs/task27_bounded_public_history_feasibility_authority_contract_v1.yaml catalog/schemas/task27_bounded_public_history_feasibility_authority.schema.json tests/fixtures/task27/bounded_public_history_feasibility_authority_v1.json tests/test_task27_bounded_public_history_feasibility_authority_contract.py
git commit -m "feat: freeze task27 public history authority packet"
```

### Task 2: Bind the acceptance receipt and deliver the offline candidate

**Files:**

- Create: `docs/evidence/task27/a0a4_bounded_public_history_feasibility_authority_acceptance_v1.json`
- Modify: `tests/test_task27_bounded_public_history_feasibility_authority_contract.py`

**Interfaces:**

- Consumes: the four Task 1 durable artifacts and their SHA-256 values.
- Produces: one receipt asserting targeted validation and zero side effects;
  future delivery and owner review consume this receipt.

- [ ] **Step 1: Add the failing receipt-binding test**

Add a test that expects the receipt to bind each durable file by repository
relative path and SHA-256, report the final focused test count, report ten
adversarial rejections, preserve `state_change = "NONE"`, and state:

```python
self.assertFalse(receipt["next_boundary"]["provider_read_authority_granted"])
self.assertTrue(receipt["next_boundary"]["requires_fresh_source_smoke_before_external_request"])
```

- [ ] **Step 2: Run the focused test and observe RED**

Run the Task 1 test command.

Expected: `FAIL` because the A4 acceptance receipt is absent.

- [ ] **Step 3: Create the acceptance receipt from actual local artifacts**

Populate the receipt only after calculating SHA-256 from the Task 1 files.
Record the exact targeted command, actual test counts, managed write set,
semantic acceptance outcomes and all zero counters:

```json
"measured_boundary": {
  "provider_api_rpc_wss_calls": 0,
  "r2_value_reads": 0,
  "r3_value_or_path_reads": 0,
  "wallet_signer_transaction_actions": 0,
  "cash_spend_usd_cents": 0,
  "raw_provider_responses_retained": 0,
  "project_source_changes": 0
}
```

The receipt must name no real Source smoke, no external endpoint and no
actual provider activity.

- [ ] **Step 4: Run the focused test and observe GREEN**

Run the Task 1 command again.

Expected: all tests pass, artifact hashes match, and the receipt remains
offline-only.

- [ ] **Step 5: Run direct predecessor compatibility tests**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_price_volume_research_screen_contract tests.test_task27_historical_collection_authority_contract tests.test_task27_bounded_public_history_feasibility_authority_contract
```

Expected: all three contract suites pass; A4 does not alter A2/A3 semantics.

- [ ] **Step 6: Commit the receipt slice**

```text
git add docs/evidence/task27/a0a4_bounded_public_history_feasibility_authority_acceptance_v1.json tests/test_task27_bounded_public_history_feasibility_authority_contract.py
git commit -m "test: bind task27 public history authority receipt"
```

- [ ] **Step 7: Perform one exact delivery gate**

Before the first push, ensure the committed worktree is clean and run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: one isolated tracked-only full validation for the exact candidate;
the receipt remains ignored under `local/delivery_preflight/` and is not
added to the delivery diff.

- [ ] **Step 8: Inspect the committed delivery inventory**

Run:

```text
git status --short
git log --oneline 1703a991a7b3a1ab2ef456a17cc04fe27bdb2429..HEAD
git diff --check 1703a991a7b3a1ab2ef456a17cc04fe27bdb2429..HEAD
git diff --name-only 1703a991a7b3a1ab2ef456a17cc04fe27bdb2429..HEAD
```

Expected: only the design, plan, five Task 1 artifacts and Task 2 receipt are
present; no generated Catalog changes, Source changes, raw data or secret
material.

- [ ] **Step 9: Push, create one Draft PR and read CI**

Push non-force to `task27/bounded-history-authority`, create a Draft PR whose
description states the offline boundary and exact zero-side-effect counters,
then read GitHub CI for the exact PR head. Stop before Ready/merge; merge still
requires exact owner confirmation of that PR and head.

## Plan self-review

- **Spec coverage:** Task 1 covers source binding, caps, source-only policy,
  raw manifest, retention, PIT semantics, non-claims and adversarial guards.
  Task 2 covers content binding, compatibility, tracked-only delivery and
  remote-readback stop.
- **No placeholder scan:** no `TODO`, `TBD`, generic validation or unspecified
  error path remains.
- **Type consistency:** `semantic_errors(packet)` is declared and used only by
  the focused test module; all receipt and fixture paths match the managed
  write set.
