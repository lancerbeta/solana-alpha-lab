# Baton preflight (read-only local; exact GitHub read under standing grant)

Use only when launch inputs are explicitly provided. Make **zero local writes**.
Stop before mutation.

## Required launch inputs

- `repository`: full name (`lancerbeta/solana-alpha-lab`)
- `issue`: exact Issue number
- `revision`: expected contract revision (integer)
- `expected_contract_sha256`: out-of-band lowercase 64-hex trust anchor
- standing project autonomy or a stricter explicit grant for the exact named
  GitHub read

The out-of-band hash is the trust anchor. Do not derive trust only from the
Issue body or from any hash embedded inside that body.

If any required input is missing, return `BLOCKED` and stop.
If the active contract explicitly forbids network or the standing grant is
unavailable, return `BLOCKED_AUTHORITY` and stop.

## Steps

1. Read `AGENTS.md`, `docs/agent/EXECUTION_ROUTER_PROTOCOL.md` and
   `docs/agent/GITHUB_BATON_PROTOCOL.md`.
2. Run:

```text
uv run --locked --managed-python python -B scripts/baton_preflight.py \
  --repository <owner/name> \
  --issue <number> \
  --revision <int> \
  --expected-contract-sha256 <64-hex> \
  [--issue-body-file <path>] \
  [--allow-github-read]
```

3. Live mode (`--allow-github-read`) may perform **one** exact named
   `gh issue view` for that repository and Issue under the standing grant.
4. Forbid issue search, listing, newest/latest discovery, other repo reads,
   comments, edits, labels, PR writes, push, merge or settings.
5. On revision/hash mismatch, treat result as `BLOCKED_CONTRACT_MISMATCH`.
6. Stop before mutation.

## Output

Return the script JSON, including:

```json
"side_effects": {
  "github_reads": 0,
  "github_writes": 0,
  "local_writes": 0
}
```

## Hard stops

- Missing out-of-band `expected_contract_sha256`
- Active contract forbids the exact bounded GitHub read or standing grant is
  unavailable
- Any base/identity/hash/authority mismatch
- Any request to commit, push, comment or open a PR during preflight

Do not stage, commit, push, perform GitHub writes, or edit files.
No GitHub writes or unbounded/discovery reads.
Never search/list Issues or infer latest/current Issue.
