# TASK-30 H07/H01 owner-visible vertical slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the already frozen H07/H01 research family into one owner-readable, deterministic offline decision: whether the present evidence can start a limited diagnostic, requires a specifically bounded capture gate, must redesign its data contract, or must close the route.

**Architecture:** A small pure-Python evaluator reads a versioned YAML control record and the immutable TASK-28 H07/H01 definition. It produces structured decision data and a Russian owner readout. A thin CLI renders that same result as JSON or Markdown; tests bind the relevant prior receipts, reject unsafe promotions, and verify a tracked acceptance receipt. No collector, provider adapter, scheduler, storage subsystem, lifecycle mutation, or dashboard is introduced.

**Tech Stack:** Python 3.13 stdlib, PyYAML, unittest, existing repository hash and validation conventions.

## Global Constraints

- Base contract: `origin/main` commit `6efa3b199f38a52864eadcf035a8cc8568dafb51`, tree `4c0c2ba65496fb061d2e00daca2d0cc9917ba7f6`.
- The worktree is a linked task branch. The ordinary repository validator intentionally fails there at `branch_main_or_ci_detached`; its full policy gate is exercised by GitHub Actions on the pull request and by tracked-only delivery after the candidate commit.
- Keep all operations offline. Provider/API/RPC/WSS, credentials, raw data, R2/R3, wallet, signer, transaction, cash, scheduler, background process, strategy promotion, numeric NetReturn and TASK-30 acceptance are forbidden.
- Treat missing and UNKNOWN as neither zero, no-trade, flat, nor settled. The evaluator must not turn price-only or quote-only observations into execution truth.
- Preserve TASK-28 frozen definitions and the empty historical lifecycle skeletons. This atom creates neither a selection-affecting trial nor a holdout-consumption record.
- Do not add a JSON schema, synthetic fixture file, database migration, provider adapter, new dependency, dashboard, ADR, registry mutation, or Catalog fan-out. The parent TASK-30 remains open; Catalog propagation is one terminal action after the parent task has a durable outcome.

## Files and Responsibilities

| File | Responsibility |
|---|---|
| `docs/tasks/TASK-30-h07-h01-owner-visible-vertical-slice.md` | Durable re-entry: consumer, evidence boundary, terminal decision semantics and non-claims. |
| `docs/contracts/task30_h07_h01_owner_visible_vertical_slice_contract_v1.md` | Human contract for the fail-closed evaluator and its owner-facing decision. |
| `configs/task30_h07_h01_owner_visible_vertical_slice_v1.yaml` | Versioned input bindings, evidence states, decision policy, authority counters and expected result. |
| `src/solana_alpha_lab/task30_h07_h01_owner_visible_vertical_slice.py` | Pure validation, decision and rendering functions. |
| `scripts/show_task30_h07_h01_owner_readout.py` | Read-only CLI that renders the configured decision as JSON or Russian Markdown. |
| `docs/reports/task30/h07_h01_owner_readout_v1.md` | Checked-in current owner view, generated from the versioned config. |
| `tests/test_task30_h07_h01_owner_visible_vertical_slice.py` | Deterministic happy-path, binding and adversarial tests. |
| `docs/evidence/task30/a7_h07_h01_owner_visible_vertical_slice_acceptance_v1.json` | Hash-bound receipt for the offline decision. |

## Task 1: Encode the frozen evidence boundary and decision policy

**Files:**
- Create: `tests/test_task30_h07_h01_owner_visible_vertical_slice.py`
- Create: `docs/tasks/TASK-30-h07-h01-owner-visible-vertical-slice.md`
- Create: `docs/contracts/task30_h07_h01_owner_visible_vertical_slice_contract_v1.md`
- Create: `configs/task30_h07_h01_owner_visible_vertical_slice_v1.yaml`
- Create: `src/solana_alpha_lab/task30_h07_h01_owner_visible_vertical_slice.py`

- [ ] **Step 1: Create the versioned YAML input, then write the failing unit-test scaffold.**

  The YAML control record is deterministic test input rather than production code, so create it first with the exact narrow shape specified in Step 4. Do not create the evaluator or any CLI before the test is written and observed failing.

  Load the new YAML configuration and the frozen `RC001-H07-H01-LIQUIDITY-RETENTION` group from `configs/task28_rc001_registry_freeze_v1.yaml`. Import `evaluate_owner_visible_slice` and `validate_owner_visible_slice` conditionally, so missing implementation is a clear test failure. Assert the current result is exactly `CAPTURE_REQUIRED` with ordered blockers `CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE` and `SETTLED_EXECUTION_TRUTH_UNAVAILABLE`.

  Add precise tests that mutate copies of the config and expect `ValueError` for:

  ```python
  cases = {
      "price_only_to_trial": ("current_evidence", "trial_admissible", True),
      "quote_to_settlement": ("current_evidence", "settled_execution_truth", "AVAILABLE"),
      "missing_to_zero": ("missingness_policy", "missing_to_zero", "ALLOWED"),
      "wrong_frozen_group": ("frozen_definition", "group_id", "RC001-H13-COMPOSITE-VETO"),
      "provider_authority": ("authority", "provider_api_rpc_wss_calls", 1),
  }
  ```

  The test must also assert that the three prior evidence paths and SHA-256 values are present: TASK-27 route close, TASK-26B execution-witness decision, and TASK-30 A6 forward-capture decision.

- [ ] **Step 2: Run the new test and record its expected red state.**

  Run:

  ```powershell
  uv run --locked --managed-python python -B tests/test_task30_h07_h01_owner_visible_vertical_slice.py
  ```

  Expected before implementation: import/availability failure for the new evaluator, not a skip.

- [ ] **Step 3: Write the task and human contract.**

  The task document must define the consumer as the next exact H07/H01 data-contract Entry Gate, explain in Russian that this atom is a map of the missing evidence rather than a strategy test, and state the four allowable terminal decisions:

  - `RUN_LIMITED_DIAGNOSTIC` only when every declared diagnostic input is explicitly available;
  - `CAPTURE_REQUIRED` when named, missing PIT input is the cheapest next uncertainty;
  - `REDESIGN_DATA` when a feasible capture cannot produce the frozen inputs;
  - `CLOSE_ROUTE` when the named route cannot meet the contract within its cap.

  Bind the contract to the immutable TASK-28 group ID and definition hash `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7`. State that current evidence is price/transport feasibility only; it is neither a research trial nor evidence of alpha, execution, PnL, or NetReturn.

- [ ] **Step 4: Complete and review the YAML control record.**

  Use a narrow top-level shape:

  ```yaml
  schema: smial.task30.h07-h01-owner-visible-vertical-slice.v1
  task_id: TASK-30
  atom_id: T30-A7_H07_H01_OWNER_VISIBLE_VERTICAL_SLICE_V1
  consumer: TASK30_H07_H01_EXACT_DATA_CONTRACT_ENTRY_GATE
  frozen_definition:
    group_id: RC001-H07-H01-LIQUIDITY-RETENTION
    definition_sha256: 14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7
  input_evidence:
    task27_route_close:
      path: docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json
      sha256: e901a59a72da29b3eb4a90e24a7d3bde91a4fc00c023310086376747ebe47e6d
    task26b_execution_witness:
      path: docs/evidence/task26b/a1_execution_witness_route_acceptance_v1.json
      sha256: 86cd5d33f3e29f9c3d365afc1aca511b212d6a809fa7be3ea2c6e65ffebd4b73
    task30_a6_forward_capture:
      path: docs/evidence/task30/a6_birdeye_route_hold_forward_capture_decision_acceptance_v1.json
      sha256: e40b3fc46762c015f439a453f68939859114f8f498e1791a0a68f1790829e036
  current_evidence:
    continuous_pit_price_history: MISSING_UNKNOWN
    settled_execution_truth: UNSUPPORTED
    trial_admissible: false
  missingness_policy:
    missing_to_zero: FORBIDDEN
    unknown_to_settled: FORBIDDEN
  authority:
    provider_api_rpc_wss_calls: 0
    credential_use: 0
  decision:
    value: CAPTURE_REQUIRED
    next_boundary: EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE
  ```

  `current_evidence` must preserve `MISSING_UNKNOWN` for continuous PIT history and `UNSUPPORTED` for settled execution truth. It may name the 96-slot forward-capture concept from A6, but must say provider is `NOT_SELECTED` and capture is `NOT_STARTED`.

- [ ] **Step 5: Implement the pure evaluator.**

  Implement only these public functions:

  The module exposes exactly `validate_owner_visible_slice(config, frozen_group)`, `evaluate_owner_visible_slice(config, frozen_group)`, and `render_owner_readout(result)`. Each receives mappings only and returns a `dict` or a `str`; no public function accepts a URL, credential, filesystem path, output path, clock or network client.

  Validation is fail-closed: every authority and side-effect counter must be zero/false; the frozen identity and definition hash must match; all current blocker states must match the frozen requirement states; missingness coercion, implicit trial admission, synthetic settlement, provider selection and background collection raise named `ValueError`s. Evaluation returns the current decision plus ordered blockers, plain-language Russian explanation, explicitly allowed next boundary and non-claims. The renderer must be a deterministic function with no clock, filesystem write or network call.

- [ ] **Step 6: Run the focused test until green.**

  Run the Task 1 command again. It must pass every adversarial case and not add a test skip.

## Task 2: Expose the same decision to the owner without a new control plane

**Files:**
- Modify: `tests/test_task30_h07_h01_owner_visible_vertical_slice.py`
- Create: `scripts/show_task30_h07_h01_owner_readout.py`
- Create: `docs/reports/task30/h07_h01_owner_readout_v1.md`

- [ ] **Step 1: Add failing CLI/report tests first.**

  Add a `subprocess.run` test which invokes:

  ```powershell
  uv run --locked --managed-python python -B scripts/show_task30_h07_h01_owner_readout.py --format json
  uv run --locked --managed-python python -B scripts/show_task30_h07_h01_owner_readout.py --format markdown
  ```

  Assert both exit zero; JSON parses and contains `CAPTURE_REQUIRED`, the two ordered blocker codes, and `EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE`; Markdown contains the short Russian answer, an explicit “не готово к исследовательскому trial” statement, no numeric PnL/NetReturn, and no claim of provider selection. Assert the checked-in report equals the renderer output followed by one newline exactly.

- [ ] **Step 2: Run the tests and record the expected red state.**

  The initial failure must be a missing CLI/report or mismatched generated output, not a skipped test.

- [ ] **Step 3: Implement a read-only CLI.**

  The script loads only the two tracked YAML files, calls the three public functions, and writes exactly one selected format to stdout. Accept no credentials, URLs, provider names, scheduling flags or arbitrary output paths. It must not create any file and must exit nonzero for an unsupported `--format`.

- [ ] **Step 4: Generate the tracked owner report once.**

  Render Markdown through the implemented function and save the exact output to `docs/reports/task30/h07_h01_owner_readout_v1.md`. The report starts with `# TASK-30 — H07/H01: что нужно дальше`, then gives the simple decision, missing evidence, what does not follow from the current data, and the one next boundary. It does not include future speculative backlog or implementation detail.

- [ ] **Step 5: Run focused test and direct CLI checks.**

  Verify both output formats and `git diff --check`. Confirm no raw data, secret, provider URL, or generated bytecode became tracked.

## Task 3: Bind the result as evidence and run delivery-grade validation

**Files:**
- Modify: `tests/test_task30_h07_h01_owner_visible_vertical_slice.py`
- Create: `docs/evidence/task30/a7_h07_h01_owner_visible_vertical_slice_acceptance_v1.json`

- [ ] **Step 1: Add a failing receipt-integrity test.**

  Test that the acceptance receipt has the expected schema, atom ID, current decision, zero side effects, and actual SHA-256 values for the task doc, contract, config, module, script, report and test. Separately assert its input evidence bindings equal the existing receipt paths and hashes. Reject a changed bound SHA, `task30_acceptance: true`, a nonzero provider call, or `state_change` other than `NONE`.

- [ ] **Step 2: Run the receipt test and record expected red state.**

  Expected before the receipt exists: explicit missing acceptance artifact failure.

- [ ] **Step 3: Create the acceptance receipt.**

  Its decision must be `CAPTURE_REQUIRED`, `state_change` must be `NONE`, `task30_trial_or_acceptance_actions` must be zero, and `project_sources_disposition` must be `NO_CHANGE`. Include `FACTORY_FIT_REVIEW: FULL_REVIEW` with a short review covering mission, research truth, owner operability, efficiency, flexibility, execution-to-cashflow non-claim, monitoring/recovery, and reuse/build decision `BUILD_MINIMAL_PURE_EVALUATOR`.

- [ ] **Step 4: Run the complete local evidence set.**

  Run, in order:

  ```powershell
  uv run --locked --managed-python python -B tests/test_task30_h07_h01_owner_visible_vertical_slice.py
  uv run --locked --managed-python python -B tests/test_task28_rc001_registry_freeze.py
  uv run --locked --managed-python python -B scripts/validate_catalog.py
  uv run --locked --managed-python python -B scripts/validate_baton.py
  ```

  Run `uv run --locked --managed-python python -B scripts/validate_ci.py` only as topology diagnostic on the task branch; document the expected `branch_main_or_ci_detached` policy stop if it is the sole failure. Do not change the validator to accommodate a feature branch.

- [ ] **Step 5: Deliver the bounded implementation.**

  Inspect status and diff, run `git diff --check`, commit the atom, push non-force, and let the pull-request workflow execute the full attached-main gate. After green CI, run the repository’s tracked-only delivery preflight for the exact committed candidate. Keep the pull request draft and stop before merging; routine merge remains covered by the standing Work/Codex autonomy only after validation read-back.

## Completion Criteria

- One offline deterministic readout reports only the current evidence state and `CAPTURE_REQUIRED`.
- A misleading promotion from sparse price/quote evidence to trial, settlement, zero/no-trade, provider authority, or background collection is rejected by automated tests.
- The exact frozen H07/H01 definition and the three prior receipts are hash-bound.
- The owner can read the result from one short tracked Markdown report or invoke one CLI command; no new UI, service, dependency, or scheduler exists.
- Full PR CI and tracked-only delivery validation pass on the exact candidate. The parent TASK-30 remains open, `STATE_CHANGE=NONE`, and no Project Source update is requested.
