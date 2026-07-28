---
contract_id: CONTRACT-T11-ENTITY-INPUT-OBSERVATION-001
contract_version: "1.0"
task_id: TASK-11
atom_id: T11-A2
status: FROZEN_OFFLINE_CONTRACT
as_of: 2026-07-28
provider_calls: 0
cash_spend_usd: 0
contains_secrets: false
---

# TASK-11 entity-input observation contract v1

## 1. Purpose and accepted claim

This contract freezes the smallest point-in-time-safe boundary needed to test
holder concentration for one mint without converting provider labels into
facts.

The first accepted claim is only:

`RAW_TOP_ACCOUNT_CONCENTRATION_FEASIBILITY`

It means that the project can preserve current supply, the twenty largest SPL
token accounts, their resolved owners, separate RPC context slots and local
availability timestamps well enough to replay the same raw concentration
calculation.

It does **not** establish:

- a complete holder distribution, holder graph, cluster or common ownership;
- deployer, ultimate funder, insider or bundler ground truth;
- a historical snapshot before the first retained observation;
- launch-universe coverage, alpha, veto logic, Fillable or NetReturn.

The selected future pilot mint is
`4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump`, inherited from accepted
TASK-10 quote-compatibility evidence. No endpoint is called by this atom.

## 2. Reuse boundary

TASK-11 applies `ADOPT -> WRAP -> FORK -> BUILD`:

- `ADOPT` official Solana standard RPC semantics and TASK-05
  `SCHEMA-T05-REL-ENTITY-INPUT-SNAPSHOTS-001`;
- `WRAP` TASK-06 raw envelopes and the TASK-08 lifecycle evidence boundary;
- `FORK` nothing;
- `BUILD` only the pure offline reducer in
  `src/solana_alpha_lab/entity_inputs.py`.

No dependency, general collector framework, graph database or vendor scoring
engine is added.

## 3. Evidence classes

Every fact or metric belongs to exactly one class:

| Class | Meaning | May alter raw value? | May exclude an account? |
|---|---|---:|---:|
| `RAW_ONCHAIN` | Provider-neutral RPC value with context slot and raw lineage | No | Yes, with explicit evidence |
| `DERIVED_ADJUSTED` | Deterministic result from raw facts plus a complete exclusion inventory | No | No |
| `VENDOR_LABEL` | Versioned provider assertion such as bundler, insider or developer | No | No |
| `PROJECT_INFERENCE` | Project rule with evidence reference, version and confidence | No | Only at medium/high confidence |

A vendor label can be retained for disagreement analysis. It cannot silently
change supply, balances, exclusions or an ownership claim.

## 4. Primary raw candidate

The primary future path is `HELIUS_STANDARD_SOLANA_RPC` using exactly:

1. `getTokenSupply`;
2. `getTokenLargestAccounts`;
3. `getMultipleAccounts`.

The first method supplies current mint supply. The second supplies at most
twenty largest token **accounts**, not wallet owners. The third resolves the
owner field of those accounts.

Each response remains a distinct TASK-06 raw event. The reducer retains:

- the three raw event IDs;
- provider and provider/runtime version;
- the context slot returned by each method;
- response observation and availability times;
- revision identity and deterministic content hash.

The candidate future cap is three calls, zero retries and zero cash spend. It
is planning data only and grants no provider, credential or raw-write
authority.

## 5. Point-in-time and availability

Standard current-state RPC responses expose a context slot but do not give the
block time at which the complete joined snapshot became available locally.
Therefore v1 uses:

`event_time = observed_at`

and requires the quality flag:

`EVENT_TIME_PROXY_OBSERVED_AT_NO_BLOCK_TIME`

The order is:

```text
event_time
<= observed_at
<= first_reliable_available_at
<= available_to_strategy_at
<= ingested_at
```

Supply, largest-account and owner-resolution context slots remain separate.
Different slots require `MULTI_SLOT_SNAPSHOT`; they must not be rewritten to a
fictional common slot.

Current RPC observations are `FORWARD_ONLY` until raw bytes have actually
been retained. They cannot be backdated to token launch or a prior signal.

## 6. Holder calculations

Raw concentration is:

```text
SUM(top account amount_atomic) / total supply_atomic
```

Rules:

- missing owner is not zero and not a synthetic wallet;
- missing balance is not zero;
- zero supply makes the share undefined (`null`), not `0`;
- token accounts are not treated as wallet owners until resolved;
- duplicate token accounts or top balances greater than supply fail closed;
- top-twenty concentration is not a complete-distribution HHI or Gini.

Adjusted concentration is:

```text
SUM(included top account amount_atomic)
/
(total supply_atomic - total evidence-backed excluded supply_atomic)
```

It is emitted only when:

- every top account has a resolved inclusion/exclusion disposition;
- the exclusion inventory is explicitly complete for the stated scope;
- that completeness claim has a durable evidence reference;
- total excluded supply is known and reconciles with excluded top accounts;
- each exclusion has a reason, evidence reference, evidence class and
  medium/high confidence.

Otherwise adjusted concentration is `null` with
`ADJUSTED_CONCENTRATION_UNAVAILABLE`. Raw concentration remains unchanged.

## 7. Deployer, funder and bundler boundary

- a deployer claim requires a raw deployer fact or an explicit project
  inference with source and confidence;
- an immediate funder is not an ultimate funder;
- unavailable history is `NOT_TESTABLE`;
- provider failure is `PROVIDER_ERROR`, never empty or zero;
- bundler/insider/developer labels remain `VENDOR_LABEL`;
- ownership without evidence is forbidden.

The first pilot may finish with an explicit deployer/funder/bundler blocker.
That is preferable to fabricating a complete entity graph.

## 8. TASK-05 projection

The reducer projects five `EntityInputSnapshot` metrics:

1. `raw_top_accounts_amount_atomic`;
2. `raw_top_accounts_supply_share`;
3. `adjusted_top_accounts_supply_share`;
4. `unresolved_owner_account_count`;
5. `context_slot_spread`.

`quality_flags` carries the evidence class and all partial/undefined
conditions. `source`, `source_version`, `revision_number`, raw lineage and
content SHA-256 are mandatory. A null metric row is retained when the adjusted
value is unavailable; null is not deleted or converted to zero.

## 9. Offline authority and security

Atom `T11-A2` permits writes only to:

- `docs/contracts/entity_input_observation_contract_v1.md`;
- `src/solana_alpha_lab/entity_inputs.py`;
- `tests/fixtures/task11/entity_input_observation_contract_v1.json`;
- `tests/test_task11_entity_inputs.py`.

It permits zero:

- network or provider/API/RPC/WSS calls;
- credential reads or use;
- cash or provider-credit spend;
- dependency changes;
- wallet, signer, transaction build, simulation or send actions;
- commit or push.

Fixtures are synthetic. Durable metadata rejects sensitive-key fields and
machine-specific absolute paths.

## 10. Validation and next boundary

Atom 2 passes only if targeted tests prove:

- exact frozen fixture identity and managed write set;
- raw and adjusted metrics remain separate;
- incomplete exclusions yield adjusted `null`;
- vendor labels cannot drive exclusions;
- missing owner and zero supply remain distinct;
- timestamps and multi-slot context fail closed;
- projection validates against TASK-05 `EntityInputSnapshot`;
- offline authority rejects any external action claim.

After PASS, stop before provider access. A future live pilot requires a
separate exact authority envelope covering provider, credential use, calls,
credits, bytes, raw-write location, duration and rollback.
