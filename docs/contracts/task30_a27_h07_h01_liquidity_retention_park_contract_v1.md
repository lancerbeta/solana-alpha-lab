# TASK-30 A27 H07/H01 liquidity-retention park contract v1

## Decision

Apply the exact owner phrase
`OK T30-A26 RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION` as a
park-from-priority decision for `RC001-H07-H01-LIQUIDITY-RETENTION`.
Keep A24/A25/A26 science in git. Do not delete research memory. Do not
promote TASK-30. Do not freeze notionals, authorize `ROUTE_FEASIBILITY`
capture, buy a provider, or start H13/H02 trials.

## Frozen inputs

The packet reads, never restates:

- A26 acceptance
  `docs/evidence/task30/a26_h07_h01_owner_fork_packet_acceptance_v1.json`
  with SHA-256
  `8d4755643c4f64f325e3d2986d928a93f9c1bf64e7694c47230440b8271aecd7`.
  Terminal must remain
  `FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY`.
  Task state must remain `BLOCKED_DATA`.
- Retained A24 acceptance SHA-256
  `257e81801afbfa3ba6bf64e8c25b41009e560bb168e9a01d92c606ca4bcdb183`.
- Retained A25 acceptance SHA-256
  `c29ecd424e4c2276259ffc05aec6fb8058b53469a30c763db972c0581f84ceca`.
- RC001 freeze `configs/task28_rc001_registry_freeze_v1.yaml` for group
  `RC001-H07-H01-LIQUIDITY-RETENTION` with definition SHA-256
  `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7`.
  The freeze file is not mutated.

Any hash, terminal, phrase or freeze drift is `STOP_INTEGRITY_CONFLICT`.

## Park versus delete

In this factory, `RETIRE` closes future use by policy. It does not
delete versions, trials, negative results or prior evidence. The owner
word «паркуем» is that same policy: park from priority, retain science.

## Terminal outcomes

- `RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED` — the family is
  off the live priority queue; TASK-30 stays `BLOCKED_DATA`.
- `STOP_INTEGRITY_CONFLICT` — frozen input drifted.

## Non-claims

No TASK-30 acceptance or canonical DONE. No RC001 definition change. No
H07/H01, H13 or H02 trial. No effect estimate, alpha, fill, settlement,
PnL, NetReturn or cashflow. No notional-bucket freeze. No
`ROUTE_FEASIBILITY` registry insert or capture. No provider, credential,
network, cash, wallet or signer action.
