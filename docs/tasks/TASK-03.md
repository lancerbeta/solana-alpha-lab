---
task_id: TASK-03
task_version: "1.0"
implementation_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
phase: P0
cash_cap: USD_0
repository_commit: 85ab008b762edacd335bba3d9776100bc52775ce
remote: NONE
provider_calls: 0
contains_secrets: false
---

# TASK-03 — Private repository, controls & Project Asset Catalog

## Accepted checkpoints

- Repository baseline commit: accepted.
- Catalog foundation commit: `ee6119ae0b7750710c7f822c50137ed95b4977e9`, accepted.
- Atom 4 — Pre-Git lineage import / `T03-A4C`: last accepted atom.
- Accepted import commit: `e03639f4811d7e40f25b965ab79626c229c0fd8a`;
  parent: `ee6119ae0b7750710c7f822c50137ed95b4977e9`.
- Work-acceptance checkpoint commit: `85ab008b762edacd335bba3d9776100bc52775ce`;
  parent: `e03639f4811d7e40f25b965ab79626c229c0fd8a`.
- `TASK03-ATOM-4B` receipt: PASS; imported SHA-256 reconciliation:
  20/20 PASS; `ARCH-INTENT-001` hash: PASS.
- Atom 4 acceptance-sync validation: 42/42 PASS before and after commit.
- Remote/push: absent. Provider/API/RPC calls: 0.

## Acceptance limitations

- Pre-commit execution for import commit `e03639f4811d7e40f25b965ab79626c229c0fd8a`:
  NOT_TESTABLE.
- Tests at the import commit: NOT_RUN.

These limitations do not replace the accepted Atom 4 receipt and read-only hash
reconciliation evidence.

## Atom 5 implementation candidate

Atom 5 adds one versioned discriminator schema and nine active lifecycle registry
skeletons with `records: []`: research cycles, hypotheses, global trial ledger,
feature catalog, holdout consumption, strategies, bot instances, reuse candidates,
and decisions/negative results.

The active reuse registry references `PRE-GIT-TASK01-A024` as historical source
material and does not copy its ten candidates, decisions, or lifecycle states.
No research-cycle, hypothesis, trial, feature, strategy, bot, decision, negative
result, or reuse-candidate record is activated by this atom.

Catalog-only generation produces `docs/PROJECT_MAP.md` and
`catalog/generated/asset_edges.json`. Generated views omit hashes, receipts,
fingerprints, and evidence payloads, are deterministic, and are checked for
freshness by the repository gate. The Catalog candidate has 58 assets, 4 asset
shards, 4 schemas, 4 queries, and 9 empty lifecycle registries. Graph database
support remains deferred.

`ARCH-INTENT-001` remains `ACCEPTED_DIRECTION_NOT_IMPLEMENTED`; appearing in
generated navigation is not implementation evidence.

## Current authorization boundary

- TASK-03 remains `IN_PROGRESS`.
- Atom 5 remains an `IMPLEMENTATION_CANDIDATE` until separate Work acceptance.
- Atom 6 is `NOT YET AUTHORIZED`.
- No canonical lifecycle state is activated or synchronized by this candidate.
- Remote, push, connector permission, external service writes, provider/API/RPC
  calls, database deployment, VPS, wallet, signer, or real-money action is authorized.
- The candidate commit subject is
  `feat: add registry skeletons and generated navigation`.

## Next safe checkpoint

After a passing local commit and post-commit validation, return Atom 5 evidence to
Work for separate acceptance. Do not start Atom 6.
