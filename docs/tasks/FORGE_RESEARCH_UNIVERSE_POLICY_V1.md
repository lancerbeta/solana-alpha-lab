---
task_id: FORGE_RESEARCH_UNIVERSE_POLICY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-03'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
- DIRECT_CODEX_DELIVERY
required_review_roles:
- CODE_REVIEWER
- GOAL_DOD_CRITIC
- ARCHITECTURE_CRITIC
- OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3c6ee4aca8614e91238fabdae264f03c68269fea
  expected_upstream: origin/main
  expected_upstream_oid: 3c6ee4aca8614e91238fabdae264f03c68269fea
  expected_branch: cursor/forge-research-universe-policy-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  One Forge research-universe policy so new Forge operations admit only
  observations that meet the owner minimum holders and liquidity at decision
  time, changed by preview/apply/readback without a Git PR, while frozen
  results, budgets and recovery keep their exact policy binding.
managed_write_set:
- docs/tasks/FORGE_RESEARCH_UNIVERSE_POLICY_V1.md
- docs/contracts/forge_research_universe_policy_v1.md
- src/solana_alpha_lab/factory/hfic_research_universe_policy.py
- src/solana_alpha_lab/factory/research_store.py
- src/solana_alpha_lab/factory/scientific_eligibility_projection.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_representation_ladder.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_evidence_identity.py
- scripts/hypothesis_forge.py
- .agents/skills/hypothesis-forge/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- configs/hypothesis_forge_independent_critic_v1.yaml
- tests/test_forge_research_universe_policy_v1.py
- catalog/schemas/forge_research_universe_policy_v1.schema.json
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/FACTORY_SEMANTIC_MAP.md
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/forge_research_universe_policy_v1/a1_delivery_completion_evidence_v1.json
- docs/evidence/forge_research_universe_policy_v1/a1_delivery_independent_review_v1.json
- docs/evidence/forge_research_universe_policy_v1/a1_delivery_factory_fit_v1.json
- docs/evidence/forge_research_universe_policy_v1/a1_semantic_premise_packet_v1.json
- docs/reports/forge_research_universe_policy_v1/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_IF_HOLDER_OR_LIQUIDITY_FIELD_IS_NOT_THE_CANONICAL_PIT_POINT
- STOP_PROVIDER_RPC_OR_NEW_COLLECTION
- STOP_WALLET_SIGNER_OR_REAL_TRADE
- STOP_C5_OR_PROTECTED_CORPUS_READ
- STOP_SCIENTIFIC_QUOTA_RESET_OR_NEW_JOURNAL
- STOP_BASE_X_REDEFINITION_OR_CORPUS_REWRITE
- STOP_SECOND_LIVE_CONFIG_IN_GIT
- STOP_PRODUCTION_ACTIVATION_OR_MAIN_LOOK
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids:
  - MODULE-FACTORY-V1-RESEARCH-STORE-001
  - DOC-HYPOTHESIS-FORGE-OPERATOR-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - src/solana_alpha_lab/factory/hfic_memory_policy.py
    - src/solana_alpha_lab/factory/scientific_eligibility_projection.py
    - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
    - docs/contracts/forge_temporal_holder_point_feature_v1.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# FORGE_RESEARCH_UNIVERSE_POLICY_V1

ENTRY_DECISION: START_AS_WRITTEN. MODEL_EFFORT: SOL_XHIGH.
Factory Fit: FULL_REVIEW. SPEC_ROUTE: DESIGN_SPEC (contained here; public
semantics also land in `docs/contracts/forge_research_universe_policy_v1.md`).
Reuse: WRAP `hfic_memory_policy` preview/apply/readback and the canonical PIT
point selector. No new store, journal, provider, or predicate engine.

## Task outcome

- DECISION_DELTA: new Forge search uses an owner-operated market-scale
  filter over existing BASE_X; 5k→20k is an activation, not a code change
  and not a new scientific look.
- UNCERTAINTY_REMOVED: whether population membership, frozen identity,
  replay and budgets share one policy binding, or a fixture-only mask can
  pass while production composition stays unfiltered.
- CAPABILITY_OR_EVIDENCE: one ResearchStore profile, public preview/apply/
  readback, and the same binding on every active Forge consumer found at
  Entry and during the atom.
- Consumer: ordinary Forge owner path (preflight, discovery, freeze, Critic,
  replay, restart). Not strategies, bots, or collection.
- Cheapest falsifier: a production-composed run admits a row below the
  active minimum, or a test passes only because it built the mask itself.
- STOP: exact-head CI plus `ready_for_owner_phrase=true`. No merge, no
  production activation, no MAIN look.
- NEXT: separate bounded OPERATE — preview 50/5000, owner-authorized apply,
  cold readback — only after this atom's merge.
- REPLAN_TRIGGER: canonical PIT fields are not holder count and liquidity
  USD; a second live config appears necessary; repair needs a new store,
  provider, or BASE_X rewrite; the same production binding stays broken
  after one authoritative-owner repair.
- Evidence budget: disposable production-shaped publish/import, public CLI
  scenario including 5k→20k, restart and rollback/retry. Real-data proof is
  feature/metadata only on C1–C4 when those reads already exist locally.
- Product horizon / capability radar NOW: NONE. WATCH: size-aware execution
  feasibility after a named surviving candidate.

## Owner outcome

Кузня не расходует поиск на токены вне выбранного владельцем минимального
масштаба. Владелец меняет минимум holders и liquidity обычной операцией,
без разработки, Git PR и пересборки корпуса. Исторические результаты,
бюджеты и восстановление остаются корректными.

First profile, owner product constraints, not a return optimum:

- `min_holders = 50`
- `min_liquidity_usd = 5000`
- both required at the decision time of each frozen request
- confirmed fail excludes the observation from the research population
- unknown stays unknown
- policy applies to new Forge operations, not automatically to strategies
  or bots

Changing 5000 → 20000 is the same capability. A new filter type is not.

## Non-goals

Quote/RPC adapter, new collection, wallet/signer, real trades, new
service or database, generic rule DSL, hypothesis generator, harness
cleanup, corpus relabel, BASE_X change, new first-passage decision model,
recompute of prior scientific results. Do not promise provider or storage
savings. Git examples are not active settings. No second live YAML beside
ResearchStore.

## Data and PIT

Sequence stays
`collection → raw/PIT → publish/import → existing BASE_X → market policy
at decision time → bounded discovery → candidate/critic → frozen
experiment/OOS → execution evidence → separately authorized trading`.

The profile is a filter view, not a copied dataset and not a replacement
for scientific eligibility.

`E_p(m,t) = existing_population_eligibility(m) AND holder_count(m,t) >= p.min_holders AND liquidity_usd(m,t) >= p.min_liquidity_usd`

Only values the canonical PIT selector treats as available at t. No
end-of-life, path-max, late snapshot, or unconfirmed last-known value.
Do not change lateness tolerances or move a nominal buy earlier than data
availability. A fail at one decision time does not ban a later allowed
decision time. The profile does not create extra decision times. First
crossing is a different experiment, not a fallback.

Statuses: `PASS` all required checks known and passed; `FAIL` at least one
confirmed failure; `UNKNOWN` no confirmed fail and at least one required
check unknown. One terminal status. Status counts partition; reason counts
may overlap. Observed zero is not missing.

`N_base = N_pass + N_fail + N_unknown`. Only PASS enters the target search.
UNKNOWN stays visible. An integrity blocker blocks the scientific verdict;
it is not "the market is bad". Membership is fixed before any future
outcome is read. Later death, route loss, or missing exit stays inside the
admitted set. Baseline and comparison groups are built inside one `E_p`.
Do not compare a filtered matched set with unfiltered BASE_X.

## Single owner

Git owns code, schema, field meaning, validator and runbook. Existing
ResearchStore owns operational profile definitions, activations and
receipts, using the append-only `RESEARCH_ARTIFACT` pattern of
`HFIC_SEARCH_MEMORY_POLICY` with a distinct artifact kind. Frozen
experiment/result owns the exact applied snapshot. Profile semantic hash
is independent of activation revision, reason and timestamp. Re-applying
the same values is idempotent readback, not a new scientific identity.
Unknown keys, NaN, Infinity, negatives and false precision are rejected.
Normalization must not silently round a scientifically meaningful
difference.

Frozen query, context packet, saved result, candidate, Critic and
downstream experiment receive that same binding. Do not copy the
definition into independently editable configs.

## Owner operation

Requirements for the new public interface. Not already-existing commands.

- Status: active profile values and identity, pending operation,
  basis/cohorts, current-run policy binding, next action.
- Preview: two numbers; schema/PIT/basis/holdout checks; eligibility,
  counts, missingness and coverage delta only; immutable proposal with
  expected current revision. No future price, return or outcome. Development
  scope C1–C4; C5 excluded until a value loader exists. Respect existing
  feature-preview admission and budget. An exhausted preview budget is not
  bypassed by a new utility.
- Apply: separate exact owner authorization. Check proposal hash and
  expected revision/basis, then atomically append. Stale or wrong proposal
  writes nothing. Replay of the same apply is idempotent readback.
- Readback: a new ordinary process reads the active profile and the
  effective policy of the future run. The apply response is not product
  readback.
- Pending Forge operation: finish it or stop it under the existing pending
  policy, then apply. No change queue and no hot-swap mid-run.

Example: «Для новых запусков Кузни holders от 50, ликвидность от $20k;
текущий frozen эксперимент не менять».

## Identity, budgets, history

The profile semantic hash enters affected search/query/cache/replay
identity and the scientific definition of the population. A name is not
enough. Changing the default does not rewrite an old run's frozen recipe.
5k→20k is not new market evidence and does not reset MAIN, adaptive or
focus budgets. Use the existing journal. No extra look for rename,
revision timestamp, restart, or A→B→A. Threshold selection after seeing
returns is adaptation, not an independent test. Exact match of a prior
answer requires the same population semantics. A→B→A with the same
data/spec returns to the previous A science identity and existing result;
activation history keeps every change.

## Entry

Checked on this worktree, base `3c6ee4aca8614e91238fabdae264f03c68269fea`
(`Merge pull request #368`). The design note's open-PR / pre-merge main
`94b284534b6ad55a95002d51b9d04b4a5ced6bde` is stale. #368 is merged.

Semantic routes actually resolved, not treated as authority:

- `SEM-HYPOTHESIS-FORGE` → operator doc, skill, trajectory contract,
  `configs/hypothesis_forge_independent_critic_v1.yaml`
- `SEM-PRIOR-WORK` → `research_store.py`
- `SEM-MARKET-DATA-FEATURES` → common market feature surface and market
  context definition
- `SEM-LIVE-EVIDENCE-TO-FORGE` → cohort release into Forge, source of
  rows, not the policy owner

Code references for the owner path:

- `hfic_memory_policy.py` — preview/apply/readback precedent. Different
  estimand. Do not overload it.
- `scientific_eligibility_projection.py` and `hfic_grounded_discovery.py`
  — BASE_X stays the population owner. Policy is a later view.
- `hfic_temporal_discovery.py` — PIT point selector.
  Entry candidate fields: `FIELD-HOLDER-COUNT-001` and
  `FIELD-LIQUIDITY-USD-001`. Confirm during implementation that liquidity
  is not mcap, volume, or executable depth. If it is, stop
  `STOP_IF_HOLDER_OR_LIQUIDITY_FIELD_IS_NOT_THE_CANONICAL_PIT_POINT`.
- Public CLI in `scripts/hypothesis_forge.py`: `preflight`, forge input /
  run, `discovery-preview`, `discovery-execute`, `freeze`, and the
  memory-policy status/preview/apply shape to copy, not to reuse.

Не считать приведённый в spec список consumers исчерпывающим: executor
обязан получить фактический consumer/write-set из current semantic routes
и code references; найденный active public path становится частью DoD
автоматически.

The YAML `managed_write_set` is the Entry snapshot. A newly found active
public path is added to that set in this same atom before it is edited.
Historical evidence pins and unrelated harness files stay out.

Still unread at contract freeze, and not a reason to launch: live runtime,
eligible counts C1–C4, remaining scientific/preview budget, pending
operations, C5 role, intended notional. Zero eligible population is a
diagnostic, not a reason to lower thresholds. Prior C1–C4 exposure stays
exploratory. Old coverage numbers and any assumed C5 import date do not
authorize a start.

## Vertical Capability Repair Loop — обязательный execution contract

Реализация считается завершённой только после прохождения того же owner
scenario end-to-end через реальные production bindings.

1. Trace first: до mutation воспроизвести текущий owner path и определить
   все authoritative consumers policy.
2. Locate: при каждом failure находить самый ранний сломанный production
   boundary; не латать downstream symptom.
3. Repair owner: менять authoritative owner один раз; derived
   views/adapters только получают эту семантику.
4. Propagate: в этом же atom обновить все реально затронутые public
   entrypoints, schemas/contracts, Catalog/generated views, Prompt A/
   freeze/Critic/replay/operator path.
5. Validate same path: после каждой material repair повторить исходный
   end-to-end owner scenario, включая 5k→20k, restart и rollback/retry.
6. No test-only wiring: acceptance test не имеет права вручную собирать
   policy/mask/result или обходить production composition, если production
   consumer получает их другим путём.
7. No deferred correctness: найденный в пределах заявленного owner path
   broken binding, bypass, stale/recovery defect или semantic inconsistency
   входит в этот atom. Follow-up допустим только для явно non-goal
   capability.
8. Finish condition: новый чистый процесс без знания реализации способен
   выполнить owner scenario по canonical route; все active consumers либо
   применяют exact policy binding, либо дают typed blocker. Green unit/CI
   без этого недостаточен.

## Acceptance / DoD

Mandatory end-to-end scenario on disposable production-shaped data:

`production publish/import binding → public policy preview → authorized fixture apply → cold status/preflight → ordinary query → baseline/matched → saved result → Prompt A/freeze/Critic/owner → registered replay → restart`

Then change 5k→20k through that same interface, without a Git/code change.
Replay of the first result stays on 5k. A→B→A grants no new quota.

| Group | Prove |
|---|---|
| Thresholds | 49/50/51 holders; liquidity below/equal/above; 5k and 20k share one code path |
| PIT | A later value does not admit an earlier entry; no future loader; per-field lineage; no false time precision |
| Missingness | Zero is not missing; mixed fail/unknown has one status; status totals add up |
| Denominator | Baseline/matched/complement use one policy; future dead/no-route/missing Y does not shrink the admission denominator |
| No bypass | SIMPLE/COMPOUND and a direct public launch cannot skip the gate; an unsupported consumer stops with a typed blocker |
| Integrity | Substituted hash/definition/member binding is rejected before outcome/MAIN; an empty or wrong profile does not drop the filter |
| History | Old V1–V5/spec digests stay unchanged; an old frozen result does not inherit the current default; the new result shows the new policy |
| Recovery | A stale preview writes nothing; crash/retry does not create a second apply or look; cold readback restores policy and result |
| Budgets | Apply, rename, capability merge and A→B→A do not reset quota; feature previews keep existing accounting |
| Holdout | C5 or any protected corpus is unavailable to preview, loader and derived output; activation does not change evidence role |
| Downstream | Experiment/replay uses the exact policy or typed-blocks; it does not silently keep the legacy population |
| Owner UX | One understandable operation; values, delta, claim limits, next action; no hand-edited SQL/JSON/multiple configs |

Real-data compatibility, only if already-local permitted feature/metadata
reads of C1–C4 exist: no returns, MAIN, C5, provider calls, or production
activation. Show ResearchStore scientific inventory/budget unchanged in
that scope. If those reads are absent, do not replace the proof with
synthetic counts presented as real.

Review follows the current harness. Code, architecture/science semantics
and owner-operability are required. Evidence is the scenario, results,
hashes and fixture references.

## Rollout

One PR for the capability, tests and semantic propagation. Merge is a
separate exact owner phrase after machine readiness. Merge does not
activate the policy and does not start MAIN.

First operation, after post-merge readback, is a separate bounded OPERATE.
If the basis moved, repeat the feature-only preview. Later runs snapshot
the active policy. 5k→20k repeats the same operation. Historical
operations read their own bindings.

Policy failure: block new affected research; keep collection, history and
replay. Do not fall through to unfiltered. Parameter rollback activates
the previous profile on the same guarded path. With no previous safe
profile, pause new runs. Code rollback before persisted artifacts is an
ordinary revert. After persisted artifacts, keep a reader or repair
forward.

No automatic promotion, strategy change, or risk change. A future open
position follows its frozen exit/risk policy.

## Science consequence

The old question `holder_count(Y900)>=3` is not the universe
`holder_count(Y900)>=50`. Do not launch it and do not silently edit the
old preregistration. Keep the original wording and prior exposure. Record
applicability to the new owner scope separately, not as a negative market
result. Read back the real old run before assuming it did not execute.

The next scientific question is chosen after policy readback, not by this
atom. 50 holders / $5k does not prove low impact. Executable claims need
intended notional, cost/impact constraints and entry/exit evidence through
existing capabilities. This atom builds no provider and no execution
engine.
