# TASK-30 A14P-R1 — auth recovery gate

## Entry Gate

- Mission/estimand: determine whether one future bounded Helius public-read
  stream can return target-bound transaction observations; no market label or
  cash estimand is opened.
- Consumer: the exact owner external-read gate for TASK-30.
- Cheapest falsifier: a fresh V2 attempt fails before capture or cannot produce
  a closed, hash-verified terminal receipt.
- Information gain: separates the consumed V1 auth/access failure from a clean
  bounded transport outcome without rewriting old evidence.
- Cost/risk: offline work only now; any later external attempt is capped by the
  frozen V2 profile and requires a new owner phrase.
- Recovery: V1 remains immutable; unresolved V2 blocks another attempt until
  its terminal truth is reconciled.
- Reuse/build: WRAP the accepted TASK-08 WSS transport and the A14P adapter;
  add no provider client, scheduler or generic stream service.
- Verdict: `START_AS_WRITTEN` for the offline recovery package.

## Bounded deliverable

This atom adds V2 execution/runtime profiles, a separate ignored A4 root,
closed schema/fixture bindings, deterministic fake-transport tests, the prior
V1 negative-evidence reference and an offline acceptance receipt. It stops
before the next credential lookup or WSS call.

## Hard stop

Do not use the V2 owner phrase, read `HELIUS_API_KEY`, contact Helius, retain
provider raw data, schedule/reconnect/retry, access R2/R3, open a trial, change
Project Sources, or claim TASK-30 acceptance in this atom. Those require a
separate exact owner gate after merge and CI.

## Factory Fit / Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`: the patch preserves history, reuses the
existing transport, makes the recovery seam explicit and keeps unknown/raw
truth fail-closed. `NOW` is one exact V2 owner external gate after delivery;
`WATCH` is repeat/scheduled capture only if a valid first capture proves that
coverage—not auth or transport—is the bottleneck.
