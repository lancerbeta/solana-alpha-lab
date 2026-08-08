# ARCH-INTENT-004 Context Capsule Boundary — Design

## Purpose

Preserve one durable product direction: a future **Factory Context Capsule**
must make the existing hypothesis factory easier to enter, navigate, reuse and
extend without becoming a second source of truth or an early generic platform.

The owner decision it supports is: *before starting or extending a hypothesis,
what relevant evidence, constraints, prior attempts and next safe action
already exist?*

## Decision

Register `ARCH-INTENT-004_FACTORY_CONTEXT_CAPSULE_AND_WORKBENCH_BOUNDARY_V1`
as an `ACCEPTED_DIRECTION_NOT_IMPLEMENTED` architecture intent. It extends
`ARCH-INTENT-002` and the three-plane topology in `ARCH-INTENT-003`; it does
not amend their truth, authority or execution boundaries.

The Context Capsule is a deterministic, read-only projection over existing
Catalog records, lifecycle registries, contracts and retained evidence. Git
remains byte truth; the Catalog remains discovery/relationship truth; lifecycle
registries remain lifecycle truth. The Capsule stores no competing records and
cannot mutate a hypothesis, trial, strategy, execution attempt or owner
decision.

## Future interaction model

When justified, one bounded entry query for a task or hypothesis should return:

1. relevant stable asset IDs, paths, hashes and named consumers;
2. applicable invariants, authority limits and known missing evidence;
3. related hypotheses, trials, decisions and negative results where present;
4. the current lifecycle state and the next safe decision boundary; and
5. an explicit `UNKNOWN` / `CATALOG_GAP` when evidence is absent.

Results must be deterministic, evidence-linked and ordered by declared stable
rules. They must not summarize unretained chat, expose secrets, invent semantic
similarity or turn absent records into a conclusion.

## Architecture boundaries

- No vector database, graph database, embeddings, remote RAG service, web UI,
  new dependency or provider call belongs to this intent.
- Stable Catalog edges and deterministic local queries are the first and only
  allowed implementation shape. A graph database remains deferred under
  `ADR-001` until a measured query workload justifies its cost, migration and
  exit plan.
- The Research Workbench is an owner/GPT workflow surface, not an application
  to build now. The future Owner Pulse remains a read model and never gains
  authority from the Capsule.
- The intent has no execution, wallet, signer, transaction, cash, strategy,
  PnL, NetReturn or Project Source activation authority.

## Activation trigger

Do not implement the Capsule merely because this intent exists. A separate
bounded Entry Gate is required when the first of these is true:

1. TASK-28 is ready to create the first non-empty hypothesis family or a
   second real hypothesis is proposed;
2. two task cycles require repeated manual context reconstruction; or
3. a bounded Entry Gate cannot resolve relevant prior assets and constraints
   through the existing Catalog and lifecycle registries without material
   operator delay.

The cheapest falsifier is an ordinary Catalog/lifecycle query: if it answers
the owner question clearly and deterministically, no Capsule is built.

## Intended future DoD

The first implementation, if triggered, is limited to a deterministic local
read model and tests proving: stable input identities, stable ordering,
evidence-path traceability, no hidden state, explicit missingness, and no
mutation or network effect. Any search, vector, graph-database, dashboard or
automation proposal is a separate decision with its own measured need.

## Delivery shape for this atom

The implementation after this design review will add only the durable intent,
its Catalog record and generated discovery outputs. It will not implement the
Capsule itself.

Planned manually authored files:

- `docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md`
- `catalog/assets/architecture.yaml`
- `catalog/catalog_manifest.yaml`
- `tests/test_arch_intent_004_context_capsule_boundary.py`

Generated files, produced only by the existing repository generator:

- `catalog/generated/asset_edges.json`
- `docs/PROJECT_MAP.md`

Validation will use the focused new test, existing Catalog validation and one
tracked-only delivery gate. No dependency, provider, wallet or Project Source
change is planned.
