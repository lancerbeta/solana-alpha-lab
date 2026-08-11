# Model Effort Router v1 — design

Date: 2026-08-11

## Objective

Make model and reasoning-effort advice deterministic at the two boundaries
where it can change execution economics without creating another approval
ceremony:

1. before the first complex task, atom, or uninterrupted autonomous chain;
2. after the current material atom finishes and immediately before the next
   approval or handoff.

The policy optimizes useful engineering per owner attention and Codex usage.
It does not claim that one model is universally best.

## Routing policy

Use exactly one recommendation for the selected scope:

- `LUNA_MAX`: default implementation workhorse for bounded Python work,
  tests, bug fixes, local refactoring, Git/CI delivery, and tasks whose
  architecture and acceptance contract are already clear.
- `SOL_XHIGH`: use when the work contains material architectural ambiguity,
  a new public contract or schema, several coupled subsystems, difficult root
  cause analysis, PIT/statistical/security truth, or repository-wide invariant
  reconciliation.
- `SOL_MAX`: exceptional escalation for irreversible or high-impact decisions,
  real-money/security authority gates, adversarial closure with several
  plausible models, or a material problem that remains unresolved after
  `SOL_XHIGH`.
- `TERRA_XHIGH`: fallback when `LUNA_MAX` is unavailable or when a single
  no-switch compromise is explicitly preferable. It is not a mandatory
  intermediate escalation.
- `ROUTINE_NO_SWITCH`: deterministic smoke, exact read-back, ordinary merge,
  or another simple step that does not merit a model change.

For one uninterrupted autonomous chain, the hardest material segment sets the
recommendation for the whole chain. A different recommendation is allowed only
after an explicit checkpoint creates a separately executable segment.

## Timing and deduplication

The router emits one compact line in exactly two situations:

- `MODEL_EFFORT_RECOMMENDATION` at Entry Gate before a complex scope starts,
  unless a still-valid finish-side recommendation already names the same
  scope;
- `NEXT_MODEL_EFFORT` after the current material atom or task checkpoint and
  immediately before the next owner approval or handoff.

Do not emit effort advice during routine microsteps. Do not stay silent merely
because the default is sufficient. Do not repeat an unchanged recommendation
for the same exact scope. Recompute only when the selected scope or a material
architecture, data-contract, estimand, security, or safety boundary changes.

Each line contains the exact scope, recommendation, one concrete reason, and
one escalation trigger. It is advisory and grants no authority.

Use these exact shapes:

```text
MODEL_EFFORT_RECOMMENDATION=<enum>; scope=<exact atom or chain>; reason=<one sentence>; escalation=<one trigger>
NEXT_MODEL_EFFORT=<enum or DEFERRED>; scope=<exact next atom or chain>; reason=<one sentence>; escalation=<one trigger>
```

## Integration surfaces

Use the smallest set that covers the active local workflow:

1. `start-solana-task/references/router-v3.md` owns the detailed routing rule.
2. `start-solana-task/SKILL.md` invokes it and requires the Entry Gate output.
3. `finish-solana-task/SKILL.md` requires the next-scope recommendation before
   the next approval or handoff and passes it into an auto-chain.
4. Repository `AGENTS.md` carries the compact invariant so repository agents
   cannot silently omit or contradict the control-plane recommendation.
5. A versioned `PROJECT_INSTRUCTION_V3_5.md` candidate carries the same compact
   invariant into cloud-only Project threads after one explicit owner UI
   replacement and read-back.

Do not add a new skill, registry, scoring system, dependency, Project Source,
or Source bundle. Project Instruction v3.5 is a replacement candidate, not a
Project Source and not proof of UI activation. Catalog and generated-view
updates are allowed only as required consumers of that candidate.

## Failure handling

- If the next scope is unknown, return `NEXT_MODEL_EFFORT=DEFERRED` and name
  task selection as the prerequisite; do not guess.
- If `LUNA_MAX` is unavailable for bounded implementation, use
  `TERRA_XHIGH`. If a Sol recommendation is unavailable, preserve it in the
  handoff and use the strongest available model only when the named failure
  mode remains safely covered; otherwise defer that segment.
- A model mismatch is not an authority gate. Stop only when it creates a
  material quality risk that the selected scope cannot safely absorb.
- Do not encode volatile prices, credit multipliers, benchmarks, or UI labels
  as repository truth. Verify current official OpenAI documentation when those
  facts materially affect a decision.

## Validation

- Run the skill creator `quick_validate.py` against both modified personal
  skills.
- Check that the start router, start skill, finish skill, and repository
  invariant expose the same five recommendations, exact line shapes, and
  timing rules.
- Validate the Project Instruction v3.5 size/header, Catalog binding, generated
  consumers, and its exact model-effort invariant.
- Run repository diff/policy checks required by the changed `AGENTS.md` owner;
  delegate the exact-head full gate to the repository's normal CI route.
- Inspect the exact diff for unrelated control-plane or Project Sources
  changes.

## Acceptance

The design passes when a future complex atom always receives one visible
recommendation at start or from the immediately preceding finish checkpoint,
an uninterrupted autonomous chain is sized by its hardest material segment,
routine microsteps do not generate repeated advice, and no new approval or
authority class is created. Cloud coverage remains explicitly pending until
the owner activates the v3.5 candidate in the Project UI and returns its exact
smoke receipt.
