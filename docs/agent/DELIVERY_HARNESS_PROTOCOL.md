---
protocol_id: DELIVERY_HARNESS_PROTOCOL_V1
status: ACTIVE_IMPLEMENTATION_CANDIDATE
as_of: '2026-08-14'
harness_id: DELIVERY_HARNESS_V1
---

# Delivery Harness Protocol

## Exact workflow

`CHECK -> CONTEXT -> ENTRY/OUTCOME -> EXECUTE -> RISK-ROUTED REVIEW -> FINISH CONTENT -> BIND EVIDENCE -> PREFLIGHT-PUSH -> PUSH/PR -> EXACT-HEAD CI -> MERGE-READINESS -> OWNER PHRASE -> GUARDED MERGE -> POST-MERGE READBACK`

Owner navigation phrases inspect Git truth without a new contract and must not
mutate. `ORIENTATION` may return `CONTINUE` plus the exact recommended task but
never enters `EXECUTE` in the same turn; a subsequent explicit execution/resume
command is required. Discriminate `ORIENTATION` versus `EXECUTE` with
`.cursor/rules/10-input-routing.mdc`. The workflow below starts only on
`EXECUTE`.

### Check and context

Run the deterministic harness check and require an exact Git task contract.
Generate L0/L1 context; L2/L3 are on-demand. Never discover the task from
recency. Route and context receipt stay bound to the candidate.

### Entry/outcome

Freeze owner decision, product outcome, named consumer, cheapest falsifier,
user-visible result, non-goals, evidence budget and replan trigger. Choose
`SPEC_ROUTE = NONE | PRD_LITE | DESIGN_SPEC | BOTH`; do not duplicate the task
contract.

Each substantial atom declares `DECISION_DELTA`, `UNCERTAINTY_REMOVED`,
`CAPABILITY_OR_EVIDENCE`, `STOP` and `NEXT`. Replan after a repeated blocker,
preparatory-only atom, impossible falsifier, second route/provider pivot or
evidence/time budget breach.

### Execute and review

Routine bounded delivery is autonomous. Use targeted tests; after bootstrap
the guarded merge is the sole project-bound gate executor for the unchanged
fingerprint. If a leftover space, encoded query, wrong endpoint or shape can
still fail the atom, probe and fix it on the working path before Catalog,
receipts, reviews or PR. Do not document a five-second mechanical miss.
Code review is mandatory. Goal/DoD, architecture, refactor and owner-UX critics
are trigger-routed and must run in isolated context. The exact required
role-set is frozen by the task contract `required_review_roles` and
strengthened by deterministic floors (CODE_REVIEWER always; ARCHITECTURE_CRITIC
on control/schema/authority surfaces); contracts without the field and
LIVE_PR_HEAD resolve to the legacy triple
CODE_REVIEWER+GOAL_DOD_CRITIC+ARCHITECTURE_CRITIC. Machine gates
(bind-evidence, preflight-push, merge-readiness, guarded merge) require the
exact resolved role-set through one shared resolver; a candidate cannot pass
bind/preflight and later fail merge because stages interpreted roles
differently. Launch `owner-ux-critic`
only when the diff changes owner-operable surfaces (CLI/console entrypoints,
manual operator flows, readouts, cockpit/workbench interaction, or owner-facing
error/next-action copy). `SINGLE_AGENT_REVIEW_FALLBACK` is `NOT_READY` for merge;
deterministic validation still runs.

### Derived-hash maintenance

Catalog integrity hashes, generated navigation views and manifest checkpoints
are derived state.

Routine FINISH (exact task/control base known):

```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <exact expected_base>
```

Recovery / orphan integrity drift / CI fail-closed repair (full Catalog oracle):

```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply
```

`--apply --full` is the same full oracle. Never hand-edit a derived `sha256:`
field or generated projection; manual rebinding caused repeated red CI runs on
2026-08-21 (LF/CRLF blob drift). Primary records (source files, task contracts,
evidence) stay read-only to sync; if the catalog itself fails validation,
fix the primary record first — sync never invents records.

### Delivery-evidence binding

FINISH closes the delivery-evidence hash chain with:

```text
uv run --locked --managed-python python -B scripts/harness_sync.py bind-evidence --task-id <TASK_ID> --apply
```

`bind-evidence --verify` checks the active branch chain against the task
contract scope. `bind-evidence --verify-all-delivered` is a read-only audit of
historical completion chains. Sync updates only binding fields the guard reads;
verdicts, findings and non-claims remain agent-owned. `--apply` operates
against the committed HEAD and requires a clean worktree; implementation
bindings hash committed Git blob bytes (`git show <head>:<path>`), so
worktree/CRLF representation can never alter a binding.

### Preflight-push

After the evidence commit and before the first remote push of the task branch,
run the read-only local preflight:

```text
uv run --locked --managed-python python -B scripts/delivery_harness.py preflight-push --task-id <TASK_ID> --contract docs/tasks/<TASK_ID>.md --route <ROUTE> --actor <ACTOR>
```

It orchestrates existing validators (identity, contract shape, write set,
derived drift, evidence chain, deterministic context rebuild) plus two
local classes that CI previously had to catch after push: SEPARATE
historical `{path,sha256}` pins whose target is in the candidate diff, and
worktree bytes that differ from `git show HEAD:<path>`. Frozen-commit
evidence files listed in `FROZEN_SEMANTICS_EVIDENCE_FILES` are exempt.
A historical pin to a harness-owned aggregate path (Catalog manifest, asset
registries, generated navigation outputs; one shared set read from the
`harness_sync` constants `MANIFEST_RELATIVE`, `ASSET_REGISTRIES`, `NAV_OUTPUTS`)
is snapshot-only: it records the bytes then and never blocks a later change.
Aggregates stay guarded by `harness_sync.check_drift` (derived drift and Catalog
validation) in the same preflight; pins to every other path keep the DENY.

Evidence policy (forward-only): commit what cannot be regenerated (real-run
receipts, review verdicts, completion bindings, owner/critic decisions). For a
reproducible synthetic run commit a compact summary: key numbers, sha256 of the
outputs and the exact reproduce command, not multi-hundred-line machine dumps.
Goldens a test consumes belong in `tests/fixtures/`, not `docs/evidence/`.
Zero GitHub/network calls and zero mutations. Exit 0 and
`ready_for_first_push: true` are required before any normal remote task-branch
push; it claims no CI, no merge authority and no product acceptance, and does
not replace merge-readiness.

### CI fail-closed presentation

When derived hashes drift, child validators still fail closed. Before their
details, `validate_ci.py` and `validate_baton.py` print one actionable line.
A scoped `--check --paths-from-staging` failure also prints the actual impact
class and planned unique HASH_SCOPE bound (example):

```text
DERIVED_HASH_DRIFT: class=RECORD_ADD_OR_MOVE hashed≤4; run uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <exact expected_base>
```

`--apply` and `--check` print `HARNESS_SYNC_PLAN` on stderr before the first
hash. Scoped `--check --paths-from-staging` uses the same HASH_SCOPE classifier
as `--apply` (index vs HEAD, including NAV_OUTPUTS when nav is required).
Unscoped `--check` remains the whole-catalog fail-closed backstop.

When no unambiguous task `expected_base` is available, the same line ends with
`# RECOVERY_FULL_ORACLE` and bare `--apply` is correct.

Pre-commit runs a scoped staging check only:

```text
uv run --locked --managed-python python -B scripts/harness_sync.py --check --paths-from-staging
```

The summary does not replace validation; it only surfaces the sanctioned repair.

### Process throughput guardrails

After the harness-sync control sprint (derived-hash sync, evidence binding,
actionable CI drift messages), the control plane is **frozen** for the next
**five substantive product or research atoms**.

During the freeze, do not change `delivery-harness/`, owner-attention gate
semantics, evidence protocol, CI architecture, or harness scripts except for a
**confirmed blocker** on the active atom (machine `DENY`, repeated friction on
the working path, or a security defect).

Completion evidence MAY include optional `delivery_efficiency` counts:

- `substantive_commits` — product/research implementation commits;
- `repair_commits` — derived-hash, evidence-rebind, or CI-drift repair commits;
- `control_only_commits` — control/harness-only commits;
- `repair_ratio` — `(repair + control_only) / total` when total > 0.

Use:

```text
uv run --locked --managed-python python -B scripts/delivery_efficiency.py --base <oid> --head HEAD --json
```

Factory Python is guarded by a scoped static gate:

```text
uv run --locked --managed-python python -B scripts/validate_factory_static.py
```

Replan the process if three consecutive product atoms each show
`repair_commits >= 2` or `repair_ratio > 0.30`.

### Finish and merge

Run Factory Fit, Product Horizon and capability radar. Record exact inventory,
head/tree, tests, limitations, non-claims and rollback. Capability candidates
grant no installation/credential/network/spend authority. Require exact-head CI, then
`scripts/owner_attention_gate.py --merge-readiness` with `ready_for_owner_phrase: true`,
and only then the exact owner PR/head phrase; the readiness response exposes
`owner_phrase` with the exact copy/paste phrase when ready, `null` otherwise.
The owner never
clicks GitHub Merge. Re-read machine state, evaluate v2, merge once only on
`AUTONOMOUS`, then verify the base-bound profile default branch and its
post-merge CI. Order:
`CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`.
`context --pr` (`LIVE_PR_HEAD`) is only for diffs entirely inside
`harness_control_write_prefixes`; a product path is `IDENTITY_MODE_MISMATCH`.
Product work still requires an exact task contract (`--contract`).
Do not widen control prefixes to admit a product write set.
The guarded submission's `merge_commit` becomes the expected default-branch
head. The self-hashed submission is a mandatory input to
`--post-merge-readback --submission-receipt <GUARDED_SUBMISSION_JSON>`; the
separate hash-bound terminal receipt must prove the
ordered parents are exactly the frozen base then approved head, plus exact push
CI success. Read-only polling needs no
second owner approval; merge submission alone is never a completed delivery.

For task-contract receipts, post-merge readback replays the complete frozen
delivery context from immutable approved-head Git bytes in a private scratch
repository with the task's frozen upstream. It proves the clean head/tree,
task path/hash, exact selected context and frozen delivery scope independently
of the elected checkout or advanced origin/main. Base policy/profile remain
bound to the frozen base. The source checkout, refs, index and configuration
are not rewound or changed by that proof. Only ordinary tracked files are
supported; symlinks/submodules fail closed. LIVE_PR_HEAD retains its existing
verification path because it has no frozen task-contract base binding.
Git process write-location overrides and command-scope configuration other
than safe.directory allowances fail closed; scratch hooks/fsmonitor are
disabled. Unsafe Windows path aliases fail before scratch materialization.
The preserved PR head branch must also equal the frozen task branch.
Pre-merge live context verification and task Git freshness are unchanged.
This is immediate exact-merge closure, not historical ancestor acceptance.

Guarded merge requires every key present on the expected-base
`delivery-harness/project-profile.yaml` to match the live profile. Additive
live-only top-level keys do not raise `PROJECT_PROFILE_BASE_BINDING_INVALID`.
Changing `validation` commands or `repository` identity still fails closed.

When the bound profile sets `factory_v1_readiness_contract`, Entry Gate
selects that file in task context and `check` fail-closes on a wrong path,
missing file, invalid mapping, or a present-but-wrong
`live_invariant_owner`. The product stamp `entry_gate_resolves_this_file`
is not a `check` predicate.

Validation commands are project-profile bindings, not portable-core guesses.
The guard executes them with `shell=false`; it never trusts a pre-existing local
receipt. A portable seed with null bindings may CHECK and build CONTEXT, but it
must report `delivery_gate_ready=false` and cannot merge until bootstrap binds
the repository's actual commands and exact PR-CI identity. In the normal path,
the guard runs the local focused primary once and consumes existing exact PR
CI as its full-suite evidence. The tracked-only fallback is exceptional and is
executed by that same guard only when the primary route is ineligible; it is
never a second pre-PR plus merge-time local run. A `LIVE_PR_HEAD` control PR
whose focused primary is ineligible consumes already-green exact-head GitHub CI
instead of repeating a local full suite. The first harness installation
is delivered by the predecessor owner-approved route after one pre-PR
tracked-only gate; the new guard activates only after its policy/profile exist
on the default branch.

## Context and cloud export

Git is working project memory. `OWNER_MANAGED_OPTIONAL_EXPORT` means the harness
never prompts for Project Sources/Project Instruction replacement or smoke and
never uses cloud activation as an execution or DONE gate. Historical release
bytes remain audit-only.

## Direct client entry

The executing client chooses the route. Cursor Agent uses
`DIRECT_CURSOR_DELIVERY` / `CURSOR`. Codex uses `DIRECT_CODEX_DELIVERY` /
`CODEX`. Claude Code uses `DIRECT_CLAUDE_CODE_DELIVERY` / `CLAUDE_CODE` and
reads root `CLAUDE.md`, whose only instruction line is `@AGENTS.md`. Another
coding client uses `DIRECT_OTHER_DELIVERY` / `OTHER` and names itself in the
start checkpoint (`coding_client`, `model` or `UNKNOWN`). That declaration is
not a grant. Unknown names are not rewritten to `OTHER`. Skills are read by
exact path when a client does not auto-load `.agents/skills`.

Starter prompt for a future client, one exact task, no standing task picker:

```text
Client: <coding client name>
Route: DIRECT_OTHER_DELIVERY
Actor: OTHER
Model: UNKNOWN
Task: docs/tasks/<TASK>.md
Read AGENTS.md, then .agents/skills/delivery-harness/SKILL.md.
Run scripts/delivery_harness.py check, then context with this route and the exact task.
Execute only that task. Stop at the exact owner merge phrase.
```

Claude Code uses the same steps with route `DIRECT_CLAUDE_CODE_DELIVERY` and
actor `CLAUDE_CODE`. Cursor and Codex keep their existing routes. A route
change mid-atom needs a saved checkpoint and an explicit replan. The current
PR is authorized only by the frozen expected-base policy.

## External boundary

This protocol grants no provider/API/RPC/WSS, credential, dependency adoption,
payment, deployment, settings, wallet, signer, transaction, cash, destructive
or force/history authority.
