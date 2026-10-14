# Воспроизведение saved checkpoint

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

`replay-v3-a1` уже существует и immutable. Перед повторным cold replay выберите
новый уникальный `-Attempt` и проверьте доступный budget; неизменённая команда
выше остановится с `IMMUTABLE_ATTEMPT_ALREADY_PRESENT`. Новый Attempt не разрешает
fresh scientific run. Launcher проверяет
owned marker/labels, immutable image, nonroot/no-network/readonly boundary и
потом child canaries. Повтор требует retained owned volumes; image ID
`sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071`.
Image/runtime install, изменения Docker settings и provider access не нужны.

В output volume сохранены:

- `base-v3/<kind>/spec.json`, `classified.json`, `upstream.json`, `numeric-oracle-check.json`;
- `base-v3/<kind>-run.json`, `<kind>-replay.json` и `base-v3/plane`;
- `base-v3/plane/research/artifacts/results/<result_artifact_id>.json`;
- `base-v2/classified-plane`, `fault-before-commit`, `fault-after-commit`, `negative-*`;
- первоначальный `attempts.jsonl`, полные phase/read traces, прежние v2 results;
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

Next exact gate: SC06 ещё не начинался. Для него нужен owner budget replan;
текущий cap 512 MiB нельзя расширить постфактум. Ни `prepare-changed`, ни `changed`
пока не являются доказанной successful execution командой. B execution по current
main недоступен: не создавать 64-day worlds и самописный confirmer.
