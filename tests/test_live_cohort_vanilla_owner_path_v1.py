"""Vanilla owner path: identity, bounded plan, incremental import, current Forge view."""

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

from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    enumerate_rdp_datasets,
    enumerate_work,
    reset_enumerate_work,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    LiveCohortReleaseError,
    import_live_cohort,
    seal_live_cohort,
    verify_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.live_cohort_to_forge import synthetic_closed_receipt  # noqa: E402
from solana_alpha_lab.factory.live_cohort_vanilla_path import (  # noqa: E402
    classify_mirror,
    select_next_mature_unimported_cohort,
    unpack_next_live_cohort,
)
from solana_alpha_lab.storage.manifests import (  # noqa: E402
    build_dataset_manifest,
    build_partition_manifest,
    compute_dataset_manifest_id,
)
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    ACTIVATION,
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _snapshot_for_week,
    cohort_id_for_admission,
)

CORPUS_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"


class VanillaOwnerPathTests(unittest.TestCase):
    def test_rollover_does_not_invent_predecessor_successor_window(self) -> None:
        cutover = datetime(2026, 9, 14, 17, 35, 10, 845525, tzinfo=UTC)
        predecessor = {
            "schedule_sha256": "a" * 64,
            "activation_id": "ACT-PREDECESSOR",
            "starts_at": "2026-09-02T11:19:00Z",
            "stops_admitting_at": "2026-09-23T11:19:00Z",
        }
        successor = {
            "schedule_sha256": "b" * 64,
            "activation_id": "ACT-SUCCESSOR",
            "starts_at": "2026-09-14T17:35:10.845525Z",
            "stops_admitting_at": "2026-09-21T17:35:10.845525Z",
        }
        chosen = select_next_mature_unimported_cohort(
            activations=[predecessor, successor],
            rollovers=[
                {
                    "predecessor_schedule_sha256": predecessor["schedule_sha256"],
                    "predecessor_activation_id": predecessor["activation_id"],
                    "cutover_at": "2026-09-14T17:35:10.845525Z",
                }
            ],
            imported_cohort_ids={
                "REL-20260902T111900Z-20260909T111900Z",
                "REL-20260909T111900Z-20260916T111900Z",
            },
            as_of=datetime(2026, 9, 26, tzinfo=UTC),
        )
        assert chosen is not None
        self.assertEqual(chosen["cohort_id"], "REL-20260914T173510Z-20260921T173510Z")
        self.assertEqual(chosen["activation_id"], "ACT-SUCCESSOR")
        self.assertNotEqual(chosen["cohort_id"], "REL-20260916T111900Z-20260923T111900Z")
        self.assertGreaterEqual(cutover, chosen["window_start"])

    def test_unpack_rejects_open_future_before_build(self) -> None:
        receipt = synthetic_closed_receipt(
            schedule_sha256="b" * 64,
            activation_id="ACT-SUCCESSOR",
            cohort_id="REL-20260914T173510Z-20260921T173510Z",
            as_of=datetime(2026, 9, 26, tzinfo=UTC),
            members_total=1,
        )
        receipt["due_states"] = {"OBSERVED": 1}
        receipt["pending_future"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LiveCohortReleaseError) as raised:
                unpack_next_live_cohort(
                    observation_rdp=Path(tmp),
                    data_root=Path(tmp),
                    repo_root=ROOT,
                    activations=[],
                    rollovers=[],
                    closure_receipt=receipt,
                    as_of=datetime(2026, 9, 26, tzinfo=UTC),
                    plan_only=True,
                )
        self.assertEqual(str(raised.exception), "COHORT_PENDING_FUTURE")

    def test_mirror_conflict_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp)
            target = mirror / "datasets" / "keep.parquet"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"local-bytes")
            manifest = {
                "entries": [
                    {
                        "path": "datasets/keep.parquet",
                        "sha256": "ab" * 32,
                        "bytes": 11,
                    }
                ]
            }
            classified = classify_mirror(manifest, mirror)
            self.assertEqual(classified["conflicts"], 1)
            self.assertEqual(classified["status"], "CONFLICT")

    def test_ordinary_append_does_not_rehash_historical_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            first_bytes = 0
            for week in (0, 1):
                obs = base / f"obs-{week}"
                release = base / f"rel-{week}"
                snap = _snapshot_for_week(week, coverage="GAP_SUSPECTED")
                write_observation_rdp_source(obs, snap)
                cohort = cohort_id_for_admission(
                    CAMPAIGN_STARTS + timedelta(days=7 * week, hours=1),
                    starts_at=CAMPAIGN_STARTS,
                    stops_admitting_at=CAMPAIGN_STOPS,
                )
                assert cohort is not None
                as_of = CAMPAIGN_STARTS + timedelta(days=7 * week + 10)
                seal_live_cohort(
                    observation_rdp_root=obs,
                    cohort_id=cohort,
                    release_root=release,
                    sealed_at=as_of,
                    as_of=as_of,
                )
                verify_live_cohort(release)
                imported = import_live_cohort(
                    release_root=release,
                    data_root=data_root,
                    import_time=as_of + timedelta(hours=1),
                )
                self.assertEqual(imported["status"], "IMPORTED")
                self.assertEqual(int(imported["historical_parquet_bytes_hashed"]), 0)
                self.assertGreater(int(imported["new_cohort_parquet_bytes_hashed"]), 0)
                if week == 0:
                    first_bytes = int(imported["new_cohort_parquet_bytes_hashed"])
                else:
                    self.assertNotEqual(
                        int(imported["new_cohort_parquet_bytes_hashed"]),
                        first_bytes + int(imported["new_cohort_parquet_bytes_hashed"]),
                    )
            reset_enumerate_work()
            enumerate_rdp_datasets(data_root, live_corpus_current_only=True)
            current_only_bytes = enumerate_work()["parquet_bytes_hashed"]
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            current = json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )["current_dataset_manifest_id"]
            current_doc = json.loads(
                (data_root / "datasets" / "manifests" / f"{current}.json").read_text(encoding="utf-8")
            )
            for index in range(200):
                blob = b"x" * (32 + index)
                rel = f"datasets/partitions/date=2099-01-01/extra-{index}.parquet"
                dest = data_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                digest = __import__("hashlib").sha256(blob).hexdigest()
                version = f"extra-corpus-{index}"
                part = build_partition_manifest(
                    dataset_id=CORPUS_ID,
                    dataset_version=version,
                    partition_id=f"extra-{index}",
                    logical_location=rel,
                    file_sha256=digest,
                    content_sha256=digest,
                    row_count=1,
                    first_reliable_available_at=CAMPAIGN_STARTS,
                    created_at=CAMPAIGN_STARTS,
                    min_event_time=CAMPAIGN_STARTS,
                    max_event_time=CAMPAIGN_STARTS,
                    min_available_to_strategy_at=CAMPAIGN_STARTS,
                    max_available_to_strategy_at=CAMPAIGN_STARTS,
                )
                part_path = part_dir / f"{part.partition_manifest_id}.json"
                part_path.write_text(part.model_dump_json(), encoding="utf-8")
                dataset = build_dataset_manifest(
                    dataset_id=CORPUS_ID,
                    dataset_version=version,
                    schema_id=current_doc["schema_id"],
                    schema_sha256=current_doc["schema_sha256"],
                    generation_task_id="EXTRA",
                    generation_run_id=f"extra-{index}",
                    validation_receipt_sha256="ab" * 32,
                    first_reliable_available_at=CAMPAIGN_STARTS,
                    created_at=CAMPAIGN_STARTS,
                    partitions=[part],
                )
                manifest_id = compute_dataset_manifest_id(CORPUS_ID, version)
                self.assertEqual(dataset.dataset_manifest_id, manifest_id)
                (data_root / "datasets" / "manifests" / f"{manifest_id}.json").write_text(
                    dataset.model_dump_json(),
                    encoding="utf-8",
                )
            reset_enumerate_work()
            enumerated, _warnings = enumerate_rdp_datasets(
                data_root,
                live_corpus_current_only=True,
            )
            work = enumerate_work()
            visible = [item["dataset_manifest_id"] for item in enumerated if item["dataset_id"] == CORPUS_ID]
            self.assertEqual(visible, [current])
            self.assertGreaterEqual(work["superseded_live_corpus_skipped"], 200)
            self.assertEqual(work["datasets_partition_scanned"], 1)
            self.assertEqual(work["parquet_bytes_hashed"], current_only_bytes)


if __name__ == "__main__":
    unittest.main()
