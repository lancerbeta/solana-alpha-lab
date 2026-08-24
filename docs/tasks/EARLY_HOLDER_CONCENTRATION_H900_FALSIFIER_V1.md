---
task_id: EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 64e24c61cd064e45c85d8be6a91a5efb069acee4
  expected_upstream: origin/main
  expected_upstream_oid: 64e24c61cd064e45c85d8be6a91a5efb069acee4
  expected_branch: cursor/early-holder-concentration-h900-falsifier
  dirty_mode: ALLOW_REPORTED
objective: One combined atom — inject a mechanism-independent scoring/decision
  seam into the existing one-snapshot EARLY campaign, add a tiny holder-concentration
  X projector, and obtain one fresh PIT scientific terminal for HOLDER_CONCENTRATION_RISK.
managed_write_set:
- docs/tasks/EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1.md
- configs/early_holder_concentration_h900_falsifier_v1.yaml
- src/solana_alpha_lab/ordinary_recent_organic_pressure_h900_audition.py
- src/solana_alpha_lab/early_holder_concentration_h900_falsifier.py
- scripts/run_early_holder_concentration_h900_falsifier.py
- tests/test_ordinary_recent_organic_pressure_h900_audition.py
- tests/test_early_holder_concentration_h900_falsifier.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/early_holder_concentration_h900_falsifier/a1_acceptance_v1.json
- docs/evidence/early_holder_concentration_h900_falsifier/a1_runtime_receipt_v1.json
- docs/evidence/early_holder_concentration_h900_falsifier/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_holder_concentration_h900_falsifier/a1_delivery_independent_review_v1.json
- docs/evidence/early_holder_concentration_h900_falsifier/a1_delivery_factory_fit_v1.json
- docs/reports/early_holder_concentration_h900_falsifier/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
- CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION
- CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT
- DOTENV_READ
- API_KEY_IN_URL_LOG_RECEIPT_OR_GIT
- RAW_BODY_CONTAINS_CREDENTIAL
- JUPITER_EXECUTE_OR_BUILD
- TAKER_OR_SIGNER_SUPPLIED
- WALLET_SIGNER_TRANSACTION_OR_DEPLOYMENT
- RETRY_OR_FALLBACK
- CALL_CAP_EXCEEDED
- PACE_BELOW_THREE_SECONDS
- SECOND_PROVIDER_OR_PAID_PLAN
- PRIOR_MINT_REUSED
- ABSENT_AS_ZERO
- NEW_CAMPAIGN_RUNTIME_CLONE
- FACTORY_RUNNER_CHANGE
- THRESHOLD_QUARTILE_LOO_OR_SMOOTHING_RESCUE
- SECOND_CAPTURE_WINDOW
- HARNESS_OR_PROCESS_ATOM
- RESEARCH_SCREEN_SCHEMA_OR_LEDGER
- CAUSAL_TRANSFORM_OR_SMA_EWMA
- DISCOVERY_OR_A7_ACTIVATION
- VPS_OR_SHADOW_OR_MICRO_LIVE
- ALPHA_OR_NETRETURN
- PREPARATORY_ONLY_READY_FOR_LIVE_PR
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-ICP-FREEZE-AND-MATURITY-BRANCH-CLOSE-001
  - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
  - MODULE-EARLY-STRUCTURAL-BACKING-PIT-COMMISSIONING-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - EVIDENCE-EARLY-VALUATION-LIQUIDITY-DIVERGENCE-ACCEPTANCE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v10.yaml
    - configs/early_icp_freeze_and_maturity_branch_close_v1.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_completion_evidence_v1.json
    - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_independent_review_v1.json
    - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
    - docs/evidence/early_structural_backing_pit_commissioning/a1_acceptance_v1.json
---

# EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1

## Entry Gate

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` for contract + reusable scoring seam /
scientific validity. Routine implementation thereafter may use the working model.

`ROADMAP_VERDICT=KEEP`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at the live-phrase checkpoint and at
PR/CI/merge after the scientific terminal.

Owner selection of **one bounded product/research atom** after completed
DESIGN_ONLY screening. Do not open a process/harness atom. Do not open a
preparatory capability atom.

`strongest_rejected_alternative`: treat the gap as a whole
`PROSPECTIVE_EARLY_ONE_SNAPSHOT_FALSIFIER_RUNTIME`, then a later holder atom.
Rejected because `run_campaign()` already owns recent → exclude → freeze →
seasoning → bulk search → injected `project_x` → BUY → H900 → SELL → raw.
`early_structural_backing_pit_commissioning` already wraps it. Building a
second campaign engine is preparatory-only Factory waste.

`ADOPTION_ROUTE=ADOPT_RUN_CAMPAIGN_WRAP_PROJECT_X_AND_SCORE_FN_BUILD_NO_NEW_RUNTIME`

Named reusable gap for this consumer:

```text
EARLY_H900_INJECTABLE_SCIENTIFIC_DECISION_SEAM
```

Do not rename the organic module. Do not generalize to DAG/platform/plugin.
Do not migrate/rewrite historical #189 merely to manufacture reuse.

If implementation begins duplicating cohort/search/BUY/H900/SELL loops in a
bespoke `run_holder_concentration_campaign`, stop with
`FACTORY_LEVERAGE_REPLAN`.

## Atom identity

```text
DECISION_DELTA: injectable score_fn seam on the existing one-snapshot campaign
  plus a tiny holder-concentration X projector
UNCERTAINTY_REMOVED: whether higher observable topHoldersPercentage at EARLY
  decision time predicts worse executable H900 quote recovery
CAPABILITY_OR_EVIDENCE: one fresh PIT scientific/data terminal; the seam is
  closed only together with this consumer
STOP: exact owner provider phrase before first live byte; exact merge phrase
  after exact-head CI; confirmatory OOS is owner-only
NEXT: CLOSE_HOLDER_CONCENTRATION_FAMILY | INVALID_EVIDENCE_REPLAN |
  EARN_ONE_CONFIRMATORY_FRESH_OOS
REPLAN_TRIGGER: preparatory-only READY_FOR_LIVE; duplicated campaign runtime;
  post-Y rescue; second provider; semantic X/Y/scorer change after first
  market byte
```

This atom is FAIL/preparatory-only if it ends merely with `RUNTIME_READY`,
`SCORER_READY`, or `READY_FOR_LIVE`. Do not open a PR whose only product claim
is `READY_FOR_LIVE`.

---

## Owner decision

Test whether higher observable top-holder concentration at EARLY decision time
predicts worse executable H900 quote outcome.

## Product outcome

One fresh, PIT-safe scientific answer **plus** the minimum reusable
decision/scoring seam necessary to obtain it without another
hypothesis-specific campaign clone.

## Named consumer

Current: `HOLDER_CONCENTRATION_RISK`.

Existing evidence of the same architectural pressure:

- structural backing already injects a different X into the shared campaign;
- #189 separately had to implement sign-only Kendall rather than use the
  legacy positive/quartile/LOO scorer.

## Frozen scientific contract

### Population

`ICP-EARLY-PUMPFUN-V1`. Fresh mints only. Exclude every previously consumed
research mint, including #189. Existing EARLY liquidity/age/project eligibility
remains applicable; do not alter ICP to improve yield. Cohort remains the
existing ordinary EARLY campaign shape (`24`) unless live Git proves that
number is no longer canonical.

### X

Exactly `X = audit.topHoldersPercentage` from the **single** decision-time
bulk search snapshot. Jupiter scale observed/documented as 0–100.
`ABSENT = MISSING`, never zero.

Forbidden: `holderCount` surrogate; `devBalance` combination; rank transform;
threshold; quartile; smoothing; R1/delta; wallet attribution.

Preserve limitation: Jupiter semantics do not establish that pool/curve/system
accounts are excluded from `topHoldersPercentage`. This limits interpretation;
it does not authorize another data/provider branch.

### Mechanism

Higher observable concentration of transferable supply among top holders
creates greater latent supply-overhang / coordinated-dump capacity and may
therefore predict worse subsequent executable H900 outcome.

Do not claim holder identity, human ownership, sybil resistance, scam
classification, or malicious intent.

### Y

Existing quote-only: BUY quote at decision → SELL quote at H900 → recovery.
No taker/build/execute/wallet/signer/transaction.

### Expected direction

`tau_b(X, Y_H900) < 0`

### Evidence-yield floor

Existing ordinary EARLY floors: min decision-time eligible `18`, min rankable
H900 `14`. If live repository contracts prove a newer canonical floor, use that
exact existing floor and report the patch before execution.

### Scientific terminals

```text
eligible/rankable below frozen evidence floor
OR X semantics/data invalid
OR degenerate tau (None)
→ INVALID_EVIDENCE_REPLAN
```

```text
valid sample AND tau_b >= 0
→ CLOSE_HOLDER_CONCENTRATION_FAMILY
```

```text
valid sample AND tau_b < 0
→ EARN_ONE_CONFIRMATORY_FRESH_OOS
```

First negative-sign sample is **not alpha** and does not authorize
Strategy/Shadow. No p-value/significance claim is required from this cheapest
directional falsifier.

### No-rescue

After observing Y, forbidden: threshold search; quartiles; excluding the low
concentration cluster; log/rank X rescue; alternative decision age; smoothing;
second snapshot; alternate H900 horizon; second provider; wallet graph; dev
fields; changing evidence floor.

---

## SSD — minimum reusable patch

Reuse existing `ordinary_recent_organic_pressure_h900_audition.run_campaign`.
Preserve default behavior of all existing consumers.

Allowed reusable core delta: the campaign may receive a supplied scientific
decision/scoring function rather than always invoking legacy `score_audition`.
When no new scorer is supplied, existing organic-pressure semantics remain
unchanged. Existing structural-backing wrapper must continue to behave as
before. Test this directly.

Plus only the minimum policy-validation seam so the current hypothesis is not
forced to declare unused legacy `tau>=0.20 + quartile + LOO` fields.

Holder-specific code is a small X projector/policy wrapper analogous in role
to structural backing. It may validate launchpad/project predicate, ICP
age/seasoning, liquidity floor, timestamp PIT, audit mapping, and finite X in
0..100. It must not contain recent/search orchestration, sleeps, quote loops,
H900 scheduling, raw persistence, provider pacing, or duplicate campaign
runtime.

Scoring: implement/reuse a narrow sign-only Kendall decision function over
standard rankable `{x,y}` rows. Do not put holder-specific field knowledge
into the scorer. Prefer existing `_kendall_tau_b`. Do not perform a broad
statistics refactor.

---

## Delivery / market ordering

```text
exact task contract
→ smallest implementation
→ targeted compatibility/scientific tests
→ pre-live semantic review as actually required
→ STOP once for exact owner provider phrase
→ one fresh market window
→ scientific/data terminal
→ FINISH evidence/Catalog/generated/readout
→ PR / exact-head CI
→ exact merge gate
→ read-back
```

Freeze a tested pre-live implementation before asking for the phrase; semantic
X/Y/scorer changes after first market byte invalidate the run. Do not create
completion/readout/Factory-Fit bureaucracy around a mechanical five-second
fail. Provider call remains separately owner-gated.

## External boundary

Prepare but do not consume an exact owner phrase for: one Jupiter Free-key
read-only campaign; local process-environment API key only; no `.env` read;
key in `x-api-key` header only; `/recent`; one bulk `/tokens/v2/search`;
quote-only `/swap/v2/order`; no `/build` or `/execute`; no taker; no
wallet/signer/transaction; cash cap `$0`; call cap `60`; global provider pace
`>=3s`; retry `0`; fallback `false`; second provider forbidden; all prior
consumed mints excluded.

Stop for the exact owner phrase only when local code/contract/test state is
ready.

---

## SCREENING_PROVENANCE

Compact sanitized post-#189 DESIGN_ONLY batch. This is **not** a new lifecycle
registry and does not pretend to solve `RESEARCH_SCREEN_MEMORY_GAP`.
No schema/catalog object per screened candidate.
`RESEARCH_SCREEN_MEMORY_GAP` remains `WATCH_ONLY`.
`Y_INSPECTED_DURING_SELECTION=false`.

| candidate | decision | summary |
|---|---|---|
| `COHORT_CROWDING` | KILL | `/recent cap=30 / biased coverage` |
| `PARTICIPATION_BREADTH` | KILL | joint 16/24 |
| `HOLDER_ACQUISITION_VELOCITY` | KILL | effective holder-count degeneracy |
| `TRADE_SIZE_ASYMMETRY` | KILL | joint 16/24 |
| `HOLDER_GROWTH` | KILL | semantics/noise |
| `DEV_RETAINED_SUPPLY_RISK` | KILL | 4/24 |
| `SERIAL_DEPLOYER_RISK` | KILL | `devMints` semantics mismatch |
| `PRE_POOL_DELAY` | KILL | constant |
| `HOLDER_CONCENTRATION_RISK` | SURVIVED_SCREEN | coverage + distinctness on R0 |

## Explicitly out of scope

Harness/process fast path; change to process kill-switch; dedicated
research-memory subsystem; research-screen schema; causal transform/SMA/EWMA
grammar; prospective observation tape; Discovery/A7; Helius/transaction layer;
wallet graph; new provider; generic feature store; generic experiment
platform; Strategy/Bot/Shadow; alpha/NetReturn/micro-live.

`CAUSAL_TRANSFORM_GRAMMAR_NOT_CURRENTLY_EXPRESSIBLE` remains `WATCH_ONLY`.

## DoD

1. existing shared one-snapshot EARLY runtime remains backwards compatible;
2. no new duplicated campaign orchestration is introduced;
3. holder X semantics/missingness/PIT are tested;
4. frozen sign-only negative Kendall rule is tested;
5. one fresh prospective market window produces a typed scientific/data terminal;
6. exact live evidence is retained safely;
7. no rescue or adjacent scope is opened;
8. normal Delivery Harness closeout/CI/merge happens only after the substantive terminal.

`NEXT` after terminal:

- `CLOSE_HOLDER_CONCENTRATION_FAMILY` → stop, no rescue;
- `INVALID_EVIDENCE_REPLAN` → distinguish data/provider vs reusable-runtime defect, no automatic retry;
- `EARN_ONE_CONFIRMATORY_FRESH_OOS` → stop and return to owner. Confirmatory run must use this same implementation with **new production/orchestration code = 0**.

Do not start confirmatory OOS automatically.
