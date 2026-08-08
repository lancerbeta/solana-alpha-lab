## Contract

- Contract ID:
- Contract revision:
- Out-of-band expected SHA-256:
- Linked control Issue:

## Objective and scope

- Objective:
- Managed write set:
- Authority class:

## Exact changed files

-

## Files outside managed write set

- None / list:

## Validation

- Candidate commit/tree or staged fingerprint:
- Targeted commands:
- Single full-gate owner (`Cursor` / `Codex` / `GitHub CI`):
- Full-gate receipt, reuse, or `FULL_VALIDATION=DELEGATED_TO_CI`:
- Catalog delta:

## Side effects

- GitHub reads:
- GitHub writes:
- Provider calls:
- Cash spend USD:
- Wallet/signer/transaction actions:

## Security

- Secrets exposed: no
- Absolute user paths: no

## Limitations / blockers

-

## Rollback

-

## GPT acceptance status

- Not accepted / accepted by GPT control plane:

## OWNER_ATTENTION_GATE and merge status

- Execution route:
- Exact PR head:
- Gate decision (`AUTONOMOUS` / `OWNER_ATTENTION_REQUIRED` / `DENY`):
- Merge preconditions all PASS:
- Post-merge exact main read-back / main CI:

---

Draft PR is candidate evidence, not canonical acceptance.
Cursor never merges. Local Codex merges only after `OWNER_ATTENTION_GATE`
returns `AUTONOMOUS` for the exact head; baton-route merge returns to the
Project Chat/owner boundary.
Commit/tests/CI do not establish DONE.
