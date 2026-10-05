# OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1

VERDICT: PARTIAL_WITH_EXACT_GATE. R1–R4 locally pass through production owners
with synthetic physical inputs; live commissioning is NOT_RUN. Frozen base:
`576e8c54715bb8af6b84877b91678ae659a42f88`. Exact delivered bytes are the harness
implementation bindings, not a pre-commit working-tree name. Task:
`docs/tasks/OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1.md`.

До ремонта ordinary tick искал identity через payload всей истории. Теперь
ResearchStore может явно подготовить derived identity pointers на копии. Этот
артефакт живёт между oneshot процессами; authoritative manifests/Parquet и
научные readers остаются прежними. Exact replay проверяет involved canonical
transaction; corrupt/stale/missing prepared state явно отказывает. Full audit
произвольной исторической порчи отделён от bounded append. Contract:
`docs/contracts/research_write_lookup_v1.md`.

## R1: реальный tick, история и холодный процесс

Замеры вызывают `scripts/observation_schedule.py tick --once` с полным
TickPhysicalOverrides. HTTP/clock синтетические; publisher, append, lease,
lifecycle и файловые чтения настоящие. Запрещены network и secret access.
Instrumentation вызывает original operations. Setup и явная preparation
измерены отдельно; каждый tick/restart/status запускается новым процессом.

Frozen-base normal tick при 0/32/128 валидных retired transactions открывает
30/190/670 canonical partitions, читает 321,552/1,854,142/6,452,202 canonical
bytes, wall 0.662/0.815/1.825s. Это найденный линейный seam, а не private helper
benchmark. Same-work repaired proof и полные stages сохранены в
`operability_proof_summary_v1.json`.

История финального aged proof: canonical one-record ResearchEvent transactions
с разнообразным high-entropy payload, retired schedule identities и настоящими
serializer/hash/schema/inventory checks. Это валидная нерелевантная research
history; это не утверждение о полном native producer corpus за 30 дней.
Model cadence: 288 publication slots/day × 3 ResearchStore transactions =
864/6048/25920/51840 transactions для 1/7/30/60-day equivalents.

| Equivalent days | Transactions | Final cold normal wall | RSS bytes | Canonical opens / bytes | Full inventory |
|---|---:|---:|---:|---:|---:|
| 1 | 864 | 0.632s | 91,766,784 | 7 / 81,460 | 0 |
| 7 | 6048 | 0.664s | 91,848,704 | 7 / 81,460 | 0 |
| 30 | 25920 | 0.630s | 91,926,528 | 7 / 81,460 | 0 |
| 60 | 51840 | 0.717s | 92,024,832 | 7 / 81,460 | 0 |

Каждый normal tick публикует один batch. При doubles history растёт bounded trie
route work (path bytes 482,546→487,852), а не payload scan. Final fresh restart:
один canonical partition, 8,142 bytes, no provider attempt; status: zero
canonical payload reads. После critic repairs повторены 12 fresh-process
normal/restart/status runs на тех же aged roots, с новым normal work. Ceiling был frozen до final proof: tick wall<30s,
RSS<512MiB, fixed-work opens≤7, full inventory=0. Это local Windows limits.
Linux oneshot, filesystem stamp semantics и power-loss durability UNVERIFIED.

Явная bulk preparation O(history), без surprise на первом tick. 60-day setup
занял 1103.33s, preparation 377.85s; combined process high-water upper bound
335,155,200 bytes. Отдельная CLI preparation на 30-day synthetic copy: 394.726s,
process peak186,085,376 bytes, 25,929 canonical records. Эта операция не встроена
в tick/deploy. Не экстраполировать этот результат как HOST_PASS.

## R2: границы времени, budget, pressure и drain

Один production-entry mixed scenario пересекает UTC day и Monday cycle:
known legacy debit/pacing, normal admission, completed call recovery,
ambiguous STARTED без resend, 429, TimeoutError, late response, missing value,
daily/account budget exhausted, повтор fresh tick и early stop-intake.
Большой budget debit специально seeded fixture; это не реальные HTTP calls.
Known legacy debit также seeded через существующий accounting owner; реальный
legacy producer call этим mixed fixture не исполняется.
Round/admission quota guards дополнительно покрыты direct producer regressions.
Restart не сбрасывает aggregate budget, cycle не readmits активный mint,
прошлые slots не backfill. Перед actual transport резервируется request day;
при UTC rollover старый debit сохраняется, новый день проверяется/резервируется.
Консервативные reservations могут превышать число actual HTTP attempts.

Pressure через физическую disk boundary закрывает intake штатным DRAINING до
новой nomination. Admitted obligations не удаляются; tail завершён COMPLETE,
unpublished=0. DRAINING pause/resume отказываются. Reserve 6 copies +256MiB —
MODEL proxy, не проверка полного Factory footprint или backup volume.

Episode status/operational packet разделяет intake, last CLOSED frame, admitted/
open/terminal slots, attempted/provider failures/value missing/no-request,
publication backlog/age, last publication и cohort maturity. Исторические
rows без execution metadata дают UNKNOWN_LEGACY_METADATA. Legacy source_poll
age отсутствует для episode; coverage=NOT_APPLICABLE_EPISODE_NOMINATION.
PROCESS_OK не является provider/data PASS. Account/drain значения без binding
остаются UNKNOWN с причиной. Timers, snapshot writer и notification receivers
этим PR не активируются.

## R3: workstation OFF, новый capture и обычный consumer

Producer создал 25 admissions /24 mints /3 UTC cohorts, 3450 due slots:
OBSERVED923, CENSORED2516, DISAPPEARED11. Sparse/gap vertical fixture проверяет
lifecycle; он не используется как нормальный footprint. 121 production ticks,
sum tick wall59.14s, producer peak120,999,936 bytes; consumer peak496,422,912.

Workstation условно OFF до maturation. Public capture/freeze/transfer/build/
seal/import догнал history без backfill. Torn import до lineage commit был
fail-closed; новый capture invocation с новым as-of сохранил frozen closure и
transfer identity, затем ordinary retry завершил оставшиеся cohorts. Actual
population card25 создаёт consumer; mixed temporal price/liquidity/holders/time
question получает native packet/mask/eligibility от production owners.
Ordinary synthetic lifecycle и literal numerical oracle проходят. Exact repeat:
values_loaded=false, scientific look delta main0/adaptive0.

Два real producer activations одного UTC admission day отказываются
`EPISODE_COHORT_FRAGMENTED_UNSUPPORTED` до partial capture и через direct closure
owner. Malformed frozen closure отказывает typed, evidence bytes сохраняются.
Nonempty synthetic protection inventory с frozen pins проходит export/import/
cold restore; substitution/missing/corruption явно отказываются. Actual
completeness из этого не следует.

## R4: непустой existing-owner backup и detached restore

Existing `remote_ops.package_backup` без pruning упаковал producer + workstation
с schedule/raw/protection dependencies; `restore_backup_isolated` восстановил
новый root. Final bundle24,739,594 bytes, SHA256
`ccc2ec8dd8ee6dbd4256296df46e89fa7e5ca7b15e5ac900768bdb7a0dad68b9`.
Original roots и provider network заблокированы для cold phase.
Три releases verify; saved public read не меняет history; numerical replay
совпадает с oracle. Exact duplicate import=PASS_ALREADY_PRESENT_EXACT и history
unchanged. Corrupt/missing dependency: RELEASE_HASH_MISMATCH /
RELEASE_DEPENDENCY_MISSING. Legacy corpus readable. Eviction не включается.

Actual frozen-base writer также append/read подтверждён отдельной rollback
репетицией. Старый writer игнорирует index, новый после old append отказывает
WRITE_LOOKUP_STALE_PREPARATION_REQUIRED; явная reprepare возвращает readiness.
Откат кода не отменяет calls, admissions/T0, debits, pins или research history.

## FACT / MODEL / UNKNOWN и следующий gate

FACT: cold work/bytes/RSS, canonical validation, локальные R1–R4, rollback,
211 focused tests PASS (2 platform symlink skips), дополнительный exhausted-STARTED
regression и один повторный полный vertical test PASS.
MODEL: 1/7/30/60-day equivalents, 139 observation rows/admission, 24/day canary,
per-route/account envelope, all-copy 30/97d forecasts и drain reserve.
UNKNOWN: actual payload distribution, Linux acceptance, whole Factory reserve,
actual protection completeness, approved shared-account envelope/other consumers
и accepted receipt exact category5m routes. Current VPS facts/receipts/full logs
и commissioning packet сохраняются вне Git.

Dense physical sensitivity: varying price/liquidity/holder and high-entropy rich
vendor payload at4KiB/64KiB/near8MiB frozen cap; отдельный gap run. Measured units
в summary включают ops/WAL/raw/witness/publications/research/manifests. Packet
отдельно моделирует export/staging, backup peak, mirror/corpus и restore scratch
для canary48 и normal100/day на30/97d. Near-cap sensitivity не даёт общего
Factory ≤40GiB TARGET /≤50GiB HARD PASS. Это scope policy, не filesystem size;
actual free space, current Factory footprint и независимые volumes различаются.
Normal population/caps не меняются ради PASS.

Сначала merge boundary: exact-head CI и machine merge-readiness. Queue или
degradation =PENDING_INFRA; не code failure и не PASS. Merge в этом атоме
запрещён. Позднее нужен отдельный OPERATE grant: exact merged SHA/host,
lane disabled deployment, immutable24/day48h canary+72h tail, свежий calendar
window/expiry, current assignment/account/disk bindings.
Для default tick canary старый legacy intake и drain должны быть COMPLETE,
иначе several ACTIVE/DRAINING scopes требуют explicit selection.
Минимально недостаёт 3 one-shot category5m receipts через existing approved credential; no retries/
fallback/new secrets/provider comparison. Real science и destructive eviction
остаются отдельной authority.

Reproduction: `scripts/prove_opportunity_episode_operability.py` (fresh subprocess
per phase), `scripts/prove_opportunity_episode_rehearsals.py`,
`tests/test_opportunity_episodes_operability_v1.py`,
`tests/test_opportunity_episodes_vertical_v1.py` with `OEP_VERTICAL_WORK` absolute
new root. Full local proof roots and hashes are referenced by summary. New
roots preserve failed evidence; scripts refuse an already-present proof root.

Post-review regression: 21 focused direct-consumer tests PASS, включая реальную
сборку operational packet и запись storage history. Mixed legacy/new terminal
metadata сохраняет null общего missing-count; известная часть не выдаётся за
полный ноль. Linux fsync claim ограничен lookup files и immediate parent,
canonical/ancestor directory power-loss durability остаётся UNVERIFIED.

Accounting boundary replan: существующий owner теперь проверяет gate и
списывает один captured request-day timestamp после credential work. Два
exhausted-new-day regressions (до reservation и после STARTED) запрещают
transport; старый неизвестный debit не возвращается. Lookup decoder/reuse
имеют bounded byte read и общий typed error boundary для deep JSON и IO.
На этой версии: 211 focused tests (2 Windows symlink skips), один дополнительный
exhausted-STARTED test и повтор полного R3–R4 vertical PASS. Новые 12 cold runs
считают bounded lookup reads вместе с canonical/Path operations.

Final public adapter: existence/init/stamp входят целиком в ResearchStore
error conversion. Public lookup и preparation CLI возвращают canonical typed
refusal; frozen closure deep JSON также отказывает typed и сохраняет bytes.
63 owner tests (1 symlink skip) и 27 lookup/capture tests PASS после этого
узкого error-path repair. Последний полный R2–R4 предшествует только этому
исправлению обработки ошибок; успешные операции и научные bytes не менялись.
Финальный cold phase — 50m search (1 synthetic attempt), предыдущий 45m
nomination+search phase (4 attempts) также сохранён; оба дают один batch,
3 appends и 7 canonical partitions. Paired before/after 0/32/128 неизменён.

Final owner boundary: pending recovery converts canonical source IO denial;
frozen capture converts invalid self-hashed timestamp without replacing bytes.
Unverified schedule scope stays UNKNOWN. 66 owner tests (1 Windows symlink
skip) and 29 lookup/capture tests PASS; groups overlap and are not summed.
12 fresh processes repeated normal/restart/status on final sources at 55m:
7 canonical partitions / 81,460 bytes, full inventory 0. Prior 45m/50m
phases remain evidence; successful producer/scientific paths are unchanged.
Frozen-unreadable recovery NEXT preserves bytes and requires exact verified
backup on an isolated copy; maturity wait or regenerated closure is not repair.
