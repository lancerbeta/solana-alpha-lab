---
task_id: HANDOFF_MANIFEST_V1_1_WORDING_V1
task_version: '1.0'
status: READY
as_of: '2026-09-26'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 0ecc322ac45c1b77c80ae2a33e8d5cce0db472c7
  expected_upstream: origin/main
  expected_upstream_oid: 0ecc322ac45c1b77c80ae2a33e8d5cce0db472c7
  expected_branch: cursor/handoff-manifest-v1-1-wording-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Align science_to_strategy_handoff_v1.md with the shipped freeze:
  a new PROMOTE that includes ExecutionEvidenceBinding freezes
  promotion_handoff_manifest schema_version 1.1. A manifest without that
  binding stays 1.0. Historical 1.0 bytes are not rewritten. Materializing
  a 1.0 manifest remains EXECUTION_EVIDENCE_BINDING_GAP. No code change.

managed_write_set:
  - docs/tasks/HANDOFF_MANIFEST_V1_1_WORDING_V1.md
  - docs/contracts/science_to_strategy_handoff_v1.md
  - tests/test_science_to_strategy_handoff_v1.py
  - docs/reports/handoff_manifest_v1_1_wording/a1_owner_readout_v1.md
  - docs/evidence/handoff_manifest_v1_1_wording/a1_delivery_completion_evidence_v1.json
  - docs/evidence/handoff_manifest_v1_1_wording/a1_delivery_independent_review_v1.json
  - docs/evidence/handoff_manifest_v1_1_wording/a1_delivery_factory_fit_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - PROMOTION_HANDOFF_CODE_CHANGE
  - HISTORICAL_DECISION_EVENT_REWRITE
  - SCIENCE_TO_STRATEGY_TASK_HISTORY_REWRITE
  - HFIC_CLASSIFIER_CHANGE
  - EXPERIMENT_SPEC_SCHEMA_CHANGE

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
      - docs/evidence/handoff_manifest_v1_1_wording/a1_delivery_completion_evidence_v1.json
      - docs/evidence/handoff_manifest_v1_1_wording/a1_delivery_independent_review_v1.json
      - docs/evidence/handoff_manifest_v1_1_wording/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HANDOFF_MANIFEST_V1_1_WORDING_V1

SPEC_ROUTE=PRD_LITE. FACTORY_FIT=FAST_PATH. MODEL_EFFORT=`LUNA_MAX`.
Route `DIRECT_CURSOR_DELIVERY`. Base `0ecc322ac45c1b77c80ae2a33e8d5cce0db472c7`.

`freeze_promotion_handoff_manifest` already writes schema_version `1.1` when
the caller supplies an ExecutionEvidenceBinding, and `1.0` when it does not.
The human contract still said every new PROMOTE freezes `1.0`.

`docs/tasks/SCIENCE_TO_STRATEGY_HANDOFF_V1.md` stays the history of that
earlier atom. `src/` is not in this write set.

The task21 core.yaml pin is in the write set because registering catalog
assets changes `catalog/assets/core.yaml`. Only that pin's bytes and sha256
move.

## Task Outcome Brief

- **Owner decision:** the contract names the manifest version the freeze already writes.
- **Named consumer:** an agent reading `science_to_strategy_handoff_v1.md` before PROMOTE.
- **Cheapest falsifier:** `test_handoff_contract_names_manifest_1_1_when_binding_is_present`.
- **Non-goals:** promotion code, classifier code, historical decision events, experiment spec schema.
- **Evidence budget:** the contract file and one reader test. No provider or wallet.

## Decision capsule

- `DECISION_DELTA`: контракт называет ту же версию manifest, которую уже пишет freeze.
- `UNCERTAINTY_REMOVED`: агент больше не ждёт тихий 1.0 у нового PROMOTE с binding.
- `CAPABILITY_OR_EVIDENCE`: одна согласованная фраза и тест, который её держит.
- `STOP`: зелёный CI и ready_for_owner_phrase. Merge не входит в атом.
- `NEXT`: нет. Очередь этого треда после merge пуста.
- `REPLAN_TRIGGER`: the sentence cannot be aligned without editing `promotion_handoff.py`, rewriting historical decision bytes, or changing the HFIC classifier.
