from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.research_store import (
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)


NOW = datetime(2026, 8, 25, 12, 30, tzinfo=UTC)


def canonical_payload(payload: object) -> tuple[str, str]:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_fixture(
    *,
    record_id: str = "RUN-EVENT-001",
    record_kind: str = "RUN_STARTED",
    transaction_id: str = "RESEARCH-TXN-001",
    payload: object | None = None,
) -> ResearchEvent:
    payload_json, payload_sha256 = canonical_payload(
        payload if payload is not None else {"status": "STARTED"}
    )
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id="RUN-0123456789ABCDEF01234567",
        hypothesis_version_id="HYP-VERSION-FAST-LANE-V1",
        run_id="RUN-0123456789ABCDEF01234567",
        transaction_id=transaction_id,
        effective_at=NOW,
        first_reliable_available_at=NOW,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=payload_sha256,
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="a" * 40,
        created_at=NOW,
    )


class ResearchStoreTests(unittest.TestCase):
    def store(self, root: Path) -> ResearchStore:
        return ResearchStore(root)

    def test_envelope_schema_matches_closed_record_kind_contract(self) -> None:
        schema = json.loads(
            (
                ROOT / "catalog/schemas/research_event_envelope.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(
            schema["required"],
            [
                "record_id",
                "record_kind",
                "entity_id",
                "hypothesis_version_id",
                "run_id",
                "transaction_id",
                "effective_at",
                "first_reliable_available_at",
                "supersedes_record_id",
                "payload_json",
                "payload_sha256",
                "schema_version",
                "producer_capability_id",
                "producer_git_sha",
                "created_at",
            ],
        )
        valid = event_fixture().model_dump(mode="json")
        jsonschema.validate(valid, schema)
        invalid = dict(valid)
        invalid["record_kind"] = "UNDECLARED_KIND"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_read_after_publish_returns_canonical_record_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            second = event_fixture(record_id="RUN-EVENT-002")
            first = event_fixture(record_id="RUN-EVENT-001")
            receipt = store.append(
                [second, first],
                transaction_id="RESEARCH-TXN-001",
            )

            self.assertEqual(receipt.disposition, "CREATED")
            self.assertTrue(receipt.logical_uri.startswith("smial-data://research/"))
            observed = tuple(store.iter_committed_records())
            self.assertEqual(
                [record.record_id for record in observed],
                ["RUN-EVENT-001", "RUN-EVENT-002"],
            )

    def test_identical_transaction_replay_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            records = [event_fixture()]
            first = store.append(records, transaction_id="RESEARCH-TXN-001")
            second = store.append(records, transaction_id="RESEARCH-TXN-001")

            self.assertEqual(first.manifest, second.manifest)
            self.assertEqual(second.disposition, "REPLAY_IDENTICAL")
            self.assertEqual(len(tuple(store.iter_committed_records())), 1)

    def test_conflicting_transaction_id_fails_without_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            first = event_fixture()
            receipt = store.append([first], transaction_id="RESEARCH-TXN-001")
            parquet_path = Path(tmp) / receipt.manifest.logical_location
            original_bytes = parquet_path.read_bytes()
            conflicting = event_fixture(
                record_id="RUN-EVENT-002",
                payload={"status": "DIFFERENT"},
            )

            with self.assertRaisesRegex(
                ResearchStoreError,
                "TRANSACTION_CONFLICT",
            ):
                store.append(
                    [conflicting],
                    transaction_id="RESEARCH-TXN-001",
                )
            self.assertEqual(parquet_path.read_bytes(), original_bytes)

    def test_transaction_id_rejects_absolute_and_parent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            for transaction_id in (
                "../RESEARCH-TXN-001",
                "/private/RESEARCH-TXN-001",
                "C:\\private\\RESEARCH-TXN-001",
                "C:private\\RESEARCH-TXN-001",
            ):
                with self.subTest(transaction_id=transaction_id):
                    event = event_fixture().model_copy(
                        update={"transaction_id": transaction_id}
                    )
                    with self.assertRaises(ResearchStoreError):
                        store.append(
                            [event],
                            transaction_id=transaction_id,
                        )

    def test_payload_rejects_physical_and_parent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            for value in ("../secret.json", "/private/secret.json", "C:\\secret.json"):
                with self.subTest(value=value):
                    with self.assertRaises(ResearchStoreError):
                        store.append(
                            [event_fixture(payload={"artifact": value})],
                            transaction_id="RESEARCH-TXN-001",
                        )

    def test_payload_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            invalid = event_fixture().model_copy(
                update={"payload_sha256": "0" * 64}
            )
            with self.assertRaisesRegex(
                ResearchStoreError,
                "PAYLOAD_HASH_MISMATCH",
            ):
                store.append([invalid], transaction_id="RESEARCH-TXN-001")

    def test_duplicate_record_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            duplicate = event_fixture()
            with self.assertRaisesRegex(
                ResearchStoreError,
                "DUPLICATE_RECORD_ID",
            ):
                store.append(
                    [duplicate, duplicate],
                    transaction_id="RESEARCH-TXN-001",
                )

    def test_second_writer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = self.store(Path(tmp))
            second = self.store(Path(tmp))
            with first.writer_lease():
                with self.assertRaisesRegex(ResearchStoreError, "WRITER_BUSY"):
                    second.append(
                        [event_fixture()],
                        transaction_id="RESEARCH-TXN-001",
                    )

    def test_orphan_partition_is_not_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            store.test_write_partition_without_manifest([event_fixture()])
            self.assertEqual(tuple(store.iter_committed_records()), ())

    def test_persisted_manifest_contains_no_physical_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            store.append(
                [event_fixture()],
                transaction_id="RESEARCH-TXN-001",
            )
            manifest_bytes = next(
                (Path(tmp) / "research/manifests/partitions").glob(
                    "partition-*.json"
                )
            ).read_text(encoding="utf-8")
            self.assertNotIn(str(Path(tmp)), manifest_bytes)
            self.assertNotIn("\\", manifest_bytes)


if __name__ == "__main__":
    unittest.main()
