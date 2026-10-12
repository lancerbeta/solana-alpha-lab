"""Native lock/restore proofs, with synthetic source bytes and lowest HTTP seam."""
from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime, timedelta
import copy
from decimal import Decimal
import json
import shutil
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
from tests import test_trading_core_operational_closure_v1 as closure_fixture
from solana_alpha_lab.factory.hfic_research_scope import sha256_of
from solana_alpha_lab.factory.paper_plane import PaperPlaneError, PaperPlaneStore
from solana_alpha_lab.factory.trading_adapters import (
    ENDPOINT, REGISTRY_PATH, ROUTE_ID, JupiterQuoteAdapter,
)
from solana_alpha_lab.factory.trading_coordinator import TradingCoordinator, restore_native_backup
from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner


class _GrantedRecordingAdapter(JupiterQuoteAdapter):
    """Retain original effects independently while keeping production quota checks."""
    def __init__(self, ledger, grant):
        self.ledger = ledger
        super().__init__(timeout_seconds=1, max_response_bytes=8192, grant=grant,
            credential_supplier=lambda: None)

    def dispatch(self, attempt, request, *, as_of):
        result, proof = super().dispatch(attempt, request, as_of=as_of)
        receipt = {"attempt": attempt, "request": request, "result": result}
        receipt["receipt_sha256"] = sha256_of(receipt)
        with closing(sqlite3.connect(self.ledger)) as connection:
            connection.execute("INSERT INTO calls(attempt_id,receipt_json) VALUES (?,?)",
                (attempt["attempt_id"], json.dumps(receipt, sort_keys=True)))
            connection.commit()
        return result, proof


class OperationalRecoveryTests(unittest.TestCase):
    # Compose only fixture helpers; inherited driver tests would duplicate the suite.
    setUp = closure_fixture.OperatingDriverTests.setUp
    tearDown = closure_fixture.OperatingDriverTests.tearDown
    prepare = closure_fixture.OperatingDriverTests.prepare
    start_operating = closure_fixture.OperatingDriverTests.start_operating
    quote_inputs = closure_fixture.OperatingDriverTests.quote_inputs
    wire_files = closure_fixture.OperatingDriverTests.wire_files
    ledger_receipts = closure_fixture.OperatingDriverTests.ledger_receipts
    recovery_cut = closure_fixture.OperatingDriverTests.recovery_cut

    def empty_ledger(self):
        ledger, _ = self.wire_files()
        with closing(sqlite3.connect(ledger)) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS calls(call_id INTEGER PRIMARY KEY,attempt_id TEXT NOT NULL,receipt_json TEXT)")
            connection.commit()
        return ledger

    def restored(self, backup, *, suffix="restored", adapter=None, mode="SHADOW"):
        destination = self.root / "local" / suffix
        destination.mkdir()
        shutil.copyfile(self.data / "offline_runtime.json", destination / "offline_runtime.json")
        runner = TradingContinuityRunner(self.root, data_root=destination)
        outcome = restore_native_backup(backup_path=backup, destination_runner=runner)
        self.assertFalse(outcome["new_effects_enabled"])
        coordinator = TradingCoordinator(runner, mode=mode, clock=lambda: self.now,
            quote_adapter=adapter)
        self.assertTrue(coordinator.status()["restore_guard"])
        return runner, coordinator

    def acknowledge(self, coordinator, cut):
        inventory = coordinator.status()["inventory"]
        coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(inventory),
            as_of=cut["as_of"], cut=cut)
        self.assertFalse(coordinator.status()["restore_guard"])

    def claims(self, runner):
        with closing(PaperPlaneStore(runner.store_path, readonly=True)) as store:
            return store.filtered_execution_events(event_type="QUOTE_CALL_CLAIMED")

    def witness_operating(self):
        original_inputs = self.quote_inputs

        def witness_profile(**kwargs):
            self.profile["quote"]["asset_metadata_file"] = None
            original_inputs(**kwargs)

        with patch.object(self, "quote_inputs", side_effect=witness_profile):
            self.start_operating(mode="SHADOW")
        self.assertIsNone(self.profile["quote"]["asset_metadata_file"])

    def original_grant(self):
        grant = {"quote_calls_authorized": True, "route_id": ROUTE_ID, "endpoint": ENDPOINT,
            "registry_path": REGISTRY_PATH, "mode": "SHADOW", "activation_epoch_id": self.epoch,
            "strategy_sha256": self.runner.strategy["spec_sha256"], "signing_authorized": False,
            "financial_authority": False, "calls_max": 1, "expires_at": "2026-10-05T14:00:00Z"}
        return {**grant, "grant_sha256": sha256_of(grant)}

    def production_cut(self, backup, *, effects=()):
        cut = self.coordinator.export_recovery_cut(backup_path=backup, effects=list(effects),
            external_cut_id="INDEPENDENT-SYNTHETIC-DELAYED-CUT", as_of=self.now.isoformat().replace("+00:00", "Z"))
        return {**cut, "cut_sha256": sha256_of(cut)}

    def partial_shadow(self):
        self.start_operating(mode="SHADOW", exit_cap="4000000000000")
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "120000000"},
                                      {"outAmount": "132000000"}, {"outAmount": "60000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.tick()
        original = self.runner.readback()["positions"][0]
        self.assertEqual(Decimal(original["remaining_qty_dec"]), Decimal("6000000"))
        self.assertEqual(Decimal(original["remaining_cost_basis_usd_dec"]), Decimal("18"))
        return ledger, original

    def test_partial_projection_damage_blocks_ordinary_quote_until_truthful_restoration(self):
        metrics = []
        for field, bad in (("remaining_qty_dec", "9000000"), ("remaining_cost_basis_usd_dec", "99"),
                           ("realized_net_pnl_usd_dec", "99")):
            with self.subTest(field=field):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    ledger, original = case.partial_shadow()
                    before = case.runner.readback()
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        with store.immediate_write():
                            store._conn.execute("UPDATE positions SET " + field + "=? WHERE position_id=?", (bad, original["position_id"]))
                    case.coordinator.run(ticks=2)
                    view = case.coordinator.status()
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
                    self.assertEqual(view["inventory"]["position_count"], 1)
                    self.assertIsNone(view["inventory"]["outstanding_cost_basis_usd"])
                    self.assertEqual(len(case.ledger_receipts(ledger)), 2)
                    self.assertEqual(case.runner.readback()["modeled_attempts"], before["modeled_attempts"])
                    self.assertEqual(case.runner.readback()["modeled_results"], before["modeled_results"])
                    self.assertIn("EXIT_INVENTORY_WITNESS_CONFLICT", {row["reason"] for row in view["incidents"] if row["active"]})
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        self.assertEqual(store.get_position(original["position_id"])[field], bad)
                        with store.immediate_write():
                            store._conn.execute("UPDATE positions SET " + field + "=? WHERE position_id=?", (original[field], original["position_id"]))
                    case.coordinator.tick()
                    next_partial = case.runner.readback()["positions"][0]
                    self.assertEqual(Decimal(next_partial["remaining_qty_dec"]), Decimal("2000000"))
                    self.assertEqual(Decimal(next_partial["remaining_cost_basis_usd_dec"]), Decimal("6"))
                    self.assertEqual(Decimal(next_partial["realized_net_pnl_usd_dec"]), Decimal("1.20"))
                    self.assertEqual(Decimal(case.ledger_receipts(ledger)[-1]["attempt"]["remaining_quantity"]), Decimal("6000000"))
                    case.coordinator.tick()
                    final = case.runner.readback()["positions"][0]
                    self.assertEqual(final["state"], "RECONCILED")
                    self.assertEqual(Decimal(final["remaining_qty_dec"]), 0)
                    self.assertEqual(Decimal(final["remaining_cost_basis_usd_dec"]), 0)
                    self.assertEqual(Decimal(final["remaining_entry_fee_usd_dec"]), 0)
                    self.assertEqual(Decimal(final["realized_net_pnl_usd_dec"]), Decimal("1.20"))
                    self.assertEqual(case.coordinator.status()["status"], "READY")
                    self.assertEqual(len(case.ledger_receipts(ledger)), 4)
                    metrics.append({"damaged": field, "denied_extra_quotes": 0, "restored_second_partial_quantity": "2000000",
                        "restored_second_partial_cost_usd": "6", "terminal_net_usd": "1.20"})
                finally:
                    case.tearDown()
        self.metrics = {"cases": metrics}

    def test_native_projection_race_between_preflight_and_claim_denies_before_attempt(self):
        ledger, original = self.partial_shadow()
        before = self.runner.readback()
        native_inputs = self.coordinator._inputs
        reached = []

        def corrupt_after_preflight(*args):
            request = native_inputs(*args)
            if args[-2] == "EXIT":
                reached.append(request["remaining_quantity"])
                with closing(PaperPlaneStore(self.runner.store_path)) as writer:
                    with writer.immediate_write():
                        writer._conn.execute("UPDATE positions SET remaining_qty_dec='9000000' WHERE position_id=?", (original["position_id"],))
            return request

        with patch.object(self.coordinator, "_inputs", side_effect=corrupt_after_preflight):
            self.coordinator.tick()
        self.assertEqual([Decimal(value) for value in reached], [Decimal("6000000")])
        self.assertEqual(self.runner.readback()["modeled_attempts"], before["modeled_attempts"])
        self.assertEqual(self.runner.readback()["modeled_results"], before["modeled_results"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            with store.immediate_write():
                store._conn.execute("UPDATE positions SET remaining_qty_dec=? WHERE position_id=?",
                    (original["remaining_qty_dec"], original["position_id"]))
            stale_request = native_inputs(self.runner.for_epoch(original["activation_epoch_id"]), store, original,
                self.profile, "EXIT", "2026-10-05T13:10:00Z")
        # A genuine ordinary result now consumes another 4M. The older request
        # is internally intact, but its 6M reservation cannot send against 2M.
        self.coordinator.tick()
        self.assertEqual(Decimal(self.runner.readback()["positions"][0]["remaining_qty_dec"]), Decimal("2000000"))
        original_attempts = self.runner.readback()["modeled_attempts"]
        with patch.object(self.coordinator, "_inputs", return_value=stale_request):
            self.coordinator.tick()
        self.assertEqual(self.runner.readback()["modeled_attempts"], original_attempts)
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.coordinator.tick()
        self.assertEqual(len(self.ledger_receipts(ledger)), 4)
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "RECONCILED")
        self.metrics = {"preflight_proved_quantity": "6000000", "native_writer_mutation": "9000000",
            "new_committed_attempts_while_corrupt": 0, "new_quote_effects_while_corrupt": 0, "atomic_claim_guard": "DENY",
            "genuine_result_reduces_quantity_to": "2000000", "stale_larger_request_extra_quotes": 0}

    def test_native_projection_race_after_claim_retains_original_capture_without_resend(self):
        ledger, original = self.partial_shadow()
        before = self.runner.readback()
        adapter = self.coordinator.quote_adapter
        native_dispatch = adapter.dispatch
        captured = []

        def corrupt_after_effect(*args, **kwargs):
            result, proof = native_dispatch(*args, **kwargs)
            captured.append(result)
            with closing(PaperPlaneStore(self.runner.store_path)) as writer:
                with writer.immediate_write():
                    writer._conn.execute("UPDATE positions SET entered_notional_usd_dec='31' WHERE position_id=?", (original["position_id"],))
            return result, proof

        with patch.object(adapter, "dispatch", side_effect=corrupt_after_effect):
            self.coordinator.tick()
        damaged = self.runner.readback()
        self.assertEqual(damaged["modeled_results"], before["modeled_results"])
        self.assertEqual(len(damaged["modeled_attempts"]), len(before["modeled_attempts"]) + 1)
        pending = damaged["modeled_attempts"][-1]["payload"]
        self.assertEqual(Decimal(pending["remaining_quantity"]), Decimal("6000000"))
        self.assertEqual(damaged["positions"][0]["state"], "EXITING")
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.coordinator.run(ticks=2)
        self.assertEqual(self.runner.readback()["modeled_results"], before["modeled_results"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.assertEqual(self.coordinator.status()["pending_attempts"], 1)
        self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            retained = store.get_execution_event("CAPTURE-" + pending["attempt_id"])
            self.assertEqual(retained["payload"]["result"], captured[0])
            with store.immediate_write():
                store._conn.execute("UPDATE positions SET entered_notional_usd_dec=? WHERE position_id=?",
                    (original["entered_notional_usd_dec"], original["position_id"]))
        self.coordinator.tick()
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 4)
        self.assertEqual(len({row["attempt"]["attempt_id"] for row in receipts}), 4)
        self.assertEqual(sum(row["attempt"]["attempt_id"] == pending["attempt_id"] for row in receipts), 1)
        restored = self.runner.readback()
        self.assertIn(captured[0], [event["payload"]["result"] for event in restored["modeled_results"]])
        self.assertEqual(restored["positions"][0]["state"], "RECONCILED")
        self.assertEqual(Decimal(restored["positions"][0]["realized_net_pnl_usd_dec"]), Decimal("1.20"))
        self.assertEqual(self.coordinator.status()["status"], "READY")
        self.metrics = {"original_claim_quantity": "6000000", "corrupt_original_entry_cost_usd": "31",
            "unaccepted_capture_retained": True, "pending_attempts_while_corrupt": 1,
            "repeat_original_quote_effects": 0, "truthful_restoration_terminal_net_usd": "1.20"}

    def test_partial_original_result_damage_blocks_quote_and_healthy_neighbor_continues(self):
        native_activate = TradingCoordinator.activate

        def two_positions(coordinator, **kwargs):
            kwargs["profile"]["envelope"].update(max_outstanding_positions=2, max_outstanding_cost_basis_usd="60")
            return native_activate(coordinator, **kwargs)

        with patch.object(TradingCoordinator, "activate", new=two_positions):
            self.start_operating(mode="SHADOW", exit_cap="4000000000000")
        first_epoch = self.epoch
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "10000000000000"},
            {"outAmount": "120000000"}, {"outAmount": "120000000"}, {"outAmount": "132000000"}, {"outAmount": "60000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        second_epoch = first_epoch + "-OTHER"
        self.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:40:00Z", profile=self.profile,
            switch_key="SECOND-PARTIAL-CANDIDATE", expected_current_epoch=first_epoch)
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.tick()
        positions = {row["activation_epoch_id"]: row for row in self.runner.readback()["positions"]}
        self.assertTrue(all(Decimal(row["remaining_qty_dec"]) == Decimal("6000000") for row in positions.values()))
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            results = store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED", position_ids=[positions[first_epoch]["position_id"]])
            original = results[-1]
            damaged = copy.deepcopy(original["payload"])
            damaged["result"]["quantity_sold"] = "1"
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(damaged), original["event_id"]))
        self.coordinator.tick()
        self.coordinator.tick()
        after = {row["activation_epoch_id"]: row for row in self.runner.readback()["positions"]}
        self.assertEqual(Decimal(after[first_epoch]["remaining_qty_dec"]), Decimal("6000000"))
        self.assertEqual(after[second_epoch]["state"], "RECONCILED")
        self.assertEqual(Decimal(after[second_epoch]["realized_net_pnl_usd_dec"]), Decimal("1.20"))
        view = self.coordinator.status()
        self.assertEqual(view["inventory"]["position_count"], 1)
        self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
        self.assertEqual(len(self.ledger_receipts(ledger)), 6)
        bad_quotes = [row for row in self.ledger_receipts(ledger) if row["attempt"]["position_id"] == positions[first_epoch]["position_id"]]
        self.assertEqual(len(bad_quotes), 2)
        self.metrics = {"corrupt_original_result_extra_quotes": 0, "healthy_other_exit": "RECONCILED",
            "healthy_terminal_net_usd": "1.20", "unknown_position_count": 1}

    def test_transient_exit_funding_recovers_without_stale_active_incident(self):
        metrics = []
        for damage in ("MISSING", "MALFORMED", "STALE"):
            with self.subTest(funding=damage):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    case.start_operating(mode="SHADOW")
                    ledger, plan = case.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
                    case.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
                    case.coordinator.run(ticks=1)
                    case.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
                    case.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
                    funding = case.source.data_root / "funding.json"
                    if damage == "MISSING":
                        funding.unlink()
                    elif damage == "MALFORMED":
                        funding.write_text("{", encoding="utf-8")
                    case.coordinator.tick()
                    failed = case.coordinator.status()
                    incident = next(row for row in failed["incidents"] if row["active"] and row["incident_key"].startswith("EXIT-INPUT-"))
                    self.assertEqual(incident["reason"], "EXECUTION_FUNDING_INPUT_UNAVAILABLE" if damage == "MISSING" else "EXECUTION_FUNDING_INPUT_INVALID")
                    self.assertEqual(failed["inventory"]["inventory_status"], "KNOWN")
                    self.assertTrue(failed["integrity_verified"])
                    self.assertFalse(failed["exit_reconciliation_healthy"])
                    self.assertEqual(len(case.ledger_receipts(ledger)), 1)
                    case.quote_inputs(at="2026-10-05T13:10:00Z")
                    case.coordinator.run(ticks=3)
                    cold = TradingCoordinator(TradingContinuityRunner(case.root, data_root=case.data),
                        mode="SHADOW", clock=lambda: case.now)
                    after = cold.status()
                    self.assertEqual(after["status"], "READY")
                    self.assertTrue(after["integrity_verified"])
                    self.assertTrue(after["exit_reconciliation_healthy"])
                    self.assertEqual(after["inventory"]["position_count"], 0)
                    self.assertEqual(after["pending_attempts"], 0)
                    self.assertEqual(case.runner.readback()["positions"][0]["state"], "RECONCILED")
                    retained = next(row for row in after["incidents"] if row["incident_key"] == incident["incident_key"])
                    self.assertEqual(retained["reason"], incident["reason"])
                    self.assertEqual(retained["first_at"], incident["first_at"])
                    self.assertEqual(retained["active"], 0)
                    self.assertEqual(len(case.ledger_receipts(ledger)), 2)
                    metrics.append({"funding": damage, "after": after["status"], "effects": 2,
                        "active_exit_input_incidents": 0, "audit_incident_retained": True})
                finally:
                    case.tearDown()
        self.metrics = {"cases": metrics}

    def test_corrupt_exit_request_stays_unknown_until_exact_owner_witness_restored(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        (self.source.data_root / "funding.json").unlink()
        self.coordinator.tick()
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            original = store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND")[0]
            damaged = {**original["payload"], "asset_metadata_sha256": "0" * 64}
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                    (json.dumps(damaged), original["event_id"]))
        self.coordinator.tick()
        self.coordinator.tick()
        failed = self.coordinator.status()
        self.assertEqual(failed["status"], "ACTION_REQUIRED")
        self.assertEqual(failed["inventory"]["inventory_status"], "UNKNOWN")
        self.assertIsNone(failed["inventory"]["outstanding_cost_basis_usd"])
        self.assertEqual(Decimal(failed["inventory"]["known_cost_basis_floor_usd"]), Decimal("30"))
        self.assertFalse(failed["integrity_verified"])
        self.assertFalse(failed["exit_reconciliation_healthy"])
        self.assertIn("EXECUTION_ASSET_METADATA_INTEGRITY_CONFLICT", {row["reason"] for row in failed["incidents"] if row["active"]})
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                    (json.dumps(original["payload"]), original["event_id"]))
        self.coordinator.run(ticks=3)
        self.assertEqual(self.coordinator.status()["status"], "READY")
        self.assertTrue(all(not row["active"] for row in self.coordinator.status()["incidents"]))
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        self.metrics = {"damaged_witness": "UNKNOWN", "known_floor_usd": "30",
            "corrupt_witness_extra_effects": 0, "exact_restored_witness": "READY", "audit_retained": True}

    def test_complete_cut_restores_tighter_envelope_and_disabled_runtime_policy(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        for control in ("ENVELOPE", "RUNTIME_POLICY"):
            with self.subTest(control=control):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    case.start_operating(mode="SHADOW")
                    ledger = case.empty_ledger()
                    case.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, [{"outAmount": "10000000000000"}])
                    backup = case.data / "backups/pre-config-revision.sqlite"
                    case.coordinator.backup(destination_relative="backups/pre-config-revision.sqlite")
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        if control == "ENVELOPE":
                            current = policy_owner.read_operating_envelope(store, "SHADOW")
                            policy_owner.configure_operating_envelope(store, mode="SHADOW",
                                candidate_raw={**case.profile["envelope"], "max_outstanding_cost_basis_usd": "10"},
                                expected_current_sha256=current["envelope_sha256"], idempotency_key="TIGHTER-10",
                                as_of="2026-10-05T12:40:00Z")
                        else:
                            with patch.object(policy_owner, "_now", return_value="2026-10-05T12:40:00Z"):
                                policy_owner.apply_policy(closure_fixture.ROOT, store, mode="SHADOW",
                                    candidate_raw={"new_entries_enabled": False}, expected_current_sha256="0" * 64,
                                    idempotency_key="DISABLE-AFTER-BACKUP",
                                    owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                                    reason="SYNTHETIC_RECOVERY_POLICY")
                    case.coordinator.tick()
                    self.assertEqual(case.runner.readback()["modeled_attempts"], [])
                    cut = case.production_cut(backup)
                    self.assertEqual(cut["effects"], [])
                    self.assertEqual(cut["pending_attempts"], [])
                    runner, coordinator = case.restored(backup, adapter=RecordingQuoteAdapter(ledger, [{"outAmount": "10000000000000"}]))
                    coordinator.reconcile_cut(cut)
                    self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
                    case.acknowledge(coordinator, cut)
                    with closing(PaperPlaneStore(runner.store_path)) as store:
                        self.assertEqual(policy_owner.operating_configuration_snapshot(store, mode="SHADOW", as_of=cut["as_of"]), cut["operating_configuration"])
                    bot = coordinator.status()["instances"][0]["bot_instance_id"]
                    runner.command({"command_type": "RESUME_NEW_ENTRIES", "idempotency_key": "RESTORED-RESUME", "bot_instance_id": bot})
                    coordinator.run(ticks=2)
                    self.assertEqual(runner.readback()["modeled_attempts"], [])
                    self.assertEqual(case.ledger_receipts(ledger), [])
                    if control == "ENVELOPE":
                        self.assertEqual(coordinator.status()["envelope"]["revision"], 2)
                        self.assertEqual(coordinator.status()["envelope"]["envelope"]["max_outstanding_cost_basis_usd"], "10")
                    else:
                        with closing(PaperPlaneStore(runner.store_path, readonly=True)) as store:
                            current = policy_owner.resolve_current_policy(store, "SHADOW")
                        self.assertEqual(current["revision"], 1)
                        self.assertFalse(current["policy"]["new_entries_enabled"])
                finally:
                    case.tearDown()
        self.metrics = {"controls": ["ENVELOPE_REVISION_2_10_USD", "RUNTIME_POLICY_ENTRIES_DISABLED"],
            "original_attempts": 0, "restored_attempts": 0, "external_effects": 0, "idempotent_reconcile": True}

    def test_recovered_funding_with_unknown_exit_keeps_attempt_and_inventory_fence(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"status": 503}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        (self.source.data_root / "funding.json").unlink()
        self.coordinator.tick()
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.run(ticks=3)
        after = self.coordinator.status()
        self.assertEqual(after["status"], "ACTION_REQUIRED")
        self.assertEqual(after["inventory"]["inventory_status"], "UNKNOWN")
        self.assertEqual(after["pending_attempts"], 1)
        self.assertFalse(after["exit_reconciliation_healthy"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        self.assertEqual(len(self.runner.readback()["modeled_attempts"]), 2)
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "UNRESOLVED")
        self.assertFalse(any(row["active"] for row in after["incidents"] if row["incident_key"].startswith("EXIT-INPUT-")))
        self.assertIn("ATTEMPT_RECONCILIATION_REQUIRED", {row["reason"] for row in after["incidents"] if row["active"]})
        self.metrics = {"input_cause_recovered": True, "exit_outcome": "UNKNOWN", "pending_attempts": 1,
            "repeated_quote_effects": 0, "inventory_status": "UNKNOWN"}

    def test_configuration_chain_damage_or_omission_cannot_acknowledge_restore(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        self.start_operating(mode="SHADOW")
        backup = self.data / "backups/pre-config-negative.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-config-negative.sqlite")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            current = policy_owner.read_operating_envelope(store, "SHADOW")
            policy_owner.configure_operating_envelope(store, mode="SHADOW",
                candidate_raw={**self.profile["envelope"], "max_outstanding_cost_basis_usd": "10"},
                expected_current_sha256=current["envelope_sha256"], idempotency_key="TIGHTER-NEGATIVE",
                as_of="2026-10-05T12:40:00Z")
            with patch.object(policy_owner, "_now", return_value="2026-10-05T12:40:00Z"):
                policy_owner.apply_policy(closure_fixture.ROOT, store, mode="SHADOW",
                    candidate_raw={"new_entries_enabled": False}, expected_current_sha256="0" * 64,
                    idempotency_key="DISABLE-NEGATIVE", owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                    reason="SYNTHETIC_RECOVERY_POLICY")
        cut = self.production_cut(backup)
        outcomes = []
        for damage in ("MISSING", "TRUNCATED_ENVELOPE", "TRUNCATED_POLICY", "HASH", "FOREIGN_MODE", "FUTURE_CLOCK"):
            with self.subTest(damage=damage):
                bad = copy.deepcopy(cut)
                config = bad["operating_configuration"]
                if damage == "MISSING":
                    del bad["operating_configuration"]
                elif damage == "TRUNCATED_ENVELOPE":
                    config["envelope_events"].pop()
                elif damage == "TRUNCATED_POLICY":
                    config["policy_revisions"].clear()
                elif damage == "HASH":
                    config["envelope_events"][-1]["payload"]["envelope_sha256"] = "0" * 64
                elif damage == "FOREIGN_MODE":
                    config["mode"] = "PAPER"
                else:
                    config["policy_revisions"][-1]["created_at"] = "2026-10-05T12:41:00Z"
                bad["cut_sha256"] = sha256_of({key: value for key, value in bad.items() if key != "cut_sha256"})
                runner, coordinator = self.restored(backup, suffix="negative-" + damage.lower())
                expected = "RESTORE_OPERATING_CONFIGURATION_REQUIRED" if damage == "MISSING" else "RESTORE_OPERATING_CONFIGURATION_INVALID"
                with self.assertRaisesRegex(PaperPlaneError, "^" + expected + "$"):
                    coordinator.reconcile_cut(bad)
                with self.assertRaisesRegex(PaperPlaneError, "^" + expected + "$"):
                    coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(coordinator.status()["inventory"]), as_of=bad["as_of"], cut=bad)
                bot = coordinator.status()["instances"][0]["bot_instance_id"]
                runner.command({"command_type": "RESUME_NEW_ENTRIES", "idempotency_key": "UNSAFE-RESUME", "bot_instance_id": bot})
                coordinator.tick()
                self.assertTrue(coordinator.status()["restore_guard"])
                self.assertEqual(runner.readback()["positions"], [])
                self.assertEqual(runner.readback()["modeled_attempts"], [])
                outcomes.append({"damage": damage, "reason": expected, "attempts": 0, "guard": True})
        self.metrics = {"cases": outcomes}

    def test_configuration_restore_preserves_later_local_authority_and_detects_damage(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        self.start_operating(mode="SHADOW")
        backup = self.data / "backups/pre-config-extension.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-config-extension.sqlite")

        def configure(runner, amount, key):
            with closing(PaperPlaneStore(runner.store_path)) as store:
                current = policy_owner.read_operating_envelope(store, "SHADOW")
                return policy_owner.configure_operating_envelope(store, mode="SHADOW",
                    candidate_raw={**self.profile["envelope"], "max_outstanding_cost_basis_usd": amount},
                    expected_current_sha256=current["envelope_sha256"], idempotency_key=key,
                    as_of="2026-10-05T12:40:00Z")

        configure(self.runner, "10", "CUT-10")
        cut = self.production_cut(backup)
        runner, coordinator = self.restored(backup, suffix="conflicting-local")
        configure(runner, "20", "LOCAL-20")
        with self.assertRaisesRegex(PaperPlaneError, "^RESTORE_OPERATING_CONFIGURATION_CONFLICT$"):
            coordinator.reconcile_cut(cut)
        self.assertTrue(coordinator.status()["restore_guard"])
        self.assertEqual(coordinator.status()["envelope"]["envelope"]["max_outstanding_cost_basis_usd"], "20")
        runner, coordinator = self.restored(backup, suffix="later-local")
        coordinator.reconcile_cut(cut)
        extended = configure(runner, "5", "LATER-5")
        self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
        self.acknowledge(coordinator, cut)
        self.assertEqual(coordinator.status()["envelope"]["envelope_sha256"], extended["envelope_sha256"])
        self.assertEqual(coordinator.status()["envelope"]["revision"], 3)
        runner, coordinator = self.restored(backup, suffix="ack-damage")
        coordinator.reconcile_cut(cut)
        with closing(PaperPlaneStore(runner.store_path)) as store:
            original = store.get_execution_event("OPERATING-ENVELOPE-SHADOW-2")
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", (original["event_id"],))
        with self.assertRaisesRegex(PaperPlaneError, "^RESTORE_OPERATING_CONFIGURATION_INVALID$"):
            self.acknowledge(coordinator, cut)
        self.assertTrue(coordinator.status()["restore_guard"])
        self.assertEqual(runner.readback()["modeled_attempts"], [])
        self.metrics = {"conflicting_local_revision": "DENY", "later_local_revision": 3,
            "later_cap_preserved_usd": "5", "post_import_damage_ack": "DENY", "attempts": 0}

    def test_sqlite_writer_wait_cannot_authorize_entry_after_ttl(self):
        self.start_operating(clock_at=datetime(2026, 10, 5, 12, 40, 29, 750000, tzinfo=UTC))
        base = self.now
        started = []
        ready = threading.Event()
        errors = []
        threads = []
        original_inputs = self.coordinator._inputs

        def writer():
            try:
                with closing(sqlite3.connect(self.runner.store_path, timeout=5)) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    ready.set()
                    time.sleep(1.4)
                    connection.commit()
            except BaseException as error:
                errors.append(error)
                ready.set()

        def contend(*args):
            request = original_inputs(*args)
            self.assertEqual(args[-2], "ENTRY")
            started.append(time.monotonic())
            thread = threading.Thread(target=writer)
            threads.append(thread)
            thread.start()
            self.assertTrue(ready.wait(timeout=5), "NATIVE_SQLITE_WRITER_NOT_READY")
            return request

        self.coordinator.clock = lambda: base + timedelta(seconds=time.monotonic() - started[0]) if started else base
        with patch.object(self.coordinator, "_inputs", side_effect=contend):
            try:
                self.coordinator.tick()
            finally:
                for thread in threads:
                    thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(len(started), 1)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertGreaterEqual((self.coordinator.clock() - base).total_seconds(), 1.3)
        view = self.runner.readback()
        self.assertEqual(view["modeled_attempts"], [])
        self.assertEqual(view["modeled_results"], [])
        self.assertEqual({position["state"] for position in view["positions"]}, {"CANCELLED"})
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"), [])
        self.metrics = {"sqlite_writer_hold_seconds": 1.4, "entry_ttl_seconds": 30, "expired_attempts": 0}

    def test_restore_without_effects_imports_successor_binding_and_generation_paused(self):
        self.start_operating(mode="SHADOW")
        predecessor_epoch, old_profile = self.epoch, self.profile
        backup = self.data / "backups/pre-switch.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-switch.sqlite")
        ledger = self.empty_ledger()
        self.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
        profile = {**old_profile, "source": {"root": str(self.source.data_root),
            "file": "observation_schedule_state.sqlite", "schedule_sha256": self.admission["schedule_sha256"],
            "activation_id": self.admission["activation_id"]}}
        self.coordinator = TradingCoordinator(self.runner, mode="SHADOW", clock=lambda: self.now)
        switched = self.coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:40:00Z",
            profile=profile, switch_key="RECOVERY-B", expected_current_epoch=predecessor_epoch)
        self.assertEqual(switched["generation"], 2)
        cut = self.recovery_cut(ledger, backup)
        self.assertEqual(cut["effects"], [])
        self.assertEqual(cut["quote_claims"], [])
        self.assertEqual(len(cut["operating_bindings"]), 2)
        runner, coordinator = self.restored(backup)
        self.assertEqual(coordinator.status()["activation_epoch_id"], predecessor_epoch)
        coordinator.reconcile_cut(cut)
        imported = coordinator.status()
        self.assertEqual(imported["activation_epoch_id"], self.epoch)
        self.assertEqual(imported["generation"], 2)
        self.assertEqual({bot["activation_epoch_id"] for bot in imported["instances"]}, {predecessor_epoch, self.epoch})
        self.assertTrue(all(bot["entries_paused"] for bot in imported["instances"]))
        self.acknowledge(coordinator, cut)
        coordinator.tick()
        self.assertEqual(runner.readback()["positions"], [])
        self.assertTrue(all(bot["entries_paused"] for bot in coordinator.status()["instances"]))
        self.assertEqual(self.ledger_receipts(ledger), [])

    def test_post_restore_stop_survives_older_complete_cut(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-stop.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-stop.sqlite")
        cut = self.recovery_cut(ledger, backup)
        self.assertEqual(cut["controls"][0]["status"], "RUNNING")
        runner, coordinator = self.restored(backup)
        bot_id = coordinator.status()["instances"][0]["bot_instance_id"]
        stopped = runner.command({"command_type": "STOP_BOT", "idempotency_key": "POST-RESTORE-STOP",
            "bot_instance_id": bot_id})
        self.assertEqual(stopped["bot_status"], "STOPPED")
        coordinator.reconcile_cut(cut)
        self.acknowledge(coordinator, cut)
        coordinator.reconcile_cut(cut)
        coordinator.tick()
        bot = coordinator.status()["instances"][0]
        self.assertEqual(bot["status"], "STOPPED")
        self.assertTrue(bot["entries_paused"])
        self.assertEqual(runner.readback()["positions"], [])

    def test_post_restore_drain_with_inventory_survives_older_complete_cut(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        backup = self.data / "backups/pre-drain.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-drain.sqlite")
        cut = self.recovery_cut(ledger, backup)
        self.assertEqual(cut["controls"][0]["status"], "RUNNING")
        runner, coordinator = self.restored(backup)
        bot_id = coordinator.status()["instances"][0]["bot_instance_id"]
        draining = runner.command({"command_type": "STOP_BOT", "idempotency_key": "POST-RESTORE-DRAIN",
            "bot_instance_id": bot_id})
        self.assertEqual(draining["bot_status"], "DRAINING")
        coordinator.reconcile_cut(cut)
        self.acknowledge(coordinator, cut)
        coordinator.reconcile_cut(cut)
        bot = coordinator.status()["instances"][0]
        self.assertEqual(bot["status"], "DRAINING")
        self.assertTrue(bot["entries_paused"])
        self.assertEqual(coordinator.status()["inventory"]["position_count"], 1)
        self.assertEqual(runner.readback()["positions"][0]["state"], "OPEN")
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)

    def test_complete_cut_restores_consumed_quote_grant_and_exit_cannot_resend(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-quote-claim.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-quote-claim.sqlite")
        self.assertEqual(self.claims(self.runner), [])
        grant = self.original_grant()
        self.coordinator.quote_adapter = _GrantedRecordingAdapter(ledger, grant)
        calls = []

        def fake_http(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            body = {"transaction": None, "inputMint": raw["inputMint"], "outputMint": raw["outputMint"],
                "inAmount": raw["amount"], "outAmount": "10000000000000", "router": "metis", "mode": "ultra",
                "feeBps": 20, "feeMint": raw["outputMint"], "requestId": "SYNTHETIC-GRANTED-ORIGINAL"}
            return {"status": 200, "body": json.dumps(body).encode(), "url": ENDPOINT + "?" + urlencode(raw)}

        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=fake_http):
            self.coordinator.tick()
            self.assertEqual(len(calls), 1)
            original_claims = self.claims(self.runner)
            self.assertEqual(len(original_claims), 1)
            self.assertEqual(original_claims[0]["payload"]["grant_sha256"], grant["grant_sha256"])
            cut = self.recovery_cut(ledger, backup)
            self.assertEqual(cut["quote_claims"], original_claims)
            fresh_adapter = _GrantedRecordingAdapter(ledger, grant)
            self.assertEqual(fresh_adapter.calls, 0)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            self.assertEqual(self.claims(runner), [])
            coordinator.reconcile_cut(cut)
            coordinator.reconcile_cut(cut)
            self.assertEqual(self.claims(runner), original_claims)
            self.acknowledge(coordinator, cut)
            self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
            self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
            self.quote_inputs(at="2026-10-05T13:10:00Z")
            coordinator.tick()
            coordinator.tick()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        self.assertEqual(self.claims(runner), original_claims)
        self.assertEqual(fresh_adapter.calls, 0)
        self.assertEqual(coordinator.status()["inventory"]["position_count"], 1)
        self.assertIn("QUOTE_CALL_CAP_EXHAUSTED", {incident["reason"] for incident in coordinator.status()["incidents"]})
        self.metrics = {"original_claims": 1, "restored_claims": 1, "synthetic_http_calls": 1,
            "fresh_adapter_calls": 0, "provider_calls": 0}

    def test_native_witness_metadata_survives_source_deletion_for_due_exit(self):
        self.witness_operating()
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        entry_receipt = self.ledger_receipts(ledger)[0]
        request = entry_receipt["request"]
        asset = request["asset_metadata"]
        self.assertEqual(asset["mint"], self.mint)
        self.assertEqual(asset["decimals"], 6)
        self.assertEqual(request["asset_metadata_sha256"], sha256_of(asset))
        self.assertEqual(request["output_decimals"], 6)
        origin = request["recovery_closure"]["origin"]["provenance"]["origin_admission"]
        self.assertEqual(asset["witness_response_sha256"], origin["witness_response_sha256"])
        self.assertEqual(asset["witness_object_sha256"], origin["witness_object_sha256"])
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "OPEN")
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        funding_path = self.source.data_root / "funding.json"
        funding = json.loads(funding_path.read_text())
        funding.update(observed_at="2026-10-05T13:10:00Z", available_at="2026-10-05T13:10:00Z")
        funding_path.write_text(json.dumps(funding), encoding="utf-8")
        witness_path = self.source.data_root / origin["witness_raw_body_rel"]
        witness_path.unlink()
        (self.source.data_root / "assets.json").unlink()
        cold = TradingCoordinator(TradingContinuityRunner(self.root, data_root=self.data), mode="SHADOW",
            clock=lambda: self.now, quote_adapter=RecordingQuoteAdapter(ledger, json.loads(plan.read_text())))
        cold.tick()
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[1]["attempt"]["side"], "EXIT")
        self.assertEqual(receipts[1]["request"]["asset_metadata"], asset)
        self.assertEqual(receipts[1]["request"]["asset_metadata_sha256"], request["asset_metadata_sha256"])
        self.assertEqual(receipts[1]["request"]["input_decimals"], 6)
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "RECONCILED")
        self.assertEqual(cold.status()["inventory"]["position_count"], 0)
        self.assertFalse(witness_path.exists())
        self.assertFalse((self.source.data_root / "assets.json").exists())

    def test_native_witness_hash_conflict_denies_before_quote_effect(self):
        self.witness_operating()
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        reached = []

        def corrupt_witness(point):
            if point == "AFTER_DECISION_COMMIT":
                reached.append(point)
                witness = self.source.data_root / self.admission["witness_raw_body_rel"]
                witness.write_bytes(witness.read_bytes() + b" ")

        self.coordinator.fault = corrupt_witness
        with self.assertRaisesRegex(PaperPlaneError, "EXECUTION_ASSET_WITNESS_INTEGRITY_CONFLICT"):
            self.coordinator.tick()
        self.assertEqual(reached, ["AFTER_DECISION_COMMIT"])
        self.assertEqual(self.runner.readback()["modeled_attempts"], [])
        self.assertEqual(self.runner.readback()["modeled_results"], [])
        self.assertFalse(ledger.exists())

    def test_authored_vendor_witness_boolean_decimals_denied_before_quote_effect(self):
        original_object = closure_fixture.continuity_fixture.token_object

        def malformed_vendor_object(*args, **kwargs):
            return {**original_object(*args, **kwargs), "decimals": True}

        with patch.object(closure_fixture.continuity_fixture, "token_object", side_effect=malformed_vendor_object):
            self.witness_operating()
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        with self.assertRaisesRegex(PaperPlaneError, "EXECUTION_ASSET_IDENTITY_INVALID"):
            self.coordinator.tick()
        self.assertEqual(self.runner.readback()["modeled_attempts"], [])
        self.assertEqual(self.runner.readback()["modeled_results"], [])
        self.assertFalse(ledger.exists())

    def test_pending_quote_claim_restores_unknown_without_manufacturing_result_or_resend(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-pending-attempt.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-pending-attempt.sqlite")
        self.assertEqual(self.claims(self.runner), [])
        grant = self.original_grant()
        self.coordinator.quote_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
            grant=grant, credential_supplier=lambda: None)
        calls = []

        def effect_without_result(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            raise RuntimeError("SYNTHETIC_LOSS_BEFORE_RESULT_CAPTURE")

        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=effect_without_result):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_LOSS_BEFORE_RESULT_CAPTURE"):
                self.coordinator.tick()
            self.assertEqual(len(calls), 1)
            original = self.runner.readback()
            self.assertEqual(original["positions"][0]["state"], "ATTEMPTING")
            self.assertIsNone(original["positions"][0]["qty_dec"])
            self.assertEqual(original["modeled_results"], [])
            cut = self.recovery_cut(ledger, backup)
            self.assertEqual(cut["effects"], [])
            self.assertEqual(len(cut["pending_attempts"]), 1)
            self.assertEqual(cut["pending_attempts"][0]["attempt"], original["modeled_attempts"][0]["payload"])
            original_claims = self.claims(self.runner)
            self.assertEqual(cut["quote_claims"], original_claims)
            self.assertEqual(len(original_claims), 1)
            fresh_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
                grant=grant, credential_supplier=lambda: None)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            coordinator.reconcile_cut(cut)
            coordinator.reconcile_cut(cut)
            view = runner.readback()
            self.assertEqual(view["positions"][0]["position_id"], original["positions"][0]["position_id"])
            self.assertEqual(view["positions"][0]["state"], "ATTEMPTING")
            self.assertIsNone(view["positions"][0]["qty_dec"])
            self.assertEqual(view["modeled_attempts"][0]["payload"], original["modeled_attempts"][0]["payload"])
            with closing(PaperPlaneStore(runner.store_path, readonly=True)) as store:
                self.assertEqual(store.get_execution_event("REQUEST-" + cut["pending_attempts"][0]["attempt"]["attempt_id"])["payload"],
                    cut["pending_attempts"][0]["request"])
                self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_RESULT_CAPTURED"), [])
            self.assertEqual(view["modeled_results"], [])
            self.assertEqual(self.claims(runner), original_claims)
            inventory = coordinator.status()["inventory"]
            self.assertEqual(inventory["inventory_status"], "UNKNOWN")
            self.assertEqual(Decimal(inventory["known_cost_basis_floor_usd"]), Decimal("30"))
            with self.assertRaisesRegex(PaperPlaneError, "RESTORE_RECONCILIATION_REQUIRED"):
                coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(inventory), as_of=cut["as_of"], cut=cut)
            coordinator.tick()
            coordinator.tick()
            self.assertTrue(coordinator.status()["restore_guard"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(fresh_adapter.calls, 0)
            self.assertEqual(self.ledger_receipts(ledger), [])
            self.assertEqual(self.claims(runner), original_claims)
            self.assertEqual(runner.readback()["positions"][0]["state"], "ATTEMPTING")
        self.metrics = {"original_pending_attempts": 1, "synthetic_effects_without_result": 1,
            "known_fills": 0, "restored_claims": 1, "repeated_http_calls": 0, "ack_denied": True}

    def test_later_paper_cut_preserves_original_pending_model_result_clock(self):
        self.start_operating()
        backup = self.data / "backups/pre-pending-paper.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-pending-paper.sqlite")

        def after_attempt(point):
            if point == "AFTER_ATTEMPT_COMMIT":
                raise RuntimeError("SYNTHETIC_LOSS_BEFORE_PAPER_MODEL")

        self.coordinator.fault = after_attempt
        with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_LOSS_BEFORE_PAPER_MODEL"):
            self.coordinator.tick()
        original = self.runner.readback()
        self.assertEqual(original["positions"][0]["state"], "ATTEMPTING")
        self.assertEqual(original["modeled_results"], [])
        self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
        cut = self.production_cut(backup)
        self.assertEqual(cut["effects"], [])
        self.assertEqual(cut["quote_claims"], [])
        self.assertEqual(len(cut["pending_attempts"]), 1)
        self.assertEqual(cut["pending_attempts"][0]["request"]["result_at"], "2026-10-05T12:40:00Z")
        runner, coordinator = self.restored(backup, mode="PAPER")
        coordinator.reconcile_cut(cut)
        before = runner.readback()
        self.assertEqual(before["positions"][0]["state"], "ATTEMPTING")
        self.assertEqual(before["modeled_results"], [])
        self.assertEqual(before["modeled_attempts"][0]["payload"], original["modeled_attempts"][0]["payload"])
        self.assertEqual(coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
        coordinator.tick()
        after = runner.readback()
        self.assertEqual(after["positions"][0]["state"], "OPEN")
        self.assertEqual(len(after["modeled_attempts"]), 1)
        self.assertEqual(len(after["modeled_results"]), 1)
        result = after["modeled_results"][0]["payload"]["result"]
        self.assertEqual(result["attempt_id"], original["modeled_attempts"][0]["payload"]["attempt_id"])
        self.assertEqual(result["observed_at"], "2026-10-05T12:40:00Z")
        self.assertEqual(result["outcome"], "LANDED_SUCCESS")
        self.assertEqual(coordinator.status()["inventory"]["inventory_status"], "KNOWN")
        self.acknowledge(coordinator, cut)
        coordinator.tick()
        self.assertEqual(len(runner.readback()["modeled_attempts"]), 1)

    def test_later_shadow_pending_cut_accepts_original_earlier_definitive_receipt(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-pending-shadow.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-pending-shadow.sqlite")
        grant = self.original_grant()
        self.coordinator.quote_adapter = _GrantedRecordingAdapter(ledger, grant)
        calls = []

        def fake_http(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            body = {"transaction": None, "inputMint": raw["inputMint"], "outputMint": raw["outputMint"],
                "inAmount": raw["amount"], "outAmount": "10000000000000", "router": "metis", "mode": "ultra",
                "feeBps": 20, "feeMint": raw["outputMint"], "requestId": "SYNTHETIC-OLD-DEFINITIVE-QUOTE"}
            return {"status": 200, "body": json.dumps(body).encode(), "url": ENDPOINT + "?" + urlencode(raw)}

        def after_effect(point):
            if point == "AFTER_ADAPTER_EFFECT":
                raise RuntimeError("SYNTHETIC_LOSS_BEFORE_NATIVE_CAPTURE")

        self.coordinator.fault = after_effect
        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=fake_http):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_LOSS_BEFORE_NATIVE_CAPTURE"):
                self.coordinator.tick()
            original = self.runner.readback()
            self.assertEqual(original["modeled_results"], [])
            self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
            cut = self.production_cut(backup)
            self.assertEqual(cut["effects"], [])
            self.assertEqual(len(cut["pending_attempts"]), 1)
            self.assertEqual(len(cut["quote_claims"]), 1)
            fresh_adapter = _GrantedRecordingAdapter(ledger, grant)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            coordinator.reconcile_cut(cut)
            self.assertEqual(runner.readback()["positions"][0]["state"], "ATTEMPTING")
            self.assertEqual(runner.readback()["modeled_results"], [])
            self.assertEqual(coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
            receipt = self.ledger_receipts(ledger)[0]
            self.assertEqual(receipt["result"]["observed_at"], "2026-10-05T12:40:00Z")
            accepted = coordinator.reconcile_restored_effect(receipt)
            self.assertFalse(accepted["send_permitted"])
            self.assertTrue(coordinator.reconcile_restored_effect(receipt)["idempotent"])
            self.assertEqual(runner.readback()["positions"][0]["state"], "OPEN")
            self.assertEqual(len(runner.readback()["modeled_attempts"]), 1)
            self.assertEqual(runner.readback()["modeled_results"][0]["payload"]["result"], receipt["result"])
            self.acknowledge(coordinator, cut)
            coordinator.tick()
            coordinator.tick()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        self.assertEqual(fresh_adapter.calls, 0)

    def test_export_cut_denies_known_after_backup_result_omission_or_conflict(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        backup = self.data / "backups/pre-final-export.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-final-export.sqlite")
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 1)
        before = self.runner.readback()
        with self.assertRaisesRegex(PaperPlaneError, "RECOVERY_KNOWN_RESULT_OMITTED_OR_CONFLICTING"):
            self.production_cut(backup)
        conflicting = json.loads(json.dumps(receipts[0]))
        conflicting["result"]["unit_price_usd"] = "0.5"
        conflicting["receipt_sha256"] = sha256_of({key: value for key, value in conflicting.items() if key != "receipt_sha256"})
        with self.assertRaisesRegex(PaperPlaneError, "RECOVERY_KNOWN_RESULT_OMITTED_OR_CONFLICTING"):
            self.production_cut(backup, effects=[conflicting])
        valid = self.production_cut(backup, effects=receipts)
        self.assertEqual(valid["effects"], receipts)
        self.assertEqual(valid["pending_attempts"], [])
        self.assertEqual(self.runner.readback(), before)

    def test_corrupt_predecessor_binding_does_not_starve_other_due_exit(self):
        native_activate = TradingCoordinator.activate

        def two_positions(coordinator, **kwargs):
            profile = kwargs["profile"]
            profile["envelope"].update(max_outstanding_positions=2, max_outstanding_cost_basis_usd="60")
            return native_activate(coordinator, **kwargs)

        with patch.object(TradingCoordinator, "activate", new=two_positions):
            self.start_operating()
        first_epoch = self.epoch
        self.coordinator.tick()
        profile = self.profile
        second_epoch = first_epoch + "-OTHER"
        self.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:40:00Z", profile=profile,
            switch_key="SECOND-SAME-CANDIDATE", expected_current_epoch=first_epoch)
        self.coordinator.tick()
        self.assertEqual({position["activation_epoch_id"] for position in self.runner.readback()["positions"]},
            {first_epoch, second_epoch})
        self.assertEqual(self.coordinator.status()["inventory"]["position_count"], 2)
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", ("OPERATING-" + first_epoch,))
        self.coordinator.tick()
        positions = {position["activation_epoch_id"]: position for position in self.runner.readback()["positions"]}
        self.assertEqual(positions[first_epoch]["state"], "OPEN")
        self.assertEqual(positions[second_epoch]["state"], "RECONCILED")
        self.assertEqual(self.coordinator.status()["inventory"]["position_count"], 1)
        self.assertIn(positions[first_epoch]["position_id"],
            {incident["incident_key"] for incident in self.coordinator.status()["incidents"]})

    def test_active_successor_profile_failure_does_not_starve_predecessor_exit(self):
        for damage in ("missing", "corrupt"):
            with self.subTest(profile=damage):
                case = OperationalRecoveryTests(methodName=self._testMethodName)
                case.setUp()
                try:
                    case.start_operating()
                    case.coordinator.tick()
                    first_epoch, first_runner = case.epoch, case.runner
                    first_profile = json.loads(json.dumps(case.profile))
                    before = first_runner.readback()
                    self.assertEqual([row["state"] for row in before["positions"]], ["OPEN"])
                    with closing(PaperPlaneStore(first_runner.store_path, readonly=True)) as store:
                        retained_profile = store.get_execution_event("PROFILE-" + first_epoch)

                    case.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
                    self.assertNotEqual(case.runner.strategy["strategy_id"], first_runner.strategy["strategy_id"])
                    self.assertNotEqual(case.runner.strategy["spec_sha256"], first_runner.strategy["spec_sha256"])
                    second_epoch = case.epoch
                    case.coordinator = TradingCoordinator(case.runner, mode="PAPER", clock=lambda: case.now)
                    switched = case.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:41:00Z",
                        profile=first_profile, switch_key="PROFILE-GAP-B", expected_current_epoch=first_epoch)
                    self.assertEqual(switched["generation"], 2)
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        if damage == "missing":
                            store._conn.execute("DELETE FROM execution_events WHERE event_id=?", ("PROFILE-" + second_epoch,))
                        else:
                            profile_event = store.get_execution_event("PROFILE-" + second_epoch)
                            payload = profile_event["payload"]
                            payload["profile"]["poll_seconds"] = 0.03
                            # Retain the original hash: valid JSON with a corrupt native binding.
                            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                                (json.dumps(payload, sort_keys=True), "PROFILE-" + second_epoch))

                    case.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
                    case.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
                    cold_runner = TradingContinuityRunner(case.root, data_root=case.data)
                    cold = TradingCoordinator(cold_runner, mode="PAPER", clock=lambda: case.now)
                    outcome = cold.run(ticks=2)
                    self.assertEqual(outcome["status"], "GRACEFUL_SHUTDOWN")
                    self.assertEqual(outcome["ticks"], 2)
                    after = cold_runner.readback()
                    self.assertEqual([(row["activation_epoch_id"], row["state"]) for row in after["positions"]],
                        [(first_epoch, "RECONCILED")])
                    self.assertEqual(len(after["modeled_attempts"]), 2)
                    self.assertEqual(len(after["modeled_results"]), 2)
                    self.assertEqual({row["position_id"] for row in after["modeled_attempts"]},
                        {before["positions"][0]["position_id"]})
                    self.assertEqual([row["payload"]["side"] for row in after["modeled_attempts"]], ["ENTRY", "EXIT"])
                    view = cold.status()
                    self.assertEqual(view["activation_epoch_id"], second_epoch)
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["inventory"]["position_count"], 0)
                    self.assertEqual(view["inventory"]["inventory_status"], "KNOWN")
                    self.assertEqual(view["input_reason"], "OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT")
                    self.assertIsNone(view["profile_sha256"])
                    self.assertIsNone(view["process_alive"])
                    self.assertIsNone(view["progress_moving"])
                    self.assertFalse(view["input_fresh"])
                    self.assertIn("OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT",
                        {row["reason"] for row in view["incidents"] if row["active"]})
                    with closing(PaperPlaneStore(cold_runner.store_path, readonly=True)) as store:
                        self.assertEqual(store.get_execution_event("PROFILE-" + first_epoch), retained_profile)
                        state = store._conn.execute("SELECT source_status FROM ordinary_state WHERE mode='PAPER'").fetchone()
                        self.assertEqual(state[0], "ACTIVE_PROFILE_UNAVAILABLE")
                finally:
                    case.tearDown()

    def test_active_successor_binding_failure_does_not_starve_predecessor_exit(self):
        for damage in ("missing", "corrupt"):
            with self.subTest(binding=damage):
                case = OperationalRecoveryTests(methodName=self._testMethodName)
                case.setUp()
                try:
                    case.start_operating()
                    case.coordinator.tick()
                    first_epoch, first_runner = case.epoch, case.runner
                    first_profile = json.loads(json.dumps(case.profile))
                    before = first_runner.readback()
                    self.assertEqual([row["state"] for row in before["positions"]], ["OPEN"])
                    with closing(PaperPlaneStore(first_runner.store_path, readonly=True)) as store:
                        retained = {prefix: store.get_execution_event(prefix + first_epoch)
                            for prefix in ("PROFILE-", "OPERATING-")}

                    case.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
                    self.assertNotEqual(case.runner.strategy["spec_sha256"], first_runner.strategy["spec_sha256"])
                    second_epoch = case.epoch
                    case.coordinator = TradingCoordinator(case.runner, mode="PAPER", clock=lambda: case.now)
                    switched = case.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:41:00Z",
                        profile=first_profile, switch_key="BINDING-GAP-B", expected_current_epoch=first_epoch)
                    self.assertEqual(switched["generation"], 2)
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        if damage == "missing":
                            store._conn.execute("DELETE FROM execution_events WHERE event_id=?", ("OPERATING-" + second_epoch,))
                        else:
                            # Preserve event identity anchors while corrupting only disposable payload bytes.
                            store._conn.execute("UPDATE execution_events SET payload_json='null' WHERE event_id=?",
                                ("OPERATING-" + second_epoch,))

                    case.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
                    case.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
                    cold_runner = TradingContinuityRunner(case.root, data_root=case.data)
                    cold = TradingCoordinator(cold_runner, mode="PAPER", clock=lambda: case.now)
                    inventory = cold.status()["inventory"]
                    self.assertEqual(inventory["position_count"], 1)
                    self.assertEqual(inventory["inventory_status"], "UNKNOWN")
                    self.assertIsNone(inventory["outstanding_cost_basis_usd"])
                    self.assertEqual(Decimal(inventory["known_cost_basis_floor_usd"]), Decimal("30"))
                    outcome = cold.tick()
                    self.assertEqual(outcome["status"], "TICK_COMPLETE")
                    self.assertEqual(outcome["exits"], 1)
                    self.assertFalse(outcome["entries_enabled"])
                    self.assertEqual(outcome["source_status"], "ACTIVE_PROFILE_UNAVAILABLE")
                    self.assertEqual(cold.run(ticks=2)["status"], "GRACEFUL_SHUTDOWN")
                    after = cold_runner.readback()
                    self.assertEqual([(row["activation_epoch_id"], row["state"]) for row in after["positions"]],
                        [(first_epoch, "RECONCILED")])
                    self.assertEqual(len(after["modeled_results"]), 2)
                    self.assertEqual([row["payload"]["side"] for row in after["modeled_attempts"]], ["ENTRY", "EXIT"])
                    self.assertEqual({row["position_id"] for row in after["modeled_attempts"]},
                        {before["positions"][0]["position_id"]})
                    view = cold.status()
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["activation_epoch_id"], second_epoch)
                    self.assertFalse(view["integrity_verified"])
                    self.assertEqual(view["inventory"]["position_count"], 0)
                    self.assertEqual(view["inventory"]["inventory_status"], "KNOWN")
                    self.assertIn({"epoch_id": second_epoch, "status": "INTEGRITY_CONFLICT"}, view["integrity_gaps"])
                    self.assertIn("OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT",
                        {row["reason"] for row in view["incidents"] if row["active"]})
                    with closing(PaperPlaneStore(cold_runner.store_path, readonly=True)) as store:
                        for prefix, event in retained.items():
                            self.assertEqual(store.get_execution_event(prefix + first_epoch), event)
                finally:
                    case.tearDown()

    def test_complete_cut_retains_known_cost_floor_before_later_unknown_total(self):
        self.start_operating(mode="SHADOW")
        backup = self.data / "backups/pre-unknown-cost-attempt.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-unknown-cost-attempt.sqlite")
        grant = self.original_grant()
        self.coordinator.quote_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
            grant=grant, credential_supplier=lambda: None)
        calls = []

        def lose_response(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            raise RuntimeError("SYNTHETIC_UNKNOWN_COST_CALLBACK_REQUIRED")

        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=lose_response):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_UNKNOWN_COST_CALLBACK_REQUIRED"):
                self.coordinator.tick()
            self.assertEqual(len(calls), 1)
            pending = self.runner.readback()
            self.assertEqual(pending["positions"][0]["state"], "ATTEMPTING")
            self.assertEqual(pending["modeled_results"], [])
            attempt = pending["modeled_attempts"][0]["payload"]
            with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
                request = store.get_execution_event("REQUEST-" + attempt["attempt_id"])["payload"]
            results = [{"attempt_id": attempt["attempt_id"], "result_id": identity,
                "outcome": "UNKNOWN_REQUIRES_RECONCILIATION", "observed_at": at,
                "chargeable_cost_usd": cost} for identity, at, cost in (
                    ("C20-COST-KNOWN", "2026-10-05T12:40:10Z", "0.25"),
                    ("C20-COST-UNKNOWN", "2026-10-05T12:40:20Z", None))]
            self.runner.result(results[0])
            self.assertEqual(Decimal(self.runner.readback()["modeled_attempt_costs"]["known_additional_cost_usd"]),
                Decimal("0.25"))
            self.runner.result(results[1])
            original = self.runner.readback()
            self.assertEqual(original["positions"][0]["state"], "UNKNOWN")
            self.assertEqual(original["modeled_attempt_costs"]["additional_cost_status"], "UNKNOWN")
            self.assertEqual(Decimal(original["modeled_attempt_costs"]["known_additional_cost_usd"]), Decimal("0.25"))
            self.assertEqual([event["payload"]["result"] for event in original["modeled_results"]], results)
            self.assertEqual([event["created_at"] for event in original["modeled_results"]],
                [result["observed_at"] for result in results])
            receipt = {"attempt": attempt, "request": request, "result": results[-1]}
            receipt["receipt_sha256"] = sha256_of(receipt)
            self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
            cut = self.production_cut(backup, effects=[receipt])
            self.assertEqual(cut["effects"], [receipt])
            self.assertEqual(cut["result_observations"], original["modeled_results"])
            original_claims = self.claims(self.runner)
            self.assertEqual(len(original_claims), 1)
            self.assertEqual(cut["quote_claims"], original_claims)
            fresh_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
                grant=grant, credential_supplier=lambda: None)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            coordinator.reconcile_cut(cut)
            self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
            restored = runner.readback()
            self.assertEqual(restored["modeled_attempts"], original["modeled_attempts"])
            self.assertEqual(restored["modeled_results"], original["modeled_results"])
            self.assertEqual(restored["modeled_attempt_costs"], original["modeled_attempt_costs"])
            self.assertEqual(restored["positions"][0]["position_id"], original["positions"][0]["position_id"])
            self.assertEqual(restored["positions"][0]["state"], "UNKNOWN")
            self.assertIsNone(restored["positions"][0]["qty_dec"])
            self.assertEqual(self.claims(runner), original_claims)
            view = coordinator.status()
            self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
            self.assertEqual(Decimal(view["inventory"]["known_cost_basis_floor_usd"]), Decimal("30"))
            self.assertEqual(Decimal(view["economics"][0]["additional_costs"]["known_additional_cost_usd"]), Decimal("0.25"))
            coordinator.tick()
            coordinator.tick()
            self.assertEqual(runner.readback()["modeled_results"], original["modeled_results"])
            self.assertEqual(runner.readback()["modeled_attempt_costs"], original["modeled_attempt_costs"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(fresh_adapter.calls, 0)
            self.assertTrue(coordinator.status()["restore_guard"])
        self.metrics = {"original_observations": 2, "restored_observations": 2,
            "known_additional_cost_floor_usd": "0.25", "unknown_total_retained": True,
            "original_http_calls": 1, "repeated_http_calls": 0}
