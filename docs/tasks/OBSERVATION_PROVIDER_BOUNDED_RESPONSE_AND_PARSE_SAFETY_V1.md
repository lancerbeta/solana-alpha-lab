---
task_id: OBSERVATION_PROVIDER_BOUNDED_RESPONSE_AND_PARSE_SAFETY_V1
task_version: "1.0"
status: READY
as_of: "2026-09-04"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 85e8dd6d9c8f3029db07bac5fce37d424ad996cf
  expected_upstream: origin/main
  expected_upstream_oid: 85e8dd6d9c8f3029db07bac5fce37d424ad996cf
  expected_branch: cursor/observation-provider-bounded-response-parse-safety-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Make the Jupiter ObservationSchedule transport memory-bounded and lease-safe
  even when a provider returns an unexpectedly huge, endless/chunked, or
  CPU-expensive JSON response. Close the GIL/large-body failure class that
  defeated OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_V1 in live
  commissioning. No VPS deploy and no live provider calls in this atom.

managed_write_set:
  - docs/tasks/OBSERVATION_PROVIDER_BOUNDED_RESPONSE_AND_PARSE_SAFETY_V1.md
  - src/solana_alpha_lab/factory/observation_provider_bounded_response.py
  - src/solana_alpha_lab/factory/observation_schedule_runtime.py
  - src/solana_alpha_lab/factory/observation_primitives.py
  - src/solana_alpha_lab/factory/observation_provider_wall_deadline.py
  - configs/observation_primitive_registry_v1.yaml
  - tests/test_observation_provider_bounded_response_and_parse_safety_v1.py
  - configs/ci_test_shards_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/observation_provider_bounded_response_and_parse_safety_v1/a1_owner_readout_v1.md
  - docs/evidence/observation_provider_bounded_response_and_parse_safety_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/observation_provider_bounded_response_and_parse_safety_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/observation_provider_bounded_response_and_parse_safety_v1/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - FAILURE_CLASS_NOT_MECHANICALLY_REPRESENTABLE
  - EQUIVALENT_CAPABILITY_ALREADY_EXISTS
  - PROVIDER_ROUTE_OR_CREDENTIAL_CHANGE_REQUIRED
  - RETRY_OR_FALLBACK_AUTHORITY_WIDENING
  - SCIENTIFIC_ESTIMAND_OR_SAMPLING_CHANGE_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - DEPLOYMENT_OR_VPS_ACTION_REQUIRED
  - SECOND_ARCHITECTURE_PIVOT
  - REPEATED_MATERIAL_BLOCKER
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - LEASE_SECONDS_INCREASE_AS_THE_REPAIR
  - NEW_SERVICE_DAEMON_OR_PLATFORM

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/observation_provider_wall_deadline.py
      - src/solana_alpha_lab/factory/observation_schedule_runtime.py
    DELIVERY_EVIDENCE:
      - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OBSERVATION_PROVIDER_BOUNDED_RESPONSE_AND_PARSE_SAFETY_V1

## Decision delta

Can an adversarial or unexpected Jupiter body (huge, chunked/endless, or
CPU/GIL-expensive JSON) starve the ObservationSchedule tick through the 120s
lease envelope even after the V1 thread wall-deadline, and can a bounded
read + bounded parse close that class without retries, lease-TTL increase,
or a new service?

## Binding

- Base: `85e8dd6d9c8f3029db07bac5fce37d424ad996cf` (post-#256 main)
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `BOTH`
- Live VPS deploy remains a separate owner gate
- Predecessor live miss: wall watchdog is thread-based; `time.sleep` synthetic
  stall releases the GIL and did not represent CPU/GIL/large-body starvation.

## Owner decision

Repair production `JupiterReadonlyOpener` so it never unbounded-`read()`s
provider input; enforce an explicit byte budget from official recent-feed
semantics plus existing same-family 2 MiB transport caps; map oversize,
malformed JSON, wall timeout and transport error to typed missingness; keep
STARTED fail-closed for interrupted process/restart.

## Named consumer

ObservationSchedule production tick / RDP append-only truth: a bounded
provider miss must complete the call ledger and release the lease so
source-poll can progress.

## Cheapest falsifier

Zero-network, before repair design:

1. streaming/large HTTP-like body that makes unbounded `read()` grow materially;
2. CPU/GIL-heavy processing showing the thread wall watchdog is not a hard
   deadline;
3. current production-shaped opener violating the intended wall/lease envelope.

If the live class cannot be represented, STOP.

## Terminal

`OBSERVATION_PROVIDER_BOUNDED_RESPONSE_AND_PARSE_SAFETY_PASS`

## Non-claims

No VPS deploy/commissioning, no live provider calls, no provider
forever-compat, no alpha/cashflow, no systemd cadence retune, no historical
evidence rewrite, no LEASE_SECONDS increase as the repair.

## Replan trigger

Repeated blocker, preparatory-only output, cheapest falsifier impossible,
second provider/route pivot, or evidence/time budget breach.
