# RESEARCH_LIFECYCLE_WORKBENCH_V1 — owner readout

Это read-only owner surface над `LifecycleProjectionV1`, не source truth,
не mutation workflow, не alpha и не VPS deploy.

## VERDICT

```text
RESEARCH_LIFECYCLE_WORKBENCH_V1_PASS
```

Entry: `START`. Route: `DIRECT_CURSOR_DELIVERY`.
Factory Fit: `RESEARCH_LIFECYCLE_WORKBENCH_FACTORY_FIT_PASS`.

## EXACT BASE / HEAD / PR

```text
BASE = 97281cccca06365515b282868174cdfd0b023845
HEAD = (bind after evidence commit)
PR   = (opened after push)
```

## ЧТО ТЕПЕРЬ ВИДНО НА /research

Petr открывает `/research` и за 30–60 секунд видит: что есть, что
сейчас выполняется (или `NOT AVAILABLE`), какие trials/decisions/negatives
уже материализованы, что требует внимания, какие gaps, откуда объект и
с чем он явно связан. Без Git/SSH/SQLite археологии.

## 4 OWNER LOOPS

- what exists — overview counters/groups from `LifecycleProjectionV1`
- detail — plane-safe locator click; source-owned fields only
- lineage — inbound/outbound Move-0 relations; GAP/CONFLICT visible
- trust — source panel, `PARTIAL`, degraded copy, UNKNOWN as text

## REAL OBJECTS PROVEN

- trial `TRIAL-RC002-H11-NEXT-GTA-TARGET-001` — native outcome, created_at, hypothesis relation or TARGET_GAP
- ExperimentSpec `EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001` — QUESTION/ESTIMAND/POPULATION/FALSIFIER
- negative `NEGATIVE-T30-CURRENT-DATA-ROUTE-001` — explicit negative memory, not killed hypothesis
- disposable ResearchStore HYPOTHESIS_VERSION → TRIAL → DECISION_EVENT, then no filesystem mutation

## READ-ONLY PROOF

Missing ResearchStore stays `NOT_PRESENT`. GET `/research` does not mkdir,
lease, manifest, or rebuild. SQLite opens `mode=ro&immutable=1`.
Optional `--data-root` never creates. Normal Workbench start path unchanged.

## VISUAL RESULT

- STEEL_SIGNAL shared chrome (HOME / RESEARCH / OPERATIONS / ECONOMICS / SYSTEM)
- EVIDENCE_EDITORIAL detail
- TRACE lineage
- Visual OS tokens only; DARK_ONLY; no second palette

## SEMANTIC CLOSURE

- existing `SEM-OWNER-LIFECYCLE` reused
- second binding `ACTIVE-RESEARCH-LIFECYCLE-WORKBENCH`
- Prior Work repair: `REGISTRY-GLOBAL-TRIAL-LEDGER-001` on `SEM-PRIOR-WORK`
- Catalog/generated navigation current
- no new semantic route; `max_routes` unchanged

## ЧТО ОСТАЛОСЬ GAP / UNKNOWN

- VPS deployed state is UNKNOWN unless separately read back
- holdout / experiment evidence quality is Move 2
- invented strategic groups (`KILLED`, `READY_TO_TEST`, …) stay absent
- activity is `NOT AVAILABLE` when runtime/evidence sources are not observable

## ЧТО НЕ МЕНЯЛОСЬ

source truth, research mutation, existing HOME/Operations commands,
authority, production systemd/runtime, root README/AGENTS.

## TEST / REVIEW / CI

Focused unittest green: real trial/experiment/negative, non-mutating
ResearchStore, missing store, plane conflict, Visual OS, operations
command regression, EN/RU semantic gold + anti-hijack. Isolated critics
PASS (code / goal / architecture; packet `95e57db9…`). Factory Fit
`FULL_REVIEW` PASS. Exact-head CI remains the live machine gate.

## DEPLOYMENT STATUS

```text
Git capability = repository PR candidate
VPS deployed state = UNKNOWN unless separately read back
```

This atom did not SSH, deploy, or restart systemd.

## ROLLBACK

Ordinary Git revert. No data/runtime/browser-state migration.
Source truth survives independently of Workbench.

## NEXT RECOMMENDED MOVE

```text
EXPERIMENT_EVIDENCE_DECISION_V1
```

Do not auto-start. Design Move 2 against objects and pain visible here.

## MERGE READINESS

Stop at `OWNER_ATTENTION_GATE_V2`. Do not merge until exact-head CI is
green and `--merge-readiness` reports `ready_for_owner_phrase: true`
for this unchanged PR/head. Owner supplies the exact phrase; the elected
agent merges.

## Factory Fit answers

```text
owner archaeology materially lower       YES
Move-0 lifecycle projection reused        YES
global trial source visible if canonical  YES
new truth store                           NO
new semantic route                        NO
normal browser read writes Git            NO
normal browser read writes evidence       NO
frontend framework                        NO
useful in degraded mode                   YES
Visual OS reused                          YES
future frontend replaceable               YES
capability_radar.now                      NONE
```
