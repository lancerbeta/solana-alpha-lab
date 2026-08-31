# PathRisk live-window glue — owner readout

Pre-merge terminal: `PATHRISK_LIVE_WINDOW_GLUE_PASS_READY_FOR_MERGE_GATE`.

Это **ремонт executable PathRisk live path**, не новое estimand, не alpha и не live capture. `PATHRISK_SURFACE_INFORMATIVE` значит только: наблюдаемая PathRisk-поверхность невырождена. Это не profitability, не NetReturn и не strategy readiness.

Provider/API/RPC/WSS calls в этом PR = 0. Credential value reads = 0. Cash = 0. Wallet/signer/tx = false.

## Что закрыто

1. Ровно один Tokens V2 `/recent` и ровно один bulk `/tokens/v2/search` как единственный R0 snapshot.
2. Recurring `source_poll` для этого окна выключен. В X300 нет второго `/search`.
3. Hard cap `26` = 1 recent + 1 search + 24 quotes. Retry/fallback = false.
4. Consumed-mint exclusion резолвится детерминированно из Git receipts ∪ RDP `outcome_consumed` на старте окна.
5. Если после exclusion eligible < 4: `CALIBRATION_ELIGIBLE_BELOW_FLOOR`, `quote_calls=0`.
6. `build_readout()` исполняется на реальном completed live window, не только в тестах.
7. Crash/resume не повторяет completed provider occurrence.

## Сейчас — STOP

Не вызывать provider. Не авторизовывать live capture. Не нажимать GitHub Merge.

```
Do not authorize live PathRisk capture. Do not click GitHub Merge.
```

После guarded merge агент заново прогонит read-only `PATHRISK_LIVE_PREEXECUTION_GATE_V1`. Phrase владельцу печатается только если gate вернёт `execution_path.complete=true`, `total_max=26`, `consistent=true`, `population.exclusion_proven=true`.
