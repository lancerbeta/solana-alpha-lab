# HFIC fast lane: definition hash

Голый ExperimentSpec больше не получает `FAST_LANE_READY`. Classify принимает spec только вместе с `hypothesis_definition_sha256` замороженного кандидата. Иначе результат — `HYPOTHESIS_DEFINITION_UNBOUND`.

`HYP-*` и `HFIC-CAND-*` не уравниваются. Совпадение feature ids само по себе Fast Lane не открывает. Совпавший hash по-прежнему проходит существующий PIT gate. Receipt записывает `hypothesis_version` из spec.

Стратегии и текст manifest 1.0 этот PR не меняет.
