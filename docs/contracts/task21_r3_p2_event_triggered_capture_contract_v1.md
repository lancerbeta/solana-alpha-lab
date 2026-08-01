# TASK-21 R3 P2 event-triggered foreground capture contract v1

## Purpose

Complete the final P2 panel for the exact two frozen R3 members after the minimum separation from their accepted P1 receipts. This is the last data-collection panel in the event-triggered final-cohort plan; it does not analyze outcomes or authorize TASK-22.

## Frozen execution

- Population: `T21-WATCH-7a678b1052ac10b7d492`, then `T21-WATCH-2c5632a2ba71c8e44637`.
- Predecessor: hash-bound R3 P1 receipts; P2 cannot run before both members are eligible.
- Provider: keyless Jupiter quote endpoint only.
- Each member: four USD notionals and at most eight quote requests.
- Whole P2: at most 16 provider calls, retries 0, concurrency 1, create-only local evidence at most 16 MiB.
- Recovery: the fresh R3 P0/P1 Drive read-back and isolated-restore receipt must remain hash-bound and healthy.

Any protected-input drift, stale recovery, incomplete population eligibility, cap pressure, expired member span, collision, or provider failure retains evidence and stops without retry.

## Boundary after PASS

PASS closes collection for the five-member R2+R3 extension and routes to a separate final-cohort review and freeze. It does not claim alpha, market-wide coverage, TASK-22 eligibility, Catalog finalization, Source reconciliation, or TASK-21 DONE. No credentials, cash, scheduler, deploy, wallet, signer, transaction, delete, overwrite, or merge action is permitted.
