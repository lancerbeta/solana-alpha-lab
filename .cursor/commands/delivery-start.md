# Delivery start

Use `DELIVERY_HARNESS_V1` and an exact task contract supplied as input. Run
`scripts/delivery_harness.py check`, then `scripts/delivery_harness.py context`
for the executing client's direct route. Record declared provenance in the
entry checkpoint: coding client, and model or `UNKNOWN`. `OTHER` requires an
explicit client name such as `Kimi Code CLI`; it is not a catch-all. Return
Entry/Outcome, the receipt hash, explicit gaps, model-effort recommendation
and exact next safe action. Do not mutate before the bounded contract and
write set are resolved.
