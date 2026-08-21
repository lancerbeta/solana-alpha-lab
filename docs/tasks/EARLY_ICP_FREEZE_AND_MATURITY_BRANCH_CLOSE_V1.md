---
task_id: EARLY_ICP_FREEZE_AND_MATURITY_BRANCH_CLOSE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6f94ae9de19494a012fa0e8f4eff519dfe2c2e8e
  expected_upstream: origin/main
  expected_upstream_oid: 6f94ae9de19494a012fa0e8f4eff519dfe2c2e8e
  expected_branch: cursor/early-icp-freeze-maturity-branch-close
  dirty_mode: ALLOW_REPORTED
objective: Freeze the first reproducible product ICP as EARLY pump.fun wait-then-search from the retained hash-pinned live Stage A evidence (27 EARLY >= 12), close the /toptraded SEASONED acquisition branch as TOPTRADED_NOT_SAME_POPULATION, and record the one optional same-cohort maturity probe without a second campaign.
managed_write_set:
  - docs/tasks/EARLY_ICP_FREEZE_AND_MATURITY_BRANCH_CLOSE_V1.md
  - configs/early_icp_freeze_and_maturity_branch_close_v1.yaml
  - src/solana_alpha_lab/early_icp_freeze_acceptance.py
  - scripts/run_early_icp_freeze_acceptance.py
  - scripts/probe_early_cohort_maturity_lookup.py
  - tests/test_early_icp_freeze_acceptance.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json
  - docs/evidence/early_icp_freeze/a1_acceptance_v1.json
  - docs/evidence/early_icp_freeze/a1_delivery_completion_evidence_v1.json
  - docs/evidence/early_icp_freeze/a1_delivery_independent_review_v1.json
  - docs/evidence/early_icp_freeze/a1_delivery_factory_fit_v1.json
  - docs/reports/early_icp_freeze/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - SECOND_TOPTRADED_ATTEMPT
  - LIMIT_100_OR_THRESHOLD_RESCUE
  - FRESH_REPLACEMENT_COHORT
  - QUOTES_OR_H900_IN_THIS_WRITE_SET
  - NEW_FEATURE_OR_STATE_X
  - ALPHA_OR_NETRETURN
  - FACTORY_RUNNER_CHANGE
  - PROVIDER_CALL_IN_ACCEPTANCE_WRITE_SET
  - CREDENTIAL_OR_API_KEY_READ_IN_OFFLINE_ATOM
  - WALLET_SIGNER_TX_OR_CASH
  - ARCHITECTURE_INTENT_OR_ROADMAP
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-IN-SCOPE-POPULATION-AND-STATE-DISCOVERY-RUNTIME-001
    - EVIDENCE-IN-SCOPE-POPULATION-AND-STATE-DISCOVERY-ACCEPTANCE-001
    - EVIDENCE-IN-SCOPE-POPULATION-FIT-RECONCILIATION-RUNTIME-001
    - EVIDENCE-ORDINARY-RECENT-EARLY-PATH-H900-AUDITION-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/early_icp_freeze/a1_delivery_completion_evidence_v1.json
      - docs/evidence/early_icp_freeze/a1_delivery_independent_review_v1.json
      - docs/evidence/early_icp_freeze/a1_delivery_factory_fit_v1.json
      - docs/evidence/in_scope_population_and_state_discovery/a1_runtime_receipt_v1.json
      - docs/evidence/in_scope_population_and_state_discovery/a1_acceptance_v1.json
      - docs/evidence/in_scope_population_fit_reconciliation/a1_runtime_receipt_v1.json
      - docs/evidence/ordinary_recent_early_path_h900_audition/a1_ordinary_recent_early_path_h900_audition_runtime_receipt_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_ICP_FREEZE_AND_MATURITY_BRANCH_CLOSE_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=PRD_LITE`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

Owner direction: `muv-5.md` ATOM 1. This Git contract is the bounded write set.

## Entry action result

The retained local runtime evidence of the already-run live Stage A attempt
exists outside Git at `local/in_scope_population_live_supply_gate/`
(hash-enveloped raw bodies plus `probe_runtime_receipt_v1.json`,
receipt sha256 `adf4afb5ccfa18e09d7c9c3c8c61ce28903c9b8421e3891d068474601e961cab`,
matching the config pin).
Live supply: EARLY n=27 (>=12) via WAIT_THEN_SEARCH; `/toptraded`-derived
SEASONED n=5 with launchpad selection confounding. Work proceeds from these
retained bytes. No reconstruction from chat text and no fresh cohort.

## Decision capsule

- `DECISION_DELTA:` Freeze ICP-EARLY-PUMPFUN-V1 (pump.fun, age 5–15m,
  liquidity >= $1000, acquired by wait-then-search). Close the SEASONED
  acquisition path as TOPTRADED_NOT_SAME_POPULATION — an invalid acquisition
  design, not SEASONED_SUPPLY_FAILED. Maturity comparison is off the critical
  path.
- `UNCERTAINTY_REMOVED:` whether the live result is durably retained and what
  it proves about population acquisition channels.
- `CAPABILITY_OR_EVIDENCE:` thin acceptance projector over hash-pinned local
  bytes + canonical EARLY ICP freeze receipt + one optional same-cohort
  maturity probe answer. Core capability NONE; Factory runner unchanged.
- `STOP:` after the freeze packet, owner readout and exact-head CI. The
  optional maturity probe was already executed once inside this atom under its
  six preconditions; no second probe, no separate PR for it.
- `NEXT:` ATOM 2 `EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1` under a new owner
  contract. If retained evidence cannot be verified:
  `LIVE_SUPPLY_EVIDENCE_NOT_DURABLY_RETAINED`, which does not auto-repeat the
  campaign.
- `CHEAPEST_FALSIFIER:` pinned body sha256 drift, EARLY count < 12, source
  channel treated as population class, or any threshold rescue.
- `REPLAN_TRIGGER:` second preparatory-only atom; request to widen to quotes,
  X, new provider or a replacement cohort.
- `strongest_rejected_alternative:` continue the 12+12 campaign and run 3 X on
  the mixed population. Rejected: mixes maturity effect, survival selection
  and acquisition channel; statistically decorated noise.

## Optional maturity probe (executed inside this atom)

Allowed only because all six held simultaneously: exact 27-mint cohort
retained; decision-time timestamps retained; cohort still inside the valid
30–120m observation window; zero new product code (existing credentialed GET +
existing bulk search URL); no new sampling route/provider; ordinary existing
raw retention method. One later-search over the same mints answered whether
same-population SEASONED availability exists. It does not change the frozen
EARLY ICP, does not unlock Atom-blocked work and never gets a second attempt.
If the window had passed: `EXPLICIT_GAP_NO_BACKFILL`, no reshoot.

## PRD

**Problem.** PR #170 left the frozen design expecting 12+12 via instant
3-call harvest; live evidence refutes the SEASONED half. Continuing would mix
maturity effect + survival selection + acquisition channel and fail the
original estimand.

**Owner decision unlocked.** Exactly one of:

`EARLY_ONLY_ICP_CONFIRMED`
`LIVE_SUPPLY_EVIDENCE_NOT_DURABLY_RETAINED`

**Named consumer.** ATOM 2 `EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1`.

**Canonical fields per observed candidate:** mint, source_channel,
observed_at, pool_age_at_observation, launchpad, liquidity_usd,
population_class, membership_reason. `source_channel` and `population_class`
are strictly different things: source=/toptraded never implies
population=SEASONED.

**Terminal rules.** `EARLY_ONLY_ICP_CONFIRMED` iff retained evidence shows
EARLY qualifying count >= 12 AND acquisition = WAIT_THEN_SEARCH. The SEASONED
route closes as TOPTRADED_NOT_SAME_POPULATION.

**Validation minimum.** 27 EARLY confirmed from exact retained bytes;
/toptraded rows do not gain population membership from source alone; OLDER
>120m excluded; missing launchpad = UNKNOWN/excluded; no threshold rescue;
Factory runner SHA unchanged.

**Explicitly forbidden.** Second `/toptraded/1h` attempt; limit=100; widening
120m; lowering n; fresh replacement cohort; quotes; 3 X; new feature; new
provider; alpha inference.

**Process delta.** Do not duplicate PR #171 probe-before-packet. Comparable
technical probes inside one material owner question do not create a new atom.

**Non-goals.** No strategy, bot, paper/shadow, PostgreSQL, Cockpit, alpha,
NetReturn, architecture intent or roadmap in this write set.

## SSD

**Reuse.** Existing offline projector pattern (`in_scope_population_supply_gate`),
hash-pinned config pattern, existing acceptance/runtime evidence schemas,
existing navigation generator. No new reusable market component.

**Truth model.** Local A4 raw bytes stay outside Git; Git stores receipts with
body sha256 pins. Acceptance derives only from pinned hashes.

**Failure semantics.** Unknown launchpad is UNKNOWN, never zero; provider
failure in the past attempt is not re-fought; missing evidence is an explicit
gap, not a reconstruction invitation.

**DoD.** Owner receives one conclusion: Factory has a reproducible EARLY ICP;
maturity comparison is off the critical path; next question is whether a
decision-time state inside EARLY carries useful execution/return information.
