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

During implementation run targeted checks. Elect one full-gate owner per exact
candidate fingerprint. Use an eligible focused gate only when machine
classification admits it; otherwise use:

`uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

`CI_OWNED_DELIVERY_PILOT`, when eligible, uses
`uv run --locked --managed-python python -B scripts/validate_ci.py --ci-owned-delivery`.
`GITHUB_PR_EXACT_HEAD_CI` owns the full clean-checkout suite. The next three
eligible observations must each finish focused checks within 120 seconds, pass
first-head CI without repair and save at least seven minutes. Record
`observation N/3`; after 3/3 do not admit a fourth before keep/repair/rollback.
A false admission, missed clean-checkout/local-data defect or focused overrun
falls back to `--tracked-only-delivery`.

## Owner attention and guarded merge

Routine bounded local/GitHub delivery continues without micro-approval. Stop
for the material/external/user-only/destructive/safety gates in
`OWNER_ATTENTION_GATE_V2`.

Both direct routes stop for exactly:

`PR #<number>, head <40 lowercase hex> проверен; ready + merge разрешаю.`

Immediately before mutation re-read repository, PR, head, mergeability,
required tests/CI/full gate/Factory Fit, write set, secret scan, unresolved
reviews, standard-merge mode, branch preservation and settings. A stale head or
failed check is `DENY`, not a human override prompt. On `AUTONOMOUS`, perform
one ordinary merge, preserve the feature branch/settings and read back exact
main plus post-merge main CI.

## Startup

1. Read `AGENTS.md`, harness and elected profile.
2. Run `scripts/delivery_harness.py check`.
3. Require exact task ID and exact Git task-contract path.
4. Generate the context receipt and report explicit gaps.
5. Freeze Task Outcome Brief, evidence budget, write set and route.
6. Execute the Delivery Harness skill through the first real boundary.

If any identity, contract, scope, route, write-set, safety or authority fact is
missing/conflicting, stop with a stable reason. Do not guess the next task.
