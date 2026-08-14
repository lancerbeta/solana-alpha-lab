# TASK-30 A23 Helius Bounded Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task.

**Goal:** Reuse the immutable A22 first page and make at most two Helius continuation requests to decide whether the exact frozen batch is complete within explicit page, credit and byte caps.

**Architecture:** Wrap the tested A22 request/validation seam; add one A23 state machine that binds page 0 by SHA-256, hashes opaque cursors, writes create-only continuation pages outside Git, and stops terminally on completeness, budget exhaustion or typed drift. No generic provider abstraction and no second route.

**Tech stack:** Python 3.11+, stdlib HTTP/JSON/hashlib, YAML + JSON Schema, pytest, Delivery Harness.

---

### Task 1: Freeze the A23 contract and observable state machine

**Files:**
- Create: `docs/contracts/task30_a23_helius_bounded_pagination_complete_batch_contract_v1.md`
- Create: `configs/task30_a23_helius_bounded_pagination_complete_batch_v1.yaml`
- Create: `catalog/schemas/task30_a23_helius_bounded_pagination_complete_batch.schema.json`
- Create: `tests/fixtures/task30/helius_bounded_pagination_v1.json`
- Create: `tests/test_task30_a23_helius_bounded_pagination.py`
- Modify: `src/solana_alpha_lab/task30_helius_get_transactions_for_address.py`
- Create: `src/solana_alpha_lab/task30_helius_bounded_pagination.py`

1. Write failing tests for immutable A22 page binding, continuation payload identity, cursor hashing/cycle rejection, strict cross-page ordering and signature uniqueness, 25 MB/page and 50 MB/new-total caps, 100 credits/page and 200 credits/atom caps, early completion, two-call incomplete stop, and no retry/redirect/fallback.
2. Run `uv run --locked --managed-python python -B -m unittest tests.test_task30_a23_helius_bounded_pagination tests.test_task30_a22_helius_get_transactions_for_address` and retain the expected RED cause.
3. Expose only the minimal tested A22 public seam and implement the A23 state machine until the same command is GREEN.

### Task 2: Add the fail-closed runner and offline acceptance

**Files:**
- Create: `scripts/run_task30_a23_helius_bounded_pagination.py`
- Create: `docs/evidence/task30/a23_helius_bounded_pagination_runtime_receipt_v1.json`
- Create: `docs/evidence/task30/a23_helius_bounded_pagination_acceptance_v1.json`
- Create: `docs/reports/task30/a23_helius_bounded_pagination_readout_v1.md`

1. Add runner tests proving one credential-free preflight, exactly one credential read, at most two sequential POSTs, 30-second timeout, redirects disabled, secret-free output and create-only raw storage.
2. Implement preflight and runner; keep the existing API key solely in process memory and endpoint query construction.
3. Run focused A22+A23 tests and secret/static scans. Do not make a provider call during tests.

### Task 3: Execute the one authorized bounded batch and propagate observed evidence

**Files:**
- Create: `configs/provider_route_capability_registry_v6.yaml`
- Create: `catalog/schemas/provider_route_capability_registry_v6.schema.json`
- Create: `src/solana_alpha_lab/provider_route_capability_registry_v6.py`
- Create: `tests/test_provider_route_capability_registry_v6.py`
- Create: `docs/evidence/task30/a23_provider_route_capability_registry_acceptance_v1.json`
- Modify: Catalog, lifecycle, navigation and TASK-30 decision registries only where the observed result requires it.

1. Verify the retained A22 page SHA/count/cursor hash without reading a credential.
2. Run exactly one A23 foreground invocation. It may issue zero, one or two continuation POSTs and must stop early on a null cursor or any typed failure.
3. Record only response byte hashes/counts, cursor hashes, credit upper bounds and terminal classification; never record a credential or raw cursor.
4. Append v6 registry evidence without changing v5 semantics, update Catalog/generated navigation using the repository generator, and keep `TASK-30=BLOCKED_DATA`.

### Task 4: Review and deliver the exact candidate

**Files:**
- Create: `docs/evidence/task30/a23_delivery_completion_evidence_v1.json`
- Create: `docs/evidence/task30/a23_delivery_independent_review_v1.json`
- Create: `docs/evidence/task30/a23_delivery_factory_fit_v1.json`
- Modify: `docs/tasks/TASK-30-a23-helius-bounded-pagination-complete-batch.md`

1. Run code, goal/DoD and architecture review; record `SINGLE_AGENT_REVIEW_FALLBACK` if no isolated reviewer is authorized.
2. Run proportional focused validation, schema/catalog checks, generated-file check, diff/write-set check and secret scan. Do not run the local full gate.
3. Finish through ordinary commit, non-force push, PR and exact-head CI. Stop for the repository-bound exact owner merge phrase; do not claim TASK-30 acceptance.
