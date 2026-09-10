"""Focused proofs for FACTORY_OPERABILITY_SIGNAL_CALIBRATION_V1."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_operational_packet import (  # noqa: E402
    DISK_CRITICAL_PCT,
    STORAGE_HISTORY_RELATIVE,
    build_collector_operational_packet,
    compose_health_classes,
    resident_rdp_bytes,
    storage_history_sample_blocked,
)
from solana_alpha_lab.factory.collector_owner_pulse import (  # noqa: E402
    run_daily_owner_pulse,
)
from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    derive_current_provider_state,
)
from solana_alpha_lab.factory.hot90_storage_admission import (  # noqa: E402
    HARD_BYTES,
    HORIZON_DAYS,
    TARGET_BYTES,
    project_storage_runway,
)
from solana_alpha_lab.factory.observation_primitives import (  # noqa: E402
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_OK,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
)
from solana_alpha_lab.factory.observation_schedule import render_utc  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.operability_watch import INCIDENT_GRACE_SECONDS  # noqa: E402
from solana_alpha_lab.factory.remote_ops import load_config_v1_1  # noqa: E402

RECENT = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
SEARCH = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
QUOTE_BUY = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001"
NOW = datetime(2026, 9, 10, 7, 53, tzinfo=UTC)
OPEN_SPIKE = 200_000
RESIDENT_SCIENCE = 1_000_000
COMPLETED_RESIDENT = 50_000
LEGACY_RESIDENT = 25_000


def _call(
    primitive: str,
    at: datetime | str,
    http_class: str,
) -> dict[str, object]:
    stamp = at if isinstance(at, str) else render_utc(at)
    return {
        "primitive_id": primitive,
        "updated_at": stamp,
        "created_at": stamp,
        "payload": {"http_class": http_class},
    }


def _write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def _sqlite_bytes(store: ObservationScheduleStore) -> int:
    path = Path(store.path)
    size = int(path.stat().st_size)
    wal = Path(str(path) + "-wal")
    if wal.is_file():
        size += int(wal.stat().st_size)
    return size


def _write_history(
    root: Path,
    *,
    observed_at: datetime,
    sqlite_bytes: int,
    rdp_bytes: int,
) -> None:
    hist = root / STORAGE_HISTORY_RELATIVE
    hist.parent.mkdir(parents=True, exist_ok=True)
    hist.write_text(
        json.dumps(
            {
                "observed_at": render_utc(observed_at),
                "disk_used_pct": 10,
                "sqlite_bytes": sqlite_bytes,
                "rdp_bytes": rdp_bytes,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class ProviderCurrentStateTests(unittest.TestCase):
    def test_p1_recovered_recent_timeout_keeps_24h_but_not_current_failed(self) -> None:
        t0 = NOW - timedelta(hours=7)
        t1 = NOW - timedelta(hours=6)
        calls = [
            _call(RECENT, t0, HTTP_CLASS_TIMEOUT),
            _call(RECENT, t1, HTTP_CLASS_OK),
        ]
        current = derive_current_provider_state(calls)
        self.assertFalse(current["provider_current_failed"])
        classes = compose_health_classes(
            {
                "TIMEOUT_24h": 1,
                "provider_current_failed": False,
                "provider_current_auth_failed": False,
                "provider_current_rate_limited": False,
            }
        )
        self.assertNotIn("PROVIDER_FAILED", classes)

    def test_p2_search_ok_does_not_mask_recent_timeout(self) -> None:
        current = derive_current_provider_state(
            [
                _call(RECENT, NOW - timedelta(hours=2), HTTP_CLASS_TIMEOUT),
                _call(SEARCH, NOW - timedelta(hours=1), HTTP_CLASS_OK),
            ]
        )
        self.assertTrue(current["provider_current_failed"])

    def test_p3_quote_timeout_not_cleared_by_recent_ok(self) -> None:
        current = derive_current_provider_state(
            [
                _call(QUOTE_BUY, NOW - timedelta(hours=2), HTTP_CLASS_TIMEOUT),
                _call(RECENT, NOW - timedelta(hours=1), HTTP_CLASS_OK),
            ]
        )
        self.assertTrue(current["provider_current_failed"])

    def test_p4_quote_recovery_same_primitive(self) -> None:
        current = derive_current_provider_state(
            [
                _call(QUOTE_BUY, NOW - timedelta(hours=2), HTTP_CLASS_TIMEOUT),
                _call(QUOTE_BUY, NOW - timedelta(hours=1), HTTP_CLASS_OK),
            ]
        )
        self.assertFalse(current["provider_current_failed"])

    def test_p5_current_auth_401_and_403(self) -> None:
        for http_class in (HTTP_CLASS_401, HTTP_CLASS_403):
            with self.subTest(http_class=http_class):
                current = derive_current_provider_state(
                    [_call(RECENT, NOW - timedelta(minutes=5), http_class)]
                )
                self.assertTrue(current["provider_current_auth_failed"])
                self.assertFalse(current["provider_current_failed"])

    def test_p6_recovered_auth_keeps_24h_absent_current(self) -> None:
        current = derive_current_provider_state(
            [
                _call(RECENT, NOW - timedelta(hours=2), HTTP_CLASS_401),
                _call(RECENT, NOW - timedelta(hours=1), HTTP_CLASS_OK),
            ]
        )
        self.assertFalse(current["provider_current_auth_failed"])
        classes = compose_health_classes(
            {
                "HTTP_401_24h": 1,
                "provider_current_auth_failed": False,
                "provider_current_failed": False,
                "provider_current_rate_limited": False,
            }
        )
        self.assertNotIn("PROVIDER_AUTH_FAILED", classes)

    def test_p7_rate_limit_same_semantics(self) -> None:
        unresolved = derive_current_provider_state(
            [_call(RECENT, NOW - timedelta(minutes=5), HTTP_CLASS_429)]
        )
        self.assertTrue(unresolved["provider_current_rate_limited"])
        recovered = derive_current_provider_state(
            [
                _call(RECENT, NOW - timedelta(hours=2), HTTP_CLASS_429),
                _call(RECENT, NOW - timedelta(hours=1), HTTP_CLASS_OK),
            ]
        )
        self.assertFalse(recovered["provider_current_rate_limited"])

    def test_p8_one_recovered_plus_one_unresolved_stays_failed(self) -> None:
        current = derive_current_provider_state(
            [
                _call(RECENT, NOW - timedelta(hours=3), HTTP_CLASS_TIMEOUT),
                _call(RECENT, NOW - timedelta(hours=2), HTTP_CLASS_OK),
                _call(QUOTE_BUY, NOW - timedelta(hours=1), HTTP_CLASS_5XX),
            ]
        )
        self.assertTrue(current["provider_current_failed"])

    def test_p9_latest_by_time_not_list_order(self) -> None:
        timeout_at = NOW - timedelta(hours=1)
        ok_at = NOW - timedelta(minutes=10)
        reversed_list = [
            _call(RECENT, ok_at, HTTP_CLASS_OK),
            _call(RECENT, timeout_at, HTTP_CLASS_TIMEOUT),
        ]
        self.assertFalse(derive_current_provider_state(reversed_list)["provider_current_failed"])
        later_timeout_first = [
            _call(RECENT, timeout_at, HTTP_CLASS_TIMEOUT),
            _call(RECENT, NOW - timedelta(hours=3), HTTP_CLASS_OK),
        ]
        self.assertTrue(
            derive_current_provider_state(later_timeout_first)["provider_current_failed"]
        )

    def test_p10_malformed_ordering_cannot_manufacture_ok(self) -> None:
        current = derive_current_provider_state(
            [
                _call(RECENT, NOW - timedelta(hours=2), HTTP_CLASS_TIMEOUT),
                _call(RECENT, "not-a-timestamp", HTTP_CLASS_OK),
            ]
        )
        self.assertTrue(current["provider_current_failed"])
        malformed_failure = derive_current_provider_state(
            [
                _call(RECENT, "bad-time", HTTP_CLASS_TIMEOUT),
                _call(RECENT, NOW - timedelta(minutes=1), HTTP_CLASS_OK),
            ]
        )
        self.assertTrue(malformed_failure["provider_current_failed"])

    def test_fail_closed_missing_current_fields_still_use_24h(self) -> None:
        classes = compose_health_classes({"TIMEOUT_24h": 1, "HTTP_5XX_24h": 0})
        self.assertIn("PROVIDER_FAILED", classes)

    def test_transport_and_5xx_are_current_provider_failure(self) -> None:
        for http_class in (HTTP_CLASS_5XX, HTTP_CLASS_TRANSPORT):
            with self.subTest(http_class=http_class):
                current = derive_current_provider_state(
                    [_call(QUOTE_BUY, NOW - timedelta(minutes=3), http_class)]
                )
                self.assertTrue(current["provider_current_failed"])


class StorageResidentRunwayTests(unittest.TestCase):
    def test_s1_s2_open_job_not_multiplied_by_97_but_counted_once(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _write_bytes(rdp / "datasets" / "science.bin", RESIDENT_SCIENCE)
            _write_bytes(
                rdp / "datasets" / "publication_jobs" / "completed" / "done.json",
                COMPLETED_RESIDENT,
            )
            _write_bytes(
                rdp / "datasets" / "publication_jobs" / "legacy_full" / "old.json",
                LEGACY_RESIDENT,
            )
            _write_bytes(
                rdp / "datasets" / "publication_jobs" / "open" / "hot.json",
                OPEN_SPIKE,
            )
            resident = (
                RESIDENT_SCIENCE + COMPLETED_RESIDENT + LEGACY_RESIDENT
            )
            store = ObservationScheduleStore(root / "ops.sqlite")
            _write_history(
                root,
                observed_at=NOW - timedelta(hours=24),
                sqlite_bytes=_sqlite_bytes(store),
                rdp_bytes=resident,
            )
            packet = build_collector_operational_packet(
                root=root,
                store=store,
                now=NOW,
                observation_rdp=rdp,
            )
            self.assertEqual(packet["publication_jobs_open_bytes"], OPEN_SPIKE)
            self.assertEqual(packet["observation_rdp_resident_bytes"], resident)
            self.assertGreaterEqual(packet["observation_rdp_bytes"], resident + OPEN_SPIKE)
            growth = packet["data_growth_24h_bytes"]
            self.assertIsInstance(growth, int)
            self.assertLess(abs(int(growth)), OPEN_SPIKE)
            amplified = OPEN_SPIKE * HORIZON_DAYS
            projected = int(packet["projected_97d_bytes"])
            sqlite = int(packet["observation_sqlite_bytes"])
            baseline = project_storage_runway(
                incremental_compressed_bytes_per_day=max(0, int(growth)),
                current_same_volume_factory_bytes=sqlite + resident,
                mutable_backup_peak_bytes=0
                if packet.get("backup_sink_bytes") == "UNKNOWN"
                else int(packet.get("backup_sink_bytes") or 0)
                if isinstance(packet.get("backup_sink_bytes"), int)
                else 0,
                staging_peak_bytes=OPEN_SPIKE,
                retention_class="HOT90_RESIDENT",
            )
            self.assertEqual(projected, baseline["projected_total_same_volume_bytes"])
            self.assertLess(projected, sqlite + resident + amplified)
            self.assertGreaterEqual(projected, sqlite + resident + OPEN_SPIKE - 1)
            store.close()

    def test_s3_open_gone_does_not_oscillate_from_open_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _write_bytes(rdp / "datasets" / "science.bin", RESIDENT_SCIENCE)
            _write_bytes(
                rdp / "datasets" / "publication_jobs" / "completed" / "done.json",
                COMPLETED_RESIDENT,
            )
            resident = RESIDENT_SCIENCE + COMPLETED_RESIDENT
            store = ObservationScheduleStore(root / "ops.sqlite")
            _write_history(
                root,
                observed_at=NOW - timedelta(hours=24),
                sqlite_bytes=_sqlite_bytes(store),
                rdp_bytes=resident,
            )
            open_path = rdp / "datasets" / "publication_jobs" / "open" / "hot.json"
            _write_bytes(open_path, OPEN_SPIKE)
            with_open = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            open_path.unlink()
            without_open = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            delta = abs(
                int(with_open["projected_97d_bytes"])
                - int(without_open["projected_97d_bytes"])
            )
            self.assertLess(delta, OPEN_SPIKE * 2)
            self.assertLess(delta, OPEN_SPIKE * HORIZON_DAYS / 2)
            store.close()

    def test_s4_genuine_resident_growth_is_amplified_by_97(self) -> None:
        extra = 80_000
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _write_bytes(rdp / "datasets" / "science.bin", RESIDENT_SCIENCE + extra)
            store = ObservationScheduleStore(root / "ops.sqlite")
            _write_history(
                root,
                observed_at=NOW - timedelta(hours=24),
                sqlite_bytes=_sqlite_bytes(store),
                rdp_bytes=RESIDENT_SCIENCE,
            )
            packet = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            growth = int(packet["data_growth_24h_bytes"])
            self.assertGreater(growth, extra // 2)
            projected = int(packet["projected_97d_bytes"])
            sqlite = int(packet["observation_sqlite_bytes"])
            self.assertGreater(
                projected,
                sqlite + RESIDENT_SCIENCE + extra + extra * 50,
            )
            store.close()

    def test_s5_completed_and_legacy_remain_in_resident(self) -> None:
        total = RESIDENT_SCIENCE + COMPLETED_RESIDENT + LEGACY_RESIDENT + OPEN_SPIKE
        resident = resident_rdp_bytes(total, OPEN_SPIKE)
        self.assertEqual(resident, total - OPEN_SPIKE)
        self.assertEqual(resident, RESIDENT_SCIENCE + COMPLETED_RESIDENT + LEGACY_RESIDENT)

    def test_s6_physical_disk_critical_unchanged(self) -> None:
        classes = compose_health_classes(
            {
                "filesystem_disk_used_pct": DISK_CRITICAL_PCT,
                "provider_current_failed": False,
                "TIMEOUT_24h": 1,
            }
        )
        self.assertIn("DISK_CRITICAL", classes)

    def test_s7_target40_hard50_unchanged(self) -> None:
        self.assertEqual(TARGET_BYTES, 40 * 1024**3)
        self.assertEqual(HARD_BYTES, 50 * 1024**3)
        self.assertEqual(HORIZON_DAYS, 97)

    def test_s8_history_rows_read_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            rdp.mkdir()
            hist = root / STORAGE_HISTORY_RELATIVE
            hist.parent.mkdir(parents=True)
            original = {
                "observed_at": render_utc(NOW - timedelta(hours=24)),
                "disk_used_pct": 10,
                "sqlite_bytes": 42,
                "rdp_bytes": 99,
                "legacy_extra": "keep-me",
            }
            hist.write_text(json.dumps(original, sort_keys=True) + "\n", encoding="utf-8")
            store = ObservationScheduleStore(root / "ops.sqlite")
            build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            loaded = json.loads(hist.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(loaded, original)
            store.close()

    def test_s9_pulse_skips_history_when_open_jobs_exist_and_still_succeeds(self) -> None:
        self.assertTrue(
            storage_history_sample_blocked(
                publication_jobs_open_count=1, publication_jobs_open_bytes=0
            )
        )
        self.assertTrue(
            storage_history_sample_blocked(
                publication_jobs_open_count=0, publication_jobs_open_bytes=1
            )
        )
        self.assertFalse(
            storage_history_sample_blocked(
                publication_jobs_open_count=0, publication_jobs_open_bytes=0
            )
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _write_bytes(
                rdp / "datasets" / "publication_jobs" / "open" / "hot.json",
                OPEN_SPIKE,
            )
            store = ObservationScheduleStore(root / "ops.sqlite")
            sent: list[tuple[str, str, str]] = []

            def _transport(token: str, chat_id: str, body: str) -> None:
                sent.append((token, chat_id, body))

            emitted = run_daily_owner_pulse(
                root=root,
                store=store,
                mode="emit",
                now=NOW,
                observation_rdp=rdp,
                remote_config=load_config_v1_1(ROOT),
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "pulse-token",
                    "FACTORY_TELEGRAM_CHAT_ID": "42",
                },
                transport=_transport,
                record_storage_history=True,
            )
            self.assertEqual(emitted["mode"], "emit")
            self.assertTrue(sent)
            self.assertIn("FACTORY / DAILY", sent[0][2])
            hist = root / STORAGE_HISTORY_RELATIVE
            self.assertFalse(hist.is_file())
            store.close()

    def test_s10_next_sample_after_skip_normalizes_elapsed_span(self) -> None:
        extra = 36_000
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _write_bytes(rdp / "datasets" / "science.bin", RESIDENT_SCIENCE + extra)
            store = ObservationScheduleStore(root / "ops.sqlite")
            _write_history(
                root,
                observed_at=NOW - timedelta(hours=36),
                sqlite_bytes=_sqlite_bytes(store),
                rdp_bytes=RESIDENT_SCIENCE,
            )
            packet = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            growth = int(packet["data_growth_24h_bytes"])
            scaled = int(round(extra * (24.0 / 36.0)))
            self.assertLess(abs(growth - scaled), extra // 5)
            store.close()

    def test_source_data_stale_and_watch_grace_untouched(self) -> None:
        stale = compose_health_classes({"source_poll_age": 181, "period_seconds": 60})
        not_stale = compose_health_classes({"source_poll_age": 180, "period_seconds": 60})
        self.assertIn("DATA_STALE", stale)
        self.assertNotIn("DATA_STALE", not_stale)
        self.assertEqual(INCIDENT_GRACE_SECONDS["SUSTAINED_PROVIDER_FAILURE"], 1800)
        self.assertEqual(INCIDENT_GRACE_SECONDS["DISK_RUNWAY_HARD50"], 0)
        watch = (ROOT / "src/solana_alpha_lab/factory/operability_watch.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("SOURCE_DATA_STALE", watch)


if __name__ == "__main__":
    unittest.main()
