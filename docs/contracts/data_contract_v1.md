# Data contract v1 — TASK-05 Atom 2 candidate

Status: local uncommitted candidate. This document freezes field semantics for
the DuckDB v1 projection in `schemas/schema_v1.sql`; it does not claim that any
later writer, collector, migration runner, provider adapter, execution engine or
live dataset exists.

## 1. System model and truth ownership

Immutable, redacted raw bytes and future immutable Parquet pieces own durable
data truth. Dataset, partition and migration manifests own inventory, schema,
availability and replay identity. DuckDB is a rebuildable, single-writer
projection over those truths. TASK-06 is the first writer for raw envelopes and
dataset/partition manifests. Atom 3 will implement migration files and the thin
ledger runner; this atom defines only the target relation.

All rows are append-only. Corrections are new rows with a new surrogate ID,
idempotency identity, content hash and explicit `revision_of`; no writer may
update or delete prior evidence. A business key groups claims but is never a
storage primary key. Provider disagreement is preserved because source identity
is part of each claim, while idempotency prevents replaying the same claim.

`TIMESTAMPTZ` means a timezone-aware instant normalized to UTC at every external
boundary. `available_to_strategy_at` is the decision-eligibility gate.
`first_reliable_available_at` records the earliest *reliably known*
availability; import or backfill must not move it backward. Event time alone
never authorizes a point-in-time read.

Missing or unknown values are SQL `NULL` unless a relation defines an explicit
state. `NULL`, zero, false, empty text and an empty collection are distinct.
There are no semantic numeric or boolean defaults. Atomic token and lamport
amounts use `HUGEINT`/`UBIGINT`, never binary floating point. Token amounts name
their mint and decimals. Decimal estimates use `DECIMAL` plus a unit and, where
monetary, a currency or mint.

Conditional state-coherence constraints are fail-closed: their complete SQL
predicate must evaluate to `TRUE`. SQL `UNKNOWN`, including an unexpected
`NULL` in a state-required field, is rejected rather than treated as valid.

All v1 relations are non-secret analytical records. Raw bodies must already be
redacted before insertion. Public chain identifiers can still be sensitive when
joined into behavior profiles, so entity and execution relations are
restricted to authorized research and operations consumers. No relation stores
signer material, recovery data, credentials, private endpoints or request
headers.

## 2. Shared field dictionary

The following definitions apply wherever the named field occurs.

| Field | Definition, nullability and unit |
|---|---|
| `*_id` primary key | Immutable, non-empty surrogate storage identity (`VARCHAR`). Never derived only from a mutable business key. |
| `idempotency_key` | Stable request/content identity for one exact row claim; non-null and unique within its relation. A legitimate revision gets a new key. |
| `business_key` | Non-null grouping identity for the real-world entity/event/metric. Duplicate values are intentional across revisions and providers. |
| `event_time` | UTC time of the represented event or state. Nullable only in the raw envelope when the source supplies no event time. |
| `observed_at` | UTC time the source or collector observed the claim; non-null. |
| `available_to_strategy_at` | UTC eligibility gate; the row must not influence an earlier decision. |
| `ingested_at` | UTC time bytes entered the project boundary; non-null. It does not retroactively grant availability. |
| `first_reliable_available_at` | Earliest UTC availability supported by reliable evidence; non-null and never backdated. |
| `source`, `source_version` | Truth-producing system and exact contract/adapter version. Synthetic fixtures use explicit synthetic identities. |
| `schema_version` | Version of the canonical row contract, not the provider payload version. |
| `revision_number` | Positive source-scoped revision ordinal. It is not globally unique. |
| `revision_of` | Nullable prior surrogate ID. It must not self-reference; a correction links to an already retained row. |
| `raw_event_id` | Nullable or required link to the redacted raw envelope as specified per relation. |
| `content_sha256`, `*_sha256`, `*_fingerprint` | Lowercase SHA-256 identity represented by 64 hexadecimal characters. Atom 2 checks length; writers must validate hexadecimal form before insertion. |
| `quality_flags` | Nullable stable delimited flag set. Null means no flags were emitted, not that quality was proven perfect. |
| `*_atomic`, `*_lamports` | Exact integer atomic units. Requested/input/output/reserve/fee amounts are non-negative; signed deltas are allowed only in a future field explicitly named as a delta. |
| `*_decimals` | Mint decimal metadata, integer 0..30. It is provenance for display conversion, not a scaling instruction that changes stored atomic identity. |

Unless a relation says otherwise, retention is durable append-only in Parquet
and rebuildable in DuckDB. Known global limitations: DuckDB constraints cannot
forbid privileged `UPDATE`/`DELETE`, cannot prove that a hash matches bytes and
cannot establish external clock accuracy. TASK-06/12 writer policy and receipts
must enforce those boundaries.

## 3. Source and observation relations

### `raw_api_events`

Purpose and truth owner: append-only redacted request/response or program-event
envelope; the retained redacted bytes and their manifest own truth. First writer:
TASK-06. Consumers: TASK-07 provider smoke, TASK-08 lifecycle discovery,
TASK-09 pool/trade snapshots, TASK-10 quote logger, TASK-12 health, TASK-13
pilot audit, TASK-18/19 quality/replay and TASK-20..24 dataset diagnostics.

Identity: `raw_event_id` is the surrogate ID; `idempotency_key` prevents exact
replay; `request_hash` groups request content without exposing it. A response
revision uses `revision_number`/`revision_of` and a new content identity.
Retention: durable append-only, not rebuildable from canonical rows. Security:
body must be redacted under `redaction_version`; raw unredacted payloads are
forbidden. PIT: only rows whose availability fields pass the requested as-of
may feed downstream canonicalization.

| Fields | Definition |
|---|---|
| `raw_event_id`, `idempotency_key`, shared timestamps/source/version/revision fields | Shared dictionary; `provider_version` and `protocol_version` may be null when not applicable. |
| `endpoint_or_method` | Non-secret stable endpoint, RPC method or program-event kind; never a private URL. |
| `request_hash` | SHA-256 of canonical redacted request identity. |
| `response_status`, `error_class` | `SUCCESS` requires null error; `HTTP_ERROR`, `PROVIDER_ERROR`, `TIMEOUT`, `INVALID_RESPONSE` require a typed error. Failure is a retained row. |
| `redacted_body` | Non-null already-redacted bytes (`BLOB`); an error body may be empty bytes but is not null. |
| `content_sha256` | SHA-256 of exactly `redacted_body`. |
| `redaction_version` | Version of the deterministic redaction rules applied before storage. |

### `canonical_observations`

Purpose and truth owner: generic revision-aware canonical claims used when a
family-specific relation is unnecessary; immutable Parquet plus lineage owns
truth. First writer: TASK-06 for normalized raw records, extended by TASK-08..11.
Consumers: TASK-13, TASK-18/19, TASK-20..24, TASK-28..35 and TASK-36..40.

Identity: surrogate `observation_id`; exact-claim `idempotency_key`; repeated
`business_key` is required for revisions and provider disagreement. PIT:
`decision_safe_observations(as_of)` is the mandatory safe read surface.
Retention: durable/rebuildable. Security: inherited source classification.
Limitation: this generic relation supports one decimal estimate and one atomic
value; rich typed families remain separate.

| Fields | Definition |
|---|---|
| Shared identity/time/source/revision/hash/quality fields | As defined above; `event_time` is required. `raw_event_id` is nullable for derived/imported claims with manifest lineage. |
| `entity_type`, `entity_id`, `observation_type` | Stable subject kind, subject identity and metric/event kind. |
| `value_decimal` | Nullable decimal estimate. Null means the source value is missing/unknown, never zero. |
| `value_atomic`, `amount_mint`, `amount_decimals` | Optional exact token amount. They are all absent together or amount plus mint/decimals are present. |
| `unit` | Nullable only when both values are null or the observation type itself fixes the unit. Writers should emit it whenever a value exists. |

### `token_lifecycle_events`

Purpose/truth owner: token creation, activation and migration claims sourced from
raw program/provider evidence. First writer: TASK-08. Consumers: TASK-09,
TASK-13, TASK-18/19, TASK-20..24 and TASK-28..40. Identity, revision, PIT,
retention and security follow the shared contract.

| Fields | Definition |
|---|---|
| `lifecycle_event_id`, `idempotency_key`, `business_key`, shared evidence fields | Immutable claim identity and provenance. |
| `token_mint` | Token mint named by the lifecycle claim. |
| `lifecycle_state` | `DISCOVERED`, `CREATED`, `ACTIVE`, `MIGRATION_STARTED`, `MIGRATED`, `INACTIVE` or explicit `UNKNOWN`. |
| `related_pool_id` | Nullable pool involved at this state. |
| `migrated_to_program`, `migrated_to_pool_id` | Both required for `MIGRATED`; otherwise nullable. |

### `pool_state_snapshots`

Purpose/truth owner: revision-aware pool reserve/state input; provider/program
raw evidence plus immutable canonical dataset owns truth. First writer: TASK-09.
Consumers: TASK-13, TASK-18/19, TASK-20..24, TASK-25/26, TASK-28..40 and
TASK-43..47. PIT, identity, retention and security use the shared rules.

| Fields | Definition |
|---|---|
| `pool_snapshot_id`, `idempotency_key`, `business_key`, shared evidence fields | Snapshot identity, replay protection and provenance. |
| `pool_id` | Canonical pool identity. |
| `base_mint`, `quote_mint` | Distinct reserve mints. |
| `base_decimals`, `quote_decimals` | Required mint decimal provenance. |
| `base_reserve_atomic`, `quote_reserve_atomic` | Nullable non-negative reserves. Null is unavailable/unknown; zero is an observed empty reserve. |
| `context_slot` | Nullable non-negative Solana slot supplied by evidence. |

### `trade_orderflow_inputs`

Purpose/truth owner: exact observed trades/order-flow inputs, not simulated
fills. First writer: TASK-09. Consumers: TASK-13, TASK-18/19, TASK-20..26,
TASK-28..40 and TASK-43..47. Durable/rebuildable; provider disagreement and
revisions coexist under shared identity/PIT rules.

| Fields | Definition |
|---|---|
| `trade_input_id`, `idempotency_key`, `business_key`, shared evidence fields | Immutable evidence identity and lineage. |
| `pool_id`, `side` | Pool and explicit `BUY`/`SELL` from the canonical base-token perspective. |
| `input_mint`, `input_amount_atomic`, `input_decimals` | Non-negative exact input amount and provenance. |
| `output_mint`, `output_amount_atomic`, `output_decimals` | Non-negative exact output amount and provenance; mint differs from input. |
| `trader_entity_id`, `transaction_signature`, `context_slot` | Nullable public-chain correlation evidence. Null means unavailable, not anonymous-by-proof. |

### `entity_input_snapshots`

Purpose/truth owner: holder, deployer, wallet or cluster metric inputs. First
writer: TASK-11. Consumers: TASK-13, TASK-18/19, TASK-20..24, TASK-28..40 and
TASK-43..47. These rows are behaviorally sensitive; consumers must minimize and
aggregate identities where possible. PIT/revision/retention use shared rules.

| Fields | Definition |
|---|---|
| `entity_snapshot_id`, `idempotency_key`, `business_key`, shared evidence fields | Immutable snapshot claim. |
| `entity_type`, `entity_id` | `HOLDER`, `DEPLOYER`, `WALLET`, `CLUSTER` or explicit `UNKNOWN`, plus its canonical identity. |
| `token_mint` | Nullable mint scope. |
| `metric_name` | Stable metric identity. |
| `metric_value_decimal` | Nullable decimal estimate; null never means zero. |
| `metric_value_atomic`, `amount_decimals`, `unit` | Optional atomic or unit-bearing metric. An atomic value requires both `token_mint` and `amount_decimals`; null remains distinct from zero. |

## 4. Derived research and decision relations

### `feature_observations`

Purpose/truth owner: PIT-safe derived feature value with immutable dataset
lineage. First writer: TASK-28..35. Consumers: TASK-36..40 and TASK-43..47.
Identity/revisions follow the shared rules; durable feature Parquet owns truth
and DuckDB is rebuildable. A feature row is eligible only after both availability
timestamps and may never use inputs unavailable at its own as-of.

| Fields | Definition |
|---|---|
| `feature_observation_id`, `idempotency_key`, `business_key`, shared time/source/revision/hash fields | Immutable derived claim. |
| `entity_type`, `entity_id` | Subject of the feature. |
| `feature_name`, `feature_version` | Stable definition identity and exact implementation/config version. |
| `value_decimal`, `unit` | Nullable feature value and unit. Null retains missingness. |
| `lineage_dataset_id`, `lineage_dataset_version`, `lineage_fingerprint` | Required immutable input dataset identity and deterministic root. |

### `regime_observations`

Purpose/truth owner: revision-aware market/regime classification derived from
PIT-safe inputs. First writer: TASK-28..35. Consumers: TASK-36..40 and
TASK-43..47. Retention, revisions and PIT follow feature observations.

| Fields | Definition |
|---|---|
| `regime_observation_id`, `idempotency_key`, `business_key`, shared evidence fields | Immutable regime claim. |
| `regime_name`, `regime_version`, `regime_state` | Classifier identity/version and explicit state label. |
| `confidence_decimal` | Nullable calibrated value in [0,1]; null means uncalibrated/unknown. |
| `lineage_fingerprint` | Required deterministic root of the PIT-safe inputs/config. |

### `signal_decision_events`

Purpose/truth owner: immutable strategy decision evidence, never a command to a
router or signer. First writer: TASK-36..40. Consumers: TASK-43..47, TASK-25/26
modeling and TASK-13/19 audit/replay. Retention is durable; revisions may correct
metadata but cannot erase the original decision.

| Fields | Definition |
|---|---|
| `signal_decision_id`, `idempotency_key`, `business_key`, shared evidence fields | Immutable decision identity and provenance. |
| `strategy_id`, `strategy_version`, `entity_id` | Strategy definition/version and decision subject. |
| `decision`, `side` | `ENTER`/`EXIT` require `BUY`/`SELL`; `HOLD`/`REJECT` require null side. |
| `decision_as_of` | UTC decision cutoff. The row's availability must be no later than this time. |
| `feature_set_fingerprint` | Required deterministic identity of exactly the eligible feature set. |

## 5. Quote, execution and outcome relations

### `quote_attempts`

Purpose/truth owner: every buy/sell quote request outcome, including `NO_ROUTE`
and typed errors. First writer: TASK-10. Consumers: TASK-13, TASK-18/19,
TASK-25/26, TASK-36..40 and TASK-43..47. Quote status is not execution status.
Rows are durable/rebuildable from raw plus manifests; raw link is mandatory.

| Fields | Definition |
|---|---|
| `quote_attempt_id`, `idempotency_key`, `business_key`, `request_hash` | Surrogate row ID, exact replay identity, stable request/attempt grouping identity and canonical request SHA-256. |
| `provider`, `provider_version`, `side` | Provider contract identity/version and explicit `BUY`/`SELL`. |
| `input_mint`, `input_requested_atomic`, `input_decimals` | Required non-negative request amount and provenance. |
| `output_mint`, `output_quoted_atomic`, `output_decimals` | Output identity; quoted amount exists only for `QUOTE_AVAILABLE`. |
| `route_id`, `route_count` | Executable route evidence. Available quotes require a route and positive count; `NO_ROUTE` requires null route and count zero. |
| `context_slot` | Nullable provider context slot. |
| `requested_at`, `response_at`, `available_to_strategy_at`, `ingested_at`, `first_reliable_available_at` | UTC request lifecycle. `response_at` is null only where no response occurred. |
| `quote_age_ms`, `provider_latency_ms` | Nullable non-negative integer milliseconds. Null means not measurable. |
| `provider_fee_atomic`, `platform_fee_atomic`, `fee_mint`, `included_in_output_amount` | Separate fee attribution. If a fee exists, mint and inclusion/non-overlap semantics are required. |
| `status`, `error_class` | `QUOTE_AVAILABLE`, `NO_ROUTE`, or `PROVIDER_ERROR`/`INVALID_RESPONSE`/`TIMEOUT`. Error statuses require typed error. |
| `revision_number`, `revision_of` | Explicit response revision chain. A provider correction is a new row; it never overwrites the prior quote evidence. |
| `raw_event_id`, `response_content_sha256`, `schema_version`, `quality_flags` | Required raw/content lineage and contract metadata. |

Known limitation: route details remain in redacted raw evidence; v1 does not
normalize provider-specific route legs.

### `execution_attempts`

Purpose/truth owner: immutable local and on-chain reconciliation state for one
atomic transaction attempt. First writer: TASK-43..47; TASK-25/26 may write only
synthetic modeled rows in separately identified datasets. Consumers: TASK-13,
TASK-19, TASK-25/26 and TASK-43..47. This relation does not sign, send or infer
landing probability.

| Fields | Definition |
|---|---|
| `execution_attempt_id`, `idempotency_key`, `business_key` | Immutable row ID, exact request-content identity and stable real attempt identity shared by reconciliation revisions. |
| `quote_attempt_id`, `signal_decision_id` | Nullable lineage to the quote and decision; null must be justified by source/version metadata outside v1. |
| `side`, input/output mint/decimals, `requested_input_atomic` | Explicit direction and exact non-negative requested amount. |
| `submitted_at`, `terminal_at`, shared observation/availability timestamps | UTC submission (null before send), terminal classification, observation, strategy eligibility, ingestion and first reliable availability. |
| `terminal_state` | Exactly `REJECTED_BEFORE_SEND`, `DROPPED_OR_EXPIRED_NOT_PROCESSED`, `LANDED_FAILED`, `LANDED_SUCCESS`, or `UNKNOWN_REQUIRES_RECONCILIATION`. |
| `processed_on_chain`, `transaction_signature` | False/no signature before send; false/signature for dropped; true/signature for landed; null/signature for unresolved unknown. |
| `realized_input_atomic`, `realized_output_atomic` | Both present only for atomic `LANDED_SUCCESS`; no partial-fill state exists. |
| `actual_network_fee_lamports`, `actual_relay_tip_lamports`, `actual_ata_rent_lamports`, `fee_payer_mint` | Separately reconciled actual costs. Unprocessed and unknown rows keep them null; landed rows may carry actual costs, with network fee required in v1. |
| `error_class` | Nullable typed failure/rejection reason; must be null for landed success. |
| `reconciliation_reference` | Required only for `UNKNOWN_REQUIRES_RECONCILIATION`; it must not turn unknown into success, failure or zero cost. |
| `source`, `source_version`, `revision_number`, `revision_of`, `raw_event_id`, `quality_flags` | Reconciliation source, explicit append-only revision chain, optional raw evidence and quality metadata. |
| `content_sha256`, `schema_version` | Deterministic attempt-state content identity and contract version. |

Security: signatures are public correlation identifiers; no transaction bytes,
signer or wallet secrets are stored. Limitation: v1 treats execution as one
atomic transaction and cannot model multi-transaction plans.

### `strategy_outcomes`

Purpose/truth owner: typed strategy evaluation and unresolved-inventory state.
First writer: TASK-25/26 for models and TASK-43..47 for observed canary/live
evidence. Consumers: TASK-25/26, TASK-36..40 and TASK-43..47. Durable outcome
datasets own truth; rows are never deleted when exit evidence is absent.

| Fields | Definition |
|---|---|
| `strategy_outcome_id`, `idempotency_key`, `business_key`, strategy/version/position IDs | Immutable row identity, replay identity, stable outcome grouping key and model/position scope. |
| `outcome_type` | Exactly `TouchReturn`, `FillableReturn`, `RealizedVWAPReturn`, `NetReturn` or `PathRisk`; types remain separate rows. |
| `outcome_value_decimal`, `outcome_unit` | Nullable result and unit. Null preserves unresolved measurement. |
| `measured_as_of`, availability/ingestion timestamps | UTC evaluation cutoff and evidence availability. Outcome evidence cannot be eligible before its cutoff: `measured_as_of <= available_to_strategy_at`. |
| `inventory_state` | `FLAT`, `OPEN`, `UNRESOLVED_REQUIRES_RECOVERY` or `RECOVERED`. |
| `remaining_inventory_atomic`, mint/decimals | Zero with null mint metadata only for `FLAT`; positive and fully identified otherwise. |
| `last_executable_liquidation_quote_id` | Nullable link to the last actual executable liquidation evidence; a `NO_ROUTE` quote is not executable evidence. |
| `recovery_lower_bound_decimal`, `recovery_upper_bound_decimal`, `recovery_unit`, `recovery_currency_or_mint` | Required coherent lower/upper bounds for unresolved inventory; valuation is not silently forced to zero. |
| `failed_exit_state` | For unresolved inventory: `NO_ROUTE`, `EXIT_FAILED` or `UNKNOWN_REQUIRES_RECONCILIATION`. |
| source/version/schema/hash/quality fields, `revision_number`, `revision_of` | Outcome model or observed-evidence provenance and explicit append-only correction chain. |

Known limitation: v1 stores recovery bounds but does not prescribe their
estimator or mark-to-market policy.

## 6. Manifest relations

### `dataset_manifests`

Purpose/truth owner: immutable dataset version and deterministic root. First
writer: TASK-06. Consumers: TASK-12/13, TASK-18/19, TASK-20..40 and
TASK-43..47. The manifest is durable source truth; DuckDB is rebuildable.

| Fields | Definition |
|---|---|
| `dataset_manifest_id` | Immutable surrogate manifest row ID. |
| `dataset_id`, `dataset_version` | Stable dataset identity and immutable version; pair is unique. |
| `schema_id`, `schema_sha256` | External schema identity and exact content hash. |
| `dataset_fingerprint` | Deterministic root over ordered partition identities/content. |
| `generation_task_id`, `generation_run_id` | Producing task and idempotent run identity. |
| `validation_receipt_sha256` | Exact receipt proving the generated version passed its gate. |
| `first_reliable_available_at`, `created_at` | UTC evidence availability and creation; availability cannot predate creation. |
| `content_sha256` | Hash of the canonical manifest representation. |

Security: logical metadata only; machine paths and private endpoints are
forbidden. Limitation: deterministic root algorithm is finalized by TASK-06.

### `partition_manifests`

Purpose/truth owner: immutable file/partition inventory within a dataset
manifest. First writer and consumers match `dataset_manifests`. Identity:
surrogate `partition_manifest_id`; `(dataset_manifest_id, partition_id)` and
logical location are unique. Durable, not inferred from DuckDB.

| Fields | Definition |
|---|---|
| identity and dataset link fields | Immutable partition identity and parent dataset manifest. |
| `logical_location` | Repository-independent dataset-relative logical name, never an absolute machine path or private URL. |
| `file_sha256`, `content_sha256` | Exact file bytes and canonical logical-content hashes. |
| `row_count` | Non-negative exact row count. |
| min/max event and availability timestamps | Nullable pairs; each pair is both null or ordered UTC bounds. |
| `first_reliable_available_at`, `created_at` | UTC partition evidence availability and creation; no backdating. |

### `migration_manifests`

Purpose/truth owner: immutable ordered migration declaration/application
receipt. Atom 3 is first writer. Consumers: TASK-06, TASK-12/13, TASK-18/19 and
all rebuilds through TASK-47. The repository migration file plus its hash and
application receipt own truth; DuckDB row is a rebuildable ledger projection.

| Fields | Definition |
|---|---|
| `migration_manifest_id`, `migration_id`, `migration_order` | Surrogate row ID, stable migration ID and unique positive total order. |
| `migration_kind` | `DDL`, `DATA_BACKFILL`, `REBUILD` or `REPAIR`. |
| `schema_version`, `content_sha256` | Target contract version and exact immutable migration bytes hash. |
| `supersedes_migration_id` | Nullable prior migration identity; cannot self-reference. Supersession does not erase history. |
| `application_state` | `DECLARED`, `APPLIED` or `FAILED`. |
| `applied_at`, `application_receipt_sha256` | Both null while declared; both required for applied/failed attempts. |
| `first_reliable_available_at`, `created_at` | UTC evidence availability and declaration creation; no backdating. |

Known limitation: cross-row supersession foreign keys and a migration
application runner remain outside v1. Atom 3 validates the repository ledger,
exact ordering, immutable content hashes and replay from a fresh DuckDB
database; it does not claim that a declared migration was applied.

## 7. Decision-safe macro

### `decision_safe_observations(as_of_timestamp)`

Macro identity: `decision_safe_observations`.

Purpose: parameterized DuckDB table macro exposing only canonical observations
whose `available_to_strategy_at` and `first_reliable_available_at` are no later
than the supplied UTC cutoff. Truth owner is the input dataset/manifests; the
macro is a rebuildable read policy. First runtime consumer: TASK-13, then
TASK-18/19, TASK-20..40 and TASK-43..47.

Input `as_of_timestamp` must be a timezone-aware UTC timestamp. Output fields are
exactly all `canonical_observations` fields with no revision collapsing:
provider disagreement and historical revisions remain visible so each consumer
can apply a declared revision-selection policy. The macro cannot prove that a
writer set truthful timestamps; source receipts and replay tests must do so.

## 8. Writer and validation rules

Before insertion, a writer must validate full hexadecimal SHA-256 syntax,
timezone awareness, mint/unit provenance, idempotency derivation and its
authority to classify availability. Inserts run under one DuckDB writer.
Duplicate idempotency is a hard error or may be treated by the caller as an
idempotent no-op only after verifying that every supplied field exactly matches
the retained row. It must never overwrite the row.

TASK-18/19 replay must rebuild from the same immutable pieces and manifests,
select by the same as-of cutoff and obtain the same deterministic fingerprints.
Any mismatch invalidates the derived projection; it does not authorize repairing
historical evidence in place.

## 9. Executable boundary and migration policy

`src/solana_alpha_lab/contracts/schema_v1.py` is the executable v1 boundary for
all 15 relations. Every DDL column has one same-named Pydantic v2 field. All
fields are explicitly required at the boundary, including nullable fields:
callers must send `null` rather than silently omit unknown values. Models are
strict, frozen and reject undeclared fields. JSON boundary parsing accepts the
standard JSON encodings required for aware timestamps, decimals and bytes, then
returns typed values for parameterized DuckDB insertion.

Cross-field model checks mirror the DDL state machines and PIT constraints:
revision self-links fail; first reliable availability cannot follow strategy
availability; atomic values require mint/decimals provenance; missing remains
distinct from zero; quote fee/status, signal side, execution terminal state,
inventory recovery and migration application evidence fail closed.

`migrations/0001_canonical_schema_v1.sql` is an exact byte snapshot of
`schemas/schema_v1.sql`, identified by SHA-256
`eae9d1544b11cffc03afba1e263153168a11dc6f648df9117a55a4cae5d23f09`.
`migrations/ledger_v1.json` gives migrations stable IDs, contiguous positive
order, immutable content hashes and explicit application state. Existing ledger
entries may not be deleted, reordered or mutated; only a declared entry may
transition to a terminal state.

The v1 evolution allow-list is deliberately narrow: initial schema declaration,
adding an explicitly nullable column and verified widening of supported integer
or decimal types. Narrowing, dropping a column, making a column required,
path traversal, checksum drift, duplicate IDs/orders and order gaps are rejected.
The ledger is a declaration/control surface, not an application receipt:
database mutation and setting `APPLIED` or `FAILED` require a later bounded
runner plus exact receipt.
