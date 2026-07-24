from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage import (  # noqa: E402
    AtomicPublicationError,
    ParquetConflictError,
    ParquetContractError,
    ParquetIntegrityError,
    WriteDisposition,
    build_dataset_manifest,
    build_raw_api_event,
    canonical_raw_event_rows_bytes,
    verify_dataset_manifest,
    verify_raw_event_partition,
    write_raw_event_partition,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task06"
    / "raw_envelope_v1.json"
)
LOGICAL_LOCATION = (
    "raw-api-events/date=2026-07-24/hour=12/part-000.parquet"
)


class Task06ParquetStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.base_time = datetime.fromisoformat(
            cls.fixture["timestamps"]["observed_at"].replace(
                "Z",
                "+00:00",
            )
        )

    def events(self) -> tuple[object, ...]:
        first = build_raw_api_event(
            source="synthetic.provider",
            source_version="fixture-1",
            endpoint_or_method="GET /v1/items",
            request_identity=self.fixture["request_identity"],
            response_body=self.fixture["success_body"],
            response_status="SUCCESS",
            error_class=None,
            event_time=self.base_time - timedelta(minutes=2),
            observed_at=self.base_time,
            available_to_strategy_at=self.base_time
            + timedelta(seconds=2),
            ingested_at=self.base_time + timedelta(seconds=1),
            first_reliable_available_at=self.base_time
            + timedelta(seconds=2),
            provider_version="fixture-1",
            schema_version="1.0",
            protocol_version="fixture-1",
            quality_flags="synthetic_fixture",
        )
        timeout = build_raw_api_event(
            source="synthetic.provider",
            source_version="fixture-1",
            endpoint_or_method="GET /v1/items",
            request_identity={"request": "timeout"},
            response_body=b"",
            response_status="TIMEOUT",
            error_class="SyntheticTimeout",
            event_time=None,
            observed_at=self.base_time + timedelta(minutes=1),
            available_to_strategy_at=self.base_time
            + timedelta(minutes=1, seconds=2),
            ingested_at=self.base_time
            + timedelta(minutes=1, seconds=1),
            first_reliable_available_at=self.base_time
            + timedelta(minutes=1, seconds=2),
            provider_version="fixture-1",
            schema_version="1.0",
            protocol_version="fixture-1",
            quality_flags="synthetic_fixture",
        )
        revision = build_raw_api_event(
            source="synthetic.provider",
            source_version="fixture-1",
            endpoint_or_method="GET /v1/items",
            request_identity=self.fixture["request_identity"],
            response_body={"result": {"slot": 124}},
            response_status="SUCCESS",
            error_class=None,
            event_time=self.base_time - timedelta(minutes=2),
            observed_at=self.base_time + timedelta(minutes=2),
            available_to_strategy_at=self.base_time
            + timedelta(minutes=2, seconds=2),
            ingested_at=self.base_time
            + timedelta(minutes=2, seconds=1),
            first_reliable_available_at=self.base_time
            + timedelta(minutes=2, seconds=2),
            provider_version="fixture-1",
            schema_version="1.0",
            protocol_version="fixture-1",
            revision_number=2,
            revision_of=first.raw_event_id,
            quality_flags="synthetic_revision",
        )
        return first, timeout, revision

    def write_kwargs(
        self,
        root: Path,
        *,
        events: tuple[object, ...] | None = None,
    ) -> dict[str, object]:
        return {
            "root": root,
            "dataset_id": "raw-api-events",
            "dataset_version": "2026-07-24.1",
            "partition_id": "date=2026-07-24/hour=12",
            "logical_location": LOGICAL_LOCATION,
            "events": events if events is not None else self.events(),
            "created_at": self.base_time + timedelta(hours=1),
            "first_reliable_available_at": self.base_time
            + timedelta(hours=1, seconds=1),
        }

    @staticmethod
    def physical_path(root: Path) -> Path:
        return root.joinpath(*LOGICAL_LOCATION.split("/"))

    def test_round_trip_binds_exact_bytes_rows_schema_and_manifest(
        self,
    ) -> None:
        expected_events = tuple(
            sorted(self.events(), key=lambda item: item.raw_event_id)
        )
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_roundtrip_"
        ) as temporary:
            root = Path(temporary)
            result = write_raw_event_partition(
                **self.write_kwargs(root)
            )
            path = self.physical_path(root)
            observed = verify_raw_event_partition(
                root=root,
                manifest=result.manifest,
            )
            data = path.read_bytes()
            table = pq.ParquetFile(path).read()

        self.assertEqual(result.disposition, WriteDisposition.CREATED)
        self.assertEqual(observed, expected_events)
        self.assertEqual(result.file_size_bytes, len(data))
        self.assertEqual(
            result.manifest.file_sha256,
            hashlib.sha256(data).hexdigest(),
        )
        self.assertEqual(
            result.manifest.content_sha256,
            hashlib.sha256(
                canonical_raw_event_rows_bytes(expected_events)
            ).hexdigest(),
        )
        self.assertEqual(result.manifest.row_count, 3)
        self.assertEqual(table.num_rows, 3)
        self.assertEqual(
            table.schema.metadata[b"smial.contract"],
            b"RawApiEvent",
        )
        self.assertIn(b"", table["redacted_body"].to_pylist())

    def test_reversed_input_produces_identical_bytes_and_manifest(
        self,
    ) -> None:
        events = self.events()
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_order_a_"
        ) as first_temp, tempfile.TemporaryDirectory(
            prefix="task06_parquet_order_b_"
        ) as second_temp:
            first_root = Path(first_temp)
            second_root = Path(second_temp)
            first = write_raw_event_partition(
                **self.write_kwargs(first_root, events=events)
            )
            second = write_raw_event_partition(
                **self.write_kwargs(
                    second_root,
                    events=tuple(reversed(events)),
                )
            )
            first_bytes = self.physical_path(first_root).read_bytes()
            second_bytes = self.physical_path(second_root).read_bytes()

        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(first.manifest, second.manifest)

    def test_identical_replay_is_noop_without_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_replay_"
        ) as temporary:
            root = Path(temporary)
            first = write_raw_event_partition(
                **self.write_kwargs(root)
            )
            path = self.physical_path(root)
            original = path.read_bytes()
            second = write_raw_event_partition(
                **self.write_kwargs(root)
            )
            after = path.read_bytes()
            remaining = sorted(
                item.name for item in path.parent.iterdir()
            )

        self.assertEqual(first.disposition, WriteDisposition.CREATED)
        self.assertEqual(
            second.disposition,
            WriteDisposition.REPLAY_IDENTICAL,
        )
        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(remaining, [path.name])
        self.assertEqual(after, original)

    def test_conflicting_replay_never_replaces_existing_bytes(self) -> None:
        events = self.events()
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_conflict_"
        ) as temporary:
            root = Path(temporary)
            write_raw_event_partition(**self.write_kwargs(root))
            path = self.physical_path(root)
            original = path.read_bytes()
            changed = list(events)
            changed[-1] = build_raw_api_event(
                source="synthetic.provider",
                source_version="fixture-1",
                endpoint_or_method="GET /v1/items",
                request_identity={"request": "changed"},
                response_body={"result": {"slot": 999}},
                response_status="SUCCESS",
                error_class=None,
                event_time=self.base_time,
                observed_at=self.base_time + timedelta(minutes=3),
                available_to_strategy_at=self.base_time
                + timedelta(minutes=3, seconds=2),
                ingested_at=self.base_time
                + timedelta(minutes=3, seconds=1),
                first_reliable_available_at=self.base_time
                + timedelta(minutes=3, seconds=2),
                provider_version="fixture-1",
                schema_version="1.0",
                protocol_version="fixture-1",
                quality_flags="synthetic_conflict",
            )
            with self.assertRaisesRegex(
                ParquetConflictError,
                "immutable_target_conflict",
            ):
                write_raw_event_partition(
                    **self.write_kwargs(
                        root,
                        events=tuple(changed),
                    )
                )
            after = path.read_bytes()

        self.assertEqual(after, original)

    def test_atomic_failure_removes_temp_file_and_empty_parents(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_atomic_failure_"
        ) as temporary:
            root = Path(temporary)
            with mock.patch(
                "solana_alpha_lab.storage.parquet_store.os.link",
                side_effect=OSError("synthetic atomic failure"),
            ):
                with self.assertRaisesRegex(
                    AtomicPublicationError,
                    "atomic_no_clobber_publication_failed",
                ):
                    write_raw_event_partition(
                        **self.write_kwargs(root)
                    )
            remaining = list(root.rglob("*"))

        self.assertEqual(remaining, [])

    def test_tampered_file_fails_hash_verification(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_tamper_"
        ) as temporary:
            root = Path(temporary)
            result = write_raw_event_partition(
                **self.write_kwargs(root)
            )
            path = self.physical_path(root)
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaisesRegex(
                ParquetIntegrityError,
                "parquet_file_hash_mismatch",
            ):
                verify_raw_event_partition(
                    root=root,
                    manifest=result.manifest,
                )

    def test_empty_duplicate_and_tampered_events_fail_before_write(
        self,
    ) -> None:
        events = self.events()
        invalid_cases = (
            ((), "events_must_not_be_empty"),
            ((events[0], events[0]), "duplicate_raw_event_id"),
            (
                (
                    events[0].model_copy(
                        update={"redacted_body": b"tampered"}
                    ),
                ),
                "raw_event_integrity_invalid",
            ),
        )
        for invalid_events, message in invalid_cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory(
                prefix="task06_parquet_invalid_"
            ) as temporary:
                root = Path(temporary)
                with self.assertRaisesRegex(
                    ParquetContractError,
                    message,
                ):
                    write_raw_event_partition(
                        **self.write_kwargs(
                            root,
                            events=invalid_events,
                        )
                    )
                self.assertEqual(list(root.iterdir()), [])

    def test_nullable_event_time_bounds_are_conservative(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_null_bounds_"
        ) as temporary:
            result = write_raw_event_partition(
                **self.write_kwargs(Path(temporary))
            )

        self.assertIsNone(result.manifest.min_event_time)
        self.assertIsNone(result.manifest.max_event_time)
        self.assertIsNotNone(
            result.manifest.min_available_to_strategy_at
        )
        self.assertIsNotNone(
            result.manifest.max_available_to_strategy_at
        )

    def test_partition_manifest_integrates_with_dataset_root(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_dataset_root_"
        ) as temporary:
            result = write_raw_event_partition(
                **self.write_kwargs(Path(temporary))
            )
        created_at = result.manifest.first_reliable_available_at
        dataset = build_dataset_manifest(
            dataset_id="raw-api-events",
            dataset_version="2026-07-24.1",
            schema_id="raw-api-events-v1",
            schema_sha256="a" * 64,
            generation_task_id="TASK-06",
            generation_run_id="fixture-run-atom4",
            validation_receipt_sha256="b" * 64,
            created_at=created_at,
            first_reliable_available_at=created_at
            + timedelta(microseconds=1),
            partitions=(result.manifest,),
        )
        verify_dataset_manifest(
            dataset,
            partitions=(result.manifest,),
        )
        self.assertEqual(
            dataset.dataset_manifest_id,
            result.manifest.dataset_manifest_id,
        )

    def test_relative_root_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ParquetContractError,
            "root_must_be_absolute",
        ):
            write_raw_event_partition(
                **self.write_kwargs(Path("relative-root"))
            )

    def test_symlink_escape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="task06_parquet_symlink_root_"
        ) as temporary, tempfile.TemporaryDirectory(
            prefix="task06_parquet_symlink_outside_"
        ) as outside_temporary:
            root = Path(temporary)
            outside = Path(outside_temporary)
            linked = root / "raw-api-events"
            original_is_symlink = Path.is_symlink
            original_resolve = Path.resolve

            def simulated_is_symlink(path: Path) -> bool:
                if path == linked:
                    return True
                return original_is_symlink(path)

            def simulated_resolve(
                path: Path,
                *,
                strict: bool = False,
            ) -> Path:
                if path == linked:
                    return original_resolve(outside, strict=True)
                return original_resolve(path, strict=strict)

            with mock.patch.object(
                Path,
                "is_symlink",
                simulated_is_symlink,
            ), mock.patch.object(
                Path,
                "resolve",
                simulated_resolve,
            ):
                with self.assertRaisesRegex(
                    ParquetContractError,
                    "logical_parent_escapes_root",
                ):
                    write_raw_event_partition(
                        **self.write_kwargs(root)
                    )


if __name__ == "__main__":
    unittest.main()
