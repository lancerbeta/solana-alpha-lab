# FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1 — Git readout

Результат: ограниченное чтение call diagnostics для read model, полного packet,
watch и pulse; caps двух oneshot; heartbeat зависит от свежего bounded snapshot.
Репозиторий описывает способность и процедуру. Текущие SHA, timer state, память,
данные, backup/archive и Telegram устанавливает только датированный readback VPS.
Это Git-кандидат, не live commissioning и не canonical DONE.

## BEFORE / AFTER

Windows / CPython 3.13.14. Каждый потребитель запускается в отдельном процессе;
wall охватывает полный вызов, RSS — OS lifetime PeakWorkingSetSize, включая imports.
Fixture `one`: 2,048 старых calls по 65,725 bytes payload, 128 недавних calls,
6,000 candidates, 12,000 due, 2,500 RDP files; SQLite 215,031,808 bytes.

| Потребитель | BEFORE wall, s | AFTER wall, s | BEFORE peak, MiB | AFTER peak, MiB |
|---|---:|---:|---:|---:|
| Read model | 0.915 | 0.127 | 330.0 | 72.2 |
| Полный packet | 1.225 | 0.466 | 330.2 | 74.3 |
| Watch dry-run | 1.169 | 0.436 | 329.9 | 73.9 |
| Pulse dry-run | 1.171 | 0.443 | 330.5 | 74.2 |

BEFORE каждый потребитель возвращал/декодировал 2,176 полных call payload.
AFTER сканирует 2,176 timestamps и возвращает только 128 scalar call projections;
полных call payload в Python: 0. Due/candidate payload ещё декодируются существующими
bounded iterators; это не заявление о нуле всех JSON decodes в packet.

При удвоении старой истории (4,096 old calls; SQLite 350,363,648 bytes),
не меняя recent window, peak полного packet/watch/pulse: 73.7 / 73.5 / 74.0 MiB.
Рост памяти не пропорционален историческим payload. Scale regression проверяет
также отдельный полный packet с 1,024 → 2,048 old calls.

Стресс AFTER: SQLite 2,244,997,120 bytes (2.09 GiB); 32,768 old calls,
те же 128 recent, candidates/due/RDP. Watch: 73.8 MiB / 1.717s;
pulse: 73.4 MiB / 1.703s; полный packet: 74.0 MiB / 1.752s.
Локальные пороги <512 MiB и <120s выполнены. Это синтетические данные;
эквивалентность текущей VPS-базе и live MemoryPeak не проверялись.

Полные числа и метод: `docs/evidence/factory_operability_bounded_call_diagnostics/a1_resource_profile_v1.json`.
Повторить: `tests/operability_bounded_call_profile.py create --root <LOCAL_FIXTURE>`;
затем fresh processes `measure --root <LOCAL_FIXTURE> --consumer read_model|packet|watch|pulse`.
BEFORE выполнен до изменения production modules на базе
`5263abdd327455f239767c0c31855909f90435b7`; fixture builder входит в PR.

## Что изменилось и как проверено

- Store делает timestamp-filtered SQL projection пяти диагностических полей;
  нет all-call list, historical payload decode, ORDER BY всех payload или fallback.
  Provider state агрегируется потоком; due pressure/censored/X/candidates используют
  существующие scoped iterators. Индексы, retention и scientific bytes не меняются.
- 24h boundary и campaign scope сохраняются. STARTED и чужой primitive не дают
  recovery; равные timestamps не являются более поздним успехом. Poll clocks
  выбираются по времени, включая microseconds. Invalid/future/invalid payload дают
  `UNKNOWN`/null counts; известный unresolved failure остаётся True.
  Invalid projection не доказывает ни failure, ни recovery. UNKNOWN получает
  отдельный incident `CALL_DIAGNOSTICS_UNKNOWN`, не смысл confirmed discovery gap.
- Обе service templates: MemoryMax=768M, TimeoutStartSec=180s. Watch cadence 15m.
  CLI открывают operational SQLite read-only, с WAL visibility; missing store не
  создаётся. Старый source_snapshot/RDP repair и signal calibration сохранены.
- Heartbeat читает максимум 65,536 bytes snapshot; stale/missing/invalid → NO_PING.
  Configured path не импортирует operational packet/store. Fresh snapshot не
  подтверждает Telegram. Fake transports проверяют success/failure/retry/dedupe/
  recovery; никакой реальной отправки в этом атоме.
- 124 focused + 15 semantic tests PASS, включая старые два repair suites, полные вертикальные
  consumers, executable pulse CLI и новый memory-scale regression. Independent
  verdicts и exact bindings — в canonical delivery evidence; до их PASS кандидат
  не готов к merge. Exact-head CI/merge-readiness проверяются отдельно перед фразой.
  UNKNOWN не закрывает прежний provider/source incident как RECOVERED.

## Catalog / semantic discovery

Изменённые asset hashes и generated projections обслуживает harness_sync.
Исходный запрос `campaign successor` вернул пустой search result; исправление
ограничено terms существующего SEM-LIVE-COLLECTION плюс четыре
gold queries. После генерации проверяется следующий routing:

| search-routes query | Top route | resolve-route operator root |
|---|---|---|
| VPS OOM | SEM-REMOTE-OPS-RECOVERY | FACTORY_UNATTENDED_OPERABILITY.md |
| Telegram watch | SEM-REMOTE-OPS-RECOVERY | FACTORY_UNATTENDED_OPERABILITY.md |
| campaign successor | SEM-LIVE-COLLECTION | FACTORY_LIFECYCLE_COLLECTOR.md |
| collector writes data | SEM-LIVE-COLLECTION | FACTORY_LIFECYCLE_COLLECTOR.md |

Все routes сохраняют `authority_granted=false`, `EXTERNAL_GATED_READBACK`.
Collector runbook остаётся существующим root binding/operator asset; его
дублирование в root assets превысило 16 KiB budget и поэтому исключено.
README уже ведёт к правильному recovery route; менять его не требуется.
Generated FACTORY_SEMANTIC_MAP / OPERATOR_NAVIGATION / PROJECT_MAP руками не редактируются.
Preflight обнаружил SEPARATE Catalog pin в TASK-21 owner-pulse evidence:
обновлены только SHA/bytes этой ссылки и exact managed scope; историческая
приёмка и scientific fields не изменены.

## UNKNOWN и операционная граница

UNKNOWN: текущий deploy SHA, actual timer state, live resource peak/время,
source/RDP progression, backup/archive verification и Telegram delivery.
По owner-provided readback 2026-10-02 отчётные timer были остановлены,
collector/renewal оставались включены; этот PR не проверял и не изменял хост.
Off-host receiver не подключён: оповещение о смерти VPS = NOT_CONFIGURED.
Timestamp scan остаётся O(ledger rows); single-row/native JSON и filesystem
costs тоже нуждаются в host commissioning. Измерений хватает для Git PR,
но не для обещания беспроблемной работы на любом объёме.

Read-only continuity checkpoint после renewal 2026-10-03 09:40 МСК:
тот же cohort family, окно через 2026-10-05 13:00 UTC, актуальная authority и
доказанный rollover. Возьмите exact IDs из свежего status, не из исторического
Git отчёта. Если continuity не доказана — exact blocker владельцу; не authorize.
Автоматизация не создавалась, будущий readback ещё не выполнен.

## Deploy / rollback после отдельного разрешения

Pre-deploy probe теперь использует только scoped primary-key / bounded rowid
SQLite queries с mode=ro и без payload_json; generic status не вызывается.
Timer readback показывает installed disabled units. Canary повторяет effective
unit environment и backup sink, сохраняет unit через remain-after-exit и
проверяет численный MemoryPeak/monotonic clocks; missing peak остаётся UNKNOWN.
Canary повторяет фактический sink соответствующего CLI: watch использует
env-selected sink, существующий pulse packet — git-side default. Совпадение
pulse с принятым backup envelope требует отдельного readback; mismatch
останавливает rollout. Production code этой операторской правкой не менялся.

Точные команды и stop criteria: `docs/operator/FACTORY_UNATTENDED_OPERABILITY.md`,
раздел Commissioning. Сначала dated pre-readback (SHA/backup/archive/disk/
collector/source/RDP/timers), затем existing owner-gated exact-SHA release.
Установить templates, bounded watch dry-run; PASS требует <512 MiB / <120s.
Включить watch, доказать два цикла/snapshot/incident/recovery/delivery. Отдельно
bounded pulse dry-run и его реальная delivery. Off-host receiver — своё решение.
При провале выключить проблемный report timer/service, exact-SHA rollback,
collector/renewal и все runtime/scientific bytes сохранить. Отчётные timer
после rollback остаются выключенными до повторной commissioning.
Через 7 и 30 дней — короткий result check из того же runbook.

Неизменённые live boundaries: zero provider/API/RPC calls, zero live SQLite
mutation, zero retention/delete, zero campaign authorization/parameter changes,
zero deploy, zero real Telegram/heartbeat. GitHub transport обслуживает только
этот PR. STOP: точная owner merge phrase после exact-head CI и readiness.

Factory Fit: FULL_REVIEW; capability radar NOW=NONE. NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH
для Git readback; отдельная commissioning с live recovery требует SOL_XHIGH.
