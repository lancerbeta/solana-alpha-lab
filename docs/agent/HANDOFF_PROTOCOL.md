# Local Work-Codex handoff protocol

Default: `INPUT=DIRECT_PROMPT`.

- Read local input only when the current prompt explicitly contains
  `LOCAL_HANDOFF: <repository-relative path>`.
- Read Work acceptance output only when the current prompt explicitly contains
  `ACCEPT_LOCAL_HANDOFF: <repository-relative path>`.
- A `LOCAL_HANDOFF` target must remain under
  `.smial-handoff/work-to-codex/`; an `ACCEPT_LOCAL_HANDOFF` target must remain
  under `.smial-handoff/codex-to-work/`.
- Reject absolute paths, parent traversal, and symlink or reparse-point escapes.
- Read only the named target and children explicitly listed by its manifest.
- Never discover a handoff by newest or last-modified time.
- A trigger grants read access only. It grants no write, commit, push, external
  action, acceptance, or status authority.
- Work owns canonical task status and acceptance.
- Handoffs contain no secrets, machine paths, usernames, or raw environment
  dumps.
- Retain final outputs until Work acceptance. Remove only exact temporary state
  created by the named atom.
