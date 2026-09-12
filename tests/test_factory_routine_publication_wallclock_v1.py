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

from solana_alpha_lab.factory.hot90_archive import (
    package_closed_day_archive,
    list_closed_day_relative_paths,
)
from solana_alpha_lab.factory.hot90_closed_day_loop import (
    prune_stale_operational_caches,
)
from solana_alpha_lab.factory.members_snapshot_delta import (
    MembersDeltaError,
    append_delta_publication,
    operational_latest_cache_bytes,
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

    def test_poisoned_operational_db_with_intact_meta_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i) for i in range(30)],
            )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            db_path = unit_dir / _OPERATIONAL_LATEST_DB
            # Tamper durable bytes while leaving meta untouched.
            raw = bytearray(db_path.read_bytes())
            raw[-17] = (raw[-17] + 1) % 256
            db_path.write_bytes(bytes(raw))
            reset_fingerprint_work()
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-d1",
                rows=[_member(i, tag="P" if i == 1 else "A") for i in range(30)],
            )
            self.assertGreaterEqual(
                publication_stage_stats()["operational_latest_misses"], 1
            )
            self.assertEqual(publication_stage_stats()["operational_latest_hits"], 0)

    def test_coordinated_meta_db_rebind_falls_back_to_reconstruct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i) for i in range(25)],
            )
            # Build a foreign cache with matching seq/count but different members.
            foreign = data_root / "foreign"
            foreign.mkdir()
            write_snapshot_unit(
                foreign,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i, tag="X") for i in range(25)],
            )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            foreign_dir = foreign / "datasets/members_snapshot_plus_delta/20260912"
            meta = json.loads(
                (unit_dir / _OPERATIONAL_LATEST_META).read_text(encoding="utf-8")
            )
            # Swap DB bytes from foreign population; keep unit-tail fingerprint in meta
            # but recompute members_db_sha256 so file-bind alone would accept.
            import hashlib

            foreign_db = (foreign_dir / _OPERATIONAL_LATEST_DB).read_bytes()
            (unit_dir / _OPERATIONAL_LATEST_DB).write_bytes(foreign_db)
            meta["members_db_sha256"] = hashlib.sha256(foreign_db).hexdigest()
            (unit_dir / _OPERATIONAL_LATEST_META).write_text(
                json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            reset_fingerprint_work()
            unit = append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-d1",
                rows=[_member(i, tag="Y" if i == 2 else "A") for i in range(25)],
            )
            # Hit attempted then fingerprint mismatch → reconstruct path.
            self.assertGreaterEqual(
                publication_stage_stats()["reconstruct_calls_hot"], 1
            )
            reconstructed = reconstruct_publication(data_root, unit, "dataset-d1")
            self.assertEqual(
                next(r for r in reconstructed if r["typed_values"]["idx"] == 2)[
                    "typed_values"
                ]["tag"],
                "Y",
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

    def test_history_depth_100_warm_hot_path_does_not_scale(self) -> None:
        """Warm append at depth>=100 must not scale with history depth."""

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
            depth = 100
            for d in range(1, depth + 1):
                append_delta_publication(
                    data_root,
                    utc_day="20260912",
                    dataset_manifest_id=f"dataset-h{d:03d}",
                    rows=[
                        _member(i, tag=f"D{d}" if i == (d % n) else "A")
                        for i in range(n)
                    ],
                )
            reset_fingerprint_work()
            t0 = time.perf_counter()
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-hot100",
                rows=[_member(i, tag="HOT" if i == 13 else "A") for i in range(n)],
            )
            wall = time.perf_counter() - t0
            stats = publication_stage_stats()
            self.assertGreaterEqual(stats["operational_latest_hits"], 1)
            self.assertEqual(stats["reconstruct_calls_hot"], 0)
            self.assertEqual(stats["full_population_passes"], 1)
            # Warm hot path must be bounded, not scaling with 100-deep history.
            self.assertLess(wall, 2.0)
            self.assertLess(wall, 5.0 * 0.8)  # far below even the shallow baseline margin
            unit = json.loads((data_root / "datasets/members_snapshot_plus_delta/20260912/unit.json").read_text(encoding="utf-8"))
            self.assertEqual(len(unit["publications"]), depth + 2)
            reconstructed = reconstruct_publication(
                data_root, unit, "dataset-hot100"
            )
            self.assertEqual(
                next(
                    r for r in reconstructed if r["typed_values"]["idx"] == 13
                )["typed_values"]["tag"],
                "HOT",
            )
            # The depth-5 proof still reconstructs losslessly on the same unit.
            deep = reconstruct_publication(data_root, unit, "dataset-h050")
            self.assertEqual(
                next(
                    r for r in deep if r["typed_values"]["idx"] == 50 % n
                )["typed_values"]["tag"],
                f"D{50}",
            )

    def test_cache_miss_fallback_correct_at_depth_60(self) -> None:
        """Corrupt cache at non-trivial depth falls back to replay and stays correct."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            n = 200
            depth = 60
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i) for i in range(n)],
            )
            for d in range(1, depth + 1):
                append_delta_publication(
                    data_root,
                    utc_day="20260912",
                    dataset_manifest_id=f"dataset-f{d:03d}",
                    rows=[
                        _member(i, tag=f"F{d}" if i == (d % n) else "A")
                        for i in range(n)
                    ],
                )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            # Corrupt the durable cache so the next append must fall back to
            # full replay of 60 deltas and still publish scientifically correct
            # state. Cold fallback is allowed to be slow; it must be correct.
            (unit_dir / _OPERATIONAL_LATEST_META).write_text("{bad", encoding="utf-8")
            reset_fingerprint_work()
            t0 = time.perf_counter()
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-after-fallback",
                rows=[_member(i, tag="FB" if i == 9 else "A") for i in range(n)],
            )
            fallback_wall = time.perf_counter() - t0
            stats = publication_stage_stats()
            self.assertGreaterEqual(stats["operational_latest_misses"], 1)
            self.assertGreaterEqual(stats["reconstruct_calls_hot"], 1)
            unit = json.loads((unit_dir / "unit.json").read_text(encoding="utf-8"))
            reconstructed = reconstruct_publication(
                data_root, unit, "dataset-after-fallback"
            )
            self.assertEqual(len(reconstructed), n)
            self.assertEqual(
                next(
                    r for r in reconstructed if r["typed_values"]["idx"] == 9
                )["typed_values"]["tag"],
                "FB",
            )
            # Prior depth states remain exact after the fallback append.
            deep = reconstruct_publication(data_root, unit, "dataset-f030")
            self.assertEqual(
                next(
                    r for r in deep if r["typed_values"]["idx"] == 30 % n
                )["typed_values"]["tag"],
                "F30",
            )
            # Cold fallback contract: correct, not fast; explicit bound recorded.
            print(
                json.dumps(
                    {
                        "schema": "smial.factory-routine-publication-wallclock-cold-fallback",
                        "depth": depth,
                        "fallback_wall_s": round(fallback_wall, 3),
                        "contract": "cold fallback must be correct, not fast; fast path is the warm cache",
                    },
                    sort_keys=True,
                )
            )
            self.assertLess(fallback_wall, 60.0)

    def test_history_depth_100_cold_fallback_cost_bounded(self) -> None:
        """Cold (cache-miss) append at depth=100 stays correct at a loose bound.

        Companion to test_history_depth_100_warm_hot_path_does_not_scale: same
        depth, but the operational cache is corrupted so the hot append must
        replay the full 100-delta history. The cold path may be slower than the
        warm path; it must remain correct and bounded, proving warm-cache speed
        is the optimization, not a correctness dependency.
        """

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            n = 200
            depth = 100
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i) for i in range(n)],
            )
            for d in range(1, depth + 1):
                append_delta_publication(
                    data_root,
                    utc_day="20260912",
                    dataset_manifest_id=f"dataset-c{d:03d}",
                    rows=[
                        _member(i, tag=f"C{d}" if i == (d % n) else "A")
                        for i in range(n)
                    ],
                )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            # Corrupt the durable cache: next append cold-replays depth 100.
            (unit_dir / _OPERATIONAL_LATEST_META).write_text("{bad", encoding="utf-8")
            reset_fingerprint_work()
            t0 = time.perf_counter()
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-cold100",
                rows=[_member(i, tag="COLD" if i == 17 else "A") for i in range(n)],
            )
            cold_wall = time.perf_counter() - t0
            stats = publication_stage_stats()
            self.assertGreaterEqual(stats["operational_latest_misses"], 1)
            self.assertGreaterEqual(stats["reconstruct_calls_hot"], 1)
            # Loose bound: correctness gate, not a performance gate. The warm
            # depth-100 proof carries the performance claim (<2s); cold replay
            # of 100 deltas on 200 members must still be far under any envelope.
            self.assertLess(cold_wall, 30.0)
            unit = json.loads((unit_dir / "unit.json").read_text(encoding="utf-8"))
            self.assertEqual(len(unit["publications"]), depth + 2)
            reconstructed = reconstruct_publication(
                data_root, unit, "dataset-cold100"
            )
            self.assertEqual(len(reconstructed), n)
            self.assertEqual(
                next(
                    r for r in reconstructed if r["typed_values"]["idx"] == 17
                )["typed_values"]["tag"],
                "COLD",
            )
            # An early depth state is still exact after the cold append.
            deep = reconstruct_publication(data_root, unit, "dataset-c001")
            self.assertEqual(
                next(
                    r for r in deep if r["typed_values"]["idx"] == 1 % n
                )["typed_values"]["tag"],
                "C1",
            )
            print(
                json.dumps(
                    {
                        "schema": "smial.factory-routine-publication-wallclock-cold-fallback-100",
                        "depth": depth,
                        "cold_wall_s": round(cold_wall, 3),
                        "contract": "cold replay at depth 100 is correct and bounded; warm cache is the speed claim",
                    },
                    sort_keys=True,
                )
            )

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

    def test_archive_inventory_ignores_operational_cache_state(self) -> None:
        """Cache present/absent/stale/corrupt must not change archive inventory."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            write_snapshot_unit(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-anchor",
                rows=[_member(i) for i in range(30)],
            )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260912"
            append_delta_publication(
                data_root,
                utc_day="20260912",
                dataset_manifest_id="dataset-d1",
                rows=[_member(i, tag="B" if i == 1 else "A") for i in range(30)],
            )
            self.assertTrue((unit_dir / _OPERATIONAL_LATEST_DB).is_file())

            baseline = list_closed_day_relative_paths(data_root, "20260912")
            packed_with_cache = package_closed_day_archive(
                data_root,
                utc_day="20260912",
                relative_paths=baseline,
                dest_dir=root / "a-cache",
            )
            self.assertNotIn(
                f"datasets/members_snapshot_plus_delta/20260912/{_OPERATIONAL_LATEST_DB}",
                set(baseline),
            )
            self.assertNotIn(
                f"datasets/members_snapshot_plus_delta/20260912/{_OPERATIONAL_LATEST_META}",
                set(baseline),
            )
            cache_bytes = operational_latest_cache_bytes(unit_dir)
            self.assertGreater(cache_bytes["cache_db_bytes"], 0)

            # Absent cache: same inventory.
            _invalidate_operational_latest(unit_dir)
            absent = list_closed_day_relative_paths(data_root, "20260912")
            self.assertEqual(absent, baseline)
            packed_absent = package_closed_day_archive(
                data_root,
                utc_day="20260912",
                relative_paths=absent,
                dest_dir=root / "a-absent",
            )

            # Stale cache (bytes from an older generation): same inventory.
            (unit_dir / _OPERATIONAL_LATEST_DB).write_bytes(
                (root / "a-cache" / packed_with_cache["filename"]).read_bytes()[:1024]
            )
            stale = list_closed_day_relative_paths(data_root, "20260912")
            self.assertEqual(stale, baseline)

            # Corrupt cache (garbage meta): same inventory.
            (unit_dir / _OPERATIONAL_LATEST_DB).write_bytes(b"garbage")
            (unit_dir / _OPERATIONAL_LATEST_META).write_text("{bad", encoding="utf-8")
            corrupt = list_closed_day_relative_paths(data_root, "20260912")
            self.assertEqual(corrupt, baseline)
            packed_corrupt = package_closed_day_archive(
                data_root,
                utc_day="20260912",
                relative_paths=corrupt,
                dest_dir=root / "a-corrupt",
            )
            self.assertEqual(
                packed_absent["inventory_sha256"], packed_corrupt["inventory_sha256"]
            )
            self.assertEqual(
                packed_with_cache["inventory_sha256"], packed_corrupt["inventory_sha256"]
            )

            # Scientific reconstruction still works with cache absent then corrupt.
            unit = json.loads((unit_dir / "unit.json").read_text(encoding="utf-8"))
            _invalidate_operational_latest(unit_dir)
            got = reconstruct_publication(data_root, unit, "dataset-d1")
            self.assertEqual(len(got), 30)
            self.assertEqual(
                next(r for r in got if r["typed_values"]["idx"] == 1)["typed_values"]["tag"],
                "B",
            )

    def test_prune_stale_operational_caches_bounds_retention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            for day in ("20260908", "20260909", "20260910"):
                unit_dir = (
                    rdp / "datasets/members_snapshot_plus_delta" / day
                )
                unit_dir.mkdir(parents=True)
                (unit_dir / _OPERATIONAL_LATEST_DB).write_bytes(b"x" * 32)
                (unit_dir / _OPERATIONAL_LATEST_META).write_text("{}", encoding="utf-8")
            report = prune_stale_operational_caches(root, today="20260912")
            # No receipts anywhere → nothing verified → open-day guard alone
            # applies: days < today without verified receipts are pruned.
            self.assertEqual(report["pruned"], ["20260908", "20260909", "20260910"])
            self.assertEqual(
                report["kept_days"], []
            )
            for day in ("20260908", "20260909", "20260910"):
                unit_dir = rdp / "datasets/members_snapshot_plus_delta" / day
                self.assertFalse((unit_dir / _OPERATIONAL_LATEST_DB).is_file())
            # Current day cache is never pruned.
            today_dir = rdp / "datasets/members_snapshot_plus_delta/20260912"
            today_dir.mkdir(parents=True)
            (today_dir / _OPERATIONAL_LATEST_DB).write_bytes(b"y" * 32)
            (today_dir / _OPERATIONAL_LATEST_META).write_text("{}", encoding="utf-8")
            report2 = prune_stale_operational_caches(root, today="20260912")
            self.assertEqual(report2["pruned"], [])
            self.assertTrue((today_dir / _OPERATIONAL_LATEST_DB).is_file())


if __name__ == "__main__":
    unittest.main()
