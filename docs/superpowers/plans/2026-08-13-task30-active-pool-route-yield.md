# TASK-30 A17 Active-Pool Route-Yield Discriminator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one offline-validated, owner-gated same-window discriminator that tests standard WSS yield on a currently active Orca POPCAT/SOL pool and conditionally reconciles an acknowledged empty WSS window with one signature page.

**Architecture:** A closed policy module owns target selection, request binding and terminal classification. A separate runtime adapter owns exact one-shot sequencing and A4 retention through injected transports so every branch is deterministic offline. One runner supplies real transports only after an exact future owner phrase.

**Tech Stack:** Python 3.13, PyYAML, jsonschema, existing `websockets` and repository transport/Catalog infrastructure; no new dependency.

## Global Constraints

- `SPEC_ROUTE=DESIGN_SPEC`; the approved design is `docs/superpowers/specs/2026-08-13-task30-active-pool-route-yield-design.md`.
- One keyless DexScreener GET; one conditional Helius WSS; one RPC only after acknowledged zero-notification WSS.
- Maximum WSS open time 180 seconds, one notification, 300,000 stream bytes and estimated Helius credit cap 8.
- No retry, reconnect, fallback, scheduler, transaction follow-up, cash, wallet, TASK-30 trial or acceptance.
- Raw external bytes remain A4 outside Git; tracked fixtures are synthetic.
- Any non-yield runtime terminal returns to task-level replan and cannot create an automatic A17 repair suffix.

---

### Task 1: Closed policy and terminal classifier

**Files:**
- Create: `configs/task30_active_pool_route_yield_v1.yaml`
- Create: `catalog/schemas/task30_active_pool_route_yield.schema.json`
- Create: `tests/fixtures/task30/active_pool_route_yield_v1.json`
- Create: `src/solana_alpha_lab/task30_active_pool_route_yield.py`
- Create: `tests/test_task30_active_pool_route_yield.py`

**Interfaces:**
- Produces: `evaluate_active_pool_route_yield_policy(config)`,
  `select_active_pool(document)`, `bind_pool_logs_subscribe(pool, key)`,
  `bind_pool_activity_request(pool, key)`, and
  `classify_route_window(config, selection, wss_capture, rpc_capture)`.
- Consumes: `BoundProbeRequest`, `WssCapture`, `HttpCapture` and the provider
  registry resolver.

- [ ] Write failing tests for the closed schema/policy, deterministic active
  pool selection, no-active stop, first-notification success, activity-without-
  WSS, no-activity bracket, transport/coverage unknown, type confusion,
  target mismatch and non-claims.
- [ ] Run `uv run --locked --managed-python python -B -m unittest tests.test_task30_active_pool_route_yield` and require a missing-module failure.
- [ ] Implement the minimum pure policy, request binders and classifier.
- [ ] Re-run the targeted test and require PASS.

### Task 2: One-shot runtime and retained receipt

**Files:**
- Create: `src/solana_alpha_lab/task30_active_pool_route_yield_runtime.py`
- Create: `scripts/run_task30_active_pool_route_yield.py`
- Modify: `tests/test_task30_active_pool_route_yield.py`

**Interfaces:**
- Produces: `execute_active_pool_route_yield(...) -> dict[str, object]` with
  injected discovery, WSS and RPC exchanges; `node_keyless_get_exchange`,
  `bounded_first_notification_wss_exchange` for the future runner.
- Consumes: Task 1 classifier and exact future owner phrase.

- [ ] Add failing tests proving no Helius credential read when discovery has no
  active target, no RPC after a notification, exactly one conditional RPC after
  acknowledged zero WSS, immutable A4 manifests, safe receipts, exact authority
  matching and transport failure fail-closed behavior.
- [ ] Run the targeted test and require failure because runtime is absent.
- [ ] Implement one-shot sequencing, in-memory credential handling, bounded
  adapters and immutable A4 retention without executing network in tests.
- [ ] Re-run the targeted test and require PASS.

### Task 3: Contract, Factory Fit, Catalog and delivery evidence

**Files:**
- Create: `docs/contracts/task30_active_pool_route_yield_contract_v1.md`
- Create: `docs/evidence/task30/a17_active_pool_route_yield_acceptance_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Generate: `catalog/generated/asset_edges.json`
- Generate: `docs/PROJECT_MAP.md`
- Test: `tests/test_task30_active_pool_route_yield.py`

**Interfaces:**
- Produces: Catalog-discoverable A17 assets, hash-bound offline acceptance and
  one exact future external owner phrase.
- Consumes: exact tested bytes from Tasks 1–2.

- [ ] Add contract and FULL_REVIEW evidence with terminal replan rule,
  `project_sources_disposition=NO_CHANGE` and `STATE_CHANGE=NONE`.
- [ ] Register only durable contract/config/schema/fixture/modules/runner/test/
  evidence assets; classify design/plan as process docs outside Catalog.
- [ ] Update manifest counts/version/schema list and regenerate navigation.
- [ ] Bind exact SHA-256 values after bytes stabilize.
- [ ] Run targeted A17, provider-registry, A15 and A16 tests plus Catalog and
  generated-navigation checks.
- [ ] Review the exact diff for secrets, raw bodies, absolute paths, widened
  authority, manual generated edits and duplicate PRD/SSD.
- [ ] Commit the unchanged candidate fingerprint, run the repository-selected
  delivery gate, push, create PR and use exact-head CI as the full-suite owner.

## Self-review

- Spec coverage: every Task Outcome Brief field, terminal state, authority cap,
  retention rule, same-window branch and replan trigger maps to Tasks 1–3.
- Placeholder scan: PASS; there are no deferred implementation placeholders.
- Type/interface consistency: the runtime consumes the pure module interfaces
  named in Task 1 and returns one terminal receipt consumed by Task 3.
