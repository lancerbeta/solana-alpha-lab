# Risk and Economics V1

Owner-facing `/economics` composition over existing PaperPlane accounting.
Does not own StrategyVersion definition, PaperPlane lifecycle, science,
commands, HOME attention, system health, Visual OS, or LIVE cashflow.

Catalog document: `DOC-RISK-AND-ECONOMICS-001`
Semantic route: `SEM-OWNER-LIFECYCLE` (reused; no `SEM-RISK` / `SEM-ECONOMICS`)
No new canonical binding: attach through lifecycle/operations Catalog relations.

```text
StrategyVersion + PaperPlane accounting
        → RISK_AND_ECONOMICS_V1
        → /economics + FactoryApplication.economics_projection
        → Operations drilldown when action is required
```

```text
authority_granted = false
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
GET /economics = non-mutating
projection persists nowhere
current PnL/risk never enters Git or Catalog
```

## 1. Owner questions

```text
Что именно измерено, на какой evidence-модели, какие costs учтены,
где результат UNKNOWN, какой declared entry-admission risk доказуем,
и чего из этих цифр нельзя заключать?
```

## 2. Truth planes

```text
SCIENTIFIC MEANING              → Experiment / Research
STRATEGY + DECLARED POLICY      → Git StrategyVersion
BOT / POSITION / MARK / EXIT    → PaperPlane
TRADING COMMAND / INVENTORY     → TRADING_OPERATIONS_WORKBENCH_V2
SYSTEM HEALTH                   → SYSTEM_OPERABILITY_SURFACE_V2
ECONOMIC / RISK INTERPRETATION  → derived RiskEconomicsProjectionV1
GLOBAL DAILY ATTENTION          → OWNER_ATTENTION_AND_CHANGE_FEED_V1
OWNER PRESENTATION              → Workbench
```

## 3. Two economic planes

Reconciled model economics and open-mark economics are never summed into
one TOTAL PNL / equity / cash balance.

```text
RECONCILED  → completed modeled outcome
OPEN MARK   → as-of estimate on unresolved inventory; NOT_SETTLED
```

PAPER and SHADOW are visually and numerically separate. Neither is LIVE
owner cash.

## 4. Scope identity

Every aggregation is keyed by `strategy_id`, `strategy_version`, `mode`,
`pnl_evidence_class`. Optional inspectable drilldown: `activation_epoch_id`,
`bot_instance_id`. No aggregation across versions, PAPER vs SHADOW, evidence
classes, or UNKNOWN vs KNOWN.

Money without an accepted evidence class is `EVIDENCE_CLASS_UNKNOWN` and
does not enter a trusted headline.

If more than one incompatible reconciled scope is present:

```text
MIXED_EVIDENCE_NOT_AGGREGATED
reconciled_net_pnl_usd = null
```

Exactly one compatible reconciled scope may populate the legacy
`reconciled_net_pnl_usd` compatibility field.

## 5. Accounting

Trusted reconciled rows expose entered/exit notional, gross, entry fee,
exit fee, net. Invariant:

```text
NET = GROSS - ENTRY_MODELED_FEE - EXIT_MODELED_FEE
```

Decimal / ROUND_HALF_UP as in PaperPlane. Conflict →
`ACCOUNTING_INVARIANT_CONFLICT`, source bytes preserved, row excluded from
trusted aggregate. No silent recompute.

`MODELED_FEE_COVERAGE` is COMPLETE only when those PaperPlane fee components
exist for all included trusted rows. It is not all real trading costs.

```text
TOTAL_REAL_TRADING_COST = NOT_ESTABLISHED
NETRETURN_STATUS = NOT_ESTABLISHED
OWNER_FCF_STATUS = NOT_AVAILABLE
```

## 6. Open marks

Forward `record_position_mark` uses one helper:

```text
mark_value = mark_price * qty
unrealized_gross = mark_value - entered_notional
modeled_exit_fee_at_mark = mark_value * fee_bps / 10000
unrealized_net = gross - entry_fee - modeled_exit_fee_at_mark
```

Legacy rows are not rewritten. Projection may derive current marked
interpretation from complete raw components
(`DERIVED_FROM_LEGACY_RAW_COMPONENTS`). Missing component →
`OPEN_MARK_COST_COMPONENT_GAP` / net UNKNOWN.

`mark_as_of` may yield `mark_age_seconds`. No TTL policy exists:

```text
MARK_FRESHNESS_POLICY = NOT_DEFINED
```

Do not classify FRESH / STALE / EXPIRED. Missing `mark_as_of` →
`MARK_TIME_UNKNOWN`.

## 7. Path metrics

Drawdown is `RECONCILED_MODEL_PNL_DRAWDOWN_USD` over cumulative
chronological reconciled model PnL from zero — not account/equity/cash
drawdown. Event time is an aware UTC instant (`Z` or `+00:00`). Naive ISO,
non-UTC offsets, empty or unparseable `closed_at`, or any
UNKNOWN/conflict that can affect the path → numeric null, status UNKNOWN.
The path is walked in UTC-instant order, not string order. No
skip-and-calculate subset.

Loss streak: exact or UNKNOWN. Trailing known losses that hit UNKNOWN
before a known non-loss or fully-known start → count null.

## 8. Declared risk

`risk_policy.max_open_positions` is `DECLARED ENTRY-ADMISSION POSITION LIMIT`
using the same `OPEN_RISK_STATES` as `pre_trade_risk_snapshot()`. Not
capital, portfolio, max loss, or outstanding inventory.

```text
count < limit  WITHIN_DECLARED_ENTRY_LIMIT
count == limit ENTRY_LIMIT_REACHED
count > limit  DECLARED_ENTRY_LIMIT_BREACH
```

Exact StrategyVersion required. No latest-version inference. Missing
identity → `POLICY_UNKNOWN`. Conflicting Git definitions →
`STRATEGY_POLICY_CONFLICT`. Other limits (daily loss, capital, drawdown,
capacity, CVaR/VaR, Kelly) are `NOT_DEFINED`, not unlimited/safe.

Unresolved / EXIT_REQUIRED inventory remains Operations-owned. Entry
headroom never means all risk is clear.

## 9. Exposure

`ENTERED_NOTIONAL_EXPOSURE_USD` scoped by strategy_version and mode. Not
CAPITAL_AT_RISK. UNKNOWN inventory is not zero.

## 10. GET purity

GET `/economics` creates no SQLite, migration, PaperPlane write, mark,
event, command, review cursor, Git write, provider call, or network
mutation. Absent PaperPlane → `SOURCE_NOT_PRESENT`, not PnL = 0.

No commands on `/economics`. Commands stay on `/operations`.

## 11. HOME

No fourth Owner Attention domain. No economics review cursor. Default:
`OWNER_ATTENTION_AND_CHANGE_FEED_V1 = NO_CHANGE_REQUIRED`.

## 12. Non-claims

```text
NO ALPHA
NO NETRETURN
NO LIVE PNL
NO OWNER FCF
NO LIVE CAPITAL
NO CAPACITY CLAIM
NO PROMOTION
NO REAL MONEY
NO DEPLOY
NO PROVIDER
NO WALLET
```
