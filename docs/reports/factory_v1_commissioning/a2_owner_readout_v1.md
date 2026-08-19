# Factory v1 commissioning — owner readout

Live Free-key cycle completed through Factory. This is a product
commissioning packet, not alpha and not `FACTORY_V1_OPERATIONAL_READY`.

## Packet

| Field | Value |
| --- | --- |
| QUESTION | Can the owner start from Factory and complete one bounded Jupiter Free-key quote-native experiment through ExperimentSpec without a hypothesis-specific core runner? |
| ESTIMAND | QuotedRoundTripFriction(t0) -> QuotedLiquidationRecovery(H900) |
| POPULATION | new live 6 RECENT + 6 TRADED, excluding A1 and MOVE 2 mints |
| DATA | capture policy + exclusion receipts available; runtime and acceptance now hash-bound |
| RESULT | `DIRECTIONAL_HINT_NOT_CONFIRMATION` |
| UNCERTAINTY | screening hint, not OOS confirmation |
| ROBUSTNESS | H3600 predeclared robustness, not searchable Y |
| FAILURE | scientific hint is not alpha; H14400 remains an explicit gap |
| DECISION | product PASS (`FACTORY_COMMISSIONING_LIVE_CYCLE_PASS`); scientific result stays a hint |
| NEXT | ATOM 3 VPS only after this packet is accepted; do not start MOVE 3 |

## Non-claims

No alpha, NetReturn, MOVE 3, paid plan, second provider, `/execute`, wallet,
signer, transaction, or operational-ready milestone.
