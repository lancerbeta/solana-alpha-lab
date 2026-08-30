from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory import research_store as research_store_module
from solana_alpha_lab.factory.research_store import (
    PidLiveness,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
    _timestamp_text,
    probe_local_pid,
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

    def test_payload_rejects_file_uris_without_committing_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self.store(Path(tmp))
            for value in (
                "file:///private/secret.json",
                "file:///C:/secret.json",
            ):
                with self.subTest(value=value):
                    with self.assertRaises(ResearchStoreError) as raised:
                        store.append(
                            [event_fixture(payload={"artifact": value})],
                            transaction_id="RESEARCH-TXN-001",
                        )
                    self.assertEqual(raised.exception.code, "PHYSICAL_PATH_FORBIDDEN")
                    self.assertEqual(tuple(store.iter_committed_records()), ())

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


class WriterLeaseStaleRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._clock_backup = research_store_module._lease_clock
        self._probe_backup = research_store_module._pid_liveness_probe
        self.addCleanup(self._restore_hooks)

    def _restore_hooks(self) -> None:
        research_store_module._lease_clock = self._clock_backup
        research_store_module._pid_liveness_probe = self._probe_backup

    def _write_lease(
        self,
        root: Path,
        *,
        expiry: datetime,
        opened_at: datetime,
        pid: int,
        token: str = "a" * 32,
        host: str | None = None,
        raw: bytes | None = None,
    ) -> Path:
        locks = root / "locks"
        locks.mkdir(parents=True, exist_ok=True)
        path = locks / "research-writer.lock"
        if raw is not None:
            path.write_bytes(raw)
            return path
        payload = {
            "expiry": _timestamp_text(expiry),
            "host": socket.gethostname() if host is None else host,
            "opened_at": _timestamp_text(opened_at),
            "pid": pid,
            "token": token,
        }
        path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return path

    def test_t1_ordinary_acquire_release_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ResearchStore(root)
            with store.writer_lease():
                lock = root / "locks" / "research-writer.lock"
                self.assertTrue(lock.is_file())
                lease = json.loads(lock.read_text(encoding="utf-8"))
                self.assertEqual(lease["pid"], os.getpid())
                self.assertEqual(lease["host"], socket.gethostname())
            self.assertFalse((root / "locks" / "research-writer.lock").exists())

    def test_t2_non_expired_lease_not_recovered(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=now + timedelta(minutes=2),
                opened_at=now - timedelta(minutes=1),
                pid=os.getpid(),
                token="b" * 32,
            )
            original = path.read_bytes()
            store = ResearchStore(root)
            with self.assertRaisesRegex(ResearchStoreError, "WRITER_BUSY"):
                with store.writer_lease():
                    pass
            self.assertEqual(path.read_bytes(), original)

    def test_t3_expired_but_owner_alive_not_recovered(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.ALIVE
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=10),
                pid=424242,
                token="c" * 32,
            )
            original = path.read_bytes()
            with self.assertRaisesRegex(ResearchStoreError, "WRITER_BUSY"):
                with ResearchStore(root).writer_lease():
                    pass
            self.assertEqual(path.read_bytes(), original)

    def test_t4_expired_remote_host_not_recovered(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=10),
                pid=424242,
                token="d" * 32,
                host="other-host.example",
            )
            original = path.read_bytes()
            with self.assertRaisesRegex(
                ResearchStoreError,
                "WRITER_LEASE_REMOTE_OR_AMBIGUOUS",
            ):
                with ResearchStore(root).writer_lease():
                    pass
            self.assertEqual(path.read_bytes(), original)

    def test_t5_malformed_lease_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=datetime(2020, 1, 1, tzinfo=UTC),
                opened_at=datetime(2020, 1, 1, tzinfo=UTC),
                pid=1,
                raw=b"{not-json",
            )
            original = path.read_bytes()
            with self.assertRaisesRegex(ResearchStoreError, "WRITER_LEASE_INVALID"):
                with ResearchStore(root).writer_lease():
                    pass
            self.assertEqual(path.read_bytes(), original)

    def test_t6_pid_unknown_fails_closed(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.UNKNOWN
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=10),
                pid=424242,
                token="e" * 32,
            )
            original = path.read_bytes()
            with self.assertRaisesRegex(
                ResearchStoreError,
                "WRITER_LEASE_REMOTE_OR_AMBIGUOUS",
            ):
                with ResearchStore(root).writer_lease():
                    pass
            self.assertEqual(path.read_bytes(), original)

    def test_t7_killed_writer_shape_recovers(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        token = "f" * 32
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_lease(
                root,
                expiry=now - timedelta(seconds=30),
                opened_at=now - timedelta(minutes=10),
                pid=2**30 - 3,
                token=token,
            )
            store = ResearchStore(root)
            with store.writer_lease():
                lock = root / "locks" / "research-writer.lock"
                lease = json.loads(lock.read_text(encoding="utf-8"))
                self.assertNotEqual(lease["token"], token)
                self.assertEqual(lease["pid"], os.getpid())
            artifact = root / "locks" / "recovery" / f"{token}.json"
            self.assertTrue(artifact.is_file())
            body = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(body["classification"], "EXPIRED_LOCAL_OWNER_DEAD")
            self.assertEqual(body["old_token"], token)
            self.assertNotIn(str(root), artifact.read_text(encoding="utf-8"))

    def test_t8_recovery_artifact_create_only(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        token = "1" * 32
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recovery = root / "locks" / "recovery"
            recovery.mkdir(parents=True)
            prior = recovery / f"{token}.json"
            prior.write_text('{"kept":true}', encoding="utf-8")
            self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=5),
                pid=2**30 - 5,
                token=token,
            )
            with ResearchStore(root).writer_lease():
                pass
            self.assertEqual(prior.read_text(encoding="utf-8"), '{"kept":true}')

    def test_t9_concurrent_recovery_race(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        token = "2" * 32
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=5),
                pid=2**30 - 7,
                token=token,
            )
            start = threading.Barrier(2)
            hold = threading.Event()
            outcomes: list[str] = []
            guard = threading.Lock()

            def contender() -> None:
                store = ResearchStore(root)
                start.wait(timeout=5)
                try:
                    with store.writer_lease():
                        with guard:
                            outcomes.append("acquired")
                        hold.wait(timeout=5)
                except ResearchStoreError as exc:
                    with guard:
                        outcomes.append(exc.code)

            threads = [
                threading.Thread(target=contender),
                threading.Thread(target=contender),
            ]
            for thread in threads:
                thread.start()
            # Wait until one side has either acquired or failed.
            deadline = datetime.now(UTC).timestamp() + 5
            while datetime.now(UTC).timestamp() < deadline:
                with guard:
                    if len(outcomes) >= 1:
                        break
                hold.wait(0.01)
            hold.set()
            for thread in threads:
                thread.join(timeout=10)
            self.assertEqual(outcomes.count("acquired"), 1)
            self.assertEqual(len(outcomes), 2)
            loser_codes = {code for code in outcomes if code != "acquired"}
            self.assertTrue(
                loser_codes <= {"WRITER_BUSY", "WRITER_LEASE_RECOVERY_RACE"}
            )

    def test_t10_lease_changed_after_inspection(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        token = "3" * 32
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=5),
                pid=2**30 - 9,
                token=token,
            )
            successor = {
                "expiry": _timestamp_text(now + timedelta(minutes=5)),
                "host": socket.gethostname(),
                "opened_at": _timestamp_text(now),
                "pid": os.getpid(),
                "token": "4" * 32,
            }
            successor_bytes = json.dumps(
                successor,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            original_read = path.read_bytes()

            real_link = os.link

            def link_then_swap(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                # After exclusive claim of observed stale bytes, swap lock to successor.
                real_link(src, dst)
                Path(src).write_bytes(successor_bytes)

            with mock.patch("os.link", side_effect=link_then_swap):
                with self.assertRaisesRegex(
                    ResearchStoreError,
                    "WRITER_BUSY|WRITER_LEASE_RECOVERY_RACE",
                ):
                    with ResearchStore(root).writer_lease():
                        pass
            self.assertEqual(path.read_bytes(), successor_bytes)
            self.assertNotEqual(path.read_bytes(), original_read)

    def test_t11_symlink_lock_fails_closed(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            locks = root / "locks"
            locks.mkdir(parents=True)
            outside = Path(tmp) / "outside.lock"
            outside.write_text("{}", encoding="utf-8")
            link = locks / "research-writer.lock"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation not permitted")
            with self.assertRaises(ResearchStoreError):
                with ResearchStore(root).writer_lease():
                    pass
            self.assertTrue(link.is_symlink())

    def test_t12_append_flow_still_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            receipt = store.append(
                [event_fixture()],
                transaction_id="RESEARCH-TXN-001",
            )
            self.assertEqual(receipt.disposition.value, "CREATED")
            self.assertEqual(len(tuple(store.iter_committed_records())), 1)

    def test_t13_orphan_quarantine_after_link_still_recovers(self) -> None:
        now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        research_store_module._lease_clock = lambda: now
        research_store_module._pid_liveness_probe = lambda _pid: PidLiveness.DEAD
        token = "5" * 32
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_lease(
                root,
                expiry=now - timedelta(seconds=1),
                opened_at=now - timedelta(minutes=5),
                pid=2**30 - 11,
                token=token,
            )
            stale_bytes = path.read_bytes()
            recovery = root / "locks" / "recovery"
            recovery.mkdir(parents=True)
            quarantine = recovery / f"reclaimed-{token}.lock"
            os.link(path, quarantine)
            self.assertEqual(quarantine.read_bytes(), stale_bytes)
            self.assertTrue(path.is_file())
            with ResearchStore(root).writer_lease():
                lease = json.loads(path.read_text(encoding="utf-8"))
                self.assertNotEqual(lease["token"], token)
                self.assertEqual(lease["pid"], os.getpid())
            self.assertFalse(path.exists())
            artifact = recovery / f"{token}.json"
            self.assertTrue(artifact.is_file())

    def test_probe_local_pid_dead_and_alive(self) -> None:
        self.assertEqual(probe_local_pid(2**30 - 3), PidLiveness.DEAD)
        self.assertEqual(probe_local_pid(os.getpid()), PidLiveness.ALIVE)
        self.assertEqual(probe_local_pid(0), PidLiveness.UNKNOWN)
        self.assertEqual(probe_local_pid(-1), PidLiveness.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
