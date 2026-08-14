# Delivery Harness bootstrap

After ADR-005 is merged:

1. open only the repository root (or one worktree root) in Cursor;
2. paste `delivery-harness/templates/bootstrap-prompt.md` into Cursor;
3. let Cursor perform its read-only check/context bootstrap;
4. do not install plugins or update cloud Project Sources/Instruction.

The generated portable runtime supports Python 3.11+ using only the standard
library. `delivery-harness/runtime-requirements.txt` is deliberately empty and
records that no package installation is part of bootstrap. The generated
profile, owner-attention policy and bootstrap prompt are all rendered from the
same exact `owner/repository` identity and the initializer refuses an origin
mismatch, nested checkout or reparse boundary.

From a trusted exact source checkout, initialize another existing Git root with
the standard-library-only source entrypoint. Preview is zero-write; inspect the
closed file inventory and retain its fingerprint before apply:

```text
python -B scripts/delivery_harness.py init --target <NEW_REPOSITORY_ROOT> --repository <OWNER/REPOSITORY> --default-branch <DEFAULT_BRANCH> --preview --format json
python -B scripts/delivery_harness.py init --target <NEW_REPOSITORY_ROOT> --repository <OWNER/REPOSITORY> --default-branch <DEFAULT_BRANCH> --apply --plan-sha256 <PLAN_SHA256> --format json
```

Do not substitute a downloaded loose script or a dirty/untrusted template
directory. The bundle manifest validates every source SHA-256 before the first
target write.

The portable profile intentionally starts with null validation bindings.
During repository bootstrap Cursor must discover and bind the repository's
existing shell-free test/full-gate and credential-scan argv, validate the
profile, bind the actual PR workflow file/name/event and required jobs, set
`github_ci_bound=true`, and obtain `delivery_gate_ready=true`. Until then CHECK/CONTEXT are
usable but guarded merge is fail-closed. A local PASS receipt is never a
substitute for executing the bound command.

The first installation is intentionally not self-hosting. Its profile and v2
policy are absent from the frozen base, so the new guard must deny that PR.
Merge the bootstrap candidate only through the repository's preceding exact
owner-approved route. After the bytes land on the repository's exact default branch, candidate profile/policy
must remain byte-identical to their base owners; there is no first-install
self-trust exception inside the guard.

Cursor may need one window reload to discover new project-level custom agents.
Their absence is non-blocking because deterministic review fallback is part of
the harness.

The initializer also refuses the user home directory itself, even if it happens
to be a Git root. No global Cursor/Codex setting or user file is modified by repository
bootstrap. Cloud exports remain `OWNER_MANAGED_OPTIONAL_EXPORT`.
