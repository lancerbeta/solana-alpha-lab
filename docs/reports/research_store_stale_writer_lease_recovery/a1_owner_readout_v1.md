# Owner readout — RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_V1

## Result
Dead local ResearchStore writer leases no longer permanently wedge writer_lease().

## What changed
- Expired + same-host + PID DEAD => reclaim via os.link quarantine, create-only recovery artifact, fresh lease.
- Live / non-expired / remote / UNKNOWN / malformed => fail-closed, no deletion.
- Orphan quarantine after crash between link and unlink is resumable (T13).
- Successor locks are protected by inode identity checks; Windows PermissionError maps to race.

## Validation
- python -m unittest tests.test_research_store — PASS (T11 symlink skipped without privilege).

## Non-claims
- Not multi-writer.
- Not a distributed lock service.
- No provider/credential/wallet actions.

## Next
After merge: return to product/research (/hypothesis-forge). No reliability-refactor chain.
