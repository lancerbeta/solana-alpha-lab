# OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1

VERDICT: PARTIAL_WITH_EXACT_GATE. Local R1–R4 и owner patch PASS; live commissioning
NOT_RUN. Base/current observed main: 576e8c54715bb8af6b84877b91678ae659a42f88.
Owner review PR377 head01f22cb4865ea27677e1ccddc8796a0ad70b4d08:
PATCH_BEFORE_MERGE, P0 none. P1-A/P1-B/P2 закрываются в том же atom.
Exact delivered bytes задают harness bindings. Raw proof receipts вне Git;
их logical refs/hashes и reproduce recipes — в operability_proof_summary_v1.json.
Commissioning packet: local/episodes_operability/commissioning_packet_v1.json;
final head/hash фиксирует local commissioning_packet_receipt_v1.json, без hash cycle.

P1-A: isolated-copy preparation supported; filesystem-bound lookup не переносится
на production. Explicit --production-commissioning готовит canonical root in place
после отдельного OPERATE, verified backup, measured copy rehearsal и quiesced
writers/timer. CLI требует attestation refs и exact existing producer OPS store.
OPERATE-ref validation проверяет формат и допускает literal UNKNOWN; approved
authority и receipts подтверждает оператор отдельно. Structural PASS не выдаёт OPERATE.
OPS write transaction и ResearchStore lease держат оба fences весь audit, включая
фазу за TTL. CLI не выдаёт authority и не проверяет backup самостоятельно.
Deploy/tick/startup не готовят lookup. Ordinary writer использует prepared lookup;
old-writer append и moved/restored root требуют explicit target-root reprepare.
21 lookup tests PASS: copy/canonical modes, concurrent OPS/canonical writer refusal,
fence beyond TTL, bounded append/read, moved-root refusal/reprepare. Реальный
frozen-base writer append/read повторён: stale refusal и explicit reprepare PASS.
Real CLI tick с запрещённым prepare подтверждает отсутствие auto-preparation.
Canonical VPS preparation здесь не выполнялась.

P1-B: remaining/prospective slots ×8MiB×6 +margin больше не runtime kill-switch.
Whole-Factory six-copy forecast — отдельный MODEL/advisory по actual volumes;
UNKNOWN topology блокирует activation до ACTIVE. Runtime использует immutable
EPISODE_PRODUCER_STORAGE_COMMISSIONING_V1: exact root/schedule/activation,
OPERATE/backup/copy/volume/Factory receipt refs и approved producer-local limits.
Reserve и nomination связаны одним current decision instant после pacing.
Граница00:44:59→00:45:01 с3GiB отказывает до HTTP/admission; пустой tail
сразу COMPLETE. Legacy episode-only option получает typed refusal до ACTIVE
и canonical append. Точный16-field JSON template/offline hash recipe проверен.
Partial cutoff00:45:10 при tick00:30:20 на frozen headf5f155cb создавал
1 admission с3 unfunded nomination calls (100,663,296 bytes). Round-start ceil
теперь покрывает последний eligible round; отказ до HTTP/admission. Fresh pacing/
capture clock также запрещает late T0 и ведёт штатный natural drain.
Reserve покрывает все committed assigned-time/chunk calls/due slots, будущие
nominations, каждую prospective next-round obligation и fixed/safety headroom.
Raw/OPS/WAL/publications/research/manifests/lookup входят в per-call bound;
terminal metadata — в per-slot bound. Unsafe/unknown bound LOCAL free space
закрывает intake штатно и сохраняет tail. Missing binding блокирует nominations,
сохраняя lifecycle. Sampling/caps/scientific semantics не снижены.
192 real CLI rounds:24/day×48h, active cap48, decode cap8MiB, synthetic free
78,746,222,592 bytes. 24+24 admissions,6,624 due slots; peak local reserve
29,696,851,968 bytes. Old proxy отказал бы около22 admissions, running canary
сохраняет ACTIVE/LOCAL_HEADROOM. Free1 byte -> DRAINING без новых nominations,
tail COMPLETE/unpublished0. Large all-null late-tail выявил лишний identical-schema
Arrow cast: он устранён; different-schema safe cast и values/schema сохранены.
Это synthetic local envelope, не actual Factory PASS или OPERATE grant.

P2: admitted_episodes/open_episodes/terminal_episodes считают admissions/entities;
slot_states authoritative для due backlog. Tests различают48 episodes/6,624 slots,
direct packet consumer и docs обновлены; legacy execution UNKNOWN сохраняется.

R1: frozen-base real CLI tick, complete HTTP/clock overrides, реальные Store/
publisher/lease/filesystem. При0/32/128 valid distinct retired transactions:
30/190/670 partitions,321,552/1,854,142/6,452,202 canonical bytes.
Current paired fresh-process normal work:7 partitions/81,950 bytes при всех
размерах, inventory0. Дополнительные490 bytes — commissioning metadata binding.
На864/6048/25920/51840 transactions12 fresh normal/restart/status процессов:
fixed90m due tail6 partitions/73,318 bytes, wall0.61–0.65s, RSS<90MB, inventory0.
Cutoff60m имеет дополнительный lifecycle append и измерен отдельно от fixed work.
Pre-upgrade local fixtures получают synthetic binding через public OPS owner;
production migration не заявлена. Setup/preparation вне timing; warm cache не proof.
1/7/30/60-day equivalents — cadence MODEL, не полный live trajectory corpus.
Ceilings30s/512MiB/7partitions не изменены; active paired proof покрывает local control.

R2: UTC/cycle, synthetic legacy accounting debit/pacing, STARTED UNKNOWN без retry,
429/timeout/missing/late, cap, sticky stop/drain повторены. Legacy seed — accounting
fixture, не legacy provider tick. Credential/STARTED drift не обходит new-day cap.
R3: full vertical25 admissions/24mints/3cohorts, public capture/freeze/export/
transfer/seal/import после72h workstation-off, torn import/new-as-of retry и exact
repeat. Native card/PIT/protection provenance и synthetic numeric oracle сохранены.
Real scientific MAIN/ADAPTIVE looks0.
R4: existing backup owner, nonempty detached restore, original/network BLOCKED,
saved readback без write, numerical replay equality, duplicate import и typed
corrupt/missing refusals. New archive24,742,883 bytes, SHA
c5e2d5fde8693f9c47a3816122437e5081514aef5e24d278d20783b77c1b115c.
Windows process proof не устанавливает Linux unit/power-loss acceptance.
Lookup reprepare на target root не перепривязывает immutable envelope старой
activation. Changed root identity блокирует intake; canonical recovery/tail —
отдельный OPERATE/repair gate с target-volume headroom до COMPLETE/backlog0.
Новый envelope — новая supported activation/cohort boundary, без intraday fragments.
R4 не доказывает ACTIVE producer restart на root с изменённой identity.

Validation:76 targeted tests PASS без skips (lookup/lifecycle/producer/operability);
Current suite включает полный canary/R2 и три temporal cutoff regressions.
R3/R4 three-process repeat PASS на committed unchanged Git; intermediate
GIT_MUTATION refusal сохранён, gate не обходился.
Groups overlap, не суммируются. R1 paired и aged fresh-process proofs повторены
после последнего implementation delta. Все12 source hashes совпадают с code.
Direct semantic consumer:15 tests PASS без skips. Предыдущий Actions shard4
выявил new alias headroom→OOM и overview16,457>16,384 bytes. Navigation config
исправлен: VPS OOM→SEM-REMOTE-OPS-RECOVERY, overview16,368 bytes; gold queries/
лимиты/engine сохранены. Lookup доступен через operator runbook. Runtime hashes
не изменились; R1–R4 evidence остаётся применимым.
Four isolated reviews повторяются на exact final content перед binding.

WATCH без optimization:60-day root21,910 node files/19,434,842 bytes;
один measured tail tick +17 files/+20,839 bytes. Packet при138 actual due rows
0.34/1.87/5.16/11.74s на1/7/30/60-day histories; canary6,624 rows —0.50s.
Это разные histories, не функция только due count. Linux inode allocation/growth
UNKNOWN; Windows file-count proxy — MODEL. GC/retention/engine redesign/packet
optimization отсутствуют.

FACT: local owner paths, fresh processes/counters, rehearsals, pressure/recovery,
WATCH. MODEL: calendar equivalents, account/copy/30d/97d forecasts, inode proxy.
UNKNOWN: actual approved local/whole-Factory envelope/volumes/backup peaks,
shared account/other consumers, actual protection completeness, category5m
receipt, Linux acceptance, notification receiver. Near-cap sensitivity не даёт
Factory <=40GiB TARGET/<=50GiB HARD PASS.

Один следующий owner gate: MERGE boundary после unchanged exact-head CI PASS
и machine readiness. Queue/degradation=PENDING_INFRA, не FAIL и не PASS.
Merge в atom запрещён. Позднее только separate OPERATE с exact merged SHA/host,
disabled lane, backup/copy/quiescence, canonical in-place preparation, actual
local/Factory envelope и fresh calendar/authority. Legacy intake+tail сначала
COMPLETE. Deploy/settings/timer/provider calls, production import, real science,
destructive cleanup и JUPITER_CORE reopening здесь отсутствуют.
