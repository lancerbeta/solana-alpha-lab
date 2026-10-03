# Factory: ремонт ресурсоёмкого watch/pulse

Кандидат на проверку и merge; реальный ремонт на VPS ещё не подтверждён.

Один разрешённый Linux-профиль показал watch 106,816 с и cgroup peak 768 MiB.
Из них 16,170 с ушло на полный timestamp-проход 48 008 старых/свежих вызовов;
immutable activation proof повторялся по ~17 с трижды. RSS процесса был ~184 MiB;
вклад файлового кэша — обоснованный вывод, без отдельного измерения по этапам.

Индекс теперь выбирает свежие call-кандидаты до чтения payload. Python точно
проверяет нижнюю границу времени; invalid/future остаются UNKNOWN. Неподготовленный
или другой индекс даёт UNKNOWN без recovery full scan. Встроенные функции SQLite
сохраняют запись старым collector после отката. Уже заполненная база получает
индекс отдельной backup-first командой, а не скрыто при старте collector.
Ресурсный тест покрывает UTC-форматы producer и совместимые дробные формы.
Другие ISO-форматы или повреждённые timestamps остаются кандидатами чтения
заголовка; Python отсекает старые записи до payload. Их массовое появление
не входит в доказательство постоянной стоимости.

Immutable manifests и проверенные релевантные partitions переиспользуются только
внутри одного packet. Следующий цикл проверяет их заново. Старые Parquet payload
не открываются в проверке состояния кампании: из неё убран ненужный поиск старого
member predecessor. Научная реконструкция members сохраняет прежний поиск.
Заголовки manifest всё ещё перечисляются один раз за packet.
Это остаточная стоимость, а не обещание бесконечного масштаба.

Из 138 адресных тестов 137 PASS, один platform skip. На реальной синтетической цепочке
один packet читает 19 manifest вместо 57 и проверяет 3 partitions вместо 33;
старые member payload читаются 0 раз вместо 24. История включает чужие member batches;
24-hour diagnostics остаётся EXACT с 128 свежими наблюдениями. Windows-измерение
не заменяет Linux. Перед merge обязателен PASS workflow Factory operability
resource proof на точном head: два размера истории и 1162 свежих вызова; fsync и
advisory DONTNEED для synthetic файлов (резидентность кэша отдельно не доказана),
768 MiB/180 с guard и <512 MiB/<120 с для каждого настоящего CLI.
Ресурсный job включён в обязательный `Repository validation / validate`,
поэтому его missing/failure/skipped/cancelled не даёт зелёный merge-gate.
Для нерелевантных diff proof пропускает только тяжёлый step, сам job проверяется.

После merge: свежий host preflight/backup, точный release pin, короткое controlled
collector stop для однократного prepare-index с rollback при отказе, затем restart
и доказательство продвижения source clocks/publication. Следом реальные watch/pulse
canaries под прежними unit env и caps, два watch-цикла, подтверждённая Telegram
доставка и включение двух report timers. При UNKNOWN/threshold failure timers
остаются выключенными; код откатывается на проверенный SHA. Внешний heartbeat
нуждается в настроенном off-host получателе и отдельной проверке пропуска ping.
Это третья намеренно отключённая возможность, не доказанный канал уведомления.

Операционные receipts, backups, synthetic fixtures и live payload остаются вне Git.
Новая служба, dependency, provider route и авторизация кампании не добавляются.
