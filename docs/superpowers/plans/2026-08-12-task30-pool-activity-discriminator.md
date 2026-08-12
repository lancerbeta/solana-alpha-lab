# TASK-30 A16 Pool-Activity Discriminator Implementation Plan

> **For Codex:** Execute this plan as one bounded offline CHAIN. Stop before the
> external owner gate.

**Goal:** Produce a fail-closed offline packet that can classify one future
exact-pool `getSignaturesForAddress` response against the frozen A15P window.

**Architecture:** A closed YAML policy and JSON Schema freeze identity,
authority, request and time boundaries. A pure Python module validates the
policy, builds the secret-free JSON-RPC body and classifies synthetic response
objects. Acceptance and FULL Factory Fit are hash-bound and Catalog-discoverable.

**Tech stack:** Python 3.11+, PyYAML, jsonschema in tests, unittest, existing
Catalog/navigation validators.

---

### Task 1: Freeze the contract and make the test fail

**Files:**
- Create: `docs/contracts/task30_pool_activity_discriminator_contract_v1.md`
- Create: `configs/task30_pool_activity_discriminator_v1.yaml`
- Create: `catalog/schemas/task30_pool_activity_discriminator.schema.json`
- Create: `tests/fixtures/task30/pool_activity_discriminator_v1.json`
- Create: `tests/test_task30_pool_activity_discriminator.py`

- [ ] Encode exact pool, A15P timestamps/floors, one-request proposal, zero
  current authority and exact future owner phrase.
- [ ] Encode closed response and mutation fixtures for positive, exhausted,
  bracketing, boundary, null, truncated, malformed, error and ordering cases.
- [ ] Assert policy/schema closure, secret-safe request body and all truth states.
- [ ] Run the targeted test and record the expected import failure before the
  production module exists.

### Task 2: Implement the smallest pure classifier

**Files:**
- Create: `src/solana_alpha_lab/task30_pool_activity_discriminator.py`
- Modify: `tests/test_task30_pool_activity_discriminator.py`

- [ ] Implement type-strict policy validation with exact field sets.
- [ ] Implement a deterministic request-body builder with no URL or credential.
- [ ] Implement response validation and conservative classification.
- [ ] Reject bool/int confusion, extra fields, duplicates and ordering drift.
- [ ] Run targeted tests until green.

### Task 3: Bind acceptance and Factory Fit

**Files:**
- Create: `docs/evidence/task30/a16_pool_activity_discriminator_acceptance_v1.json`
- Create: `docs/evidence/task30/a16_pool_activity_discriminator_factory_fit_v1.json`
- Modify: `tests/test_task30_pool_activity_discriminator.py`
- Modify: `catalog/assets/core.yaml`
- Modify generated Catalog/navigation consumers only through their generator.

- [ ] Bind all stable artifacts by exact SHA-256.
- [ ] Register contract, config, schema, fixture, module, test and evidence.
- [ ] Record `STATE_CHANGE=NONE`, `NO_CHANGE` Sources and zero external authority.
- [ ] Complete FULL Factory Fit and Product Horizon Radar.
- [ ] Run targeted, Catalog, generated and diff checks.

### Task 4: Independent review and delivery

- [ ] Obtain independent code/contract review; repair only actionable findings.
- [ ] Run repository-policy delivery gate in a tracked-only exact candidate.
- [ ] Commit ordinary bounded changes, non-force push, create one PR and verify CI
  on the exact head.
- [ ] If the machine owner-attention gate permits ordinary merge, merge and verify
  main; otherwise stop for the exact PR decision.
- [ ] Do not call Helius. Return the exact future owner phrase as the only material
  next action.
