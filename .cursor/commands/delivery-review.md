# Delivery review

For the exact task contract and exact diff, verify `DELIVERY_HARNESS_V1` with
`scripts/delivery_harness.py check`. Launch isolated critics: code review always;
add goal/DoD, architecture or refactor critics on their triggers. If isolated
critics cannot run, record `SINGLE_AGENT_REVIEW_FALLBACK` with verdict
`NOT_READY`. Merge denies fallback. Apply the same deterministic gates.
