# TASK-21 dataset freeze, Catalog and Factory Fit contract v1

## Purpose

T21-A7 turns the already collected and remotely recoverable TASK-21 evidence
into one immutable, owner-readable analysis input. It performs no collection,
does not inspect outcomes and does not start TASK-22.

## Accepted truth

The exact dataset contains 91 files in 13 roots, 1,263,895 stored bytes and has
inventory SHA-256
aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae.
The private content-addressed archive was read back byte-for-byte and restored
in isolation before this acceptance.

The effective sample is intentionally narrow:

- eight members were nominated and admitted;
- five members have complete P0/P1/P2 panels across two complete nomination
  clusters, R2 and R3;
- three earlier R1 members retain H0/H1, one H24 sentinel and an explicit
  three-panel H6 gap with no backfill;
- the whole set contains 22 observed panels, 88 quote pairs and 176 quote
  attempts from three content-distinct nomination batches;
- no outcome, label, strategy decision or PnL value was opened during
  collection or acceptance.

This is enough to exercise a deterministic split and holdout ledger and to run
narrow conditional analysis. It is not evidence of market-wide coverage,
cross-regime generalization, statistical power, alpha, executable NetReturn or
production readiness.

## Freeze rules

The tracked freeze manifest lists every accepted local file path, byte count
and SHA-256. Accepted source bytes are immutable. A correction requires a new
dataset identity and must preserve this version; silent replacement, deletion,
backfill and historical rewrite fail closed.

TASK-22 must record its split and holdout ledger before reading any outcome.
The two complete nomination clusters must remain visible as grouping keys so a
member-level random split cannot silently leak a shared nomination batch.

## Catalog economy

TASK-21 created many atom-level plans, receipts and tests. Registering every
intermediate file as a first-class Catalog asset would add maintenance without
improving discovery. A content-addressed TASK-21 artifact index therefore
preserves every path and hash while Catalog registers only durable contracts,
controls, read models, final evidence, handoff and external bundle. Prior
planned IDs not selected as stable assets are explicitly superseded by that
index; they are not silently lost.

## Product and owner reconciliation

The product-vision gate resolves as CANONICALIZED_WITH_PATCH in the local
canonical candidate. It preserves the Research Workbench, shared evidence and
truth plane, and production control plane/Owner Cockpit as separate but linked
planes. The roadmap patch binds a documentation foundation and a
production-lite control-plane task to durable triggers without implementing
either in TASK-21.

The final Owner Pulse is a derived read model. It must expose the final dataset
identity, sample limitations, recovery health, exact next action and zero
external authority. It cannot become a second truth owner.

## Authority and stop boundary

This atom is LOCAL_WRITE_ONLY. Provider/API/RPC/WSS calls, Drive actions,
credentials, cash spend, wallet/signer/transaction actions, collection,
raw/dataset writes, Project Source mutation, commit, push, PR, merge and
destructive actions are zero. The next boundary is a separately authorized
T21-A8 repository delivery; TASK-22 remains a later Entry Gate.
