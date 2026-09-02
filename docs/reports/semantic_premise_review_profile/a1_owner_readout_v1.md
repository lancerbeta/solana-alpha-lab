# SEMANTIC_PREMISE_REVIEW_PROFILE_V1 — owner readout

## Terminal

```text
SEMANTIC_PREMISE_REVIEW_PROFILE_PASS_READY_FOR_MERGE_GATE
```

## Что изменилось?

У `ARCHITECTURE_CRITIC` появился профиль `SEMANTIC_PREMISE` (не четвёртая
merge-роль). При материальном semantic risk delivery-review делает
`classify` → frozen packet → fail-closed `validate-launch` → isolated critic
с packet+diff без implementation transcript.

## Что именно атакует профиль?

Premises: estimand, evidence admissibility, UNKNOWN→negative, family/global
closure, lifecycle authority, harness/merge meaning — когда путь или
`SEMANTIC_PREMISE_HIGH_RISK: true` детерминированно выбирает профиль.

## Честность независимости

Packet `independence.claim_scope = PACKET_INFORMATION_PATH`: доказывает только
исключение transcript из пакета и candidate-bind. `launch_isolation =
PROCESS_OBLIGATION` — живая изоляция запуска не «доказана» builder'ом.
`model_diversity` по умолчанию `UNPROVEN`; `PROVEN` требует явный identity.

## Machine packet

```text
FOURTH_REVIEW_ROLE = false
OWNER_GATE_CHANGED = false
MERGE_SCHEMA_CHANGED = false
FORGE_RUNTIME_CHANGED = false
TRIGGER = path_prefix OR exact_marker OR force_profile
PACKET_BOUND = true
IMPLEMENTATION_TRANSCRIPT_IN_PACKET = false
STALE_INVALIDATES = true
CONTEXT_ISOLATION = PACKET_INFORMATION_PATH
MODEL_DIVERSITY = UNPROVEN
SMOKE_ROUTINE_STANDARD = PASS
SMOKE_FALSE_GLOBAL_CLOSURE = NOT_READY
SMOKE_BOUNDED_CLOSURE = PASS
PROVIDER_CALLS = 0
```
