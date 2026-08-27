---
task_id: HFIC_REPO_LOCAL_RDP_GUARD_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-27'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5c5a14b5eb554f4b44f8f58afc15c58ad2495526
  expected_upstream: origin/main
  expected_upstream_oid: 5c5a14b5eb554f4b44f8f58afc15c58ad2495526
  expected_branch: cursor/hfic-repo-local-rdp-guard-v1
  dirty_mode: ALLOW_REPORTED
objective: Correct the importer Git publication guard so the canonical
  gitignored local/factory_v1/data_plane subtree is the only in-repo
  write target, without touching the already-bound production panel.
managed_write_set:
- docs/tasks/HFIC_REPO_LOCAL_RDP_GUARD_V1.md
- src/solana_alpha_lab/factory/early_market_panel_importer.py
- tests/test_early_market_panel_importer.py
- tests/test_hfic_repo_local_rdp_guard.py
- docs/evidence/hfic_repo_local_rdp_guard/a1_guard_corrective_v1.json
- docs/evidence/hfic_repo_local_rdp_guard/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_repo_local_rdp_guard/a1_delivery_factory_fit_v1.json
- docs/evidence/hfic_repo_local_rdp_guard/a1_delivery_completion_evidence_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_API_RPC_WSS
- PRODUCTION_RDP_DELETE_OR_REBIND
- X_Y_SCORE_OR_EXPERIMENT
- HYPOTHESIS_FORGE_SLASH_INVOKE
- TWO_RUNG
- CLOSED_FAMILY_REOPEN
- PHYSICAL_PATH_IN_GIT
- PRODUCTION_BYTES_IN_GIT
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
      - docs/evidence/hfic_repo_local_rdp_guard/a1_guard_corrective_v1.json
      - docs/evidence/hfic_repo_local_rdp_guard/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_repo_local_rdp_guard/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_repo_local_rdp_guard/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_REPO_LOCAL_RDP_GUARD_V1

## Task Outcome Brief

- **Owner decision:** correct the leftover `DATA_ROOT_INSIDE_GIT` over-deny.
  Keep the already-bound production panel untouched.
- **Product outcome:** importer may write inside the repository only at
  the canonical subtree `local/factory_v1/data_plane`, and only when Git
  itself reports `local/` ignored, the path has no symlink components,
  the target has no tracked or staged files, and it does not overlap
  `.git`. Any other in-repo descendant stays DENY.
- **Named consumers:** post-merge production-local bind path; importer
  publication fences.
- **Cheapest falsifier:** isolated git-repo regressions listed in the
  owner contract. Production RDP is read-only for this atom.
- **Evidence budget:** offline only. `provider_calls=0`.
- **Non-goals:** rebind, delete, move, or recapture the production
  dataset; `/hypothesis-forge`; X↔Y; TWO_RUNG; provider calls;
  physical paths or production bytes in Git.

## Guard policy

ALLOW in-repo only when all of these hold:

- resolved data root is the canonical subtree
  `<repo>/local/factory_v1/data_plane` (exact root or descendant after
  resolve);
- `git check-ignore` reports `local/` ignored;
- data root and every path component through the worktree are not
  symlinks;
- `git ls-files --cached` and staged diff under the target are empty;
- target does not overlap `.git`;
- every Git command used by the guard exits successfully.

DENY: repo root; `.git` and descendants; any other repository
descendant including untracked-but-not-ignored; tracked or staged
target; symlink in any path component; source/data-root overlap;
broad or filesystem-root unsafe target; Git command failure.

External temp roots remain ALLOW.

## DECISION_DELTA

In-repo writes are bound to the canonical ignored data-plane subtree,
not to a generic `local/` prefix and not to a blanket worktree ban.

## UNCERTAINTY_REMOVED

Whether a clean checkout can legally bind into the project-default
RDP without opening an arbitrary in-repo write zone.

## CAPABILITY_OR_EVIDENCE

Corrected publication guard plus isolated regressions.

## STOP

Exact-head CI green. Owner merge phrase. No production mutation.

## NEXT

Guarded merge, then idempotent production read-back only.

## REPLAN_TRIGGER

Any need to move, delete, or rewrite the bound production panel.
