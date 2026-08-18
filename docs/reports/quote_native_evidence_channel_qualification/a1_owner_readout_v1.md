# Quote-native evidence channel — итог для владельца

## Вердикт

Текущий quote-native alpha-маршрут **закрыт/поставлен на паузу**:
`PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE`, причина
`INVALID_CAPTURE_CONTRACT`.

Численные пороги этого единственного Free-key запуска **выполнены**.
Evidence-fit **не принят**. Это не alpha, не NetReturn, не causal mechanism и
не разрешение на mechanism audition / MOVE 2.

## Что именно разблокировалось

После серии keyless атомов с `HTTP 429` и `SAMPLE_INVALID` теперь ясно:

1. Keyless quota и структурная непригодность канала — разные вещи.
2. Jupiter Free API key + глобальный pace `>=3s` дал 50 bounded GET без
   `429`: 10 complete X/Y (порог 10), 8 time-separated (порог 6), обе
   strata, TRADED control kill не сработал.
3. Этот конкретный campaign **нельзя** принять как evidence substrate:
   в каноническом receipt нет hash-bound capture-time и нет доказанного
   attempt-marker до чтения ключа. Portal logs подтверждают пакетные
   окна H900/H3600, но не identity каждой из 50 строк.

Итог: диагностический застой снят; зелёный свет на mechanism trial не
открыт. Контракт запрещает автоматический второй campaign.

## Наблюдённые факты

- Заморожен outcome-blind cohort: 6 RECENT и 6 TRADED.
- 50 GET: Token API 2× HTTP 200; Swap API 42× HTTP 200 и 6× HTTP 400.
  Шесть 400 сохранены как typed missing, не как ноль.
- Один credential read, ноль retry/fallback, нет taker/build/execute/
  wallet/signer, cash spend = $0.
- Scorer в runtime receipt пишет `QUOTE_NATIVE_EVIDENCE_FIT_PASS`. Это
  только numeric floors, не acceptance.
- `Content-Type` убран из Git-receipt до поставки (sanitized candidate);
  этот header больше не текущий blocker.
- v9 registry фиксирует, что три Free-key маршрута **наблюдались**.
  Наблюдение ≠ accepted evidence-fit и не даёт call authority.

## Почему PASS не принят

1. Canonical runtime не содержит hash-bound `observed_at` на строках.
   Filesystem `mtime` — только upper bound.
2. Attempt reservation до credential read в этом запуске не доказана
   каноническим receipt.
3. Portal reconciliation подтверждает batch windows, не 50-row identity
   (request ID намеренно не сохранялись).

Исправления runner после запуска (userinfo URL, transaction-scan,
deadline после call, timestamp после raw write) действуют только на
будущий отдельно авторизованный контракт.

## Следующее решение владельца

Ровно одно:

- оставить quote-native на паузе; или
- явно авторизовать **новый** recapture-контракт с уже hardened runner.

Автоматический replacement campaign, paid plan, второй provider, H13/H11/H07/H02
unpark и mechanism audition сейчас запрещены.

## Ограничения

- H14400 остаётся explicit gap.
- Шесть HTTP 400 `/order` остаются typed missing.
- Даже принятый numeric sample квалифицировал бы только evidence
  substrate этого contour, не execution fitness и не provider reliability.
