---
name: delivery-harness
description: Use when starting, resuming, implementing, reviewing or finishing bounded repository work through the Git-native Delivery Harness, including exact context projection, owner-attention routing and guarded delivery. Do not use for orientation phrases such as го дальше, что дальше, or поднимем голову; those stay read-only until EXECUTE.
---

# Delivery Harness

Run one workflow:

`CHECK -> CONTEXT -> ENTRY/OUTCOME -> EXECUTE -> RISK-ROUTED REVIEW -> FINISH -> EXACT MERGE GATE -> READ-BACK`

## Check and context

If `.cursor/rules/10-input-routing.mdc` classifies the turn as `ORIENTATION`
or `NEITHER`, do not start this workflow.

Read `AGENTS.md`, `delivery-harness/harness.yaml` and the elected profile. Run
the deterministic check. Require one exact task contract; never discover work
by recency. Generate L0/L1 context, preserve explicit gaps and keep the route
fixed. Git is working project memory. Cloud artifacts are
`OWNER_MANAGED_OPTIONAL_EXPORT`; never request a bundle replacement or smoke.

## Entry and outcome

Freeze mission, owner decision, named consumer, cheapest falsifier, evidence
budget, non-goals and user-visible result. Choose exactly:

`SPEC_ROUTE=NONE | PRD_LITE | DESIGN_SPEC | BOTH`

Do not duplicate an existing task contract. Every substantial atom carries:

- `DECISION_DELTA`
- `UNCERTAINTY_REMOVED`
- `CAPABILITY_OR_EVIDENCE`
- `STOP`
- `NEXT`

Set `REPLAN_TRIGGER` for repeated blocker, preparatory-only output, impossible
falsifier, second provider/route pivot or budget breach. Design, spec, plan,
implementation, tests and review are phases, not automatic owner gates.

## Execute and validate

Use bounded routine autonomy without micro-approval. Apply test-first behavior
for changed behavior and the smallest targeted checks during implementation.
If a leftover space, encoded query, wrong endpoint or shape can still fail the
atom, probe and fix that on the working path before Catalog, receipts, reviews
or PR. Do not document a five-second mechanical miss.

After bootstrap the guarded merge is the sole project-bound gate executor for
an unchanged fingerprint. Generated consumers are routine
propagation; unrelated changes stay untouched.

After the first material blocker, inspect exact reusable candidates and current
official/maintained solutions before custom construction. Tool research never
widens provider, dependency, credential, spend or install authority.

## Review

Run code review for every delivery. Add goal/DoD review for a new/changed
outcome, architecture review for boundaries/contracts/schemas/security or
multiple components, owner-UX review when CLI/console/readouts/manual operator
flows change, and refactor review only after correctness with measured cost.
Launch critics in isolated context. Before architecture review, classify
`scripts/semantic_premise_review_cli.py classify`. On `SEMANTIC_PREMISE`, build a
frozen packet, run fail-closed `validate-launch`, launch the architecture critic
with packet+diff only (no implementation transcript), and bind
`packet_fingerprint_sha256=<hex>` in architecture findings. Packet independence
attests `PACKET_INFORMATION_PATH` only; launch isolation remains
`PROCESS_OBLIGATION`. Canonical independent-review evidence still uses role
`ARCHITECTURE_CRITIC` only. `SINGLE_AGENT_REVIEW_FALLBACK` is `NOT_READY` for
merge; deterministic checks remain mandatory.

## Finish and merge

Run Factory Fit, Product Horizon and capability radar. A default result is
`CAPABILITY_RADAR_NOW=NONE`; any candidate does not grant install authority.
Require `delivery_gate_ready=true`. Validation and credential-scan commands are
closed, shell-free project-profile bindings; execute them and never infer PASS
from a local receipt. Null bindings deny merge until project bootstrap fixes
them. `github_ci_bound=true` is valid only after the live PR workflow file,
event and required jobs match the base-bound owner policy. Use focused local
validation plus existing exact PR CI as the normal route; the same guard runs
tracked-only fallback once for an explicitly ineligible control/validation
change. Do not run that local full gate both before PR and at merge. First
installation alone uses the predecessor route and one pre-PR tracked-only gate.
Bind exact inventory, tests, head/tree, limitations and rollback. Push/open PR
inside routine authority (draft CI overlap is allowed). Isolated critics run on
the inventory that `bind-evidence` will hash; FAIL or later content change
requires re-review and rebind before merge-readiness. Completion evidence keys
must be exactly the gate whitelist (`required ∪ optional`); extra narrative
keys (e.g. roadmap notes) belong in the owner readout, not completion JSON.
Run `scripts/harness_sync.py bind-evidence --verify` before merge-readiness —
it fails closed on unexpected/missing completion keys and merge-gate evidence
shape (`factory_fit.mode`, independent-review roles). After cataloged script
changes, repair derived hashes with incremental sync before commit:

```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <task expected_base>
```

Bare `--apply` is recovery/full oracle only; pre-commit and CI drift lines
prefer `--base-ref` when the branch task contract is unambiguous. After exact-head CI run
`scripts/owner_attention_gate.py --merge-readiness` (no phrase, no `gh pr merge`).
STOP for one exact owner approval only when `ready_for_owner_phrase` is true.
Order: `CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`.
The owner never clicks GitHub Merge. Product work uses
`context --contract --task-id`. `context --pr` is `LIVE_PR_HEAD` only when every
changed path is inside `harness_control_write_prefixes`; otherwise
`IDENTITY_MODE_MISMATCH` (use `--contract`). Do not widen those prefixes to
admit a product write set. Task-contract merge may land drifted
`CONTROL_RUNTIME_PATHS` listed in that task `managed_write_set`; unlisted
runtime drift stays `CONTROL_RUNTIME_CHANGED`. Re-read every machine precondition, evaluate
`OWNER_ATTENTION_GATE_V2`, then perform at most one ordinary guarded merge and
read back the profile's exact default branch/post-merge CI. Use
`scripts/owner_attention_gate.py --guarded-merge` so the agent cannot supply
pre-asserted test/CI/Factory-Fit booleans.

The merge submission is not the terminal receipt. Persist its self-hashed JSON,
bind its `merge_commit` as the expected default-branch head and require
`scripts/owner_attention_gate.py --post-merge-readback --submission-receipt
<GUARDED_SUBMISSION_JSON>` to verify the ordered parents
`[frozen default-branch head, approved head]`, the exact merge commit and
successful push CI. Polling this
read-only state requires no new owner gate;
do not claim delivery complete before the hash-bound receipt exists.

Recommend `MODEL_EFFORT_RECOMMENDATION` once before a substantial chain and
`NEXT_MODEL_EFFORT` only at its material checkpoint, never on microsteps.
