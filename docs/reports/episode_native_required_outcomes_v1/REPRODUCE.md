# Reproduce the bounded repair proof

Use the elected clean candidate, existing locked host environment and no
provider credentials. `PYTHONPATH=src`; Windows native atomic store publication
may require an allowed non-sandbox process. Do not alter tracked Git bytes while
preparing frozen fixtures or running authoritative persistence cases.

Native fixture owner:
`tests.fixtures.episode_native_required_outcomes_v1.proof.prepare`.
The existing generator captures synthetic ingress, publishes/imports native
episode releases, fixes an input-label membership oracle before discovery,
performs two explicitly counted MAIN setup looks and persists/freezes LIST and
MIXED recipes. Target prices and one missing future cell change at ingress only.

In a fresh disposable absolute directory, call `prepare` for:

```python
from pathlib import Path
from tests.fixtures.episode_native_required_outcomes_v1.proof import prepare
r = Path('local/episode-native-reproduce-v1').resolve()
prepare(r / 'ready')
prepare(r / 'world-values-v2', target_price=1.35)
prepare(r / 'world-missing-v2', missing_target=True)
```

This fresh reproduction performs six setup MAIN looks; it never erases prior
campaign history. For a new Git candidate, reuse saved immutable ingress with
`prepare(new_path, reuse_ingress=old_path)` where old_path contains the registered
`capture` directory. The source is shared and imported through native owners
without duplicating capture bytes; do not reuse a stale frozen session
as current action authority. `target_price` and `missing_target` must describe
the selected reused ingress. Legacy tests have their own temporary fixtures.

Set environment variables to the absolute prepared directories:

```text
ERNOC_FIXTURE=<r>/ready
ERNOC_VARIANTS=<r>
ERNOC_MISSING_FIXTURE=<r>/world-missing-v2
ERNOC_PROOF_OUT=<r>/proof
```

Run the actual entry point in the existing locked environment:

```text
uv run --locked --managed-python --no-sync python -B -m unittest tests.test_episode_native_required_outcome_contract_v1 -v
```

Require all 16 cases with zero skips. Missing variants are explicitly skipped by
the general CI entry point; a skipped run does not reproduce this campaign's full
16-case evidence. Saved positive/blocked receipts and raw reader traces remain
under `ERNOC_PROOF_OUT`; compare logical bindings and native counters, not physical
host locators or byte-identical SQLite files.

The committed focused-checks receipt records two actual selected legacy commands
(82+2 PASS), the proof implementation head and elapsed time. Product owner hashes
are bound by Catalog and the final delivery inventory; later report-only commits
do not retroactively upgrade frozen scientific/Git evidence. No numerical
experiment, new science decision, activation or PAPER is part of this procedure.
