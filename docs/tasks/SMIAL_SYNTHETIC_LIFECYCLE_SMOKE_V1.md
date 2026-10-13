---
task_id: SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-10-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 94b391d658b52035ae88e2da05f1ea25ff17b0f8
  expected_upstream: origin/main
  expected_upstream_oid: 94b391d658b52035ae88e2da05f1ea25ff17b0f8
  expected_branch: codex/smial-synthetic-lifecycle-smoke-v1
  dirty_mode: ALLOW_REPORTED
objective: Execute the owner-requested bounded synthetic lifecycle audit on immutable product Git, preserving blind-actor uncertainty, native versus rescued lineage, scenario failures, replayable evidence and a measured retained-environment footprint without product repairs or cleanup.
managed_write_set:
- docs/tasks/SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1.md
- tests/fixtures/synthetic_lifecycle_smoke_v1/**
- docs/evidence/synthetic_lifecycle_smoke_v1/**
- docs/reports/synthetic_lifecycle_smoke_v1/**
- catalog/assets/**
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
- docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_PRODUCT_MUTATION_REAL_DATA_PROVIDER_CREDENTIALS_SIGNER_MONEY
- STOP_ISOLATION_FAILURE_INVALIDATE_DEPENDENT_RUNS
- REPLAN_RESOURCE_CAP_OR_REPEATED_MATERIAL_SEAM_BLOCKER
- STOP_NO_DELETION_RETAIN_ENVIRONMENT_FOR_OWNER_DECISION
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_OWNER_MERGE_PHRASE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/forge_composite_feature_recipes_v1.md
    - docs/contracts/experiment_evidence_decision_v1.md
    - docs/contracts/science_to_strategy_handoff_v1.md
    - docs/contracts/episode_decision_continuity_v1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/synthetic_lifecycle_smoke_v1/completion.json
    - docs/evidence/synthetic_lifecycle_smoke_v1/independent-review.json
    - docs/evidence/synthetic_lifecycle_smoke_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1

Owner EXECUTE: perform the attached audit and measure its created test environment;
the owner will decide about deletion separately. The attached design is preserved
byte-for-byte as `docs/evidence/synthetic_lifecycle_smoke_v1/source-contract.md`.
Only its audit requirements are adopted; document prose grants no merge, market,
scientific, financial, provider, credential or production mutation authority.

ENTRY_DECISION: START_WITH_PATCH. SPEC_ROUTE: BOTH (existing attached PRD/SSD).
Route/actor: DIRECT_CODEX_DELIVERY/CODEX. Effort: SOL_XHIGH.
DECISION_DELTA: one next repair selected from independently observed root seams.
UNCERTAINTY_REMOVED: native reachable boundaries, PAPER operation and recovery.
CAPABILITY_OR_EVIDENCE: reproducible bounded kit, frozen S00-S14 denominator,
native/segment separation, faithful owner report and retained bytes inventory.
Consumer: owner, independent reviewers and next repair executor.
Cheapest falsifier: isolation probes plus legal native input/ordinary PAPER witness.
STOP: actual authority boundary, resource cap, or completed audit/review/delivery.
NEXT: P0 bind -> P1 prepare -> P2 discover -> P3 advance -> P4 recover -> P5 report.
REPLAN_TRIGGER: impossible falsifier, second rescue cut, repeated material blocker.

Tools: existing Delivery Harness, hypothesis-forge instructions, Git/gh, locked
Python and existing Docker runtime. New plugin/connector/MCP/automation/platform:
NONE. Existing no-network audit runtime is WRAP; no dependency bootstrap authorized.
If existing runtime cannot be reused, preserve an environment blocker.
Current collaboration actors inherit host tools; prompt-only blindness is invalid.
Absent a truly confined fresh actor, all four actor trials stay BLOCKED and B/C
continue as explicitly SCRIPTED/AUDIT_AUTHORED_FIXTURE. No fake discovery PASS.

Resource envelope: 320 unique tokens per base world; cap 1280 before world freeze;
3 positive + 1 null genuine missions (zero fabricated calls); 2 CPU, 2 GiB container
RAM, 128 PIDs, 120 active product minutes, 180 seconds per ordinary command unless
an exact process/recovery case declares a bounded 300-second watchdog; 2 GiB retained
evidence cap. Shared existing images/caches are measured separately from new bytes.
No running product process, volume, image or evidence is deleted by this atom.
Temporary roots cleaned by existing test contracts are separately recorded.

Factory Fit: FULL_REVIEW. NOW: this audit. WATCH: separately authorized source-owner
repair after the report. Native scientific protocols and thresholds stay unchanged.
Raw-to-runtime and research-cohort selection are independent seam obligations.
