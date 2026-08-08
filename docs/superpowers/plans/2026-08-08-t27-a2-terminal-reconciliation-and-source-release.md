# TASK-27 A2 Terminal Reconciliation and Project Sources Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record TASK-27's limited negative public-history result, register it in the Catalog, and stage `PSR-0002-T27-CLOSE` for a later owner-only Source activation.

**Architecture:** A hash-bound offline terminal packet consumes A1S4's accepted route close. A deterministic test rejects claim expansion and invalid release state. The release registry keeps PSR-0001 active and adds PSR-0002 as the only candidate.

**Tech Stack:** Python 3.13, `unittest`, PyYAML, `jsonschema`, JSON Schema Draft 2020-12, YAML/JSON/Markdown, existing Catalog generator.

## Global Constraints

- Atom: `T27-A2_TERMINAL_RECONCILIATION_AND_SOURCES_RELEASE_CANDIDATE_V1`.
- Terminal result: `NO_FEASIBLE_PUBLIC_HISTORY_ROUTE_DEMONSTRATED_WITHIN_AUTHORIZED_SCOPE`.
- Decision: `CLOSE_WITH_LIMITED_NEGATIVE_RESULT`.
- Preserve A1S4 evidence as a SHA-256-bound input and preserve `MISSING_UNKNOWN`.
- No provider/API/RPC/WSS, credentials, raw data, R2/R3, wallet, signer, transaction, cash, dependency, deployment or cloud-UI action.
- `PSR-0001-T27-A0-A5` stays `ACTIVATED_BY_OWNER_SMOKE`; `PSR-0002-T27-CLOSE` is the only `VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING` release.
- Replace exactly five Source roles and retain Operating System v8.5 and Research Blueprint v2.3 byte-for-byte.
- Factory Fit is `FULL_REVIEW`; candidate readiness grants no execution or provider authority.

---

### Task 1: Define adversarial terminal acceptance before artifacts

**Files:**
- Create: `tests/test_task27_terminal_reconciliation_and_sources_release.py`
- Modify: `tests/test_project_sources_release_registry.py`

**Interfaces:**
- Consumes: `docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json`.
- Produces: `semantic_errors(packet) -> set[str]` and release-state assertions.

- [ ] **Step 1: Write the failing terminal test**

```python
TERMINAL_RESULT = "NO_FEASIBLE_PUBLIC_HISTORY_ROUTE_DEMONSTRATED_WITHIN_AUTHORIZED_SCOPE"
EXPECTED_ERRORS = {
    "a1s4-binding-drift": "A1S4_BINDING_DRIFT",
    "global-history": "GLOBAL_HISTORY_CLAIM_FORBIDDEN",
    "new-provider": "NEW_PROVIDER_AUTHORITY_FORBIDDEN",
    "missing-to-zero": "MISSING_TO_ZERO_FORBIDDEN",
    "premature-ui": "PREMATURE_UI_ACTIVATION_FORBIDDEN",
    "invented-next-task": "INVENTED_NEXT_TASK_FORBIDDEN",
}

def test_valid_terminal_packet_is_limited_and_authority_free(self) -> None:
    packet = load_json(FIXTURE_PATH)["valid_packets"][0]
    Draft202012Validator(load_json(SCHEMA_PATH)).validate(packet)
    self.assertEqual(packet["result"], TERMINAL_RESULT)
    self.assertEqual(semantic_errors(packet), set())
```

- [ ] **Step 2: Run the test and confirm it fails for absent terminal artifacts**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_terminal_reconciliation_and_sources_release`

Expected: `FAIL` because the terminal artifact files do not exist.

- [ ] **Step 3: Add adversarial and registry checks**

```python
for case in fixture["adversarial_cases"]:
    candidate = copy.deepcopy(valid_packet)
    set_json_pointer(candidate, case["pointer"], case["replacement"])
    self.assertEqual(semantic_errors(candidate), {EXPECTED_ERRORS[case["case_id"]]})

self.assertEqual(registry["active_ui_release_id"], "PSR-0001-T27-A0-A5")
self.assertEqual(registry["latest_candidate_release_id"], "PSR-0002-T27-CLOSE")
self.assertEqual(candidate_release["status"], CANDIDATE_STATUS)
self.assertIsNone(candidate_release["activation_receipt"])
```

- [ ] **Step 4: Update the pre-existing registry test for one active and one candidate**

Replace its former `latest_candidate_release_id is None` assertion with `PSR-0002-T27-CLOSE`; retain the rejection test for a second candidate.

- [ ] **Step 5: Commit the red test**

Run: `git add tests/test_task27_terminal_reconciliation_and_sources_release.py tests/test_project_sources_release_registry.py`

Run: `git commit -m "test: define TASK-27 terminal reconciliation boundaries"`

### Task 2: Implement the terminal packet and evidence

**Files:**
- Create: `docs/contracts/task27_terminal_reconciliation_and_sources_release_contract_v1.md`
- Create: `configs/task27_terminal_reconciliation_and_sources_release_v1.yaml`
- Create: `catalog/schemas/task27_terminal_reconciliation_and_sources_release.schema.json`
- Create: `tests/fixtures/task27/terminal_reconciliation_and_sources_release_v1.json`
- Create: `docs/evidence/task27/a2_terminal_reconciliation_and_sources_release_acceptance_v1.json`

**Interfaces:**
- Consumes: Task-1 test constants and the exact A1S4 receipt.
- Produces: a schema-valid golden packet and hash-bound acceptance receipt.

- [ ] **Step 1: Define the exact decision, authority and claim fields**

```yaml
decision:
  task27_outcome: CLOSE_WITH_LIMITED_NEGATIVE_RESULT
  terminal_result: NO_FEASIBLE_PUBLIC_HISTORY_ROUTE_DEMONSTRATED_WITHIN_AUTHORIZED_SCOPE
  task27_repository_state: TECHNICALLY_RECONCILED_PENDING_SOURCE_ACTIVATION
  next_task_selected: false
authority:
  provider_api_rpc_wss_calls: 0
  credential_use: false
  wallet_signer_transaction_actions: 0
  cash_spend_usd_cents: 0
claims:
  public_history_globally_infeasible: false
  pit_admissible: false
  alpha: false
  execution: false
  pnl: false
  netreturn: false
  cashflow: false
```

- [ ] **Step 2: Bind A1S4 and implement the semantic rejects**

```python
if packet["source_bindings"]["a1s4_acceptance"] != expected_a1s4:
    errors.add("A1S4_BINDING_DRIFT")
if packet["claims"]["public_history_globally_infeasible"]:
    errors.add("GLOBAL_HISTORY_CLAIM_FORBIDDEN")
if packet["authority"]["provider_api_rpc_wss_calls"] or packet["authority"]["credential_use"]:
    errors.add("NEW_PROVIDER_AUTHORITY_FORBIDDEN")
```

- [ ] **Step 3: Add one synthetic golden fixture and six exact mutations**

The golden packet declares `fixture_kind: SYNTHETIC_GOLDEN_ONLY`, `missingness.state: MISSING_UNKNOWN`, `missing_as_zero: false`, `source_release.activation_state: UI_ACTIVATION_PENDING_OWNER_SMOKE`, and `next_task.selected: false`.

- [ ] **Step 4: Produce the acceptance receipt after Task-2 file hashes are stable**

Bind the five new artifacts and A1S4; record one valid fixture, six rejections, zero side effects, `FULL_REVIEW`, `PASS_WITH_LIMITATIONS`, the terminal NOW candidate and named-consumer-only WATCH trigger. Declare a `RELEASE_CANDIDATE` disposition for PSR-0002.

- [ ] **Step 5: Run and pass the new test**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_terminal_reconciliation_and_sources_release`

Expected: `PASS` with six adversarial rejections.

- [ ] **Step 6: Commit the packet**

Run: `git add docs/contracts/task27_terminal_reconciliation_and_sources_release_contract_v1.md configs/task27_terminal_reconciliation_and_sources_release_v1.yaml catalog/schemas/task27_terminal_reconciliation_and_sources_release.schema.json tests/fixtures/task27/terminal_reconciliation_and_sources_release_v1.json docs/evidence/task27/a2_terminal_reconciliation_and_sources_release_acceptance_v1.json tests/test_task27_terminal_reconciliation_and_sources_release.py`

Run: `git commit -m "feat: reconcile TASK-27 terminal route outcome"`

### Task 3: Register the result in Catalog and navigation

**Files:**
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `registries/decisions_negative_results.yaml`
- Modify: `docs/PROJECT_MAP.md` (generated)
- Modify: `catalog/generated/asset_edges.json` (generated)

**Interfaces:**
- Consumes: Task-2 artifacts and the existing negative-results registry.
- Produces: seven traceable Catalog assets, a durable negative-result record and deterministic navigation.

- [ ] **Step 1: Update the Catalog manifest**

Add the terminal schema to `root_resolver.schemas`; update `catalog_version` from `0.37.0` to `0.38.0`, `schemas` from `14` to `15`, `assets` from `561` to `568`, and `lifecycle_records` from `58` to `59` after the appended negative-result record.

- [ ] **Step 2: Append seven Core asset records**

Create `EVIDENCE-T27-A1S4-OWNER-ROUTE-CLOSE-001`, `CONTRACT-T27-TERMINAL-RECONCILIATION-001`, `CONFIG-T27-TERMINAL-RECONCILIATION-001`, `SCHEMA-T27-TERMINAL-RECONCILIATION-001`, `FIXTURE-T27-TERMINAL-RECONCILIATION-001`, `TEST-T27-TERMINAL-RECONCILIATION-001`, and `EVIDENCE-T27-A2-TERMINAL-RECONCILIATION-001`. Use `TASK-27` as owner, `IMPLEMENTED_UNVERIFIED`, no secrets/raw data, and relations from contract/config/schema/fixture/test to the A2 evidence record. The A1S4 evidence asset points to its existing receipt; the A2 evidence derives from that asset and is validated by the test; consumers are `[TASK-27, FACTORY-001]`.

- [ ] **Step 3: Add one limited negative-result record**

```yaml
- record_kind: negative_result
  record_id: NEGATIVE-T27-PUBLIC-HISTORY-ROUTE-V1-001
  status: RECORDED
  created_at: '2026-08-08T00:00:00Z'
  evidence_asset_ids: [EVIDENCE-T27-A2-TERMINAL-RECONCILIATION-001]
  summary: "TASK-27 closed only the named authorized public 15-minute pool-history route: 33 of 96 required bars were observed, 63 remain MISSING_UNKNOWN, and no new provider read was authorized. This is not a claim about all public history, alpha, execution, PnL, NetReturn, or cashflow."
```

Update lifecycle source assets, version/as-of and integrity hashes coherently.

- [ ] **Step 4: Generate, bind and validate the navigation projections**

Run: `uv run --locked --managed-python python -B scripts/generate_navigation.py --write`

Set the observed generated-file SHA-256 values in lifecycle Catalog records, then run: `uv run --locked --managed-python python -B scripts/validate_catalog.py`

Run: `uv run --locked --managed-python python -B scripts/generate_navigation.py --check`

Expected: Catalog and deterministic navigation both pass.

- [ ] **Step 5: Extend the terminal test and commit**

Assert `EVIDENCE-T27-A2-TERMINAL-RECONCILIATION-001` and `NEGATIVE-T27-PUBLIC-HISTORY-ROUTE-V1-001` are registered and recorded.

Run: `git add catalog/catalog_manifest.yaml catalog/assets/core.yaml catalog/assets/lifecycle.yaml registries/decisions_negative_results.yaml docs/PROJECT_MAP.md catalog/generated/asset_edges.json tests/test_task27_terminal_reconciliation_and_sources_release.py`

Run: `git commit -m "feat: register TASK-27 terminal negative result"`

### Task 4: Build PSR-0002 and retain PSR-0001 as active

**Files:**
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/canonical_manifest.yaml`
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/roadmap.md`
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/current_system_state.md`
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/task_archive_P0_P1_v38.md`
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/task_27_public_history_feasibility.md`
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/CHECKSUMS_SHA256.txt`
- Create: `docs/project_sources/releases/PSR-0002-T27-CLOSE/FRESH_CHAT_SMOKE.md`
- Modify: `docs/project_sources/release_registry_v1.yaml`
- Modify: `tests/test_task27_terminal_reconciliation_and_sources_release.py`
- Modify: `tests/test_project_sources_release_registry.py`

**Interfaces:**
- Consumes: Tasks 2–3, PSR-0001, and the seven-role Source contract.
- Produces: one candidate bundle with self-checking hashes and no UI activation claim.

- [ ] **Step 1: Create the five mutable Source-role files**

Use: canonical manifest `4.8`, roadmap `4.8`, system state `4.4`, archive `38.0`, active task `TASK-27 / 1.1`. Required headers are `schema: solana_alpha_lab.canonical_manifest`, `Версия 4.8`, `CURRENT SYSTEM STATE — SOLANA MEMECOIN INTRADAY ALPHA LAB v4.4`, `TASK ARCHIVE P0/P1 v38`, and `# TASK-27 — Bounded public historical price/volume feasibility`.

Every document states the limited route outcome, no new provider authority, no selected next task, no alpha/execution/cash claim, and source activation pending an owner smoke.

- [ ] **Step 2: Derive hashes and smoke from final bytes**

Manifest keeps OS SHA `187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84`, Blueprint SHA `ec756d5be0196dd8207ac08512af5e3a9a5032eb5b0b40e3f8fcca2beb170ba1`, and `expected_source_count_after_activation: 7`. Checksums has exactly five mutable files. Smoke requires five replacements plus the two retained immutable roles, then `TASK27_CLOSE_SOURCE_SMOKE=PASS|FAIL`, zero authority, `STATE_CHANGE=NONE`.

- [ ] **Step 3: Register the candidate without changing actual activation**

```yaml
latest_candidate_release_id: PSR-0002-T27-CLOSE
release_id: PSR-0002-T27-CLOSE
atom_id: T27-A2_TERMINAL_RECONCILIATION_AND_SOURCES_RELEASE_CANDIDATE_V1
status: VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING
activation_receipt: null
supersedes_release_id: PSR-0001-T27-A0-A5
superseded_by_release_id: null
owner_next_action: REPLACE_EXACT_FIVE_MUTABLE_ROLES_KEEP_TWO_IMMUTABLE_ROLES_RUN_SEVEN_ROLE_SMOKE
```

Keep `active_ui_release_id: PSR-0001-T27-A0-A5`, its activation state and its status unchanged.

- [ ] **Step 4: Add release invariants and pass source tests**

Assert seven bundle files, five checksums, checksum/manifest/file agreement, candidate has no receipt, PSR-0001 stays active, and no source artifact selects TASK-28.

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_terminal_reconciliation_and_sources_release tests.test_project_sources_release_registry`

Expected: `PASS`.

- [ ] **Step 5: Commit the candidate**

Run: `git add docs/project_sources/releases/PSR-0002-T27-CLOSE docs/project_sources/release_registry_v1.yaml tests/test_task27_terminal_reconciliation_and_sources_release.py tests/test_project_sources_release_registry.py`

Run: `git commit -m "docs: stage TASK-27 terminal sources release"`

### Task 5: Run exact delivery validation before first push

**Files:**
- Modify only when an in-scope validation error identifies a defect.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: an exact-candidate tracked-only receipt, then one draft PR and exact-head CI read-back.

- [ ] **Step 1: Run focused, full and generation checks**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_terminal_reconciliation_and_sources_release tests.test_project_sources_release_registry tests.test_task27_owner_route_close_and_task_outcome`

Run: `uv run --locked --managed-python python -B -m unittest discover -s tests -p 'test_*.py'`

Run: `uv run --locked --managed-python python -B scripts/validate_catalog.py`

Run: `uv run --locked --managed-python python -B scripts/generate_navigation.py --check`

- [ ] **Step 2: Inspect scope and run clean-checkout preflight before push**

Run: `git diff --check origin/main...HEAD`

Run: `git diff --name-only origin/main...HEAD`

Run: `uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

Expected: only Tasks 1–4 and approved design/plan files changed; receipt status is `PASS`.

- [ ] **Step 3: Push once, open one Draft PR, read back exact head and CI**

Run: `git push -u origin task27/terminal-reconciliation`

Run: `gh pr create --draft --base main --head task27/terminal-reconciliation --title "TASK-27: reconcile terminal public-history route" --body "Closes only the named authorized public 15-minute history route. No provider, credential, raw-data, wallet, transaction, cash, alpha, execution, PnL, NetReturn or cloud-Source activation claim. Includes PSR-0002-T27-CLOSE as a candidate; PSR-0001 remains active until owner smoke."`

No merge occurs unless owner-attention gate returns `AUTONOMOUS` and every exact-head CI and full-gate condition passes.
