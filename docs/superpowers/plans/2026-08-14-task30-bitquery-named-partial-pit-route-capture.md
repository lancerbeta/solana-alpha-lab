# TASK-30 Bitquery Named Partial PIT Route Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one bounded Bitquery PumpSwap history query and retain a trustworthy 96-slot `OBSERVATION | TYPED_GAP` panel for the TASK-30 owner decision.

**Architecture:** A closed YAML contract owns route identity, caps and non-claims. A small pure Python module builds the exact GraphQL payload, validates a retained response and projects all 96 slots; a thin CLI owns preflight, one HTTP POST and content-addressed raw retention. After the observed result, a v4 provider registry successor preserves all v3 route semantics and records exactly one Bitquery observation.

**Tech Stack:** CPython 3.13.14, Python standard library HTTP/TLS/JSON/hashlib, PyYAML 6.0.3, jsonschema 4.26.0, unittest, Delivery Harness V1.

## Global Constraints

- Exact pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.
- Exact base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`; quote mint: `So11111111111111111111111111111111111111112`.
- PumpSwap program: `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`.
- Endpoint: `https://streaming.bitquery.io/graphql`; dataset: `archive`.
- Window: `[2026-08-12T00:00:00Z, 2026-08-13T00:00:00Z)`; 96 closed 15-minute slots.
- At most one credentialed request, 2,000,000 response bytes, 100 Bitquery points, zero retry, zero fallback and zero cash.
- Token source is local `BITQUERY_ACCESS_TOKEN`; secret value never enters Git, command arguments, URL, logs or receipts.
- Raw bytes remain under ignored `local/task30_bitquery_pit_capture/`; tracked evidence contains their SHA-256 and the full normalized slot projection.
- Historical OHLCV cannot establish fillability for the named `10, 25, 50, 100 USD` notionals.

---

### Task 1: Bind the Harness contract and deterministic capture policy

**Files:**
- Create: `docs/tasks/TASK-30-bitquery-named-partial-pit-route-capture.md`
- Create: `docs/contracts/task30_bitquery_named_partial_pit_route_capture_contract_v1.md`
- Create: `configs/task30_bitquery_named_partial_pit_route_capture_v1.yaml`
- Create: `catalog/schemas/task30_bitquery_named_partial_pit_route_capture.schema.json`
- Create: `tests/fixtures/task30/bitquery_named_partial_pit_route_capture_v1.json`
- Create: `tests/test_task30_bitquery_named_partial_pit_route_capture.py`

**Interfaces:**
- Consumes: A9 acceptance, A19 reopen rule, retained TASK-27 pool identity and provider registry v3.
- Produces: a Harness-valid TASK-30 context plus literal config constants consumed by the runtime module.

- [ ] **Step 1: Generate and verify Harness context**

Run:

```powershell
uv run --locked --managed-python python -B scripts/delivery_harness.py context --task-id TASK-30 --contract docs/tasks/TASK-30-bitquery-named-partial-pit-route-capture.md --route DIRECT_CODEX_DELIVERY --format json
```

Expected: `context_status=READY`, branch `task30/bitquery-pit-capture`, base/upstream OID `828a29af68807809fecb58d1a3b5b8b2dfcd9946`, and no path outside the declared write set.

- [ ] **Step 2: Write the failing closed-contract tests**

Add tests that load YAML and JSON Schema and require exact route identity, window, 96 slots, one-call cap, byte cap, zero retry/fallback/cash, named notionals and false fillability/alpha/execution claims. The production change each test catches is a widened external boundary or silent claim promotion.

```python
def test_policy_binds_one_bitquery_request_and_closed_identity(self):
    jsonschema.validate(self.config, self.schema)
    self.assertEqual(self.config["runtime_limits"]["max_provider_requests"], 1)
    self.assertFalse(self.config["execution_controls"]["retry"])
    self.assertEqual(self.config["pilot_window"]["expected_slots"], 96)
```

- [ ] **Step 3: Run RED**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task30_bitquery_named_partial_pit_route_capture -v`

Expected: FAIL because the config/schema/fixture and production module do not exist.

- [ ] **Step 4: Add the minimal contract, config, schema and fixture**

The fixture contains two literal aggregate rows at `00:00` and `00:30`, with hand-derived expected counts `observed=2`, `typed_gaps=94`, first slot `00:00` observed and second slot `00:15` gap.

- [ ] **Step 5: Re-run the contract-only tests**

Expected: config/schema tests pass; runtime behavior tests remain RED because the module does not exist.

- [ ] **Step 6: Commit the binding**

```powershell
git add docs/tasks/TASK-30-bitquery-named-partial-pit-route-capture.md docs/superpowers/plans/2026-08-14-task30-bitquery-named-partial-pit-route-capture.md docs/contracts/task30_bitquery_named_partial_pit_route_capture_contract_v1.md configs/task30_bitquery_named_partial_pit_route_capture_v1.yaml catalog/schemas/task30_bitquery_named_partial_pit_route_capture.schema.json tests/fixtures/task30/bitquery_named_partial_pit_route_capture_v1.json tests/test_task30_bitquery_named_partial_pit_route_capture.py
git commit -m "test(task30): bind Bitquery PIT capture contract"
```

### Task 2: Implement the pure query and 96-slot projection

**Files:**
- Create: `src/solana_alpha_lab/task30_bitquery_named_partial_pit_route_capture.py`
- Modify: `tests/test_task30_bitquery_named_partial_pit_route_capture.py`

**Interfaces:**
- Consumes: `load_policy(path) -> Mapping[str, object]`.
- Produces: `build_graphql_payload(policy) -> dict[str, object]`, `project_slots(policy, response, *, raw_sha256, response_bytes, observed_at) -> dict[str, object]`, and `classify_graphql_response(response) -> str`.

- [ ] **Step 1: Add failing query-builder behavior**

The literal assertions require `Solana(dataset: archive)`, `DEXTradeByTokens`, a 15-minute interval and variables for exact pool/base/quote/program/since/till. Mutation caught: dropping any identity or time filter.

```python
payload = build_graphql_payload(self.config)
self.assertEqual(payload["variables"]["pool"], EXPECTED_POOL)
self.assertIn("Time(interval: {count: 15, in: minutes})", payload["query"])
self.assertNotIn("ory_", json.dumps(payload))
```

- [ ] **Step 2: Run RED and confirm import/function failure**

Run the single test and require failure due to the missing module/function, not fixture syntax.

- [ ] **Step 3: Implement the minimal payload builder**

Use a static GraphQL document with variables. Do not accept endpoint, dataset, pool, token or program overrides from CLI.

- [ ] **Step 4: Run GREEN for the builder**

Expected: exact query-builder test passes.

- [ ] **Step 5: Add failing slot-projection and error tests**

Tests require two fixture rows to become two observed slots plus 94 `MISSING_UNKNOWN` gaps, reject duplicate/off-grid/out-of-window timestamps, reject pool/mint/quote/program drift, reject GraphQL `errors`, and never impute OHLCV for a gap.

```python
projection = project_slots(
    self.config,
    self.fixture["response"],
    raw_sha256="a" * 64,
    response_bytes=1234,
    observed_at="2026-08-14T12:00:00Z",
)
self.assertEqual(projection["counts"], {"observed": 2, "typed_gaps": 94, "slots": 96})
self.assertEqual(projection["slots"][1]["state"], "MISSING_UNKNOWN")
self.assertNotIn("open", projection["slots"][1])
```

- [ ] **Step 6: Run RED, then implement minimal validation/projection**

Generate slot boundaries from the frozen window. Validate returned identity on every observed row and preserve numeric values exactly as JSON numbers/strings without forward filling.

- [ ] **Step 7: Run GREEN and refactor only after all behavior passes**

Run the whole TASK-30 Bitquery test file. Keep the pure module independent of filesystem/network state.

- [ ] **Step 8: Commit the pure capability**

```powershell
git add src/solana_alpha_lab/task30_bitquery_named_partial_pit_route_capture.py tests/test_task30_bitquery_named_partial_pit_route_capture.py
git commit -m "feat(task30): project typed Bitquery PIT slots"
```

### Task 3: Add the one-shot transport and execute the bounded capture

**Files:**
- Create: `scripts/run_task30_bitquery_named_partial_pit_route_capture.py`
- Modify: `src/solana_alpha_lab/task30_bitquery_named_partial_pit_route_capture.py`
- Modify: `tests/test_task30_bitquery_named_partial_pit_route_capture.py`
- Create: `docs/evidence/task30/a20_bitquery_named_partial_pit_route_capture_acceptance_v1.json`
- Create: `docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json`
- Create: `docs/reports/task30/bitquery_named_partial_pit_route_capture_readout_v1.md`
- Write ignored raw bytes: `local/task30_bitquery_pit_capture/run=<run_id>/raw_response.json`

**Interfaces:**
- Consumes: local `BITQUERY_ACCESS_TOKEN` and the pure payload/projection functions.
- Produces: `credential_free_preflight(host, port, timeout)`, `execute_once(policy, token, raw_root)`, raw manifest and sanitized tracked receipt.

- [ ] **Step 1: Add failing transport-boundary tests**

Use a local fake response object only at the external HTTP boundary. Assert actual request URL/method/content type, `Authorization: Bearer <redacted test token>` in memory only, exact one call, response byte cap, no redirects and no token in returned receipt, exception text or files. Mutation caught: retry loop, URL drift, logging secret or accepting oversized bytes.

- [ ] **Step 2: Run RED**

Expected: missing transport/CLI functions.

- [ ] **Step 3: Implement one-shot transport and raw retention**

Use `urllib.request` with a no-redirect handler, 30-second timeout and one `read(2_000_001)`. Hash exact bytes before JSON parsing; create the run directory with exclusive semantics; write raw bytes and a sanitized manifest. Never serialize headers containing the token.

- [ ] **Step 4: Run GREEN and the secret scanner on changed files**

Run targeted tests, then `uv run --locked --managed-python python -B scripts/secret_scan.py --self-test --scan-repository`.

- [ ] **Step 5: Run credential-free DNS/TCP/TLS preflight**

Expected: `streaming.bitquery.io` resolves, TCP 443 connects and TLS hostname verification passes. A failure stops before reading the token.

- [ ] **Step 6: Execute exactly one provider request**

Load the user-level token into the child process environment without echoing it, run the CLI once, then clear the child environment value. No retry is allowed for any terminal response.

- [ ] **Step 7: Validate runtime artifacts**

Require raw path ignored by Git, raw SHA-256/byte count match, runtime receipt has exactly 96 slots, no secret substring, request count `1`, cash `0`, retry/fallback `0`, and one terminal outcome.

- [ ] **Step 8: Commit the observed result**

```powershell
git add scripts/run_task30_bitquery_named_partial_pit_route_capture.py src/solana_alpha_lab/task30_bitquery_named_partial_pit_route_capture.py tests/test_task30_bitquery_named_partial_pit_route_capture.py docs/evidence/task30/a20_bitquery_named_partial_pit_route_capture_acceptance_v1.json docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json docs/reports/task30/bitquery_named_partial_pit_route_capture_readout_v1.md
git commit -m "feat(task30): retain bounded Bitquery PIT capture"
```

### Task 4: Register the observed route, reconcile Catalog and deliver

**Files:**
- Create: `configs/provider_route_capability_registry_v4.yaml`
- Create: `catalog/schemas/provider_route_capability_registry_v4.schema.json`
- Create: `src/solana_alpha_lab/provider_route_capability_registry_v4.py`
- Create: `tests/test_provider_route_capability_registry_v4.py`
- Create: `docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json`
- Modify: `AGENTS.md`
- Modify: `delivery-harness/context-map.yaml`
- Modify: `delivery-harness/policies/solana-alpha-lab.md`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/assets/core.yaml`
- Modify generated: `catalog/generated/asset_edges.json`
- Modify generated: `docs/PROJECT_MAP.md`
- Modify: `registries/decisions_negative_results.yaml`
- Modify: `docs/tasks/TASK-30-bitquery-named-partial-pit-route-capture.md`

**Interfaces:**
- Consumes: registry v3 exact SHA/semantic route hashes and A20P runtime receipt.
- Produces: `validate_provider_route_capability_registry_v4()` and `resolve_provider_route_v4()` with one observed Bitquery route and immutable v3 carry-forward.

- [ ] **Step 1: Add failing v4 registry tests**

Require the four v3 route semantic hashes, exact v3 file SHA, exact observed Bitquery terminal result and receipt path. Mutations caught: legacy route drift, invented success, authority promotion or missing raw-retention binding.

- [ ] **Step 2: Run RED, then implement the minimal v4 successor**

The Bitquery row records the actual HTTP/GraphQL terminal class; `last_success` is populated only for a valid HTTP 200 projection. Execution policy remains retry/fallback/automatic selection/authority false.

- [ ] **Step 3: Run registry and TASK-30 tests GREEN**

Run both new test files plus A9, A19 and A18 registry tests.

- [ ] **Step 4: Reconcile Catalog and generated navigation**

Register contract/config/schema/module/script/tests/acceptance/runtime/report/registry assets with stable IDs, relations, hashes and named consumer. Run the repository generator; hand-edit no generated file.

- [ ] **Step 5: Run risk-routed single-agent reviews**

Record `SINGLE_AGENT_REVIEW_FALLBACK`; run code review, goal/DoD review and architecture review against the exact diff. Factory Fit must reject any claim that historical OHLCV establishes fill, execution or TASK-30 DONE.

- [ ] **Step 6: Run targeted validation and secret scan**

Run new tests, direct consumers, Catalog validation, generated consistency and repository secret scan. Do not run the local full delivery gate before PR; exact-head CI owns it under the Harness.

- [ ] **Step 7: Commit final reconciliation**

```powershell
git add AGENTS.md delivery-harness/context-map.yaml delivery-harness/policies/solana-alpha-lab.md configs/provider_route_capability_registry_v4.yaml catalog/schemas/provider_route_capability_registry_v4.schema.json src/solana_alpha_lab/provider_route_capability_registry_v4.py tests/test_provider_route_capability_registry_v4.py docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json catalog/catalog_manifest.yaml catalog/assets/core.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md registries/decisions_negative_results.yaml docs/tasks/TASK-30-bitquery-named-partial-pit-route-capture.md
git commit -m "chore(task30): register Bitquery route evidence"
```

- [ ] **Step 8: Push, open PR and read exact-head CI**

Push only `task30/bitquery-pit-capture`, open one PR, verify exact write set and wait for workflow `Repository validation` job `validate` on the unchanged 40-hex head. Stop after CI for the exact owner merge phrase; do not merge, delete the branch or change settings without that phrase.

## Self-review receipt

- Spec coverage: A9 provider/identity/window/lanes/notionals/caps/retention/waiver/monitoring/recovery/non-claims are each owned by Task 1 or Task 3; A19 reopen and provider-registry obligations are owned by Task 4.
- Placeholder scan: no `TBD`, `TODO`, generic error-handling instruction or undefined production interface remains.
- Type consistency: the plan uses `build_graphql_payload`, `project_slots`, `credential_free_preflight`, `execute_once`, `validate_provider_route_capability_registry_v4` and `resolve_provider_route_v4` consistently.
