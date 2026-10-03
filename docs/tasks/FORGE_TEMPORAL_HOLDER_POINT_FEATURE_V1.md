---
task_id: FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-03'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 94b284534b6ad55a95002d51b9d04b4a5ced6bde
  expected_upstream: origin/main
  expected_upstream_oid: 94b284534b6ad55a95002d51b9d04b4a5ced6bde
  expected_branch: codex/forge-temporal-holder-point-feature-v1
  dirty_mode: FORBIDDEN
objective: >-
  Allow the typed PIT FIELD-HOLDER-COUNT-001 only as a temporal point_value
  feature. Preserve PRICE_RELATIVE_PROXY, existing identities, V1-V5 replay,
  clocks, missingness, lineage and ordinary budget semantics. Prove public
  scratch preview/discovery, cold replay, Prompt A/candidate/Critic/owner exact
  X/Y binding and registered capability replay; no real scientific look.
managed_write_set:
  - docs/tasks/FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1.md
  - docs/contracts/forge_temporal_holder_point_feature_v1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
  - scripts/hypothesis_forge.py
  - tests/test_forge_temporal_holder_point_feature_v1.py
  - tests/fixtures/forge_holder_point_v1/**
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/forge_temporal_holder_point_feature_v1/**
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - REAL_SCIENTIFIC_OR_RUNTIME_WRITE
  - REAL_HOLDER_OUTCOME_READ
  - C5_ACCESS
  - PROVIDER_OR_VPS_CALL
  - OLD_PRICE_LIQUIDITY_IDENTITY_CHANGE
  - INVENTED_CLOCK_OR_MISSINGNESS_SEMANTICS
  - MANUAL_TEST_ONLY_PRODUCTION_BINDING
  - MERGE_BEFORE_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-TEMPORAL-DISCOVERY-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
      - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
      - src/solana_alpha_lab/factory/hfic_session.py
      - configs/experiment_capability_registry_v2.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_temporal_holder_point_feature_v1/completion.json
      - docs/evidence/forge_temporal_holder_point_feature_v1/independent_review.json
      - docs/evidence/forge_temporal_holder_point_feature_v1/factory_fit.json
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: DESIGN_SPEC (the exact owner contract below supplies design).
DECISION_DELTA: the preregistered early holder question becomes executable.
UNCERTAINTY_REMOVED: field/operator, PIT and production binding compatibility.
CAPABILITY_OR_EVIDENCE: one backward-compatible feature expansion and vertical proof.
STOP: exact-head CI and merge-readiness PASS; await exact owner phrase.
NEXT: separately authorized guarded merge, then separately authorized one MAIN.

TASK_OUTCOME_BRIEF:
- OWNER_DECISION: whether the frozen holder question can be asked without a code repair.
- PRODUCT_OUTCOME: remove a proven feature expressivity bottleneck in bounded search.
- NAMED_CONSUMER: EARLY_HOLDER_STATE_TO_PRICE_PATH_15M_TO_4H.
- CHEAPEST_FALSIFIER: synthetic public owner path and tampered identity refusal.
- TERMINAL_OUTCOMES: READY_FOR_OWNER_GATE or earliest fail-closed boundary.
- USER_VISIBLE_RESULT: exact holder feature/price target identity through all packets.
- NON_GOALS: no actual science/provider/C5; no extra operators or new capability.
- EVIDENCE_BUDGET: disposable synthetic proofs, one PR, isolated required reviews, CI.
- REPLAN_TRIGGER: changed old identity, invented semantics or unrelated expansion.

FACTORY_ALIGNMENT_PREFLIGHT: START_AS_WRITTEN; reuse typed observations and temporal evaluator.
PRODUCT_HORIZON: NOW=this feature atom; WATCH=separately authorized post-merge MAIN.
CAPABILITY_RADAR_NOW: NONE.

## Exact owner contract

MODE: EXECUTE
TASK: FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1
MODEL_EFFORT: SOL_XHIGH

Repository:
`lancerbeta/solana-alpha-lab`

Expected canonical base at start:
`94b284534b6ad55a95002d51b9d04b4a5ced6bde`

This is ONE bounded capability atom.
Do not split it into follow-up repair PRs for predictable integration seams.
If an acceptance-critical seam is broken, repair it inside this same atom.
Do not widen into unrelated architecture.

==================================================
OWNER OUTCOME
==================================================

Remove one proven Forge expressivity bottleneck:

allow the already typed PIT field

`FIELD-HOLDER-COUNT-001`

to be used by ordinary temporal Forge as an EARLY FEATURE via:

`point_value` ONLY,

while preserving the existing:

- `PRICE_RELATIVE_PROXY` target;
- temporal PIT / availability / snapshot lineage semantics;
- missing != zero;
- V5 downside readout;
- search-budget / session / replay semantics;
- persisted historical V1–V5 evidence;
- `CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`;
- existing PRICE and LIQUIDITY behavior.

Named consumer after merge:

`EARLY_HOLDER_STATE_TO_PRICE_PATH_15M_TO_4H`

This implementation task MUST NOT execute that real scientific look.

==================================================
ENTRY / AUTHORITY
==================================================

Start from root `AGENTS.md`.

Resolve current:
- origin/main;
- active time gate;
- exact Delivery Harness task/write contract;
- SEM-HYPOTHESIS-FORGE;
- SEM-MARKET-DATA-FEATURES;
- SEM-EXPERIMENT-CAPABILITIES;
- direct durable owners touched by this feature.

If expected base moved, inspect the relevant delta before mutation.
Do not implement against stale assumptions.

Owner authorizes for this exact atom:

- bounded code/docs/tests/evidence changes;
- commit;
- push;
- one PR;
- required isolated reviews;
- exact-head CI.

Owner does NOT authorize merge until the current machine gate returns the exact
owner phrase and that phrase is separately supplied.

No provider/API/RPC/WSS.
No VPS action.
No real ResearchStore mutation.
No real scientific look/session/reservation/operation/disposition.
No C5 access.
No next-cohort import.
No real money / signer / transaction.

==================================================
FROZEN PRODUCT / SCIENCE INTENT
==================================================

The future separately authorized scientific question is fixed now, before
holder outcomes are read:

OWNER_FOCUS:
`EARLY_HOLDER_STATE_TO_PRICE_PATH_15M_TO_4H`

population:
`BASE_X`

decision:
`Y900`

feature:
`holder_y900 = point_value(FIELD-HOLDER-COUNT-001, Y900)`

frozen predicate:
`holder_y900 >= 3`

target:
`PRICE_RELATIVE_PROXY Y900 -> Y14400`

future look budget:
exactly ONE MAIN.

The `>=3` threshold is FEATURE-SIDE ONLY.

Known holder distribution before outcome inspection:
median=2 and ~73.4% of observed Y900 values are <=2, so `>=3` avoids threshold
search around the noisy 1-vs-2 region while retaining a broad group.

DO NOT add or try:
- >=2;
- >=4;
- >=5;
- quantile-derived alternative thresholds;
- price condition;
- liquidity condition;
- interaction;
- compound refinement;
- ADAPTIVE refinement.

This task only makes the frozen question executable.

==================================================
KNOWN PRIOR EXPOSURE
==================================================

Preserve in durable task/consumer documentation:

The holder question is NOT an independent idea generated without outcome
exposure.

Previous D2 analysis on the same C1-C4 market showed that an apparent downside
difference was substantially related to whether price moved at all.

Therefore:

- activity / price-staleness is a known confound;
- a C1-C4 holder result will remain EXPLORATORY;
- a different distribution alone will not count as entry edge;
- C5 stays untouched as a possible future OOS falsifier.

Do not rewrite or hide this provenance.

==================================================
CORE DESIGN — FIELD × OPERATOR POLICY
==================================================

Do NOT simply add HOLDER to a broad global field allowlist that automatically
inherits every PRICE/LIQUIDITY operator.

The allowed semantic matrix must be explicit:

PRICE:
existing behavior unchanged.

LIQUIDITY:
existing behavior unchanged.

FIELD-HOLDER-COUNT-001:
`point_value` ONLY.

Holder MUST remain rejected for:

- ratio;
- return_ratio;
- drawdown_from_grid_max;
- rebound_from_grid_min;
- target field.

Holder point must be <= decision point.

A holder value after decision must fail through the existing future-feature
guard.

Use the smallest existing typed error vocabulary.
Do not create a policy framework/registry unless current architecture already
has the exact owner and reuse makes it strictly smaller than local explicit
policy.

==================================================
DATA / PIT SEMANTICS
==================================================

Reuse the typed Tokens V2 observation.

Forge must NOT read raw Jupiter JSON directly.

Required holder behavior:

OBSERVED numeric value:
usable.

FIELD_ABSENT / typed missing:
unknown, never zero.

available after allowed decision deadline:
unavailable.

missing/broken snapshot lineage:
fail closed.

duplicate/integrity conflict:
existing temporal integrity owner decides.

observation_clock_policy:
existing owner decides.

Do not create:
- holder-specific clock;
- holder-specific loader;
- holder-specific missing fallback;
- second temporal evaluator.

If the generic point-value path is already correct, reuse it.

==================================================
BACKWARD COMPATIBILITY
==================================================

This is a backwards-compatible FEATURE-surface expansion.

Do NOT create:
- CALC_V6 merely for this change;
- new temporal schema version;
- new capability ID.

For queries that do not use holder:

- canonical specs must remain unchanged;
- spec SHA256 must remain unchanged;
- PRICE/LIQUIDITY calculation behavior must remain unchanged;
- persisted V1–V5 readback must remain unchanged.

`validate_temporal_query()` / projections must expose HOLDER as a decision field
only when the actual query uses holder.

Do not globally advertise HOLDER in old query identities.

==================================================
REGISTERED CAPABILITY
==================================================

Existing capability remains:

`CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`

A synthetic persisted holder-feature recipe must survive:

ordinary temporal query
→ saved recipe
→ canonical recipe conversion
→ registered fixed-time capability
→ same spec identity
→ same holder feature semantics
→ existing PRICE_RELATIVE_PROXY result surface.

No holder-only replay engine.

==================================================
VERTICAL PROOF LOOP
==================================================

Do not finish at unit tests.

Prove ONE owner scenario all the way through production owners:

holder query
→ validation
→ PIT row selection
→ predicate match/missing
→ ordinary discovery
→ persisted V5-shaped evidence
→ cold replay
→ Prompt A binding
→ selected candidate binding
→ Independent Critic packet
→ owner readout
→ registered fixed-time capability replay.

Every stage must consume the output of the previous real production owner.
Tests must not manually reconstruct a binding that production does not create.

If any stage requires test-only glue, treat that as a product integration gap
and repair the earliest broken production boundary in this same atom.

==================================================
REQUIRED TEST / EVIDENCE MATRIX
==================================================

A. VALIDATOR POSITIVE

Accept:

`point_value(FIELD-HOLDER-COUNT-001, Y900)`

when decision=Y900.

Confirm holder appears in decision-field projection only for that query.

B. VALIDATOR NEGATIVES

Must reject before value read:

- holder ratio;
- holder return_ratio;
- holder drawdown;
- holder rebound;
- holder target;
- holder point after decision.

Include a regression proving a future broad `ALLOWED_FIELDS` change cannot
silently give holder these operators.

C. PIT / MISSING / LINEAGE

Using production temporal selection:

- observed holder before deadline matches;
- FIELD_ABSENT does not match and remains feature_unknown/missing;
- value 0, if ever validly OBSERVED, is a value and is not confused with
  FIELD_ABSENT;
- late holder is excluded;
- malformed/missing lineage fails closed;
- price present + holder absent cannot silently match holder predicate;
- holder and price from the same provider snapshot preserve correct occurrence
  / availability binding.

D. OLD-SPEC REGRESSION

Pin representative existing PRICE and LIQUIDITY temporal queries from current
main.

Before and after the implementation require identical:
- canonical spec;
- spec SHA256;
- result for frozen synthetic input.

Do not update expected old hashes merely to make the test pass.
A changed old identity is a blocker.

E. SCRATCH PUBLIC PREVIEW

Disposable store/data only.

Run holder query through existing public preview path.

Require:
- feature can be inspected before target outcome;
- no provider call;
- no scientific look;
- no hidden target load;
- missing support visible.

F. SCRATCH PUBLIC DISCOVERY

Disposable production-shaped store/data.

Execute exactly:

holder_y900 = point_value(holder,Y900)
holder_y900 >= 3
PRICE_RELATIVE_PROXY Y900->Y14400

Require normal current V5 result:

- matched_n;
- observed/missing;
- baseline;
- mean;
- median;
- zero_n;
- downside profile;
- by_cohort;
- calendar semantics;
- frozen recipe;
- existing cost labels.

G. COLD REPLAY / CRASH SAFETY

Cold replay of the holder result must:

- return saved result;
- not create another look;
- not load evaluator again where replay contract forbids it;
- preserve ordinary operation state semantics.

Include at least one interrupted-path test if this new field crosses a code path
not already covered by the existing crash regression.

Do NOT duplicate recovery machinery.

H. PROMPT A → CRITIC → OWNER

Use the actual production packet builders.

Require the same exact scientific identity:

X:
`FIELD-HOLDER-COUNT-001 point_value Y900 >= 3`

Y:
`PRICE_RELATIVE_PROXY Y900 -> Y14400`

to remain visible through:
- Prompt A grounded evidence;
- frozen selected candidate;
- Critic input packet;
- owner projection.

No fixture may claim a different feature or horizon than the calculated result.

Add a negative binding test:
tampering holder field / point / threshold / target horizon must fail rather
than silently pass using the old result.

I. REGISTERED OFFLINE REPLAY

Feed the synthetic saved holder recipe through:

`CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`

Require:
- accepted capability;
- same spec SHA;
- same frozen input;
- same holder feature;
- same target;
- no provider call;
- no labeled NetReturn.

J. REAL C1-C4 READ-ONLY COMPATIBILITY

Canonical real store may be inspected READ ONLY only after synthetic vertical
passes.

Do NOT read the Y900->Y14400 outcome for the holder question.

Allowed:
- holder feature availability/readiness;
- query validation;
- exact routing;
- pre-values admission;
- runtime inventory before/after.

Require real store inventory unchanged.

C5 MUST NOT be accessed.

==================================================
FUTURE SCIENTIFIC DECISION CONTRACT
==================================================

The implementation must preserve this preregistration in the task/handback.

After this capability is separately merged, the future one-MAIN C1-C4 run will
ask:

Does holder_count >=3 at Y900 identify a group with positive subsequent price
direction that is not explained merely by a greater probability of price
moving at all?

No vague "distribution differs" success criterion.

The future result will be classified using existing V5 fields only.

Because baseline includes matched, complement may later be derived only for
additive quantities after proving matched is a subset of baseline:

- observed N;
- sum / mean;
- zero_n;
- negative_n;
- <=-20 count/rate;
- <=-50 count/rate;
- negative_mass.

Do not derive complement median / quantiles / ES / concentration.

Activity decomposition later is descriptive only:

move_n = observed_n - zero_n
move_rate = move_n / observed_n
mean_given_move = (mean * observed_n) / move_n

when move_n > 0.

It is NOT a second estimand/look.

Future classification is frozen as:

`HOLDER_NO_POSITIVE_ENTRY_EDGE`
when pooled matched mean <=0 OR matched mean <= complement mean.

`HOLDER_ACTIVITY_ONLY`
when pooled matched mean is positive and beats complement, but
matched mean_given_move <= complement mean_given_move.

`HOLDER_DIRECTIONAL_EDGE_COHORT_UNSTABLE`
when directional advantage survives activity decomposition but fewer than
3 of 4 cohort matched means are positive or material cohort support is absent.

`HOLDER_DIRECTIONAL_EDGE_OOS_WORTHY`
only when:
- pooled matched mean >0;
- pooled matched mean > complement mean;
- matched mean_given_move > complement mean_given_move;
- >=3 of 4 cohort matched means >0;
- result is not dominated by one winner or an integrity/missingness defect.

`HOLDER_RESULT_INCONCLUSIVE`
only for a real support/integrity/readout blocker.

Equal medians are not a standalone kill.
Not every downside metric must agree.

If downside is worse, report the tradeoff.
Do not optimize the holder threshold to fix it.

==================================================
ECONOMIC BOUNDARY
==================================================

Current cost stress output remains visible.

Do not use current ~10% BASE haircut as a hard scientific kill because its
contract is:

`ASSUMPTION_STRESS_ONLY`
`ASSUMPTION_NOT_CALIBRATED`.

`ESTIMATED_NET_PROXY != NetReturn`.

A gross signal that survives is only eligible for the NEXT economic/execution
gate.

It is not strategy/promotion.

==================================================
C5 BOUNDARY
==================================================

C5 is untouched.

Only a future:

`HOLDER_DIRECTIONAL_EDGE_OOS_WORTHY`

result may recommend spending C5 on one preregistered holder OOS falsifier.

If so, the following stay frozen:

- threshold >=3;
- decision Y900;
- target Y900->Y14400;
- activity decomposition;
- fixed downside metrics.

No C1-C4 re-optimization before C5.

This implementation task does not access or assign C5.

==================================================
NON-GOALS
==================================================

No holder target.
No holder growth/activation target.
No holder ratio/delta/path ops.
No STATS5M.
No market-cap expansion.
No launchpad expansion.
No generic event target.
No arbitrary expression language / DSL.
No ML.
No feature selection.
No threshold optimizer.
No new provider/data collection.
No new representation.
No complement-policy engine.
No D2 work.
No AUTO repair.
No C5.
No CALC_V6 solely for holder feature.
No new capability ID.

==================================================
ANTI-FOLLOW-UP-PR RULE
==================================================

Before declaring the task ready, explicitly ask:

"What predictable failure will the very first real holder MAIN hit that my
synthetic/vertical proof did not exercise?"

Inspect:
- validator;
- loader;
- clocks;
- missingness;
- spec identity;
- ordinary operation;
- replay;
- V5 result;
- Prompt A;
- Critic;
- owner projection;
- registered capability consumer.

If the answer identifies a concrete in-scope seam, test and close it NOW in the
same PR.

Do not create speculative infrastructure.

If the discovered issue belongs to an unrelated capability, document residual
and leave it out.

A task is NOT DONE with:
"core implementation works; operational path to be fixed later."

==================================================
FAIL / RECOVERY
==================================================

Fail closed and STOP if:

- holder semantics require invented missing/clock semantics;
- production path needs holder-specific raw provider access;
- existing PRICE/LIQ spec identity changes;
- synthetic success requires manual construction production never does;
- Prompt/Critic identity differs from executed query;
- registered capability cannot replay holder recipe;
- real-data proof would require reading new holder outcome;
- C5 is required to prove the capability works.

Return earliest broken boundary and evidence.

Do not autonomously widen scope into a general research engine.

==================================================
DONE
==================================================

DONE means ONE exact PR head proves:

- holder point_value Y900 works;
- forbidden holder ops remain forbidden;
- holder target remains forbidden;
- missing / late / lineage fail correctly;
- old price/liquidity specs and behavior remain unchanged;
- public scratch preview works;
- public scratch discovery emits normal V5;
- cold replay works;
- Prompt A / candidate / Critic / owner carry exact X/Y identity;
- registered fixed-time capability replays the same recipe;
- real C1-C4 compatibility check is read-only;
- no C5 access;
- no real scientific/runtime writes;
- required isolated reviews PASS;
- exact-head CI PASS;
- merge-readiness returns true.

Required review must include:
- CODE_REVIEWER;
- GOAL_DOD_CRITIC;
- ARCHITECTURE_CRITIC;
- any stronger role mandated by current harness.

Architecture review must explicitly answer:
"What could pass unit tests here and still corrupt scientific validity?"

Stop at merge owner gate.
Do not merge without exact owner phrase.

==================================================
HANDOFF
==================================================

Return a compact owner summary first.

Then:

TASK:
BASE:
PR:
HEAD:
GIT_CLEAN:

OWNER:
FIELD_OPERATOR_POLICY:

HOLDER_POINT_VALUE_Y900:
HOLDER_RATIO:
HOLDER_RETURN_RATIO:
HOLDER_DRAWDOWN:
HOLDER_REBOUND:
HOLDER_TARGET:
HOLDER_AFTER_DECISION:

MISSING_NOT_ZERO:
LATE_VALUE:
BROKEN_LINEAGE:
PRICE_PRESENT_HOLDER_MISSING:

OLD_PRICE_SPEC_SHA_UNCHANGED:
OLD_LIQUIDITY_SPEC_SHA_UNCHANGED:
OLD_RESULT_REGRESSION:
OLD_V1_V5_READBACK:

SCRATCH_PREVIEW:
SCRATCH_DISCOVERY:
SCRATCH_V5_RESULT:
COLD_REPLAY:
CRASH_OR_INTERRUPTED_PATH:

PROMPT_A_XY_BINDING:
CANDIDATE_XY_BINDING:
CRITIC_XY_BINDING:
OWNER_XY_BINDING:
TAMPERED_BINDING_REFUSAL:

OFFLINE_CAPABILITY:
OFFLINE_SPEC_SHA_EQUAL:
OFFLINE_RESULT_SEMANTICS_EQUAL:

REAL_C1_C4_CHECK:
REAL_STORE_BEFORE:
REAL_STORE_AFTER:
REAL_STORE_UNCHANGED:

PREREGISTERED_FOCUS:
PREREGISTERED_PREDICATE:
PRIOR_ACTIVITY_EXPOSURE_RECORDED:
FUTURE_DECISION_TAXONOMY_BOUND:
FUTURE_LOOK_EXECUTED: false

C5_ACCESSED: false
PROVIDER_CALLS: 0
REAL_LOOKS: 0
REAL_SESSIONS: 0
REAL_OPERATIONS: 0
REAL_RESERVATIONS: 0
REAL_DISPOSITIONS: 0

ANTI_FOLLOWUP_SEAM_REVIEW:
RESIDUALS:
ROLLBACK:

REQUIRED_REVIEWS:
EXACT_HEAD_CI:
READY_FOR_OWNER_PHRASE:
OWNER_PHRASE:

TERMINAL:
`FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1_READY_FOR_OWNER_GATE`
