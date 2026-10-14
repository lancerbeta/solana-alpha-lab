---
design_id: EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1
status: OWNER_DECISION_REQUIRED_NOT_EXECUTABLE
as_of: '2026-10-14'
origin: SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1_TARGETED_CONTINUATION
---

# Один bounded repair atom: явный outcome-контракт для native episodes

Проблема воспроизведена на неизменном product base
`94b391d658b52035ae88e2da05f1ea25ff17b0f8`. Native `episode_query` 1.2 использует
`OPPORTUNITY_EPISODES`, `NOMINATION_T0`, `EPISODE_T0` membership, E1800/E14400
и `FIRST_RELIABLE_AVAILABLE_AT`. PROMPT B требует ExperimentSpec 1.3 с явными
`required_outcomes`. Его `point_id` принимает только `^[XY][0-9]{1,7}$`;
`E14400` получает `EXPERIMENT_SPEC_SCHEMA_INVALID`. Это необходимое поле,
а не качество наблюдений, размер N или научный порог. Raw schema control
проходит, единственная замена outcome на E14400 отказывает точно по этому полю.

Ценность атома — выражать и проверять неизменённый episode outcome до чтения
значений. Он не делает нынешний кандидат научно ценным и не создаёт accepted
chronological validation. Фактический Critic после одной revision сохранил
`KILL_LOW_INFORMATION_VALUE`; этот terminal и история остаются неизменными.

## PRD

Потребитель — native Critic/classifier и следующий источник научных evidence.
Единица результата — один explicit episode-native ExperimentSpec, который
сохраняет population, episode identity, номинальные часы, available-at, list
scope, frozen input hashes, исходный denominator и требуемые outcomes.

Owner принимает точный versioned contract: расширение совместимой версии либо
новую версию Spec с episode-native reuse branch. До этого не менять схему,
authority, capability registry, guards, thresholds или data-contract meaning.
Этот документ — дизайн следующего решения, не READY task и не разрешение repair.

In scope только выразимость и fail-closed metadata projection исходных episodes:
schema → source-bound interpretation → classifier readiness. Не делать новый
scientific consumer, OOS scorer, bootstrap runner, strategy, activation или PAPER.
Не добавлять synthetic PASS lane и не разрешать runtime metrics заменять science.
Не переводить E в X/Y или recurring episode identity в один TOKEN_MINT.

## SSD

Сначала использовать существующие owners: `opportunity_episodes.resolve_point`
для point/clock, `hfic_research_scope` для scope/membership,
`hfic_temporal_discovery` для frozen recipe и target admissibility. Schema-only
union E/X/Y недостаточен: текущий scientific projector принадлежит factory
`X300` и canonical X_ELIGIBLE, его нельзя молча применить к episodes.

Episode branch должен требовать явный population/anchor/time contract и
immutable released source identity, связывать каждый required outcome с той же
episode и тем же schedule. Metadata projection не читает target numeric values
и не оценивает эффект. Complete coverage считается на неизменном native
decision base; UNKNOWN/INVALID/missing остаются типизированными и не уменьшают
denominator до complete cases. Source schedules и receipts должны проверяться
against frozen и current stricter protection по штатному пути.

Никаких новых сервисов, платных зависимостей, providers, deployments или
модельных transports. Изменения перечисленных production owners требуют нового
exact task/write set и обычного risk-routed review; здесь они не выполнены.

Приёмка атома:

1. Один допустимый frozen E1800→E14400 recipe выражен без изменения estimand;
   native schema/metadata/classifier принимают именно его episode bindings.
2. Потерянный outcome, неверный clock/anchor/episode identity, stale source hash,
   неверная availability/protection и конфликт definition дают typed refusal.
   Даже observed targets не создают scientific acceptance или PROMOTE.
3. Reuse-only projection не декодирует Y values; N не сужается; masks/denominators
   и immutable source refs видимы в machine receipt.
4. Legacy X/Y contracts и текущие gates сохраняют meaning и regression checks.
5. Короткий synthetic acceptance probe сохраняет этот Spec/recipe/source lineage;
   результат `schema/classifier ready` явно отделён от science/Strategy readiness.

STOP: требуется изменение estimand, population, научного порога, authority,
provider, production state или accepted confirmation protocol. Тогда replan,
а не расширение этого атома. Даже после его PASS независимое подтверждение,
полезность scientific question и qualifying DIRECT science остаются отдельными
условиями полного пути. `NEXT_MODEL_EFFORT=SOL_XHIGH`.
