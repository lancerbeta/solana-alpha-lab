# Jupiter readonly transport parity — owner readout

Pre-merge: `JUPITER_READONLY_TRANSPORT_PARITY_PASS_READY_FOR_MERGE_GATE`.

## DONE

`JupiterReadonlyOpener` now sends the proven readonly request profile: `Accept: application/json`, `User-Agent: solana-alpha-lab/quote-native-evidence-qualification-v1`, `x-api-key` header-only, explicit no-redirect opener. PR #226 HTTP status/class diagnostics are unchanged. `ACT-PATHRISK-LIVE-001` не трогали.

Provider calls в этом PR = 0. Реальный ключ не читали. User-Agent alone не объявлен причиной 403/200.

## BLOCKED

В этом PR запрещены: Jupiter, `--real-provider`, PathRisk window, reopen `ACT-PATHRISK-LIVE-001`. GitHub Merge не нажимать.

## NEXT

Только merge gate этого PR. Следующий probe или live-run — отдельная authority.

```
Do not authorize a provider call in this PR. Do not click GitHub Merge.
```
