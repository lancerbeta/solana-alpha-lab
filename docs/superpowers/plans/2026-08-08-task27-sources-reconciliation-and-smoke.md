# TASK-27 Source Reconciliation and Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manifest-first offline Project Sources replacement candidate that records TASK-27 A0-A2 through A0-A4 without granting any provider or execution authority.

**Architecture:** The candidate is a versioned documentation bundle, not a service. Five replacement roles live together under one repository-tracked directory; two immutable roles are hash-bound but not copied. A YAML contract, JSON Schema, synthetic fixture and deterministic unittest independently verify role membership, hashes, UI-activation truth and external-authority boundaries.

**Tech Stack:** Markdown, YAML, JSON Schema Draft 2020-12, Python `unittest`, PyYAML, jsonschema, SHA-256, uv.

## Global Constraints

- Input baseline is the integrity-checked but unactivated Source candidate: manifest 4.6, roadmap 4.6, state 4.2, archive 36.0 and owner-packet active task 1.0.
- Candidate records merged main `082f3f8184e84c31c876a484cf8e876a40691f62` and GitHub push CI run `31224401848` as successful repository evidence.
- Candidate changes exactly five Project Source roles: manifest, roadmap, current system state, phase archive and active task; Operating System v8.5 and Blueprint v2.3 are retained byte-for-byte by SHA-256.
- Bundle status is always `VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING` until an owner-run seven-role smoke returns `SMOKE=PASS`.
- Provider/API/RPC/WSS, raw history, R2/R3, credential, dependency, catalog-root, wallet, signer, transaction, cash, alpha, PIT, PnL and NetReturn actions or claims are excluded.
- A successful smoke only clears the Source-alignment prerequisite for a separate owner external-read review; it never grants provider-read authority.
- No Project Sources UI action occurs in this plan. The user action remains a post-delivery stop.

---

### Task 1: Freeze the source-reconciliation contract and first failing test

**Files:**
- Create: `docs/contracts/task27_permanent_sources_reconciliation_contract_v1.md`
- Create: `configs/task27_permanent_sources_reconciliation_contract_v1.yaml`
- Create: `catalog/schemas/task27_permanent_sources_reconciliation.schema.json`
- Create: `tests/fixtures/task27/permanent_sources_reconciliation_v1.json`
- Create: `tests/test_task27_permanent_sources_reconciliation_contract.py`

**Interfaces:**
- Consumes: A4 contract at `docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md`; Source versions 4.6/4.6/4.2/36.0/1.0; immutable hashes for OS 8.5 and Blueprint 2.3.
- Produces: `semantic_errors(packet) -> set[str]` and a JSON Schema-valid synthetic packet with one valid candidate and adversarial mutations.

- [ ] **Step 1: Write the failing artifact-existence and boundary test**

```python
def test_required_contract_artifacts_exist_and_bundle_is_not_live() -> None:
    for path in REQUIRED_PATHS:
        self.assertTrue(path.exists(), path)
    self.assertEqual(config["bundle_status"], "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING")
    self.assertFalse(config["authority"]["provider_read_authority"])
```

- [ ] **Step 2: Run the test to verify it fails before the artifacts exist**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_permanent_sources_reconciliation_contract
```

Expected: `FAIL` because the contract, config, schema and fixture are absent.

- [ ] **Step 3: Implement the minimal contract, config, schema and fixture**

Freeze these exact semantic fields:

```yaml
task_id: TASK-27
atom_id: T27-A0-A5_PERMANENT_SOURCES_RECONCILIATION_AND_SMOKE_V1
bundle_status: VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING
mutable_roles: [canonical_manifest, roadmap, current_system_state, phase_archive, active_task]
immutable_roles: [operating_system, research_blueprint]
repository_evidence:
  main_commit: 082f3f8184e84c31c876a484cf8e876a40691f62
  main_ci_run_id: 31224401848
  main_ci_conclusion: success
authority:
  provider_api_rpc_wss_calls: 0
  provider_read_authority: false
  wallet_signer_transaction_actions: 0
  cash_spend_usd_cents: 0
```

The fixture's adversarial cases must cover: extra mutable role, old active task,
immutable hash drift, false UI activation, missing smoke prompt, wrong merged
main/CI binding, external-authority promotion and a direct `PIT_ADMISSIBLE`
claim.

- [ ] **Step 4: Run the targeted test to verify the new contract passes**

Run the Task 1 command again. Expected: all contract/schema/fixture checks pass
and every adversarial case is rejected by its named error.

- [ ] **Step 5: Commit the contract layer**

```text
git add docs/contracts/task27_permanent_sources_reconciliation_contract_v1.md configs/task27_permanent_sources_reconciliation_contract_v1.yaml catalog/schemas/task27_permanent_sources_reconciliation.schema.json tests/fixtures/task27/permanent_sources_reconciliation_v1.json tests/test_task27_permanent_sources_reconciliation_contract.py
git commit -m "feat: freeze task27 source reconciliation contract"
```

### Task 2: Build the five-role replacement candidate and smoke assets

**Files:**
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/canonical_manifest.yaml`
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/roadmap.md`
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/current_system_state.md`
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/task_archive_P0_P1_v37.md`
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/task_27_public_history_feasibility.md`
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/CHECKSUMS_SHA256.txt`
- Create: `docs/project_sources/releases/PSR-0001-T27-A0-A5/FRESH_CHAT_SMOKE.md`

**Interfaces:**
- Consumes: Task 1 contract fields, immutable-role hash bindings, A2/A3/A4 evidence and the exact merged-main CI identity.
- Produces: a five-file replacement set plus receipts that an owner can use to replace exactly five Source roles and then run one seven-role smoke.

- [ ] **Step 1: Extend the test with content/hash invariants and run it red**

```python
def test_bundle_has_exactly_five_replacements_and_retains_two_immutable_roles() -> None:
    self.assertEqual(bundle_manifest["activation_map"]["replace_source_roles"], EXPECTED_MUTABLE_ROLES)
    self.assertEqual(bundle_manifest["activation_map"]["keep_byte_for_byte"], EXPECTED_IMMUTABLE_ROLES)
    self.assertEqual(bundle_manifest["current_state"]["last_validated_repository_commit"], MAIN_SHA)
    self.assertEqual(bundle_manifest["current_state"]["main_ci_run_id"], 31224401848)
```

Run the Task 1 command. Expected: `FAIL` because the candidate bundle and
checksums do not exist.

- [ ] **Step 2: Write the five Source roles using the v4.6 candidate as historical baseline**

Use semantic versions manifest `4.7`, roadmap `4.7`, state `4.3`, archive
`37.0` and active TASK-27 `1.0`. The active-task record must list A2, A3 and A4
as merged offline foundation, A5 as the source reconciliation candidate, and
the next boundary as `ACTIVATION_CONFIRMED_USER_SMOKE` followed by a separate
exact owner external-read review.

The roadmap, state and archive must retain the canary's no-authority posture
and explicitly state that TASK-27's offline documentation does not override
the canary decision or independently permit execution.

- [ ] **Step 3: Create checksums, validation receipt and smoke prompt**

`CHECKSUMS_SHA256.txt` must bind the manifest and all five mutable files. The
repository acceptance receipt binds their paths/hashes, immutable-role hashes,
main SHA, CI run, zero side effects and `UI_ACTIVATION_PENDING`.
`FRESH_CHAT_SMOKE.md` must ask for role → semantic version → required header →
actual SHA-256 → physical filename for all seven roles and require explicit
`STATE_CHANGE=NONE`.

- [ ] **Step 4: Run targeted validation to verify the candidate is internally consistent**

Run the Task 1 command. Expected: all manifest/header/hash checks pass,
candidate says `UI_ACTIVATION_PENDING`, and no provider authority is present.

- [ ] **Step 5: Commit the bundle bytes**

```text
git add docs/project_sources/releases/PSR-0001-T27-A0-A5 tests/test_task27_permanent_sources_reconciliation_contract.py
git commit -m "docs: prepare task27 source reconciliation bundle"
```

### Task 3: Bind acceptance, run delivery validation and prepare the owner stop

**Files:**
- Create: `docs/evidence/task27/a0a5_permanent_sources_reconciliation_acceptance_v1.json`
- Modify: `tests/test_task27_permanent_sources_reconciliation_contract.py`

**Interfaces:**
- Consumes: Task 1 contract and Task 2 bundle checksums.
- Produces: acceptance receipt with exact artifact hashes, targeted validation
counts, delivery status and a single post-delivery `USER_UI` activation step.

- [ ] **Step 1: Write the failing receipt-binding test**

```python
def test_acceptance_receipt_binds_bundle_and_stops_before_ui_activation() -> None:
    self.assertTrue(RECEIPT_PATH.exists(), RECEIPT_PATH)
    self.assertEqual(receipt["state_change"], "NONE")
    self.assertEqual(receipt["ui_activation"], "PENDING_USER_REPLACEMENT_AND_SMOKE")
    self.assertFalse(receipt["next_boundary"]["provider_read_authority_granted"])
```

- [ ] **Step 2: Run the targeted test to verify it fails without a receipt**

Run the Task 1 command. Expected: `FAIL` because the acceptance receipt does
not exist.

- [ ] **Step 3: Implement the acceptance receipt and final adversarial checks**

The receipt must report zero provider, R2/R3, wallet/signer/transaction, cash,
credential, dependency and catalog-root actions. It must bind all source-bundle
support files, state that activation is not claimed, and name only this future
owner action: replace the five mutable roles, keep two immutable roles, run the
seven-role smoke, return the exact result.

- [ ] **Step 4: Run focused compatibility and delivery checks**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_price_volume_research_screen_contract tests.test_task27_historical_collection_authority_contract tests.test_task27_bounded_public_history_feasibility_authority_contract tests.test_task27_permanent_sources_reconciliation_contract
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: all targeted compatibility tests and the one tracked-only delivery
gate pass on the exact committed candidate.

- [ ] **Step 5: Commit and deliver the completed offline candidate**

```text
git add docs/evidence/task27/a0a5_permanent_sources_reconciliation_acceptance_v1.json tests/test_task27_permanent_sources_reconciliation_contract.py
git commit -m "test: bind task27 source reconciliation receipt"
git push origin task27/source-reconciliation-and-smoke
```

Open one Draft PR, read back its exact head and CI, then stop before Ready or
merge. Do not perform the Source UI replacement.
