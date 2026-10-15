SMIAL — REVIEW FOLLOW-UP / PATCH PR #407

VERDICT: PATCH_BEFORE_MERGE.
Reviewed head:
b8ed4be809652714065b0db6c54fe454a8129ec7
Base:
b3fb9d8ecffbffda468dccabaa81ca3392da6f15

Архитектурное направление I2 принято. Не перепроектировать backup,
не создавать новый PR или платформу. Исправления — в #407,
с propagation в actual owners и OPERATE_PACKET.

Это findings по маршрутам кода, не результаты fault injection на VPS.
Сначала воспроизведи exact сценарии на disposable native stores.
Если какой-либо finding опровергается существующим production path,
верни конкретный trace/oracle, а не количество зелёных тестов.

P1-1. LEGACY FULL → NEW DELTA: преждевременная проверка recovery closure

Owners:
- remote_ops.py::restore_backup_isolated
- remote_ops.py::restore_incremental_chain_isolated
- remote_ops.py::_verify_recovery_control
- offhost_backup.py::_prepare_checkpoint_operation

Проблема:
_raw_only=True откладывает marker, но не _verify_recovery_control.
Поэтому full проверяется на наличие authority/transition ResearchEvents
до применения delta. Старый mutable-only producer их в full не включал;
новая I2 delta может впервые доставлять эту closure.

Воспроизведение:
1. Создай native ACTIVE/DRAINING scope на base producer b3fb9d8e,
   с настоящими authority/state events в исходном ResearchStore.
2. Его старым mutable-only packager получи full/chain.
3. Новым I2 owner выполни обычный daily checkpoint с delta.
4. Независимо восстанови новый checkpoint штатным entrypoint.

Не подменять old full новым I2 full, просто перепакованным в STORED:
это другой, более лёгкий сценарий.

Ожидаемый результат:
- reader доходит до delta, восстанавливает exact final inventory
  и final control-event closure; marker ставится последним;
- hashes/membership каждого raw звена проверяются как прежде;
- отсутствие event в окончательной реконструкции остаётся отказом;
- standalone неполный исторический backup не получает ложный PASS.

Выбери минимальный совместимый repair. Если правильная миграция
объективно требует нового полного baseline, это должно быть явным
upgrade path до публикации непригодного checkpoint, а не сюрпризом
при disaster restore. Старые bytes/hashes не переписывать.

P1-2. DEFERRED НЕ ИМЕЕТ АВТОМАТИЧЕСКОГО ПРОДОЛЖЕНИЯ

Owners:
- remote_ops.py::_capture_writer_fences / backup_plane_lock
- offhost_backup.py::run_offhost_checkpoint
- scripts/factory_offhost_backup_copy.py
- existing daily/weekly service/timer

Проблема:
WRITER_BUSY → DEFERRED → CLI exit 0. Существующий oneshot не назначает
повтор после освобождения writer. Нормальная краткая конкуренция
может пропустить суточный checkpoint.

Воспроизведение:
Обычный scheduled caller запускается при действующем collector lease
или backup lock. Затем владелец освобождает lock через короткий
нормальный интервал. Никакой ручной второй команды не подавать.

DoD:
- checkpoint автоматически завершается в ограниченном допустимом окне;
- повтор реализован через существующий caller/service, без нового daemon;
- нет force-unlock, остановки collector, параллельных snapshots;
- уже созданный pending operation сохраняет exact identity и bytes;
- долгий busy/исчерпанный retry budget даёт видимый terminal/incident
  и точный resume, не бесконечное ожидание и не ложный backup PASS;
- weekly/daily overlap не создаёт дублирующие работы.

Границы ожидания/backoff выбери по реальной cadence и approved RPO.
Повтор cadence/freshness должен быть частью автоматического пути,
а не инструкцией Петру запустить backup ещё раз.

P1-3. RECLAIM: REBOOT/RESTART ДО РУЧНОГО RESUME

Owners:
- observation_schedule_retention.py::_apply_physical_reclaim
- observation_schedule_retention.py::recover_physical_reclaim
- observation_schedule_store.py::__init__ / _connect
- обычные writable entrypoints и OPERATE quiesce/recovery

Проблема:
После rename original → rollback основной DB-path временно отсутствует.
Обычный writable open не проверяет pending reclaim и способен создать
новую пустую SQLite. После SWITCHED также нет доказанного durable
запрета обычных writes до recovery decision.

Воспроизведение:
Kill отдельного процесса:
- после подготовки new DB;
- между rename и обновлением intent;
- в ORIGINAL_MOVED;
- после SWITCHED до reclaim-resume.
Затем запусти обычный collector/health writable entrypoint новым
процессом ДО ручного recovery — как при возврате enabled units
после reboot. Не ограничиваться вызовом reclaim-rollback из теста.

DoD:
- незавершённый reclaim обнаруживается до создания/изменения SQLite;
- пустой store, новый source UUID, reset grants/debits невозможны;
- exact resume/rollback доступен без ручной правки DB/intent;
- старые и новые данные не смешиваются;
- после resumed/new writes старый rollback запрещён;
- owned pre-intent staging после kill имеет безопасный recovery path;
- после успешной приёмки есть exact завершение recovery и судьба
  rollback/staging bytes, без бесконечного HOT-хвоста.

Переиспользуй существующий durable intent/entrypoint.
Допустима эквивалентная доказанная reboot-safe защита actual units,
но одного --writers-quiesced или инструкции «writers не запускать»
недостаточно. Никакой новой orchestration platform.

P1-4. APPROVED POLICY REVISION → STALE ACTIVE_PLAN → ВЕЧНЫЙ FAILED

Owners:
- install_maintenance_policy
- run_maintenance_step / apply_retirement_plan
- run_checkpoint_maintenance
- retention_control.active_plan и retention_progress

Проблема:
Новая policy оставляет сохранённый план старой revision.
Последующие ordinary runs каждый раз получают PLAN_STALE_POLICY,
оставляют тот же active_plan и не доходят до восстановления workflow.

Воспроизведение:
1. Создай реальный план с несколькими candidates.
2. Выполни часть эффектов; останови процесс.
3. Штатно одобри новую revision с более узкими limits/scope
   или disable → enable.
4. Перезапусти ordinary maintenance caller несколько раз.

DoD:
- старый неразрешённый остаток не применяется;
- выполненные compaction effects, ROWIDs, provenance и cold pins
  не откатываются и не теряются;
- устаревший intent штатно superseded/reconciled;
- следующий допустимый run продолжает под новой approved policy
  без SQL-редактирования и ежедневного вмешательства владельца;
- настоящий candidate/integrity conflict не маскируется
  автоматическим пересозданием плана.

ОБЩИЕ ГРАНИЦЫ

Не повторять полный аудит I1/I3 и все CI ради каждого микропатча.
Расширить существующие native fixtures ровно под найденные seams.
Использовать независимые raw SQLite/file/receipt readbacks:
код и тест не должны подтверждать одну и ту же ошибочную модель.

Защитить A, B, APPLIED managed profile, общий account budget,
C1/C2, реальные clocks, missingness и scientific history.
Никаких production calls/deploy/uploads/retirement/reclaim/delete
или изменения actual timers/RPO/grants в рамках этого review patch.

Synthetic compression ratio и tiny-store timing не переносить
на 5.2-GB production. Live sizing и обычный backup/maintenance cycle
остаются staged acceptance, а не дополнительные фальшивые PASS.

ОТБИВКА

По каждому P1:
- точный reproducer и результат ДО;
- minimal owning fix либо доказанное опровержение;
- независимый результат ПОСЛЕ;
- что осталось для production gate.

Затем:
- новый exact head #407;
- актуальные contract/OPERATE/evidence bindings;
- обычные exact-head CI и machine merge-readiness;
- один следующий owner action.

Не запрашивать merge phrase до закрытия этих material findings.