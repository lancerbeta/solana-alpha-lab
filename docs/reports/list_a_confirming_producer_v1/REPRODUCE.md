# Exact readback and bounded reproduction

Истина: Git definition + native source-owner bindings/grants + immutable
ResearchStore transactions/result JSON. JSON success строки, CI и merge не
заменяют эти carriers. Ordinary locator:

```text
entity_id=EXP-LIST-A-CHRONOLOGICAL-CONFIRMATION-V1
truth_plane=GIT
native_kind=EXPERIMENT_SPEC
```

Проверить точный experiment_id в definition; не подставлять название hypothesis.
Runtime sample/grant/binding/trial лежат в DATA_ROOT, definition — в Git.

## Read-only saved state

Retained named volume: `list-a-confirmation-v1-proof`; plane `/proof/plane`.
Early retained host stores: sibling directory
`list-a-chronological-confirming-producer-v1-runtime/{p0-positive,p0-positive-attempt2}`.
Source observations и scientific records не удалять, не переписывать и не создавать
новый plane ради «новой первой попытки» на прежнем acquisition. Reference positive:

```text
LA-TRIAL-204361B9128D79D7728E63FE53BF0B4BB8B8B01ACCB262E619003EEE337D41F9
binding=d4c72653fa868660bd18b52d6990ea7ebf5c8c95520a78e65e14d08312289381
result=8440f65943cbb8040854dc3a1b8d163a175391cdbb4a22ae0521442094fc547d
```

В compatible saved runtime выполнить обычный cold command:

```text
python -B scripts/list_a_confirmation.py status --data-root /proof/plane --trial-id LA-TRIAL-204361B9128D79D7728E63FE53BF0B4BB8B8B01ACCB262E619003EEE337D41F9
```

`show` возвращает тот же typed результат. Cold read не требует новый grant,
не открывает source Parquet и не дописывает ResearchStore. Grant validity/current
protection для нового submit/resume проверяются заново; сохранённый historic
result не превращается в текущую authority. При orphan/pending статус INTERRUPTED,
next_action RESUME_EXACT_TRIAL; invalid-after-reserve не получает новую попытку.
После current отказа classify/submit сохраняют phase BLOCKED_AFTER_RESERVE и
charge=1. Prepare/authorize не переоткрывают consumed trial: ALREADY_RESERVED,
prior_scientific_checkpoint и исходный trial. Недоступная история даёт UNKNOWN/null;
повреждённый result оставляет reservation/charge видимыми при evidence CONFLICT.

Native operating sequence для **отдельно разрешённого** нового sample:

```text
python -B scripts/list_a_confirmation.py register-source --data-root <owned-plane> --source-input <native-input.json>
python -B scripts/list_a_confirmation.py register-source --data-root <owned-plane> --sample-ref <returned-relative-ref> --owner-phrase "REGISTER <domain> LIST A SOURCE <returned-sha>"
python -B scripts/list_a_confirmation.py prepare --data-root <owned-plane> --sample-ref <returned-relative-ref>
python -B scripts/list_a_confirmation.py authorize --data-root <owned-plane> --binding-id <returned-binding> --valid-until <exact-expiry> --owner-phrase "AUTHORIZE <domain> LIST A <returned-request-sha>"
python -B scripts/list_a_confirmation.py classify --data-root <owned-plane> --binding-id <returned-binding>
python -B scripts/list_a_confirmation.py submit --data-root <owned-plane> --binding-id <returned-binding>
python -B scripts/list_a_confirmation.py resume --data-root <same-plane> --trial-id <original-trial> --binding-id <original-binding>
```

Source-owner input содержит native admission documents, census, schedule, bounded
frames, observations и protection documents. Raw manifest/`untouched:true`/caller
COMPLETE без committed ingress/source authority недостаточны. Source registration
и grant — разные exact действия. REAL values/registration/grant не разрешены
текущим implementation atom.

Штатный отзыв exact grant (в текущей кампании только SYNTHETIC):

```text
python -B scripts/list_a_confirmation.py revoke --data-root <same-plane> --binding-id <original-binding>
python -B scripts/list_a_confirmation.py revoke --data-root <same-plane> --binding-id <original-binding> --owner-phrase "REVOKE <domain> LIST A <returned-request-sha>"
```

Первый вызов read-only показывает точную фразу. Второй требует её совпадения;
`approved:true` не принимается. Отзыв не возвращает scientific allowance,
сохраняет cold result и не требует текущей admissibility для нового исполнения.

## Qualification and tests

Runtime: exact CPython 3.13.14 binary64, locked uv dependencies. Зафиксировать
UV_PROJECT_ENVIRONMENT на existing shared environment до Git hooks; не создавать
новую .venv. Production implementation assets должны совпадать в Catalog,
committed Git и working bytes. Local filesystem обязан пройти native qualifier.

```text
python -B -m unittest tests.test_list_a_confirmation_method_v1 tests.test_list_a_confirmation_admission_v1 tests.test_list_a_confirmation_vertical_v1 tests.test_fast_lane_classifier tests.test_experiment_evidence_decision_v1 -v
python -B -m unittest tests.test_episode_native_required_outcome_contract_v1 -v
```

Это disposable TEST stores с разрешённым обычным temporary cleanup, отдельно от
named scientific history. Git fences снимают full snapshot до/после операций;
checkout **и весь refs set** должны оставаться неизменными весь fixture. Параллельные
commits/отчёты/работа других worktrees могут вызвать GIT_MUTATION_DETECTED или
PREFLIGHT_GIT_COMPOSITE_MISMATCH. Для длительного regression использован owned
byte snapshot checkout и отдельная копия Git objects/refs/HEAD/index; обязательный
`.git` entry сохранён, exact producer SHA пробирован до capture. Guards не отключались.

Native contained acceptance: существующий cached image
`sha256:24756b930a05912affa82c7c801cbb8704b0a132da72d6b412ca338219f07387`,
`ftc-candidate-b50a4a95df48:local`. Network none, read-only root, nonroot 65534,
cap-drop ALL, no-new-privileges, memory tmpfs 64 MiB. Repo/Git mounts read-only,
единственный writable owned proof volume; home/credentials/production mounts нет.
Для collector legacy fixture TMPDIR находится на owned physical proof filesystem:
маленький tmpfs не удовлетворяет штатному drain-reserve free-space check.

После **отдельного разрешения нового named synthetic campaign и его budget**
на новом owned volume с writable uid65534 и смонтированными `/repo`, `/git`, `/proof`:

```text
PYTHONPATH=/repo/src
GIT_DIR=/git/worktrees/list-a-chronological-confirming-producer-v1
GIT_COMMON_DIR=/git
GIT_WORK_TREE=/repo
HOME=/tmp
python -B -m tests.fixtures.list_a_confirmation_v1.proof campaign
```

Campaign пишет fixed-plan до первого scientific submit; шесть studies/grants,
OS crashes/concurrency, fsynced actual-reader events и cold processes. Existing
`/proof/acceptance` вызывает refusal `exist_ok=False`; не удалять его ради повторного
запуска. Crash orchestration resume возможен только original trial; не перезапускать
campaign как обход. OS exits 86 — ожидаемые fault witnesses, не scientific negative.
Engineering/CI repeat не автоматически разрешает новую named scientific кампанию.

Clean-host bootstrap **не доказан**: нужны exact runtime/dependencies и cached
image; build/pull/install не входит в authority. Core frozen source pins относятся
к историческому ref; current qualification в отдельном receipt. Numeric results
и raw trace digests воспроизводимы, IDs technical attempt/transaction UUID меняются
при новой разрешённой кампании. Early P0 точный reader count восстановить нельзя.
Allocation измерена по regular files/owned volumes/SizeRw; physical Docker VHDX,
daemon metadata/logs и total shared cache остаются отдельно UNKNOWN.

Rollback: обычный code/schema/registry revert сохраняет stores, reservations,
attempts/results и charges. Pending несовместимый trial не считается untouched;
нельзя refund charge или менять core/thresholds ради повторного запуска.
