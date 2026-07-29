---
evidence_id: EVIDENCE-T17-FIRST-BOUNDED-HYPOTHESIS-CYCLE-001
evidence_version: "1.0"
task_id: TASK-17
atom_id: T17-A2_FROZEN_FIRST_REAL_HYPOTHESIS_DOSSIER_V1
status: FROZEN_REAL_CANDIDATE_PAUSED_FOR_SEPARATE_DATA_GATE
as_of: "2026-07-29T12:18:49Z"
hypothesis_family_id: HYP-FAMILY-EXECUTION-CAPACITY-CURVATURE
hypothesis_version_id: HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1
research_cycle_id: RESEARCH-CYCLE-EXECUTION-CAPACITY-001
origin_route: RETAINED_DATA_EXPLORATION
schema_origin_kind: DATA_ANALYSIS
data_verdict: LIVE_NON_RECONSTRUCTABLE_NEED
live_capture:
  authority: NOT_AUTHORIZED
  scope: VERSIONED_HYPOTHESIS_WATCHLIST_MEMBERS_ONLY
  max_members: 8
  triggered_windows_per_member: 3
  notionals_usd: [10, 25, 50, 100]
  quote_legs_per_notional: 2
  max_provider_calls: 192
  concurrency: 1
  retries: 0
  cash_cap_usd: 0
search_budget:
  hypothesis_versions: 1
  primary_estimands: 1
  planned_trial_variants: 1
  holdout_looks: 0
provider_calls_in_atom: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# TASK-17 first bounded hypothesis cycle v1

## Owner decision

Decide whether future strategy sizing needs a versioned execution-capacity
curve and veto, instead of treating one quote, one liquidity number or one
fixed position size as safe across notionals.

This dossier accepts one candidate for bounded research. It does not claim
alpha, fillability, realized execution, NetReturn or permission to collect
more data.

## Origin and prior work

The canonical Entry Gate route `RETAINED_DATA_EXPLORATION` maps to the TASK-16
schema enum `DATA_ANALYSIS`. The candidate is grounded in two retained assets:

- `PRE-GIT-TASK01-A019` named `H08 execution/capacity gate` and prescribed a
  notional sweep whose cheapest falsifier closes a strategy version when its
  edge vanishes at intended size.
- `EVIDENCE-T10-JUPITER-QUOTE-SUMMARY-002` recorded one selected mint at one
  bounded point in time. Quote-only recovery deteriorated monotonically:
  96.578340% at USD 10, 95.194668% at USD 25, 92.950736% at USD 50 and
  88.811179% at USD 100. The corresponding quote-only costs were 342.1660,
  480.5332, 704.9264 and 1118.8821 bps.

The offline TASK-16 prior-work query was exercised before this record existed.
Production research memory was empty. Its deterministic fixture returned one
synthetic `liquidity reversal` example, which is unrelated and excluded from
production history.

`what_changed`: TASK-17 now has real retained quote evidence tied to the
historical H08 capacity question. It does not reuse the fixture's mechanism,
outcome or lifecycle decision.

## Frozen hypothesis definition

- **Statement:** across matched point-in-time quote panels, quote-only
  round-trip cost tends to rise as USD notional increases from 10 to 100;
  therefore future capacity decisions must use a size curve rather than one
  generic liquidity figure or a single quote.
- **Mechanism:** limited executable route depth and route fragmentation create
  nonlinear price impact as order size consumes progressively worse liquidity.
- **Falsifier:** in the bounded matched population, the median
  `cost_bps(USD100) - cost_bps(USD10)` is not positive, no more than half of
  complete panels have all three adjacent cost increases, or the apparent
  pattern exists only during provider error/outage states.
- **Expected regime:** fragmented liquidity, thin executable depth and
  volatile intraday conditions. Regime terms are explanatory strata, not
  permission to tune variants after seeing results.
- **Primary estimand:** median across complete panels of
  `cost_bps(USD100) - cost_bps(USD10)`, where
  `cost_bps(n) = 10,000 * (1 - reverse_sell_usdc_atomic / buy_usdc_atomic)`.
- **Population and controls:** only members of the exact versioned
  hypothesis watchlist used by the eventual test; matched within token,
  triggered window, provider endpoint/version and response class; four frozen
  notionals; every reverse-sell amount equals its preceding buy output.
  `NO_ROUTE`, timeout and invalid response remain terminal observations and
  are not coerced into a numeric quote.
- **Error cost:** falsely declaring capacity safe can turn a paper edge into
  loss; rejecting a usable size is the cheaper error at this stage.

The search budget permits one frozen definition, one primary estimand and one
planned trial variant with zero holdout looks. Changing the statement,
notionals, controls, outcome rule or mechanism requires a new hypothesis
version or a separately frozen trial contract.

## Cheapest route and data decision

`ADOPT` the retained TASK-01/TASK-10 evidence and TASK-16 research-memory
contract/query. `WRAP` the already validated TASK-10 buy/reverse-sell panel
semantics. `FORK=0`, `BUILD=0`: no new provider, dependency, plugin, vector
store or analytical platform is justified.

Verdict: `LIVE_NON_RECONSTRUCTABLE_NEED`.

Historical chain state can reconstruct reserves and swaps, but it cannot
reconstruct the executable quote response, route/error class, provider
version and local request/receipt timing that would have been observed for
each size. The one retained TASK-10 point is directionally useful but cannot
estimate a population or separate size deterioration from a transient
provider/window condition.

The smallest future capture candidate, still `NOT_AUTHORIZED`, is:

```text
8 versioned watchlist members
× 3 triggered windows per member
× 4 frozen notionals
× 2 sequential legs (buy then reverse-sell)
= 192 provider calls maximum
```

Each window must retain the watchlist and hypothesis versions, trigger ID,
token/provider/endpoint versions, exact atomic inputs and outputs, route or
error class, context slot, request/receipt timestamps, latency, fee fields,
raw-content hash and the TASK-10 lineage envelope. Concurrency is one, retries
are zero and cash cap is USD 0.

Proposed retention follows the existing `R1_T0_RAW` boundary: quote/error raw
payloads stay hot for 90 days, then replayable through research-cycle close
plus 365 days; hashes, manifests, sanitized aggregate and decision record stay
for project lifetime. This is a proposed policy for a separately authorized
capture, not a deletion or collection action in TASK-17 A2.

## Truth ownership and lifecycle

`first_bounded_hypothesis_cycle_v1.json` is the immutable detailed lifecycle
snapshot governed by the TASK-16 schema. This Markdown file is its
human-readable decision evidence. The legacy
`registries/research_cycles.yaml` and `registries/hypotheses.yaml` remain
byte-for-byte empty historical inputs pinned by TASK-16 acceptance; populating
them would rewrite that migration evidence and create a second editable copy.
Any future current-state projection must be generated from the immutable
snapshot through an explicit schema/Catalog transaction.

The hypothesis has one `PAUSE` decision event and no trial or activation
epoch. The pause means: request a separate exact authority gate for the
bounded live slice, or close the candidate. It does not authorize a watchlist,
provider call, signal, strategy, execution, position or trade.

## Non-claims and next boundary

- no provider/API/RPC/WSS call occurred in A2;
- no historical hydration or live collection occurred;
- no account, credential, purchase, deployment or scheduler was used;
- no strategy, execution, position, fill, PnL or alpha result exists;
- no wallet, signer, transaction or real-money action occurred.

The next local atom may add deterministic acceptance and Catalog registration.
Any actual live capture remains a separate explicit provider/API boundary.
