# T27-A0-A3 Historical Collection Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze and prove offline the authority and evidence rules that a future bounded historical price/volume capture must satisfy before it can be proposed to the owner.

**Architecture:** Markdown and YAML freeze semantics; a JSON Schema and synthetic fixture carry an authority packet; one unittest validates schema, semantics, hashes, and zero external actions. There is no collector, provider adapter, database, or runtime service.

**Tech Stack:** Markdown, YAML, JSON Schema Draft 2020-12, Python `unittest`, `jsonschema`, repository `uv` validation.

## Global Constraints

- The implementation write set is exactly the six A3 artifacts approved in the design; this plan and its prior design are process documents.
- Provider/API/RPC/WSS, R2/R3, credentials, wallets, signers, transactions, cash spend, raw provider data, dependency changes, Catalog/registry mutation, and Project Source changes are forbidden and measured as zero.
- Source candidate is `GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`; it grants neither standing authority nor an automatic fallback provider.
- Grades are exactly `DESCRIPTIVE_ONLY` and `PIT_ADMISSIBLE`; absent availability proof cannot become PIT.
- Freeze the maximums: discovery 6, OHLCV 24, complete panels 12, panel duration 24 hours, interval 900 seconds.
- The fixture must contain no real pool ID, URL, raw response, credential, wallet material, signed bytes, or NetReturn.

---

### Task 1: Write the failing authority-contract test

**Files:**
- Create: `tests/test_task27_historical_collection_authority_contract.py`
- Test: `tests/test_task27_historical_collection_authority_contract.py`

**Interfaces:**
- Produces `semantic_errors(packet: dict[str, Any]) -> set[str]`.
- Consumes the six exact A3 artifact paths.

- [ ] **Step 1: Write the failing test**

```python
def test_all_required_artifacts_exist(self) -> None:
    for path in REQUIRED_PATHS:
        self.assertTrue(path.exists(), path)

def test_adversarial_packets_cannot_expand_authority(self) -> None:
    self.assertIn("PIT_CLAIM_WITHOUT_AVAILABILITY_PROOF", semantic_errors(packet))
    self.assertIn("DISCOVERY_CAP_EXCEEDED", semantic_errors(packet))
    self.assertIn("AUTO_FALLBACK_PROVIDER_FORBIDDEN", semantic_errors(packet))
```

- [ ] **Step 2: Run it to prove red state**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_historical_collection_authority_contract`

Expected: FAIL because no A3 contract artifacts exist.

- [ ] **Step 3: Keep the red test uncommitted if the repository pre-commit rejects incomplete states**

Do not commit a knowingly failing repository state.

### Task 2: Implement the contract, packet schema, fixture, and semantic matrix

**Files:**
- Create: `docs/contracts/task27_historical_collection_authority_contract_v1.md`
- Create: `configs/task27_historical_collection_authority_contract_v1.yaml`
- Create: `catalog/schemas/task27_historical_collection_authority.schema.json`
- Create: `tests/fixtures/task27/historical_collection_authority_v1.json`
- Modify: `tests/test_task27_historical_collection_authority_contract.py`
- Test: `tests/test_task27_historical_collection_authority_contract.py`

**Interfaces:**
- Consumes packet keys `proposal`, `evidence`, `retention`, and `decision`.
- Produces exact codes: `PIT_CLAIM_WITHOUT_AVAILABILITY_PROOF`, `DISCOVERY_CAP_EXCEEDED`, `OHLCV_CAP_EXCEEDED`, `INSUFFICIENT_COMPLETE_PANELS`, `UNFROZEN_SELECTION_SNAPSHOT`, `AUTO_FALLBACK_PROVIDER_FORBIDDEN`, `RAW_EVIDENCE_MANIFEST_REQUIRED`, `FORBIDDEN_CLAIM_SCOPE`.

- [ ] **Step 1: Write minimal contract and configuration**

Require both evidence grades, named owner decision enum, source candidate, future caps, two-tier retention, six-file write set, and all external authority counters at zero.

- [ ] **Step 2: Add schema and valid synthetic packet**

Use `fixture_kind="SYNTHETIC_GOLDEN_ONLY"`, a synthetic hash-shaped selection snapshot, `DESCRIPTIVE_ONLY`, 6-or-fewer discovery requests, 24-or-fewer OHLCV requests, at least 12 complete panels, raw-evidence manifest ID, and `AUTHORIZE_FEASIBILITY_CAPTURE`.

- [ ] **Step 3: Add one adversarial mutation for each declared code**

Use unsupported PIT, 7 discovery requests, 25 OHLCV requests, 11 panels, blank selection hash, fallback enabled, blank manifest, and alpha/execution/NetReturn scope.

- [ ] **Step 4: Implement the smallest semantic validator**

```python
def semantic_errors(packet: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    if packet["evidence"]["grade"] == "PIT_ADMISSIBLE" and not packet["evidence"]["availability_proof"]:
        errors.add("PIT_CLAIM_WITHOUT_AVAILABILITY_PROOF")
    if packet["proposal"]["discovery_requests"] > 6:
        errors.add("DISCOVERY_CAP_EXCEEDED")
    return errors
```

Complete the six remaining checks with the exact error codes. Validate with `Draft202012Validator` before evaluating the semantic matrix.

- [ ] **Step 5: Run the targeted test**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_historical_collection_authority_contract`

Expected: PASS for the valid packet and rejection for each adversarial case.

### Task 3: Bind receipt and delivery evidence

**Files:**
- Create: `docs/evidence/task27/a0a3_historical_collection_authority_acceptance_v1.json`
- Modify: `tests/test_task27_historical_collection_authority_contract.py`
- Test: `tests/test_task27_historical_collection_authority_contract.py`

**Interfaces:**
- Consumes SHA-256 values of the contract, configuration, schema, and fixture.
- Produces exact artifact bindings, test/adversarial counts, zero-action boundary, `state_change="NONE"`, and a future-authority requirement.

- [ ] **Step 1: Write the receipt-binding test**

```python
for key, path in artifact_paths.items():
    self.assertEqual(receipt["artifact_bindings"][key]["sha256"], sha256(path))
self.assertEqual(receipt["measured_boundary"]["provider_api_rpc_wss_calls"], 0)
self.assertEqual(receipt["state_change"], "NONE")
```

- [ ] **Step 2: Add receipt with current hashes**

Set full validation to `PENDING_TRACKED_ONLY_DELIVERY_PREFLIGHT` until it has actually run. Do not claim CI or canonical completion.

- [ ] **Step 3: Run targeted tests and normalized-file checks**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_historical_collection_authority_contract`

Expected: PASS, LF endings, no BOM, no CRLF.

- [ ] **Step 4: Commit complete contract**

Run: `git add docs/contracts/task27_historical_collection_authority_contract_v1.md configs/task27_historical_collection_authority_contract_v1.yaml catalog/schemas/task27_historical_collection_authority.schema.json tests/fixtures/task27/historical_collection_authority_v1.json tests/test_task27_historical_collection_authority_contract.py docs/evidence/task27/a0a3_historical_collection_authority_acceptance_v1.json`

Run: `git commit -m "feat: freeze task27 historical collection authority"`

### Task 4: Bind the tracked-only delivery result

**Files:**
- Modify: `docs/evidence/task27/a0a3_historical_collection_authority_acceptance_v1.json`
- Test: repository delivery gate

**Interfaces:**
- Consumes clean committed A3 artifacts.
- Produces a receipt whose full-validation field reports the exact tracked-only result.

- [ ] **Step 1: Run delivery preflight**

Run: `uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

Expected: PASS. If it fails, diagnose only the demonstrated A3 or repository-policy issue; do not relax authority rules.

- [ ] **Step 2: Update only receipt validation and its bindings**

Set `full_validation="PASS_TRACKED_ONLY_DELIVERY_PREFLIGHT"` only after actual success.

- [ ] **Step 3: Repeat targeted test and delivery preflight**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task27_historical_collection_authority_contract`

Run: `uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

Expected: both PASS with final hashes.

- [ ] **Step 4: Commit receipt-only binding**

Run: `git add docs/evidence/task27/a0a3_historical_collection_authority_acceptance_v1.json`

Run: `git commit -m "test: bind task27 collection authority delivery receipt"`

## Self-review

- The plan maps all approved design requirements: evidence grades, caps, frozen selection, retention, no fallback, no external authority, adversarial rejection, and reproducible delivery.
- No placeholders, unbounded validation steps, or undeclared semantic error codes remain.
- Packet sections and error codes are consistent across all tasks.

## Execution choice

Use inline execution in this isolated worktree. This is one tightly coupled offline contract and parallel subagents are not available in this runtime.
