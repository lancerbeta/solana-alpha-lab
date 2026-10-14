# Воспроизведение окончательного bounded audit

Рабочая база продукта: `fbac5449f6dd22a7bc066114109be8bbed830447`; runtime source
read-only. Первичное evidence — base-v3; base-v2 и failed Windows capture retained.
Сначала читать [summary.json](../../evidence/science_lifecycle_smoke_v1/summary.json),
а не запускать MAIN. Resume не обнуляет counters или resource cap.

Проверенная offline команда из elected checkout; использован существующий locked
runtime, без установки зависимостей:

```powershell
$env:UV_PROJECT_ENVIRONMENT=(Resolve-Path '..\solana-alpha-lab\.venv').Path
$env:UV_CACHE_DIR=Join-Path $env:LOCALAPPDATA 'uv\cache'
$env:PYTHONUTF8='1'
uv run --locked --managed-python --no-sync python -B tests/fixtures/science_lifecycle_smoke_v1/verify_saved.py --evidence docs/evidence/science_lifecycle_smoke_v1
uv run --locked --managed-python --no-sync python -B -m unittest tests.test_science_lifecycle_smoke_v1 -v
```

Обе проверяют настоящие saved numerical/passport/record witnesses. Tests отвергают
forged COMPLETE без native completion, неверный comparator, artifact corruption
и membership corruption; дополнительно проверяют обязательные guard/fault receipts,
полноту cohort/calendar и [20 сохранённых clock metadata](../../evidence/science_lifecycle_smoke_v1/chronology-geometry.json).
Никаких datasets, product evaluator или новых looks при offline проверке.

Исторически выполненная native cold команда в этой кампании:

```powershell
& tests/fixtures/science_lifecycle_smoke_v1/launch.ps1 -RuntimeRoot '..\smial-science-lifecycle-smoke-v1-runtime' -Phase replay-v3 -Attempt replay-v3-a1 -UseVolumes
```

`replay-v3-a1` уже существует и immutable. Не повторяйте cold replay на исходных retained stores: старый kit пишет общий
receipt alias и может уничтожить прежний raw trace. Уникальный `-Attempt` сохраняет
kit/container, но не изолирует эти aliases. Историческая неизменённая команда
выше остановится с `IMMUTABLE_ATTEMPT_ALREADY_PRESENT`. Новый Attempt не разрешает scientific run или replay на исходных stores. Launcher проверяет
owned marker/labels, immutable image, nonroot/no-network/readonly boundary и
потом child canaries. Исторический runtime использовал retained owned volumes; image ID
`sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071`.
Image/runtime install, изменения Docker settings и provider access не нужны.

В output volume сохранены:

- `base-v3/<kind>/spec.json`, `classified.json`, `upstream.json`, `numeric-oracle-check.json`;
- `base-v3/<kind>-run.json`, `<kind>-replay.json` и `base-v3/plane`;
- `base-v3/plane/research/artifacts/results/<result_artifact_id>.json`;
- `base-v2/classified-plane`, `fault-before-commit`, `fault-after-commit`, `negative-*`;
- первоначальный `attempts.jsonl`, latest exported phase/read witnesses, прежние v2 results; ранняя per-attempt replay trace history INCOMPLETE;
- `chronology-geometry.json` в output volume: независимо пересчитанные часы из
  metadata-only observation columns, 10 matched episodes и 20 E1800/E14400 cells;
- `definition-ingress` — definition fixture; product imports всегда из `/repo`.

Locators и hashes входят в [source-binding.json](../../evidence/science_lifecycle_smoke_v1/source-binding.json)
и actual passports. Для read-only выгрузки конкретного сохранённого файла можно
использовать `docker cp` от остановленного owned container; не требуется запускать
producer снова. Git содержит компактные значимые числа и receipts, не весь store.
Offline verifier проверяет независимую арифметику и связи сохранённых witnesses;
он не заявляет повторный runtime execution или физическую доступность каждого
remote blob только по его hash.

Пример checked host resource readback:

```powershell
uv run --locked --managed-python --no-sync python -B tests/fixtures/science_lifecycle_smoke_v1/measure_host.py --runtime '..\smial-science-lifecycle-smoke-v1-runtime' --checkout . --out '..\smial-science-lifecycle-smoke-v1-runtime\output\host-footprint.json'
uv run --locked --managed-python --no-sync python -B tests/fixtures/science_lifecycle_smoke_v1/capture_host.py --runtime '..\smial-science-lifecycle-smoke-v1-runtime' --out '..\smial-science-lifecycle-smoke-v1-runtime\output\container-attempts.json'
```

`footprint` phase использует Linux `st_blocks` и dedup `(st_dev, st_ino)`;
host — NTFS allocation с file identity dedup. Directory metadata и shared VHD
growth не zero-filled. `finish_packet.py` пересчитывает отчет/ledger из saved
native evidence и этих measurements; export — audit data, не product carriers.

## SC06: выполненные native команды и границы повторения

```powershell
& tests/fixtures/science_lifecycle_smoke_v1/launch.ps1 -RuntimeRoot '..\smial-science-lifecycle-smoke-v1-runtime' -Phase prepare-changed -Attempt prepare-changed-a1 -UseVolumes
& tests/fixtures/science_lifecycle_smoke_v1/launch.ps1 -RuntimeRoot '..\smial-science-lifecycle-smoke-v1-runtime' -Phase changed -Attempt changed-a1 -UseVolumes
& tests/fixtures/science_lifecycle_smoke_v1/launch.ps1 -RuntimeRoot '..\smial-science-lifecycle-smoke-v1-runtime' -Phase replay-changed -Attempt replay-changed-a1 -UseVolumes
```

Это исторические receipts, не инструкция заново открыть MAIN: все три attempts
уже immutable. Current MAIN=6/6, evaluator=10/12. Fresh campaign/prepare requires
отдельную authority; новый Attempt не сбрасывает cap. Новый cold repeat на исходных retained stores этим runbook не разрешён: он
перезаписывает общий replay receipt. Сначала нужны отдельная authority и сохранение
прежних raw aliases. Offline verifier и read-only Docker export остаются доступными.
changed future source публиковался штатным generator до native MAIN. Immutable
base capture/old worlds не переписывались; product snapshot и image переиспользованы.
[sc06.json](../../evidence/science_lifecycle_smoke_v1/sc06.json) содержит actual
artifacts/passports/committed records, independent oracle и filtered native prefix
hashes. Prefix E0..E1800 неизменен; release_id меняется вместе с future source bytes.
Offline verifier проверяет −0.09 / −0.045, unchanged D/M/C, current lineage,
zero-evaluator cold replay. Десять тестов дополнительно отвергают changed prefix,
changed membership/denominator и unchanged future oracle.

## Конкретные ограничения воспроизведения

1. Пакет Git содержит компактные actual witnesses, а не полную копию datasets.
   Offline PASS воспроизводит проверку сохранённых receipts, не runtime experiment.
2. Native cold replay зависит от retained campaign volumes, marker и локального
   image ID. Этот ID не опубликован как переносимый registry digest. При потере
   volumes/image одного Git clone недостаточно. В этой кампании dependencies
   не устанавливались и image не строился. Shared locked uv runtime pre-existed.
3. Первичная подготовка Linux owned volumes потребовала ручного seed/UID repair;
   launcher их только проверяет. Windows bind capture превысил 600s. Поэтому
   clean-host one-command bootstrap не доказан; не выдавать Linux reuse за него.
4. Definition registration — explicit fixture, Actor/Critic scripted. Reproduce
   не проверяет blind-agent behavior или обычное authoring/registration UI.
5. Mandatory Git hook при checkpoint создал .venv и нарушил прежний 512 MiB cap.
   Owner разрешил только её проверенное удаление и forward cap 640 MiB. Для Git
   commands заранее задаётся UV_PROJECT_ENVIRONMENT к existing shared runtime;
   hooks остаются включёнными. Если .venv появится снова, она входит в cap.
6. B execution недоступен: accepted confirming producer/reservation absent.
   Не создавать 64-day worlds, новый estimator или authored scientific carriers.

Original budget breach и authorized cleanup сохранены в budget-continuation.json.
Финальный live footprint после Git content — local/delivery_harness/science-final-footprint.json;
его timestamp/measurement stage не подменяют исторический committed snapshot.
Stores/receipts/trial history/caches не удалять. Docker VHD/log-directory physical
allocation остаётся UNKNOWN; logical log size не служит физическим замером.

Известный дополнительный audit defect: ранние same-world replay attempts сохраняли
общий `<kind>-replay.json`; полный старый read-trace witness мог быть перезаписан.
Scientific ledger/counters/native records сохранены, current exported hashes проверены,
но ранние per-attempt read traces не реконструированы: UNAVAILABLE. Не считать
immutable kit/container доказательством сохранения всех response/read receipts.

Allocation-only `resource-probe` используется только для проверки самого launcher:
он не вызывает campaign, source reader или evaluator. Pre/post receipts уникальны
по Attempt; `-TelemetryFailureProbe` намеренно отказывает после start и проверяет
finally stop/readback. Это не scientific trial или способ получить PASS результата.
