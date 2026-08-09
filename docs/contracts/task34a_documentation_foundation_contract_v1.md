# TASK-34A Documentation Foundation Contract v1

## Purpose

Provide one deterministic, repository-native navigation layer for the goal owner
and future Entry Gates. It resolves the activated Project Sources release and
can diagnose a locally materialized Sources directory without making that
directory a second truth owner.

## Authority and inputs

The authority order is:

1. `docs/project_sources/release_registry_v1.yaml`;
2. the one `ACTIVATED_BY_OWNER_SMOKE` release and its hash-bound activation
   receipt;
3. that release's canonical manifest and seven role bindings.

An optional local Sources directory is read-only diagnostic input. Its absence,
old contents, filenames, or UI numeric suffixes never demote a release that is
proven active by the registry and owner-smoke receipt.

## Mirror states

The resolver returns exactly one of the following states:

- `MIRROR_MATCHES_ACTIVE_RELEASE`;
- `STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED`;
- `MIRROR_UNAVAILABLE`;
- `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW`.

Only a conflict blocks task selection. A registry, receipt, manifest, or
hash-binding contradiction fails closed rather than being represented as a
mirror state.

## Output and non-claims

The context card reports stable release identity, receipt identity, active task
identity, mirror state, and task-selection eligibility. It never prints the
supplied absolute local directory, secrets, raw provider data, or credentials.

This task makes no claim about live Sources UI activation, provider access,
wallets, transactions, cash, strategy quality, alpha, or NetReturn. It does not
create a documentation portal, RAG service, UI, dependency, or external call.

## Authority boundary

All provider/API/RPC/WSS access, credentials, Project Sources UI actions,
wallet/signer/transaction actions, cash spend, deployment, and release actions
remain outside this contract and require their own exact authority.
