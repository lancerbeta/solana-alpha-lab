# Reusable offline replay

Entry: `tests/fixtures/forge_trust_closure_v1/replay.py`. Параметр source — exact
current committed HEAD, tracked bytes clean, BASE ancestor. Никакого newest
discovery. Audit kit берётся из Git head PR393, сохраняет original hashes,
параметризует source pin в новой копии и проверяет его внутри контейнера.
Candidate image собирается offline Git bundle поверх уже существующего runtime.
No dependency download/bootstrap. Если pinned runtime отсутствует — explicit
blocker, а не скрытая установка.

Prerequisite runtime image ID:
`sha256:b1a9aeff235915d05f6b6d0436972e5609b631a6c77e2a9e0a664a04d36e96bb`,
tag `smial-baa-v1-snapshot:local`. Python3.13.14 / SQLite3.53.1. Linux mount/egress/
UID/child/source checks выполняются реальным pinned safety preflight каждого run.
Host launcher имеет Docker/Git доступ; product process и его children confined.
Этот launcher не назван confined actor или actor tool adapter.

На clean committed candidate:

```text
uv run --locked --managed-python python -B tests/fixtures/forge_trust_closure_v1/replay.py --source-commit <40hex-current-head> --phase wal --attempt <new-attempt> --output-root local/forge-trust-closure-v1/runs
uv run --locked --managed-python python -B tests/fixtures/forge_trust_closure_v1/replay.py --source-commit <40hex-current-head> --phase producer --attempt <new-attempt> --output-root local/forge-trust-closure-v1/runs
uv run --locked --managed-python python -B tests/fixtures/forge_trust_closure_v1/replay.py --source-commit <40hex-current-head> --phase joint --producer-volume ftc-<head12>-producer-<new-attempt>-evidence --attempt <new-joint-attempt> --output-root local/forge-trust-closure-v1/runs
uv run --locked --managed-python python -B tests/fixtures/forge_trust_closure_v1/replay.py --source-commit <40hex-current-head> --phase residual --residual-group closure --attempt <new-attempt> --output-root local/forge-trust-closure-v1/runs
```

`residual --residual-group all` запускает прежние выбранные native/contract seams,
без импорта исторических charter verdicts. `bridge` — более узкий producer→dossier
segment; baseline compatibility использует retained baseline producer volume.
`joint` дополнительно связывает тот же input с открытым operational WAL и fresh
API/HTTP. Synthetic operational job — отдельный штатный input этого store,
он не создаёт ни scientific records, ни execution relation.

Перед новым batch измерить размер exact owned volumes/run roots; лимит evidence
2GiB, sequences200. CPU/RAM/PID bounds — 2/2GiB/128; run deadline <=1800s.
`--timeout-seconds` с меньшим значением допустим для intentional control.
NOT_RUN, HARNESS_ERROR, PRODUCT_TEST_FAILURE, TIMEOUT, INTERRUPTED и PASS
разделены; timeout останавливает exact owned container и сохраняет terminal.
Failed attempts сохраняются. Один неправильный joint oracle исправлен с exact
reason; timeout canary не участвует в scientific grading.

Evidence root содержит `manifest.json`, `terminal.json`, `run.log`, source/kit
hashes, compact summary, safety preflight и self-contained `receipt.json`.
Проверка receipt требует внешнего expected hash:

```text
uv run --locked --managed-python python -B tests/fixtures/forge_trust_closure_v1/replay.py --verify <owned-run-root>/receipt.json --expected-receipt-sha256 <recorded-64hex>
```

Изменение summary с прежним receipt даёт ARTIFACT_HASH_MISMATCH. Изменение receipt
даёт RECEIPT_HASH_MISMATCH. Это integrity check по доверенному pin, а не подпись
или защита от владельца host, который может переписать все независимые pins.
Stale observer canary получает настоящий RUNNING при committed COMPLETE;
identity canaries меняют реальные row/spec inputs, не assert-False.

Compact Git evidence хранит logical container/volume/run locators, source/output
hashes и key observations. Raw `/audit` retained в exact owned Docker volumes;
`local/forge-trust-closure-v1/runs/<run-id>` — ignored host copy. Другому executor
raw volumes недоступны без отдельного переноса; отсутствие pinned runtime тоже
явно UNKNOWN/BLOCKED. Git bundle/kit воспроизводимы из immutable Git objects;
timestamps/temp IDs означают, что будущий raw hash может отличаться. Acceptance
оценивает observable assertions/source identity, не byte equality будущего run.

Финальный cleanup readback должен подтвердить ноль running campaign containers
и retained artifacts. Ничьи volumes, исторические baa-* и `.claude/` не удалять.
Docker prune, изменение credentials/settings, network/provider/bootstrap/deploy
не входят в этот reproducer.
