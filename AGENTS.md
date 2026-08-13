# AGENTS.md — Solana Alpha Lab repository contract

## MISSION

Implement only the active bounded task that advances the Solana Memecoin Intraday Alpha Lab toward executable, net-of-cost evidence and eventual owner cashflow.

## STATUS_OWNERSHIP

The GPT control plane owns canonical mission, roadmap, task status, acceptance, and
canonical state. The elected owning ChatGPT Project GPT control plane surface is:

- Project Work when `LOCAL_WORK_CODEX` is selected;
- Project Chat Pro when `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is selected.

Repository agents and Codex may propose status changes in handoff evidence but
must not claim acceptance. Cursor is always `EXECUTION_ONLY`: it never selects
the current or next canonical task, never declares DONE, and never infers
authority from an Issue, PR, commit, tests, or files alone.

## OWNER_ATTENTION_GATE

The goal owner owns mission, hypotheses, estimands, product meaning and
priority, budget/cost caps, risk appetite, material data-source choices,
external-material authority, and physically user-only UI activation. Codex
owns routine engineering decisions and evidence quality inside the accepted
bounded objective.

Before asking for approval or performing merge, evaluate
`control/owner_attention_gate_v1.yaml`. Its terminal decisions are
`AUTONOMOUS`, `OWNER_ATTENTION_REQUIRED`, and `DENY`. Do not ask the user to
override a failed machine check. Ask only when the gate identifies a material
owner decision, authorization/access recovery, user-only activation,
external-material action, unresolved safety/truth conflict, or stricter stop.

## STANDING_PROJECT_AUTONOMY

The goal owner granted a durable project-local autonomy envelope on 2026-07-28.
Within the active objective and this repository, Codex and Cursor may proceed
without a new approval for:

- read-only inspection, official-document verification, calculations, and
  validation;
- bounded local writes, refactoring, Catalog maintenance, generated consumers,
  routine repair, tests, and exact staging;
- exact Atom Contract Issue creation/update/read-back by the GPT control plane,
  exact named-Issue receipt comments by an executor, task branches, ordinary
  commits, Git fetch/read-back, non-force push to a task branch, and creation
  or update of a pull request;
- routine implementation choices whose alternatives do not materially change
  the estimand, scope, cost, data contract, or safety boundary.

This is an explicit standing grant across the listed authority classes, not
authority inferred from a file, commit, Issue, PR, or passing test. A stricter
active-task contract, exact write set, offline requirement, cap, or stop
condition still wins. Cursor receives the objective and bounded scope from the
active direct prompt, handoff, or baton; the standing grant supplies routine
execution classes and necessary direct test, Catalog, hash, and generated
consumers. It does not let Cursor select a task, widen product semantics, or
claim canonical acceptance or `DONE`.

On `LOCAL_WORK_CODEX`, Codex may perform an ordinary pull-request merge when
`OWNER_ATTENTION_GATE` returns `AUTONOMOUS` for the exact PR head and every
machine precondition is true. It then reads back the exact main commit and
requires post-merge main CI before completion. On
`PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`, Cursor never merges and the route has
no Codex auto-merge grant; merge returns to the Project Chat/owner boundary.
Passing checks or a merge never establish canonical acceptance or `DONE`.

The standing grant does not authorize force push, history rewrite, destructive
cleanup, branch deletion, repository or account settings, credentials or
secrets, provider/API/RPC/WSS execution, purchases, deployment,
wallet/signer/transaction actions, real money, or any action that only the user
can complete. Those remain explicit user gates. If an ordinary step exposes one
of these boundaries, stop only at that boundary and return the smallest
concrete user action.

## LANGUAGE_AND_REPORTING

User-facing communication defaults to Russian. Keep code, paths, schema keys,
protocol labels, enums, product names, and machine-readable JSON/YAML in their
canonical form; explain exact English errors in Russian. This is a
project-scoped reporting rule only—it grants no task authority or action
permission.

## MODEL_EFFORT_ROUTER

At the Entry Gate for a complex task, atom, or uninterrupted autonomous chain,
emit exactly one compact recommendation unless the immediately preceding
finish checkpoint already carries the same tuple for the same scope:

```text
MODEL_EFFORT_RECOMMENDATION=<enum>; scope=<exact atom or chain>; reason=<one sentence>; escalation=<one trigger>
```

Use `LUNA_MAX` as the bounded implementation workhorse; use `SOL_XHIGH` for
material architecture, public contract/schema, cross-system, difficult root
cause, PIT/statistical/security, or invariant-reconciliation work; reserve
`SOL_MAX` for irreversible/high-impact or still-unresolved adversarial work.
`TERRA_XHIGH` is the bounded fallback when Luna is unavailable, not a mandatory
escalation. Use `ROUTINE_NO_SWITCH` for deterministic smoke, exact read-back,
ordinary merge, and other simple steps.

For one uninterrupted autonomous chain, its `hardest material segment` sets the
recommendation for the whole chain. After a material atom/task checkpoint and
immediately before the next approval or handoff, emit:

```text
NEXT_MODEL_EFFORT=<enum or DEFERRED>; scope=<exact next atom or chain>; reason=<one sentence>; escalation=<one trigger>
```

Use `DEFERRED` only when canonical task selection has not identified the next
scope. Do not stay silent when the default is sufficient, repeat an unchanged
tuple for the same scope, or emit advice during routine microsteps. Recompute
only after a material scope, architecture, data-contract, estimand, security,
or safety-boundary change. Model advice grants no task, mutation, external,
spend, wallet, signer, transaction, merge, or canonical-status authority.

## INPUT_ROUTING

Default: `INPUT=DIRECT_PROMPT`.

- The active task and atom come from the current GPT-control-plane-approved
  direct prompt or an explicitly named local handoff.
- Read local input only when the current prompt contains
  `LOCAL_HANDOFF: <repository-relative path>`.
- Read Work acceptance output only when the current prompt contains
  `ACCEPT_LOCAL_HANDOFF: <repository-relative path>`.
- Read a GitHub-transported Atom Contract only when the current prompt contains
  `GITHUB_BATON: <exact contract locator>` and the contract is validated under
  `docs/agent/GITHUB_BATON_PROTOCOL.md`. `GITHUB_BATON` is a live accepted
  input route for `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`; it grants no implicit
  Issue/PR write, commit, push, or status authority. Those routine actions are
  authorized only by the explicit standing grant above or a stricter direct
  user instruction.
- Local handoff validation and path rules are defined by
  `docs/agent/HANDOFF_PROTOCOL.md`.
- Execution-route selection among `GPT_ONLY`, `LOCAL_WORK_CODEX`, and
  `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is defined by
  `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`.
- Never search for the newest, latest, or most recently modified handoff.
- A direct prompt, handoff, baton, or standing grant defines the applicable
  authority envelope. Never infer a broader envelope from an Issue, PR,
  commit, tests, or files alone.

## WORKSPACE_ONLY

Operate only inside this repository workspace. Do not read or write unrelated folders. Machine-specific absolute paths must not enter tracked files or Catalog metadata.

## NO_SECRETS

Never create, request, display, store, or commit `.env` values, API keys, access tokens, passwords, cookies, private endpoints, seed phrases, private keys, wallet recovery data, or signer material. `.env.example` remains placeholder-only.

## EXTERNAL_ACTIONS

GitHub transport covered by `STANDING_PROJECT_AUTONOMY` may be used for exact
Atom Contract Issue creation/update/read-back, exact named-Issue receipt
comments, ordinary fetch, non-force task-branch push, pull-request work, CI
read-back, and routine review interaction. It does not authorize unrelated
Issue discovery or account/repository-wide mutation. Public official
documentation may be read when it changes a decision. Provider/API/RPC/WSS
execution, account or repository settings, payment, remote creation, connector
permission changes, VPS actions, package adoption, deployment,
wallet/signer/transaction actions, and any other external side effect remain
separately gated.

Before building or invoking an external provider route, resolve its stable ID
through the current append-only provider route registry. The current successor
is `PROVIDER-ROUTE-CAPABILITY-REGISTRY-002` at
`configs/provider_route_capability_registry_v2.yaml`; it must preserve the
semantic hashes and exact SHA of immutable predecessor
`PROVIDER_ROUTE_CAPABILITY_REGISTRY_V1` at
`configs/provider_route_capability_registry_v1.yaml`. Reuse only an observed
transport boundary that fits the exact consumer and current authority. A
missing record is `REGISTRY_GAP`, not provider unavailability; a stale or
failed record requires the declared preflight and a new bounded authority gate.
The registry grants no call, credential, retry, fallback or provider-selection
authority.

When a credentialed provider attempt is bounded by a one-shot/request cap and
current local network health is uncertain, run a credential-free route
preflight first: DNS resolution, TCP reachability to the already allowlisted
host/port, and current official endpoint/method confirmation. A failed
preflight reads no credential, writes no market evidence and does not consume
the external attempt. It stops before the provider call. This is an ordering
rule, not provider authority, retry authority or a substitute for exact raw
retention after a real attempt.

## PRE_GIT_PROVENANCE

- Exact imported bytes live under `docs/evidence/pre_git/`.
- Repository-authored Project Sources release candidates live only under
  `docs/project_sources/releases/` and are discoverable only through
  `docs/project_sources/release_registry_v1.yaml`; their manifest and
  checksums are exact SHA-256 bindings.
- Cloud Project Sources activation stays outside Git. A release is active only
  after the owner reports its exact seven-role smoke; Git, PR and CI prove a
  candidate, never UI activation.
- At Entry Gate read the release registry. At Finish Gate every new or modified
  task acceptance receipt declares `NO_CHANGE`, `RELEASE_CANDIDATE` or
  `ACTIVATION_RECEIPT`; the registry test rejects an unregistered release or
  a missing disposition after its enforcement start.
- Every imported record preserves origin task, source path, legacy ID where available, creation date, `first_reliable_available_at`, retention, and named consumers.
- Import/backfill never creates past availability.
- Exact imported evidence is content-addressed and exempt from style normalization; repository-authored files remain subject to whitespace diff checks.
- Bundle-only superseded code must not become active code.
- `ARCH-INTENT-001` is current user-owned direction from 2026-07-21, not historical TASK-01/02 evidence.

## ARCHITECTURE_INTENT_BOUNDARY

External context such as AOT/ALBS is advisory only. It must carry as-of, first-reliable-availability, TTL, revision, hash, confidence/calibration, lineage, evidence, and allowed-consumer fields. It cannot directly command a bot and cannot bypass risk, execution, inventory, holdout, or economics gates.

## VALIDATION_COMMAND

Platform-neutral gate:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py
```

Windows compatibility wrapper:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

Tracked-only delivery preflight:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

CI-owned delivery pilot preflight:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --ci-owned-delivery
```

Control-only task-close fast path:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --control-only-task-close
```

## CONTROL_ONLY_TASK_CLOSE_FAST_PATH

- The fast path is prospective and applies only after one exact owner terminal
  `TASK<NN>_SOURCE_SMOKE=PASS; OWNER_DONE_ACCEPTANCE`. The two clauses are
  validated separately: Source smoke never implies task DONE, and task
  acceptance never activates Project Sources.
- `control/control_only_task_close_fast_path_v1.yaml` admits exactly one new
  combined activation-and-close receipt plus the closed registry and
  Catalog/generated write set. Product code, tests, schemas, contracts,
  workflows, release payloads, dependencies, deletes, renames, and repairs are
  ineligible.
- Run the focused gate once for the exact committed candidate before push.
  `GITHUB_PR_EXACT_HEAD_CI` is the full-suite owner; exact-main post-merge CI
  remains mandatory.
- Any classification or focused-check failure falls back to
  `--tracked-only-delivery`; owner attention cannot waive a failed check.
- Keep the fast path only if the next three eligible task closes need no
  control/clean-checkout repair and each local focused gate finishes within
  120 seconds. A false classification or missed drift disables the path.

## CI_OWNED_DELIVERY_PILOT

- Prospectively admit the next three eligible bounded offline/routine delivery
  candidates through `--ci-owned-delivery`. The exact candidate must be
  committed and tracked-clean; the mode preserves the new-test skip policy and
  runs focused security, baton, Catalog, generated-view, architecture, lock,
  workflow and hook checks within 120 seconds.
- Workflow, hook, dependency/lock, validation/security/control-policy,
  schema/migration and validation-test changes are ineligible. Semantic
  ambiguity, any machine classification failure, or a focused-check failure
  falls back to `--tracked-only-delivery`; owner attention cannot waive it.
- `GITHUB_PR_EXACT_HEAD_CI` is the sole clean-checkout/full-suite owner for an
  admitted candidate. Its first pushed exact head must pass before merge, and
  exact-main post-merge CI remains mandatory. Do not repeat the local full
  suite for unchanged admitted bytes.
- Before admission, read prior merged PR validation evidence for this pilot.
  Record `CTRL-CI-OWNED-DELIVERY-PILOT-V1 observation N/3` plus the focused
  receipt summary in the existing PR Validation section. After observation 3/3,
  do not admit a fourth candidate until the pilot keep/repair/rollback review.
- Keep the route only after 3/3 first-head PR CI passes with no repair and at
  least seven minutes saved per eligible delivery. Immediately disable it and
  fall back to `--tracked-only-delivery` after a false admission, a missed
  clean-checkout or local-data defect, a first-head failure caused by omitted
  local coverage, or a focused gate above 120 seconds.

## TRACKED_ONLY_DELIVERY_PREFLIGHT

- Unless `CONTROL_ONLY_TASK_CLOSE_FAST_PATH` or `CI_OWNED_DELIVERY_PILOT`
  admits the exact candidate, run the tracked-only delivery preflight once for
  the exact committed candidate before its first push. It creates an isolated
  local clone from Git objects, copies no untracked or ignored inputs, runs the
  full locked gate offline, removes the temporary checkout, and writes a
  compact ignored receipt under `local/delivery_preflight/`.
- The candidate must have no staged or unstaged tracked changes. Untracked and
  ignored local evidence may remain in the source workspace because it is not
  copied into the isolated checkout.
- A delivery diff must not introduce a test skip as a substitute for absent
  local/raw evidence. Prefer a tracked synthetic fixture. A genuinely
  non-decision-critical skip requires an adjacent
  `DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: <tracked docs/decisions or docs/evidence path>`
  marker and an existing tracked proof reviewed with the candidate.
- This is a delivery gate, not an implementation-loop or per-atom hook. Its
  wall-time cap is 15 minutes. Do not run the ordinary full gate in the source
  workspace for the same candidate first.

## REUSE_FIRST_RECOVERY_TRIGGER

After the first material, evidence-backed blocker in a bounded atom, stop
expansion before custom construction, route widening, or infrastructure
addition. It applies to incomplete or semantically ambiguous external data, a
documented provider or protocol capability limit, a repeated delivery/control
failure with the same root cause, or a concrete component gap that would
otherwise prompt custom construction. It does not apply to a routine
deterministic test failure, an already-known limitation, or a blocker whose
recovery is already prescribed by an exact active gate.

Preserve and classify the first result: no hidden retry or fallback. Consult
`registries/reuse_candidates.yaml`, relevant accepted decisions including
`ADR-002`, and only the smallest useful set of current official, OSS, or
commercial alternatives for the named consumer. Record exactly one outcome —
`ADOPT`, `WRAP`, `FORK`, `BUILD`, or `STOP` — with its cheapest falsifier.

When the current atom's decision or acceptance receipt already exists, keep a
compact record there containing only the blocker, alternatives considered, and
chosen outcome with its fit rationale. It is not a registry row, permanent
Source, or generic scan artifact for every failure. Missing, vague, stale, or
conflicting third-party documentation produces `STOP` or an explicitly
unresolved result; it never licenses a custom workaround by default.
`BUILD` remains valid only for a narrow project-owned truth boundary after the
other outcomes are evidenced unfit.

This trigger does not authorize a provider, dependency, cost, security, or
owner-boundary change. Every ordinary external, license, dependency, security,
cost, and owner gate remains in force.

## VALIDATION_ECONOMY

- During implementation, run the smallest targeted checks for the changed
  behavior and direct consumers.
- Use one full-gate owner per exact candidate fingerprint: Cursor locally,
  Codex validation, or GitHub CI. Do not repeat the full gate after staging,
  commit, or publication when the candidate and environment are unchanged.
- When the route guarantees full validation on the same pushed head, Cursor may
  return targeted evidence plus `FULL_VALIDATION=DELEGATED_TO_CI`, then read
  back CI when transport is available. Delegation is not a blocker.
- For an ordinary candidate outside an active fast path or pilot, the
  tracked-only preflight is the local full-gate owner. For an admitted
  control-only close or CI-owned pilot delivery, `GITHUB_PR_EXACT_HEAD_CI` is
  the sole full-gate owner after the focused local gate. GitHub is independent
  remote read-back for the legacy route and the actual full owner for admitted
  focused routes; do not add another local full-gate run for unchanged bytes.
- Re-run a failed check only after its root cause changed; re-run a passed full
  gate only when the candidate fingerprint, dependencies, relevant runtime, or
  validation policy changed.
- Catalog, generated-view, security, and topology checks apply when their owner
  or consumer changed; read-only work does not trigger repository validation.

## FACTORY_LEVERAGE_INVARIANT

- The default path for a comparable hypothesis already covered by Factory
  capabilities is configuration, data/query composition and a trial, without a
  product-code modification.
- A Git/code/deploy cycle is justified only by a named reusable capability gap,
  defect, safety or reliability requirement, or measured scale bottleneck.
- When comparable work repeatedly requires hypothesis-specific product code,
  use the existing `FACTORY_FIT_REVIEW` before replicating that pattern. Name
  the reusable gap and the next real consumer.
- This is a review trigger, not an automatic blocker and not a new registry,
  metric or recurring report.

## CHANGE_PROTOCOL

Read this file and the task/handoff explicitly named by the current prompt,
confirm the bounded objective, apply `VALIDATION_ECONOMY`, inspect the exact
staged or committed inventory, and use the standing autonomy envelope without
pausing for routine microsteps. Apply `OWNER_ATTENTION_GATE` before any owner
prompt or merge. Cursor never merges; Codex auto-merge exists only on
`LOCAL_WORK_CODEX` after the exact machine gate passes. Do not cross a stricter
task cap, perform an excluded authority class, or change canonical status. The
GPT control plane owns canonical status and acceptance.

## ACTIVE_TIME_GATE_CHECK

Before selecting or starting a new task or parallel atom, read
`control/active_time_gates.json` when it exists.

- An `ACTIVE_WAITING` gate does not block non-interfering parallel work before
  its `earliest_at`.
- When current UTC is at or after `earliest_at`, stop before any new mutation
  and return to the marker's exact `required_next_atom`.
- A marker is a durable reminder and precedence rule, not authority for
  provider/API/RPC/WSS calls, candidate admission, spend, deployment,
  credentials, wallet, signer, transaction, merge or destructive action.
- Only the marker's declared `resolution_owner` may move it from
  `ACTIVE_WAITING` to a terminal state, with an exact evidence pointer.
