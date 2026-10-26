# Ordinary Forge-run finalization

Engineering outcome: the existing ordinary BASE and normalized sessions can be
folded into their genuine owner-final without another scientific attempt. This
is operational completion, not scientific acceptance or family closure.

The defect had three connected parts: ordinary BASE did not provide the parent
for representation discovery; a saved BASE draft falsely implied a child resume;
and completion assumed every operation shared the aggregate's active BASE slot.
Code evolution also changes capability provenance, so fully completed frozen
chains need an explicitly limited historical readback path.

The existing ladder now discovers ordinary children by frozen parent, focus,
market and slot, distinguishes their own saved draft, and retains CONTROL as a
separate protocol. Every ACTIVE representation action selects its own slot and
passes existing scientific admission. Incompatible pending source capabilities
block; a BASE draft cannot conceal a child or turn it into a fresh START.
The existing orphan-draft validator receives the child's frozen parent/payload,
rather than a controller-side recovery exception. Orphan recovery additionally
requires the BASE/control parent selected by this aggregate; the draft cannot
attest its own parent. Episode resume prints its own saved-draft instruction. Historical aggregation requires a wholly completed chain,
consistent source capability and unchanged representation versions. The existing
transition owner still decides the final; no new state machine or storage.

The completion owner verifies each operation's own stage, scientific slot and
journal, plus exact parent/version/payload for a representation. One aggregate
can therefore complete both operations regardless of which included stage is
active. Foreign bindings, pending child, stale receipt and missing evidence fail
closed. Legacy BASE and completion monotonicity stay supported.

Proof: validation.json describes one native synthetic published-episode vertical
and short negative controls. The vertical checks no-write inventory equality,
both operations OPEN before persistence, one native persisted owner-final,
COMPLETED for both, repeated persist with no append, unchanged scientific
look-ledgers and released universe-policy gate. It checks actual child-slot and
admission calls, and top-level NEXT/PERSIST before append versus native DONE and
committed READBACK afterwards; a computed receipt hash is never labelled saved. Existing direct-consumer tests
cover ordinary/CONTROL, saved-scope and prefreeze recovery routes. A foreign-parent
occupied slot stays blocked rather than issuing another START; its source
session is never consumed as this run's stage. No real-data scientific call,
publication, reminder change, provider call or dependency was introduced.

## Operational handback after merge

Revalidate the exact run and saved IDs/hashes in the task contract. On accepted
code run the normal read-only entry, require its two original completed stages
and owner-final, capture scientific inventory and look accounting, then perform
only native forge-run --persist. Cold-read both operations and universe status;
require both COMPLETED, no unresolved reservations, no scientific byte or spend
change. Repeat persist must add nothing. Owner-stop is not this recovery.

At engineering review this real append is intentionally still pending. Code/CI
or merge never substitutes for the operational receipt. The already authorized
post-merge action needs no new science/publication/reminder approval; merge
itself retains the repository's exact-head owner gate. Before operational append
ordinary code revert is available; afterwards preserve the receipt and prefer
forward repair, because an older reader may again fail to derive child completion.

## Exact post-merge recipe

Run from the accepted canonical checkout; `local/` outputs stay local. Stop on
any mismatch with the exact sessions/results in the task. Focus is fixed:
`OPPORTUNITY_EPISODES:AUTO`. Capture the native read-only inventory/lifecycle
snapshot before append, then repeat after append with only the output filename
changed to `local/forge-finalization-after.json`:

```powershell
$env:PYTHONUTF8='1'
@'
import sys,json
from pathlib import Path
sys.path.insert(0, 'src')
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.hfic_ordinary_operation import get_operation,operation_lifecycle,journal_occupancy
store=ResearchStore(Path('local/factory_v1/data_plane'),create_if_missing=False)
ops=['dd17712c78eab047fa7e5cf8977e0940f99291211b31ada000fbe14e044c5050','868bc7e50e1adced93a024380b0e00680775f2c8843b3903561a2cfe3e7e40f8']
rows={r.record_id:r.payload_sha256 for r in store.iter_committed_records()}
state={o:operation_lifecycle(store,get_operation(store,o)) for o in ops}
looks={get_operation(store,o)['journal_scope']:journal_occupancy(store,get_operation(store,o)['journal_scope']) for o in ops}
print(json.dumps({'records':rows,'lifecycle':state,'occupancy':looks},default=str,sort_keys=True))
'@ | uv run --locked --managed-python python -B - > local/forge-finalization-before.json
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --no-write --owner-focus OPPORTUNITY_EPISODES:AUTO > local/forge-finalization-preview.json
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-show --result-ref HFIC-ART-DISCOVERY-100FCD16C57B5FC2E5113EDEC62D15D8D6BEB622
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-show --result-ref HFIC-ART-DISCOVERY-CDF6AA01A92047EA6ED5F37C4C661E0882797797
```

Require run `FORGE-RUN-174FEA4EFD507581`, its two exact source sessions,
`SEARCH_EXHAUSTED_CURRENT_EVIDENCE`, source capability preserved, writes zero,
NEXT/PERSIST and both operations OPEN. Verify both result hashes against the
task. Only then append once and cold-read:

```powershell
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --persist --owner-focus OPPORTUNITY_EPISODES:AUTO > local/forge-finalization-persist.json
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --no-write --owner-focus OPPORTUNITY_EPISODES:AUTO > local/forge-finalization-cold.json
uv run --locked --managed-python python -B scripts/hypothesis_forge.py research-policy-status --for-operation dd17712c78eab047fa7e5cf8977e0940f99291211b31ada000fbe14e044c5050
uv run --locked --managed-python python -B scripts/hypothesis_forge.py research-policy-status --for-operation 868bc7e50e1adced93a024380b0e00680775f2c8843b3903561a2cfe3e7e40f8
uv run --locked --managed-python python -B scripts/hypothesis_forge.py universe-policy-status
```

Repeat the snapshot as `local/forge-finalization-after.json`. Require both native
lifecycle states COMPLETED, original record ID-to-payload-hash map a complete
unchanged subset, exactly one new FORGE_RUN_RECEIPT artifact, identical occupancy,
zero unresolved reservations and empty universe `blocking_operations`. One
repeat of the same `forge-run --persist` must add no record. Preserve the saved
receipt and unrelated historical UNKNOWN; stop on mismatch rather than rerun
science, rewrite source history or use owner-stop. No reminder/publication step.
