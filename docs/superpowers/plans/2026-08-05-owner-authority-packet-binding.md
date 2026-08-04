# Owner Authority Packet Binding v1 — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Цель:** Построить offline детерминированный validator, который превращает согласованную владельцем форму technical canary с лимитом USD 3.00 в fail-closed packet для review, не выдавая authority для wallet, signer, transaction, provider, cash или TASK-27.

**Архитектура:** Новый модуль `owner_authority_packet_binding` читает только tracked YAML/JSON fixtures, классифицирует packet как неполный owner draft или complete packet для review и выдаёт детерминированное acceptance evidence. JSON Schema валидирует evidence, а второй test suite связывает новые assets с существующим Catalog и запускает существующий navigation generator.

**Стек:** Python 3 standard library, PyYAML, jsonschema, unittest, JSON Schema Draft 2020-12, YAML/JSON/Markdown и существующий Catalog generator.

## Глобальные ограничения

- Будущий flow строго `SOL -> one exact memecoin -> SOL`; выход немедленный после terminal observation первого этапа и inventory reconciliation.
- `total_cash_at_risk_cap_usd_cents` строго равен `300`; input notional, network, relay/priority, ATA rent и все отдельные fees учитываются до того, как packet может стать готовым к review.
- Отсутствующий token, program, route, публичный адрес wallet, notional, fee cap, quote basis, expiry, monitoring/reconciliation reference или recovery procedure — это `OWNER_INPUT_REQUIRED`, а не default и не ноль.
- `DRAFT_OWNER_INPUT_REQUIRED` и `READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION` — оба неисполняемые состояния: `canary_authority=false`, `task27_authority=false`, numeric NetReturn запрещён.
- Запрещены создание и funding wallet, seed/private key, signed bytes, transaction, simulation, provider/API/RPC/WSS call, cash spend, R3 read, dependency, deployment и strategy logic.
- `UNKNOWN`, неудачная reconciliation первого этапа, monitoring loss, inventory mismatch, route/program mismatch или cap breach блокируют planned exit и каждый retry.
- Использовать контракты `TASK-26C` как hash-bound inputs; не менять артефакты `TASK-26C` и не строить generic execution platform.

---

## Карта файлов

| Путь | Роль |
|---|---|
| `docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md` | Человеко-читаемые scope, owner decision, non-claims, lifecycle и Definition of Done. |
| `docs/contracts/owner_authority_packet_binding_contract_v1.md` | Versioned offline packet contract и точная семантика state/field. |
| `configs/owner_authority_packet_binding_v1.yaml` | Machine-readable constants, согласованный owner cap, required fields, health blocks и TASK-26C hash bindings. |
| `catalog/schemas/owner_authority_packet_binding.schema.json` | JSON Schema для детерминированного acceptance evidence. |
| `tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json` | Synthetic draft, complete-review, cap-breach, unknown, monitoring, inventory и route-negative cases. |
| `src/solana_alpha_lab/owner_authority_packet_binding.py` | Чистый parser/evaluator/evidence writer; без network или signer imports. |
| `tests/test_owner_authority_packet_binding.py` | Тесты contract, fixture, schema, evaluator и deterministic evidence. |
| `docs/evidence/owner_authority_packet_binding/a1_offline_packet_binding_acceptance_v1.json` | Сгенерированный детерминированный acceptance receipt. |
| `tests/test_owner_authority_packet_binding_catalog_factory_fit.py` | Hash-bound тесты Catalog/Factory-Fit receipt. |
| `docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json` | Full Factory Fit, Product Horizon и zero-side-effect receipt. |
| `catalog/assets/core.yaml` | Catalog records и relations для outputs новой задачи. |
| `catalog/assets/lifecycle.yaml` | Lifecycle record, помечающий задачу как authority preparation без execution authority. |
| `catalog/catalog_manifest.yaml` | Регистрация version/checkpoint/schema. |
| `catalog/generated/asset_edges.json`, `docs/PROJECT_MAP.md` | Generated Catalog projections; только регенерировать, не править вручную. |

## Task 1: Offline packet evaluator, contract, schema и adversarial matrix

**Файлы:**
- Create: `docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md`
- Create: `docs/contracts/owner_authority_packet_binding_contract_v1.md`
- Create: `configs/owner_authority_packet_binding_v1.yaml`
- Create: `catalog/schemas/owner_authority_packet_binding.schema.json`
- Create: `tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json`
- Create: `src/solana_alpha_lab/owner_authority_packet_binding.py`
- Create: `tests/test_owner_authority_packet_binding.py`

**Интерфейсы:**
- Потребляет: `CONTRACT-T26C-OWNED-CANARY-READINESS-001` и `EVIDENCE-T26C-A3-CATALOG-FACTORY-FIT-001` по exact SHA-256 из config.
- Производит: `PacketBindingError`, `evaluate_packet(packet) -> dict[str, object]`, `evaluate_exit_precondition(first_leg) -> dict[str, str]`, `build_binding_evidence(repo_root) -> dict[str, object]` и `write_outputs(repo_root) -> str`.
- Инвариант: каждое return value — offline classification, никогда не execution command.

- [ ] **Шаг 1: Написать падающие evaluator/schema tests**

```python
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.owner_authority_packet_binding import (
    PacketBindingError,
    build_binding_evidence,
    evaluate_exit_precondition,
    evaluate_packet,
)

class OwnerAuthorityPacketBindingTests(unittest.TestCase):
    def test_draft_keeps_missing_values_visible(self) -> None:
        result = evaluate_packet({
            "packet_state": "DRAFT_OWNER_INPUT_REQUIRED",
            "flow": "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT",
            "total_cash_at_risk_cap_usd_cents": 300,
            "owner_input_fields": REQUIRED_OWNER_INPUTS,
        })
        self.assertEqual(result["decision"], "OWNER_INPUT_REQUIRED")
        self.assertFalse(result["canary_authority"])
        self.assertFalse(result["task27_authority"])

    def test_complete_packet_is_review_only(self) -> None:
        result = evaluate_packet(COMPLETE_PACKET)
        self.assertEqual(result["packet_state"], "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION")
        self.assertEqual(result["next_action"], "OWNER_EXACT_APPROVAL_REQUIRED")
        self.assertFalse(result["canary_authority"])

    def test_exit_requires_reconciled_first_leg(self) -> None:
        with self.assertRaisesRegex(PacketBindingError, "exit_before_first_leg_reconciliation"):
            evaluate_exit_precondition({"terminal_state": "LANDED_SUCCESS", "reconciled": False})
```

Добавить tests, которые отвергают: cap `301`, fees, подменённые нулём, отсутствующий exact token/program/route, duplicate/ambiguous owner input list, `UNKNOWN_REQUIRES_RECONCILIATION`, `NO_MONITORING`, `INVENTORY_MISMATCH` и `ROUTE_PROGRAM_MISMATCH`. Валидировать generated evidence через `Draft202012Validator` и доказать, что все side-effect counters равны нулю.

- [ ] **Шаг 2: Запустить tests до implementation**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding -v
```

Ожидание: FAIL, потому что `solana_alpha_lab.owner_authority_packet_binding` и перечисленных contract files ещё не существует.

- [ ] **Шаг 3: Реализовать минимальный чистый evaluator**

Создать `src/solana_alpha_lab/owner_authority_packet_binding.py` без imports помимо `hashlib`, `json`, `pathlib`, `typing` и `yaml`. Определить exact constants:

```python
TASK_ID = "OWNER_AUTHORITY_PACKET_BINDING_V1"
FLOW = "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT"
CAP_USD_CENTS = 300
DRAFT_STATE = "DRAFT_OWNER_INPUT_REQUIRED"
READY_STATE = "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION"

class PacketBindingError(ValueError):
    pass

def evaluate_packet(packet: Mapping[str, Any]) -> dict[str, object]:
    state = str(packet["packet_state"])
    _require(packet["flow"] == FLOW, "wrong_canary_flow")
    _require(packet["total_cash_at_risk_cap_usd_cents"] == CAP_USD_CENTS, "cash_cap_must_equal_300")
    if state == DRAFT_STATE:
        _require(set(packet["owner_input_fields"]) == REQUIRED_OWNER_INPUTS, "draft_owner_inputs_mismatch")
        return _decision(state, "OWNER_INPUT_REQUIRED")
    _require(state == READY_STATE, "invalid_packet_state")
    _require(not packet.get("owner_input_fields"), "ready_packet_has_unbound_owner_inputs")
    _require(packet["estimated_total_cost_usd_cents"] <= CAP_USD_CENTS, "cash_cap_breach")
    _require(packet["maximum_separate_fees_usd_cents"] > 0, "separate_fee_cap_missing_or_zero")
    return _decision(state, "OWNER_EXACT_APPROVAL_REQUIRED")
```

`_decision` всегда обязан устанавливать `canary_authority=False`, `task27_authority=False`, `numeric_netreturn="FORBIDDEN"` и `execution_action="NONE"`. `evaluate_exit_precondition` принимает только `LANDED_SUCCESS` с `reconciled=True`, `monitoring_healthy=True`, `inventory_match=True`, `allowlist_match=True` и `fee_cap_ok=True`; он возвращает `EXIT_LEG_SHAPE_VALIDATED_NOT_AUTHORIZED`.

Построить config и contract вокруг этих constants. Fixture должна быть synthetic и не содержать публичный адрес wallet, token mint, реальный route, quote, signature или secret. Schema обязана требовать `side_effect_counters` с шестью нулевыми counters, совпадающими с TASK-26C.

- [ ] **Шаг 4: Сгенерировать и валидировать deterministic evidence**

Run:

```powershell
uv run --locked --managed-python python -c "from pathlib import Path; from solana_alpha_lab.owner_authority_packet_binding import write_outputs; print(write_outputs(Path('.')))"
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding -v
```

Ожидание: receipt — canonical JSON, проходит новую schema, все synthetic cases совпадают, каждый authority counter равен нулю.

- [ ] **Шаг 5: Закоммитить self-contained offline contract slice**

```powershell
git add docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md docs/contracts/owner_authority_packet_binding_contract_v1.md configs/owner_authority_packet_binding_v1.yaml catalog/schemas/owner_authority_packet_binding.schema.json tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json src/solana_alpha_lab/owner_authority_packet_binding.py tests/test_owner_authority_packet_binding.py docs/evidence/owner_authority_packet_binding/a1_offline_packet_binding_acceptance_v1.json
git commit -m "feat: add owner authority packet binding contract"
```

## Task 2: Full Factory Fit receipt и Catalog transaction

**Файлы:**
- Create: `docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json`
- Create: `tests/test_owner_authority_packet_binding_catalog_factory_fit.py`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Regenerate: `catalog/generated/asset_edges.json`
- Regenerate: `docs/PROJECT_MAP.md`

**Интерфейсы:**
- Потребляет: Task 1 receipt, config, schema, fixture, module и test hashes; TASK-26C Factory Fit receipt.
- Производит: десять registered assets: task doc, contract, config, schema, fixture, module, evaluator test, A1 evidence, A2 evidence и A2 Catalog/Factory-Fit test.
- Инвариант: verdict receipt может быть `PASS_WITH_FOLLOWUP`, но `canary_authority` и `task27_authority` остаются false.

- [ ] **Шаг 1: Написать падающие Catalog/Factory-Fit tests**

```python
NEW_IDS = {
    "DOC-OWNER-AUTHORITY-PACKET-001",
    "CONTRACT-OWNER-AUTHORITY-PACKET-001",
    "CONFIG-OWNER-AUTHORITY-PACKET-001",
    "SCHEMA-OWNER-AUTHORITY-PACKET-001",
    "FIXTURE-OWNER-AUTHORITY-PACKET-001",
    "MODULE-OWNER-AUTHORITY-PACKET-001",
    "TEST-OWNER-AUTHORITY-PACKET-001",
    "EVIDENCE-OWNER-AUTHORITY-PACKET-A1-001",
    "EVIDENCE-OWNER-AUTHORITY-PACKET-A2-001",
    "TEST-OWNER-AUTHORITY-PACKET-A2-001",
}

def test_full_factory_fit_keeps_execution_forbidden() -> None:
    assert receipt["factory_fit"]["mode"] == "FULL_REVIEW"
    assert receipt["accepted_result"]["canary_authority"] is False
    assert receipt["accepted_result"]["task27_authority"] is False
    assert receipt["owner_packet"]["all_in_cash_at_risk_cap_usd_cents"] == 300
    assert receipt["owner_packet"]["status"] == "DRAFT_OWNER_INPUT_REQUIRED"
```

Test обязан пересчитать SHA-256 receipt после удаления `receipt_sha256`, проверить, что hash каждого registered asset совпадает с физическим файлом, потребовать, чтобы generated navigation перечисляла каждый новый ID, и потребовать Product Horizon с ровно `now` и `watch`.

- [ ] **Шаг 2: Запустить Catalog test до добавления records**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding_catalog_factory_fit -v
```

Ожидание: FAIL, потому что receipt, registered IDs и Catalog records ещё не существуют.

- [ ] **Шаг 3: Добавить deterministic Catalog и Factory-Fit receipt**

Создать A2 с `FULL_REVIEW`, одним durable NOW follow-up с именем
`EXACT_OWNER_PACKET_INPUT_AND_SEPARATE_CANARY_GATE`, and one WATCH item
`TASK-27_EXECUTION_TRUTH_EVALUATION`. Явно указать, что первый item требует
owner inputs и более поздний separate authority; это не execution task. Все
side-effect counters установить в ноль.

В `core.yaml` создать десять перечисленных ID с `record_version: '1.0'`, exact
file SHA-256 values, `consumers: [OWNER_AUTHORITY_PACKET_BINDING_V1, FACTORY-001]`
и следующими relations:

```yaml
- {relation_type: derived_from, target_asset_id: CONTRACT-T26C-OWNED-CANARY-READINESS-001}
- {relation_type: governed_by, target_asset_id: CONTRACT-OWNER-AUTHORITY-PACKET-001}
- {relation_type: validated_by, target_asset_id: TEST-OWNER-AUTHORITY-PACKET-001}
- {relation_type: produces, target_asset_id: EVIDENCE-OWNER-AUTHORITY-PACKET-A1-001}
```

Зарегистрировать schema в `catalog_manifest.yaml`, монотонно увеличить version
и checkpoint counts, добавить один lifecycle record с decision
`OFFLINE_OWNER_PACKET_READY_NO_EXECUTION_AUTHORITY`, затем регенерировать views:

```powershell
uv run --locked --managed-python python scripts/generate_navigation.py --write
```

- [ ] **Шаг 4: Валидировать Catalog transaction**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding tests.test_owner_authority_packet_binding_catalog_factory_fit -v
uv run --locked --managed-python python scripts/generate_navigation.py --check
```

Ожидание: обе suites проходят; navigation актуальна; каждый receipt hash и asset hash совпадает.

- [ ] **Шаг 5: Закоммитить Catalog closure**

```powershell
git add docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json tests/test_owner_authority_packet_binding_catalog_factory_fit.py catalog/assets/core.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md
git commit -m "feat: register owner authority packet binding"
```

## Task 3: Ограниченная delivery и semantic acceptance

**Файлы:**
- Менять только если validation выявит непосредственно затронутый дефект: файлы из Tasks 1–2.
- Не создавать: wallet, signer, route provider, deployment, UI, Source bundle или TASK-27 artifact.

**Интерфейсы:**
- Потребляет: оба local commits и deterministic receipts из Tasks 1–2.
- Производит: чистый validated delivery candidate плюс exact no-side-effect report.
- Stop boundary: до любого external provider, wallet, funding, transaction, merge или Project Sources action.

- [ ] **Шаг 1: Проверить exact change scope**

Run:

```powershell
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --porcelain
```

Ожидание: изменены только пути design, plan и Tasks 1–2; не появляется local secret, wallet или raw-data path.

- [ ] **Шаг 2: Один раз запустить targeted и full delivery validation**

Run:

```powershell
uv run --locked --managed-python python -m unittest tests.test_owner_authority_packet_binding tests.test_owner_authority_packet_binding_catalog_factory_fit -v
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Ожидание: targeted tests проходят; tracked-only gate не копирует ignored/local inputs и не сообщает о новом skip, скрывающем missing evidence.

- [ ] **Шаг 3: Провести semantic acceptance checklist**

Проверить все следующие пункты по actual bytes до любого push:

```text
packet states are draft/review only
cash cap is exactly USD 3.00 / 300 cents
all unknown input fields remain explicit
UNKNOWN blocks retry and exit
monitoring/inventory/route/cap failures block action
all side-effect counters are zero
canary_authority=false
task27_authority=false
no seed/private key/signed bytes/provider path exists
```

Если любой пункт не проходит, исправить только непосредственно ответственный Task 1–2 file, повторить его targeted test, затем повторить delivery gate, только если candidate fingerprint изменился.

- [ ] **Шаг 4: Закоммитить validation repair, затем push и открыть draft PR**

Запускать только после прохождения semantic checklist:

```powershell
git status --porcelain
git push -u origin owner-authority-packet-binding
gh pr create --draft --base main --head owner-authority-packet-binding --title "feat: bind owner authority packet offline" --body-file docs/superpowers/plans/2026-08-05-owner-authority-packet-binding.md
```

Ожидание: один draft PR с exact head; остановиться до Ready/merge. Pull request description обязан сообщать, что implementation не даёт authority для canary, wallet, signer, transaction, provider, cash или TASK-27.

## Самопроверка плана

- **Покрытие spec:** Task 1 реализует оба packet states, USD 3.00 cap, immediate-exit precondition, явные missing inputs, schema и adversarial cases. Task 2 реализует Catalog, Factory Fit, Product Horizon и durable no-authority evidence. Task 3 проверяет exact scope и delivery без расширения в external execution.
- **Проверка placeholders:** нет `TODO`, `TBD`, undefined interface или implicit external action. `OWNER_INPUT_REQUIRED` — намеренное runtime value, не placeholder.
- **Согласованность типов:** Task 1 определяет каждый module symbol, используемый его tests. Task 2 читает Task 1 hashes и receipt. Task 3 вызывает только два test modules и существующие validation commands репозитория.
