# TASK-40 contract — bonding_curve PDA GTA clock capture

ADOPT the sealed A22 `getTransactionsForAddress` body, the TASK-08 Pump event decoder, and the official Pump `bonding_curve` PDA seeds (`const "bonding-curve"` plus mint). FORK only the address (derived PDA of the TASK-38 mint) and omit the one-day `blockTime` window. Never GTA `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`.

Owner phrase: `OK T40-RC002 H11_BONDING_CURVE_PDA_GTA_ONE_SHOT`. Cash 0. Max 3 provider requests. Secrets stay in local env.

Frozen curve: `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC` from mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`.

Terminals: `CLOCKS_RECONSTRUCTED_COHORT_READY`, `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`, `INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE`, `STOP_INTEGRITY_CONFLICT`.
