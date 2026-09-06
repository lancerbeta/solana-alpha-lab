# EXPERIMENT_EVIDENCE_DECISION_V1 — owner readout

Это bounded Move 2: одна существующая карточка эксперимента становится
русским циклом «понял → доказал/не доказал → записал научное решение».
Не StrategyVersion, не PAPER/SHADOW/LIVE, не alpha и не VPS deploy.

## VERDICT

```text
EXPERIMENT_EVIDENCE_DECISION_V1_READY_FOR_MERGE
OWNER_LANGUAGE_RU_PASS
```

Entry: `START`. Route: `DIRECT_CURSOR_DELIVERY`.
Factory Fit: `FULL_REVIEW` PASS. Isolated critics PASS.
`EXPERIMENT_EVIDENCE_DECISION_V1_PASS` только после exact-head CI
и merge-readiness.

## EXACT BASE / HEAD / PR

```text
BASE = 9ce5f80e775ce1e7bacf9383e3dd4412501f88d6
HEAD = 64c5e3d69fc0e5b909bd0765459c30fdc348ab15
PR   = (открывается после push)
merge = (после guarded-merge)
```

## ЧТО ТЕПЕРЬ ВИДНО НА /research

Petr открывает эксперимент и видит по-русски: что проверяли, какие
доказательства прямые, какие только прошлый контекст, чего не хватает,
и может записать `REJECT` / `REVISE` / `PAUSE` / `PROMOTE` как научный
`DECISION_EVENT`, затем прочитать его обратно. Machine IDs и enum
остаются английскими.

Неполный честный эксперимент — PASS. Угаданные join — FAIL.

Реальный объект `EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001` /
`HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1` рендерится честно неполным:
фальсификатор есть в Git-определении, научных PIT/N/result нет,
`next_safe_action: DO_NOT_PROMOTE`, `PROMOTE` закрыт.

## LANGUAGE

```text
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
TRANSLATION != SCIENTIFIC MUTATION
```

Legacy scientific English не переписывался. Presentation translation
не владеет научной истиной. Нет i18n-фреймворка и нет runtime LLM.

## DECISION BOUNDARY

`PROMOTE` пишет только scientific `DECISION_EVENT`. Не создаёт
StrategyVersion, не стартует PAPER/SHADOW/LIVE, не трогает wallet,
provider, deploy.

GET `/research` остаётся non-mutating. Запись — POST `RESEARCH_DECISION`
через `FactoryApplication`.

## SEMANTIC CLOSURE

Существующий `SEM-OWNER-LIFECYCLE` расширен. Нового semantic route нет.
Catalog/generated navigation обновлены generator-ом.

## ЧТО ОСТАЛОСЬ GAP / UNKNOWN

- VPS deployed state = UNKNOWN unless separately read back
- `SCIENCE_TO_STRATEGY_HANDOFF_V1` — WATCH, не стартовать
- Git overview column `evidence_class=NOT_APPLICABLE` для ExperimentSpec
  остаётся Move-1 metadata списка; научная матрица dossier его не
  использует
- `science_guard` — key-presence eligibility, не научная валидность PIT

## ЧТО НЕ МЕНЯЛОСЬ

source truth ExperimentSpec/trials/evidence hashes, StrategyVersion,
provider/RPC, wallet, production systemd, root README/AGENTS.

## TEST / REVIEW / CI

Focused unittest green: incomplete real experiment, DIRECT vs RELATED,
CONFLICT, NOT_TESTED → UNKNOWN, RUN_COMPLETED ≠ PIT PRESENT,
HTTP REJECT readback, `OWNER_LANGUAGE_RU_PASS`, semantic anti-hijack.

Isolated critics PASS (code / goal / architecture; packet
`7610d11b23c4376d12593f0526b8fa63b72bfdb89cdc7707f9327f035e18c7e4`).
Factory Fit `FULL_REVIEW` PASS. Exact-head CI — live machine gate.

## DEPLOYMENT STATUS

```text
Git capability = repository PR candidate
VPS deployed state = UNKNOWN unless separately read back
```

This atom did not SSH, deploy, or restart systemd.

## ROLLBACK

Ordinary Git revert. Do not delete a real `DECISION_EVENT`; use a
superseding/corrective event.

## NEXT RECOMMENDED MOVE

```text
SCIENCE_TO_STRATEGY_HANDOFF_V1
```

Do not auto-start.

## MERGE READINESS

Stop at `OWNER_ATTENTION_GATE_V2`. Do not merge until exact-head CI is
green and `--merge-readiness` reports `ready_for_owner_phrase: true`
for this unchanged PR/head. Owner supplies the exact phrase; the elected
agent merges.

## Factory Fit answers

```text
owner archaeology materially lower       YES
strategy / live / wallet widened         NO
second truth store                       NO
i18n framework / LLM translation         NO
legacy scientific rewrite                NO
```
