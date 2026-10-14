# Replay и сохранность targeted continuation

Product base — `94b391d658b52035ae88e2da05f1ea25ff17b0f8`.
Исходный audit delivery — PR #401, commit
`e6141191c185a5aa02c0bc3178b2efeaa534417b`; он не переписан этим продолжением.
Оба benchmark и все trials сохранены. Код меняет только disposable synthetic
ingress и audit kit; product calculator/filter/classifier не подменяются.

Нужны уже установленные locked runtime и pinned image
`sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071`.
Новых installs/pulls/services нет. Продукт в существующем `sls-v1-product`
readonly; сохранённый episode world в `sls-v1-scratch`. Перед launcher проверяет
точные существующие volume labels, поэтому неверный alias не создаёт новый
volume. InputRoot/ResumeRoot только внутри явно переданного retained root.

Из Git root, с переданным пользователем расположением retained, проверка pins
и сборка компактного результата:

```powershell
$env:UV_PROJECT_ENVIRONMENT='<existing-project-venv>'
$env:PYTHONUTF8='1'
uv run --locked --managed-python --no-sync python -B tests/fixtures/synthetic_lifecycle_targeted_v1/verify.py --retained '<retained-root>'
if ($LASTEXITCODE -ne 0) { throw 'RETENTION_OR_BOUNDARY_VERIFICATION_FAILED' }
```

`verify.py` читает pinned files и повторяет необходимое schema-ограничение.
Он не выполняет native scientific looks, experiments, finalize, promotion или
Docker cleanup. Schema hash обязан совпасть с frozen product; иной код не
доказывает исторический результат. Raw packets/receipts лежат в retained,
Git хранит их hashes, реальные Critic decisions и компактные bindings.

Сохранённые production-shaped этапы:

| Run | Смысл |
|---|---|
| diagnose-a1 | INVALID_HARNESS: ошибочный volume alias создал пустой repo. Два пустых volume сохранены и учтены по exact failed-container ownership. |
| diagnose-a2 | Старые frozen raw candidates → readonly classifier Spec 1.1, inventory unchanged. |
| diagnose-a3 | То же плюс schema-valid Spec 1.3 candidate с public raw request; NO_COVERING_SNAPSHOT, не frozen schedule binding и не OOS verdict. |
| episode-a1 | Один native source capture/import/look; observer ошибся в имени comparator. Продуктовый результат сохранён. |
| episode-resume-a1 | Тот же benchmark/world и native saved-look retry, new_look=false; правильный comparator oracle, persist/freeze и schema boundary proof. |
| revise-a1 | Настоящий REVISE_ONCE → одна native design revision, new looks=0. |
| finalize-a1 | Второй genuine packet-only Critic → KILL_LOW_INFORMATION_VALUE → durable native terminal, cold readback unchanged. |
| legacy-a1 | Accepted runner completed; observer incorrectly required no nonmatching runs in the shared synthetic store. All records retained. |
| legacy-a2 | Same run idempotent replay → DIRECT records, target run not conflicted → native science guard BLOCKED. |

Exact engine calls записаны в per-attempt kit snapshots и pinned process logs.
Новый `episode` отказывает при уже существующем benchmark; `episode-resume`
проверяет его неизменность и требует `new_look=false`. Для новой кампании нужна
новая явно зарегистрированная версия/world, а не очистка старой истории.
`revise` исполняется только для настоящего REVISE_ONCE; `finalize` требует
переданный настоящий Critic result. Каждый subprocess bounded, контейнеры
network none / readonly root / UID1000 / cap-drop ALL / no-new-privileges /
2CPU / 2GiB / 128PID. Watchdog: 30 active product minutes, 2GiB own data.

`collect.py --retained <root> --output docs/evidence/synthetic_lifecycle_targeted_v1`
пересобирает canonical audit facts только после сохранённых exact runs и
footprint receipts; не заменяет свежий запуск продукта. Все non-PASS attempts
остаются. После любого инструмента проверять exit code перед чтением summary.

Размер — snapshot точной campaign directory, обоих owned campaign labels,
двух доказанно принадлежащих failed launcher aliases, volumes, layers и logs.
Windows allocation deduplicated внутри directory; hardlinks к shared cache
могут завышать дополнительную allocation. Existing runtime image и shared
Docker VHDX исключены из новых bytes. Shared uv cache growth — UNKNOWN:
pre-campaign baseline отсутствует. Последующий Git/metadata рост не включён
в snapshot. Никаких rm/prune/volume-delete/branch-delete/cleanup действий нет.
