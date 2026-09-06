"""Compact SNAPSHOT_PLUS_DELTA economy, mixed-chain replay, and signal repair."""

from __future__ import annotations

import hashlib
import json
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

from solana_alpha_lab.factory.collector_operational_packet import (  # noqa: E402
    UNKNOWN,
    _growth_and_projection,
)
from solana_alpha_lab.factory.hot90_activation import (  # noqa: E402
    STAGE_WRITE_ONLY_SHADOW,
    load_hot90_activation,
)
from solana_alpha_lab.factory.hot90_archive import (  # noqa: E402
    hydrate_closed_day_archive,
    list_closed_day_relative_paths,
    package_closed_day_archive,
    reconstruct_members_from_hydrated,
)
from solana_alpha_lab.factory.members_snapshot_delta import (  # noqa: E402
    DELTA_SCHEMA,
    DELTA_SCHEMA_VERSION_V1,
    DELTA_SCHEMA_VERSION_V2,
    MembersDeltaError,
    _write_layout_sidecar,
    _write_unit,
    append_delta_publication,
    diff_member_snapshots,
    fingerprint_work,
    load_member_rows_for_location,
    persist_delta_payload,
    reconstruct_publication,
    reset_fingerprint_work,
    snapshot_fingerprint,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.operability_watch import classify_incidents  # noqa: E402

GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 2, 0, 10, tzinfo=UTC)


def _member(entity_id: str, state: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "schedule_sha256": "a" * 64,
        "activation_id": "ACT-1",
        "entity_id": entity_id,
        "membership_state": state,
        "event_time": "2026-09-02T00:05:00Z",
        "first_reliable_available_at": "2026-09-02T00:10:00Z",
        "field_values": [
            {
                "field_id": "F1",
                "value_kind": "STRING",
                "typed_value_or_null": extra.get("value"),
                "state": "OBSERVED" if extra.get("value") is not None else "MISSING",
                "missing_reason": None if extra.get("value") is not None else "UNAVAILABLE",
            }
        ],
    }
    row.update({key: value for key, value in extra.items() if key != "value"})
    return row


def _universe(n: int, *, prefix: str = "E") -> list[dict[str, object]]:
    return [_member(f"{prefix}{i:05d}", "INCLUDED", value=str(i)) for i in range(n)]


def _append_v1_fat(
    data_root: Path,
    *,
    utc_day: str,
    dataset_manifest_id: str,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    unit_dir = data_root / "datasets" / "members_snapshot_plus_delta" / utc_day
    unit_path = unit_dir / "unit.json"
    unit = json.loads(unit_path.read_text(encoding="utf-8"))
    previous_id = str(unit["publications"][-1]["dataset_manifest_id"])
    reconstructed = reconstruct_publication(data_root, unit, previous_id)
    previous_fp = str(unit["publications"][-1]["snapshot_fingerprint"])
    delta = diff_member_snapshots(reconstructed, rows, include_unchanged=True)
    current_fp = snapshot_fingerprint(rows)
    payload = {
        "schema": DELTA_SCHEMA,
        "schema_version": DELTA_SCHEMA_VERSION_V1,
        "dataset_manifest_id": dataset_manifest_id,
        "previous_dataset_manifest_id": previous_id,
        "previous_fingerprint": previous_fp,
        **delta,
    }
    seq = int(unit["publications"][-1]["seq"]) + 1
    rel = (
        f"datasets/members_snapshot_plus_delta/{utc_day}/deltas/"
        f"{seq:04d}-{dataset_manifest_id}/members.parquet"
    )
    path = data_root / rel
    digest = persist_delta_payload(path, payload)
    unit["publications"].append(
        {
            "seq": seq,
            "dataset_manifest_id": dataset_manifest_id,
            "kind": "delta",
            "rel": rel.replace("\\", "/"),
            "sha256": digest,
            "row_count": len(rows),
            "snapshot_fingerprint": current_fp,
        }
    )
    _write_unit(unit_path, unit)
    _write_layout_sidecar(path, unit, dataset_manifest_id)
    return unit


def _read_delta_json(path: Path) -> dict[str, object]:
    import pyarrow.parquet as pq

    rows = pq.read_table(path).to_pylist()
    return json.loads(str(rows[0]["delta_json"]))


class CompactDeltaEconomyTests(unittest.TestCase):
    def test_new_delta_omits_unchanged_and_is_schema_v2(self) -> None:
        base = _universe(40)
        nxt = base + [_member("NEW", "INCLUDED", value="n")]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            write_snapshot_unit(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-a", rows=base
            )
            unit = append_delta_publication(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-b", rows=nxt
            )
            payload = _read_delta_json(data_root / unit["publications"][-1]["rel"])
            self.assertEqual(payload["schema_version"], DELTA_SCHEMA_VERSION_V2)
            self.assertNotIn("unchanged", payload)
            self.assertEqual(payload["counts"]["added"], 1)
            self.assertEqual(payload["counts"]["changed"], 0)
            self.assertEqual(payload["counts"]["removed"], 0)
            self.assertEqual(payload["current_fingerprint"], snapshot_fingerprint(nxt))

    def test_delta_bytes_scale_with_change_set_not_universe(self) -> None:
        def _v1_v2_sizes(n: int) -> tuple[int, int, int, int]:
            base = _universe(n)
            nxt = base + [_member("NEW", "INCLUDED", value="n")]
            with tempfile.TemporaryDirectory() as tmp:
                data_root = Path(tmp)
                write_snapshot_unit(
                    data_root, utc_day="20260906", dataset_manifest_id="dataset-a", rows=base
                )
                fat = _append_v1_fat(
                    data_root,
                    utc_day="20260906",
                    dataset_manifest_id="dataset-fat",
                    rows=nxt,
                )
                fat_path = data_root / fat["publications"][-1]["rel"]
                v1 = fat_path.stat().st_size
                j1 = len(json.dumps(_read_delta_json(fat_path), separators=(",", ":")))
            with tempfile.TemporaryDirectory() as tmp:
                data_root = Path(tmp)
                write_snapshot_unit(
                    data_root, utc_day="20260906", dataset_manifest_id="dataset-a", rows=base
                )
                compact = append_delta_publication(
                    data_root, utc_day="20260906", dataset_manifest_id="dataset-b", rows=nxt
                )
                compact_path = data_root / compact["publications"][-1]["rel"]
                v2 = compact_path.stat().st_size
                j2 = len(json.dumps(_read_delta_json(compact_path), separators=(",", ":")))
            return v1, v2, j1, j2

        v1_small, v2_small, j1_small, j2_small = _v1_v2_sizes(400)
        v1_large, v2_large, j1_large, j2_large = _v1_v2_sizes(1600)
        self.assertLess(j2_small * 8, j1_small)
        self.assertLess(j2_large * 20, j1_large)
        self.assertGreater(j1_large, j1_small * 2)
        self.assertLess(j2_large, j2_small * 3)
        self.assertGreater(v1_large, v1_small * 2)
        self.assertLess(v2_large, v2_small * 3)

    def test_replay_work_is_not_universe_times_chain(self) -> None:
        n_members = 120
        n_deltas = 80
        rows = _universe(n_members)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            unit = write_snapshot_unit(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-000", rows=rows
            )
            for index in range(1, n_deltas + 1):
                rows = rows + [_member(f"N{index:04d}", "INCLUDED", value=str(index))]
                unit = append_delta_publication(
                    data_root,
                    utc_day="20260906",
                    dataset_manifest_id=f"dataset-{index:04d}",
                    rows=rows,
                )
            last_id = str(unit["publications"][-1]["dataset_manifest_id"])
            expected = snapshot_fingerprint(rows)
            reset_fingerprint_work()
            got = reconstruct_publication(data_root, unit, last_id)
            work = fingerprint_work()
            self.assertEqual(snapshot_fingerprint(got), expected)
            self.assertLessEqual(work["snapshot_fingerprint"], 2)
            self.assertLess(
                work["snapshot_fingerprint"],
                n_deltas,
                "replay hashed whole snapshots once per delta",
            )


class MixedChainAndIntegrityTests(unittest.TestCase):
    def test_mixed_old_fat_then_new_compact_reconstructs(self) -> None:
        first = _universe(30)
        second = first + [_member("N1", "INCLUDED", value="1")]
        third = [
            row if row["entity_id"] != "E00001" else _member("E00001", "EXCLUDED", value="1")
            for row in second
        ] + [_member("N2", "INCLUDED", value="2")]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            write_snapshot_unit(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-a", rows=first
            )
            unit = _append_v1_fat(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-b", rows=second
            )
            unit = append_delta_publication(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-c", rows=third
            )
            self.assertEqual(
                _read_delta_json(data_root / unit["publications"][1]["rel"])["schema_version"],
                DELTA_SCHEMA_VERSION_V1,
            )
            self.assertEqual(
                _read_delta_json(data_root / unit["publications"][2]["rel"])["schema_version"],
                DELTA_SCHEMA_VERSION_V2,
            )
            self.assertEqual(
                snapshot_fingerprint(reconstruct_publication(data_root, unit, "dataset-a")),
                snapshot_fingerprint(first),
            )
            self.assertEqual(
                snapshot_fingerprint(reconstruct_publication(data_root, unit, "dataset-b")),
                snapshot_fingerprint(second),
            )
            self.assertEqual(
                snapshot_fingerprint(reconstruct_publication(data_root, unit, "dataset-c")),
                snapshot_fingerprint(third),
            )

    def test_v1_unchanged_list_may_be_ignored_when_target_fingerprint_holds(self) -> None:
        first = _universe(20)
        second = first + [_member("N1", "INCLUDED", value="1")]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            write_snapshot_unit(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-a", rows=first
            )
            unit = _append_v1_fat(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-b", rows=second
            )
            rel = unit["publications"][-1]["rel"]
            path = data_root / rel
            payload = _read_delta_json(path)
            payload["unchanged"][0]["fingerprint"] = "0" * 64
            persist_delta_payload(path, payload)
            unit["publications"][-1]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            got = reconstruct_publication(data_root, unit, "dataset-b")
            self.assertEqual(snapshot_fingerprint(got), snapshot_fingerprint(second))

    def test_corrupt_missing_and_reordered_delta_fail_closed(self) -> None:
        first = [_member("A", "INCLUDED", value="x")]
        second = [_member("A", "INCLUDED", value="x"), _member("B", "INCLUDED", value="y")]
        third = [_member("B", "INCLUDED", value="y"), _member("C", "INCLUDED", value="z")]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            write_snapshot_unit(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-a", rows=first
            )
            unit = append_delta_publication(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-b", rows=second
            )
            unit = append_delta_publication(
                data_root, utc_day="20260906", dataset_manifest_id="dataset-c", rows=third
            )
            mutated = json.loads(json.dumps(unit))
            path = data_root / mutated["publications"][1]["rel"]
            payload = _read_delta_json(path)
            payload["added"][0]["membership_state"] = "EXCLUDED"
            persist_delta_payload(path, payload)
            with self.assertRaises(MembersDeltaError) as hashed:
                reconstruct_publication(data_root, mutated, "dataset-b")
            self.assertEqual(str(hashed.exception), "DELTA_HASH_MISMATCH")
            mutated["publications"][1]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(MembersDeltaError) as replay:
                reconstruct_publication(data_root, mutated, "dataset-b")
            self.assertEqual(str(replay.exception), "DELTA_REPLAY_MISMATCH")
            reordered = json.loads(json.dumps(unit))
            reordered["publications"][1], reordered["publications"][2] = (
                reordered["publications"][2],
                reordered["publications"][1],
            )
            with self.assertRaises(MembersDeltaError) as seq:
                reconstruct_publication(data_root, reordered, "dataset-c")
            self.assertIn(str(seq.exception), {"DELTA_SEQUENCE_INVALID", "DELTA_HASH_MISMATCH"})
            missing = json.loads(json.dumps(unit))
            (data_root / missing["publications"][1]["rel"]).unlink()
            with self.assertRaises(MembersDeltaError) as gone:
                reconstruct_publication(data_root, missing, "dataset-b")
            self.assertEqual(str(gone.exception), "DELTA_MISSING")

    def test_archive_hydrate_mixed_chain(self) -> None:
        first = _universe(12)
        second = first + [_member("N1", "INCLUDED", value="1")]
        third = second + [_member("N2", "INCLUDED", value="2")]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "rdp"
            source.mkdir()
            write_snapshot_unit(
                source, utc_day="20260906", dataset_manifest_id="dataset-a", rows=first
            )
            _append_v1_fat(
                source, utc_day="20260906", dataset_manifest_id="dataset-b", rows=second
            )
            unit = append_delta_publication(
                source, utc_day="20260906", dataset_manifest_id="dataset-c", rows=third
            )
            relatives = list_closed_day_relative_paths(source, "20260906")
            packaged = package_closed_day_archive(
                source, utc_day="20260906", relative_paths=relatives, dest_dir=Path(tmp) / "arch"
            )
            isolated = Path(tmp) / "hydrated"
            live = Path(tmp) / "live"
            live.mkdir()
            hydrate_closed_day_archive(
                packaged["path"], isolated_data_root=isolated, live_data_root=live
            )
            loc = str(unit["publications"][-1]["rel"])
            got = reconstruct_members_from_hydrated(isolated, loc)
            self.assertEqual(snapshot_fingerprint(got), snapshot_fingerprint(third))


class PublicationConsumerTests(unittest.TestCase):
    def test_publish_batch_compact_delta_roundtrip(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        digest = schedule["schedule_sha256"]
        shadow = {
            "activation_stage": STAGE_WRITE_ONLY_SHADOW,
            "production_compaction_enabled": False,
            "production_eviction_enabled": False,
            "drive_writes_enabled": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with patch(
                "solana_alpha_lab.factory.observation_panel_publisher.load_hot90_activation",
                return_value=load_hot90_activation(ROOT, override=shadow),
            ):
                first = publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                    members=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintA",
                            "membership_state": "INCLUDED",
                        }
                    ],
                    observations=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintA",
                            "point_id": "X300",
                            "state": "OBSERVED",
                            "event_time": "2026-09-02T00:05:00Z",
                            "first_reliable_available_at": "2026-09-02T00:10:00Z",
                        }
                    ],
                )
                second = publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=datetime(2026, 9, 2, 0, 20, tzinfo=UTC),
                    producer_git_sha=GIT_SHA,
                    members=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintA",
                            "membership_state": "EXCLUDED",
                        },
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintB",
                            "membership_state": "INCLUDED",
                        },
                    ],
                    observations=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintB",
                            "point_id": "X300",
                            "state": "OBSERVED",
                            "event_time": "2026-09-02T00:15:00Z",
                            "first_reliable_available_at": "2026-09-02T00:20:00Z",
                        }
                    ],
                )
            unit = json.loads(
                (
                    data_root
                    / "datasets"
                    / "members_snapshot_plus_delta"
                    / "20260902"
                    / "unit.json"
                ).read_text(encoding="utf-8")
            )
            loc = str(unit["publications"][-1]["rel"])
            loaded = load_member_rows_for_location(data_root, loc)
            by_entity = {row["entity_id"]: row for row in loaded}
            self.assertEqual(by_entity["MintA"]["membership_state"], "EXCLUDED")
            self.assertEqual(by_entity["MintB"]["membership_state"], "INCLUDED")
            payload = _read_delta_json(data_root / loc)
            self.assertEqual(payload["schema_version"], DELTA_SCHEMA_VERSION_V2)
            self.assertNotIn("unchanged", payload)
            self.assertEqual(len(unit["publications"]), 2)
            self.assertEqual(
                first["dataset_manifest_id"],
                unit["publications"][0]["dataset_manifest_id"],
            )
            self.assertEqual(
                second["dataset_manifest_id"],
                unit["publications"][1]["dataset_manifest_id"],
            )


class OperabilitySignalAndGrowthTests(unittest.TestCase):
    def test_data_stale_is_one_incident_not_collector_stalled(self) -> None:
        found = classify_incidents({"health_classes": ["PROCESS_OK", "DATA_STALE"]})
        self.assertIn("SOURCE_DATA_STALE", found)
        self.assertNotIn("COLLECTOR_STALLED", found)

    def test_growth_normalizes_long_span_and_unknown_short_span(self) -> None:
        now = datetime(2026, 9, 6, 16, 0, tzinfo=UTC)
        long_history = [
            {
                "observed_at": (now - timedelta(hours=31)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "disk_used_pct": 8,
                "sqlite_bytes": 1000,
                "rdp_bytes": 2000,
            },
            {
                "observed_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "disk_used_pct": 8,
                "sqlite_bytes": 2000,
                "rdp_bytes": 4100,
            },
        ]
        _disk, data, _proj = _growth_and_projection(
            long_history, now=now, current_disk_pct=8
        )
        self.assertEqual(data, int(round(3100 * (24.0 / 31.0))))
        exact = [
            {
                "observed_at": (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "disk_used_pct": 8,
                "sqlite_bytes": 1000,
                "rdp_bytes": 2000,
            },
            {
                "observed_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "disk_used_pct": 8,
                "sqlite_bytes": 2000,
                "rdp_bytes": 4100,
            },
        ]
        _disk, data24, _proj = _growth_and_projection(
            exact, now=now, current_disk_pct=8
        )
        self.assertEqual(data24, 3100)
        short = [
            {
                "observed_at": (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "disk_used_pct": 8,
                "sqlite_bytes": 1000,
                "rdp_bytes": 2000,
            },
            {
                "observed_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "disk_used_pct": 8,
                "sqlite_bytes": 2000,
                "rdp_bytes": 4100,
            },
        ]
        _disk, data_short, _proj = _growth_and_projection(
            short, now=now, current_disk_pct=8
        )
        self.assertEqual(data_short, UNKNOWN)


if __name__ == "__main__":
    unittest.main()
