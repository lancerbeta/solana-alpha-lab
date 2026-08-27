---
task_id: HYPOTHESIS_FORGE_OPERATIONAL_CLOSURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-26'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b559646ebf62583d357a3f3bb349695cbec320dc
  expected_upstream: origin/main
  expected_upstream_oid: b559646ebf62583d357a3f3bb349695cbec320dc
  expected_branch: cursor/hypothesis-forge-operational-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Close the Hypothesis Forge operational loop so one slash invocation
  resolves one store, commissions Fast Lane offline when safe, freezes
  content-stable candidates, runs isolated Critic, persists the full cycle in
  Research Data Plane, and refuses same-evidence shopping.
managed_write_set:
- docs/tasks/HYPOTHESIS_FORGE_OPERATIONAL_CLOSURE_V1.md
- delivery-harness/harness.yaml
- configs/hypothesis_forge_independent_critic_v1.yaml
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- catalog/schemas/hypothesis_forge_draft_v1.schema.json
- catalog/schemas/hypothesis_critic_result_v1.schema.json
- catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json
- catalog/schemas/hypothesis_forge_synthesis_handoff_v1_1.schema.json
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- catalog/schemas/hypothesis_forge_synthesis_handoff_v1.schema.json
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_identity.py
- src/solana_alpha_lab/factory/data_root.py
- src/solana_alpha_lab/factory/prior_work.py
- src/solana_alpha_lab/factory/commissioning_proof.py
- src/solana_alpha_lab/factory/document_runner.py
- scripts/hypothesis_forge.py
- scripts/hypothesis_fast_lane.py
- schemas/research_memory_projection_v1.sql
- .agents/skills/hypothesis-forge/SKILL.md
- .agents/skills/independent-hypothesis-critic/SKILL.md
- .cursor/commands/hypothesis-forge.md
- .cursor/commands/independent-hypothesis-critic.md
- tests/test_hfic_operational_closure_v1.py
- tests/test_hfic_identity.py
- tests/test_hfic_preflight.py
- tests/test_hfic_session.py
- tests/test_hfic_cli.py
- tests/test_hypothesis_forge_independent_critic_v1.py
- tests/fixtures/hypothesis_forge/**
- catalog/query_recipes.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/hypothesis_forge_operational_closure/a1_delivery_completion_evidence_v1.json
- docs/evidence/hypothesis_forge_operational_closure/a1_delivery_independent_review_v1.json
- docs/evidence/hypothesis_forge_operational_closure/a1_delivery_factory_fit_v1.json
- .github/workflows/ci.yml
- scripts/validate_ci.py
- tests/test_ci.py
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- TWO_RUNG_LIVE_H900_V1
- PROVIDER_API_RPC_WSS
- WALLET_SIGNER_TX_OR_CASH
- AUTONOMOUS_HYPOTHESIS_GENERATOR
- AUTOMATIC_PROMOTION
- DATA_ROOT_SPLIT_BRAIN_WITHOUT_OWNER
- LIVE_COLLECTION_OR_HOLDOUT
- NEW_DEPENDENCY_OR_DEPLOYMENT
context_requirements:
  catalog_asset_ids:
  - CTRL-HYPOTHESIS-FAST-LANE-001
  - MODULE-FACTORY-V1-RESEARCH-STORE-001
  - SCRIPT-HYPOTHESIS-FAST-LANE-001
  - ADR-006-HYPOTHESIS-FAST-LANE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - ADR-006-HYPOTHESIS-FAST-LANE-001
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/hypothesis_forge_operational_closure/a1_delivery_completion_evidence_v1.json
    - docs/evidence/hypothesis_forge_operational_closure/a1_delivery_independent_review_v1.json
    - docs/evidence/hypothesis_forge_operational_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HYPOTHESIS_FORGE_OPERATIONAL_CLOSURE_V1 — PRD + SSD + EXECUTION PLAN

> **For Cursor:** REQUIRED SUB-SKILL: use the repository's canonical planning/execution, test-first, review, and guarded-merge procedures. Execute this document end-to-end. Do not stop after writing another design document.

## 0. Исполнительная команда

```text
EXECUTE HYPOTHESIS_FORGE_OPERATIONAL_CLOSURE_V1
```

Выполнить один bounded capability change от свежего `origin/main` до доказанного post-merge runtime commissioning. Владелец участвует только:

1. точной фразой разрешения merge на неизменный exact head;
2. при реальном критическом blocker из закрытого списка §3.4.

Не спрашивать владельца, какой каталог данных выбрать, что означает `SMIAL_DATA_ROOT`, какую команду запустить дальше, какой кандидат взять или создавать ли следующий PR. Все безопасные read-only/offline решения и переходы ниже разрешены этим контрактом.

---

## 1. Task Outcome Brief

### 1.1. Проблема

После merge `HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1` и `HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1` существуют правильные части, но ещё нет замкнутого эксплуатационного контура:

```text
/hypothesis-forge
→ достоверная текущая память
→ ограниченный portfolio
→ frozen candidate identities
→ независимый Critic
→ детерминированный terminal/lane
→ append-only память всего цикла
→ следующий запуск видит прошлый цикл и не повторяет его
```

Первый реальный Forge-прогон проявил gap, который уже нельзя закрыть дисциплиной пользователя:

- Fast Lane store был `healthy`, но выглядел пустым; commissioning receipt не был найден. Наиболее вероятная причина — разные resolved data roots у commissioning и Forge либо commissioning фактически не был выполнен на активном root.
- `research_memory_as_of` оказался старее доступной проектной реальности.
- выбранная гипотеза была честно убита `KILL_PREPARATORY_LOOP`, но весь portfolio и terminal не были записаны в Research Data Plane; новый чат способен повторить тот же поиск.
- human ordinals разошлись: route-fragmentation candidate фигурировал как `C3` и как `C4`, хотя schema validation прошла. Значит существующая schema проверяет форму, но не referential integrity между portfolio, selected/rejected alternative и critic handoff.
- оператор может технически повторять Forge на тех же evidence до получения приятного PASS. Это hypothesis shopping, а не исследовательский процесс.
- существующий runner-up упоминается текстом, но не имеет гарантированного frozen packet/id; recovery path не детерминирован.
- HFIC bindings пока не являются полноценными Catalog assets/query recipes, хотя это уже повторяемый consumer поиска и навигации.

### 1.2. Целевой продуктовый результат

После выполнения владелец в новом Cursor-чате вызывает только:

```text
/hypothesis-forge
```

Дальше агент без промежуточных вопросов:

1. сам находит один активный Research Data Plane root;
2. доказывает или безопасно выполняет offline Fast Lane commissioning;
3. получает небольшой deterministic context/prior packet, не сканируя пол-репозитория;
4. создаёт 4–6 причинно различных кандидатов;
5. валидатор присваивает стабильные content-based IDs и блокирует противоречивые ссылки;
6. независимый Critic получает только frozen packet в изолированном контексте;
7. deterministic finalize сохраняет cycle, все candidates, Critic receipt, решения и единственный NEXT в append-only RDP;
8. повторный запуск на тех же evidence/focus возвращает ранее полученный результат или честный STOP, а не генерирует новый portfolio;
9. ни routine hypothesis generation, ни Critic, ни сохранение результата не создают branch/PR/CI.

Git остаётся фабрикой: код, схемы, prompt/skill versions, гардрейсы, query recipes и promotion artifacts. Nightly hypotheses, killed ideas, sessions, metrics и artifacts остаются data-plane records вне Git.

### 1.3. Outcome terminal

Единственный успешный terminal этого capability atom:

```text
HFIC_OPERATIONAL_LOOP_PROVEN
```

Он допустим только после merge и post-merge proof из §13. До него терминалы: `DESIGN_ONLY`, `IMPLEMENTED_NOT_MERGED`, `MERGED_NOT_COMMISSIONED` либо named blocker.

### 1.4. Named consumers

- владелец: вечерний explicit `/hypothesis-forge`;
- `.agents/skills/hypothesis-forge/SKILL.md`;
- `.agents/skills/independent-hypothesis-critic/SKILL.md`;
- `hypothesis_fast_lane` / ResearchStore / DuckDB prior-work projection;
- future scheduler/autonomous generator, но только как будущий consumer этого стабильного protocol — не scope текущего атома;
- lane classifier и будущий no-Git experiment runner после Critic PASS.

### 1.5. Decision unlocked

Можно ли безопасно использовать ручную Forge как MVP без повторных чатов «пока не найдётся хорошая гипотеза»? После этого атома — да: один explicit invocation становится bounded, remembered, resumable и fail-closed. Scientific PASS всё ещё не гарантируется и не является KPI.

---

## 2. Product requirements (PRD)

### PR-01 — Один owner action

Обычный happy path начинается одним `/hypothesis-forge` и заканчивается одним terminal + одним NEXT. Запрещены промежуточные просьбы владельцу:

- выставить/объяснить `SMIAL_DATA_ROOT`;
- отдельно вызвать commissioning;
- вручную скопировать packet Critic;
- выбрать candidate/runner-up;
- сохранить результат;
- перезапустить в новом чате после KILL.

Recovery command может существовать для аварии, но не быть happy path.

### PR-02 — Commissioning прежде творчества

Forge не имеет права строить portfolio, пока preflight не докажет `NO_GIT_FAST_LANE_PROVEN` на том же resolved store, куда будет записан session.

Признак commissioning — не существование каталога и не зелёные unit tests. Нужен содержательный receipt в RDP, привязанный как минимум к:

- `HYPOTHESIS_FAST_LANE_OFFLINE_V1`;
- `DATASET-MANIFEST-FAST-LANE-COMMISSIONING-001`;
- completed run, hypothesis/version, events, metric, evidence binding и retrievable result artifact;
- полному passport/integrity proof;
- `provider_calls=0` и no-Git proof.

Технический CLI terminal `COMMISSION_OFFLINE_OK` можно нормализовать в owner/preflight terminal `NO_GIT_FAST_LANE_PROVEN`; исторический payload не переписывать.

Если ни один допустимый root не commissioned, preflight сам выполняет accepted offline commissioning на выбранном root и повторяет proof. Это разрешено без owner approval, потому что provider/cash/wallet/Git mutations равны нулю.

### PR-03 — Один data-root resolver, без split brain

Все Fast Lane/HFIC команды используют одну библиотечную функцию разрешения root. Нельзя дублировать логику в skill или shell.

Проверять только bounded candidates:

1. явный `--data-root`, если передан внутренним recovery flow;
2. абсолютный валидный `SMIAL_DATA_ROOT`, если установлен;
3. канонический default `<repo>/local/factory_v1/data_plane`.

Политика:

- ровно один candidate содержит валидный commissioned store → использовать его;
- ни один → выбрать env root, если валиден, иначе default; commission offline;
- два идентичных/replay-equivalent stores → выбрать env root, иначе default, и вернуть duplicate receipt без копирования;
- два разных непустых commissioned stores → `DATA_ROOT_SPLIT_BRAIN`; не объединять и не терять события автоматически;
- symlink root, path outside authorized local data scope, broken manifests или immutable conflicts → fail closed.

Не писать physical path в Git, Catalog, Parquet payload, owner report или telemetry. В runtime receipt использовать только `data_root_instance_fingerprint`/`store_inventory_digest` и logical URIs. Не использовать Google Drive sync folder как live root.

### PR-04 — Детализированная, но ограниченная Forge

Оставить творческую абдукцию модельной. Детально кодировать только стабильные проверки вокруг неё.

Один session:

- 4–6 candidates;
- один preselected candidate;
- один predeclared runner-up reference;
- одна Critic evaluation;
- максимум одна bounded revision без смены mechanism и без новых outcomes;
- ноль experiment/provider/holdout actions;
- ноль автоматических переходов к runner-up после KILL.

Forge quality измеряется не PASS rate, а novelty, falsifiability, executable-truth proximity, information value и памятью отрицательных результатов.

### PR-05 — Стабильная идентичность, не `C1/C2/C3`

Ordinal разрешён только для отображения. Канонический `candidate_id` формируется детерминированно из нормализованного semantic definition:

```text
claim/mechanism
actor_counterparty
population
decision_timestamp/state_transition
primary_x_family
primary_y + horizon + notional
negative_control
cheapest_falsifier
```

Canonical JSON → SHA-256 → `HFIC-CAND-<stable prefix>`; длину prefix выбрать по текущей stable-id convention и зафиксировать тестом collision handling. Полный hash хранить отдельно.

ID не должен меняться от:

- порядка candidates;
- display ordinal;
- whitespace/case/punctuation, где нормализация семантически безопасна;
- generated timestamp;
- model name;
- live Git SHA сам по себе.

Нельзя «нормализовать» разные causal claims в один ID. Если collision полного canonical payload невозможен — identity equal; если prefix collision при разных full hashes — расширить prefix детерминированно либо terminal `CANDIDATE_ID_COLLISION`.

### PR-06 — Cross-reference integrity

До запуска Critic валидатор обязан доказать:

- все candidate IDs уникальны;
- selected ID существует ровно один раз;
- runner-up ID существует ровно один раз и отличается от selected;
- `CRITIC_INPUT_PACKET.selected_candidate.candidate_id` совпадает с frozen selected ID;
- `strongest_rejected_alternative` ссылается на stable candidate ID, а не свободное `C3/C4`;
- portfolio card, Pareto/ranking record, critic packet и synthesis handoff согласованы;
- packet/hash/prompts/head/evidence epoch относятся к одному session;
- post-Critic terminal и optional classifier receipt согласованы со schema policy.

Регрессионный fixture с текущим дефектом `C3` ↔ `C4` обязан падать до Critic.

### PR-07 — Evidence epoch и bounded search

Ввести `evidence_epoch_sha256`: digest material truth, реально доступной Forge до генерации.

В digest включить отсортированные canonical bindings:

- content hashes использованных Git/Catalog truth roots;
- active lifecycle/scientific terminals и closure records;
- accepted capability/query-recipe schema hashes;
- dataset manifest IDs/fingerprints, доступные для feasibility;
- prior-work projection digest, очищенный от HFIC session records текущего protocol;
- hashes targeted public research, только если оно действительно использовано.

Не включать:

- clock timestamps;
- model/effort;
- owner-facing prose;
- Git head без content binding;
- unrelated Git files;
- HFIC session/events, созданные самим поиском;
- физический data-root path.

Определить:

```text
focus_key_sha256 = SHA256(normalized OWNER_FOCUS)
search_key_sha256 = SHA256(evidence_epoch_sha256 + focus_key_sha256 + prompt_version)
```

Запись нового HFIC session не должна менять evidence epoch и сама разблокировать новый поиск.

### PR-08 — Anti-shopping budget

Минимальная политика `HFIC-V1.1`:

- `AUTO`: максимум один completed/frozen session на evidence epoch;
- всего максимум три distinct focus keys на evidence epoch;
- exact same evidence epoch + focus + prompt version → вернуть существующий session/terminal; новый generation запрещён;
- failed schema attempt: одна deterministic repair attempt; затем `HFIC_PROTOCOL_INVALID`;
- Critic `REVISE_ONCE`: один revision, затем PASS/KILL; mechanism change запрещён;
- KILL/`NO_WORTHY_HYPOTHESIS` не запускают runner-up и не разрешают новый AUTO session на тех же evidence;
- новый session допустим после material evidence epoch change либо при другом явном focus в оставшемся budget;
- prompt-version change не должна использоваться как лазейка: если evidence+focus те же, prior result всегда показывается, а новый search требует `method_change_reason` и остаётся в том же epoch budget.

Exact duplicate — hard veto. Near/semantic duplicate — deterministic component overlap receipt для Forge/Critic; код не должен притворяться полноценным semantic judge.

### PR-09 — Crash-safe/resumable

Session state machine:

```text
PREFLIGHT_PROVEN
→ DRAFT_VALIDATED
→ FROZEN_AWAITING_CRITIC
→ CRITIC_RESULT_READY
→ SYNTHESIS_COMPLETE
```

Каждый material boundary имеет immutable receipt. При повторном invocation:

- `FROZEN_AWAITING_CRITIC` → продолжить Critic с уже frozen packet, не генерировать;
- `CRITIC_RESULT_READY` → только finalize;
- `SYNTHESIS_COMPLETE` → вернуть сохранённый terminal/NEXT;
- stale/invalid pending session → named terminal и одна repair action; не создавать параллельный session.

Использовать существующий single-writer lease. Каждый append batch атомарен, replay-identical идемпотентен, conflict запрещён.

### PR-10 — Research memory включает весь portfolio

После freeze/finalize в RDP должны быть доступны:

- session/cycle metadata;
- все 4–6 candidate definitions;
- selected и runner-up links;
- Forge prompt/model/effort/head/evidence epoch/search budget receipt;
- prior queries и returned stable IDs;
- frozen critic input packet hash + retrievable bytes;
- critic model/effort/terminal/report hash + retrievable bytes;
- classifier receipt, если post-classification terminal;
- decision event для каждого candidate;
- single owner terminal + NEXT;
- authority counters и non-claims.

Нельзя хранить только hash без retrievable canonical payload. Нельзя коммитить dynamic session в Git.

### PR-11 — Decision mapping

Использовать существующие `RecordKind`; новый event store/DB не создавать.

Для selected candidate:

- `KILL_*` или `NO_WORTHY_HYPOTHESIS` → `DECISION_EVENT.decision_kind=REJECT`;
- `REVISE_ONCE` → `REVISE` до финального bounded pass;
- pre-classification/infrastructure/owner gate → `PAUSE` с typed reason;
- `PASS_FAST_LANE_READY`, `PASS_CHANGE_LANE_REQUIRED`, `PASS_DATA_OPTION_REQUIRED` → `PAUSE` с соответствующим typed reason; это readiness, не scientific proof и не promotion;
- автоматический `PROMOTE` запрещён.

Для всех non-selected candidates → `PAUSE`, reason `NOT_SELECTED_IN_SESSION`; они остаются prior work, а не считаются отвергнутыми наукой.

`CAPABILITY_GAP` добавлять только при deterministic post-classification `PASS_CHANGE_LANE_REQUIRED`. Запись gap не создаёт branch/PR автоматически.

### PR-12 — Детальная память первого прогона

После merge выполнить один backfill owner-supplied legacy cycle из уже известного первого прогона, чтобы следующий `/hypothesis-forge` не повторил его. Это runtime RDP write, не Git evidence.

Минимум зафиксировать:

1. corroborated early-wallet cohort → H900 PathRisk — selected, `KILL_PREPARATORY_LOOP`;
2. raw-concentration MEU reframe — duplicate/watch-only;
3. predecision route-fragmentation recovery — duplicate/closed + PIT unresolved;
4. creator-linked outflow withdrawal — identity/PIT unavailable;
5. organic-flow breadth divergence — prior field-yield/data infeasible.

Не выдумывать отсутствующие поля. Поддержать `LEGACY_PARTIAL` record с `source=OWNER_SUPPLIED_TRANSCRIPT`, `backfilled=true`, explicit `missing_fields`, и исключить его из требований полного critic packet. Он должен участвовать в prior/dedupe, но не маскироваться под complete commissioned session.

Route-fragmentation candidate должен получить один stable ID; исторический конфликт `C3/C4` сохранить как `legacy_aliases`, не как две гипотезы.

### PR-13 — Catalog/navigation closure

Зарегистрировать стабильные HFIC components и bindings в текущем Catalog по действующим conventions:

- HFIC session protocol capability;
- Forge draft schema;
- Critic result/session receipt schemas;
- query recipe «найти exact/related prior work»;
- query recipe «найти session по evidence epoch + focus»;
- query recipe «найти resumable pending session»;
- dependency edges к Fast Lane/ResearchStore/lane classifier/operator skills;
- lifecycle status и owner/consumer links.

Generated Catalog files, manifest, edges и `docs/PROJECT_MAP.md` обновлять только canonical generator/harness command. Не редактировать generated outputs вручную. Не внедрять RAG, embeddings или graph DB: при текущем объёме Catalog + DuckDB exact/component search достаточно.

### PR-14 — Routine no-Git fence

Каждый `/hypothesis-forge` session делает before/after snapshot:

- HEAD;
- symbolic ref;
- index/worktree;
- refs digest;
- composite SHA.

Finalization запрещён, если runtime мутировал Git. Runtime CLI не запускает branch/PR/full CI. CI используется один раз для capability change в этом плане и позже только для реального code/schema/prompt capability change или promotion.

### PR-15 — Honest terminal semantics

Владелец получает по-русски только:

- что случилось;
- один canonical terminal;
- один NEXT;
- краткий receipt (`session_id`, stable candidate ID, evidence epoch prefix, RDP receipt present, Git diff 0, provider calls 0).

Не публиковать chain-of-thought. Не завершать «можно ещё». KILL/STOP — полноценный полезный результат.

---

## 3. Scope, authority и стопы

### 3.1. В scope

- deterministic root/commissioning preflight;
- HFIC session state machine, validation, identity, evidence epoch, budget, persistence, resume;
- versioned schemas/config/operator/skills/CLI;
- Catalog/query recipes/projection views;
- tests, delivery evidence, one PR;
- exact-head CI + owner merge gate;
- post-merge offline commissioning, legacy backfill и end-to-end smoke proof.

### 3.2. Явно не в scope

- `EXECUTE TWO_RUNG_LIVE_H900_V1` — остаётся `FROZEN_PENDING_FAST_LANE`/`NOT_STARTED`;
- market/provider/API/RPC/WSS calls;
- wallet/signer/transaction/cash;
- live/forward collector;
- experiment execution или просмотр новых outcomes;
- autonomous scheduler/generator;
- RAG, embeddings, knowledge graph, graph DB, ClickHouse, PostgreSQL, vector DB;
- UI/dashboard;
- автоматический PR после `PASS_CHANGE_LANE_REQUIRED`;
- automatic promotion/trading logic;
- migration/merge двух divergent production roots без owner decision.

### 3.3. Разрешённая автономия

Разрешены без дополнительных вопросов:

- read-only repository/Catalog inspection;
- создание изолированной branch/worktree;
- изменения только внутри согласованного managed write set;
- local test/validate/format/generator commands;
- push и создание одного PR;
- исправления в том же PR до exact-head green;
- offline production-root commissioning после merge;
- append-only legacy backfill;
- local snapshot/restore proof;
- создание Google Drive-compatible snapshot в локальный staging destination, но не сетевой upload и не live root.

### 3.4. Единственные owner blockers

Остановиться и спросить владельца только при одном из условий:

1. exact-head merge approval;
2. два разных непустых commissioned roots (`DATA_ROOT_SPLIT_BRAIN`), где выбор уничтожает/скрывает историю;
3. требуется provider credential, wallet, cash, live collection или untouched holdout;
4. обнаружено несовместимое изменение current truth/contract, из-за которого цель требует materially другого product decision;
5. protected GitHub workflow/permissions физически не позволяют PR/merge.

Таймаут локального clone/gate, обычный CI failure, lint, write-set mismatch или тестовая ошибка не являются owner blockers: диагностировать и исправлять автономно в том же PR.

---

## 4. Target UX and protocol

### 4.1. Happy path

```text
Owner: /hypothesis-forge [OWNER_FOCUS=AUTO|text]

Skill → `hfic preflight`
  ↳ resolves one active store
  ↳ commissions offline if safely absent
  ↳ returns bounded FORGE_CONTEXT_PACKET + search budget

Forge model → FORGE_DRAFT (4–6 candidate cards)

Skill → `hfic freeze --draft ... --preflight-receipt ...`
  ↳ schema + cross-reference validation
  ↳ content IDs + evidence epoch/search key
  ↳ exact/component prior checks
  ↳ persists FROZEN_AWAITING_CRITIC
  ↳ returns only frozen CRITIC_INPUT_PACKET

Isolated Critic → CRITIC_RESULT

Skill → `hfic finalize --session-id ... --critic-result ...`
  ↳ validates terminal/revision/classifier consistency
  ↳ persists decisions, report, terminal and NEXT
  ↳ rebuilds/proves projection
  ↳ proves no-Git/provider=0

Owner receives one concise terminal + one NEXT
```

Dynamic JSON and temporary handoff files live under an OS temp directory or RDP runtime staging, never tracked repository paths. On success, temporary copies are removable because canonical bytes are retrievable from RDP.

### 4.2. Resume path

`preflight` searches by `search_key_sha256` before allowing model generation:

- complete match → `RETURN_EXISTING_SESSION`;
- frozen match → `RESUME_CRITIC` with canonical packet bytes;
- critic-ready match → `RESUME_FINALIZE`;
- no match + budget → `START_NEW_SESSION`;
- no match + exhausted → `SEARCH_BUDGET_EXHAUSTED`.

### 4.3. Owner-facing terminals

Protocol-level terminals:

```text
RETURN_EXISTING_SESSION
SAME_EVIDENCE_FOCUS_ALREADY_SEARCHED
SEARCH_BUDGET_EXHAUSTED
FAST_LANE_NOT_COMMISSIONABLE
DATA_ROOT_SPLIT_BRAIN
HFIC_PROTOCOL_INVALID
HFIC_PERSISTENCE_FAILED
```

Scientific/decision terminals remain exactly the existing B4 and post-classification enums; do not invent near-synonyms.

---

## 5. Software system design (SSD)

### 5.1. Design principles

1. **Creative core, deterministic shell.** Model proposes mechanisms; code owns identity, bindings, budget, state, persistence and routing.
2. **Append-only truth.** DuckDB is rebuildable projection, not source of truth.
3. **Content-bound, not chat-bound.** Stable IDs/hashes connect every layer.
4. **Fail closed before Critic/execution.** An invalid reference never reaches Critic.
5. **No infrastructure cosplay.** Reuse ResearchStore, Parquet, DuckDB, Catalog and lane classifier.
6. **Commissioning is a runtime fact.** Green CI is not commissioning.
7. **KILL narrows the search space.** Negative outcomes are first-class memory.

### 5.2. Recommended component layout

Use current repo conventions after fresh inspection; keep responsibilities equivalent even if final filenames adapt to established package boundaries.

```text
src/solana_alpha_lab/factory/hfic_session.py
    canonical models
    normalization + hashes
    candidate identity
    evidence epoch
    search budget policy
    state-machine transitions
    ResearchEvent batch construction
    session/prior/resume queries

src/solana_alpha_lab/factory/hfic_preflight.py
    active data-root resolution
    commissioning receipt verification
    bounded context packet construction

scripts/hypothesis_forge.py
    thin network-free CLI:
      preflight
      freeze
      finalize
      show-session
      prior
      backfill-legacy
      prove-runtime

catalog/schemas/hypothesis_forge_draft_v1.schema.json
catalog/schemas/hypothesis_critic_result_v1.schema.json
catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json
catalog/schemas/hypothesis_forge_synthesis_handoff_v1_1.schema.json

configs/hypothesis_forge_independent_critic_v1.yaml
.agents/skills/hypothesis-forge/SKILL.md
.agents/skills/independent-hypothesis-critic/SKILL.md
.cursor/commands/hypothesis-forge.md
.cursor/commands/independent-hypothesis-critic.md
docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
docs/tasks/HYPOTHESIS_FORGE_OPERATIONAL_CLOSURE_V1.md

schemas/research_memory_projection_v1.sql
src/solana_alpha_lab/factory/prior_work.py
tests/...
catalog/... + generated assets/evidence by current conventions
```

Avoid a new service. `scripts/hypothesis_forge.py` must be a thin adapter; business logic lives in importable tested modules.

### 5.3. Data model on existing RecordKind

#### Freeze transaction

Append atomically under one transaction ID:

- `RESEARCH_CYCLE`: `phase=FROZEN_AWAITING_CRITIC`, session/search/evidence/budget/provenance metadata;
- one `HYPOTHESIS_VERSION` per complete candidate;
- one `RESEARCH_ARTIFACT`: canonical `FORGE_DRAFT`/portfolio bytes;
- one `RESEARCH_ARTIFACT`: canonical frozen `CRITIC_INPUT_PACKET` bytes;
- optionally `EVIDENCE_BINDING` records for consumed truth/data/query recipe bindings if current schema semantics permit non-run bindings; otherwise keep bindings inside cycle/artifact payload and expose through HFIC projection, without weakening existing run binding semantics.

#### Finalize transaction

Append atomically:

- `RESEARCH_CYCLE`: `phase=SYNTHESIS_COMPLETE`, superseding/linking frozen cycle record;
- one `DECISION_EVENT` per candidate;
- `RESEARCH_ARTIFACT`: canonical Critic report/result bytes;
- `RESEARCH_ARTIFACT`: canonical final session receipt bytes;
- classifier receipt artifact when applicable;
- `CAPABILITY_GAP` only for deterministic Change Lane outcome.

Use deterministic record IDs derived from session/full payload hashes where consistent with store rules. Retry with identical bytes must be `REPLAY_IDENTICAL`; same IDs with different bytes must fail.

#### Legacy backfill transaction

`RESEARCH_CYCLE.phase=LEGACY_PARTIAL` + partial hypothesis definitions/artifact + decision hints. Never emit a fake complete Critic receipt.

### 5.4. New projection views

Add rebuildable views, minimally:

```text
hfic_sessions
hfic_candidates
hfic_candidate_decisions
hfic_search_budget
hfic_pending_sessions
```

They must support:

- lookup by session ID;
- lookup by search/evidence/focus key;
- latest phase deterministically;
- all candidate stable IDs and states;
- exact fingerprint search;
- component-based related-prior query;
- pending/resume lookup;
- prompt version/model/head provenance;
- exclusion of HFIC self-events from evidence epoch material digest.

Extend `prior_work` only compatibly. Existing consumers/tests must keep working. `RESEARCH_CYCLE` multiple phase records must not create ambiguous latest-state selection; order by reliable timestamp then record ID or explicit ordinal per current deterministic convention.

### 5.5. Draft schema

`hypothesis_forge_draft_v1` contains:

- schema/prompt version;
- owner focus;
- preflight receipt ID/hash;
- truth roots and prior query receipts;
- 4–6 full candidate cards;
- display ordinal (non-authoritative);
- selected candidate reference;
- runner-up reference;
- Pareto/ranking factors;
- non-claims and authority counters.

Model may propose a human label; it may not assign canonical stable ID. `freeze` computes IDs and rewrites references in the frozen representation only after validation.

### 5.6. Critic result schema

`hypothesis_critic_result_v1` contains:

- session ID;
- critic input packet SHA-256;
- selected stable candidate ID/full definition hash;
- critic prompt version/model/effort;
- isolated-context attestation;
- exactly one allowed terminal;
- exactly one NEXT;
- structured attack matrix/material defects;
- revision receipt, final contract, ExperimentSpec/classifier receipt only when terminal policy requires;
- authority counters and non-claims.

Conditional schema rules must enforce:

- B4 PASS cannot become post-classification PASS without valid classifier receipt;
- KILL cannot contain execution unit;
- `REVISE_ONCE` requires bounded revision contract and revision ordinal 0;
- post-classification PASS remains STOP-before-execution;
- input packet hash and candidate ID must match frozen session.

### 5.7. Session receipt schema

`hypothesis_forge_session_receipt_v1` is the canonical machine result:

```yaml
session_id:
session_state: SYNTHESIS_COMPLETE
evidence_epoch_sha256:
focus_key_sha256:
search_key_sha256:
prompt_version:
live_git_head:
store_inventory_digest:
candidate_ids: []
selected_candidate_id:
runner_up_candidate_id:
critic_input_packet_sha256:
critic_result_sha256:
critic_terminal:
lane_classifier_terminal: null|string
decision_event_ids: []
next:
authority:
  git_mutation: 0
  experiment_execution: 0
  provider_api_rpc_wss_calls: 0
no_git_fence_receipt:
created_at:
```

Timestamp не участвует в semantic/session identity.

### 5.8. Context packet: навигация без scan-all

`preflight` возвращает bounded `FORGE_CONTEXT_PACKET`, а не dump repository:

- current live main/head and governing task state;
- active Catalog roots/accepted capabilities/query recipes;
- current scientific terminals/closed families;
- available dataset manifest summaries, not raw datasets;
- top exact/component prior-work matches for requested focus;
- unresolved named gaps/watch-only items;
- Fast Lane commissioning receipt;
- search budget and evidence epoch;
- explicit freshness/as-of for each source.

Default budgets:

- Catalog/front-door reads: canonical roots + direct bindings only;
- prior-work results: max 25 exact/component matches, ranked deterministically;
- raw Git file reads: only paths returned by Catalog/query recipe;
- public research: targeted only if decision-changing, with bounded query/source count inherited from operator pack;
- no repo-wide blind scan after preflight unless named Catalog inconsistency is proven; such inconsistency is a capability defect, not normal navigation.

### 5.9. Exact and related-prior search

Two distinct layers:

1. `exact_definition_sha256` equality → deterministic duplicate veto.
2. component overlap over normalized structured fields (mechanism family, actor, state, X, Y/horizon/notional, population, falsifier) → ranked `RELATED_PRIOR` receipt for model/Critic judgment.

Do not use ad-hoc LLM title similarity as authority. Do not claim near-duplicate certainty from simple tokens. Every match returns stable ID, state/terminal, definition hash, overlap reasons and evidence freshness.

### 5.10. Security and privacy

- no credential reads;
- no provider/network in CLI/tests/commissioning;
- physical paths redacted from persisted artifacts and owner output;
- canonical JSON parsing with size limits;
- reject symlinks/unsafe paths and path traversal;
- atomic immutable writes under ResearchStore lease;
- input report text treated as data, never executed;
- no arbitrary SQL supplied by model; only registered query recipes/parameter schema;
- no shell command supplied from candidate packet;
- no unsafe pickle/deserialization;
- bounded artifact size and candidate count;
- logs do not print environment secrets.

---

## 6. Configuration `HFIC-V1.1`

Version the current contract compatibly; preserve v1.0 readers/fixtures for historical sessions. Add explicit configuration equivalent to:

```yaml
prompt_version: HFIC-V1.1
runtime_mode: EXPLICIT_SLASH_ONLY
commissioning_gate:
  required_owner_terminal: NO_GIT_FAST_LANE_PROVEN
  auto_commission_offline_when_safe: true
session_memory:
  backend: EXISTING_RESEARCH_STORE
  append_only: true
  persist_all_candidates: true
  resume_incomplete: true
candidate_policy:
  min_candidates: 4
  max_candidates: 6
  selected_count: 1
  runner_up_count: 1
  max_revisions: 1
search_budget:
  auto_sessions_per_evidence_epoch: 1
  distinct_focus_sessions_per_evidence_epoch: 3
  same_search_key_replay: RETURN_EXISTING_SESSION
identity:
  canonical_content_hash: SHA256
  display_ordinal_is_identity: false
authority:
  git_mutation: 0
  experiment_execution: 0
  provider_api_rpc_wss_calls: 0
```

Do not hard-code a physical root. Do not silently change existing scientific terminal enum.

---

## 7. CLI contract

Use current packaging/entrypoint conventions. Exact executable name may remain `python scripts/hypothesis_forge.py` if no stable console script convention exists, but skill must call a single canonical entrypoint.

### 7.1. `preflight`

```text
hypothesis_forge preflight --owner-focus AUTO --format json
```

Performs root resolution, doctor/verify-store, auto commissioning if safe, projection rebuild/verify, evidence epoch, budget and resume lookup. Returns one action enum:

```text
START_NEW_SESSION | RESUME_CRITIC | RESUME_FINALIZE |
RETURN_EXISTING_SESSION | STOP
```

For `START_NEW_SESSION`, also returns `FORGE_CONTEXT_PACKET` and immutable preflight receipt hash.

### 7.2. `freeze`

```text
hypothesis_forge freeze \
  --preflight-receipt <temp-json> \
  --draft <temp-json> \
  --format json
```

One schema-repair attempt may be performed by the agent on validator errors. CLI itself never asks model to rewrite content. Success writes frozen records and returns session ID + canonical Critic packet.

### 7.3. `finalize`

```text
hypothesis_forge finalize \
  --session-id <id> \
  --critic-result <temp-json> \
  --format json
```

Validates, appends decisions/artifacts, rebuilds and verifies projection, checks no-Git fence, returns canonical session receipt and owner summary fields.

### 7.4. Recovery/read-only

```text
hypothesis_forge show-session --session-id <id> --format json
hypothesis_forge prior --candidate <json>|--query <text> --format json
hypothesis_forge prove-runtime --session-id <id> --format json
hypothesis_forge backfill-legacy --packet <json> --format json
```

`backfill-legacy` is idempotent and accepts only explicit `LEGACY_PARTIAL`; it cannot create PASS/promotion/execution readiness.

### 7.5. Exit behavior

Machine-readable stdout only when `--format json`; diagnostics to stderr; stable non-zero codes for validation, store, budget, authority and persistence failures. Do not leak full physical paths.

---

## 8. Skills and prompt integration

### 8.1. Forge skill

Update `.agents/skills/hypothesis-forge/SKILL.md` so the mandated workflow is executable, not prose-only:

1. run canonical `preflight` first;
2. branch on returned action;
3. only for `START_NEW_SESSION`, run PROMPT A/HFIC-V1.1 using only bounded context packet plus explicitly resolved evidence;
4. emit machine `FORGE_DRAFT` to temp, not final free-form packet;
5. call `freeze` and use its canonical packet;
6. auto-launch Critic in new isolated context;
7. call `finalize` with structured critic result;
8. verify `SYNTHESIS_COMPLETE`/RDP receipt before telling owner completion;
9. on crash/retry, resume, never regenerate;
10. owner report in Russian, exact enums/IDs in English.

Skill may still present a concise Forge report, but code-generated/frozen packet is authority.

### 8.2. Critic skill

Update Critic so it accepts only frozen packet + session metadata, returns `hypothesis_critic_result_v1`, and does not persist directly. Finalizer owns persistence. Critic independently re-resolves cited truth via bounded paths; it must not receive Forge narrative/scratchpad.

### 8.3. Slash commands

`/hypothesis-forge` remains explicit-only and becomes the only normal command. `/independent-hypothesis-critic` remains recovery-only. No owner copy/paste in happy path.

### 8.4. Prompt quality upgrades

Do not rewrite PROMPT A/B wholesale. Patch only measured gaps:

- candidate ordinal is display-only;
- output machine draft with stable reference slots;
- exact/component prior receipts required;
- evidence epoch and search budget visible;
- selected/runner-up predeclared before Critic;
- no same-evidence rerun until PASS;
- all candidate outcomes remembered;
- Critic KILL terminates the session;
- `PASS_*` means routing readiness, never alpha proof.

---

## 9. Managed write set

Before editing, resolve exact current paths and declare one task contract with a bounded managed write set. Expected scope:

- new HFIC task contract;
- HFIC config/operator/skills/slash commands;
- new HFIC library modules + thin CLI;
- versioned JSON schemas and fixtures;
- research projection/prior-work extensions;
- Catalog source assets/query recipes/lifecycle/dependency bindings;
- generated Catalog outputs/PROJECT_MAP through generator;
- tests;
- delivery completion, independent review and factory-fit evidence;
- harness control evidence only if current delivery route requires it.

Do not modify market collectors, live runners, trading code, provider registry, wallet code, `TWO_RUNG_LIVE_H900_V1`, unrelated roadmap items or historical evidence.

If harness classifies this as `CONTROL_RUNTIME_CHANGED`, follow the exact harness route and widen allowed prefixes narrowly in the same PR; do not bypass gate and do not add broad directory allowances.

---

## 10. Implementation plan (test-first, one PR)

### Task 0 — Restore live truth and bind the task

1. Fresh-fetch `origin/main`; report exact base SHA.
2. Read in canonical order: `AGENTS.md` → delivery harness/profile → current Catalog/context-map → Fast Lane task/config/runtime → HFIC task/config/skills/operator/schemas → current tests/time gates.
3. Prove current expected facts rather than trusting this document where main advanced.
4. Create `docs/tasks/HYPOTHESIS_FORGE_OPERATIONAL_CLOSURE_V1.md` with objective, routes, write set, authority, stops, DoD and post-merge phase.
5. Run task preflight before implementation.

**Gate:** no code until task route/write set is accepted by repository validation.

### Task 1 — Write failing contract tests

Add fixtures/tests for:

- root resolution/commissioning proof and split brain;
- candidate canonicalization/ID stability/collision;
- cross-reference mismatch `C3/C4` fail;
- evidence epoch invariance/material change;
- search budget/replay/resume;
- freeze/finalize atomicity/idempotence/conflict;
- projection/prior lookup;
- schema terminal conditionals;
- no-Git/provider fences;
- legacy partial backfill;
- end-to-end skill protocol.

Run them and capture expected RED. Do not create tests that merely assert static strings if behavioral proof is possible.

### Task 2 — Unify data-root and commissioning preflight

1. Extract/reuse one root resolver shared with `hypothesis_fast_lane`.
2. Implement content-level commissioning verifier.
3. Implement bounded root-candidate reconciliation policy.
4. Implement safe auto `commission-offline` and re-verification.
5. Return redacted machine receipt/context action.

**Gate:** tests prove empty store becomes commissioned with Git diff 0/provider 0; divergent stores stop.

### Task 3 — Implement schemas, identity, evidence epoch and budget

1. Add versioned schemas/fixtures.
2. Implement canonical candidate definition and stable identity.
3. Implement reference validator.
4. Implement evidence epoch with explicit include/exclude list.
5. Implement focus/search keys and budget policy against projection.

**Gate:** reorder/timestamp/model/unrelated commit/session write do not alter identity/epoch; material binding does.

### Task 4 — Implement persisted state machine

1. Build ResearchEvent batches using existing RecordKind.
2. Freeze transaction persists all candidates and frozen packet.
3. Finalize transaction persists all decisions/reports/receipt.
4. Implement replay-identical/conflict semantics and resume.
5. Add legacy partial transaction.

**Gate:** injected failure never leaves an apparently complete session; retry resumes without duplicate candidate/session.

### Task 5 — Projection and deterministic navigation

1. Add HFIC views.
2. Extend prior query model for exact + component overlap.
3. Add registered query recipes and Catalog dependencies.
4. Ensure context packet is bounded and freshness-bound.
5. Rebuild/generate Catalog outputs through canonical tool.

**Gate:** first-run killed/paused candidates are retrievable by mechanism/component and block exact repeat without repo scan.

### Task 6 — CLI and skills

1. Implement thin CLI commands.
2. Update Forge/Critic skill and slash command handshake.
3. Enforce one automatic correction, isolated Critic, finalize receipt.
4. Implement concise owner output and recovery actions.

**Gate:** simulated slash happy path needs no owner input between initial command and final terminal.

### Task 7 — Behavioral and adversarial verification

Run at least:

- targeted HFIC unit/integration tests;
- Fast Lane semantic DoD/CLI/runner/store/snapshot tests;
- Catalog validate/generation stability tests;
- delivery harness contract tests;
- complete repo-required local validation;
- adversarial fixtures: prompt injection in candidate text, oversized draft, invalid terminal, fake classifier receipt, packet hash mismatch, symlink root, split roots, writer busy, partial crash, same-evidence shopping attempt.

Run independent review against PRD/SSD. Fix all P0/P1 and correctness-affecting P2 in same PR. Do not declare complete on test count alone; map evidence to §12.

### Task 8 — PR and exact-head merge gate

1. One clean branch, one PR.
2. No routine hypothesis/session records in Git.
3. Provide decision-focused PR body: gap, architecture, non-goals, tests, rollback, post-merge commissioning.
4. Wait for exact-head CI green.
5. Re-resolve head and mergeability.
6. Ask owner only for exact phrase bound to PR number + full head SHA.
7. On head change, invalidate old phrase and request new exact phrase.
8. After phrase, perform repository-approved guarded merge; do not trust a stale local timeout over GitHub exact-head CI, but do not bypass required policy.

### Task 9 — Post-merge runtime closure

Continue in the same owner workflow after merge; do not return another design-only NEXT.

1. Refresh clean `main`; bind merge SHA.
2. Run HFIC preflight on active production-local data root.
3. If safe and absent, auto commission offline; prove `NO_GIT_FAST_LANE_PROVEN`.
4. Perform idempotent `LEGACY_PARTIAL` backfill of first Forge run.
5. Rebuild and verify projection; query the five prior families.
6. Run end-to-end deterministic commissioning session on fixture/temp root through `preflight → freeze → isolated critic fixture → finalize → show/prove → snapshot → clean restore → rebuild → same result`.
7. On production root, run only read-only `preflight/prove-runtime`; do not generate a new real hypothesis and do not execute TWO_RUNG.
8. Prove post-run Git composite unchanged and provider calls 0.
9. Emit `HFIC_OPERATIONAL_LOOP_PROVEN` only if all checks pass.

---

## 11. Test matrix

### 11.1. Data root / commissioning

- env absent + default empty → auto commissioning succeeds;
- env valid commissioned + default empty → env store selected;
- env empty + default commissioned → commissioned default selected consistently;
- both identical → no duplicate writes;
- both divergent nonempty commissioned → `DATA_ROOT_SPLIT_BRAIN`;
- uncommissioned directory alone is not proof;
- corrupted/missing commissioning artifact fails;
- resolved root/path never appears in persisted event or owner JSON;
- commissioning produces zero Git mutation and provider calls.

### 11.2. Candidate identity/references

- shuffled portfolio → same IDs;
- ordinal change → same ID;
- material mechanism/X/Y/population change → different full hash;
- duplicate full definitions rejected;
- selected missing/duplicated rejected;
- selected=runner-up rejected;
- free-text `C3`/`C4` mismatch rejected;
- Critic input ID/hash mismatch rejected;
- near duplicate is returned as `RELATED_PRIOR`, not silently equated.

### 11.3. Evidence/search policy

- HFIC session append does not alter epoch;
- unrelated Git change does not alter epoch;
- material Catalog/data/scientific truth change does;
- same epoch/focus returns existing session;
- AUTO second search blocked;
- distinct focus allowed up to 3;
- fourth focus blocked;
- prompt bump cannot erase prior memory;
- KILL does not auto-run runner-up.

### 11.4. State/persistence

- freeze contains all candidates + retrievable packet;
- crash after freeze resumes Critic;
- crash before final append does not show complete;
- finalize retry identical is idempotent;
- conflicting retry fails;
- KILL selected → REJECT; others → PAUSE;
- PASS readiness → PAUSE, never PROMOTE;
- Change Lane alone creates typed capability gap;
- projection rebuild yields identical digest/results;
- cold backup/restore preserves session/artifacts/prior decisions.

### 11.5. Skill/user flow

- one `/hypothesis-forge` invocation reaches final receipt;
- Critic receives packet only, not Forge narrative;
- no manual copy/paste;
- no branch/PR/CI during runtime;
- no provider/experiment/holdout;
- no completion without RDP receipt;
- repeated slash returns/resumes instead of generating;
- owner output has one terminal and one NEXT.

### 11.6. Regression

- all existing 63+ Fast Lane tests remain green;
- HFIC v1.0 fixtures remain readable or have explicit migration compatibility;
- current lane classifier behavior unchanged;
- current Catalog search/gold queries unchanged;
- `TWO_RUNG_LIVE_H900_V1` remains frozen and untouched.

---

## 12. Definition of Done

Все пункты обязательны:

1. Exact-head CI green; one PR; independent review passed.
2. Post-merge main contains code/schemas/skills/Catalog bindings, но не nightly session data.
3. Один active production-local store доказан; divergent ambiguity отсутствует.
4. Offline commissioning receipt реально находится на том же store, который читает Forge.
5. Первый реальный Forge cycle backfilled как honest `LEGACY_PARTIAL` и находится prior query.
6. Runtime session проходит с Git composite unchanged, branch/PR/CI absent, provider calls 0.
7. Append-only memory содержит cycle, all candidates, artifacts, decisions, terminal и NEXT.
8. Passport/receipt содержит prompt/model/head, evidence/search hashes, stable candidate IDs, store digest, terminal, authority/no-Git proof.
9. Dynamic raw/canonical artifacts остаются вне Git и переживают snapshot → clean restore → projection rebuild.
10. C3/C4 regression падает до Critic.
11. Same evidence+focus repeat возвращает existing session/STOP; hypothesis shopping невозможно обычным интерфейсом.
12. Crash recovery продолжает frozen session без новой генерации.
13. Catalog/query recipes дают bounded context/prior navigation без blind repo scan.
14. `/hypothesis-forge` является единственным обычным owner action.
15. `TWO_RUNG_LIVE_H900_V1=NOT_STARTED/FROZEN_PENDING_FAST_LANE` и provider calls 0.

### Semantic acceptance scenarios

#### Scenario A — новый безопасный вечерний цикл

Given commissioned active store и новый evidence epoch; when owner invokes `/hypothesis-forge`; then portfolio frozen, Critic isolated, final receipt stored, one terminal/NEXT returned, Git unchanged.

#### Scenario B — повторный новый чат

Given completed session на тех же epoch/focus; when `/hypothesis-forge`; then no model generation, existing terminal returned with `RETURN_EXISTING_SESSION`.

#### Scenario C — interruption

Given frozen session without critic terminal; when slash invoked again; then Critic resumes from stored packet and finalizes same session.

#### Scenario D — worthy hypothesis

Given Critic `PASS_TO_CLASSIFICATION`; then schema-valid ExperimentSpec + offline classifier are required; final `PASS_*` is saved as readiness/PAUSE, experiment not run.

#### Scenario E — weak hypothesis

Given `KILL_PREPARATORY_LOOP`; then selected REJECT, other candidates PAUSE, NEXT=STOP, no runner-up/new generation.

---

## 13. Merge, commissioning и финальный handoff

### 13.1. Merge request format

После exact-head green вернуть владельцу только проверяемые данные и exact phrase:

```text
PR #<N>, head <FULL_SHA> проверен; ready + merge разрешаю.
```

Не просить «нажмите merge сами», если текущий repo policy разрешает guarded merge после фразы. Не выполнять merge до phrase.

### 13.2. Post-merge success report

Финальный отчёт должен быть коротким, по-русски и содержать:

```text
TERMINAL=HFIC_OPERATIONAL_LOOP_PROVEN
main_sha=<full sha>
active_store=COMMISSIONED (fingerprint only)
first_forge_cycle_memory=BACKFILLED_LEGACY_PARTIAL
runtime_no_git=PROVEN
provider_calls=0
TWO_RUNG_LIVE_H900_V1=NOT_STARTED
owner_next=/hypothesis-forge
```

Если DoD не закрыт, нельзя писать «готово почти». Вернуть named failure, доказательство и ровно один repair NEXT, продолжая автономно, если это не §3.4 blocker.

---

## 14. Rollback and compatibility

- Capability PR можно revert одним commit; append-only RDP records не удалять.
- HFIC-V1.0 historical packets остаются readable; new writes используют V1.1.
- При rollback новые RDP records должны оставаться игнорируемыми старой projection либо иметь versioned reader; projection всегда пересобираема.
- Legacy backfill помечен, поэтому его можно исключить из analytics фильтром без удаления.
- No automatic root merge/move/delete.
- No destructive migration of Parquet/manifests.

---

## 15. Исполнительские запреты против «почти готово»

Не закрывать задачу одним из следующих суррогатов:

- ещё один PRD без runtime implementation;
- `doctor=healthy` на пустом store;
- зелёные tests без post-merge commissioning;
- хранение только selected candidate;
- хранение только hashes без retrievable packet/report;
- human `C1/C2/C3` как primary key;
- простой повтор Forge в новом чате после KILL;
- новый repo scan/RAG/graph вместо Catalog/query recipe;
- автоматический запуск научного атома;
- запись physical data-root path в Git;
- «owner должен сам выполнить несколько CLI»;
- отдельные PR для каждой мелкой поправки этого capability atom.

Цель — не повысить вероятность красивого PASS. Цель — получить честный, быстрый, запоминающий и воспроизводимый контур, где хороший candidate может дойти до правильной lane, а слабый один раз умирает и больше не съедает вечер.
