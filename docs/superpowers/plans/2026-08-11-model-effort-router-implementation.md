# Model Effort Router v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make model/effort advice deterministic at complex-work entry and at the finish-to-next-approval boundary, with `LUNA_MAX` as the implementation default.

**Architecture:** Keep the detailed selection rubric in the existing `start-solana-task` router, add thin mandatory entry/finish hooks, and mirror only the invariant in repository `AGENTS.md` and a versioned cloud Project Instruction candidate. Reuse the existing owner-attention policy test and Catalog/generator pipeline; add no new skill, registry, dependency, or Project Source.

**Tech Stack:** Markdown skill contracts, repository policy Markdown, Python `unittest`, YAML Project Asset Catalog, existing Catalog generator and locked repository validator.

## Global Constraints

- Recommendations are exactly `LUNA_MAX`, `SOL_XHIGH`, `SOL_MAX`, `TERRA_XHIGH`, or `ROUTINE_NO_SWITCH`; unknown next scope uses `DEFERRED` only in `NEXT_MODEL_EFFORT`.
- One uninterrupted autonomous chain is routed by its hardest material segment.
- Emit advice only at complex-work entry or after a material finish immediately before the next approval/handoff; deduplicate an unchanged recommendation for the same scope.
- Advice is not an authority gate and grants no provider, spend, repository-setting, wallet, signer, transaction, or canonical-status authority.
- Do not encode volatile prices, credit multipliers, benchmark scores, or assumed UI availability.
- Project Instruction v3.5 is a candidate outside Project Sources; Git delivery does not prove UI activation.
- Preserve all unrelated TASK-30 files and the stale primary checkout.

---

### Task 1: Repository policy and cloud candidate

**Files:**
- Modify: `AGENTS.md`
- Create: `docs/agent/PROJECT_INSTRUCTION_V3_5.md`
- Modify: `tests/test_owner_attention_gate_policy.py`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Regenerate: `docs/PROJECT_MAP.md`
- Regenerate: `catalog/generated/asset_edges.json`

**Interfaces:**
- Consumes: the accepted five-value routing policy and existing `OWNER_ATTENTION_GATE`/Catalog contracts.
- Produces: repository invariant `MODEL_EFFORT_ROUTER`, UI-safe Project Instruction v3.5 candidate, and machine checks that fail if either surface drops required enums or timing.

- [ ] **Step 1: Extend the existing policy test so the unimplemented candidate fails**

Update `test_project_instruction_candidate_is_ui_safe_and_policy_aligned` to read `PROJECT_INSTRUCTION_V3_5.md`, require the v3.5 header, retain all owner-attention assertions, and require all five routing enums plus `MODEL_EFFORT_RECOMMENDATION`, `NEXT_MODEL_EFFORT`, and `hardest material segment` in the relevant repository surfaces. Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_owner_attention_gate_policy -v
```

Expected: FAIL because `PROJECT_INSTRUCTION_V3_5.md` and the repository invariant do not yet exist.

- [ ] **Step 2: Add the minimum policy surfaces**

Add `## MODEL_EFFORT_ROUTER` to `AGENTS.md` with these exact output shapes:

```text
MODEL_EFFORT_RECOMMENDATION=<enum>; scope=<exact atom or chain>; reason=<one sentence>; escalation=<one trigger>
NEXT_MODEL_EFFORT=<enum or DEFERRED>; scope=<exact next atom or chain>; reason=<one sentence>; escalation=<one trigger>
```

Create `PROJECT_INSTRUCTION_V3_5.md` from v3.4, change only the version header and add the compact equivalent. Keep `len(text) <= 8000`.

- [ ] **Step 3: Make Catalog ownership exact**

Update `CTRL-AGENTS-001` and `TEST-OWNER-ATTENTION-GATE-001` record versions, purposes, dates, and SHA-256 values. Mark `PROJECT-INSTRUCTION-CANDIDATE-3-4-001` `DEPRECATED` with `superseded_by -> PROJECT-INSTRUCTION-CANDIDATE-3-5-001`; add the v3.5 `PROPOSED` asset with exact path/hash and existing control-plane consumers. Increment the manifest asset checkpoint from 713 to 714, then regenerate Catalog consumers with:

```powershell
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
```

- [ ] **Step 4: Run targeted repository validation**

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_owner_attention_gate_policy -v
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
git diff --check
```

Expected: all commands PASS; no Project Sources, TASK-30 product code, provider, wallet, or transaction files change.

- [ ] **Step 5: Commit the repository implementation**

```powershell
git add -- AGENTS.md docs/agent/PROJECT_INSTRUCTION_V3_5.md tests/test_owner_attention_gate_policy.py catalog/assets/core.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml docs/PROJECT_MAP.md catalog/generated/asset_edges.json docs/superpowers/plans/2026-08-11-model-effort-router-implementation.md
git commit -m "feat: route model effort at task boundaries"
```

### Task 2: Personal start/finish skill enforcement

**Files:**
- Modify: `C:\Users\lance\.codex\skills\start-solana-task\SKILL.md`
- Modify: `C:\Users\lance\.codex\skills\start-solana-task\references\router-v3.md`
- Modify: `C:\Users\lance\.codex\skills\finish-solana-task\SKILL.md`

**Interfaces:**
- Consumes: the accepted routing policy and finish-side carry-forward tuple `(scope, recommendation, reason, escalation)`.
- Produces: mandatory Entry Gate `MODEL_EFFORT_RECOMMENDATION`, mandatory finish-side `NEXT_MODEL_EFFORT`, and exact carry-forward/dedup behavior.

- [ ] **Step 1: Prove the old silent-baseline behavior is present**

```powershell
rg -n "NO_REASONING_CHANGE|usual GPT Sol baseline|stay silent|считай его.*Sol" C:\Users\lance\.codex\skills\start-solana-task
```

Expected: at least one match in `SKILL.md` and one in `references/router-v3.md`.

- [ ] **Step 2: Replace the old adequacy advice in the start skill and router**

Replace the `Sol HIGH` baseline and silence-on-default rule with the five-value policy, hardest-segment chain rule, exact line shape, carry-forward dedup, material-boundary recomputation, unavailable-model fallback, and authority non-claim. Add router changelog v3.7.

- [ ] **Step 3: Add the finish-side handoff contract**

Require `NEXT_MODEL_EFFORT` after the current material checkpoint and immediately before the next approval/handoff. Pass an unchanged tuple into auto-chain so `start-solana-task` does not repeat it; emit `DEFERRED` only when canonical selection has not identified the next scope.

- [ ] **Step 4: Validate both skills and semantic parity**

```powershell
uv run --with pyyaml python -X utf8 C:\Users\lance\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\lance\.codex\skills\start-solana-task
uv run --with pyyaml python -X utf8 C:\Users\lance\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\lance\.codex\skills\finish-solana-task
rg -n "LUNA_MAX|SOL_XHIGH|SOL_MAX|TERRA_XHIGH|ROUTINE_NO_SWITCH|MODEL_EFFORT_RECOMMENDATION|NEXT_MODEL_EFFORT|hardest material segment" C:\Users\lance\.codex\skills\start-solana-task C:\Users\lance\.codex\skills\finish-solana-task
```

Expected: both validators PASS; all required routing tokens and boundary labels are present; old silent-baseline language is absent.

### Task 3: Exact delivery and activation boundary

**Files:**
- Verify only: exact repository diff and ignored local preflight receipt.
- External user-only target after merge: ChatGPT Project Instruction UI field.

**Interfaces:**
- Consumes: committed repository candidate, locally validated personal skills, and standing `LOCAL_WORK_CODEX` delivery authority.
- Produces: exact PR/CI/main receipts and one bounded UI replacement instruction; no Source activation claim.

- [ ] **Step 1: Inspect the exact candidate and run the one local full-gate owner**

```powershell
git status --short
git diff origin/main...HEAD --name-only
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: tracked-only gate PASS on the exact committed candidate; receipt remains ignored under `local/delivery_preflight/`.

- [ ] **Step 2: Push, create one PR, and read exact-head CI**

```powershell
git push -u origin ctrl/model-effort-router-v1
gh pr create --repo lancerbeta/solana-alpha-lab --base main --head ctrl/model-effort-router-v1 --title "feat: make model effort routing deterministic" --body "Adds deterministic Luna/Sol effort recommendations at task boundaries, a v3.5 Project Instruction candidate, and fail-closed policy checks. No provider, wallet, transaction, spend, dependency, or Project Sources changes."
$prNumber = gh pr view ctrl/model-effort-router-v1 --repo lancerbeta/solana-alpha-lab --json number --jq '.number'
gh pr checks $prNumber --repo lancerbeta/solana-alpha-lab --watch
```

Expected: PR exact head equals local committed candidate and all required checks PASS.

- [ ] **Step 3: Apply the exact-head machine gate and merge autonomously if PASS**

Verify scope, targeted/full checks, Catalog/generator integrity, secret scan, review, mergeability, and exact PR head. If every repository precondition returns `AUTONOMOUS_AFTER_MACHINE_GATE`, merge normally, preserve the branch/settings, and read back exact main plus post-merge main CI. Any failed machine evidence returns `DENY`, not an approval request.

- [ ] **Step 4: Return the single owner-only activation action**

Provide the exact merged `PROJECT_INSTRUCTION_V3_5.md` bytes for replacement in the ChatGPT Project Instruction field and request `PROJECT_INSTRUCTION_V3_5_SMOKE=PASS`. Until that receipt, report `UI_ACTIVATION_PENDING` and do not claim cloud coverage active.
