---
task_id: DISCOVERY_EVIDENCE_RELEASE_BRIDGE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 2597104aed0fd372ac756af84a497ad7b2705235
  expected_upstream: origin/main
  expected_upstream_oid: 2597104aed0fd372ac756af84a497ad7b2705235
  expected_branch: cursor/discovery-evidence-release-bridge-v1
  dirty_mode: ALLOW_REPORTED
objective: Close the Discovery Evidence Release Bridge so hash-bound Tokens V2 raw
  becomes one typed projection, one compact sealed release, verified RDP import,
  HFIC-visible feature families, and an evidence-epoch change — without a second
  data platform, providers, credentials, or VPS deploy.
managed_write_set:
- docs/tasks/DISCOVERY_EVIDENCE_RELEASE_BRIDGE_V1.md
- src/solana_alpha_lab/factory/tokens_v2_typed_projection.py
- src/solana_alpha_lab/factory/discovery_evidence_release.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- configs/observation_primitive_registry_v1.yaml
- scripts/discovery_evidence_release.py
- scripts/owner_attention_gate.py
- scripts/harness_sync.py
- tests/test_tokens_v2_typed_projection.py
- tests/test_discovery_evidence_release_bridge.py
- tests/test_delivery_harness_merge_guard.py
- tests/test_harness_sync_bindings.py
- docs/evidence/discovery_evidence_release_bridge/a1_delivery_completion_evidence_v1.json
- docs/evidence/discovery_evidence_release_bridge/a1_delivery_independent_review_v1.json
- docs/evidence/discovery_evidence_release_bridge/a1_delivery_factory_fit_v1.json
- docs/evidence/control/delivery_harness_acceptance_v1.json
- docs/evidence/control/a1_merge_readiness_before_owner_phrase_completion_v1.json
- delivery-harness/templates/portable-bundle-manifest.json
- docs/reports/discovery_evidence_release_bridge/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- .agents/skills/delivery-harness/SKILL.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_SECOND_DATA_PLATFORM
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_VPS_OR_DEPLOY_REQUIRED
- STOP_VERTICAL_PROOF_UNREPAIRABLE
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- A2_OR_LATER_SCOPE_CREEP
- WALLET_BUILD_EXECUTE_TRANSACTION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - DELIVERY_EVIDENCE
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
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/discovery_evidence_release_bridge/a1_delivery_completion_evidence_v1.json
    - docs/evidence/discovery_evidence_release_bridge/a1_delivery_independent_review_v1.json
    - docs/evidence/discovery_evidence_release_bridge/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DISCOVERY_EVIDENCE_RELEASE_BRIDGE_V1

## SPEC_ROUTE

`PRD_LITE` — master roadmap
`PRD_SSD_FORGE_EVIDENCE_PLANES_VPS_DISCOVERY_ROADMAP_V2.md` section A1 is the
product authority. This file is the exact frozen task contract on
`main@2597104aed0fd372ac756af84a497ad7b2705235`.

## Decision capsule

- **DECISION_DELTA:** existing rich Tokens V2 bytes and future schedule
  observations become one typed reusable discovery language and one compact
  Forge-visible release path.
- **UNCERTAINTY_REMOVED:** whether Forge evidence can widen without a second
  data pipeline or live provider calls.
- **CAPABILITY_OR_EVIDENCE:** `CAP-DISCOVERY-EVIDENCE-RELEASE-BRIDGE-V1`
- **STOP:** one PR at exact merge gate; zero provider/credential/deployment.
- **NEXT:** A2 on merged main (out of scope here).

## Task Outcome Brief

- **Owner decision:** `OK DISCOVERY_EVIDENCE_RELEASE_BRIDGE_V1.` Implement
  ONLY A1 under `VERTICAL_CAPABILITY_REPAIR_LOOP`.
- **Product outcome:** old hash-bound Tokens V2 raw → one generic typed
  Tokens V2 projection → compact sealed discovery release → verified import
  into temp/canonical-form RDP → HFIC sees structured feature families →
  evidence epoch changes; the same typed projection is what future
  ObservationSchedule will use.
- **Named consumers:** HFIC preflight; historical bind A3; future weekly
  release; future ObservationSchedule search projection; owner evidence
  status.
- **Cheapest falsifier:** zero-network path over the Git
  `DISCOVERY_SEARCH_R0` fixture (roadmap `VAL_R0` alias): typed replay →
  seal → verify → import → HFIC packet shows new feature families and a
  changed evidence epoch; historical role remains discovery-only; no
  confirmation claim; no provider calls.
- **Terminal outcomes:**
  - `DISCOVERY_EVIDENCE_RELEASE_BRIDGE_PASS_READY_FOR_MERGE_GATE`
  - `STOP_VERTICAL_PROOF_UNREPAIRABLE`
  - `STOP_SECOND_DATA_PLATFORM`
- **Non-goals:** A2+, live provider, credentials, VPS, scheduler fairness,
  monitoring, paid plan, quotes, state-transition algorithm, feature
  correlations, ML, Postgres, world model.
- **Evidence budget:** one vertical zero-network proof; repair first real
  bounded blocker in-place; replan instead of expanding into a second data
  platform.
- **Replan trigger:** repeated same blocker; preparatory-only output;
  cheapest falsifier impossible without providers/new platform; evidence
  budget exceeded.

## Required end-state before merge gate

```text
hash-bound Tokens V2 raw
→ one generic typed Tokens V2 projection
→ compact sealed discovery release
→ verified import into temp/canonical-form RDP
→ HFIC sees structured new feature families
→ evidence epoch changes
```

Same projection semantics for future ObservationSchedule search responses.
No fake shared provenance between historical replay and live schedule.

## Architecture preserved

Adopt/wrap existing ObservationPlane + ResearchStore + HFIC preflight.
Do not invent a second collector, second RDP, or second Forge context path.
HFIC current capability enumeration converges onto
`experiment_capability_registry_v2.yaml`; v1 remains the immutable
compatibility predecessor. ObservationSchedule stays v2-only.
