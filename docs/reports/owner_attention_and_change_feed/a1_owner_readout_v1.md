# OWNER_ATTENTION_AND_CHANGE_FEED_V1 — owner readout

Petr на GET `/` видит одно ежедневное HOME: что требует его сейчас, что
новое с прошлого просмотра, что изменилось без действия, полноту
источников и следующий безопасный шаг. Success = нет material item,
coverage видна, DO NOTHING.

HOME не владеет фактами. Адаптеры только приводят форму Research /
Operations / System. Курсор — checkpoint, не RESOLVED.

## VERDICT

```text
START_WITH_PATCH
OWNER_ATTENTION_AND_CHANGE_FEED_V1_READY_FOR_MERGE
```

## EXACT BASE / HEAD / PR

```text
BASE = ac5c91c3baab36c055ab0e48dbd0ae4d37de2ac4
HEAD = ff779c7148579565adb694ce96e6bec8401d4dfd
PR   = https://github.com/lancerbeta/solana-alpha-lab/pull/277
```

HEAD в этом файле — product freeze до bind-evidence. После evidence-commit
канонический head смотреть в Git / PR.

## OWNER SENTENCE

За ≤30 секунд на HOME: нужно ли Петру что-то сейчас, или можно ничего
не делать, при видимой полноте источников.

## ADAPTERS / CURSOR

- Research: существующий ResearchStore / research projection
- Operations: TradingOperationsProjectionV2 / PaperPlane
- System: существующий runtime / cockpit, всегда `STATE_ONLY`
- Cursor path: `local/factory_v1/owner_review_cursor_v1.json`
- Projection: `OwnerAttentionProjectionV1` (derived, persist nowhere)

## REVIEWED != RESOLVED

`MARK_REVIEWED` пишет только курсор при совпадении
`review_snapshot_sha256`. P0 остаётся в current attention. Потерянный
или битый курсор увеличивает видимость, не прячет P0.

## GIT / RUNTIME

Git panel не делает research `CHANGE_HISTORY=AVAILABLE`. Product Git
не утверждает runtime. SYSTEM не имитирует историю изменений.

## THREE VERTICAL LOOPS

- Current attention: PASS — source-local facts; noise не global; ключ
  `domain:code:native_identity`.
- Change newness: PASS — parsed UTC instant, затем native identity;
  дробные секунды не старше целой секунды watermark.
- Review cursor: PASS — hash-bound; unavailable/invalid watermark
  не двигается; GET HOME = 0 writes.

## SEMANTIC GIT

Новый маршрут `SEM-OWNER-DAILY-ATTENTION` ≠ `OWNER_ATTENTION_GATE_V2`.
Merge/gate вопросы остаются на `SEM-AUTHORITY-BOUNDARIES`.

## COLLISION PROOF

Product daily attention не читает merge-gate state. Delivery gate не
читает HOME cursor.

## TESTS / CRITICS / FIT / CI

Vertical A/B/C + coverage honesty + present-unopenable INVALID +
fractional availability. Isolated CODE / GOAL / ARCHITECTURE PASS на
`ff779c71`.
`packet_fingerprint_sha256=1a682a506137287edf4374a35b5bd3c7ea271bf7729c57cc507724c38ed50534`
Factory Fit FULL_REVIEW PASS. Exact-head CI после evidence push.

## NON-CLAIMS

NO ALPHA. NO LIVE. NO OWNER FCF. NO SYSTEM HEALTH CLAIM. NO PROVIDER.
NO DEPLOY. NO WALLET. NO ATTENTION DATABASE. NO CANONICAL DONE.

## ROLLBACK

Обычный revert. ResearchStore / PaperPlane / Git product bytes не
переписываются. Курсор — local JSON.

## HORIZON

```text
NOW   = NONE
WATCH = SYSTEM_OPERABILITY_SURFACE_V2
```

Move 6 не стартовать автоматически.

## OWNER_ATTENTION_GATE_V2

Stop at merge-readiness. Owner never clicks GitHub Merge.
