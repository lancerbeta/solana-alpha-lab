# T27-A0-A5 — Source reconciliation and smoke design

## Decision

Prepare one repository-tracked, offline replacement candidate that makes the
Project Sources truthful about the completed TASK-27 offline foundation. It
does not activate Project Sources, collect market data, or grant any external
authority.

The candidate starts from the last integrity-checked cloud bundle (manifest
4.6) and reconciles only facts that are stronger in the merged repository:
TASK-27 A0-A2 through A0-A4, merge commit
`082f3f8184e84c31c876a484cf8e876a40691f62`, and its successful post-merge CI
run `31224401848`.

## Why this comes before data collection

The A4 authority contract requires `ACTIVATION_CONFIRMED_USER_SMOKE` before a
future external-read review can be `READY`. The current Source candidates end
before TASK-27 and are explicitly packaging candidates, not activated truth.
Using them as though they described the current task would let an external
request escape the owner-visible memory of the project.

## Selected approach

Three options were considered:

1. Use the old v4.6 Sources and request data now. Rejected: it violates A4's
   smoke binding and hides TASK-27 from the owner-visible state.
2. Build a generic Source synchronization service. Rejected: no repeated
   consumer justifies a new platform.
3. Produce one manifest-first, five-role replacement candidate with a
   deterministic validator and a user-run smoke. Selected: it is the smallest
   reversible repair of the actual blocker.

## Scope

The implementation will create a single candidate directory containing:

- five mutable Source roles: canonical manifest, roadmap, current system
  state, phase archive, and active TASK-27 record;
- an immutable-role binding for Operating System v8.5 and Blueprint v2.3;
- checksums, a validation receipt, and a copy-paste smoke prompt;
- one JSON Schema, one deterministic synthetic fixture, and one validator
  test; and
- one acceptance receipt describing the zero-side-effect boundary.

The active TASK-27 record will distinguish the delivered offline contracts
from any future provider read. It will say that a fresh smoke is a prerequisite
for a separate owner review, and that neither the smoke nor the bundle grants
provider, wallet, signer, transaction, cash, R2/R3, execution, alpha, PnL or
NetReturn authority.

The user-facing activation operation is deliberately outside the repository:
replace exactly the five mutable Project Source roles, keep the two immutable
roles byte-for-byte, then run the provided seven-role smoke. No claim of
activation is valid until the user returns that receipt.

## Data and integrity model

The bundle is manifest-first. The manifest binds each Source role to semantic
version, required header, SHA-256 and physical filename. The manifest does not
attempt to hash itself; an adjacent checksums file and validation receipt bind
its bytes.

The validator must reject at least: an old active-task identity, a source role
outside the five-role replacement set, a mutable role without header/hash,
changed immutable-role bytes, a false `UI_ACTIVATION_CONFIRMED` claim, a
provider-authority claim, and a mismatch between the merged main identity and
the recorded CI identity.

## Validation and recovery

Synthetic tests validate candidate completeness and the adversarial cases.
The repository delivery gate runs in a tracked-only checkout before its first
push. The user smoke is separate evidence: `SMOKE=PASS` activates no provider
right and only clears A4's Source-alignment prerequisite.

Rollback is simple and explicit: restore the preceding five mutable Source
roles recorded in the candidate manifest, retain Operating System and Blueprint
unchanged, then run the preceding manifest's smoke. No provider response,
wallet state or cashflow exists to recover.

## Out of scope

No Project Source UI mutation, provider/API/RPC/WSS request, raw history,
credential, dependency, catalog-root migration, wallet, signer, transaction,
spend, strategy decision, PIT claim, alpha claim, PnL/NetReturn claim or
TASK-27 completion is in scope.
