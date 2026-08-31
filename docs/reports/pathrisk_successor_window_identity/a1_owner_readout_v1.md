# PathRisk successor window identity — owner readout

Pre-merge: `PATHRISK_SUCCESSOR_WINDOW_IDENTITY_PASS_READY_FOR_MERGE_GATE`.

## DONE

Обычный `CALIBRATION_ELIGIBLE_BELOW_FLOOR` больше не требует Git/PR, чтобы открыть следующее чистое PathRisk-окно.

Git policy теперь **стабильные successor-правила**, а не `activation_id: ACT-PATHRISK-LIVE-00N`. Runtime биндит `ACT-(N+1)` из явных CLI-аргументов и детерминированной owner phrase. ACT-001 и ACT-002 остаются неизменным историческим local state.

Provider calls в этом PR = 0. Ключ не читали. Live ACT-003 не исполняли.

## BLOCKED

В этом PR запрещены: Jupiter, `--real-provider` live ACT-003, Forge, supply watcher. GitHub Merge не нажимать.

## NEXT

После merge, zero-network preflight против уже существующего local ACT-002 BELOW_FLOOR journal:

```
uv run --locked --managed-python python -B scripts/early_quote_surface_pathrisk_calibration.py successor-preflight --data-root <factory-data-root>
```

Команда печатает `exact_future_owner_phrase` для ACT-003. Фраза не исполняется этим PR. Renderer не потребляет authority.

ACT-002 phrase и ACT-001 phrase **consumed**. Они не авторизуют ACT-003.

Informative/COMPLETE predecessor ordinary successor не даёт.

```
Do not authorize ACT-PATHRISK-LIVE-003 in this PR. Do not click GitHub Merge.
```
