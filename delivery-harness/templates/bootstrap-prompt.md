# Delivery Harness bootstrap

Repository: https://github.com/lancerbeta/solana-alpha-lab

Open exactly one repository or worktree root. Do not open a parent checkout and
its child worktree together.

1. Fetch `main` and report its exact HEAD and tree without changing files.
2. Read `AGENTS.md`, `delivery-harness/harness.yaml` and
   `delivery-harness/project-profile.yaml`.
3. Run `python -B scripts/delivery_harness.py check` in read-only mode with
   Python 3.11 or newer. The portable runtime is standard-library-only; do not
   install packages. If no suitable Python is available, stop with a stable
   runtime-unavailable reason instead of changing the machine.
4. Require `delivery_gate_ready=true`. If the portable profile still has null
   validation bindings or `github_ci_bound=false`, inspect the repository's existing test/CI and
   credential-leak checks, then bind their exact shell-free argv arrays in
   `delivery-harness/project-profile.yaml`. Also bind the actual PR workflow
   file/name/event and required job names in
   `control/owner_attention_gate_v2.yaml`; set `github_ci_bound=true` only
   after those facts match the live repository. Reuse existing project commands;
   do not invent a new toolchain or install dependencies. If no trustworthy
   project-owned commands exist, stop with
   `PROJECT_VALIDATION_BINDING_REQUIRED`; guarded merge must remain denied.
5. Use only an exact task contract named by the owner or canonical READY
   contract. Never infer work from recency, branch names or chat history.
6. Generate the L0/L1 context receipt and report its hash and explicit gaps.
7. Confirm that no active Cursor rule or command elects the historical baton.
8. Treat cloud Project Sources/Project Instruction as
   `OWNER_MANAGED_OPTIONAL_EXPORT`. Do not request replacement or smoke.
9. Do not change global Cursor/Codex settings and do not connect external
   systems during bootstrap.

For the first PR that installs this harness, the candidate policy/profile are
not trusted by their own guard because they do not yet exist on base `main`.
Deliver that one bootstrap PR through the repository's pre-existing exact
owner-approved merge route. The guarded route activates only after those bytes
are present on `main`; never add a self-approval bypass.

Finish with exactly one terminal:

```text
DELIVERY_HARNESS_BOOTSTRAP=PASS
DELIVERY_HARNESS_BOOTSTRAP=BLOCKED:<stable_reason>
```
