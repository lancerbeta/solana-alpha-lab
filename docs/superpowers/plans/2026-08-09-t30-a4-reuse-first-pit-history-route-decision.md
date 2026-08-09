# T30-A4 Reuse-first PIT history route decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing OHLCV route evidence into one fail-closed decision that closes only the unsafe T30-A0 reuse path and names the precise conditions for any future provider work.

**Architecture:** A task-owned YAML policy freezes concise, dated facts from three existing routes: the retained GeckoTerminal response, the observed Solana Tracker pair response, and Birdeye's documented candidate surface. A thin pure-Python evaluator returns one stable no-pilot decision; it never fetches a URL or accesses a credential. Existing Catalog validation and generation register the result without adding a collector, service, or dependency.

**Tech Stack:** Python 3.13, PyYAML, JSON Schema Draft 2020-12, Python `unittest`, locked `uv`, existing Catalog generator.

## Global Constraints

- T30-A4 is offline: provider/API/RPC/WSS calls, credential access, raw-data writes, R2/R3 access, dependency changes, wallet/signer/transaction actions, cash spend, trial opening, and holdout consumption are forbidden.
- The existing TASK-27, T30-A0, T30-A1, and T30-A3 receipts remain byte-for-byte unchanged. Documentation facts may explain their scope but never rewrite their decisions.
- `MISSING_UNKNOWN`, observed zero-volume carry-forward candles, a continuous panel, and PIT admissibility are separate states.
- The decision closes only reuse of the frozen T30-A0 response for its requested target window. It does not claim that GeckoTerminal, Solana Tracker, Birdeye, or all future historical routes are unusable.
- Official-document facts are tracked only as URL, concise fact, and `as_of` date. No downloaded documentation page, API response, key, or raw market value enters Git.
- Generated views are created only by `scripts/generate_navigation.py --write`; do not edit `catalog/generated/asset_edges.json` or `docs/PROJECT_MAP.md` manually.
- Project Sources disposition remains `NO_CHANGE`.

---

## File structure

| Path | Responsibility |
|---|---|
| `docs/contracts/task30_reuse_first_pit_history_route_decision_contract_v1.md` | Human-readable consumer, evidence, bounded decision, authority, and non-claim contract. |
| `configs/task30_reuse_first_pit_history_route_decision_v1.yaml` | Machine-readable three-route evidence policy and sole permitted decision. |
| `catalog/schemas/task30_reuse_first_pit_history_route_decision.schema.json` | Closed JSON Schema for the policy. |
| `tests/fixtures/task30/reuse_first_pit_history_route_decision_v1.json` | Hand-authored expected decision and route states. |
| `src/solana_alpha_lab/task30_reuse_first_pit_history_route.py` | Pure fail-closed evaluator; reads its mapping only. |
| `tests/test_task30_reuse_first_pit_history_route_decision.py` | Behavioral, adversarial, receipt, and Catalog tests. |
| `docs/evidence/task30/a4_reuse_first_pit_history_route_decision_acceptance_v1.json` | Hash-bound acceptance plus `FULL_REVIEW` Factory Fit and zero-side-effect receipt. |
| `catalog/assets/core.yaml` | Stable records for the seven T30-A4 outputs. |
| `catalog/catalog_manifest.yaml` | Schema entry, mandatory IDs, and checkpoint update. |
| `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md` | Regenerated Catalog consumers. |

## Decision contract

The evaluator must produce exactly:

```python
{
    "decision": "T30_A0_REUSE_CLOSED_NO_PROVIDER_PILOT",
    "route_states": {
        "GECKO_T30_A0": "DOCUMENTED_START_LABEL_CONFLICTS_WITH_RETAINED_BOUNDARY",
        "SOLANA_TRACKER_PAIR": "OBSERVED_INSUFFICIENT_33_OF_96",
        "BIRDEYE_V3_PAIR": "CANDIDATE_NOT_READY"
    },
    "next_boundary": "NEW_NAMED_PROVIDER_CANDIDATE_REQUIRES_ENTRY_GATE",
    "project_sources_disposition": "NO_CHANGE"
}
```

`GECKO_T30_A0` is closed because the retained response has a newest candle
timestamp equal to its `before_timestamp`, while the current official contract
describes candle timestamps as starts of intervals and describes
`before_timestamp` as returning data before that value. This is a boundary
conflict, not proof that the provider is generally defective. The policy also
records that `include_empty_intervals=true` forward-fills OHLC from the prior
close and sets volume to zero; that documented transformation may not be
mistaken for a verified trade or price observation.

`SOLANA_TRACKER_PAIR` is not reused because its retained named-pool sample has
33 of the required 96 bars. `BIRDEYE_V3_PAIR` remains a candidate only: its
documentation describes pair OHLCV and empty-interval padding, but this
evidence set has no exact pair binding, REST-15m proof, key-presence
attestation, or owner authority.

## Task 1: Contract-first evaluator and adversarial tests

**Files:**
- Create: `docs/contracts/task30_reuse_first_pit_history_route_decision_contract_v1.md`
- Create: `configs/task30_reuse_first_pit_history_route_decision_v1.yaml`
- Create: `catalog/schemas/task30_reuse_first_pit_history_route_decision.schema.json`
- Create: `tests/fixtures/task30/reuse_first_pit_history_route_decision_v1.json`
- Create: `src/solana_alpha_lab/task30_reuse_first_pit_history_route.py`
- Create: `tests/test_task30_reuse_first_pit_history_route_decision.py`

**Interfaces:**
- Consumes: `evaluate_reuse_first_history_route(config: Mapping[str, Any])` receives a policy matching the new schema.
- Produces: a dictionary with exactly `decision`, `route_states`, `next_boundary`, and `project_sources_disposition` as shown above.

- [ ] **Step 1: Write the failing behavioral tests**

Name the production change each test catches before writing it: removing the
route conflict, promoting documentation to a panel, accepting an unbound
Birdeye candidate, or widening authority. Start with these assertions:

```python
def test_evaluates_only_the_closed_no_pilot_result(self) -> None:
    policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    self.assertEqual(evaluate_reuse_first_history_route(policy), fixture["expected_result"])

def test_rejects_promoting_a_documented_empty_interval_to_pit_history(self) -> None:
    policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    policy["non_claims"]["continuous_panel_claim"] = True
    with self.assertRaisesRegex(ReuseFirstHistoryRouteError, "PROMOTION_CLAIM_FORBIDDEN"):
        evaluate_reuse_first_history_route(policy)

def test_rejects_a_birdeye_pair_or_key_without_independent_evidence(self) -> None:
    policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    policy["routes"]["BIRDEYE_V3_PAIR"]["pair_identity"] = "PROVEN"
    with self.assertRaisesRegex(ReuseFirstHistoryRouteError, "BIRDEYE_CANDIDATE_PROMOTION_FORBIDDEN"):
        evaluate_reuse_first_history_route(policy)
```

Add separate literal-expectation cases for: removal of the Gecko boundary
conflict, changing `33` or `96`, setting any authority value non-zero/true,
adding a credential-like key, selecting `EXACT_OWNER_PROOF_CALL_REQUIRED`,
and changing `project_sources_disposition`.

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```text
uv run --locked --managed-python python -m unittest tests.test_task30_reuse_first_pit_history_route_decision -v
```

Expected: import failure for `solana_alpha_lab.task30_reuse_first_pit_history_route`; no production evaluator exists yet.

- [ ] **Step 3: Add the closed policy, schema, fixture, contract, and minimal evaluator**

Use these exact policy identities and facts:

```yaml
schema: smial.task30.reuse-first-pit-history-route.policy
schema_version: '1.0'
task_id: TASK-30
atom_id: T30-A4_REUSE_FIRST_PIT_HISTORY_ROUTE_DECISION_V1
contract_id: TASK30-REUSE-FIRST-PIT-HISTORY-ROUTE-DECISION-V1
consumer: FUTURE_NAMED_PROVIDER_ENTRY_GATE
decision: T30_A0_REUSE_CLOSED_NO_PROVIDER_PILOT
next_boundary: NEW_NAMED_PROVIDER_CANDIDATE_REQUIRES_ENTRY_GATE
project_sources_disposition: NO_CHANGE
```

The `GECKO_T30_A0` record binds raw SHA-256
`cce29d4e175bc81a474c699e3bb465daf8cb864f3cb195a9812bd0d3c0ca4163`,
requested interval `[1786100400, 1786186800)`, first observed timestamp
`1786101300`, newest observed timestamp `1786186800`, and the official
CoinGecko Pool OHLCV URL. It names the start-label, strict-before, and
empty-interval facts as `DOCUMENTED`, while the retained boundary mismatch is
`OBSERVED_CONFLICT`.

The `SOLANA_TRACKER_PAIR` record binds `33` observed bars, `96` required bars,
the named token/pool OHLCV documentation URL, and state
`OBSERVED_INSUFFICIENT_33_OF_96`. The `BIRDEYE_V3_PAIR` record binds the V3
documentation URL, `padding=true` as documented, and pair identity, REST 15m
enum, credential presence, and owner authority as unproven/not granted.

Implement only:

```python
class ReuseFirstHistoryRouteError(ValueError):
    """Raised when a frozen route decision is widened or contradicted."""

def evaluate_reuse_first_history_route(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the frozen offline evidence and return the sole permitted result."""
```

The evaluator must reject unknown mapping keys recursively when they are
credential-like (`api_key`, `authorization`, `token`, `secret`, `password`),
enforce every zero/false authority field, enforce the three exact route states,
and return the literal decision dictionary. The JSON Schema sets
`additionalProperties: false` on the root and every nested object.

- [ ] **Step 4: Run the focused test to verify GREEN**

Run:

```text
uv run --locked --managed-python python -m unittest tests.test_task30_reuse_first_pit_history_route_decision -v
```

Expected: the valid policy produces the literal expected result; each
adversarial variant fails with its declared error code.

- [ ] **Step 5: Commit the evaluated boundary**

```text
git add docs/contracts/task30_reuse_first_pit_history_route_decision_contract_v1.md configs/task30_reuse_first_pit_history_route_decision_v1.yaml catalog/schemas/task30_reuse_first_pit_history_route_decision.schema.json tests/fixtures/task30/reuse_first_pit_history_route_decision_v1.json src/solana_alpha_lab/task30_reuse_first_pit_history_route.py tests/test_task30_reuse_first_pit_history_route_decision.py
git commit -m "feat: add T30 reuse-first history route decision"
```

## Task 2: Hash-bound evidence, Catalog, Factory Fit, and delivery

**Files:**
- Create: `docs/evidence/task30/a4_reuse_first_pit_history_route_decision_acceptance_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `tests/test_task30_reuse_first_pit_history_route_decision.py`
- Regenerate: `catalog/generated/asset_edges.json`
- Regenerate: `docs/PROJECT_MAP.md`

**Interfaces:**
- Consumes: SHA-256 hashes of every Task 1 tracked artifact and the literal evaluator result.
- Produces: Catalog records `CONTRACT-T30-REUSE-FIRST-HISTORY-ROUTE-001`, `CONFIG-T30-REUSE-FIRST-HISTORY-ROUTE-001`, `SCHEMA-T30-REUSE-FIRST-HISTORY-ROUTE-001`, `FIXTURE-T30-REUSE-FIRST-HISTORY-ROUTE-001`, `MODULE-T30-REUSE-FIRST-HISTORY-ROUTE-001`, `TEST-T30-REUSE-FIRST-HISTORY-ROUTE-001`, and `EVIDENCE-T30-A4-REUSE-FIRST-HISTORY-ROUTE-001`.

- [ ] **Step 1: Add failing acceptance and Catalog tests**

```python
def test_acceptance_binds_artifacts_and_reports_zero_external_effects(self) -> None:
    receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    for binding in receipt["artifact_bindings"].values():
        self.assertEqual(binding["sha256"], sha256(ROOT / binding["path"]))
    self.assertTrue(all(value == 0 for value in receipt["side_effect_counters"].values()))
    self.assertEqual(receipt["decision"]["value"], "T30_A0_REUSE_CLOSED_NO_PROVIDER_PILOT")
    self.assertEqual(receipt["factory_fit"]["review_scope"], "FULL_REVIEW")

def test_catalog_registers_each_t30_a4_output(self) -> None:
    catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))
    asset_ids = {record["asset_id"] for record in catalog["records"]}
    expected_asset_ids = {
        "CONTRACT-T30-REUSE-FIRST-HISTORY-ROUTE-001",
        "CONFIG-T30-REUSE-FIRST-HISTORY-ROUTE-001",
        "SCHEMA-T30-REUSE-FIRST-HISTORY-ROUTE-001",
        "FIXTURE-T30-REUSE-FIRST-HISTORY-ROUTE-001",
        "MODULE-T30-REUSE-FIRST-HISTORY-ROUTE-001",
        "TEST-T30-REUSE-FIRST-HISTORY-ROUTE-001",
        "EVIDENCE-T30-A4-REUSE-FIRST-HISTORY-ROUTE-001",
    }
    self.assertTrue(expected_asset_ids.issubset(asset_ids))
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```text
uv run --locked --managed-python python -m unittest tests.test_task30_reuse_first_pit_history_route_decision -v
```

Expected: failures report that the receipt and required Catalog asset IDs do
not yet exist.

- [ ] **Step 3: Add the single acceptance receipt and Catalog transaction**

The receipt binds Task 1 files by SHA-256, preserves the historical raw digest
only as an input reference, records all provider/credential/raw/wallet/cash
counters as zero, and sets `project_sources_disposition.kind = "NO_CHANGE"`.
Its `factory_fit` section uses `FULL_REVIEW`, records `ADOPT_EXISTING` for the
existing Catalog, schema, and pure-Python stack, rejects building a collector,
and records this Product Horizon result:

```json
{
  "now": "CLOSE_UNSAFE_T30_A0_REUSE_AND_REQUIRE_A_NEW_NAMED_DATA_ROUTE",
  "watch": "ONE_PROVIDER_PROOF_CALL_ONLY_AFTER_A_CREDIBLE_CANDIDATE_AND_EXACT_OWNER_AUTHORITY"
}
```

Append only the seven T30-A4 asset records to `catalog/assets/core.yaml`.
Add the new schema and mandatory IDs to `catalog/catalog_manifest.yaml`, then
run generation instead of hand-editing derived files.

- [ ] **Step 4: Regenerate and verify Catalog consumers**

Run:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -m unittest tests.test_task30_reuse_first_pit_history_route_decision tests.test_task30_ohlcv_boundary_semantics_decision tests.test_task30_birdeye_pair_ohlcv_pilot_readiness -v
```

Expected: generated views are current, Catalog validation passes, and all
existing T30 boundaries remain fail-closed alongside T30-A4.

- [ ] **Step 5: Commit the accepted offline package**

```text
git add docs/evidence/task30/a4_reuse_first_pit_history_route_decision_acceptance_v1.json catalog/assets/core.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md tests/test_task30_reuse_first_pit_history_route_decision.py
git commit -m "feat: complete T30 reuse-first route decision"
```

- [ ] **Step 6: Run proportional delivery validation and transport**

Run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: the exact committed tree passes the clean tracked-only gate. Then
perform a non-force push, create one Draft PR, read CI for the exact head,
evaluate `OWNER_ATTENTION_GATE`, merge only if the machine decision is
`AUTONOMOUS`, preserve the feature branch, and read back `main` push CI. Do not
claim canonical TASK-30 acceptance; this atom only closes a reuse path and
selects no provider action.

## Plan self-review

- **Spec coverage:** Task 1 implements the frozen three-route evidence model,
  fail-closed evaluator, authority boundary, and adversarial cases. Task 2
  adds hash-bound evidence, Catalog discoverability, `FULL_REVIEW`, generated
  consumers, and delivery.
- **Completeness scan:** Every changed path, decision value, function name,
  test command, authority stop, Catalog ID, and delivery command is explicit.
- **Type consistency:** `evaluate_reuse_first_history_route` is defined in
  Task 1 and is the function consumed by every Task 1 and Task 2 test.
