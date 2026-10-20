# Native episode required outcomes — ExperimentSpec 1.4

ExperimentSpec 1.4 передаёт замороженный episode-native рецепт в штатный HFIC
classifier. Оператор получает сохранённую готовность повторно используемого
research artifact. Научное принятие гипотезы требует отдельного evidence.

Выбирать версию по population и рецепту, а не по версии Critic packet:

| Вход | Версия и действие |
|---|---|
| Raw X/Y | Existing 1.0–1.3 owners; required-outcome contract 1.3 |
| OPPORTUNITY_EPISODES + episode_query 1.2 + frozen fixed-time proxy | 1.4, REUSE_ONLY / EXPLORATORY_REUSE |
| Другой episode recipe или collection mode | Exact unsupported/invalid terminal; никакого raw fallback |

Schema: `catalog/schemas/experiment_spec_v1_4.schema.json`. Loader:
`factory.experiment_spec.validate_experiment_document`. Product projection:
`factory.episode_required_outcomes.project_episode_required_outcomes`.
Штатная поверхность: existing `apply-classification` после сохранённого Critic
`PASS_TO_CLASSIFICATION`; cold `load_session_bundle` возвращает старый receipt.
Повтор действия классификации заново проверяет источники и current protection.
Текущий inventory должен отдельно иметь source-owned completeness proof.
Единственный current owner — `factory.episode_current_protection` с explicit
source set `configs/episode_current_protection_sources_v1.yaml`. Native assignment
1.0 envelope сохраняется; additive completeness metadata связывает exact root,
read role, source versions/frontier и immutable installation receipt. Raw
complete-empty или historical admission pin сами не являются current authority.
Доказанный scoped complete-empty допустим после metadata assessment всех
обязательных owners и отдельно разрешённой установки. Missing/unknown источник
остаётся HOLDOUT_UNRESOLVED с source detail. TASK-22 v2 DENY остаётся у своего
TASK-21 dataset; UNBOUND List A не является confirmatory grant. `checked_at`
не TTL; compatible cohort и обычные CHECK не требуют ручного renewal.

Fixed-time binder, classifier, native discovery и fragment runner используют
один resolver. Current namespace проверяется заново перед actual value loader,
включая frozen callers, которым не нужен mutable corpus pointer. Frozen release
integrity и per-mint interval intersection проверяются отдельно; protected subset
не удаляется из denominator. Source-specific metadata proof не сбрасывает market
identity/budget и не перепривязывает старый saved result к новому capability SHA.
Test fixture устанавливает proof только в полностью контролируемом disposable
consumer через тот же native preview/apply; gate не monkeypatch-ится в ALLOW.

Весь existing envelope сохраняется. Обязательны exact selected definition,
frozen `parameters.temporal_recipe` из Critic packet, native census/observations,
release/manifest/schedule byte и semantic hashes, frozen research scope и
universe policy. Для native HFIC alias direct handoff дополнительно связывает
`parameters.hfic_replay_session_id` с завершённой native session.

```json
{
  "schema_version": "1.4",
  "population": "OPPORTUNITY_EPISODES",
  "capability_id": "CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001",
  "observation_request": {
    "collection_mode": "REUSE_ONLY",
    "requested_evidence_role": "EXPLORATORY_REUSE"
  },
  "required_outcomes": [
    {"point_id": "E14400", "field_ids": ["FIELD-USD-PRICE-001"], "role": "PRIMARY"}
  ]
}
```

Это фрагмент, не полный executable Spec. Envelope, budget, data/implementation
bindings и recipe берутся у существующих owners. PRIMARY должен точно покрывать
exit-point PRICE_RELATIVE_PROXY исходного рецепта. X/Y, неизвестные E-точки,
чужие поля, conflicting roles и raw scheduler shape запрещены.

Admission identity — episode_id. Повторный mint в другом разрешённом цикле
остаётся другим эпизодом. D — все native decision-eligible admissions до чтения
будущих исходов. M — native match; C — native contrast: для
MATCHED_VS_DECISION_ELIGIBLE C=D и пересечение разрешено. UNKNOWN/INVALID scope
не превращается в FALSE. Native NOMINATION_T0, assigned/availability clocks,
policy thresholds и feature bindings сохраняются.

Сначала opaque source hashes, identities и protection; затем scope metadata;
значения читаются только для exact episode/point/field dependencies до decision.
Будущий target читается как metadata, без typed_value. COMPLETE требует каждый
required cell OBSERVED на всём D. Missing/late/censored/absent не уменьшает D.
Incomplete data вне required horizon не создаёт veto.

| Terminal/reason | Следующее действие |
|---|---|
| FAST_LANE_READY | Рассмотреть отдельно разрешённое artifact execution; readiness не PROMOTE |
| EPISODE_OUTCOME_COVERAGE_UNRESOLVED | Отчёт coverage с неизменным D; не сжимать N, не запускать collection автоматически |
| HOLDOUT_PROTECTED / HOLDOUT_UNRESOLVED | Остановить новое действие; проверить protection owner, не исключать защищённый subset |
| Integrity/query/definition/source/schedule conflict | Исправить exact binding штатным owner; не редактировать hashes или исторический receipt |
| EPISODE_CLASSIFICATION_REVALIDATION_DENIED | Сохранённый historical receipt доступен; fresh action запрещён |

## Отказ входа и исправление записанного отказа

Невалидная оболочка Spec — это отказ входа, а не вердикт гипотезы.
`lane_classifier.spec_input_refusal` — единственная проверка оболочки; её
используют и `classify_lane`, и HFIC writer. В публичном `classify` она
срабатывает до записи receipt, decision или terminal. Ответ —
`CLASSIFICATION_INPUT_INVALID` (JSON: `detail.stage`, `reason_code`, `fields`,
`classifier_evaluated_at`, `next_action`, фактические `writes`). Сессия остаётся
`AWAITING_CLASSIFICATION`; исправленная оболочка проходит тот же `classify`.
Время оценки — runtime UTC; подставлять будущее `classifier_evaluated_at`
нельзя. Сбой registry, source, protection и прочие `DENY_*` с конкретным
reason сохраняют прежний смысл.

Отказ, записанный до этого ремонта (`DENY_INVALID_SPEC` +
`EXPERIMENT_SPEC_INVALID` → `KILL_UNBOUND_EVIDENCE`), исправляется
append-only, а не переоткрытием науки:

```text
hypothesis_forge.py classification-correction-preview --session-id <S> --experiment-spec <packet.json>
hypothesis_forge.py classification-correction-apply --proposal <saved preview stdout> --confirm-append-only
```

Packet содержит только `experiment_spec` и `hypothesis_definition_sha256`.
Preview доказывает одновременно:
- исходный isolated `PASS_TO_CLASSIFICATION` на том же packet и definition;
- сохранённый запрос заново даёт тот же отказ оболочки на своё время оценки;
- изменены только поля, названные этим отказом. Ключи вопроса, recipe,
  bindings, outcomes и scope запрещены; исправленное время не раньше Critic PASS;
- свежий classifier на исходных inputs проходит текущие gates.

Научный KILL, runner-up, repair continuation, иной receipt или вторая
поправка отказывают. Apply сверяет parent receipt и proposal SHA, пишет в ту же
сессию цикл `COMPLETE-CLSCORR-<sha12>` со своими CRITIC_RESULT, CLASSIFIER_RECEIPT,
SESSION_RECEIPT и решением выбранного кандидата. Цикл несёт
`classification_correction` (refused → corrected, diff полей, accounting
`scientific_look_delta=0`). Повтор возвращает ту же запись. Отказ, исходный
owner-final и бюджет остаются в истории; operation не переоткрывается.
`load_session_bundle` читает receipt, связанный с активным циклом. Aggregate
`forge-run` снимает completed readback один раз — только если сохранённый
owner-final указывал на exact отказанный session receipt этой поправки. Новый
`forge-run --persist` становится readback.

`episode_outcome_binding` в classifier receipt связывает Spec/definition/recipe,
sources, current protection, policy/scope, exact membership и required coverage
через canonical binding_sha256. Caller projection не является authority.
FAST_LANE_READY и COMPLETE не DIRECT qualifying evidence, chronological
confirmation или permission для StrategyVersion, activation, PAPER и PROMOTE.
Capability остаётся offline RESEARCH_ARTIFACT с promotion_authority NONE.

Rollback — ordinary revert новых code/schema/docs. Existing 1.0–1.3 остаются
читаемыми; scientific/audit KILL и synthetic receipts не переписываются.

Proof: `tests/test_episode_native_required_outcome_contract_v1.py`, native
producer fixture `tests/fixtures/episode_native_required_outcomes_v1/proof.py`.
Setup MAIN looks считаются отдельно; classify/projection/cold readback создают
ноль новых scientific looks. Следующий scope — separately authorized accepted
chronological validation producer/consumer для исходного estimand.
