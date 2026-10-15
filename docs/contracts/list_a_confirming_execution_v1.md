---
contract_id: LIST_A_CONFIRMING_EXECUTION_V1
contract_version: '1.0'
as_of: '2026-10-14'
owner: GOAL_OWNER
task: LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1
status: IMPLEMENTED_AND_VERIFIED_IN_SYNTHETIC_SCOPE
---

# List A: native confirming producer

Git definition `configs/experiment_specs/list_a_chronological_confirmation_v1.yaml`
использует version-isolated ExperimentSpec 1.5 и
`CAP-LIST-A-CHRONOLOGICAL-CONFIRMATION-001`. Legacy 1.0–1.4 сохраняют свой смысл.
Научный core `3b62c8ccdc797c8f378aef831c2b5cad45bdc1e9c336ba94417bf54ccbd7e252`
и исторический real sample binding `UNBOUND` остаются прежними.

Три разных действия: native source ingress сохраняет immutable файлы;
`register-source` показывает source-owner request и принимает exact
`REGISTER <domain> LIST A SOURCE <sha>`; `prepare` компилирует metadata binding,
а `authorize` принимает `AUTHORIZE <domain> LIST A <sha>`. Ни source registration,
ни definition/merge, ни произвольный `approved:true` не заменяют exact grant.
Эта инженерная кампания разрешает только свои disposable SYNTHETIC registrations.
REAL grant и values требуют отдельного owner scope.

Вход: native census, observations, schedule, bounded frame receipts,
`opportunity_episodes.admission_record` документы и frozen assignment inventory.
Даты/идентичности census связываются с native admission; nomination occurrence
связывается с выбранным frame/source. Budget identity использует core и immutable
mint/nomination occurrence/object/source keys. Alias, форматирование и пересекающаяся
копия не создают новую первую попытку. Scope authority — один canonical data plane.
Нет защиты от оператора, намеренно подделывающего source-owner факты или создающего
запрещённый дубликат REAL plane: такой путь не разрешён этим контрактом.

До reserve проверяются complete exposure, chronology/purge, opaque hashes,
allowlisted metadata, potential support, runtime/registry/local filesystem.
Observation state/value/statistics в preflight не декодируются. Frozen и current
native protection проверяются независимо на полном information/target interval.
Только совместимый untouched holdout допускает exact-purpose consumption;
DENY, revoke, unknown scope и incomplete inventory блокируют его.

Source role проверяется в исходных hash-bound census и observations по metadata
колонкам `evidence_role` и `confirmatory_reuse_forbidden`. На каждом row нужны
`UNTOUCHED_FORWARD_HOLDOUT` и boolean false. EXPLORATORY_REUSE/true дают typed
`CONFIRMATORY_REUSE_FORBIDDEN`; отсутствующая provenance —
`SOURCE_ROLE_PROVENANCE_UNBOUND`. Новые Sample paths/hashes и внешний exposure
не повышают исходную роль. Чтение ограничено двумя metadata колонками до source
registration, prepare и current authorization; target/state не декодируются.
Native ingress сохраняет исходные labels; consumer не дописывает untouched
из внешней роли. Проверка одна для SYNTHETIC и REAL, без blanket REAL refusal.

Одна атомарная ResearchStore transaction записывает reservation + RUN_STARTED
до первого observation decoder. OS lock действует всё вычисление; TTL takeover
отсутствует. Reservation сохраняет charge 1 после crash. Current authority
перепроверяется перед reserve, первым value read, resume и completion. Exact resume
может повторить техническое вычисление, не выдавая новую scientific attempt.

Повторные prepare/authorize показывают ALREADY_RESERVED и исходный checkpoint,
включая overlap/alias; charge не обнуляется и новый grant не выдаётся. Classify/submit
при отказе после reservation показывают BLOCKED_AFTER_RESERVE с charge 1 и
исходными trial/run, в том числе для alias, подготовленного до original reservation.
Недоступная история даёт UNKNOWN/null. Native nonfinite или unrepresentable return
завершается typed INSUFFICIENT с consumed charge 1: observed counts, membership и
denominators сохранены, means/contrast — null, resampling не запускается. Identity,
protection, PIT и chronology failures сохраняют INVALID_AFTER_RESERVE.

Метод: native E1800 decision mask, E14400 observed price-relative returns;
episode-weighted A−eligible complement C. Два pooled crossed bootstrap partition
86400/172800, 4096 local seeded replicates, nearest-rank indices 102/3993,
all leave-one mint/block contrasts. Frozen floors, 95% coverage и 5% missing-gap
соблюдаются. Нулевая decision-группа — INSUFFICIENT с null coverage.
Native request_not_before определяет допустимое acquisition; nominal_due — clustering.

Publication результата предшествует одной completion transaction из passport,
TRIAL, RESEARCH_ARTIFACT, EXPERIMENT_METRIC и DIRECT EVIDENCE_BINDING. Orphan result
без completion не доступен как PRESENT. Cold reader проверяет closed nested schema,
numeric/terminal consistency, exact binding/grant/source/reservation/run identity,
hash и все carriers в одной transaction; он не читает source values и не вычисляет.

Ordinary dossier показывает отдельные trials/bindings, conditional outcome и
неизвестное; PAUSE/REJECT/REVISE используют штатный decision writer и stale guard.
SYNTHETIC, nonpositive, insufficient и invalid confirmation запрещают PROMOTE даже
при generic fillers. VERIFIED REAL supported может пройти только прежние science
guards; подтверждённый proxy сам по себе не доказывает net alpha/executability.
Если result не верифицируется, committed reservation и consumed charge остаются
видимыми; execution UNKNOWN, evidence CONFLICT. NO_RUN/NO_DECISION требуют полного
доступного чтения истории. Недоступность не является доказательством отсутствия.

CLI: `scripts/list_a_confirmation.py register-source|prepare|authorize|revoke|classify|submit|status|show|resume`.
`--data-root` должен быть exact owned plane. Source paths относительные, traversal,
symlink/junction и foreign observation identities запрещены. Cold status по trial ID
не переоформляет исторический результат как свежую authority.
`revoke --binding-id <binding>` только показывает request и exact owner phrase;
повтор с `--owner-phrase "REVOKE <domain> LIST A <request-sha>"` записывает отзыв
именно этого grant. Отзыв доступен и после current incompatibility/expiry, не
возвращает allowance и не скрывает сохранённый результат; exact repeat идемпотентен.

Calendar maturity проверяется по metadata всех native admissions до observation
value decoding, evaluator и scientific reservation. Авторитетный clock owner —
`opportunity_episodes.resolve_point`: E14400 availability deadline включает grid
rounding и grace и должен быть <= frozen sample data_cutoff. Незрелый sample
получает `BOUND_CONTRACT_NOT_READY / TARGET_NOT_MATURE_AT_CUTOFF`; NEXT —
`WAIT_FOR_MATURITY_THEN_SEPARATELY_REBIND_EXACT_SAMPLE`. Ни cutoff, ни границы
sample автоматически не меняются. Проверка не читает target missingness или
статистики. Зрелые `MISSING_TYPED` остаются в полном decision denominator и
поступают в evaluator/coverage. Уже consumed charge и UNKNOWN не превращаются
в новый unspent trial при отказе текущего binding.

Acceptance, ресурсы и воспроизведение: `docs/reports/list_a_confirming_producer_v1/`.
Никакой StrategyVersion/activation/provider call/deploy этим producer не создаётся.
