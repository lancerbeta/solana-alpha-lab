# TASK-30 A15 Standard WSS Pool Trade Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an offline, fail-closed readiness package for one future Helius Standard WSS `logsSubscribe` capture filtered by the frozen PumpSwap pool.

**Architecture:** Add one narrow pure route module.  It owns the exact pool-targeted request body and terminal truth classification, while reusing `BoundProbeRequest`, the pinned PumpSwap IDL and TASK-09's strict `parse_logs_notification`; it does not reuse the program-wide TASK-09 binder or live runner.  A future external adapter remains outside this atom.

**Tech Stack:** Python 3.13, `unittest`, PyYAML, JSON Schema Draft 2020-12, existing PumpSwap decoder, existing Catalog generator.

## Global Constraints

- Exact pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.
- Exact base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`.
- Exact quote mint: `So11111111111111111111111111111111111111112`.
- Provider candidate: `HELIUS_STANDARD_WSS`; method: `logsSubscribe`.
- Request params: one `mentions` address equal to the pool and `commitment=confirmed`.
- One foreground connection/subscription; 600 seconds, 128 notifications, 1,000,000 stream bytes and 21 estimated credits maximum.
- `retry=false`, `reconnect=false`, `fallback=false`, `scheduler=false`, `rpc_followups=0`.
- No provider/API/RPC/WSS call, credential read, raw external write, dependency change, R2/R3 access, wallet/signer/transaction action, cash spend, trial or TASK-30 acceptance in this plan.
- Missing, no notification, truncation and transport loss remain `UNKNOWN`; never zero, flat, empty interval or complete coverage.
- `getTransaction` is excluded until an observed exact-pool log proves a named field gap.
- Previous receipts and negative evidence are append-only and are not rewritten.

---

### Task 1: Freeze the closed policy and schema

**Files:**
- Create: `docs/contracts/task30_standard_pool_logs_route_contract_v1.md`
- Create: `configs/task30_standard_pool_logs_route_v1.yaml`
- Create: `catalog/schemas/task30_standard_pool_logs_route.schema.json`
- Create: `tests/fixtures/task30/standard_pool_logs_route_v1.json`
- Create: `tests/test_task30_standard_pool_logs_route.py`

**Interfaces:**
- Consumes: frozen identity from `docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json` and limits from the accepted A15 design.
- Produces: `policy() -> dict[str, object]` test helper and the closed on-disk policy used by later tasks.

- [ ] **Step 1: Write the failing structural test**

Create `tests/test_task30_standard_pool_logs_route.py` with path constants and a first test that loads YAML and validates it against the closed schema:

```python
CONFIG = ROOT / "configs/task30_standard_pool_logs_route_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/task30_standard_pool_logs_route.schema.json"
FIXTURE = ROOT / "tests/fixtures/task30/standard_pool_logs_route_v1.json"

def policy() -> dict[str, object]:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

class Task30StandardPoolLogsRouteTests(unittest.TestCase):
    def test_policy_is_closed_and_exact(self) -> None:
        document = policy()
        Draft202012Validator(
            json.loads(SCHEMA.read_text(encoding="utf-8"))
        ).validate(document)
        self.assertEqual(document["target"]["pool_address"], POOL)
        self.assertEqual(document["wire"]["method"], "logsSubscribe")
        self.assertEqual(document["wire"]["mentions"], [POOL])
        self.assertEqual(document["wire"]["commitment"], "confirmed")
        self.assertEqual(document["execution_controls"]["rpc_followups"], 0)
```

- [ ] **Step 2: Verify RED**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_standard_pool_logs_route
```

Expected: FAIL because the policy/schema/fixture do not exist.

- [ ] **Step 3: Add the minimum closed artifacts**

The YAML must contain exactly these top-level fields:

```yaml
schema: smial.task30.standard-pool-logs-route.policy
schema_version: '1.0'
task_id: TASK-30
atom_id: T30-A15_STANDARD_WSS_POOL_TRADE_ROUTE_V1
contract_id: TASK30-STANDARD-POOL-LOGS-ROUTE-V1
consumer: RC001-H07-H01-LIQUIDITY-RETENTION
target:
  network: solana
  pool_address: URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
  base_mint: DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK
  quote_mint: So11111111111111111111111111111111111111112
  dex_id: pumpswap
wire:
  provider: HELIUS_STANDARD_WSS
  method: logsSubscribe
  mentions: [URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S]
  commitment: confirmed
runtime_limits:
  effective_open_seconds: 600
  max_notifications: 128
  max_stream_bytes: 1000000
  max_frame_bytes: 100000
  estimated_credit_cap: 21
  credit_bytes_per_unit: 100000
  credits_per_unit: 2
  connection_credits: 1
execution_controls:
  monitoring_owner: LOCAL_WORK_CODEX_FOREGROUND
  retention_class: A4
  wss_connections: 1
  subscriptions: 1
  rpc_followups: 0
  retry: false
  reconnect: false
  fallback: false
  scheduler: false
authority:
  provider_api_rpc_wss_calls: 0
  credential_read: false
  raw_data_write: false
  cash_spend_usd: 0
  task30_trial_or_acceptance: false
owner_authority:
  future_pilot_authorized: false
  future_pilot_phrase: 'T30-A15P_STANDARD_POOL_LOGS_RUNTIME_V1; pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; provider=HELIUS_STANDARD_WSS; monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; max_wss_connections=1; max_subscriptions=1; max_open_seconds=600; max_notifications=128; max_stream_bytes=1000000; estimated_credit_cap=21; retention=A4; rpc_followups=0; retry=false; reconnect=false; fallback=false'
decision: OFFLINE_ROUTE_READY_FOR_OWNER_GATE
project_sources_disposition: NO_CHANGE
```

The JSON Schema must set `additionalProperties: false` at every object level, use `const` for every frozen enum/string/number/boolean, and require every field.  The fixture contains expected terminal-state names and mutation cases for `mentions`, method, caps, type confusion and all four forbidden execution controls.

- [ ] **Step 4: Verify GREEN for structure**

Run the same unittest command.  Expected: the structural test passes; later imports may still fail only after they are added in Task 2.

- [ ] **Step 5: Commit the closed contract**

```text
git add docs/contracts/task30_standard_pool_logs_route_contract_v1.md configs/task30_standard_pool_logs_route_v1.yaml catalog/schemas/task30_standard_pool_logs_route.schema.json tests/fixtures/task30/standard_pool_logs_route_v1.json tests/test_task30_standard_pool_logs_route.py
git commit -m "test: freeze TASK-30 standard pool logs route"
```

### Task 2: Implement the pure request binder and classifier with TDD

**Files:**
- Create: `src/solana_alpha_lab/task30_standard_pool_logs_route.py`
- Modify: `tests/test_task30_standard_pool_logs_route.py`

**Interfaces:**
- Consumes: `BoundProbeRequest`, `PumpSwapIdlPlan`, `load_pinned_pumpswap_plan`, and `parse_logs_notification`.
- Produces:
  - `evaluate_standard_pool_logs_route(config: Mapping[str, Any]) -> dict[str, object]`
  - `bind_pool_logs_subscribe(api_key: str) -> BoundProbeRequest`
  - `classify_standard_pool_logs_capture(config: Mapping[str, Any], capture: StandardPoolLogsCapture, plan: PumpSwapIdlPlan) -> dict[str, object]`
  - `render_standard_pool_logs_route(config: Mapping[str, Any]) -> str`
  - `StandardPoolLogsCapture` and `StandardPoolLogsRouteError`.

- [ ] **Step 1: Write failing request-binding and policy tests**

Add imports from the missing module, then assert:

```python
def test_request_is_pool_targeted_and_secret_safe(self) -> None:
    request = bind_pool_logs_subscribe("offline-synthetic-key")
    body = json.loads(request.body)
    self.assertEqual(body["method"], "logsSubscribe")
    self.assertEqual(body["params"], [{"mentions": [POOL]}, {"commitment": "confirmed"}])
    self.assertNotIn("offline-synthetic-key", repr(request))
    self.assertNotIn("offline-synthetic-key", json.dumps(request.safe_receipt()))

def test_policy_rejects_widening_and_type_confusion(self) -> None:
    for pointer, value in (
        (("wire", "mentions"), [POOL, BASE_MINT]),
        (("runtime_limits", "effective_open_seconds"), 601),
        (("runtime_limits", "max_notifications"), True),
        (("execution_controls", "rpc_followups"), 1),
        (("execution_controls", "retry"), True),
    ):
        candidate = copy.deepcopy(policy())
        candidate[pointer[0]][pointer[1]] = value
        with self.assertRaises(StandardPoolLogsRouteError):
            evaluate_standard_pool_logs_route(candidate)
```

- [ ] **Step 2: Verify RED**

Run the targeted unittest.  Expected: import failure for `task30_standard_pool_logs_route`.

- [ ] **Step 3: Implement the strict policy validator and binder**

Use type-strict equality (`type(value) is type(expected) and value == expected`), closed key sets and canonical JSON.  Build a `BoundProbeRequest` with Helius WSS endpoint, in-memory `api-key` query, and this body:

```python
{
    "id": "task30-a15-pool-logs-subscribe",
    "jsonrpc": "2.0",
    "method": "logsSubscribe",
    "params": [
        {"mentions": [POOL_ADDRESS]},
        {"commitment": "confirmed"},
    ],
}
```

Return only a sanitized safe receipt from public APIs; never expose the URL or headers.

- [ ] **Step 4: Verify GREEN for policy and binder**

Run the targeted unittest.  Expected: request and policy tests PASS.

- [ ] **Step 5: Write failing classifier tests**

Add deterministic helpers copied only into the test module to Borsh-encode the pinned TASK-09 `BuyEvent` and `SellEvent` layouts.  For the event's `pool` pubkey bytes use `bytes(Pubkey.from_string(POOL))` from the already-pinned `solders` dependency; all other fields use deterministic synthetic values.  Build `logsNotification` frames whose program stack is the pinned PumpSwap program and whose decoded event `pool` field is therefore the exact frozen pool.

Assert these exact outcomes:

```python
self.assertEqual(classify(happy_buy)["terminal_state"], "OBSERVED_POOL_TRADE")
self.assertEqual(classify(happy_sell)["terminal_state"], "OBSERVED_POOL_TRADE")
self.assertEqual(classify(no_notifications)["terminal_state"], "NO_OBSERVATION_UNKNOWN")
self.assertEqual(classify(remote_closed)["terminal_state"], "TRANSPORT_LOST_UNKNOWN")
self.assertEqual(classify(failed_tx)["terminal_state"], "OBSERVED_NON_TRADE_OR_UNSUPPORTED")
self.assertEqual(classify(truncated)["terminal_state"], "TRUNCATED_OR_SCHEMA_DRIFT_UNKNOWN")
```

Also require hard failure on wrong request id, wrong subscription id, duplicate signature, pool mismatch and unknown notification keys.  Every result must include `zero_volume=false`, `empty_interval=false`, `interval_complete=false`, `pit_admissible=false`, `task30_trial=false` and `numeric_netreturn=false`.

- [ ] **Step 6: Verify RED for classifier**

Run the targeted unittest.  Expected: failures because classification is not implemented.

- [ ] **Step 7: Implement minimal classification**

Classification order:

1. non-`BOUND_REACHED` transport -> `TRANSPORT_LOST_UNKNOWN`;
2. typed acknowledgement error -> `SUBSCRIPTION_REJECTED`;
3. strict acknowledgement success and zero frames -> `NO_OBSERVATION_UNKNOWN`;
4. parse each frame using TASK-09 `parse_logs_notification`;
5. reject duplicate signatures and any decoded event whose `fields["pool"]` is not the frozen pool;
6. any truncation/schema drift -> `TRUNCATED_OR_SCHEMA_DRIFT_UNKNOWN`;
7. at least one exact-pool decoded `BuyEvent`/`SellEvent` -> `OBSERVED_POOL_TRADE`;
8. otherwise -> `OBSERVED_NON_TRADE_OR_UNSUPPORTED`.

Return only counts, terminal state, sanitized signature hashes and non-claims.  Do not return raw frames or credentials.

- [ ] **Step 8: Verify GREEN and refactor**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_standard_pool_logs_route tests.test_task09_pumpswap_touch_probe tests.test_task09_pumpswap_touch_decoder
```

Expected: all targeted tests PASS.  Remove duplication only inside the new module; do not refactor TASK-09 or A14P.

- [ ] **Step 9: Commit the pure route**

```text
git add src/solana_alpha_lab/task30_standard_pool_logs_route.py tests/test_task30_standard_pool_logs_route.py
git commit -m "feat: add pool-targeted standard WSS route"
```

### Task 3: Add the owner readout and deterministic rendering

**Files:**
- Create: `scripts/show_task30_standard_pool_logs_route.py`
- Create: `docs/reports/task30/standard_pool_logs_route_readout_v1.md`
- Modify: `tests/test_task30_standard_pool_logs_route.py`

**Interfaces:**
- Consumes: `render_standard_pool_logs_route()` and the versioned YAML.
- Produces: stable Russian text explaining that the route is ready offline but not authorized or observed.

- [ ] **Step 1: Write the failing renderer test**

```python
def test_owner_readout_is_exact_and_nontechnical(self) -> None:
    rendered = render_standard_pool_logs_route(policy())
    self.assertIn("Стандартный бесплатный WSS-маршрут подготовлен офлайн", rendered)
    self.assertIn("реальный запуск пока не разрешён", rendered)
    self.assertIn("отсутствие уведомлений не означает нулевой объём", rendered)
    self.assertNotIn("api-key", rendered.casefold())
    self.assertEqual(READOUT.read_text(encoding="utf-8"), rendered)
```

- [ ] **Step 2: Verify RED**

Run the targeted unittest.  Expected: missing readout/script or text mismatch.

- [ ] **Step 3: Implement the renderer and CLI**

The CLI reads only the tracked YAML, validates it, prints the renderer output and performs no environment-variable or network access.  Generate the checked-in report by running the CLI through the repository's existing UTF-8 Python environment.

- [ ] **Step 4: Verify GREEN**

Run the targeted unittest and run the CLI once.  Expected: byte-for-byte equality and no side effects.

- [ ] **Step 5: Commit the readout**

```text
git add scripts/show_task30_standard_pool_logs_route.py docs/reports/task30/standard_pool_logs_route_readout_v1.md src/solana_alpha_lab/task30_standard_pool_logs_route.py tests/test_task30_standard_pool_logs_route.py
git commit -m "docs: add standard pool logs owner readout"
```

### Task 4: Bind acceptance, Factory Fit and Catalog delivery

**Files:**
- Create: `docs/tasks/TASK-30-standard-pool-logs-route.md`
- Create: `docs/evidence/task30/a15_standard_pool_logs_route_acceptance_v1.json`
- Create: `docs/evidence/task30/a15_standard_pool_logs_route_factory_fit_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify generated: `catalog/catalog_manifest.yaml`
- Modify generated: `catalog/generated/asset_edges.json`
- Modify generated: `docs/PROJECT_MAP.md`
- Modify: `tests/test_task30_standard_pool_logs_route.py`

**Interfaces:**
- Consumes: exact artifact hashes from Tasks 1-3 and targeted test results.
- Produces: Catalog-discoverable A15 assets and a sanitized `PASS_WITH_LIMITATIONS` FULL_REVIEW receipt.

- [ ] **Step 1: Write failing binding tests**

Require the acceptance receipt to bind SHA-256 for contract, config, schema, module, fixture, test, script and report.  Require Catalog IDs:

```text
CONTRACT-T30-STANDARD-POOL-LOGS-ROUTE-001
CONFIG-T30-STANDARD-POOL-LOGS-ROUTE-001
SCHEMA-T30-STANDARD-POOL-LOGS-ROUTE-001
MODULE-T30-STANDARD-POOL-LOGS-ROUTE-001
FIXTURE-T30-STANDARD-POOL-LOGS-ROUTE-001
TEST-T30-STANDARD-POOL-LOGS-ROUTE-001
SCRIPT-T30-STANDARD-POOL-LOGS-ROUTE-001
REPORT-T30-STANDARD-POOL-LOGS-ROUTE-001
EVIDENCE-T30-A15-STANDARD-POOL-LOGS-ROUTE-001
EVIDENCE-T30-A15-STANDARD-POOL-LOGS-ROUTE-FACTORY-FIT-001
```

Assert `project_sources_disposition.kind=NO_CHANGE`, provider calls and credential reads are zero, `state_change=NONE`, and the next boundary is one separately authorized foreground external pilot.

- [ ] **Step 2: Verify RED**

Run the targeted unittest.  Expected: missing evidence and Catalog IDs.

- [ ] **Step 3: Create acceptance and FULL Factory Fit evidence**

Acceptance decision: `OFFLINE_STANDARD_POOL_LOGS_ROUTE_READY_FOR_OWNER_GATE`.

Factory Fit fields:

```json
{
  "scope": "FULL_REVIEW",
  "verdict": "PASS_WITH_LIMITATIONS",
  "mission": "PASS",
  "research_truth": "PASS",
  "flexibility": "PASS",
  "compatibility_history": "PASS",
  "efficiency": "PASS",
  "owner_operability": "PASS",
  "monitoring_recovery": "PASS_WITH_LIMITATIONS",
  "reuse_first": "PASS",
  "execution_to_cashflow": "NOT_APPLICABLE_YET",
  "red_team": "PASS"
}
```

The limitation is explicit: no real pool observation, interval coverage or PIT-admissible panel exists yet.

- [ ] **Step 4: Register Catalog assets and generate consumers**

Append only the ten product/evidence records above to `catalog/assets/core.yaml`; do not register the task, design or plan process notes.  Use existing classification anchors and relations.  Run the repository Catalog generator rather than editing generated files by hand.

- [ ] **Step 5: Run targeted validation**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_standard_pool_logs_route tests.test_task09_pumpswap_touch_probe tests.test_task09_pumpswap_touch_decoder
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: all PASS.

- [ ] **Step 6: Commit the accepted candidate**

Stage only the exact A15 inventory, inspect `git diff --cached --name-status`, then commit:

```text
git commit -m "test: accept TASK-30 standard pool logs route"
```

- [ ] **Step 7: Run the proportional delivery gate**

First classify eligibility for `--ci-owned-delivery`.  If the schema change makes the candidate ineligible, run exactly one tracked-only delivery preflight on the committed clean candidate:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Do not run an additional local full suite for unchanged bytes.

- [ ] **Step 8: Deliver and read back**

Under repository standing autonomy: non-force push the task branch, create one Draft PR, read back exact head, wait for exact-head CI, review mergeability and apply `OWNER_ATTENTION_GATE`.  Stop before merge if the exact gate is not `AUTONOMOUS`; otherwise ordinary merge is allowed only after every machine precondition passes.  Read back exact main commit/tree and require post-merge main CI.

## Completion checkpoint

Return:

- exact branch, feature head/tree and PR;
- changed-file inventory;
- targeted and delivery/CI evidence;
- Catalog version/count/delta;
- decision `OFFLINE_STANDARD_POOL_LOGS_ROUTE_READY_FOR_OWNER_GATE`;
- limits/non-claims and `STATE_CHANGE=NONE`;
- exact future owner WSS phrase, but do not execute it;
- `NEXT_MODEL_EFFORT=LUNA_MAX` for the bounded external adapter only if the offline route passes; escalate to `SOL_XHIGH` if observed logs reveal schema/PIT ambiguity.
