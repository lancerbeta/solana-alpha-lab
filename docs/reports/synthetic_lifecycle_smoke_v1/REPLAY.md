# Replay и retained среда

Продукт: `94b391d658b52035ae88e2da05f1ea25ff17b0f8`.
Runtime image: `sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071`.
Никаких pulls, installs, credentials, provider calls или удаления эта инструкция
не требует. Launcher откажется при отсутствующем pinned image.

Локальный campaign root содержит `source/`, clean `product/` и `retained/`.
Docker volume `sls-v1-product` — readonly frozen product copy;
`sls-v1-scratch` — собственный временный filesystem, в финальном замере пуст.
Оба имеют label `sls.campaign=SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1`.
Stopped containers и snapshots оставлены для решения владельца.

Из delivery checkout `source/` проверенные команды имеют такую форму:

```powershell
$campaignRoot=(Resolve-Path ..).Path
$docker=Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'
$product=Join-Path $campaignRoot 'product'
$retained=Join-Path $campaignRoot 'retained'
& ./tests/fixtures/synthetic_lifecycle_smoke_v1/launch.ps1 -ProductRoot $product -EvidenceRoot $retained -Phase recovery -Attempt replay1 -Docker $docker
```

Используйте новое `Attempt`: существующая directory/container никогда не заменяется.
Измеренный canonical replay: `prepare a3`, `world a3`, `forge-tail a1`, `trading-tail a2`,
`fortnight a1`, `recovery a2`, `spine a2`, `seams a1`, `handoff a1`, `finalize a1`.
`forge a2` имеет 28 PASS и setUpClass capacity ERROR; три недостигнутых cases отдельно
прошли в `forge-tail a1`. `trading a1` имеет 29 PASS, C16 FAIL и прерванный C21;
`trading-tail a2` прочитал original ledger и выполнил остальные 51 cases, а
`fortnight a1` отдельно закрыл исходный C21. Знаменатель не уменьшен.

Для trading-tail нужен `-InputRoot (Join-Path $retained 'sls-v1-trading-a1')`.
Он исключает только уже PASS tests и отдельно сохраняет original C21 obligation.
Для finalize нужны original bound store и независимые decisions:

```powershell
& ./tests/fixtures/synthetic_lifecycle_smoke_v1/launch.ps1 -ProductRoot $product -EvidenceRoot $retained -Phase finalize -Attempt replay1 -Docker $docker -ResumeRoot (Join-Path $retained 'sls-v1-world-a3') -InputRoot (Join-Path $retained 'critic-inputs')
```

Finalize использует исходные `/audit/native-world/rdp` bindings, пишет новый run
receipt в отдельный `/stage`, не повторяет MAIN. Saved decisions не подменяют нового
Critic для другого packet: exact packet/candidate hashes обязательны.
На existing final store повтор может быть idempotent/refused; не трактуйте replay
как новое scientific evidence.

Существующий host runtime задайте явно; bare `uv` создаёт лишнюю `.venv`:

```powershell
$env:UV_PROJECT_ENVIRONMENT=Join-Path (Split-Path $campaignRoot -Parent) 'solana-alpha-lab/.venv'
uv run --locked --managed-python --no-sync python -B tests/fixtures/synthetic_lifecycle_smoke_v1/observer.py --world-root (Join-Path $retained 'sls-v1-world-a3') --out (Join-Path $retained 'independent-observer-replay.json')
if ($LASTEXITCODE -ne 0) { throw 'FRESH_OBSERVER_REPLAY_FAILED' }
uv run --locked --managed-python --no-sync python -B tests/fixtures/synthetic_lifecycle_smoke_v1/collect.py --retained $retained --out ./local/sls-readout-replay
if ($LASTEXITCODE -ne 0) { throw 'FROZEN_CAMPAIGN_READOUT_FAILED' }
```

Observer проверяет сохранённые числа без product import и без MAIN.
Его `*-replay.json` — отдельная свежая проверка, которая должна успешно завершиться.
Collector восстанавливает исходную frozen campaign из canonical
`independent-observer-v2.json`, сохранённых footprints и attempts; свежий replay
receipt не заменяет эти исторические inputs и не является новым campaign result.
Collector требует оригинальный frozen denominator, фактические native receipts,
independent oracle и distinct scientific spec hashes; пустая/усечённая выборка
не является PASS. Исторические failed records остаются в `attempts.jsonl`.

Повторное измерение после остановки всех собственных containers:

```powershell
& ./tests/fixtures/synthetic_lifecycle_smoke_v1/measure_docker.ps1 -Docker $docker -OutputPath (Join-Path $retained 'docker-footprint-replay.json')
uv run --locked --managed-python --no-sync python -B tests/fixtures/synthetic_lifecycle_smoke_v1/measure_host.py --root $campaignRoot --out (Join-Path $retained 'host-footprint-replay.json')
```

Измеритель Docker создаёт один маленький readonly/no-network helper, оставляет его
stopped и измеряет только owned volumes/layers и exact owned log paths. Не считает
existing image новым расходом; не измеряет прирост общего VHDX. Host measurement
дедуплицирует file IDs внутри campaign; shared-cache hardlinks и directory metadata
имеют явно указанный предел учёта. Команд cleanup здесь нет.
