# TASK-24 frozen entity graph and false-positive contract v1

## 1. Purpose and status

- Task: `TASK-24 Entity graph v1`.
- Atom: `T24-A2_FROZEN_ENTITY_GRAPH_AND_FALSE_POSITIVE_CONTRACT_V1`.
- Status after validation: `VALIDATED_CONTRACT_ONLY`.
- Route owner: `LOCAL_WORK_PRIMARY`; execution route: `LOCAL_WORK_CODEX`.
- Accepted base commit: `31c01640499be6b7e86a2fe638d9217c202861cc`.
- Accepted base tree: `6677878eb2b8195018ab217c6a9a429de5726563`.

This atom freezes how linked-wallet evidence may be represented and audited before any
TASK-24 entity values are read. It does not build a graph, identify an entity, change a
holder exclusion, or establish an alpha claim.

The owner decision eventually unlocked by TASK-24 is narrow: whether entity evidence is
reliable enough to improve an adjusted concentration or eligibility read without turning
an observed relation into an unsupported ownership claim. Allowed terminal decisions are:

- `ENTITY_EVIDENCE_READY_WITH_LIMITATIONS`;
- `EXTEND_EVIDENCE`;
- `REDESIGN_DATA`;
- `STOP_NO_RELIABLE_ENTITY_SIGNAL`.

## 2. Governing interpretation

The graph is a versioned evidence read model, not an ownership truth store. A node is an
observed or derived subject. An edge is a claim with provenance, availability time and a
revision. An entity candidate is a reversible hypothesis over nodes. No wallet or account
is destructively merged, and raw evidence remains queryable after every inference.

TASK-11 remains authoritative for evidence classes and holder-concentration semantics:

- `RAW_ONCHAIN`: direct on-chain observation;
- `DERIVED_ADJUSTED`: deterministic transformation of declared inputs;
- `VENDOR_LABEL`: attributed third-party claim;
- `PROJECT_INFERENCE`: project-owned hypothesis.

Evidence classes never silently promote. A vendor label cannot become raw evidence, and a
confidence label cannot repair missing provenance.

## 3. Frozen graph vocabulary

### 3.1 Node types

The only node types in v1 are:

- `TOKEN_MINT`;
- `TOKEN_ACCOUNT`;
- `WALLET`;
- `PROGRAM_OR_POOL`;
- `TRANSACTION`;
- `ENTITY_CANDIDATE`.

Every node must carry `node_id`, `node_type`, `business_key`, all five PIT timestamps,
`source`, `source_version`, `evidence_class`, `revision_number`, `revision_of`,
`content_sha256` and `quality_flags`. `ENTITY_CANDIDATE` additionally carries the exact
rule version and member-edge references that produced it.

### 3.2 Edge types

The only edge types in v1 are:

| Edge | Source -> target | Evidence | Meaning |
|---|---|---|---|
| `RAW_TOKEN_ACCOUNT_FOR_MINT` | `TOKEN_ACCOUNT -> TOKEN_MINT` | `RAW_ONCHAIN` | The account is a token account for the mint in the cited observation. |
| `RAW_TOKEN_ACCOUNT_OWNER` | `TOKEN_ACCOUNT -> WALLET` | `RAW_ONCHAIN` | The account owner field resolved to the wallet at the cited slot. |
| `RAW_MINT_CREATED_BY_WALLET` | `TOKEN_MINT -> WALLET` | `RAW_ONCHAIN` | Exact creation instruction/transaction supports the immediate creator role. |
| `RAW_IMMEDIATE_FUNDER` | `WALLET -> WALLET` | `RAW_ONCHAIN` | Exact cited transfer directly funded the target wallet. |
| `RAW_COMMON_TRANSACTION_SIGNER` | `WALLET -> TRANSACTION` | `RAW_ONCHAIN` | The wallet signed the exact transaction; fee-payer/relayer roles stay explicit. |
| `RAW_SAME_BUNDLE_MEMBERSHIP` | `TRANSACTION -> ENTITY_CANDIDATE` | `RAW_ONCHAIN` | Exact authoritative bundle identifier links the cited transactions. |
| `DERIVED_SHARED_IMMEDIATE_FUNDER` | `WALLET -> WALLET` | `DERIVED_ADJUSTED` | Two wallets share the same cited immediate funder under the frozen rule. |
| `VENDOR_BUNDLE_LABEL` | `WALLET -> ENTITY_CANDIDATE` | `VENDOR_LABEL` | Attributed vendor claim; it cannot merge or exclude a wallet. |
| `PROJECT_ENTITY_MEMBERSHIP_CANDIDATE` | `WALLET -> ENTITY_CANDIDATE` | `PROJECT_INFERENCE` | Reversible membership hypothesis supported by declared edges. |

An edge must carry `edge_id`, source and target identifiers/types, `edge_type`,
`evidence_class`, `confidence_class`, `rule_version`, `supporting_raw_event_ids`,
`supporting_edge_ids`, all five PIT timestamps, `source`, `source_version`,
`revision_number`, `revision_of`, `content_sha256`, `quality_flags` and an optional
`conflict_set_id`.

`RAW_IMMEDIATE_FUNDER` never means ultimate source of funds. `RAW_MINT_CREATED_BY_WALLET`
never proves beneficial ownership or later control. A common signer may be a fee payer,
relayer or service. Missing deployer, funder or bundle evidence is `NOT_TESTABLE`, never
`false`, `zero` or an empty graph.

## 4. Identity, candidate construction and confidence

Entity candidates are append-only, versioned and reversible. Membership may be proposed
only from explicit supporting edges; it never rewrites their endpoints. A candidate must
retain competing candidates and conflicts.

Confidence is ordinal and claim-specific:

- `DIRECT`: the narrow raw edge is directly supported by an exact event;
- `CORROBORATED`: at least two independent compatible raw edge families support a project
  inference and no unresolved conflict contradicts it;
- `INFERRED`: a deterministic project rule supports the claim but corroboration is absent;
- `VENDOR_ONLY`: only an attributed vendor label supports the claim;
- `UNKNOWN`: evidence is absent, contradictory or not testable.

Only a raw edge can be `DIRECT`. `CORROBORATED` requires distinct evidence families, not
duplicate providers over the same event. `VENDOR_ONLY` and `UNKNOWN` cannot cause an entity
merge, holder exclusion, eligibility veto, trade decision or confidence promotion.

## 5. Point-in-time and revision contract

Every node, edge, candidate and audit judgment carries:

- `event_at`: when the underlying event occurred, or an explicit event-time proxy flag;
- `observed_at`: when the source observed it;
- `first_reliable_available_at`: earliest defensible availability;
- `available_to_strategy_at`: when the project could have consumed it;
- `ingested_at`: when persistence completed.

For a derived edge or candidate, `first_reliable_available_at` and
`available_to_strategy_at` cannot precede the maximum corresponding timestamp of every
required input. Future labels, strategy outcomes, PnL and R3 data are forbidden inputs.

Corrections append a new revision. They do not overwrite raw observations. Disagreement is
retained using `conflict_set_id`; a consumer must select an explicit revision policy.

## 6. Holder exclusions and adjusted concentration

Raw and adjusted holder concentration are separate durable fields. Raw concentration is
never overwritten. An adjusted value may be produced only when the exclusion inventory is
complete for the declared scope and every excluded account has medium/high direct or
corroborated evidence under the TASK-11 contract.

The v1 exclusion roles are `PROGRAM_OR_POOL`, `BURN`, `LOCKER_OR_ESCROW`, `TREASURY`,
`MARKET_MAKER_OR_EXCHANGE` and `UNRESOLVED`. `UNRESOLVED` is not excluded. A vendor-only
label, common funder, common signer, bundle label or entity candidate alone is insufficient
to exclude an account. The output must retain the inventory, evidence references, rule
version, raw metric, adjusted metric and unresolved count.

## 7. Frozen false-positive audit

The audit unit is one predicted membership claim (`wallet_id`, `candidate_id`,
`membership_edge_id`, `revision_number`), not a wallet treated as an independent sample.
Selection is frozen before graph values and before manual labels are opened.

The deterministic selection key is SHA-256 of
`TASK24_FALSE_POSITIVE_AUDIT_V1|stratum|candidate_id|membership_edge_id|revision_number`.
Within each stratum the lowest hashes are selected. The target sample is 24 claims:

- 8 `CORROBORATED` predicted-positive claims;
- 8 `INFERRED` or `VENDOR_ONLY` predicted-positive claims;
- 8 deterministic negative controls or deliberately ambiguous cases.

If a stratum has fewer than its target, all eligible claims are used without substitution
from a different stratum. Fewer than 12 manually reviewed predicted-positive claims makes
the false-positive gate `NOT_TESTABLE`.

Reviewers see only point-in-time supporting evidence and role metadata. Strategy identity,
entry/exit decisions, outcome, PnL, NetReturn, R3 membership and future vendor labels are
blinded. Allowed judgments are `SUPPORTED`, `REJECTED_FALSE_POSITIVE`, `AMBIGUOUS` and
`NOT_TESTABLE`, each with reviewer, timestamp and evidence references.

The gate passes only when:

- all reviewed claims are traceable to frozen inputs;
- critical violations are zero: destructive merge, hidden evidence promotion, forbidden
  future/outcome input, or exclusion from vendor-only/inferred evidence;
- at least 12 predicted-positive claims are determinate;
- at most one determinate predicted-positive claim is `REJECTED_FALSE_POSITIVE`;
- the ambiguous share among reviewed predicted-positive claims is at most 0.25;
- no systematic false-positive mechanism remains unresolved.

The receipt reports counts, point estimates and the Wilson 95% interval. No threshold,
rule, stratum or candidate may be tuned on this validation sample. A change creates a new
rule version and a new sample epoch.

## 8. Frozen data-feasibility boundary

The tracked TASK-11 fixture is usable for schema, provenance, null and limitation tests.
It contains zero owner addresses and cannot construct or validate a TASK-24 graph. The
logical raw TASK-11 runtime partitions named by the receipt are outside Git and were not
present in the current workspace at Entry Gate. No value is fabricated or reconstructed
from hashes.

Before A3 may read entity values, it must produce a pre-read manifest with exact local
paths, sizes, SHA-256 hashes, scope, retention, provenance, permitted fields and a no-R3/
no-outcome assertion. If exact admissible inputs are unavailable, A3 must return
`REDESIGN_DATA` or `STOP_NO_RELIABLE_ENTITY_SIGNAL`. Provider/RPC/WSS calls require a
separate explicit boundary and are not authorized by this atom.

## 9. Outputs and non-claims

Future v1 outputs are declarative tables or files: `entity_nodes_v1`, `entity_edges_v1`,
`entity_candidates_v1`, `entity_adjusted_concentration_v1` and
`entity_false_positive_audit_v1`. A graph database is not required.

This atom establishes none of the following: economic or beneficial ownership; insider,
deployer, funder or bundler ground truth; complete holder distribution; adjusted
concentration; toxicity or strategy veto; alpha, causality, generalization, execution,
PnL, NetReturn or owner cashflow; any R3/outcome access; canonical TASK-24 `DONE`.

## 10. Authority and next boundary

A2 authorizes only its declared local four-file write set and offline validation. It
authorizes zero provider/API/RPC/WSS calls, credential use, dependency changes, Catalog or
registry mutation, R3/outcome access, wallet/signer/transaction action, spend, deploy,
release, commit, push, PR or merge.

The next candidate atom is
`T24-A3_DETERMINISTIC_ENTITY_EVIDENCE_FEASIBILITY_AND_PROJECTION_V1`. It is conditional on
an exact pre-read manifest and is not authorized by acceptance of A2.
