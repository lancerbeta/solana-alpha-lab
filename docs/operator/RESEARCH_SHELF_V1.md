# Полка исследовательских намерений

Полка сохраняет вопрос и условие возвращения. Она принадлежит metadata plane;
native планы, бюджеты, Critic, результаты и научный допуск остаются у своих owners.
Контракт: `docs/contracts/research_shelf_v1.md`. Binding:
`configs/research_shelf_v1.json`. Route: `SEM-RESEARCH-SHELF`.

SMIAL: repository `lancerbeta/solana-alpha-lab`, branch `research-log`, prefix
`capsules/research_shelf_v1/`. SCOUT — отдельный private namespace; не зеркалировать
его карточки или rich dossiers в публичную Кузню. Code/schema приходят через PR.
Публикация выключена по умолчанию: реальная data-ветка и seeds ещё не commissioned.
Это не запрещает проверять writer на disposable local Git. Scoped wrapper готов
для того же алгоритма после приёмки; новый transport engine не создаётся.

## Один обзор на верхнем входе

До нового научного preflight агент разрешает semantic route, один раз обновляет
отдельный bare metadata cache и читает pinned snapshot. Cache находится вне
frozen execution checkout. Ни native функция, ни машинный glance не делают
fetch/push, не вызывают runner и не создают reservation. Самостоятельный helper
или следующая tool invocation не начинают новую top-level research session.

```text
uv run --locked --managed-python python -B scripts/research_shelf.py refresh --cache <separate-bare-cache> --output <snapshot.json>
uv run --locked --managed-python python -B scripts/research_shelf.py review --snapshot <snapshot.json>
```

Для saved native readback разрешённой metadata operation к `refresh` или `review`
добавляются `--data-root <existing-rdp>` и/или `--source-bundle <exact-sources.json>`.
Это read-only источники. Snapshot carries exact commit, file manifest hash и
head observation с временем проверки; не отдельный operational registry.
TTL 86400 секунд относится только к cached head observation, не к научному сроку.
Дальнейший pinned read сохраняет `REMOTE_VERIFIED` в пределах TTL. Неподтверждённый
snapshot — `UNVERIFIED_PINNED`, старый — `STALE_AS_OF`; отсутствующий/повреждённый —
`UNAVAILABLE`, missing data branch — `NOT_INITIALIZED`, неполный — `INCOMPLETE`.
Возраст карточки, cached observation и native hard deadline — разные величины.

Default machine snapshot: `local/research_shelf_v1/snapshot.json`. Явный локальный
snapshot можно передать через process-local `SMIAL_RESEARCH_SHELF_SNAPSHOT`.
Его физическое имя не записывается в научный receipt или public output.

| Public entry | Общий review и граница |
|---|---|
| Fresh `/hypothesis-forge` | Skill/command reviews shelf before first native preflight; один отдельный refresh |
| `scripts/hypothesis_forge.py forge-run` | `_emit_run` adds derived `shelf_summary` on success and every blocked/missing-root path, after receipt hash |
| `scripts/run_factory_experiment.py` | Один pinned glance до `FactoryApplication.start`; summary только в returned readout |
| `scripts/run_factory_ordinary_market_hypothesis.py` | Тот же pinned reader на top-level entry; без hidden transport |
| Direct preflight/discovery/operator helpers | Top-level Forge skill/command or semantic operator review; helpers keep native admission and are not wrapped separately |
| Frozen resume / RFV import / `research_fragments.py run-due` | Отдельный metadata CLI review; не менять frozen code/refs/inputs ради glance; старый executable допустим |

Missing shelf never заменяет native `next_action` и не запрещает независимое уже
разрешённое recovery. Due/event/expiry требуют внимания; scientific action всё
равно проходит actual native protocol, scope, budget, protection и source gates.

## Источники и связи

Два узких adapter: SMIAL `research_fragments.source_snapshot` и exact saved Scout
status. У Scout проверена существующая schema `marcopolo.concurrent-choice-feasibility`
с `PASS|DATA_LIMITED`; это prefix feasibility, **не** разрешение forward evaluation.
Неподдерживаемые readiness schemas остаются UNKNOWN. Adapter не импортирует Scout
и не исполняет его код. Source bundle — список `{source, evidence_ref, raw}`;
`source` — wire SourceLocator, `evidence_ref` — immutable GitRef, `raw` — exact
UTF-8 JSON file bytes как строка. Hash/repository/path/explicit commit проверяются.
Private body остаётся в разрешённом контексте; наружу adapter отдаёт только status/ref.
Scout adapter принимает только exact 40-hex ref. Moving ref без отдельного
source-head observation даёт `UNKNOWN / SCOUT_MOVING_REF_OBSERVATION_REQUIRED`;
свежесть SMIAL shelf не доказывает свежесть private Scout head.

MET/NOT_MET/UNKNOWN определяются сохранённым source status, не формулой из записи.
SOURCE_CHANGED без acknowledged baseline — UNKNOWN. Содержательный defer может
сохранить exact observed evidence в `acknowledged_ref`; тот же MET больше не будит,
но новая review_at работает. MANUAL без review_at — NEEDS_TRIAGE. Native expiry
выводится отдельно, без переноса сроков и запуска задним числом.
SMIAL baseline — derived `REFERENCE` с hash полного native check и refs card,
current plan и monitoring checks. `source_refs` перечислены в observation.
Это не native artifact и не scientific prior: смена plan при прежнем check,
либо check при прежнем plan меняет baseline. Он восстанавливается без registry.

До native шага вычислить stable adoption key (`adoption-key --item ... --revision
... --request-id ...`). Он не содержит ещё не созданный native ID и сам ничего
не создаёт. После шага `link` принимает exact saved identity JSON:
`{session_id,candidate_id,definition_sha256}` плюс тот же request-id, item/revision,
mutation-id, pinned snapshot и read-only RDP. Он готовит metadata revision;
`apply` — отдельная публикация. При сбое публикации повторять прежние prepared
bytes, прочитать exact saved target и дописать только link. MAIN/generation/Critic
не повторяются. Нельзя угадать target по title или сокращённому HYP alias.

`resolve --item` читает adopted revision через exact commit/hash (нужен отдельный
bare cache для readback); `find --input <native-ref.json>` включает CLOSED/history
и помечает отозванную связь `RETRACTED_SOURCE_LINK`. Неоднозначность —
`AMBIGUOUS_SOURCE_LINK`. Для переноса правильной связи применяется новая ревизия.
Уникальность требует одной текущей связи и только доказанно отозванных прочих
matches. Matching ITEM_CONFLICT/ITEM_INVALID остаётся unresolved и блокирует trace.

`resolve --strategy <strategy.yaml> --data-root ...` начинает с exact
`StrategyVersion.source_decision_asset_id`, проверяет immutable PROMOTE manifest,
direct RUN_COMPLETED passport, ExperimentSpec bytes и saved `source_lineage`,
затем native candidate и adopted shelf revision. Latest-PROMOTE view здесь не
используется. Legacy/non-replay или missing source — UNRESOLVED. Никаких новых
StrategyVersion/promotion schemas. Dossier возвращает сохранённые параметры,
риски, adverse/negative evidence, exposure и gaps; link не даёт scientific admission.

## Public/private и commissioning

Secret/path scan проверяет весь outgoing payload, но не понимает приватность
естественного языка. При private origin `apply --public` / `public-check` /
`resolve --public` требуют отдельный owner-reviewed digest **точного минимального**
public payload: `{disposition:EXPLICIT_MINIMAL_PUBLIC_DISCLOSURE,payload_sha256:...}`
через `--disclosure`. Этот инструмент не выдаёт такое одобрение автоматически.
Любое изменение title/statement/intent/reason/change_reason или вложенного dossier
аннулирует digest. Без обоснованного раскрытия сохранить local draft и отказать
в public publication; rich Scout packet не копировать. Это узкая граница review,
не новый ACL engine и не обещание автоматической классификации конфиденциальности.

Real `research-log`, metadata grant и bounded seeds принимаются отдельно после
code capability. До cutover текущие календарные напоминания сохраняются.

Для существующего GitHub transport есть `init-scoped --remote-url ...
--metadata-scope ...` и тот же `refresh/apply --metadata-scope ...`. Scope обязан
закреплять repository/branch/prefix, READ/APPEND, logical owner_scope_ref,
accepted_code_commit и SHA-256 policy bytes из этого commit. Wrapper проверяет,
что code commit — предок локального `origin/main`, policy совпадает и требует
scope, cache находится вне execution checkout, endpoint — только SMIAL, push
не перенаправлен. Он не выполняет fetch main и не меняет source refs/config.
Actual owner permission обязательно: файл scope сам по себе её не создаёт.
Private-origin disclosure проверяется writer'ом перед каждым public batch.
Этап 2 не вызывает этот transport и не выдаёт commissioning scope.

## Рабочий путь после commissioning

Команды ниже требуют уже разрешённого metadata scope; до него допустим только
disposable local Git без `--metadata-scope`. Prepared файлы сохраняются при отказе;
`apply` не меняет их. ID/hash брать из ответа `capture`/`show`.

1. Создать `idea.json`: `{"title":"Проверить сохранённый контраст","statement":"Вернуться после source readback; без запуска науки."}`.

```text
uv run --locked --managed-python python -B scripts/research_shelf.py capture --input idea.json --output prepared.json
uv run --locked --managed-python python -B scripts/research_shelf.py apply --cache <cache> --metadata-scope <scope.json> --input prepared.json
uv run --locked --managed-python python -B scripts/research_shelf.py refresh --cache <cache> --metadata-scope <scope.json> --output snapshot.json
uv run --locked --managed-python python -B scripts/research_shelf.py review --snapshot snapshot.json --all
```

2. Для defer создать `defer.json` с `review` целиком (сохранить event/baseline):
`{"review":{"review_at":"2026-11-20T09:00:00Z","review_by":"2026-11-23T09:00:00Z","event":null},"change_reason":"Осмысленный перенос административного обзора."}`.

```text
uv run --locked --managed-python python -B scripts/research_shelf.py revise --cache <cache> --metadata-scope <scope.json> --commit <snapshot-commit> --item <item-id> --mutation-id <new-uuid> --input defer.json --output defer-prepared.json
uv run --locked --managed-python python -B scripts/research_shelf.py apply --cache <cache> --metadata-scope <scope.json> --input defer-prepared.json
```

3. После отдельно разрешённого native шага записать exact native identity в
`identity.json`. Перед шагом сохранить request-id и принятую revision.

```text
uv run --locked --managed-python python -B scripts/research_shelf.py link --snapshot snapshot.json --item <item-id> --revision <adopted-revision> --request-id <stable-request> --mutation-id <new-uuid> --data-root <existing-rdp> --input identity.json --output link-prepared.json
uv run --locked --managed-python python -B scripts/research_shelf.py apply --cache <cache> --metadata-scope <scope.json> --input link-prepared.json
uv run --locked --managed-python python -B scripts/research_shelf.py resolve --cache <cache> --metadata-scope <scope.json> --snapshot snapshot.json --item <item-id>
```

После apply сначала обновить snapshot для просмотра новой связи. При сбое apply
повторять тот же prepared файл. При LINK_PENDING дочитать exact сохранённый
target и повторить link с прежним request/adopted identity; native шаг не повторять.
PARTIAL link можно обогатить тем же target: refs только добавляются, gaps только
убывают; смена candidate или утрата прежних refs даёт ADOPTION_KEY_CONFLICT.

Private-origin public payload: минимальный текст и refs сначала проверяет owner.
Его exact approval JSON передать через тот же --disclosure до обязательного writer guard:

```text
uv run --locked --managed-python python -B scripts/research_shelf.py apply --cache <cache> --metadata-scope <scope.json> --input minimal-public-prepared.json --disclosure owner-disclosure.json
```

payload_sha256 — SHA-256 canonical JSON body включая revision_sha256, без
завершающего newline файла. Scope разрешает transport; disclosure разрешает
только этот public payload. Инструмент не генерирует owner approval.

## Cloud explicit-ref recipe

Cloud агенту не нужен workstation Source, RDP или code search. Прочитать AGENTS →
SEM-RESEARCH-SHELF → operator/config. Через существующий GitHub доступ:

1. Read `repos/lancerbeta/solana-alpha-lab/git/ref/heads/research-log` и сохранить
   exact `object.sha` как H. 404 означает NOT_INITIALIZED; access error — UNAVAILABLE.
2. Read `git/trees/H?recursive=1`; `truncated=true` означает INCOMPLETE. Выбрать
   только `capsules/research_shelf_v1/`, не выполнять никакой файл из ветки.
3. Read каждый exact path через `contents/<path>?ref=H` (raw UTF-8), проверить
   wire hash, file bytes и parents; fold всех revisions в одном pinned tree.
4. Evidence всегда содержит H/path/SHA-256, а не moving branch URL. Последующие
   show/adopted reads используют exact commit. CLOSED/history остаются доступны.

GitHub code search по default branch не доказывает отсутствие data-ветки. Cloud
transport даёт те же bytes/refs; V1 conformance fixture находится в
`tests/fixtures/research_shelf_v1/`. До commissioning live missing branch не
выдаётся за успешный пустой readback.
