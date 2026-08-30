---
task_id: CTRL-MERGE-READINESS-BEFORE-OWNER-PHRASE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6850bdb15d6c2547f7f768bfc6c1b97c9a1b4636
  expected_upstream: origin/main
  expected_upstream_oid: 6850bdb15d6c2547f7f768bfc6c1b97c9a1b4636
  expected_branch: cursor/ctrl-merge-readiness-before-owner-phrase-v1
  dirty_mode: ALLOW_REPORTED
objective: Close owner-phrase loops by requiring machine merge-readiness PASS before any merge phrase, refusing LIVE_PR_HEAD for diffs outside harness_control_write_prefixes, and failing closed on invalid task-contract frontmatter at pre-commit.
managed_write_set:
- docs/tasks/CTRL-MERGE-READINESS-BEFORE-OWNER-PHRASE-V1.md
- scripts/owner_attention_gate.py
- scripts/delivery_harness.py
- scripts/validate.ps1
- tests/test_delivery_harness_merge_guard.py
- tests/test_delivery_harness_context.py
- tests/test_delivery_harness_skill.py
- .agents/skills/delivery-harness/SKILL.md
- delivery-harness/templates/portable-core/dot-agents/skills/delivery-harness/SKILL.md
- delivery-harness/templates/portable-core/dot-cursor/commands/delivery-finish.md
- delivery-harness/templates/portable-core/scripts/delivery_harness.py
- delivery-harness/templates/portable-bundle-manifest.json
- docs/evidence/control/delivery_harness_acceptance_v1.json
- docs/agent/DELIVERY_HARNESS_PROTOCOL.md
- docs/agent/EXECUTION_ROUTER_PROTOCOL.md
- .cursor/commands/delivery-finish.md
- AGENTS.md
- catalog/assets/core.yaml
- docs/evidence/control/a1_merge_readiness_before_owner_phrase_completion_v1.json
- docs/evidence/control/a1_merge_readiness_before_owner_phrase_review_v1.json
- docs/evidence/control/a1_merge_readiness_before_owner_phrase_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- AUTHORITY_WIDENING
- LIVE_PR_HEAD_BYPASS_EXTENDED_TO_PRODUCT
- HARNESS_CONTROL_PREFIX_WIDEN_FOR_PRODUCT_PATHS
- MERGE_WITHOUT_PHRASE
- PHRASE_STOP_BEFORE_MERGE_READINESS
- CATALOG_CRLF_REDESIGN
- CI_ELIGIBILITY_REWRITE
- CRITIC_ORCHESTRATION_REWRITE
- PROVIDER_OR_NETWORK_CALL
- SECRET_IN_RECEIPTS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/control/a1_merge_readiness_before_owner_phrase_completion_v1.json
    - docs/evidence/control/a1_merge_readiness_before_owner_phrase_review_v1.json
    - docs/evidence/control/a1_merge_readiness_before_owner_phrase_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-MERGE-READINESS-BEFORE-OWNER-PHRASE-V1

`SPEC_ROUTE=BOTH`. Git contract is execution authority. Base is exact `main`
after PR #222 (`6850bdb15d6c2547f7f768bfc6c1b97c9a1b4636`).

## DECISION_DELTA
Owner merge-phrase is asked only after machine merge-readiness PASS on the
exact head. `context --pr` cannot mint `LIVE_PR_HEAD` for a product-shaped
diff. Invalid task-contract `status` cannot survive pre-commit.

## UNCERTAINTY_REMOVED
Whether a green GitHub CI plus owner phrase is enough to merge. It is not.
Phrase is owner authority only. Write-set, identity mode, skip-proof,
factory-fit/review hash-bind, and task-schema are machine gates and must fail
before the owner is interrupted.

## CAPABILITY_OR_EVIDENCE
`--merge-readiness` JSON + non-zero; `IDENTITY_MODE_MISMATCH` on product
`--pr`; staged task-contract schema probe; skill/protocol one-line order.

## STOP
CTRL_MERGE_READINESS_BEFORE_OWNER_PHRASE_PASS_READY_FOR_MERGE_GATE

## NEXT
Return to product/research (`/hypothesis-forge`). No catalog CRLF atom and no
critic-orchestration rewrite unless a new fail still kills a later product
merge after this gate exists.

---

# PRD

## 1. Owner intent

Stop non-product merge loops of the class seen on PR #222 and earlier product
PRs: the owner is asked for an exact phrase, then the gate DENY's a machine
check, then a fix commit invalidates the phrase.

Named consumer: the elected direct agent (`DIRECT_CURSOR_DELIVERY` /
`DIRECT_CODEX_DELIVERY`) at FINISH. Secondary consumer: owner, who should see
at most one phrase per unchanged 40-hex head.

## 2. Problem / observed loops (closed set)

These are the same class: **owner-facing or long CI starts before a machine
gate that is still mandatory**.

| ID | Symptom on #222 / prior | Machine truth already exists | Wrong timing |
|----|-------------------------|------------------------------|--------------|
| A | `--pr` / `LIVE_PR_HEAD` on product files → `write_set_pass` DENY after phrase | `harness_control_write_prefixes` vs task `managed_write_set` | Identity chosen at merge, not at context |
| B | Agent "fixes" A by widening control prefixes | Prefix list is control allowlist | Treats product as control |
| C | No dry-run of merge checks without phrase | `build_grounded_merge_request` + `evaluate` | Phrase is the first full evaluate |
| D | `IMPLEMENTATION_UNVERIFIED` lives until merge | Task schema enum | Schema only on `context --contract` |
| E | T11 `skipTest` without `DELIVERY_PREFLIGHT_NONCRITICAL_SKIP` | `--ci-owned-delivery` skip policy | GitHub CI does not run it; merge primary does |
| F | `factory_fit_pass` DENY: evidence not in context / stale hashes / `PROPORTIONAL_REVIEW` / `project_checks` without `PASS_` | `bound_delivery_evidence` | Evidence rebound after phrase |
| G | Critics return after PR is already open on an older snapshot | Isolated critics + inventory sha | Finish/PR before RISK-ROUTED REVIEW on the fingerprint that will be approved |

Out of this atom: catalog CRLF/hash ceremony redesign; CI eligibility rewrite;
distributed critic runtime; bind-evidence two-commit algorithm.

## 3. Canonical vs practice

Protocol order is:

`EXECUTE → RISK-ROUTED REVIEW → FINISH (push/PR) → EXACT MERGE GATE → phrase`

Practice inverted FINISH/PR ahead of review and phrase ahead of machine
readiness. This atom does **not** forbid draft PR / CI overlap. It forbids
**asking the owner phrase** and **claiming finish-ready** until machine
readiness PASS on that exact head, which already includes hash-bound
independent review + factory fit for task receipts.

## 4. Outcome

1. Agent cannot honestly stop for a merge phrase until
   `scripts/owner_attention_gate.py --merge-readiness` returns
   `ready_for_owner_phrase: true` for the exact local HEAD / PR / receipt.
2. `scripts/delivery_harness.py context --pr N` fails closed with
   `IDENTITY_MODE_MISMATCH` when any path in
   `merge-base(HEAD, origin/<default_branch>)...HEAD` is outside
   `merge_policy.harness_control_write_prefixes`. Hint: use `--contract`.
3. Staging a harness task contract with invalid frontmatter (including
   `status` not in the schema enum) fails pre-commit before PR.
4. Skill + protocol + router + `delivery-finish` state one order:

   `CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`

   Explicit anti-pattern: product diff + `context --pr`; widening
   `harness_control_write_prefixes` to admit product paths.

## 5. Non-goals

- No change to the exact owner phrase regex.
- No `gh pr merge` without phrase.
- No extending `LIVE_PR_HEAD` factory-fit bypass to product task receipts.
- No adding this atom's product-like paths to control prefixes in order to
  merge it via `--pr`. **This atom merges via `--contract`.**
- No rewrite of skip-policy, CI shards, or catalog line-ending rules.
- No new critic launcher / fingerprint service. Skill text only: critics run
  on the inventory that `bind-evidence` will hash; FAIL or later content
  change → re-review + rebind before merge-readiness.

## 6. Cheapest falsifiers

1. Product path in a `--pr` context builder → not `LIVE_PR_HEAD` receipt.
2. Frontmatter `status: IMPLEMENTATION_UNVERIFIED` staged under `docs/tasks/`
   → pre-commit / probe non-zero `TASK_CONTRACT_SCHEMA_INVALID`.
3. `--merge-readiness` with a task receipt whose write-set excludes a changed
   path → JSON shows `write_set_pass: false`, `ready_for_owner_phrase: false`,
   no merge submitted.
4. `--merge-readiness` must not require `--approval-phrase` and must not
   invoke `gh pr merge`.
5. Skill contains `--merge-readiness` and the anti-pattern line.

## 7. This atom's own merge (dogfood)

Use task-contract context, not `--pr`. After exact-head CI, run
`--merge-readiness` **before** asking the owner phrase. If readiness fails,
do not interrupt the owner.

---

# SSD

## S1. `--merge-readiness`

Add exclusive CLI flag on `scripts/owner_attention_gate.py` next to
`--guarded-merge` / `--post-merge-readback`.

Required args: `--repository`, `--pr-number`, `--route`, `--actor`,
`--context-receipt`. Forbidden: `--approval-phrase` (if present →
`MERGE_READINESS_PHRASE_NOT_ALLOWED`).

Behavior:

1. Reuse `build_grounded_merge_request` live GitHub/CI/write-set/factory-fit
   path (same as guarded merge).
2. Set `owner_approval` to `null` before `evaluate`.
3. Never call `gh pr merge`.
4. Emit JSON `schema: smial.merge-readiness` `schema_version: 1.0` with
   `ready_for_owner_phrase` (bool), `decision`, `reasons`, `merge_checks`,
   `identity_mode` (`LIVE_PR_HEAD` | `TASK_CONTEXT_RECEIPT`),
   `merge_submitted: false`.
5. Exit `0` only when `ready_for_owner_phrase` is true. That is exactly:
   `evaluate` would have reached `EXACT_MERGE_APPROVAL_REQUIRED` (machine
   preconditions all true, no owner-attention triggers, no stricter stop).
6. Exit `2` on `DENY`. Map `MERGE_CHECK_FAILED:<check>` through unchanged.
   Additional stable reasons allowed: `IDENTITY_MODE_MISMATCH` is **not**
   produced here (it is context `--pr` only).

`ready_for_owner_phrase: true` is **not** merge authority and must never
print `AUTONOMOUS` / `DIRECT_AGENT_EXACT_MERGE_GATE_PASS`.

Dirty tree: keep `LOCAL_REPOSITORY_IDENTITY_MISMATCH` (same as guarded merge).
Do not relax.

Skip-proof (loop E) is covered because primary validation is the same
`--ci-owned-delivery` command. Do not duplicate skip-policy in this atom.

Factory-fit (loop F) is covered because `bound_delivery_evidence` is unchanged.
Skill must say: last content commit → `bind-evidence --apply` →
`--merge-readiness` → only then phrase.

## S2. `context --pr` identity refuse

In `build_live_pr_head_receipt` (repo script and portable-core copy):

After profile/harness load, compute changed paths
`git diff --name-only --no-renames` for
`merge-base(HEAD, origin/<default_branch>)...HEAD`.

If the set is empty → `IDENTITY_MODE_EMPTY_DIFF`.
If any path is not `path_in_managed_write_set` against
`harness_control_write_prefixes` → `IDENTITY_MODE_MISMATCH`.

Do not write a receipt. Do not suggest prefix edits.

Control-only diffs continue to build `LIVE_PR_HEAD` as today.
Existing test `test_live_pr_head_receipt_does_not_require_a_task_contract`
must mock the new diff as control-only (or empty-diff fail — prefer mock a
control path already in prefixes, e.g. `AGENTS.md`).

## S3. Staged task-contract schema probe

Harness task contracts are files under `docs/tasks/` whose frontmatter
contains `task_id` and `allowed_routes`.

On pre-commit (`scripts/validate.ps1 -PreCommit`), after secret scan, run:

`uv run --locked --managed-python python -B scripts/delivery_harness.py check-task-contracts --staged`

Implementation in `delivery_harness.py`:

- `git diff --cached --name-only --no-renames -z`
- For each staged path under `docs/tasks/` ending `.md`, if frontmatter has
  `task_id` and `allowed_routes`, parse with the same `parse_task_contract`
  schema path using `task_id` from YAML.
- Invalid enum/schema → `TASK_CONTRACT_SCHEMA_INVALID` non-zero.
- Unstaged historical invalid files are not scanned (do not fail the repo).

Do not invent `IMPLEMENTATION_*` aliases.

## S4. Docs / skill / commands

One order, copied without contradiction:

`CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`

Update at least:

- `.agents/skills/delivery-harness/SKILL.md` (and portable skill)
- `docs/agent/DELIVERY_HARNESS_PROTOCOL.md`
- `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`
- `.cursor/commands/delivery-finish.md` and portable finish
- `AGENTS.md` finish/merge paragraph only

Must state:

- Product work: `context --contract` + `--task-id`.
- `context --pr` only when the candidate diff is entirely inside
  `harness_control_write_prefixes`.
- Do not widen those prefixes to land a product write set.
- STOP for phrase only after `--merge-readiness` `ready_for_owner_phrase: true`
  on unchanged HEAD.
- Isolated critics before asking phrase; if inventory bytes change after
  review, re-run required critics and `bind-evidence` before readiness.
- Draft/open PR for CI overlap is allowed; phrase and finish-ready are not.

## S5. Tests (DoD)

Existing files only (keep write set inside already-listed test modules):

- `test_delivery_harness_merge_guard.py`: merge-readiness without phrase;
  `gh pr merge` absent from runner calls; write_set fail → not ready;
  machine-pass + null approval → ready_for_owner_phrase true and not AUTONOMOUS.
- `test_delivery_harness_context.py`: product path in diff →
  `IDENTITY_MODE_MISMATCH`; control-only diff still builds LIVE_PR_HEAD.
- `test_delivery_harness_skill.py`: markers `--merge-readiness`,
  `ready_for_owner_phrase`, `IDENTITY_MODE_MISMATCH`.
- Schema probe: unit-test the staged-file helper with a temp index or
  injected path list (no live `git commit` in the test).

## S6. Evidence / Factory Fit

`FACTORY_FIT_REVIEW=FAST_PATH` control-process. `CAPABILITY_RADAR_NOW=NONE`.
Completion evidence `mode` for factory-fit must be `FAST_PATH` or `FULL_REVIEW`
(never `PROPORTIONAL_REVIEW`). `project_checks` all `PASS_*`. Bind DELIVERY_EVIDENCE
paths in this contract (already in frontmatter). After last content commit run
`harness_sync.py bind-evidence --apply`.

## S7. Rollback

Revert the PR. No data-plane change.

## Authority and non-claims

No provider/API/RPC/WSS, credentials, wallet, cash, settings, branch deletion.
Passing merge-readiness, CI, or merge is not canonical DONE, alpha, or
cashflow.
