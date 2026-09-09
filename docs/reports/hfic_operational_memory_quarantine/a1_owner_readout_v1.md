# Owner readout — HFIC_OPERATIONAL_MEMORY_QUARANTINE_V1

## Terminal

Completed HFIC sessions can be excluded from future HFIC search memory by an
append-only ResearchStore policy. Historical bytes stay immutable. Non-HFIC
memory stays visible. `evidence_epoch_sha256` is unchanged. After this merge,
later quarantine or restore does not require Git. This is not scientific
rejection, not deletion, not CLOSE/PARK change, and not alpha.

## What landed

1. Canonical policy artifact `HFIC_SEARCH_MEMORY_POLICY` with a linear
   append-only chain. Same effective quarantined set is `NO_CHANGE`.
2. CLI `memory-policy-status`, `memory-policy-preview`, and
   `memory-policy-apply --confirm-append-only`. Preview of
   `--quarantine-all-current-hfic` freezes an exact session list. Pending
   sessions are denied. Apply is not part of `/hypothesis-forge`.
3. Search identity: genesis / empty quarantine keeps the historical
   `search_key`. Non-genesis binds `memory_eligibility_sha256`. A→B→A restore
   recovers original A identity.
4. One eligibility resolver feeds `rank_prior_candidate_ids`, `lookup_prior`,
   and `build_prior_memory_snapshot`. Disposable fixture: 67 eligible before,
   2 after quarantine-all (the two non-HFIC HVs); capacity PASS.
5. F1/F2/F3 regressions unchanged. No live RDP write during this delivery.

## Explicit non-claims

- Not scientific DONE. Not alpha.
- Quarantined ≠ rejected / deleted / superseded.
- No raise of `prior_memory.max_records=64`.
- No CLOSE/PARK semantic change. No F1/F2/F3 change.
- Live clean-room quarantine of existing completed HFIC sessions is
  post-merge operational, not this PR.

## NEXT

Exact-head CI, then merge-readiness, then one owner merge phrase. The owner
does not click GitHub Merge. After merge, operational apply on the active RDP
uses the CLI above; no second Git atom is required for that reset.
