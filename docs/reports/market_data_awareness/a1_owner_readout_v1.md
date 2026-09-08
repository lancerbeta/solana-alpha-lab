# MARKET_DATA_AWARENESS_V1 — owner readout

Petr на GET `/market` за ≤30 секунд видит SCOPE, AS OF, CONTEXT, RELATIVE
STATE, COVERAGE, INTERPRETATION и NON-CLAIMS по tracked early pump.fun
lifecycle population. Это не market platform и не regime predictor.

## VERDICT

```text
START_WITH_PATCH
PRODUCT_FREEZE_PENDING_BIND_EVIDENCE
```

Канонический `DONE` только после exact-head CI, bind-evidence и merge-readiness.

## EXACT BASE / HEAD / PR

```text
BASE = 5feede9b9e66023e6e705710fc2f0b6201a0d30e
HEAD = 3d42b62792cf9caa18451fef93dc8ac50b0b307c
PR   = PENDING
```

После evidence-commit канонический head смотреть в Git / PR.

## OWNER SENTENCE

GET `/market` показывает текущий tracked-cohort context относительно недавней
сопоставимой истории, покрытие и что нельзя заключать. HIGH_RELATIVE значит
только «выше недавней сопоставимой истории». Не return, не trade, не весь
рынок Solana / memecoin / pump.fun.

## VERTICAL LOOPS

- OBSERVE: PASS — current window по `event_time` / `authoritative_anchor`;
  PIT `first_reliable_available_at <= as_of`; unreadable parquet → `UNAVAILABLE`.
- COMPARE: PASS — like-with-like по `context_compatibility_sha256`, не whole
  `schedule_sha256`; mixed current не смешивает raw и N; previous-dependent
  raw не берёт чужой fingerprint.
- INTERPRET: PASS — вектор осей, не BULL/BEAR; Git capability не live context;
  non-claims на экране.

## SOURCE OWNERSHIP

- Git = definition / compatibility
- Observation RDP = observed values
- `/system` = runtime health
- Workbench `/market` = derived read model, 0 provider, 0 writes

## NON-CLAIMS

Нет alpha, NetReturn, expected return, trade/no-trade, market-wide claim,
regime predictor, deploy, provider, LIVE/wallet, canonical DONE.

## NEXT

Owner merge phrase после merge-readiness. Затем guarded merge.
Не стартовать `OWNER_WORKBENCH_VPS_DEPLOY_AND_SMOKE_V1` до merge.

## MODEL_EFFORT

`SOL_XHIGH` на PIT/architecture. `LUNA_MAX` на implementation. Следующий
checkpoint: `ROUTINE_NO_SWITCH` на merge-readiness / guarded merge.
