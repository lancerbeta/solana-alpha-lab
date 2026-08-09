# Reuse-first recovery trigger — design

**Status:** owner design approved (`REUSE_FIRST_TRIGGER_DESIGN_APPROVED`)

## Purpose

Turn the existing `ADOPT → WRAP → FORK → BUILD` preference into a small,
repeatable recovery trigger.  A first material blocker must cause a bounded
look-around before the project builds a custom substitute, broadens a provider
route, or adds infrastructure.

This is a decision-quality control.  It is not a market-research programme,
generic tool platform, dependency-adoption process, or new authority path.

## Chosen design

Add one `REUSE_FIRST_RECOVERY_TRIGGER` section to `AGENTS.md`, immediately
before `VALIDATION_ECONOMY`, and protect the section with one focused static
contract test.

The trigger applies after the first **material, evidence-backed** blocker in a
bounded atom, including:

- incomplete or semantically ambiguous external data;
- a documented provider or protocol capability limit;
- a repeated delivery/control failure with the same root cause; or
- a concrete component gap that would otherwise prompt custom construction.

It does not apply to a routine deterministic test failure, an already-known
limitation, or a blocker whose required recovery is already specified by an
active exact gate.

When it applies, the owner of the current atom must:

1. preserve and classify the first result; no hidden retry or fallback;
2. check the existing reuse registry and relevant accepted decisions;
3. inspect only the smallest useful set of current official, OSS, or commercial
   alternatives for the named consumer;
4. record one outcome: `ADOPT`, `WRAP`, `FORK`, `BUILD`, or `STOP`, together
   with the cheapest falsifier; and
5. keep every provider, dependency, cost, security, and owner-authority gate
   intact.

The compact record belongs in the current atom's decision or acceptance
receipt when that atom already emits one.  It contains only the blocker,
alternatives considered, chosen outcome, and why the alternatives do or do not
fit.  It does not introduce a registry row, a new permanent Source, or a
generic scan artifact for every failure.

## Why this location

`AGENTS.md` is mandatory context for repository work, so the trigger is met by
every future task without adding another workflow, service, skill, dashboard,
or manual checklist.  The existing `registries/reuse_candidates.yaml` and
`ADR-002` remain the evidence locations; this rule only tells an agent when to
consult them again.

## Boundaries and failure handling

- Missing, vague, stale, or conflicting third-party documentation produces
  `STOP` or an explicitly unresolved result; it never licenses a custom
  workaround by default.
- A valid external candidate may still require its ordinary security, license,
  provider, dependency, cost, and owner gates.
- An existing provider route is not retried or widened merely because a
  look-around found another option.
- A custom build remains valid only for a narrow project-owned truth boundary
  after the other outcomes are evidenced as unfit.

## Validation

The implementation has exactly two production-facing files:

- `AGENTS.md` — the executable policy text;
- `tests/test_ci.py` — a focused invariant that requires the trigger, its
  material-blocker boundary, its five outcomes, and its authority-preserving
  rule.

The test must first fail against the current `AGENTS.md`, then pass after the
minimal policy addition.  No full gate is needed until a delivery candidate is
created; no provider, credential, wallet, transaction, raw-data, Catalog, or
Project Sources action is part of this control patch.

## Non-goals

- automatic web searching, package installation, provider switching, or
  dependency adoption;
- a scorecard that forces a fixed number of candidate tools;
- rerunning a failed external request;
- reopening TASK-27 or accepting TASK-30;
- replacing task-level Entry Gates, owner attention, or Factory Fit review.

## Immediate application

`T30-A0` demonstrated the intended behavior: GeckoTerminal's documented empty
interval semantics provided a mature candidate, but the response's timestamp
boundary did not match the frozen window.  `T30-A1` therefore starts with an
offline boundary-semantics decision, not a custom OHLCV builder or another
provider call.
