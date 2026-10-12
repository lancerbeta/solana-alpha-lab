# SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1

VERDICT: ENGINEERING_PASS_CANDIDATE. Ordinary PAPER/SHADOW software outcome
проверен на frozen bytes; окончательные required reviews и delivery gate
связываются отдельно в independent-review/completion. Owner acceptance,
runtime commissioning и merge authority этим отчётом не предоставляются.
Base: `ba87f8e339d5cc3aa55322801ae56e3f92369446`; exact content fingerprint,
review inventory и CI связываются Delivery Harness. Green local tests не
являются owner acceptance либо merge authority.

## Возможность и поддержанный envelope

Обычный `trading_continuity.py run` сам проходит source episodes → shared
recipe/PIT decision → admission → PAPER model/quote-only adapter → originating
EXIT → readback. Одна durable PaperPlane DB владеет activations, controls,
attempts и общим учётом обязательств; coordinator не создаёт второй inventory.
Вход: `SEM-OWNER-LIFECYCLE` → [runbook](../../operator/TRADING_CONTINUITY_OFFLINE_V1.md).
Поддержаны OPPORTUNITY_EPISODES, exact accepted V1 science handoff, shared
MIXED_LIST_NUMERIC/LIST_CONTRAST recipes, explicit FROZEN_TIME_EXIT. Same-ID V2
остаётся denied. Synthetic PAPER и SHADOW quote никогда не actual chain fill.
Asset decimals берутся из native witness extract и удерживаются для old EXIT;
funding USD observation имеет собственный clock. Peg=1 не предполагается.

D1–D4 приняты прямым owner EXECUTE. Канонические изменения находятся в existing
[handoff](../../contracts/science_to_strategy_handoff_v1.md),
[decisions](../../contracts/episode_decision_continuity_v1.md),
[policy](../../contracts/trading_runtime_policy_v1.md),
[economics](../../contracts/risk_and_economics_v1.md) и
[lifecycle](../../contracts/owner_lifecycle_projection_spine_v1.md).
Original attached MD byte-for-byte находится в source-contract.md; его SHA
закреплён exact task contract. Science не переписана этим software атомом.

## Основания изменений

| Класс | До / изменение | Независимая проверка |
|---|---|---|
| ALREADY_PROVEN | #396 durable DENIED/cancellation, genuine exception rollback, decimal accounting | Existing continuity A–D и v1.0 payload/hash guards сохранены |
| REPRODUCED на base | Native CLI `run` отсутствовал, exit2 до runtime/effect | native-before.json; actual ordinary subprocess open/exit |
| NEW_CAPABILITY | Distinct accepted A@V1→B@V1, shared outstanding envelope, partial EXIT | Positive native successor; exact remaining quantity/fees |
| IMPLEMENTATION_COUNTEREXAMPLE | Reset cursor пропускал 8 из 14 timely mints | Append/rescan watermarks; native 14-day exact set14/14 |
| REVIEW_NATIVE_COUNTEREXAMPLE | Pre-admission restore повторял effect; post-backup switch терял binding | Pre-effect origin closure, complete cut bindings/generation |
| REVIEW_NATIVE_COUNTEREXAMPLE | Restore отменял STOP и сбрасывал grant quota | Restrictive controls, original consumed claims/pending attempts |
| REVIEW_NATIVE_COUNTEREXAMPLE | Writer wait/cached clock разрешал stale send | Clock после acquired transaction и перед HTTP |
| REVIEW_NATIVE_COUNTEREXAMPLE | Raw rounddown считался full ENTRY | Exact paid notional/quantity PARTIAL, fee embedded once |
| REVIEW_NATIVE_COUNTEREXAMPLE | Corrupt A starved B EXIT; NaN ломал economics | Per-obligation isolation, typed UNKNOWN/known realised legs |
| REVIEW_NATIVE_COUNTEREXAMPLE | Missing/corrupt current B profile/binding starved old A EXIT | Old obligations first; B entries disabled; cold status keeps typed gap |
| REVIEW_NATIVE_COUNTEREXAMPLE | Later cut clock заменял pending result; export пропускал known result | Original pending clock, omission/conflict denial |
| REVIEW_NATIVE_COUNTEREXAMPLE | Latest UNKNOWN total стирал known $0.25 при restore | All original accepted observations/IDs/clocks replayed through accounting owner |
| EXACT_REVIEW_COUNTEREXAMPLE | READY при missing/corrupt envelope или missing/stale/future/corrupt SHADOW funding | Current readonly readiness требует VALID envelope и свежие проверенные execution inputs |
| EXACT_REVIEW_COUNTEREXAMPLE | SQL скрывал естественные CANCELLED/RECONCILED с потерянным FINAL/result | Indexed terminal witness validation; повреждение сохраняет UNKNOWN и запрет admission |
| REMEDIATION_COUNTEREXAMPLE | Отмена до попытки удерживала лимит; противоречивый sold/remnant освобождал его | Natural unattempted cancel освобождается; result количества сверяются с original attempt |
| OWNER_UX_COUNTEREXAMPLE | CLI check принимал missing/invalid D2 envelope limits | Shared owner validation до activation, пять native readonly cases |
| OWNER_UX_COUNTEREXAMPLE | После reconcile action ещё предлагал reconcile при верной ACK-команде | Readback использует один phase predicate для action/command; native restore и cold CLI повторены |
| REVIEW_LEGACY_COUNTEREXAMPLE | Legacy recipe/provenance менялись; saved baseline packet конфликтовал, native reservation count 1→2 | Operational поля только при явном runtime_execution; absent/null сохраняют прежний packet, одну позицию и неизменённый journal |
| REVIEW_CURRENT_AUTHORITY_COUNTEREXAMPLE | Restore терял post-backup tightening $30→$10 и снова разрешал запрещённый вход | Full original envelope/runtime-policy chains и committed heads; missing/conflicting configuration сохраняет fence, later local extension не откатывается |
| REVIEW_ACTIVE_DIAGNOSIS_COUNTEREXAMPLE | Missing funding ошибочно помечал integrity; после успешного EXIT cold status оставался ACTION_REQUIRED | Отдельный EXIT-input cause закрывается после проверенного восстановления; audit history и unresolved/corrupt neighbors сохранены |
| REVIEW_CURRENT_POLICY_COUNTEREXAMPLE | Existing policy owner возвращал RUNTIME_POLICY_INVALID, cold native/CLI status — READY/VALID/NONE | Same snapshot/shared current-policy validator; typed policy status/revision/SHA/action, optional strategy-only отсутствие сохранено, original inventory/EXIT независимы |
| REVIEW_CURRENT_CLOCK_COUNTEREXAMPLE | OBSERVED status/check с --as-of или clock-file считали старый fixture clock текущим и показывали READY | Physical-clock boundary на current health/input checks; synthetic virtual time и original activation/cut metadata сохранены |
| REVIEW_PARTIAL_DISPATCH_COUNTEREXAMPLE | Partial remainder 6M→9M давал UNKNOWN, но следующий EXIT принимал повреждённый остаток и показывал READY с 5M/$15 вместо 2M/$6 | Original indexed cumulative quantity/cost/fee proof до inputs, transactional claim и result acceptance; повреждённая позиция удерживается, здоровые old EXIT продолжаются |
| REVIEW_ENTRY_NONFILL_COUNTEREXAMPLE | Valid ENTRY1.1 NO_ROUTE освобождал reservation, но два ticks/cold status сохраняли permanent EXIT_INVENTORY_WITNESS_CONFLICT | Original definitive nonfill/release proof до закрытия incident; positive/UNKNOWN/EXIT quantity guards сохраняются |
| REVIEW_GRANTED_SHADOW_SUCCESSOR_COUNTEREXAMPLE | Single B grant создавал A EXIT attempt и расходовал B quota до scope rejection; оба A/B grants доступны | Один ordinary caller выбирает отдельно разрешённый grant по origin epoch/strategy до attempt/quota; A-oldEXIT/B-newENTRY используют собственные profiles/caps |
| REVIEW_BACKUP_ARTIFACT_COUNTEREXAMPLE | Native backup менял чужие bytes через hardlinked .json/-shm; SQLite также удалял existing -journal/-wal aliases | Все пять final artifacts проверяются до записи; exclusive reservations, private SQLite staging, standalone copy и cleanup только собственных identities |
| REVIEW_ORIGINAL_JSON_COUNTEREXAMPLE | Scalar/null/list original origin или capture ломал tick/status и оставлял healthy due EXIT открытым | Typed shape validation и quarantine исходного обязательства; damaged bytes/pending UNKNOWN сохранены, healthy old EXIT закрывается без resend |
| REVIEW_RESTORE_ARTIFACT_COUNTEREXAMPLE | Restore возвращал успех и удалял existing -journal/-wal/-shm | Полная destination family проверяется до записи; exclusive publication из private native staging, cleanup только собственного reserved DB |
| RESTORE_SOURCE_SEAL_COUNTEREXAMPLE | При unchanged sealed main SHA unsigned source WAL менял envelope $30→$90 | Standalone source family и private hash-verified input; source artifacts сохранены, текущие runtime reads остаются WAL-aware |
| INTERIM_REPEAT_RESTORE_COUNTEREXAMPLE | Второй genuine restore после первого ACK падал на duplicate RESTORE-SNAPSHOT | Append-only snapshot identity и current-snapshot reconciliation/ACK; два цикла с одинаковыми inventory/clock, prior cut DENY, due original EXIT RECONCILED |
| DELIVERY_PIN_COUNTEREXAMPLE | Необязательное изменение domain-policy prose нарушало исторический TASK30 SHA | Policy/TASK30 сохранены буквально; этот task pin registry-011 остаётся explicit, gate exceptions не добавлены |

Baseline failures для новых capabilities не выдуманы. Reviewer before traces
относятся к changing implementation bytes; они не приписываются base #396.
Окончательное причинное доказательство дают native regression after traces.
История промежуточных неуспешных прогонов сохранена отдельно от final receipt.
Legacy regression исполняет exact Git blob baseline producer и сохраняет его
packet через current native source/store owners. Это проверка прежнего packet
и upgrade replay; весь старый binary/store version этим тестом не исполняется.
У компактных historical interim receipts прежний receipt SHA сохранён только
как original run reference; selfhash текущего компактного документа не заявлен.

## C01–C24

Native automated status: PASS, 176 tests, 628.937259s; source bytes до/после
совпадают с текущим кандидатом, owned roots ABSENT. Exact test IDs, durations,
source pins и root absence — [executed receipt](../../evidence/smial_trading_core_operational_closure_v1/executed-tests.json).
Final runtime proof повторён полностью после material review repairs. Ранние
EOF/canary equivalence и 116-test receipts сохранены как superseded history;
они не подменяют текущий native proof.

Дополнительно: [99 direct consumers](../../evidence/smial_trading_core_operational_closure_v1/direct-consumer-proof.json),
[independent cold operator](../../evidence/smial_trading_core_operational_closure_v1/operator-proof.json),
[clock boundary/jumps](../../evidence/smial_trading_core_operational_closure_v1/clock-proof.json).
Строгие locators для каждой строки, без усреднения verdicts, закреплены в
[coverage.json](../../evidence/smial_trading_core_operational_closure_v1/coverage.json).
Driver: test_trading_core_operational_closure_v1; recovery:
test_trading_operational_recovery_v1; engines: continuity/obligations/adapters.

| ID | Native путь / прямой oracle |
|---|---|
| C01 | Valid neighbor + handoff negative guards; invalid B сохраняет A без candidate activation |
| C02 | Actual run process сам открывает/закрывает; fresh observer видит2 attempts/results без ручных trade stages |
| C03 | Mixed/list-only shared owners; missing/late price, deadline−ε/deadline/stale; future point не лечит историю |
| C04 | Equal clocks, late insert, pagination/restart/publication; exact source/mint sets и 14/14 timely stream |
| C05 | #396 A–D durable refusal/cancellation vs native/typed/unexpected rollback; actual process loss |
| C06 | Fresh invocation без новой epoch; stable IDs, exact replay; native frozen-base legacy packet повторяется без новой позиции/journal |
| C07 | Positive different-science A/B с открытой A; invalid B сохраняет A; concurrent SQLite CAS один winner |
| C08 | A остаётся в mode envelope после switch; B без auto-shrink; UNKNOWN frees nothing; separate modes |
| C09 | Pause между reservation/send; real writer wait TTL; STOP/DRAIN restore dominance; old EXIT/reconcile |
| C10 | Cold loader без spec/strategy/ResearchStore; retained origin/time exit; unrelated history bounded |
| C11 | Failed→UNKNOWN same-ID→partial 4m/2m remainder; overfill/conflict deny; exact quantity/fee conservation |
| C12 | 400 definitive nonfill vs timeout UNKNOWN; old obligation retained; UNKNOWN no resend |
| C13 | Body/clock/hash/capture corruption и malformed original JSON typed before consume; preserved origin/result and rollback |
| C14 | Real parser/lowest fake wire; raw units/mint/amount/schema/router/null transaction guards; quote fee once |
| C15 | Actual OS process lock/kill + independent controls; corrupt/malformed A не starves healthy B due EXIT |
| C16 | Independent status alive/fresh/moving/integrity/exits; no false READY; recovered input cause inactive, audit retained; unresolved neighbors stay active |
| C17 | WAL-aware current snapshot; DB/WAL fingerprints unchanged by GET; missing/corrupt state typed |
| C18 | Guarded standalone native backup+fresh root/process; no existing artifact overwrite; external ledger не откатывается; complete admission/exit/switch/pending/quota/current configuration cut, no authority rollback |
| C19 | Actual research/spec/raw removal; frozen minimal closure/retained metadata; legacy no fabrication/forward recovery |
| C20 | Literal full $2.87/$2.85, partial $1.07/$1.06; embedded quote fee separate; UNKNOWN/floor/no combined money |
| C21 | Native producer 14 virtual days; 0/1000/4000 history; measured tick/RSS/disk;14 identities/28 attempts |
| C22 | Independent cold agent: documented CLI check/start/control/export-cut/restore/ACK/resume/EXIT/readback |
| C23 | Actual loopback egress hits0, secret sentinel not read/stored, non-target SHA unchanged, roots ABSENT |
| C24 | D1 historical mapping; separate software/science/runtime/delivery/financial and explicit live ledger |

C22: 22 ordinary CLI stages + 1 drain control + 1 readonly limit diagnostic. Независимый оператор
прошёл cold PAPER CLI до RECONCILED:2 original
attempts/results, exact inventory SHA, pause preserved after ACK. Он не
составлял bindings/per-token outcomes вручную. SHADOW missing/stale funding
preflight даёт typed refusal и русский next step. Это synthetic software
proof, не production smoke либо научный PROMOTE. Semantic route/card сверяется
после final generated sync; его отдельный observable verdict — operator-proof.

## Исторический аудит, residuals и LIVE

Owner-authorized `SMIAL_PR398_OPERATING_BOUNDARY_PATCH_V1` закрывает два P1
в существующем #398. Attached review содержит source-flow hypotheses;
native BEFORE/AFTER исполнены отдельно и имеют собственные source pins.

| Finding | Native BEFORE | Existing owner / AFTER |
|---|---|---|
| F-A: caller-controlled operating scope | Один и тот же B ENTER: ordinary отказал при A=$30/cap=$30; default/False public path создал B и разрешил attempt, raw liabilities=$60. Genuine restored EXIT также разрешил fresh attempt до ACK | PaperPlane derives managed scope from durable state/profile/switch; shared admission/attempt and runner use retained activation/binding guard. B reservation отсутствует, raw liabilities=$30; restored fresh ENTRY/EXIT запрещены без request/quota delta. Original replay/result/cut/ACK и genuine legacy сохранены |
| F-B: локальный entry failure прекращал continuous run | Реальный missing/expired B grant checker прерывал run до следующего тика; malformed source JSON и retained request array прерывали healthy old EXIT service | Coordinator isolates expected entry/source/position failures by stage. Same run/PID/3 ticks закрывает A original EXIT, B preclaim имеет0attempt/0quota. Postclaim B сохраняет1original pending attempt/request/quota; original callback reconciles без resend. Shared-store failure остаётся fatal/atomic |

Measured evidence: [managed boundary](../../evidence/smial_trading_core_operational_closure_v1/review-operating-boundary-remediation.json),
[continuous failure isolation](../../evidence/smial_trading_core_operational_closure_v1/review-source-shape-isolation-remediation.json),
[coherent inventory](../../evidence/smial_trading_core_operational_closure_v1/review-coherent-inventory-remediation.json).
Frozen9ee three actual NOT_READY reviews остаются historical; missing OWNER
review не выдуман. Intermediate guard также пропускал direct attempt при
удалённом original activation event: actual before/after сохранены, common
lineage owner исправлен. Прерванный whole run не PASS. C23 отдельно сохранил
FAIL старого exit-code oracle; новый scoped blocker меняет ожидаемый результат
run, а egress0/secret/non-target invariants остаются строгими.
Следующий whole snapshot выполнил172 tests и сохранил10 FAIL subcases в4
existing recovery methods: все ожидали exception вместо требуемого scoped
entry blocker. Этот FAIL сохранён LF carrier с неизменными JSON values/native selfhash;
original capture raw SHA отмечен отдельно. Consumer oracles
уточняются с независимыми raw reasons и прежними zero-effect/pending guards.
После PATCH source/test bytes заморожены для общего proof и новых четырёх
изолированных P0/P1 reviews. Рабочая authority этим PATCH не расширена.

Frozen7b56 native CODE/GOAL probes затем выявили два P1 в тех же границах:
массив вместо B asset map завершал run до будущего A EXIT; valid policy с
new_entries_enabled=false запрещала admission, но tick/status показывали
entries_enabled=true и READY. [Actual before и review history](../../evidence/smial_trading_core_operational_closure_v1/review-7b56df88.json)
сохраняют исходные pins и UNKNOWN отсутствующих измерений. Исторический PASS
172/99/2/24+NAV2 не доказывает закрытие этих находок. Ремонт ограничен проверкой
существующего asset input и проекцией действующего policy permission; старые
EXIT, исходные pending/result, legacy и fatal store не меняют смысла.
ARCH был прерван до verdict, OWNER на blocked inventory не запускался;
финальные четыре роли проверяют новые bytes независимо.

[Исходный S08/S13 report](../smial_trading_continuity_v1/REPORT.md) сохраняет
REPAIR_PARTIAL_BLOCKED своего scope. Negative same-ID V2 не стал positive.
D1 явно заменил текущий operational successor критерий на разные accepted
V1 identities; новый A/B native proof проверяет именно этот outcome.

| Класс | Остаток |
|---|---|
| SOFTWARE_GAP/EVIDENCE_GAP | Known critical gaps: 0 after native repairs/proof. Required-review verdict, exact inventory и delivery остаются отдельным обязательным gate |
| CONFIG_REQUIRED | Real eligible strategy, scope/runtime/source, explicit model/envelope/TTL/limits, timely funding producer/cadence |
| EXTERNAL_UNVERIFIED | Real quote latency/schema/route/quota/credentials, target-host supervision, independent ledger custody; separate owner operation |
| NOT_CONFIGURED | Scientific monitor/degrade thresholds; software health не experiment policy |
| OUT_OF_SCOPE | Same-ID V2/new DSL/network; signer/chain execution/wallet reconciliation/money |

| Live component | Code-backed факт |
|---|---|
| Intent/origin | IMPLEMENTED только PAPER/SHADOW: exact decision/activation/spec/reservation/attempt |
| Financial authorization | NOT_IMPLEMENTED ordinary path; mode guard, grant financial_authority=false |
| Quote/build | Quote-only production parser/GET IMPLEMENTED; real route EXTERNAL_UNVERIFIED; build NOT_IMPLEMENTED, non-null transaction denied |
| Signer | NOT_IMPLEMENTED; credential не signer material |
| Chain send/retry/finality | NOT_IMPLEMENTED; single quote GET не sendTransaction/confirmation |
| Wallet/token deltas | NOT_IMPLEMENTED; modeled result не balance proof |
| Fees/rent | Explicit modeled/embedded fees и known-or-UNKNOWN costs; actual fee/rent UNVERIFIED |
| Chain inventory reconciliation | NOT_IMPLEMENTED; model obligation ledger не wallet inventory |

LIVE_NOT_READY; NetReturn NOT_ESTABLISHED; owner FCF NOT_AVAILABLE; alpha и
real strategy promotion не установлены. Там, где NOT_IMPLEMENTED, future money
требует отдельной разработки/authority, а не одной проверки в бою.

## Resources, rollback, delivery

Первый exact-head CI `d8ee540f` остановился на C21: первый source admission
отсутствовал. Native reproduction при 32 GiB подтвердил `DRAIN_RESERVE_PRESSURE`
до любого nomination call: консервативный резерв четырнадцатидневного fixture
требует 142188216320 bytes. Свободное место самого CI не было записано — UNKNOWN.
Положительный synthetic сценарий теперь явно моделирует physical capacity
1 TiB; отдельный negative проверяет native stop при 32 GiB и ноль calls.
Production guard и рабочие настройки не изменены. Actual failed CI, native
before/after и прежний scoped review PASS сохранены в
[capacity remediation](../../evidence/smial_trading_core_operational_closure_v1/ci-source-capacity-remediation.json).
Тот же CI выявил semantic overview 16404 bytes при лимите 16384. Сжат только
purpose lifecycle-маршрута: IDs, вопросы, ссылки и authority сохранены; новый
размер 16349 bytes, прямой semantic consumer module — 15 PASS.

Peak suite process RSS: 147210240 bytes (140.39 MiB). Native 14-day producer
дал exact14 identities/28 attempts; источник+runtime занимали 10031615 bytes,
entry tick 0.1966–0.2683s. Synthetic modeled aggregate $36.91 — literal oracle
этого fixture, без profitability/alpha extrapolation.

| Retained history events | DB bytes | Measured tick range, s |
|---|---:|---:|
| 0 | 204800 | 0.04646–0.05003 |
| 1000 | 364544 | 0.04610–0.05042 |
| 4000 | 843776 | 0.04525–0.05009 |

Append-only journal slope:159.744 bytes/event; coalesced incident rows:1.
Terminal release проверяется по original attempt/FINAL/result на текущем snapshot.

| Native readback scope | SQLite steps | Elapsed, s |
|---|---:|---:|
| 1 outstanding | 980 | 0.000515 |
| 100 proved terminal | 78430 | 0.015224 |
| 1000 proved terminal | 774540 | 0.153898 |
| 1000 terminal + 12000 unrelated events | 774560 | 0.152157 |

Native history preparation: 13.445s.
SQL работа растёт линейно с числом terminal positions; O(outstanding) не заявлен.
Индекс ограничивает чтение соответствующими событиями, посторонний journal
не перечитывается целиком. Кэш release и новая competing truth schema не созданы.

Это bounded synthetic measurements на данном процессе, не обещание любых
объёмов/host throughput. Process kill проверен; power-loss/hardware tolerance
не заявляется. Heartbeat health ограничен явным progress TTL.
Каждый fixture имеет собственную Git producer identity; compact regeneration
заменяет тяжёлые datasets. Все proof-owned roots удалены; loopback egress hits0,
secret sentinel не прочитан/сохранён, non-target SHA unchanged.
[Cleanup receipt](../../evidence/smial_trading_core_operational_closure_v1/cleanup.json)
связывает измерения и invariants. Shared cache/.venv, рабочие данные/чужие roots,
branches и immutable provider registry не были cleanup targets.

Rollback accepted history запрещён. Ordinary1.1 store требует compatible
binary: pause entries, drain/reconcile retained obligations, native backup/
cut/export/fresh restore. Старый binary не заявлен совместимым с partial
semantics; DB ради green не удаляют. Missing closure/cut сохраняет fence.

Delivery sequence: final generated sync →4 isolated exact-inventory roles →
binding/preflight → normal task push/one PR → exact-head CI → readiness.
Только затем отдельная machine-rendered owner phrase и guarded merge/post-merge.
Актуальные verdicts/pins находятся в completion/independent-review/factory-fit;
этот отчёт не объявляет delivery выполненной до этих readbacks.
Рабочий runtime/provider/deploy здесь не запускались.
