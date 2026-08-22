# AGENTS.md — Delivery Harness front door

This repository uses `DELIVERY_HARNESS_V1`. Cursor and Codex are equal direct
delivery agents over one Git-native control core. Read this file first, then:

1. `delivery-harness/harness.yaml` — active routes, budgets and hard exclusions;
2. `delivery-harness/project-profile.yaml` — repository bindings;
3. `delivery-harness/context-map.yaml` — bounded context projection;
4. `delivery-harness/policies/solana-alpha-lab.md` — domain and lifecycle policy;
5. `docs/agent/DELIVERY_HARNESS_PROTOCOL.md` — exact workflow;
6. `control/owner_attention_gate_v2.yaml` — owner-attention and merge authority.

## WORKING_MEMORY_AND_CONTEXT

Git is the working project-memory owner. Mutation, delivery and merge require
an exact task contract named by the owner or an exact canonical READY Git
contract. Owner navigation phrases such as го дальше inspect Git truth without
a new contract and must not mutate or invent a task. Discriminate
`ORIENTATION` versus `EXECUTE` with `.cursor/rules/10-input-routing.mdc`.
Never search for the newest/latest/current task, handoff, Issue, branch or file.

Build L0/L1 context with `scripts/delivery_harness.py context`. Load L2 only for
a named capability gap and L3 only for a concrete evidence dispute. Missing
truth is an explicit gap, never an invitation to guess or load the repository
wholesale. Open exactly one repository or worktree root; a parent checkout plus
its child worktree is `MULTI_ROOT_CONTEXT_DUPLICATION_WARNING`.

Cloud Project Sources and Project Instruction are
`OWNER_MANAGED_OPTIONAL_EXPORT`. They are not working context, execution gates,
DONE gates or authority. Preserve their historical registry for audit, but
never request its replacement or smoke. The owner may export Git artifacts to a
cloud chat voluntarily outside this harness.

## ACTIVE_ROUTES_AND_STATUS

Active routes are exactly `DIRECT_CODEX_DELIVERY`, `DIRECT_CURSOR_DELIVERY` and
`DESIGN_ONLY`. `LEGACY_GITHUB_BATON_DORMANT` is historical, inactive and cannot
select work or grant authority. A route is fixed for the delivery receipt; a
change requires an explicit replan and new receipt.

The owner owns product meaning, hypotheses, estimand, priority, budget, material
risk and external authority. The elected direct agent owns bounded task
orchestration, routine engineering, tests, evidence quality and delivery.
Repository bytes, tests, a PR, CI or merge never by themselves establish
semantic acceptance, canonical `DONE`, alpha, strategy promotion or cashflow.

## AUTONOMY_AND_OWNER_ATTENTION

Inside an exact bounded objective and stricter task write set, both direct
agents proceed autonomously through read-only inspection, local writes,
refactor needed for DoD, tests, Catalog/generated propagation, ordinary
commits, fetch/read-back, non-force task-branch push, PR/review and CI work.
Do not pause for routine microsteps.

Evaluate `OWNER_ATTENTION_GATE_V2` before asking the owner or merging. Stop only
for a material product/estimand/data-contract/safety decision, external or
credentialed action, user-only access/activation, destructive/history/settings
change, real money/wallet/signer/transaction, unresolved truth/safety conflict,
or a stricter task stop. Failed machine evidence is `DENY`; reassurance cannot
override it.

Both direct agents stop once after exact-head CI for the exact owner phrase bound
to the current PR and unchanged 40-hex head. The owner never clicks GitHub Merge.
After re-reading repository, PR, head, mergeability, checks, unresolved reviews,
write set and exclusions, the elected direct agent performs one ordinary guarded
merge only when the v2 gate returns `AUTONOMOUS`. Harness or control PRs bind a
local `LIVE_PR_HEAD` receipt via `scripts/delivery_harness.py context --pr`;
product work still uses an exact task contract. Then read back exact `main` and
post-merge CI. No force push, history rewrite, branch deletion or settings
change.

## DELIVERY_WORKFLOW

On `EXECUTE`, use the repository skill at
`.agents/skills/delivery-harness/SKILL.md`:

`CHECK -> CONTEXT -> ENTRY/OUTCOME -> EXECUTE -> RISK-ROUTED REVIEW -> FINISH -> EXACT MERGE GATE -> READ-BACK`

On `ORIENTATION`, do not start that workflow.

Keep design/spec/plan/implementation/tests/review as phases of one bounded atom,
not automatic owner approvals. Each substantial atom names decision delta,
uncertainty removed, finished capability/evidence, stop and next decision.
Replan instead of adding suffix atoms when the same blocker repeats, work only
prepares more work, the cheapest falsifier cannot run, a second route/provider
pivot appears or the evidence/time budget is exceeded.

Before custom construction apply `ADOPT -> WRAP -> FORK -> BUILD`. After the
first material blocker, consult the exact reuse registry and a smallest useful
set of official/maintained solutions before inventing infrastructure. This
research grants no dependency, provider, cost or external authority.

If a cheap mechanical fail can still kill the atom — wrong URL/path/header,
encoded comma/space, phrase or config drift, missing process key, call-cap or
payload shape — probe it on the working path first. Fix in place and re-probe.
Do not write the result packet (Catalog, receipts, readout, reviews, PR) around
a five-second fail. Ceremony starts only after that probe is viable or the
terminal is a real product/evidence result, not a leftover syntax miss.

## ACTIVE_TIME_GATE_CHECK

Before selecting new work, read `control/active_time_gates.json`; a due
unresolved marker routes to its exact `required_next_atom`. Legacy
`resume_router` text that only requests Project Sources activation, bundle
replacement or user smoke is historical compatibility metadata and MUST NOT
route work or interrupt the owner under `OWNER_MANAGED_OPTIONAL_EXPORT`.
Provider work must
also preserve the immutable `PROVIDER_ROUTE_CAPABILITY_REGISTRY_V1` binding at
`configs/provider_route_capability_registry_v1.yaml`; an absent route is
`REGISTRY_GAP`, not provider failure or implied authority.

## VALIDATION_AND_REVIEW

During implementation run the smallest tests for changed behavior and direct
consumers. After the first-install bootstrap, do not run a local full gate
before PR: the guarded merge is the sole executor of the project-bound primary
or tracked-only fallback for that exact candidate fingerprint. It consumes
already-completed exact-head CI and never repeats a passing local full gate
because bytes moved through stage, commit, push or PR. The first harness
installation alone uses the predecessor route and one pre-PR tracked-only
gate. A changed fingerprint invalidates evidence.

Risk-route review: launch isolated read-only critics for the exact contract
and diff (code always; goal/DoD, architecture and owner-UX on their triggers;
refactor only after correctness with measured cost). Launch `owner-ux-critic`
when owner-operable CLI/console/readout/manual flows change. Architecture review
must name what can pass tests and still break research validity. `SINGLE_AGENT_REVIEW_FALLBACK` is `NOT_READY` for merge; the
owner-attention gate denies PASS evidence that records it.

Before task closure run the proportional `FACTORY_FIT_REVIEW` and
`PRODUCT_HORIZON_RADAR` from the domain policy. Generated files are never
hand-edited. Exception text, secrets, absolute machine paths and raw sensitive
values never enter receipts.

## LEGACY_LOCAL_HANDOFF_COMPATIBILITY

`INPUT=DIRECT_PROMPT` remains the default. `LOCAL_HANDOFF:` and
`ACCEPT_LOCAL_HANDOFF:` are dormant read-only compatibility triggers governed
by `docs/agent/HANDOFF_PROTOCOL.md`; they cannot select work or widen authority.
Never search for the newest handoff. The historical marker `GPT control plane owns canonical`
describes legacy acceptance ownership only and does not
reactivate GitHub Baton or override the Delivery Harness.

## SECURITY_AND_EXTERNAL_BOUNDARY

Operate inside the elected repository/worktree. Never create, request, display,
store or commit API keys, tokens, cookies, passwords, private endpoints, seed
phrases, private keys, wallet recovery or signer material. `.env.example` is
placeholder-only.

Provider/API/RPC/WSS, credentials, purchases, package adoption, deployment,
account/repository settings, wallet/signer/transaction and real money require
their exact domain gate. Public official documentation may be read when it
changes a decision. GitHub routine delivery transport is allowed only inside
the bounded objective and does not grant unrelated Issue discovery or mutation.

## LANGUAGE_AND_MODEL_EFFORT

Speak to the owner in Russian by default; keep paths, code, schemas, enums and
exact errors canonical. Explain new terms simply before technical detail.

Recommend model effort exactly once before a substantial atom/chain and once at
its material checkpoint before the next scope, never on microsteps. `LUNA_MAX`
is the bounded implementation workhorse; use `SOL_XHIGH` for material
architecture, contracts, schemas, difficult root cause, PIT/statistical or
security truth; `SOL_MAX` only for irreversible/high-impact or unresolved
adversarial work; `TERRA_XHIGH` is fallback; `ROUTINE_NO_SWITCH` covers simple
smoke/read-back/merge. Advice grants no action authority.
