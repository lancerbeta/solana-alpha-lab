---
task_id: DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-06'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: dc44aca566ab141c641700d5cf6e8e8ddcdc77b9
  expected_upstream: origin/main
  expected_upstream_oid: dc44aca566ab141c641700d5cf6e8e8ddcdc77b9
  expected_branch: cursor/delivery-harness-derived-sync-throughput-v1
  dirty_mode: ALLOW_REPORTED
objective: Make Catalog derived-sync HASH_SCOPE follow proof obligation, not registry
  membership, so RECORD_ADD_OR_MOVE and semantic registry delta no longer hash the
  factory while fail-closed check and full recovery stay.
managed_write_set:
- docs/tasks/DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1.md
- docs/design/DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1.md
- docs/design/FACTORY_SPEC_PACKET_V1.md
- scripts/harness_sync.py
- tests/test_harness_sync.py
- docs/agent/DELIVERY_HARNESS_PROTOCOL.md
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/control/a1_derived_sync_throughput_completion_v1.json
- docs/evidence/control/a1_derived_sync_throughput_review_v1.json
- docs/evidence/control/a1_derived_sync_throughput_factory_fit_v1.json
- docs/reports/control/a1_derived_sync_throughput_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- REPLAN_STALE_PIN_SLIP
- REPLAN_OVERHASH_WITH_PLAN
- REPLAN_SECOND_HASH_STORE
- REPLAN_ORACLE_EQUIVALENCE_BROKEN
- REPLAN_CRITIC_COUPLING
- CHECK_MODE_TAKES_APPLY_FLAGS
- OPENSPEC_CLI_OR_TREE
- SECRET_IN_RECEIPTS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/design/DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/control/a1_derived_sync_throughput_completion_v1.json
    - docs/evidence/control/a1_derived_sync_throughput_review_v1.json
    - docs/evidence/control/a1_derived_sync_throughput_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1

Scoreboard is `docs/design/DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1.md` L1+L2.
Do not edit that L2 to declare victory. `FACTORY_SPEC_PACKET_V1` lands as the
design standard only; this atom does not install OpenSpec or edit the skill.

## SPEC_ROUTE

`BOTH` — design packet is PRD+SSD; this file is the exact Git task contract.

## DECISION_DELTA

HASH_SCOPE follows proof obligation, not registry membership.
`--check --paths-from-staging` uses the same HASH_SCOPE rules against index vs HEAD.
`HARNESS_SYNC_PLAN` is public on stderr before the first `desired_sha256`.

## UNCERTAINTY_REMOVED

Why `mode=INCREMENTAL` still hashed ~all of `core.yaml` on REGISTRY_SEMANTIC;
which over-proof is safe to drop; that `--check` with staged `core.yaml` was
the same O(registry) tax.

## CAPABILITY_OR_EVIDENCE

A.4 unique-path spy on RECORD_ADD_OR_MOVE apply+check; SEMANTIC_NAV sibling;
existing-path justifying case; plan line on stderr; scoped CI drift message
with class token `RECORD_ADD_OR_MOVE`. Full `--check` remains the unscoped
fail-closed backstop.

## NON-GOALS

No Catalog shard; no hash cache/DB; no critic-gated sync; no skill rewrite;
no OpenSpec CLI; no merge-gate change; no alpha/science claim.

## CHEAPEST FALSIFIER

Fixture ≥200 sha256 members. One new record on one new file.

`--apply --base-ref <fixture-base>` and `--check --paths-from-staging` (registry
only staged) must: `class=RECORD_ADD_OR_MOVE`; unique `desired_sha256` paths
equal HASH_SCOPE (`affected ∪ NAV_OUTPUTS`, ≤8); path outside HASH_SCOPE is
fail; stale pin on the new record still fail-closed/repaired.

Special-casing only “new path”, or hashing neighbors while printing a cheap
plan, is `REPLAN_OVERHASH_WITH_PLAN`.

## DONE

`DERIVED_SYNC_THROUGHPUT_PASS` when A.4 kills, t1/t5b/t13/t14 still hold in
spirit, isolated critics PASS, Factory Fit, and exact-head CI/harness evidence
are complete.

## STOP

Do not thaw unrelated harness freeze items (owner-attention gate, bind-evidence
inventory, critic launch). Do not lift `CHECK_MODE_REJECTS_APPLY_FLAGS`.
