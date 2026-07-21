# Solana Memecoin Intraday Alpha Lab

A bounded, evidence-first research system for executable Solana memecoin alpha
on a 15-minute to 4-hour horizon.

## Current repository stage

Atom 5 is Work-accepted and canonical Atom 6 is closed by Atom-5 evidence. The
current repository change is the Atom 7A local CI candidate: a pinned workflow
and one platform-neutral validation gate. It has not run on GitHub and is not
Work-accepted. Private remote activation and clean-clone evidence remain pending.

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

## Future private clone bootstrap

Remote activation is not part of the local candidate. After separate Work
authorization supplies the private repository URL and exact commit:

```text
git clone --branch main --single-branch <PRIVATE_REPOSITORY_URL> <BOUNDED_LOCAL_DIRECTORY>
cd <BOUNDED_LOCAL_DIRECTORY>
git show -s --format=%H HEAD
git config --local core.hooksPath .githooks
uv run --locked --managed-python python -B scripts/validate_ci.py
```

The `git show` output must equal `<AUTHORIZED_COMMIT_SHA>` exactly; stop before
validation on any mismatch. Keep `main` attached to `origin/main` and do not use
a detached checkout. Do not infer a remote URL from local metadata. Clean-clone
acceptance requires a sanitized receipt proving the exact checkout, clean tree,
local hooks setup, and passing gate.

## Security and provenance boundary

Do not place `.env`, credentials, tokens, seed phrases, private keys, raw data,
wallet mappings, or machine-specific absolute paths in this repository. Exact
TASK-01/TASK-02 imported bytes remain historical references; source bundles stay
outside Git and are registered by SHA-256. `ARCH-INTENT-001` remains
`ACCEPTED_DIRECTION_NOT_IMPLEMENTED`.

Current external CI status: `NOT_RUN_EXPECTED`. Provider/API/RPC calls and cash
spend remain zero.
