---
contract_id: LIST_A_CONFIRMATION_PROTOCOL_V1
contract_version: '1.0'
as_of: '2026-10-12'
owner: GOAL_OWNER
task: LIST_A_CONFIRMATION_PROTOCOL_FREEZE_V1
status: DESIGN_VALIDATED_BOUND_CONTRACT_NOT_READY
configuration: configs/list_a_chronological_confirmation_v1.yaml
---

# List A: научный контракт первой заранее определённой проверки

Implementation continuation: `docs/contracts/list_a_confirming_execution_v1.md`
описывает отдельный native producer/Spec 1.5. Исторические поля и научный core этого
freeze не перепривязаны; real sample по-прежнему UNBOUND. Synthetic engineering
доказательства continuation не являются реальной подтверждающей проверкой.

Принятый смысл и метод материализованы. Полный data-bound freeze **не готов**:
локально найден только `REL-20261007T000000Z-20261008T000000Z`, опубликованный
как `EXPLORATORY_REUSE` с `confirmatory_reuse_forbidden=true`. Metadata даёт
верхнюю границу 24 mint и 2 calendar blocks каждого partition; baseline требует
30 в каждой группе. История exposure и current protection не установлены как
полная. Этот источник не является approved validation sample.

Authority: explicit owner EXECUTE, D01–D08 и §3 исходного PRD+SSD, сохранённого
один раз в `docs/evidence/list_a_confirmation_protocol_freeze_v1/source-contract.md`.
Данный контракт не разрешает values read, scientific look, capture, PROMOTE,
StrategyVersion, activation, VPS, EEB/trading repair или расходы. Merge принимает
только ограниченный design outcome; научный binding gap после merge сохраняется.

## Вопрос и единица анализа

Purpose — FIRST_PREREGISTERED_TEST. Существование source-bound empirical
development record не установлено; synthetic reference не является development
sample. Отсутствие такой записи в проверенном scope не доказывает отсутствие
прошлых просмотров. Новый exploratory look не требуется для задания first-test.

Population OPPORTUNITY_EPISODES; canonical A `JUPITER:toporganicscore:5m`,
membership EPISODE_T0, LIST_CONTRAST, `all_of:[A]`; decision E1800, target E14400,
field FIELD-USD-PRICE-001. A содержит decision-eligible episodes с known TRUE;
C — known FALSE в **том же** declared admitted universe. UNKNOWN/INVALID не C.
AB/AC/ABC входят в A. Admission/witness — существующая source semantics, не
новая фильтрация outcome. Scope `REQUIRE_KNOWN_REFERENCED` сохраняется.

`r_i=P_i(E14400)/P_i(E1800)-1`,
`delta_hat=mean(r_i in observed A)-mean(r_i in observed C)`.
Weights равные для episodes. Повторные mint сохраняются; exact episode copy
deduplicated; conflicting copy INVALID. Denominators: admitted → scope-known →
decision-eligible → target-observed, с reason counts для каждого исключения.
Future target не участвует в eligibility и не исправляет decision prefix.

Direction A_GREATER_THAN_COMPLEMENT, delta=0. Claim observational/predictive,
conditional-on-observed-targets; не causal, unconditional population effect,
unseen-mint generalization, practical economic edge, executable return/portfolio
profit. E14400 — возраст 4h от T0; nominal interval после E1800=12,600s=3.5h.

## Source и clock owners

`hfic_research_scope` owns definition, alias/selector/membership; reference A
проверена существующим resolver на pinned parameter-only schedule. Конфигурация
хранит definition hash и raw schedule-artifact reference отдельно от scientific
query и sample. Aliases — presentation; canonical definition с другим meaning
не становится прежней A. Source floor/sampling/universe остаются в exact pinned
source schedules; другой source scope не выбирается по эффекту/длине истории.

`opportunity_episodes.resolve_point` — единственный point/clock owner;
`hfic_temporal_discovery` — native decision-prefix/price admissibility owner.
Canonical decision time для calendar blocks — `resolve_point(..., E1800).nominal_due`;
actual price availability и deadline проверяются отдельно, без смешения clocks.
Reference schedule — metadata witness, не permission и не validation sample.
Native confirming query/spec ещё не произведён; его идентичность требуется
будущему producer, не выдумывается в этом contract-only атоме.

## Metadata, protection, exposure и chronology

Разрешены локальные metadata IDs/hashes/clocks/definition/schedule/protection/
exposure refs. Не читать numeric observations, target presence/missingness,
scores/returns, Parquet statistics/preview. Trusted manifest hashes предпочтительны
hash-only чтению raw files. Physical opaque bytes reads отличаются от semantic
value decoding. Metadata JSON с observation counts читается allowlisted token
projection; не `json.load` всего lineage. Parameter-only schedule parser не
является observation reader. Readset и before/after metadata hashes сохраняются.

Frozen protection и future current stricter protection проверяются раздельно.
`holdout=false`/`outcome_previously_consumed=false`/пустой ledger не доказывают
untouched; pending/crashed reservation потенциально exposed. Imported source
требует complete provenance, а не заявления consumer. Assignment не меняется.
Protected sample можно описать при разрешённой metadata, но значения потребуют
отдельного exact grant; exploratory DENY не ослабляется переименованием role.

Final binding: exact approved source-set IDs, release/manifest/labels/raw hashes,
schedule/definition, UTC half-open interval, exposure/protection snapshot refs,
chronology proof и structural upper bounds. No latest/current/all_available
fallback в approved sample. Discovery текущего pointer допустим для inventory;
его результаты находятся только в rejected-candidate evidence. Source order
canonical по `(cohort_id, release_id, dataset_manifest_id)`; conflicting duplicate
refuses. Earliest admissible window применяется лишь в заранее принятом exact
source scope с bound upper end. Scope/end сейчас не приняты, поэтому UNBOUND.

Для empirical development/относящегося exposure:
`boundary=max(dev_target_available_max, dev_decision_max+E)`;
`validation_information_start > boundary`, с purge overlapping information/label
intervals. E один раз задаётся максимальным bound target horizon от T0 плюс
grid/lateness/visibility allowance по pinned clocks; unknown component → gap.
E не прибавляется повторно к boundary. Naive time/equality/overlap refuse.
FIRST_PREREGISTERED_TEST без empirical development не получает fake dev clocks;
остаются реальная exposure/protection граница и preregistration requirement.
Same mint не purged только из-за identity; unseen-mint claim не заявлен.

До outcomes проверять только potential support upper bounds. `<30` →
INSUFFICIENT_POTENTIAL_SUPPORT / BOUND_CONTRACT_NOT_READY. `>=30` означает только
SUPPORT_POSSIBLE_NOT_PROVEN; target coverage и actual support остаются будущими.
Нельзя открыть targets ради preflight или снизить threshold под доступную историю.

## Замороженный метод

Episode-weighted mean contrast, crossed-cluster percentile bootstrap: mint ×
epoch-aligned UTC decision blocks, h=86400 и172800 секунд;
`block_id=floor(canonical_decision_at.unix_seconds/h)`. Labels mint canonical
lexicographic, blocks numeric ascending. B=4096 на каждый partition.
В каждой replicate M draws из M mint labels с возвращением, затем T draws из T
blocks. `w_i=mint_multiplicity_i*time_multiplicity_i`; один набор weights для A/C;
weighted means по episodes, не средние cluster means. Не хранить B копий rows.

Sampler stdlib random.Random / MT19937 / randrange на pinned CPython3.13.14;
partition seed — int первых16 hex SHA256 UTF8(core_sha256+':'+str(h)). Core
включает derivation rule, исключает собственный digest, derived seeds/receipts.
Новый runtime требует explicit compatibility/reproducibility binding до look.
Числовой backend CPython IEEE754 binary64; native price admissibility сохраняется,
ratio реализует указанную native meaning; sorted canonical episode order,
math.fsum для numerator/denominator/means. JSON shortest-roundtrip finite numbers,
`allow_nan=false`; сравнения без округления и EPS. Unresolved numeric instability
→ INSUFFICIENT, никогда automatic PASS. Hand oracles Fraction/Decimal.

Nearest-rank quantiles sorted ascending: k=ceil(p*B), 1-based; p=.025/.975,
ranks103/3994, indices102/3993. Никакой интерполяции. Empty/nonfinite replicate
→ INSUFFICIENT; нет reroll/drop/другого seed/метода. Signed-zero не создаёт >delta.

Для **каждого** partition и каждой группы ≥30 contributing mint и ≥30 contributing
time blocks; также ≥30 в целом. Обе группы nonempty. Coverage ≥.95 каждой
decision-eligible группы, missing-rate gap ≤.05. Эти future checks не открываются
при freeze. Leave-one каждый mint и каждый occupied block обоих partitions:
point contrast без нового bootstrap, обе группы finite/nonempty. Contributions
и концентрация раскрываются; raw N не effective N.

Правило в порядке precedence:

1. Incomplete method/sample/meaning → BOUND_CONTRACT_NOT_READY до look.
2. Identity/protection/PIT/chronology violation → INVALID_OR_BLOCKED, exposure
   at failure сохраняется.
3. Support/coverage/finite calculation/replicate/diagnostics absent → INSUFFICIENT.
4. Пусть CI24=[L24,U24], CI48=[L48,U48], D все declared leave-one point contrasts.
5. `L24>delta AND L48>delta AND min(D)>delta` → ASSOCIATION_SUPPORTED_CONDITIONAL.
6. `U24<=delta AND U48<=delta AND max(D)<=delta` →
   ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY.
7. Иначе INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION.

Это local protocol terminal mapping, не mutation existing global enums.
Negative не закрывает family/любой trading estimand. Constant synthetic lattice
проверяет algebra, не empirical coverage; post-look veto «слишком красиво» нет.

Crossed bootstrap требует assumptions о dependence; не гарантирует 95% coverage
для произвольного nonstationary heavy-tail рынка. Count30 не доказывает
independence;48h/leave-one screens не исправляют arbitrary serial dependence.
95% target coverage не MAR proof; отсутствующие returns не становятся zero/-100%.
Unconditional bound не выводится без accepted censoring bounds/model.

## Hash domains и cold consumer

Canonical JSON owner `observation_schedule.canonical_sha256`: sorted object keys,
compact UTF8/ensure_ascii=false/allow_nan=false. Decimal thresholds — canonical
strings, positive integer fields не bool, canonical array order explicit.
`protocol_core_sha256` hashes целиком `protocol_core`: question, logical query,
owners/versions, method, numbers, constraints и verdict. Presentation исключена.
`sample_binding_sha256` hashes целиком sample_binding, включая UNBOUND/gaps;
наличие digest не делает его bound. Derived seeds вне этих двух domains.
Freeze receipt identity hashes core/sample/accepted authority/evidence digests,
не себя/временную timestamp. Raw SHA source/contract/config отдельно.

`verify_contract.py` — compact evidence consumer, не production evaluator/CLI.
Fresh process открывает persisted config/contract/readset, пересчитывает hashes
и bound readiness. Wrong hash/representation/truncation не проходит. Он не
читает research data и не записывает store. Synthetic contract-ready witness
может быть FROZEN только в его явно synthetic-only check scope; published actual
config остаётся BOUND_CONTRACT_NOT_READY. Нельзя заменить real bindings fixture.

## Обязательства следующего producer, вне текущей реализации

Metadata/current grant → durable atomic source-bound reservation → first values
read → native verdict/limits → allowlisted substantive projection → existing
ResearchStore commit → cold dossier. Reservation count/ownership/exposure survives
crash; один evaluator; replay completed result без evaluator; unresolved resume
только original immutable identities. Generic DocumentRunner RUN_STARTED/append
после capability не является pre-values gate. Reuse public transaction/reservation
owner, не private `_reserve` и не new lock DB. Их реализации здесь нет.

Technical accepted_terminal_match не scientific metric; arbitrary artifact
whitelist и authored scientific payload запрещены как producer substitute.
Positive A не закрывает ENTRY/EXIT/COST/EEB. Contemporary entry/reverse quote
не E14400 exit. Portable query/compilation receipt должны войти в spec до
run/PROMOTE; selected cohort IDs остаются sample, не runtime universe. B-policy,
Trading Closure, effectiveness/live accounting и signer — отдельные authorities.

## Terminal, cleanup и resume

DESIGN_VALIDATED означает проверенный контракт, не empirical qualification.
FROZEN_FOR_SEPARATE_AUTHORIZED_CONFIRMATION требует всех real bindings; сейчас
BOUND_CONTRACT_NOT_READY. F01–F12 сохранены со scope/fidelity и remaining gaps.
Cleanup касается только own scratch/runtime; canonical small evidence сохраняется.
Revert unused contract/config обычным commit; exposure history никогда не reset.

Первый resume input — разрешённый sanitized metadata export exact другого
closed candidate scope: IDs/hashes/schedules/list definition, complete exposure,
frozen/current protection, declared end и structural support ≥baseline. Не менять
нынешние exploratory labels, не собирать новую campaign автоматически, не
уменьшать thresholds и не начинать empirical confirmer/market look этим task.
