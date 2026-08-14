# Solana Alpha Lab domain policy

Status: `ACTIVE_V1`
Owner: `SOLANA_ALPHA_LAB_V1`
Front door: `AGENTS.md`

This file is L2 domain policy. Load it at Entry/Finish or when the named
boundary applies; do not inject it into every model turn.

## MISSION_AND_PRODUCT_LOOP

Build a cheap, evidence-backed and owner-operable Alpha Factory for executable
Solana memecoin hypotheses over roughly 15m–4h. The target is owner cashflow
after all cash costs, risk and operator burden—not candles, gross PnL, code,
data volume, bot count or control artifacts.

The durable loop is:

`idea -> hypothesis dossier -> research route -> PIT dataset/trial -> OOS/walk-forward decision -> paper/shadow/micro-live -> trigger/risk/execution/position/exit -> reconciliation/NetReturn -> owner cashflow -> monitor/incident -> learn/retire/reactivate`

Hypothesis, strategy and bot are different versioned objects. Every durable
output names its consumer and the decision it unlocks. Selection-affecting runs
are trials; unlogged trials are research debt. Missing/unknown is never zero,
false, flat, filled or settled.

## ENTRY_AND_TASK_OUTCOME

Entry Gate checks mission/estimand, owner decision, named consumer, direct
dependencies, cheapest falsifier, evidence gain, cash/time/operator burden,
execution-to-cashflow contribution, recovery, reuse/build and Product Horizon.
Return exactly one: `START_AS_WRITTEN | START_WITH_PATCH | SPLIT | REORDER | BLOCKED | SKIP/CLOSE`.

Use a PRD-lite Task Outcome Brief in the task contract: owner decision, product
outcome, named consumer, cheapest falsifier, terminal outcomes, user-visible
result, non-goals, evidence budget and replan trigger. Use a separate design
spec only for a public contract/schema, truth-owner boundary, multiple systems,
runtime/recovery/security, provider abstraction, money/risk/position or a
multi-state user workflow. Do not duplicate an existing contract.

## FACTORY_FIT_REVIEW

Use `FAST_PATH` only for narrow reversible routine work. Use `FULL_REVIEW` for
architecture, data/lineage, cross-consumer, external authority, automation,
execution, position, risk, monitoring, security or control-plane work. Review
mission, flexibility/history, context and validation efficiency, research
truth, owner UX/operability, execution-to-cashflow, monitoring/recovery,
build-vs-buy and adversarial failure. `FAIL` blocks DONE.

## PRODUCT_HORIZON_RADAR

At Entry and before DONE return at most `NOW: one candidate` and `WATCH: one
trigger`. Each names value, evidence, cost/risk, owner, activation trigger and
why now/not now. Do not silently implement adjacent scope or turn the radar
into a decorative backlog.

## MODEL_EFFORT_ROUTER

Emit one `MODEL_EFFORT_RECOMMENDATION` before a substantial chain and one
`NEXT_MODEL_EFFORT` at its checkpoint, never on microsteps. The "hardest material segment"
sets an uninterrupted chain: `LUNA_MAX` is the workhorse;
`SOL_XHIGH` handles material architecture/contracts/PIT/security; `SOL_MAX` is
reserved for irreversible or unresolved adversarial work; `TERRA_XHIGH` is
fallback; `ROUTINE_NO_SWITCH` handles smoke/read-back/ordinary merge.

## DATA_AND_RESEARCH_TRUTH

Historical/reusable cache first. Live capture requires a named non-reconstructable
consumer, fields, cadence, availability, retention, cost cap and falsifier.
Preserve event/observed/available/ingested time, lineage, revisions and source
disagreement. No future labels. Holdout opening consumes that holdout; redesign
requires a new forward holdout.

Estimand is `NetReturn` after PIT data, executable buy/sell route, latency,
fees, retries, exit and notional. Separate `Touch | Fillable | RealizedVWAP |
Net | PathRisk`. Trigger is not order, fill or profit.

## IMPORTED_BYTES_AND_ADVISORY_CONTEXT

Every imported record preserves exact source bytes, origin task/path, legacy
ID when available, creation time, `first_reliable_available_at`, retention and
named consumers. Import or backfill never creates retroactive availability.
Content-addressed imported evidence is not style-normalized, and bundle-only
or superseded code never becomes active product code merely because it exists
in Git history.

External analytical context such as AOT/ALBS is advisory only. It must carry
as-of, first reliable availability, TTL, revision, hash, confidence or
calibration, lineage, evidence and allowed-consumer fields. It cannot command
a bot or bypass holdout, risk, execution, inventory, reconciliation or
economics gates.

## EXECUTION_RISK_AND_MONITORING

Trace hypothesis/version through watchlist, trigger, decision/risk, intent,
quote/route/simulation, attempt/settlement, position/exit, inventory
reconciliation, NetReturn/cashflow and feedback. Unknown transaction reconciles
before retry. Monitoring loss with possible open inventory blocks new entries.

Live authority needs freshness/lag, route/finality, fills/fees, inventory/exit,
PnL/drawdown/exposure, provider/process/signer health, kill switch, incident and
recovery visibility. Alive process with stale data, reconciliation or exit is
unhealthy. Before OOS+paper+shadow, Kelly is zero.

## PROVIDER_ROUTE_REGISTRY

Before building or invoking a provider route, resolve its stable ID through
`configs/provider_route_capability_registry_v4.yaml` (`PROVIDER-ROUTE-CAPABILITY-REGISTRY-004`).
This successor preserves `configs/provider_route_capability_registry_v3.yaml`
as its exact append-only predecessor rather than rewriting historical route
observations.
It preserves immutable predecessor `PROVIDER_ROUTE_CAPABILITY_REGISTRY_V1` at
`configs/provider_route_capability_registry_v1.yaml`. A missing record is
`REGISTRY_GAP`, not provider failure. A record grants no call, credential,
retry, fallback or provider-selection authority.

For an authorized one-shot credentialed attempt under uncertain network
health, run a credential-free DNS/TCP/official-endpoint preflight first. A
failed preflight consumes no credential or market attempt and stops. It is not
provider authority or a substitute for exact raw retention.

## REUSE_FIRST_RECOVERY_TRIGGER

After the first material, evidence-backed blocker, preserve the result and stop
expansion before custom construction, route widening or infrastructure. Allow
no hidden retry or fallback. Consult `registries/reuse_candidates.yaml`, `ADR-002`
and the smallest useful set of current official, maintained OSS or commercial
solutions for the named consumer. Record exactly `ADOPT`, `WRAP`, `FORK`,
`BUILD`, or `STOP` plus cheapest falsifier in the current atom's decision or
acceptance receipt—not a registry row, permanent Source, or generic scan
artifact.

This trigger excludes a routine deterministic test failure, already-known
limitation or an exact prescribed recovery. It grants no provider, dependency,
cost, security, or owner-boundary change. `BUILD` is justified only for a narrow
project-owned truth boundary after the alternatives are evidenced unfit.

## VALIDATION_ECONOMY

One exact candidate fingerprint has one full-gate owner. During implementation
run targeted checks. A failure reruns only after its root cause changes. A pass
reruns only after candidate bytes, dependencies, runtime or validation policy
change. Catalog/generated/security/topology checks run when their owner or
consumer changes.

## TRACKED_ONLY_DELIVERY_PREFLIGHT

Fail-closed local full owner selected inside guarded merge only when the
base-bound focused-plus-exact-PR-CI route is ineligible:

`uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery`

It copies no untracked or ignored inputs and runs once on a clean exact commit
in an isolated checkout. Its wall-time cap is 15 minutes. After bootstrap it is
not an implementation-loop or per-atom hook and is not a routine pre-PR gate.
New tests cannot skip missing local/raw evidence in place of a
tracked fixture or exact non-critical proof.

## CI_OWNED_DELIVERY_PILOT

Only a machine-eligible bounded offline/routine candidate may use
`uv run --locked --managed-python python -B scripts/validate_ci.py --ci-owned-delivery`.
`GITHUB_PR_EXACT_HEAD_CI` owns the full suite when the base-bound primary route
is eligible; guarded merge executes the local focused command once and reads
that existing exact-head run. The local focused cap is 120 seconds. The pilot admits the next three eligible
observations, records `observation N/3`, requires 3/3 first-head CI and at least
seven minutes saved. After 3/3, do not admit a fourth before keep/repair/rollback.
A false admission, missed clean-checkout/local-data defect or focused overrun
falls back to `--tracked-only-delivery`.

## CONTROL_ONLY_TASK_CLOSE_FAST_PATH

`--control-only-task-close` is eligible only for its exact closed control write
set and machine classification. It never requires cloud bundle activation or
smoke under `DELIVERY_HARNESS_V1`. `GITHUB_PR_EXACT_HEAD_CI` owns the full gate;
any ambiguity falls back to `--tracked-only-delivery`. Keep only after three eligible task closes
with no repair and within the declared time cap.

## FACTORY_LEVERAGE_INVARIANT

A comparable hypothesis already supported by the Factory should run by
configuration/data/query composition, without product-code changes. Code is
justified by a named reusable capability gap, defect, safety/reliability need
or measured scale bottleneck, with its next real consumer. Repeated
hypothesis-specific code triggers Factory Fit; it does not trigger a generic
platform or refactor by taste.

## ACTIVE_TIME_GATE_CHECK

`control/active_time_gates.json` is interpreted by gate records, not by stale
cloud-export prose in its legacy `resume_router`. Any resume terminal whose
only remaining action is bundle/Project Sources activation or owner smoke is
`HISTORICAL_OPTIONAL_EXPORT_NON_TRIGGERING`; it cannot select work, block DONE,
or create an owner request. This overlay preserves the old bytes for audit and
prevents their obsolete UI workflow from regaining authority.

Before selecting or starting new work, read `control/active_time_gates.json`
when present. A due unresolved marker routes to its exact
`required_next_atom`; an `ACTIVE_WAITING` marker does not block non-interfering
work before `earliest_at`. The marker grants no provider, spend, deployment,
credential, wallet, signer, transaction, merge or destructive authority. Only
its declared resolution owner may terminally update it with exact evidence.

## SECURITY_AND_CASH_BOUNDARY

Secrets never enter chat, repo, logs, URLs or receipts. Signer is isolated.
Real money follows threat model, signer/canary, exact owner gate and explicit
cash cap. Project free cashflow is settled cashflow minus trading and
infrastructure cash costs, considered with capital, CVaR/capacity and operator
time. Purchase/infrastructure follows a measured bottleneck and value above
full cost/risk.
