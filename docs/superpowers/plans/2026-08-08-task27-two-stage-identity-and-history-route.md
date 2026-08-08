# T27-A1R1 Two-stage identity and history route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create one deterministic offline contract that prepares a bounded
DexScreener identity probe followed, only after a separate gate, by a Solana
Tracker pool-specific 15-minute OHLCV pilot.

**Architecture:** The contract treats provider identity and historical-price
data as two distinct evidence roles.  Stage A contains one exact public
DexScreener pair lookup for the owner-nominated pool.  Stage B remains a
template until Stage A produces and freezes the base-token mint; it then
requires a separate exact owner gate for two Solana Tracker GETs.  Neither
stage is an automatic fallback, historical capture, PIT claim, or execution
route.

**Tech Stack:** Repository-authored Markdown/YAML/JSON, JSON Schema Draft
2020-12, Python standard library `unittest`, PyYAML, and `jsonschema`; no new
dependency.

## Global Constraints

- `T27-A1` GeckoTerminal authority is consumed; never retry, change browser
  signature, or invoke GeckoTerminal again in this atom.
- The implemented atom is offline: zero provider/API/RPC/WSS calls, zero
  credentials, zero raw provider bytes, zero R2/R3 reads, zero wallet/signer/
  transaction actions, and zero cash spend.
- Stage A is exactly one future unauthenticated DexScreener `GET` for the
  nominated Solana pool; it establishes identity only.
- Stage B is separately owner-authorised only after a retained, hash-bound
  Stage A identity.  It allows at most two future Solana Tracker GETs and a
  local header-only secret transport; no secret may appear in Git, fixtures,
  URLs, receipts, logs, or chat.
- Use a pool-specific Solana Tracker chart request, 15-minute UTC bars,
  explicit `time_from`/`time_to`, `currency=usd`,
  `removeOutliers=false`, and `fastCache=false`.  The token-only chart route
  and dynamic-pool selection are forbidden.
- Missing, incomplete, altered, or unavailable data remains `UNKNOWN` and
  stops the route.  No retry, imputation, Helius reconstruction, automatic
  provider fallback, PIT, alpha, execution, PnL, NetReturn, cashflow, or
  TASK-27-completion claim is allowed.
- Raw responses, if a later authorised runtime stage produces them, live only
  under ignored `local/`; failed/unusable raw evidence retains for 30 days
  under A4.  Tracked artifacts retain only sanitized status and hashes.
- Do not modify Project Sources, source-release registry, generated Catalog
  files, dependencies, scheduler, wallet, signer, or runtime collector.

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/contracts/task27_two_stage_identity_and_history_route_contract_v1.md` | Human-readable scope, stage sequence, evidence, authority, failure and non-claim rules. |
| `configs/task27_two_stage_identity_and_history_route_contract_v1.yaml` | Machine-readable policy: nominated pool, exact Stage A URL, Stage B templates, caps, retention and claim boundary. |
| `catalog/schemas/task27_two_stage_identity_and_history_route.schema.json` | Draft 2020-12 schema for one synthetic packet and its adversarial mutations. |
| `tests/fixtures/task27/two_stage_identity_and_history_route_v1.json` | One valid synthetic packet and exactly 17 adversarial cases. No real API key or raw provider payload. |
| `tests/test_task27_two_stage_identity_and_history_route.py` | Asset existence, source binding, schema, semantic-invariant, adversarial and receipt-binding tests. |
| `docs/evidence/task27/a1r1_two_stage_identity_and_history_route_acceptance_v1.json` | Hash-bound targeted acceptance, FULL_REVIEW outcome, non-claims and next external boundary. |

### Task 1: Implement the deterministic two-stage route contract

**Files:**

- Create: `docs/contracts/task27_two_stage_identity_and_history_route_contract_v1.md`
- Create: `configs/task27_two_stage_identity_and_history_route_contract_v1.yaml`
- Create: `catalog/schemas/task27_two_stage_identity_and_history_route.schema.json`
- Create: `tests/fixtures/task27/two_stage_identity_and_history_route_v1.json`
- Create: `tests/test_task27_two_stage_identity_and_history_route.py`
- Create: `docs/evidence/task27/a1r1_two_stage_identity_and_history_route_acceptance_v1.json`

**Interfaces:**

- Consumes: the A7 selection snapshot and its source-smoke receipt from
  `configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml`
  and `docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json`.
- Produces: `semantic_errors(packet, policy) -> set[str]` in the focused test
  module; a valid synthetic route packet; and a receipt whose four artifact
  hashes bind contract, config, schema and fixture.
- Runtime boundary: future Stage A has the exact URL
  `https://api.dexscreener.com/latest/dex/pairs/solana/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.
  Future Stage B has no concrete URL until the Stage A base mint is frozen,
  and therefore has no authority in this task.

- [ ] **Step 1: Write the failing test module before the assets exist.**

  Define the six test methods and the exact semantic-error vocabulary.  The
  first run must fail because the six new files do not exist, not because a
  provider is called.

  ```python
  EXPECTED_ERRORS = {
      "DEXSCREENER_URL_DRIFT",
      "STAGE_A_REQUEST_CAP_BREACH",
      "STAGE_A_IDENTITY_MISMATCH",
      "STAGE_B_BEFORE_FROZEN_IDENTITY",
      "TOKEN_ONLY_OR_DYNAMIC_POOL_FORBIDDEN",
      "HIDDEN_TRANSFORMATION_FORBIDDEN",
      "SECRET_TRANSPORT_FORBIDDEN",
      "UNBOUNDED_QUOTA_FORBIDDEN",
      "AUTOMATIC_FALLBACK_FORBIDDEN",
      "HELIUS_RECONSTRUCTION_FORBIDDEN",
      "RAW_MANIFEST_REQUIRED",
      "PANEL_RULE_RELAXATION_FORBIDDEN",
      "OFFLINE_AUTHORITY_PROMOTION_FORBIDDEN",
      "EXTERNAL_ACTION_IN_OFFLINE_ATOM",
      "RAW_RETENTION_IN_OFFLINE_ATOM",
      "FORBIDDEN_DECISION_CLAIM",
      "PREMATURE_OWNER_APPROVAL_FORBIDDEN",
  }

  def test_required_assets_exist(self) -> None: ...
  def test_policy_binds_a7_and_freezes_stage_a_only(self) -> None: ...
  def test_valid_packet_is_schema_valid_and_offline(self) -> None: ...
  def test_semantic_invariants_accept_the_valid_packet(self) -> None: ...
  def test_each_adversarial_case_breaks_its_named_boundary(self) -> None: ...
  def test_acceptance_receipt_binds_assets_and_preserves_full_review(self) -> None: ...
  ```

- [ ] **Step 2: Run the new test to prove the red state.**

  Run:

  ```text
  uv run --locked --managed-python python -B -m unittest tests.test_task27_two_stage_identity_and_history_route
  ```

  Expected: `FAIL` because `REQUIRED_PATHS` includes files that have not yet
  been created.  Confirm the output contains no network attempt.

- [ ] **Step 3: Create the contract and policy with all bounds explicit.**

  The Markdown contract must state that `DEXSCREENER_PUBLIC_PAIR_IDENTITY` is
  identity-only, `SOLANA_TRACKER_POOL_OHLCV` is a later history-only candidate,
  and `HELIUS_TRANSACTION_RECONSTRUCTION` is deferred and forbidden as an
  automatic recovery action.  It must carry these decision outcomes exactly:

  ```text
  READY_FOR_BOUNDED_HISTORY_CAPTURE
  REDESIGN_PUBLIC_HISTORY_ROUTE
  CLOSE_PUBLIC_HISTORY_ROUTE
  ```

  Create the YAML around this concrete policy shape.  Values under
  `synthetic_stage_b_identity` are fixtures only and are never provider facts.

  ```yaml
  schema: smial.task27.two_stage_identity_and_history_route.contract
  schema_version: '1.0'
  task_id: TASK-27
  atom_id: T27-A1R1_TWO_STAGE_IDENTITY_AND_HISTORY_ROUTE_DESIGN_V1
  consumer: OWNER_EXTERNAL_READ_DECISION
  source_binding:
    a7_selection_config: configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml
    source_smoke_receipt: docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json
  stage_a:
    provider: DEXSCREENER_PUBLIC_PAIR_IDENTITY
    request_count: 1
    method: GET
    url: https://api.dexscreener.com/latest/dex/pairs/solana/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
    output: FROZEN_BASE_MINT_AND_POOL_IDENTITY
    provider_read_authority: false
  stage_b:
    provider: SOLANA_TRACKER_POOL_OHLCV
    precondition: STAGE_A_RETAINED_IDENTITY_REQUIRED
    request_count_max: 2
    credential_transport: LOCAL_HEADER_FROM_ENV_REDACTED
    token_endpoint_template: https://data.solanatracker.io/tokens/{base_mint}
    pool_chart_endpoint_template: https://data.solanatracker.io/chart/{base_mint}/{pool_address}
    chart_parameters:
      type: 15m
      time_from: OWNER_FROZEN_UTC_EPOCH_REQUIRED
      time_to: OWNER_FROZEN_UTC_EPOCH_REQUIRED
      currency: usd
      removeOutliers: false
      fastCache: false
      timezone: UTC
      route_kind: POOL_SPECIFIC_ONLY
    provider_read_authority: false
  ```

- [ ] **Step 4: Create the schema, synthetic fixture, and semantic validator.**

  Use `additionalProperties: false` at every schema object that has a fixed
  contract.  The fixture must have one `valid_packet` and exactly 17
  `adversarial_cases`; every mutation stays schema-valid so the semantic
  validator, not incidental JSON-shape failure, proves the intended boundary.

  Implement the checks in the test module with this decision shape:

  ```python
  def semantic_errors(packet: dict[str, Any], policy: dict[str, Any]) -> set[str]:
      errors: set[str] = set()
      stage_a = packet["stage_a"]
      stage_b = packet["stage_b"]
      authority = packet["authority"]

      if stage_a["url"] != policy["stage_a"]["url"]:
          errors.add("DEXSCREENER_URL_DRIFT")
      if stage_a["request_count"] != 1:
          errors.add("STAGE_A_REQUEST_CAP_BREACH")
      if stage_a["identity_state"] != "FROZEN_BASE_MINT_AND_POOL_IDENTITY":
          errors.add("STAGE_A_IDENTITY_MISMATCH")
      if stage_b["activation_state"] != "STAGE_A_RETAINED_IDENTITY_REQUIRED":
          errors.add("STAGE_B_BEFORE_FROZEN_IDENTITY")
      if stage_b["route_kind"] != "POOL_SPECIFIC_ONLY":
          errors.add("TOKEN_ONLY_OR_DYNAMIC_POOL_FORBIDDEN")
      if stage_b["removeOutliers"] is not False or stage_b["fastCache"] is not False:
          errors.add("HIDDEN_TRANSFORMATION_FORBIDDEN")
      if stage_b["credential_transport"] != "LOCAL_HEADER_FROM_ENV_REDACTED":
          errors.add("SECRET_TRANSPORT_FORBIDDEN")
      if authority["provider_read_authority"] or authority["provider_api_rpc_wss_calls"] != 0:
          errors.add("OFFLINE_AUTHORITY_PROMOTION_FORBIDDEN")
      return errors
  ```

  Add the remaining explicit checks for the two-call Stage B cap, no quota
  claim, no fallback/Helius path, raw-manifest requirement, 96 natural bars,
  `UNKNOWN` missingness, zero raw retention in this atom, false claims, and
  disabled future approval.  Each adversarial case changes one JSON Pointer
  and asserts its named error is present while every returned error remains in
  `EXPECTED_ERRORS`.

- [ ] **Step 5: Bind the acceptance receipt after the four artifacts are final.**

  Compute SHA-256 from the final bytes of contract, config, schema and fixture.
  The receipt must identify the six-file managed write set, `FULL_REVIEW`, six
  targeted tests, 17 adversarial rejections, `NO_CHANGE` for Project Sources,
  zero in every authority/action counter, and:

  ```json
  {
    "state_change": "NONE",
    "next_boundary": {
      "provider_read_authority_granted": false,
      "next_owner_gate": "ONE_EXACT_DEXSCREENER_IDENTITY_GET_REQUIRED",
      "solana_tracker_stage_b_authorized": false
    }
  }
  ```

- [ ] **Step 6: Run the focused contract test to prove the green state.**

  Run:

  ```text
  uv run --locked --managed-python python -B -m unittest tests.test_task27_two_stage_identity_and_history_route
  ```

  Expected: `Ran 6 tests ... OK`.  Confirm all 17 mutations are rejected and
  no external client, credential lookup, raw-data directory, or network call
  exists in the test module.

- [ ] **Step 7: Review the exact diff and commit the atom.**

  Run:

  ```text
  git diff --check
  git status --short
  git diff -- docs/contracts/task27_two_stage_identity_and_history_route_contract_v1.md configs/task27_two_stage_identity_and_history_route_contract_v1.yaml catalog/schemas/task27_two_stage_identity_and_history_route.schema.json tests/fixtures/task27/two_stage_identity_and_history_route_v1.json tests/test_task27_two_stage_identity_and_history_route.py docs/evidence/task27/a1r1_two_stage_identity_and_history_route_acceptance_v1.json
  ```

  Expected: exactly the six planned paths, no secret-looking value, no
  `local/` raw evidence, and no unrelated changes.  Commit with:

  ```text
  git add -- docs/contracts/task27_two_stage_identity_and_history_route_contract_v1.md configs/task27_two_stage_identity_and_history_route_contract_v1.yaml catalog/schemas/task27_two_stage_identity_and_history_route.schema.json tests/fixtures/task27/two_stage_identity_and_history_route_v1.json tests/test_task27_two_stage_identity_and_history_route.py docs/evidence/task27/a1r1_two_stage_identity_and_history_route_acceptance_v1.json
  git commit -m "feat: freeze TASK-27 two-stage history route"
  ```

### Task 2: Validate and deliver the exact offline candidate

**Files:**

- Modify: none after the Task 1 commit.
- Generate locally only: ignored delivery-preflight receipt under
  `local/delivery_preflight/`.

**Interfaces:**

- Consumes: the exact Task 1 commit with a clean tracked working tree.
- Produces: targeted test evidence, one tracked-only full-gate receipt, a
  non-force pushed branch, Draft PR and CI head read-back.  It never produces
  TASK-27 acceptance, external provider evidence, or merge authority.

- [ ] **Step 1: Reconfirm the committed candidate is clean and exact.**

  Run:

  ```text
  git status --short
  git rev-parse HEAD
  uv run --locked --managed-python python -B -m unittest tests.test_task27_two_stage_identity_and_history_route
  ```

  Expected: empty status; one committed HEAD; six focused tests pass.  Do not
  rerun a check after a pass unless the commit bytes or validation policy
  changes.

- [ ] **Step 2: Run the single tracked-only delivery gate.**

  Run:

  ```text
  uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
  ```

  Expected: pass in an isolated tracked-only checkout, with no dependency on
  the ignored T27 raw failure evidence.  Retain the compact ignored preflight
  receipt; do not commit it.

- [ ] **Step 3: Push once and open one Draft PR.**

  Push the unchanged candidate non-force.  Open a Draft PR whose body states:

  ```text
  Offline contract only. No provider/API/RPC/WSS calls, credentials, raw data,
  wallet, signer, transaction, cash spend, Project Source change, or TASK-27
  acceptance. Future Stage A requires one new exact owner-authorised
  DexScreener GET; Stage B remains unauthorised.
  ```

  Record the exact feature head and independently read back CI for that head.
  Do not merge: exact owner confirmation of that PR remains mandatory.

## Plan Self-Review

- **Spec coverage:** Task 1 maps all required boundaries: provider-role split,
  exact Stage A URL, separately gated Stage B, header-only secret transport,
  raw retention, 96-bar rule, failure stops, non-claims, full review and
  synthetic adversarial proof. Task 2 maps the repository delivery policy.
  No spec requirement is uncovered.
- **Placeholder scan:** no `TODO`, `TBD`, generic error-handling instruction,
  or undefined task reference remains.  Stage B's dynamic base mint is
  deliberately a prohibited runtime input until Stage A is separately
  completed, rather than a placeholder.
- **Type consistency:** the plan uses `semantic_errors(packet, policy)` in
  every test step; `stage_a`, `stage_b`, `authority`, `valid_packet`, and
  `adversarial_cases` are defined by the proposed fixture/schema contract.
- **Scope:** this is one testable offline data-route contract.  It does not
  bundle an adapter framework, provider call, raw-capture program, dashboard,
  or Helius reconstruction.
