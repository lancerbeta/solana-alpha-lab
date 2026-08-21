# EARLY ICP freeze — owner readout

Терминал: `EARLY_ONLY_ICP_CONFIRMED`. SEASONED-ветка закрыта как `TOPTRADED_NOT_SAME_POPULATION`.

Это не alpha, не quotes, не 3 X и не strategy. Factory runner не менялся. Provider calls в этом атоме: 0 (acceptance-проекция офлайн).

## Простыми словами

**Первый настоящий ICP заморожен:** `ICP-EARLY-PUMPFUN-V1` = токены pump.fun в возрасте 5–15 минут, ликвидность ≥ $1000, добываются схемой «подождать ≥5 минут → один bulk search». Из сохранённых raw-байтов живого прогона сегодня восстановлено и подтверждено: **27 EARLY** при требовании 12. Supply больше не вопрос.

**SEASONED через `/toptraded` закрыт навсегда для этого ICP.** Это не «не хватило зрелых токенов», а невалидный дизайн набора: `/toptraded` отдаёт выбранных выживших со старыми пулами и неизвестным launchpad (29 из 50 строк без launchpad; 0 строк прошли бы membership только по source). Сравнение 12+12 смешивало бы эффект зрелости + survival selection + канал набора — статистически оформленный шум.

**Maturity снят с критического пути.** Один бесплатный same-cohort probe (те же 27 mint, один bulk later-search, без нового кода) показал: все 27 живы, 27 попадают в 30–120m. Это значит лишь, что «зрелость внутри cohort» когда-нибудь может стать отдельной гипотезой. ICP остаётся EARLY в любом случае. Второй попытки нет.

## Что дальше

Следующий вопрос — ATOM 2: существует ли внутри EARLY decision-time state (макс. 2 PIT-фичи), улучшающий executable outcome против unfiltered baseline, — и сразу вертикальный срез decision → StrategyVersion → BotInstance → PAPER/SHADOW.

## Evidence

- Retained live bytes: `local/in_scope_population_live_supply_gate/` (sha256-pinned в конфиге атома).
- Freeze acceptance: `docs/evidence/early_icp_freeze/a1_acceptance_v1.json`.
- Probe receipt: `local/early_icp_freeze_maturity_probe/maturity_probe_runtime_receipt_v1.json`.
