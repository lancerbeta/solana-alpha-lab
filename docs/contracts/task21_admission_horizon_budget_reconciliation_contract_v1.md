# TASK-21 admission, horizon and budget reconciliation contract v1

`T21-A6S_C0_ADMISSION_HORIZON_BUDGET_RECONCILIATION_V1` is a
forward-only overlay over the accepted TASK-21 run plan, real nomination
policy and observation-horizon correction. It resolves their execution
conflicts without rewriting any historical artifact and without starting
collection.

## Why an overlay is required

The accepted contracts are individually valid but cannot be executed together
as written:

- the real nomination policy evaluates a tranche only after its declared close;
- the observation-horizon correction makes the first capture eligible without
  waiting seven days and defines six horizons;
- the original run plan budgets exactly three panels per complete member and
  no more than 192 external requests for the whole task.

Running all six horizons for every possible member would exceed the accepted
budget. Backdating T1 admission to the original close would also create false
history. This overlay narrows execution while preserving the original
scientific and physical boundaries.

## Protected truth and precedence

The exact run plan, nomination policy, nomination source contract, source
receipt, frozen replay partition, horizon policy, correction receipt and
recovery receipt are protected by SHA-256 in the companion YAML plan. They
remain byte-for-byte unchanged.

This overlay has precedence only where those inputs conflict about admission
time, panel allocation or request arithmetic. Every other rule remains in
force. In particular:

- the original T1 anchor and P7D timestamp remain historical facts;
- T2 and T3 retain their original offsets from the original T1 anchor;
- no nomination, admission or capture is backdated;
- no quote, route, price, terminal result or hypothesis outcome may influence
  membership, panel allocation or sentinel selection;
- missed capture windows remain explicit gaps and are never backfilled.

## T1 capacity close

T1 may be closed early for capacity only for the exact three nominations
already frozen in the protected replay partition. This exception is valid
because the three events fill the accepted T1 cap, were frozen before this
correction, have no prior relevant quote exposure, and no quote outcome was
observed before the correction.

The exception does not create admissions. Under a later explicit authority,
the three events may be evaluated in their frozen deterministic order and at
most three may be admitted. Any resulting membership event uses its actual
evaluation/admission time. The original future tranche close must not be used as `entered_at`,
and later or backdated nominations cannot reorder T1.

T2 and T3 are not accelerated, compressed or replenished from unused capacity.
Their accepted schedule and caps remain unchanged.

## Base panels and sentinel panels

Every capture-eligible member receives exactly three base panels:

- `H0` at the first authorized capture;
- `H1` at `H0 + 1 hour`;
- `H6` at `H0 + 6 hours`.

These three panels preserve the original run plan's three-panel definition,
minimum 1,801-second separation and maximum one-day member span.

At most six members may be allocated base panels under this overlay. Up to
eight nomination or watchlist records may still be retained; this does not
authorize panels for all eight. Base-panel allocation is fixed before quote
outcomes and must retain at least one slot for every T1/T2/T3 tranche.

Exactly one sentinel may also receive `H24`, `H72` and `H168`. The sentinel is
the first capture-eligible admitted member by the frozen outcome-blind key
`first_reliable_available_at`, `observed_at`, `nomination_event_id`. Sentinel
panels measure persistence but do not increase the count of complete members
or complete base panels used for minimum dataset sufficiency.

There is no background scheduler. After an actual H0 anchor exists, each later
window requires a durable due marker and a separately authorized foreground
run. A missed window is recorded as a gap.

## Budget proof

The accepted outer ceiling remains 192 external requests:

- source reservation: at most 8;
- quote reservation: at most 184;
- minimum sufficient dataset: 5 members × 3 base panels × 8 calls = 120;
- sentinel supplement: 3 panels × 8 calls = 24;
- minimum-sufficiency reservation: 8 + 120 + 24 = 152, leaving 40;
- overlay maximum: 6 members × 3 base panels × 8 calls + 24 sentinel calls
  + 8 source calls = 176, leaving 16.

The next H0 stage is additionally bounded to at most three T1 admissions,
three H0 panels and 24 quote calls. These are proposed caps, not authority.

## Authority boundary

This atom is local-write-only. It performs zero provider/API/RPC/WSS calls,
zero admissions, zero live collector or dataset writes, zero Drive operations,
zero provider credits, zero cash spend and zero wallet, signer or transaction
actions. It installs no scheduler and changes no dependency.

Before any external launch, recovery health must be revalidated and a separate
exact authority must freeze the provider endpoint, request/credit/byte caps,
raw and backup destinations, admission input, and rollback/stop conditions.
TASK-21 Catalog registration remains pending `T21-A7`.
