# OWNER_TRADING_OPERABILITY_FOUNDATION_V1 — owner readout

Petr может менять PAPER/SHADOW operating envelope без Git: остановить
новые входы, смотреть открытый риск, CHECK/APPLY runtime policy через
агента. Это не LIVE, не деньги, не новый движок и не редактор политики
в Workbench.

## VERDICT

```text
START_WITH_PATCH
OWNER_TRADING_OPERABILITY_FOUNDATION_CANDIDATE
ROUTE=DIRECT_CURSOR_DELIVERY
SEMANTIC=SEM-OWNER-LIFECYCLE reuse
```

Канонический `DONE`, LIVE и Owner FCF не следуют из тестов, PR, CI или merge.
Deploy и VPS policy APPLY в этом атоме запрещены.

## OWNER SENTENCE

Обычный торговый ответ больше не требует StrategyVersion/YAML/PR.
Git владеет смыслом стратегии. Runtime владеет текущим конвертом.
GET ничего не создаёт. Первая реальная политика — отдельный
owner-authorized APPLY после merge/deploy.

## 1. RUNTIME POLICY

- Storage: существующий PaperPlaneStore (`paper_plane_state.sqlite`).
- Modes: PAPER и SHADOW независимо. LIVE → `LIVE_NOT_SUPPORTED`.
- Append-only `trading_runtime_policy_revisions` + operator_commands
  idempotency. Stale hash → `POLICY_STALE_WRITE_DENIED`.
- Bootstrap: нет row → `NOT_CONFIGURED_STRATEGY_ONLY` (старое
  StrategyVersion-only admission). Invalid → `RUNTIME_POLICY_INVALID`,
  NEW fail-closed, EXIT живёт.
- Git хранит только capability + APPLY phrase, не current values.

## 2. ENTRY ADMISSION

Один SQLite `BEGIN IMMEDIATE`: StrategyVersion + current policy +
inventory. Effective notional = min(request, runtime cap). Headroom
ниже размера → BLOCK, без auto-shrink. OPEN_RISK UNKNOWN → BLOCK.
Admission freeze: admitted notional + policy mode/revision/hash.
Concurrent last slot: 1 ALLOW / 1 BLOCK. Crash после ALLOW: reservation
держит слот, retry не ресайзит.

## 3. OWNER OPERABILITY (no Git)

SHOW → CHECK → exact phrase → APPLY → READBACK.

```text
AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY
```

Gitless уже доступны: pause/resume bot entries, close position,
close-all bot, stop bot, global `new_entries_enabled=false`.
Restart/deploy persistence: policy живёт в том же sqlite, который уже
в mutable backup; isolated copy restore доказан. Нет VPS APPLY здесь.

## 4. WORKBENCH

Широкий workstation canvas (`main` без max-width, prose 42rem).
Секции `section.zone` на существующих Visual OS tokens.
№ + compact copyable ID + pagination 25 (страница 2 = 26–50).
Operations: Торговые ограничения; requested / runtime / effective;
ACTIVE vs HISTORY. Research — индекс, не стена source text.
HOME не поднимает historical ExperimentSpec phrase как текущую команду.

## 5. SEMANTIC GIT IMPACT

| Surface | Class |
|---|---|
| AGENTS.md | NO_CHANGE_REQUIRED |
| README.md | NO_CHANGE_REQUIRED |
| PROJECT_MAP / OPERATOR_NAVIGATION / FACTORY_SEMANTIC_MAP | generator only |
| owner lifecycle projection config | NO_CHANGE_REQUIRED |
| Visual OS / Operations / Economics / Science→Strategy | CHANGE_REQUIRED (additive) |
| StrategyVersion schema | CHANGE_REQUIRED descriptions only; no v1.2 |
| PaperPlane | CHANGE_REQUIRED |
| backup/recovery docs | NO_CHANGE_REQUIRED (sqlite already backed up) |

Current runtime values never enter Git/Catalog.

## 6. PRODUCT HORIZON

```text
NOW   = NONE
WATCH = editable Workbench policy form
        only after Petr uses SHOW/CHECK/APPLY for weeks
CAPABILITY_RADAR_NOW = NONE
```

Evidence-triggered later, not this PR:

- portfolio equity + daily-loss/drawdown when canonical equity exists;
- slippage/price-impact when executable quote truth exists;
- true lot/pyramid when a strategy needs multiple adds;
- global cross-bot close-all only if bot-scoped workflow is insufficient.

## NON-CLAIMS

```text
NO LIVE
NO REAL MONEY
NO OWNER FCF
NO PROVIDER
NO DEPLOY
NO VPS POLICY APPLY
NO WORKBENCH POLICY EDITOR
NO ALPHA
NO CANONICAL DONE
```

## NEXT

Exact-head CI → merge-readiness → one owner merge phrase.
После merge отдельно: deploy/smoke, browser readback, owner-authorized
инициализация реальной PAPER/SHADOW policy, затем реальное использование.
