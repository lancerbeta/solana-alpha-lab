# TASK-21 information-sufficiency rebase contract v1.0

`T21-A6S_INFORMATION_SUFFICIENCY_REBASE_V1` replaces an invalid waiting rule
with a bounded decision rule. It does not unseal the hypothesis, collect new
data, authorize external calls, or declare the dataset ready.

## Finding

The accepted receipts contain six base panels: three H0 and three H1. H6 is an
explicit gap for all three members. The one H24 panel is a supplemental
sentinel and its frozen semantics prohibit counting it toward a complete
member. Therefore the exact current count is zero complete base members; the
checkpoint value of two was only an arithmetic upper bound from seven total
panels.

Waiting until day 30, spanning three calendar weeks, or merely naming
"multiple market states" cannot repair that shortfall. Calendar duration is not information,
and the existing plan never defined a reproducible market
state variable or threshold. Forcing such states would also invite
outcome-aware sampling. The numeric primary estimand remains unchanged, while
its claim is bounded to the documented nomination process and the contexts
actually observed.

## One final bounded extension

The forward-only replacement is two content-distinct nomination batches. The
first may admit at most three new members and the second at most two. A batch
must have a new source observation identity and content hash, a strictly later
observation time, and at least one previously unseen eligible mint. The frozen
policy and deterministic sort remain in force. Quote price, route, terminal
class, token rank, cost, PnL, or any other TASK-21 outcome cannot influence
admission or ordering.

Each new member gets exactly three foreground panels. P0 is captured after
admission; P1 and P2 become eligible after at least 1,801 seconds from the
preceding panel. There is no narrow expiry window and no minimum calendar wait.
All three panels must fit within 86,400 seconds for that member. A missed span
is retained as a gap and is never silently backfilled or relabelled.

The exact remaining envelope is sufficient but deliberately unforgiving:

```text
used                         60 external requests
two new source batches       4 requests maximum
5 members x 3 panels x 8   120 quote requests maximum
projected total             184 / 192
headroom                      8 requests
```

The headroom is safety margin, not reusable authority. Source calls remain
within 8 whole-task calls, quote calls within 184, retries remain zero, and
cash, credentials, wallet, signer and transaction actions remain zero.
The accepted owner pulse also leaves 25,079,733 response bytes, 125,464,222
stored bytes and 268,070,558 dataset bytes under their respective caps, with
186,280,022,016 free disk bytes. Variable response size is not projected as a
fact: the future runtime must fail closed against the exact byte, storage and
free-space limits on every write.

## Decision and stop rule

The narrow success gate is at least five complete members, fifteen complete
panels, sixty complete quote pairs, three content-distinct nomination batches,
healthy recovery, exact physical-cap reconciliation, complete candidate-state
retention, and sealed outcomes through collection stop. The freeze must report
member- and batch-clustered effective sample; raw panel count alone is not an
independence claim.

Observed operational or market states are reported at freeze but are neither
manufactured nor generalized. Success is therefore
`DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS`, not a market-wide or
cross-regime claim. Final TASK-22 eligibility remains a separate owner gate.

Collection stops immediately when the sufficiency gate passes, the eight-
candidate or request cap is exhausted, the next member cannot be completed
inside the remaining budget, recovery becomes unhealthy, a contract drifts,
the per-member span expires, or the original day-45 safety ceiling arrives.
There is no automatic extension, H72/H168 obligation, or rule requiring the
owner to wait until a date before enough evidence may be accepted.

## Authority and next boundary

This atom is local-write-only. It makes zero provider/API/RPC/WSS or Drive
calls, performs no nomination, admission, capture, backup, restore, Catalog or
Source mutation, and performs no Git transport. Its five files are a design
and deterministic acceptance package.

The next boundary is
`T21-A6S_EVENT_TRIGGERED_FINAL_COHORT_RUNTIME_PREP_V1`, local-write-only and
not authorized by this contract. It must bind the rebase to the existing
nomination and foreground-capture runtime and pass offline adversarial tests
before any new external authority is considered.
