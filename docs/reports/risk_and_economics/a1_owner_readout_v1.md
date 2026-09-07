# RISK_AND_ECONOMICS_V1 — owner readout

Petr на GET `/economics` за ≤30 секунд видит, что измерено, на какой
evidence-модели, какие modeled fees учтены, где UNKNOWN, какой declared
entry-admission limit доказуем, и чего из цифр нельзя заключать.

## VERDICT

```text
START_WITH_PATCH
PRODUCT_FREEZE_PENDING_ARCHITECTURE
```

Канонический `DONE` только после exact-head CI, bind-evidence и merge-readiness.

## EXACT BASE / HEAD / PR

```text
BASE = b403c4df836615a68c79453e4c7ba785e5f2e33b
HEAD = PRODUCT_FREEZE_PENDING
PR   = PENDING
```

HEAD в этом файле — product freeze до bind-evidence. После evidence-commit
канонический head смотреть в Git / PR.

## OWNER SENTENCE

GET `/economics` больше не публикует один суммарный PAPER+SHADOW net и не
называет цифру LIVE cash, NetReturn, owner FCF или portfolio risk. Один
совместимый KNOWN scope может показать scoped model net вместе с
`pnl_evidence_class` и `mode`; это не total profit.

## VERTICAL LOOPS

- ECONOMIC EVIDENCE: PASS — PAPER и SHADOW разделены; reconciled и open mark
  не суммируются; evidence class обязателен; conflict исключает строку;
  PARTIAL_UNKNOWN не публикует subset net.
- DECLARED RISK: PASS — `max_open_positions` = entry-admission readback
  тех же `OPEN_RISK_STATES`, что execution; прочие лимиты `NOT_DEFINED`.
- OWNER INTERPRETATION: PASS — non-claims на экране; команды остаются на
  `/operations`; HOME без четвёртого домена.

## SOURCE OWNERSHIP

- StrategyVersion = declared policy
- PaperPlane = accounting / mark / reconciliation truth
- `PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1` = Decimal/fee source semantics
- `TRADING_OPERATIONS_WORKBENCH_V2` = bot / inventory / commands
- `RISK_AND_ECONOMICS_V1` = one owner composer `compose_risk_economics`
- HOME = `OWNER_ATTENTION_AND_CHANGE_FEED_V1` NO_CHANGE_REQUIRED

## EVIDENCE SCOPES

PAPER и SHADOW отдельно. Reconciled отдельно от open mark. Mixed evidence
→ `MIXED_EVIDENCE_NOT_AGGREGATED`, legacy `reconciled_net_pnl_usd = null`.

## ACCOUNTING

NET = GROSS − entry modeled fee − exit modeled fee. Conflict =
`ACCOUNTING_INVARIANT_CONFLICT`; source не переписывается; строка вне
trusted aggregate.

## MARKS

`modeled_unrealized_mark` — один helper. Marked net включает known modeled
fees. `MARK_FRESHNESS_POLICY = NOT_DEFINED`. Нет TTL. Legacy rows не
переписываются. Incomplete cost → `OPEN_MARK_COST_COMPONENT_GAP`.

## PATH METRICS

Drawdown = `RECONCILED_MODEL_PNL_DRAWDOWN_USD` (не equity). Path требует
aware UTC instant (`Z` / `+00:00`) и идёт по этому instant, не по строке.
Пустой, naive или non-UTC `closed_at`, untrusted/conflict → numeric null /
UNKNOWN. Нет skip-and-calculate. Loss streak exact только при полной
UTC-хронологии; иначе UNKNOWN.

## DECLARED RISK

count < limit `WITHIN_DECLARED_ENTRY_LIMIT`; == limit `ENTRY_LIMIT_REACHED`;
> limit `DECLARED_ENTRY_LIMIT_BREACH` без команды. Headroom ≠ all risk clear.

## EXPOSURE

`ENTERED_NOTIONAL_EXPOSURE_USD`. Не capital-at-risk.

## HOME

NO_CHANGE_REQUIRED. Нет economics domain / cursor / spam.

## SEMANTIC GIT

SEM-OWNER-LIFECYCLE reused. Нет SEM-RISK / SEM-ECONOMICS. Нет третьего
root binding. Нет `ACTIVE-RISK-AND-ECONOMICS`. Catalog:
`DOC-RISK-AND-ECONOMICS-001`. README/AGENTS = NO_CHANGE_REQUIRED.

## NONCLAIMS

NO ALPHA. NO NETRETURN. NO LIVE PNL. NO OWNER FCF. NO LIVE CAPITAL.
NO CAPACITY CLAIM. NO PROMOTION. NO REAL MONEY. NO DEPLOY. NO PROVIDER.
NO WALLET.

## PRODUCT HORIZON

NOW = `RISK_AND_ECONOMICS_V1`
WATCH = `MARKET_DATA_AWARENESS_V1` only when a repeated owner decision needs
current market/liquidity/regime/capacity that Research + Operations +
Risk/Economics cannot answer. Do not auto-start.

## ROLLBACK

Ordinary Git revert. No PaperPlane history rewrite. Projection persists
nowhere.
