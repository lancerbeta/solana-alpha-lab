# T30-A11D — Factory Leverage Invariant design

**Status:** DESIGN_APPROVED

## Purpose

Keep the hypothesis factory on the product path where a comparable new
hypothesis normally reuses existing data and capabilities rather than requiring
a new product-code cycle.  The invariant is a review trigger, not an automatic
block and not a new registry or metric.

## Decision

The selected approach is a two-surface, human-readable guardrail:

1. `AGENTS.md` carries the operating rule for every repository agent at Entry
   and Finish Gates.
2. `ARCH-INTENT-002` carries the enduring product rationale and adds the same
   question to the existing Factory Fit review.

The rule applies only after a repeated requirement for hypothesis-specific
product code appears in comparable work.  It requires the existing Factory Fit
review to name the reusable capability gap and the next real consumer before
that pattern is copied further.  It does not stop work automatically.

## Exact behavior

The default path for a new hypothesis covered by existing Factory capabilities
is:

```text
hypothesis definition / configuration
→ existing data and feature capability
→ dataset or query
→ trial
→ decision
```

A Git/code/deploy cycle is justified only by a named reusable capability gap,
a defect, a safety or reliability requirement, or a measured scale bottleneck.

When comparable hypothesis work repeatedly needs product-code changes, the
existing Factory Fit review must answer:

- could the next comparable hypothesis run without product-code modification;
- if not, which reusable gap is being closed; and
- which next consumer makes the capability reusable.

## Non-goals

- No automatic blocker, quota, score, registry, schema or recurring report.
- No change to canonical Project Sources, Catalog asset IDs, schemas, data
  contracts, providers, credentials, scheduler, wallet, transaction, spend or
  deployment. Existing Catalog integrity bindings, record metadata and generated
  views may be refreshed only when the changed policy documents require it.
- No claim that the current offline A11C harness is a hypothesis or that it
  should have avoided code; it is a safety capability for a future external
  read.
- Historical TASK-15 receipt and TASK-20 frozen-input bytes remain untouched.
  Their tests must preserve those historical hashes without treating a mutable
  accepted architecture intent as if it could never evolve.

## Validation

Inspect the exact policy and required Catalog-binding diff, run the existing
owner-attention policy test that protects the active `AGENTS.md` contract, and
run the TASK-15/TASK-20 historical-binding tests that distinguish immutable
snapshots from the current architecture. Run Catalog plus repository policy
validation for the committed candidate. The completion review must confirm that
this remains a guardrail rather than a second control plane.

## Rollback

The patch is additive documentation.  Reverting its single commit restores the
previous wording without data or runtime migration.
