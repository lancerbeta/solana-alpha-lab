"""Native disposable-DB ordinary obligations and quantity accounting oracles."""
from __future__ import annotations

import copy
import json
import threading
import time
from decimal import Decimal
from unittest.mock import patch

from tests.test_paper_shadow_execution_integrity_vertical_v1 import StoreCase, ROOT, signal, EPOCH, T0
from tests.test_risk_and_economics_v1 import isolated_factory_root
from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.paper_plane import (
    PaperPlaneError, PaperPlaneStore, accept_signal_decision_outcome,
    begin_modeled_attempt, accept_modeled_result,
    assert_quantity_inventory_witness,
)
from solana_alpha_lab.factory.paper_shadow_operations import build_operations_projection
from solana_alpha_lab.factory.risk_economics import compose_risk_economics
from solana_alpha_lab.factory.strategy_runtime import canonical_spec_sha256
from solana_alpha_lab.factory.trading_runtime_policy import (
    TradingRuntimePolicyError, configure_operating_envelope, read_operating_envelope,
    normalize_operating_envelope, obligation_summary, enforce_operating_envelope,
)


class OperatingObligationsTests(StoreCase):
    def setUp(self):
        super().setUp()
        self.strategy["notional_policy"] = {"notional_usd": 30, "fee_bps": 20}
        self.strategy["spec_sha256"] = canonical_spec_sha256(self.strategy)

    def envelope(self, store, *, mode="PAPER", money="30", count=2, key="limits"):
        return configure_operating_envelope(store, mode=mode,
            candidate_raw={"max_outstanding_positions": count, "max_outstanding_cost_basis_usd": money},
            expected_current_sha256=read_operating_envelope(store, mode)["envelope_sha256"],
            idempotency_key=key, as_of=T0)

    def admission(self, store, key, *, strategy=None, mode="PAPER", ordinary=True, epoch=EPOCH):
        spec = strategy or self.strategy
        decision = {**signal(key), "strategy_id": spec["strategy_id"], "activation_epoch_id": epoch}
        return accept_signal_decision_outcome(ROOT, store, strategy=spec, signal_decision=decision,
            known_activation_epochs={epoch: {"mode": mode}}, mode=mode, as_of=T0,
            skip_fill=True, ordinary_operating=ordinary)

    def attempt(self, store, pid, side="ENTRY", key="entry", at=T0, mode="PAPER"):
        return begin_modeled_attempt(store, position_id=pid, side=side, mode=mode,
            attempt_key=key, decision_at=T0, max_age_seconds=900, as_of=at)

    def entry(self, store, *, key="SIGDEC-OBLIGATION-A", mode="PAPER", semantics="SEPARATE_MODELED_FEE", quantity="10000000"):
        admitted = self.admission(store, key, mode=mode)
        pid = admitted["position_id"]
        attempted = self.attempt(store, pid, mode=mode)
        result = {"schema_version": "1.1", "attempt_id": attempted["attempt_id"], "result_id": key + "-ENTRY",
            "outcome": "LANDED_SUCCESS", "observed_at": T0, "unit_price_usd": format(Decimal("30") / Decimal(quantity), "f"),
            "filled_notional_usd": "30", "quantity_filled": quantity, "quantity_unit": "TOKEN_UNITS",
            "fee_semantics": semantics, "chargeable_cost_usd": "0"}
        accept_modeled_result(store, result=result)
        return pid

    def exit_result(self, attempt_id, key, *, sold="4000000", remaining="6000000", price="0.0000033", cost="0.01", outcome="PARTIAL"):
        return {"schema_version": "1.1", "attempt_id": attempt_id, "result_id": key,
            "outcome": outcome, "observed_at": T0, "unit_price_usd": price,
            "quantity_sold": sold, "quantity_unit": "TOKEN_UNITS", "remaining_quantity": remaining,
            "fee_semantics": "SEPARATE_MODELED_FEE", "chargeable_cost_usd": cost}

    def test_configuration_required_and_legacy_unchanged(self):
        store = self.store()
        denied = self.admission(store, "SIGDEC-MISSING-LIMITS")
        self.assertEqual(denied["reason_code"], "CONFIGURATION_REQUIRED")
        self.assertEqual(store.positions(), [])
        legacy = self.admission(store, "SIGDEC-LEGACY", ordinary=False)
        self.assertEqual(store.open_risk_count(legacy["bot_instance_id"]), 1)
        for money in (None, "0", "-1", "NaN", "Infinity"):
            with self.assertRaises(TradingRuntimePolicyError):
                normalize_operating_envelope({"max_outstanding_positions": 2,
                    "max_outstanding_cost_basis_usd": money}, mode="PAPER")

    def test_shared_predecessor_reservation_and_no_auto_shrink(self):
        store = self.store()
        self.envelope(store)
        pid = self.entry(store)
        self.close_request(store, pid, "close-a")
        self.assertEqual(store.open_risk_count(store.get_position(pid)["bot_instance_id"]), 0)
        self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 1)
        successor = copy.deepcopy(self.strategy)
        successor["strategy_id"] = "STRAT-ACCOUNTING-CONTROL-B"
        successor["spec_sha256"] = canonical_spec_sha256(successor)
        denied = self.admission(store, "SIGDEC-OBLIGATION-B", strategy=successor, epoch="ACTIVATION-EPOCH-SUCCESSOR-001")
        self.assertEqual(denied["reason_code"], "OUTSTANDING_COST_BASIS_LIMIT")
        attempted = self.attempt(store, pid, "EXIT", "exit1")
        accept_modeled_result(store, result=self.exit_result(attempted["attempt_id"], "partial-a"))
        self.assertEqual(obligation_summary(store, mode="PAPER")["outstanding_cost_basis_usd"], "18")
        check = enforce_operating_envelope(store, mode="PAPER", admitted_notional_usd="30")
        self.assertEqual(check["reason_code"], "OUTSTANDING_COST_BASIS_LIMIT")
        self.assertEqual(check["admitted_notional_usd"], "30")

    def test_literal_partial_accounting_oracle_replay_and_cold_readback(self):
        store = self.store()
        self.envelope(store)
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        first = self.attempt(store, pid, "EXIT", "exit1")
        result = self.exit_result(first["attempt_id"], "partial")
        accepted = accept_modeled_result(store, result=result)["position"]
        self.assertEqual(accepted["qty_dec"], "10000000")
        self.assertEqual(accepted["remaining_qty_dec"], "6000000")
        self.assertEqual(accepted["remaining_cost_basis_usd_dec"], "18")
        self.assertEqual(accepted["exit_notional_usd_dec"], "13.20")
        self.assertEqual(accepted["entry_fee_usd_dec"], "0.06")
        self.assertEqual(accepted["remaining_entry_fee_usd_dec"], "0.04")
        self.assertEqual(accepted["exit_fee_usd_dec"], "0.03")
        self.assertEqual(accepted["state"], "EXIT_REQUIRED")
        before = store.execution_events()
        self.assertTrue(accept_modeled_result(store, result=result)["idempotent"])
        self.assertEqual(store.execution_events(), before)
        store.record_position_mark(position_id=pid, mark_price_dec="0.000003", as_of=T0, evidence_class="PAPER_MARK_TO_MODEL")
        economics = compose_risk_economics(ROOT, store, as_of=T0)
        self.assertEqual(economics["partial_realized_rows"][0]["remaining_quantity"], "6000000")
        self.assertEqual(economics["open_mark_scopes"][0]["rows"][0]["unrealized_net_after_modeled_fees_usd"], "-0.08")
        second = self.attempt(store, pid, "EXIT", "exit2")
        self.assertEqual(second["remaining_quantity"], "6000000")
        final = self.exit_result(second["attempt_id"], "final", sold="6000000", remaining="0.00", price="0.000003", cost="0", outcome="LANDED_SUCCESS")
        position = accept_modeled_result(store, result=final)["position"]
        self.assertEqual(position["realized_gross_pnl_usd_dec"], "1.20")
        self.assertEqual(position["realized_net_pnl_usd_dec"], "1.07")
        self.assertEqual(position["exit_fee_usd_dec"], "0.07")
        self.assertEqual(position["remaining_entry_fee_usd_dec"], "0.00")
        self.assertEqual(position["closed_at"], T0)
        self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 0)
        operations = build_operations_projection(store)
        self.assertEqual(operations["modeled_attempt_costs"]["known_additional_cost_usd"], "0.01")
        self.assertEqual(operations["modeled_net_after_additional_costs_usd"], "1.06")
        reader = PaperPlaneStore(store.path, readonly=True)
        try:
            self.assertEqual(reader.get_position(pid), position)
            self.assertEqual(read_operating_envelope(reader, "PAPER")["status"], "VALID")
            self.assertEqual(obligation_summary(reader, mode="PAPER")["position_count"], 0)
        finally:
            reader.close()

    def test_quantity_result_acceptance_rejects_corrupt_original_or_cumulative_projection(self):
        metrics = []
        damages = [("qty_dec", "9000000"), ("entry_price_dec", "0.000004"),
            ("entered_notional_usd_dec", "31"), ("entry_fee_usd_dec", "99"),
            ("remaining_qty_dec", "9000000"), ("remaining_cost_basis_usd_dec", "99"),
            ("remaining_entry_fee_usd_dec", "99"), ("exit_notional_usd_dec", "99"),
            ("exit_fee_usd_dec", "99"), ("realized_gross_pnl_usd_dec", "99"),
            ("realized_net_pnl_usd_dec", "99"), ("entry_fee_semantics", None)]
        for number, (field, value) in enumerate(damages):
            with self.subTest(field=field):
                store = self.store("projection-" + str(number) + ".sqlite")
                self.envelope(store)
                pid = self.entry(store, key="SIGDEC-PROJECTION-" + str(number))
                self.close_request(store, pid, "close-" + str(number))
                first = self.attempt(store, pid, "EXIT", "exit1")
                accept_modeled_result(store, result=self.exit_result(first["attempt_id"], "partial-" + str(number)))
                pending = self.attempt(store, pid, "EXIT", "exit2")
                original = store.get_position(pid)
                next_result = self.exit_result(pending["attempt_id"], "next-" + str(number), sold="4000000", remaining="2000000")
                with store.immediate_write():
                    store._conn.execute("UPDATE positions SET " + field + "=? WHERE position_id=?", (value, pid))
                damaged = store.get_position(pid)
                journal = store.execution_events()
                with self.assertRaisesRegex(PaperPlaneError, "^EXIT_INVENTORY_WITNESS_CONFLICT$"):
                    accept_modeled_result(store, result=next_result)
                self.assertEqual(store.get_position(pid), damaged)
                self.assertEqual(store.execution_events(), journal)
                self.assertIsNone(store.get_execution_event("FINAL-" + pending["attempt_id"]))
                with store.immediate_write():
                    store._conn.execute("UPDATE positions SET " + field + "=? WHERE position_id=?", (original[field], pid))
                restored = accept_modeled_result(store, result=next_result)["position"]
                self.assertEqual(Decimal(restored["remaining_qty_dec"]), Decimal("2000000"))
                self.assertEqual(Decimal(restored["remaining_cost_basis_usd_dec"]), Decimal("6"))
                final_attempt = self.attempt(store, pid, "EXIT", "exit3")
                final = accept_modeled_result(store, result=self.exit_result(final_attempt["attempt_id"], "final-" + str(number),
                    sold="2000000", remaining="0", price="0.000003", cost="0", outcome="LANDED_SUCCESS"))["position"]
                self.assertEqual(Decimal(final["remaining_cost_basis_usd_dec"]), 0)
                self.assertEqual(Decimal(final["remaining_entry_fee_usd_dec"]), 0)
                self.assertEqual(Decimal(final["realized_net_pnl_usd_dec"]), Decimal("2.27"))
                metrics.append({"damaged": field, "acceptance": "DENY", "new_accepted_events": 0,
                    "truthful_restoration_terminal_net_usd": "2.27"})
        self.metrics = {"cases": metrics}

    def test_modern_entry_witness_cannot_be_hidden_by_nulling_quantity_projection_flags(self):
        store = self.store()
        self.envelope(store)
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        with store.immediate_write():
            store._conn.execute("UPDATE positions SET entry_fee_semantics=NULL, remaining_qty_dec=NULL, remaining_cost_basis_usd_dec=NULL, remaining_entry_fee_usd_dec=NULL WHERE position_id=?", (pid,))
        before = store.execution_events()
        with self.assertRaisesRegex(PaperPlaneError, "^EXIT_INVENTORY_WITNESS_CONFLICT$"):
            self.attempt(store, pid, "EXIT", "flag-bypass")
        self.assertEqual(store.execution_events(), before)
        self.metrics = {"modern_origin_retained": True, "mutable_flags_null": True, "new_attempts": 0}

    def test_genuine_v1_0_entry_then_v1_1_partial_and_full_preserves_original_payload(self):
        store = self.store()
        self.envelope(store)
        pid = self.admission(store, "SIGDEC-LEGACY-PARTIAL")["position_id"]
        attempt = self.attempt(store, pid)
        original = {"attempt_id": attempt["attempt_id"], "result_id": "legacy-partial-entry",
            "outcome": "LANDED_SUCCESS", "observed_at": T0, "unit_price_usd": "0.000003",
            "filled_notional_usd": "30", "chargeable_cost_usd": "0"}
        accept_modeled_result(store, result=original)
        native_entry = store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED")[0]
        self.assertEqual(native_entry["payload"]["result"], original)
        self.close_request(store, pid, "close")
        first = self.attempt(store, pid, "EXIT", "exit1")
        self.assertNotIn("remaining_quantity", first)
        accept_modeled_result(store, result=self.exit_result(first["attempt_id"], "legacy-partial"))
        second = self.attempt(store, pid, "EXIT", "exit2")
        self.assertEqual(Decimal(second["remaining_quantity"]), Decimal("6000000"))
        final = accept_modeled_result(store, result=self.exit_result(second["attempt_id"], "legacy-final",
            sold="6000000", remaining="0", price="0.000003", cost="0", outcome="LANDED_SUCCESS"))["position"]
        self.assertEqual(final["state"], "RECONCILED")
        self.assertEqual(Decimal(final["realized_net_pnl_usd_dec"]), Decimal("1.07"))
        self.assertEqual(store.get_execution_event(native_entry["event_id"]), native_entry)
        self.metrics = {"legacy_original_payload_unchanged": True, "partial_quantity": "6000000",
            "terminal_net_usd": "1.07"}

    def test_unknown_exit_retains_inventory_and_blocks_overlapping_attempt(self):
        store = self.store()
        self.envelope(store, money="90")
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        attempted = self.attempt(store, pid, "EXIT", "exit-unknown")
        result = {"attempt_id": attempted["attempt_id"], "result_id": "unknown", "outcome": "UNKNOWN_REQUIRES_RECONCILIATION", "observed_at": T0}
        accept_modeled_result(store, result=result)
        summary = obligation_summary(store, mode="PAPER")
        self.assertEqual(summary["known_cost_basis_floor_usd"], "30")
        self.assertEqual(summary["inventory_status"], "UNKNOWN")
        self.assertEqual(enforce_operating_envelope(store, mode="PAPER", admitted_notional_usd="30")["reason_code"], "OUTSTANDING_OBLIGATIONS_UNKNOWN")
        with self.assertRaisesRegex(PaperPlaneError, "ATTEMPT_RECONCILIATION_REQUIRED"):
            self.attempt(store, pid, "EXIT", "overlap")
        accept_modeled_result(store, result=self.exit_result(attempted["attempt_id"], "later-known", sold="10000000", remaining="0", outcome="LANDED_SUCCESS", cost=None))
        self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 0)
        self.assertIsNone(build_operations_projection(store)["modeled_net_after_additional_costs_usd"])

    def test_natural_terminal_release_requires_intact_final_result_chain(self):
        for state in ("NONFILL", "FLAT"):
            for damage in ("FINAL-EMPTY", "FINAL-MISSING", "RESULT-EMPTY", "RESULT-MISSING", "RESULT-NULL", "OUTCOME-CONFLICT", "CLOCK-CONFLICT", "FINAL-INVALID-JSON", "FINAL-FOREIGN-BOT", "RESULT-ID-CONFLICT", "ATTEMPT-MISSING", "FINAL-UNHASHABLE-REFERENCE", "RESULT-NONFINITE", "RESULT-QUANTITY-CONFLICT", "ALL-MODELED-MISSING", "ENTRY-QUANTITY-CONFLICT", "ENTRY-NEAR-ROUNDING-QUANTITY", "ENTRY-NOTIONAL-CLASS-CONFLICT", "ENTRY-WRONG-SIDE-FIELD", "ENTRY-REMAINDER-WRONG-SIDE", "EXIT-WRONG-SIDE-FIELDS", "EXIT-NOTIONAL-WRONG-SIDE", "ATTEMPT-QUANTITY-CONFLICT", "ATTEMPT-QUANTITY-UNIT-CONFLICT"):
                if state == "NONFILL" and damage.startswith(("ENTRY-", "EXIT-", "ATTEMPT-QUANTITY")):
                    continue
                with self.subTest(state=state, damage=damage):
                    store = self.store(state + "-" + damage + ".sqlite")
                    self.envelope(store, money="90")
                    key = "SIGDEC-RELEASE-" + state + "-" + damage
                    if state == "NONFILL":
                        pid = self.admission(store, key)["position_id"]
                        attempt = self.attempt(store, pid)
                        accept_modeled_result(store, result={"attempt_id": attempt["attempt_id"],
                            "result_id": key + "-RESULT", "outcome": "NO_ROUTE", "observed_at": T0})
                    else:
                        pid = self.entry(store, key=key)
                        self.close_request(store, pid, "close")
                        attempt = self.attempt(store, pid, "EXIT", "full-exit")
                        accept_modeled_result(store, result=self.exit_result(attempt["attempt_id"], key + "-RESULT",
                            sold="10000000", remaining="0", cost="0", outcome="LANDED_SUCCESS"))
                    natural = store.get_position(pid)
                    self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 0)
                    final_id = "FINAL-" + attempt["attempt_id"]
                    result_id = store.get_execution_event(final_id)["payload"]["result_event_id"]
                    event_id = final_id if damage.startswith("FINAL") else result_id
                    if damage == "ALL-MODELED-MISSING":
                        store._conn.execute("DELETE FROM execution_events WHERE position_id=? AND event_type IN ('MODELED_ATTEMPT_STARTED','MODELED_ATTEMPT_FINAL','MODELED_RESULT_ACCEPTED')", (pid,))
                    elif damage.startswith("ATTEMPT-QUANTITY"):
                        payload = store.get_execution_event(attempt["attempt_id"])["payload"]
                        payload["remaining_quantity" if damage == "ATTEMPT-QUANTITY-CONFLICT" else "quantity_unit"] = "1" if damage == "ATTEMPT-QUANTITY-CONFLICT" else "FOREIGN_UNITS"
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), attempt["attempt_id"]))
                    elif damage.startswith(("ENTRY-", "EXIT-")) or damage == "RESULT-QUANTITY-CONFLICT":
                        target = next(e for e in store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[pid])
                            if e["payload"]["side"] == "ENTRY") if damage.startswith("ENTRY-") else store.get_execution_event(attempt["attempt_id"])
                        target_result_id = store.get_execution_event("FINAL-" + target["event_id"])["payload"]["result_event_id"]
                        payload = store.get_execution_event(target_result_id)["payload"]
                        changes = {"quantity_filled": "1"} if damage == "ENTRY-QUANTITY-CONFLICT" else {"quantity_filled": "9999999"} if damage == "ENTRY-NEAR-ROUNDING-QUANTITY" else {"filled_notional_usd": "29.999999"} if damage == "ENTRY-NOTIONAL-CLASS-CONFLICT" else {"remaining_quantity": "0"} if damage == "ENTRY-REMAINDER-WRONG-SIDE" else {"quantity_filled": "1", "filled_notional_usd": "30"} if damage == "EXIT-WRONG-SIDE-FIELDS" else {"filled_notional_usd": None} if damage == "EXIT-NOTIONAL-WRONG-SIDE" else {"quantity_sold": "1"}
                        payload["result"].update(changes)
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), target_result_id))
                    elif damage == "ATTEMPT-MISSING":
                        store._conn.execute("DELETE FROM execution_events WHERE event_id=?", (attempt["attempt_id"],))
                    elif damage.endswith("MISSING"):
                        store._conn.execute("DELETE FROM execution_events WHERE event_id=?", (event_id,))
                    elif damage == "FINAL-FOREIGN-BOT":
                        store._conn.execute("UPDATE execution_events SET bot_instance_id='BOT-FOREIGN' WHERE event_id=?", (final_id,))
                    elif damage == "CLOCK-CONFLICT":
                        store._conn.execute("UPDATE execution_events SET created_at='2026-09-03T12:10:01Z' WHERE event_id=?", (event_id,))
                    elif damage == "OUTCOME-CONFLICT":
                        payload = store.get_execution_event(result_id)["payload"]
                        payload["result"]["outcome"] = "UNKNOWN_REQUIRES_RECONCILIATION"
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), result_id))
                    elif damage == "FINAL-UNHASHABLE-REFERENCE":
                        payload = store.get_execution_event(final_id)["payload"]
                        payload["result_event_id"] = {}
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), final_id))
                    elif damage in {"RESULT-ID-CONFLICT", "RESULT-NONFINITE"}:
                        payload = store.get_execution_event(result_id)["payload"]
                        payload["result"]["result_id" if damage == "RESULT-ID-CONFLICT" else "chargeable_cost_usd"] = "foreign-result" if damage == "RESULT-ID-CONFLICT" else "NaN"
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), result_id))
                    else:
                        raw = "null" if damage == "RESULT-NULL" else "{" if damage == "FINAL-INVALID-JSON" else "{}"
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (raw, event_id))
                    self.assertEqual(store.get_position(pid), natural)
                    reader = PaperPlaneStore(store.path, readonly=True)
                    try:
                        summary = obligation_summary(reader, mode="PAPER")
                    finally:
                        reader.close()
                    self.assertEqual(summary["position_count"], 1)
                    self.assertEqual(summary["inventory_status"], "UNKNOWN")
                    self.assertEqual(summary["known_cost_basis_floor_usd"], "30")
                    denied = self.admission(store, key + "-AFTER")
                    self.assertEqual(denied["reason_code"], "OUTSTANDING_OBLIGATIONS_UNKNOWN")
                    self.assertEqual(store.get_position(pid), natural)

    def test_natural_unattempted_cancel_releases_only_with_original_pre_attempt_witness(self):
        for damage in (None, "MISSING", "EMPTY", "FROM-ATTEMPTING"):
            with self.subTest(damage=damage):
                store = self.store("unattempted-" + str(damage) + ".sqlite")
                self.envelope(store, money="90")
                pid = self.admission(store, "SIGDEC-NATURAL-CANCEL-" + str(damage).upper())["position_id"]
                natural = store.cancel_entry_intent(pid, reason_code="ENTRIES_PAUSED")
                self.assertIsNone(natural["qty_dec"])
                self.assertEqual(natural["remaining_qty_dec"], "0")
                self.assertEqual(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[pid]), [])
                event = next(iter(store.filtered_execution_events(event_type="ENTRY_INTENT_CANCELLED", position_ids=[pid])))
                if damage == "MISSING":
                    store._conn.execute("DELETE FROM execution_events WHERE event_id=?", (event["event_id"],))
                elif damage is not None:
                    payload = {} if damage == "EMPTY" else {**event["payload"], "from_state": "ATTEMPTING"}
                    store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), event["event_id"]))
                reader = PaperPlaneStore(store.path, readonly=True)
                try:
                    summary = obligation_summary(reader, mode="PAPER")
                finally:
                    reader.close()
                self.assertEqual(summary["position_count"], 0 if damage is None else 1)
                self.assertEqual(summary["inventory_status"], "KNOWN" if damage is None else "UNKNOWN")
                admitted = self.admission(store, "SIGDEC-AFTER-NATURAL-CANCEL-" + str(damage).upper())
                self.assertEqual(admitted["reason_code"], "VERTICAL_ENTER" if damage is None else "OUTSTANDING_OBLIGATIONS_UNKNOWN")
                self.assertEqual(store.get_position(pid), natural)

    def test_nonfill_frees_capacity_but_unknown_cost_stays_economic(self):
        store = self.store()
        self.envelope(store)
        admitted = self.admission(store, "SIGDEC-NONFILL")
        attempted = self.attempt(store, admitted["position_id"])
        accept_modeled_result(store, result={"attempt_id": attempted["attempt_id"], "result_id": "nonfill", "outcome": "NO_ROUTE", "observed_at": T0})
        self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 0)
        self.assertEqual(build_operations_projection(store)["modeled_attempt_costs"]["additional_cost_status"], "UNKNOWN")
        self.assertIsNotNone(self.admission(store, "SIGDEC-AFTER-NONFILL")["position_id"])

    def test_v1_0_native_complete_result_chain_still_releases_capacity(self):
        for exit_version in ("1.0", "1.1"):
            with self.subTest(exit_version=exit_version):
                store = self.store("legacy-entry-exit-" + exit_version + ".sqlite")
                self.envelope(store, money="90")
                pid = self.admission(store, "SIGDEC-V10-FULL-RELEASE")["position_id"]
                entry = self.attempt(store, pid)
                accept_modeled_result(store, result={"attempt_id": entry["attempt_id"], "result_id": "v10-complete-entry",
                    "outcome": "LANDED_SUCCESS", "observed_at": T0, "unit_price_usd": "0.000003",
                    "filled_notional_usd": "30", "chargeable_cost_usd": "0"})
                self.close_request(store, pid, "v10-close")
                exit_attempt = self.attempt(store, pid, "EXIT", "v10-exit")
                result = {"attempt_id": exit_attempt["attempt_id"], "result_id": "v10-complete-exit",
                    "outcome": "LANDED_SUCCESS", "observed_at": T0, "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"}
                if exit_version == "1.1":
                    result = self.exit_result(exit_attempt["attempt_id"], "v10-complete-exit", sold="10000000", remaining="0", cost="0", outcome="LANDED_SUCCESS")
                accept_modeled_result(store, result=result)
                reader = PaperPlaneStore(store.path, readonly=True)
                try:
                    self.assertEqual(obligation_summary(reader, mode="PAPER")["position_count"], 0)
                finally:
                    reader.close()
                rid = store.get_execution_event("FINAL-" + entry["attempt_id"])["payload"]["result_event_id"]
                payload = store.get_execution_event(rid)["payload"]
                original = json.dumps(payload)
                payload["result"]["filled_notional_usd"] = "31"
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(payload), rid))
                self.assertEqual(obligation_summary(store, mode="PAPER")["inventory_status"], "UNKNOWN")
                self.assertEqual(self.admission(store, "SIGDEC-DURING-CORRUPT-V10")["reason_code"], "OUTSTANDING_OBLIGATIONS_UNKNOWN")
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (original, rid))
                self.assertEqual(self.admission(store, "SIGDEC-AFTER-V10-FULL-RELEASE")["reason_code"], "VERTICAL_ENTER")

    def test_v1_1_entry_preserves_raw_quote_quantity_and_included_fee(self):
        store = self.store()
        self.envelope(store, mode="SHADOW")
        pid = self.entry(store, mode="SHADOW", quantity="9999999", semantics="INCLUDED_IN_UNIT_PRICE")
        position = store.get_position(pid)
        self.assertEqual(position["qty_dec"], "9999999")
        self.assertEqual(position["entry_fee_usd_dec"], "0")
        self.close_request(store, pid, "close")
        attempted = self.attempt(store, pid, "EXIT", "exit", mode="SHADOW")
        result = self.exit_result(attempted["attempt_id"], "quoted-exit", sold="9999999", remaining="0", outcome="LANDED_SUCCESS", cost="0")
        result["fee_semantics"] = "INCLUDED_IN_UNIT_PRICE"
        position = accept_modeled_result(store, result=result)["position"]
        self.assertEqual(position["exit_fee_usd_dec"], "0")
        self.assertEqual(position["realized_net_pnl_usd_dec"], position["realized_gross_pnl_usd_dec"])

    def test_partial_entry_raw_rounddown_retains_exact_paid_notional_without_fee_double_count(self):
        store = self.store()
        self.envelope(store, mode="SHADOW")
        admitted = self.admission(store, "SIGDEC-RAW-ROUNDDOWN", mode="SHADOW")
        attempt = self.attempt(store, admitted["position_id"], mode="SHADOW")
        notional, quantity = Decimal("29.999999"), Decimal("9999999")
        result = {"schema_version": "1.1", "attempt_id": attempt["attempt_id"],
            "result_id": "raw-rounded-entry", "outcome": "PARTIAL", "observed_at": T0,
            "unit_price_usd": format(notional / quantity, "f"), "filled_notional_usd": str(notional),
            "quantity_filled": str(quantity), "quantity_unit": "TOKEN_UNITS",
            "fee_semantics": "INCLUDED_IN_UNIT_PRICE", "chargeable_cost_usd": "0"}
        position = accept_modeled_result(store, result=result)["position"]
        self.assertEqual(position["state"], "PARTIAL")
        self.assertEqual(position["qty_dec"], "9999999")
        self.assertEqual(position["entered_notional_usd_dec"], "29.999999")
        self.assertEqual(position["remaining_cost_basis_usd_dec"], "29.999999")
        self.assertEqual(position["entry_fee_usd_dec"], "0")
        self.assertEqual(obligation_summary(store, mode="SHADOW")["outstanding_cost_basis_usd"], "29.999999")

    def test_invalid_residual_quantity_preserves_identity_bound_unknown_economics_readback(self):
        root = isolated_factory_root(self.dir / "isolated-factory")
        store = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
        self._stores.append(store)
        self.envelope(store)
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        attempt = self.attempt(store, pid, "EXIT", "partial-before-corruption")
        accept_modeled_result(store, result=self.exit_result(attempt["attempt_id"], "partial-before-corruption"))
        store.record_position_mark(position_id=pid, mark_price_dec="0.000003", as_of=T0,
            evidence_class="PAPER_MARK_TO_MODEL")
        original = store.get_position(pid)
        identity = {"position_id": pid, "bot_instance_id": original["bot_instance_id"],
            "strategy_id": original["strategy_id"], "strategy_version": original["strategy_version_label"],
            "activation_epoch_id": original["activation_epoch_id"], "mode": "PAPER"}
        app = FactoryApplication(root=root)
        for marked in (True, False):
            for residual in ("NaN", "Infinity", "not-a-decimal", "-1"):
                with self.subTest(marked=marked, residual=residual):
                    store._conn.execute("UPDATE positions SET remaining_qty_dec=?, unrealized_evidence_class=? WHERE position_id=?",
                        (residual, "PAPER_MARK_TO_MODEL" if marked else None, pid))
                    before = store.get_position(pid), store.execution_events()
                    reader = PaperPlaneStore(store.path, readonly=True)
                    try:
                        projection = compose_risk_economics(root, reader, as_of=T0)
                    finally:
                        reader.close()
                    for view in (projection, app.economics_projection()):
                        self.assertEqual(view["source_status"], "PRESENT")
                        gap = next(row for row in view["gaps"] if row["code"] == "REMAINING_QUANTITY_INVALID")
                        self.assertEqual({key: gap[key] for key in identity}, identity)
                        self.assertEqual(gap["status"], "UNKNOWN")
                        partial = view["partial_realized_rows"][0]
                        self.assertEqual(partial["status"], "UNKNOWN")
                        self.assertEqual(partial["gap"], "REMAINING_QUANTITY_INVALID")
                        self.assertIsNone(partial["remaining_quantity"])
                        self.assertEqual(partial["realized_trade_net_after_allocated_fees_usd"], original["realized_net_pnl_usd_dec"])
                        mark = view["open_mark_scopes"][0]["rows"][0]
                        self.assertEqual(mark["status"], "UNKNOWN")
                        self.assertIsNone(mark["unrealized_net_after_modeled_fees_usd"])
                        self.assertEqual(view["next_safe_action"], "INSPECT_POSITION_EVIDENCE")
                    self.assertEqual((store.get_position(pid), store.execution_events()), before)

    def test_invalid_residual_money_preserves_identity_bound_unknown_economics_readback(self):
        root = isolated_factory_root(self.dir / "isolated-factory")
        store = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
        self._stores.append(store)
        self.envelope(store)
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        attempt = self.attempt(store, pid, "EXIT", "partial-before-money-corruption")
        accept_modeled_result(store, result=self.exit_result(attempt["attempt_id"], "partial-before-money-corruption"))
        store.record_position_mark(position_id=pid, mark_price_dec="0.000003", as_of=T0,
            evidence_class="PAPER_MARK_TO_MODEL")
        original = store.get_position(pid)
        identity = {"position_id": pid, "bot_instance_id": original["bot_instance_id"],
            "strategy_id": original["strategy_id"], "strategy_version": original["strategy_version_label"],
            "activation_epoch_id": original["activation_epoch_id"], "mode": "PAPER"}
        app = FactoryApplication(root=root)
        for column, field, code in (("remaining_cost_basis_usd_dec", "remaining_cost_basis_usd", "REMAINING_COST_BASIS_INVALID"),
                ("remaining_entry_fee_usd_dec", "remaining_entry_fee_usd", "REMAINING_ENTRY_FEE_INVALID")):
            for value in ("NaN", "Infinity", "bad-decimal", "-1"):
                with self.subTest(column=column, value=value):
                    store._conn.execute("UPDATE positions SET remaining_cost_basis_usd_dec=?, remaining_entry_fee_usd_dec=? WHERE position_id=?",
                        (original["remaining_cost_basis_usd_dec"], original["remaining_entry_fee_usd_dec"], pid))
                    store._conn.execute(f"UPDATE positions SET {column}=? WHERE position_id=?", (value, pid))
                    before = store.get_position(pid), store.execution_events()
                    for view in (compose_risk_economics(root, store, as_of=T0), app.economics_projection()):
                        self.assertEqual(view["source_status"], "PRESENT")
                        gap = next(row for row in view["gaps"] if row["code"] == code)
                        self.assertEqual({key: gap[key] for key in identity}, identity)
                        self.assertEqual(gap["status"], "UNKNOWN")
                        partial = view["partial_realized_rows"][0]
                        self.assertEqual(partial["status"], "UNKNOWN")
                        self.assertEqual(partial["gap"], code)
                        self.assertIsNone(partial[field])
                        self.assertEqual(partial["remaining_quantity"], "6000000")
                        self.assertEqual(partial["realized_trade_net_after_allocated_fees_usd"], original["realized_net_pnl_usd_dec"])
                        mark = view["open_mark_scopes"][0]["rows"][0]
                        self.assertEqual(mark["status"], "UNKNOWN")
                        self.assertEqual(mark["gap"], code)
                        self.assertIsNone(mark[field])
                        self.assertIsNone(mark["unrealized_net_after_modeled_fees_usd"])
                        self.assertEqual(view["next_safe_action"], "INSPECT_POSITION_EVIDENCE")
                    self.assertEqual((store.get_position(pid), store.execution_events()), before)

        store._conn.execute("UPDATE positions SET remaining_cost_basis_usd_dec=?, remaining_entry_fee_usd_dec=? WHERE position_id=?",
            (original["remaining_cost_basis_usd_dec"], original["remaining_entry_fee_usd_dec"], pid))
        final_attempt = self.attempt(store, pid, "EXIT", "final-before-money-corruption")
        accept_modeled_result(store, result=self.exit_result(final_attempt["attempt_id"], "final-before-money-corruption",
            sold="6000000", remaining="0", price="0.000003", outcome="LANDED_SUCCESS", cost="0"))
        closed = store.get_position(pid)
        for column, code in (("remaining_cost_basis_usd_dec", "REMAINING_COST_BASIS_INVALID"),
                ("remaining_entry_fee_usd_dec", "REMAINING_ENTRY_FEE_INVALID")):
            for value in ("NaN", "Infinity", "bad-decimal", "-1"):
                with self.subTest(reconciled=True, column=column, value=value):
                    store._conn.execute("UPDATE positions SET remaining_cost_basis_usd_dec=?, remaining_entry_fee_usd_dec=? WHERE position_id=?",
                        (closed["remaining_cost_basis_usd_dec"], closed["remaining_entry_fee_usd_dec"], pid))
                    store._conn.execute(f"UPDATE positions SET {column}=? WHERE position_id=?", (value, pid))
                    before = store.get_position(pid), store.execution_events()
                    view = app.economics_projection()
                    row = view["reconciled_scopes"][0]["rows"][0]
                    self.assertEqual(row["status"], "UNKNOWN")
                    self.assertFalse(row["trusted"])
                    self.assertEqual(row["gap"], code)
                    self.assertIsNone(view["reconciled_net_pnl_usd"])
                    gap = next(item for item in view["gaps"] if item["code"] == code)
                    self.assertEqual({key: gap[key] for key in identity}, identity)
                    self.assertEqual(gap["status"], "UNKNOWN")
                    self.assertEqual((store.get_position(pid), store.execution_events()), before)

    def test_invalid_quantity_overfill_units_and_crash_are_atomic(self):
        store = self.store()
        self.envelope(store)
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        attempted = self.attempt(store, pid, "EXIT", "exit")
        result = self.exit_result(attempted["attempt_id"], "partial")
        before = store.get_position(pid), store.execution_events()
        for patch_fields in ({"quantity_sold": "NaN"}, {"quantity_sold": "-1"}, {"quantity_sold": "10000001"},
                             {"quantity_unit": "USD"}, {"remaining_quantity": "3"}, {"filled_notional_usd": "13.2"},
                             {"fee_semantics": "GUESSED"}):
            with self.assertRaises(PaperPlaneError):
                accept_modeled_result(store, result={**result, **patch_fields})
            self.assertEqual((store.get_position(pid), store.execution_events()), before)
        original = store.append_execution_event
        def crash(**kwargs):
            if kwargs["event_type"] == "MODELED_RESULT_ACCEPTED":
                raise RuntimeError("synthetic crash")
            return original(**kwargs)
        with patch.object(store, "append_execution_event", crash), self.assertRaises(RuntimeError):
            accept_modeled_result(store, result=result)
        self.assertEqual((store.get_position(pid), store.execution_events()), before)

    def test_repeat_envelope_cas_corruption_and_attempt_recheck(self):
        store = self.store()
        configured = self.envelope(store, money="60")
        request = dict(mode="PAPER", candidate_raw={"max_outstanding_positions": 2, "max_outstanding_cost_basis_usd": "60"},
            expected_current_sha256="0" * 64, idempotency_key="limits", as_of=T0)
        before = store.execution_events()
        self.assertTrue(configure_operating_envelope(store, **request)["idempotent"])
        self.assertEqual(store.execution_events(), before)
        with self.assertRaisesRegex(TradingRuntimePolicyError, "STALE_WRITE"):
            configure_operating_envelope(store, **{**request, "idempotency_key": "stale"})
        admitted = self.admission(store, "SIGDEC-BEFORE-CORRUPTION")
        store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_type='ORDINARY_OPERATING_ENVELOPE_CONFIGURED'")
        self.assertEqual(read_operating_envelope(store, "PAPER")["status"], "OPERATING_ENVELOPE_INVALID")
        denied = self.attempt(store, admitted["position_id"])
        self.assertFalse(denied["send_permitted"])
        self.assertEqual(denied["reason_code"], "OPERATING_ENVELOPE_INVALID")

    def test_modes_independent_and_concurrent_reservations_serialized(self):
        store = self.store()
        second = self.store()
        self.envelope(store, money="30", count=1)
        self.envelope(store, mode="SHADOW", key="shadow")
        self.admission(store, "SIGDEC-SHADOW-INDEPENDENT", mode="SHADOW")
        self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 0)
        barrier = threading.Barrier(2)
        results = []
        errors = []
        def reserve(connection, key):
            try:
                barrier.wait(timeout=5)
                results.append(self.admission(connection, key))
            except Exception as exc:
                errors.append(exc)
        workers = [threading.Thread(target=reserve, args=(connection, key)) for connection, key in
                   ((store, "SIGDEC-RACE-A"), (second, "SIGDEC-RACE-B"))]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(result.get("fill_deferred", False) for result in results), 1)
        self.assertEqual(obligation_summary(store, mode="PAPER")["position_count"], 1)

    def test_partial_unknown_retains_realized_leg_and_residual_upper_bound(self):
        store = self.store()
        self.envelope(store, money="90")
        pid = self.entry(store)
        self.close_request(store, pid, "close")
        first = self.attempt(store, pid, "EXIT", "first")
        accept_modeled_result(store, result=self.exit_result(first["attempt_id"], "partial", cost="0"))
        before = store.get_position(pid)
        second = self.attempt(store, pid, "EXIT", "second")
        accept_modeled_result(store, result={"attempt_id": second["attempt_id"], "result_id": "unknown-second",
            "outcome": "UNKNOWN_REQUIRES_RECONCILIATION", "observed_at": T0, "chargeable_cost_usd": "0"})
        after = store.get_position(pid)
        self.assertEqual(after["remaining_qty_dec"], "6000000")
        self.assertEqual(after["realized_net_pnl_usd_dec"], before["realized_net_pnl_usd_dec"])
        self.assertEqual(obligation_summary(store, mode="PAPER")["known_cost_basis_floor_usd"], "18")
        self.assertEqual(obligation_summary(store, mode="PAPER")["inventory_status"], "UNKNOWN")

    def test_corrupt_remainder_or_final_never_frees_capacity(self):
        store = self.store()
        self.envelope(store, money="90")
        pid = self.entry(store)
        store._conn.execute("UPDATE positions SET remaining_qty_dec='NaN', remaining_cost_basis_usd_dec='0' WHERE position_id=?", (pid,))
        summary = obligation_summary(store, mode="PAPER")
        self.assertEqual(summary["inventory_status"], "UNKNOWN")
        self.assertEqual(summary["known_cost_basis_floor_usd"], "30")
        store._conn.execute("UPDATE positions SET remaining_qty_dec='10000000', remaining_cost_basis_usd_dec='30' WHERE position_id=?", (pid,))
        store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_type='MODELED_ATTEMPT_FINAL'")
        self.assertEqual(obligation_summary(store, mode="PAPER")["inventory_status"], "UNKNOWN")
        nonfill_store = self.store("nonfill-corrupt.sqlite")
        self.envelope(nonfill_store, money="90")
        admitted = self.admission(nonfill_store, "SIGDEC-CORRUPT-NONFILL")
        attempt = self.attempt(nonfill_store, admitted["position_id"])
        accept_modeled_result(nonfill_store, result={"attempt_id": attempt["attempt_id"],
            "result_id": "nonfill-to-corrupt", "outcome": "NO_ROUTE", "observed_at": T0})
        nonfill_store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_type='MODELED_ATTEMPT_FINAL'")
        summary = obligation_summary(nonfill_store, mode="PAPER")
        self.assertEqual(summary["position_count"], 1)
        self.assertEqual(summary["inventory_status"], "UNKNOWN")
        self.assertEqual(summary["known_cost_basis_floor_usd"], "30")

    def test_entry_fee_allocation_and_leg_pnl_conserve_on_three_exits(self):
        store = self.store()
        self.envelope(store)
        pid = self.entry(store, quantity="7")
        self.close_request(store, pid, "close")
        for number, sold, remaining in ((1, "2", "5"), (2, "2", "3"), (3, "3", "0")):
            attempt = self.attempt(store, pid, "EXIT", f"leg-{number}")
            result = self.exit_result(attempt["attempt_id"], f"three-{number}", sold=sold, remaining=remaining,
                price="5", cost="0", outcome="LANDED_SUCCESS" if remaining == "0" else "PARTIAL")
            accept_modeled_result(store, result=result)
        legs = [event["payload"] for event in store.execution_events() if event["event_type"] == "MODELED_EXIT_QUANTITY_LEG"]
        position = store.get_position(pid)
        self.assertEqual(sum(Decimal(leg["allocated_entry_fee_usd"]) for leg in legs), Decimal("0.06"))
        self.assertEqual(sum(Decimal(leg["realized_gross_pnl_usd"]) for leg in legs), Decimal("5.00"))
        self.assertEqual(sum(Decimal(leg["realized_trade_net_usd"]) for leg in legs), Decimal("4.87"))
        self.assertEqual(position["realized_net_pnl_usd_dec"], "4.87")

    def test_v1_0_result_event_payload_and_replay_remain_exact(self):
        store = self.store()
        admitted = self.admission(store, "SIGDEC-V10", ordinary=False)
        attempt = self.attempt(store, admitted["position_id"])
        result = {"attempt_id": attempt["attempt_id"], "result_id": "legacy-entry", "outcome": "LANDED_SUCCESS",
            "observed_at": T0, "unit_price_usd": "0.000003", "filled_notional_usd": "30", "chargeable_cost_usd": "0"}
        accept_modeled_result(store, result=result)
        event = next(event for event in store.execution_events() if event["event_type"] == "MODELED_RESULT_ACCEPTED")
        self.assertEqual(event["payload"]["result"], result)
        self.assertNotIn("schema_version", event["payload"]["result"])
        before = store.execution_events()
        accept_modeled_result(store, result=result)
        self.assertEqual(store.execution_events(), before)

    def test_entry_price_quantity_notional_conflict_rejected_atomically(self):
        store = self.store()
        self.envelope(store)
        admitted = self.admission(store, "SIGDEC-PRICE-QUANTITY-CONFLICT")
        attempt = self.attempt(store, admitted["position_id"])
        before = store.get_position(admitted["position_id"]), store.execution_events()
        result = {"schema_version": "1.1", "attempt_id": attempt["attempt_id"], "result_id": "bad-entry",
            "outcome": "LANDED_SUCCESS", "observed_at": T0, "unit_price_usd": "0.000003",
            "filled_notional_usd": "30", "quantity_filled": "999", "quantity_unit": "TOKEN_UNITS",
            "fee_semantics": "INCLUDED_IN_UNIT_PRICE", "chargeable_cost_usd": "0"}
        with self.assertRaisesRegex(PaperPlaneError, "MODELED_ENTRY_QUANTITY_PRICE_CONFLICT"):
            accept_modeled_result(store, result=result)
        self.assertEqual((store.get_position(admitted["position_id"]), store.execution_events()), before)

    def test_readback_cost_is_bounded_by_outstanding_scope_not_historical_journal(self):
        store = self.store()
        self.envelope(store, money="60")
        pid = self.entry(store)
        bot = store.get_position(pid)["bot_instance_id"]
        def measure():
            steps = 0
            def step():
                nonlocal steps
                steps += 10
                return 0
            started = time.perf_counter()
            store._conn.set_progress_handler(step, 10)
            try:
                read_operating_envelope(store, "PAPER")
                summary = obligation_summary(store, mode="PAPER")
                assert_quantity_inventory_witness(store, store.get_position(pid), allow_pending=True)
            finally:
                store._conn.set_progress_handler(None, 0)
            self.assertEqual(summary["position_count"], 1)
            self.assertEqual(summary["inventory_status"], "KNOWN")
            return {"sqlite_steps": steps, "elapsed_seconds": time.perf_counter() - started}
        before = measure()
        # Use native model transitions: row-only terminal shapes are not proofs.
        preparation_started = time.perf_counter()
        for number in range(1000):
            key = f"SIGDEC-HISTORY-{number}"
            historical = self.admission(store, key, ordinary=False)["position_id"]
            attempt = self.attempt(store, historical)
            if number % 2:
                accept_modeled_result(store, result={"attempt_id": attempt["attempt_id"], "result_id": key + "-NONFILL",
                    "outcome": "NO_ROUTE", "observed_at": T0})
            else:
                accept_modeled_result(store, result={"attempt_id": attempt["attempt_id"], "result_id": key + "-ENTRY",
                    "outcome": "LANDED_SUCCESS", "observed_at": T0, "unit_price_usd": "0.000003",
                    "filled_notional_usd": "30", "chargeable_cost_usd": "0"})
                self.close_request(store, historical, key + "-CLOSE")
                exit_attempt = self.attempt(store, historical, "EXIT", "full-exit")
                accept_modeled_result(store, result=self.exit_result(exit_attempt["attempt_id"], key + "-EXIT",
                    sold="10000000", remaining="0", cost="0", outcome="LANDED_SUCCESS"))
            if number == 99:
                after_100_releases = measure()
        preparation_seconds = time.perf_counter() - preparation_started
        after_releases = measure()
        with store.immediate_write():
            store._conn.executemany("""INSERT INTO execution_events(event_id,event_type,bot_instance_id,
                position_id,created_at,payload_json) VALUES (?,'UNRELATED_SYNTHETIC_HISTORY',?,NULL,?,'{}')""",
                [(f"EVT-HISTORICAL-{number}", bot, T0) for number in range(12000)])
        after = measure()
        self.assertLess(after_100_releases["sqlite_steps"] - before["sqlite_steps"], 100 * 10000)
        self.assertLess(after_releases["sqlite_steps"] - after_100_releases["sqlite_steps"], 900 * 10000)
        self.assertLess(after["sqlite_steps"], after_releases["sqlite_steps"] * 1.05 + 1000)
        self.assertLess(after["elapsed_seconds"], 2)
        type(self).last_readback_metrics = {"native_valid_terminal_positions": 1000, "unrelated_journal_events": 12000,
            "native_history_preparation_seconds": preparation_seconds, "before": before, "after_100_valid_releases": after_100_releases,
            "after_1000_valid_releases": after_releases, "after_unrelated_journal": after}
        self.metrics = type(self).last_readback_metrics
        self.assertEqual(len(store.filtered_execution_events(event_type="ORDINARY_OPERATING_ENVELOPE_CONFIGURED")), 1)
