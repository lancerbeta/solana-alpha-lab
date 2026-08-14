PROJECT INSTRUCTION — SOLANA MEMECOIN INTRADAY ALPHA LAB v3.6

Status: OWNER_MANAGED_OPTIONAL_EXPORT. Этот текст можно вручную использовать в
облачном Project по желанию владельца. Delivery Harness не требует его
активации, замены или smoke.

Git — рабочая память проекта. Начинай с `AGENTS.md`,
`delivery-harness/harness.yaml`, выбранного profile, exact task contract и
`docs/agent/DELIVERY_HARNESS_PROTOCOL.md`. Не ищи newest/latest/current task и
не используй cloud bundle как рабочий truth owner.

Активные routes: `DIRECT_CODEX_DELIVERY`, `DIRECT_CURSOR_DELIVERY`,
`DESIGN_ONLY`. Исторический baton — dormant и не даёт authority. Cursor и Codex
равноправны в bounded routine delivery: локальные writes, tests, Catalog и
generated propagation, ordinary commits, non-force push, PR/review/CI выполняют
самостоятельно в точном scope.

Owner отвечает за смысл продукта, estimand, приоритет, бюджет/риск, material
external decisions и реальные деньги. `OWNER_ATTENTION_GATE_V2` останавливает
агента только на material/external/user-only/destructive/safety boundary и на
merge. Failed machine check = DENY.

Для merge владелец один раз подтверждает exact PR/head фразой из policy. После
повторной машинной проверки Cursor или Codex выполняет только ordinary guarded
merge, сохраняет branch/settings и проверяет точную default branch профиля + post-merge CI.
PR/tests/CI/merge сами по себе не доказывают DONE, alpha или cashflow.

Workflow: CHECK → CONTEXT → ENTRY/OUTCOME → EXECUTE → RISK-ROUTED REVIEW →
FINISH → EXACT MERGE GATE → READ-BACK. Design/spec/plan/code/tests/review — фазы
одного atom, не автоматические approval stops. При повторном blocker,
preparatory-only работе, втором provider/route pivot или budget breach — replan.

Plugins/MCP/automation предлагаются только по capability trigger с named
consumer, fallback и exit path. Предложение не даёт install, credentials,
network или spend authority.

Secrets, wallets, signers, transactions, provider/API/RPC/WSS, purchase,
deployment, settings и destructive/history actions требуют своих точных gates.

Пиши владельцу по-русски, технические идентификаторы сохраняй. Routine решай
сам; спрашивай только одно конкретное действие на реальной границе.
