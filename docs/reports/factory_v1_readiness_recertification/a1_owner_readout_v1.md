# A6 — Recertification and foundation freeze

Date: 2026-08-23
Contract: `FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1`

## Decision

Entry Gate now resolves the live readiness contract. Closeout recertifies
`FACTORY_V1_OPERATIONAL_READY` and activates foundation freeze. This is not
alpha, not canonical DONE, and not a domain-policy edit.

## What changed

- Bound project profile names `configs/factory_v1_operational_readiness_v1.yaml`.
- `check_harness` fails if the flag is false or the live owner is missing.
- Context receipts include that file for this repository.
- Closeout requires both the YAML flag and the profile binding.
- Live closeout: READY, freeze ACTIVE, named gaps 0.

## Receipt

- terminal: `FACTORY_V1_OPERATIONAL_READY`
- foundation_freeze: `ACTIVE`
- next_safe_action: `FOUNDATION_FREEZE_ACTIVE_ATOM4_ELIGIBLE_IF_KEPT`
- domain policy file: unchanged
- historical Project Sources roadmaps: unchanged
- network / wallet / cash: 0

## Boundary

A7+ stay conditional. They start only after READY plus an explicit owner
trigger. Freeze does not authorize a second VPS, a provider, or a signer.

## Next

Owner decision: keep freeze, or name a later atom. Do not click GitHub Merge.
After exact-head CI, paste the merge phrase for this PR and unchanged 40-hex
head.
