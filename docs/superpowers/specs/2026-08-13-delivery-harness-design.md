# Delivery Harness v1 — Design

Status: `OWNER_DESIGN_AND_SPEC_REVIEW_APPROVED`
Task: `CTRL-DELIVERY-HARNESS-V1`
Date: `2026-08-13`
Repository: `lancerbeta/solana-alpha-lab`
Design base: `e78a08ec7ce5687c89b39fa19d8503ca206c6d9e`
Design tree: `add30ddf1be54655727e8d9cf440f3f92ded180b`

## 1. Outcome

Build one repository-owned **Delivery Harness** that lets a capable agent work
on a bounded product task from context recovery through implementation, review,
PR, CI and an owner-authorized merge with little owner attention. Cursor and
Codex must consume the same Git-native control core, evidence map and validation
surface; their adapters may differ, but they must not create competing project
truth.

The owner remains responsible for product meaning, material risk/cost/access
decisions, optional cloud-export maintenance and the exact merge gate. The elected
direct-delivery agent owns bounded task orchestration, Entry/Finish checks,
routine engineering, repository reconciliation and technical/semantic evidence
inside the approved objective and safety boundary. It cannot turn its own
recommendation into new material authority.

Git is the working project-memory owner for both direct routes. The historical
cloud Project Sources registry remains preserved only as audit/rollback evidence.
A future cloud bundle or Project Instruction export is owner-managed and optional:
the harness never selects it as working context, never blocks execution or DONE on
its activation, never reminds the owner to replace it and never requests a
`SMOKE=PASS` receipt.

The harness is also a portable seed for future repositories. Reuse must require
changing a small project profile, not copying Solana-specific policy into every
new project.

This is a control-plane task. It does not advance or accept `TASK-30`, select a
new canonical product task, gather market data, run a provider route, trade or
claim alpha.

### Final adversarial hardening

The delivery candidate must additionally satisfy four fail-closed properties:

- context and delivery evidence are rebuilt from the clean exact Git candidate;
  a caller-provided self-hash is never authority;
- repository identity is one live origin plus the exact frozen merge-base, not
  a profile label or bootstrap placeholder;
- merge is compare-and-swap against the approved PR head and accepts only the
  named workflow/job in exact successful state;
- merge submission is itself self-hashed and is followed by a mandatory
  submission-bound exact-default-branch/ancestry/
  push-CI receipt. The portable seed is standard-library-only and every copied
  source byte is covered by a deterministic bundle manifest.

## 2. Why this task exists now

Three measured conditions make the work timely:

1. The current root `AGENTS.md` is 398 lines / 21,406 bytes and several Cursor
   rules repeat its policy. That increases always-on context and creates more
   places for policy drift.
2. The active Cursor adapter still treats the retired GPT-to-Cursor GitHub baton
   as its primary route. The owner now wants direct autonomous Cursor work, while
   retaining baton machinery only as historical evidence.
3. `ARCH-INTENT-004` already names repeated manual context reconstruction and
   material Entry Gate delay as activation triggers. Both have now been observed.

Official OpenAI model guidance recommends stating policy once, exposing only
relevant tools and tracking context growth. It reports directional internal
coding-agent gains from leaner prompts, but those figures are not assumed to
transfer to this repository without local validation. Cursor likewise
recommends concise project rules that point to canonical files instead of
copying whole guides.

## 3. Entry Gate

Verdict: `START_WITH_PATCH`.

### Mission and owner decision

- Mission: reduce context waste, approval fatigue and route-specific ceremony
  without weakening evidence, safety or semantic ownership.
- Owner decision after delivery: use Codex or Cursor for a bounded task with one
  shared repository memory/control surface and predictable owner interruptions.
- Named consumers: `LOCAL_WORK_CODEX`, direct local Cursor, the goal owner and a
  future repository bootstrapped from the portable profile.
- Cheapest falsifier: a deterministic context query plus one synthetic delivery
  fixture must fail to produce stable, bounded and equivalent task context for
  both adapters. If ordinary Catalog queries already satisfy this completely,
  the Context Capsule implementation must remain minimal.
- Evidence gain: exact control-route resolution, smaller always-on context,
  reproducible context receipts, explicit gaps and a tested direct-Cursor path.
- Cost/risk: one bounded control branch; no external service, paid dependency,
  provider call, credential, deployment or product-data mutation.
- Recovery: revert the new adapter/core commits; legacy baton code and history
  remain intact and can be reactivated only by a new explicit decision.

### Factory leverage invariant

The change is justified only if it makes a named future task cheaper or safer:

- a new agent can locate mission, task, contracts, evidence and tests without
  reading the whole repository;
- Cursor and Codex can resume the same branch from the same deterministic
  receipt;
- routine delivery no longer needs baton construction or repeated design/spec/
  plan approvals;
- validation and context work are proportional to changed risk.

## 4. Design principles

### 4.1 One core, thin adapters

The Git repository owns one route-neutral core. Cursor and Codex adapters only
teach their host how to enter and operate that core.

```text
Git truth / Catalog / lifecycle registries / task contracts / tests
                              |
                    Delivery Harness core
             (profile, policies, context resolver, gates)
                       /                 \
             Cursor adapter          Codex adapter
       (rules/commands/skills)    (AGENTS + shared CLI)
```

No adapter may invent task state, owner approval, canonical status or evidence.
Cursor Memories, Codex conversational memory and chat history are convenience
caches only. A cache may help discover a path; every consequential claim must
resolve back to tracked Git bytes, Catalog/lifecycle owners, exact Git/GitHub
state or a named external receipt.

### 4.2 Elected direct-delivery routes

The successor router has four explicit states:

- `DIRECT_CODEX_DELIVERY` — Codex is the active delivery orchestrator;
- `DIRECT_CURSOR_DELIVERY` — Cursor is the active delivery orchestrator;
- `DESIGN_ONLY` — no repository executor is needed;
- `LEGACY_GITHUB_BATON_DORMANT` — historical only and never auto-selected.

`LOCAL_WORK_CODEX` may remain a compatibility alias for
`DIRECT_CODEX_DELIVERY`. The live GPT-to-Cursor baton route is not a
compatibility alias; it is retired.

One task has one elected delivery agent, branch/worktree and context receipt at
a time. A second agent may review or resume from the exact receipt, but it does
not silently take ownership. Route switching is explicit and records the same
task/base/head/evidence identities.

The active agent may start an unambiguous canonical `READY` successor when the
owner's prompt explicitly means "continue the backlog" and the Entry Gate finds
no material fork. If zero or multiple materially different candidates exist, it
asks for the product decision. Branch names, latest files and chat memory never
select a task.

### 4.3 Context is routed, not dumped

Context is loaded in four lanes:

1. **L0 Always-on core** — mission boundary, authority, owner-attention rules,
   canonical entry command and safety invariants.
2. **L1 Task Capsule** — exact task/atom, base/head/tree, direct dependencies,
   consumers, changed paths, tests, evidence IDs and known gaps.
3. **L2 Dynamic capability** — relevant domain rule/skill or provider route only
   when a declared trigger matches.
4. **L3 Deep evidence** — raw receipts, prior reviews, official documentation or
   history only for a concrete unresolved question.

The resolver returns references and compact evidence-linked facts, not giant
file copies. Missing information is `UNKNOWN` or `CATALOG_GAP`; it is never
reconstructed from vague chat memory.

### 4.4 Attention is a scarce product resource

The default user-interruption budget for one bounded task is:

- zero prompts for routine read/write/test/repair/commit/push/PR/CI work within
  the approved objective;
- one semantic approval only when the work changes product meaning, architecture,
  data contract, material cost/risk or another owner-owned decision;
- one exact merge approval for a concrete PR and unchanged head SHA;
- extra prompts only for authentication/user-only UI work or an actual safety/
  truth conflict.

Design, spec, plan, implementation and review are phases of a delivery chain,
not automatically separate owner gates. The current design task still uses the
existing spec-review gate because the harness itself changes those rules.

### 4.5 Machine checks own mechanics; humans own meaning

Schemas, hashes, allowed paths, context budgets, clean checkout, tests and
exact-head CI are deterministic checks. The model and owner handle goals,
trade-offs, product decisions and ambiguous evidence. A passing machine gate is
not semantic acceptance or canonical `DONE`.

### 4.6 Portable by profile, not by lowest common denominator

The portable core defines universal concepts: authority, objective, bounded
write set, evidence, context, validation, review, merge and recovery. A project
profile binds those concepts to local files and commands.

The Solana profile may reference the historical cloud-export registry, Catalog,
Factory Fit and provider/wallet boundaries. The registry is not a working-context
truth owner. Its configured registry path defines the entire historical-cloud
boundary: those bytes may resolve only as L3 historical context, never be
relabelled as L2 delivery evidence. The portable core must not contain Solana-specific bindings. A dummy-project fixture
must prove that the core initializes and validates without Solana-specific
paths or vocabulary.

## 5. Repository architecture

### 5.1 Canonical core

The planned canonical surfaces are:

```text
delivery-harness/
  harness.yaml                 # version, capability flags, adapter contract
  project-profile.yaml         # Solana-specific bindings
  context-map.yaml             # semantic role -> truth owner -> resolver
  capability-radar.yaml        # event triggers and candidate contract
  templates/
    portable-project-profile.yaml
    bootstrap-prompt.md

docs/agent/
  DELIVERY_HARNESS_PROTOCOL.md
  DELIVERY_CONTEXT_PROTOCOL.md
  DELIVERY_HARNESS_BOOTSTRAP.md

scripts/
  delivery_harness.py          # context/status/check/init preview/apply
```

`portable-bundle-manifest.json` is the single source/destination/SHA-256
inventory for initialization. The standard-library-only `init --preview` path
validates every source hash before any target write; apply requires the exact
unchanged plan fingerprint.

Final filenames may change during implementation planning to match existing
repository conventions, but ownership and separation above must not.

The core is versioned and self-describing. Every adapter declares which core
version it consumes. Unsupported host features degrade to an explicit fallback;
they do not silently disable a gate.

### 5.2 Context map

`context-map.yaml` is a deterministic routing table, not a new knowledge base.
It maps at least these semantic roles:

| Role | Truth owner | Typical resolver |
|---|---|---|
| mission/invariants | root policy + active project profile | exact paths |
| product roadmap | active registered Source release | release registry |
| active bounded work | explicit task/atom contract | exact input, never newest |
| implementation state | Git branch/head/tree/diff | local Git |
| stable assets/relations | Catalog | bounded Catalog query |
| lifecycle | versioned registries | exact stable ID |
| external route knowledge | provider-route registry + receipts | route ID |
| architecture decisions | ADR/intent registry | exact ID |
| delivery evidence | tests/PR/CI/acceptance receipts | exact candidate SHA |
| historical context | archive and superseded releases | on-demand only |

Each result carries `path`, stable ID where available, SHA-256 or Git identity,
truth owner, as-of/commit and a missingness state. Stable ordering and a receipt
hash make Cursor/Codex handoffs comparable.

### 5.3 Measured context budgets

Initial limits are design targets and must be validated on representative work:

- root `AGENTS.md`: at most 12 KiB;
- combined Cursor `alwaysApply` project rules: at most 6 KiB;
- ordinary L1 context receipt: at most 48 KiB;
- files above 100 KiB are never auto-inlined by the harness;
- large Catalog shards, raw JSON, logs and archives are queried or referenced,
  not loaded whole.

If a required safety invariant does not fit, correctness wins and the budget is
revised with evidence. The implementation must report measured bytes and
selected paths rather than pretending it can know every model's exact tokens.

### 5.4 Root `AGENTS.md`

The current 398-line file will be reduced to a compact, route-neutral front
door. It retains unique mission, authority, safety, owner attention, canonical
entry/finish and evidence rules. Detailed policies move behind explicit links
or machine-readable owners; duplicated explanations are removed.

Tests must prove that the leaner file still reaches every mandatory policy and
that no stricter existing boundary disappears. This is a prompt refactor, not a
permission expansion.

### 5.5 Cursor adapter

Cursor uses its native primitives according to their current roles:

- `.cursor/rules/` — small static project constraints; only the true minimum is
  `alwaysApply`, while domain rules use globs or agent-requested descriptions;
- `.cursor/commands/` — explicit owner-facing entry points such as
  `/delivery-start`, `/delivery-status`, `/delivery-review` and
  `/delivery-finish`;
- `.agents/skills/` — portable workflow skills discoverable by supporting
  agents; thin `.cursor/skills/` adapters are allowed only if the installed
  Cursor version requires them;
- `.cursor/agents/` — optional isolated critics for code, goal/DoD,
  architecture and refactoring.

Subagents improve context isolation and review independence but are not a
correctness boundary. If unavailable or unreliable, the harness falls back to
the same deterministic checks plus an explicit single-agent review receipt.

Cursor must work from one opened repository/worktree root. The self-check warns
when both a parent checkout and its worktree are opened in one multi-root
workspace because duplicated always-on rules waste context and can conflict.

### 5.6 Codex adapter

Codex uses the same root `AGENTS.md`, project profile, context resolver and
tests. Existing personal `start-solana-task` / `finish-solana-task` skills may
remain user-level conveniences, but they must resolve the same core and must not
become a second repository truth owner.

No new Codex-only memory database is introduced. The material Codex improvement
is the same one as Cursor's: a lean front door, task-specific deterministic
context, evidence-linked gaps and fewer repeated approval instructions.

### 5.7 Authority-policy successor

The existing owner-attention policy is versioned rather than silently
reinterpreted. Its successor preserves every external/material/user-only and
safety gate, but distinguishes direct delivery from dormant baton execution:

- direct Cursor or Codex may perform routine delivery autonomously;
- both stop at an exact owner merge gate;
- after the owner names the exact PR and unchanged head SHA, the elected direct
  agent may perform only a standard guarded merge and read back the base-bound
  profile default branch/CI;
- dormant baton Cursor retains its historical `merge=FORBIDDEN` semantics;
- merge neither requires nor certifies a cloud bundle export and never grants
  canonical product truth unsupported by the exact Git task's Finish Gate.

The merge guard rechecks repository, default branch, PR, head SHA, mergeability, required
checks, unresolved reviews, write set and forbidden side effects immediately
before mutation. Policy, profile, guard/context runtime and their core schemas
must be byte-identical to the frozen base; any control-plane change uses the
predecessor exact-owner route and cannot self-authorize. Post-merge readback
rebuilds the same context receipt and derives the frozen first parent from its
task contract, never from a caller assertion. Any drift invalidates the
approval and stops.

### 5.8 Model/effort router

The repository keeps the already accepted rule:

- `Luna Max` is the default workhorse for bounded implementation, tests and
  ordinary reviews;
- frontier/max effort is recommended for cross-cutting architecture, security,
  irreversible data/authority contracts or a chain whose hardest step requires
  it;
- the recommendation is emitted after one atom finishes and before approval of
  the next substantial atom, not randomly during execution.

The router is advice, not a quality claim. Tests/harness remain the primary
quality control.

## 6. Delivery workflow

### 6.1 Start

`delivery-start` performs:

1. repository/worktree identity and clean-state check;
2. exact input-route and bounded objective resolution;
3. L0/L1 context receipt generation;
4. Entry Gate and Task Outcome Brief;
5. `SPEC_ROUTE = NONE | PRD_LITE | DESIGN_SPEC | BOTH`;
6. cheapest falsifier, validation owner and evidence budget selection;
7. Product Horizon and Capability Radar;
8. effort recommendation for the hardest planned step.

It never selects a canonical product task from branch names, latest files or
chat history. The owner or an already-authoritative task contract supplies that
decision.

### 6.2 Execute

After the applicable semantic gate, the agent autonomously:

1. creates/uses one task branch or isolated worktree;
2. implements in decision-changing atoms;
3. uses tests before or alongside behavior changes;
4. runs targeted checks while iterating;
5. records compact checkpoints only when they help recovery;
6. repairs in-scope failures without asking for routine approval;
7. stops and replans when the same blocker repeats, a second provider/route
   pivot appears, an atom merely prepares another atom, or the evidence budget
   is exceeded.

An atom must state `DECISION_DELTA`, `UNCERTAINTY_REMOVED`, finished
`CAPABILITY_OR_EVIDENCE`, `STOP` and `NEXT`. File-production phases are not
separate atoms by default.

### 6.3 Review

Review is risk-routed:

- code/script/test changes always receive code review;
- goal/DoD critic is added for new or semantically changed product outcomes;
- architecture critic is added for boundaries, schemas, dependencies,
  security or multi-component work;
- refactor critic runs only after correctness and only on measured complexity
  or duplication.

All critics read the exact diff and contract. They return actionable findings,
not generic scores. Correctness cannot depend on a subagent being available.

### 6.4 Finish and merge

The agent:

1. runs proportional Factory Fit and Product Horizon review;
2. runs the Capability Radar;
3. runs targeted checks; after bootstrap the guarded merge executes the elected
   project-bound gate once and consumes existing exact-head CI;
4. produces exact changed-file, tests, head/tree, limitations and rollback
   receipts;
5. pushes and opens/updates one PR;
6. requires exact-head CI and unresolved-review checks;
7. stops at an exact owner merge phrase naming PR and head SHA.

The design allows a deterministic guarded standard merge after exact owner
approval, but only if the project profile enables it. The guard must re-read the
same PR/head/check state immediately before merge. Solana Alpha Lab enables this
for `DIRECT_CODEX_DELIVERY` and `DIRECT_CURSOR_DELIVERY`; the historical baton
route remains forbidden from merging. A stale head, failed check, unresolved
review or route mismatch requires a new exact approval.

Merge/CI still do not make a canonical task `DONE`. Canonical reconciliation
follows exact Git task/evidence owners. Optional cloud export is entirely outside
the delivery gate and remains an owner-managed convenience.

## 7. Baton retirement

The old GitHub baton is not deleted from history and its deterministic tooling
is not rewritten as if it never existed. It becomes `DORMANT_HISTORICAL`.

Implementation must:

- remove baton-only rules and commands from Cursor's active discovery paths;
- replace the active router with direct Delivery Harness routes;
- mark baton ADR/protocol/Catalog lifecycle as dormant/superseded while keeping
  their bytes, tests and receipts discoverable;
- prohibit accidental `GITHUB_BATON` activation through a negative invariant;
- never delete user-global Cursor/Codex skills, rules, credentials or unrelated
  project configuration.

Cleanup is exact-path allowlisted. The bootstrap self-check previews every
remove/replace action before applying it.

## 8. Portable bootstrap

The final deliverable includes one copy-paste initialization prompt with the
repository URL and a deterministic bootstrap route.

For this repository it tells Cursor to:

1. discover or accept one exact default branch, then fetch and verify that identity;
2. read only the compact harness front door;
3. run `delivery_harness.py check` and a dry-run migration preview;
4. remove/replace only the exact project-scoped active baton adapters;
5. validate Cursor capability availability and choose explicit fallbacks;
6. generate the first context receipt;
7. stop for the owner only if a user-only setup step remains.

For a new repository it uses the standard-library-only `init --preview` then
`init --apply --plan-sha256 <PLAN_SHA256>` route to install the
portable core and a project profile. The initializer refuses non-empty/conflicting
targets unless every overwrite is explicit. It never edits global Cursor/Codex
configuration or installs plugins automatically.

## 9. Capability and Marketplace Radar

### 9.1 Decision now

`CAPABILITY_RADAR_NOW = NONE`.

No Cursor/Codex plugin or MCP is installed in this atom. Current evidence says:

- local DuckDB + Parquet is the accepted analytical store; ClickHouse has no
  selected consumer or measured DuckDB bottleneck;
- Sentry/Grafana-style observability becomes material at the first unattended
  runtime / `TASK-35A`, not during offline route closure;
- PostHog/Amplitude becomes material when an Owner Cockpit or user workflow has
  named product-behavior questions;
- existing Git/`gh`/CI paths already cover GitHub delivery without a new MCP;
- documentation search through official web sources is sufficient; Context7
  is not justified until repeated version-documentation friction is measured.

### 9.2 Event-driven trigger

The radar runs cheaply at Entry and Finish Gates, and deeply only when any of
these events occurs:

- a technology/provider/database is selected for implementation;
- a second named consumer needs the same external capability;
- the same manual workaround or access failure repeats twice;
- validation/context/tool ceremony consumes a measured material share of work;
- an external system becomes a truth owner or operational dependency;
- first unattended runtime, production incident or owner-cockpit workflow;
- a chosen component's maintenance/security/scale boundary is crossed.

### 9.3 Output contract

The result is `NONE` or exactly one candidate. A candidate must state:

- named consumer and owner decision;
- measurable value and cheapest acceptance test;
- required permissions, credentials, network and data exposure;
- security/license/maintenance and cash/operator cost;
- fallback without the tool and clean exit path;
- activation trigger and why now rather than later;
- `ADOPT -> WRAP -> FORK -> BUILD` decision.

Marketplace popularity is discovery evidence, not adoption evidence. The agent
may research candidates read-only. Installation, credentials, external access,
paid plans or deployment remain explicit owner gates.

### 9.4 Current watch list

- `WATCH: SENTRY_OR_EQUIVALENT` — first unattended runtime with named incident
  and recovery consumer.
- `WATCH: POSTHOG_OR_EQUIVALENT` — Owner Cockpit/user workflow with named
  behavior/experiment questions.
- `WATCH: CLICKHOUSE_OR_REMOTE_ANALYTICS` — measured DuckDB single-writer,
  concurrency, volume or remote-query SLA breach plus a second consumer.
- `WATCH: CONTEXT7_OR_DOCS_MCP` — two material defects/delays caused by
  version-specific documentation lookup.

These are triggers, not backlog commitments.

## 10. Validation and acceptance

Implementation follows test-first behavior for the core and skills.

### 10.1 Deterministic tests

At minimum:

1. harness/profile/schema closure and stable version binding;
2. stable Context Capsule ordering, identity/hash and explicit gaps;
3. context byte budgets and no automatic large-file inclusion;
4. no secret-like values, absolute user paths or untrusted approval inference;
5. Cursor and Codex adapters resolve the same core/context receipt and route
   ownership cannot switch silently;
6. active Cursor discovery contains no live baton route while historical baton
   assets remain searchable;
7. owner-attention matrix: routine autonomous, material/external/user-only gated,
   exact merge head required, direct-agent guarded merge allowed and dormant
   baton merge denied;
8. capability radar returns `NONE` for the current repository and exactly one
   candidate for synthetic trigger fixtures;
9. portable dummy-project initialization contains no Solana-specific leakage,
   honors an arbitrary configured historical-cloud path and supports a
   non-`main` default branch;
10. initializer preview/apply idempotence, conflict refusal and rollback;
11. Cursor missing-skill/subagent fallback remains safe;
12. Catalog/generated consumers and repository validation remain consistent.

### 10.2 Scenario acceptance

The same synthetic bounded task is started once through Cursor and once through
Codex. Both must report identical repository/task/evidence IDs and equivalent
gates from the same commit. Each may format explanations differently.

The Cursor route must then demonstrate:

- routine branch/edit/test/commit/push/PR/CI flow without extra owner prompts;
- an intentional material decision stopping at owner attention;
- exact PR/head merge request;
- clean recovery from a fresh chat using only Git and the context receipt.

### 10.3 Delivery gates

- exact changed-file inventory;
- targeted harness tests;
- Catalog/generator/security/secret checks for changed owners;
- tracked-only full repository gate because this changes validation/control
  surfaces;
- independent exact-diff review;
- non-force push and Draft PR;
- exact-head CI;
- stop at owner merge gate.

The completion, independent-review and Factory Fit files are Catalog-discoverable
by stable IDs, but their Catalog records deliberately use `integrity.kind=none`.
Their exact content integrity is owned by the live completion-review-fit hash
chain and the reviewed full-diff digest; embedding the same hashes in a Catalog
file covered by that digest would create an indirect self-reference. Catalog
validation and generated projections remain required independently.

Bootstrap exception: the frozen base of `CTRL-DELIVERY-HARNESS-V1` predates the
v2 policy/profile, therefore the new guard cannot and must not authorize its
own installation. This one candidate is merged only through the predecessor
exact PR/head owner route after the tracked-only gate and exact-head CI. The v2
guard becomes the sole direct merge route only after its reviewed bytes exist
on the exact default branch; no missing-base, candidate-self-trust or reduced-check bypass exists.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Lean `AGENTS.md` hides a safety rule | Machine policy owners, reachability tests and before/after adversarial matrix |
| Cursor capability/version drift | Capability self-check, thin adapters, explicit fallback and no correctness dependency on subagents/hooks |
| New context projection becomes second truth | Read-only derived receipt, exact owner/path/hash, no mutation, explicit gaps |
| Portable core becomes a generic platform | One current project consumer plus one dummy portability fixture; no service/plugin framework |
| Marketplace enthusiasm creates supply-chain/permission sprawl | Event trigger, one-candidate cap, read-only research, explicit adoption gate and exit path |
| Autonomous delivery expands scope | Bounded objective/write set, replan triggers, owner-attention matrix and exact diff review |
| Multiple worktree roots duplicate Cursor rules | Self-check warning and single-workspace-root bootstrap instruction |
| Old baton silently reactivates | Active-path deletion plus negative route invariant; historical files remain dormant |

## 12. Non-claims and exclusions

This task does not:

- prove Cursor and Codex models have equal reasoning quality;
- make chat memory or model memory canonical;
- install a plugin, MCP, automation, cloud agent or dependency;
- select ClickHouse, Sentry, PostHog or another product component;
- run a provider/API/RPC/WSS call or use credentials;
- change wallet, signer, transaction, cash, strategy, trial, PIT, PnL or
  NetReturn authority;
- accept/close `TASK-30` or select the next product task;
- mutate or require a cloud Project Sources/Project Instruction export;
- authorize merge before the exact PR/head gate.

## 13. Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW = FULL_REVIEW` because the change affects architecture,
control, context, security, delivery and future operator workflow.

### NOW

`DELIVERY_HARNESS_V1`: implement the minimal Git-native core, Context Capsule,
portable profile and Cursor/Codex adapters. Value: less context waste and fewer
ceremonial pauses while preserving evidence and owner boundaries. Owner: goal
owner for material semantics; agent for routine engineering. Activation:
approved spec and executable plan.

### WATCH

`FIRST_UNATTENDED_RUNTIME_CAPABILITY_STACK`: at `TASK-35A` or equivalent,
re-run the Capability Radar for observability and owner-facing operations.
Do not preinstall the stack now because no unattended runtime or named incident
consumer exists.

## 14. Planned sequence

1. Owner reviews this design specification.
2. Write an exact implementation plan with atomic RED/GREEN checkpoints and a
   bounded write set.
3. Implement core contracts and failing tests.
4. Implement context resolver and portable initializer.
5. Install Cursor/Codex adapters and retire active baton paths.
6. Reconcile Catalog/control owners and validate budgets/fallbacks.
7. Run exact-diff review, full delivery gate, push, Draft PR and exact-head CI.
8. Stop at exact owner merge approval.
9. After merge, provide the one copy-paste Cursor bootstrap prompt and only the
   manual steps that the deterministic self-check proves unavoidable.

`STATE_CHANGE=NONE` until implementation, validation, delivery and the later
canonical reconciliation are complete.

## 15. Reference basis

Official sources consulted as of `2026-08-13`:

- OpenAI model guidance:
  `https://developers.openai.com/api/docs/guides/latest-model`
- OpenAI Codex use cases:
  `https://developers.openai.com/codex/use-cases`
- Cursor agent best practices:
  `https://cursor.com/blog/agent-best-practices`
- Cursor Rules:
  `https://docs.cursor.com/context/rules`
- Cursor Commands:
  `https://docs.cursor.com/en/agent/chat/commands`
- Cursor CLI/AGENTS/context:
  `https://docs.cursor.com/en/cli/using`
- Cursor Marketplace and plugin architecture:
  `https://cursor.com/marketplace`
  and `https://cursor.com/blog/marketplace`

Product and repository evidence:

- `AGENTS.md`
- `control/owner_attention_gate_v1.yaml`
- `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`
- `docs/agent/GITHUB_BATON_PROTOCOL.md`
- `docs/decisions/ADR-003-gpt-executor-routing.md`
- `docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md`
- `docs/project_sources/release_registry_v1.yaml`
- `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/roadmap.md`
- `docs/tasks/TASK-30-terminal-route-decision.md`
- `docs/evidence/task30/a19_terminal_route_decision_acceptance_v1.json`
