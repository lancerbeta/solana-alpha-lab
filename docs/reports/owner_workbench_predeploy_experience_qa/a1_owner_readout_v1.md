# OWNER_WORKBENCH_PREDEPLOY_EXPERIENCE_QA_V1 — owner readout

## Decision unlocked

Can Petr scan the six already-deployed Workbench surfaces in ~10s without
UNKNOWN becoming $0/«исправна», without command POST values changing, and
without a frontend rewrite?

**Answer: YES** on current `main`/live SHA `52808d613d02f8e96a85aea2668e98d80aec0d51`
as the review baseline. The atom id still says `predeploy`; that is a historical
name, not a predeploy gate. This PR does not deploy.

## What landed

One presentation-only repair batch after a browser-first review:

- attention is scan-first: `details.attention-scan` with P0/P1 borders
- `НОВОЕ С ПРОСМОТРА` is on the closed summary line, not only inside the card
- SYSTEM P0/P1 chrome comes from exact `IMPACT` tokens `P0|P1|P2`; prose IMPACT is not invented as a rank
- `git_archaeology_required=` left the page-note and sits in `.page-machine`
- ECONOMICS drawdown/streak no longer render `UNKNOWN UNKNOWN`
- RESEARCH no longer repeats ATTENTION / GAPS / ACTIVE NOW in the counter grid
- Russian-first labels on coverage, research columns, operations summary, economics H2s
- MARKET `SOURCE_NOT_PRESENT` skips the empty 5-axis / matrix wall
- drill links include the attention code or source domain

## Proof

- BEFORE: live GET via SSH tunnel to Factory Workbench at 1440×900
- AFTER: local `scripts/run_factory_workbench.py` on this branch, port 18765, no VPS mutation
- Inventory: `docs/evidence/owner_workbench_predeploy_experience_qa/a1_before_after_inventory_v1.json`
- Focused tests: `tests/test_owner_workbench_predeploy_experience_qa_v1.py` plus foundation, ordinary-hypothesis consumer, Visual OS, research semantic discovery

## Non-claims

- No alpha, NetReturn, provider, wallet, VPS mutation, or canonical DONE
- Live Factory remains on `52808d61` until a later named deploy atom
- Local AFTER uses operator-local data; live BEFORE is the deployed SHA
- Residual collector/heartbeat facts stay machine truth, not this write set
- HOME GET latency is out of this presentation batch

## Stop

`OWNER_ATTENTION_GATE_V2` merge-readiness. No deploy. Next named atom is not
started from this PR.

## Rollback

Ordinary Git revert of `cursor/owner-workbench-predeploy-experience-qa-v1`.
No runtime reconciliation.
