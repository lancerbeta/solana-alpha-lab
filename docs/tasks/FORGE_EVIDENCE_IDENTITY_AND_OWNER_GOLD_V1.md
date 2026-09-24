---
task_id: FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1
task_version: '1.0'
status: READY
as_of: '2026-09-22'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 0b4c933c1f3143b7772fab943f45a8dfec309c0b
  expected_upstream: origin/main
  expected_upstream_oid: 0b4c933c1f3143b7772fab943f45a8dfec309c0b
  expected_branch: cursor/forge-evidence-identity-and-owner-gold-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Shared admission→lifecycle→occupancy→readback vertical: market/capability
  split basis, durable stamps through freeze/Critic/classify/complete, market-
  scoped discovery reuse (no stale REUSED_VALID after C3), scientific slot and
  execution provenance bound to actual representation payload, and owner gold
  over production bindings. A3 remains input owner and A4 remains ladder owner;
  no scientific market Forge, no A6.

managed_write_set:
  - docs/tasks/FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1.md
  - src/solana_alpha_lab/factory/hfic_evidence_identity.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - src/solana_alpha_lab/factory/forge_input_receipt.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/hfic_memory_policy.py
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/fast_lane_snapshot.py
  - schemas/research_memory_projection_v1.sql
  - .github/workflows/ci.yml
  - scripts/validate_ci.py
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - configs/hfic_representation_ladder_v1.yaml
  - catalog/schemas/forge_run_receipt_v1.schema.json
  - catalog/schemas/forge_input_receipt_v1.schema.json
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json
  - catalog/schemas/hypothesis_forge_session_receipt_v1_2.schema.json
  - catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json
  - tests/test_forge_evidence_identity_and_owner_gold_v1.py
  - tests/test_forge_representation_ladder_v1.py
  - tests/test_hfic_preflight.py
  - tests/test_hfic_session.py
  - tests/test_hfic_search_budget_epoch_guard_v1.py
  - tests/test_hfic_operational_memory_quarantine_v1.py
  - tests/test_hfic_epistemic_memory_semantics.py
  - tests/test_hfic_censoring_ignorability_diagnostic_v1.py
  - tests/test_hfic_selection_robustness_gate_v1.py
  - tests/test_hfic_one_frozen_runner_up_failover_v1.py
  - tests/test_forge_input_truth_and_visibility_v1.py
  - tests/test_hfic_reopened_prior_search_routing_v1.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - tests/test_hfic_cli.py
  - tests/test_hfic_critic_prior_memory_closure_v1.py
  - tests/test_hfic_discovery_prospects_and_next_action.py
  - tests/test_hfic_forge_context_and_no_worthy.py
  - tests/test_hfic_fresh_session_version_lock_v1.py
  - tests/test_hfic_manual_grounding_contract_diagnostics_v1.py
  - tests/test_hfic_provenance_clock.py
  - tests/test_hfic_vision_acceptance_operations_v1.py
  - scripts/hypothesis_forge.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/forge_evidence_identity_and_owner_gold/a1_owner_readout_v1.md
  - docs/evidence/forge_evidence_identity_and_owner_gold/a1_no_write_c1_c2_disposition_v1.json
  - docs/evidence/forge_evidence_identity_and_owner_gold/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_evidence_identity_and_owner_gold/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_evidence_identity_and_owner_gold/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - HYPOTHESIS_FORGE_SCIENTIFIC_RUN
  - PROMPT_A_B_C_ON_MARKET_EVIDENCE
  - INDEPENDENT_CRITIC_ON_REAL_HYPOTHESIS
  - STATISTICAL_DIAGNOSTIC_RUN
  - V1_SCIENTIFIC_PROBE_EXECUTION
  - COMMISSIONING
  - HISTORICAL_RECEIPT_REWRITE
  - PROVIDER_CALL
  - VPS_DEPLOY
  - A6_PROGRAM_EXTENSION
  - NEW_SERVICE_QUEUE_DB_FRAMEWORK
  - SCIENTIFIC_QUOTA_EXPANSION
  - FROZEN_V1_PREREGISTRATION_SILENT_REWRITE
  - ABSOLUTE_MACHINE_PATHS_IN_DURABLE_RECEIPT
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - SCRIPT-HYPOTHESIS-FORGE-001
      - MODULE-FACTORY-V1-HFIC-SESSION-001
      - MODULE-FORGE-INPUT-RECEIPT-001
      - MODULE-HFIC-REPRESENTATION-LADDER-001
      - MODULE-HFIC-REPRESENTATION-PROBE-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_preflight.py
      - src/solana_alpha_lab/factory/hfic_session.py
      - src/solana_alpha_lab/factory/hfic_representation_ladder.py
      - src/solana_alpha_lab/factory/forge_input_receipt.py
      - docs/contracts/normalized_trajectory_v1_capability_contract.md
      - docs/contracts/normalized_trajectory_representation_probe_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_evidence_identity_and_owner_gold/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_evidence_identity_and_owner_gold/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_evidence_identity_and_owner_gold/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
      - docs/evidence/forge_evidence_identity_and_owner_gold/a1_no_write_c1_c2_disposition_v1.json
      - docs/evidence/forge_representation_ladder/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_input_truth_and_visibility/a1_c1_c2_forge_input_v1.json
---

# FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1

ATOM_ID: `FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1`

Program: fifth atom of `SMIAL_FORGE_OWNER_PATH_CONVERGENCE_V2` (§15/§23),
refined by `SMIAL_A5_FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1_CURSOR.md`.
Depends on landed A4 `FORGE_REPRESENTATION_LADDER_V1` (main
`5f658ad9a7a80a33db51dbd83b5e109e0deac1e8`, PR #328 post-merge readback PASS,
CI run `35588267708` success). Do not implement A6 or a scientific market run.

## Entry confirmation

- Repo: `lancerbeta/solana-alpha-lab`
- Base/main: `5f658ad9a7a80a33db51dbd83b5e109e0deac1e8`
- A4 approved head: `ae657cb127a616e4679c597d965f2e0a29e4afbb`
- A4 post-merge receipt: `receipt_sha256=8ad987839d0ee5853371bf099ed97a22b1b4beeb0db816bf589f6aa69ef049c8`
- Active time gates: none due (TASK21 dormant)
- Route: `DIRECT_CURSOR_DELIVERY`
- MODEL_EFFORT: `SOL_XHIGH`

## Task Outcome Brief

- **Owner decision:** after publish/import → readback → `/hypothesis-forge`,
  the result matches the declared input; restart resumes; Git-only change does
  not reset budget; a new cohort does not inherit a stale verdict.
- **Product outcome:** split `market_evidence_epoch_sha256` /
  `capability_epoch_sha256`, scientific slot vs execution binding, one shared
  admission/budget decision, legacy read-only bridge, and sequential owner gold
  G1–G12 on production bindings (synthetic sources/generator replies only).
- **Named consumers:** Пётр; normal slash-agent; A3 input; A4 ladder; HFIC
  preflight/freeze/session; V1 adapter; later separately authorized science.
- **Cheapest falsifiers:** docs-only Git change frees a scientific slot; C3
  returns C1+C2 terminal as current answer; BASE→V1 progress mutates frozen run
  identity; interruption mints a new draft instead of resume.
- **Terminal:** whole-path gold + no-write C1/C2 disposition + reviews +
  exact-head CI + merge-readiness. STOP before new A5 owner phrase.
- **Non-goals:** market Prompt A/B/C; real Critic; statistical diagnostic;
  historical rewrite; provider/VPS; A6; scientific quota expansion; new
  service/queue/DB/framework; silent frozen V1 rewrite.

## Decision capsule

- `DECISION_DELTA`: combined legacy `evidence_epoch_sha256` is no longer the
  sole scientific admission key; market and capability split; budgets follow
  durable market stamps across lifecycle phases; discovery reuse requires
  current-market applicability; scientific slot/execution binding carry actual
  representation payload provenance.
- `UNCERTAINTY_REMOVED`: when reuse/resume/new trial is allowed for the same
  owner focus and visible cohort IDs; occupied slots survive Critic/classify;
  C3 does not inherit stale PASS as current answer.
- `CAPABILITY_OR_EVIDENCE`: shared identity/admission helper + versioned
  receipts/projections + G1–G12 gold family + no-write disposition receipt.
- `STOP`: merge-readiness; no scientific slash; no merge without the
  machine-rendered A5 owner phrase.
- `NEXT`: after A5 merge/readback, separately authorized normal
  `/hypothesis-forge` on current evidence.
- `SPEC_ROUTE`: `DESIGN_SPEC`.
- `REPLAN_TRIGGER`: frozen V1 comparative path needs scientific amendment
  beyond budget; second competing admission engine; provider/science quota
  change; cheapest falsifier cannot run.

## Architecture (minimal)

One focused shared helper
`src/solana_alpha_lab/factory/hfic_evidence_identity.py` (or existing owner if
proven sufficient) owns:

| Concept | Basis | Behavior |
|---|---|---|
| Market epoch | A3-selected decision-bearing datasets/lineage | Immutable snapshot of what the market input is |
| Capability epoch | Prompt/schema/representation/capability semantics | Protocol identity; not automatic budget reset |
| Scientific slot | market + representation@version + normalized focus | Occupancy key for the active representation; AUTO/focus budgets remain market-scoped without multiplying quota by child sessions |
| Execution binding | slot + capability + actual representation payload + memory + model | Provenance of what ran; unknown fields stay UNKNOWN — not readiness receipt hash |
| Run/checkpoint | frozen admission + stage artifact refs | Resume updates checkpoint, not admission |

A3 remains input/vision owner. A4 remains ladder/run receipt owner. HFIC remains
freeze/finalize owner. Preflight, forge-run discovery, freeze lookup, and budget
readout must share one admission decision. Legacy `evidence_epoch_sha256`
remains readable without mass RDP migration; each legacy result gets an explicit
disposition (compatible / historical-only / unresolved).

Do not invent a parallel hashing engine over raw corpus bytes. Reuse validated
manifest/fingerprint contracts. Do not expand AUTO=1 / distinct-focus=3 quotas.

## Acceptance (owner gold)

Disposable fixture world; two linked worktrees; synthetic C1/C2/C3 sources and
generator/Critic replies; production import/preflight/packet/ladder/freeze/
classifier/finalize/discovery/persistence/readout. No forced CONTROL helper as
primary acceptance; no `stages=`/`owner_final` injection; no post-build parent
rewrite.

Required scenarios G1–G12 per owner design (import, normal entry, BASE→V1
candidate and negative, completed replay, interruption resume, Git/docs change,
C3 after completed run, legacy ordinary + new evidence, tamper, future Vn/model,
concurrent/snapshot). Two exact negative controls before delivery story:
(a) stale accepted result on new current input; (b) epoch/hash drift from own
scientific artifacts.

## No-write C1/C2 Entry disposition (required before large refactor)

Canonical local RDP only: metadata/artifact readback; no generator, Critic,
new session, import, or science reinterpretation. Emit compact table of relevant
sessions (legacy key, frozen scope, terminal, disposition, slot occupancy, next)
and first-run preflight on real corpus (`visible` / planned used, effective mode,
selected slot or allowed new run, unresolved reasons). Confirm inventory
unchanged. Do not treat old CONTROL as compatible by name alone.

## Safety / rollback / authority

Rollback = ordinary Git revert of versioned code/registration; do not delete
append-only receipts. Merge requires a new exact A5 owner phrase for the final
head. Scientific market run remains a separate owner authorization after A5
post-merge readback.
