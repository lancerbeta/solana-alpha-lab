# Окончательный bounded audit: COMPLETE_WITH_FINDINGS

На продукте `fbac5449f6dd22a7bc066114109be8bbed830447` подтверждены настоящий
численный путь Spec 1.4, сохранение результата/passport/атомарных records,
холодный повтор, guards/recovery и потребление обычным dossier. SC06 завершён.
Сквозное научное подтверждение упирается в доказанный product/contract gap:
**у принятого List A протокола нет accepted confirming producer с reservation
до чтения значений и substantive scientific evidence.** Аудит завершён;
научного PASS, готовой стратегии или полного lifecycle нет. Git delivery
и merge проходят отдельные machine gates.

| Ветка | Подтверждённый результат | Evidence |
|---|---|---|
| A, SC00–SC06 | Native COMPLETE / INCONCLUSIVE; независимая арифметика, actual artifact/passport/records, cold replay, guards, оба crash boundaries | [numerical.json](../../evidence/science_lifecycle_smoke_v1/numerical.json), [sc06.json](../../evidence/science_lifecycle_smoke_v1/sc06.json), [readback.json](../../evidence/science_lifecycle_smoke_v1/readback.json) |
| B, SC09–SC12 | SC09 reachability PASS; SC10–12 BLOCKED_PRODUCT_CONTRACT. Confirming trials не запускались | [chronology.json](../../evidence/science_lifecycle_smoke_v1/chronology.json) |
| C, SC07–SC08 | Actual A completion DIRECT; dossier COMPLETED / BLOCKED / PAUSE; cold REPLAY_IDENTICAL. STALE_EVIDENCE_SNAPSHOT и PROMOTE_BLOCKED | [readback.json](../../evidence/science_lifecycle_smoke_v1/readback.json) |

SC06 меняет matched future returns на −0.20, оставляя LIST comparator неизменным:

| Метрика | base-v3 | changed |
|---|---:|---:|
| mean M, M=10 | 0.10 | −0.10 |
| LIST contrast, C=10 | 0.11 | −0.09 |
| MIXED contrast, C=D=20 | 0.055 | −0.045 |

Fraction oracle проверил результаты обеих веток. Native membership совпала
во всех полях, кроме content-addressed `release_id`: он обязан меняться при
изменении source bytes. Exact episode IDs, роли и D/M/C остались прежними.
Отдельно прочитаны только native Parquet prefix rows E0..E1800: canonical
row digest совпал между мирами; будущие typed_value эта проверка не читала.
Source hashes связаны с actual classifier и passports. Оба changed result
повторены в новом контейнере: evaluator=0, target decode=0, unchanged state.

Арифметика включает median/downside/type-7 quantiles/ES10, cohort/calendar
coverage и missing-stress MODEL. [Clock geometry](../../evidence/science_lifecycle_smoke_v1/chronology-geometry.json)
проверяет 20 E1800/E14400 metadata cells для 10 matched episodes. MIXED
сравнивает M со всем D, поэтому его contrast вдвое меньше LIST.

Проблемы разделены в [findings.json](../../evidence/science_lifecycle_smoke_v1/findings.json):

- Product gap: accepted chronological producer → pre-values reservation →
  substantive evidence. Frozen replay, schedule compile, diagnostics и quote
  capture не выполняют тот же estimand; эквивалентный путь не найден.
- Ошибки audit kit: Windows bind timeout, response field, mutable clone lookup,
  foreign RUN attribution, унаследованные quote question/estimand и лишний
  Catalog binding. Corrected base-v3 зарегистрирована до classification/run;
  старые specs/results/failures сохранены без refunds. Base-v2 guard/recovery
  specimens — segments с теми же recipe/sources/masks.
- Ожидаемые отказы: COMPLETE остаётся INCONCLUSIVE; PIT/population/HOLDOUT
  UNKNOWN, qualifying obligations MISSING, evidence BLOCKED и PROMOTE_BLOCKED.
  Технический RUN не заменяет научное подтверждение.
- Ограничения исходного аудита: SC06 storage stop закрыт owner continuation;
  ordinary definition registration и blind Actor по-прежнему не доказаны.

FULL_PRODUCT_PATH относится только к «Spec1.4 → committed numeric artifact»
и «actual RUN → ordinary dossier → PAUSE». Scripted Actor/Critic и definition
fixture остаются SEGMENT_PRODUCT_PATH. StrategyVersion, activation и PAPER
не запускались; guards/thresholds/Spec semantics не ремонтировались.

Учет: **6 MAIN / 10 evaluator invocations / 0 B / 0 LLM science trials**.
MAIN cap исчерпан. Все interrupted/failed invocations включены; прежние 22 MAIN
из #403 — отдельно. [Ledger](../../evidence/science_lifecycle_smoke_v1/attempts.jsonl)
сохраняет native sequence и отдельно clocked operational attempts; для host
attempts без достоверного времени сохранён timestamp UNKNOWN.

[Footprint](../../evidence/science_lifecycle_smoke_v1/footprint.json) измеряет owned
file allocation host + два volumes + container RW. На замере после SC06 и allocation-only probes известно
**556.94 MiB из forward cap 640 MiB**, test environment без checkout —
**487.30 MiB**; финальный live readback после Git content сохраняется отдельно.
Shared preexisting image — ещё 508.97 MiB, новых images нет. Это не физический
рост Docker VHD. VHD growth, allocation logs и directory metadata UNKNOWN.

Исходный cap 512 MiB действительно был превышен: Git hook создал локальную
.venv, known total достиг **673.93 MiB**, превышение **161.93 MiB**. Факт
сохранён в [budget-continuation.json](../../evidence/science_lifecycle_smoke_v1/budget-continuation.json).
После проверки процессов и отсутствия shared/reparse links удалена только
разрешённая .venv — **164.62 MiB**. Научные stores, trials, receipts и caches
сохранены. Mandatory Git hooks используют existing locked shared runtime.
640 MiB действует только вперёд; прежняя история не пересчитана.

Воспроизводимость: offline verifier требует locked dependencies; native cold
replay требует retained volumes и локального exact image ID. Fresh capture
не разрешён exhausted MAIN cap. Первичная ручная подготовка Docker volumes
не является clean-host one-command bootstrap; см. [REPRODUCE](REPRODUCE.md).
Десять offline falsifier tests PASS, включая UNKNOWN allocation и противоречивый footprint.

**Один NOW repair:** [List A confirming producer/reservation/consumer](REPAIR_PRD_SSD.md),
PROPOSED_ONLY. Сначала отдельный exact task и sample/data authority; method,
floors, estimand и scientific guards сохраняются. Новый сервис не требуется.
WATCH: после его cold substantive evidence повторно оценить science decision.
Текущий audit не даёт repair, sample activation, provider или merge authority.

Честные UNKNOWN: AGENT_BEHAVIOR_UNVERIFIED; ordinary definition registration; неполная история ранних replay read traces;
PIT/population/HOLDOUT в dossier; costs ABSENT и NetReturn false; opaque hash-byte
reads не инструментированы; physical Docker storage рост не установлен.

Финальный независимый review выявил и исправил audit-kit resource defects:
UNKNOWN container allocation теперь запрещён; сумма и остаток cap пересчитываются;
allocation checks работают до и после даже короткого child; telemetry exception
останавливает только owned child через finally. Allocation-only probes не читают
scientific sources и не добавляют MAIN/evaluator. Это kit correction, не product repair.

Ранние replay receipts использовали общий alias и могли перезаписать прежний raw
trace. Trial ledger/native stores и экспортированные current witnesses сохранены,
но полный per-attempt replay trace history — INCOMPLETE/UNAVAILABLE. Повтор native
replay на исходных retained worlds по этому runbook запрещён; доступны offline
проверка и read-only export. Новая authority и сохранение прежних aliases обязательны
до любого следующего native repeat. Этот дефект не выдаётся за сохранённую историю.
