# Product+System contract mapping

Load this only before creating or materially updating an atom/task contract.
The executable artifact is the existing exact task contract
(`catalog/schemas/delivery_harness_task_contract.schema.json` plus the
`docs/tasks/` body pattern, e.g. `TASK-30-a25-*` or `CTRL-*`). This file is a
thinking overlay, not a second standard.

Do not emit a separate PRD, SSD, plan, or design memo for the same atom unless
`SPEC_ROUTE` already requires a distinct public contract/schema.

## Adaptive depth

- Routine / `CONTINUE` with unchanged scope: do not rewrite the contract.
- Ordinary new atom: compact overlay, then one schema-valid contract.
- Architecture, PIT, security, money, or multi-system: deeper `ssd_lite` and
  `SPEC_ROUTE=DESIGN_SPEC` or `BOTH` per domain policy. Still one contract.
- No prose for prose's sake.

## Compact overlay

Fill internally, then map into the Git contract. Omit a field only when the
target contract already answers it.

```yaml
decision:
  route:              # allowed_routes + frozen delivery route
  roadmap_verdict:    # KEEP|PATCH|REORDER|REBASE
  atom:               # task_id / atom name
  thesis:             # objective
  why_now:            # DECISION_DELTA / why this atom now
  evidence_basis:     # context_requirements + named receipts
  key_uncertainty:    # UNCERTAINTY_REMOVED
  strongest_rejected_alternative:  # only if the fork is material

prd_lite:
  outcome:            # Task Outcome Brief product outcome
  product_link:       # north star / named hypothesis or control consumer
  downstream_consumer:# named consumers
  current_gap:        # current_reality vs outcome
  success_observable: # user-visible result + cheapest falsifier
  invalidation:       # cheapest falsifier + replan trigger
  non_goals:          # non-goals

ssd_lite:
  baseline_truth:     # git_binding
  design:             # CAPABILITY_OR_EVIDENCE / how
  invariants:         # stop_conditions + body invariants
  affected_surfaces:  # subsystems touched
  expected_write_set: # managed_write_set (must cover every tracked file)
  failure_modes:      # stop_conditions / failure classes
  validation_surface: # Definition of Done + targeted tests
  rollback:           # how to revert the atom

delivery:
  milestones:         # internal phases, not owner gates
  definition_of_done: # Definition of Done
  review_level:       # FACTORY_FIT FAST_PATH|PROPORTIONAL|FULL_REVIEW
  owner_gates:        # real v2 stops, including exact merge
  budget_or_caps:     # external_caps + evidence budget
```

Minimum questions the mapped contract must answer:

```text
какой outcome должен стать истинным?
почему сейчас?
какой downstream consumer?
какую неопределённость закрываем?
почему выбран именно этот design?
что намеренно не решаем?
что может опровергнуть подход?
как доказать результат?
как откатить?
```

## Mapping into the exact contract

Write schema-required frontmatter first. Put narrative in the body as
Task Outcome Brief + Decision capsule (`DECISION_DELTA`,
`UNCERTAINTY_REMOVED`, `CAPABILITY_OR_EVIDENCE`, `STOP`, `NEXT`) +
`SPEC_ROUTE` + `REPLAN_TRIGGER`. Do not duplicate those fields in a second
YAML document.

Harness/control PRs still bind `LIVE_PR_HEAD` via
`scripts/delivery_harness.py context --pr` at the merge gate; product work
still uses `--task-id`. The overlay does not replace that identity.

Control atoms that must not invent a product `TASK-XX` still need a
schema-valid `CTRL-*` contract when policy requires an exact write set.

## Anti-patterns

- Second source of truth beside the Git task contract
- Owner-facing essay instead of an executable write set
- Copying Delivery Harness procedures into the atom contract
- Expanding `external_caps` or owner gates beyond current policy
