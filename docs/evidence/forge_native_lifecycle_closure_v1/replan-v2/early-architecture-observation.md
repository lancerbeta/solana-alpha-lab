# ARCHITECTURE_CRITIC — early V2 consultation

head=398fa895235e26825d87f05e5c7399924f259993
base=d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc
packet_fingerprint_sha256=a245e5b5d6f587893ec18d3832c2b19a9968f4881cefb0ea7c04757d970ba916
diff_sha256=579545b06df0ac15b5b4fd21d808ea0717fd752c3d50d272431b501ede867015
role=ARCHITECTURE_CRITIC
profile=SEMANTIC_PREMISE
semantic_verdict=FAIL_SCOPED_REQUEST_REFUSAL_PROVENANCE
architecture_verdict=NOT_READY
ready_for_new_native_trial=false
merge_readiness=NOT_EVALUATED
native_acceptance=NOT_EVALUATED
model_diversity=UNPROVEN

Ключевой результат: новые scope/UNKNOWN semantics соответствуют V2, но текущий публичный отказ не привязан к исходному request, несмотря на прямое обещание provenance. До нового native trial нужен один ограниченный repair этой границы и affected delta review. Desired scientific terminal, alpha и модельная diversity здесь не критерии готовности.

## Scope и проверенные bindings

Review запущен отдельно, read-only; единственная запись — этот отчёт. Исходный контекст: frozen architecture packet, candidate.diff, validate-launch.json и candidate-binding.json. Implementation transcript, native ответы, исторические readouts и скрытые source/oracle fixtures не использовались. Проверены exact HEAD, чистый worktree, hash diff, task contract и двух разрешённых evidence files. Проверялись V2 source/normative hunks exact diff; это не полное delivery review всех исторических evidence hunks.

Дополнительно разрешён точный ref `replan-v2-development-control/control-frozen.json`, разрешённый родителем для проверки спорного actual-packet claim. Его SHA256 совпал с hash frozen mechanics evidence: `b96eeb5e1bc7e44ae22af74b1ae3d5aa9dde68564bdd37818f6c5d5a39b19533`. Прочитаны необходимые поля `critic_input_packet`; это scripted control, не native output. Packet version 1.5, packet hash `c58534e7e9278d7f2d78f271a973eb4dd132f99e973893f126b630d9ff180d48`.

`independence.claim_scope=PACKET_INFORMATION_PATH` подтверждает ограничения информационного пути packet. Builder flags и validate-launch не доказывают live launch isolation; это PROCESS_OBLIGATION. Наличие отдельного reviewer не доказывает alternate-model identity. Parent reassurance не использовалось как evidence.

## Findings

**P1 — implementation defect: отказ CURRENT_REQUEST_BEFORE_MAIN теряет provenance исходного request.**

Exact requirement: `docs/contracts/forge_native_lifecycle_closure_v1.md:116-117` обещает stage, missing/conflicting fields, provenance и zero new effects. `validate_discovery_request_scope`, `src/solana_alpha_lab/factory/hfic_grounded_discovery.py:1354-1386`, формирует mode/field diagnostics, но не source refs и не hash исходного spec/scope. CLI `scripts/hypothesis_forge.py:1497-1501` только переносит detail; поэтому у двух разных invalid requests может быть одинаковый refusal без machine binding к проверенным bytes. Refusal перед MAIN остаётся техническим и не создаёт negative evidence, но заявленный provenance contract не выполнен. Тест `tests/test_forge_native_lifecycle_closure_v1.py:147-169` проверяет реальные inventory/look/operation effects и loader/reservation, но source binding не проверяет; он проходит с этим дефектом.

Минимальная коррекция: сохранить hash/ref именно прочитанных исходных query/scope bytes и включать их в текущий публичный refusal. Не включать absolute paths или raw значения. Для prior отказа сохранить существующие source refs; для source unavailable явно сохранить typed unavailable. Использовать существующие hash helpers и error transport, без нового store/DSL/framework. Проверка repair: два различных invalid current request получают различные проверяемые source bindings; loader/reservation не вызваны, inventory/look/operation unchanged; saved replay/correction не приобретают новых look или новых binding semantics. Это обязательный адресный repair перед новым trial.

**P2 — evidence limitation: equality axes не доказывает Q3, соответствие авторского вопроса actual query.**

`mechanics.json:9,33` ограниченно подтверждает `PASS_INDEPENDENT_AXIS_EQUALITY` и scope_match. Actual scripted packet сохраняет claim `List A membership separates ...`, но `grounded_evidence.descriptive_readout.scientific_identity.primary_x_family` задаёт holder delta, а scope statement — `NUMERIC_IN_SCOPE`, `UNIVERSE=(ALL)`, `SIGNAL=NONE`. Сравниваемые tags population/decision/target/estimand/condition/hash/statement совпадают с selected candidate. Проза claim при этом не описывает фактически вычисленный discriminator.

Это конкретный пример того, что может пройти tests и сломать исследовательский смысл. Control остаётся допустимым mechanics evidence, потому что он явно excluded from native numerator и scientific acceptance. Его нельзя расширять до доказательства faithful question или успешного independent Critic. Минимальная коррекция — явно удержать этот предел в readout и требовать от native Critic сравнения текста вопроса с actual experiment_recipe, comparator, scope и missingness. Старые control/native bytes не редактировать и не переоценивать. Этот P2 отдельно не требует нового model call или desired terminal.

**P2 — documentation ambiguity: “guards establish no active restriction” следует читать как “guard не установил block”.**

Наиболее точное evidence поле — `guard_assessment=NO_BLOCK_ESTABLISHED_BY_SCOPE_GUARD`, `hfic_grounded_discovery.py:1591-1597`. Более сильная формулировка skill `independent-hypothesis-critic/SKILL.md:200-202` может быть прочитана как доказанное отсутствие любых applicable restrictions. UNKNOWN applicability такого вывода не позволяет. Поля applicability/novelty остаются UNKNOWN; claim_dependency требует independent assessment. Минимально уточнить wording в будущем affected delta: guard result не доказывает отсутствие ограничения или scope distinction. Это wording issue, не обнаруженное расширение runtime authority.

P0 не обнаружены. P1 не является scientific premise rejection всей V2 матрицы: её основание поддержано; нарушен конкретный promise provenance в новом error boundary.

## Проверенные architecture boundaries

- **PASS, scope до новой MAIN/value/reservation.** CLI читает actual spec/scope один раз, валидирует новый request в `hypothesis_forge.py:1492-1496`; operation creation/reservation идут после этого (`:1610,1625`), partition loader — `:1686`. Executor повторяет тот же public validator для actual spec (`hfic_grounded_discovery.py:2540-2547`). Это не отдельный check-only result, который можно применить к другому query.
- **PASS, machine truth.** Population/decision/target/list-rule hash и statement derives existing canonical query owners; explicit mismatch refuses (`hfic_grounded_discovery.py:1365-1385`). Authored estimand/condition требуют presence, не выводят из Y. Содержательная верность этих строк остаётся независимой задачей Critic.
- **PASS, mode distinctions.** Omission получает existing ordinary-route label; explicit null, unknown/invalid и conflicting known route имеют разные mode_state (`:1355-1363`). Это route provenance, не научная оценка. Explicit old labels/saved results не переименованы. Current error provenance отдельно FAIL по P1.
- **PASS, prior matrix.** Current incomplete scope refuses. Exact relation блокирует (`:1567-1572`); near-close с совпадающими доступными axes и gap блокирует (`:1499-1513,1573-1581`). Full archive guard исполняется до ranking (`hfic_generation_context.py:271-287`) и повторно при candidate working view (`:415-455`). Ограничение относится к существующему scope guard, не к математически доказанному глобальному отсутствию любой сходной работы.
- **PASS, actual packet UNKNOWN.** Actual frozen packet содержит UNKNOWN relation, missing axes, hypothesis record_id/payload_sha256, effective/first-reliable clocks, unknown_prior_is_evidence=false и claim_dependency=REQUIRES_INDEPENDENT_CLAIM_ASSESSMENT. Source capsule остаётся HISTORICAL с null outcome и failure_boundary UNKNOWN. Ничего не превращено в distinct, negative, closed, zero или family reopening.
- **PASS, необходимые actual-packet fields.** Grounded candidate_scope содержит mode и все binding axes; selected_candidate содержит authored axes, claim/alternative/falsifier; query/result spec hashes совпадают. Mode отсутствует в normalized selected_candidate, но доступен в grounded candidate_scope — это нельзя читать как explicit null. FULL_ELIGIBLE_ARCHIVE receipt находится в generation_context.safety_receipt; его hash совпадает с prior_memory.safety_check_receipt_ref. UNKNOWN capsule действительно включён в memory. Claim dependency не объявлена машиной доказанной.
- **PASS с пределом, PIT/history/recovery.** Provenance retains separate research cutoff и source availability clocks; этот diff не меняет temporal evaluator, list admission, budget owner или readable packet enums. CLI saved-result path пропускает новое current admission и читает saved result; corrections остаются отдельным compatible owner. Не запускались store recovery или native replay; runtime доказательство V2 recovery ещё требуется внутри основной задачи.

## Truth owners, blast radius и проверка premise

Authored смысл принадлежит Generator/owner; machine axes — canonical query/scope owners; immutable look — discovery/session owners; научная оценка dependency/quality — independent domain Critic; acceptance/budget — owner contract. Engineering scope validator и lifecycle status не становятся scientific truth owners. В частности FROZEN_AWAITING_CRITIC, scope_match и technical KILL не получают scientific authority.

Если DuckDB projection исчезнет, truth остаётся в immutable `research/events/date=.../*.parquet`, canonical payloads и hash-bound partition manifests; `research_store.py:1477-1502` задаёт location/content/file hashes. Projection/lookup не заменяет эти bytes (`research_store.py:1315,1815-1822`). Diff не добавляет store и не меняет durable envelope. Rollback кода не должен менять старые packets/verdicts или возвращать spent looks.

Нового TASK-модуля, импортирующего другой TASK private API, нет. Новый validator имеет public name. Legacy wrapper readback уже использует `hfic_ordinary_operation._looks/_operation_result` (`hypothesis_forge.py:224-261`), а generation context — session artifact loader и `_valid_close`; это существующие зависимости одной Forge границы, не новая task authority. Их private coupling повышает стоимость будущей смены owners; отдельный public readback wrapper уместен только при реальном следующем изменении этой границы, не как условие этого repair.

Самая простая зрелая альтернатива сохранена: один existing canonical query validator, existing scope relation/full archive guard, existing hash-bound log и compatible readers. Новый generic platform/DSL/provider/storage не нужен.

Premise может быть ложным даже при точном протоколе: Critic ошибочно принимает семантически иной вопрос, либо interprets “no block established” как novelty. Самое сильное неподтверждённое расширение — faithful scientific question из equality tags; concrete falsifier уже виден в scripted packet. UNKNOWN/missing не преобразуются в отрицательную evidence; lifecycle/schema не переписывают старое значение. Будущий агент должен вывести только “request syntactically bound, safety guard found no block, claim still needs independent assessment”. Нужная минимальная коррекция runtime — request-refusal provenance (P1); нужна сдержанность evidence wording (P2), не расширение science.

Verification: read-only code/contract inspection, exact file hashes и selected actual-packet comparisons. Tests не запускались; retained test-count PASS рассмотрен как bounded mechanics receipt, не независимый повтор. Runtime/store/task/Git не изменялись.

Следующий шаг: ограниченный P1 repair и affected delta architecture verification, затем можно заморозить evaluation epoch и запускать новый primary trial в существующем V2 envelope. Этот отчёт не разрешает merge, не признаёт native closure и не меняет старые verdicts.