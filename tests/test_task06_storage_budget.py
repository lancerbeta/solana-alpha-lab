from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage import (  # noqa: E402
    StorageBudgetAlert,
    StorageBudgetContractError,
    StorageBudgetExceededError,
    StorageBudgetPolicy,
    StorageBudgetStatus,
    StorageInventoryError,
    WriteDisposition,
    evaluate_storage_budget,
    write_budgeted_raw_event_partition,
)
import test_task06_parquet_store as parquet_fixture  # noqa: E402

FREE_BYTES = 1_000_000
LOGICAL_LOCATION = parquet_fixture.LOGICAL_LOCATION


class Task06StorageBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parquet_fixture.Task06ParquetStoreTests.setUpClass()

    def setUp(self) -> None:
        self.parquet = parquet_fixture.Task06ParquetStoreTests()
        self.disk_usage = mock.patch(
            "solana_alpha_lab.storage.budget.shutil.disk_usage",
            return_value=SimpleNamespace(free=FREE_BYTES),
        )
        self.disk_usage.start()

    def tearDown(self) -> None:
        self.disk_usage.stop()

    @staticmethod
    def policy(
        *,
        max_partition_bytes: int = 20_000,
        max_dataset_bytes: int = 100_000,
        min_free_bytes: int = 100_000,
        warning_threshold_bps: int = 8000,
        forecast_partition_count: int = 2,
    ) -> StorageBudgetPolicy:
        return StorageBudgetPolicy(
            max_partition_bytes=max_partition_bytes,
            max_dataset_bytes=max_dataset_bytes,
            min_free_bytes=min_free_bytes,
            warning_threshold_bps=warning_threshold_bps,
            forecast_partition_count=forecast_partition_count,
        )

    def write(
        self,
        root: Path,
        *,
        logical_location: str = LOGICAL_LOCATION,
        partition_id: str = "date=2026-07-24/hour=12",
        policy: StorageBudgetPolicy | None = None,
    ):
        kwargs = self.parquet.write_kwargs(root)
        kwargs["logical_location"] = logical_location
        kwargs["partition_id"] = partition_id
        return write_budgeted_raw_event_partition(
            **kwargs,
            budget_policy=policy or self.policy(),
        )

    @staticmethod
    def physical_path(
        root: Path,
        logical_location: str = LOGICAL_LOCATION,
    ) -> Path:
        return root.joinpath(*logical_location.split("/"))

    def test_policy_rejects_invalid_integer_limits(self) -> None:
        invalid_cases = (
            (
                {"max_partition_bytes": True},
                "max_partition_bytes_must_be_positive_int",
            ),
            (
                {"max_dataset_bytes": 0},
                "max_dataset_bytes_must_be_positive_int",
            ),
            (
                {"min_free_bytes": -1},
                "min_free_bytes_must_be_non_negative_int",
            ),
            (
                {"warning_threshold_bps": 10_000},
                "warning_threshold_bps_must_be_below_10000",
            ),
            (
                {"forecast_partition_count": 0},
                "forecast_partition_count_must_be_positive_int",
            ),
            (
                {
                    "max_partition_bytes": 101,
                    "max_dataset_bytes": 100,
                },
                "max_partition_bytes_exceeds_dataset_budget",
            ),
        )
        defaults = {
            "max_partition_bytes": 20_000,
            "max_dataset_bytes": 100_000,
            "min_free_bytes": 100_000,
            "warning_threshold_bps": 8000,
            "forecast_partition_count": 2,
        }
        for changes, message in invalid_cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                StorageBudgetContractError,
                message,
            ):
                StorageBudgetPolicy(**(defaults | changes))

    def test_budgeted_write_returns_sanitized_post_write_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_allowed_"
        ) as temporary:
            root = Path(temporary)
            result = self.write(root)
            path = self.physical_path(root)
            data = path.read_bytes()

        snapshot = result.budget_snapshot
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(result.disposition, WriteDisposition.CREATED)
        self.assertEqual(snapshot.status, StorageBudgetStatus.OK)
        self.assertEqual(snapshot.dataset_logical_root, "raw-api-events")
        self.assertEqual(snapshot.existing_partition_count, 1)
        self.assertEqual(snapshot.existing_dataset_bytes, len(data))
        self.assertEqual(snapshot.incoming_partition_bytes, len(data))
        self.assertEqual(snapshot.incremental_write_bytes, 0)
        self.assertEqual(snapshot.projected_dataset_bytes, len(data))
        self.assertNotIn(str(root), repr(snapshot))

    def test_identical_replay_is_not_charged_twice(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_replay_"
        ) as temporary:
            root = Path(temporary)
            first = self.write(root)
            second = self.write(root)
            files = list(root.rglob("*.parquet"))

        assert first.budget_snapshot is not None
        assert second.budget_snapshot is not None
        self.assertEqual(
            second.disposition,
            WriteDisposition.REPLAY_IDENTICAL,
        )
        self.assertEqual(len(files), 1)
        self.assertEqual(
            second.budget_snapshot.existing_dataset_bytes,
            first.file_size_bytes,
        )
        self.assertEqual(
            second.budget_snapshot.incremental_write_bytes,
            0,
        )

    def test_partition_limit_rejects_before_filesystem_write(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_partition_stop_"
        ) as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(
                StorageBudgetExceededError,
                "partition_byte_budget_exceeded",
            ):
                self.write(
                    root,
                    policy=self.policy(max_partition_bytes=1),
                )
            remaining = list(root.iterdir())

        self.assertEqual(remaining, [])

    def test_dataset_limit_rejects_second_piece_without_side_effect(
        self,
    ) -> None:
        second_location = (
            "raw-api-events/date=2026-07-24/hour=13/"
            "part-000.parquet"
        )
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_dataset_stop_"
        ) as temporary:
            root = Path(temporary)
            first = self.write(root)
            limit = first.file_size_bytes + 1
            with self.assertRaisesRegex(
                StorageBudgetExceededError,
                "dataset_byte_budget_exceeded",
            ):
                self.write(
                    root,
                    logical_location=second_location,
                    partition_id="date=2026-07-24/hour=13",
                    policy=self.policy(
                        max_partition_bytes=limit,
                        max_dataset_bytes=limit,
                    ),
                )
            files = list(root.rglob("*.parquet"))
            second_parent = self.physical_path(
                root,
                second_location,
            ).parent

        self.assertEqual(len(files), 1)
        self.assertFalse(second_parent.exists())

    def test_filesystem_reserve_rejects_before_write(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_disk_stop_"
        ) as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(
                StorageBudgetExceededError,
                "filesystem_free_space_reserve_exceeded",
            ):
                self.write(
                    root,
                    policy=self.policy(
                        min_free_bytes=FREE_BYTES - 1,
                    ),
                )
            remaining = list(root.iterdir())

        self.assertEqual(remaining, [])

    def test_warning_forecasts_dataset_and_disk_growth(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_warning_"
        ) as temporary:
            root = Path(temporary)
            baseline = self.write(root)
            size = baseline.file_size_bytes
            policy = self.policy(
                max_partition_bytes=size,
                max_dataset_bytes=size * 2,
                min_free_bytes=FREE_BYTES - size * 3 + 1,
                warning_threshold_bps=4000,
                forecast_partition_count=3,
            )
            result = self.write(root, policy=policy)

        snapshot = result.budget_snapshot
        assert snapshot is not None
        self.assertEqual(snapshot.status, StorageBudgetStatus.WARNING)
        self.assertEqual(
            snapshot.alerts,
            (
                StorageBudgetAlert.DATASET_UTILIZATION_WARNING,
                StorageBudgetAlert.FORECAST_DATASET_BUDGET_EXCEEDED,
                StorageBudgetAlert.FORECAST_FILESYSTEM_RESERVE_EXCEEDED,
            ),
        )

    def test_unexpected_inventory_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_inventory_"
        ) as temporary:
            root = Path(temporary)
            unexpected = root / "raw-api-events" / "stale.tmp"
            unexpected.parent.mkdir()
            unexpected.write_bytes(b"stale")
            with self.assertRaisesRegex(
                StorageInventoryError,
                "inventory_unexpected_file",
            ):
                self.write(root)
            self.assertFalse(self.physical_path(root).exists())

    def test_dataset_root_symlink_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_symlink_"
        ) as temporary:
            root = Path(temporary)
            linked = root / "raw-api-events"
            original_is_symlink = Path.is_symlink

            def simulated_is_symlink(path: Path) -> bool:
                if path == linked:
                    return True
                return original_is_symlink(path)

            with mock.patch.object(
                Path,
                "is_symlink",
                simulated_is_symlink,
            ), self.assertRaisesRegex(
                StorageInventoryError,
                "dataset_root_symlink_forbidden",
            ):
                self.write(root)
            remaining = list(root.iterdir())

        self.assertEqual(remaining, [])

    def test_direct_evaluation_rejects_unsafe_logical_locations(
        self,
    ) -> None:
        invalid_locations = (
            "raw-api-events//part.parquet",
            "raw-api-events/../part.parquet",
            "raw-api-events/part.txt",
            "C:/raw-api-events/part.parquet",
            "raw-api-events/part?.parquet",
        )
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_unsafe_path_"
        ) as temporary:
            root = Path(temporary)
            for logical_location in invalid_locations:
                with self.subTest(
                    logical_location=logical_location
                ), self.assertRaisesRegex(
                    StorageBudgetContractError,
                    "logical_location_invalid",
                ):
                    evaluate_storage_budget(
                        root=root,
                        logical_location=logical_location,
                        incoming_file_sha256="a" * 64,
                        incoming_partition_bytes=1,
                        policy=self.policy(),
                    )

    def test_conflicting_target_hash_fails_before_publication(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_conflict_"
        ) as temporary:
            root = Path(temporary)
            target = self.physical_path(root)
            target.parent.mkdir(parents=True)
            target.write_bytes(b"different")
            original = target.read_bytes()
            with self.assertRaisesRegex(
                StorageInventoryError,
                "immutable_target_conflict",
            ):
                self.write(root)
            after = target.read_bytes()

        self.assertEqual(after, original)

    def test_post_write_budget_failure_rolls_back_new_piece(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_postcheck_"
        ) as temporary:
            root = Path(temporary)
            real_evaluator = evaluate_storage_budget
            calls = 0

            def fail_second_check(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise StorageBudgetExceededError(
                        "synthetic_post_write_drift"
                    )
                return real_evaluator(**kwargs)

            with mock.patch(
                "solana_alpha_lab.storage.parquet_store."
                "evaluate_storage_budget",
                side_effect=fail_second_check,
            ), self.assertRaisesRegex(
                StorageBudgetExceededError,
                "synthetic_post_write_drift",
            ):
                self.write(root)
            remaining = list(root.rglob("*"))

        self.assertEqual(calls, 2)
        self.assertEqual(remaining, [])

    def test_direct_evaluation_binds_existing_hash_and_size(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_direct_"
        ) as temporary:
            root = Path(temporary)
            target = self.physical_path(root)
            target.parent.mkdir(parents=True)
            target.write_bytes(b"parquet-placeholder")
            data = target.read_bytes()
            snapshot = evaluate_storage_budget(
                root=root,
                logical_location=LOGICAL_LOCATION,
                incoming_file_sha256=hashlib.sha256(data).hexdigest(),
                incoming_partition_bytes=len(data),
                policy=self.policy(),
            )

        self.assertEqual(snapshot.existing_partition_count, 1)
        self.assertEqual(snapshot.incremental_write_bytes, 0)
        self.assertEqual(snapshot.projected_dataset_bytes, len(data))

    def test_snapshot_is_json_serializable_without_physical_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_budget_json_"
        ) as temporary:
            root = Path(temporary)
            result = self.write(root)
            snapshot = result.budget_snapshot
            assert snapshot is not None
            payload = json.dumps(
                {
                    field: (
                        [str(item) for item in value]
                        if field == "alerts"
                        else str(value)
                        if field == "status"
                        else value
                    )
                    for field, value in (
                        (name, getattr(snapshot, name))
                        for name in snapshot.__dataclass_fields__
                    )
                },
                sort_keys=True,
            )

        self.assertNotIn(str(root), payload)
        self.assertIn('"dataset_logical_root": "raw-api-events"', payload)


if __name__ == "__main__":
    unittest.main()
