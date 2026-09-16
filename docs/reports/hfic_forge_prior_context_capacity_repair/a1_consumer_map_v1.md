# Consumer map — HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1

Classification of fields touched by this atom.

## GENERATION_SEARCH_CONTEXT (Prompt A)

| Field | Notes |
| --- | --- |
| `ranked_prior_candidate_ids` | Ranked identity list; unchanged |
| `ranked_prior_entries` | Now Forge projection via `compact_forge_prior_entry` |
| `owner_focus`, `evidence_epoch_sha256`, `search_key_sha256` | Binding |
| `feature_hints` / `feature_families` / `feature_grounding_*` | Evidence surface |
| `closed_family_ledger` | Anti-rediscovery ledger |
| `dataset_entries` / `capability_entries` | Admissible evidence/capabilities |
| `prior_work_receipts` | Query-recipe receipts only (QUERY-HFIC-*) |

Forge prior entry retained keys (when present):
`hypothesis_version_id`, `memory_status`, `decision_kind`, `reason_code`,
`park_status`, `definition_sha256`, `mechanism` xor `claim`,
`primary_x_family`, `primary_y`, `cheapest_falsifier`,
`actor_counterparty` only if mechanism/claim absent,
compact `legacy_definition` subset for reopenables.

## CRITIC_MEMORY (unchanged)

| Surface | Notes |
| --- | --- |
| `compact_prior_entry` | Full Critic capsule |
| `build_prior_memory_snapshot` | max_records=64, max_bytes=65536 |
| `CRITIC_INPUT_PACKET.prior_memory` | Freeze-owned snapshot |

## MACHINE_BINDING_ONLY

| Field | Notes |
| --- | --- |
| `dataset_manifest_ids` / `dataset_fingerprints` | Parallel to `dataset_entries`; kept (freeze/tests) |
| `capability_ids` | Used by freeze grounding (`_accepted_capability_ids_from_preflight`) |
| `forge_context_packet_sha256` | Hash binding |
| `vision_integrity.status` | PASS/BLOCKED gate |

## AUDIT_ONLY / permanent schema cleanup (not capacity-gated)

These removals are permanent de-duplication after consumer proof, not an
overflow valve that runs only when the packet is oversize:

| Field | Notes |
| --- | --- |
| `related_prior_recipe_ids` | Was byte-identical to QUERY list in `prior_work_receipts`; no other consumer; removed |
| Ranked IDs inside `prior_work_receipts` | Duplicated `ranked_prior_candidate_ids`; removed from receipts |

## CRITIC-ONLY richness (omitted from Prompt A when a lean distinguisher remains)

| Field | Notes |
| --- | --- |
| `session_id`, `hfic_protocol` | Machine/audit binding; not Prompt A anti-rediscovery |
| `population`, `decision_timestamp`, `horizon_notional`, `negative_control` | Omitted when mechanism/claim/X/Y/falsifier/legacy already distinguish; retained as fallback when they are the only source distinguishers |

## UNKNOWN → do not change

No field with unknown consumers was modified.
