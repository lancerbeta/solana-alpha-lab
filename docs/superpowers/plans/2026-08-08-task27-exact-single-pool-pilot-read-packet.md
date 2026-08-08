# TASK-27 Exact Single-Pool Pilot Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic offline A7 packet that binds the owner-nominated Solana pool to exactly two future keyless GeckoTerminal GET requests without executing or authorizing either request.

**Architecture:** Follow the existing TASK-27 contract/config/schema/fixture/test/receipt pattern. The config is the policy owner and contains one content-addressed selection snapshot, two canonical future URLs, inherited A4 limits, retention rules, fail-closed future acceptance rules, and a disabled exact owner-approval phrase. JSON Schema enforces structure; one focused unittest module adds cross-file hashes and semantic invariants.

**Tech Stack:** Markdown, YAML, JSON Schema Draft 2020-12, Python 3.13 `unittest`, `jsonschema`, `PyYAML`, SHA-256, repository `uv` validation.

## Global Constraints

- Atom: `T27-A0-A7_EXACT_SINGLE_POOL_SELECTION_AND_PILOT_READ_PACKET_V1`.
- Base: `origin/main` at `62a03bed41bbd45204c81389ba42d8110a3d6fca`.
- Network: `solana`.
- Pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.
- Selection class: `OWNER_NOMINATED_SINGLE_POOL`.
- Universe: `ONE_NON_REPRESENTATIVE_TECHNICAL_FEASIBILITY_TARGET`.
- Selection snapshot time: `2026-08-08T11:03:00Z`.
- Frozen OHLCV boundary: `before_timestamp=1786186800` (`2026-08-08T11:00:00Z`).
- Selection canonicalization: UTF-8 JSON with lexicographically sorted keys and separators `(',', ':')`.
- Selection snapshot SHA-256: `922e2b1f529d5e1d2beab34c93320914a0ac9670a956c0123fb69ba5ad5315a2`.
- Future pilot budget: exactly one metadata GET plus one OHLCV GET; zero calls in A7.
- OHLCV shape: `minute`, aggregate `15`, limit `96`, `currency=usd`, `token=base`, `include_empty_intervals=false`.
- No provider/API/RPC/WSS execution, credential, retained provider response, R2/R3 read, wallet, signer, transaction, cash spend, dependency, Catalog root, generated consumer, or Project Source change.
- Passing the future pilot does not satisfy A4's minimum of 12 complete retained panels.
- Missing/omitted intervals remain `UNKNOWN`; carrying price forward or converting missing volume to zero is forbidden.

---

## File map

- `docs/contracts/task27_exact_single_pool_selection_and_pilot_read_packet_v1.md`: human-readable purpose, target, request, retention, decision, and non-claim contract.
- `configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml`: machine policy owner for exact identity, URLs, hashes, caps, authority, and future acceptance.
- `catalog/schemas/task27_exact_single_pool_selection_and_pilot_read_packet.schema.json`: Draft 2020-12 structure for the golden and adversarial fixture.
- `tests/fixtures/task27/exact_single_pool_selection_and_pilot_read_packet_v1.json`: deterministic offline golden packet plus one-change adversarial cases.
- `tests/test_task27_exact_single_pool_selection_and_pilot_read_packet.py`: schema, cross-file binding, canonical hash, semantic, and receipt tests.
- `docs/evidence/task27/a0a7_exact_single_pool_selection_and_pilot_read_packet_acceptance_v1.json`: measured offline acceptance and next-boundary receipt.

These six files are the atom's `managed_write_set`. The already committed design and this plan are delivery-support documents, not runtime truth owners.

---

### Task 1: Build the offline policy packet with red-first contract tests

**Files:**
- Create: `tests/test_task27_exact_single_pool_selection_and_pilot_read_packet.py`
- Create: `docs/contracts/task27_exact_single_pool_selection_and_pilot_read_packet_v1.md`
- Create: `configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml`
- Create: `catalog/schemas/task27_exact_single_pool_selection_and_pilot_read_packet.schema.json`
- Create: `tests/fixtures/task27/exact_single_pool_selection_and_pilot_read_packet_v1.json`

**Interfaces:**
- Consumes: A6 config/contract and A5R1 Source-smoke receipt by exact repository path and SHA-256.
- Produces: `semantic_errors(packet: dict[str, Any], policy: dict[str, Any]) -> set[str]`, the exact future request packet, and a schema-valid adversarial fixture used by Task 2.

- [ ] **Step 1: Write the failing test module**

Create the path constants, loaders, canonical hash helper, JSON-pointer mutation helper, packet-schema helper, and semantic validator. The canonical snapshot helper must be exactly:

```python
def canonical_json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
```

`semantic_errors` must compare the packet to policy and emit only these stable error IDs:

```python
EXPECTED_ERRORS = {
    "WRONG_NETWORK",
    "WRONG_POOL",
    "UNVERIFIED_HINT_PROMOTION",
    "SELECTION_HASH_MISMATCH",
    "UNALIGNED_BEFORE_TIMESTAMP",
    "FLOATING_WINDOW_FORBIDDEN",
    "REQUEST_COUNT_MISMATCH",
    "NON_GET_METHOD",
    "REQUEST_URL_MISMATCH",
    "EMPTY_INTERVAL_IMPUTATION_FORBIDDEN",
    "PANEL_RULE_RELAXATION_FORBIDDEN",
    "RAW_MANIFEST_REQUIRED",
    "FALLBACK_PROVIDER_FORBIDDEN",
    "AUTHORITY_PROMOTION_FORBIDDEN",
    "EXTERNAL_ACTION_IN_A7_FORBIDDEN",
    "RAW_RETENTION_IN_A7_FORBIDDEN",
    "FORBIDDEN_DECISION_CLAIM",
    "PREMATURE_APPROVAL_FORBIDDEN",
}
```

Add four tests:

```python
class ExactSinglePoolSelectionAndPilotReadPacketTests(unittest.TestCase):
    def test_required_assets_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_policy_binds_a6_source_smoke_selection_and_exact_urls(self) -> None:
        policy = load_yaml(CONFIG_PATH)
        selection = policy["selection_snapshot"]
        self.assertEqual(canonical_json_sha256(selection["content"]), selection["sha256"])
        self.assertEqual(selection["sha256"], "922e2b1f529d5e1d2beab34c93320914a0ac9670a956c0123fb69ba5ad5315a2")
        self.assertEqual(policy["pilot"]["request_count"], 2)
        self.assertEqual(policy["pilot"]["before_timestamp"], 1786186800)
        self.assertEqual(policy["pilot"]["before_timestamp"] % 900, 0)
        self.assertFalse(policy["pilot"]["include_empty_intervals"])

    def test_valid_offline_packet_is_schema_valid_and_never_authorized(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])
        self.assertEqual(list(Draft202012Validator(packet_schema(schema)).iter_errors(fixture["valid_packet"])), [])
        self.assertEqual(semantic_errors(fixture["valid_packet"], load_yaml(CONFIG_PATH)), set())
        self.assertFalse(fixture["valid_packet"]["authority"]["provider_read_authority"])

    def test_each_adversarial_case_rejects_one_specific_boundary_break(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        validator = Draft202012Validator(packet_schema(schema))
        policy = load_yaml(CONFIG_PATH)
        self.assertEqual({case["expected_error"] for case in fixture["adversarial_cases"]}, EXPECTED_ERRORS)
        for case in fixture["adversarial_cases"]:
            with self.subTest(case=case["case_id"]):
                packet = copy.deepcopy(fixture["valid_packet"])
                apply_json_pointer(packet, case["pointer"], case["value"])
                self.assertEqual(list(validator.iter_errors(packet)), [])
                self.assertEqual(semantic_errors(packet, policy), {case["expected_error"]})
```

- [ ] **Step 2: Run the targeted test and verify the red state**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_exact_single_pool_selection_and_pilot_read_packet
```

Expected: FAIL in `test_required_assets_exist` because the contract/config/schema/fixture do not exist. This is the intended TDD red state; do not create a skip.

- [ ] **Step 3: Write the exact YAML policy**

Create `configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml` with these exact decision-bearing values:

```yaml
schema: smial.task27.exact_single_pool_selection_and_pilot_read_packet.contract
schema_version: '1.0'
task_id: TASK-27
atom_id: T27-A0-A7_EXACT_SINGLE_POOL_SELECTION_AND_PILOT_READ_PACKET_V1
consumer: OWNER_EXTERNAL_READ_DECISION
inherits:
  a6_contract:
    path: docs/contracts/task27_exact_owner_external_read_review_contract_v1.md
    sha256: d0942963f5e98bb0a80cacef79aa5c1c2fac47323a3e0a474facdd89f0a87342
  a6_config:
    path: configs/task27_exact_owner_external_read_review_contract_v1.yaml
    sha256: f82c80194068ed7e51efac0126383453eb3f505357233d576afe85fe996eb683
source_candidate: GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE
selection_snapshot:
  id: T27-A7-OWNER-NOMINATED-POOL-001
  canonicalization: SORTED_KEYS_MINIFIED_UTF8_V1
  sha256: 922e2b1f529d5e1d2beab34c93320914a0ac9670a956c0123fb69ba5ad5315a2
  content:
    network: solana
    owner_supplied_url: https://www.geckoterminal.com/solana/pools/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
    pool_address: URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
    selected_at: '2026-08-08T11:03:00Z'
    selection_class: OWNER_NOMINATED_SINGLE_POOL
    universe_description: ONE_NON_REPRESENTATIVE_TECHNICAL_FEASIBILITY_TARGET
  page_hints:
    state: UNVERIFIED_HINT_ONLY
    dex_label: PumpSwap
    pair_label: Cope/SOL
pilot:
  provider: GECKOTERMINAL_KEYLESS_PUBLIC_API
  base_url: https://api.geckoterminal.com/api/v2
  request_id: T27-A1-EXACT-SINGLE-POOL-PILOT-001
  raw_evidence_manifest_id: T27-A1-RAW-MANIFEST-001
  request_count: 2
  discovery_requests: 1
  ohlcv_requests: 1
  window_mode: FROZEN_BEFORE_TIMESTAMP
  before_timestamp: 1786186800
  interval_seconds: 900
  panel_duration_hours: 24
  required_natural_bars: 96
  include_empty_intervals: false
  automatic_fallback_provider: null
  requests:
    - kind: POOL_METADATA
      method: GET
      url: https://api.geckoterminal.com/api/v2/networks/solana/pools/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
    - kind: POOL_OHLCV
      method: GET
      url: https://api.geckoterminal.com/api/v2/networks/solana/pools/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S/ohlcv/minute?aggregate=15&before_timestamp=1786186800&limit=96&currency=usd&token=base&include_empty_intervals=false
future_acceptance:
  runtime_outcomes:
    - READY_FOR_BOUNDED_HISTORY_CAPTURE
    - REDESIGN_PUBLIC_HISTORY_ROUTE
    - CLOSE_PUBLIC_HISTORY_ROUTE
  current_state: READY_FOR_SEPARATE_OWNER_EXTERNAL_READ_DECISION
  timestamps_unique_required: true
  timestamps_ascending_required: true
  timestamps_aligned_required: true
  gaps_allowed: false
  duplicates_allowed: false
  natural_observations_only: true
  ohlc_positive_required: true
  ohlc_consistent_required: true
  volume_currency: usd
  missing_result: UNKNOWN
  carried_forward_forbidden: true
retention:
  raw_location_pattern: local/task27_public_history_pilot/run=<run_id>/raw_manifest_v1.json
  failed_or_unusable_probe_days: 30
  dependent_research: RETAIN_WITH_DEPENDENT_RESEARCH_AND_HASHES
authority:
  user_authority: T27-A0-A7_OFFLINE_PACKET_ONLY
  provider_read_authority: false
  provider_api_rpc_wss_calls: 0
  raw_provider_responses_retained: 0
  credential_use: false
  r2_value_reads: 0
  r3_value_or_path_reads: 0
  wallet_signer_transaction_actions: 0
  cash_spend_usd_cents: 0
  dependency_changes: false
  catalog_or_registry_mutation: false
  project_source_changes: false
claims:
  scope: HISTORICAL_FEASIBILITY_ONLY
  history_grade: DESCRIPTIVE_ONLY
  representative_sample: false
  pit_admissible: false
  alpha: false
  execution: false
  pnl: false
  netreturn: false
  cashflow: false
future_owner_approval:
  state: EXACT_PACKET_READY_OWNER_AUTHORITY_REQUIRED
  approval_granted: false
  phrase: 'Подтверждаю T27-A1_EXACT_SINGLE_POOL_PUBLIC_HISTORY_PILOT_V1: разрешаю ровно 2 публичных GET-запроса GeckoTerminal для pool URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S с before_timestamp=1786186800 и сохранение exact raw JSON вне Git по retention A4; без ключей, кошелька, RPC, транзакций, расходов, R3 и TASK-27 acceptance.'
```

Append the exact six-file `managed_write_set` from the File map.

- [ ] **Step 4: Write the contract, schema, and fixture**

The Markdown contract must state, in this order: purpose; exact owner-nominated target; content-addressed selection snapshot; exact two-request future pilot; raw manifest fields; 96-natural-bar acceptance; three runtime outcomes; retained A4 12-panel minimum; authority; non-claims; recovery by `REDESIGN`/`CLOSE` without fallback.

The JSON Schema must use Draft 2020-12, `additionalProperties: false` on every object, and define:

```json
{
  "required": ["fixture_kind", "valid_packet", "adversarial_cases"],
  "$defs": {
    "packet": {
      "required": [
        "fixture_kind",
        "selection_snapshot",
        "pilot",
        "future_acceptance",
        "authority",
        "claims",
        "future_owner_approval"
      ]
    }
  }
}
```

Use string patterns for 64-character lowercase SHA-256 and UTC timestamps, integer minima for counts, and arrays with `minItems: 2`, `maxItems: 2` for the request list. Structural schema validation must still allow each adversarial mutation; semantic rejection belongs to `semantic_errors`.

The fixture's `valid_packet` must mirror the exact policy values, set
`fixture_kind=SYNTHETIC_VALUES_WITH_OWNER_NOMINATED_IDENTITY`, and state that
no provider response exists. Add exactly 18 adversarial cases, one per
`EXPECTED_ERRORS` item, using one JSON-pointer mutation each.

- [ ] **Step 5: Implement `semantic_errors` and run the green test**

Compare all exact request fields and URLs to the YAML policy; recompute the
selection snapshot hash; require `before_timestamp % 900 == 0`; require the
fail-closed panel rules; and reject any authority or claim promotion. For the
two-request structure, validate both list length and exact kinds/methods/URLs.

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_exact_single_pool_selection_and_pilot_read_packet
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 6: Commit the tested policy packet**

```text
git add docs/contracts/task27_exact_single_pool_selection_and_pilot_read_packet_v1.md configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml catalog/schemas/task27_exact_single_pool_selection_and_pilot_read_packet.schema.json tests/fixtures/task27/exact_single_pool_selection_and_pilot_read_packet_v1.json tests/test_task27_exact_single_pool_selection_and_pilot_read_packet.py
git diff --cached --check
git commit -m "test: freeze TASK-27 single-pool pilot packet"
```

Expected: one ordinary commit containing exactly five paths; pre-commit gate PASS.

---

### Task 2: Add a content-bound offline acceptance receipt

**Files:**
- Modify: `tests/test_task27_exact_single_pool_selection_and_pilot_read_packet.py`
- Create: `docs/evidence/task27/a0a7_exact_single_pool_selection_and_pilot_read_packet_acceptance_v1.json`

**Interfaces:**
- Consumes: the four decision-bearing assets from Task 1 and their exact SHA-256 values.
- Produces: one receipt proving targeted validation, zero external effects, `STATE_CHANGE=NONE`, and the exact future owner gate.

- [ ] **Step 1: Add the failing receipt test**

Add `ACCEPTANCE_PATH` and this fifth test:

```python
def test_acceptance_receipt_binds_assets_and_preserves_offline_boundary(self) -> None:
    self.assertTrue(ACCEPTANCE_PATH.is_file(), ACCEPTANCE_PATH)
    receipt = load_json(ACCEPTANCE_PATH)
    expected_bindings = {
        CONTRACT_PATH.relative_to(ROOT).as_posix(): sha256(CONTRACT_PATH),
        CONFIG_PATH.relative_to(ROOT).as_posix(): sha256(CONFIG_PATH),
        SCHEMA_PATH.relative_to(ROOT).as_posix(): sha256(SCHEMA_PATH),
        FIXTURE_PATH.relative_to(ROOT).as_posix(): sha256(FIXTURE_PATH),
    }
    actual_bindings = {
        binding["path"]: binding["sha256"]
        for binding in receipt["artifact_bindings"].values()
    }
    self.assertEqual(actual_bindings, expected_bindings)
    self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
    self.assertEqual(receipt["validation"]["targeted_tests_run"], 5)
    self.assertEqual(receipt["validation"]["adversarial_cases_rejected"], 18)
    self.assertEqual(receipt["state_change"], "NONE")
    self.assertFalse(receipt["next_boundary"]["provider_read_authority_granted"])
    for value in receipt["measured_boundary"].values():
        self.assertIn(value, (0, False))
```

- [ ] **Step 2: Run the test and verify the red state**

Run the targeted unittest command from Task 1.

Expected: exactly one failure because the acceptance receipt does not exist;
the four Task 1 tests remain green.

- [ ] **Step 3: Create the acceptance receipt with measured hashes**

Create the receipt with:

- schema `smial.task27.a0a7.exact_single_pool_selection_and_pilot_read_packet.acceptance`;
- status `PASS_TARGETED_VALIDATION_PENDING_DELIVERY`;
- branch `task27/exact-single-pool-pilot-read-packet` and the exact Task 1 commit;
- four artifact bindings for contract/config/schema/fixture;
- targeted tests `5/5`, adversarial cases `18`, schema Draft `2020-12`;
- semantic PASS entries for identity, selection hash, fixed window, exact URLs,
  natural-only bars, raw-manifest requirement, no fallback, no authority, and
  no forbidden claims;
- Project Sources disposition `NO_CHANGE`;
- measured boundary values all zero/false;
- `state_change: NONE`;
- next boundary with `provider_read_authority_granted: false`,
  `requires_new_exact_owner_instruction: true`, exact request count `2`, and
  the approval phrase copied byte-for-byte from the YAML policy.

Calculate hashes from the working tree; do not copy them from terminal history.

- [ ] **Step 4: Run the complete targeted module**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task27_exact_single_pool_selection_and_pilot_read_packet
```

Expected: `Ran 5 tests` and `OK`.

- [ ] **Step 5: Commit the receipt and receipt test**

```text
git add tests/test_task27_exact_single_pool_selection_and_pilot_read_packet.py docs/evidence/task27/a0a7_exact_single_pool_selection_and_pilot_read_packet_acceptance_v1.json
git diff --cached --check
git commit -m "docs: record TASK-27 A7 offline acceptance"
```

Expected: one ordinary commit containing exactly two paths; pre-commit gate PASS.

---

### Task 3: Run the delivery gate and publish a Draft PR

**Files:**
- Verify only; no new tracked files.

**Interfaces:**
- Consumes: exact committed A7 candidate.
- Produces: tracked-only validation receipt, pushed branch, Draft PR, and exact-head CI read-back; no merge or external provider read.

- [ ] **Step 1: Verify exact committed inventory and clean state**

Run:

```text
git status --short --branch
git diff --name-status origin/main...HEAD
git diff --check origin/main...HEAD
```

Expected inventory: the design, this plan, and the six managed atom files;
working tree clean; no generated Catalog or Project Source change.

- [ ] **Step 2: Run the single local full-gate owner**

Run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: PASS within 15 minutes, no decision-critical skips, ignored receipt
under `local/delivery_preflight/`, and no tracked changes.

- [ ] **Step 3: Push the task branch without changing remote configuration**

Run:

```text
git push git@github.com:lancerbeta/solana-alpha-lab.git HEAD:refs/heads/task27/exact-single-pool-pilot-read-packet
```

Expected: non-force push succeeds over SSH.

- [ ] **Step 4: Create one Draft PR and read back exact head**

Create a Draft PR targeting `main` with title
`TASK-27: freeze exact single-pool pilot-read packet`. The body must state:

- exact atom and owner-nominated pool;
- offline-only two-request specification;
- targeted and tracked-only validation receipts;
- raw provider responses `0`, provider calls `0`;
- `STATE_CHANGE=NONE`;
- future exact owner gate required; and
- no TASK-27 acceptance, provider authority, PIT, alpha, execution, PnL,
  NetReturn, or cashflow claim.

Read back PR number, base SHA, exact head SHA, changed-file inventory, and CI
conclusion. If CI is pending, poll boundedly. If CI fails, diagnose only the
exact failure and repair no wider scope.

- [ ] **Step 5: Stop before Ready or merge**

Return the PR number, exact head, tests/CI/evidence, limits, Factory Fit
`FULL_REVIEW`, Product Horizon `NOW/WATCH`, and exact future owner action. Do
not mark the PR Ready and do not merge without the owner's exact confirmation
for that PR and head.

---

## Plan self-review

- Spec coverage: every design section maps to Task 1 policy/schema/tests or
  Task 2 receipt; Task 3 covers delivery without crossing the external gate.
- Scope: one subsystem and one bounded offline atom; no split is needed.
- Type consistency: `selection_snapshot`, `pilot`, `future_acceptance`,
  `authority`, `claims`, and `future_owner_approval` use the same keys across
  YAML, schema, fixture, semantic validator, and receipt.
- Validation economy: one red/green targeted cycle per implementation task and
  one tracked-only delivery full gate; no duplicate local full suite.
- Recovery: a failed pilot later emits `REDESIGN_PUBLIC_HISTORY_ROUTE` or
  `CLOSE_PUBLIC_HISTORY_ROUTE`; A7 itself has no provider or raw state to undo.
