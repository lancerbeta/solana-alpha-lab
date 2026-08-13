# Delivery start

Use `DELIVERY_HARNESS_V1` and an exact task contract supplied as input. Run
`scripts/delivery_harness.py check`, then `scripts/delivery_harness.py context`
for `DIRECT_CURSOR_DELIVERY`. Return Entry/Outcome, the receipt hash, explicit
gaps, model-effort recommendation and exact next safe action. Do not mutate
before the bounded contract and write set are resolved.
