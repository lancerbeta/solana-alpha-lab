# BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1 — owner readout

| Field | Value |
|---|---|
| Atom | `BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1` |
| Route | `DIRECT_CURSOR_DELIVERY` |
| Terminal | `RETAINED_ASSOCIATION_NULL_CLOSE` |
| Next action (not started) | Park BUY-impact as selector/X. Surface/notional reframe remains the product question. |
| Selector authorized | **false** |
| Automatic NEXT started | **false** |
| Provider calls | 0 |

## What was asked

Is decision-time BUY-quote microstructure associated with already frozen H900
executable tails strongly enough to justify a later prospective replication?
This atom does not build a selector.

## Frozen rules (before numbers)

- Primary: literal `BUY_T0` only (W-EP, W-SB, W-HC-A, W-HC-B, W-S30).
- W-VL is appendix only and did not enter the terminal vote.
- Direction = within-window `median(X \| family) − median(X \| FLOOR)`.
- BETTER and WORSE tails are never pooled as NOT_FLOOR for the mutex terminal.
- Overall terminal = weaker of the two family terminals.
- Drop-window may lower a family terminal, never raise it.
- `priceImpactPct` units are a **working assumption**, not a FACT. Signs are
  invariant to `x → 100x`. Absolute magnitude is not interpreted as percent or bps.

## Counts

| Quantity | N |
|---|---:|
| Capsule rows extracted | 103 |
| Primary analysis rows | 87 |
| Distinct tokens in analysis | 87 |
| Informative windows (BETTER) | 4 |
| Informative windows (WORSE) | 4 |

W-EP BETTER is not informative (`n_better = 1`). W-S30 WORSE is not informative
(`n_worse = 0`).

## Family terminals

| Family | Full-cohort | After drop-only-downgrade | Vote |
|---|---|---|---|
| BETTER vs FLOOR | `RETAINED_ASSOCIATION_NULL_CLOSE` | same | 3 plus / 1 minus |
| WORSE vs FLOOR | `RETAINED_ASSOCIATION_REPLICATION_WORTHY` | same | 4 minus / 0 plus |

Mutex overall is the weaker family: `RETAINED_ASSOCIATION_NULL_CLOSE`.

If BETTER and WORSE had been pooled as a single NOT_FLOOR class, the WORSE
unanimity could have been mistaken for a replication-worthy escape association.
That pooling is forbidden. The better-than-floor contrast is split 3–1 and does
not meet the predeclared majority threshold.

## Git capsule

Derived scalars live in:

- `docs/evidence/buy_decision_time_quote_microstructure_association/a1_derived_capsule_v1.jsonl`
- `docs/evidence/buy_decision_time_quote_microstructure_association/a1_association_input_v1.json`
- `docs/evidence/buy_decision_time_quote_microstructure_association/a1_runtime_receipt_v1.json`

Raw A4 trees were not committed. Each capsule row binds `raw_body_sha256` to the
Git receipt manifest, copies frozen `y_h900`, and names extractor
`BUY_DT_QUOTE_MS_EXTRACTOR_V1`. The mutex terminal replays from the Git capsule
without local A4:

```
uv run --locked --managed-python python -B scripts/run_buy_decision_time_quote_microstructure_association.py --from-capsule
```

## Non-claims

No alpha, NetReturn, unit FACT, production selector, strategy availability of X
at snapshot, Discovery, crystallization, or canonical DONE.

## Stop

`STOP_AFTER_TYPED_TERMINAL`. No NEXT atom is started.
