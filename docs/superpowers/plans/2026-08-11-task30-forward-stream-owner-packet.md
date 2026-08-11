# TASK-30 A13 — Forward Stream Owner Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.  Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic, offline-only readiness package for one
future owner-authorised `transactionSubscribe` technical pilot on the frozen
pool.  It must make the external boundary, caps, terminal truth states,
retention/recovery obligations and non-claims machine-checkable without
opening a connection or choosing a live provider.

**Architecture:** The durable contract/configuration/schema freeze one
*proposed* Helius-compatible stream envelope.  One pure Python evaluator
validates the packet and returns a safe readiness decision; one renderer turns
it into an owner-readable Russian packet.  The evaluator has no transport,
credential, filesystem-retention or scheduler capability.  Synthetic fixtures
exercise every terminal state and rejection path.  Catalog bindings and a
FULL_REVIEW receipt make the boundary discoverable without changing Project
Sources.

**Tech Stack:** Python 3.13, `unittest`, YAML, JSON Schema, existing Catalog
generator, `uv` locked environment.  No new dependency and no live provider
client.

## Global constraints

- Bind only `TASK-30`, `T30-A13_FORWARD_STREAM_OWNER_PACKET_READINESS_V1`,
  frozen group `RC001-H07-H01-LIQUIDITY-RETENTION`, network `solana`, pool
  `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`, and base mint
  `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`.
- This implementation has zero provider/API/RPC/WSS calls, credential reads,
  raw writes, scheduler/background process, new dependencies, R2/R3 access,
  wallet/signer/transaction action, cash spend, trial opening, or Project
  Sources change.
- `HELIUS_TRANSACTION_SUBSCRIBE` is `PROPOSED`, never selected or active.
  No endpoint, URL, API key, subscription ID or live response may enter a
  tracked artifact.
- The sole proposed technical envelope is one foreground WSS connection, one
  subscription, maximum 1,200 seconds, maximum 500 notifications and zero
  retry/reconnect/fallback.  A later external gate must name the actual A4
  absolute retention root outside Git; this offline package stores only the
  retention class and requirement.
- Missing and transport loss are not market facts.  `UNKNOWN` never becomes
  empty, zero, flat, complete, projected, H07/H01 evidence, a trial,
  execution, settlement, PnL or NetReturn.
- Reuse verdict is `WRAP_CANDIDATE`: a later implementation may inspect the
  bounded WSS/receipt boundary in
  `src/solana_alpha_lab/lifecycle_discovery_transport.py`, but must not reuse
  its Pump-specific `logsSubscribe` binding/parser without a new exact fit
  decision.
- A later external pilot needs a new exact owner authority phrase.  Passing
  this package authorizes neither that pilot nor its reconciliation.

## Task 1: Freeze the packet’s policy and prove its schema adversarially

**Files:**
- Create: `docs/tasks/TASK-30-forward-stream-owner-packet.md`
- Create: `docs/contracts/task30_forward_stream_owner_packet_contract_v1.md`
- Create: `configs/task30_forward_stream_owner_packet_v1.yaml`
- Create: `catalog/schemas/task30_forward_stream_owner_packet.schema.json`
- Create: `tests/fixtures/task30/forward_stream_owner_packet_v1.json`
- Create: `tests/test_task30_forward_stream_owner_packet.py`

**Interfaces:**
- Contract ID: `TASK30-FORWARD-STREAM-OWNER-PACKET-V1`.
- Config schema: `smial.task30.forward-stream-owner-packet.policy`, version
  `1.0`.
- Synthetic fixture supplies one valid `expected_result`, and invalid packets
  are produced by pointer replacement in tests.

- [ ] **Step 1: Write the failing contract-and-schema test first**

Create `tests/test_task30_forward_stream_owner_packet.py` with a test that
loads YAML, JSON Schema and the fixture.  It should fail until the policy and
evaluator exist.  Its test names must describe the truth boundaries—not a
provider integration.

```python
def test_policy_is_schema_valid_and_only_proposes_one_pilot(self) -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    self.assertFalse(list(Draft202012Validator(schema).iter_errors(config)))
    self.assertEqual(evaluate_forward_stream_owner_packet(config), fixture["expected_result"])
```

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_owner_packet
```

Expected: an import/collection failure proving the tests demand the absent
offline evaluator.  Do not add a placeholder evaluator to make this green.

- [ ] **Step 2: Add the versioned contract, task note, config, schema and fixture**

The contract and config must contain:

- frozen task/atom/consumer/group/target identity;
- `provider_candidate=HELIUS_TRANSACTION_SUBSCRIBE`,
  `provider_selection=PROPOSED_NOT_SELECTED`, `transport_candidate=WSS_JSON_RPC`;
- candidate request semantics, but no endpoint: `transactionSubscribe`,
  `commitment=confirmed`, `encoding=jsonParsed`, `transactionDetails=full`,
  `maxSupportedTransactionVersion=0`, `failed=false`, `vote=false`;
- caps `{connections: 1, subscriptions: 1, open_duration_seconds: 1200,
  notifications: 500}`;
- `retry=false`, `reconnect=false`, `fallback=false`,
  `monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND`, `retention_class=A4`, and
  `absolute_raw_root=OWNER_INPUT_REQUIRED`;
- exact later-pilot owner phrase template, without an endpoint or credential;
- the terminal enum from the accepted design:
  `PILOT_NOT_AUTHORIZED`, `CONNECTION_OR_AUTH_REJECTED`,
  `SUBSCRIPTION_REJECTED`, `NO_OBSERVED_TX_NO_EMPTY_CLAIM`,
  `OBSERVATION_RETAINED_TECHNICAL_ONLY`, `TRANSPORT_LOST_UNKNOWN`, and
  `RETENTION_FAILED_STOP`;
- explicit stop and recovery rules, including a distinct reconciliation
  reference requirement for `UNKNOWN`; and
- authority counters all zero and non-claims all false.

The JSON Schema must reject credential-shaped keys recursively where practical
and enforce enums, exact numeric caps and required fields.  The valid fixture
must document the expected safe result but contain no raw payload, provider URL
or secrets.

- [ ] **Step 3: Add adversarial policy tests before evaluator implementation**

Use table-driven pointer replacements to prove schema or evaluator rejection
for all of these mutations:

1. selected/active provider rather than proposal;
2. a credential key/value, URL or credential-read flag;
3. more than one connection/subscription, duration over 1,200, notification
   cap over 500, or nonzero cash cap;
4. retry/reconnect/fallback enabled or unattended monitoring;
5. missing A4 retention requirement, no owner phrase or no reconciliation
   reference;
6. target pool/base-mint drift or an invented DEX program/route;
7. `NO_OBSERVED_TX_NO_EMPTY_CLAIM` promoted to an empty/zero/complete claim;
8. `TRANSPORT_LOST_UNKNOWN` followed by retry, projection, acceptance or
   automatic reconciliation; and
9. a technical receipt promoted to hypothesis evidence, trial, execution,
   settlement, PnL or numeric NetReturn.

Run the test module again.  Expected: it remains red only because the pure
evaluator is missing; the policy/schema failure cases themselves must already
be well-defined.

- [ ] **Step 4: Commit the frozen policy boundary**

```text
git add docs/tasks/TASK-30-forward-stream-owner-packet.md docs/contracts/task30_forward_stream_owner_packet_contract_v1.md configs/task30_forward_stream_owner_packet_v1.yaml catalog/schemas/task30_forward_stream_owner_packet.schema.json tests/fixtures/task30/forward_stream_owner_packet_v1.json tests/test_task30_forward_stream_owner_packet.py
git commit -m "docs: define forward stream owner packet"
```

## Task 2: Implement the pure evaluator and owner-readable packet

**Files:**
- Create: `src/solana_alpha_lab/task30_forward_stream_owner_packet.py`
- Create: `scripts/show_task30_forward_stream_owner_packet.py`
- Create: `docs/reports/task30/forward_stream_owner_packet_readout_v1.md`
- Modify: `tests/test_task30_forward_stream_owner_packet.py`

**Interfaces:**
- Public exception: `ForwardStreamOwnerPacketError(ValueError)`.
- Public evaluator:
  `evaluate_forward_stream_owner_packet(config: Mapping[str, Any]) -> dict[str, Any]`.
- Public renderer:
  `render_forward_stream_owner_packet(config: Mapping[str, Any]) -> str`.
- The CLI loads only the tracked YAML and prints the exact renderer output; it
  accepts no credential, endpoint, raw-path or network argument.

- [ ] **Step 1: Add the first red evaluator assertions**

Extend the test with an expected `READY_FOR_OWNER_EXTERNAL_READ_GATE_WITH_LIMITATIONS`
result whose `authority` counters are zero, `provider_selection` is proposed
only, and `next_action` is the exact later owner gate.  Add a failing import
test for the evaluator and renderer.

- [ ] **Step 2: Implement the fail-closed pure evaluator**

Implement helpers for typed mappings, exact fields, recursive
credential-shaped-key detection and terminal/non-claim validation.  The
evaluator must not import `urllib`, `socket`, `ssl`, `websockets`, provider
modules, environment access or filesystem writers.

Pseudocode:

```python
def evaluate_forward_stream_owner_packet(config: Mapping[str, Any]) -> dict[str, Any]:
    _require_exact_identity(config)
    _require_zero_authority(config["authority"])
    _require_no_secret_or_endpoint(config)
    _require_proposal_only(config["provider"], config["transport"])
    _require_frozen_caps_and_no_retry(config["pilot_limits"])
    _require_unknown_recovery_without_auto_action(config["terminal_truth"])
    _require_non_claims(config["non_claims"])
    return {
        "decision": "READY_FOR_OWNER_EXTERNAL_READ_GATE_WITH_LIMITATIONS",
        "provider_selection": "PROPOSED_NOT_SELECTED",
        "external_action_authorized": False,
        "project_sources_disposition": "NO_CHANGE",
    }
```

`READY` means only “the owner can review a gate”; it never grants authority.
No evaluator path may contact the network or perform any write.

- [ ] **Step 3: Implement the Russian renderer and static readout**

The renderer must state in plain language:

- one proposed, read-only technical capture—not a trade;
- exact target and caps;
- what is retained only after a future gate;
- no retry/reconnect/fallback;
- the stop/recovery handling of `UNKNOWN`; and
- the exact later approval phrase template.

It must omit credentials, URLs, provider-commercial claims, raw notifications,
prices, volumes and performance figures.  Generate the tracked Markdown
readout from the renderer and add a byte-for-byte test against it.

- [ ] **Step 4: Make all targeted behavior tests green**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_owner_packet
```

Expected: PASS for valid policy, every adversarial case, safe renderer and
readout comparison.  Confirm the module import graph remains free of transport
and environment-access modules.

- [ ] **Step 5: Commit the pure offline evaluator**

```text
git add src/solana_alpha_lab/task30_forward_stream_owner_packet.py scripts/show_task30_forward_stream_owner_packet.py docs/reports/task30/forward_stream_owner_packet_readout_v1.md tests/test_task30_forward_stream_owner_packet.py
git commit -m "feat: evaluate forward stream owner packet offline"
```

## Task 3: Bind acceptance, Factory Fit and Catalog discovery

**Files:**
- Create: `docs/evidence/task30/a13_forward_stream_owner_packet_acceptance_v1.json`
- Create: `docs/evidence/task30/a13_forward_stream_owner_packet_factory_fit_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`
- Modify: `docs/OPERATOR_NAVIGATION.md`
- Modify: `tests/test_task30_forward_stream_owner_packet.py`

**Interfaces:**
- Acceptance binds the exact SHA-256 of every A13 artifact—including accepted
  design and implementation plan—and declares `STATE_CHANGE=NONE`.
- Factory Fit is `FULL_REVIEW`, expected verdict `PASS_WITH_LIMITATIONS`.
- Catalog receives durable task/contract/config/schema/fixture/module/script/
  report/test/evidence identifiers using current repository conventions.

- [ ] **Step 1: Extend the test with acceptance and Factory Fit checks**

Assert all artifact hashes, zero side-effect counters, proposal-only provider
state, `NO_CHANGE` Sources disposition and correct Factory Fit/radar outcomes.
Mutate the in-memory receipt so that a provider call, raw write, selected
provider or trial claim is present; the test must reject it.

- [ ] **Step 2: Create receipts and Catalog registrations**

The acceptance record must include the reuse-first conclusion:
`WRAP_CANDIDATE` for the existing WSS safety/receipt pattern, with the
Pump-specific parser explicitly unfit for direct reuse.  Factory Fit must
state that this package lowers future operator ambiguity without claiming a
data route works.  Its Product Horizon result is:

- `NOW`: one explicit owner external-read decision only after the packet;
- `WATCH`: replay-capable transport only after a valid future pilot exposes an
  unresolved coverage/recovery requirement.

Both receipts must list all provider, credential, raw-data, cash, wallet,
transaction, R2/R3 and Project Sources counters as zero/false.

- [ ] **Step 3: Regenerate derived Catalog consumers**

Run:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
```

Expected: generated edges/project map/operator navigation change only as
required by the new registered assets.

- [ ] **Step 4: Run targeted integrity validation**

```text
uv run --locked --managed-python python -B -m unittest tests.test_task30_forward_stream_owner_packet
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: all PASS, all durable files registered and no generated-view drift.

- [ ] **Step 5: Commit bound evidence**

```text
git add docs/evidence/task30/a13_forward_stream_owner_packet_acceptance_v1.json docs/evidence/task30/a13_forward_stream_owner_packet_factory_fit_v1.json catalog/assets/core.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md docs/OPERATOR_NAVIGATION.md tests/test_task30_forward_stream_owner_packet.py
git commit -m "docs: bind forward stream owner packet"
```

## Task 4: Deliver one exact offline candidate

**Files:**
- Modify only Task 1–3 outputs if a targeted validation or Catalog repair
  proves necessary.

- [ ] **Step 1: Verify the exact candidate and owner-attention route**

Run the current `control/owner_attention_gate_v1.yaml` checker for the exact
head.  It must return `AUTONOMOUS` for push/PR/ordinary merge and reject any
external pilot action.  Inspect:

```text
git diff --name-status origin/main...HEAD
git diff --check origin/main...HEAD
```

Expected: only design/plan, offline policy, synthetic fixture/test/evaluator,
receipts and required Catalog/generated views.  No provider transport,
credential, dependency, Source release or wallet path.

- [ ] **Step 2: Run the proportional delivery gate once**

Attempt the repository’s CI-owned delivery pilot:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --ci-owned-delivery
```

If its machine eligibility rejects the candidate, run exactly one:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Do not run both a local full gate and a remote full gate for unchanged bytes.
Do not introduce a test skip to satisfy a clean checkout.

- [ ] **Step 3: Push and open one Draft PR**

```text
git push -u origin task30/a13-forward-stream-owner-packet
```

Create one Draft PR through the standard GitHub transport, then read back the
exact head and remote CI once.  No provider API/RPC/WSS request is involved.

- [ ] **Step 4: Stop at the external owner boundary**

Return exact PR/head/CI evidence, `STATE_CHANGE=NONE`, the Factory Fit result,
the Product Horizon result and the future exact owner phrase.  Do not execute
the pilot, claim provider selection or data completeness, or declare canonical
TASK-30 acceptance.

## Plan self-review

- **Spec coverage:** Tasks 1–3 cover the proposal-only stream packet,
  adversarial fail-closed behavior, safe owner readout, Catalog, acceptance,
  FULL Factory Fit and reuse-first finding.  Task 4 covers proportional
  delivery only.
- **Scope:** No task creates a connection, client, endpoint, credential,
  retention folder, scheduler, decoder, panel, trial, wallet action or spend.
- **Efficiency:** Existing WSS safety patterns are named and guarded as a
  future wrap candidate.  This avoids both a duplicate transport and premature
  dependency adoption.
- **Truth:** Every terminal outcome preserves the difference between “nothing
  observed” and “nothing happened”; `UNKNOWN` is irreducible without a separate
  reconciliation authority.
