"""Bounded reads, edge truth, vertical consumers and heartbeat liveness."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from solana_alpha_lab.factory.collector_read_model import build_collector_read_model
from solana_alpha_lab.factory.collector_operational_packet import build_collector_operational_packet
from solana_alpha_lab.factory.collector_owner_pulse import run_daily_owner_pulse
from solana_alpha_lab.factory.operability_watch import (
    SNAPSHOT_RELATIVE, build_collector_snapshot, evaluate_operability,
)
from solana_alpha_lab.factory.external_heartbeat import HEARTBEAT_ENV, run_external_heartbeat
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.observation_schedule import render_utc

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
DIGEST = "a" * 64
RECENT = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
SEARCH = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"


class BoundedCallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = ObservationScheduleStore(self.root / "store.sqlite3")
        self.store.upsert_activation({
            "schedule_sha256": DIGEST, "activation_id": "A", "schedule_key": "fixture",
            "state": "ACTIVE", "starts_at": render_utc(NOW - timedelta(days=1)),
            "stops_admitting_at": render_utc(NOW + timedelta(days=3)),
            "payload": {"last_tick_at": render_utc(NOW)},
        }, clock=NOW)
        self.i = 0

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def call(self, at, *, primitive=RECENT, http="HTTP_OK", state="COMPLETED", **payload):
        self.i += 1
        stamp = render_utc(at) if isinstance(at, datetime) else at
        body = {"schedule_sha256": DIGEST, "activation_id": "A", "http_class": http,
                "status": "OBSERVED", **payload}
        self.store._conn.execute("INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(self.i), f"c{self.i}", f"a{self.i}", state, primitive,
             json.dumps(body), stamp, stamp))
        self.store._conn.commit()

    def read(self):
        return build_collector_read_model(self.store, now=NOW, schedule_sha256=DIGEST, activation_id="A")

    def test_window_scope_counters_and_strict_same_primitive_recovery(self):
        self.call(NOW - timedelta(days=2), http="HTTP_403", huge="x" * 100_000)
        self.call(NOW - timedelta(hours=24), http="TIMEOUT")
        self.call(NOW - timedelta(minutes=3), primitive=SEARCH)
        self.call(NOW - timedelta(minutes=2), state="STARTED", http=None, status="")
        self.call(NOW - timedelta(minutes=1), activation_id="OTHER", http="HTTP_401")
        model = self.read()
        self.assertEqual(model["TIMEOUT_24h"], 1)
        self.assertEqual(model["HTTP_403_24h"], 0)
        self.assertEqual(model["HTTP_401_24h"], 0)
        self.assertTrue(model["provider_current_failed"])
        self.call(NOW)
        model = self.read()
        self.assertFalse(model["provider_current_failed"])
        self.assertEqual(model["TIMEOUT_24h"], 1)
        self.assertEqual(model["observations_24h"], 3)
        self.assertEqual(model["last_source_poll_success_at"], render_utc(NOW))

    def test_equal_time_does_not_recover_and_fractional_order_is_temporal(self):
        self.call(NOW, http="TIMEOUT")
        self.call(NOW)
        self.assertTrue(self.read()["provider_current_failed"])
        # Seconds and fractional-seconds strings do not sort chronologically.
        self.call(NOW - timedelta(seconds=1))
        self.call(NOW - timedelta(seconds=1) + timedelta(microseconds=1), http="TIMEOUT")
        self.assertEqual(self.read()["last_source_poll_attempt_at"], render_utc(NOW))

    def test_invalid_and_future_never_manufacture_healthy_truth(self):
        self.call(NOW - timedelta(minutes=2), http="TIMEOUT")
        self.call(NOW + timedelta(days=1))
        self.call("not-a-timestamp", primitive=SEARCH)
        model = self.read()
        self.assertTrue(model["provider_current_failed"])
        self.assertEqual(model["call_diagnostics_status"], "UNKNOWN")
        self.assertIsNone(model["observations_24h"])
        self.assertIsNone(model["TIMEOUT_24h"])
        self.assertIsNone(model["last_source_poll_success_at"])
        self.assertIsNone(model["source_poll_age"])
        packet = build_collector_operational_packet(root=self.root, store=self.store, now=NOW,
                                                   remote_config={}, environ={})
        self.assertIn("PROVIDER_STATE_UNKNOWN", packet["health_classes"])
        self.assertNotEqual(packet["collector_verdict"], "OK")

    def test_malformed_payload_is_typed_unknown_not_crash_or_zero(self):
        self.call(NOW)
        self.store._conn.execute("UPDATE call_ledger SET payload_json = '{invalid'")
        self.store._conn.commit()
        model = self.read()
        self.assertEqual(model["call_diagnostics_status"], "UNKNOWN")
        self.assertIsNone(model["observations_24h"])
        self.assertIsNone(model["provider_current_failed"])

    def test_fractional_source_clock_and_missing_reason_parity(self):
        self.call(NOW, status="MISSING_TYPED", missing_reason="ENTITY_ABSENT_FROM_RESPONSE")
        self.call(NOW + timedelta(microseconds=1))
        # Future microseconds are not rounded into a success at NOW.
        self.assertIsNone(self.read()["observations_24h"])
        self.store._conn.execute("DELETE FROM call_ledger WHERE call_occurrence_id = 'c2'")
        self.store._conn.commit()
        self.call(NOW - timedelta(seconds=1), status="", missing_reason="ENTITY_ABSENT_FROM_RESPONSE")
        self.call(NOW - timedelta(seconds=1) + timedelta(microseconds=1), status="", missing_reason="DEPENDENCY_MISSING")
        model = self.read()
        self.assertEqual(model["typed_missing_24h"], 2)
        self.assertEqual(model["last_source_poll_attempt_at"], render_utc(NOW))

    def test_real_store_watch_retry_dedupe_recovery_and_daily_delivery(self):
        from solana_alpha_lab.factory.remote_ops import RemoteOpsError
        self.call(NOW, http="TIMEOUT", status="")
        alert = {"alert": {"token_env": "FACTORY_TELEGRAM_BOT_TOKEN", "chat_id_env": "FACTORY_TELEGRAM_CHAT_ID"}}
        env = {"FACTORY_TELEGRAM_BOT_TOKEN": "fixture-token", "FACTORY_TELEGRAM_CHAT_ID": "42"}
        delivered = []
        def ok(_token, _chat, text):
            delivered.append(text)
        def fail(_token, _chat, _text):
            raise RemoteOpsError("PULSE_TRANSPORT_FAILED")
        common = dict(root=self.root, store=self.store, remote_config=alert, environ=env, persist=True)
        evaluate_operability(**common, now=NOW, emit=False)
        failed = evaluate_operability(**common, now=NOW + timedelta(seconds=1801), emit=True, transport=fail)
        self.assertGreater(failed["pending_count"], 0)
        evaluate_operability(**common, now=NOW + timedelta(seconds=1802), emit=True, transport=ok)
        incident_count = sum("INCIDENT=SUSTAINED_PROVIDER_FAILURE" in text for text in delivered)
        self.assertEqual(incident_count, 1)
        first = len(delivered)
        evaluate_operability(**common, now=NOW + timedelta(seconds=1803), emit=True, transport=ok)
        self.assertEqual(len(delivered), first)
        self.call(NOW + timedelta(seconds=1804))
        evaluate_operability(**common, now=NOW + timedelta(seconds=1804), emit=True, transport=ok)
        self.assertTrue(any("MESSAGE_TYPE=RECOVERED" in text and "INCIDENT=SUSTAINED_PROVIDER_FAILURE" in text for text in delivered))
        pulse_common = {key: value for key, value in common.items() if key != "persist"}
        with self.assertRaisesRegex(RemoteOpsError, "PULSE_TRANSPORT_FAILED"):
            run_daily_owner_pulse(**pulse_common, now=NOW + timedelta(seconds=1805), mode="emit", transport=fail)
        pulse = run_daily_owner_pulse(**pulse_common, now=NOW + timedelta(seconds=1805), mode="emit", transport=ok)
        self.assertTrue(pulse["delivery"]["delivered"])
        repeated = run_daily_owner_pulse(**pulse_common, now=NOW + timedelta(seconds=1806), mode="emit", transport=ok)
        self.assertTrue(repeated["delivery"]["deduped"])

    def test_full_vertical_path_has_no_all_call_or_due_materialization(self):
        self.call(NOW, huge="x" * 200_000)
        with patch.object(self.store, "list_calls", side_effect=AssertionError("all calls")), \
             patch.object(self.store, "due_in_states", side_effect=AssertionError("all due")), \
             patch.object(self.store, "list_candidates", side_effect=AssertionError("all candidates")):
            self.assertEqual(self.read()["observations_24h"], 1)
            common = dict(root=self.root, store=self.store, now=NOW, remote_config={}, environ={})
            self.assertEqual(build_collector_operational_packet(**common)["observations_24h"], 1)
            self.assertIn("packet_verdict", evaluate_operability(**common, emit=False, persist=False))
            self.assertIn("MESSAGE_TYPE=DAILY", run_daily_owner_pulse(**common, mode="dry-run")["text"])

    def test_unknown_diagnostics_cannot_emit_provider_recovered(self):
        self.call(NOW, http="TIMEOUT", status="")
        delivered = []
        alert = {"alert": {"token_env": "FACTORY_TELEGRAM_BOT_TOKEN", "chat_id_env": "FACTORY_TELEGRAM_CHAT_ID"}}
        common = dict(root=self.root, store=self.store, remote_config=alert,
                      environ={"FACTORY_TELEGRAM_BOT_TOKEN": "fixture-token", "FACTORY_TELEGRAM_CHAT_ID": "42"},
                      transport=lambda _token, _chat, text: delivered.append(text), emit=True, persist=True)
        evaluate_operability(**common, now=NOW)
        evaluate_operability(**common, now=NOW + timedelta(seconds=1801))
        self.assertTrue(any("INCIDENT=SUSTAINED_PROVIDER_FAILURE" in text for text in delivered))
        self.store._conn.execute("UPDATE call_ledger SET payload_json = '{invalid'")
        self.store._conn.commit()
        evaluate_operability(**common, now=NOW + timedelta(seconds=1802))
        self.assertFalse(any("MESSAGE_TYPE=RECOVERED" in text and "INCIDENT=SUSTAINED_PROVIDER_FAILURE" in text for text in delivered))


class HeartbeatTests(unittest.TestCase):
    def test_only_fresh_valid_bounded_snapshot_pings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / SNAPSHOT_RELATIVE
            path.parent.mkdir(parents=True)
            sent = []
            env = {HEARTBEAT_ENV: "https://fixture.invalid/ping"}
            def run():
                return run_external_heartbeat(root=root, now=NOW, environ=env,
                    transport=lambda url: sent.append(url) or 200)
            self.assertEqual(run()["reason"], "WATCH_SNAPSHOT_MISSING")
            for stamp, reason in ((NOW - timedelta(seconds=1081), "WATCH_SNAPSHOT_STALE"),
                                  (NOW + timedelta(seconds=181), "WATCH_SNAPSHOT_INVALID")):
                path.write_text(json.dumps(build_collector_snapshot({"health_classes": []}, observed_at=render_utc(stamp))))
                self.assertEqual(run()["reason"], reason)
            for body in ("bad", "x" * 65537, json.dumps({"schema": "wrong"})):
                path.write_text(body)
                result = run()
                self.assertEqual(result["terminal"], "NO_PING")
                self.assertEqual(result["network_calls"], 0)
            self.assertEqual(sent, [])
            path.write_text(json.dumps(build_collector_snapshot({"health_classes": ["PROVIDER_FAILED"]}, observed_at=render_utc(NOW))))
            self.assertEqual(run()["terminal"], "HEARTBEAT_SENT")
            self.assertEqual(len(sent), 1)

    def test_import_is_light_and_unconfigured_is_quiet(self):
        code = "import sys; from pathlib import Path; from solana_alpha_lab.factory.external_heartbeat import run_external_heartbeat; result = run_external_heartbeat(root=Path('missing-fixture'), environ={'FACTORY_EXTERNAL_HEARTBEAT_URL': 'https://fixture.invalid/ping'}); assert result['terminal'] == 'NO_PING'; assert 'solana_alpha_lab.factory.collector_operational_packet' not in sys.modules; assert 'solana_alpha_lab.factory.observation_schedule_store' not in sys.modules"
        result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); " + code], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(run_external_heartbeat(environ={})["terminal"], "NOT_CONFIGURED")


class ResourceScaleTests(unittest.TestCase):
    def test_doubled_old_payload_history_does_not_double_full_packet_rss(self):
        from operability_bounded_call_profile import create_fixture
        measurements = []
        with tempfile.TemporaryDirectory() as directory:
            for rows in (1024, 2048):
                root = Path(directory) / str(rows)
                create_fixture(root, rows, 65536)
                completed = subprocess.run([
                    sys.executable, "-B", str(ROOT / "tests/operability_bounded_call_profile.py"),
                    "measure", "--root", str(root), "--consumer", "packet",
                ], cwd=ROOT, capture_output=True, text=True, check=True, timeout=120)
                measurements.append(json.loads(completed.stdout))
        first, doubled = measurements
        self.assertLess(doubled["peak_rss_bytes"], first["peak_rss_bytes"] * 1.25 + 8 * 1024**2)
        for result in measurements:
            self.assertEqual(result["legacy_call_read"]["call_payloads_decoded"], 0)
            self.assertEqual(result["store_read_stats"]["call_diagnostics_rows_returned"], 128)
            self.assertLess(result["peak_rss_bytes"], 512 * 1024**2)
            self.assertLess(result["wall_seconds"], 120)


if __name__ == "__main__":
    unittest.main()
