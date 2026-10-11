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

Baseline failures для новых capabilities не выдуманы. Reviewer before traces
относятся к changing implementation bytes; они не приписываются base #396.
Окончательное причинное доказательство дают native regression after traces.
История промежуточных неуспешных прогонов сохранена отдельно от final receipt.

## C01–C24

Native automated status: PASS, 116 tests, 381.488962s; source bytes до/после
совпадают, owned roots ABSENT. Exact test IDs, durations, source pins и root
absence — [executed receipt](../../evidence/smial_trading_core_operational_closure_v1/executed-tests.json).
После proof staged-diff hook потребовал убрать один лишний LF в EOF
coordinator. [EOF equivalence](../../evidence/smial_trading_core_operational_closure_v1/eof-normalization-proof.json)
связывает original tested hash и final hash: AST со всеми location attributes
и compiled code object совпадают byte-for-byte. Исходные test pins сохранены;
runtime rerun ради этого пробела не объявлен. Exact-head CI остаётся обязательным.
Secret scan затем выявил локальную переменную synthetic sentinel с именем
secret. Она переименована в canary (три references внутри одного C23);
[актуальный C23 повторён: PASS](../../evidence/smial_trading_core_operational_closure_v1/canary-rename-proof.json).
Остальные source bytes тестового файла совпадают; secret scan PASS без обхода hook.

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
| C06 | Fresh invocation без новой epoch; stable IDs, exact replay, conflict без content overwrite |
| C07 | Positive different-science A/B с открытой A; invalid B сохраняет A; concurrent SQLite CAS один winner |
| C08 | A остаётся в mode envelope после switch; B без auto-shrink; UNKNOWN frees nothing; separate modes |
| C09 | Pause между reservation/send; real writer wait TTL; STOP/DRAIN restore dominance; old EXIT/reconcile |
| C10 | Cold loader без spec/strategy/ResearchStore; retained origin/time exit; unrelated history bounded |
| C11 | Failed→UNKNOWN same-ID→partial 4m/2m remainder; overfill/conflict deny; exact quantity/fee conservation |
| C12 | 400 definitive nonfill vs timeout UNKNOWN; old obligation retained; UNKNOWN no resend |
| C13 | Body/clock/hash/capture corruption detected before consume; preserved origin/result and rollback |
| C14 | Real parser/lowest fake wire; raw units/mint/amount/schema/router/null transaction guards; quote fee once |
| C15 | Actual OS process lock/kill + independent controls; corrupt A не starves healthy B due EXIT |
| C16 | Independent status alive/fresh/moving/integrity/exits; no false READY; incidents coalesced |
| C17 | WAL-aware current snapshot; DB/WAL fingerprints unchanged by GET; missing/corrupt state typed |
| C18 | Native backup+fresh root/process; external ledger не откатывается; admission/exit/switch/pending/quota cut |
| C19 | Actual research/spec/raw removal; frozen minimal closure/retained metadata; legacy no fabrication/forward recovery |
| C20 | Literal full $2.87/$2.85, partial $1.07/$1.06; embedded quote fee separate; UNKNOWN/floor/no combined money |
| C21 | Native producer 14 virtual days; 0/1000/4000 history; measured tick/RSS/disk;14 identities/28 attempts |
| C22 | Independent cold agent: documented CLI check/start/control/export-cut/restore/ACK/resume/EXIT/readback |
| C23 | Actual loopback egress hits0, secret sentinel not read/stored, non-target SHA unchanged, roots ABSENT |
| C24 | D1 historical mapping; separate software/science/runtime/delivery/financial and explicit live ledger |

C22 независимый оператор уже прошёл cold PAPER CLI до RECONCILED:2 original
attempts/results, exact inventory SHA, pause preserved after ACK. Он не
составлял bindings/per-token outcomes вручную. SHADOW missing/stale funding
preflight даёт typed refusal и русский next step. Это synthetic software
proof, не production smoke либо научный PROMOTE. Semantic route/card сверяется
после final generated sync; его отдельный observable verdict — operator-proof.

## Исторический аудит, residuals и LIVE

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

Peak suite process RSS: 123162624 bytes (117.46 MiB). Native 14-day producer
дал exact14 identities/28 attempts; источник+runtime занимали 10031615 bytes,
entry tick 0.1924–0.2887s. Synthetic modeled aggregate $36.91 — literal oracle
этого fixture, без profitability/alpha extrapolation.

| Retained history events | DB bytes | Measured tick range, s |
|---|---:|---:|
| 0 | 204800 | 0.04294–0.04847 |
| 1000 | 364544 | 0.04401–0.05123 |
| 4000 | 843776 | 0.04403–0.05023 |

Append-only journal slope:159.744 bytes/event; coalesced incident rows:1.
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
