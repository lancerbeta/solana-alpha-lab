# Episode decision continuity v1

An eligible scientific decision defines a strategy; explicit activation defines
an offline bot. The runner lives at `scripts/trading_continuity.py`. It calls the
upstream episode producer, then the existing generic PaperPlane. Git owns
definitions, ResearchStore owns scientific receipts, ObservationScheduleStore
owns episode observations, and PaperPlane owns runtime events and positions.
No additional truth store or scientific promotion is introduced.

Supported input is StrategyVersion 1.1 with a verified PROMOTE manifest and
execution binding, and its exact ExperimentSpec `parameters.episode_query` in
the existing HFIC query 1.2 grammar. Both LIST_CONTRAST and MIXED_LIST_NUMERIC
reuse canonical list definitions, aliases, selectors, EPISODE_T0 coverage,
feature interpretation and the single `resolve_point`. Exact registered local
membership dependencies are `parameters.membership_snapshot_shas` (at most 32).
Explicit research-corpus cohort selection is refused with
`RUNTIME_COHORT_SELECTION_UNSUPPORTED`; it cannot silently become runtime scope.
Absent query is `BOUND_EPISODE_RECIPE_REQUIRED`. No default trading hypothesis,
new expression language, EMA or risk limit is invented.

The prefix reader opens WAL-aware readonly SQLite in one snapshot. Membership
coverage is checked before lazy numeric reads.
The shared scientific `episode_decision_price` owner then requires OBSERVED
PRICE at the decision point before any entry features, including LIST_CONTRAST.
Missing/late PRICE gives `EPISODE_DECISION_PRICE_<status>` and UNKNOWN without
admission; it cannot be healed by a later point. List-only therefore reads the
eligibility PRICE but no holder feature. Originating exits evaluate their frozen
target through the arithmetic owner without re-admitting or re-checking lists.
Observations must satisfy their
own point deadline and the frozen decision cutoff. Pending outbox observations
and canonical, hash-verified publications are read through the source owner;
source-owned `ingested_visible_at` is carried unchanged from outbox into hashed
publication rows. A later publication can retain an earlier input's first
visibility without claiming the publication itself existed earlier. Legacy
published rows without this clock use publication time as a conservative floor.
Exact episode/point filters exclude future point values. This reader neither
seals nor exports nor admits a mature research release. Publication removes
outbox rows under the existing publisher contract.
An unavailable or conflicting historical prefix is refused; it is never healed
with a future value. The readset records point, field, deadline, content hash and
row count, first visibility and source event/received/reliable-availability
clocks. Consumers verify the packet hash, evidence reference and originating
strategy/epoch rather than trust a bare SHA string.

The runner uses PaperPlane's `accept_signal_decision_outcome` while owning the
outer source/admission transaction. A valid source ENTER and admission DENIED
are separate facts: source action/provenance stay unchanged. Normal stale,
operator-stop/pause and existing risk-policy refusals return `outcome=DENIED`,
with exact reason, mode/strategy/version/epoch, source fingerprint and an
`evaluation_event_id` resolving `SIGNAL_ADMISSION_DENIED` in the existing event
table. Risk-policy evaluation retains its PRE_TRADE_RISK_SNAPSHOT and policy
status/revision/hash; refusals before policy evaluation leave policy fields null.
Reservation cancellation records CANCELLED and its existing cancellation event
in that same transaction. ATTEMPTING/UNKNOWN remain reconciliation states.
Evaluation identity includes source fingerprint, explicit evaluation time,
bot status/pause and, where evaluated, exact risk snapshot/policy binding.
Identical evaluation replay adds no events or positions. A different policy or
inventory evaluation remains distinguishable and may admit the same source;
earlier denials are retained. This does not introduce a permanent denial cache.
Malformed/conflicting inputs, unknown exceptions and SQLite failures propagate
and roll back source, risk and reservation together. Successful admission still
freezes amount, fee and policy revision atomically. `accept_signal_decision`
retains its legacy exception API; callers composing an outer transaction use
the outcome API so a normal refusal cannot accidentally abort their commit.

Logical signal identity is strategy/version + activation epoch + episode +
frozen recipe hash + decision slot. Mint alone is not identity. Closed
SignalDecision/ExitDecision schemas are preserved: `evidence_refs` points to
`execution-event:SRC-<decision_id>:sha256:<provenance_hash>`. The actual packet is
durable in the existing execution event table, committed atomically with
admission/exit. Same identity with different packet is a conflict. Attempts
resolve that packet before starting. All ordinary calls require explicit as-of.

`begin_modeled_attempt` commits a stable attempt before the fake external side
may act; replay returns `send_permitted=false`. Entry stop/pause/staleness wins
before this commit. A possibly submitted attempt cannot be resent under another
key. The result consumer accepts only its closed provider-neutral payload:
attempt_id, result_id, outcome, observed_at, optional unit_price_usd,
filled_notional_usd, chargeable_cost_usd. Its observation, position/accounting
mutation and final marker share one transaction. Unknown observations can be
followed by one definitive result; conflicting or second final results refuse.

| Outcome | Entry | Exit |
|---|---|---|
| NO_ROUTE / REJECTED_BEFORE_SEND / DROPPED_OR_EXPIRED_NOT_PROCESSED / LANDED_FAILED | CANCELLED, no fabricated quantity/PnL; cost preserved | UNRESOLVED, inventory preserved; definitive retry permitted |
| UNKNOWN_REQUIRES_RECONCILIATION | UNKNOWN; same attempt reconciled | UNRESOLVED; same attempt reconciled |
| LANDED_SUCCESS | OPEN after exact admitted size/fee checks | RECONCILED through existing fill/accounting owner |
| PARTIAL | Existing PARTIAL entry inventory | PARTIAL_EXIT_MODEL_UNSUPPORTED, no effects |

Delayed proof permits UNKNOWN → OPEN/PARTIAL/CANCELLED in the result seam.
After an operator close request, a delayed positive entry preserves
EXIT_REQUIRED while recording quantity/fee; a definitive non-fill permits
EXIT_REQUIRED → CANCELLED. An exit attempt cannot start before entry is known.
Exit as-of must follow originating decisions and accepted result observations.
Operator cancellation still cannot assert non-fill for UNKNOWN. PAPER evidence
is PAPER_MODEL; SHADOW is SHADOW_QUOTE_MODEL, never REAL_FILL. An attempt's
chargeable_cost_usd is its cumulative **additional modeled cost excluding**
entry/exit price-leg fees. Unknown cost stays unknown. Costs are counted once
per attempt, preserving its confirmed lower bound even when a later total is
UNKNOWN. A known cumulative total cannot decrease; observation clocks cannot
move backwards. Unknown total never becomes zero or a fully known headline.
Trade PnL and additional costs are
separate; a combined modeled net is shown only for one compatible, terminal,
fully known scope. Modes, strategy versions and epochs are never summed into a
cashflow headline. NETRETURN_STATUS=NOT_ESTABLISHED; OWNER_FCF_STATUS=NOT_AVAILABLE.

Exit uses the originating recipe, position version and epoch, independent of
subsequent list disappearance. Automatic scientific exit on an inactive bot is
`AUTOMATIC_EXIT_INACTIVE_EPOCH_UNRESOLVED_USE_OPERATOR`: the unresolved policy
question is preserved. Existing REQUEST_CLOSE_POSITION, result reconciliation
and drain remain available. STOP_BOT alone does not request a modeled exit.
The runner calls maybe_finish_drain after result acceptance; a crash between
these steps is recoverable by exact result replay.

| State | Entry-admission count | Possible inventory | Operator settled | Drain clear | Next safe action |
|---|---|---|---|---|---|
| WATCHED / SIGNALLED / INTENT_CREATED | yes | no submitted fill | no | no | attempt if permitted, or cancel |
| ATTEMPTING / UNKNOWN | yes | uncertain | no | no | reconcile same attempt |
| OPEN / PARTIAL | yes | yes | no | no | originating/operator exit |
| EXIT_REQUIRED / EXITING / UNRESOLVED | no | yes/uncertain | no | no | exit/reconcile |
| CLOSED | no | requires reconciliation | yes | no | reconcile |
| RECONCILED | no | no | yes | yes | readback |
| CANCELLED | no | definitive non-fill | yes | yes | readback; PnL N/A |

These columns mirror existing authority; entry limits are not inventory limits.
Adding EXIT_* / UNRESOLVED to the admission veto needs an owner risk-policy
decision. The operator count now uses the actual OPEN_RISK_STATES owner.
Readonly readback never creates/migrates/checkpoints state. Missing/corrupt/native
read failure gives typed unavailable, not healthy zero.

Originating EXIT integrity uses the existing execution-event owner. In the same
transaction as SOURCE_EXIT_PRODUCED and accepted exit state, the runner stores
one SOURCE_EXIT_ADMISSION_BOUND event (EXITBIND-<exit_decision_id>) with the
canonical complete packet hash, source event ID, position ID, exit decision ID
and admitted SignalDecision hash. Identical replay retains the same binding;
any actual binding failure rolls the entire source/exit transaction back.
Before source-originated EXIT attempt/result, event types, position/bot scope
and exact binding must match. Missing or changed binding is typed provenance
refusal before effects. Operator exits without source exit decisions retain
the existing route. A source exit accepted after operator close still creates
this binding although the generic owner needs no second EXIT_DECISION_ACCEPTED
transition. No schema, stale threshold or admission/exit risk policy changes.
