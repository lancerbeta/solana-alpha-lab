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
используют и `classify_lane`, и HFIC writer. В публичном `classify` все такие
отказы происходят до записи receipt, decision или terminal. Stdout — один JSON
(`status`, `reason_code`, `detail.stage`/`reason_code`/`fields`, `next_action`,
фактические `writes.research_store`). Сессия остаётся `AWAITING_CLASSIFICATION`;
исправленный packet проходит тот же `classify`.

| reason_code | stage | смысл |
|---|---|---|
| `CLASSIFICATION_INPUT_INVALID` | `CLASSIFICATION_INPUT` | оболочка Spec: schema/document, time, capabilities, path; `fields` называет поля |
| `CLASSIFIER_CLOCK_INVALID` | `CLASSIFIER_CLOCK` | переданный `classifier_evaluated_at` будущий, naive или нечитаемый |
| `CLASSIFIER_CONFIG_UNAVAILABLE` | `CLASSIFIER_CONFIG` | registry/schema недоступны: конфигурация, не вердикт |

Время оценки — runtime UTC. Переданный `classifier_evaluated_at` допустим только
aware и не позже runtime (replay/тесты); будущим значением запрет не обходится.
Source, protection, integrity и прочие `DENY_*` с конкретным reason сохраняют
прежний смысл. На уже завершённой сессии revalidation даёт
`EPISODE_CLASSIFICATION_REVALIDATION_DENIED`.

Отказ, записанный до этого ремонта (`DENY_INVALID_SPEC` +
`EXPERIMENT_SPEC_INVALID` → `KILL_UNBOUND_EVIDENCE`), исправляется
append-only, а не переоткрытием науки. Это не `apply-provenance-correction`
(тот исправляет placeholder-время записей). `--data-root` — глобальный флаг до
подкоманды:

```text
hypothesis_forge.py --data-root <root> classification-correction-preview --session-id <S>
hypothesis_forge.py --data-root <root> classification-correction-preview --session-id <S> --experiment-spec <packet.json>
hypothesis_forge.py --data-root <root> classification-correction-apply --proposal <saved preview stdout> --confirm-append-only
```

1. Без `--experiment-spec` preview только читает: `TEMPLATE` с
   `refused_experiment_spec_packet`, причиной, `correctable_fields`,
   `expected_instant` и `refused_at_source`.
2. Скопируйте `refused_experiment_spec_packet`, уберите `classifier_evaluated_at`.
   В `experiment_spec` поставьте и `as_of`, и `availability_cutoff` ровно в
   `expected_instant` — момент исходной оценки, округлённый вниз до секунды.
   Другие значения не принимаются: более поздний cutoff засчитал бы исходы,
   созревшие после оценки. Если на этот момент данные не готовы, это
   `CURRENT_GATE_DENIED`, а не поправка. Другие поля не меняйте.
3. Preview с packet доказывает одновременно:
   - исходный isolated `PASS_TO_CLASSIFICATION` на том же packet и definition;
   - сохранённый запрос заново даёт отказ времени оболочки
     (`SPEC_AS_OF_AFTER_EVALUATION`, `SPEC_AVAILABILITY_CUTOFF_AFTER_AS_OF`,
     `SPEC_TIME_INVALID`) на своё время оценки;
   - изменены только `as_of`/`availability_cutoff` (allowlist), оба = `expected_instant`;
   - хронология Critic PASS ≤ отказанная оценка ≤ эта проверка (с точностью до секунды);
   - сохранённый result всё ещё hash-verified look;
   - свежий classifier на исходных inputs допущен текущими gates. KILL или
     `BLOCKED_DATA` — это отказ без записи, а не поправка.
4. Сохраните весь stdout `PREVIEW_READY` и передайте его в apply.

| reason_code | next_action |
|---|---|
| `CLASSIFICATION_CORRECTION_PREVIEW_STALE` | повторить preview, сохранить новый stdout, затем apply |
| `CLASSIFICATION_CORRECTION_ALREADY_APPLIED` | `show-session`, затем `forge-run --no-write` |
| `CONFIRM_APPEND_ONLY_REQUIRED` | повторить apply с `--confirm-append-only` |
| `CLASSIFICATION_CORRECTION_PACKET_INVALID` / `_SCOPE_FORBIDDEN` / `_TIME_RULE_VIOLATED` | пересобрать packet из TEMPLATE и повторить preview |
| `CLASSIFICATION_CORRECTION_CURRENT_GATE_DENIED` | остановиться: текущий gate запрещает, история сохраняется |
| `CLASSIFICATION_CORRECTION_NOT_INPUT_REFUSAL` / `_ORIGINAL_PASS_UNAVAILABLE` | остановиться: не исправляется, читать сохранённый result |
| `CLASSIFICATION_CORRECTION_SOURCE_UNAVAILABLE` / `_FORK` | остановиться: восстановить exact saved source / разобрать историю |
| `CLASSIFICATION_CORRECTION_PROPOSAL_INVALID` | передать сохранённый stdout preview без изменений |
| `CLASSIFICATION_CORRECTION_CHRONOLOGY_UNPROVEN` | остановиться: порядок Critic PASS ≤ отказ ≤ исправление (по секундам) не доказан |
| `CLASSIFICATION_CORRECTION_SESSION_NOT_COMPLETE` | сессия ещё ждёт классификации: обычный `classify` |
| `SESSION_NOT_FOUND` | проверить `--session-id` и `--data-root` |
| `CLASSIFICATION_INPUT_INVALID` / `CLASSIFIER_*` из preview | исправить названные поля / убрать `classifier_evaluated_at` / восстановить config |

Поле `next_action` в JSON авторитетно; таблица его поясняет.

Apply сверяет parent session receipt и SHA тела поправки (`correction_sha256`),
под writer lease (compare-before-append) пишет в ту же сессию цикл
`COMPLETE-CLSCORR-<sha12>` со своими CRITIC_RESULT, CLASSIFIER_RECEIPT,
SESSION_RECEIPT и решением выбранного кандидата. Цикл несёт
`classification_correction` (refused → corrected, `field_changes` по каждому
полю, refused/corrected capability, accounting `scientific_look_delta=0`).
Исправленная классификация выполнена текущим кодом: её capability epoch —
capability завершения (execution binding выводится из него), исходный остаётся в
`refused`; это единственное разрешённое изменение execution identity, как у
repair continuation. Это единственное разрешённое исключение по capability;
оно не означает, что look и Critic выполнялись текущим кодом: их capability —
`look_capability_epoch_sha256` (= `refused`). Повтор, в том числе одновременный,
возвращает ту же запись; две разные поправки одной
сессии — `CLASSIFICATION_CORRECTION_FORK`. Отказ, исходный owner-final, look
ledger и бюджет остаются в истории; operation не переоткрывается; чтение на
cutoff до поправки показывает прежний REJECT. Receipt помечает
`no_git_fence_receipt.fence_basis=CLASSIFICATION_CORRECTION`.

`load_session_bundle` и `show-session` (`classification_correction`) читают
receipt и lineage активного цикла. Apply возвращает `forge_run_args`.
Aggregate `forge-run` снимает completed readback один раз — только если
сохранённый owner-final указывал на exact отказанный session receipt этой
поправки; после `forge-run --persist` readback — новый receipt. Перед persist на
реальном store сначала `forge-run --no-write`: BASE-стадия должна быть этой
сессией; иначе остановиться.

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
