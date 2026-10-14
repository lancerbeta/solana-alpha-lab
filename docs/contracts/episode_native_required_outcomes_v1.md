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
Текущий inventory должен отдельно иметь native completeness proof. Законный
пустой inventory выражается complete-empty assignment document существующего
owner; missing/empty/unreadable/incomplete current source даёт HOLDOUT_UNRESOLVED.
Историческая completeness frozen admission не заменяет текущую.

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
