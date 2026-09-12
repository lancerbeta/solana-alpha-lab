"""FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1 — parity, cache, telemetry, envelope."""

from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from solana_alpha_lab.factory.members_snapshot_delta import (
    MembersDeltaError,
    append_delta_publication,
    publication_stage_stats,
    reconstruct_publication,
    reset_fingerprint_work,
    write_snapshot_unit,
    _OPERATIONAL_LATEST_DB,
    _OPERATIONAL_LATEST_META,
    _diff_sqlite_members_to_ops,
    _invalidate_operational_latest,
    _spill_member_sequence,
)


def _member(i: int, *, tag: str = "A") -> dict:
    mint = f"M{i:06d}{'x' * 36}"
    return {
        "entity_id": mint,
        "schedule_sha256": "a" * 64,
        "activation_id": "ACT-WALLCLOCK",
        "membership_state": "ADMITTED",
        "typed_values": {"tag": tag, "idx": i},
        "admitted_at": "2026-09-12T16:25:11.282126Z",
    }


class RoutinePublicationWallclockV1Tests(unittest.TestCase):
    def test_merge_diff_parity_with_add_change_remove(self) -> None:
        prev = [_member(i) for i in range(50)]
        curr = [_member(i, tag="B" if i in {1, 2} else "A") for i in range(1, 52)]
        prev_spill, prev_conn = _spill_member_sequence(prev)
        curr_spill, curr_conn = _spill_member_sequence(curr)
        try:
            ops_spill, ops_conn, counts = _diff_sqlite_members_to_ops(prev_conn, curr_conn)
            try:
                self.assertEqual(counts["removed"], 1)
                self.assertEqual(counts["changed"], 2)
                self.assertEqual(counts["added"], 2)
                ops = list(
                    ops_conn.execute(
                        "SELECT op, entity_id FROM delta_ops ORDER BY seq"
                    )
                )
                self.assertEqual(
                    {(o, e) for o, e in ops if o == "removed"},
                    {("removed", prev[0]["entity_id"])},
                )
                self.assertEqual(
                    {(o, e) for o, e in ops if o == "changed"},
                    {
                        ("changed", prev[1]["entity_id"]),
                        ("changed", prev[2]["entity_id"]),
                    },
                )
                self.assertEqual(
                    {(o, e) for o, e in ops if o == "added"},
                    {
                        ("added", curr[-2]["entity_id"]),
                        ("added", curr[-1]["entity_id"]),
                    },
                )
            finally:
                ops_conn.close()
                ops_spill.unlink(missing_ok=True)
        finally:
            prev_conn.close()
            curr_conn.close()
            prev_spill.unlink(missing_ok=True)
            curr_spill.unlink(missing_ok=True)

    def test_operational_latest_cache_hit_and_corrupt_miss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            rows = [_member(i) for i in range(40)]
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=rows,
            )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            self.assertTrue((unit_dir / _OPERATIONAL_LATEST_DB).is_file())
            self.assertTrue((unit_dir / _OPERATIONAL_LATEST_META).is_file())

            reset_fingerprint_work()
            buf = io.StringIO()
            next_rows = [_member(i, tag="B" if i == 3 else "A") for i in range(40)]
            prev_timing = os.environ.get("SMIAL_PUBLICATION_STAGE_TIMING")
            os.environ["SMIAL_PUBLICATION_STAGE_TIMING"] = "1"
            try:
                with redirect_stdout(buf):
                    unit = append_delta_publication(
                        data_root,
                        utc_day="20260912",
                        dataset_manifest_id="dataset-d1",
                        rows=next_rows,
                    )
            finally:
                if prev_timing is None:
                    os.environ.pop("SMIAL_PUBLICATION_STAGE_TIMING", None)
                else:
                    os.environ["SMIAL_PUBLICATION_STAGE_TIMING"] = prev_timing
            stats = publication_stage_stats()
            self.assertGreaterEqual(stats["operational_latest_hits"], 1)
            markers = [
                json.loads(line)
                for line in buf.getvalue().splitlines()
                if line.strip()
            ]
            self.assertTrue(
                any(m.get("stage") == "PUBLICATION_APPEND_END" for m in markers)
            )
            self.assertTrue(
                any(m.get("cache_hit") is True for m in markers if "cache_hit" in m)
            )

            reconstructed = reconstruct_publication(data_root, unit, "dataset-d1")
            self.assertEqual(len(reconstructed), 40)
            self.assertEqual(
                next(
                    r for r in reconstructed if r["typed_values"]["idx"] == 3
                )["typed_values"]["tag"],
                "B",
            )

            (unit_dir / _OPERATIONAL_LATEST_META).write_text("{not-json", encoding="utf-8")
            reset_fingerprint_work()
            third = [
                _member(i, tag="C" if i == 4 else ("B" if i == 3 else "A"))
                for i in range(40)
            ]
            unit2 = append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-d2",
                rows=third,
            )
            self.assertEqual(publication_stage_stats()["operational_latest_misses"], 1)
            again = reconstruct_publication(data_root, unit2, "dataset-d2")
            self.assertEqual(
                next(r for r in again if r["typed_values"]["idx"] == 4)["typed_values"][
                    "tag"
                ],
                "C",
            )

    def test_cache_invalidate_helper_forces_reconstruct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            rows = [_member(i) for i in range(20)]
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=rows,
            )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            _invalidate_operational_latest(unit_dir)
            reset_fingerprint_work()
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-d1",
                rows=[_member(i, tag="Z" if i == 0 else "A") for i in range(20)],
            )
            self.assertGreaterEqual(
                publication_stage_stats()["operational_latest_misses"], 1
            )
            self.assertGreaterEqual(
                publication_stage_stats()["reconstruct_calls_hot"], 1
            )

    def test_history_depth_cache_bounds_second_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            n = 200
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i) for i in range(n)],
            )
            for d in range(1, 6):
                append_delta_publication(
                    data_root,
                    utc_day="20260912",
                    dataset_manifest_id=f"dataset-h{d}",
                    rows=[
                        _member(i, tag=f"D{d}" if i == d else "A") for i in range(n)
                    ],
                )
            reset_fingerprint_work()
            t0 = time.perf_counter()
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-hot",
                rows=[_member(i, tag="HOT" if i == 7 else "A") for i in range(n)],
            )
            wall = time.perf_counter() - t0
            self.assertGreaterEqual(
                publication_stage_stats()["operational_latest_hits"], 1
            )
            self.assertLess(wall, 2.0)

    def test_missing_anchor_still_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(MembersDeltaError):
                append_delta_publication(
                    root,
                    utc_day="20260912",
                    dataset_manifest_id="x",
                    rows=[_member(0)],
                )


if __name__ == "__main__":
    unittest.main()
