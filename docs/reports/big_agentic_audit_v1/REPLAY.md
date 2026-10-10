# Повтор BIG_AGENTIC_AUDIT_V1

Запускать из audit-kit checkout на Windows. Docker должен работать. `SOURCE_ROOT` — **отдельный чистый clone** ровно `90ba76e37515b3d521478a6d05a149fb0f1d2b75`, без `.env`, `.venv`, `data`, `local`, `node_modules`. Это не production checkout. Существующий prepared source нельзя обновлять между фазами.

`EVIDENCE_ROOT` — отдельный пустой каталог; launcher устанавливает campaign owner marker. `ATTEMPT` каждый раз новый. Контейнеры и native volumes сохраняются, повтор не overwrites прежнюю попытку. Ни одна команда ниже не меняет product source и не удаляет историю.

## Runtime

Существующий approved runtime использовать прежде нового bootstrap. Кампания исполнила pinned managed CPython 3.13.14, uv 0.11.29 и существующий `uv.lock` внутри официальных images. Первый build использует сеть, требует отдельного owner разрешения; все последующие product runs — `--network none`.

```powershell
& tests/fixtures/big_agentic_audit_v1/bootstrap.ps1 `
  -SourceRoot $SOURCE_ROOT -BuildRoot $NEW_BUILD_ROOT -ApprovedBootstrap
```

`-ApprovedBootstrap` фиксирует ранее полученную authority, не создаёт её. Dockerfiles закрепляют official image digests. BuildRoot должен быть новым. Snapshot включает Git objects и восстанавливает tracked Git blobs, чтобы Windows CRLF и file ownership не изменили исполнение. В original campaign эквивалентные шаги были реально выполнены; сам reusable bootstrap wrapper проверен синтаксически, полного повторного скачивания не было.

Каждый entrypoint перед product steps проверяет actual `/repo` HEAD и tracked bytes внутри image. Несовпадение или любой отказ containment останавливает запуск и сохраняет `safety-preflight.json` с failed keys; это HARNESS/ENVIRONMENT stop, не product finding. При `source_base_verified=false` или `source_tracked_bytes_verified=false` не повторять тот же Attempt: проверить snapshot и пересобрать его в новом BuildRoot только при действующей bootstrap authority. При остальных failed guards восстановить ограниченную среду; product steps не продолжать.

## Самый короткий NOW reproducer

Эти две команды реально проверены на standalone producer-a1 → bridge-b1. Первый запуск обычно занимает около двух минут; второй — несколько секунд.

```powershell
& tests/fixtures/big_agentic_audit_v1/launch.ps1 `
  -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase producer -Attempt r1

& tests/fixtures/big_agentic_audit_v1/launch.ps1 `
  -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase bridge -Attempt r1 `
  -ProducerVolume baa-producer-r1-evidence
```

На audit base producer: exit0. Bridge: **exit1 — ожидаемый воспроизводимый product finding**, `producer_complete_for_exact_spec=true`, `expected_execution_plane=COMPLETED`, `planes.execution=NO_RUN`. `promotion_refusal_check=PASS` и `readonly_check=PASS`. После будущего ремонта execution должен стать COMPLETED, scientific guard оставаться PROMOTE_BLOCKED.

Bridge получает настоящий уже использованный operator ExperimentSpec, кладёт его в disposable definition slot и читает настоящие producer records через неизменённый production consumer. Он не добавляет scientific records, evidence bindings, RUN_COMPLETED или решения.

## Второй finding

```powershell
& tests/fixtures/big_agentic_audit_v1/launch.ps1 `
  -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase wal -Attempt r1
```

На audit base exit1: reference COMPLETE, readonly OperationalStore RUNNING, LifecycleProjection RUNNING, after writer close COMPLETE. Schedule: RUNNING commit → checkpoint → COMPLETE commit с живым writer → independent mode=ro SELECT → два production reads → close control. Source/read-only inventory не изменён.

## Bounded campaign

Для повторения остальных независимых фаз используйте тот же launcher с новым Attempt:

```powershell
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase smoke -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase core -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase spine -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase branches -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase science -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase critic -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase interactions -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase metrics -Attempt r1
& tests/fixtures/big_agentic_audit_v1/launch.ps1 -SourceRoot $SOURCE_ROOT -EvidenceRoot $EVIDENCE_ROOT -Phase probes -Attempt r1
```

Probes exit1 из-за WAL finding; остальные healthy fixtures exit0. В branches один SKIP требует настоящий canonical store, который сознательно не подключён. Recovery phase повторяет ровно два ранее заблокированных snapshot-ownership теста; на исправленном image они PASS. Учёт отражает все попытки, не только лучшую.

Модели, внешние providers и реальные holdouts не вызываются. Scripted Critic проверяет транспорт/guards. Fresh-context [actor missions](../../../tests/fixtures/big_agentic_audit_v1/actor_missions.json) нельзя запускать через host-access agents: сначала доказать OS confinement всех их tools и разрешить budget.

## Evidence и grading

Каждый запуск сохраняет containment/terminal receipts и `baa-<phase>-<attempt>-retained/evidence.tar.gz`. Native volume `baa-<phase>-<attempt>-evidence` содержит полную исходную synthetic среду. Tar хранит symlinks без изменения Windows settings. Не извлекать произвольные archive paths; collector читает только ограниченные regular summary/trace members.

```powershell
uv run --offline --locked --managed-python python -B tests/fixtures/big_agentic_audit_v1/collect_evidence.py --evidence-root $EVIDENCE_ROOT --output-root $NEW_REPLAY_OUTPUT
uv run --offline --locked --managed-python python -B tests/fixtures/big_agentic_audit_v1/assemble_coverage.py --ledger-root $NEW_REPLAY_OUTPUT --output-root $NEW_REPLAY_OUTPUT
uv run --offline --locked --managed-python python -B -m unittest tests.test_big_agentic_audit_v1 -q
```

`NEW_REPLAY_OUTPUT` — новый отдельный каталог вне source; читать его `run-ledger.json` и `coverage.json`. Baseline report/summary/manifest остаются привязаны к исходной кампании. Scripts отказываются перезаписывать существующий результат; `--refresh-baseline` предназначен только для явно выбранного builder refresh. Последняя команда проверяет oracle controls baseline kit, а первые две формируют отдельный replay coverage и не закрывают UNKNOWN автоматически. `charter_bindings.json` содержит judgments baseline campaign; перед сравнением иным source ref требуется отдельная привязка. Сначала сохранить оригинальные findings и все failed attempts.

Bound: 120 минут product wall envelope, 2 CPU / 2 GiB / 128 PIDs на контейнер, ≤2 GiB evidence, ≤200 generated sequences. RAM/CPU/PID/network/rootfs обеспечиваются Docker. Time/storage контролировал executor; launcher не является disk-quota или deterministic OS scheduler. При исчерпании envelope остановить owned process, сохранить incomplete trace и checkpoint; не запускать следующий batch.

Cleanup в эту поставку не входит. После сохранения evidence удалять можно только resources с точным campaign label и проверенным owner path, по отдельному scoped действию. Original production stores/history никогда не подключались.
