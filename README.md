# Solana Memecoin Intraday Alpha Lab

A bounded, evidence-first research system for executable Solana memecoin alpha
on a 15-minute to 4-hour horizon.

## Repository status boundary

This README is bootstrap documentation, not a live task-status source.
Work/control plane owns canonical status and acceptance. For current work, use
only the task and handoff explicitly named by the Work-approved prompt. The
repository may contain an uncommitted or staged candidate without changing the
canonical task state.

## Delivery Harness bootstrap

The repository-owned entrypoint for Cursor and Codex is `AGENTS.md` plus
`DELIVERY_HARNESS_V1`. Cursor bootstrap uses the exact copy-paste prompt at
`delivery-harness/templates/bootstrap-prompt.md`; the protocol is
`docs/agent/DELIVERY_HARNESS_BOOTSTRAP.md`.

Open one repository/worktree root, require an exact Git task contract and run:

```text
uv run --locked --managed-python python -B scripts/delivery_harness.py check --root . --format json
```

Cloud Project Sources/Project Instruction are optional owner-managed exports.
The harness neither requires nor requests their update or smoke.

Catalog counts, lifecycle counts, exact dependency pins, and candidate state
are checked by the repository validation gate and recorded in the explicitly
named task/handoff.

## Exact prerequisites

- CPython `3.13.14`;
- uv `0.11.29`;
- dependencies resolved only from the committed `uv.lock`.

No repository or environment secret is required for validation.

## Platform-neutral validation

```text
uv run --locked --managed-python python -B scripts/validate_ci.py
```

The gate checks exact runtime and uv pins, lock immutability, fake-secret
rejection, repository secret scanning, Catalog schemas and semantics, stable-ID
resolution, generated navigation freshness, exact pre-Git provenance,
repository state, hooks, EOL policy, and the full test suite.

On the validated Windows workstation, the compatibility command delegates to
the same gate:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

## Private clean-clone bootstrap

For an authorized bounded acceptance clone of the private repository:

```text
git clone --branch main --single-branch <PRIVATE_REPOSITORY_URL> <BOUNDED_LOCAL_DIRECTORY>
cd <BOUNDED_LOCAL_DIRECTORY>
git show -s --format=%H HEAD
git config --local core.hooksPath .githooks
uv run --locked --managed-python python -B scripts/validate_ci.py
```

The `git show` output must equal `<AUTHORIZED_COMMIT_SHA>` exactly; stop before
validation on any mismatch. Keep `main` attached to `origin/main` and do not use
a detached checkout. The clean-clone receipt must prove the authorized final
commit, exact private origin, clean tree, clone-local hooks setup, and a passing
gate. Temporary-clone cleanup is a separate, target-specific user decision.

## Security and provenance boundary

Do not place `.env`, credentials, tokens, seed phrases, private keys, raw data,
wallet mappings, or machine-specific absolute paths in this repository. Exact
TASK-01/TASK-02 imported bytes remain historical references; source bundles stay
outside Git and are registered by SHA-256. `ARCH-INTENT-001` remains
`ACCEPTED_DIRECTION_NOT_IMPLEMENTED`.

Provider/API/RPC access, wallet or signer use, and real-money actions require a
separate explicit Work authorization; repository documentation does not grant
that authority.
