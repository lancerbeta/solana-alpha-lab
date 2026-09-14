---
task_id: DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1
task_version: '1.0'
status: VALIDATED
as_of: '2026-09-14'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b652a66af554d96fb4ce3e2de3410c1d04e8bfd1
  expected_upstream: origin/main
  expected_upstream_oid: b652a66af554d96fb4ce3e2de3410c1d04e8bfd1
  expected_branch: cursor/delivery-harness-deterministic-finish-v1
  dirty_mode: ALLOW_REPORTED
objective: "Make the normal delivery path deterministic so GitHub/CI stops acting as a linter for locally knowable failures: exact-head evidence bindings hash committed Git blob bytes, a read-only local preflight-push orchestrates existing validators before the first remote task-branch push, harness_control_write_prefixes return LIVE_PR_HEAD to a true control-plane route, owner navigation phrases can never mutate in the same turn, merge-readiness machine-renders the exact owner phrase, and actor CLI casing is normalized - no merge authority in this atom."
managed_write_set:
- docs/tasks/DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1.md
- scripts/harness_sync.py
- scripts/delivery_harness.py
- scripts/owner_attention_gate.py
- delivery-harness/harness.yaml
- delivery-harness/templates/portable-core/scripts/delivery_harness.py
- delivery-harness/templates/portable-core/dot-agents/skills/delivery-harness/SKILL.md
- delivery-harness/templates/portable-core/dot-cursor/commands/delivery-finish.md
- delivery-harness/templates/portable-bundle-manifest.json
- AGENTS.md
- .agents/skills/delivery-harness/SKILL.md
- .cursor/rules/10-input-routing.mdc
- .cursor/commands/delivery-finish.md
- docs/agent/DELIVERY_HARNESS_PROTOCOL.md
- tests/test_delivery_harness_context.py
- tests/test_delivery_harness_contract.py
- tests/test_delivery_harness_merge_guard.py
- tests/test_delivery_harness_skill.py
- tests/test_harness_sync.py
- tests/test_harness_sync_bindings.py
- tests/test_delivery_harness_authority.py
- tests/test_delivery_harness_bootstrap.py
- tests/test_delivery_harness_deterministic_finish.py
- delivery-harness/templates/portable-core/AGENTS.md.tmpl
- delivery-harness/templates/portable-core/delivery-harness/harness.yaml
- catalog/assets/core.yaml
- docs/evidence/control/a1_delivery_harness_deterministic_finish_completion_v1.json
- docs/evidence/control/a1_delivery_harness_deterministic_finish_review_v1.json
- docs/evidence/control/a1_delivery_harness_deterministic_finish_factory_fit_v1.json
- docs/evidence/control/delivery_harness_acceptance_v1.json
- docs/evidence/control/delivery_harness_factory_fit_v1.json
- docs/evidence/control/a1_delivery_harness_deterministic_finish_ux_v1.json
- docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- NO_MERGE_AUTHORITY_STOP_BEFORE_MERGE
- OWNER_AUTHORITY_WIDENING_REQUIRED
- MERGE_POLICY_SCHEMA_CHANGE_REQUIRED
- PRECHECK_NEEDS_GITHUB_OR_NETWORK
- TASK_CONTRACT_SCHEMA_EXPANSION_REQUIRED
- REVIEW_ROLE_SEMANTICS_MUST_CHANGE
- CI_ARCHITECTURE_REWRITE_REQUIRED
- PORTABLE_CORE_REDESIGN_REQUIRED
- SECOND_GENERIC_ORCHESTRATOR_REQUIRED
- PRODUCT_PATH_MUST_REMAIN_LIVE_PR_HEAD_FOR_CORRECTNESS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/control/a1_delivery_harness_deterministic_finish_completion_v1.json
    - docs/evidence/control/a1_delivery_harness_deterministic_finish_review_v1.json
    - docs/evidence/control/a1_delivery_harness_deterministic_finish_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1

## Managed write set additions (exact reasons)

- `tests/test_delivery_harness_deterministic_finish.py` — mandated 18-point
  acceptance matrix home.
- `delivery-harness/templates/portable-core/delivery-harness/harness.yaml` —
  required Part C/H source: portable prefix narrowing plus bundle-manifest
  hash propagation.
- `catalog/assets/core.yaml` — sanctioned `harness_sync --apply --base-ref`
  derived output for the cataloged bytes this atom changes.
- `docs/evidence/control/delivery_harness_acceptance_v1.json` and
  `docs/evidence/control/delivery_harness_factory_fit_v1.json` — pin
  retargeting after sanctioned edits of pinned files (precedent `5403a8ab`).

## Task Outcome Brief

Close the deterministic-finish gap in the normal delivery path. Six coupled
repairs, all control-plane, no product behavior:

- **A. Exact-head bindings**: `bind-evidence` hashes committed Git blob bytes
  (`git show <head>:<path>`), refuses a dirty candidate on `--apply`, and
  `--verify` checks committed bytes only. Git blob bytes are canonical; no
  CRLF normalization inside the hasher.
- **B. Preflight-push**: `scripts/delivery_harness.py preflight-push` is a
  read-only, local-only orchestrator over existing validators. It fails
  deterministically before the first remote push on identity mismatch, dirty
  tree, invalid contract, write-set violation, stale derived state, malformed
  or stale evidence, binding mismatch, review/fit inventory incoherence, and
  non-rebuildable context. No CI run, no critics, no `gh`, no push, no
  mutation, does not replace merge-readiness.
- **C. Narrow `harness_control_write_prefixes`**: remove product-shaped and
  history-shaped LIVE_PR_HEAD eligibility (factory runtime modules, Forge
  scripts, product fixtures/tests, catalog assets, PROJECT_MAP, pyproject,
  uv.lock, historical task/evidence exceptions). LIVE_PR_HEAD stays valid for
  real Delivery Harness control-plane self-maintenance. False negatives are
  acceptable; false positives are not.
- **D. Orientation cannot mutate**: owner navigation phrases return
  ORIENTATION verdicts read-only; the same turn never enters EXECUTE. An
  explicit execution/resume command is required for mutation.
- **E. Machine-rendered owner phrase**: `owner_attention_gate.py` renders the
  canonical phrase from pr_number + exact head, validates it with
  `re.fullmatch` against the base-bound `exact_phrase_pattern`, fails closed.
  `merge-readiness` always exposes `owner_phrase` (nullable); exact valid
  copy/paste phrase only when `ready_for_owner_phrase=true`. Rendering grants
  no approval and submits no merge.
- **F. Actor CLI normalization**: at the human CLI boundary, case variants
  (`cursor`/`Cursor`/`CURSOR`, `codex`/`Codex`/`CODEX`) normalize to canonical
  uppercase. Unknown actors stay invalid. No fuzzy aliases. Internal receipts
  remain uppercase.
- **G/H. Adapter convergence + portable core**: the canonical workflow gains
  the explicit PREFLIGHT-PUSH step across AGENTS.md, delivery-harness skill,
  portable-core skill, input-routing rule, delivery-finish commands and the
  protocol doc. Portable behavior changes propagate through the portable-core
  templates and bundle manifest hashes. No new overlapping protocol document,
  no Cursor-only semantics, no second orchestrator.

## Decision capsule

- `DECISION_DELTA`: the normal delivery path detects locally-knowable failure
  classes before the first remote push, and the owner phrase is machine output
  instead of agent reconstruction.
- `UNCERTAINTY_REMOVED`: whether a candidate is push-ready is now a
  deterministic local boolean assembled from existing validators, not a
  GitHub/CI discovery.
- `CAPABILITY_OR_EVIDENCE`: capability - `preflight-push` plus exact-head
  committed-byte bindings, exercised by this atom's own delivery.
- `STOP`: no merge; no review-role schema change; no CI architecture change;
  no second generic orchestrator; preflight stays thin orchestration over
  existing helpers.
- `NEXT`: owner reviews the exact PR/head and, on readiness, supplies the
  exact merge phrase.

## SPEC_ROUTE

`BOTH` — PRD + SSD inside this contract.

## PRD

- **Outcome:** a normal candidate can detect, before first remote push: stale
  evidence bindings; write-set violations; invalid task/evidence shape;
  derived-state drift; wrong committed-byte hashes; invalid LIVE_PR_HEAD
  eligibility; actor casing mistakes. Machine merge-readiness returns the
  exact owner phrase.
- **Product link:** delivery cost and certainty per atom; owner attention is
  spent only on the merge phrase.
- **Downstream consumer:** direct delivery agents (Cursor/Codex) at FINISH;
  owner at merge-readiness.
- **Success observable:** acceptance matrix tests green; this atom's own
  delivery uses preflight-push PASS before its first remote push.
- **Invalidation:** a later atom must not reintroduce worktree-byte bindings
  or widen control prefixes to product paths.
- **Non-goals:** review routing semantics; remediation-history schema; critic
  orchestration; CI architecture; evidence database; workflow state machine;
  catalog architecture; .gitattributes policy; product/research behavior.

## SSD

- **Baseline:** origin/main `b652a66af554d96fb4ce3e2de3410c1d04e8bfd1`.
- **Design:** bind-evidence reuses `git show <head>:<path>` for both apply and
  verify; preflight-push composes `check_harness`, task-contract validation,
  `check_drift` (scoped), bind-evidence verify, `build_context_receipt`
  rebuild, and write-set/branch/identity assertions already owned by
  `delivery_harness.py`/`harness_sync.py`/`owner_attention_gate.py`. Prefix
  narrowing edits only the live and portable harness.yaml lists. Phrase
  rendering lives in `owner_attention_gate.py` next to
  `validate_exact_merge_approval`. Actor normalization is a CLI boundary map
  in the same two scripts.
- **Failure modes:** deterministic DENY (exit 2) with stable reason codes;
  network/`gh` calls are structurally absent from preflight (monkeypatched
  runner asserts no such call).
- **Validation:** targeted unit/integration tests covering the 18-point
  acceptance matrix, including dirty-worktree apply refusal, committed-blob
  binding identity, CRLF worktree drift neutrality, preflight DENY classes,
  LIVE_PR_HEAD mismatch classes, orientation read-only contract,
  actor casing, phrase rendering/regex/null semantics, and no-merge on
  rendering.
- **Rollback:** revert branch.

## Definition of Done

- Acceptance matrix tests green in targeted suites.
- Dogfood: this atom passes `preflight-push` before its first remote push.
- PR exact-head CI green; merge-readiness reports `ready_for_owner_phrase:
  true` with machine-rendered phrase; stop for the owner phrase.

## Owner gates

Exact merge phrase only after CI on unchanged head. No merge authority in
this atom.
