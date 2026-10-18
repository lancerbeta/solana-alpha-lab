# Исследовательские фрагменты V1 — owner readback

Полка находится в существующей workstation-консоли: `/research?kind=fragments`.
Карточка, Forge и CLI читают один source snapshot из прежнего ResearchStore.
Этот checkpoint относится к кандидату PR; реальное включение ещё не выполнено.

| Уровень результата | Состояние и основание |
|---|---|
| `CAPABILITY_DELIVERED` | **WAITING** принятия версии: реализован связный путь registration → projection/HTTP GET → ordinary prior/context-view/freeze → настоящий import caller → native bounded measurement → cold resume. Проверки и границы — в [validation.json](validation.json); exact-head CI, review и merge имеют отдельные gates. |
| `SEED_REGISTERED` | **WAITING** post-merge scope. Реальный registration preview прошёл; карточек пока 0. Exact seed и проверка неизменности источника — [source-readback.json](source-readback.json), [entry.json](entry.json). |
| `PLAN_ENABLED` | **BLOCKED — HOLDOUT_UNRESOLVED**. Текущий `protection/assignments` не даёт native complete inventory. Исторический bootstrap pin as_of 2026-10-06 и пустой Git registry не доказывают сегодняшнюю полноту. План — proposal, не enabled artifact. |
| `NEW_EVIDENCE_OBSERVED` | **WAITING** разрешённого плана, закрытого окна и полного импорта. Новых реальных market looks нет; исходный MAIN остаётся 1. |

Первый фрагмент — предполагаемый **контекстный фильтр**: на E1800 reported price
E300→E1800 снизился, а reported USD-liquidity return неотрицателен. Исходный
target — price-relative mark proxy E1800→E5400; baseline SAME_DECISION_ELIGIBLE
включает matched. Наблюдались 15 matched / 213 baseline, ES10 −2.2485% / −54.1943%,
четыре зависимых дня и tail mass 1.5. Reference/exit event times UNKNOWN;
исполнение, net return и строгий post-D target не установлены. Ещё одно окно
того же proxy даст exploratory информацию о повторяемости, не подтверждение торговли.

Источник: `HFIC-CAND-297E8EF0F13F`, result
`HFIC-ART-DISCOVERY-7805D0BDB4432682C450578B66F060F31E21C578`,
SHA `39028f4afacd8c0af9575ee37bf0447be10c19f147fda56bcb62ce9114d68c87`.
После регистрации ожидается `RFV-8228C9408D18DE5CC98C9C1EA924B1C8`.
Scout H/L — holders decline и абсолютная liquidity — другой механизм.
Его результаты сюда не импортируются. Известная широкая adaptive exposure
сохранена в исходных restrictions и обычном Forge context; независимого OOS нет.

Forge получает typed fragment capsule внутри существующей bounded prior memory:
смысл, роль, исходное и каждое последующее evidence, missingness, ограничения и
exact source refs. Материальная ссылка сохраняется в frozen Critic closure.
Отрицательный или INCONCLUSIVE результат остаётся видимым; автоматических
PROMOTE/KILL и усреднения ES10 разных окон нет.

Перепроверку вызывает **существующий local production import path**:
`live_cohort_vanilla_path → unpack/replay → import_episode_release → run_due`.
Import сначала коммитится; отдельный `fragment_refresh` сообщает результат или
блокер. Duplicate import и explicit CLI `run-due` восстанавливают native pending
operation/result без второго списания. Один вызов делает максимум одно новое
измерение. GET ничего не запускает. Нового scheduler нет; выключенный workstation,
отсутствующий импорт или blocked plan не образуют автономный lifecycle.
Если result уже записан, но ссылка CHECK ещё нет, полка сообщает о metadata
recovery через run-due. Отдельный отказ плана не скрывает проверенное evidence.

Исправления content review PR #416: readback показывает exact no-result attempt
и удержание universe gate при pause/expiry; продолжение проверяет последнюю native
версию operation. Непригодная попытка завершается существующим явным native STOP,
без CHECK, научного verdict или возврата резервации; следующий run-due выбирает
следующее разрешённое окно. Новый plan binding не делает старую попытку совместимой.
Полка и Forge получают одинаковую bounded поддержку по дням/когортам, сохранённые
признаки зависимости/repeated mint и observed/required/met/reason information rule.
Полный источник остаётся по exact result_ref, через bounded discovery-show.

Единый post-merge proposal: зарегистрировать exact seed и, **после получения
source-owned текущего complete protection inventory и утверждения scope**, включить
одно окно admissions **2026-10-20 00:00Z → 2026-11-17 00:00Z**. Input closure
**2026-11-20 01:00Z**, deadline **2026-11-24 00:00Z**; максимум **1 evaluation**,
**10M raw metadata rows**, native stricter cap сохраняется. Только
EXPLORATORY_MONITORING; Forge/Scout access EXPOSED_OR_UNKNOWN, protected holdouts
исключаются. Collection и Scout не меняются. Cadence/lifetime можно пересмотреть
native plan revision до соответствующих окон, без PR и без подгонки по outcomes.

По exposed metadata ожидается примерно 105–168 matched за 28 полностью покрытых
дней против 26–42 за неделю. Это условный ориентир из четырёх наблюдавшихся cohorts,
не power estimate. Одно длинное окно полезнее четырёх малых хвостовых оценок.
Information rule: matched ≥60, ≥14 calendar blocks, tail mass ≥6; adverse ES10
delta 5 п.п. создаёт attention, не научный verdict. Нужны **все 28 суточных releases**:
отсутствующий день не считается пустым и не исключается молча. Неполный импорт
оставит план waiting/blocked. При позднем согласовании даты необходимо сдвинуть
prospectively. Точные local requests и hashes сохранены в
`local/research_fragments_v1/post-merge-proposal.json`; native plan preview ещё
невозможен до регистрации карточки. Одобрение плана не заменяет protection gate.

Следующий шаг — fresh exact-head PR readiness и решение владельца по merge.
После merge разрешена регистрация exact seed, полка и ordinary prior readback;
включение плана отдельно требует current protection и exact scope; нынешний protection gap должен быть закрыт его
настоящим владельцем, без выдуманного complete-empty. Реальные registration,
enablement и первое новое окно подтверждаются отдельным native readback.

Cleanup: disposable synthetic fixtures/logs/diffs ограничены
`local/research_fragments_v1/disposable`; после завершения проверок и handoff они
удаляются с измерением объёма. Worktree для этой задачи не создавался. Branch/history,
canonical ResearchStore и recovery прежнего MAIN сохраняются. Итоговый cleanup
receipt относится только к принадлежащим этой задаче disposable outputs.
