# Reuse-first recovery trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require one bounded reuse-first decision after the first material, evidence-backed blocker before custom construction or route widening.

**Architecture:** Keep the behaviour in the repository's mandatory operating contract, `AGENTS.md`, rather than create another workflow, registry, service, or package.  A single static test in the established `tests/test_ci.py` contract suite protects the trigger's scope, recovery options, receipt boundary, and preservation of existing authority gates.

**Tech Stack:** Markdown policy text, Python 3.13, `unittest`, existing locked `uv` validation commands.

## Global Constraints

- Change only `AGENTS.md` and `tests/test_ci.py`; do not alter Catalog, Sources, workflows, schemas, dependencies, or runtime code.
- Insert `## REUSE_FIRST_RECOVERY_TRIGGER` immediately before `## VALIDATION_ECONOMY`.
- The trigger starts only after the first material, evidence-backed blocker; routine deterministic test failures, already-known limitations, and recoveries prescribed by an exact active gate remain outside it.
- Preserve the first result and forbid hidden retry or fallback; the rule grants no provider, dependency, cost, security, or owner-boundary change.
- Reuse evidence is deliberately bounded: consult `registries/reuse_candidates.yaml`, accepted decisions including `ADR-002`, and only the smallest useful official, OSS, or commercial alternatives for the named consumer.
- Record exactly one of `ADOPT`, `WRAP`, `FORK`, `BUILD`, or `STOP` with its cheapest falsifier.  If the current atom already emits a decision or acceptance receipt, the compact record contains only the blocker, alternatives considered, chosen outcome, and fit rationale.
- Missing, vague, stale, or conflicting external documentation yields `STOP` or explicitly unresolved; it never defaults to custom construction.  A narrow custom project-truth boundary is valid only after the other outcomes are evidenced unfit.
- No provider request, credential, wallet, transaction, raw-data action, Project Source action, or TASK-30 acceptance is part of this patch.
- Before first push of the exact committed candidate, run the one tracked-only delivery preflight required by `AGENTS.md`; do not duplicate an unchanged full gate.

---

## File Structure

- `AGENTS.md` — repository-wide operating contract that tells every future bounded atom when a proven first blocker must trigger a small reuse decision.
- `tests/test_ci.py` — static `unittest` invariant which fails if the trigger, its scope, recovery outcomes, authority preservation, or placement disappear.

### Task 1: Add and lock the reuse-first recovery trigger

**Files:**
- Modify: `AGENTS.md` — insert one policy section directly before `## VALIDATION_ECONOMY`.
- Modify: `tests/test_ci.py` — add `ReuseFirstRecoveryTriggerTests` before `ControlOnlyTaskCloseDocumentationTests`.
- Test: `tests/test_ci.py::ReuseFirstRecoveryTriggerTests.test_agents_contract_requires_reuse_first_after_material_blocker`.

**Interfaces:**
- Consumes: the approved design in `docs/superpowers/specs/2026-08-09-reuse-first-recovery-trigger-design.md`; existing `ROOT` and `unittest` conventions in `tests/test_ci.py`.
- Produces: `AGENTS.md` section `REUSE_FIRST_RECOVERY_TRIGGER`; test method `ReuseFirstRecoveryTriggerTests.test_agents_contract_requires_reuse_first_after_material_blocker()` that returns normally only when the policy contract is present and correctly placed.

- [ ] **Step 1: Write the failing static contract test**

  Add this class before `ControlOnlyTaskCloseDocumentationTests` in `tests/test_ci.py`:

  ```python
  class ReuseFirstRecoveryTriggerTests(unittest.TestCase):
      def test_agents_contract_requires_reuse_first_after_material_blocker(self) -> None:
          text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
          required_fragments = (
              "## REUSE_FIRST_RECOVERY_TRIGGER",
              "first material, evidence-backed blocker",
              "no hidden retry or fallback",
              "`registries/reuse_candidates.yaml`",
              "`ADR-002`",
              "`ADOPT`, `WRAP`, `FORK`, `BUILD`, or `STOP`",
              "cheapest falsifier",
              "current atom's decision or acceptance receipt",
              "not a registry row, permanent Source, or generic scan artifact",
              "provider, dependency, cost, security, or owner-boundary change",
          )
          for fragment in required_fragments:
              with self.subTest(fragment=fragment):
                  self.assertIn(fragment, text)
          self.assertIn("routine deterministic test failure", text)
          self.assertIn("already-known limitation", text)
          self.assertLess(
              text.index("## REUSE_FIRST_RECOVERY_TRIGGER"),
              text.index("## VALIDATION_ECONOMY"),
          )
  ```

- [ ] **Step 2: Run the new test to verify it fails before the policy exists**

  Run:

  ```powershell
  uv run --locked --managed-python python -B -m unittest tests.test_ci.ReuseFirstRecoveryTriggerTests.test_agents_contract_requires_reuse_first_after_material_blocker
  ```

  Expected: `FAIL` because `AGENTS.md` does not yet contain `## REUSE_FIRST_RECOVERY_TRIGGER`.

- [ ] **Step 3: Add the minimal policy section**

  Insert the following exact section immediately before `## VALIDATION_ECONOMY` in `AGENTS.md`:

  ```markdown
  ## REUSE_FIRST_RECOVERY_TRIGGER

  After the first material, evidence-backed blocker in a bounded atom, stop
  expansion before custom construction, route widening, or infrastructure
  addition.  It applies to incomplete or semantically ambiguous external data,
  a documented provider or protocol capability limit, a repeated
  delivery/control failure with the same root cause, or a concrete component
  gap that would otherwise prompt custom construction.  It does not apply to a
  routine deterministic test failure, an already-known limitation, or a
  blocker whose recovery is already prescribed by an exact active gate.

  Preserve and classify the first result: no hidden retry or fallback.  Consult
  `registries/reuse_candidates.yaml`, relevant accepted decisions including
  `ADR-002`, and only the smallest useful set of current official, OSS, or
  commercial alternatives for the named consumer.  Record exactly one outcome
  — `ADOPT`, `WRAP`, `FORK`, `BUILD`, or `STOP` — with its cheapest falsifier.

  When the current atom already emits a decision or acceptance receipt, keep a
  compact record there containing only the blocker, alternatives considered,
  chosen outcome, and why the alternatives do or do not fit.  It is not a
  registry row, permanent Source, or generic scan artifact for every failure.
  Missing, vague, stale, or conflicting third-party documentation produces
  `STOP` or an explicitly unresolved result; it never licenses a custom
  workaround by default.  `BUILD` remains valid only for a narrow
  project-owned truth boundary after the other outcomes are evidenced unfit.

  This trigger does not authorize a provider, dependency, cost, security, or
  owner-boundary change.  Every ordinary external, license, dependency,
  security, cost, and owner gate remains in force.
  ```

- [ ] **Step 4: Run the focused test to verify the policy contract passes**

  Run:

  ```powershell
  uv run --locked --managed-python python -B -m unittest tests.test_ci.ReuseFirstRecoveryTriggerTests.test_agents_contract_requires_reuse_first_after_material_blocker
  ```

  Expected: `OK` with one test run.

- [ ] **Step 5: Run the direct contract suite and whitespace check**

  Run:

  ```powershell
  uv run --locked --managed-python python -B -m unittest tests.test_ci
  git diff --check
  ```

  Expected: the `tests.test_ci` module reports `OK`; `git diff --check` emits no output.

- [ ] **Step 6: Inspect exact scope and commit the independently testable patch**

  Run:

  ```powershell
  git status --short
  git diff -- AGENTS.md tests/test_ci.py
  git add AGENTS.md tests/test_ci.py
  git commit -m "test: enforce reuse-first recovery trigger"
  ```

  Expected: the commit includes exactly `AGENTS.md` and `tests/test_ci.py`; the separately approved design and plan commits remain unchanged.

- [ ] **Step 7: Run the one delivery preflight on the exact committed candidate before its first push**

  Run:

  ```powershell
  uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery --base-ref origin/main
  ```

  Expected: `RESULT: PASS` and a compact ignored receipt under `local/delivery_preflight/`; any failure stops delivery until its root cause changes.

- [ ] **Step 8: Publish and independently read back the exact delivery candidate**

  Run:

  ```powershell
  git push -u origin ctrl/reuse-first-trigger-v1
  ```

  Expected: one ordinary non-force branch push.  Create/read back the pull request and exact-head CI only under the existing standing autonomy and owner-attention gate; an accepted implementation, PR, or CI still does not claim canonical task acceptance.

## Plan Self-Review

- **Spec coverage:** Task 1 implements the prescribed two-file surface.  The static test locks the trigger, material-blocker boundary, five outcomes, receipt boundary, gate preservation, and placement.  The policy itself limits evidence collection, preserves negative results, rejects automatic retries and custom-default recovery, and excludes all external/value-bearing actions.
- **Scope check:** The patch is one policy subsystem with one direct test consumer; splitting it would create an untested intermediate policy state.
- **Placeholder scan:** no deferred implementation markers or unspecified validation steps are present.
- **Type consistency:** the only public Python identifier is `ReuseFirstRecoveryTriggerTests.test_agents_contract_requires_reuse_first_after_material_blocker`; its module, class, and command use the same spelling.
