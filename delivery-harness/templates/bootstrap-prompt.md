# Delivery Harness bootstrap

Repository: https://github.com/lancerbeta/solana-alpha-lab

Open exactly one repository or worktree root. Do not open a parent checkout and
its child worktree together.

1. Fetch `main` and report its exact HEAD and tree without changing files.
2. Read `AGENTS.md`, `delivery-harness/harness.yaml` and
   `delivery-harness/project-profile.yaml`.
3. Run the repository's `delivery_harness.py check` command in read-only mode.
4. Use only an exact task contract named by the owner or canonical READY
   contract. Never infer work from recency, branch names or chat history.
5. Generate the L0/L1 context receipt and report its hash and explicit gaps.
6. Confirm that no active Cursor rule or command elects the historical baton.
7. Do not change global Cursor/Codex settings and do not connect external
   systems during bootstrap.

Finish with exactly one terminal:

```text
DELIVERY_HARNESS_BOOTSTRAP=PASS
DELIVERY_HARNESS_BOOTSTRAP=BLOCKED:<stable_reason>
```
