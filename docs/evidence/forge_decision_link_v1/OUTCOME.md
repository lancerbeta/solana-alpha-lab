# FORGE_DECISION_LINK_V1 — квалификация результата

Исправлена потеря безопасного продолжения и публичного доступа к исходным
связям теста. Нового хранения или правила выбора нет. Основание остаётся в
существующем immutable `question_text`; результаты, accounting и оценки — у
прежних владельцев.

До ремонта changed explanation могла занять вторую резервацию того же pending
spec под другим operation. Это воспроизведено в multi-b03. Теперь outer gate и
повторная проверка под writer lease возвращают original operation/reservation.
Неоднозначная старая двойная pending-запись возвращает typed conflict: система
не выбирает победителя задним числом. Для landed result replay показывает
исходного producer и его текст, отдельно от нового requested operation hash.

Второй дефект — navigation. Связи хранились, но cold consumer собирал их через
private helpers и файлы. Новый `discovery-show` в существующем CLI читает их из
одного committed snapshot. Положительная ветка получает exact source links к
draft/selected packet и переходит к штатному session owner. Это ссылки на
источники, а не новый scientific verdict или lesson lifecycle.

## Проверяемый consumer route

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <existing-store> discovery-show --result-ref <result-ref>
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <existing-store> discovery-show --operation-sha256 <original-operation-sha256> --offset 0 --limit 20
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <existing-store> show-session --session-id <source_links.session_id>
```

Первое чтение показывает исходный request/план, точный canonical query,
резервацию, result hash и применимость оценок. Отсутствующее — `NOT_RECORDED`,
нечитаемый или противоречивый источник — typed gap. `RECORDED_REQUEST` означает
сохранённый исходный текст, а не автоматическое научное принятие плана. Общий
operation-level текст нескольких legacy tests не превращается в отдельные
pre-test планы по каждому query. Parent P2 не переписывает
P1. `SOURCE_DERIVED_CANONICAL_QUERY` восстанавливает штатную нормализованную
форму; исходные author-file bytes не заявлены. Ни одно чтение не запускает
preflight, commissioning, values или evaluator.

`source_links` сопоставляет одновременно result ref и SHA. Context-only
runner-up не становится подтверждённым candidate. Собственный Critic и итог
проверяет `show-session`, а не эта проекция. Отсутствующая отдельная disposition
не понижает positive outcome и не вынуждает писать отрицательную оценку.

## Evidence и границы

- **Multi-look:** native P1 → MAIN T1 → R1 → новый parent continuation P2 →
  ADAPTIVE T2 → R2; оба полных плана сохранены до своих loader/evaluator.
  У P2 названы exposed R1, discriminator, outcome actions и forbidden claims.
  Общая accounting lineage; занято MAIN1/ADAPTIVE1/PREVIEW0, pending0. Journal
  limits6/2/2 не менялись. Fixed literal oracles: T1 n4/observed3/missing1,
  mean0.10/contrast0.20; T2 n4/observed3/missing1, mean−0.20/contrast−0.325.
- **Recovery:** реальные child exits после committed reservation и после
  durable result до ACK. Cold resume и conflicting-story replay сохраняют
  original basis/result и не расходуют второй look.
- **Race:** два автора доходят до native reserve barrier; unrelated append
  остаётся допустимым. Одна резервация, typed loser с original locator;
  loader/evaluator0 у обоих fault children.
- **Сцепления:** один fixture correction → old assessment review-required →
  successor current → withdrawal; другой fixture advisory append → stale detail
  → эквивалентный reissue с прежним cutoff → hidden full-archive guard. Late
  records не перемещают прежний context. Старые source bytes сохранены.
- **Совместимость:** legacy ordinary/positive/freeze/revision/finalize,
  normalized/cycle-two accounting и scoped close/recovery проверены адресно.
  Сценарный scientific Critic здесь доказывает переходы, не научное принятие.
  Откат BASE script-reader проверен на текущих неизменённых disposition owners;
  полный исторический program rollback не заявлен.
- **Retention:** на исходном b06 проверены159 artifact hashes,17 source snapshots
  и272 native files. Wrong link, missing terminal и changed artifact на копиях
  дают exit2; исходные2063 файла сохранены. Финальное cold чтение связано
  отдельно с final reader: child9.021s, wall14.456s,272 файла без изменений;
  текущий audit проверяет211 artifacts/17source snapshots. Все11 адресных
  тестов reader/pending PASS за24.184s. Integrity отделён от product PASS.

Полный знаменатель V01–V18 и R1–R12/D1–D12 сохранён в `qualification.json`.
Это доказательство названной synthetic per-test вертикали и конкретных impact
subsets; самостоятельные subsets не складываются во всю Factory FULL.

Исходный S0 остаётся историческим:935.136s против900s, утраченная часть raw cold
history и stale command-log hash. Новое разрешение не исправляет прошлое.
multi-b01/b02/b04/b05 и qualification-c01/c02 сохраняют собственные failures и
source fingerprints. b05 сравнивал sparse ingress с нормализованным query;
исправлен oracle convention в новом b06, не landed план. c02 выявил ошибку
семантического config ceiling, исправленную без расширения ceiling.

impact-d01 содержит44 успешных assertions, но parent watchdog900s сработал,
остановка owned tree была отклонена системой, процесс завершился за925.511s.
Его resource status остаётся `FAIL_OR_HARNESS_ERROR`. d02 сохранил pre-product
CRLF harness failure. В d03 прошли positive и первый cycle-two сценарий, затем
parent600s прервал следующий тест. d03 также `FAIL_OR_HARNESS_ERROR`.
Только незавершённые сценарии проверены отдельно: d04 — один normalized variant
за169.633s, d05 — два recovery tests за133.870s, без timeout. Пять уникальных
assertions PASS; единого успешного campaign здесь нет. Все owned children
завершены, source/input artifact manifests проверены без mismatches.
Измеренное subprocess wall time учитывается отдельно от elapsed window.
Подготовка, CPU/RAM, полное model usage и стоимость — `UNKNOWN`; file timestamps
не названы compute. Raw synthetic outputs остаются в локальных immutable
invocations; в Git сохранены ключевые результаты, hashes и воспроизводители.

## Раздельные выводы

`TECHNICAL_CONTINUITY=VERIFIED_IN_SYNTHETIC_SCOPE`.
`CHOICE_QUALITY=NO_DISTINCT_TREATMENT`: точный A9/A10 semantic excerpt не изменён.
Улучшение выбора и полезный научный transfer не доказаны. Policy A/B не
проводился, поскольку нового policy treatment нет.
`LIVE_USE=NOT_EXECUTED`; alpha/OOS/realized economics=`NOT_EVALUATED`.

Итоговая поставка — один bounded candidate с четырьмя независимыми reviews,
привязанными к committed inventory. CI и machine merge-readiness проверяются
на точном PR head; затем требуется отдельная точная owner-фраза. Git merge
сам по себе не даёт scientific acceptance или canonical product DONE.

Следующий шаг в этом атоме — штатная delivery до готовности к owner-фразе.
Новая selection policy требует отдельного измеримого treatment и authority.
Новые tools/plugins/providers/dependencies: NONE. На merge/readback достаточно
`ROUTINE_NO_SWITCH`.

## Воспроизведение

Raw stores/logs доступны только в retained local folders данного checkout;
Git содержит key numbers, hashes и исходный воспроизводитель. Hash сам по себе
не объявлен переносимым raw replay kit. Для независимого fresh synthetic run
из нового checkout сначала создать fixture существующим entry producer:

```powershell
$decisionLinkHead = git rev-parse HEAD
uv run --locked --managed-python python -B tests/fixtures/forge_decision_link_v1/entry_probe.py --output local/forge_decision_link_v1/entry-reproduce-r01 --expected-head $decisionLinkHead
uv run --locked --managed-python python -B tests/fixtures/forge_decision_link_v1/multi_look_probe.py --output local/forge_decision_link_v1/multi-reproduce-r01 --fixture-source local/forge_decision_link_v1/entry-reproduce-r01/fixture
```

Оба output directories должны отсутствовать. Уже сохранённый b06 читать и
проверять без setup/writers/new values:

```text
uv run --locked --managed-python python -B tests/fixtures/forge_decision_link_v1/multi_look_probe.py --output local/forge_decision_link_v1/multi-b06 --cold-only
uv run --locked --managed-python python -B tests/fixtures/forge_decision_link_v1/multi_look_probe.py --verify-retained local/forge_decision_link_v1/multi-b06
uv run --locked --managed-python python -B -m unittest tests.test_forge_decision_link_v1
```

## Review repair и повторная квалификация

Первый independent review candidate59ddfc8 — `NOT_READY`: найдено окно,
где B проходит раннюю проверку, A сохраняет результат, затем B получает writer
lease. Pending-only guard уже не видит A и допускает лишнюю reservation/loader;
повторный evaluator в этом окне не утверждается. Existing saved-look owner
теперь повторно проверяет точный active-policy/corpus результат под тем же lease
и возвращает `ORDINARY_LOOK_LANDED_DURING_RESERVATION` с original result locator
до append/values. Новый ledger/lock service не нужен.

`land-race-c01` использует настоящие matcher, reserve, writer и evaluator:
B entry PASS → barrier до native append → A durable result → исходный
B before_commit отказывает. B reservation/loader/evaluator=0/0/0;
A literal oracle matched/observed/missing=4/3/1, mean.10, contrast.20.
Cold replay/read сохранил230 файлов и inventory; audit проверил84 artifacts
и19 source snapshots. Native child windows29.893s, helper elapsed30.391s.

13 unit assertions PASS в c01; один policy counterpart сначала имел ошибку
порядка fixture: policy activation после нового ACTIVE operation. Existing owner
корректно отказал. C01 остаётся `HARNESS_ERROR13PASS/1ERROR`; c02 проверил только
исправленный порядок и PASS. Это distinct13+1, не успешный all14 batch.
Changed corpus/policy проверены через native reservation seam unit counterparts;
полный public admission новой policy не заявлен. Между c01/c02 изменился только
этот порядок в тесте; runtime/helper совпадают с native snapshot.
Parent windows66.594s/25.238s,600s watchdog не сработал, product children180s.

Пять S0 JSON остались исходными CRLF, их historical hashes не переписаны.
Первый commit использовал старый LF cache Git index; scoped renormalization
пяти entries и новый ordinary commit сохраняют исходные bytes. Первые review
findings сохранены, исправленный committed inventory получает fresh reviews.
Сводный raw receipt boundSHA611e3882da78d6fddc025db82692a4d3ad0372375093192f69ed3141e611b851;
ключевые числа и source bindings — `native-qualification.json`.

Fresh fixture для этого schedule сначала создать entry producer, как выше;
output нового run должен отсутствовать:

```text
uv run --locked --managed-python python -B tests/fixtures/forge_decision_link_v1/multi_look_probe.py --output local/forge_decision_link_v1/land-race-reproduce-r01 --fixture-source local/forge_decision_link_v1/entry-reproduce-r01/fixture --land-race-only
```
