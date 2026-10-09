# A4 — PaperPlane readonly freshness

`PAPER_PLANE_READ_FRESHNESS_V1`, 2026-10-09. F02 исправлен на кандидате:
новое owner-чтение видит committed position и current runtime policy через
общий `PaperPlaneStore`, включая живой WAL. Результат synthetic/offline;
merge и deploy этим отчётом не подтверждаются.

Base: `fb65d69f6e48c49b26937bb6caf324b3417b094e`.
Точные head/tree, reviewed inventory и role verdicts находятся в соседней
[completion evidence](../../evidence/paper_plane_read_freshness/a1_delivery_completion_evidence_v1.json)
и [independent review](../../evidence/paper_plane_read_freshness/a1_delivery_independent_review_v1.json).
PR/CI/head перечитываются из GitHub перед machine merge-readiness;
сохранённый локальный PASS не заменяет этот gate.

| Public P6 при открытом writer | Неисправленная база | Кандидат |
|---|---|---|
| Позиция после committed exit | `OPEN`, stale | `UNRESOLVED`, 2/2 |
| Current policy | revision1 / cap30, stale hash | revision2 / cap20, writer hash совпадает, 2/2 |
| Следующий commit и owner read | дефект воспроизводится | revision3 / cap15, writer hash совпадает, 2/2 |
| Исторический admission | 30 | 30, сохранён |
| Бизнес-состояние после GET | проверялось отдельно | SHA256 всего SQLite schema/data dump до/после равны, 2/2 |
| Запрещённые созданные файлы | — | 0 |

Полные actual hashes, environment и команды повторения — в
[vertical acceptance](../../evidence/paper_plane_read_freshness/a1_vertical_acceptance_v1.json).
Baseline повторён адресно на base: два assertion failures `OPEN != UNRESOLVED`.
Исторический P6 пакет сохранён: SHA256 `23d3ca241fd93263b17ebae3e47c3e98c2ef55857b1f0e2377128e189bdc02f0`.
Его безусловный `status=FAIL` не используется как verdict исправления.

Общий connection owner использует обычный SQLite `mode=ro`; readonly
проекция получает один read snapshot и освобождает его до следующего запроса.
Operations/economics/current policy согласованы внутри него; HTTP использует
уже вычисленную economics. Lifecycle переиспользует тот же owner.
Reader и source status принадлежат request thread, reader закрывается после
materialization. Два пересекающихся GET не закрывают snapshot друг друга;
HTTP собирает model из готового результата без повторного обращения к cache.
Commit во время чтения виден следующему чтению, а не обязан попадать в уже
начатый snapshot. Immutable fallback текущего runtime удалён из design.

Missing root/DB даёт `NOT_PRESENT`; corrupt, реальный отказ доступа OS и
SQL read failure дают `UNAVAILABLE` / `RUNTIME_SOURCE_UNAVAILABLE` в
существующем vocabulary. Позиции и policy не подменяются старым успехом,
пустой inventory или нулевым PnL. Совместимость с `journal_mode=DELETE`
проверена; SQL write через readonly connection отвергается.

Владелец отдельно разрешил native SQLite `-wal/-shm` при readonly GET.
Это требуется обычному [SQLite WAL reader](https://www.sqlite.org/wal.html).
Purity допускает создание/изменение только этих двух sidecars. Data-root,
БД, таблицы, migrations/checkpoint/repair и business writes запрещены.
Main DB и все прочие файлы проверяются по hash; полная logical business
inventory проверяется независимо от `total_changes` одного connection.

На Windows отказ доступа подтверждён эксклюзивным OS handle и отдельным
`PermissionError`, а не декоративным chmod. Linux использует реальный отказ
через права файла; этот case входит в execution-domain CI без skip.
Локальная среда: Python3.13.14 / SQLite3.53.1 / uv0.11.29.
После исправления ownership повторены 187 execution-domain tests: 185 PASS;
два прежних пропуска —
`LOCAL_A4_ABSENT`, отсутствие отдельного live evidence, не пропуск новых A4
проверок. Первые сбои сохранены: неполная HTTP/lifecycle fixture, SHA drift
до sync и purity expectation до owner clarification. Они исправлены в scope;
первый review дополнительно выявил общий cache reader между GET. Его
детерминированный overlap reproducer завершил Windows process с
`0xC0000005` до ownership fix; после fix оба GET проходят и закрывают только
свои handles. Общий полный local merge gate не запускался.

Recovery: обычный code revert без data migration. Он вернёт прежний stale
readback и не является решением свежести. Чужая generator branch и её dirty
работа сохранены в исходном checkout. F01/F03/F04 остаются открыты;
F04 — несогласованная классификация состояний риска, завершённости и drain:
A4 обеспечивает свежесть чтения, но не устраняет это расхождение.
`CAPABILITY_HEALTHY` для Post-Forge / Pre-Trade не заявляется. Нет alpha,
scientific acceptance, реального look/holdout, provider calls, LIVE или deploy.

## Один NEXT_SCOPE

Рекомендация: `POST_FORGE_EPISODE_DECISION_CONTINUITY_V1` — bounded offline
increment F01. Теперь owner видит правду, но обычного producer, который
превращает timely episode prefix в решение, всё ещё нет. Это следующий
разрыв перед исполнением; external attempt/result consumer F03 следует позже.

Input: frozen `StrategyVersion1.1`, version/hash recipe и source-bound
`ListA@T0`, episode identity и минимальный collector prefix с отдельными
event/observed/available/ingested times. Synthetic правило:
`ListA@T0 AND delta(H,E300,E1800)>0`, fixed exit E3600. Для T0=12:01:10Z
resolver назначает E1800 на grid12:35, decision cutoff остаётся **12:40**.
Output: обычные deterministic `SignalDecision` / `ExitDecision` с episode,
recipe, strategy hash, source refs, availability и typed refusal; существующий
PaperPlane принимает их без второго decision owner.

Reuse: `hfic_research_scope` и существующие list/recipe owners, текущий
point resolver и collector prefix reader, decision validators и durable
PaperPlane identity/restart guards. Replay и timely prefix должны идти через
одного semantic owner; зрелый research dataset нельзя выдавать за ранний feed.
Новый список-алиас не создаёт новый look или trade; episode не сводится к mint.

DoD на том же independent oracle:

| Case | Проверяемый результат |
|---|---|
| O1: A TRUE, H60→66, timely, также sourceB | Одна ENTER identity/effect на episode |
| O2: тот же mint, другой weekly episode, A FALSE | NO_ENTER, membership не наследуется |
| O3: A TRUE, H60→60 | NO_ENTER |
| O4: H(start) missing | Typed unavailable, без zero-imputation |
| O5: A UNKNOWN | Coverage refusal до чтения numeric values |
| O6: H(end) available после cutoff | Значение не используется, late/missing явно |
| O7: O1 после restart | Saved identity/effect, без повторного admission |
| O8: меняется только future E14400 | Decision/prefix неизменны, loader не читает point |

Дополнительно: list-only без фиктивного numeric predicate, aliases,
`exactly2` против `atLeast2`, новый selector/window меняет question/version;
новая версия не ломает exit старой открытой позиции.

Decision-critical unknown: какие frozen recipe outputs уже имеют достаточную
execution eligibility и как получить prefix до maturity через существующий
reader с тем же semantic owner. Самый дешёвый falsifier — O1/O5/O8 через
этот обычный путь. Нельзя обходить maturity/availability защиту ради PASS.

Ограничения next: только disposable offline inputs; никаких настоящих
scientific looks/holdout, market/provider calls, внешнего execution, LIVE,
deploy, новых зависимостей и изменений risk/admission semantics. Эта
рекомендация не начинает соседнюю реализацию. `NEXT_MODEL_EFFORT=SOL_XHIGH`.

Product Horizon: `NOW=NONE` для нового инструмента. WATCH — F01 после
post-merge readback A4: ценность — обычное своевременное решение; стоимость —
один bounded offline vertical; риск — потеря PIT/episode lineage; owner —
GOAL_OWNER, activation trigger — отдельная exact task authority.
