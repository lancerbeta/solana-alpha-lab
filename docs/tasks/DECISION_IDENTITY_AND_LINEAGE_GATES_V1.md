---
task_id: DECISION_IDENTITY_AND_LINEAGE_GATES_V1
task_version: '1.0'
status: READY
as_of: '2026-09-26'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
  - DIRECT_CODEX_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 05abd3b328f28af671d2086012b4562f9cf414f1
  expected_upstream: origin/main
  expected_upstream_oid: 05abd3b328f28af671d2086012b4562f9cf414f1
  expected_branch: cursor/decision-identity-and-lineage-gates-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Evaluate every SignalDecision against an explicit processing clock, bind
  one signal_decision_id to one decision body, fail closed on StrategyVersion
  content drift under an unchanged version, and make a position traceable in
  SQLite to spec hash, decision fingerprint, evidence refs and separate entry
  and exit reasons. Series PAPER_SHADOW_EXECUTION_INTEGRITY atom 3 of 5.
managed_write_set:
  - docs/tasks/DECISION_IDENTITY_AND_LINEAGE_GATES_V1.md
  - docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/trading_operations.py
  - tests/test_paper_shadow_execution_integrity_vertical_v1.py
  - tests/test_factory_strategy_execution_boundary_v1.py
  - tests/test_trading_runtime_policy_v1.py
  - tests/test_trading_runtime_admission_concurrency_v1.py
  - tests/test_paper_shadow_accounting_and_control_v1.py
  - tests/test_trading_operations_workbench_v2.py
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_risk_and_economics_v1.py
  - tests/test_owner_lifecycle_projection_spine_v1.py
  - scripts/factory_paper_shadow_operator_smoke.py
  - docs/contracts/trading_runtime_policy_v1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/decision_identity_and_lineage_gates/a1_owner_readout_v1.md
  - docs/evidence/decision_identity_and_lineage_gates/a1_delivery_completion_evidence_v1.json
  - docs/evidence/decision_identity_and_lineage_gates/a1_delivery_independent_review_v1.json
  - docs/evidence/decision_identity_and_lineage_gates/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PROVIDER_API_RPC_WSS_REQUIRED
  - CREDENTIAL_VALUE_REQUIRED
  - VPS_OR_DEPLOY_MUTATION_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - SIGNAL_OR_EXIT_SCHEMA_CHANGE_REQUIRED
  - A2_NOT_MERGED
  - TEST_DELETION_SKIP_OR_WEAKENING
  - WRITE_SET_EXPANSION_REQUIRED
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
    ARCHITECTURE_DECISIONS:
      - docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/decision_identity_and_lineage_gates/a1_delivery_completion_evidence_v1.json
      - docs/evidence/decision_identity_and_lineage_gates/a1_delivery_independent_review_v1.json
      - docs/evidence/decision_identity_and_lineage_gates/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---
# DECISION_IDENTITY_AND_LINEAGE_GATES_V1
`SPEC_ROUTE=DESIGN_SPEC`: design in `docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md` §7;
this file is the exact task contract. Delivery mode: `VERTICAL_CAPABILITY_REPAIR_LOOP`, one atom, one PR.
Series atom 3 of 5; requires A2 merged. Model effort: `LUNA_MAX`.
## DECISION_DELTA
A SignalDecision is accepted only with an explicit `as_of`, never from the future beyond 2 s, and one id
means one body; a StrategyVersion whose content changed under the same version cannot run; every position
carries its spec hash, decision fingerprint, evidence refs and separate entry and exit reasons.
## UNCERTAINTY_REMOVED
Whether a runner bug (missing clock, replayed or re-signed decision, edited strategy file) can silently
produce positions, and whether a position can be traced to its evidence from the store alone.
## CAPABILITY_OR_EVIDENCE
Audit cases that were accepted — day-old decision without `as_of`, `as_of` an hour before `decision_at`,
same id with another mint, `NO_ENTER` after `ENTER` — are rejected with exact codes; V2 ExitDecision can no
longer close a V1 position; lineage columns and events are readable after J1.
## STOP
`DECISION_IDENTITY_AND_LINEAGE_GATES_PASS_READY_FOR_MERGE_GATE`
## NEXT
`PAPER_PLANE_READ_FRESHNESS_V1` (series atom 4).
## Task Outcome Brief
- Owner decision: fail closed on identity; no schema change of SignalDecision/ExitDecision contracts.
- Named consumers: the future runner (must pass its clock); replay/backtest harnesses (explicit clock);
  the owner reading traces; A5 (attempts link to fingerprinted decisions).
- Cheapest falsifier (≤ 20 min): a call site in production code (not tests) cannot supply `as_of`.
- Terminal outcomes: PASS; `STOP SIGNAL_OR_EXIT_SCHEMA_CHANGE_REQUIRED`; `STOP WRITE_SET_EXPANSION_REQUIRED`.
- User-visible result: traces show the exit decision step; readouts can cite evidence refs per position.
- Evidence budget: focused tests; at most two exact-head CI iterations.
- Replan trigger: a caller outside the listed tests and smoke script omits `as_of`.
## 1. Forensic truth (audit + independent reproduction)
- `as_of=None` → `as_of_dt = decision_at` → age 0: a day-old decision opened a position (2/2). `as_of` an
  hour before `decision_at` → negative age → accepted.
- Retry with the same `signal_decision_id` compares only epoch, strategy and bot: another mint answered
  `idempotent=true` with the old mint; `NO_ENTER` under the id of an open ENTER position answered
  `opened=false` without error. The policy APPLY path already rejects the analogue
  (`POLICY_IDEMPOTENCY_REQUEST_MISMATCH`).
- SQLite has no StrategyVersion spec hash, no decision fingerprint, no evidence refs; `apply_exit_decision`
  overwrites `positions.reason_code` with the exit reason and writes no event; `accept_exit_decision` checks
  the ExitDecision version against the passed strategy object, not against the position (V2 closed V1).
## 2. Operational invariants
- G1 Clock: `as_of` required; `decision_at - as_of > 2 s` → `SIGNAL_DECISION_FROM_FUTURE`.
- G2 Identity: `signal_decision_sha256 = canonical_spec_sha256(validated decision)`; a different body under
  an id that owns a position → `SIGNAL_DECISION_IDEMPOTENCY_MISMATCH`; any non-ENTER decision under an id
  that owns a position → the same code. Legacy rows with NULL fingerprint skip the ENTER comparison.
- G3 Spec drift: `start_bot` with a stored spec hash ≠ loaded hash → `STRATEGY_SPEC_DRIFT`; NULL backfilled.
- G4 Exit identity: ExitDecision `strategy_version` ≠ `positions.strategy_version_label` →
  `EXIT_POSITION_VERSION_MISMATCH`.
- G5 Lineage: columns `positions.signal_decision_sha256`, `positions.strategy_spec_sha256`,
  `positions.exit_reason_code`, `bot_instances.strategy_spec_sha256`; `SIGNAL_DECISION_ACCEPTED` payload adds
  `signal_decision_sha256`, `evidence_refs`, `source_hypothesis_refs`, `first_reliable_available_at`,
  `strategy_spec_sha256`; `EXIT_DECISION_ACCEPTED` event (stage `POSITION`); entry `reason_code` preserved.
- G6 Existing test call sites gain explicit `as_of` only (the decision's `decision_at` or their own
  clock); no other test change; zero weakening.
## 3. Execution
### 3.0 Hygiene and binding
Fresh worktree from `origin/main` containing A2 (`STOP A2_NOT_MERGED` otherwise); bind base; commit this contract.
### 3.1 Baseline
```text
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1 tests.test_factory_strategy_execution_boundary_v1
```
### 3.2 Red: add `DecisionIdentityGateTests` to the vertical module
```python
from solana_alpha_lab.factory.paper_plane import accept_exit_decision  # noqa: E402  (extend the import)
from solana_alpha_lab.factory.strategy_runtime import canonical_spec_sha256  # noqa: E402


def exit_decision(
    position_id: str,
    *,
    exit_id: str = "EXITDEC-VERT-1",
    strategy_version: str = "V1",
    reason_code: str = "VERTICAL_EXIT",
) -> dict[str, Any]:
    return {
        "schema": "smial.exit-decision",
        "schema_version": "1.0",
        "exit_decision_id": exit_id,
        "position_id": position_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": strategy_version,
        "activation_epoch_id": EPOCH,
        "decision_at": "2026-09-03T12:20:00Z",
        "first_reliable_available_at": "2026-09-03T12:19:00Z",
        "action": "EXIT",
        "reason_code": reason_code,
        "evidence_refs": ["sha256:" + "e" * 64],
    }


class DecisionIdentityGateTests(StoreCase):
    """A3 DECISION_IDENTITY_AND_LINEAGE_GATES_V1."""

    def test_as_of_is_required(self) -> None:
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_AS_OF_REQUIRED"):
            accept(self.store(), self.strategy, "SIGDEC-VERT-NOCLOCK", as_of=None)

    def test_future_decision_is_rejected_beyond_skew(self) -> None:
        store = self.store()
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_FROM_FUTURE"):
            accept(store, self.strategy, "SIGDEC-VERT-FUT-3", decision_at="2026-09-03T12:10:03Z")
        self.assertTrue(accept(store, self.strategy, "SIGDEC-VERT-FUT-2", decision_at="2026-09-03T12:10:02Z")["opened"])

    def test_one_id_binds_one_body(self) -> None:
        store = self.store()
        self.assertTrue(accept(store, self.strategy, "SIGDEC-VERT-ID")["opened"])
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_IDEMPOTENCY_MISMATCH"):
            accept(store, self.strategy, "SIGDEC-VERT-ID", mint=MINT_B)
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_IDEMPOTENCY_MISMATCH"):
            accept(store, self.strategy, "SIGDEC-VERT-ID", action="NO_ENTER")
        again = accept(store, self.strategy, "SIGDEC-VERT-ID")
        self.assertEqual((again["idempotent"], again["state"]), (True, "OPEN"))
        self.assertEqual(store.get_position("POS-SIG-SIGDEC-VERT-ID")["mint"], MINT)

    def test_exit_decision_version_must_match_the_position(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-XVER")
        v2 = dict(self.strategy, strategy_version="V2")
        with self.assertRaisesRegex(PaperPlaneError, "EXIT_POSITION_VERSION_MISMATCH"):
            accept_exit_decision(ROOT, store, strategy=v2, exit_decision=exit_decision(pid, strategy_version="V2"), known_activation_epochs=KNOWN_EPOCHS)
        self.assertEqual(store.get_position(pid)["state"], "OPEN")

    def test_strategy_spec_drift_fails_closed(self) -> None:
        store = self.store()
        store.start_bot(self.strategy, mode="PAPER", activation_epoch_id=EPOCH)
        drifted = dict(self.strategy, spec_sha256="0" * 64)
        with self.assertRaisesRegex(PaperPlaneError, "STRATEGY_SPEC_DRIFT"):
            store.start_bot(drifted, mode="PAPER", activation_epoch_id=EPOCH)

    def test_position_lineage_is_queryable_from_the_store(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-LINEAGE")
        accept_exit_decision(ROOT, store, strategy=self.strategy, exit_decision=exit_decision(pid), known_activation_epochs=KNOWN_EPOCHS)
        row = store.get_position(pid)
        self.assertEqual(row["signal_decision_sha256"], canonical_spec_sha256(signal("SIGDEC-VERT-LINEAGE")))
        self.assertEqual(row["strategy_spec_sha256"], self.strategy["spec_sha256"])
        self.assertEqual((row["reason_code"], row["exit_reason_code"]), ("VERTICAL_ENTER", "VERTICAL_EXIT"))
        events = {e["event_type"]: e["payload"] for e in store.execution_events() if e.get("position_id") == pid or (e.get("payload") or {}).get("signal_decision_id") == "SIGDEC-VERT-LINEAGE"}
        self.assertEqual(events["SIGNAL_DECISION_ACCEPTED"]["evidence_refs"], signal("SIGDEC-VERT-LINEAGE")["evidence_refs"])
        self.assertEqual(events["EXIT_DECISION_ACCEPTED"]["exit_decision_id"], "EXITDEC-VERT-1")
        trading = compose_trading_operations(ROOT, store)
        trace = next(t for t in trading["traces"] if t.get("signal_decision_id") == "SIGDEC-VERT-LINEAGE")
        stages = {item["event_type"]: item["stage"] for item in trace["events"]}
        self.assertEqual(stages["EXIT_DECISION_ACCEPTED"], "POSITION")
```
Expected red: all six.
### 3.3 Fix: `paper_plane.py`
1. `from solana_alpha_lab.factory.strategy_runtime import canonical_spec_sha256` (extend the import);
   `SIGNAL_MAX_CLOCK_SKEW_SECONDS = 2`.
2. Migration `_migrate_decision_identity_v1()` (called after A2's): `_ensure_column` for
   `positions.signal_decision_sha256 TEXT`, `positions.strategy_spec_sha256 TEXT`,
   `positions.exit_reason_code TEXT`, `bot_instances.strategy_spec_sha256 TEXT`.
3. `start_bot`: compute `spec = str(strategy.get("spec_sha256") or "") or None`. For an existing bot:
   `known and spec and known != spec` → `STRATEGY_SPEC_DRIFT`; `not known and spec` → `UPDATE bot_instances
   SET strategy_spec_sha256 = ? WHERE bot_instance_id = ? AND strategy_spec_sha256 IS NULL`, then return the
   refreshed row (existing status rules unchanged). New bot: insert the column; `ON CONFLICT` keeps
   `COALESCE(bot_instances.strategy_spec_sha256, excluded.strategy_spec_sha256)`.
4. `open_position_from_signal(..., signal_decision_sha256: str | None = None, strategy_spec_sha256: str |
   None = None)`: insert both columns.
5. `accept_signal_decision`:
```python
    if mode not in {"PAPER", "SHADOW"}:
        raise PaperPlaneError("BOT_MODE_INVALID")
    if not as_of:
        raise PaperPlaneError("SIGNAL_AS_OF_REQUIRED")
    ...  # unchanged: normalize, eligibility, validate_signal_decision, strategy id/version, epoch
    decision_sha256 = canonical_spec_sha256(decision)
    as_of_dt = _parse_utc(as_of)
    decision_at = _parse_utc(decision["decision_at"])
    if (decision_at - as_of_dt).total_seconds() > SIGNAL_MAX_CLOCK_SKEW_SECONDS:
        raise PaperPlaneError("SIGNAL_DECISION_FROM_FUTURE")
    ...  # unchanged PIT rule (first_reliable_available_at > decision_at with ENTER)
    lineage = {
        "signal_decision_sha256": decision_sha256,
        "evidence_refs": list(decision["evidence_refs"]),
        "source_hypothesis_refs": list(decision["source_hypothesis_refs"]),
        "first_reliable_available_at": decision["first_reliable_available_at"],
        "strategy_spec_sha256": strategy.get("spec_sha256"),
    }
    position_id = position_id_for_signal_decision(str(decision["signal_decision_id"]))
    action = str(decision["action"])
    if action != "ENTER":
        if store.get_position(position_id) is not None:
            raise PaperPlaneError("SIGNAL_DECISION_IDEMPOTENCY_MISMATCH")
        ...  # unchanged SIGNAL_DECISION_ACCEPTED append, payload extended with **lineage; return
```
   Inside the admission transaction, right after `existing = store.get_position(position_id)`:
```python
        if existing is not None:
            stored = existing.get("signal_decision_sha256")
            if stored not in {None, ""} and str(stored) != decision_sha256:
                raise PaperPlaneError("SIGNAL_DECISION_IDEMPOTENCY_MISMATCH")
```
   Pass `signal_decision_sha256=decision_sha256` and `strategy_spec_sha256=strategy.get("spec_sha256")` to
   `open_position_from_signal`; extend the ENTER `SIGNAL_DECISION_ACCEPTED` payload with `**lineage`. With
   `as_of` mandatory, A2's `as_of_dt = _parse_utc(as_of) if as_of else ...` becomes `_parse_utc(as_of)`.
6. `accept_exit_decision`, after the existing position strategy check:
```python
    label = position.get("strategy_version_label")
    if label and str(label) != str(decision["strategy_version"]):
        raise PaperPlaneError("EXIT_POSITION_VERSION_MISMATCH")
```
7. `apply_exit_decision` (already atomic since A1): write `exit_decision_id` and `exit_reason_code` (never
   `reason_code`); transition `OPEN|PARTIAL|UNKNOWN → EXIT_REQUIRED` as today (`EXIT_REQUIRED` stays); then
```python
            self.append_execution_event(
                event_type="EXIT_DECISION_ACCEPTED",
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={
                    **_identity_fields(position),
                    "exit_decision_id": str(exit_decision["exit_decision_id"]),
                    "exit_reason_code": str(exit_decision["reason_code"]),
                    "from_state": from_state,
                    "to_state": "EXIT_REQUIRED",
                    "exit_decision_at": exit_decision.get("decision_at"),
                    "evidence_refs": list(exit_decision.get("evidence_refs") or []),
                },
            )
```
   (Named `exit_decision_at` so the trace's first-wins `decision_at` keeps the entry time.)
### 3.4 Fix: `trading_operations.py`
`EVENT_STAGE["EXIT_DECISION_ACCEPTED"] = "POSITION"`.
### 3.5 Call sites and contract
- Run the execution-domain suite; every failure `SIGNAL_AS_OF_REQUIRED` in the listed tests or in
  `scripts/factory_paper_shadow_operator_smoke.py` gets `as_of=<decision_at of that decision>` (or the test's
  own clock). No other edit to those files. List each changed call site in the readout.
- `docs/contracts/trading_runtime_policy_v1.md`: a short "Decision identity" subsection (G1–G5).
- Design file: note A3 delivered.
### 3.6 Focused green, suite, propagation
```text
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_accounting_and_control_v1 tests.test_trading_runtime_admission_concurrency_v1 tests.test_factory_strategy_execution_boundary_v1 tests.test_trading_runtime_policy_v1 tests.test_trading_runtime_policy_backup_restore_v1 tests.test_trading_operations_workbench_v2 tests.test_owner_trading_operability_workbench_v1 tests.test_owner_operations_cockpit_v1 tests.test_factory_v1_owner_cockpit tests.test_risk_and_economics_v1 tests.test_owner_lifecycle_projection_spine_v1 tests.test_early_state_to_paper_vertical_slice tests.test_factory_unattended_shadow_vertical_slice tests.test_execution_domain_modularity_and_fast_ci_v1 tests.test_science_to_strategy_handoff_v1
uv run --locked --managed-python python -B scripts/factory_paper_shadow_operator_smoke.py
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <expected_base>
```
The smoke script runs in its own temp directory; confirm it writes nothing inside the repository.
### 3.7 Review and finish
Critics attack: (1) any production path that can still accept without a clock; (2) fingerprint stability
(key order, list order inside `evidence_refs`, unicode) — `canonical_spec_sha256` sorts keys, lists keep
order: a producer that reorders refs is a new body by design, say so; (3) legacy rows with NULL fingerprint
or spec hash; (4) the VPS heartbeat (`run_shadow_tick`, v1.0) after deploy: first tick backfills the bot
spec hash; a later edit of the commissioning strategy without a version bump now stops the heartbeat with
`STRATEGY_SPEC_DRIFT` — state it in the readout as intended fail-closed behavior; (5) what passes every
test yet breaks research validity: a replay harness that used `as_of=None` silently changes meaning — now
it fails loudly. Then Factory Fit, Russian readout, evidence, bind, preflight-push, PR.
## 4. Vertical Capability Repair Loop
```text
bind (A2 merged) + baseline
-> red DecisionIdentityGateTests (clock, future, identity, exit version, spec drift, lineage)
-> gates + lineage (3.3, 3.4)
-> execution-domain suite: add explicit as_of at failing call sites only (3.5)
   '- a production caller without a clock appears -> STOP WRITE_SET_EXPANSION_REQUIRED
-> smoke script + harness_sync -> isolated review -> finish -> bind -> preflight-push -> ONE PR
-> exact-head CI -> merge-readiness -> owner phrase -> guarded merge -> post-merge readback
```
## 5. Definition of Done
1. `DecisionIdentityGateTests`, `EntryIntentIntegrityTests`, `WriteIntegrityTests` green.
2. The four audit gate cases rejected with exact codes; identical replay stays idempotent.
3. Lineage readable from SQLite and events after J1; entry and exit reasons separate; exit step visible in
   the trace (`POSITION` stage proven by `EXIT_DECISION_ACCEPTED`).
4. `STRATEGY_SPEC_DRIFT` on content drift; NULL backfill works on an old store copy.
5. Only `as_of` additions in existing tests and the smoke script; suite green; zero weakened tests.
## 6. Non-goals
Schema changes of SignalDecision/ExitDecision; staleness for exits (exits stay privileged); OD-3 (exit
validity after epoch deactivation); readonly freshness (A4); attempts (A5).
## 7. Rollback and limitations
Rollback: revert the merge commit; added columns are ignored by old code. Limitation: legacy positions
(pre-A3) keep NULL fingerprints and skip the ENTER body comparison.
## 8. Final return
```yaml
capability: DECISION_IDENTITY_AND_LINEAGE_GATES_V1
base: <40hex>
head: <40hex>
gates:
  as_of_missing: SIGNAL_AS_OF_REQUIRED
  future_beyond_skew: SIGNAL_DECISION_FROM_FUTURE
  same_id_other_body: SIGNAL_DECISION_IDEMPOTENCY_MISMATCH
  exit_version_mismatch: EXIT_POSITION_VERSION_MISMATCH
  spec_drift: STRATEGY_SPEC_DRIFT
lineage_columns: [signal_decision_sha256, strategy_spec_sha256, exit_reason_code, bot.strategy_spec_sha256]
call_sites_given_as_of: [<file:line>]
tests_weakened: 0
ci: {exact_head_run: <id>, result: success}
pr: <url>
```
