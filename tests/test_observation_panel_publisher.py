from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    ObservationPanelPublisherError,
    PublicationFault,
    build_panel_snapshot,
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id  # noqa: E402


GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


class ObservationPanelPublisherTests(unittest.TestCase):
    def test_manifest_last_and_canonical_dataset_id(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
                members=[{"schedule_sha256": schedule["schedule_sha256"], "entity_id": "MintA"}],
                observations=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "entity_id": "MintA",
                        "point_id": "X300",
                        "state": "OBSERVED",
                        "event_time": "2026-09-01T00:05:00Z",
                        "first_reliable_available_at": "2026-09-01T00:10:00Z",
                    }
                ],
            )
            self.assertFalse(first["replay"])
            self.assertTrue(first["dataset_manifest_id"].startswith("dataset-"))
            self.assertEqual(len(first["dataset_manifest_id"]), len("dataset-") + 64)
            manifest_path = (
                data_root / "datasets" / "manifests" / f"{first['dataset_manifest_id']}.json"
            )
            published_path = (
                data_root
                / "datasets"
                / "manifests"
                / f"{first['dataset_manifest_id']}.published"
            )
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(published_path.is_file())
            partition = json.loads(
                next(
                    (data_root / "datasets" / "manifests" / "partitions").glob("*.json")
                ).read_text(encoding="utf-8")
            )
            self.assertNotEqual(
                partition["min_event_time"],
                partition["first_reliable_available_at"],
            )
            self.assertEqual(first["min_event_time"], "2026-09-01T00:05:00Z")
            self.assertEqual(first["first_reliable_available_at"], "2026-09-01T00:10:00Z")
            second = publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
                members=[{"schedule_sha256": schedule["schedule_sha256"], "entity_id": "MintA"}],
                observations=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "entity_id": "MintA",
                        "point_id": "X300",
                        "state": "OBSERVED",
                        "event_time": "2026-09-01T00:05:00Z",
                        "first_reliable_available_at": "2026-09-01T00:10:00Z",
                    }
                ],
            )
            self.assertTrue(second["replay"])
            self.assertEqual(second["dataset_manifest_id"], first["dataset_manifest_id"])

    def test_empty_observations_are_forbidden(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaisesRegex(
                ObservationPanelPublisherError, "PARTIAL_DATASET_FORBIDDEN"
            ):
                publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                )

    def test_snapshot_hash_is_canonical(self) -> None:
        snapshot = build_panel_snapshot(
            schedule_sha256="a" * 64,
            availability_cutoff=NOW,
            dataset_manifest_ids=["dataset-" + "b" * 64],
            dataset_fingerprints=["c" * 64],
        )
        again = build_panel_snapshot(
            schedule_sha256="a" * 64,
            availability_cutoff=NOW,
            dataset_manifest_ids=["dataset-" + "b" * 64],
            dataset_fingerprints=["c" * 64],
        )
        self.assertEqual(snapshot["snapshot_sha256"], again["snapshot_sha256"])
        self.assertEqual(
            compute_dataset_manifest_id("observation-panel-abc", "20260901-1-deadbeef"),
            compute_dataset_manifest_id("observation-panel-abc", "20260901-1-deadbeef"),
        )

    def test_publication_faults_repair_to_one_complete_dataset(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        members = [{"schedule_sha256": schedule["schedule_sha256"], "entity_id": "MintA"}]
        observations = [
            {
                "schedule_sha256": schedule["schedule_sha256"],
                "entity_id": "MintA",
                "point_id": "X300",
                "state": "OBSERVED",
                "event_time": "2026-09-01T00:05:00Z",
                "first_reliable_available_at": "2026-09-01T00:10:00Z",
            }
        ]
        for stage in (
            "AFTER_ARTIFACTS",
            "AFTER_ONE_RDP_EVENT",
            "AFTER_MANIFEST",
            "AFTER_MARKER",
        ):
            with tempfile.TemporaryDirectory() as tmp:
                data_root = Path(tmp) / "rdp"
                data_root.mkdir()
                with self.assertRaises(PublicationFault):
                    publish_observation_batch(
                        data_root=data_root,
                        root=ROOT,
                        schedule=schedule,
                        activation_id="ACT-OBS-001",
                        now=NOW,
                        producer_git_sha=GIT_SHA,
                        members=members,
                        observations=observations,
                        fault_after=stage,
                    )
                repaired = publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                    members=members,
                    observations=observations,
                )
                replay = publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                    members=members,
                    observations=observations,
                )
                self.assertTrue(replay["replay"])
                self.assertEqual(replay["dataset_manifest_id"], repaired["dataset_manifest_id"])
                marker = (
                    data_root
                    / "datasets"
                    / "manifests"
                    / f"{repaired['dataset_manifest_id']}.published"
                )
                self.assertTrue(marker.is_file())
                from solana_alpha_lab.factory.research_store import ResearchStore

                kinds = {
                    str(item.record_kind)
                    for item in ResearchStore(data_root).iter_committed_records()
                }
                self.assertIn("OBSERVATION_BATCH", kinds)
                self.assertIn("OBSERVATION_MEMBER_BATCH", kinds)


if __name__ == "__main__":
    unittest.main()
