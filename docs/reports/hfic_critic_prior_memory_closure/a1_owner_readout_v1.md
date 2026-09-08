# Owner readout — HFIC_CRITIC_PRIOR_MEMORY_CLOSURE_V1

## Terminal

Fresh HFIC-V1.2 freeze emits critic `packet_version=1.3` with
`generator_prompt_version=HFIC-V1.2` and a complete bounded `prior_memory`
snapshot. Isolated Critic recovered `HYP-PTRUE-SEED-CIRCLE-001` from the packet
alone (RDP reads=0). Historical critic `1.0` / `1.1` / `1.2` stay readable;
`1.2` does not require `prior_memory`. Forge lexical top-N stayed blind.
Capacity overflow is `PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED` /
`OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`.

## What landed

1. `hfic_prior_memory.py` projects every eligible historical `HYPOTHESIS_VERSION`
   (not only `ranked_prior_candidate_ids`) into compact capsules with existing
   `memory_status` semantics. Bound: 64 records / 65536 bytes. No silent
   truncation.
2. `freeze_draft` attaches the snapshot to critic `packet_version=1.3` after
   `PREFLIGHT_STORE_DIGEST_MISMATCH` binding and before `persist_frozen_session`.
   Forge draft stays `packet_version=1.2` / `HFIC-V1.2`. Historical critic `1.2`
   remains readable without `prior_memory`.
3. Critic skill / Prompt B / slash recovery: packet is the sole research-memory
   input. Lexical identity equality is not required. Visibility is not
   automatic hard-close.
4. T1–T7 plus isolated packet-only Critic smoke. Ranker unchanged.

## Explicit non-claims

- Not scientific DONE. Not alpha. Not Critic-reasoning completeness.
- Ranker / `MAX_RANKED_PRIORS` / Prompt A search unchanged.
- F3 runner-up lifecycle still open.
- Calibration memory rebase not implemented.
- No embeddings, RAG, vector DB, or generator.

## NEXT

Exact-head CI, then merge-readiness, then one owner merge phrase. The owner does
not click GitHub Merge.
