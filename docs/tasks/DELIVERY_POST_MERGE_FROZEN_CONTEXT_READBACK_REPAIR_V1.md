---
task_id: DELIVERY_POST_MERGE_FROZEN_CONTEXT_READBACK_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-10-02'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, ARCHITECTURE_CRITIC, GOAL_DOD_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 92e0143d2e8cacf39b9b74cad49b2d3c00f70055
  expected_upstream: origin/main
  expected_upstream_oid: 92e0143d2e8cacf39b9b74cad49b2d3c00f70055
  expected_branch: codex/delivery-post-merge-frozen-context-readback-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Verify frozen task delivery context from immutable approved Git objects
  separately from immediate exact merge topology and push CI, preserving all
  strict pre-merge freshness, scope and merge authority checks.
managed_write_set:
  - scripts/owner_attention_gate.py
  - delivery-harness/templates/portable-bundle-manifest.json
  - tests/test_delivery_harness_merge_guard.py
  - tests/test_delivery_harness_executor_extension.py
  - tests/test_delivery_post_merge_frozen_context_v1.py
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - docs/tasks/DELIVERY_POST_MERGE_FROZEN_CONTEXT_READBACK_REPAIR_V1.md
  - docs/evidence/control/delivery_post_merge_frozen_context_readback_repair_v1/**
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/evidence/control/owner_attention_gate_acceptance_v1.json
  - docs/evidence/control/delivery_harness_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PRODUCT_OR_SCIENCE_CHANGE
  - REAL_DATA_PLANE_MUTATION
  - C4_ACCESS_OR_IMPORT
  - FORGE_RUN
  - CONTEXT_RECEIPT_REDESIGN
  - HISTORICAL_POST_MERGE_CLOSURE
  - PRE_MERGE_FRESHNESS_OR_AUTHORITY_WEAKENING
  - MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [SCRIPT-OWNER-ATTENTION-GATE-001, PROTOCOL-DELIVERY-HARNESS-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - scripts/delivery_harness.py
      - control/owner_attention_gate_v2.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/control/delivery_post_merge_frozen_context_readback_repair_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/control/delivery_post_merge_frozen_context_readback_repair_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/control/delivery_post_merge_frozen_context_readback_repair_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DELIVERY_POST_MERGE_FROZEN_CONTEXT_READBACK_REPAIR_V1

ENTRY_DECISION: START_AS_WRITTEN. MODEL_EFFORT: SOL_XHIGH.
SPEC_ROUTE: DESIGN_SPEC (contained here). Factory Fit: FULL_REVIEW.
Reuse: WRAP existing strict context builder and frozen base policy/profile,
Git immutable objects and existing post-merge topology/CI checks. No new
dependency, plugin, connector, MCP or automation. The gate script is the
portable bundle's source owner; there is no separate authoritative code copy.

## Outcome and bounds

- DECISION_DELTA: immediate post-merge closure proves frozen A/H independently
  from current M; it cannot require current origin/main to remain A.
- UNCERTAINTY_REMOVED: whether a valid ordinary merge can receive its canonical
  terminal receipt after the upstream advances to that exact merge.
- CAPABILITY_OR_EVIDENCE: immutable frozen-context replay, real scratch Git DAG
  regression and fail-closed negatives without relaxing pre-merge checks.
- Consumer: canonical --post-merge-readback for task-contract delivery receipts.
- Cheapest falsifier: A/H/M with ordered parents [A,H] and origin/main=M;
  generic pre-merge rebuild fails while canonical post-merge verification passes.
- STOP: exact-head CI PASS plus ready_for_owner_phrase=true; no merge.
- NEXT: LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2 after merge.
- REPLAN_TRIGGER: receipt redesign, historical closure, weakened freshness,
  arbitrary ancestor acceptance or product/scientific scope needed.
- Evidence budget: focused merge-guard and production-shaped scratch DAG tests,
  three isolated review roles, existing exact-head CI. No local full gate.
- Owner UX review is not required: CLI, receipt schema and terminal authority
  remain unchanged; only the invalid lifecycle binding is repaired.
- Product Horizon / Capability Radar NOW: NONE.

## Frozen delivery proof

Preserve verify_live_context_receipt and validate_task_git_binding for all
pre-merge actions. For task receipts, replay the existing context builder in a
private tracked-byte snapshot of H with frozen upstream A, without changing
the elected repository's checkout, refs, index or configuration. Compare the
entire canonical receipt, including task path/hash, selected refs/roles/hashes,
base/write set, head/tree/branch, budgets and gaps. Reuse base-bound scope and
policy/profile checks in that same immutable snapshot. An approved delivery
receipt must describe a clean committed candidate, not uncommitted bytes.
Reject process Git write-location overrides and command-scope configuration
other than read-only safe.directory ownership allowances. Scratch hooks and
fsmonitor are disabled locally; no process-global environment mutation is
needed. Reject Windows drive-relative/ADS/alias paths before snapshot writes,
then prove destination containment. PR head branch must equal the frozen task
branch, not merely point another preserved branch at the same H.

LIVE_PR_HEAD has no task-contract frozen-base binding; preserve its existing
verification path. Do not extend its identity schema or invent historical
closure as part of this atom.

## Independent immediate reality proof

Preserve repository/PR binding, MERGED state, exact approved head and exact
submission merge, ordered parents [A,H], preserved task branch, current default
branch exactly M, latest successful exact-M push workflow/jobs, and authority
from base A. Never substitute current merge-base HEAD origin/main for A/H.

Required negatives: tampering (including rehashed substitutions), wrong head,
tree, task bytes/base/context selection; reversed/extra merge parents; wrong
repo/PR; deleted branch; missing/failing/wrong-SHA CI; current main != M;
pre-merge stale-base denial. Snapshot construction/recovery must not mutate
the source repository, including its raw index under GIT_INDEX_FILE injection.
Global hooks/fsmonitor and unsafe Git tree paths are negative isolation tests.
No product/science code, real corpus, C4 or Forge.

## Incident provenance

PR #362 approved H=8af67e4f24f8d98b730547a8f35f0e3410961bc8,
A=68b986e12e5752d36b3cc2e14d85a855fa90b09f,
M=92e0143d2e8cacf39b9b74cad49b2d3c00f70055: merge, direct ordered-topology
readback and exact-M push CI succeeded. Its canonical terminal receipt remains
blocked by TASK_EXPECTED_BASE_MISMATCH. No mutation/reopening or fabricated
historical receipt. This confirmed active-delivery blocker permits the narrow
control-plane freeze exception.

Rollback: ordinary Git revert of this atom; preserve all historical receipts.
Preflight found a SEPARATE current-byte evaluator pin in the existing
owner-attention acceptance evidence. Its evaluator SHA is repinned only;
historical verdict, base, tests, limits and semantic acceptance remain intact.
