# FORGE_EVIDENCE_GUIDED_GENERATION_V1

Обычная Forge получила фазовый контекст и ограниченную рабочую память с
проверяемыми источниками. Рост архива больше не требует помещать все записи
в prompt: полный архив проверяется независимо от выбранных для модели записей.
Качество формулирования подтверждено частично; сравнительный выигрыш не установлен.

Постановка: SMIAL_Evidence_Guided_Generator_PRD_SSD_V1_2026-10-09.md,
R1–R10, P1–P8, отдельные оси §14. Base:
`fb65d69f6e48c49b26937bb6caf324b3417b094e` / PR388.
Финальная реализация: `20cdc7f3fe5bdb541d6961fe996b379bec0ddd90`;
capability `ba8d2b3b6a3ded23f3147466a752596932bc82aa0e31a52cc5fe50ba30810a13`.
Исторические native inputs относятся к исходной реализации706e917; их
Git/capability bindings сохранены и не переименованы в финальный epoch.
Последующие evidence/content commits связываются completion/harness отдельно.
Route `DIRECT_CODEX_DELIVERY`, actor `CODEX`. Только disposable synthetic stores.

## Результат и границы

| Ось | Результат |
|---|---|
| IMPLEMENTATION | PASS в выполненном техническом scope; независимая проверка ниже |
| SAFETY_AND_COMPATIBILITY | PASS по выполненным машинным проверкам; native read-set ограничения сохранены |
| FORMULATION_ON_SYNTHETIC | PARTIAL_FORMULATION |
| COMPARATIVE_QUALITY | QUALITY_GAIN_NOT_ESTABLISHED |
| DELIVERY | NOT_MERGED; exact-head CI/readiness ещё не заявлены |
| MARKET_ALPHA / CHRONOLOGY / LIVE_ECONOMICS | NOT_EVALUATED |

Это не доказательство здоровья всей Factory или работоспособности на рынке.
Карточки агентов после первого persist не редактировались; failed attempts не
заменены успешными повторами. Scientific KILL и технический отказ сохраняют
разный смысл, ни один автоматически не закрывает семейство.

## Что переиспользовано и изменено

Переиспользованы projector/authoring descriptor #388, ResearchStore, существующие
admission, scope, prior/session/time, discovery/evaluator, Critic/finalize и
recovery owners. Не добавлены сервис, БД, embeddings, агентный framework,
провайдер, evaluator/operator, scientific budget или deployment.

Один новый read-model `hfic_generation_context.py` связывает source facts,
scope, оба research clocks, собственную session вердикта, material restrictions,
selection/omission receipts и адресное read-only чтение. Ранжирование учитывает
структуру вопроса и разнообразие, не знак результата. Прежние full-scope guards
работают по всем eligible sources, независимо от ranking.

Fresh episode Critic packet1.5 наследует все1.4 grounding floors; working
snapshot1.1 сообщает неполноту архива внутри packet. Исторические1.0–1.4 и
snapshot1.0 не пересобираются. Initial capsules≤8, Critic capsules≤64,
весь canonical UTF8 Critic packet≤65536 bytes, включая metadata.
Mandatory overflow отказывает до нового draft/slot. Metadata/preview/main имеют
разные permissions; prefix preview не читает будущий target, повтор не даёт look.

`episode_query_capabilities` публикует существующую grammar1.2 и закрытые
feature/predicate nodes. Late consulted details не превращаются задним числом
в initial historical memory. Изменение store требует fresh bound receipt,
не возврат квот. Нового truth owner для свободной модельной summary нет.

## Техническое evidence

На intermediate capability51f21e3702f641e8718976fc9d3a4316c3012afcf57047e5439a5cf7593409b1
прошли54 проверки:20 новых/direct consumer,30 legacy/recovery,2 future-prefix,
2 producer/protected guards. Последняя узкая правка recovery отдельно проверена
на финальном capabilityba8d2b:4/4 PASS,82.804s. В них входят exact recovery
locator, stale detail, mandatory overflow и повреждённый hidden archive вне
выбранных8 источников: public refusal и unchanged hashes всего store.
Commands, log hashes, before/after capability находятся в manifest и raw bundle.
Прежние53 проверки и9 growth processes относятся к historical3dcbe81 epoch.
Это focused validation; local full gate до PR не запускался.

| Архив: добавлено / фактически eligible | Cold processes | Wall seconds | Initial / Critic capsules | Whole Critic bytes |
|---|---:|---:|---:|---:|
|40 /41|3|29.252–32.079|8 /28|64428|
|400 /401|3|31.976–35.937|8 /28|64434|
|4000 /4001|3|63.058–68.961|8 /28|64440|

Дополнительный eligible source сохранён, не удалён ради круглого denominator.
Все9 cold production-CLI paths закончились FROZEN_AWAITING_CRITIC; guard
рассмотрел весь eligible archive. Метрики содержат actual PID, per-stage physical
partition reads/bytes/record decodes и Windows peak working set. Token counts
не измерены; это bytes/RSS/wall measurements. Все growth cards scripted,
они не входят в native formulation numerator. Старые capability/failed runs
сохранены отдельными raw locators, не переименованы в final PASS.

После финальной правки отдельно повторён один cold public CLI path на4001
eligible source:63.064s, initial8 / Critic28, whole packet64440 bytes,
peak RSS465047552 bytes, полный guard4001, FROZEN_AWAITING_CRITIC. Исходные9
замеров не выданы за новые. Все cold measurements — fresh process, не cold OS cache.

Стоимость существующего BASE owner и текущего отбора измерена18 отдельными
cold processes:3 на arm/размер, один неизменённый source root и cutoff на пару.
Три integrity/scope owners имеют одинаковые Git blob/disk hashes в BASE и
candidate. Каждая partition проверяется один раз внутри read scope; inventories
не меняются, writes/new looks0. Это component read/selection timing, без imports,
setup и process launch; полного successful BASE CLI при архиве>64 нет.

| Добавлено | BASE median seconds | Candidate median seconds | Physical reads / hashed bytes, оба arms |
|---|---:|---:|---:|
|40|0.01496|0.01327|2 /44485|
|400|0.03128|0.05165|2 /293654|
|4000|0.21489|0.42474|2 /2789065|

На4000 extra selection CPU около0.210s, примерно2x на этом компоненте;
RSS сопоставим (максимум179146752 bytes). Нет N-кратного повторного чтения;
это не доказательство ускорения всей ordinary Forge относительно frozen BASE.

## R1–R10 → P1–P8

| Requirement | Production owner / прямое evidence |
|---|---|
|R1|preflight/context, generation brief, actual episode grammar; new module14 tests, public native inputs|
|R2|full eligible safety receipt independent of rank;65-entry freeze, hidden exact prior, mandatory overflow,9 growth processes|
|R3|source_detail/findings/own Critic objections; persisted prior matrix, source clocks, bound exact native reads|
|R4|temporal preview/ordinary look owners; no-target preview/replay, readonly detail, stale writer,2 future-prefix + protected-loader tests|
|R5|fixed core16 + repair4 + transfer2, anonymous quality grading; PARTIAL, no forced actor-story|
|R6|existing DSL/readiness owners; supported fixed queries, unsupported ingress FAILs retained, KILL/proxy≠alpha|
|R7|projector #388 and Critic1.5; scripted public full passage, real native frozen packet and actual Critic output; native finalize BLOCKED below|
|R8|actual saved Critic→new public context→native readonly answer; technical advice separate; first cycle scripted, not native quality numerator|
|R9|existing collection/field/provenance owners, grammar export; renamed/scaled unused fixtures, owner mutation changes capability not market/charges, protected/unknown/hash refusal|
|R10|legacy30 tests; actual OS reply loss, cold moved-root resume preserves original draft/charge; revision same look; immutable Git-fence refusal retained|

| Probe | Executed result | Evidence / limit |
|---|---|---|
|P1|PARTIAL|core dynamics questions; untouched transfer01 persists/freezes unchanged; its finalize blocked by Git binding|
|P2|PASS in tested scope|technical vs exact valid close differentiated; no new budget/family-wide inference|
|P3|PARTIAL|two saved parents and compound question; first persist/alias failures remain; no proven conjunction/incremental price-gate gain|
|P4|PARTIAL|tiny/null restraint correct; tail case chose wrong short horizon, retained as miss|
|P5|PASS|65+/4000 archive, hidden close beyond ranking, structural/diversity/byte-bound tests and9 cold processes|
|P6|PASS in executed machine scope|both research clocks/own session, future poison, prefix-only and protected/unknown/hash guards; no claim of exhaustive native prompt-injection coverage|
|P7|PASS in tested existing-field scope|metadata/producer/capability binding and unused renamed/scaled inputs; no new provider or units contract adopted|
|P8|PASS for bounded memory/recovery; native full-first-cycle PARTIAL|real saved Critic control consumed by real native next output,0 new looks; native first-cycle finalize failed and remains failed|

## Native denominator, first failures и repair

Фиксировано16 core calls:8 baseline после#388 и8 candidate. Denominator на arm:
5 positive opportunities и3 ожидаемых scoped refusals. Blind core grader
получил original outputs/first cards + frozen oracle; model/seed UNKNOWN.

| Core semantic metric | Baseline | Candidate first pass |
|---|---:|---:|
|Supported meaningful positive opportunity|3/5 +2 UNKNOWN|4/5|
|Correct expected negative action|1/3|3/3|
|End-to-end usability grade|0/8|4/8, включая3 scoped stops и1 no-worthy freeze|

4/5 semantic yield не означает4 законченных scientific paths. Ни одна positive
core card не закончила обычный handoff; P4 tail выбран с неправильным horizon.
Post-development/transfer outcomes не увеличивают исходный denominator.

Один адресный cycle выделил4 repair calls на те же cases01/02/05/06. Итоги:
FEATURE_INVALID, PREDICATE_INVALID, UNKNOWN_PRIOR_SCOPE, CARD_ALIAS_CONFLICT.
Первоначальные failures и все scientific plans/cards сохранены. Перед MAIN
допускалась только mechanical ingress correction из public method, без смены
science; её стоимость/первый FAIL остаются. После first persist cards immutable.
Повторившиеся seams остановили дальнейший tuning; оставшиеся4 repair calls
из разрешённых8 не использованы.

До outcomes были выделены4 extra calls:2 next-cycle и2 unused transfer.
Transfer recipe source transform/neutral labels зафиксирован до запусков.
Transfer01: MAIN1/PREVIEW1, first-draft unchanged, packet1.5 frozen.
Transfer05: MAIN1/PREVIEW0, first persist UNKNOWN_PRIOR_SCOPE, no freeze.
Полного paired baseline transfer нет; comparative causal gain не установлен.

Blind оценка этих8 дополнительных outputs:4 grounded discriminators,
1 false,3 UNKNOWN. Среди6 positive question cases семантическая возможность
названа6/6, handoff завершён1/6; это разные метрики. First transport по всем
8 outputs:7 NOT_MET,1 UNKNOWN, включая method/helper failures. Для2 read-only
P8 outputs memory_correct=2/2; отсутствие новой карточки там не является FAIL.
64 rubric cells:53 MET,5 NOT_MET,2 NOT_APPLICABLE,4 UNKNOWN. Все original
output hashes после оценки перепроверены, core denominator не изменён.
Схема2 next-cycle +2 transfer выбрана до outcomes как разрешённая альтернатива
четырём factorial arms §11.4; отдельный A/B/C/D не исполнялся.

## Critic и next-cycle: реальные пределы

Выполнены2 настоящих independent native Critic calls, отдельно от24 Generator:

1. Scripted growth control, packet64428 bytes/28 capsules, фактический
   KILL_LOW_INFORMATION_VALUE. Public finalize PASS, сохранённый review source.
   Новый native Generator прочитал его через production prior, назвал
   candidate/bound-evidence applicability и family_suppression_authority=false,
   оставил full-scope sign/independence UNKNOWN и остановился без new look.
   Ни Critic summary, ни expected answer не подставлялись в его prompt вручную.
2. Реальная transfer01 first card, packet38533 bytes, actual native Critic
   KILL_UNBOUND_EVIDENCE. Result schema/hash validated; public finalize returned
   GIT_COMPOSITE_CHANGED. Critic result не стал saved terminal. Неизменённый
   frozen session остаётся FROZEN_AWAITING_CRITIC. Его текст не выдан за память
   последующего run. Подготовленный dependent input сохранён как failed setup,
   native invocation на нём не запускался.

Native Git-fence mismatch сохраняет исходную preflight composite identity:
5093edf62bacf33535a7962d8728b4be632770b904b74c69e1e9bdb11b0dfb52
против clean current0242f7ffb2d77e3a4dcadc7060ea0c23043bed9828f709f7a9a3fcae42234350.
HEAD текущей frozen card и repo706e917 совпадает. Inputs были подготовлены
до product commit; claim о полном native ordinary finalize не делается.
Исходный payload не перепривязан и gate не ослаблен.

Technical second output использует source-bound authored assessment фактического
UNKNOWN_PRIOR_SCOPE через disposition-record/show. Это operator projection
реального отказа, не придуманный scientific KILL. Advice после initial research
cutoff отделено от historical working view; поздний result detail корректно
BLOCKED GENERATION_CONSULTED_SOURCE_UNAVAILABLE. MAIN1 остаётся spent.

## Стоимость, provenance и ограничения

Actual launches:24 Generators =16 core+4 repair+2 transfer+2 readonly next-cycle;
hard cap28. Critics2; semantic quality graders2; engineering reviews отдельно.
Native per-focus counters считаны existing journal metadata без values/writes.
Pending attempts считаются отдельно от completed; self-reported counters не
переопределяют owner readback. По22 scientific-focus stores:MAIN completed8,
PREVIEW completed1/pending3, ADAPTIVE completed0/pending0. Два P8 clone чтения
добавили0 новых looks и не суммируются повторно с originating store.
Model/seed/tokens/dollar cost UNKNOWN; нового
платного API, ключа или cash spend не было. Latency имеет указанные boundaries;
subprocess/materialization time не выдаётся за весь LLM wall time.

FORK_NONE даёт logical isolation, не OS sandbox/model diversity. Методические
JIT reads, изменения development capability и неодинаковый history preparation
мешают строгому causal comparison. Core candidate07/08 read-set deviations,
один condition hint в blind projection, Critic method-read deviations и
частично tool-only mechanical failures сохранены. Whole-file shell I/O и
model-visible sliced text различаются; strict byte-level conformance не заявлена.
Raw wrappers местами реконструированы из saved artifacts; отсутствующие bytes
не восстановлены догадкой. Эти ограничения не исчезают после successful run.

## Evidence и воспроизведение

`manifest.json` — machine-readable traceability/metrics/hash map.
`raw-evidence.json` — deduplicated lossless byte archive. Private workspace/
profile prefixes tokenized BEFORE compression. Materializer из
`tests/fixtures/forge_evidence_guided_generation_v1/materialize_raw_evidence.py`
восстанавливает explicit producer bindings и проверяет original SHA/byte length
каждого файла. Private paths существуют только в локальном восстановленном
output. Binary synthetic stores/captures остаются локально; deterministic source
builders/inputs/packets/receipts/commands позволяют воспроизводить direct probes.
Native outputs нельзя регенерировать как deterministic goldens.

```text
uv run --locked --managed-python python -B -m unittest -v tests.test_forge_evidence_guided_generation_v1
uv run --locked --managed-python python -B -c "from pathlib import Path; from tests.test_forge_research_flow_reliability_v1 import create_episode_fixture; p=Path('local/forge_evidence_guided_generation_v1/source-base'); create_episode_fixture(p) if not p.exists() else None"
uv run --locked --managed-python python -B tests/fixtures/forge_evidence_guided_generation_v1/growth_probe.py
uv run --locked --managed-python python -B tests/fixtures/forge_evidence_guided_generation_v1/materialize_raw_evidence.py docs/evidence/forge_evidence_guided_generation_v1/raw-evidence.json local/egg-raw
```

Growth source prerequisite создаётся только в fresh disposable location
existing fixture owner. На другом компьютере lossless materialization требует
явно заданных original producer workspace/profile bindings; default bindings
пригодны только на исходном producer. Hash proof относится к inventoried bytes,
не восстанавливает отсутствующие tool-only captures.

Roundtrip/private-prefix scan и independent reviews привязаны в manifest;
exact-head CI/readiness имеют отдельные live receipts. Никакого alpha/OOS,
strategy promotion, live migration/deploy/provider/holdout/wallet/money.

## Factory Fit, horizon, rollback

FULL_REVIEW: bounded context/capacity полезен ordinary generator и Critic;
history/authority guards retained, native uncertainty не замаскирована.
Execution-to-cashflow contribution — меньше rediscovery/operator repair;
NetReturn/chronology/executable economics не измерены.
CAPABILITY_RADAR_NOW=NONE. WATCH=order-preserving representation только после
paired measured bottleneck при достаточном support, не после small-N/transport.

Rollback plan: остановить fresh producer новой policy только для новых
допустимых runs, сохранить reader1.5/1.1 и старые bytes. Не удалять records,
не менять quotas, не превращать смотренный evidence в unseen. Legacy/readback/
cold-recovery tests выполнены; production settings rollback не выполнялся.

Следующая decision — только реальный delivery gate после независимой проверки
и exact-head CI. Полную native formulation capability этот атом не объявляет;
новый science/live/repair cycle требует отдельного exact scope.
