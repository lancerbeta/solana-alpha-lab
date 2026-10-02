# HFIC market basis V2 — owner readout

Метаданные публикации больше не создают новый научный рынок и не освобождают
бюджет исследований. V2 связывает epoch с составом cohorts, неизменными
release/content/source, логическим содержимым partitions, временем событий
и доступности для стратегии, а также фактически используемой A3 eligibility.
Manifest IDs, fingerprints, схемы, часы публикации и validation receipts
остаются проверяемым provenance. Повреждённые данные останавливают admission.

V1 хешировал также publication wrapper и весь labels surface: изменение
`imported_at` могло скрыть прежнюю occupancy. V2 исключает эти поля из
научного хеша. Сами квоты AUTO=1 и distinct-focus=3 не меняются.

| Проверка | Результат |
|---|---|
| imported_at-only / equivalent schema-root republish | тот же V2 epoch, занятый бюджет сохранён |
| decision-bearing A3 / verified content-PIT-source change | новый epoch или typed integrity STOP |
| новый synthetic cohort | новый рынок, fresh budget допустим |
| parquet / lineage / canonical receipt tamper | STOP, не новый рынок |
| доказанная V1 continuity | прежняя occupancy продолжает считаться |
| неоднозначная V1 continuity | STOP `MARKET_EPOCH_CONTINUITY_UNRESOLVED`, не свободный слот |

Current real C1–C3 read-only comparison: corpus v3; AUTO 1/1, focus 3/3,
remaining 0 до и после. Все бюджетные поля совпадают, кроме идентификатора
алгоритма epoch. Scoped inventory из 55 файлов и committed ResearchStore
inventory не изменились. Точные hashes и scope:
[read-only proof](../../evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_readonly_budget_v1.json).

V1 epoch: `ae771cf5c1e7692c007b442c0048e7547005dc09125eeb9eb75e24406e429749`.
V2 epoch: `e722f33420194c1e28e9ba39ddb6bb0c129064f812530588cd4777b0376e1a8e`.
Это смена версии хеша, а не новый scientific market.

Validation на исправленном кандидате: 29 V2/budget tests PASS; полный
owner-gold 54 PASS; два ordinary consumer tests PASS; direct preflight 19
tests — 18 PASS и один существующий non-critical skip. Новых skips нет.
Exact-head CI и owner merge gate проверяются отдельно; локальные tests не
означают delivery DONE.

Независимые critics выявили и потребовали закрыть alias-профиль manifest,
missing LIVE labels/fence и восстановление явного NULL reservation.
Теперь parsed manifest ID обязан совпадать с именем файла; canonical
integrity нельзя обойти stable filename. Используется existing LIVE
REQUIRED_LABELS contract; missing обязательные labels/counters/families
дают STOP, а штатные optional NULL сохраняются. Явный NULL reservation
не восстанавливается из lifecycle. Optional generic reuse flag совпадает
с фактическим bool-default потребителя, без искусственного нового рынка.
Owner output объясняет continuity STOP и указывает на runbook.

Operator readback: существующий `forge-run --no-write` показывает saved
artifacts и identity без новой попытки. AUTO/focus counters доступны в
`search_budget` через `preflight --no-auto-commission --owner-focus AUTO
--format json` на уже разрешённом current root, без persistence/commissioning.
При unresolved continuity budget=UNRESOLVED, не zero. При incomplete basis сначала
восстановить валидный current input в отдельно разрешённом atom; при
unresolved continuity сверить frozen basis и current verified composition,
не стирать историю и не сбрасывать квоты. Exact operator path:
[runbook](../../operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md).

Ограничение: V1 frozen basis с отличающимся wrapper не содержит достаточно
данных для доказательства равенства научных полей. Такой случай намеренно
блокируется; historical records не мигрируются и не переписываются.
Откат — обычный Git revert, без изменения ResearchStore или LIVE inventory.

Нет real data-plane writes, real C4 access/import, scientific Forge,
quota/estimand changes, provider/deploy и LIVE repair.
Следующий отдельно разрешаемый atom после merge:
`LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2`.
Factory Fit FULL_REVIEW. Capability radar NOW=NONE; WATCH=metadata repair
must retain the V2 scientific projection and verify integrity before publish.

## Exact-head CI remediation

CI on a71dfdadfbafafa9371101e3e8692795a11e0dce failed. The temporal CLI
recomputed ordinary admission from the explicit row root after validating the
canonical market/store root. Both gates now retain the validated market root;
invalid identity remains a typed STOP. The original failing vertical test PASS.

Fixture corrections retain integrity and continuity checks: canonical roots
use real builder/fingerprint/receipt hashes and required LIVE labels; frozen
priors carry a verified earlier synthetic basis; ladder freeze/readback use the
same effective payload; the vanilla oracle includes verified partition claims;
source/revision selection is checked in both storage orders.

Focused remediation PASS: closure 2, selection 1, ladder 27, vanilla/revision 2,
V2/budget 29, full owner-gold 54, censoring consumers 54, synthetic Forge input 11.
A broader local consumer run also automatically read the installed C1-C3 v3
plane. Its inventory remained unchanged. Two legacy LIVE smoke assertions
failed: hard-coded corpus v2 and expected preflight receipt absent. They remain
explicit limitations, not PASS or a newly skipped assertion; the isolated rerun
selects synthetic cases only. No real repair, C4, or scientific operation.
Fresh review, evidence binding and new exact-head CI remain mandatory.
