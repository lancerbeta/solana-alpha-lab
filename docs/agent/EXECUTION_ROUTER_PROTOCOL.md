---
protocol_id: DELIVERY_EXECUTION_ROUTER_V1
status: ACTIVE
as_of: '2026-08-14'
truth_owner: DELIVERY_HARNESS_V1
---

# Execution Router Protocol

This protocol elects one route for an exact bounded Git task. The route stays
fixed for the candidate fingerprint and context receipt.

## Active routes

| Route | Actor | Use | Merge |
|---|---|---|---|
| `DIRECT_CODEX_DELIVERY` | Codex | bounded repository delivery | exact owner PR/head approval plus machine gate |
| `DIRECT_CURSOR_DELIVERY` | Cursor | bounded repository delivery | exact owner PR/head approval plus machine gate |
| `DESIGN_ONLY` | either | read-only design/review with no delivery mutation | forbidden |

`LEGACY_GITHUB_BATON_DORMANT` is historical and inactive. It cannot select a
task, receive a new atom, grant execution authority or merge. Historical bytes
remain under `docs/agent/GITHUB_BATON_PROTOCOL.md`, scripts, fixtures and tests.

## Route election

Use `DESIGN_ONLY` when no repository mutation or delivery evidence is needed.
Use the direct route matching the active agent when an exact task contract and
bounded objective exist. Never route from recency, a branch name, Issue, PR,
commit, tests or a historical baton receipt.

The elected route receives routine autonomy from `AGENTS.md` and
`control/owner_attention_gate_v2.yaml`. A stricter task contract wins. A route
change is `ACTIVE_ROUTE_CHANGED`: stop, replan and issue a new context receipt.

## Context and status

Git is working project memory. Generate bounded context through
`scripts/delivery_harness.py context` from an exact task contract. Cloud Project
Sources or Project Instruction are `OWNER_MANAGED_OPTIONAL_EXPORT`; never read
them as active context, request replacement/smoke or block execution/DONE on
them.

Repository bytes, tests, PR, CI and merge establish technical evidence only.
The exact Git task's Finish Gate owns semantic acceptance and canonical DONE.

## Validation ownership

During implementation run targeted checks only. After bootstrap, the guarded
merge owns the one project-bound gate execution for the unchanged candidate:
it runs the base-bound focused command and consumes existing exact-head PR CI,
or machine-selects `--tracked-only-delivery` when that primary route is
ineligible. Never run the same local full gate once before PR and again at
merge. `CI_OWNED_DELIVERY_PILOT` remains an observation policy inside this
route: focused work is capped at 120 seconds and the three-observation
keep/repair/rollback rule remains unchanged. The first harness installation is
the sole exception: because v2 does not exist on its frozen base, the
predecessor exact-owner route requires one pre-PR tracked-only gate.

The exact pilot command retained for policy verification is
`uv run --locked --managed-python python -B scripts/validate_ci.py --ci-owned-delivery`.
`GITHUB_PR_EXACT_HEAD_CI` admits the next three eligible observations; record
`observation N/3`, require 3/3 and seven minutes saved, and do not admit a
fourth before keep/repair/rollback. A missed clean-checkout defect falls back
to `--tracked-only-delivery`.

## Owner attention and guarded merge

Routine bounded local/GitHub delivery continues without micro-approval. Stop
for the material/external/user-only/destructive/safety gates in
`OWNER_ATTENTION_GATE_V2`.

Both direct routes stop for exactly:

`PR #<number>, head <40 lowercase hex> проверен; ready + merge разрешаю.`

The owner never clicks GitHub Merge. After that phrase, the elected direct
agent runs `scripts/owner_attention_gate.py --guarded-merge`. Harness or
control PRs bind a local `LIVE_PR_HEAD` receipt; product tasks still bind an
exact task contract.

Immediately before mutation re-read repository, PR, head, mergeability,
required tests/CI/full gate/Factory Fit, write set, secret scan, unresolved
reviews, standard-merge mode, branch preservation and settings. A stale head or
failed check is `DENY`, not a human override prompt. On `AUTONOMOUS`, perform
one ordinary merge, preserve the feature branch/settings and read back exact
the profile's exact default branch plus its post-merge CI.

## Startup

1. Read `AGENTS.md`, harness and elected profile.
2. Run `scripts/delivery_harness.py check`.
3. Require exact task ID and exact Git task-contract path.
4. Generate the context receipt and report explicit gaps.
5. Freeze Task Outcome Brief, evidence budget, write set and route.
6. Execute the Delivery Harness skill through the first real boundary.

If any identity, contract, scope, route, write-set, safety or authority fact is
missing/conflicting, stop with a stable reason. Do not guess the next task.
