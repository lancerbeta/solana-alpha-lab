# TASK-30 Forward Raw Trade Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic offline contract that decides whether a future raw-transaction data route is safely specified for the frozen H07/H01 consumer, without opening a provider connection or constructing a collector.

**Architecture:** Keep the only reusable logic in one pure Python module: validate the zero-authority route policy, accept only synthetic observation envelopes, and project coverage into explicit `COMPLETE`, `UNKNOWN`, `INVALID`, or `STOPPED` states. The provider adapter, raw retention, DEX decoder, reconciliation source and 15-minute research panel remain future owner-gated boundaries.

**Tech Stack:** Python 3.13, `unittest`, YAML, JSON Schema, existing Catalog generator and `uv` locked environment.

## Global Constraints

- Bind exactly `TASK-30`, frozen group `RC001-H07-H01-LIQUIDITY-RETENTION`, and `OBSERVATION_WINDOW_15M`.
- External API/RPC/WSS calls, credential use, raw writes, scheduler/background process, dependencies, R2/R3, wallet/signer/transaction actions, cash, trial opening and Project Sources changes are all zero.
- Do not select Helius, another provider, an endpoint, a transport, a parser or a recovery source.
- `UNKNOWN` is never empty, zero, flat, no-trade, complete or projectable.
- Reuse the project’s pure-policy/module/fixture/readout pattern; add no framework or generic streaming platform.
- Preserve the A12 design’s `REUSE_RESEARCH_GATE` conclusion: inspect official/current references and maintained candidates before a future build or external-owner packet.

---

### Task 1: Freeze the offline forward-route contract and adversarial fixture

**Files:**
- Create: `docs/tasks/TASK-30-forward-raw-trade-route.md`
- Create: `docs/contracts/task30_forward_raw_trade_route_contract_v1.md`
- Create: `configs/task30_forward_raw_trade_route_contract_v1.yaml`
- Create: `catalog/schemas/task30_forward_raw_trade_route.schema.json`
- Create: `tests/fixtures/task30/forward_raw_trade_route_v1.json`
- Create: `tests/test_task30_forward_raw_trade_route.py`

**Interfaces:**
- Consumes: `configs/task28_rc001_registry_freeze_v1.yaml` and the committed A12 design.
- Produces: a schema-valid `ForwardRawTradeRoutePolicy` fixture and tests that call `validate_forward_raw_trade_route_policy()` and `evaluate_forward_coverage()` from Task 2.

- [x] **Step 1: Write the failing contract tests**

```python
def test_policy_binds_frozen_consumer_and_every_external_authority_is_zero(self) -> None:
    validate_forward_raw_trade_route_policy(policy(), frozen_group())
    self.assertEqual(policy()["authority"]["provider_api_rpc_wss_calls"], 0)

def test_unknown_interval_cannot_be_projected_as_empty_or_complete(self) -> None:
    result = evaluate_forward_coverage(policy(), frozen_group(), unknown_gap_events())
    self.assertEqual(result["projection_state"], "UNKNOWN")
    self.assertFalse(result["interval_projectable"])

def test_duplicate_signature_reconnect_without_coverage_and_wrong_identity_fail_closed(self) -> None:
    for events, code in cases:
        with self.subTest(code=code):
            with self.assertRaisesRegex(ForwardRawTradeRouteError, code):
                evaluate_forward_coverage(policy(), frozen_group(), events)
```

- [x] **Step 2: Run the new test and confirm the missing module fails**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_raw_trade_route`

Expected: FAIL because `solana_alpha_lab.task30_forward_raw_trade_route` does not exist.

- [x] **Step 3: Write the minimal policy, schema and synthetic fixture**

```yaml
authority:
  provider_api_rpc_wss_calls: 0
  credential_use: 0
  raw_data_writes: 0
  scheduler_or_background_processes: 0
coverage_states: [COMPLETE, GAP_SUSPECTED, UNKNOWN, RECONCILED, INVALID, STOPPED]
future_external_boundary: OWNER_PACKET_REQUIRED
```

The fixture must contain one valid synthetic observation sequence and separate adversarial cases for duplicate signature, wrong identity, loss of transport, unreconciled reconnect, missing raw hash, zero/empty coercion, retry and fallback.

- [x] **Step 4: Run schema and fixture tests after each policy change**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_raw_trade_route`

Expected: tests still fail only because the pure evaluator is absent; YAML and JSON schema loading must not be the failure cause.

- [x] **Step 5: Commit the contract surface**

```bash
git add docs/tasks/TASK-30-forward-raw-trade-route.md docs/contracts/task30_forward_raw_trade_route_contract_v1.md configs/task30_forward_raw_trade_route_contract_v1.yaml catalog/schemas/task30_forward_raw_trade_route.schema.json tests/fixtures/task30/forward_raw_trade_route_v1.json tests/test_task30_forward_raw_trade_route.py
git commit -m "test: define forward raw trade route contract"
```

### Task 2: Implement the pure coverage evaluator and owner readout

**Files:**
- Create: `src/solana_alpha_lab/task30_forward_raw_trade_route.py`
- Create: `scripts/show_task30_forward_raw_trade_route.py`
- Create: `docs/reports/task30/forward_raw_trade_route_readout_v1.md`
- Modify: `tests/test_task30_forward_raw_trade_route.py`

**Interfaces:**
- Consumes: the Task 1 policy and synthetic fixtures.
- Produces: `validate_forward_raw_trade_route_policy(policy, frozen_group)`, `evaluate_forward_coverage(policy, frozen_group, events)`, and `render_forward_raw_trade_route_readout(result)`.

- [x] **Step 1: Implement exact policy validation**

```python
def validate_forward_raw_trade_route_policy(policy: Mapping[str, Any], frozen_group: Mapping[str, Any]) -> None:
    _exact(policy, "task_id", "TASK-30", "TASK_ID_INVALID")
    _exact(policy, "frozen_group_id", "RC001-H07-H01-LIQUIDITY-RETENTION", "FROZEN_GROUP_INVALID")
    for value in _mapping(policy["authority"], "AUTHORITY_INVALID").values():
        _require(value in (0, False), "AUTHORITY_PROMOTION")
```

- [x] **Step 2: Implement fail-closed synthetic coverage evaluation**

```python
def evaluate_forward_coverage(policy, frozen_group, events):
    validate_forward_raw_trade_route_policy(policy, frozen_group)
    _reject_duplicate_signature_per_epoch(events)
    _require_bound_identity_and_raw_hash(events)
    if _has_transport_loss_without_reconciliation(events):
        return {"projection_state": "UNKNOWN", "interval_projectable": False, "execution_disposition": "STOP_RUN"}
    return {"projection_state": "COMPLETE", "interval_projectable": False, "execution_disposition": "OWNER_PACKET_REQUIRED"}
```

The `COMPLETE` result means only that the synthetic coverage protocol is internally complete. It must not assert data completeness, a valid price, no-trade, PIT eligibility, H07/H01 evidence, a trial, execution, settlement, PnL or NetReturn.

- [x] **Step 3: Add the deterministic Russian readout**

The readout must show one of `OFFLINE_CONTRACT_VALIDATED`, `UNKNOWN` or `STOPPED`, list the reason external authority is still required, and state that no provider has been selected. It must contain no URL, credential-shaped text, raw payload, price, volume or numeric performance claim.

- [x] **Step 4: Run targeted behavior and readout tests**

Run: `uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_raw_trade_route`

Expected: PASS, including every adversarial case and byte-for-byte CLI/report comparison.

- [x] **Step 5: Commit the pure evaluator**

```bash
git add src/solana_alpha_lab/task30_forward_raw_trade_route.py scripts/show_task30_forward_raw_trade_route.py docs/reports/task30/forward_raw_trade_route_readout_v1.md tests/test_task30_forward_raw_trade_route.py
git commit -m "feat: evaluate forward raw trade coverage offline"
```

### Task 3: Bind acceptance, Catalog and delivery evidence

**Files:**
- Create: `docs/evidence/task30/a12_forward_raw_trade_route_acceptance_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`
- Modify: `docs/OPERATOR_NAVIGATION.md`
- Modify: `tests/test_task30_forward_raw_trade_route.py`

**Interfaces:**
- Consumes: all Task 1–2 artifact hashes and the A12 design/plan paths.
- Produces: a hash-bound `PASS_WITH_LIMITATIONS` receipt, complete Catalog registrations and generated navigation.

- [x] **Step 1: Extend the test with immutable acceptance checks**

```python
def test_acceptance_binds_every_artifact_and_cannot_promote_authority(self) -> None:
    receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert_acceptance(receipt)
    candidate = copy.deepcopy(receipt)
    candidate["authority"]["provider_api_rpc_wss_calls"] = 1
    with self.assertRaises(AssertionError):
        assert_acceptance(candidate)
```

- [x] **Step 2: Create the acceptance receipt and register all durable assets**

Bind task, contract, configuration, schema, fixture, module, script, report, test, design and plan by exact SHA-256. The receipt must declare `state_change=NONE`, `project_sources_disposition=NO_CHANGE`, full Factory Fit, the `REUSE_DECISION=WRAP_CANDIDATE` finding, and every authority/side-effect counter at zero.

- [x] **Step 3: Regenerate only the derived Catalog views**

Run: `uv run --locked --managed-python python -B scripts/generate_navigation.py --write`

Expected: only `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md` and `docs/OPERATOR_NAVIGATION.md` change as required by the Catalog.

- [x] **Step 4: Run targeted integrity validation**

Run:

```bash
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_raw_trade_route
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: all PASS and no unregistered durable output or generated-view drift.

- [x] **Step 5: Commit the bound offline package**

```bash
git add docs/evidence/task30/a12_forward_raw_trade_route_acceptance_v1.json catalog/assets/core.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md docs/OPERATOR_NAVIGATION.md tests/test_task30_forward_raw_trade_route.py
git commit -m "docs: bind forward raw trade route acceptance"
```

### Task 4: Deliver one exact candidate without a duplicate local full gate

**Files:**
- Modify: only Task 1–3 files if a targeted validation or Catalog repair proves necessary.

**Interfaces:**
- Consumes: the exact committed candidate from Tasks 1–3.
- Produces: one tracked-only full preflight receipt, a non-force task-branch push, one PR, exact CI read-back and an owner-facing no-external-boundary result.

- [ ] **Step 1: Run the repository-owned fast preflight if eligibility is exact**

Run: `uv run --locked --managed-python python -B scripts/validate_ci.py --ci-owned-delivery`

Expected: an eligible focused PASS receipt. If the candidate is ineligible, run the repository-required tracked-only delivery preflight instead; never use a focused skip to conceal a missing raw input.

- [ ] **Step 2: Inspect the exact committed write set**

Run: `git diff --name-status origin/main...HEAD` and `git diff --check origin/main...HEAD`.

Expected: only the offline contract, synthetic harness, acceptance and generated Catalog paths planned above; no secret, raw capture, provider transport, dependency, Sources release or wallet path.

- [ ] **Step 3: Push and create one PR**

Run: `git push -u origin task30/a12-forward-raw-trade-route-design` followed by the repository’s ordinary PR creation command.

Expected: one PR whose exact head matches the locally validated commit.

- [ ] **Step 4: Read back CI once per exact head**

Expected: targeted evidence plus remote CI for the exact PR head. Do not rerun the same full local validation after a successful unchanged candidate.

- [ ] **Step 5: Stop before any external action or canonical acceptance**

Return `STATE_CHANGE=NONE`, the Factory Fit result, the next external owner boundary, and the exact PR/head/CI receipt. Do not claim a provider selection, continuous panel, trial or TASK-30 completion.

## Plan self-review

- **Spec coverage:** Tasks 1–3 cover the policy, synthetic adversarial cases, pure evaluator, owner readout, reuse finding, acceptance, Catalog and full Factory Fit; Task 4 covers proportional delivery only.
- **Scope:** The plan ends before any provider transport, raw-data write, credential use, DEX parser, recovery execution, scheduler or research trial.
- **Consistency:** Every task preserves `UNKNOWN` and the zero-authority contract; the only `COMPLETE` state is synthetic protocol coverage, never research evidence.
- **No placeholders:** File paths, interfaces, commands, failure modes and expected outcomes are explicit.
