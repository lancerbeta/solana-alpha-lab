# TASK-21 final cohort evidence-freeze contract v1

## Purpose

This atom closes the collection loop without opening the hypothesis outcome. It
proves that the exact five-member R2/R3 extension is complete, bounded,
content-addressed at the receipt and local-file levels, and ready for the
separate TASK-21 A7 acceptance boundary.

This is an **evidence-set freeze**, not yet the final dataset freeze. The latest
remote recovery proof covers R3 P0/P1 but predates R3 P2 and does not cover the
entire final dataset. A7 must therefore include or be preceded by a full
content-addressed remote read-back and isolated restore of the final dataset.

## Frozen facts

- Five exact new members: three from R2 and two from R3.
- Fifteen complete P0/P1/P2 panels.
- Sixty complete directional quote pairs and 120 terminal quote attempts.
- Three time-ordered, identity-distinct and content-distinct nomination batches.
- Maximum membership share from one extension batch: 3 / 5 = 0.6.
- Minimum P0→P1 and P1→P2 separation: 1,801 seconds.
- Maximum P0-completion→P2-completion span per member: 86,400 seconds.
- Whole-task stop usage: 184 / 192 external requests, 8 / 8 source requests,
  176 / 184 quote requests, and 335,817 / 25,165,824 response bytes.
- Six local create-only evidence roots: 59 files and 807,082 stored bytes.

The accepted disposition remains
`DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS_PENDING_A7`. It is not a
market-wide, cross-regime, trade, fill, position, PnL, profit or alpha claim.

## Fail-closed rules

The deterministic reviewer rejects:

- a changed, reordered, duplicated or outcome-selected member;
- a reused source observation identity or content hash;
- missing panels, non-terminal attempts, timing violations or duplicate receipts;
- provider, request, response-byte or local-evidence drift;
- non-zero retries, concurrency other than one, cash, credentials, scheduler,
  deploy, Catalog, Source, wallet/signer/transaction, destructive or merge action;
- any attempt to declare A7 or TASK-22 authorized;
- any attempt to call the complete dataset frozen before full final recovery proof.

The reviewer consumes lineage, identities, timestamps, counts, hashes, caps and
recovery status only. It does not read quote, route, price, cost, ranking, PnL,
return or hypothesis-verdict values.

## Authority and next boundary

This atom is `LOCAL_WRITE_ONLY`. It performs zero provider/API/RPC/WSS or Drive
calls, spends no cash, uses no credentials, and performs no commit, push, PR,
merge, Catalog, Source, wallet, signer, transaction, raw-data or dataset write.

Passing this atom sets `cohort_evidence_frozen=true`, `dataset_frozen=false`,
`a7_review_eligible=true`, and `task22_eligible=false`. The next boundary is a
separately authorized A7 path that first proves full final-dataset recovery,
then reconciles Catalog, product-vision durability, documentation ownership and
Factory Fit before TASK-22 can be considered.
