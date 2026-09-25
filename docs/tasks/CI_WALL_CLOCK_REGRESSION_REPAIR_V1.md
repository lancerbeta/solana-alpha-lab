---
task_id: CI_WALL_CLOCK_REGRESSION_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-25'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 971e0a09e600ae3210b07094dd071824708d6bbd
  expected_upstream: origin/main
  expected_upstream_oid: 971e0a09e600ae3210b07094dd071824708d6bbd
  expected_branch: cursor/ci-wall-clock-regression-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Repair the A5 CI wall-clock regression at its root: parse the semantic
  Catalog once per exact file content per process (C YAML loader, private
  copies) with zero change to any admission identity; make shard logs name
  slow modules even when a job is cancelled; restore CI job budgets from the
  temporary A5 headroom.
managed_write_set:
  - docs/tasks/CI_WALL_CLOCK_REGRESSION_REPAIR_V1.md
  - src/solana_alpha_lab/factory_semantic_operability.py
  - tests/test_factory_semantic_operability.py
  - scripts/run_ci_test_shard.py
  - tests/test_run_ci_test_shard.py
  - scripts/validate_ci.py
  - .github/workflows/ci.yml
  - tests/test_ci.py
  - configs/ci_test_shards_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/ci_wall_clock_regression_repair/a1_owner_readout_v1.md
  - docs/evidence/ci_wall_clock_regression_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/ci_wall_clock_regression_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/ci_wall_clock_regression_repair/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - IDENTITY_DIGEST_CHANGED
  - CAPABILITY_SURFACE_EDIT_REQUIRED
  - CI_BUDGET_NOT_MET_AFTER_REPAIR
  - TEST_DELETION_SKIP_OR_WEAKENING
  - NEW_DEPENDENCY_OR_LOCK_CHANGE
  - RUNNER_SHARD_COUNT_OR_WORKFLOW_ARCHITECTURE_CHANGE
  - REMOTE_HOST_OR_DEPLOYMENT_ACTION
  - BASE_DRIFT_REQUIRES_REPLAN
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/ci_wall_clock_regression_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/ci_wall_clock_regression_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/ci_wall_clock_regression_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---
# CI_WALL_CLOCK_REGRESSION_REPAIR_V1
`SPEC_ROUTE=NONE`: this file is the exact task contract. Delivery mode:
`VERTICAL_CAPABILITY_REPAIR_LOOP`, one atom, one PR. Model effort: `LUNA_MAX`.
## DECISION_DELTA
The semantic Catalog is parsed once per exact file content per process; CI job
limits return from temporary A5 headroom to budgets; shard logs name slow
modules even when a job is cancelled.
## UNCERTAINTY_REMOVED
Whether the A5 CI regression is fully explained by repeated Catalog parsing
and can be repaired with zero change to any admission identity.
## CAPABILITY_OR_EVIDENCE
Exact-head and main CI back under budget; semantic/capability digests
byte-identical base vs head; the next wall-clock regression names its module
on its first PR.
## STOP
`CI_WALL_CLOCK_REGRESSION_REPAIR_PASS_READY_FOR_MERGE_GATE`
## NEXT
Return to the product route. No CI-optimization chain.
## Task Outcome Brief
- Owner decision: repair the root cause and restore budgets; no CI redesign.
- Named consumers: every PR's exact-head `validate-tests` matrix; Forge CLI
  processes on the Factory host (one fast parse per process instead of one
  slow parse per identity computation).
- Cheapest falsifier (within ~20 minutes of starting): the two heavy cases in
  3.1 are not >=4x faster, or either identity digest differs from base.
- Terminal outcomes: `CI_WALL_CLOCK_REGRESSION_REPAIR_PASS_READY_FOR_MERGE_GATE`,
  `STOP IDENTITY_DIGEST_CHANGED`, `STOP CAPABILITY_SURFACE_EDIT_REQUIRED`,
  `STOP CI_BUDGET_NOT_MET_AFTER_REPAIR`.
- User-visible result: CI back to ~15-20 min per run; slow modules named in
  every shard log.
- Evidence budget: focused tests only, no full local gate; at most two
  exact-head CI iterations; one optional ~1 h local profile only inside the
  repair iteration.
- Replan trigger: a balanced shard stays over budget (second root cause), or
  the fix needs any file outside this write set.
## 1. Forensic truth (owner-side analysis, 2026-09-25)
- Main before A5, run 36003690161: 16.4 min, shard sum 3015 s. Main after A5
  (PR #329), run 36114465077: 53.2 min, shard sum 7632 s (+77 min) for
  +1 module and +77 cases (+1.4%). Same-day PR #332 without A5: 12-18 min,
  so runners are not the cause.
- Root cause: `hfic_evidence_identity.build_capability_epoch_basis` ->
  `semantic_capability_digest_for_repo` -> `load_semantic_catalog_views`
  re-parses 2.07 MB of Catalog YAML with pure-Python `yaml.safe_load` on every
  call (`catalog/assets/core.yaml`: 2.09 s pure-Python vs 0.33 s
  `CSafeLoader`). A5 calls it from preflight, forge input receipt, session,
  reopened-prior routing, forge-run and `compute_split_identity` (which parses
  again through legacy `evidence_epoch_material`). One heavy case performs
  22 loads; they take ~90% of its 61 s.
- Counterfactual (in-memory patch on the authoring workstation, module totals):
  A5 gold 1316->277 s, ladder 496->131 s, robustness gate 238->70 s, input
  truth 233->76 s, live cohort 135->44 s. The exact design in 3.3: 61->11.2 s
  and 75->13.3 s; 7 parses serve 329 requests.
- Amplifier: the shard plan was last profiled 2026-09-13; 54 of 421 modules are
  unplanned and every new test file reshuffles them. A perfectly balanced but
  unfixed suite would still need ~32 min per shard.
- Masking: timeouts were raised 25->35->60->80 inside the A5 branch;
  `scripts/validate_ci.py` labels 80 "Temporary headroom for the final A5 test
  shards only".
- Not causes: repository size or `git clone` in tests (16 MiB pack), Catalog
  growth (+4% since 2026-09-13), test count.
## 2. Operational invariants
- **I1 Identity neutrality.** For identical bytes the code returns identical
  `semantic_capability_digest_for_repo(root)` and
  `compute_capability_epoch_for_repo(root)[0]`. This diff touches no capability
  surface, so both values at the final head equal the values recorded at base.
  A shifted capability epoch would turn every occupied scientific slot on the
  Factory host into capability drift (`OBSERVABILITY_BLOCKED`) after the next
  release: mismatch is `STOP IDENTITY_DIGEST_CHANGED`.
- **I2 Protected surface, read-only here:** every path in
  `_CAPABILITY_PROTOCOL_FILES` (`src/solana_alpha_lab/factory/hfic_evidence_identity.py`),
  `docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`,
  `configs/factory_semantic_operability_v1.yaml`,
  `catalog/schemas/factory_semantic_operability.schema.json`, and the nine
  semantic-digest asset files: `configs/experiment_capability_registry_v2.yaml`,
  `configs/factory_v1_common_market_feature_surface_v1.yaml`,
  `configs/market_context_definition_v1.yaml`,
  `configs/provider_route_capability_registry_v10.yaml`,
  `src/solana_alpha_lab/factory/research_store.py`,
  `src/solana_alpha_lab/factory/live_cohort_discovery_release.py`,
  `src/solana_alpha_lab/factory/live_cohort_to_forge.py`,
  `registries/decisions_negative_results.yaml`,
  `registries/global_trial_ledger.yaml`. Needing any of them is
  `STOP CAPABILITY_SURFACE_EDIT_REQUIRED`. "Compute identity once per
  operation" lives in that surface and is out of scope.
- **I3 Fail-closed preserved.** Cache parse trees only, never validation
  results, digests or receipts. Every call still reads the files, validates the
  projection and recomputes the digest; YAML errors keep their `yaml.YAMLError`
  subclasses and are never cached; the A5 test that patches
  `semantic_capability_digest_for_repo` keeps working.
- **I4 Mutation isolation.** Callers always receive a private deep copy.
- **I5 Freshness.** The key is the exact decoded file text: a changed file
  (release, clone, temp repo) is re-parsed on the next call; no path or mtime
  keys, no restart needed.
- **I6 Bounded memory.** `lru_cache(maxsize=16)`; one parsed `core.yaml` is
  ~9 MB; one repository state is 7 entries.
- **I7 Parser equivalence.** `CSafeLoader` only while it yields structures equal
  to `yaml.SafeLoader` on every Catalog file (7/7 at authoring, same exception
  classes); otherwise fall back to `yaml.SafeLoader` and keep the cache (record
  it; not a stop).
- **I8** No test deletion/skip/weakening; no dependency or `uv.lock` change
  (PyYAML 6.0.3 already ships libyaml wheels); no runner, shard-count or
  workflow-architecture change; no remote host action.
## 3. Execution
### 3.0 Hygiene
- One fresh worktree at `expected_base`, opened as the only root.
- Run local tests alone: they assert the repository git state is unchanged,
  and a second test process on the same checkout causes false
  `GIT_MUTATION_DETECTED`.
- If `origin/main` has moved: when the new commits touch neither this write set
  nor I2, rebind `expected_base`/`expected_upstream_oid` and redo 3.1 on the new
  base; otherwise `STOP BASE_DRIFT_REQUIRES_REPLAN`. Open PRs #334 and #331
  overlap only on derived `catalog/assets/core.yaml` (resolve with harness_sync).
### 3.1 Baseline at base, before any edit
```text
uv run --locked --managed-python python -B -c "import sys; sys.path.insert(0, 'src'); from pathlib import Path; from solana_alpha_lab.factory_semantic_operability import semantic_capability_digest_for_repo as s; from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo as c; r = Path('.').resolve(); print('semantic_capability_digest_sha256=' + s(r)); print('capability_epoch_sha256=' + c(r)[0])"
uv run --locked --managed-python python -B -m unittest --durations 2 tests.test_forge_evidence_identity_and_owner_gold_v1.IdentityUnitTests.test_corrupt_slot_reservation_remains_unresolved_occupancy tests.test_forge_evidence_identity_and_owner_gold_v1.OwnerGoldSequentialTests.test_g11_capability_change_does_not_free_completed_slot
```
Record both digests and both durations (authoring workstation: ~61 s, ~75 s).
### 3.2 Red guard tests: `tests/test_factory_semantic_operability.py`
Add after the existing imports:
```python
from solana_alpha_lab import factory_semantic_operability as fso  # noqa: E402
```
Add the class:
```python
class SemanticCatalogParseCacheTests(unittest.TestCase):
    def test_repeated_digest_parses_each_catalog_file_once(self) -> None:
        fso._parse_yaml_text.cache_clear()
        first = fso.semantic_capability_digest_for_repo(ROOT)
        parsed = fso._parse_yaml_text.cache_info().misses
        second = fso.semantic_capability_digest_for_repo(ROOT)
        self.assertEqual(first, second)
        self.assertGreater(parsed, 0)
        self.assertEqual(fso._parse_yaml_text.cache_info().misses, parsed)
    def test_cached_views_are_private_copies(self) -> None:
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        asset_id = sorted(assets)[0]
        assets[asset_id]["status"] = "MUTATED_BY_TEST"
        bindings["MUTATED_BY_TEST"] = {}
        again_assets, again_bindings, _ = load_semantic_catalog_views(ROOT)
        self.assertNotEqual(again_assets[asset_id].get("status"), "MUTATED_BY_TEST")
        self.assertNotIn("MUTATED_BY_TEST", again_bindings)
    def test_changed_text_is_reparsed(self) -> None:
        self.assertEqual(fso._load_yaml_text("value: 1\n"), {"value": 1})
        self.assertEqual(fso._load_yaml_text("value: 2\n"), {"value": 2})
        self.assertEqual(fso._load_yaml_text("value: 1\n"), {"value": 1})
    def test_fast_loader_matches_safe_loader_on_catalog_files(self) -> None:
        manifest = yaml.safe_load(
            (ROOT / fso.MANIFEST_RELATIVE).read_text(encoding="utf-8")
        )
        resolver = manifest.get("root_resolver") or {}
        relatives = [fso.PROJECTION_RELATIVE, fso.MANIFEST_RELATIVE]
        relatives += list(resolver.get("asset_registries") or [])
        relatives += list(resolver.get("query_registries") or [])
        for relative in relatives:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(path=relative):
                self.assertEqual(
                    fso._load_yaml_text(text),
                    yaml.load(text, Loader=yaml.SafeLoader),
                )
```
Run `uv run --locked --managed-python python -B -m unittest tests.test_factory_semantic_operability`;
expected red: `AttributeError` on `_parse_yaml_text` / `_load_yaml_text`.
### 3.3 Minimal fix: `src/solana_alpha_lab/factory_semantic_operability.py` (only product file)
```python
import copy
from functools import lru_cache
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
@lru_cache(maxsize=16)
def _parse_yaml_text(text: str) -> Any:
    return yaml.load(text, Loader=_YAML_LOADER)
def _load_yaml_text(text: str) -> Any:
    # Parse trees are shared across callers; only a copy may leave the cache.
    return copy.deepcopy(_parse_yaml_text(text))
```
Swap exactly four calls, `yaml.safe_load(<path>.read_text(encoding="utf-8"))` ->
`_load_yaml_text(<path>.read_text(encoding="utf-8"))`: one in
`load_semantic_projection`, three in `load_semantic_catalog_views`. Keep
`read_text(encoding="utf-8")`, the try/except shapes, schema validation and
every error code. Nothing else changes in `src/`.
### 3.4 Focused green and proofs (alone)
```text
uv run --locked --managed-python python -B -m unittest tests.test_factory_semantic_operability
uv run --locked --managed-python python -B -m unittest tests.test_owner_lifecycle_projection_spine_v1 tests.test_smial_visual_operating_system_v1 tests.test_trading_operations_workbench_v2 tests.test_factory_unattended_operability_closure_v1
uv run --locked --managed-python python -B -m unittest tests.test_forge_evidence_identity_and_owner_gold_v1
```
The last must be 54/54 (~5 min on the authoring workstation, ~22 min before).
Re-run both 3.1 commands: digests equal base (I1); each heavy case >=4x faster
(expected ~11 s and ~13 s).
### 3.5 Streaming shard telemetry: `scripts/run_ci_test_shard.py`
```python
SHARD_SOFT_BUDGET_SECONDS = 20 * 60
SHARD_OVER_SOFT_BUDGET = "CI_SHARD_OVER_SOFT_BUDGET"
SLOWEST_MODULES_SHOWN = 10
class ModuleTimingResult(unittest.TextTestResult):
    """Attribute wall time between test completions to each test module."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.module_seconds: dict[str, float] = {}
        self.module_cases: dict[str, int] = {}
        self._module: str | None = None
        self._mark = time.perf_counter()
    def stopTest(self, test) -> None:
        super().stopTest(test)
        now = time.perf_counter()
        module = type(test).__module__
        if self._module is not None and module != self._module:
            self._report(self._module)
        self._module = module
        self.module_seconds[module] = self.module_seconds.get(module, 0.0) + now - self._mark
        self.module_cases[module] = self.module_cases.get(module, 0) + 1
        self._mark = now
    def stopTestRun(self) -> None:
        super().stopTestRun()
        if self._module is not None:
            self._report(self._module)
    def _report(self, module: str) -> None:
        # Streamed so a job cancelled at its timeout still names finished modules.
        print(
            f"module_done seconds={self.module_seconds[module]:.1f} "
            f"cases={self.module_cases[module]} module={module}",
            flush=True,
        )
```
In `run_shard`: pass `resultclass=ModuleTimingResult` to `unittest.TextTestRunner`.
After the existing summary prints (unchanged) and before the failure branch:
```python
    slowest = sorted(
        result.module_seconds.items(), key=lambda item: (-item[1], item[0])
    )[:SLOWEST_MODULES_SHOWN]
    print(f"slowest_modules={len(slowest)}")
    for module, seconds in slowest:
        print(
            f"slow_module seconds={seconds:.1f} "
            f"cases={result.module_cases[module]} module={module}"
        )
    if elapsed > SHARD_SOFT_BUDGET_SECONDS:
        top = ",".join(f"{module}:{seconds:.0f}s" for module, seconds in slowest[:3])
        print(
            f"::warning title={SHARD_OVER_SOFT_BUDGET}::shard_index={index} "
            f"elapsed_seconds={elapsed:.0f} "
            f"budget_seconds={SHARD_SOFT_BUDGET_SECONDS} top={top}"
        )
```
Exit codes and existing lines stay unchanged; the warning never fails a job.
Test in `tests/test_run_ci_test_shard.py` (add `from unittest import mock`),
following the stale-warning test pattern:
```python
    def test_module_timings_stream_and_soft_budget_only_warns(self) -> None:
        bodies = {
            "test_timing_fast": "self.assertTrue(True)",
            "test_timing_slow": "time.sleep(0.2)",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            for name, body in bodies.items():
                (tests / f"{name}.py").write_text(
                    "import time\nimport unittest\n\n\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_case(self):\n"
                    f"        {body}\n",
                    encoding="utf-8",
                )
            plan = partition.plan_shards(
                {f"tests/{name}.py": 1.0 for name in bodies},
                shard_count=1,
                source_profile_sha256="x",
            )
            plan_path = root / "plan.json"
            partition.write_plan(plan_path, plan)
            tests_dir = str(tests.resolve())
            outputs: dict[int, str] = {}
            try:
                for budget in (3600, 0):
                    capture = io.StringIO()
                    with mock.patch.object(
                        runner, "SHARD_SOFT_BUDGET_SECONDS", budget
                    ), contextlib.redirect_stdout(capture):
                        code = runner.run_shard(
                            index=0, count=1, plan_path=plan_path, root=root
                        )
                    self.assertEqual(code, 0)
                    outputs[budget] = capture.getvalue()
                    for name in bodies:
                        sys.modules.pop(name, None)
            finally:
                while tests_dir in sys.path:
                    sys.path.remove(tests_dir)
        quiet, loud = outputs[3600], outputs[0]
        done = [line for line in quiet.splitlines() if line.startswith("module_done ")]
        slow = [line for line in quiet.splitlines() if line.startswith("slow_module ")]
        self.assertEqual(len(done), 2)
        self.assertTrue(slow[0].endswith("module=test_timing_slow"))
        self.assertNotIn(runner.SHARD_OVER_SOFT_BUDGET, quiet)
        self.assertIn(f"::warning title={runner.SHARD_OVER_SOFT_BUDGET}::", loud)
```
### 3.6 Budgets: `scripts/validate_ci.py`, `.github/workflows/ci.yml`
Replace the two stale comments and values:
```python
# CI job limits are budgets, not headroom: a job near its limit is a
# regression to diagnose from the shard log's module_done/slow_module lines.
# Tracked-only delivery preflight keeps its separate local full-gate cap.
GITHUB_VALIDATE_TIMEOUT_MINUTES = 25
GITHUB_VALIDATE_TESTS_TIMEOUT_MINUTES = 30
```
Edit `ci.yml` by hand to match: `validate-core` and `validate-execution` 25,
`validate-tests` 30, aggregator stays 5. There is no render command;
`validate_workflow_text` checks the file against `expected_workflow()`;
`tests/test_ci.py` reads the constants and should pass unchanged.
```text
uv run --locked --managed-python python -B -m unittest tests.test_run_ci_test_shard tests.test_ci tests.test_ci_test_partition
```
Merge path: editing `scripts/validate_ci.py` nullifies both local validator
bindings (trusted-path drift inside this write set), so exact-head CI owns the
full gate at guarded merge. Expected. Never commit `ci.yml` without the matching
`validate_ci.py` change: that routes the merge to the 25-minute local
tracked-only full gate.
### 3.7 Propagation
```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref 971e0a09e600ae3210b07094dd071824708d6bbd
```
Re-pin `docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json` only if
preflight-push reports its `core.yaml` shadow pin (precedent PR #333). Never
hand-edit derived hashes. Re-run the 3.1 identity command: still equal to base.
### 3.8 Review and finish
Isolated critics on the final inventory. The architecture critic attacks:
(1) can a cached parse ever produce a stale or different digest (key, loader
equivalence, error caching); (2) can a caller mutate shared state; (3) are
exception types, encoding and error codes unchanged; (4) memory in long-running
host processes; (5) does the diff or its propagation touch I2; (6) what passes
all tests yet changes research validity: a silent capability-epoch shift on the
host, closed by the I1 proof. Then Factory Fit / Product Horizon (expected
`CAPABILITY_RADAR_NOW=NONE`), owner readout with the before/after table,
evidence, `bind-evidence --apply` and `--verify`, `preflight-push`
(`ready_for_first_push: true`), push, PR.
## 4. Vertical Capability Repair Loop
```text
baseline at base (identity digests + heavy-case timings)
-> red guard tests
-> one-file fix
-> focused green + I1 identity proof + >=4x local speed proof
-> streaming telemetry + budgets + focused CI-script tests
-> propagation (identity re-proved)
-> isolated review -> finish -> bind -> preflight-push -> ONE PR
-> exact-head CI = vertical smoke on real runners
   |- every validate-tests shard <= 20 min, no soft-budget annotation -> merge-readiness
   |- a shard > 20 min or cancelled, and max/min shard time > 1.3
   |     -> exactly one repair iteration: fresh profile -> plan -> re-review delta -> rebind -> CI
   '- otherwise, or still > 20 min after the repair -> STOP CI_BUDGET_NOT_MET_AFTER_REPAIR
-> owner phrase -> guarded merge -> post-merge readback (record main push CI)
```
Repair iteration (run alone, ~1 h; precedent `CI_SHARD_REBALANCE_AND_ANTI_DRIFT_V1`):
```text
uv run --locked --managed-python python -B scripts/profile_test_wall_clock.py --output local/ci_profile/ci_wall_clock_regression_repair_v1.json --progress
uv run --locked --managed-python python -B scripts/ci_test_partition.py --profile local/ci_profile/ci_wall_clock_regression_repair_v1.json --reserved-manifest configs/execution_domain_v1.json --shard-count 4 --output configs/ci_test_shards_v1.json
```
In-loop repairs (same PR): helper edge cases; test isolation (cache_clear,
sys.modules/sys.path cleanup); `ci.yml`/`validate_ci.py` drift; harness_sync
drift; the task21 shadow pin; CRLF/LF divergence flagged by preflight-push;
timing-test flakiness (assert ordering, never absolute seconds). Never raise a
timeout to pass.
## 5. Definition of Done
1. I1: final-head `semantic_capability_digest_sha256` and
   `capability_epoch_sha256` equal the base values; `git diff --name-only
   <base>..HEAD` contains no I2 path.
2. The four guard tests pass; the focused commands in 3.4 and 3.6 pass; A5 gold
   54/54.
3. Heavy cases >=4x faster than baseline, same machine, run alone.
4. Exact-head CI green; every `validate-tests` shard <= 20 min; each shard log
   has `module_done` and `slow_module` lines; no soft-budget annotation.
5. Budgets: tests 30, core/execution 25, aggregator 5; stale comments replaced.
6. Zero deleted/skipped/weakened tests; `pyproject.toml`/`uv.lock` unchanged;
   zero provider, remote-host or deployment actions.
7. Post-merge readback records the main push CI (was 53.2 min in run
   36114465077; target <= 22 min). A miss is reported with its `slow_module`
   lines, not retuned inside this atom.
## 6. Non-goals
Other `yaml.safe_load` call sites; identity computed once per operation (I2
surface); edits to A5 tests or fixtures; the unplanned-module assignment
algorithm; more shards or larger runners; per-test budgets; deploying to the
Factory host.
## 7. Rollback and limitations
Rollback: revert the merge commit. No persisted state, schema, identity or data
changes; the cache is in-process only. Limitations: CLI tests that spawn
subprocesses (`tests/test_hfic_cli.py`) still pay one C-loader parse per child
(~0.3 s); pre-existing uncached YAML reads elsewhere are unchanged.
## 8. Final return
```yaml
capability: CI_WALL_CLOCK_REGRESSION_REPAIR_V1
base: <40hex>
head: <40hex>
identity:
  semantic_capability_digest_sha256: {base: <hex>, head: <hex>, equal: true}
  capability_epoch_sha256: {base: <hex>, head: <hex>, equal: true}
  protected_paths_touched: []
parse_cache:
  loader: CSafeLoader
  catalog_structural_equality: 7/7
local_proof_seconds:
  corrupt_slot_case: {base: <s>, head: <s>}
  g11_capability_case: {base: <s>, head: <s>}
ci:
  before_main: {run: 36114465077, minutes: 53.2, max_shard_minutes: 52.8}
  exact_head: {run: <id>, minutes: <m>, shard_minutes: [<m>, <m>, <m>, <m>]}
  post_merge_main: {run: <id>, minutes: <m>}
budgets_minutes: {validate_core: 25, validate_execution: 25, validate_tests: 30, aggregator: 5}
rebalance: NOT_NEEDED | DONE
tests_weakened: 0
remote_actions: 0
```
