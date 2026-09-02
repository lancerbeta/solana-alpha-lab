# Delivery review

For the exact task contract and exact diff, verify `DELIVERY_HARNESS_V1` with
`scripts/delivery_harness.py check`. Launch isolated critics: code review always;
add goal/DoD, architecture or refactor critics on their triggers. If isolated
critics cannot run, record `SINGLE_AGENT_REVIEW_FALLBACK` with verdict
`NOT_READY`. Merge denies fallback. Apply the same deterministic gates.

Before launching the architecture critic, classify the review profile:

```text
uv run --locked --managed-python python -B scripts/semantic_premise_review_cli.py classify \
  --changed-path <path> ... \
  --task <exact-task-contract>
```

When the result profile is `STANDARD`, do not supply a semantic packet.

When the result profile is `SEMANTIC_PREMISE`:

1. Build a frozen `smial.semantic-premise-review-packet` via
   `build-packet` (live args or fixture). Packet independence fields attest
   `PACKET_INFORMATION_PATH` only — not live parent-prompt isolation.
2. Run fail-closed `validate-launch` with the classification JSON, packet, and
   exact candidate binding (task/base/head/diff/claims). Stale or missing packet
   blocks architecture launch.
3. Launch `architecture-critic` in isolated context with that packet + exact
   diff + named claim files only. Do not pass the implementation transcript.
4. Architecture findings must include
   `packet_fingerprint_sha256=<exact fingerprint>`.

Canonical independent-review evidence still records role `ARCHITECTURE_CRITIC`
only — never a fourth merge role. Semantic routing cannot select work or grant
authority. Model diversity defaults to `UNPROVEN`; `PROVEN` requires an explicit
model identity string.
