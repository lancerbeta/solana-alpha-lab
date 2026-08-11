# Factory Leverage Invariant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make reusable-factory leverage an explicit operating and Factory Fit invariant without adding a new control system.

**Architecture:** The invariant lives in two existing owners. `AGENTS.md` makes it an operating rule at Entry and Finish Gates; `ARCH-INTENT-002` records the product rationale and the exact Factory Fit question. Both point to the existing review rather than creating a new registry, score or automated blocker.

**Tech Stack:** Markdown, repository policy validation, existing Python unittest harness, Git.

## Global Constraints

- Base: `origin/main` at `55e9984d189f41d3b54c9d5515d6e50bfa600048`.
- Modify only `AGENTS.md` and `docs/architecture/intents/ARCH-INTENT-002-hypothesis-factory-operating-model.md`; the design and this plan are already versioned planning artifacts.
- No Catalog, Project Sources, schema, dependency, provider/API/RPC/WSS, credential, scheduler, wallet, signer, transaction, cash, deploy or UI action.
- A repeated hypothesis-specific code need triggers the existing Factory Fit review; it never automatically blocks work.
- Use the existing `VALIDATION_ECONOMY` and tracked-only delivery preflight for the final committed candidate.

---

### Task 1: Add the two-surface Factory Leverage Invariant

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/architecture/intents/ARCH-INTENT-002-hypothesis-factory-operating-model.md`
- Test: `tests/test_owner_attention_gate_policy.py`

**Interfaces:**

- Consumes: the existing `CHANGE_PROTOCOL`, `VALIDATION_ECONOMY` and Factory Fit Gate in `ARCH-INTENT-002`.
- Produces: one identical operating concept for repository agents and the enduring product intent: comparable hypotheses use existing Factory capabilities by default; repeated hypothesis-specific code invokes the existing Factory Fit review and names a reusable gap plus next consumer.

- [ ] **Step 1: Inspect the policy anchors and write-set baseline**

Run:

```text
git diff -- AGENTS.md docs/architecture/intents/ARCH-INTENT-002-hypothesis-factory-operating-model.md
rg -n "CHANGE_PROTOCOL|VALIDATION_ECONOMY|Factory Fit Gate before completion|Flexibility and reuse" AGENTS.md docs/architecture/intents/ARCH-INTENT-002-hypothesis-factory-operating-model.md
```

Expected: no implementation diff yet; the anchors are found exactly once in their current owners.

- [ ] **Step 2: Add the operating rule to `AGENTS.md`**

Insert a `FACTORY_LEVERAGE_INVARIANT` subsection adjacent to the existing
change/validation policy. Its text must say all of the following:

```text
Default comparable-hypothesis path: existing capabilities + configuration/data/query + trial, with no product-code modification.
Code is justified only by a named reusable capability gap, defect, safety/reliability requirement or measured scale bottleneck.
When comparable work repeatedly requires hypothesis-specific product code, use the existing FACTORY_FIT_REVIEW before replication; name the gap and next real consumer.
The review is a trigger, not an automatic blocker or a new registry/metric/report.
```

- [ ] **Step 3: Add the enduring intent and Factory Fit question**

In `ARCH-INTENT-002`, add a `Factory leverage invariant` subsection before
the Factory Fit Gate. Add one Factory Fit question under flexibility/reuse that
requires the reviewer to answer:

```text
Could the next comparable hypothesis run through existing Factory capabilities without product-code modification? If not, which reusable capability gap is closed and who is the next real consumer?
```

State that a repeated unaccounted need for hypothesis-specific code is an
architecture warning requiring that existing review before copying the pattern,
not an automatic block.

- [ ] **Step 4: Validate the text and active policy compatibility**

Run:

```text
git diff --check
uv run --locked --managed-python python -B -m unittest tests.test_owner_attention_gate_policy -v
uv run --locked --managed-python python -B scripts/validate_ci.py
```

Expected: clean whitespace, existing owner-attention rules still pass, and the
repository gate passes without new dependencies or external actions.

- [ ] **Step 5: Inspect the exact scope and commit**

Run:

```text
git diff --name-only origin/main...HEAD
git status --short
git add AGENTS.md docs/architecture/intents/ARCH-INTENT-002-hypothesis-factory-operating-model.md
git commit -m "docs: add factory leverage invariant"
```

Expected committed implementation inventory: the two target policy files plus
the already committed design and plan; no Catalog or Project Sources change.

- [ ] **Step 6: Deliver through the ordinary repository route**

Run the tracked-only delivery preflight once for the exact committed candidate,
then use the standing GitHub transport authority for non-force push, one Draft
PR, exact-head CI read-back and the repository `OWNER_ATTENTION_GATE` before
any ordinary merge. Preserve the branch and do not claim canonical TASK-30
completion: its separate next boundary remains owner-authorized external read.
