---
task_id: DELIVERY_HARNESS_LOCATION_AWARE_INCREMENTAL_SYNC_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-28'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 86b24cb1abe5867becc1ead16efb3754044550df
  expected_upstream: origin/main
  expected_upstream_oid: 86b24cb1abe5867becc1ead16efb3754044550df
  expected_branch: cursor/delivery-harness-location-aware-incremental-sync-v1
  dirty_mode: ALLOW_REPORTED
objective: "Stop false INCREMENTAL_SCOPE_UNPROVEN full rehash when Catalog holds correct sha256 external_bundle|logical_only records without repository_path; keep HASH_SCOPE to locally hashable git_path assets only, preserve external SHA as semantic, fail closed on corrupt location."
managed_write_set:
- docs/tasks/DELIVERY_HARNESS_LOCATION_AWARE_INCREMENTAL_SYNC_V1.md
- scripts/harness_sync.py
- tests/test_harness_sync.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/control/a1_location_aware_incremental_sync_completion_v1.json
- docs/evidence/control/a1_location_aware_incremental_sync_review_v1.json
- docs/evidence/control/a1_location_aware_incremental_sync_factory_fit_v1.json
- docs/evidence/control/a1_location_aware_incremental_sync_benchmark_v1.json
- docs/reports/control/a1_location_aware_incremental_sync_owner_readout_v1.md
required_review_roles:
- CODE_REVIEWER
- GOAL_DOD_CRITIC
- ARCHITECTURE_CRITIC
- OWNER_UX_CRITIC
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- FULL_FALLBACK_FROM_VALID_EXTERNAL_SHA
- EXTERNAL_SHA_TREATED_AS_LOCAL_PIN
- FALSE_NOOP_ON_CORRUPT_LOCATION
- SECOND_HASH_STORE_OR_CACHE
- UNSCOPED_CHECK_CLAIMED_ACCELERATED
- SECRET_IN_RECEIPTS
- PROVIDER_OR_CREDENTIAL_USE
- LIVE_VPS_OR_CAMPAIGN_MUTATION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/control/a1_location_aware_incremental_sync_completion_v1.json
    - docs/evidence/control/a1_location_aware_incremental_sync_review_v1.json
    - docs/evidence/control/a1_location_aware_incremental_sync_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DELIVERY_HARNESS_LOCATION_AWARE_INCREMENTAL_SYNC_V1

`SPEC_ROUTE=NONE` — owner OK plus this exact Git contract; no separate PRD/SSD.

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` once (location/integrity boundary +
fail-closed Catalog semantics). Implementation workhorse remains bounded.

## Decision capsule

- `DECISION_DELTA`: classify `sha256` Catalog records by `location.kind` so
  path index / derived-pin compare cover only `git_path`, while
  `external_bundle|logical_only` SHA stays a primary semantic field and never
  forces false `INCREMENTAL_SCOPE_UNPROVEN`.
- `UNCERTAINTY_REMOVED`: whether correct no-path external SHA records alone
  explain measured full rehash on routine `--apply --base-ref`.
- `CAPABILITY_OR_EVIDENCE`: location-aware incremental apply/check; CLI fixture
  with spy + plan + counters; one real-repo timing receipt vs historical 20.3m.
- `STOP`: after exact-head CI and merge-readiness; before owner merge phrase.
- `NEXT`: none from this atom; unscoped `--check` remains full backstop.

## Confirmed trigger (pre-fix main)

On `origin/main` `86b24cb1…`: Catalog has 1684 `sha256+git_path`, plus
10 valid `sha256` without `repository_path` (2 `external_bundle`, 8
`logical_only`). `collect_asset_records()` hashes only `git_path`.
`_registry_path_index()` required a path for every `sha256` record →
`INCREMENTAL_SCOPE_UNPROVEN` → full fallback.

## Required semantics

| kind | local rehash | path required | strip SHA in semantic projection |
| --- | --- | --- | --- |
| `sha256` + `git_path` | yes | yes | yes (derived pin) |
| `sha256` + `external_bundle\|logical_only` | no | no | no (primary SHA) |
| missing path on `git_path`, unknown location, ambiguous structure | fail-closed `INCREMENTAL_SCOPE_UNPROVEN` | | |

Location-kind change for one asset id remains semantic. Apply and staged
`--check --paths-from-staging` share the same HASH_SCOPE boundary.

## Non-goals

No new DB/cache/threads/deps/Catalog schema; no historical rewrite; no change
to explicit full recovery; no claim that unscoped `--check` or all of CI is
faster; no VPS/provider/credentials/science/retention/campaign/gate edits.

## Cheapest falsifier

Isolated Git fixture: ≥200 `sha256+git_path`, ≥10 correct external/logical
SHA records without path. One local file edit + one new local SHA record +
one external SHA edit. `--apply --base-ref` with `HARNESS_SYNC_SHA256_SPY`
must be `mode=incremental`, `full_fallback=false`, `fallback=none`, and spy
unique paths == changed local paths ∪ NAV_OUTPUTS (if nav). Repeat apply
NOOP. Staged check catches stale local pin narrowly. Corrupt/unknown/kind
flip fail closed. Small-fixture full oracle byte match. Then one real
`--apply --base-ref` timing receipt; if still full or <5× vs historical
conditions, replan instead of DONE.

## DoD

1. Shared classifier used by path index, derived pins, semantic projection,
   HASH_SCOPE construction.
2. End-to-end CLI fixture proof above.
3. Existing incremental/idempotency/LF-CRLF tests still pass.
4. Benchmark receipt records plan/mode/fallback/hashed/desired_sha/elapsed;
   no wall-clock assert in CI.
5. Independent code, goal/DoD, architecture (external SHA not claimed local),
   owner-UX reviews; Factory Fit; bind-evidence; PR; exact-head CI;
   merge-readiness; stop before owner phrase.
