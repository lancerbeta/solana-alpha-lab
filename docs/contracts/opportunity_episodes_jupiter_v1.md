# OPPORTUNITY_EPISODES — Jupiter core vertical slice contract V1

Status: ACTIVE software capability, live lane DISABLED by default.
Owner task: `docs/tasks/OPPORTUNITY_EPISODES_JUPITER_VERTICAL_SLICE_V1.md`.
Domain owner: `src/solana_alpha_lab/factory/opportunity_episodes.py`.

This contract is additive. Legacy newborn `BASE_X` collection, its
`smial.observation-schedule` 1.0 documents, X/Y point parser and hashes,
release schemas 1.0/1.1, `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`,
temporal query 1.0 and calculation versions V1–V5 keep their meaning. An
episode is never interpreted as a newborn birth and a mint is never an episode.

## 1. Stable identifiers

| Field | Value |
|---|---|
| population | `OPPORTUNITY_EPISODES` |
| population_contract | `OPPORTUNITY_EPISODES_V1` — all committed admissions are the denominator |
| anchor_kind | `NOMINATION_T0` — the durable admission commit instant |
| logical_dataset_id | `DATASET-OPPORTUNITY-EPISODES-DISCOVERY-CORPUS-001` |
| collection_kind | `JUPITER_CORE_OPPORTUNITY_EPISODES_V1` |
| collection namespace | `OPPORTUNITY_EPISODES` (all cohort/release/import keys) |
| schedule_contract | `OPPORTUNITY_EPISODE_SCHEDULE_V1` |
| schedule document | `smial.opportunity-episode-schedule` 1.0 |
| release schema | `smial.live-cohort-discovery-release` 1.2 (+ `collection`) |
| temporal query | `smial.hfic-temporal-query` 1.1 with `population=OPPORTUNITY_EPISODES` |
| evidence role | existing `EXPLORATORY_REUSE` after the metadata protection gate |

Unknown combinations of dataset/population/anchor/schedule/version are refused
before any value loader.

## 2. Identities

* Mint: canonical Solana mint string. Never replaced by an episode id.
* Call occurrence: one durable call-ledger occurrence (route/query, request
  hash, request/receipt clocks, raw body ref). Equal bytes from different calls
  stay different occurrences.
* Source occurrence: call occurrence + mint + source id + rank.
* Intake frame: `(activation, round_id)` + complete declared source set +
  protection/policy fingerprints. It is the vendor-frame denominator, not the
  Solana universe.
* Sampling ticket: `(collection_lineage, cycle_start, mint)`; priority =
  `sha256(canonical{seed, cycle_start, mint, version})`; one stable lottery per
  fixed cycle (Monday 00:00 UTC → next Monday).
* Episode: one committed ticket admission.
  `episode_id = "EP-" + sha256(canonical{collection_lineage_id, cycle_start, mint})[:32]`.
  T0 is not part of the key; a second commit for the same key with different
  content is `EPISODE_ADMISSION_CONFLICT`, never an overwrite.
* Cohort: `(OPPORTUNITY_EPISODES, UTC admission day)`; id
  `REL-<day>T000000Z-<day+1>T000000Z`, always used together with the namespace.
* Scientific trial/look: unchanged existing ordinary operation accounting.

Research joins use `episode_id`; `mint` stays the true mint. Population cards
report admissions, distinct mints and repeated mints separately.

## 3. Schedule and clocks (`OPPORTUNITY_EPISODE_SCHEDULE_V1`)

Offsets (seconds): `{0} ∪ {300..21600 step 300} ∪ {25200..259200 step 3600}` —
139 points, ids `E0`, `E300`, …, `E259200`. Legacy `X300/Y…` are not aliases.

For `o > 0`: `nominal_due = T0 + o`; `assigned_at = ceil_UTC(nominal_due, 300)`
when `o ≤ 21600`, else `ceil_UTC(nominal_due, 3600)`; an instant already on
the grid is not moved. Dispatch window `[assigned_at, assigned_at + 60s)`;
availability deadline `assigned_at + 300s`. A missed dispatch window is a
no-request gap; no catch-up request is ever issued for a past slot.

`E0` is the admission witness: the selected whole object received before T0
with its original request/receipt/availability clocks (never restamped to T0).
Its numeric use requires `T0 − witness_available_at ≤ witness_max_age`.

One resolver (`opportunity_episodes.resolve_point`) returns
`nominal_due/assigned_at/dispatch_deadline/availability_deadline` for
`(schedule binding, T0, point)` and is used by the producer, release closure,
evaluator, preview, replay and card. `POINT_OFFSET` is never patched.

Time features under query 1.1 use `time_feature_clock=FIRST_RELIABLE_AVAILABLE_AT`:
`elapsed_seconds` is the difference of the actual availability of the two
selected PRICE cells; `utc_hour` is the hour of the actual availability. The
decision cutoff is the resolver availability deadline of the decision point,
fixed before values. A query uses at most 8 points in the union of features,
decision, reference and exit; no interpolation, nearest lookup or backfill.

## 4. Admission (producer)

Round every 900 s UTC; sources `toporganicscore/5m`, `toptraded/5m`,
`toptrending/5m`, limit ≤ 100, no retry/fallback. A round is complete only when
every declared source returns a bounded valid body inside
`[round_start, round_start + slack]`; an incomplete round admits nothing.

Order: bounded raw receipt (HOT raw plane, content addressed) → identity
projection → protection decision → value projection → asset/capture-floor
qualification → dedupe (freshest whole object by receipt time; tie by source
order then object hash; a fresher FAIL is never healed by an older PASS) →
sampling. Capture floor: holders ≥ 50, 5,000 ≤ liquidity USD ≤ 1,000,000,
finite USD price > 0, all from one whole object.

Quota: daily ceiling `C`; round `j` of the UTC day admits at most
`k_j = floor(C(j+1)/96) − floor(Cj/96)`; idle quota is not carried; rolling
24h admissions ≤ C; one episode per mint per cycle; one active trajectory per
mint; active-episode cap; pressure stops intake, never drops admitted work.

Commit: one SQLite transaction writes the episode row (identity, T0, witness
refs, policy/schedule refs, priority, cohort), all 138 future slot rows and an
outbox row. T0 = commit clock. Crash before commit: no member, orphan raw is
harmless, no backdating. Crash after commit: same episode recovered and the
outbox is republished; no new lottery or replacement.

Protection gate (`ALLOW | DENY_PROTECTED | UNRESOLVED_SCOPE`): metadata-only
over registered assignment sources named by the schedule; a missing source or
missing completeness proof is `UNRESOLVED_SCOPE` (never blanket ALLOW). Denied
or unresolved rows never reach the value projection; only counts are recorded.

## 5. Observation states

| Situation | State + reason |
|---|---|
| valid explicit field | `OBSERVED` |
| mint absent from a valid batch | `DISAPPEARED` + `MINT_ABSENT_IN_RESPONSE` |
| field missing/invalid | `MISSING_TYPED` / `EXCLUDED_AMBIGUOUS` + field reason |
| slot never requested | `CENSORED` + `SLOT_NOT_EXECUTED` |
| provider/transport failure | `CENSORED` + HTTP/transport class |
| response after availability deadline | `CENSORED_LATE` (clocks/bytes kept, no value) |
| intent recorded, durable result unknown | `IN_FLIGHT_CALL_INDETERMINATE` + `ATTEMPT_OUTCOME_UNKNOWN` |

Typed null is never 0. Capture floor is applied once at admission; later
declines, disappearance or bad outcomes never remove an admission.

## 6. Release, import and closure

Cohort maturity: admission day closed, every admitted episode's 138 slots
terminal, every outbox row published, publication jobs complete. A timer is
not a closure proof. Release 1.2 (collection strategy inside the current
release owner) carries census (one row per admission), observations, the
schedule artifact (byte hash separate from semantic hash), selection/frame
receipts, and the required raw body dependency set; one file resolver is used
by hash, verify, transport, import and cold package. Import goes to the
separate episode corpus lineage; identical identity+bytes are reused
(`PASS_ALREADY_PRESENT_EXACT`), same identity with other bytes conflicts.
Import validity is not research sufficiency.

## 7. Forge

The population card is generated by import/readback/preflight. Query 1.1 with
`population=OPPORTUNITY_EPISODES` resolves the episode corpus binding; base =
all committed admissions; decision eligibility = existing universe policy at
the decision point + observed decision PRICE; holder delta/return_ratio,
price/liquidity point/return/ratio and time features reuse existing temporal
arithmetic. Saved readback loads zero values; registered replay recomputes.

## 8. Non-goals

No live activation, provider calls, Birdeye, volume numeric features, backfill,
new evaluator/importer/DB/service, trading or lowered scientific floors. The
category 5m routes are a `PROVIDER_ROUTE_REGISTRY_GAP` in
`CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010` until OPERATE commissioning
records real evidence; the episode authority profile does not grant activation.

## 9. Accepted limits and open owner decisions

Bounded operability uses the shared ResearchStore's optional explicitly prepared
identity lookup (`docs/contracts/research_write_lookup_v1.md`). It changes writer
work, not canonical episode bytes, timing, population, protection or readers.
Fresh capture with a later as-of revalidates closure content, then retains an
already frozen closure/release identity. Regressed as-of or changed closed
content is refused. Multiple activation/profile fragments of one UTC-day cohort
are explicitly `EPISODE_COHORT_FRAGMENTED_UNSUPPORTED` before partial export;
the canary uses one profile with no intraday switch.

Episode calls reserve budget before durable STARTED/send; ambiguous outcomes
keep that debit. A UTC rollover during STARTED persistence conservatively
charges the request_started_at day too, with no refund of the earlier debit.
Completion adds bytes/pacing without a second ordinary debit. This affects
episode accounting only; legacy calls keep the previous completion policy.
Counter debits are conservative reservations, not evidence of HTTP attempts.

Before nomination the storage admission owner projects committed slots plus
the next round at the frozen response cap, six possible copies and 256MiB
margin. Insufficient/unknown filesystem free bytes commits ordinary stop-intake
and DRAINING; no admissions or committed obligations are deleted. This is a
conservative local MODEL, not an approved shared-account/whole-Factory budget
or a proven compression guarantee. TARGET <=40GiB/HARD <=50GiB still require
the existing whole-Factory commissioning envelope. Other consumers, unrelated
resident bytes and backup peaks remain separate gates, never inferred absent.

Metadata readback distinguishes intake, frames, obligations, attempted/no-request/
ambiguous execution, missing values, publication backlog and next maturity.
Legacy rows lacking new diagnostic metadata return UNKNOWN, without backfill.
Episode nomination does not inherit birth/recent source-poll coverage semantics.

- Protection reaches raw evidence too: the published E0 dependency is a
  content-addressed witness extract holding only the admitted object and the
  hash of its source response. A nomination response stays on the capture host.
- The focus owns the collection. A query whose `population` differs from the
  focus collection stops before values with `FOCUS_POPULATION_MISMATCH`; the
  grounded BASE_X evaluator refuses an episode binding and keeps its X/Y point
  allowlist.
- The base is every admission for counts and decision eligibility. Effect means
  use target-available episodes only; `episode_target_attrition` reports missing
  targets by reason for the matched set and the decision baseline, with no
  adjustment (`TARGET_ATTRITION_NOT_ADJUSTED`). A vanished mint at exit can be
  outcome-linked. Any imputation or sensitivity rule is an owner estimand
  decision.
- The market evidence epoch stays data-root global, as before this slice: any
  current dataset publication, an episode import included, rotates it and with
  it per-epoch session and focus budgets. A per-collection epoch is an open
  owner decision.
- One question never mixes clock semantics across cohorts
  (`SCHEDULE_CLOCK_MIXED`). Only the lineage-current corpus version binds.
- `asset_class` UNKNOWN (no tags) is admitted and remains a census field; the
  stable/LST exclusion list applies only to explicit identities and tags.
- Repeated mints across cycles and same-day episodes are not independent
  (`NO_IID_CLAIM`); the estimand is admitted episodes, not random nominated
  mint-rounds. `elapsed_seconds` and `utc_hour` under
  `FIRST_RELIABLE_AVAILABLE_AT` include collector latency and grid phase.
- Registered replay recomputes the frozen recipe from the release bytes in a
  separate process; it is a determinism check, with literal oracle values
  asserted alongside, not an independent implementation.

## 10. Frozen protection provenance and stop-intake

- The protection sources frozen in the schedule (assignment id + semantic sha)
  are the only admission-time policy. Capture export reads each registered
  assignment file and fails closed, before writing anything, when it is
  missing, a symlink, unreadable, of another identity or of another semantic
  hash. The release carries exactly those assignments as mandatory
  dependencies; `verify_episode_release` re-derives the pins from the schedule
  artifact, requires them to equal the closure's, and refuses a missing, extra
  or substituted file even when the manifest agrees with it. The Forge reader
  binds only these frozen assignments (plus any current stricter ones).
- Operator stop-intake (`scripts/observation_schedule.py stop-intake`) is an
  early ACTIVE → DRAINING on the existing lifecycle owner and ResearchEvent
  evidence (`operator_stop_intake`); it exists for the episode lane only,
  closes admission at its committed instant and leaves committed obligations,
  publication and completion to the ordinary drain. It is idempotent, never
  reopens intake after a crash, and does not change `pause`, which still stops
  all obligations.
- Residual, stated: the drain proof reads `operator_stop_intake` from the
  immutable ResearchEvent written by the episode-only command; it does not
  additionally re-resolve the schedule kind. A late holdout inside a running
  activation needs a new schedule (the pinned assignment may not change).
