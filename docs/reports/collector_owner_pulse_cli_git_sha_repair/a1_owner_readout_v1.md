# COLLECTOR_OWNER_PULSE_CLI_GIT_SHA_REPAIR_V1 — owner readout

## What changed

`scripts/collector_owner_pulse.py` now resolves producer identity with the
canonical ObservationSchedule helper:

```text
producer_git_sha = git_sha(ROOT, runtime.get("producer_git_sha"))
```

Precedence unchanged: runtime `producer_git_sha` → Git HEAD → `.factory_deploy_sha`.
No second resolver. `git_sha()` API unchanged. Deploy pin remains identity-only.

## Proof

- Original falsifier cleared: `scripts/collector_owner_pulse.py --mode dry-run`
  no longer raises `TypeError: git_sha() missing 1 required positional argument`
- Executable CLI suite: `tests/test_collector_owner_pulse_cli_git_sha_repair.py`
  - checkout dry-run render
  - no-`.git` + valid `.factory_deploy_sha`
  - configured `producer_git_sha` beats pin
  - missing/malformed pin fail-closed
- Dry-run: `network_calls=0`, `credential_value_reads=0`, `jupiter_credentials_read=0`

## Explicit next (not this atom)

Re-run `FACTORY_LIVE_BASELINE_COMMISSIONING_PREFLIGHT_V1` from repaired main.
Do not deploy from this merge alone.

Expected remaining ops/authority blockers after green product preflight:
SSH hardening, Jupiter env presence, same-volume durability decision.

## Non-claims

No VPS mutation/deploy, no provider/API/RPC/WSS, no credential values,
no Telegram emit, no campaign authorize/activate, no SSH/backup changes,
no alpha.
