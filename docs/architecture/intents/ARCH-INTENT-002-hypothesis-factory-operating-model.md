---
asset_id: ARCH-INTENT-002
title: Hypothesis Factory Operating Model and Owner Pulse
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
owner: user
origin_date: 2026-07-29
first_reliable_available_at: 2026-07-29
truth_owner: ChatGPT_Project_Work_until_coordinated_handoff
contains_secrets: false
---

# ARCH-INTENT-002 — Hypothesis Factory Operating Model and Owner Pulse

## Intent

The product is an owner-operated factory for discovering, falsifying,
promoting, monitoring and reactivating trading hypotheses. Infrastructure,
datasets, models, AI tools, dashboards and bots exist to shorten that loop and
improve its decision quality. They are not goals by themselves.

The owner should be able to:

- bring an observation, question, candidate pattern or external idea;
- ask the factory to explore data and propose testable mechanisms;
- route each research question to a validated existing analytical tool or
  justify one bounded new capability;
- assemble reproducible point-in-time evidence;
- reject weak ideas cheaply;
- promote a surviving hypothesis through OOS, shadow/paper and later
  separately authorized execution gates;
- see current candidates, open positions, financial result, data health and
  problems from one owner-facing pulse.

## Core operating loop

```text
observation / data mining / AI-assisted exploration
→ hypothesis family and immutable version
→ mechanism, falsifier and regime statement
→ hypothesis-owned data requirement
→ historical dataset plus controls
→ retrospective test and cheap kill
→ OOS / walk-forward / robustness
→ shadow or paper pilot
→ frozen strategy version
→ monitored activation epoch
→ pause / dormant / retire / reformulate / reactivate
```

A hypothesis is not a strategy, a watchlist or a position. These are linked
but separately versioned entities.

## Entity ownership

The minimum stable entities are:

- `research_cycle`: one bounded exploration question;
- `hypothesis_family`: the persistent economic or behavioral mechanism;
- `hypothesis_version`: immutable rules, features, labels and falsifier;
- `hypothesis_origin`: immutable provenance of how a candidate was obtained;
- `hypothesis_derivation_edge`: parent-child link and transformation rationale;
- `trial`: one dataset/window/method/result;
- `research_artifact`: content-addressed input, method, output or conclusion;
- `hypothesis_data_requirement`: fields, population, controls and acquisition;
- `watchlist_membership`: hypothesis-owned candidate evaluation;
- `strategy_version`: frozen entry, monitoring and exit rules;
- `activation_epoch`: one regime-bound period in which a strategy is enabled;
- `position`: one triggered entry-through-exit lifecycle;
- `tool_capability`: validated analytical capability and its data interface;
- `regime_observation`: point-in-time market/context state;
- `decision_event`: append-only accept/reject/pause/reactivate evidence.

One token may appear in several hypothesis watchlists. Each membership retains
its own rule version and reason. A dormant hypothesis may be revalidated later
when liquidity, volatility, attention or another named regime changes. The new
epoch never rewrites the old trial or activation result.

## Hypothesis provenance and research memory

Every `hypothesis_version` has an append-only provenance chain regardless of
whether it came from an owner observation, data analysis, AI hypothesis
mining, external research, a tool or framework, or an existing hypothesis.
Origin prestige never substitutes for evidence.

The minimum chain records:

- origin kind, originating actor or system, observed/created time, source
  references and the initial observation or question;
- mechanism, falsifier, expected regime and links to parent hypotheses or
  trials when the idea is derived;
- exact tool capability, model/tool version and sanitized prompt, query,
  notebook, code, configuration or parameter artifacts needed to reproduce
  generation or analysis;
- dataset asset IDs and immutable snapshots, population, controls, exclusions,
  event/availability cutoffs and point-in-time lineage;
- test design, estimand, search budget, metrics, costs, assumptions and known
  limitations;
- results with uncertainty, anomalies and failed, negative or inconclusive
  outcomes rather than only promoted winners;
- conclusion, decision rationale, reviewer/owner, decision time and the exact
  evidence that caused reject, revise, promote, pause, retire or reactivate;
- child insights and hypotheses with an explicit statement of what was reused,
  contradicted or newly inferred.

History is append-only. Corrections and changed conclusions create a new
version or `decision_event` with `supersedes` links; they never overwrite the
reasoning that was available at an earlier decision time. Sensitive or noisy
raw conversation is not stored by default: the record keeps the minimum
sanitized reproducible artifact or its content hash and governed location.

Before opening a new research cycle, the factory queries this memory for
semantic duplicates, related mechanisms, reused datasets, prior falsifiers and
regime-dependent failures. Similarity does not automatically reject an idea:
the new cycle must state what changed and why repeating or extending the work
has information value. This both prevents accidental repetition and turns
negative history into input for derivative insights.

## Research and tool routing

The factory must not route work by brand name or novelty. Each research atom
starts with a problem contract:

```text
question
estimand
population and controls
available data
required output
error cost
time / money / privacy cap
validation owner
```

An existing tool is preferred when its capability record proves:

- accepted input schemas and point-in-time semantics;
- supported analytical methods and known limitations;
- deterministic or calibrated output contract;
- validation status and evidence;
- cost, latency, privacy and reproducibility boundary;
- named output consumer.

Examples include SQL/Python statistics, notebooks, data-quality checks,
visualization, time-series and regime analysis, causal or event-study methods,
LLM-assisted document/news extraction and AI-assisted pattern generation.
These are capability classes, not preapproved conclusions.

A new tool is added only when a named research question exposes a material
capability gap that cannot be closed by data preparation, composition or a
validated existing tool. Tool adoption never bypasses statistical validation.

## Data operating model

Data acquisition follows `CONTRACT-T15-BOUNDED-SUSTAINED-COLLECTION-001`:

```text
thin online decision ledger
→ historical batch first
→ reusable content-addressed cache
→ hypothesis-specific dataset
→ triggered live capture only for non-reconstructable evidence
```

Pattern discovery may use a bounded broad historical universe. Hypothesis
validation must also include rejected candidates or explicit controls; a
winner-only or selected-candidate-only dataset is invalid.

Every derived feature and label retains source revision, event/availability
times, code/config version and lineage. Historical hydration cannot pretend
that reconstructed data was available to a strategy earlier.

## Validation and promotion

A backtest is evidence, not promotion. The minimum research discipline is:

- mechanism and falsifier before parameter search;
- PIT-safe features and labels;
- transaction-cost and route/execution assumptions;
- selection/survivorship and missing-data accounting;
- train/validation/OOS or walk-forward separation;
- multiple-testing/search-budget accounting;
- regime and sensitivity analysis;
- negative and inconclusive results retained;
- frozen version before shadow/paper evaluation.

Promotion depends on evidence quality and net-of-cost economics, not a single
headline metric. Live degradation, data drift, capacity, execution quality and
regime mismatch can pause an otherwise valid strategy.

## Execution bridge and position truth

A validated hypothesis produces profit or loss only through a separately
versioned execution bridge. The intended causal and audit chain is:

```text
hypothesis_version
→ frozen strategy_version and activation_epoch
→ watchlist_membership and trigger_event
→ signal_decision and pre-trade risk snapshot
→ execution_intent
→ quote / route / simulation evidence
→ execution_attempt and observed settlement
→ position events and exit decisions
→ inventory reconciliation
→ NetReturn and realized owner cashflow
→ strategy degradation and hypothesis feedback
```

A trigger is not an order, an order is not a fill, and a successful entry is
not profit. Risk, stale-data, no-route, capacity, duplicate-send and unresolved
inventory vetoes remain active between every arrow.

Every position must retain stable links to the hypothesis/version, trial,
strategy version, activation epoch, watchlist reason, trigger, signal,
execution attempts and exit rationale that created it. Intended, submitted,
landed, filled, partially filled, unresolved, recovered and closed facts cannot
be collapsed into one boolean. When several hypotheses target the same mint,
logical attribution stays separate while an account-level risk view aggregates
net exposure; netting must not erase which hypothesis created the risk or PnL.

The project owns the semantics and truth of:

- strategy and trigger versions;
- capital allocation, exposure, daily-loss and kill-switch policy;
- idempotency and duplicate-send protection;
- position, inventory and reconciliation state;
- actual fees, fills, settlement and net owner cashflow;
- evidence lineage, incidents, decisions and recovery.

It does not have to build every transport primitive. DEX aggregation,
transaction construction/simulation, submission transport, RPC adapters,
custody interfaces and monitoring backends may be adopted or wrapped when a
current `ADOPT → WRAP → FORK → BUILD` gate proves fit, maintenance, license,
supply-chain, signer isolation, observability, rollback and total-cost
advantages. A third-party bot or router never becomes the owner of hypothesis,
risk, position or cashflow truth.

Backtest, replay, paper, shadow and live modes should share the same strategy,
feature, decision and position interfaces. Mode-specific approximations are
explicit evidence, not hidden branches. Promotion to a mode with more authority
requires the previous mode's versioned results and a separately accepted gate.

Monitoring is a precondition for live authority, not a dashboard added later.
Before any unattended or real-money activation, the owner must be able to see
and alert on:

- input freshness, clock/feature lag and trigger-to-decision latency;
- quote age, route availability, simulation and submission disposition;
- landing/finality, actual fills, fees and reconciliation age;
- open, partial, pending-exit and unresolved inventory;
- gross/net PnL, drawdown, exposure, capacity and daily-loss headroom;
- process/provider/signer health and the last proven safe state;
- kill-switch state, incident owner, recovery action and decision deadline.

A process that is alive while its data, signer, reconciliation or exit path is
stale is unhealthy. Restart after an unknown transaction state fails closed:
reconcile first, then decide whether another action is allowed. Monitoring loss
with open or unresolved inventory pauses new entries and escalates recovery; it
never silently widens risk.

## Owner pulse and future interface

The future dashboard is a read model over accepted registries and evidence. It
does not become a second truth owner or gain trading authority.

The minimum owner pulse should answer:

1. Which hypotheses are exploring, validating, piloting, active, degraded,
   dormant, retired or awaiting a decision?
2. Which tokens are currently evaluated or watched, under which hypothesis and
   why?
3. Which positions are open, what strategy/epoch opened them, what is their
   risk/exit state and data freshness?
4. What is gross and net financial result after trading and infrastructure
   costs, with realized and hypothetical results separated?
5. Which datasets/providers/tools are stale, incomplete, failing, expensive or
   blocking a named consumer?
6. Which alerts or owner decisions need attention now?
7. Where did a hypothesis come from, what was already tried, what was learned,
   and which later insights derive from it?

Useful views include:

- hypothesis funnel, trial queue and evidence quality;
- hypothesis-specific watchlists and decision reasons;
- open-position lifecycle and exit readiness;
- realized owner cashflow, drawdown, costs and capacity;
- regime/decay monitoring and revalidation candidates;
- provider/data freshness, gaps, credits and storage;
- research-tool availability, validation and current blockers.

The interface may start as generated text/CLI/SQL views before any web UI. A
dashboard is justified only when the stable read contracts exist and repeated
operator questions prove its information value.

## Human, AI and automation boundary

The owner supplies goals, observations, constraints and final high-impact
decisions. AI may propose questions, mechanisms, features, research routes,
tests and interpretations, but must expose evidence, uncertainty and
falsifiers.

Automation can later maintain datasets, run accepted trials, monitor drift and
surface actions. It cannot silently change a hypothesis definition, consume a
holdout twice, activate a strategy, widen capital, buy infrastructure or send
a transaction without the applicable accepted gate.

## Factory leverage invariant

The factory earns its name only when comparable new hypotheses become cheaper
to evaluate as reusable capabilities accumulate. The default path for a
hypothesis already covered by existing Factory capabilities is a versioned
definition, configuration, data/query composition and trial; it does not need
a product-code modification.

A Git/code/deploy cycle is justified only by a named reusable capability gap,
a defect, a safety or reliability requirement, or a measured scale bottleneck.
When comparable work repeatedly requires hypothesis-specific product code, that
is an architecture warning. Before replicating the pattern, the existing
Factory Fit review must name the reusable gap and the next real consumer. The
review is a trigger for reasoning and correction, not an automatic block or a
second control plane.

## Factory Fit Gate before completion

A green test suite proves implementation consistency, not product direction.
Every future canonical task therefore receives one adversarial
`FACTORY_FIT_REVIEW` after technical DoD and before its completion/Project
Sources bundle. The gate is mandatory; only its depth varies.

The review binds to the exact candidate inventory and asks:

1. **Mission and consumer:** does the result shorten or protect a named
   hypothesis-to-cashflow decision, or is it infrastructure without demand?
2. **Flexibility, reuse and leverage:** can a new hypothesis, field, provider,
   cadence or regime be added without editing unrelated components? Could the
   next comparable hypothesis run through existing Factory capabilities without
   product-code modification? If not, which reusable capability gap is closed
   and who is the next real consumer?
3. **Compatibility and history:** are migrations, PIT, lineage, cache reuse,
   old evidence and forward-only evolution preserved?
4. **Efficiency:** was the cheapest falsifier used; are storage, calls,
   credits, operator attention and validation proportional to information
   gain?
5. **Research truth and memory:** where relevant, can another analyst
   reconstruct origin, tools, data, methods, negative results, OOS/walk-forward,
   search budget, regime dependence, decisions and derivative links?
6. **Operability:** can the owner see freshness, failures, cost, recovery and
   decision state without creating a second truth owner?
7. **Safety and authority:** did the result accidentally widen provider,
   deployment, account, wallet, transaction or real-money authority?
8. **Red team:** what breaks with ten times more hypotheses, a disappearing
   historical source, overlapping watchlists, hypothesis reactivation, a stale
   dashboard or a persuasive but invalid AI/tool result?

Each relevant dimension must cite repository or canonical evidence. An
irrelevant dimension is marked `NOT_APPLICABLE` with a reason; it does not
generate boilerplate.

Routine bounded tasks use `FAST_PATH`: mission/consumer, contradiction,
compatibility, proportionality and authority are checked compactly. Tasks that
change architecture, data semantics, research validity, execution, money,
security or the control plane use `FULL_REVIEW` and all applicable dimensions.
The owning control plane cannot skip the gate by classifying a task as routine.

The only verdicts are:

- `FACTORY_FIT_PASS` — proceed to the completion bundle;
- `FACTORY_FIT_PATCH_REQUIRED` — repair inside the same task, revalidate and
  rerun the review;
- `FACTORY_FIT_REPLAN_REQUIRED` — stop before the bundle and change the task
  contract or roadmap.

The review may retain at most one bounded follow-up candidate. It must not turn
speculative improvements into a refactoring queue.

The owning control plane performs the structured review. A separate critic or
stronger reasoning surface is used only when an irreversible or statistically
high-risk decision materially benefits from independent challenge.

## Roadmap implications

After TASK-15 repository acceptance, canonical roadmap/state/source
reconciliation should preserve these future capability owners:

- hypothesis/trial/activation lifecycle schema capable of dormant and
  reactivation epochs;
- append-only hypothesis provenance, derivation and research-artifact ledger
  with a bounded prior-work query before a new trial;
- versioned trigger-to-cashflow execution bridge with position attribution,
  account-level risk aggregation, reconciliation and hypothesis feedback;
- shared replay/paper/shadow/live interfaces plus an `ADOPT → WRAP → FORK →
  BUILD` gate for replaceable execution plumbing;
- mandatory monitoring, kill-switch, incident and recovery evidence before
  unattended or real-money activation;
- hypothesis data-requirement and watchlist ownership contracts;
- analytical tool-capability registry and research router;
- reproducible dataset builder and cached historical hydration;
- OOS/walk-forward/multiple-testing/regime evidence contracts;
- owner-pulse read models, monitoring and later interface;
- position lifecycle and net owner-cashflow views;
- bounded live acquisition only for proven non-reconstructable needs.
- mandatory `FACTORY_FIT_REVIEW` after technical DoD and before every future
  task's completion bundle, with `FAST_PATH` and `FULL_REVIEW` depths;
- reconciliation of that gate into the canonical Operating System, roadmap and
  `finish-solana-task` workflow so new threads cannot omit it.

This list is an architectural dependency map, not an instruction to create all
components immediately. Roadmap order remains consumer-driven and uses the
cheapest falsifier before implementation.

## Current boundary

This intent records accepted direction only. It implements no dashboard,
research platform, model, tool registry, watchlist engine, collector, strategy,
bot, position manager, provider call, deployment, wallet or transaction.

TASK-15 A3 may register and validate this intent. Canonical Project Sources and
roadmap versions change only through their later controlled reconciliation and
activation workflow.
