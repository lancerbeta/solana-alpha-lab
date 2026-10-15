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
named scientific history. Финальная production closure прошла 26 native checks
в `list-a-confirmation-frozen-boundary-final`: 6 method, 17 admission, 3 vertical.
Дополнительно 8 method checks прошли в `list-a-confirmation-terminal-oracles`;
negative/zero/concentrated effect и пустые crossed replicates имеют literal oracle.
Nonfinite/unrepresentable return — completed INSUFFICIENT с charge 1, полными
observed counts и null means/contrast, без bootstrap draws. Предыдущая engineering
проверка INVALID сохранена как superseded; identity/PIT/protection failures — INVALID.
Git fences снимают full snapshot до/после операций;
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
Checkpoint snapshot 15 октября: 189.605 MiB owned / 225.430 MiB conservative charged,
30 stopped containers. Предыдущие snapshots сохранены. См.
`docs/evidence/list_a_confirming_producer_v1/footprint-checkpoint.json`.
Один ошибочный review запуск создал пустую .venv без установки пакетов; она
перемещена в owned scratch archive после no-process/non-reparse проверки, не
использовалась для product/science и не удалена. Archived files учтены в allocation.
Этот факт нарушил literal no-new-.venv clause; delivery требует explicit owner
acceptance, а не изменения прошлого receipt. Current CLI-specific positive test
прошёл за 36.570s: actual status/show с одним trial-id на missing/conflicting result
сохраняют committed consumed identity. Последние six cold receipts — cli-final,
current production qualification — отдельная post_review_implementation запись.

Rollback: обычный code/schema/registry revert сохраняет stores, reservations,
attempts/results и charges. Pending несовместимый trial не считается untouched;
нельзя refund charge или менять core/thresholds ради повторного запуска.


## Targeted source-role checkpoint (PR406)

На существующем locked CPython runtime, без install/sync/new .venv:

```text
python -B -m unittest tests.test_list_a_confirmation_admission_v1.SourceRoleProvenanceTests -v
python -B -m unittest tests.test_list_a_confirmation_admission_v1 tests.test_list_a_confirmation_vertical_v1 tests.test_fast_lane_classifier tests.test_experiment_evidence_decision_v1 -v
```

Первый тест конструирует только disposable synthetic TEST ingress; затем вызывает
настоящий `register-source --source-input` с original source role/forbidden labels
при outer untouched/false. Census-only, observations-only и обе поверхности,
включая последнюю строку, должны отказать до SOURCEAUTH/grant/reservation/run.
Instrumentation разрешает observation decoding только двух role columns; future
target values не открываются. Missing/invalid labels fail closed. Domain-independent
compatible-label oracle использует те же synthetic bytes; REAL grant не выдаётся.
Unit stores имеют ordinary temporary cleanup и не являются replay named campaign.

Сохранённый before/after native CLI witness использует один неизменный TEST source;
до repair были SOURCE_PREPARED/SOURCE_REGISTERED/PREPARED/AUTHORIZED/FAST_LANE_READY,
после — CONFIRMATORY_REUSE_FORBIDDEN и BLOCKED_BEFORE_RESERVE. Existing granted
binding тоже отказывает. Raw receipt UTF-8 и hashes находятся в
`source-role-provenance.json`; uncommitted after-native-1 явно не является proof
исправленного Git head. Native observations reader metadata-only; 0 values,
0 reservations, 0 charges. Все attempts сохранены в owned scratch.

Старый PR406 CI FAILURE не повторяет эти targeted checks: три оставшихся legacy
test compatibility paths вне managed_write_set перечислены в receipt. Новый full
CI пока не заявлен. Historical qualification/results не переписываются для новой
metadata границы; сохранённые charges остаются consumed. Merge phrase не запрашивать.


## Owner-authorized three-test compatibility regression

```text
python -B -m unittest tests.test_factory_ordinary_market_hypothesis tests.test_discovery_evidence_release_bridge tests.test_harness_sync tests.test_list_a_confirmation_admission_v1.SourceRoleProvenanceTests -v
```

Existing shared locked runtime only; no install/new environment. Expected55 tests:
13 ordinary-hypothesis,5 release bridge,34 harness_sync,3 source-role provenance.
These are disposable unit fixtures, not a named scientific campaign or a replay
of seven consumed charges. Original four-operation source-role CLI receipts remain
in source-role-provenance.json; before/after source hashes/role flags are exact.
Fixture schema set is the original base four paths, independent of manifest order.
P2 recovery next-action is still a separately unresolved production finding;
compatibility PASS does not assert independent-review/bindings/fullCI/merge PASS.


## Separately authorized P2 recovery copy

Apply only proposal SHA256381fc5e1fc06be5768b16facd8c9e6e7eb76ecea8b815f33acaed7877fc335ba.
Repeat ordinary classify then submit on the retained source-role-falsifier-before-native-1
TEST plane and its existing binding with the fixture as-of clock
(use native.NOW from tests/fixtures/list_a_confirmation_v1/native.py as authority).
Expected reason CONFIRMATORY_REUSE_FORBIDDEN, terminal BLOCKED_BEFORE_RESERVE,
next_action STOP_THIS_SOURCE_KEEP_LABELS_HISTORY_REQUIRE_SEPARATE_SOURCE_AUTHORITY.
Do not regenerate a world or scientific run; original source hashes are in
source-role-provenance.json#recovery_copy_20261015.receipt.raw_utf8. The retained
local recovery_copy_witness.py uses explicit metadata-only decoder guards,
fail-on-entry runner/evaluator spies and complete17-file store hash inventories.
Separate injected checkpoint/exception branch oracle is unit-only: charge1 keeps
VERIFY_SAVED_CHECKPOINT_KEEP_CONSUMED_ALLOWANCE; other reasons keep previous
binding recovery; unknown charge remains null/BLOCKED_RESERVATION_UNKNOWN.

```text
python -B -m unittest tests.test_fast_lane_classifier tests.test_list_a_confirmation_admission_v1.SourceRoleProvenanceTests -v
```

Expected34 PASS on shared existing runtime; no new environment/install. Prior55
compatibility checks need not repeat for a copy-only change. No campaign replay,
requalification of saved science, REAL scope or merge authority follows.
