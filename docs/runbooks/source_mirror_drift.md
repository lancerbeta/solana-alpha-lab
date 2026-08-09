# Handle Project Sources mirror drift

## Purpose

Classify a locally materialized Project Sources folder without mistaking it for
the active Project Sources release.

## Read-only diagnostic

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format json --sources-dir <local-sources-directory>
```

Do not copy, rename, delete, upload, or replace any Source file as part of this
diagnostic.

## Interpret the state

- `MIRROR_MATCHES_ACTIVE_RELEASE`: the seven semantic roles match the activated
  release. Continue through the normal Entry Gate.
- `STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED`: the local folder is old or incomplete;
  the registry and owner-smoke receipt remain the active truth. No repair is
  required for a safe offline Entry Gate.
- `MIRROR_UNAVAILABLE`: the local folder is absent or inaccessible. Use the
  registry/receipt path; do not treat absence as activation failure.
- `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW`: two exact semantic copies or another
  ambiguity prevents safe selection. Stop and obtain a control decision.

If the goal is a cloud Project Sources UI replacement, stop here: that is an
external UI mutation and belongs to
[external authority stop](external_authority_stop.md), not this runbook.
