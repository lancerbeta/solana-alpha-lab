---
task_id: QUOTE_SURFACE_RETENTION_CONFIRMATORY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: bab6caec67e731fc3cb5a392d4f71678541054cc
  expected_upstream: origin/main
  expected_upstream_oid: bab6caec67e731fc3cb5a392d4f71678541054cc
  expected_branch: cursor/quote-surface-retention-confirmatory
  dirty_mode: ALLOW_REPORTED
objective: Run one fresh Free-key confirmatory 6+6 quote-surface retention trial with clock_valid time-separation, excluding consumed PR 156 mints, without recapture, Atom 2, or scientific rewrite of PR 156.
managed_write_set:
  - docs/tasks/QUOTE_SURFACE_RETENTION_CONFIRMATORY_V1.md
  - catalog/schemas/factory_v1_quote_surface_retention_confirmatory.schema.json
  - configs/factory_v1_quote_surface_retention_confirmatory_v1.yaml
  - configs/experiment_specs/quote_surface_retention_confirmatory_v1.yaml
  - configs/quote_native_quote_surface_retention_confirmatory_audition_v1.yaml
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/application.py
  - tests/test_quote_surface_retention_confirmatory.py
  - tests/test_quote_surface_retention_falsifier.py
  - tests/test_factory_v1_owner_cockpit.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/quote_surface_retention_confirmatory/c1_quote_surface_retention_confirmatory_runtime_receipt_v1.json
  - docs/evidence/quote_surface_retention_confirmatory/c1_quote_surface_retention_confirmatory_acceptance_v1.json
  - docs/evidence/quote_surface_retention_confirmatory/c1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_surface_retention_confirmatory/c1_delivery_independent_review_v1.json
  - docs/evidence/quote_surface_retention_confirmatory/c1_delivery_factory_fit_v1.json
  - docs/reports/quote_surface_retention_confirmatory/c1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
  - SCIENTIFIC_RECLASSIFICATION_OF_PR_156
  - RECAPTURE_OF_PR_156
  - TRADED_ONLY_RESCUE
  - POST_HOC_THRESHOLD_SEARCH
  - CLOSED_T0_FRICTION_FAMILY_REOPENED
  - RC001_H07_H01_UNPARK_OR_MUTATION
  - ATOM_2_OR_ALPHA_OR_NETRETURN
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - KERNEL_PROVIDER_CALLS_TRUE
  - WALLET_SIGNER_TX_OR_CASH
  - PAID_PLAN_OR_SECOND_PROVIDER
  - EXECUTE_BUILD_OR_TAKER
  - A1_MOVE2_COMMISSIONING_ATOM5_ATOM6_OR_PR156_MINT_REUSE
context_requirements:
  catalog_asset_ids:
    - CTRL-QUOTE-SURFACE-RETENTION-FALSIFIER-001
    - EVIDENCE-QUOTE-SURFACE-RETENTION-FALSIFIER-RUNTIME-001
    - MODULE-FACTORY-V1-QUOTE-SURFACE-RETENTION-001
    - CTRL-QUOTE-SURFACE-RETENTION-CLOCK-QUALIFY-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_surface_retention_confirmatory/c1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_surface_retention_falsifier/a1_quote_surface_retention_falsifier_runtime_receipt_v1.json
      - docs/evidence/quote_surface_retention_falsifier/a1_quote_surface_retention_falsifier_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_SURFACE_RETENTION_CONFIRMATORY_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP`

Owner authorized one confirmatory 6+6 after Phase Q clocks landed on
`main`. This is not Atom 2, not recapture of PR #156, and not a rewrite
of the #156 scientific terminal.

`го` is not the confirmatory Jupiter phrase.

`strongest_rejected_alternative`: reopen Atom 2 / OOS or close the family
from the engineering #156 replay. Clocks were not yet live-confirmed.

## PRD-lite

- **Outcome:** one fresh 6 RECENT + 6 TRADED capture using
  `clock_valid` time-separation and frozen KEEP/VETO/Y; owner gets
  `FRESH_OOS_REPLICATION_EARNED`,
  `CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY`, or
  `SAMPLE_INVALID_REPLAN_REQUIRED`.
- **Consumer:** owner deciding whether this family may later earn Atom 2.
- **Gap:** #156 is consumed and scientifically invalid; clocks are
  qualified only as engineering.
- **Success:** capture PASS, no reused excluded mints, both strata scored
  with the frozen projector, 0 cash, call cap 62.
- **Invalidation:** amount-inequality clocks; TRADED-only salvage;
  recapture of #156 mints; treating confirmatory PASS as Atom 2.
- **Non-goals:** Atom 2/3/4, VPS, alpha, NetReturn, registry seed,
  unpark RC001, reopen ATOM 5/6, scientific rewrite of #156.

## SSD-lite

- **Baseline truth:** `origin/main`
  `bab6caec67e731fc3cb5a392d4f71678541054cc`.
- **Design:** ADOPT Free-key `/order`. WRAP existing retention schedule
  and projector. FORK only `(atom_id, owner_phrase, exclusions including
  PR 156, capture policy, ExperimentSpec, Factory selector)`. BUILD no
  new runner logic.
- **Invariants:** KEEP/VETO/Y frozen; overlay still pins consumed #156;
  UNKNOWN != 0 != VETO; RECENT/TRADED not pooled for PASS; cash $0.
- **Rollback:** revert this branch. #156 receipts remain create-only.

## Decision capsule

- `DECISION_DELTA`: live-confirm clock-based retention after Phase Q.
- `UNCERTAINTY_REMOVED`: whether a fresh 6+6 with valid clocks supports
  KEEP vs baseline in both strata.
- `CAPABILITY_OR_EVIDENCE`: confirmatory capture + classified receipt.
- `STOP`: exact-head CI, then merge phrase. Not Atom 2.
- `NEXT`: if PASS, Atom 2 only under a later exact contract; if FAIL,
  close this family; if INCONCLUSIVE, REPLAN, no automatic recapture.
- `ADOPTION_ROUTE=WRAP_EXISTING_FREE_KEY_CAPTURE_PLUS_RETENTION_PROJECTOR`
- `REPLAN_TRIGGER`: core runner must learn retention; cheapest falsifier
  cannot run; TRADED-only salvage; second provider/route; budget breach.

## Exact live-capture owner phrase

Owner authorized this atom including Free-key capture. Paste is not
required again in chat; the runner still matches this exact string:

```
OK QUOTE_SURFACE_RETENTION_CONFIRMATORY_V1: one Jupiter Free-key quote-surface retention confirmatory 6+6 after clock qualification; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 62; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding A1, MOVE 2, commissioning, ATOM 5 veto, ATOM 6 t0-screen and PR 156 falsifier mints; frozen KEEP if RETENTION_DELTA >= 0 and H900 routes exist; clock_valid from due_at/observed_at/terminal only; H3600 exact sell of BUY_H900 outAmount; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; WRAP existing capture plus retention projector; not recapture of PR 156; not Atom 2; not alpha; not VPS; no post-hoc threshold search; no TRADED-only rescue.
```

## Definition of Done

1. Confirmatory ExperimentSpec, capture policy, and Factory selector exist.
2. Phrase mismatch returns `BLOCKED_AUTHORITY` with 0 calls.
3. Exclusions include A1, MOVE 2, commissioning, ATOM 5, ATOM 6, and PR 156.
4. Overlay still does not rescore consumed #156.
5. After the exact phrase: one fresh capture, hash-bound receipts, Catalog,
   owner readout. No registry seed. No alpha. Not Atom 2.
