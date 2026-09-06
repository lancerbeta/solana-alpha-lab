# Science to Strategy Handoff V1

Exact semantics for transforming an accepted scientific PROMOTE into a
reviewable StrategyVersion v1.1 candidate. Does not own ExperimentSpec
meaning, science obligation definitions, PaperPlane operation, or
deployment.

Catalog document: `DOC-SCIENCE-TO-STRATEGY-HANDOFF-001`
Semantic route: `SEM-OWNER-LIFECYCLE` (existing; no new route)
Visual owner: `SMIAL_VISUAL_OPERATING_SYSTEM_V1`

```text
authority_granted = false
activation_created = false
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
PROMOTE = scientific DECISION_EVENT only
StrategyVersion = Git definition, not runtime
```

## 1. Owner questions

```text
Есть ли scientific PROMOTE?
Какой exact decision его зафиксировал?
Какой evidence был использован именно тогда?
Готов ли handoff к StrategyVersion?
Что блокирует переход?
Создана ли StrategyVersion?
Откуда взялось каждое material поле?
Что пока НЕ было запущено?
```

## 2. Truth owners

```text
SCIENTIFIC DEFINITION              → Git ExperimentSpec
SCIENTIFIC EVIDENCE                → append-only ResearchStore
SCIENTIFIC DECISION                → append-only DECISION_EVENT
SCIENCE→STRATEGY HANDOFF RECEIPT   → part of exact PROMOTE payload
STRATEGY DEFINITION                → Git StrategyVersion v1.1
CURRENT BOT/POSITION/EXECUTION     → PaperPlane/runtime source
CURRENT HOST/SERVICE HEALTH        → direct machine readback
OWNER PRESENTATION                 → derived Workbench projection
LIFECYCLE INDEX                    → derived LifecycleProjection
```

`ScienceToStrategyHandoffV1` is a derived read model. It owns no durable
truth and is rebuilt from source owners. Forbidden: `handoff.sqlite`,
strategy-status database, promotion registry, attention database,
workflow-state database.

## 3. Manifest meaning

New PROMOTE events freeze `promotion_handoff_manifest` schema_version `1.0`
inside the scientific decision payload.

The manifest means:

```text
These were the exact machine inputs represented by this accepted
scientific PROMOTE at decision time.
```

It does not mean alpha, PIT/OOS sufficiency beyond the existing science
contract, profit, executable live, StrategyVersion created, or strategy
activated. Move 2 science guard remains what that contract says. A
key-presence eligibility guard is not a new scientific-validity claim.

`evidence_snapshot_sha256` retains its exact existing meaning. The
manifest is additive. Historical DECISION_EVENT bytes are never rewritten.

## 4. Legacy PROMOTE

A PROMOTE without a valid frozen manifest is `LEGACY_PROVENANCE_GAP`.
Forbidden: reconstructing decision-time evidence from latest records,
taking today's ExperimentSpec as historical truth, filename/title/date
matching, LLM reconstruction, or silent migration.

## 5. Handoff state

Top-level vocabulary:

```text
NOT_PROMOTED | BLOCKED | READY_TO_MATERIALIZE | MATERIALIZED | CONFLICT
```

Specificity lives in `blocker_codes`:

```text
LEGACY_PROVENANCE_GAP
HANDOFF_MANIFEST_INVALID
EXPERIMENT_SPEC_BINDING_GAP
EVIDENCE_RELATION_GAP
EVIDENCE_HASH_CONFLICT
EXECUTION_INPUT_GAP
STRATEGY_IDENTITY_CONFLICT
STRATEGY_CONTENT_CONFLICT
SOURCE_UNAVAILABLE
```

UNKNOWN stays UNKNOWN. No percentage readiness and no traffic-light score.

A valid frozen manifest plus later source unavailability is:

```text
HANDOFF_MANIFEST = VALID
SOURCE_REVALIDATION = UNAVAILABLE
```

Materialization prefers decision-time receipt stability. Current online
revalidation is not a blanket requirement.

## 6. StrategyVersion field provenance

Existing StrategyVersion v1.1 is the target. Do not create v1.2.

Every field belongs to exactly one class:

```text
SCIENCE_DERIVED
  source_decision_asset_id = exact DECISION_EVENT identity
  source_hypothesis_refs
  population_ref
  title / strategy_id identity from frozen scientific ids

EXECUTION_CONTRACT_FIXED
  signal_input.contract / contract_version / enter_actions
  exit_input.contract / contract_version
  mode_eligibility.paper = true
  mode_eligibility.micro_live = false
  authority_class = PAPER_SHADOW_ONLY

EXPLICIT_EXECUTION_INPUT
  signal_input.max_age_seconds
  notional_policy.notional_usd
  notional_policy.fee_bps
  risk_policy.max_open_positions
  mode_eligibility.shadow
```

Missing explicit execution values yield `EXECUTION_INPUT_GAP`, never
defaults, nearest strategy, commissioning templates, rationale prose,
filenames, or LLM guesses.

## 7. Materialization seam

Conceptual operations: `CHECK`, `RENDER`, `VERIFY`.

Same identity + same canonical content → MATERIALIZED / replay-identical.
Same identity + different content → CONFLICT, zero overwrite.
Workbench GET/POST research ≠ Git mutation. No "Create strategy and
commit" / "Start strategy" / "Promote & run" controls.

When READY_TO_MATERIALIZE, owner copy is:

```text
Научный переход готов. Для создания StrategyVersion нужен bounded Git
materialization step.
```

## 8. Lifecycle relation

```text
ExperimentSpec → DECISION_EVENT(PROMOTE) → StrategyVersion
```

Only `EXPLICIT_SOURCE_FIELD`, `EXPLICIT_FOREIGN_KEY`,
`EXPLICIT_CATALOG_RELATION`, or `EXPLICIT_CONTRACT_KEY`.
`source_decision_asset_id` on handoff-generated strategies resolves to
the exact DECISION_EVENT identity. Missing target is `TARGET_GAP`.
Incompatible identities are `CONFLICT`. Do not synthesize a target.

## 9. Authority invariant

```text
scientific PROMOTE ≠ StrategyVersion
StrategyVersion ≠ activation
Git capability ≠ live health
GET /research ≠ writer
```

Zero activation epoch, BotInstance, PAPER start, SHADOW start, LIVE,
provider, wallet, signer, or spend from this capability.

This contract does not own ExperimentSpec meaning, science obligation
definitions, StrategyVersion v1.1 schema, or
`FACTORY_STRATEGY_EXECUTION_BOUNDARY_V1` runtime execution.
