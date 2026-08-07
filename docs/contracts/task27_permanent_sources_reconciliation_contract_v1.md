# TASK-27 permanent Sources reconciliation contract v1

## Purpose

`T27-A0-A5_PERMANENT_SOURCES_RECONCILIATION_AND_SMOKE_V1` prepares one
repository-tracked replacement candidate for the five mutable Project Source
roles. It brings owner-visible project memory forward from the unactivated
v4.6 candidate to the merged TASK-27 offline foundation.

The candidate is not a Project Sources UI action. It cannot activate itself,
does not contact a provider, and does not authorize a provider request.

## Candidate boundary

The candidate may replace only these roles:

- `canonical_manifest`;
- `roadmap`;
- `current_system_state`;
- `phase_archive`; and
- `active_task`.

It retains Operating System v8.5 and Research Blueprint v2.3 byte-for-byte by
their existing SHA-256 bindings. The candidate records merged main
`082f3f8184e84c31c876a484cf8e876a40691f62` and successful GitHub push CI run
`31224401848` as repository evidence.

## Activation and recovery

Its only permitted status before user UI work is
`VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING`. The owner must replace exactly the
five mutable roles, keep the two immutable roles, and return one manifest-first
seven-role smoke result. Until that result is reported, activation is unknown.

Rollback restores the prior five mutable roles named by the candidate manifest,
keeps the immutable roles unchanged, and runs the prior manifest's smoke.

## Authority and non-claims

This atom makes zero provider/API/RPC/WSS calls, reads no R2/R3 values or
paths, retains no raw history, uses no credential, changes no dependency or
Catalog root, creates no wallet/signer/transaction, and spends no cash.

A passing future smoke clears only A4's Source-alignment prerequisite for a
separate exact owner external-read review. It does not make such a review
`READY`, grant provider-read authority, or establish history fitness, PIT,
alpha, execution, PnL, NetReturn or owner cashflow.
