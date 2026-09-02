"""Zero-network vertical proof for collector operability + retention + daily pulse."""

from __future__ import annotations

import hashlib
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
    UNKNOWN,
    build_collector_operational_packet,
)
from solana_alpha_lab.factory.collector_owner_pulse import (  # noqa: E402
    DAILY_PULSE_ON_CALENDAR,
    render_daily_owner_pulse,
    run_daily_owner_pulse,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    RELEASE_MANIFEST_NAME,
    cohort_id_for_admission,
    seal_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.observation_primitives import HTTP_CLASS_OK  # noqa: E402
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_retention import (  # noqa: E402
    COMPACTION_MARKER,
    apply_retention,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.remote_ops import load_config_v1_1  # noqa: E402
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _snapshot_for_week,
)
from tests.test_observation_scheduler import GIT_SHA, NOW, _activate  # noqa: E402

OLD = NOW - timedelta(days=40)
RECENT = NOW - timedelta(hours=2)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_tree(path: Path) -> str:
    parts: list[str] = []
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = child.relative_to(path).as_posix()
        parts.append(f"{rel}:{_sha_file(child)}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


class CollectorOperabilityRetentionPulseTests(unittest.TestCase):
    def test_vertical_packet_pulse_retention_preserves_science(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        remote = load_config_v1_1(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rdp = root / "observation_rdp"
            rdp.mkdir(parents=True)
            store = ObservationScheduleStore(root / "ops.sqlite")
            activation_id = _activate(store, schedule)

            # Aged COMPLETED discovery call with large decoded body.
            old_req = "1" * 64
            store.start_call(
                request_sha256=old_req,
                call_occurrence_id="OCC-OLD",
                attempt_id="ATT-OLD",
                primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                payload={},
                clock=OLD,
            )
            big_rows = [{"id": f"m{i}", "liquidity": "1000"} for i in range(200)]
            store.complete_call(
                request_sha256=old_req,
                call_occurrence_id="OCC-OLD",
                attempt_id="ATT-OLD",
                payload={
                    "status": "OBSERVED",
                    "http_class": HTTP_CLASS_OK,
                    "response_sha256": "e" * 64,
                    "rows": big_rows,
                },
                clock=OLD,
            )
            # Scientific-terminal due referencing the old request.
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": "MintOld11111111111111111111111111111111111",
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "OBSERVED",
                    "due_at": render_utc(OLD),
                    "deadline_at": render_utc(OLD + timedelta(minutes=5)),
                    "request_sha256": old_req,
                    "payload": {"status": "OBSERVED"},
                },
                clock=OLD,
            )

            # Recent COMPLETED call — must not compact.
            recent_req = "2" * 64
            store.start_call(
                request_sha256=recent_req,
                call_occurrence_id="OCC-RECENT",
                attempt_id="ATT-RECENT",
                primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                payload={},
                clock=RECENT,
            )
            store.complete_call(
                request_sha256=recent_req,
                call_occurrence_id="OCC-RECENT",
                attempt_id="ATT-RECENT",
                payload={
                    "status": "OBSERVED",
                    "http_class": HTTP_CLASS_OK,
                    "response_sha256": "f" * 64,
                    "rows": [{"id": "recent"}],
                },
                clock=RECENT,
            )

            # In-flight STARTED — must not compact.
            inflight_req = "3" * 64
            store.start_call(
                request_sha256=inflight_req,
                call_occurrence_id="OCC-FLY",
                attempt_id="ATT-FLY",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={},
                clock=RECENT,
            )

            # Aged poll slot body.
            store.save_poll_slot(
                poll_slot_id="POLL-OLD",
                request_sha256=old_req,
                payload={"rows": big_rows},
                clock=OLD,
            )

            # Immutable scientific RDP + publish marker + sealable live source.
            snap = _snapshot_for_week(0, coverage="COVERED")
            write_observation_rdp_source(rdp, snap)
            manifest_dir = rdp / "datasets" / "manifests"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            (manifest_dir / "ds-test.published").write_text("ok\n", encoding="utf-8")
            science_file = rdp / "datasets" / "parquet" / "ds-test" / "observations.parquet"
            science_file.parent.mkdir(parents=True, exist_ok=True)
            science_file.write_bytes(b"PARQUET-FIXTURE-BYTES-NOT-REAL")
            science_before = _sha_file(science_file)
            rdp_before = _sha_tree(rdp)

            release_root = root / "releases"
            cohort = cohort_id_for_admission(
                datetime(2026, 1, 5, 12, tzinfo=UTC),
                starts_at=CAMPAIGN_STARTS,
                stops_admitting_at=CAMPAIGN_STOPS,
            )
            assert cohort is not None
            sealed = seal_live_cohort(
                observation_rdp_root=rdp,
                cohort_id=cohort,
                release_root=release_root,
                as_of=datetime(2026, 1, 20, tzinfo=UTC),
            )
            release_manifest = release_root / RELEASE_MANIFEST_NAME
            self.assertEqual(sealed["release_id"], json.loads(release_manifest.read_text(encoding="utf-8"))["release_id"])
            release_before = _sha_file(release_manifest)

            # Storage history spanning 24h for growth projection.
            hist = root / "local" / "factory_v1" / "collector_storage_history.jsonl"
            hist.parent.mkdir(parents=True, exist_ok=True)
            hist.write_text(
                json.dumps(
                    {
                        "observed_at": render_utc(NOW - timedelta(hours=25)),
                        "disk_used_pct": 40,
                        "sqlite_bytes": 1000,
                        "rdp_bytes": 2000,
                    },
                    sort_keys=True,
                )
                + "\n"
                + json.dumps(
                    {
                        "observed_at": render_utc(NOW - timedelta(hours=1)),
                        "disk_used_pct": 41,
                        "sqlite_bytes": 1100,
                        "rdp_bytes": 2100,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            packet = build_collector_operational_packet(
                root=root,
                store=store,
                now=NOW,
                deploy_git_sha=GIT_SHA,
                period_seconds=60,
                observation_rdp=rdp,
                remote_config=remote,
                environ={},
                scientific_rdp_root=release_root,
            )
            self.assertEqual(packet["deploy_git_sha"], GIT_SHA)
            self.assertNotEqual(packet["filesystem_disk_used_pct"], None)
            self.assertIn("health_classes", packet)
            self.assertEqual(
                packet["raw_retention_substrate"],
                "DECODED_CANONICAL_PROVIDER_JSON_IN_CALL_LEDGER_NOT_BYTE_IDENTICAL_HTTP",
            )
            # Unavailable backup must not silently become healthy.
            self.assertEqual(packet["last_backup_at"], UNKNOWN)
            self.assertIn("BACKUP_DEGRADED", packet["health_classes"])
            self.assertEqual(packet["collector_verdict"], "ACTION_REQUIRED")

            text = render_daily_owner_pulse(packet)
            self.assertIn("FACTORY / DAILY", text)
            self.assertIn("Collector:", text)
            self.assertIn("Storage:", text)
            self.assertIn("Owner action:", text)
            self.assertNotIn("Owner action:\nNONE", text)

            dry = run_daily_owner_pulse(
                root=root,
                store=store,
                mode="dry-run",
                now=NOW,
                deploy_git_sha=GIT_SHA,
                observation_rdp=rdp,
                remote_config=remote,
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "must-not-be-read",
                    "FACTORY_TELEGRAM_CHAT_ID": "must-not-be-read",
                    "JUPITER_FREE_API_KEY": "must-not-be-read",
                },
            )
            self.assertEqual(dry["network_calls"], 0)
            self.assertEqual(dry["credential_value_reads"], 0)
            self.assertEqual(dry["jupiter_credentials_read"], 0)
            self.assertEqual(dry["on_calendar_utc"], DAILY_PULSE_ON_CALENDAR)

            sent: list[tuple[str, str, str]] = []

            def _transport(token: str, chat_id: str, body: str) -> None:
                sent.append((token, chat_id, body))

            emitted = run_daily_owner_pulse(
                root=root,
                store=store,
                mode="emit",
                now=NOW,
                deploy_git_sha=GIT_SHA,
                observation_rdp=rdp,
                remote_config=remote,
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "pulse-token",
                    "FACTORY_TELEGRAM_CHAT_ID": "42",
                    "JUPITER_FREE_API_KEY": "jupiter-must-not-be-read",
                },
                transport=_transport,
            )
            self.assertTrue(emitted["delivery"]["delivered"])
            self.assertEqual(emitted["jupiter_credentials_read"], 0)
            self.assertEqual(sent[0][0], "pulse-token")
            self.assertIn("FACTORY / DAILY", sent[0][2])

            status = apply_retention(
                store, now=NOW, raw_retention_days=31, dry_run=True
            )
            self.assertEqual(status["mode"], "dry-run")
            self.assertGreaterEqual(status["eligible_call_compactions"], 1)
            self.assertIn("OCC-OLD", status["eligible_call_ids"])
            self.assertNotIn("OCC-RECENT", status["eligible_call_ids"])
            self.assertNotIn("OCC-FLY", status["eligible_call_ids"])

            applied = apply_retention(
                store, now=NOW, raw_retention_days=31, dry_run=False
            )
            self.assertEqual(applied["mode"], "apply")
            self.assertGreaterEqual(applied["applied_call_compactions"], 1)

            old_payload = store.call_payload("OCC-OLD")
            assert old_payload is not None
            self.assertEqual(old_payload.get("raw_payload_retention"), COMPACTION_MARKER)
            self.assertNotIn("rows", old_payload)
            self.assertEqual(old_payload.get("response_sha256"), "e" * 64)
            self.assertEqual(store.call_state("OCC-OLD"), "COMPLETED")
            # Compaction must not rewrite updated_at into the 24h window.
            old_row = [
                c for c in store.list_calls() if c["call_occurrence_id"] == "OCC-OLD"
            ][0]
            self.assertEqual(old_row["updated_at"], render_utc(OLD))

            recent_payload = store.call_payload("OCC-RECENT")
            assert recent_payload is not None
            self.assertIn("rows", recent_payload)
            self.assertEqual(store.call_state("OCC-FLY"), "STARTED")

            packet_after = build_collector_operational_packet(
                root=root,
                store=store,
                now=NOW,
                deploy_git_sha=GIT_SHA,
                observation_rdp=rdp,
                remote_config=remote,
                environ={},
                scientific_rdp_root=release_root,
            )
            # Aged compacted call must not inflate 24h provider/observation counts.
            self.assertEqual(packet_after["observations_24h"], 1)

            # Scientific bytes unchanged; release unchanged.
            self.assertEqual(_sha_file(science_file), science_before)
            self.assertEqual(_sha_tree(rdp), rdp_before)
            self.assertEqual(_sha_file(release_manifest), release_before)

            # Idempotent second apply.
            again = apply_retention(
                store, now=NOW, raw_retention_days=31, dry_run=False
            )
            self.assertEqual(again["applied_call_compactions"], 0)

            # Rebuild collector/release packet still works.
            packet2 = build_collector_operational_packet(
                root=root,
                store=store,
                now=NOW,
                deploy_git_sha=GIT_SHA,
                observation_rdp=rdp,
                remote_config=remote,
                environ={},
                scientific_rdp_root=release_root,
            )
            self.assertEqual(packet2["schedule_sha256"], schedule["schedule_sha256"])
            self.assertIn("FACTORY / DAILY", render_daily_owner_pulse(packet2))
            store.close()

    def test_zero_eligible_is_not_provider_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                packet = build_collector_operational_packet(
                    root=Path(tmp),
                    store=store,
                    now=NOW,
                    remote_config=load_config_v1_1(ROOT),
                    environ={},
                )
                self.assertNotIn("PROVIDER_FAILED", packet["health_classes"])
                self.assertNotIn("PROVIDER_AUTH_FAILED", packet["health_classes"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
