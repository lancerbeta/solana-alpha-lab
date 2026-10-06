---
name: hypothesis-forge
description: Manual Hypothesis Forge for Solana Alpha Lab under MANUAL_FALLBACK_UNTIL_GENERATOR. Use only when the owner explicitly invokes /hypothesis-forge. Runs executable preflight → forge-run → freeze → isolated Critic → optional revise/classify → finalize. No Git mutation, provider calls, experiment execution or autonomous generator.
---

# Hypothesis Forge

Use **only** when the owner explicitly invokes `/hypothesis-forge`. Do not run Forge
from orientation, autonomous delivery, or implicit continuation phrases.

Manual hypothesis synthesis contour for Solana Alpha Lab while
`MANUAL_FALLBACK_UNTIL_GENERATOR` remains active. Prompt version `HFIC-V1.2`
(new sessions). Historical `HFIC-V1.1` drafts/receipts remain readable.
V1.2 adds deterministic feature grounding, typed unresolved requirements,
diagnostics-only `structural_signature_v1_sha256` (not HFIC-CAND identity),
and read-only `diagnostics --last N` (1..20).

## Ordinary operation

A short owner request is an `ORDINARY_OPERATION_V1` row in the ResearchStore,
not a new journal and not a repair continuation. Read state with ordinary
`forge-run --no-write` for that focus. `PAUSED_CAP` means the question was
saved and the owner cap is spent. Its next step is
`ordinary_operation.next_action`, not a replacement of the run's
`next_action`. A blocked readback and a frozen scientific terminal keep
their own `next_action`. Do not emit `NO_WORTHY` or `WAIT_FOR_NEW_EVIDENCE`
for that pause. A `STOPPED` operation
or a real `CLOSED` repair slot is not reopened by a restart.
A temporal `discovery-execute` and a stored preview require that operation;
omitting it does not bypass the cap. A new Forge run also requires the
active ResearchStore research-universe profile (`universe-policy-status`).
Absence is `UNIVERSE_POLICY_REQUIRED`, not an unfiltered search. Change the
two minima with `universe-policy-preview` then `universe-policy-apply
--confirm-append-only`. Do not put the live minima in Git. Replay uses the
recipe snapshot, not today's profile. Apply waits until no Forge operation
is effectively `OPEN` (`blocking_operations` names each one). A
`SCIENTIFIC_TERMINAL` operation completes from its own persisted owner-final:
at the run owner-final, run `forge-run --persist` for that focus. An
unneeded or stuck operation is stopped only by exact id with
`operation-stop-preview` then `operation-stop --confirm-append-only`; a stop
is not a scientific result and returns no quota. Contract:
`docs/contracts/forge_ordinary_operation_lifecycle_v1.md`. A null owner cap is the protocol
remainder, not a silent cap of one. Coverage without values stays
`discovery-coverage`.
`next_action=CORRECT_CALCULATION_REVISION` means the saved temporal result is
internally inconsistent. It is a technical stop, not a request for more
looks. Revise that exact result with `discovery-execute ... --correct-result-ref
<ref> --correct-result-sha256 <hash>` on the same spec and input. This writes
one `CALCULATION_REVISION` with `new_look=false` and spends no MAIN. Then read
the saved question again.

Temporal V5 carries `descriptive_readout` beside the full persisted result.
Use that same machine block for Prompt A, Critic and owner: compare matched
with baseline, support/missingness, event frequency, ES10 and loss
concentration. Equal medians alone do not falsify a tail/veto question.
Legacy V1–V4 replay without computation and explicitly report unavailable
tails. An exact coherent closed V4 may receive an owner-authorized
readout-only `discovery-execute --correct-result-ref <ref>
--correct-result-sha256 <hash>` on its saved spec/input/operation and current
market. Reason is `DOWNSIDE_READOUT_ADDED`; no new look, slot reopening,
freeze, assessment or budget. Exact retry reads the saved revision without
evaluation/writes. Historical terminal stays source-bound; reassessment is
separate. Contract: `docs/contracts/forge_downside_descriptive_v1.md`.

After reading a saved result or finishing a bounded pre-values synthesis
inside this authorized run, record its authored assessment with
`disposition-record --input <packet>` (normal path, not a backfill; see
Authority for when a write is allowed). An unwritten assessment stays `NOT_RECORDED`;
do not invent a non-candidate, session or `NO_WORTHY`. `forge-run --no-write`
shows `scientific_context` as advice beside, never instead of, the machine
`next_action`; it opens, closes and budgets nothing. Contract, packet shape and
statuses: `docs/contracts/hfic_scientific_disposition_continuity_v1.md`;
detail: `disposition-show --owner-focus <FOCUS>`.

Canonical entrypoint: `scripts/hypothesis_forge.py`.
No-write state-only coverage, never selecting `typed_value` and never reserving a slot:

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-coverage --format json
```
Operator-executable prefix:
`uv run --locked --managed-python python -B scripts/hypothesis_forge.py`.
Required interpreter: CPython `3.13.14`. Do not invoke a bare workstation `python`.

## Raw composite recipes

Current fresh recipe owner: `docs/contracts/forge_composite_feature_recipes_v1.md`.
Before selecting a discovery query, read actual ordinary preflight
`forge_context_packet.temporal_recipe_capabilities`. Holder count supports
`point_value`, `delta` and `return_ratio`; the two transforms require explicit
field/start/end with bound start < end <= decision. Delta is holder count;
return is a dimensionless fraction (1 = +100%) and needs a positive base.
No EWM, generic holder ratio, holder target or interpolation exists. Missing,
late, conflicting, boolean/nonfinite and invalid-lineage cells are unavailable.

Mechanism -> smallest supported representation -> authorized feature-only
support if needed -> exact query. Holder growth alone can be SIMPLE; holder
growth with an independent price/liquidity mechanism can be COMPOUND_FIRST.
Usually 1–3 meaningful predicates suffice. A raw-holder mixed preview (holder delta/return_ratio) keeps all
declared features and reports full joint support on decision eligibility before
24 examples. Universe PASS alone is insufficient: decision price is required.
Support does not prove variance, precision, independence or alpha. A changed
seed spends exposure; do not sweep windows/thresholds/components.

Without raw holder dynamics, preview keeps the historical point_value-only projection; no full joint prefix support claim. An accepted temporal capability can ground a raw candidate with required_feature_ids=[] and unresolved_requirements=[], but exact computed grounded_evidence remains mandatory at freeze. Capability binding grants no authority; GROUNDED does not imply scientific acceptance.

For bound H>=50, only H>=3 is a typed non-discriminating refusal, and H<50 is
impossible. H>=50 AND delta(H)>0 proceeds with a redundant-conjunct warning;
keep the exact spec/hash. Earlier points and unknown equivalence are not proven
tautologies. Saved readback/correction uses frozen identity/policy before this
fresh guard; STOPPED/COMPLETED cannot admit a new look. A cold saved support
readback loads zero values; registered numerical replay performs the evaluator.
Legacy missing support detail is explicit, never reconstructed silently.

After outcomes, changes in operator/window/threshold/component retain existing
adaptive/new-question accounting. Related holder prior is not exact closure of
a new dynamics recipe; renaming an exact old question does not reopen it.
Preserve exposure, prior applicability and resource permission separately.
The atom's synthetic evidence grants no real MAIN/adaptive or live mutations.

## List-aware questions (episodes)

Owner contract: `docs/contracts/forge_list_aware_research_scope_v1.md`. For
`OPPORTUNITY_EPISODES` read `forge_context_packet.list_dimension_context` before
choosing a candidate: it names the lists, their `TRUE/FALSE/UNKNOWN` coverage, the
overlap counts and the selector grammar. Lists are a research dimension with three
roles: the universe a mechanism is studied in, a signal of their own, or a fixed
diagnostic slice. `witness_source_id` is not membership.

- A list-only idea is first class: `hypothesis_kind=LIST_CONTRAST`, `list_condition`
  and no numeric predicate (query 1.2). Never add a fake price predicate to satisfy a
  validator. `NUMERIC_IN_SCOPE` studies a numeric mechanism inside a list universe;
  `MIXED_LIST_NUMERIC` combines both.
- Resolve names with `hypothesis_forge.py research-scope-resolve --spec <draft>`
  (reads no market value). It returns the canonical query, its rule digest and the
  coverage counts. `UNKNOWN` membership is never `FALSE`: the run refuses before
  values unless a covered scope (`evidence_selection.cohort_ids`) is declared first.
- Say `exactly two` or `at least two` for "two of three"; never use "all lists" in a
  frozen recipe; one membership claim never proves interaction or causality.
- The candidate card must echo `research_scope_rule_sha256` and
  `research_scope_statement` from `temporal_holder_claim_identity`; the Critic judges
  the card against that machine statement and the per-side support and attrition.
- Own lists: `hypothesis_forge.py list-snapshot-register --snapshot <json>`; a list
  registered today is not historically known before today.
- Episode normalized view: after a BASE `NO_WORTHY_HYPOTHESIS` (or an explicit owner
  request) `forge-run` may return `START/RESUME_NORMALIZED_TRAJECTORY_EPISODES_V1`.
  Build it with `hypothesis_forge.py episode-normalized-view --spec <draft>
  --parent-session-id <BASE session>`; it reads prefix points only and returns the
  `ladder_freeze_preflight` for `persist-draft --representation-id
  NORMALIZED_TRAJECTORY_EPISODES_V1`. The legacy `NORMALIZED_TRAJECTORY_V1` is not an
  episode representation and episodes have no CONTROL surface.

## Authority

Read `configs/hypothesis_forge_independent_critic_v1.yaml` and the operator pack at
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

One explicit `/hypothesis-forge` is scoped authorization for exactly one bounded
Forge **run** (`ONE_SLASH_ONE_BOUNDED_RUN`), which may contain already defined
BASE and eligible ACTIVE representation sessions. Authority expires at the run
owner-final or STOP. A single HFIC session terminal is not automatically the
owner-final of the whole search.
`ZERO_MID_CYCLE_OWNER_INTERVENTION`: do not ask the owner to press Run or
approve an RDP write between preflight, forge-run, freeze, Critic, revision/classification
and finalize. `PASS_TO_CLASSIFICATION` and exactly one bounded **primary** `REVISE_ONCE`
remain inside the original slash authority and continue automatically.
A final primary `KILL_*` continues once as isolated Critic #2 on the pre-frozen
C2 packet. C2 `REVISE_ONCE` does not auto-continue (`RUNNER_UP_REVISION_REQUIRED`).
After Prompt A `NO_WORTHY_HYPOTHESIS`, the same slash automatically runs
Prompt C (`HFIC-NEXT-V1.0`) and freeze `--next-action` without owner intervention.

Authorized without additional owner questions: read-only Git/Catalog navigation;
in general Forge, read-only active RDP navigation; preflight and safe offline
commissioning on the same canonical data root if genuinely required;
process-owned OS temp files; append-only RDP writes for context artifact,
session/cycle, all candidate versions, frozen Critic packet, Critic result,
revision receipt, classifier receipt, decisions, session receipt, next
epistemic action and terminal; one authored assessment produced by this run
via `disposition-record` (preview and read are always allowed); automatic
isolated Critic handoff; network-free deterministic lane classification;
finalize; replay/resume/`prove-runtime`; cleanup of process-owned temp files.

Scientific dispositions: the assessment record itself grants no authority and
never widens look, provider, data or experiment scope. `disposition-show` and
`disposition-record --preview` are read-only. A non-preview
`disposition-record` outside an explicitly invoked run needs an explicit
mutation/OPERATE scope. Any `HISTORICAL_IMPORT` is outside the slash cycle and
needs a separate explicit OPERATE authorization.

In `CURRENT_REPRESENTATION_CONTROL_V1`, Prompt A RDP access is limited to the
coarse `FORGE_CONTEXT_PACKET` and labels/fingerprints already in that packet —
not raw current lifecycle observation rows, parquet bodies, or trajectories.

Before proposing `PASS_CHANGE_LANE_REQUIRED`, `CAPABILITY_OPTION_READY`, a new
collector, provider adapter or infrastructure, compare the need against
`semantic_capability_entries` and `capability_entries` in
`FORGE_CONTEXT_PACKET`. Reuse or compose an accepted capability when sufficient;
state an exact named gap when missing; do not invent infrastructure under
uncertainty. Semantic entries never grant provider/data authority.

If isolated Critic context is unavailable, return typed `AUTO_HANDOFF_UNAVAILABLE`.
Do not silently self-criticize in the Forge context.

Slash does **not** authorize `apply-provenance-correction` or
`memory-policy-apply`. Read-only `inventory-placeholder-times` and
`memory-policy-status` / `memory-policy-preview` are also outside the slash
cycle. Memory-policy apply runs only after the slash ends, with
`--confirm-append-only`.

If the host platform mechanically requires command approval, request at most one
narrowly scoped batch at cycle start for
`uv run --locked --managed-python python -B scripts/hypothesis_forge.py ...`,
process-owned OS temp files, and append-only writes under the resolved canonical
RDP. Do not request broad shell/filesystem authority, a bare `python`
interpreter, unrestricted “Run Everything”, or user-level settings changes.

Hard boundaries — the slash does **not** authorize:

- Git mutation, branch, commit, PR or task creation
- Experiment execution or viewing new outcomes for ranking
- Untouched/forward holdout access
- Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash spend
- Deployment, promotion, or production strategy/bot execution
- Destructive RDP mutation, deletion, overwrite or restore
- A new capability atom
- Reopening a completed search on the same evidence+focus
- Autonomous Hypothesis Generator («magic ball»)

For `PASS_FAST_LANE_READY`, stop before experiment execution.
For `PASS_CHANGE_LANE_REQUIRED`, return one PRD+SSD and stop; do not create the PR.
For `PASS_DATA_OPTION_REQUIRED`, return the data option and stop; do not collect.

Allowed: read-only Git/Catalog navigation, bounded prior-work query, offline
commissioning when Fast Lane proof is absent and safe, design packets.

## Executable workflow

Happy path — no owner copy/paste between the slash command and the final terminal:

1. Run `uv run --locked --managed-python python -B scripts/hypothesis_forge.py preflight --owner-focus <AUTO|text> --format json`.
   If the executing model provenance digest is available from the caller,
   pass `--model-provenance-sha256 <64-hex>`; this is a caller-supplied
   compatibility label, not an attestation that the model actually ran.
   Missing model identity remains UNKNOWN and cannot authorize completed-result
   reuse.
   For the preregistered unchanged-representation CONTROL only, add
   `--control-current-representation` so the receipt carries
   `evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1`. Do not use this
   flag for ordinary Forge. CONTROL preflight stops with
   `CONTROL_YIELD_BELOW_MIN` or `CONTROL_CORPUS_UNRESOLVABLE` before creating a
   session when the imported live corpus yield is below
   `MIN_USABLE_YIELD_ELIGIBLE` or the corpus cannot be resolved from metadata.
   Immediately print the preflight `owner_forge_input` block (`FORGE INPUT`:
   visible cohorts, active evidence set, historical calibration including
   `caveat_router` when integrity is PASS, visibility, representations,
   `forge_input_next`, `evidence_surface_mode`). Ordinary preflight
   machine-stops `OBSERVABILITY_BLOCKED` / `FORGE_VISION_INTEGRITY_BLOCKED`
   before synthesis. Do **not** skip to session `RETURN_EXISTING_SESSION` stop
   before `forge-run`. Prompt A / synthesis only when `forge-run` next is
   `START_BASE`, preflight `action` is not `STOP`, **and** `forge_runnable` is
   true. If `forge_runnable` is false (`INPUT_NOT_READY`), stop before Prompt
   A even when ordinary `action` is `START_NEW_SESSION`. Typed classes are
   `INPUT_NOT_READY` and `OBSERVABILITY_BLOCKED`. Typed `forge_input_next` is
   `WAIT_FOR_IMPORT_OR_STOP` or `STOP_OBSERVABILITY`. Ready `forge_input_next` is
   `STOP_BEFORE_SYNTHESIS` (FORGE INPUT visibility, not slash authority,
   not CONTROL next, not an observability halt). Always show
   `evidence_surface_mode` (`ordinary` when JSON is null). PIT/missingness
   `NOT_EVALUATED` is not a READY basis. Do not invent `NO_WORTHY`.
   Then resolve the bounded run (default no-write diagnostic; persist only
   when this slash continues past READY):

   If the available model-provenance digest was supplied to `preflight`, pass
   the exact same `--model-provenance-sha256 <64-hex>` to `forge-run`; omitting
   or changing it makes completed-result compatibility UNKNOWN/blocked.

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --no-write --format json --owner-focus AUTO
```
   Immediately print the `owner_readout` field (`FORGE RUN` block) as the owner
   result, including the `history:` line. An unreadable current market or
   store provenance `INVALID:` is STOP before Prompt A. Any other history
   warning stays visible and does not by itself stop the slash. Do not treat
   the raw JSON dump as the owner result. `--persist`
   records `RESEARCH_ARTIFACT` `FORGE_RUN_RECEIPT`; the readout `persisted`
   line names that kind, not a filesystem path.
   Identity (A5): `market_evidence_epoch_sha256` is the scientific admission
   key (declared datasets/cohorts/lineage). `capability_epoch_sha256` is
   protocol provenance and does **not** alone reset AUTO/distinct-focus
   budget. Docs/Git-only changes must not free a market slot. Completed
   replay is `RETURN_EXISTING` with scientific writes=0 for the same market
   + frozen representations + focus. A new cohort after a completed run is a
   new market snapshot — do not return the old PASS/NO_WORTHY as the current
   answer. Legacy sessions without market stamps are historical/unresolved
   unless exact compatibility is proven; focus-only match is insufficient.
   Branch on `forge-run` `next_action` **before** Prompt A and **before**
   session-level `RETURN_EXISTING_SESSION` stop:
   - `START_V1` auto-advances from effective BASE
     `NO_WORTHY_HYPOTHESIS` / allowed duplicate-close when V1 is eligible.
     Do **not** run ordinary Prompt A / `START_NEW_SESSION`. Print `owner_readout`
     (`status: NEXT`). Owner pastes nothing. Same slash continues V1 envelope
     construction via `consume_start_v1_envelope` on the CONTROL
     `FORGE_CONTEXT_PACKET` (no fake critic packet). Keep
     `ladder_representation_id` on the envelope only — never inject it into
     the frozen challenger schema. Marker/parent alone do
     **not** authorize freeze: embed the envelope `challenger` into
     `prepare_ladder_freeze_preflight(..., challenger=..., control_receipt=...)`
     (or re-attach after envelope); production revalidates payload/CONTROL hashes
     and sets used scope from representation `corpus_binding.cohort_id`. Compact V1
     fields are stamped onto Critic input as **CONTEXT_ONLY**. A bare `forge-run`
     without envelope may leave
     `ladder_freeze_pending_reason=LADDER_FREEZE_CHALLENGER_REQUIRED` and print
     `freeze_pending:` while `next_action` stays `START_V1` — continue envelope.
     A present-but-corrupt challenger or CONTROL bind failure is
     `OBSERVABILITY_BLOCKED` (`status: BLOCKED`, `freeze_block:`) — stop; not
     soft-pend. Do **not** freeze from a CONTROL
     packet copy with only a V1 marker. Persist a generated V1 draft with
     `persist-draft --representation-id NORMALIZED_TRAJECTORY_V1` before
     freeze; `forge-run --persist` records only the aggregate receipt and is
     not a substitute for storing draft bytes. Freeze/Critic only after a V1 candidate
     exists on that envelope (fixture stubs allowed). After freeze/finalize,
     if terminal is `PASS_TO_CLASSIFICATION`, run network-free
     `classify` then finalize — that intermediate is `RESUME_V1`, not
     owner-final. Re-run `forge-run` so the aggregate reads real V1
     session artifacts; do not inject completed stages. That is the production
     adapter for a later authorized slash, not Prompt A on market evidence and
     not the scientific V1 probe. Do **not** launch Independent Critic on empty
     BASE.
     Do not stop as if Prompt C `WAIT_FOR_NEW_EVIDENCE` were the owner-final.
     Do not ask the owner to «продолжить».
   - `RESUME_V1` resumes the saved V1 draft (`--saved-draft-sha256` /
     existing freeze identity) **or** pending classify after
     `PASS_TO_CLASSIFICATION`. Do **not** call `consume_start_v1_envelope`
     (that helper is START_V1 only).
   - `START_BASE` from a no-write diagnostic (`forge-run --no-write` or
     `forge-input --no-write`) is not slash authority. A fresh ordinary focus
     emits `ORDINARY_DISCOVERY_READY` and
     `evidence_surface_mode=ORDINARY_GROUNDED_DISCOVERY_V1`. It does **not**
     continue as CONTROL. `CONTROL_SURFACE_REQUIRED` remains only when
     `forge-run` is invoked with `--control-current-representation` and no
     CONTROL session matches; that diagnostic `next:` is
     `STOP_BEFORE_SYNTHESIS`. Do **not** launch
     `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL` from an ordinary
     diagnostic. Explicit CONTROL stays trajectory-blind. A completed CONTROL
     `KILL_*` readback is that CONTROL scope only: the readout line
     `scope_exhausted: CURRENT_REPRESENTATION_CONTROL_V1` means raw ordinary
     discovery was `NOT_RUN`. Do **not** invent a second BASE trial to switch
     mode after an ordinary PASS or pending session.
   - `RESUME_BASE` → resume the exact pending BASE stage from the saved draft;
     do not regenerate.
   - `RETURN_EXISTING_RUN` is readback; stop; no second trial.
   - `FINISH_RUNNER_UP` continues isolated Critic #2; do not start V1.
   - `OWNER_CANDIDATE` / `SEARCH_EXHAUSTED_CURRENT_EVIDENCE` /
     `NON_SCIENTIFIC_STOP` / `INPUT_NOT_READY` /
     `OBSERVABILITY_BLOCKED` → print `owner_readout`; stop (evening-final or
     blocked).
   - `KEEP_PAUSE` is a typed pause (`status: NEXT`, `owner_final` null); print
     `owner_readout` and stop — do **not** start V1 and do **not** report
     evening DONE / success. Persisted pause must not lock the run as
     completed readback; later slash re-resolves from live session state.
   - Do **not** treat a missing CONTROL surface as owner-final. Ordinary
     `START_BASE` is `ORDINARY_DISCOVERY_READY`, not `CONTROL_SURFACE_REQUIRED`.
     `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL` remains expert-only
     and is not a separate owner evening.
   Technical / visibility failures stay `OBSERVABILITY_BLOCKED`, never
   scientific `NO_WORTHY` or `SEARCH_EXHAUSTED_CURRENT_EVIDENCE`.
   A no-write diagnostic that never starts a session. Pass the same
   `--owner-focus` as preflight:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-input --no-write --format json --owner-focus AUTO
```
2. Branch on preflight `action` **only after** `forge-run` next is `START_BASE`
   or an in-session `RESUME_*` of BASE. Session `RETURN_EXISTING_SESSION` does
   **not** stop the bounded run when `forge-run` next is `START_V1`.
   - `RETURN_EXISTING_SESSION` → if `forge-run` next is `START_V1` / `RESUME_V1`,
     continue the run. Otherwise report `effective_control_terminal` when
     present, else `critic_terminal`, plus NEXT; stop. Do not treat primary C1
     `critic_terminal` as the CONTROL probe branch after F3 failover.
   - `RESUME_CRITIC` → use `critic_input_packet` from the preflight JSON
     (canonical frozen bytes); do not generate.
   - `RESUME_FINALIZE` → run finalize only.
   - `RESUME_REVISE` → `uv run --locked --managed-python python -B scripts/hypothesis_forge.py revise` (exactly one
     bounded revision), then isolated Critic again. Do not freeze a new search.
   - `RESUME_CLASSIFY` → `uv run --locked --managed-python python -B scripts/hypothesis_forge.py classify` with a
     schema-valid ExperimentSpec (network-free `classify_lane()`), then finalize.
     `PASS_TO_CLASSIFICATION` is not complete.
   - `STOP` → report the named terminal; stop.
     For `CONTROL_YIELD_BELOW_MIN`: show `control_yield_eligible` vs
     `min_usable_yield_eligible`; `OWNER NEXT=WAIT_FOR_IMPORT_OR_STOP`. Do not
     drop `--control-current-representation`. Do not recover by running general
     Forge. Do not freeze or launch Critic.
     For `CONTROL_CORPUS_UNRESOLVABLE`: `OWNER NEXT=STOP_CORPUS_UNRESOLVABLE`.
     Same recovery fence.
   - `START_NEW_SESSION` → continue only when `forge-run` next is `START_BASE`.
3. Only for `START_NEW_SESSION` on the ordinary route (no `--control-current-representation`),
   before Prompt A, resolve the published discovery binding. Do not hand-write
   `EXPLORATORY_REUSE` or `holdout=false`. The resolver admits only when the
   published labels match `REQUIRED_LABELS` and no protected holdout assignment
   is present. A stop before row values uses the command's code:
   `DISCOVERY_ROLE_UNKNOWN`, `DISCOVERY_ROLE_FORBIDDEN`,
   `DISCOVERY_ROLE_CONFLICT`, `DISCOVERY_AUTHORITY_ABSENT`,
   `HOLDOUT_PROTECTED`, `HOLDOUT_UNRESOLVED`, `DISCOVERY_IDENTITY_MISMATCH`,
   `BINDING_HASH_MISMATCH`, `DISCOVERY_ARTIFACT_MISSING`, or
   `DISCOVERY_SCOPE_UNSUPPORTED`.

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-binding --format json
```

   Then run the query. Omit `--binding`. On an authorized ordinary slash,
   pass the canonical data root as both `--data-root` and `--store`, because
   freeze checks the look in that store. Pass `--operation` with the explicit
   owner request for this journal; temporal looks refuse missing/empty/foreign
   operations before values. Do not pass a combined file when cohort hashes
   differ. An exact repeated `--cohort-partition` is eliminated; a second path
   for the same cohort stops. Copy the whole returned evidence object onto the
   draft as `grounded_evidence`. After `persist-draft`, re-run
   `preflight --discovery-contract` and freeze against that fresh receipt so a
   saved candidate can continue without a new MAIN.

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-execute --data-root <canonical-data-root> --store <canonical-data-root> --spec <spec.json> --candidate-scope <scope.json> --journal-scope <preflight-search-key-sha256> --operation <ordinary-operation.json> --format json
```

   Before persist/freeze, ordinary discovery may escalate inside the same
   journal. Tiers `SIMPLE_SCREEN` and `COMPOUND_SCREEN` are internal labels,
   not new terminals. Shared budget stays 6 main + 2 adaptive. AUTO reserves
   3 main slots for compound until compound is used. A simple screen with no
   freeze-worthy candidate escalates to compound before any
   `NO_WORTHY_HYPOTHESIS` terminal. Do not call an unused compound tier
   executed. `SKIPPED_BUDGET` and a model error are not `EXECUTED`.
   Feature-only preview:

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-preview --data-root <canonical-data-root> --store <canonical-data-root> --journal-scope <preflight-search-key-sha256> --spec <preview.json> --format json
```

   Preview has no target. Pass `--store` and `--journal-scope` together; one flag
   alone is `PREVIEW_STORE_SCOPE_REQUIRED`. A third distinct preview is
   `PREVIEW_ENVELOPE_EXHAUSTED`. `SCHEDULE_CONTEXT_UNBOUND`,
   `SCHEDULE_LATENESS_MISMATCH`,    `FROZEN_INPUT_MISMATCH`,
   `SEARCH_EXHAUSTED_WITHOUT_COMPOUND`, and `CANONICAL_X300_SCHEDULE_INCOMPATIBLE` are technical
   stops (`scientific_negative=false`), not a scientific negative. A temporal query uses schema
   `smial.hfic-temporal-query`. Relative results are
   `PRICE_RELATIVE_PROXY`. Cost output is `ESTIMATED_NET_PROXY`, never
   `NetReturn`. The frozen recipe's fixed-time consumer is
   `CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`.

   Pass `--journal-scope` as the preflight `search_key_sha256`. Copy the
   whole returned evidence object onto the draft as `grounded_evidence`.
   Do not copy only `result_refs` and do not hand-write the summary.
   A stamped ordinary receipt requires that evidence object for 0, 1, 4, and 6 candidates.
   Ordinary preflight carries `discovery_contract_version` for every
   non-CONTROL receipt. `--discovery-contract` is accepted and does not
   decide the stamp. Do not hand-write that field.
   `evidence_surface_mode` stays unset unless the run is explicit CONTROL.
   Do not invent those fields.
   CONTROL does not run this command. `discovery-binding` does not load
   values. On an authorized ordinary slash, `--data-root` and `--store` are
   both the canonical data root.
   Then run **PROMPT A** from the operator pack using
   `HFIC-V1.2` and only the bounded `FORGE_CONTEXT_PACKET` plus explicitly
   resolved evidence. In `CURRENT_REPRESENTATION_CONTROL_V1`, "explicitly
   resolved evidence" does **not** authorize reading raw current lifecycle
   observation rows, parquet observation bodies, per-mint raw trajectories,
   ordered raw lifecycle sequences, future `normalized_trajectory_v1` motifs,
   or any manually reconstructed equivalent of the challenger representation.
   CONTROL Prompt A may use the exact `FORGE_CONTEXT_PACKET`, its coarse
   dataset identities/fingerprints/labels, `feature_hints` / `feature_families`,
   `feature_grounding` projection, closed-family ledger, eligible prior memory
   under existing F2 rules, and ordinary Git/Catalog/operator truth required to
   interpret those IDs/contracts. General Forge read-only active-RDP navigation
   remains unchanged when the CONTROL flag is absent.
   Output a machine-valid `FORGE_DRAFT` with `packet_version=1.2`,
   `generator_prompt_version=HFIC-V1.2`, schema
   `catalog/schemas/hypothesis_forge_draft_v1_2.schema.json`.
   Do not emit `packet_version=1.1` or `HFIC-V1.1` on this fresh binding; freeze
   will fail closed with `FRESH_SESSION_DRAFT_VERSION_MISMATCH`.
   Copy `truth_roots_used`, `prior_work_receipts` and `research_memory_as_of` from
   preflight.    Do **not** emit `CRITIC_INPUT_PACKET`; freeze is the only packet builder.
   Prompt A search still uses only the bounded `ranked_prior_candidate_ids`
   shortlist; do not change candidate-generation strategy to recover omitted priors.
   Do **not** query prospects or include prospect IDs/research text in Prompt A.
4. Write machine `FORGE_DRAFT` to an OS temp file, then immediately persist
   those exact bytes against their source preflight before freeze:

   ```text
   uv run --locked --managed-python python -B scripts/hypothesis_forge.py persist-draft --draft <temp> --preflight-receipt <preflight-temp> --representation-id BASE --format json
   ```

   For the V1 envelope path, use the prepared representation-aware receipt and
   `--representation-id NORMALIZED_TRAJECTORY_V1`. Pass
   `--model-provenance-sha256 <64-hex>` only when that digest is actually
   supplied by the caller. The command revalidates current market/capability
   identity and atomically persists slot occupancy plus draft when the slot is
   new. One ordinary selected candidate omits `runner_up_candidate_ref` and
   `strongest_rejected_alternative`. After persist, run preflight again.
   Freeze consumes that restart receipt and the same draft bytes. The draft
   stays bound to the source preflight hash.
5. If Prompt A returned `NO_WORTHY_HYPOTHESIS`, omit `selected_candidate_ref`. Do not send `""` or null. `SEARCH_EXHAUSTED_WITHOUT_COMPOUND` means run compound before that closure:
   - query `uv run --locked --managed-python python -B scripts/hypothesis_forge.py prospects --trigger POST_NO_WORTHY_REVIEW --max-results 3 --format json`;
   - run **PROMPT C** (`HFIC-NEXT-V1.0`) from the operator pack using only the
     already-bound `FORGE_CONTEXT_PACKET`, no-worthy portfolio, terminal, and
     at most three prospect summaries;
   - write a draft matching `hfic_next_epistemic_action_draft_v1.schema.json`;
   - one schema-repair attempt; if still invalid, omit `--next-action` so freeze
     persists deterministic `WAIT_FOR_NEW_EVIDENCE` / `NEXT_ACTION_GENERATION_FALLBACK`;
   - run `uv run --locked --managed-python python -B scripts/hypothesis_forge.py freeze --draft <temp> --preflight-receipt <temp> --next-action <temp-or-omit> --format json`;
   - skip Independent Critic; do not finalize; report `NO_WORTHY_HYPOTHESIS` plus
     the typed next action. Re-run `forge-run`. If `next_action` is `START_V1`,
     continue the same slash — Prompt C `WAIT_FOR_NEW_EVIDENCE` is not the
     owner-final. Proposed owner phrases are `PROPOSED_NOT_AUTHORITY`
     and must not be executed.
6. Otherwise run `uv run --locked --managed-python python -B scripts/hypothesis_forge.py freeze --draft <temp> --preflight-receipt <temp> --format json`.
   Frozen packet is authority. One schema-repair attempt, then `HFIC_PROTOCOL_INVALID`.
   Do not pass `--next-action` on a selected-candidate path.
   Fresh HFIC-V1.2 freeze emits critic `packet_version=1.4` with
   `generator_prompt_version=HFIC-V1.2`, freeze-owned selected-candidate
   grounding, and a complete bounded `prior_memory`
   snapshot of eligible historical `HYPOTHESIS_VERSION` records from the
   preflight-bound store **before** current session persist. Do not emit
   HFIC-V1.3 Prompt A. If freeze returns
   `PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED`: BLOCKED, not a crash; session was
   not written; do not launch Critic; do not paste a packet; do not retry the
   same slash expecting success. `OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`.
   If freeze returns `PRIOR_MEMORY_RECORD_UNIDENTIFIED`: BLOCKED; session was
   not written; do not launch Critic. `OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`.
7. **Mandatory auto-handoff (selected path only):** launch Independent Critic in a new isolated context
   with only the frozen packet. Do not persist from Critic.
8. After critic returns `hypothesis_critic_result_v1`, branch on **which
   candidate this packet screened** and on `finalize` `session_state`:
   - Primary/C1 `REVISE_ONCE` only → `finalize` persists `REVISION_REQUIRED`;
     then `revise` (one claim-wording repair); then isolated Critic again;
     second terminal must be PASS/KILL, never a second `REVISE_ONCE`.
   - `PASS_TO_CLASSIFICATION` → `finalize` persists `AWAITING_CLASSIFICATION`;
     then `classify`; then finalize. This is not a completed terminal.
   - Primary/C1 `KILL_*` → `finalize`. If `session_state=RUNNER_UP_AWAITING_CRITIC`,
     do **not** emit `SYNTHESIS_COMPLETE` and do **not** mark the evening done.
     Same slash: launch Critic #2 in a **new** isolated context with **only**
     the pre-frozen C2 packet (`RESUME_CRITIC` `critic_input_packet` or freeze
     `runner_up_critic_input_packet`). Then `finalize` the C2 result.
   - C2 `REVISE_ONCE` → `finalize` persists `PAUSE` / `RUNNER_UP_REVISION_REQUIRED`.
     Do **not** run `revise`. No C3. No new search.
   - PASS/OWNER/DATA/CHANGE on C1 never launches runner-up Critic.
   Fake/nonempty classifier objects are invalid. Final `PASS_*` requires a live
   network-free classifier receipt bound to session/selected/spec hash.
9. Verify `SYNTHESIS_COMPLETE` / RDP receipt, Git mutation 0, provider calls 0
   before telling the owner the cycle is complete. If `forge-run` next is
   still `START_V1` / `RESUME_V1`, the bounded run is not evening-complete.
   At the run owner-final, record it with `forge-run --persist --owner-focus
   <FOCUS>` (idempotent); the ordinary operation then reads `COMPLETED` and
   no longer holds the research-universe profile.
10. On crash/retry, resume; never regenerate the same evidence+focus search.

## Mandatory auto-handoff (non-negotiable)

Forge is **not complete** when the packet is printed. The owner must not need to
remember step 2.

Immediately after a valid frozen `CRITIC_INPUT_PACKET` (selected path only):

1. Emit a synthesis handoff receipt with `synthesis_status: PENDING_CRITIC` per
   `catalog/schemas/hypothesis_forge_synthesis_handoff_v1_1.schema.json` (v1.0
   readers remain valid for historical fixtures).
2. **Launch Independent Critic in a new isolated context** using `Task`
   subagent, `.agents/skills/independent-hypothesis-critic/SKILL.md`, and
   **only** the packet (no Forge narrative, no intermediate reasoning, no
   ResearchStore walk). Compact V1 fields on that packet
   (`normalized_trajectory_v1` / representation hashes /
   `ladder_representation_id`), when present, are **CONTEXT_ONLY** — not an
   estimand, not a FEAT, not probe execution evidence. Fresh critic
   `packet_version=1.4` already carries complete prior memory and freeze-owned
   grounding. Do not reconstruct `prior_memory` for historical `1.2`. Do not
   reconstruct packet 1.4 grounding from Catalog/RDP. Historical
   `packet_version=1.3` remains readable.
   If isolated context cannot launch, return typed `AUTO_HANDOFF_UNAVAILABLE`
   and STOP. Do not instruct the owner to open a new chat, paste the packet,
   or press Run. Do not silently self-criticize in the Forge context.
3. Do not mark the evening cycle done, do not propose execution tasks, and do not
   treat synthesis as finished until `finalize` has persisted `SYNTHESIS_COMPLETE`.
   Primary `KILL_*` that returns `RUNNER_UP_AWAITING_CRITIC` is **not** complete:
   launch Critic #2 first. C2 `REVISE_ONCE` completes as `PAUSE` /
   `RUNNER_UP_REVISION_REQUIRED` with `OWNER NEXT=STOP` — no `revise`, no C3,
   no new AUTO search, no candidate shopping.
4. After `finalize` returns `session_state=SYNTHESIS_COMPLETE`, emit handoff with
   `synthesis_status: SYNTHESIS_COMPLETE`,
   `critic_terminal`, `critic_report_present: true`, and when the final terminal is
   post-classification (`PASS_FAST_LANE_READY`, `PASS_CHANGE_LANE_REQUIRED`,
   `PASS_DATA_OPTION_REQUIRED`): `classifier_receipt_present: true` plus
   `lane_classifier_terminal` from offline `classify_lane()`. `PASS_*` is readiness
   / `PAUSE`, never promotion or alpha. A packet-1.4 availability-gate denial is a
   persisted `KILL_UNBOUND_EVIDENCE` (`DENY_HFIC_AVAILABILITY_GATE`), not an
   exception and not `AWAITING_CLASSIFICATION`. The owner readout shows
   `route=` and `reasons=`. A Critic-claimed final `PASS_*` may be downgraded
   to that KILL; the machine never upgrades a claim.

   The v1.1 synthesis handoff schema is `additionalProperties: false` and cannot
   carry v1.3 `final_session_terminal` / `runner_up_critic_terminal`. On runner-up
   failover, read those fields from the session receipt / `show_session`, not from
   the v1.1 handoff. Legacy handoff `critic_terminal` stays the C1 primary KILL for
   v1.2 identity and is **not** the evening scientific result. Do not claim C1
   KILL as C2's outcome. Do not put C2's classifier lane on C1-bound
   `lane_classifier_terminal`.

If packet validation fails, return `STATUS=NOT_READY`, keep
`synthesis_status: FORGE_NOT_READY`, and one repair action. Do not launch critic
on an invalid packet.

## Output contract

Speak to the owner in Russian. Keep schemas, enums, packet fields and paths
canonical in English.

Never end with a conditional backlog. One execution unit maximum per cycle.
KILL/STOP is a complete useful result. Primary `KILL_*` plus pending C2 screen
is not evening-complete. C2 `RUNNER_UP_REVISION_REQUIRED` is a typed PAUSE STOP,
not a prompt to shop another candidate or start a second AUTO search.

## Representation challenger (runtime-ready, not executed)

`NORMALIZED_TRAJECTORY_V1` is a separate capability. Ordinary `/hypothesis-forge`
is unchanged and CONTROL stays trajectory-blind. The three explicit modes are:

- `ORDINARY`: existing `/hypothesis-forge` path and budget;
- `CONTROL`: `--control-current-representation`, still trajectory-blind;
- `REPRESENTATION_CHALLENGER`: a later, one-run bounded envelope built from the
  exact hash-verified CONTROL packet plus the compact anonymous representation.

The implementation boundary is `src/solana_alpha_lab/factory/normalized_trajectory_v1.py`
plus `hfic_representation_probe.py`. The read-only status surface is
`uv run --locked --managed-python python -B scripts/hypothesis_forge_representation.py representation-status --input <json>`.
It consumes a supplied snapshot and does not read current cohort values,
ResearchStore, providers, or runtime state by default.

The challenger must reuse the same evidence epoch, `HFIC-V1.2` prompt, prior
memory baseline, feature grounding, candidate constraints, and the shared
operational packet envelope (`FORGE_OPERATIONAL_PACKET_MAX_BYTES`). CONTROL
terminal `PASS_*` routes to
`MARKET_FALSIFIER_FIRST`; `RUNNER_UP_REVISION_REQUIRED` pauses; observability
or grounding failures are blocked. The adapter never runs the probe and never
creates a `FEAT-*` alias from a motif.

`RUNTIME_READY_NOT_EXECUTED` means a completed `NO_WORTHY` CONTROL plus a
verified C2 release can build a hash-bound prefix-through-T payload and
challenger envelope without a fake critic packet. It does not mean the
representation probe ran, passed, produced alpha, or changed runtime
deployment. This slash does not execute market Prompt A or the scientific
V1 probe; after `START_V1` it freeze/Critics a V1 candidate with
`ladder_freeze_preflight`, then re-runs `forge-run`.

## Post-merge CONTROL reconsideration

Not part of `/hypothesis-forge`. After merge of
`HFIC_REOPENED_PRIOR_SEARCH_ROUTING_V1`, local append-only commissioning is:

1. read-only `preview-reopened-prior-routing`;
2. `commission-reopened-priors --confirm-append-only` after the applicable
   owner gate;
3. read-only `memory-policy-preview` for
   `HFIC-SESS-8F4A703030408365` with
   `PRE_CAPABILITY_BASELINE_CALIBRATION_RESET` (must follow commissioning so
   the proposal binds the post-commission store head);
4. `memory-policy-apply --proposal proposal.json --confirm-append-only`;
5. machine readback and another `preview-reopened-prior-routing` expecting
   `CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION` (post-apply preview
   compares the defective session identity, not a pending overlay delta);
6. owner `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`.

Do not rewrite `HFIC-SESS-8F4A703030408365`. Do not invent FEAT/capability IDs.
Ordinary Prompt A packets now carry `ranked_prior_entries` one-to-one with
`ranked_prior_candidate_ids`; missing bodies fail closed as
`RANKED_PRIOR_BODY_CONTEXT_INCOMPLETE`.

## Packet capacity vs missing prior body

Ordinary Forge, representation CONTROL, and the challenger share one
operational hard cap of **65536** bytes (`FORGE_OPERATIONAL_PACKET_MAX_BYTES`)
and one growth-warning threshold of **20480** bytes
(`FORGE_PACKET_GROWTH_WARNING_BYTES`). Resolve via
`forge_context_packet_max_bytes(evidence_surface_mode)` — never from focus
text, and no longer as a mode-split byte identity. This amends the previous
16384 CONTROL freeze; it does not deny that freeze existed. Crossing 20480 warns;
it does not drop required scientific information.

`RANKED_PRIOR_BODY_CONTEXT_INCOMPLETE` means a ranked prior identity has no
decision-useful resolvable body (one-to-one Prompt A body closure failed).

`FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED` means required bodies are complete
but the operational `FORGE_CONTEXT_PACKET` hard cap cannot represent a
non-minimal Forge search context after allowed semantic/feature-grounding
compaction.

`MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND` means Prompt A already carries the
disposition-gated scientific minimum (HARD_CLOSE/PARK with scope axes from
shared `latest_hypothesis_decisions`) and the packet still cannot fit without
stripping material feature grounding. Do not quarantine, drop ranked priors,
or raise the packet limit inside a slash — return to owner.

Prompt A `ranked_prior_entries` use a Forge-specific projection
(`compact_forge_prior_entry`) wired to the same DECISION_EVENT resolver as
Critic. Critic `prior_memory` continues to use the fuller
`compact_prior_entry` / `build_prior_memory_snapshot` path.

## Model effort

Use `SOL_XHIGH` for mechanism/PIT/estimand reasoning. Critic handoff may use the
same or a different strong model; isolation matters more than model identity.
