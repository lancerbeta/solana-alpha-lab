# TASK-07 provider smoke execution summary v1

Status: **PASS_WITH_PROVIDER_FAILURE_EVIDENCE**

## Decision

The bounded 35-attempt live provider smoke is sufficient to retain Helius,
Solana Tracker, Jupiter and Raptor hosted beta as research transport candidates.
It proves that the frozen request and response contracts can be exercised under
the approved caps. It does not prove fillability, executable realized VWAP,
net return, provider SLA or alpha.

TASK-07 remains in progress. This atom records sanitized evidence only and does
not change canonical status.

## Evidence roots

| Source run | Attempts | Files | Raw bytes | Response bytes | Fileset SHA-256 |
|---|---:|---:|---:|---:|---|
| `t07a4b-20260724T132144Z` | 33 | 99 | 466,676 | 48,777 | `cbf9d931a9337c67bceeb83887e8eca3fd326050f81266443f31cb3aeaffbf0c` |
| `t07a4b-20260724T135632Z` | 2 | 6 | 22,738 | 827 | `729922dbf54b1b8e229119d65a11b2a69cc7283460335c5e1fa4c2bab61ea92c` |

The raw runs remain ignored, local and immutable. The tracked fixture stores
typed metadata and content hashes only; it contains no response bodies, request
values, headers, credentials or absolute paths.

Tracked evidence:

- fixture: `tests/fixtures/task07/provider_smoke_live_evidence_v1.json`
  (`efc95a74868a8868501051ea64216e18788eafa15e226d872ac9695e24b60668`);
- machine receipt:
  `docs/evidence/task07/provider_smoke_execution_receipt_v1.json`
  (`900cf054916995e2b839fad3bf4873666bcd9ca635903d1a58937b346de27786`).

## Accepted result

| Terminal class | Count |
|---|---:|
| `SUCCESS` | 32 |
| `INVALID_REQUEST` | 1 |
| `PROVIDER_5XX` | 2 |

Provider attempt inventory is exact: Helius RPC 11, Helius WSS 2, Solana
Tracker Data 8, Jupiter Swap 9 and Raptor hosted 5. Total response payload is
49,604 bytes. The source executions made 35 network attempts with zero retries,
used 15 modeled Helius credits, spent USD 0 and performed no wallet, signer or
transaction action.

Three source classifications are corrected in the accepted evidence layer:

- `R01#1`: exact Raptor health response `OK` is accepted as success;
- `R02#1` and `R03#1`: Raptor quotes use provider-specific `amountOut`, so both
  are accepted as success.

The original raw receipts are not rewritten. The fixture carries both the
source classification and the accepted classification, so the correction is
auditable rather than silent.

`J09#1` and `R05#1` remain `PROVIDER_5XX/http_500`. In particular, `R05#1` is
not converted to `NO_ROUTE`, zero or success. This is useful failure evidence,
not a reason to falsify provider feasibility.

## Boundaries and residuals

- Successful quote transport is not a fill or NetReturn observation.
- Raptor hosted beta remains optional research infrastructure with no accepted
  production SLA.
- No provider/API/RPC/WSS call was made while producing this tracked evidence.
- No raw file, dependency, Catalog record, Git index, commit, remote or
  canonical Source was changed.
- Catalog registration is still `CATALOG_GAP_PENDING_SEPARATE_ATOM` and requires
  its own authority gate.
- Validation passed: evidence tests 11/11, full repository suite 376/376,
  secret scan, Catalog validation and generated-navigation check. The legacy
  repository-state policy does not recognize this untracked TASK-07 candidate;
  changing that policy is outside Atom 5A.

The next safe checkpoint is Work/control-plane acceptance of Atom 5A from the
four managed files and their validation receipt.
