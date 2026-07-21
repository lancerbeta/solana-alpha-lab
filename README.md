# Solana Memecoin Intraday Alpha Lab

A bounded, evidence-first research system for executable Solana memecoin alpha
on a 15-minute to 4-hour horizon.

## Current repository stage

Atom 7B is Work-accepted. The private repository is active on `origin/main`; the
prior accepted HEAD is `21cfe7fb5c0d410bd9c86976ee3c815dca249399`, and GitHub
Actions run `29868825180` passed for that exact commit. The current change is the
T03-A7C final acceptance candidate. It still requires a new terminal CI PASS and
an exact-final-HEAD clean-clone receipt before Work may reconcile canonical
Sources or accept TASK-03 as complete.

The Catalog contains 60 assets, 4 asset shards, 4 schemas, and 5 read-only query
recipes. All nine lifecycle registries remain empty.

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

Accepted external CI evidence: run `29868825180` PASS at the prior accepted
HEAD. The T03-A7C candidate requires its own new terminal run. Provider/API/RPC
calls and cash spend remain zero.
