# TASK-11 entity-input pilot execution summary v1

## Result

`T11-A4_OFFLINE_REPLAY_AND_SANITIZED_EVIDENCE_V1` passes for the
accepted claim:

`RAW_TOP20_ACCOUNT_CONCENTRATION_FEASIBILITY`

The retained `T11-A3` run was replayed without network access. Its canonical
runtime receipt, three immutable Parquet rows, file hashes, logical content
hashes, raw-event lineage and RPC schemas agree. The replay deterministically
projects five TASK-05-compatible `EntityInputSnapshot` rows.

This is a current, forward-only feasibility observation for one mint. It is
not a holder-distribution, ownership-cluster, toxicity, strategy-veto or alpha
result.

## Accepted observation

- Mint: `4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump`
- Run: `t11a3-20260728T102537Z`
- Supply: `924355154265060` atomic units, decimals `6`
- Largest token accounts observed: `20`
- Token-account owners resolved: `20/20`
- Raw top-account amount: `896130192559592` atomic units
- Raw top-account supply share:
  `0.9694652411735517224957652807`
- Context slots: supply `435725697`, largest accounts `435725699`, owners
  `435725701`; spread `4`
- Availability: `PARTIAL_CURRENT_SNAPSHOT`

The raw share is intentionally named **top-account concentration**. The twenty
accounts are SPL token accounts, not twenty proven independent economic
owners. The pilot did not identify pools, program accounts, treasuries, burn,
escrow or other exclusions.

## Unavailable claims

- Exclusion inventory: incomplete; unresolved `20/20`
- Adjusted concentration: `null`
- Deployer: `NOT_TESTED`
- Immediate or ultimate funder: `NOT_TESTED`
- Bundler/common ownership: `NOT_TESTED`
- Complete historical or launch-time snapshot: not established
- Strategy veto, promotion, execution and alpha: not established

Missing evidence remains missing. No vendor label or unsupported ownership
inference is promoted to fact.

## Evidence and reproducibility

- Runtime receipt SHA-256:
  `0cad0cb9fac95475691ab9f71fac01a29ae63b87a8910647e0a0afcc23d233f1`
- Portable fixture:
  `tests/fixtures/task11/entity_input_live_evidence_v1.json`
- Portable fixture SHA-256:
  `2c0e00c1aacb32a75cbe5807517e5e514751cec0271a540594147390e8fbf7b2`
- Tracked receipt:
  `docs/evidence/task11/entity_input_pilot_execution_receipt_v1.json`
- Tracked receipt SHA-256:
  `324c9ace8c49668864c274de19c09d42a7e794169f9a5ad619df8b47f3209ff4`

Offline replay:

```powershell
.\.venv\Scripts\python.exe -B .\scripts\run_task11_entity_input_probe.py --replay-run t11a3-20260728T102537Z
```

The command requires the ignored local raw run. The portable tracked fixture
contains aggregate values, timestamps, stable lineage IDs and hashes only. It
contains no provider body, owner-address inventory, credential value, headers
or machine-specific absolute path.

## Caps and side effects

The source run made exactly three Helius standard Solana RPC calls with zero
retries, `14090` received bytes, `51441` Parquet bytes, `55666` total durable
bytes, modeled `30` Helius credits and cash spend USD `0`.

Atom 4 made zero network/provider calls, used no credential or provider
credits, wrote no raw data, changed no dependency and performed no wallet,
signer or transaction action.

Validation:

- replay/evidence suite: `8/8 PASS`;
- related TASK-05/TASK-06/TASK-11 suite: `79/79 PASS`;
- full repository suite: `862/862 PASS`;
- Catalog transaction: `0.14.0 / 242 assets / 4 shards / 4 schemas /
  7 queries PASS`;
- generated navigation, secret scanning and file hygiene: `PASS`.

## Status and next boundary

`T11-A5` is a technical publication candidate. TASK-11 remains `IN_PROGRESS`;
`DONE` is not implied before repository merge/read-back and the separate
finish gate.

The next boundary is repository delivery: exact task branch/commit, non-force
push, draft PR and CI read-back. It must not reinterpret the raw share as
adjusted concentration, add provider calls or merge without the exact user
gate.
