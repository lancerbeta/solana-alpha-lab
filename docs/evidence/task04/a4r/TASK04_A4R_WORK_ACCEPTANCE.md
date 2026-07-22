---
artifact_id: EVIDENCE-T04-A4R-WORK-ACCEPTANCE-001
artifact_version: "1.0"
task_id: TASK-04
atom_id: T04-A4R
status: PASS_WITH_PATCH
prototype_gate: CLOSED
as_of: 2026-07-22
source_bundle: TASK04_A4R_RESULT_BUNDLE.zip
source_bundle_sha256: b0e60d98645abf4a9ba043e3073a9ac64292baf9f9d9379f37fead7880590a81
canonicality: NONCANONICAL_EVIDENCE_PENDING_TASK04_ATOM5
repository_write_performed: false
provider_api_rpc_calls: 0
cash_spend_usd: 0
contains_secrets: false
---

# TASK-04 / Atom 4R — Work acceptance memo

## Verdict

**PASS_WITH_PATCH.**

The bounded technical question `P04-Q1-CORE-NATIVE-REPLAY` is answered positively.
The prototype gate is closed. TASK-04 itself is not complete and its canonical status
remains `READY` until the ADR/registry/Catalog transaction, commit/CI acceptance and
canonical reconciliation are finished.

## Independent bundle validation

- ZIP inventory: 10 expected files, no extras.
- Internal SHA-256 ledger: 9/9 files match.
- All JSON files parse.
- No ZIP symlinks, absolute paths, username, email, secret/key/token patterns.
- Result bundle SHA-256: `b0e60d98645abf4a9ba043e3073a9ac64292baf9f9d9379f37fead7880590a81`.

## Accepted exact candidate set

- CPython `3.13.14`
- uv `0.11.29`
- DuckDB `1.5.5`
- PyArrow `25.0.0`
- Pydantic `2.13.4`
- pydantic-core `2.46.4`
- solana `0.40.1`
- solders `0.28.0`
- prometheus-client `0.25.0`
- pip-audit `2.10.1`

One 51-package lock graph was resolved for Windows x64 and Linux glibc x86-64.
The lock SHA-256 is:

`6b3a67c3fac536d8f5d51a5eaf73a9f5bb5e44a17ace7cf228ef6ed70a93cb8f`

All required imports passed on both platforms. Linux ran in the resolved
`python:3.13.14-slim-bookworm` linux/amd64 image with networking disabled for the
test phase.

## Accepted replay/storage evidence

- Cross-platform deterministic receipt:
  `b9aaac19c2ad9642b043227f133da245cd7511d0b9aec02b9d4e2a96400af017`
- Canonical/query result digest:
  `c854465fc38d8d3ffb31f4ea6d1ff62206a0344ba1483d7d5098d5adb10f3182`
- Parquet SHA-256:
  `424e53467877833fc3cecaf43301711183e70e23e7359fd703b23257fc3aed9e`
- Dataset manifest SHA-256:
  `2f2ebf6454dbf449dd41e77f04a714c07b20fd86bbfd5e16b0ae22136a5c76d5`
- Migration ledger SHA-256:
  `da8e5cf10f1c328a0e3d77de12ceff54e93c08dbee12c868d854865332b469b8`

Accepted checks:

- binary payload round-trip;
- nullable value remains NULL;
- all four operational timestamps survive;
- future-unavailable observation is excluded;
- reverse input order does not change canonical digest;
- accepted Parquet bytes are not modified in place;
- two fresh DuckDB rebuilds yield one digest;
- unsafe BIGINT-to-INTEGER narrowing fails;
- DuckDB extension auto-install/auto-load/community policy is deny-by-default;
- unapproved `httpfs` load is blocked.

## Accepted supply-chain evidence

- CycloneDX 1.5 artifact SHA-256:
  `4db108ab39ea41339949ca4fc74383e80aa040855b5222f6b9892f257f81aeb6`
- Normalized SBOM graph SHA-256:
  `e970bdc62a01229b926f7e734acfcd2deefb56addb0807641729962e151a772f`
- `pip-audit` import/CLI binding: PASS on both platforms.
- Vulnerability database: `NOT_QUERIED_BY_POLICY`.
- No absence-of-CVE claim is accepted.

## Cleanup and side effects

- Repository HEAD remains `f8ff483dbcf00454852a9638466eb4123e2c5809`.
- Repository tree remains `cfbf181fa2c005cf517a218c70ede51c701b5a43`.
- Index/worktree remain clean.
- Project `.venv` inventory is unchanged.
- Temporary root is absent.
- No residual test containers.
- Newly pulled image was removed and confirmed absent.
- Repository writes/commit/push/settings/provider/API/RPC/wallet/signer/transaction actions: 0.
- Cash spend: USD 0.

## Mandatory patches before TASK-04 completion

1. **Repository integration is still untested.**
   The prototype lock was isolated. Atom 5 must merge accepted candidates with the
   repository's existing `PyYAML==6.0.3` and `jsonschema==4.26.0`, produce the real
   `uv.lock`, and rerun local/Linux/full repository validation.

2. **Security tooling must not inflate runtime deployment.**
   `pip-audit` belongs in a dedicated development/security dependency group. Runtime
   sync/images must exclude that group while the project lock may still record it.

3. **Prototype reproducibility must become tracked evidence.**
   The returned bundle contains receipts but not the temporary prototype source, as
   requested by the cleanup contract. Atom 5 must preserve a sanitized deterministic
   offline fixture/test in Git so the accepted result can be rerun.

4. **License evidence remains incomplete for two exact artifacts.**
   `jsonalias==0.1.1` has a project-level MIT claim but no exact-artifact license
   metadata in the receipt. `solders==0.28.0` also lacks exact-artifact license
   metadata in this bundle. Resolve official repository/package license evidence or
   retain an explicit metadata discrepancy before final ADOPT.

5. **SBOM raw bytes are not deterministic.**
   Two exports differ in generated timestamp/serial only; the normalized graph is
   stable. ADR/Catalog must state this and bind both the raw artifact hash and
   normalized graph digest.

## Next atom

`TASK-04 Atom 5A — ADR/registry/Catalog local candidate, without commit or push`.

The atom must create the accepted ADR-002, final matrix, append-only reuse decisions,
Catalog assets/relations, reproducible prototype tests/receipts, exact integrated lock,
generated navigation and repository task/handoff candidate. It must not claim TASK-04
DONE and must stop before commit.
