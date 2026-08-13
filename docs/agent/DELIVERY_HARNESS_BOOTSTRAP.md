# Delivery Harness bootstrap

After ADR-005 is merged:

1. open only the repository root (or one worktree root) in Cursor;
2. paste `delivery-harness/templates/bootstrap-prompt.md` into Cursor;
3. let Cursor perform its read-only check/context bootstrap;
4. do not install plugins or update cloud Project Sources/Instruction.

Cursor may need one window reload to discover new project-level custom agents.
Their absence is non-blocking because deterministic review fallback is part of
the harness.

No global Cursor/Codex setting or user file is modified by repository
bootstrap. Cloud exports remain `OWNER_MANAGED_OPTIONAL_EXPORT`.
