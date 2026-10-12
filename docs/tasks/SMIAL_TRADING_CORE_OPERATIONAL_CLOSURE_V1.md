---
task_id: SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-10-11'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ba87f8e339d5cc3aa55322801ae56e3f92369446
  expected_upstream: origin/main
  expected_upstream_oid: ba87f8e339d5cc3aa55322801ae56e3f92369446
  expected_branch: codex/smial-trading-core-operational-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Complete the ordinary source-driven PAPER/SHADOW software operating path, including durable activation, automatic adapters, successor continuity, shared outstanding-obligation envelope, originating exits, partial accounting, cold recovery, truthful readback and ownership cleanup, without operational or financial authority.
managed_write_set:
- docs/tasks/SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1.md
- docs/evidence/smial_trading_core_operational_closure_v1/**
- docs/reports/smial_trading_core_operational_closure_v1/**
- docs/operator/TRADING_CONTINUITY_OFFLINE_V1.md
- docs/contracts/science_to_strategy_handoff_v1.md
- docs/contracts/trading_runtime_policy_v1.md
- docs/contracts/risk_and_economics_v1.md
- docs/contracts/episode_decision_continuity_v1.md
- docs/contracts/owner_lifecycle_projection_spine_v1.md
- src/solana_alpha_lab/factory/trading_runner.py
- src/solana_alpha_lab/factory/trading_coordinator.py
- src/solana_alpha_lab/factory/trading_adapters.py
- src/solana_alpha_lab/factory/episode_decision.py
- src/solana_alpha_lab/factory/strategy_runtime.py
- src/solana_alpha_lab/factory/promotion_handoff.py
- src/solana_alpha_lab/factory/hfic_research_scope.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/paper_plane.py
- src/solana_alpha_lab/factory/paper_shadow_operations.py
- src/solana_alpha_lab/factory/paper_shadow_commands.py
- src/solana_alpha_lab/factory/trading_operations.py
- src/solana_alpha_lab/factory/trading_runtime_policy.py
- src/solana_alpha_lab/factory/risk_economics.py
- scripts/trading_continuity.py
- scripts/prove_trading_core_operational_closure.py
- configs/execution_domain_v1.json
- configs/factory_semantic_operability_v1.yaml
- delivery-harness/policies/solana-alpha-lab.md
- tests/test_trading_core_operational_closure_v1.py
- tests/test_trading_operational_adapters_v1.py
- tests/test_trading_operational_obligations_v1.py
- tests/test_trading_operational_recovery_v1.py
- tests/test_trading_continuity_v1.py
- tests/fixtures/trading_core_operational_closure_v1/**
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
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
- STOP_MATERIAL_CONFLICT_OUTSIDE_OWNER_ACCEPTED_D1_D4
- STOP_WORKING_RUNTIME_PROVIDER_CREDENTIALS_DEPLOY_SIGNER_TRANSACTIONS_OR_MONEY
- STOP_NEW_DEPENDENCY_UNOWNED_CLEANUP_SETTINGS_OR_HISTORY_REWRITE
- REPLAN_IMPOSSIBLE_FALSIFIER_REPEATED_SEAM_FAILURE_OR_RESOURCE_UNSAFETY
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, EXTERNAL_ROUTE_KNOWLEDGE, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: [CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-011]
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/science_to_strategy_handoff_v1.md
    - docs/contracts/trading_runtime_policy_v1.md
    - docs/contracts/risk_and_economics_v1.md
    - docs/evidence/smial_trading_core_operational_closure_v1/source-contract.md
    DELIVERY_EVIDENCE:
    - docs/evidence/smial_trading_core_operational_closure_v1/completion.json
    - docs/evidence/smial_trading_core_operational_closure_v1/independent-review.json
    - docs/evidence/smial_trading_core_operational_closure_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1

Source PRD/SSD is the exact attached MD, preserved byte-for-byte at
`docs/evidence/smial_trading_core_operational_closure_v1/source-contract.md`,
SHA256 `addc05071197efb3462771b52f5699170d54061656efeda0b7f48e52bdb0f0b7`.
The owner's explicit EXECUTE accepts D1-D4; document proposals alone grant no
authority. This binding does not create a second PRD. C01-C24 are mandatory.

ENTRY_DECISION: START_WITH_PATCH. SPEC_ROUTE: BOTH (attached PRD/SSD).
Route/actor: DIRECT_CODEX_DELIVERY/CODEX. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
DECISION_DELTA: software commissioning readiness for ordinary PAPER/SHADOW.
UNCERTAINTY_REMOVED: automatic callers, durable state and independent recovery.
CAPABILITY_OR_EVIDENCE: source-driven process, A@V1 to B@V1 with A inventory,
shared mode obligations, frozen old exits, partial conservation, cold restore.
Named consumer: future authorized commissioning operator and eligible strategy.
Cheapest falsifier: cold ordinary process autonomously consumes an eligible
source episode and persists its linked attempt/result without manual stitching.
STOP: exact machine-ready owner merge phrase, or a material new authority fork.
NEXT: complete all safe dependent slices, whole-outcome proof, cleanup, reviews,
bindings, preflight, task push/PR and exact-head CI/readiness.
REPLAN_TRIGGER: repeated seam failure, impossible oracle or resource unsafety.
Evidence budget: compact synthetic fixtures, real disposable SQLite and bounded
subprocesses, virtual time, no real data or full local gate before PR.

D1: distinct accepted scientific identities A@V1/B@V1; same-ID V2 still denied.
D2: one entry-enabled bot per mode, shared versioned outstanding envelope;
absence of explicit limits is CONFIGURATION_REQUIRED, UNKNOWN frees nothing.
D3: pause/stop/switch close new entries; originating exits/results continue.
D4: ordinary driver plus real PAPER/quote-only SHADOW adapters are software
scope, external activation and all financial execution are excluded.
Historical S08/S13 and previous PARTIAL outcomes are preserved; replacement
positive successor evidence references this explicit accepted decision.

Tool Entry: existing delivery-harness, Git/gh, locked toolchain, native SQLite.
New plugin/connector/MCP/automation/package/service: NONE. Factory Fit FULL_REVIEW.
NOW: this exact operating closure. WATCH: separately authorized commissioning.
Readback proved predecessor #396/main CI success. Clean base, one checkout;
prior task branch retained. All active time gates are resolved/superseded.
Current canonical provider binding resolves to registry-011 and is pinned
explicitly by this task context. Preserve the historical domain-policy bytes
and TASK30 receipt; policy-wide prose normalization is outside this atom.
Immutable predecessors and provider grants stay intact.

Implementation replan inside this same authorized atom: frozen 0df9aa7e
architecture review reproduced a partial EXIT using a corrupted remainder
despite UNKNOWN readback. Reuse the existing PaperPlane original witnesses
to verify cumulative quantity/cost/fee projection before EXIT inputs, inside
attempt creation and at result acceptance. Quarantine the affected obligation
while healthy originating exits continue. No new state owner, schema/cache,
dependency, product decision or operational authority; no internal seam is
deferred to commissioning. Preserve actual role verdicts and native before,
then require fresh whole-outcome evidence and all four exact-inventory roles.

The subsequent frozen 4a327869 review found two required internal seams:
valid schema1.1 definitive ENTRY nonfill must finish recovery without being
mistaken for positive inventory; ordinary SHADOW must select separately
authorized existing grants by originating epoch/strategy before attempt/quota
claim, so A-oldEXIT and B-newENTRY coexist in one caller. Reuse native original
attempt/FINAL/result release proofs and existing scoped adapter/grant owners.
No grant issuance, operational configuration, new registry or external action.
Preserve actual CODE/ARCH NOT_READY and GOAL PASS for that frozen head; require
native before/after and fresh exact-inventory review after both repairs.

Frozen 1cdf0003 CODE/GOAL/ARCH reviews returned actual NOT_READY: native backup
could overwrite an existing hardlinked manifest/SQLite auxiliary artifact;
malformed original JSON could crash tick/status and starve healthy old EXIT.
Bound the same backup owner to all five final artifacts before any write,
exclusive reservations and private native SQLite staging with standalone copy.
Validate original JSON shapes in existing origin/capture/attempt owners;
quarantine the exact affected obligation without resend or fabricated closure.
No new schema, state owner, dependency, product decision or external authority.
Preserve native before/after and actual role verdicts; require fresh whole
outcome, cold operator and all four isolated exact-inventory reviews.

Frozen 08c5ae1e CODE review reproduced a P1 restore destination collision:
preexisting regular -journal/-wal/-shm were deleted by native SQLite while
restore returned success. Actual GOAL and ARCH PASS remain scoped historical
verdicts; OWNER review was not performed on the blocked inventory. Reuse the
native restore owner with complete fresh destination-family guards, exclusive
publication and private preparation of the original fence/pause/snapshot event.
Preserve native before/after and rerun whole outcome plus four frozen roles.
Further critic output is restricted to P0/P1 by the owner's explicit steering;
the required role set, exact-head gate and separate merge phrase stay binding.
The bounded native repair falsifier also proved an unhashed WAL overlay could
change the restored envelope $30 to $90 while the sealed main DB hash matched,
for both historical WAL-format and fresh DELETE-format carriers. Preserve this
actual P1 before evidence; require a standalone source and hash-verified private
input copy before native restore, without deleting source artifacts or using
immutable readers for current runtime truth.
An interim repair native two-cycle backup/restore/reconcile/ACK falsifier then
hit the fixed RESTORE-SNAPSHOT event ID; its actual interim source pins are
preserved separately rather than attributed to frozen 08c5ae1e. Append a new
snapshot-bound event through the same owner, retain every original event/body/
clock, and bind cut/reconcile/ACK to the current restore. Prove the second ACK
and originating due EXIT before fresh whole-outcome evidence.

Exact-head CI for d8ee540f failed the fourteen-day C21 source startup with
an empty first admission. A native 32 GiB capacity reproduction confirmed
the existing producer guard stops before nomination: its conservative
fourteen-day fixture reserve is 142188216320 bytes. Actual CI free space
was not logged and stays UNKNOWN. Keep production storage/admission unchanged;
explicitly model physical capacity in the positive synthetic scenario and
prove the low-capacity native stop with zero calls. Preserve that actual CI
failure and the scoped four-role PASS on 1a617c5f as history. Refresh whole
native outcome, consumer/clock/operator receipts, four isolated P0/P1 reviews
and exact-head CI in this same PR; no operational configuration or new grant.
The same CI's shard4 also proved the semantic overview was 16404 bytes against
the existing 16384-byte limit. Compress only SEM-OWNER-LIFECYCLE purpose text;
retain route/question/owner/operator bindings and authority/size boundaries.
The direct semantic consumer module proves 16349 bytes and 15 PASS tests.
