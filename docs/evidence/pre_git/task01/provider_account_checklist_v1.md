---
artifact_id: SMIAL_TASK_01_PROVIDER_ACCOUNT_CHECKLIST
artifact_version: "1.0"
task_id: TASK-01
task_execution_status: DONE
artifact_status: VALIDATED_JUST_IN_TIME_CHECKLIST
owner: user+assistant
as_of: 2026-07-18
execution_now: PROHIBITED_NOT_NEEDED
accounts_created: false
purchases_executed: false
contains_secrets: false
---

# TASK-01 — Provider account checklist для новичка

## 1. Что делать сейчас

**Ничего.** Этот файл — инструкция для just-in-time шага перед TASK-07, а не приглашение регистрироваться сегодня.

Аккаунты создаются только после:

1. TASK-02 подготовил workstation и локальное место для secrets;
2. TASK-03 создал `.gitignore`/secret scanning;
3. TASK-06 создал redacted raw envelope;
4. TASK-07 повторно подтвердил, что provider всё ещё входит в frozen spec.

## 2. Минимальный будущий набор

| Provider | Сейчас | Когда может понадобиться | Платёж |
|---|---|---|---|
| Helius Free | Не создавать | Перед TASK-07, если остаётся primary RPC/WSS | Не требуется |
| Solana Tracker Data Free | Не создавать | Перед TASK-07, если остаётся indexed comparison | Не требуется |
| Jupiter | Не создавать | Только если актуальный official contract действительно требует API key; keyless перепроверяется первым | Не требуется |
| Raptor hosted beta | Не создавать | Auth/terms проверяются; только GET quote comparator | Не требуется по текущим docs |
| Birdeye Standard/x402 | Не создавать | Только при named measured gap после initial smoke | x402 запрещён без отдельного signer/cost approval |
| Dune | Не создавать | Только для утверждённого bounded historical query | Не требуется сейчас |

## 3. Перед регистрацией: security preflight

- [ ] Открыта только официальная domain/URL из `sources_v1.yaml`; ссылка не пришла из рекламы, DM или Telegram.
- [ ] Используется уникальный пароль из password manager.
- [ ] Включён MFA, если provider предлагает его.
- [ ] Recovery codes сохраняются в password manager/offline secure location, не в Git/чат/Project Sources.
- [ ] Устройство обновлено; browser extension и remote-control software проверены.
- [ ] В проекте уже существует локальное секретное хранилище из TASK-02/03.
- [ ] Известен конкретный consumer/case из `provider_smoke_spec_v1.yaml`.
- [ ] Provider terms/region/privacy повторно проверены.
- [ ] Paid checkout не открывается: initial plan должен быть `$0`.

## 4. Во время регистрации

Пользователь выполняет UI-действия самостоятельно. Ассистент может объяснять поля, но никогда не просит показать или вставить:

- API key/token или его фрагмент;
- cookie/session ID;
- seed/private key;
- wallet backup;
- recovery code;
- billing receipt/transaction hash;
- screenshot страницы, где может отображаться secret.

Если dashboard показывает key сразу после создания:

1. скопировать его непосредственно в локальный secret store;
2. дать переменной нейтральное имя, например `HELIUS_API_KEY`;
3. не вставлять value в terminal history, chat, Git, Markdown, YAML или screenshot;
4. закрыть/очистить экран;
5. сообщить ассистенту только `credential stored locally: YES`.

## 5. Что можно сообщить ассистенту

Только sanitized attestation:

```text
provider: <HELIUS|SOLANA_TRACKER|JUPITER|...>
account_created: YES|NO
plan_label: <Free/Keyless/...>
dashboard_monthly_allowance: <number or UNKNOWN>
dashboard_rate_limit: <number/unit or UNKNOWN>
payment_rail_visible: <crypto|fiat_only|unknown|not_applicable_free>
credential_stored_locally: YES|NO|NOT_REQUIRED
MFA_enabled: YES|NO|NOT_OFFERED
region_or_terms_blocker: NONE|PRESENT_NO_DETAILS
```

Не сообщать email, имя, wallet address, key prefix/suffix, invoice ID или screenshot.

## 6. Provider-specific будущие шаги

### Helius Free

- [ ] Recheck official Free plan/credits/RPS.
- [ ] Создать один project/key только для research smoke.
- [ ] Ограничить/rotate key, если dashboard поддерживает.
- [ ] Сохранить только локально.
- [ ] Не создавать webhook и не включать auto crypto wallet authorization.
- [ ] После smoke проверить dashboard credit delta и записать только число.

### Solana Tracker Data Free

- [ ] Recheck Free request allowance и RPS.
- [ ] Создать один research key.
- [ ] Не покупать Advanced/Premium/Datastream.
- [ ] Paid payment rail не угадывать; attestation нужна только при реальном upgrade decision.

### Jupiter

- [ ] Сначала повторно открыть official Plans и Swap auth docs.
- [ ] Если keyless реально работает в frozen contract — аккаунт не создавать.
- [ ] Если official current contract требует key — создать только Free API project.
- [ ] Не вызывать `/execute`, `/submit`; не указывать `taker`, `payer`, `receiver` в quote-only smoke.

### Raptor hosted beta

- [ ] Повторно проверить beta status, auth, terms, base URL и quote schema.
- [ ] Не скачивать/self-host binary.
- [ ] Использовать только GET `/health` и GET `/quote`, если case остаётся утверждён.
- [ ] Не вызывать `/swap`, `/swap-instructions`, `/quote-and-swap`, `/send-transaction` или transaction status.

### Birdeye

- [ ] Не создавать account в initial smoke.
- [ ] Standard добавляется только при named coverage gap.
- [ ] x402 требует отдельного payment/signer ADR, disclosed route price и explicit user approval.
- [ ] Не подключать production wallet и не разрешать autonomous payment.

## 7. Stop/revoke/recovery

Остановиться и ничего не продолжать, если:

- UI требует карту/платёж для заявленного Free plan;
- требуется wallet connect/signature;
- domain отличается от official evidence;
- browser/password manager предлагает вставить secret в чат;
- dashboard limit/plan materially отличается от spec;
- regional/terms restriction неясна;
- невозможно отделить research key от production wallet/signer.

При подозрении на утечку:

1. revoke/rotate provider key в dashboard;
2. остановить smoke runner;
3. не публиковать leaked value в incident report;
4. записать только provider, время, affected scope и rotation status;
5. проверить Git/logs/shell history; удалить secret безопасным способом и считать старый key скомпрометированным.

## 8. Handoff

```text
user_action_required_now: NONE
account_state_all_candidates: NOT_CREATED_OR_NOT_REQUIRED
next_user_action: only after final TASK-01 handoff and prerequisite tasks
```
