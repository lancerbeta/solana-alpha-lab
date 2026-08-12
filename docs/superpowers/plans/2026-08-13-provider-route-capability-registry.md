# Provider Route Capability Registry V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, secret-free registry that lets future tasks reuse observed DexScreener and Helius transport knowledge without granting or performing provider calls.

**Architecture:** A closed YAML document is the single route-memory owner. A JSON Schema and a small pure Python validator enforce exact shape, timestamp/hash integrity, secret boundaries and fail-closed semantics; Catalog only indexes the durable assets. Immutable runtime receipts retain history while the registry exposes separate last-success and last-observation summaries.

**Tech Stack:** Python standard library, PyYAML and jsonschema already locked by the repository, YAML, JSON Schema draft 2020-12, unittest, existing Catalog generator/validator.

## Global Constraints

- No provider/API/RPC/WSS calls, credential reads, retries, fallbacks, scheduler, wallet, transaction, cash spend, R2/R3 access or TASK-30 acceptance action.
- Do not add a dependency, service, database, generic provider router or automatic transport selection.
- Tracked files must contain no secret values, credential-bearing URLs, raw provider bodies or absolute local user paths.
- `last_success` and `last_observation` remain distinct; a failure does not erase success and success does not hide a later failure.
- A local transport failure is never promoted to provider failure, data invalidity, market inactivity or zero volume.
- Use TDD for every production behavior and preserve the existing dirty A16P runtime work without broad rewrites.

---

## File Structure

- Create `configs/provider_route_capability_registry_v1.yaml`: two current route records and update/non-claim policy.
- Create `catalog/schemas/provider_route_capability_registry.schema.json`: closed machine-readable structure.
- Create `src/solana_alpha_lab/provider_route_capability_registry.py`: pure semantic validation and stable-ID lookup.
- Create `tests/test_provider_route_capability_registry.py`: schema, semantic, security and Catalog binding tests.
- Create `docs/evidence/task30/a16r1_provider_route_capability_registry_acceptance_v1.json`: sanitized acceptance and POPCAT V2 transport receipt.
- Modify `AGENTS.md`: one mandatory pre-external-read lookup pointer, with no duplicated route facts.
- Modify `docs/evidence/task30/a16p_pool_activity_discriminator_runtime_receipt_v2.json`: replace pending hashes with exact final hashes.
- Modify `catalog/assets/core.yaml`, `catalog/assets/lifecycle.yaml`, `catalog/catalog_manifest.yaml`: register new assets, V2 evidence and exact integrity values.
- Regenerate `catalog/generated/asset_edges.json` and `docs/PROJECT_MAP.md` only through `scripts/generate_navigation.py`.

### Task 1: Closed registry semantics

**Files:**
- Create: `tests/test_provider_route_capability_registry.py`
- Create: `configs/provider_route_capability_registry_v1.yaml`
- Create: `catalog/schemas/provider_route_capability_registry.schema.json`
- Create: `src/solana_alpha_lab/provider_route_capability_registry.py`

**Interfaces:**
- Consumes: a Python `Mapping[str, Any]` loaded from the YAML registry.
- Produces: `validate_provider_route_capability_registry(registry: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]` and `resolve_provider_route(registry: Mapping[str, Any], route_id: str) -> Mapping[str, Any]`.

- [ ] **Step 1: Write the failing positive and lookup tests**

```python
def test_registry_validates_and_resolves_two_observed_routes(self) -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    routes = validate_provider_route_capability_registry(registry)
    self.assertEqual([route["route_id"] for route in routes], [
        "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001",
        "HELIUS-SOLANA-GET-SIGNATURES-001",
    ])
    self.assertEqual(
        resolve_provider_route(registry, "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001")["last_observation"]["terminal_class"],
        "HTTP_SUCCESS",
    )

def test_schema_closes_registry_and_routes(self) -> None:
    jsonschema.Draft202012Validator.check_schema(schema())
    jsonschema.validate(instance=registry(), schema=schema())
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_provider_route_capability_registry -v
```

Expected: FAIL because the module and registry do not exist.

- [ ] **Step 3: Add the closed schema and two exact route records**

The YAML root is exactly:

```yaml
schema: smial.provider-route-capability-registry
schema_version: '1.0'
registry_id: PROVIDER-ROUTE-CAPABILITY-REGISTRY-001
as_of: '2026-08-13'
update_policy: {observed_receipt_required: true, preserve_receipt_history: true, separate_last_success: true, registry_gap_is_unavailability: false, automatic_routing: false, authority_granted: false}
routes: []
non_claims: {provider_reliability: false, data_completeness: false, market_activity: false, task30_trial: false, alpha: false, numeric_netreturn: false}
```

Each route is closed over `route_id`, `provider`, `endpoint_family`, `network`, `access_class`, `operation`, `protocol`, `runtime`, `preflight`, `last_success`, `last_observation`, `known_failures`, `execution_policy`, `evidence`, and `non_claims`. DexScreener records HTTP 200 at `2026-08-12T21:17:48.620Z`, 42,510 response bytes and SHA-256 `34ee46d235f6525c0c09cadf372a8577be61b9534afe35946438be76a24619f4`. Helius records its earlier HTTP 200 success from the A16P V2 receipt and the later `ECONNRESET` observation at `2026-08-12T21:19:32.164Z` with no HTTP status or response hash.

- [ ] **Step 4: Add minimal pure semantic validation**

```python
class ProviderRouteRegistryError(ValueError):
    pass

def validate_provider_route_capability_registry(
    registry: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    root = _mapping(registry, "REGISTRY_ROOT_REQUIRED")
    _require(frozenset(root) == ROOT_FIELDS, "REGISTRY_ROOT_FIELDS_DRIFT")
    raw_routes = root["routes"]
    _require(type(raw_routes) is list and bool(raw_routes), "ROUTES_REQUIRED")
    routes = tuple(_mapping(item, "ROUTE_RECORD_REQUIRED") for item in raw_routes)
    route_ids = [route.get("route_id") for route in routes]
    _require(len(route_ids) == len(set(route_ids)), "DUPLICATE_ROUTE_ID")
    for route in routes:
        _validate_route(route)
    return routes

def resolve_provider_route(
    registry: Mapping[str, Any], route_id: str
) -> Mapping[str, Any]:
    routes = validate_provider_route_capability_registry(registry)
    for route in routes:
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
```

Implement the validation explicitly rather than executing network preflights or importing provider clients.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Task 1 unittest command. Expected: the positive tests pass.

### Task 2: Adversarial safety and truth boundaries

**Files:**
- Modify: `tests/test_provider_route_capability_registry.py`
- Modify: `src/solana_alpha_lab/provider_route_capability_registry.py`

**Interfaces:**
- Consumes: the Task 1 validation functions.
- Produces: stable fail-closed error codes for unsafe or semantically widened entries.

- [ ] **Step 1: Add failing adversarial cases**

```python
def test_registry_rejects_secret_and_authority_widening(self) -> None:
    cases = {
        "SECRET_VALUE_FORBIDDEN": lambda value: value["routes"][1]["evidence"].update({"note": "api" + "-key=fixture"}),
        "AUTHORITY_PROMOTION": lambda value: value["routes"][0]["execution_policy"].update({"authority_granted": True}),
        "RETRY_PROMOTION": lambda value: value["routes"][0]["execution_policy"].update({"retry": True}),
        "FAILURE_LAYER_CONFLATION": lambda value: value["routes"][1]["last_observation"].update({"layer": "MARKET"}),
    }
    for expected, mutate in cases.items():
        candidate = copy.deepcopy(registry())
        mutate(candidate)
        with self.assertRaisesRegex(ProviderRouteRegistryError, expected):
            validate_provider_route_capability_registry(candidate)

def test_unknown_route_is_registry_gap_not_unavailability(self) -> None:
    with self.assertRaisesRegex(ProviderRouteRegistryError, "REGISTRY_GAP"):
        resolve_provider_route(registry(), "UNKNOWN-ROUTE")
```

Also test duplicate IDs, non-UTC timestamps, malformed hashes, absolute Windows paths, credential-bearing URLs, response hash without bytes, and an observation earlier than `last_success`.

- [ ] **Step 2: Run tests and verify RED**

Expected: each new case fails because the corresponding semantic check is absent.

- [ ] **Step 3: Implement the minimal fail-closed checks**

Use recursive key/value inspection, `urllib.parse` for credential-bearing URLs, `datetime.fromisoformat` for `Z` timestamps, and type-strict equality. Do not add provider-specific client behavior.

- [ ] **Step 4: Run focused tests and verify GREEN**

Expected: every adversarial mutation returns its exact error code and the valid registry remains accepted.

- [ ] **Step 5: Commit Tasks 1–2**

```powershell
git add -- configs/provider_route_capability_registry_v1.yaml catalog/schemas/provider_route_capability_registry.schema.json src/solana_alpha_lab/provider_route_capability_registry.py tests/test_provider_route_capability_registry.py
git commit -m "feat: add provider route capability registry"
```

### Task 3: Durable encounter path and acceptance receipt

**Files:**
- Modify: `AGENTS.md`
- Create: `docs/evidence/task30/a16r1_provider_route_capability_registry_acceptance_v1.json`
- Modify: `tests/test_provider_route_capability_registry.py`

**Interfaces:**
- Consumes: the validated registry and exact hashes from Tasks 1–2.
- Produces: one startup/reuse pointer and one sanitized acceptance receipt with decision `REGISTRY_VALIDATED_NO_RUNTIME_AUTHORITY`.

- [ ] **Step 1: Add failing encounter and receipt-binding tests**

```python
def test_agents_requires_registry_lookup_before_external_route_work(self) -> None:
    agents = AGENTS.read_text(encoding="utf-8")
    self.assertIn("PROVIDER_ROUTE_CAPABILITY_REGISTRY_V1", agents)
    self.assertIn("configs/provider_route_capability_registry_v1.yaml", agents)

def test_acceptance_hash_binds_registry_schema_module_and_test(self) -> None:
    receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    for binding in receipt["artifact_bindings"].values():
        self.assertEqual(binding["sha256"], sha256(ROOT / binding["path"]))
    self.assertEqual(receipt["decision"], "REGISTRY_VALIDATED_NO_RUNTIME_AUTHORITY")
```

- [ ] **Step 2: Run tests and verify RED**

Expected: FAIL because `AGENTS.md` has no registry pointer and the receipt is absent.

- [ ] **Step 3: Add the minimal AGENTS pointer**

Require future external route Entry/Reuse gates to resolve the stable route ID in the registry before building or invoking transport. State that absence is `REGISTRY_GAP`, staleness requires a new bounded gate, and the registry grants no call/retry/fallback authority. Do not copy route-specific facts into `AGENTS.md`.

- [ ] **Step 4: Create the sanitized acceptance receipt**

Bind exact artifact hashes, the POPCAT selection metrics, Helius `ECONNRESET`, call counts, WSS=0, cash=0, raw A4 logical identity, non-claims, rollback and Factory Fit `PASS_WITH_LIMITATIONS`. Do not include raw bodies, signatures, keys or absolute paths.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: encounter and binding tests pass.

### Task 4: Catalog transaction and A16P reconciliation

**Files:**
- Modify: `docs/evidence/task30/a16p_pool_activity_discriminator_runtime_receipt_v2.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify generated: `catalog/generated/asset_edges.json`
- Modify generated: `docs/PROJECT_MAP.md`
- Modify: `tests/test_provider_route_capability_registry.py`
- Existing A16P files already in worktree: runtime module, script, test and V1/V2 receipts.

**Interfaces:**
- Consumes: exact final file hashes and existing Catalog generator.
- Produces: discoverable registry assets plus finalized A16P runtime evidence with no pending bindings.

- [ ] **Step 1: Add failing Catalog assertions**

Require stable IDs for registry config, schema, module, test and acceptance evidence; require a separate A16P V2 evidence asset; require every Catalog hash to equal its file bytes.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: FAIL because the new assets and finalized V2 evidence entry are absent.

- [ ] **Step 3: Finalize A16P hashes and add Catalog records**

Calculate SHA-256 only after all source/test edits settle. Replace all `PENDING_*_HASH` values in the V2 receipt. Add five registry assets and the A16P V2 receipt asset with relations to their validators/consumers. Increment the Catalog checkpoint once for the whole transaction; add the new schema path to the manifest.

- [ ] **Step 4: Regenerate navigation and close generated-view hashes**

```powershell
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
```

If generated-view integrity changes, update only their Catalog hashes, rerun the generator, and then run it without `--write` to prove zero drift.

- [ ] **Step 5: Validate the transaction**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_provider_route_capability_registry tests.test_task30_pool_activity_discriminator_runtime -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py
git diff --check
```

Expected: focused tests PASS, Catalog PASS, generated check PASS and no whitespace errors.

### Task 5: Candidate verification and delivery

**Files:** all exact files from Tasks 1–4 plus the previously dirty A16P runtime set and the committed design/plan documents.

**Interfaces:**
- Consumes: an unchanged candidate fingerprint after Catalog closure.
- Produces: reviewed task-branch commit, PR/CI evidence and exact merge/read-back if the repository machine gate returns `AUTONOMOUS`.

- [ ] **Step 1: Run full locked validation once**

```powershell
uv run --locked --managed-python python -B scripts/validate_ci.py
```

Expected: full repository gate PASS. Do not rerun it after staging/commit if candidate bytes and validation policy remain unchanged.

- [ ] **Step 2: Review exact diff and secret boundary**

Confirm no raw bodies, absolute local paths, credential-bearing URLs, manual generated edits or unrelated files. Confirm provider calls 1 DexScreener + 1 Helius and WSS 0 in the acceptance receipt.

- [ ] **Step 3: Commit the implementation transaction**

Stage only the plan, registry, receipt, A16P runtime, Catalog and generated files named above. Commit with:

```powershell
git commit -m "feat: retain verified provider route capabilities"
```

- [ ] **Step 4: Push, open/read back PR and verify exact-head CI**

Use non-force push. Create one PR against `main`, read back exact head SHA, changed-file inventory, mergeability and all required checks. No settings or branch deletion.

- [ ] **Step 5: Apply Owner Attention Gate and finish**

If exact-head tests, full gate, Catalog, generated drift, secret scan, review and mergeability all pass, use the repository's `AUTONOMOUS_AFTER_MACHINE_GATE` route for ordinary merge and read back exact `main` plus post-merge CI. Otherwise stop with the exact failed invariant. Merge does not mark TASK-30 DONE or grant another provider read.
