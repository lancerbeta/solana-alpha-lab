# TASK-27 A2 — Terminal reconciliation and Project Sources release

**Status:** Design approved by owner's 2026-08-08 direction to close TASK-27 after the route-close result
**Task:** `TASK-27`
**Atom:** `T27-A2_TERMINAL_RECONCILIATION_AND_SOURCES_RELEASE_CANDIDATE_V1`

## Purpose

Close the research question addressed by TASK-27 without widening it. A1S2
showed that the frozen Solana Tracker route supplied only 33 of the required
96 natural 15-minute bars. A1S3 kept that conclusion route-specific. A1S4
bound the owner's decision to stop further provider reads.

A2 converts those facts into a final limited task outcome and a new,
repository-validated Project Sources release candidate. It does not activate
the cloud Sources; activation remains a single later owner replacement and
seven-role smoke.

## Chosen approach

The chosen approach has two linked outputs:

1. a terminal reconciliation record with
   `CLOSE_WITH_LIMITED_NEGATIVE_RESULT`; and
2. `PSR-0002-T27-CLOSE`, a five-role replacement candidate that makes the
   current cloud context stop pointing at an obsolete external-read review.

A record without the release would leave the active Sources stale. Direct
cloud editing without a release candidate would bypass manifest/hash/smoke
control. Neither is acceptable.

## Exact meaning

The terminal result is:

`NO_FEASIBLE_PUBLIC_HISTORY_ROUTE_DEMONSTRATED_WITHIN_AUTHORIZED_SCOPE`.

It means only that one named route was insufficient and the owner declined a
new source read. It does not imply that other providers, all public history,
all price/volume research, alpha, execution, PnL, NetReturn, or cashflow are
negative or impossible.

TASK-27 becomes technically reconciled only after the local contract, Catalog
transaction, factory-fit review, release candidate, tests, delivery, and CI
pass. Its canonical Source activation and final user-visible completion remain
pending until the owner replaces exactly five mutable Source roles and returns
the seven-role smoke.

## Source-release design

The release copies the current hot-set model:

- replace: canonical manifest, roadmap, current system state, phase archive,
  and active TASK-27 record;
- retain byte-for-byte: Operating System v8.5 and Research Blueprint v2.3;
- preserve `PSR-0001-T27-A0-A5` as rollback history;
- register `PSR-0002-T27-CLOSE` as the only candidate while
  `PSR-0001-T27-A0-A5` remains the actual active UI release;
- include a manifest-first smoke prompt and checksums.

The active task record will show a technically reconciled, limited negative
result and the exact user-only activation step. It must not silently select a
next task or revive external provider authority.

## Scope

The atom creates or updates only the bounded terminal contract/config/schema,
synthetic fixture/test, acceptance evidence, Catalog transaction and generated
navigation, release registry, and the new PSR-0002 bundle. It may update
project-state/roadmap/archive text only inside that bundle.

No provider/API/RPC/WSS calls, credentials, raw retention, R2/R3 reads,
wallet/signer/transaction actions, spend, deployment, strategy promotion, or
cloud Sources replacement is in scope.

## Validation and recovery

Tests must reject a global-history conclusion, a new provider authority,
missing-to-zero conversion, premature UI-activation claim, a wrong A1S4 hash,
a release that overwrites PSR-0001, a release with the wrong five-role map, or
a task closure that invents a next strategy task.

Factory Fit is `FULL_REVIEW`. Delivery uses the normal tracked-only
clean-checkout gate and exact-head CI. If the later owner smoke fails, restore
the five prior PSR-0001 files, rerun its known smoke, and retain PSR-0002
unchanged for diagnosis. No deletion is needed.
