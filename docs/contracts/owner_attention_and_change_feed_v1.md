# Owner Attention and Change Feed V1

Global daily HOME composition over source-local attention. Does not own
Research, PaperPlane, System probes, Visual OS, or delivery merge
authority (`OWNER_ATTENTION_GATE_V2`).

Catalog document: `DOC-OWNER-ATTENTION-AND-CHANGE-FEED-001`
Semantic route: `SEM-OWNER-DAILY-ATTENTION` (new)
Source owners consumed, not superseded:

```text
Research local attention
Operations local attention (TRADING_OPERATIONS_WORKBENCH_V2)
System/runtime local attention (STATE_ONLY / PARTIAL allowed)
        → OWNER_ATTENTION_AND_CHANGE_FEED_V1
        → HOME
```

```text
authority_granted = false
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
GET HOME = non-mutating
REVIEWED != RESOLVED
current attention is never Git truth
```

## 1. Owner questions

```text
Что реально требует внимания сейчас?
Что стало новым с момента моего прошлого осмысленного просмотра?
Я это состояние реально просмотрел. Что считать новым дальше?
```

Normal success: no material Petr item, source coverage visible, DO NOTHING.

## 2. Truth planes

```text
PRODUCT / POLICY / CATALOG     → Git
SCIENCE                        → ResearchStore
BOT / POSITION / EXECUTION     → PaperPlane
SYSTEM VISIBILITY              → existing runtime projection
OWNER REVIEW CHECKPOINT        → OwnerReviewCursorV1 local JSON only
OWNER PRESENTATION             → derived HOME projection (persists nowhere)
```

## 3. Pipeline

```text
SOURCE-LOCAL FACTS
  → source adapters (shape only)
  → OwnerAttentionProjectionV1
  → CURRENT ATTENTION + CHANGE FEED
  → HOME
  → source drilldown
  → OwnerReviewCursorV1
```

HOME owns no source fact. Workbench does not query stores directly.

## 4. Eligibility

Global attention requires CURRENT OWNER IMPACT. Gap != attention.

```text
P0  proven unresolved execution/inventory risk;
    reconciliation failure while exposure may remain;
    monitoring blindness while exact open risk is proven
P1  named consumer blocked by unavailable/invalid source;
    active operation stuck/degraded
P2  scientific owner decision became available
INFO meaningful change, no action required
UNKNOWN insufficient evidence to rank
```

Never automatically elevate:

```text
ACTIVATION_PATH_GAP
WATCHLIST_SOURCE_GAP
generic TARGET_GAP
legacy provenance gap
unactivated StrategyVersion
absence of mark TTL
```

No numeric severity score.

## 5. Change feed

Only sources with trustworthy native history contribute CHANGE.

```text
RESEARCH   ResearchStore record_id + first_reliable_available_at
OPERATIONS PaperPlane execution event_id + created_at
SYSTEM     CHANGE_HISTORY_UNAVAILABLE unless source already proves chronology
```

Newness uses availability/append order, not effective time alone.
Projection build time and filename mtime are never event time.
Git commits are not the operational change feed.

## 6. Review cursor

Path: `local/factory_v1/owner_review_cursor_v1.json` via the existing
`local/factory_v1` runtime root (same family as other operational JSON).

Stores only schema, `reviewed_at`, per-source watermarks, and
`review_snapshot_sha256`.

GET HOME: 0 cursor writes. POST `MARK_REVIEWED` writes only this file
(atomic temp + replace). Stale snapshot → `STALE_REVIEW_SNAPSHOT`,
zero writes. Unavailable source watermark is not advanced.

Cursor loss/corruption increases visibility; it never hides current P0.

## 7. HOME

```text
ТРЕБУЕТ ВНИМАНИЯ
ИЗМЕНИЛОСЬ С ПРОСМОТРА
ИЗМЕНЕНИЯ БЕЗ ДЕЙСТВИЯ
ПОЛНОТА ИСТОЧНИКОВ
existing lower-level Factory summary
```

Only HOME command: `MARK_REVIEWED`. Domain commands stay on owning
surfaces. Drilldown: `/research`, `/operations`, `/system`.

## 8. Authority collision

```text
OWNER_ATTENTION_AND_CHANGE_FEED_V1 / SEM-OWNER-DAILY-ATTENTION
  ≠ OWNER_ATTENTION_GATE_V2 (delivery merge authority)
```

Product feed never consumes delivery gate state as product evidence.

## 9. Non-claims

NO ALPHA. NO LIVE. NO OWNER FCF. NO SYSTEM HEALTH CLAIM. NO PROVIDER.
NO DEPLOY. NO WALLET. NO ATTENTION DATABASE. NO CANONICAL DONE.
