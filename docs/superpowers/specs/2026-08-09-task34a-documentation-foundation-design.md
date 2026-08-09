# TASK-34A Documentation Foundation and AI/Operator Runbooks — design v1

## Decision

Implement TASK-34A as a small, generated navigation and operational-reference
layer, not as a documentation portal. Its first consumer is a future task
Entry Gate and the goal owner who needs one trustworthy answer to: what is
active, what is blocked, where is the evidence, and what is the next safe
action?

The task starts because its roadmap trigger is observed: repeated manual
context recovery and documentation friction. It does not reopen any
data-provider route, research trial, wallet, execution, cash, or Project
Sources UI action.

## Scope and staged delivery

### A1 — Context binding and Source-mirror freshness preflight

Build one deterministic, read-only command and its contract. It resolves the
active Project Sources release through `docs/project_sources/release_registry_v1.yaml`,
then optionally compares a user-supplied local Project Sources directory with
that activated release by role, required header, and SHA-256.

The command must emit one explicit state for the local mirror:

- `MIRROR_MATCHES_ACTIVE_RELEASE`;
- `STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED`;
- `MIRROR_UNAVAILABLE`;
- `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW`.

No machine-specific path is tracked. A stale or absent mirror cannot demote an
activated release that has an owner smoke receipt. A conflict in the release
registry, binding, or activation receipt fails closed and must not select a
task.

### A2 — Generated operator navigation card

Generate a compact repository-native text/JSON card from the release registry,
Catalog, active time gates, and accepted task records. It must show the active
release, canonical task state, implementation head, material blocker, named
next boundary, and stable artifact pointers. It is a read model: Git remains
the bytes owner, Catalog owns discovery/relations, and registries own lifecycle
truth.

### A3 — Minimal runbooks and freshness check

Add only the runbooks that solve observed operator friction:

1. start or resume a task;
2. diagnose a stale Source mirror or release-binding conflict;
3. safely stop at an external-authority boundary.

Add one deterministic check that the runbook links and generated card bindings
resolve. Do not build hosting, a dashboard, a wiki, a vector store, or a RAG
service.

### A4 — Acceptance and integration

Register task artifacts in the Catalog, generate downstream navigation, and
perform a FULL Factory Fit review. The Project Sources disposition is
`NO_CHANGE` unless a later, separately justified canonical task-status change
requires a registered release candidate.

## Interfaces and data flow

```text
release registry + owner smoke receipt ─┐
Catalog + lifecycle + active time gates ├─> deterministic context card
optional local Sources directory ───────┘        │
                                                  ├─> operator runbooks
                                                  └─> Entry Gate / owner
```

The optional local directory is an input to a command, never a repository
configuration value. The implementation must not read cloud UI state, mutate
Project Sources, copy a bundle, or infer activation from filenames.

## Error handling and safety

- Hash, semantic role, header, or release-registry contradictions are explicit
  errors; never silently select the newest-looking file.
- A user-provided directory is read-only. Unreadable/missing files produce a
  classified result, not a repair attempt.
- The output contains no raw Project Sources bytes, secrets, credentials,
  absolute user paths, provider URLs with credentials, or transaction data.
- `MIRROR_UNAVAILABLE` and a proven active release permit a read-only Entry
  Gate; `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW` blocks task selection.

## Validation

Deterministic synthetic fixtures cover:

- active release with a matching mirror;
- activated release with a stale mirror;
- unavailable mirror;
- wrong hash, missing role, and header mismatch;
- candidate release without activation receipt;
- output redaction of supplied absolute paths;
- generated-card and runbook-link freshness.

Targeted unit tests, Catalog validation, generated-project-map validation, and
the repository delivery gate validate the exact candidate. No provider call,
credential use, dependency addition, wallet/signer action, cash action, or
Project Sources UI action is permitted.

## Alternatives rejected

1. **Use the local mirror as canonical.** Rejected: it is an application-managed
snapshot and demonstrably lags an activated release.
2. **Build a web/RAG documentation system now.** Rejected: it creates a second
navigation surface before a small deterministic read model is proven
insufficient.
3. **Do nothing until research data arrives.** Rejected: repeatable operator
friction already consumes attention and increases the risk of choosing a task
from stale context.

## Completion conditions

The task is complete only when the generated navigation tells a new local
operator which source release is active, whether the mirror is safe to use,
and where the next action is bound; runbooks cover the three observed recovery
paths; all outputs are deterministic and Catalog-discoverable; and Factory Fit
confirms the layer did not create a second truth owner.
