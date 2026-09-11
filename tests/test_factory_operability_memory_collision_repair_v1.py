"""Focused proofs for FACTORY_OPERABILITY_MEMORY_COLLISION_REPAIR_V1."""

from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory import collector_operational_packet as packet_mod  # noqa: E402
from solana_alpha_lab.factory.collector_operational_packet import (  # noqa: E402
    STORAGE_HISTORY_RELATIVE,
    _rdp_inventory_bytes,
    build_collector_operational_packet,
    compose_health_classes,
    resident_rdp_bytes,
    storage_history_sample_blocked,
)
from solana_alpha_lab.factory.collector_owner_pulse import (  # noqa: E402
    DAILY_PULSE_ON_CALENDAR,
    run_daily_owner_pulse,
)
from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    derive_current_provider_state,
)
from solana_alpha_lab.factory.hot90_storage_admission import (  # noqa: E402
    HARD_BYTES,
    HORIZON_DAYS,
    TARGET_BYTES,
)
from solana_alpha_lab.factory.observation_primitives import (  # noqa: E402
    HTTP_CLASS_OK,
    HTTP_CLASS_TIMEOUT,
)
from solana_alpha_lab.factory.observation_schedule import render_utc  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.operability_watch import (  # noqa: E402
    INCIDENT_GRACE_SECONDS,
    WATCH_ON_CALENDAR,
)
from solana_alpha_lab.factory.remote_ops import load_config_v1_1  # noqa: E402

NOW = datetime(2026, 9, 11, 7, 25, tzinfo=UTC)
SCIENCE = 4_000
OPEN_JSON = 800
OPEN_TMP = 150
COMPLETED = 500
LEGACY = 300


def _write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def _seed_rdp(rdp: Path) -> dict[str, int]:
    _write_bytes(rdp / "datasets" / "science.bin", SCIENCE)
    _write_bytes(rdp / "datasets" / "publication_jobs" / "open" / "hot.json", OPEN_JSON)
    _write_bytes(
        rdp / "datasets" / "publication_jobs" / "open" / "partial.json.tmp",
        OPEN_TMP,
    )
    _write_bytes(
        rdp / "datasets" / "publication_jobs" / "completed" / "done.json",
        COMPLETED,
    )
    _write_bytes(
        rdp / "datasets" / "publication_jobs" / "legacy_full" / "old.json",
        LEGACY,
    )
    link = rdp / "datasets" / "science.link"
    try:
        os.symlink(rdp / "datasets" / "science.bin", link)
    except OSError:
        pass
    open_bytes = OPEN_JSON + OPEN_TMP
    total = SCIENCE + open_bytes + COMPLETED + LEGACY
    return {
        "total": total,
        "open_count": 2,
        "open_bytes": open_bytes,
        "science": SCIENCE,
        "resident": total - open_bytes,
    }


class RdpInventoryParityTests(unittest.TestCase):
    def test_r1_streaming_inventory_matches_representative_tree(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            rdp = Path(tmp) / "observation_rdp"
            expected = _seed_rdp(rdp)
            total, open_count, open_bytes, science = _rdp_inventory_bytes(rdp)
            self.assertEqual(total, expected["total"])
            self.assertEqual(open_count, expected["open_count"])
            self.assertEqual(open_bytes, expected["open_bytes"])
            self.assertEqual(science, expected["science"])
            self.assertEqual(resident_rdp_bytes(total, open_bytes), expected["resident"])
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            packet = build_collector_operational_packet(
                root=Path(tmp), store=store, now=NOW, observation_rdp=rdp
            )
            self.assertEqual(packet["observation_rdp_bytes"], expected["total"])
            self.assertEqual(packet["publication_jobs_open_count"], 2)
            self.assertEqual(packet["publication_jobs_open_bytes"], expected["open_bytes"])
            self.assertEqual(packet["observation_rdp_resident_bytes"], expected["resident"])
            self.assertEqual(
                packet["observation_rdp_bytes_excluding_publication_jobs"],
                expected["science"],
            )
            store.close()

    def test_r2_implementation_does_not_retain_path_inventory(self) -> None:
        source = inspect.getsource(_rdp_inventory_bytes)
        self.assertNotIn("files.append", source)
        self.assertNotIn("files: list", source)
        self.assertNotIn("list[tuple[Path, int]]", source)
        self.assertNotRegex(source, r"\bfiles\s*=")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            rdp = Path(tmp) / "rdp"
            for idx in range(250):
                _write_bytes(rdp / "datasets" / "many" / f"{idx:04d}.bin", 3)
            total, open_count, open_bytes, science = _rdp_inventory_bytes(rdp)
            self.assertEqual(open_count, 0)
            self.assertEqual(open_bytes, 0)
            self.assertEqual(total, 250 * 3)
            self.assertEqual(science, 250 * 3)

    def test_r3_packet_does_not_call_second_whole_rdp_walk(self) -> None:
        self.assertFalse(hasattr(packet_mod, "rdp_bytes_excluding_publication_jobs"))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            rdp = Path(tmp) / "observation_rdp"
            _seed_rdp(rdp)
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            rdp_walks: list[str] = []
            real_walk = os.walk

            def _walk(top: str | os.PathLike[str], *args: object, **kwargs: object):
                resolved = os.path.abspath(top)
                if os.path.abspath(rdp) == resolved or resolved.startswith(
                    os.path.abspath(rdp) + os.sep
                ):
                    rdp_walks.append(resolved)
                return real_walk(top, *args, **kwargs)

            with patch(
                "solana_alpha_lab.factory.observation_publication_jobs.rdp_bytes_excluding_publication_jobs",
                side_effect=AssertionError("second whole-RDP traversal"),
            ), patch("solana_alpha_lab.factory.collector_operational_packet.os.walk", _walk):
                packet = build_collector_operational_packet(
                    root=Path(tmp), store=store, now=NOW, observation_rdp=rdp
                )
            self.assertEqual(len(rdp_walks), 1)
            self.assertEqual(packet["publication_jobs_open_count"], 2)
            store.close()


class NoScienceSnapshotTests(unittest.TestCase):
    def test_r4_ordinary_packet_does_not_load_scientific_source(self) -> None:
        self.assertFalse(hasattr(packet_mod, "load_observation_rdp_source"))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _seed_rdp(rdp)
            snapshot = rdp / "live_observation_rebuild" / "source_snapshot.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(
                json.dumps(
                    {
                        "members": [{"entity_id": "x"}] * 50,
                        "observations": [{"id": n} for n in range(50)],
                        "open_publication": True,
                        "discovery_coverage_class": "READY_VALID",
                    }
                ),
                encoding="utf-8",
            )
            manifest = rdp / "live_cohort_release_demo" / "release_manifest.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    {
                        "release_id": "REL-BOUNDED-001",
                        "corpus_version": 2,
                        "labels": {"logical_dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"},
                    }
                ),
                encoding="utf-8",
            )
            store = ObservationScheduleStore(root / "ops.sqlite")
            with patch(
                "solana_alpha_lab.factory.live_cohort_discovery_release.load_observation_rdp_source",
                side_effect=AssertionError("scientific corpus loaded"),
            ):
                packet = build_collector_operational_packet(
                    root=root, store=store, now=NOW, observation_rdp=rdp
                )
            self.assertEqual(packet["cohort_readiness_state"], "UNKNOWN")
            self.assertEqual(packet["release_state"], "UNKNOWN")
            self.assertEqual(packet["release_blocked_reasons"], [])
            self.assertNotEqual(packet["cohort_readiness_state"], "READY_VALID")
            self.assertNotEqual(packet["release_state"], "COLLECTING")
            self.assertEqual(packet["last_sealed_release_id"], "REL-BOUNDED-001")
            store.close()

    def test_r4b_packet_import_does_not_load_scientific_release_module(self) -> None:
        import subprocess

        probe = (
            "from solana_alpha_lab.factory import collector_operational_packet as m\n"
            "import sys\n"
            "assert 'solana_alpha_lab.factory.live_cohort_discovery_release' not in sys.modules\n"
            "assert not hasattr(m, 'load_observation_rdp_source')\n"
            "assert m.RELEASE_MANIFEST_NAME == 'release_manifest.json'\n"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", probe],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(SRC)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_r4c_corrupt_or_empty_manifest_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _seed_rdp(rdp)
            empty = rdp / "live_cohort_release_demo" / "release_manifest.json"
            empty.parent.mkdir(parents=True, exist_ok=True)
            empty.write_text("{}", encoding="utf-8")
            store = ObservationScheduleStore(root / "ops.sqlite")
            packet = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            self.assertEqual(packet["last_sealed_release_id"], packet_mod.UNKNOWN)
            self.assertNotEqual(packet["last_sealed_release_id"], "live_cohort_release_demo")
            empty.write_text("{not-json", encoding="utf-8")
            bad = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            self.assertEqual(bad["last_sealed_release_id"], packet_mod.UNKNOWN)
            self.assertNotEqual(bad["last_sealed_release_id"], "live_cohort_release_demo")
            store.close()


class SemanticsPreservedTests(unittest.TestCase):
    def test_r5_open_bytes_once_not_times_97_completed_legacy_resident(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            expected = _seed_rdp(rdp)
            store = ObservationScheduleStore(root / "ops.sqlite")
            hist = root / STORAGE_HISTORY_RELATIVE
            hist.parent.mkdir(parents=True, exist_ok=True)
            sqlite_now = int(Path(store.path).stat().st_size)
            wal = Path(str(store.path) + "-wal")
            if wal.is_file():
                sqlite_now += int(wal.stat().st_size)
            hist.write_text(
                json.dumps(
                    {
                        "observed_at": render_utc(NOW - timedelta(hours=24)),
                        "disk_used_pct": 10,
                        "sqlite_bytes": sqlite_now,
                        "rdp_bytes": expected["resident"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            packet = build_collector_operational_packet(
                root=root, store=store, now=NOW, observation_rdp=rdp
            )
            self.assertEqual(packet["observation_rdp_resident_bytes"], expected["resident"])
            self.assertEqual(packet["publication_jobs_completed_bytes"], COMPLETED)
            self.assertEqual(packet["publication_jobs_legacy_full_bytes"], LEGACY)
            self.assertEqual(
                packet["observation_rdp_bytes_excluding_publication_jobs"],
                expected["science"],
            )
            growth = packet["data_growth_24h_bytes"]
            self.assertIsInstance(growth, int)
            self.assertLess(abs(int(growth)), expected["open_bytes"])
            projected = int(packet["projected_97d_bytes"])
            sqlite = int(packet["observation_sqlite_bytes"])
            amplified = expected["open_bytes"] * HORIZON_DAYS
            self.assertLess(projected, sqlite + expected["resident"] + amplified)
            self.assertGreater(amplified, expected["open_bytes"])
            self.assertEqual(TARGET_BYTES, 40 * 1024**3)
            self.assertEqual(HARD_BYTES, 50 * 1024**3)
            self.assertEqual(HORIZON_DAYS, 97)
            store.close()

    def test_r6_provider_current_state_still_clears_on_later_ok(self) -> None:
        timeout = {
            "primitive_id": "PRIM-JUPITER-TOKENS-V2-RECENT-001",
            "updated_at": render_utc(NOW - timedelta(minutes=10)),
            "created_at": render_utc(NOW - timedelta(minutes=10)),
            "payload": {"http_class": HTTP_CLASS_TIMEOUT},
        }
        recovered = {
            "primitive_id": "PRIM-JUPITER-TOKENS-V2-RECENT-001",
            "updated_at": render_utc(NOW - timedelta(minutes=1)),
            "created_at": render_utc(NOW - timedelta(minutes=1)),
            "payload": {"http_class": HTTP_CLASS_OK},
        }
        failed = derive_current_provider_state([timeout], now=NOW)
        self.assertTrue(failed["provider_current_failed"])
        ok = derive_current_provider_state([timeout, recovered], now=NOW)
        self.assertFalse(ok["provider_current_failed"])

    def test_r7_daily_pulse_renders_and_skips_history_while_open(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            _seed_rdp(rdp)
            store = ObservationScheduleStore(root / "ops.sqlite")
            sent: list[tuple[str, str, str]] = []

            def _transport(token: str, chat_id: str, body: str) -> None:
                sent.append((token, chat_id, body))

            dry = run_daily_owner_pulse(
                root=root,
                store=store,
                mode="dry-run",
                now=NOW,
                observation_rdp=rdp,
            )
            self.assertEqual(dry["on_calendar_utc"], DAILY_PULSE_ON_CALENDAR)
            self.assertIn("FACTORY / DAILY", dry["text"])
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
            self.assertTrue(sent)
            self.assertTrue(
                storage_history_sample_blocked(
                    publication_jobs_open_count=emitted["packet"][
                        "publication_jobs_open_count"
                    ],
                    publication_jobs_open_bytes=emitted["packet"][
                        "publication_jobs_open_bytes"
                    ],
                )
            )
            self.assertFalse((root / STORAGE_HISTORY_RELATIVE).is_file())
            for child in (rdp / "datasets" / "publication_jobs" / "open").iterdir():
                child.unlink()
            sampled = run_daily_owner_pulse(
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
            self.assertFalse(
                storage_history_sample_blocked(
                    publication_jobs_open_count=sampled["packet"][
                        "publication_jobs_open_count"
                    ],
                    publication_jobs_open_bytes=sampled["packet"][
                        "publication_jobs_open_bytes"
                    ],
                )
            )
            self.assertTrue((root / STORAGE_HISTORY_RELATIVE).is_file())
            store.close()

    def test_r8_pulse_offset_from_watch_observation_timer_unchanged(self) -> None:
        self.assertEqual(DAILY_PULSE_ON_CALENDAR, "*-*-* 06:20:00 UTC")
        self.assertNotEqual(DAILY_PULSE_ON_CALENDAR, "*-*-* 06:15:00 UTC")
        self.assertEqual(WATCH_ON_CALENDAR, "*-*-* *:0/15:00 UTC")
        pulse_timer = (
            ROOT / "configs/factory_remote_ops/factory-collector-owner-pulse.timer"
        ).read_text(encoding="utf-8")
        watch_timer = (
            ROOT / "configs/factory_remote_ops/factory-operability-watch.timer"
        ).read_text(encoding="utf-8")
        obs_timer = (
            ROOT / "configs/factory_remote_ops/factory-observation-schedule.timer"
        ).read_text(encoding="utf-8")
        self.assertIn("OnCalendar=*-*-* 06:20:00 UTC", pulse_timer)
        self.assertNotIn("OnCalendar=*-*-* 06:15:00 UTC", pulse_timer)
        self.assertIn("OnCalendar=*-*-* *:0/15:00 UTC", watch_timer)
        self.assertIn("OnUnitActiveSec=60s", obs_timer)
        self.assertNotIn("06:20", watch_timer)
        self.assertNotIn("06:15", obs_timer)

    def test_r9_source_data_stale_and_science_behavior_untouched(self) -> None:
        stale = compose_health_classes({"source_poll_age": 181, "period_seconds": 60})
        not_stale = compose_health_classes({"source_poll_age": 180, "period_seconds": 60})
        self.assertIn("DATA_STALE", stale)
        self.assertNotIn("DATA_STALE", not_stale)
        self.assertEqual(INCIDENT_GRACE_SECONDS["SOURCE_DATA_STALE"], 1800)
        watch = (ROOT / "src/solana_alpha_lab/factory/operability_watch.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"SOURCE_DATA_STALE": 1800', watch)
        scheduler = (ROOT / "src/solana_alpha_lab/factory/observation_scheduler.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def tick_once", scheduler)


if __name__ == "__main__":
    unittest.main()
