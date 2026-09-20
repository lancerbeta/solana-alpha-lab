---
task_id: FORGE_REPRESENTATION_LADDER_V1
task_version: '1.0'
status: READY
as_of: '2026-09-20'
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
  expected_base: dd4224d5a604d92148bd9421fb994d017a0616ab
  expected_upstream: origin/main
  expected_upstream_oid: dd4224d5a604d92148bd9421fb994d017a0616ab
  expected_branch: cursor/forge-representation-ladder-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  One bounded Forge run over existing BASE then eligible ACTIVE representations
  with a deterministic resolver, aggregate run receipt/readout, idempotent
  resume/readback, and E2E fixture routing; A3 remains the only input truth
  owner; no scientific Forge, no A5 identity/gold, no new market epoch.

managed_write_set:
  - docs/tasks/FORGE_REPRESENTATION_LADDER_V1.md
  - configs/hfic_representation_ladder_v1.yaml
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - catalog/schemas/forge_run_receipt_v1.schema.json
  - tests/test_forge_representation_ladder_v1.py
  - tests/test_hfic_provenance_clock.py
  - scripts/hypothesis_forge.py
  - .agents/skills/hypothesis-forge/SKILL.md
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
  - docs/reports/forge_representation_ladder/a1_owner_readout_v1.md
  - docs/evidence/forge_representation_ladder/a1_no_write_vertical_v1.json
  - docs/evidence/forge_representation_ladder/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_representation_ladder/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_representation_ladder/a1_delivery_factory_fit_v1.json
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
  - NEW_MARKET_EPOCH
  - NEW_TRIAL_ON_CANONICAL_RDP
  - A5_IDENTITY_OR_GOLD
  - FROZEN_V1_PREREGISTRATION_CHANGE
  - PROVIDER_CALL
  - VPS_DEPLOY
  - ABSOLUTE_MACHINE_PATHS_IN_DURABLE_RECEIPT
  - GENERIC_WORKFLOW_FRAMEWORK
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
      - MODULE-NORMALIZED-TRAJECTORY-V1-001
      - MODULE-HFIC-REPRESENTATION-PROBE-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_representation_probe.py
      - src/solana_alpha_lab/factory/hfic_control_integrity.py
      - src/solana_alpha_lab/factory/hfic_session.py
      - src/solana_alpha_lab/factory/forge_input_receipt.py
      - docs/contracts/normalized_trajectory_v1_capability_contract.md
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_representation_ladder/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_representation_ladder/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_representation_ladder/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
      - docs/evidence/forge_input_truth_and_visibility/a1_c1_c2_forge_input_v1.json
      - docs/reports/normalized_trajectory_v1_execution_closure/a1_owner_readout_v1.md
---

# FORGE_REPRESENTATION_LADDER_V1

ATOM_ID: `FORGE_REPRESENTATION_LADDER_V1`

Program: fourth atom of `SMIAL_FORGE_OWNER_PATH_CONVERGENCE_V2`. Depends on
landed A3 `FORGE_INPUT_TRUTH_AND_VISIBILITY_V1` (main
`dd4224d5a604d92148bd9421fb994d017a0616ab`). Do not implement A5.

Owner briefing: `SMIAL_A4_FORGE_REPRESENTATION_LADDER_V1_CURSOR.md`.

## Task Outcome Brief

- **Owner decision:** one `/hypothesis-forge` is a bounded Forge **run**, not
  a single HFIC session. It must complete allowed search and return a short
  result that can be trusted in an explicit scope:
  `FORGE INPUT → BASE → eligible ACTIVE representations → candidate /
  scoped exhaustion / non-scientific stop`.
- **Product outcome:** deterministic ladder resolver + aggregate run
  receipt/readout over existing sessions, A3 input, frozen V1 adapter, and
  existing HFIC freeze/finalize. Runtime wiring is implemented; this delivery
  does not execute a real scientific generator/Critic on market evidence.
- **Named consumer:** Пётр; slash-agent Cursor/Codex; existing HFIC
  sessions/Critic; A5 identity + program gold.
- **Cheapest falsifier:** BASE returned admissible NO_WORTHY, V1 is eligible,
  but slash stopped; or V1 did not execute and owner got SEARCH_EXHAUSTED; or
  a repeat slash silently started a new trial.
- **Terminal:** targeted E2E fixture cases + real no-write C1/C2 compatibility
  + isolated reviews + exact-head CI + merge-readiness. Stop before owner
  phrase.
- **Non-goals:** Prompt A/B/C on market evidence; Independent Critic on a real
  hypothesis; V1 scientific probe execution; commissioning; historical rewrite;
  new market epoch; A5 identity/provenance/gold; VPS/provider; program
  acceptance.

## Decision capsule

- `DECISION_DELTA`: an HFIC session terminal is no longer automatically the
  owner-final of the whole search.
- `UNCERTAINTY_REMOVED`: whether allowed search completed or stopped between
  already existing capabilities.
- `CAPABILITY_OR_EVIDENCE`: `smial.forge-run-receipt` 1.0 plus E2E fixture
  routing through real persistence/readback APIs and a no-write real
  BASE/CONTROL → V1 envelope compatibility receipt.
- `STOP`: merge-readiness; no scientific slash; no merge without the
  machine-rendered owner phrase.
- `NEXT`: after merge/readback, recommended A5 identity/provenance + owner gold.
- `SPEC_ROUTE`: `DESIGN_SPEC`.
- `REPLAN_TRIGGER`: frozen V1 must change; a second competing readiness
  engine appears; canonical RDP mutates; A5 identity work leaks into A4;
  cheapest falsifier cannot run.

## Architecture

A3 remains the only input/visibility owner. No "A4 readiness". Startup uses
`build_forge_input_receipt`. Representation-specific applicability uses the
existing scientific contract (`representation_status`,
`control_probe_permitted`, frozen V1 adapter).

Registry `configs/hfic_representation_ladder_v1.yaml` holds only
id/version/order/status/reuse class/allowed trigger terminals. Known IDs
resolve in code. Unknown ACTIVE id fail-closes. New Vn needs definition,
implementation, tests, and explicit activation; it does not get a new owner
command or a rewritten transition engine.

Aggregate run stores refs/hashes of stages and the owner-final, not copies of
scientific payloads. Persist as `RESEARCH_ARTIFACT` with
`artifact_kind=FORGE_RUN_RECEIPT` on a process-owned or disposable store.
Do not add a ResearchStore `RecordKind`. Do not create a market evidence
epoch. Legacy epoch used for identity binding is the existing CONTROL
`evidence_epoch_sha256`.

Machine invocation, Skill, Cursor command, critic YAML, and operator doc
must agree. `ONE_SLASH_ONE_SESSION` cannot remain the machine boundary next
to a multi-stage run. Scope stays one admissible trial per
representation/version. No generate-until-PASS.

Python selects the transition and checks identity. The elected slash agent
executes existing Prompt/isolated Critic. No new LLM client, service, or
autonomous endless agent.

## Transition contract (resolver)

| Actual state | Allowed behavior |
|---|---|
| Input missing | `INPUT_NOT_READY`; no synthesis or scientific negative |
| Identity/visibility/packet broken | `OBSERVABILITY_BLOCKED`; no scientific negative |
| BASE candidate passes required screen | Return candidate + exact next decision; do not start V1 for variety |
| BASE primary KILL, runner-up pending | Finish the already allowed runner-up path; no early V1 |
| Effective BASE = `NO_WORTHY` / allowed duplicate-close | If V1 eligible, auto-advance without owner "continue" |
| Effective BASE = data/grounding INVALID or frozen Case C | Typed non-scientific stop; not exhaustion; do not switch lens |
| `RUNNER_UP_REVISION_REQUIRED` / other live PAUSE | Keep PAUSE; representation is not tried until complete |
| V1 candidate | Existing isolated Critic + required screen on exact frozen challenger |
| V1 scientific KILL/NO_WORTHY | Next ACTIVE only if its trigger allows; else scoped final |
| V1 INVALID / no executable runtime result | `OBSERVABILITY_BLOCKED` or existing typed pending/stop, not scientific KILL |
| All required admissible stages completed without candidate | `SEARCH_EXHAUSTED_CURRENT_EVIDENCE` with explicit scope |
| Same slash on completed run | Readback existing result; no new search |
| Same slash on incomplete run | Resume exact pending stage from saved artifacts; no regenerate |

Do not permit V1 after arbitrary `KILL_*`. Do not rename a session
`NO_WORTHY` into the ladder final. Prompt C must not emit final WAIT while an
eligible next representation remains. Historical Prompt C bytes stay frozen;
the aggregate readout explains the current next action.

Ready A3 `forge_input_next=STOP_BEFORE_SYNTHESIS` is diagnostic surface, not
cancellation of an already-authorized slash.

Crash after generation reuses the saved draft. Uncertain execution is not
silent regeneration. Technical/schema/transport/packet-loss/missing-handler
failures are not scientific KILL.

## E2E cases (disposable plane, real routing)

Fixtures may stub generator/Critic answers. Dataset/packet binding, resolver,
HFIC freeze/finalize, persistence/readback, and owner rendering must be real.

1. Positive BASE candidate → Critic/finalize; V1 not started.
2. BASE empty → V1 candidate; auto-advance; Critic sees challenger, not only old BASE packet.
3. BASE empty → V1 scientific negative → scoped exhaustion only after a real stage receipt.
4. V1 broken visibility → `OBSERVABILITY_BLOCKED`; no scientific negative.
5. Primary kill + runner-up pending/pass/pause → effective terminal; no early V1.
6. Retry at stage boundaries → no second trial/payload in the same slot.
7. Crash after generation → saved draft reused.
8. Known eligible synthetic mechanism is not closed for missing proven alpha, unrelated historical caveat, or lexical similarity.
9. Future-leak counterpart is rejected for the exact reason; science not weakened.
10. Two worktrees + synthetic C3 import → one root; new input visible without config/threshold/path edits; historical C1 receipt unchanged.
11. Later registered representation → known synthetic handler via registry; engine not rewritten; unknown ACTIVE id fail-closes.
12. Scope/caveat reporting → cumulative visible cohorts are not V1 used cohorts; missingness not hidden.

Real current C1/C2 no-write acceptance is separate from fixture PASS. CI uses
tracked fixtures. Runtime evidence is not a skipTest-shaped required gold.

## Semantic propagation

Primary route: `SEM-HYPOTHESIS-FORGE`. `SEM-LIVE-EVIDENCE-TO-FORGE` /
`SEM-PRIOR-WORK` only if their semantics actually change. Catalog the ladder
module, registry, schema, tests. Skill/command/operator agree on bounded run.
Do not edit root `AGENTS.md` or harness authority. Frozen V1 preregistration
is read-only.

## Rollback

Ordinary Git revert of code/registration. Do not delete imported raw/release
evidence or historical trials. New runtime artifacts stay readable or
explicitly version-typed. No destructive recovery.
