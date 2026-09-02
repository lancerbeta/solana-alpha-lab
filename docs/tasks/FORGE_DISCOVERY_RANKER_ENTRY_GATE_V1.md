---
task_id: FORGE_DISCOVERY_RANKER_ENTRY_GATE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-02'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: ebb4c726c322ea7da1534af2506a610f889a0014
  expected_upstream: origin/main
  expected_upstream_oid: ebb4c726c322ea7da1534af2506a610f889a0014
  expected_branch: cursor/forge-discovery-ranker-entry-gate-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Determine with bounded repository and existing research-memory evidence
  whether ARCH-INTENT-006 activation is now genuinely proven for a bounded
  discovery-generator upgrade; persist one decision-bearing terminal without
  implementing the generator or creating new scientific infrastructure.

managed_write_set:
  - docs/tasks/FORGE_DISCOVERY_RANKER_ENTRY_GATE_V1.md
  - docs/evidence/forge_discovery_ranker_entry_gate/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_discovery_ranker_entry_gate/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_discovery_ranker_entry_gate/a1_delivery_factory_fit_v1.json
  - docs/reports/forge_discovery_ranker_entry_gate/a1_owner_readout_v1.md
  - docs/architecture/intents/ARCH-INTENT-006-hypothesis-discovery-and-opportunity-surface.md
  - catalog/assets/architecture.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - PROVIDER_API_RPC_WSS_REQUIRED
  - EXPERIMENT_EXECUTION_REQUIRED
  - HOLDOUT_ACCESS_REQUIRED
  - AUTONOMOUS_GENERATOR_IMPLEMENTATION
  - NEW_DISCOVERY_PLATFORM
  - OWNER_ATTENTION_SEMANTICS_CHANGE
  - HARNESS_REDESIGN
  - ACTIVATION_CANNOT_BE_PROVEN_FROM_ADMISSIBLE_EVIDENCE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-006-hypothesis-discovery-and-opportunity-surface.md
      - docs/architecture/prospects/hfic_scientific_discovery_prospects_v1.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_discovery_ranker_entry_gate/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_discovery_ranker_entry_gate/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_discovery_ranker_entry_gate/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_DISCOVERY_RANKER_ENTRY_GATE_V1

## Entry / outcome

- `DECISION_DELTA`: whether the project crossed from "manual hypothesis supply still sufficient" to "systematic candidate discovery is a material bottleneck"
- `UNCERTAINTY_REMOVED`: whether a bounded discovery-generator is justified **now**
- `CAPABILITY_OR_EVIDENCE`: one hash-bound activation decision receipt
- `STOP`: terminal + exact-head CI + ordinary merge gate
- `NEXT`: A1 only if terminal is `DISCOVERY_GENERATOR_TRIGGER_PROVEN`

## Trigger evaluation (A0)

Architecture prose triggers from ARCH-INTENT-006 §8 are evaluated independently.
Task enums map interpretively onto that prose; they are not literal strings in the intent.

### Trigger A — hypothesis supply bottleneck

Mapped condition: Factory can execute comparable hypotheses materially faster than
the owner can supply or prioritize high-quality next hypotheses.

| Sub-check | Verdict | Admissible evidence |
|---|---|---|
| Factory V1 operationally ready (stamp) | PASS | `configs/factory_v1_operational_readiness_v1.yaml`; `docs/evidence/factory_v1_readiness_recertification/a1_acceptance_v1.json` (`FACTORY_V1_OPERATIONAL_READY`) |
| Comparable work composes reusable capabilities | WEAK | Readiness freeze prefers composition; recent scientific atoms still add bespoke modules (`EARLY_VALUATION_*`, `EARLY_HOLDER_*`) |
| Owner hypothesis supply/prioritization is the limiting step | FAIL | No Git measurement of Factory cycle time vs owner supply/prioritization. Cannot infer from READY alone. HFIC remains `MANUAL_FALLBACK_UNTIL_GENERATOR`; prior HFIC delivery non-claim `NO_DISCOVERY_RANKER_TRIGGER_PROVEN` |

**Trigger A result:** not proven.

### Trigger B — materially large decision surface

Mapped condition: owner must choose the next hypothesis family from a materially
large currently credible candidate space where unsystematic selection is itself
a bottleneck.

| Sub-check | Verdict | Admissible evidence |
|---|---|---|
| Distinct currently credible directions | WEAK | 23-record advisory portfolio is mostly `NOT_IMPLEMENTED` / blocked / deferred; not a census of currently credible executable candidates |
| Observable/capability availability variation | WEAK-PASS | Factory common market feature surface mixes PIT / reconstructible / forward-only / missing classes |
| Manual Forge prioritization burden measured | FAIL | Design/ops search-budget thresholds exist; no Git proof thresholds were met |
| `OWNER_DISCOVERY_REFRAME` | PRESENT as priority signal only | Owner rebind + EXECUTE of this Entry Gate shows priority; **insufficient alone** per gate contract |

**Trigger B result:** not proven.

## Terminal

```text
DISCOVERY_GENERATOR_TRIGGER_NOT_YET_PROVEN
```

Rationale: Factory readiness stamps satisfy only a precondition of Trigger A.
Neither Trigger A limiting-step nor Trigger B material current decision-surface
pressure is hash-proven from admissible Git/Catalog evidence. Owner reframe alone
does not force PASS. No genuine truth conflict → not `UNRESOLVED`.

## Non-claims

- No generator / ranker / QD / VOI implementation
- No ARCH-INTENT-006 activation to build-now
- No provider / experiment / holdout / deployment / cash spend
- No successor A1 contract instantiation in this atom

## Machine checks required

```text
PROVIDER_CALLS = 0
EXPERIMENT_EXECUTION = 0
HOLDOUT_TOUCHES = 0
GENERATOR_CODE_ADDED = 0
NEW_DB = 0
CURRENT_SEMANTIC_ROOTS_USED = true
HISTORICAL_TASK_STATUS_USED_AS_IMPLEMENTATION_TRUTH = false
ARCH_INTENT_TRIGGER_CRITERIA_EVALUATED = true
OWNER_REFRAME_ALONE_FORCES_PASS = false
```
