# SYSTEM_OPERABILITY_SURFACE_V2 — owner readout

Petr на GET `/system` за ≤30 секунд видит, можно ли сейчас оставить Factory
технически работать без него; если нет — что сломано / DEGRADED / UNKNOWN,
почему это важно и какой recovery path смотреть. Кнопок START/STOP/deploy нет.

## VERDICT

```text
START_WITH_PATCH
SYSTEM_OPERABILITY_SURFACE_V2_READY_FOR_MERGE
```

Канонический `DONE` только после exact-head CI, bind-evidence и merge-readiness.

## EXACT BASE / HEAD / PR

```text
BASE = 2df9fbcfb657d69d4f29d4dbef515552708b384c
HEAD = b13a47d306a1b0c92c2cfeb1318551e4f1629eaa
PR   = https://github.com/lancerbeta/solana-alpha-lab/pull/278
```

HEAD в этом файле — product freeze до bind-evidence. После evidence-commit
канонический head смотреть в Git / PR.

## OWNER SENTENCE

На `/system` видно текущее машинное здоровье, а не Git-capability и не
«процесс жив, потому что yaml существует».

## VERTICAL LOOPS

- OBSERVE: PASS — `process_alive` больше не выводится из Git+store; HTTP-self,
  managed unit и таймеры разделены; systemd unavailable ≠ all down.
- DIAGNOSE: PASS — stale collector, timer fail, backup/offhost/archive/disk
  как source-owned conditions; trading P0 остаётся Operations.
- ROUTE & VERIFY: PASS — карточка несёт recovery route и authority как
  описание, не кнопку; recovery не объявляется из HTTP 200.

## CURRENT TRUTH REPAIR

`FactoryApplication.read_model` больше не вызывает
`project_runtime_health(..., process_alive=True)`. Runtime.yaml —
capability inventory. Текущий health — `SystemOperabilityProjectionV2`.

## READONLY REPAIR

ObservationSchedule GET: `sqlite` URI `mode=ro&immutable=1`. Absent file =
`SOURCE_NOT_PRESENT` без mkdir. GET `/system` не пишет WAL/shm/incident JSON.

## MACHINE SOURCES

Collector packet, readonly ObservationSchedule, `systemctl is-active` без
sudo, `.factory_deploy_sha` vs local Git HEAD, Telegram env class,
`FACTORY_EXTERNAL_HEARTBEAT_URL` class only (URL не дергается).

## /system BEFORE / AFTER

До: HTTP alive + store existence выглядели как живой процесс; Git
`deploy_version` мог заполнить «Развёрнутая версия».
После: вопрос с «технически»; `OK_OBSERVED` даёт русскую leave-фразу;
пробелы покрытия — UNKNOWN/NOT_CONFIGURED, не AVAILABLE. Material
offhost/archive UNKNOWN, NOT_CONFIGURED или DEGRADED не даёт «можно оставить».

## DEPLOY IDENTITY

Owner strip и таблица Deploy показывают `deployed_sha` / `git_head` /
`deploy_relation`. Git `capability_deploy_version` остаётся inventory в
machine dump, не текущий deployed SHA.

## STORAGE / DURABILITY

Mutable / off-host / archive читаются из collector packet. Нет класса и нет
поля = UNKNOWN или NOT_CONFIGURED, не AVAILABLE. Mixed disk/runway sentinel
не OR в AVAILABLE. Recovery — unattended runbook, не новая кнопка.

## HOME

System-local attention кормит Move 5. Если `/system` UNKNOWN/DEGRADED/
ACTION_REQUIRED, HOME SYSTEM coverage не AVAILABLE. Trading P0 не
дублируется. REVIEWED ≠ RESOLVED.

## HONEST UNKNOWN

Windows/no systemd = `SYSTEMD=UNAVAILABLE`. Alert CONFIGURED ≠ delivery
proved. Heartbeat NOT_CONFIGURED ≠ P1. Workbench не видит смерть своего VPS.

## GIT VS RUNTIME

Product Git не утверждает runtime health. Catalog/semantic — capability и
маршруты recovery, не live proof.

## SEMANTIC CLOSURE

- Contract: `docs/contracts/system_operability_surface_v2.md`
- Binding: `ACTIVE-FACTORY-REMOTE-OPERATIONS` (13 live; 14th not added)
- Route: `SEM-REMOTE-OPS-RECOVERY` reused; no `SEM-SYSTEM`
- Gold: system/unattended questions hit remote-ops; restart/deploy stay
  `SEM-AUTHORITY-BOUNDARIES`
- `FACTORY_SEMANTIC_MAP` / `PROJECT_MAP` updated; `OPERATOR_NAVIGATION`
  `NO_CHANGE_REQUIRED`; README frozen

## TESTS / CRITICS / FIT / CI

Vertical A/B/C/D + GET purity + CLI JSON + forced MATCH/MISMATCH +
MATCH-isolated durability falsifiers.
Isolated CODE / GOAL / ARCHITECTURE PASS on this product freeze.
Factory Fit FULL_REVIEW. `CAPABILITY_RADAR_NOW=NONE`.
`packet_fingerprint_sha256=8b77c12ec86141b3c5c201b8a63be966a84c14ce624a5ef073c567d557bb3dd8`

## NON-CLAIMS

```text
NO ALPHA
NO LIVE
NO REAL MONEY
NO OWNER FCF
NO DEPLOY
NO PROVIDER CALL
NO DRIVE WRITE
NO TELEGRAM SEND
NO WALLET
NO SYSTEM HEALTH FROM GIT
NO MONITORING PLATFORM
NO CANONICAL DONE
```

## ROLLBACK

Revert the PR merge. No runtime DB migration. No host mutation in this atom.

## PRODUCT HORIZON

```text
NOW   = SYSTEM_OPERABILITY_SURFACE_V2
WATCH = RISK_AND_ECONOMICS_V1
CAPABILITY_RADAR_NOW = NONE
```

Не стартовать Move 7 автоматически. Не деплоить.
