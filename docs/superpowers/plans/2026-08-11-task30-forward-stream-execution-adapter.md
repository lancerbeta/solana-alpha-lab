# TASK-30 A14P Forward-Stream Execution Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate one offline execution adapter that can later perform exactly one owner-authorised, foreground, target-locked Helius `transactionSubscribe` capture with durable A4 raw evidence and fail-closed recovery.

**Architecture:** Keep `task30_forward_stream_runtime.py` as the target and terminal-truth owner, wrap the existing TASK-08 `websockets_wss_exchange()` rather than copying socket logic, and add one focused execution module that owns create-only attempt state plus exact raw retention. A thin CLI supplies the production environment/transport only after all non-secret preflight checks and the exact owner phrase pass.

**Tech Stack:** Python 3.13, standard library, existing `websockets` 16.1.1 dependency, PyYAML, jsonschema, unittest, Git/Catalog validators.

## Global Constraints

- Network and target remain `solana`, pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`, base mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`.
- The only proposed wire route is Helius `transactionSubscribe` with `accountInclude=[pool]`, `failed=false`, `vote=false`, `confirmed`, `jsonParsed`, `full`, and `maxSupportedTransactionVersion=0`.
- Effective caps remain one connection, one subscription, 540 seconds, 500 notifications, 1,000,000 stream bytes, 100,000 bytes per frame and estimated credit cap 21.
- `retry=false`, `reconnect=false`, `fallback=false`, `scheduler=false`; monitoring is foreground-only.
- Raw bytes live only under ignored logical root `local/task30_forward_stream`; no absolute machine path enters tracked artifacts or Catalog.
- `HELIUS_API_KEY` is read only in execute mode, after exact authority, policy, target, unresolved-attempt and raw-root checks pass; it never enters output, tracked files, receipts, object representations or exceptions.
- No provider/API/RPC/WSS call, credential read or raw external-data write occurs while implementing or validating this plan.
- No dependency, R2/R3, wallet, signer, transaction, cash, trial, PIT, alpha, PnL, NetReturn or Project Sources action is in scope.
- A second external attempt is forbidden while any prior run lacks a valid terminal receipt.

---

### Task 1: Freeze the A14P policy without rewriting accepted A14 evidence

**Files:**
- Create: `configs/task30_forward_stream_execution_adapter_v1.yaml`
- Create: `catalog/schemas/task30_forward_stream_execution_adapter.schema.json`
- Create: `tests/fixtures/task30/forward_stream_execution_adapter_v1.json`
- Create: `tests/test_task30_forward_stream_execution.py`

**Interfaces:**
- Consumes: accepted A14 policy path and immutable A14 artifact bindings.
- Produces: exact closed execution-policy bytes consumed by Task 2.

Do not modify `task30_forward_stream_runtime.py`, its test or the historical
A14 acceptance receipt. Those bytes are hash-bound accepted evidence. A14P
must mediate TASK-08 transport terminals in its new module instead of silently
rewriting A14 history.

- [ ] **Step 1: Write the closed A14P policy/schema/fixture tests**

The policy must have `additionalProperties: false` at every object layer and
freeze these fields:

```yaml
schema: smial.task30.forward-stream-execution-adapter.policy
schema_version: '1.0'
task_id: TASK-30
atom_id: T30-A14P_FORWARD_STREAM_EXECUTION_ADAPTER_V1
consumer: EXACT_OWNER_FORWARD_STREAM_EXTERNAL_GATE
runtime_policy: configs/task30_forward_stream_runtime_harness_v1.yaml
retention:
  class: A4
  logical_root: local/task30_forward_stream
  started_receipt: attempt_started.json
  manifest: raw_manifest.json
  terminal_receipt: terminal_receipt.json
  create_only: true
credential:
  environment_variable: HELIUS_API_KEY
  read_after_started_receipt: true
execution:
  max_attempts: 1
  retry: false
  reconnect: false
  fallback: false
  scheduler: false
authority:
  provider_api_rpc_wss_calls: 0
  credential_read: false
  raw_external_data_write: false
decision: OFFLINE_EXECUTION_ADAPTER_PENDING_IMPLEMENTATION
project_sources_disposition: NO_CHANGE
```

In `tests/test_task30_forward_stream_execution.py`, validate the YAML against
the schema, compare it with the fixture and adversarially reject extra keys,
booleans in integer fields, alternate roots, alternate environment names and
any true/non-zero authority value.

- [ ] **Step 2: Run the new policy tests and confirm RED, then add only the declared files**

Run before creating the policy files:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution
```

Expected: missing configuration/schema/fixture failure. Create the exact YAML,
closed JSON Schema and fixture, then rerun the same command and expect PASS.

- [ ] **Step 3: Commit Task 1**

```text
git add configs/task30_forward_stream_execution_adapter_v1.yaml catalog/schemas/task30_forward_stream_execution_adapter.schema.json tests/fixtures/task30/forward_stream_execution_adapter_v1.json tests/test_task30_forward_stream_execution.py
git diff --cached --check
git commit -m "test: freeze forward stream execution policy"
```

---

### Task 2: Implement create-only A4 attempt and raw retention

**Files:**
- Create: `src/solana_alpha_lab/task30_forward_stream_execution.py`
- Modify: `tests/test_task30_forward_stream_execution.py`

**Interfaces:**
- Consumes: A14P policy from Task 1, A14 `OWNER_EXECUTION_PHRASE`, `bind_transaction_subscribe()`, `RuntimeCapture`, `classify_forward_stream_capture()`, and TASK-08 `WssCapture`.
- Produces:
  - `validate_forward_stream_preflight(execution_config: Mapping[str, Any], runtime_config: Mapping[str, Any], *, authority_phrase: str, repository_root: Path, raw_root: Path) -> dict[str, object]`
  - `prepare_forward_stream_attempt(execution_config: Mapping[str, Any], runtime_config: Mapping[str, Any], *, authority_phrase: str, repository_root: Path, raw_root: Path, now: datetime, nonce: str) -> StartedAttempt`
  - `classify_task08_capture(runtime_config: Mapping[str, Any], capture: WssCapture) -> dict[str, object]`
  - `execute_forward_stream_attempt(execution_config: Mapping[str, Any], runtime_config: Mapping[str, Any], *, authority_phrase: str, repository_root: Path, raw_root: Path, credential_loader: Callable[[str], str], wss_exchange: Callable[..., WssCapture], clock: Callable[[], datetime], nonce_factory: Callable[[], str]) -> dict[str, object]`
  - `find_unresolved_attempts(raw_root: Path) -> tuple[str, ...]`
  - `ForwardStreamExecutionError(code: str)`

- [ ] **Step 1: Write failing preflight tests**

Use `TemporaryDirectory` and injected counters:

```python
def test_wrong_authority_fails_before_credential_transport_or_write(self) -> None:
    calls = {"credential": 0, "transport": 0}
    with self.assertRaisesRegex(ForwardStreamExecutionError, "PILOT_NOT_AUTHORIZED"):
        execute_forward_stream_attempt(
            execution_policy(), runtime_policy(),
            authority_phrase="WRONG",
            repository_root=self.root,
            raw_root=self.raw_root,
            credential_loader=counting_credential(calls),
            wss_exchange=counting_transport(calls),
            clock=lambda: FROZEN_NOW,
            nonce_factory=lambda: "a1b2c3d4",
        )
    self.assertEqual(calls, {"credential": 0, "transport": 0})
    self.assertFalse(self.raw_root.exists())

def test_unresolved_attempt_blocks_next_attempt(self) -> None:
    first = prepare_forward_stream_attempt(
        execution_policy(), runtime_policy(),
        authority_phrase=OWNER_EXECUTION_PHRASE,
        repository_root=self.root,
        raw_root=self.raw_root,
        now=FROZEN_NOW,
        nonce="a1b2c3d4",
    )
    self.assertEqual(find_unresolved_attempts(self.raw_root), (first.run_id,))
    with self.assertRaisesRegex(ForwardStreamExecutionError, "UNRESOLVED_PRIOR_ATTEMPT"):
        prepare_forward_stream_attempt(
            execution_policy(), runtime_policy(),
            authority_phrase=OWNER_EXECUTION_PHRASE,
            repository_root=self.root,
            raw_root=self.raw_root,
            now=FROZEN_NOW,
            nonce="e5f6a7b8",
        )
```

Also cover absolute-root requirement, exact logical-root containment, symlink
components, existing run collision, naïve timestamps, unsafe nonce and type
confusion.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution
```

Expected: import or missing-interface failure.

- [ ] **Step 3: Implement strict policy evaluation and started-attempt publication**

Use focused types and create-only publication:

```python
@dataclass(frozen=True, slots=True)
class StartedAttempt:
    run_id: str
    run_root: Path
    logical_run_root: str
    started_at: datetime
    planned_request_receipt: Mapping[str, object]

def _publish_new(path: Path, body: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)
    temporary.unlink()
```

`validate_forward_stream_preflight()` must validate the execution and A14
runtime policies, exact owner phrase, raw-root identity, absence of unresolved
attempts and all types without creating the root. `prepare_forward_stream_attempt()`
calls that function and then publishes the started marker. Compute the
non-secret planned request receipt using
`bind_transaction_subscribe("offline-preflight-sentinel")` and require the real
request's later safe receipt to match it exactly.

- [ ] **Step 4: Run preflight tests and confirm GREEN**

Run the test module from Step 2. Expected: preflight tests pass; capture tests
that have not yet been added are absent rather than skipped.

- [ ] **Step 5: Write failing exact-retention and terminal tests**

Construct real TASK-08 `WssCapture` values with aware timestamps. Cover one
valid notification, zero notifications, remote close, oversized response,
JSON-RPC subscription error, subscription-id drift and a simulated raw-file
publication failure.

The happy-path assertions must reproduce every hash from disk:

```python
FAKE_CREDENTIAL = "synthetic-" + "credential-value"
receipt = execute_forward_stream_attempt(
    execution_policy(), runtime_policy(),
    authority_phrase=OWNER_EXECUTION_PHRASE,
    repository_root=self.root,
    raw_root=self.raw_root,
    credential_loader=lambda name: FAKE_CREDENTIAL,
    wss_exchange=fake_success,
    clock=lambda: FROZEN_NOW,
    nonce_factory=lambda: "a1b2c3d4",
)
self.assertEqual(receipt["terminal_state"], "OBSERVATION_RETAINED_TECHNICAL_ONLY")
self.assertEqual(receipt["notifications"], 1)
self.assertEqual(receipt["logical_run_root"], f"local/task30_forward_stream/run={receipt['run_id']}")
manifest = json.loads((run_root / "raw_manifest.json").read_text(encoding="utf-8"))
for item in manifest["raw_objects"]:
    body = (run_root / item["path"]).read_bytes()
    self.assertEqual(item["bytes"], len(body))
    self.assertEqual(item["sha256"], hashlib.sha256(body).hexdigest())
```

Assert the fake secret is absent from recursive local files, receipt JSON,
exceptions and `repr()` of all new objects.

- [ ] **Step 6: Implement one-shot execution and retention**

The orchestration order is fixed:

```python
attempt = prepare_forward_stream_attempt(
    execution_config,
    runtime_config,
    authority_phrase=authority_phrase,
    repository_root=repository_root,
    raw_root=raw_root,
    now=clock(),
    nonce=nonce_factory(),
)
credential_value = credential_loader("HELIUS_API_KEY")
request = bind_transaction_subscribe(credential_value)
_require(request.safe_receipt() == attempt.planned_request_receipt, "REQUEST_RECEIPT_DRIFT")
wss_capture = wss_exchange(
    request,
    max_open_seconds=MAX_OPEN_SECONDS,
    max_stream_bytes=MAX_STREAM_BYTES,
    max_notifications=MAX_NOTIFICATIONS,
)
_require(type(wss_capture) is WssCapture, "WSS_CAPTURE_TYPE_INVALID")
manifest = retain_exact_capture(attempt, wss_capture)
classification = classify_task08_capture(runtime_config, wss_capture)
return publish_terminal_receipt(attempt, manifest, classification)
```

Persist acknowledgement and notifications before semantic classification so
malformed provider bytes remain auditable. Verify retained bytes from disk
before publishing the manifest. If raw retention fails while a terminal receipt
can still be written, emit `RETENTION_FAILED_STOP`; if the root is no longer
writable, leave only `UNRESOLVED_EXTERNAL_ATTEMPT` and raise a sanitized error.

`classify_task08_capture()` is the compatibility seam that preserves accepted
A14 bytes. For any TASK-08 terminal other than `BOUND_REACHED`, return
`TRANSPORT_LOST_UNKNOWN` with `unknown=true` after enforcing byte/frame caps.
Only a bounded capture is converted to `RuntimeCapture` and passed to the A14
classifier. Catch only `SUBSCRIPTION_REJECTED` to emit that exact closed
terminal; other schema/identity errors remain fail-closed adapter errors.

- [ ] **Step 7: Run adapter, A14 and TASK-08 compatibility suites**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution tests.test_task30_forward_stream_runtime tests.test_task08_lifecycle_discovery_transport
```

Expected: PASS with no real network calls and no retained test output outside
temporary directories.

- [ ] **Step 8: Commit Task 2**

```text
git add src/solana_alpha_lab/task30_forward_stream_execution.py tests/test_task30_forward_stream_execution.py
git diff --cached --check
git commit -m "feat: add bounded forward stream execution adapter"
```

---

### Task 3: Add the guarded foreground CLI

**Files:**
- Create: `scripts/run_task30_forward_stream_capture.py`
- Modify: `tests/test_task30_forward_stream_execution.py`

**Interfaces:**
- Consumes: `execute_forward_stream_attempt()` and `websockets_wss_exchange()`.
- Produces: `main(argv: Sequence[str] | None = None, *, environ: Mapping[str, str] | None = None, wss_exchange: Callable[..., WssCapture] = websockets_wss_exchange) -> int`.

- [ ] **Step 1: Write failing CLI tests**

Test `main()` directly with injected environment and transport. Required cases:

```python
def test_dry_run_does_not_read_key_write_or_call_transport(self) -> None:
    result = cli.main(
        ["--dry-run", "--authority", OWNER_EXECUTION_PHRASE,
         "--raw-root", str(self.raw_root)],
        environ=ExplodingMapping(),
        wss_exchange=fail_if_called,
    )
    self.assertEqual(result, 0)
    self.assertFalse(self.raw_root.exists())

def test_execute_reads_named_environment_key_only_after_started_marker(self) -> None:
    observed = {}
    fake_credential = "synthetic-" + "credential-value"
    result = cli.main(
        ["--execute", "--authority", OWNER_EXECUTION_PHRASE,
         "--raw-root", str(self.raw_root)],
        environ=RecordingMapping({"HELIUS_API_KEY": fake_credential}),
        wss_exchange=fake_success,
    )
    self.assertEqual(result, 0)
    self.assertTrue(observed["started_marker_existed_before_environment_read"])
```

Also reject both/neither mode, clock overrides in execute mode, unknown flags,
relative roots and any execute request without the exact phrase. Capture stdout
and stderr and assert the fake secret and raw payload are absent.

- [ ] **Step 2: Run CLI tests and confirm RED**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution
```

Expected: missing CLI module or `main()` failure.

- [ ] **Step 3: Implement the thin CLI**

Use a mutually exclusive required mode group. Load both versioned YAML files
from repository-relative constants. In dry-run, call only the pure policy,
authority and root validators and emit:

```json
{"credential_read":false,"network_calls":0,"output_created":false,"result":"DRY_RUN_PASS"}
```

In execute mode, use a loader that returns only `environ["HELIUS_API_KEY"]`
and passes the value directly to the execution module. Catch only known
`ForwardStreamExecutionError` / `ForwardStreamRuntimeError` classes and emit a
sanitized error code; unexpected exceptions must become
`UNCLASSIFIED_LOCAL_FAILURE` without `repr(exc)`.

- [ ] **Step 4: Run CLI and compatibility tests and confirm GREEN**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution tests.test_task30_forward_stream_runtime
```

Expected: PASS, zero network calls.

- [ ] **Step 5: Run the real CLI only in dry-run mode**

```text
$rawRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) 'local/task30_forward_stream'))
uv run --locked --managed-python python -B scripts/run_task30_forward_stream_capture.py --dry-run --authority "T30-A14P_FORWARD_STREAM_RUNTIME_V1; pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; max_wss_connections=1; max_subscriptions=1; max_open_seconds=1200; max_notifications=500; max_stream_bytes=1000000; estimated_credit_cap=21; retention=A4; retry=false; reconnect=false; fallback=false" --raw-root $rawRoot
```

Expected sanitized JSON: `DRY_RUN_PASS`, zero credential reads, zero calls and
zero output. The resolved machine path is process-local and never enters a
tracked artifact or Catalog record.

- [ ] **Step 6: Commit Task 3**

```text
git add scripts/run_task30_forward_stream_capture.py tests/test_task30_forward_stream_execution.py
git diff --cached --check
git commit -m "feat: add guarded forward stream capture runner"
```

---

### Task 4: Bind acceptance, Factory Fit and Catalog; deliver the offline candidate

**Files:**
- Create: `docs/tasks/TASK-30-forward-stream-execution-adapter.md`
- Create: `docs/contracts/task30_forward_stream_execution_adapter_contract_v1.md`
- Create: `docs/evidence/task30/a14p_forward_stream_execution_adapter_acceptance_v1.json`
- Create: `docs/evidence/task30/a14p_forward_stream_execution_adapter_factory_fit_v1.json`
- Modify: `tests/test_task30_forward_stream_execution.py`
- Modify: `catalog/assets/core.yaml`
- Modify generated: `catalog/catalog_manifest.yaml`
- Modify generated: `catalog/generated/asset_edges.json`
- Modify generated: `docs/PROJECT_MAP.md`
- Modify generated/hash binding if required: `catalog/assets/lifecycle.yaml`

**Interfaces:**
- Consumes: exact committed implementation/config/schema/fixture/CLI/test bytes from Tasks 1–3.
- Produces: Catalog-discoverable offline candidate and a machine-bound decision `READY_FOR_EXACT_OWNER_EXTERNAL_GATE_WITH_LIMITATIONS`.

- [ ] **Step 1: Write failing artifact-binding and Catalog tests**

Require the acceptance receipt to bind SHA-256 for task, contract, config,
schema, fixture, module, runner, test, design and Factory Fit artifacts. Require
zero authority/side-effect counters, `project_sources_disposition=NO_CHANGE`,
`external_capture_authorized=false`, `raw_external_data_collected=false` and
the following Catalog IDs:

```text
CONTRACT-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001
CONFIG-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001
SCHEMA-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001
FIXTURE-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001
MODULE-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001
SCRIPT-T30-FORWARD-STREAM-CAPTURE-001
TEST-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001
EVIDENCE-T30-A14P-FORWARD-STREAM-EXECUTION-ADAPTER-001
EVIDENCE-T30-A14P-FORWARD-STREAM-EXECUTION-FACTORY-FIT-001
```

- [ ] **Step 2: Run binding tests and confirm RED**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution
```

Expected: missing docs/evidence/Catalog identifiers.

- [ ] **Step 3: Create the bounded task/contract and FULL Factory Fit evidence**

The tracked acceptance decision is exactly:

```json
{
  "validation_status": "PASS_WITH_LIMITATIONS",
  "state_change": "NONE",
  "decision": {
    "value": "READY_FOR_EXACT_OWNER_EXTERNAL_GATE_WITH_LIMITATIONS",
    "external_capture_authorized": false,
    "raw_external_data_collected": false,
    "task30_trial_admissible": false
  },
  "project_sources_disposition": {"kind": "NO_CHANGE"}
}
```

The Factory Fit review is `FULL_REVIEW` and explicitly checks research truth,
secret handling, owner operability, compatibility with A14/TASK-08, recovery,
reuse-first, execution-to-cashflow non-applicability and adversarial stop cases.

- [ ] **Step 4: Register only durable product/control artifacts and regenerate consumers**

Register the nine IDs above with exact versions, paths, hashes, relations and
consumers `[TASK-30, FACTORY-001]`. Keep the design and implementation plan as
hash-bound process docs outside Catalog product assets. Run the canonical
generator rather than editing generated files by hand:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py
```

- [ ] **Step 5: Run targeted semantic acceptance**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_execution tests.test_task30_forward_stream_runtime tests.test_task08_lifecycle_discovery_transport
uv run --locked --managed-python python -B -m unittest tests.test_catalog
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: all commands PASS and the worktree contains only the declared A14P
write set plus mechanically required Catalog/generated hash consumers.

- [ ] **Step 6: Commit Task 4**

```text
git add docs/tasks/TASK-30-forward-stream-execution-adapter.md docs/contracts/task30_forward_stream_execution_adapter_contract_v1.md docs/evidence/task30/a14p_forward_stream_execution_adapter_acceptance_v1.json docs/evidence/task30/a14p_forward_stream_execution_adapter_factory_fit_v1.json tests/test_task30_forward_stream_execution.py catalog/assets/core.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md catalog/assets/lifecycle.yaml docs/superpowers/specs/2026-08-11-task30-forward-stream-execution-adapter-design.md docs/superpowers/plans/2026-08-11-task30-forward-stream-execution-adapter.md
git diff --cached --check
git commit -m "test: accept TASK-30 forward stream execution adapter"
```

- [ ] **Step 7: Run the exact delivery gate once**

This candidate changes a schema and validation tests, so it is ineligible for
the CI-owned focused pilot. Use the tracked-only full gate on the exact clean
commit:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: full locked validation PASS, compact ignored receipt under
`local/delivery_preflight/<exact-head>.json`, and no source-worktree mutation.

- [ ] **Step 8: Perform routine repository delivery under standing autonomy**

Verify exact inventory and clean status, non-force push
`task30/a14p-forward-stream-execution-adapter`, create one Draft PR, read back
the exact head and wait for exact-head CI. Apply `OWNER_ATTENTION_GATE`; merge
with the standard method only if it returns `AUTONOMOUS` and every machine
precondition passes. Preserve the branch, read back exact main and require
post-merge main CI.

- [ ] **Step 9: Stop at the external-material boundary**

Do not read `HELIUS_API_KEY`, open WSS, create an A4 external run or alter
TASK-30 acceptance. Return one exact owner action: the already frozen
`T30-A14P_FORWARD_STREAM_RUNTIME_V1; pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; max_wss_connections=1; max_subscriptions=1; max_open_seconds=1200; max_notifications=500; max_stream_bytes=1000000; estimated_credit_cap=21; retention=A4; retry=false; reconnect=false; fallback=false`
phrase. A later external execution must use Sol Max and the merged exact-main
bytes; any target, quota, transport, retention or authority drift invalidates
the gate.
