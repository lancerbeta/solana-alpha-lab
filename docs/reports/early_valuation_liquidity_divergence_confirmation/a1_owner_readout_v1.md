# EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1 — owner readout

## Verdict

`OFFLINE_COMPOSITION_READY_LIVE_CAPTURE_REQUIRES_PHRASE`

Entry Gate: `START_WITH_PATCH`. Это не повтор закрытой семьи
EARLY_STRUCTURAL_BACKING: там тестировали абсолютный уровень
`liquidity/mcap`; здесь — фиксированное изменение `X = ln(R1/R0)` на двух
prospective snapshots через 300s. Factory runner не менялся.

Discovery / A7 выключены. Положительный первый sample не даёт SHADOW, alpha,
поиска порога, второго интервала, нового провайдера, кошелька или micro-live.

## Что готово

- YAML policy + WRAP projector + CLI.
- Zero-network тесты: temporal ≠ level; UNKNOWN≠0; fdv reject; R0 age;
  R1 liquidity floor; `createdAt` mismatch; typed stop →
  `INVALID_EVIDENCE_REPLAN`; неверная фраза читает 0 credentials; два search
  вызова; `run_campaign` не вызывается; sign-only score.
- Live capture остаётся за той же exact owner-phrase. Отдельного
  подготовительного атома нет.

## Что не сделано

Свежего provider read нет. Научного терминала ещё нет.

## Единственные научные терминалы

После одной authorized window ровно один из трёх:

- `CLOSE_VALUATION_LIQUIDITY_DIVERGENCE_FAMILY`
- `INVALID_EVIDENCE_REPLAN`
- `EARN_ONE_CONFIRMATORY_FRESH_OOS`

CLI печатает `owner_state=DONE|BLOCKED`, `terminal_outcome` и `next`.
`INVALID_EVIDENCE_REPLAN` и pre-campaign ошибки дают exit 2.

## Live capture

`JUPITER_API_KEY` уже должен быть в process environment. Не читать `.env`.
Не вставлять ключ в команду, URL, лог, receipt или Git.

`--excluded-mints-file` — локальный файл вне Git, непустой JSON:

```json
{"mints":["<prior-consumed-mint>"]}
```

Список — все ранее consumed mints. Пустой или битый файл =
`PRIOR_MINT_EXCLUSION_INPUT_INVALID` → `INVALID_EVIDENCE_REPLAN`.

На PowerShell фразу передавать **single-quoted**: в тексте есть `$0` и `;`.
Double-quoted строка разъедет точное совпадение.

Одно окно. После reservation процесс молча ждёт ~300s, затем ~900s.
Не перезапускать и не жать Ctrl+C, чтобы «попробовать ещё раз»:
повтор = `CREATE_ONLY_EXISTS` → `INVALID_EVIDENCE_REPLAN`, reservation
уже сожжена.

Exact owner phrase:

```
OK EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1: one bounded Jupiter Free-key read-only PIT campaign using a local process-environment key only; Tokens V2 /recent plus two bulk /tokens/v2/search snapshots 300s apart plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 fresh mints only excluding all prior consumed mints; X = ln(R1/R0) from FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO at two prospective search snapshots (mcap != fdv; UNKNOWN never zero); no closed-family threshold, window or quartile reopen; quote-only BUY after the second snapshot and quote-only SELL at H900; one window only; Factory runner unchanged; Discovery, A7, Strategy, Bot, Shadow, alpha, NetReturn and micro-live forbidden.
```

PowerShell live command (подставить локальный excluded-mints path; фраза уже
в single quotes):

```
uv run --locked --managed-python python -B scripts/run_early_valuation_liquidity_divergence_confirmation.py --owner-phrase 'OK EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1: one bounded Jupiter Free-key read-only PIT campaign using a local process-environment key only; Tokens V2 /recent plus two bulk /tokens/v2/search snapshots 300s apart plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 fresh mints only excluding all prior consumed mints; X = ln(R1/R0) from FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO at two prospective search snapshots (mcap != fdv; UNKNOWN never zero); no closed-family threshold, window or quartile reopen; quote-only BUY after the second snapshot and quote-only SELL at H900; one window only; Factory runner unchanged; Discovery, A7, Strategy, Bot, Shadow, alpha, NetReturn and micro-live forbidden.' --excluded-mints-file local/excluded-mints.json
```

## Merge phrase

После exact-head CI, не раньше. Owner никогда не нажимает GitHub Merge.
Шаблон (N и 40-hex подставятся после PR):

```
PR #<N>, head <40-hex> проверен; ready + merge разрешаю.
```

## Non-claims

No alpha, no SHADOW, no NetReturn, no micro-live, no Discovery/A7, no
canonical DONE.
