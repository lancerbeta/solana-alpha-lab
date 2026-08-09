# TASK-28 A3 — Project Sources release candidate design

## Decision

Create `PSR-0003-T28-RC001-FREEZE` directly from the currently activated,
Git-tracked `PSR-0002-T27-CLOSE` release. This is the correct base because
its owner-smoke activation receipt is registered in
`docs/project_sources/release_registry_v1.yaml`; the stale local Project
mirror is not a truth owner.

The candidate updates exactly five mutable Source roles for TASK-28 and keeps
the Operating System v8.5 and Research Blueprint v2.3 byte-for-byte unchanged.
It is a repository artifact only. Cloud replacement and the seven-role smoke
remain owner-only actions after delivery.

## Bounded outputs

- Add `docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/` containing
  the five mutable files, `canonical_manifest.yaml`, `CHECKSUMS_SHA256.txt`
  and `FRESH_CHAT_SMOKE.md`.
- Update the release registry with exactly one pending candidate while keeping
  PSR-0002 as the active release until an owner smoke creates a later
  activation receipt.
- Add a hash-bound TASK-28 A3 acceptance receipt and one focused deterministic
  test.
- Register the acceptance receipt in the existing Catalog and regenerate its
  two derived navigation views.

## Source semantics

The new candidate reports manifest/roadmap `4.9`, state `4.5`, archive `39.0`
and active task `TASK-28 / 1.0`. It records only the delivered offline RC-001
freeze: three groups remain `BLOCKED_DATA`, no trial or holdout exists, and no
provider, credential, R2/R3, wallet, signer, transaction, cash, alpha or
numeric NetReturn authority is created.

`TASK28_SOURCE_SMOKE=PASS` is valid only when all seven role/version/header/
SHA-256 bindings match. It confirms Source activation, not research-trial or
market authority.

## Non-claims and recovery

No historical Source byte is overwritten or deleted. Before activation,
PSR-0002 remains the active UI release and the candidate is reversible by
discarding its unactivated release record. After a future failed smoke, the
owner restores exactly the five PSR-0002 mutable roles and reruns that release's
smoke; immutable roles remain unchanged.

No external provider, RPC, credential, wallet, transaction, spend,
dependency, deployment, repository-setting or cloud-UI action is in scope.
