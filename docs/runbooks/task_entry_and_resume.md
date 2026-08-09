# Start or resume a task

## Purpose

Recover the current, proven project context before choosing or resuming a bounded
task. The repository registry and its owner-smoke receipt decide which Project
Sources release is active; an app-local mirror is only a diagnostic input.

## First action

From the repository root, run:

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format text
```

If a local Sources folder is available and a diagnostic is useful, run the same
command with `--format json --sources-dir <local-sources-directory>`. The
directory is read-only and is redacted from output.

## Continue only when binding is clear

- `MIRROR_MATCHES_ACTIVE_RELEASE`, `STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED`, or
  `MIRROR_UNAVAILABLE`: use the shown active release and run the normal Entry
  Gate for the candidate task.
- `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW` or `TASK34A_CONTEXT: FAIL`: stop.
  Do not select a task, replace Sources, or invent a newer truth owner. Record
  the state and ask for the appropriate control review.

This runbook performs no external action. Before any provider, credential,
wallet, transaction, cash, deployment, or cloud Project Sources UI action,
follow [external authority stop](external_authority_stop.md).
