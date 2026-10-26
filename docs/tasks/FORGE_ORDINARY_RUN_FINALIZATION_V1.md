---
task_id: FORGE_ORDINARY_RUN_FINALIZATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-26'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3bb9da411b085084d6da45af761378257c050479
  expected_upstream: origin/main
  expected_upstream_oid: 3bb9da411b085084d6da45af761378257c050479
  expected_branch: codex/forge-run-ordinary-finalization
  dirty_mode: ALLOW_REPORTED
objective: Repair aggregate ordinary Forge-run finalization over existing BASE and episode representation sessions, preserving scientific identity/history/exposure and deriving completion of both bound operations from one genuine persisted owner-final.
managed_write_set:
- docs/tasks/FORGE_ORDINARY_RUN_FINALIZATION_V1.md
- src/solana_alpha_lab/factory/hfic_representation_ladder.py
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_session.py
- scripts/hypothesis_forge.py
- tests/test_forge_ordinary_run_finalization_v1.py
- tests/test_forge_representation_ladder_v1.py
- docs/contracts/forge_ordinary_operation_lifecycle_v1.md
- docs/evidence/forge_ordinary_run_finalization_v1/**
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_AFTER_EXACT_HEAD_CI_AND_MERGE_READINESS_BEFORE_OWNER_PHRASE
- NO_REAL_SCIENTIFIC_LOOK_PROVIDER_EXPERIMENT_PUBLICATION_OR_REMINDER_CHANGE
- NO_REAL_RESEARCHSTORE_WRITE_BEFORE_MERGE_AND_POST_MERGE_READBACK
- AFTER_MERGE_ONLY_NATIVE_FORGE_RUN_OWNER_FINAL_APPEND_ON_THE_EXACT_EXISTING_RUN
- NEVER_REWRITE_IDS_HISTORY_RESULTS_DRAFTS_ASSESSMENTS_RESERVATIONS_OR_BUDGETS
- REPLAN_ON_UNRESOLVED_IDENTITY_CONFLICT_OR_NEW_SCIENTIFIC_STATE_REQUIREMENT
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-REPRESENTATION-LADDER-001]
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/forge_ordinary_operation_lifecycle_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_ordinary_run_finalization_v1/completion.json
    - docs/evidence/forge_ordinary_run_finalization_v1/independent-review.json
    - docs/evidence/forge_ordinary_run_finalization_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# Ordinary Forge-run finalization

Explicit owner authorization: repair completion on the existing sessions, preserve
IDs/history/look accounting, prove owner-final and completion of both OPEN
operations; no new science/publication/reminder changes. Operational finalization
is authorized after merge, subject to exact existing-state revalidation.

SPEC_ROUTE=BOTH: this outcome brief and a bounded update of the existing lifecycle
contract; no new state machine, schema, command, migration, provider or dependency.

DECISION_DELTA: a completed ordinary two-stage run reads its genuine owner-final
and releases the research-universe profile without an artificial owner stop.
UNCERTAINTY_REMOVED: ordinary parent discovery and per-stage completion binding
can preserve ordinary/CONTROL separation and prevent foreign-stage completion.
The existing orphan-draft owner retains its own frozen parent/payload binding;
no controller-side bypass or new scientific recovery authority is introduced.
CAPABILITY_OR_EVIDENCE: an exact synthetic native vertical plus metadata-only
readback of the unchanged saved v12 run; after merge one native owner-final append.
Consumers: ordinary Forge entry/resume, operation_lifecycle and universe-policy gate.

## Entry and bounded design

START_AS_WRITTEN. Existing harness CHECK and Git transport PASS. Base is the
accepted main commit above. No active due marker supersedes this explicit task.
CAPABILITY_RADAR_NOW=NONE. Reuse the existing ladder, committed ResearchStore,
scientific-slot/session identities and operation_lifecycle completion owner.

Root boundary: selecting ordinary BASE must provide a parent for its applicable
representation children without labelling it CONTROL. A saved draft may resume
only its own representation. One genuine aggregate owner-final must bind BASE
and each linked representation operation to their own stage, slot and journal;
a focus/market-only match is insufficient. Legacy BASE proof remains supported.
Code evolution must not lose a wholly completed frozen chain: historical
aggregation requires source-epoch agreement and a final from the existing
transition owner; it cannot reopen or resume incomplete science on new code.

DoD: the native ordinary BASE + bound normalized session (both zero-candidate)
produces SEARCH_EXHAUSTED_CURRENT_EVIDENCE with both stages; no-write changes no
store bytes. Before persistence both operations remain OPEN. Native --persist
creates one owner-final and both derive COMPLETED; repeat adds no receipt or
exposure. Negative controls retain pending child, wrong parent/market/journal,
stale receipt and CONTROL restrictions. Existing synthetic science is fixture
setup only, never real market evidence.

Cheapest falsifier: one small synthetic published-episode fixture using existing
production owners and literal expected final/state transitions, plus focused
identity-negative controls. No full local gate before PR; exact PR CI owns it.
Budget: focused ladder/operation/direct-consumer tests; no blanket TDD or new
infrastructure. Replan on scope expansion or a repeated material blocker.

## Exact operational target (after merge)

- Run: FORGE-RUN-174FEA4EFD507581.
- Market: 170d8cc12e6e0609ebc6359c0f55f98421ae6a655d86d33e1927f733e7218dcf.
- BASE: HFIC-SESS-11151487AB3A19C1, journal 11151487ab3a19c15519c35db7c81cf8966c0d45c97340ee02524533ba546a71.
- Child: HFIC-SESS-AAD7A29F0F26D5AC, journal aad7a29f0f26d5acaf2bba820ad7c693ec6097705114aabfc835cdfbbf1d27df.
- BASE operation: dd17712c78eab047fa7e5cf8977e0940f99291211b31ada000fbe14e044c5050.
- Child operation: 868bc7e50e1adced93a024380b0e00680775f2c8843b3903561a2cfe3e7e40f8.
- Both source terminals: SYNTHESIS_COMPLETE / NO_WORTHY_HYPOTHESIS.
- Exact saved result hashes: 0559e2104100cf714d696559128eb8e84ee110b4d544384de208278b6f63801f and c445f16946c6a86e5ad56921b9d043691287a1a62a59c210bfcc9d1504535ea1.

Revalidate exact run/sessions/results, capture exposure and native inventory;
read --no-write, append only a machine-derived owner-final via forge-run --persist,
then cold-read both operations, gate and unchanged scientific records/exposure.
Do not use owner-stop to conceal the defect or infer scientific acceptance.

STOP: exact-head CI + merge-readiness, then one owner phrase. NEXT after accepted
merge: the already-authorized operational finalization above. No scientific rerun.
PRODUCT_HORIZON_NOW=NONE beyond this closure; WATCH only a reproducible wrong
parent/journal association. Model effort recommendation: SOL_XHIGH.

CI REPLAN (same outcome, no added science): full exact-head CI exposed three
existing finite-cap prefix scenarios. The public CLI projected the newest
operation by focus/market only: a paused BASE journal overrode START on a distinct
child slot. Narrow the existing projection by the aggregate's active scientific
slot; keep same-slot cap/authority behavior intact. No state, budget, new command
or workflow limit change. Verify the three exact failed scenarios and a short
foreign-slot negative, then rebind independent review and exact-head CI.

The same CI vertical then reached a formerly invisible selected-child review
rejection. For previously unmatched child review/technical terminals, reuse
interpret_critic_terminal as BASE does: the fallback is NON_SCIENTIFIC_STOP,
never scientific exhaustion or family closure. Preserve legacy registered
known-negative routing; require the saved stage reference and keep unknown,
pending and missing blocked. This
preserves Critic ownership and adds no new terminal/schema/authority.
