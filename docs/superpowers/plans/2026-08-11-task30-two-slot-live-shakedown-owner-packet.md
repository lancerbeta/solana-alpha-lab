# TASK-30 A11B Two-Slot Live Shakedown Owner Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, deterministic owner packet that can later request—without granting—two bounded live OHLCV shakedown slots.

**Architecture:** A pure Python validator reads one YAML packet and frozen A10/A11A bindings. It fails closed on a provider promotion, an unsafe read shape, missing retention/monitoring or a premature second slot. A small local renderer produces a Russian owner readout from tracked bytes; no network or runtime collection component exists.

**Tech Stack:** Python standard library, PyYAML, jsonschema, unittest and existing Catalog validation/generation scripts.

## Global Constraints

- Base: `60d9a1f2fbb06c0bfb4bc4b6f85c33dbfca13e8a`; branch: `task30/a11b-two-slot-owner-packet`.
- The only candidate is the A10 public keyless GeckoTerminal OHLCV route for frozen pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`; candidate does not mean selection or authority.
- Exactly two 900-second closed slots × offsets `[0, 15, 30, 60]` gives an eight-GET maximum. Retry, fallback, credential, scheduler and background process are forbidden.
- Raw JSON is future-only and must remain outside Git under retention `A4`; this atom writes no raw data.
- Any capture-health failure stops the run. It cannot become a market gap or a restart permission.
- No provider/API/RPC/WSS call, key use, dependency, database, R2/R3 access, wallet/signer/transaction, spend, task trial/acceptance or numeric NetReturn is in scope.
- Use the existing Catalog generator; never hand-edit generated Catalog outputs.

---

## File map

| Path | Responsibility |
| --- | --- |
| `docs/tasks/TASK-30-two-slot-live-shakedown-owner-packet.md` | Bounded A11B task statement and exact external boundary. |
| `docs/contracts/task30_two_slot_live_shakedown_owner_packet_contract_v1.md` | Human-readable future approval and recovery contract. |
| `configs/task30_two_slot_live_shakedown_owner_packet_v1.yaml` | Unauthorised machine-readable candidate packet. |
| `catalog/schemas/task30_two_slot_live_shakedown_owner_packet.schema.json` | Structural packet schema. |
| `src/solana_alpha_lab/task30_two_slot_live_shakedown_owner_packet.py` | Pure fail-closed packet validator and readout model. |
| `scripts/show_task30_two_slot_live_shakedown_owner_packet.py` | Local JSON/Markdown renderer with no request capability. |
| `tests/fixtures/task30/two_slot_live_shakedown_owner_packet_v1.json` | Synthetic expected packet-validation result. |
| `tests/test_task30_two_slot_live_shakedown_owner_packet.py` | Behaviour, adversarial, readout, receipt and Catalog checks. |
| `docs/reports/task30/two_slot_live_shakedown_owner_packet_readout_v1.md` | Deterministic Russian owner-facing packet preview. |
| `docs/evidence/task30/a11b_two_slot_live_shakedown_owner_packet_acceptance_v1.json` | Hash-bound offline acceptance. |
| Catalog core/lifecycle/manifest and generated map/edges | Stable asset records and generated navigation. |

## Task 1: Define and prove the non-executable packet

**Files:**
- Create: task statement, contract, YAML, JSON Schema and `tests/test_task30_two_slot_live_shakedown_owner_packet.py`.
- Create: `src/solana_alpha_lab/task30_two_slot_live_shakedown_owner_packet.py`.

**Interfaces:**
- Consumes: A10 runtime receipt, A11A acceptance receipt and frozen TASK-28 group.
- Produces: a schema-valid mapping accepted by `validate_owner_packet(packet) -> dict[str, object]`.

- [ ] **Step 1: Write the failing packet-behaviour test**

```python
def test_packet_is_only_a_candidate_and_cannot_authorize_external_capture():
    result = validate_owner_packet(load_yaml(PACKET_PATH))
    self.assertEqual(result["status"], "OWNER_APPROVAL_REQUIRED")
    self.assertFalse(result["external_capture_authorized"])
    self.assertEqual(result["max_provider_gets"], 8)
```

- [ ] **Step 2: Run it and observe the expected missing-module failure**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_owner_packet.Task30TwoSlotLiveShakedownOwnerPacketTests.test_packet_is_only_a_candidate_and_cannot_authorize_external_capture -v
```

Expected: FAIL because the packet module and tracked packet do not exist.

- [ ] **Step 3: Add task, contract, YAML and JSON Schema**

The YAML must carry `TASK-30`, `T30-A11B_TWO_SLOT_LIVE_SHAKEDOWN_OWNER_PACKET_V1`, `GECKOTERMINAL_PUBLIC_KEYLESS`, `provider_selected: false`, `external_capture_authorized: false`, `slot_count: 2`, offsets `[0, 15, 30, 60]`, `max_provider_gets: 8` and `retention: A4`. It binds frozen pool, 900 seconds, A10 `START_LABELED` and A11A. It requires foreground starts, an immediate raw-manifest/health receipt, no retry/fallback or credentials and `OWNER_APPROVAL_REQUIRED`.

- [ ] **Step 4: Implement the minimal pure validator**

```python
class TwoSlotOwnerPacketError(ValueError):
    pass

def validate_owner_packet(packet: Mapping[str, Any]) -> dict[str, object]:
    """Return an unauthorised owner-review result or fail closed."""
```

Reject a changed binding, selected provider, external authority, wrong slot count/offsets/read cap, retry, fallback, credentials, optional retention/monitoring, an unsafe second slot and every promoted research/execution/cashflow claim. Import no network client.

- [ ] **Step 5: Re-run the focused test**

Expected: PASS.

## Task 2: Lock unsafe paths and generate the owner readout

**Files:**
- Modify: validator and test.
- Create: fixture, local renderer and tracked Russian readout.

**Interfaces:**
- Consumes: valid tracked packet.
- Produces: deterministic JSON model and Markdown preview.

- [ ] **Step 1: Write failing adversarial and readout tests**

```python
def test_selected_provider_retry_or_unsafe_second_slot_is_rejected():
    for changed in (
        {"provider_selected": True},
        {"retry": True},
        {"second_slot_requires_prior_receipt": False},
    ):
        with self.assertRaises(TwoSlotOwnerPacketError):
            validate_owner_packet(mutated_packet(changed))

def test_readout_names_the_eight_get_cap_and_no_authority():
    completed = subprocess.run([...], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=False)
    self.assertEqual(completed.returncode, 0)
    self.assertIn("8", completed.stdout)
    self.assertIn("не разрешает", completed.stdout)
```

- [ ] **Step 2: Run the focused suite and observe expected failure**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_owner_packet -v
```

Expected: FAIL until guards and renderer exist.

- [ ] **Step 3: Add only the required guards and renderer**

The renderer supports `--format json` and `--format markdown`, reads tracked YAML and imports no request library. Markdown names two foreground slots, eight GET maximum, future-only A4 retention, immediate health stop and remaining owner review.

- [ ] **Step 4: Add the synthetic fixture and verify focused PASS**

Run the Step 2 command. Expected: PASS with zero external side effects.

## Task 3: Record acceptance and Catalog relationships

**Files:**
- Create: hash-bound acceptance receipt.
- Modify: test, Catalog core/lifecycle/manifest.
- Regenerate: `catalog/generated/asset_edges.json` and `docs/PROJECT_MAP.md`.

**Interfaces:**
- Consumes: all Task 1–2 artifacts.
- Produces: `PASS_WITH_LIMITATIONS`, `STATE_CHANGE=NONE` evidence plus registered assets.

- [ ] **Step 1: Write the failing receipt/Catalog test**

```python
def test_acceptance_binds_packet_artifacts_and_zero_side_effects():
    receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
    self.assertFalse(receipt["non_claims"]["external_capture_authorized"])
    assert_bound_hashes(receipt)
```

- [ ] **Step 2: Add minimal acceptance and Catalog records**

The receipt records `FULL_REVIEW`, `PASS_WITH_LIMITATIONS`, `STATE_CHANGE=NONE`, `NO_CHANGE` for Project Sources and zero counts for excluded authority. Assets depend on A10/A11A and are consumed by only `TASK-30` and `FACTORY-001`.

- [ ] **Step 3: Regenerate and run final targeted validation**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_task30_two_slot_live_shakedown_owner_packet -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: PASS; no raw data, key or scheduler registration exists.

## Task 4: Deliver the offline atom

**Files:** all validated A11B files only.

**Interfaces:**
- Consumes: clean committed branch and focused validation.
- Produces: one tracked-only delivery receipt, exact-head CI and a PR; merge remains governed by the repository owner-attention machine gate.

- [ ] **Step 1: Confirm exact inventory**

```powershell
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
```

Expected: only File map/generated Catalog paths, never a provider response, credential, raw data, scheduler or dependency lock change.

- [ ] **Step 2: Run the one full delivery owner gate**

```powershell
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: `TRACKED_ONLY_DELIVERY_PREFLIGHT: PASS`; do not repeat another full local gate for unchanged bytes.

- [ ] **Step 3: Push, create one Draft PR and read exact-head CI**

```powershell
git push -u origin task30/a11b-two-slot-owner-packet
gh pr create --draft --base main --head task30/a11b-two-slot-owner-packet
gh pr view --json headRefOid,statusCheckRollup,mergeStateStatus,reviews
```

Expected: exact PR head and all required CI checks pass.

## Plan self-review

- Spec coverage: Task 1 fixes the unauthorised packet surface; Task 2 proves safety branches and owner readout; Task 3 binds acceptance/Catalog; Task 4 delivers one isolated candidate.
- Placeholder scan: no unfinished implementation field is used; future external execution is deliberately an excluded owner boundary.
- Type consistency: `validate_owner_packet`, `TwoSlotOwnerPacketError`, packet status and external-authority boolean are declared before tests and renderer consume them.
