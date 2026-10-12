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
CURRENT RUNTIME ENVELOPE        → TradingRuntimePolicyV1 in PaperPlane (read-only)
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

`/economics` may read TradingRuntimePolicyV1 as current operating envelope
context. It does not own or edit policy. Visually separate economic
evidence, StrategyVersion requested/declared values, and runtime limits.
Open-risk notional is not wallet cash, available balance, portfolio
equity, or Owner FCF.

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

`CANCELLED` is a terminal non-fill. It is not an `OPEN_RISK_STATES` member,
not entry-admission risk, and not inventory. Its PnL status is
`NOT_APPLICABLE`.

## 9. Exposure

The Operations projection exposes compatible bot/version/epoch/mode scopes.
MIXED_SCOPE suppresses aggregate money/streak/drawdown/exposure headlines.
Its modeled attempt costs are cumulative additional costs **excluding** the
price-leg fees already included in trade PnL; failures remain in this denominator.
Missing cost is UNKNOWN. `reconciled_trade_net_pnl_usd` retains the existing
fee-only trade component. `modeled_net_after_additional_costs_usd` is available
only for one compatible, terminal, fully-known modeled scope. Neither is live
NetReturn or FCF. Exact semantics: `docs/contracts/episode_decision_continuity_v1.md`.

`ENTERED_NOTIONAL_EXPOSURE_USD` scoped by strategy_version and mode. Not
CAPITAL_AT_RISK. UNKNOWN inventory is not zero.

## 9.1 Quantity-based modeled results V1.1

`accept_modeled_result` remains byte-compatible for stored v1.0 results and
their exact replays. Its additive v1.1 contract uses explicit quantity in
`TOKEN_UNITS`; entry `filled_notional_usd` is not an exit proceeds field.
Positive ENTRY requires `quantity_filled`, `filled_notional_usd`, and
`unit_price_usd`. Positive EXIT requires `quantity_sold`,
`remaining_quantity`, and `unit_price_usd`. A partial EXIT has strictly
positive remaining quantity; a full EXIT has zero. Sold plus remaining must
equal the last proved inventory, without overfill, negative/NaN values or
unsupported units. A definitive partial completes one attempt and returns
the position to its originating `EXIT_REQUIRED`; the next attempt targets
only the remainder. UNKNOWN cannot authorize an overlapping attempt.
ENTRY quantity times its effective paid-notional unit price must agree with
the filled notional at the model's cent precision. A quote's market midpoint
cannot substitute for that effective net quote price.

V1.1 positive results require `fee_semantics`:
`SEPARATE_MODELED_FEE` uses the frozen fee basis points per price leg;
`INCLUDED_IN_UNIT_PRICE` declares fees already net in quote price/quantity and
adds no modeled fee again. Raw quote quantity is preserved exactly. The
separate `chargeable_cost_usd` remains cumulative additional cost excluding
both such leg fees. Missing costs preserve economic UNKNOWN even after a
quantity-proved physical drain.
Cold recovery retains every original accepted result observation after the
backup, including its result ID, physical clock and known cumulative cost.
Replay passes through the same accounting owner before the latest receipt;
a later UNKNOWN total cannot erase the earlier known cost floor.

The original `qty_dec`, entry cost and total entry fee stay immutable.
`remaining_qty_dec`, `remaining_cost_basis_usd_dec` and
`remaining_entry_fee_usd_dec` express the proved remainder. Append-only
`MODELED_EXIT_QUANTITY_LEG` records realized proceeds and fee allocation.
Entry fee allocation uses the cumulative sold fraction rounded to cents;
the final leg consumes the exact residual fee, so total allocation equals
the original entry fee. Partial realized rows and residual open marks are
separate, without a settled/full-return headline or mixed-mode aggregation.

Before another quantity EXIT, the existing PaperPlane owner verifies
the current remainder and accumulated cost/fee/proceeds/net against indexed
original accepted entry and ordered EXIT witnesses. Readback and dispatch
share this proof. The same check runs inside attempt creation and EXIT result
acceptance transactions. A corrupt partial projection cannot become new
inventory authority through another attempt: retain typed UNKNOWN, the
original quantities and any pending result, without another quote effect.
Healthy neighboring originating obligations continue independently. No
new truth table, cache or schema is introduced. An exact restored original
witness/projection may resume through the same validated ordinary path.

Literal synthetic oracle: 10M units at `$0.000003` enter for `$30` plus
`$0.06` fee. Exit 4M at `$0.0000033` gives `$13.20` proceeds and `$0.03`
fee, retaining 6M units and `$18` cost basis. Exit the final 6M at
`$0.000003` gives `$18` proceeds and `$0.04` fee. Aggregate gross is
`$1.20`, trade net `$1.07`; additional `$0.01` gives model net `$1.06`.
Exact result replay creates no second accounting effect. These are offline
engineering quantities, with no alpha, live cash, NetReturn or FCF claim.

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
