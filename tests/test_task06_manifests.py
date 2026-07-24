from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage import (  # noqa: E402
    ManifestContractError,
    ManifestIntegrityError,
    build_dataset_manifest,
    build_partition_manifest,
    canonical_manifest_bytes,
    compute_dataset_fingerprint,
    compute_dataset_manifest_id,
    verify_dataset_manifest,
    verify_partition_manifest,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task06"
    / "manifest_identity_v1.json"
)


class Task06ManifestIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def as_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def partition_kwargs(self, index: int) -> dict[str, object]:
        dataset = self.fixture["dataset"]
        partition = self.fixture["partitions"][index]
        return {
            "dataset_id": dataset["dataset_id"],
            "dataset_version": dataset["dataset_version"],
            "partition_id": partition["partition_id"],
            "logical_location": partition["logical_location"],
            "file_sha256": partition["file_sha256"],
            "content_sha256": partition["content_sha256"],
            "row_count": partition["row_count"],
            "min_event_time": self.as_datetime(
                partition["min_event_time"]
            ),
            "max_event_time": self.as_datetime(
                partition["max_event_time"]
            ),
            "min_available_to_strategy_at": self.as_datetime(
                partition["min_available_to_strategy_at"]
            ),
            "max_available_to_strategy_at": self.as_datetime(
                partition["max_available_to_strategy_at"]
            ),
            "created_at": self.as_datetime(partition["created_at"]),
            "first_reliable_available_at": self.as_datetime(
                partition["first_reliable_available_at"]
            ),
        }

    def partitions(self) -> tuple[object, ...]:
        return (
            build_partition_manifest(**self.partition_kwargs(0)),
            build_partition_manifest(**self.partition_kwargs(1)),
        )

    def dataset_kwargs(self) -> dict[str, object]:
        dataset = self.fixture["dataset"]
        return {
            "dataset_id": dataset["dataset_id"],
            "dataset_version": dataset["dataset_version"],
            "schema_id": dataset["schema_id"],
            "schema_sha256": dataset["schema_sha256"],
            "generation_task_id": dataset["generation_task_id"],
            "generation_run_id": dataset["generation_run_id"],
            "validation_receipt_sha256": (
                dataset["validation_receipt_sha256"]
            ),
            "created_at": self.as_datetime(dataset["created_at"]),
            "first_reliable_available_at": self.as_datetime(
                dataset["first_reliable_available_at"]
            ),
        }

    def test_fixture_binds_exact_identity_profile(self) -> None:
        partitions = self.partitions()
        dataset = build_dataset_manifest(
            **self.dataset_kwargs(),
            partitions=partitions,
        )
        expected = self.fixture["expected"]
        self.assertEqual(
            dataset.dataset_manifest_id,
            expected["dataset_manifest_id"],
        )
        self.assertEqual(
            [item.partition_manifest_id for item in partitions],
            expected["partition_manifest_ids"],
        )
        self.assertEqual(
            dataset.dataset_fingerprint,
            expected["dataset_fingerprint"],
        )
        self.assertEqual(
            dataset.content_sha256,
            expected["dataset_content_sha256"],
        )

    def test_dataset_id_is_semantic_and_versioned(self) -> None:
        dataset = self.fixture["dataset"]
        first = compute_dataset_manifest_id(
            dataset["dataset_id"],
            dataset["dataset_version"],
        )
        second = compute_dataset_manifest_id(
            dataset["dataset_id"],
            dataset["dataset_version"],
        )
        changed = compute_dataset_manifest_id(
            dataset["dataset_id"],
            dataset["dataset_version"] + ".next",
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_partition_is_deterministic_and_timezone_normalized(self) -> None:
        kwargs = self.partition_kwargs(0)
        first = build_partition_manifest(**kwargs)
        shifted = dict(kwargs)
        offset = timezone(timedelta(hours=3))
        for name in (
            "min_event_time",
            "max_event_time",
            "min_available_to_strategy_at",
            "max_available_to_strategy_at",
            "created_at",
            "first_reliable_available_at",
        ):
            shifted[name] = kwargs[name].astimezone(offset)
        second = build_partition_manifest(**shifted)
        self.assertEqual(first, second)
        verify_partition_manifest(first)

    def test_fingerprint_is_input_order_independent(self) -> None:
        first, second = self.partitions()
        kwargs = self.dataset_kwargs()
        direct = compute_dataset_fingerprint(
            dataset_id=kwargs["dataset_id"],
            dataset_version=kwargs["dataset_version"],
            schema_id=kwargs["schema_id"],
            schema_sha256=kwargs["schema_sha256"],
            partitions=(first, second),
        )
        reversed_order = compute_dataset_fingerprint(
            dataset_id=kwargs["dataset_id"],
            dataset_version=kwargs["dataset_version"],
            schema_id=kwargs["schema_id"],
            schema_sha256=kwargs["schema_sha256"],
            partitions=(second, first),
        )
        self.assertEqual(direct, reversed_order)

    def test_changed_partition_claim_changes_partition_and_dataset(self) -> None:
        first, second = self.partitions()
        changed_kwargs = self.partition_kwargs(0)
        changed_kwargs["row_count"] = changed_kwargs["row_count"] + 1
        changed = build_partition_manifest(**changed_kwargs)
        self.assertNotEqual(
            first.partition_manifest_id,
            changed.partition_manifest_id,
        )
        kwargs = self.dataset_kwargs()
        baseline = build_dataset_manifest(
            **kwargs,
            partitions=(first, second),
        )
        variant = build_dataset_manifest(
            **kwargs,
            partitions=(changed, second),
        )
        self.assertNotEqual(
            baseline.dataset_fingerprint,
            variant.dataset_fingerprint,
        )
        self.assertNotEqual(
            baseline.content_sha256,
            variant.content_sha256,
        )

    def test_duplicate_partition_identity_and_location_fail_closed(
        self,
    ) -> None:
        first, _ = self.partitions()
        kwargs = self.dataset_kwargs()
        with self.assertRaisesRegex(
            ManifestContractError,
            "duplicate_partition_manifest_id",
        ):
            build_dataset_manifest(
                **kwargs,
                partitions=(first, first),
            )

        changed_kwargs = self.partition_kwargs(1)
        changed_kwargs["logical_location"] = first.logical_location
        same_location = build_partition_manifest(**changed_kwargs)
        with self.assertRaisesRegex(
            ManifestContractError,
            "duplicate_logical_location",
        ):
            build_dataset_manifest(
                **kwargs,
                partitions=(first, same_location),
            )

    def test_partition_parent_mismatch_fails_closed(self) -> None:
        first, second = self.partitions()
        other_kwargs = self.partition_kwargs(1)
        other_kwargs["dataset_version"] = "other-version"
        other_kwargs["partition_id"] = "date=2026-07-24/hour=10"
        other_kwargs["logical_location"] = (
            "raw-api-events/date=2026-07-24/hour=10/part-000.parquet"
        )
        other = build_partition_manifest(**other_kwargs)
        kwargs = self.dataset_kwargs()
        with self.assertRaisesRegex(
            ManifestContractError,
            "partition_parent_mismatch",
        ):
            build_dataset_manifest(
                **kwargs,
                partitions=(first, second, other),
            )

    def test_unsafe_logical_locations_fail_closed(self) -> None:
        unsafe = (
            "/absolute/part.parquet",
            "C:/data/part.parquet",
            r"dataset\part.parquet",
            "https://provider.invalid/part.parquet",
            "dataset/../part.parquet",
            "dataset//part.parquet",
            "dataset/part.json",
        )
        for location in unsafe:
            with self.subTest(location=location):
                kwargs = self.partition_kwargs(0)
                kwargs["logical_location"] = location
                with self.assertRaises(ManifestContractError):
                    build_partition_manifest(**kwargs)

    def test_naive_timestamps_and_invalid_bounds_fail_closed(self) -> None:
        kwargs = self.partition_kwargs(0)
        kwargs["created_at"] = kwargs["created_at"].replace(tzinfo=None)
        with self.assertRaisesRegex(
            ManifestContractError,
            "created_at_must_be_timezone_aware",
        ):
            build_partition_manifest(**kwargs)

        incoherent = self.partition_kwargs(0)
        incoherent["min_event_time"] = None
        with self.assertRaises(ValidationError):
            build_partition_manifest(**incoherent)

    def test_manifest_availability_cannot_be_backdated(self) -> None:
        partition_kwargs = self.partition_kwargs(0)
        partition_kwargs["created_at"] = partition_kwargs[
            "max_available_to_strategy_at"
        ] - timedelta(microseconds=1)
        with self.assertRaisesRegex(
            ManifestContractError,
            "partition_created_before_available_content",
        ):
            build_partition_manifest(**partition_kwargs)

        partitions = self.partitions()
        dataset_kwargs = self.dataset_kwargs()
        dataset_kwargs["created_at"] = (
            partitions[-1].first_reliable_available_at
            - timedelta(microseconds=1)
        )
        dataset_kwargs["first_reliable_available_at"] = partitions[
            -1
        ].first_reliable_available_at
        with self.assertRaisesRegex(
            ManifestContractError,
            "dataset_created_before_partition_reliable",
        ):
            build_dataset_manifest(
                **dataset_kwargs,
                partitions=partitions,
            )

    def test_invalid_hash_and_boolean_row_count_fail_closed(self) -> None:
        invalid_hash = self.partition_kwargs(0)
        invalid_hash["file_sha256"] = "A" * 64
        with self.assertRaisesRegex(
            ManifestContractError,
            "file_sha256_must_be_lowercase_sha256",
        ):
            build_partition_manifest(**invalid_hash)

        invalid_count = self.partition_kwargs(0)
        invalid_count["row_count"] = True
        with self.assertRaisesRegex(
            ManifestContractError,
            "row_count_must_be_non_negative_integer",
        ):
            build_partition_manifest(**invalid_count)

    def test_dataset_verifier_detects_all_root_tampering(self) -> None:
        partitions = self.partitions()
        dataset = build_dataset_manifest(
            **self.dataset_kwargs(),
            partitions=partitions,
        )
        variants = (
            (
                dataset.model_copy(
                    update={"dataset_manifest_id": "dataset-" + ("0" * 64)}
                ),
                "dataset_manifest_id_mismatch",
            ),
            (
                dataset.model_copy(
                    update={"dataset_fingerprint": "0" * 64}
                ),
                "dataset_fingerprint_mismatch",
            ),
            (
                dataset.model_copy(update={"content_sha256": "0" * 64}),
                "dataset_content_hash_mismatch",
            ),
        )
        for variant, message in variants:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    ManifestIntegrityError,
                    message,
                ):
                    verify_dataset_manifest(
                        variant,
                        partitions=partitions,
                    )

    def test_partition_verifier_detects_tampering(self) -> None:
        partition = self.partitions()[0]
        tampered = partition.model_copy(update={"row_count": 999})
        with self.assertRaisesRegex(
            ManifestIntegrityError,
            "partition_manifest_id_mismatch",
        ):
            verify_partition_manifest(tampered)

    def test_receipt_hash_changes_content_not_dataset_fingerprint(
        self,
    ) -> None:
        partitions = self.partitions()
        kwargs = self.dataset_kwargs()
        first = build_dataset_manifest(
            **kwargs,
            partitions=partitions,
        )
        kwargs["validation_receipt_sha256"] = "1" * 64
        second = build_dataset_manifest(
            **kwargs,
            partitions=partitions,
        )
        self.assertEqual(
            first.dataset_manifest_id,
            second.dataset_manifest_id,
        )
        self.assertEqual(
            first.dataset_fingerprint,
            second.dataset_fingerprint,
        )
        self.assertNotEqual(
            first.content_sha256,
            second.content_sha256,
        )

    def test_empty_inventory_is_deterministic_but_not_acceptance(self) -> None:
        kwargs = self.dataset_kwargs()
        first = build_dataset_manifest(**kwargs, partitions=())
        second = build_dataset_manifest(**kwargs, partitions=())
        self.assertEqual(first, second)
        verify_dataset_manifest(first, partitions=())

    def test_canonical_manifest_bytes_are_stable_and_complete(self) -> None:
        partitions = self.partitions()
        dataset = build_dataset_manifest(
            **self.dataset_kwargs(),
            partitions=partitions,
        )
        first = canonical_manifest_bytes(dataset)
        second = canonical_manifest_bytes(dataset)
        parsed = json.loads(first)
        self.assertEqual(first, second)
        self.assertEqual(
            parsed["content_sha256"],
            dataset.content_sha256,
        )
        self.assertEqual(
            canonical_manifest_bytes(partitions[0]),
            canonical_manifest_bytes(partitions[0]),
        )


if __name__ == "__main__":
    unittest.main()
