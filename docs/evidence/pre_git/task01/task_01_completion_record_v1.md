---
task_id: TASK-01
record_version: "1.0"
title: Source/provider manifest
final_status: DONE
completion_scope: DESIGN_AND_STATIC_VALIDATION_ONLY
entry_verdict: START_AS_WRITTEN
completed_at: 2026-07-18
owner: user+assistant
blocker: NONE
state_change: DELTA-01-001_PENDING_USER_ACTIVATION
contains_secrets: false
api_rpc_provider_requests_executed: false
accounts_created: false
purchases_executed: false
real_money_actions: false
---

# TASK-01 — Completion record

## Objective

Create an auditable source/provider and reusable-data contract before workstation, schema, raw envelope and controlled provider validation. Prevent provider-driven schema design, survivorship bias, fabricated point-in-time availability and execution illusion.

## Scope actually completed

- Provider-neutral D01–D20 research/execution/economics domain inventory.
- RC-001 and plausible-next-family hypothesis/data coverage.
- Primary/fallback product mapping with explicit forward-only and unresolved gaps.
- T0/T1/T2 option-value, cadence, retention, credit/cash and stop policies.
- Official-doc provider/product/auth/pricing/payment evidence as of 2026-07-18.
- Public/OSS data/router/decoder/software candidate review under `ADOPT → WRAP → FORK → BUILD`.
- Conditional zero-cash provider decision and beginner just-in-time account checklist.
- Frozen TASK-07 smoke design with 34 cases, 35 planned attempts, hard cap 50 and no transaction/payment paths.

## Validated artifacts

| Artifact | Version/status | Downstream consumers |
|---|---|---|
| `sources_v1.yaml` | 1.0 / validated | TASK-04/05/06/07/08+ |
| `hypothesis_data_coverage_matrix_v1.md` | 1.0 / validated | TASK-05/20/28 |
| `data_option_tiers_v1.yaml` | 1.0 / validated | TASK-05/10/16/20 |
| `provider_cost_snapshot_v1.csv` | snapshot / validated | TASK-04/07/15/47 |
| `reuse_candidate_registry.yaml` | 1.0 data subset / validated | TASK-03/04 |
| `provider_decision_v1.md` | 1.0 / validated | TASK-04/07 |
| `provider_account_checklist_v1.md` | 1.0 / validated | TASK-07 Entry Gate |
| `provider_smoke_spec_v1.yaml` | 1.0 design / frozen, not executed | TASK-07 |
| `task_01_final_gap_audit_v1.md` | 1.0 / tested pass | Canonical handoff and audit |

Exact content hashes are recorded in the completion bundle checksum file.

## Decisions

1. Initial cash cap is `$0`; no paid plan before a reproducible measured bottleneck and user approval.
2. Helius Free is the conditional raw RPC/WSS candidate; Solana Tracker Free is the conditional indexed comparison.
3. Jupiter Swap v2 `/order` quote-only is the primary executable quote candidate; hosted Raptor GET quote is a bounded second-router comparator, not validated fill evidence.
4. Birdeye and paid/self-hosted paths remain deferred until a named measured gap.
5. Historical catalogs may support discovery/backfill/cross-check but never fabricate historical `observed_at` or `available_to_strategy_at`.
6. No account or key is needed until TASK-07 prerequisites close.
7. The user's payment preference is active: among goal-feasible services, prefer a service accepting at least one cryptocurrency supported by that service; fiat-only exception requires explicit user approval.

## Tests and acceptance

- Final DoD: 16/16 requirements `PASS` or `PASS_PENDING_USER_ACTIVATION` for the locally validated handoff.
- YAML/CSV parse and structural validation: `PASS`.
- Domain/tier/source reconciliation: `PASS` after `T01-GAP-001` repair.
- Smoke dependency graph, counts, caps and safety boundary: `PASS`.
- Secret-pattern scan: `PASS`.
- Provider/API/RPC requests: `0`.
- Accounts and purchases: `0`.
- Runtime/provider truth: explicitly `NOT_TESTED`.

## Limitations

The design does not prove endpoint availability, universe completeness, parser quality, quotas, latency, quote overlap or fillability. Open evidence states remain assigned to TASK-07 and later pilots.

## Architecture/access delta

`DELTA-01-001`: validated source/data-option/cost/reuse/smoke contracts now exist in the pre-Git durable artifact archive. Provider connections, accounts, secrets, collectors, DB and runtime remain absent. Canonical activation requires the user's manual Project Sources/Instruction replacement.

## Handoff

```text
TASK-01: DONE
active_candidate: TASK-02 READY
last_validated: TASK-01
blocker: NONE
next: TASK-03 after TASK-02 DONE
user_action_before_next_session: install the coordinated seven-file handoff and paste Project Instruction v2.8
provider_requests: remain prohibited until TASK-07
```

At TASK-03, import all validated TASK-01 artifacts, their hashes and validation evidence into the new private Git registry. Preserve origin/version/history and validate the importing commit from a clean clone.

Exact next-session command after installation:

> Продолжаем проект. Кандидат: TASK-02. Сначала выполни Task Entry Gate; не начинай автоматически и выдай полную Beginner Task Brief, затем только первый безопасный атом.

