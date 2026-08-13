---
protocol_id: GITHUB_BATON_PROTOCOL_V1
status: DORMANT_HISTORICAL
as_of: '2026-08-14'
superseded_for_active_routing_by: ADR-005
active_authority: false
---

# GitHub Baton Protocol — dormant historical record

> **NO ACTIVE AUTHORITY.** This document preserves the former
> `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` transport for audit, rollback analysis
> and exact historical receipt verification. `DELIVERY_HARNESS_V1` forbids it
> as an active input route.

The historical machine layer remains content-addressed and testable:

- `scripts/baton_contract.py`
- `scripts/baton_preflight.py`
- `scripts/baton_receipt.py`
- `scripts/baton_scope.py`
- `scripts/validate_baton.py`
- `tests/fixtures/baton/`

Its safety properties remain historical facts: exact UTF-8 payload bytes,
revision and out-of-band SHA-256 binding; mutable GitHub transport; bounded
repository/Issue identity; fail-closed managed write set; sanitized receipts;
no authority inferred from Issue, PR, commit or tests.

## Dormant boundary

- No active Cursor rule or command references this protocol.
- A historical Issue/receipt cannot select work or authorize a write.
- Baton validation may verify old fixtures and byte invariants, but it cannot
  perform a GitHub read/write or activate the route.
- Dormant baton merge remains forbidden even if an old approval phrase exists.
- Reactivation requires a new owner-approved task and successor ADR that
  explicitly supersedes ADR-005; editing this historical file is insufficient.

Historical receipts and predecessor contracts are append-only. Do not delete
or rewrite them to resemble the direct route.
