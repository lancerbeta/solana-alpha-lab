# Prior-Git t0 friction screen — owner readout

Живая Free-key кампания завершилась. Это закрывает точное семейство
prior-Git t0 friction-screen. Это не alpha, не MOVE 3 и не
`FACTORY_V1_OPERATIONAL_READY`.

## Packet

| Field | Value |
| --- | --- |
| QUESTION | Улучшает ли заранее замороженный t0-cutoff из prior-Git complete-XY **X** медиану и правый хвост H900 quoted-exit против того же eligible baseline на свежей outcome-blind когорте? |
| ESTIMAND | baseline eligible H900 quoted liquidation recovery versus same baseline after `VETO_IF_X_LT_FROZEN_PRIOR_GIT_MEDIAN` |
| POPULATION | новая live 6 RECENT + 6 TRADED, исключая A1, MOVE 2, commissioning и ATOM 5 veto-campaign mints |
| DATA | capture policy + four exclusion receipts; frozen cutoff `-0.0205835` (n=33); runtime и acceptance теперь hash-bound |
| RESULT | `CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY` (`STRATUM_UNSTABLE`: kept arm только TRADED) |
| UNCERTAINTY | screening hint, не OOS confirmation |
| ROBUSTNESS | H3600 predeclared robustness, not searchable Y |
| FAILURE | audition `CLOSE_EXACT_QUOTE_FRICTION_MECHANISM`; экран не удерживает оба страта |
| DECISION | закрыть это точное t0-screen семейство; без post-hoc threshold search; без recapture suffix |
| NEXT | не EXTEND_TO_SHADOW; не MOVE 3; не VPS; ATOM 5 остаётся закрытым |

## Что говорят числа

Capture PASS: 12 complete-XY, 11 time-separated, 6/6 TRADED time-separated,
50 provider requests, 0 retries/fallbacks, cash $0.

Замороженный cutoff `-0.0205835` (не подсмотренный ATOM 5 `-0.0116887`)
отрезал 7 из 12 complete-XY. Все 6 RECENT ушли в veto. Kept = 5 TRADED.
Медиана и p90 kept лучше baseline, но правило PASS требует оба страта
RECENT и TRADED, поэтому семейство закрывается.

Audition на этой выборке дал `CLOSE_EXACT_QUOTE_FRICTION_MECHANISM`
(concordance 0.418). Overlay-терминал экрана — отдельное owner decision,
не научный «механизм подтверждён».

## Architecture residual

Cutoff — медиана complete-XY **X** из A1 + MOVE 2 + commissioning, а не
живая t0-only политика. Projector не делает этот cutoff deployable t0
filter. Нельзя читать этот атом как operational-ready или как reopen ATOM 5.

## Non-claims

Нет alpha, NetReturn, MOVE 3, VPS, paid plan, second provider, `/execute`,
wallet, signer, transaction, post-hoc threshold search или
`FACTORY_V1_OPERATIONAL_READY`.
