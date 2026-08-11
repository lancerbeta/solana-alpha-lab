# T30-A11C Two-slot shakedown runtime harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested, fail-closed one-slot foreground runner that can later execute the A11B two-slot technical shakedown only after an exact owner external-read authorization.

**Architecture:** The Python module owns pure policy validation, authority-phrase parsing, request planning, receipt verification and a bounded dependency-injected transport.  The CLI owns argument parsing and local A4 writes for exactly one slot; it can dry-run without I/O or, only after a future exact owner phrase, execute at most four requests.  A second independent CLI invocation validates the first slot's receipt before it opens transport.

**Tech Stack:** Python 3.13 standard library, PyYAML, jsonschema, unittest, existing Catalog validator and navigation generator.  No new dependency, provider SDK, database, scheduler or remote service.

## Global Constraints

- Base: `origin/main` at `1dec3ed6bae3c73608e2db388fe8365ba1f15d87`; branch: `task30/a11c-two-slot-shakedown-runtime-harness`.
- Frozen candidate: public keyless GeckoTerminal HTTPS route for pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`, 900-second USD/base OHLCV intervals.
- One invocation owns one slot and four offsets `[0, 15, 30, 60]`; two separately started invocations are the sole way to reach the total cap of eight GETs.
- The tracked code accepts no credentials, retries, fallback, redirect, scheduler/background process, R2/R3, wallet/signer/transaction, spend or dependency change.
- `--execute` remains unusable until a later owner phrase binds both exact UTC slots, `LOCAL_WORK_CODEX_FOREGROUND`, `max_gets=8`, retention A4 and the no-retry/no-fallback terms.
- Raw bytes and runtime receipts are future-only, create-only and outside Git below `local/task30_two_slot_live_shakedown/`; no implementation-time provider request is permitted.
- Missing, malformed or failed observations remain typed unknowns.  This atom cannot claim PIT admissibility, H07/H01 evidence, a trial, execution, PnL, NetReturn, provider selection or 24-hour authority.
- Historical A11B artifacts remain unchanged.  Project Sources disposition is `NO_CHANGE`.

---

## File map

| Path | Responsibility |
| --- | --- |
| `docs/contracts/task30_two_slot_live_shakedown_runtime_contract_v1.md` | Human-readable executable boundary, authority grammar, artifacts and stop rules. |
| `configs/task30_two_slot_live_shakedown_runtime_v1.yaml` | Frozen non-time policy and zero-authority default. |
| `catalog/schemas/task30_two_slot_live_shakedown_runtime.schema.json` | Closed structural schema for the tracked policy. |
| `tests/fixtures/task30/two_slot_live_shakedown_runtime_v1.json` | Synthetic authority, healthy responses and expected non-promoting result. |
| `src/solana_alpha_lab/task30_two_slot_live_shakedown_runtime.py` | Pure validation, plan, bounded transport and receipt-chain implementation. |
| `scripts/run_task30_two_slot_live_shakedown.py` | One-slot `--dry-run`/future `--execute` CLI. |
| `tests/test_task30_two_slot_live_shakedown_runtime.py` | Test-first behavioural, timing, storage and adversarial checks. |
| `docs/evidence/task30/a11c_two_slot_live_shakedown_runtime_offline_acceptance_v1.json` | Hash-bound offline acceptance, FULL_REVIEW and zero-side-effect receipt. |
| `catalog/assets/core.yaml` | Stable IDs for the eight A11C artifacts. |
| `catalog/catalog_manifest.yaml` | New schema registration and exact checkpoint counts. |
| `catalog/assets/lifecycle.yaml` | Rebound integrity hashes for generated views. |
| `docs/PROJECT_MAP.md`, `catalog/generated/asset_edges.json`, `docs/OPERATOR_NAVIGATION.md` | Generated Catalog navigation; never hand-edit. |

## Task 1: Freeze the runtime contract and prove the zero-I/O boundary

**Files:**

- Create: `docs/contracts/task30_two_slot_live_shakedown_runtime_contract_v1.md`.
- Create: `configs/task30_two_slot_live_shakedown_runtime_v1.yaml`.
- Create: `catalog/schemas/task30_two_slot_live_shakedown_runtime.schema.json`.
- Create: `tests/fixtures/task30/two_slot_live_shakedown_runtime_v1.json`.
- Create: `tests/test_task30_two_slot_live_shakedown_runtime.py`.
- Create: `src/solana_alpha_lab/task30_two_slot_live_shakedown_runtime.py`.

**Interfaces:**

- Consumes: the A11B policy identity, A10 `START_LABELED`, A11A `OFFLINE_PROBE_POLICY_VALIDATED`, frozen pool and A4 retention rule.
- Produces: `validate_runtime_policy(policy) -> dict[str, object]`, `parse_execution_authority(text) -> dict[str, object]`, and `build_slot_plan(policy, authority, slot_index, now_epoch) -> list[dict[str, object]]`.

- [ ] **Step 1: Write the first failing policy/authority test**

```python
def test_exact_authority_and_first_slot_plan_have_four_gets_and_zero_io(self) -> None:
    policy = load_yaml(POLICY_PATH)
    authority = parse_execution_authority(
        "T30-A11C_TWO_SLOT_SHAKEDOWN_EXECUTION_V1;"
        "pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S;"
        "slot_starts_utc=2026-08-12T10:00:00Z,2026-08-12T10:15:00Z;"
        "monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND;max_gets=8;"
        "retention=A4;retry=false;fallback=false"
    )
    plan = build_slot_plan(policy, authority, slot_index=1, now_epoch=1786529670)
    self.assertEqual([item["offset_seconds"] for item in plan], [0, 15, 30, 60])
    self.assertTrue(all(item["method"] == "GET" for item in plan))
    self.assertTrue(all(item["before_timestamp"] == 1786529700 for item in plan))
```

- [ ] **Step 2: Run the test and observe the expected missing-module failure**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_exact_authority_and_first_slot_plan_have_four_gets_and_zero_io -v
```

Expected: `FAIL` because `solana_alpha_lab.task30_two_slot_live_shakedown_runtime` does not exist.

- [ ] **Step 3: Create the contract, policy, schema and fixture**

The policy must require `schema: smial.task30.two-slot-live-shakedown-runtime`, atom `T30-A11C_TWO_SLOT_SHAKEDOWN_RUNTIME_HARNESS_V1`, exact pool/network, `aggregate=15`, `currency=usd`, `token=base`, `include_empty_intervals=false`, `limit=1`, offsets `[0, 15, 30, 60]`, `requests_per_slot_max: 4`, `requests_total_max: 8`, `request_timeout_seconds: 20`, `response_bytes_max: 4194304`, `late_offset_seconds_max: 15`, `retry: false`, `fallback: false`, `credentials: false`, `scheduler: false`, `raw_json_outside_git: true`, and every non-claim set to false.

The JSON Schema must set `additionalProperties: false` for the policy root and every policy sub-object.  The fixture uses only synthetic JSON response bytes and expected technical-only classification.

- [ ] **Step 4: Implement minimal pure validation and planning**

```python
class TwoSlotShakedownRuntimeError(ValueError):
    """Raised before an unsafe plan can reach transport."""

def parse_execution_authority(text: str) -> dict[str, object]:
    """Parse the only accepted non-secret owner phrase or fail closed."""

def build_slot_plan(
    policy: Mapping[str, Any],
    authority: Mapping[str, object],
    *,
    slot_index: int,
    now_epoch: int,
) -> list[dict[str, object]]:
    """Return exactly four future, same-host GET descriptions for one slot."""
```

`build_slot_plan` rejects a non-UTC timestamp, unequal/non-consecutive
15-minute slot starts, a non-future start, slot index outside `{1, 2}`, an
already-missed offset, changed pool, cap drift, retry/fallback, or any phrase
term outside the exact grammar.  It has no file or network effect.

- [ ] **Step 5: Run the focused test and schema validation**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_exact_authority_and_first_slot_plan_have_four_gets_and_zero_io -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
```

Expected: focused test passes; Catalog is temporarily unchanged and remains valid.

## Task 2: Implement one-slot foreground transport and the immutable receipt chain

**Files:**

- Modify: `src/solana_alpha_lab/task30_two_slot_live_shakedown_runtime.py`.
- Modify: `tests/test_task30_two_slot_live_shakedown_runtime.py`.

**Interfaces:**

- Consumes: `build_slot_plan`, a `Callable[[Mapping[str, object]], Capture]` fake/real transport, injected UTC clock and sleep callable.
- Produces: `run_slot(policy, authority, slot_index, raw_root, transport, now, sleep, prior_receipt=None) -> dict[str, object]` and `verify_prior_slot_receipt(path, authority) -> dict[str, object]`.

- [ ] **Step 1: Write failing happy-path and unsafe-second-slot tests**

```python
def test_healthy_fake_first_slot_writes_four_immutable_checkpoints(self) -> None:
    result = run_slot(policy(), authority(), slot_index=1, raw_root=self.temp_root,
                      transport=FakeTransport(healthy_response_bytes()),
                      now=FakeClock.at_slot_end(), sleep=FakeClock.sleep)
    self.assertEqual(result["terminal_state"], "SLOT_TECHNICAL_HEALTHY")
    self.assertEqual(len(list(self.temp_root.glob("raw/*.json"))), 4)
    self.assertEqual(len(list(self.temp_root.glob("raw_manifest_*.json"))), 4)
    self.assertEqual(len(list(self.temp_root.glob("health_receipt_*.json"))), 4)

def test_second_slot_rejects_altered_first_receipt_before_transport(self) -> None:
    with self.assertRaisesRegex(TwoSlotShakedownRuntimeError, "PRIOR_RECEIPT"):
        run_slot(policy(), authority(), slot_index=2, raw_root=self.temp_root,
                 transport=FailIfCalledTransport(), now=FakeClock.for_slot_two(),
                 sleep=FakeClock.sleep, prior_receipt=self.altered_receipt)
```

- [ ] **Step 2: Run both tests and observe the expected absent-interface failures**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_healthy_fake_first_slot_writes_four_immutable_checkpoints tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_second_slot_rejects_altered_first_receipt_before_transport -v
```

Expected: `FAIL` because `run_slot` and receipt verification do not exist.

- [ ] **Step 3: Add the bounded transport and create-only checkpoint writer**

Implement a transport that validates HTTPS, `api.geckoterminal.com`, the exact
`/api/v2/networks/solana/pools/{pool}/ohlcv/minute` path and query before
calling `urllib.request`.  It rejects redirects, uses a 20-second timeout and
reads at most `response_bytes_max + 1` bytes.  It returns a sanitized capture
record plus raw bytes; it never retries.

For each ordinal, write raw bytes with exclusive create, then
`raw_manifest_<ordinal>.json`, then `health_receipt_<ordinal>.json`, each with
canonical JSON and SHA-256.  If any write fails, produce a create-only
`STOP_RUN` receipt when possible and make no later request.  `run_slot` must
call the injected clock/sleep only until the exact offset, reject a late offset
greater than 15 seconds and never compress missed calls.

`verify_prior_slot_receipt` checks the first-slot authority fingerprint,
slot-index 1, healthy terminal state, raw-manifest chain and all referenced
SHA-256 values before slot two can initialize transport.

- [ ] **Step 4: Add adversarial tests before expanding implementation**

```python
def test_late_offset_stops_before_any_request(self) -> None:
    transport = FailIfCalledTransport()
    result = run_slot(policy(), authority(), slot_index=1, raw_root=self.temp_root,
                      transport=transport, now=FakeClock.after_first_offset_limit(),
                      sleep=FakeClock.sleep)
    self.assertEqual(result["terminal_state"], "STOP_RUN")
    self.assertEqual(transport.calls, 0)

def test_invalid_interval_start_is_a_typed_gap_not_research_evidence(self) -> None:
    result = run_slot(policy(), authority(), slot_index=1, raw_root=self.temp_root,
                      transport=FakeTransport(wrong_interval_response_bytes()),
                      now=FakeClock.at_slot_end(), sleep=FakeClock.sleep)
    self.assertEqual(result["terminal_state"], "SLOT_TECHNICAL_INCONCLUSIVE")
    self.assertFalse(result["claims"]["pit_admissible"])
    self.assertFalse(result["claims"]["h07_h01_evidence"])
```

- [ ] **Step 5: Run the complete runtime test module**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime -v
```

Expected: all fake-transport, timing, write-chain, prior-receipt and
non-promotion checks pass with zero external requests.

## Task 3: Provide a one-slot CLI and prove dry-run versus execute gating

**Files:**

- Create: `scripts/run_task30_two_slot_live_shakedown.py`.
- Modify: `tests/test_task30_two_slot_live_shakedown_runtime.py`.
- Modify: `src/solana_alpha_lab/task30_two_slot_live_shakedown_runtime.py` only if an exported `main` helper is needed.

**Interfaces:**

- Consumes: tracked policy plus `--slot-index`, `--authority`, `--raw-root` and one mutually exclusive mode.
- Produces: deterministic JSON for `--dry-run`; `slot_receipt_v1.json` only during a separately authorized future `--execute` run.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_cli_dry_run_emits_four_requests_and_creates_no_output(self) -> None:
    completed = subprocess.run(DRY_RUN_COMMAND, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.assertEqual(completed.returncode, 0, completed.stderr)
    payload = json.loads(completed.stdout)
    self.assertEqual(payload["network_calls"], 0)
    self.assertEqual(len(payload["plan"]), 4)

def test_cli_execute_without_exact_authority_fails_before_network_io(self) -> None:
    completed = subprocess.run(EXECUTE_WITH_BAD_AUTHORITY_COMMAND, cwd=ROOT,
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.assertNotEqual(completed.returncode, 0)
    self.assertIn("AUTHORITY", completed.stderr)
```

- [ ] **Step 2: Run the CLI tests and observe the expected missing-script failure**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_cli_dry_run_emits_four_requests_and_creates_no_output tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_cli_execute_without_exact_authority_fails_before_network_io -v
```

Expected: `FAIL` because the runner script is absent.

- [ ] **Step 3: Implement the CLI with mutually exclusive modes**

```python
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--dry-run", action="store_true")
mode.add_argument("--execute", action="store_true")
parser.add_argument("--slot-index", type=int, choices=(1, 2), required=True)
parser.add_argument("--authority", required=True)
parser.add_argument("--prior-receipt", type=Path)
```

`--dry-run` calls only `build_slot_plan` and prints `network_calls: 0` plus
`output_created: false`.  `--execute` uses the bounded transport only after all
authority, timing, output-root and prior-receipt checks pass.  It accepts no
environment variable, API key or fallback switch.  Slot two requires
`--prior-receipt`; slot one rejects it.

- [ ] **Step 4: Run the CLI tests and direct consumer tests**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime tests.test_task30_gecko_interval_semantics_runner tests.test_task30_route_availability_probe tests.test_task30_two_slot_live_shakedown_owner_packet -v
```

Expected: PASS; no process has contacted GeckoTerminal.

## Task 4: Bind offline acceptance, Catalog and generated navigation

**Files:**

- Create: `docs/evidence/task30/a11c_two_slot_live_shakedown_runtime_offline_acceptance_v1.json`.
- Modify: `tests/test_task30_two_slot_live_shakedown_runtime.py`.
- Modify: `catalog/assets/core.yaml`.
- Modify: `catalog/catalog_manifest.yaml`.
- Modify: `catalog/assets/lifecycle.yaml`.
- Regenerate: `docs/PROJECT_MAP.md`, `catalog/generated/asset_edges.json`, `docs/OPERATOR_NAVIGATION.md`.

**Interfaces:**

- Consumes: every tracked A11C artifact and Catalog generator.
- Produces: eight discoverable asset IDs, hash-bound offline evidence and current generated navigation.

- [ ] **Step 1: Write failing acceptance and Catalog assertions**

```python
def test_offline_acceptance_binds_runtime_artifacts_and_zero_side_effects(self) -> None:
    receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    self.assertEqual(receipt["validation_status"], "PASS_WITH_LIMITATIONS")
    self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
    self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
    self.assertFalse(receipt["non_claims"]["twenty_four_hour_capture_authorized"])

def test_catalog_registers_all_eight_runtime_assets(self) -> None:
    records = load_yaml(CATALOG_CORE_PATH)["records"]
    self.assertTrue(EXPECTED_A11C_ASSET_IDS.issubset({record["asset_id"] for record in records}))
```

- [ ] **Step 2: Run the tests and observe expected missing-acceptance failure**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_offline_acceptance_binds_runtime_artifacts_and_zero_side_effects tests.test_task30_two_slot_live_shakedown_runtime.Task30TwoSlotLiveShakedownRuntimeTests.test_catalog_registers_all_eight_runtime_assets -v
```

Expected: `FAIL` because A11C receipt and stable asset IDs do not exist.

- [ ] **Step 3: Create receipt and add only required Catalog records**

Use these IDs:

```text
CONTRACT-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
CONFIG-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
SCHEMA-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
FIXTURE-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
MODULE-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
SCRIPT-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
TEST-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
EVIDENCE-T30-A11C-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001
```

Every record has `truth_owner: TASK-30`, `contains_secrets: false`,
`contains_raw_data: false`, `consumers: [TASK-30, FACTORY-001]` and relations
to its direct contract/config/module/test/evidence owner.  Add the new schema
to `root_resolver.schemas`, change `schemas` from 27 to 28 and `assets` from
683 to 691.  The receipt binds the contract, config, schema, fixture, module,
script, test, design and plan hashes; sets `FULL_REVIEW`,
`PASS_WITH_LIMITATIONS`, `state_change: NONE`, `project_sources_disposition:
NO_CHANGE` and every external counter to zero.

- [ ] **Step 4: Generate, rebind and check Catalog views**

```powershell
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

After generation, update only the generated-view SHA-256 values in
`catalog/assets/lifecycle.yaml`, then re-run the three commands until the
checker is clean.  Never edit the three generated outputs directly.

- [ ] **Step 5: Run targeted acceptance and Catalog checks**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_runtime tests.test_catalog tests.test_generate_navigation -v
```

Expected: PASS with no provider call, raw write, credential, spend or Project
Sources change.

## Task 5: Delivery and independent validation

**Files:**

- Modify only the files created or enumerated in Tasks 1–4.

**Interfaces:**

- Consumes: one clean committed candidate.
- Produces: tracked-only receipt, exact PR head, CI read-back and a compact A11C checkpoint.

- [ ] **Step 1: Inspect the exact write set and security boundary**

```powershell
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
rg -n -i "api[_-]?key|token|secret|seed|private[_-]?key|password" --glob '!uv.lock' --glob '!docs/evidence/pre_git/**' .
```

Expected: only planned tracked artifacts and no secret-bearing value.

- [ ] **Step 2: Commit the complete candidate**

```powershell
git add -- <exact planned paths>
git commit -m "feat: add task30 two-slot shakedown harness"
```

- [ ] **Step 3: Run one tracked-only delivery preflight**

```powershell
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: PASS within the 15-minute cap.  Do not run a duplicate ordinary full
gate for unchanged bytes.

- [ ] **Step 4: Push, open PR and read back CI on the exact head**

```powershell
git push --set-upstream origin task30/a11c-two-slot-shakedown-runtime-harness
gh pr create --draft --base main --head task30/a11c-two-slot-shakedown-runtime-harness --title "feat: add TASK-30 two-slot shakedown harness"
gh pr checks --watch
```

Expected: CI passes for the exact pushed head.  Apply `OWNER_ATTENTION_GATE`;
the offline implementation and ordinary repository transport are autonomous,
but no provider execution occurs.

## Plan self-review

- Spec coverage: Tasks 1–3 cover exact authority, one-slot separation,
timing, bounded transport, A4 persistence and no hidden retry; Task 4 covers
proof, Catalog and generated navigation; Task 5 covers delivery.
- Scope: one runner and one CLI only; no generic collector, scheduler, adapter,
database or UI is introduced.
- Type consistency: `parse_execution_authority`, `build_slot_plan`, `run_slot`
and `verify_prior_slot_receipt` are defined before their consumers; slot index
is consistently integer `1` or `2`.
- Placeholder scan: no deferred implementation marker or unspecified error
path remains.  All terminal error categories map to fail-closed `STOP_RUN` or
pre-transport rejection.
