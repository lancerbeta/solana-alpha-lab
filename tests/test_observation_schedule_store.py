from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)


NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
DIGEST = "a" * 64


class ObservationScheduleStoreTests(unittest.TestCase):
    def _store(self, tmp: str) -> ObservationScheduleStore:
        return ObservationScheduleStore(Path(tmp) / "observation_schedule_state.sqlite")

    def test_relative_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(ObservationScheduleStoreError, "OPS_STORE_PATH_NOT_ABSOLUTE"):
            ObservationScheduleStore(Path("relative.sqlite"))

    def test_due_uniqueness_and_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            row = {
                "schedule_sha256": DIGEST,
                "activation_id": "ACT-OBS-001",
                "entity_id": "Mint111111111111111111111111111111111111111",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "PENDING",
                "due_at": "2026-09-01T00:05:00Z",
                "deadline_at": "2026-09-01T00:10:00Z",
                "payload": {},
            }
            store.insert_due(row, clock=NOW)
            store.insert_due({**row, "state": "PENDING"}, clock=NOW)
            claimed = store.claim_due(limit=10, now=NOW, owner="tick-once")
            self.assertEqual(len(claimed), 1)
            self.assertEqual(claimed[0]["state"], "CLAIMED")
            again = store.claim_due(limit=10, now=NOW, owner="tick-once")
            self.assertEqual(again, [])
            store.close()

    def test_lease_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = self._store(tmp)
            second = self._store(tmp)
            self.addCleanup(first.close)
            self.addCleanup(second.close)
            first_token = first.acquire_lease("owner-a", clock=NOW)
            self.assertTrue(first_token)
            self.assertFalse(second.acquire_lease("owner-b", clock=NOW))
            second.release_lease("not-the-owner-token")
            self.assertFalse(second.acquire_lease("owner-b", clock=NOW))
            assert first_token is not None
            first.release_lease(first_token)
            second_token = second.acquire_lease("owner-b", clock=NOW)
            self.assertTrue(second_token)
            later = NOW + timedelta(seconds=121)
            first_token_after_expiry = first.acquire_lease("owner-c", clock=later)
            self.assertTrue(first_token_after_expiry)
            assert first_token_after_expiry is not None
            second.release_lease(second_token)
            first.release_lease(first_token_after_expiry)
            first.close()
            second.close()

    def test_write_renews_lease_so_second_owner_stays_fenced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = self._store(tmp)
            second = self._store(tmp)
            self.addCleanup(first.close)
            self.addCleanup(second.close)
            token = first.acquire_lease("owner-a", clock=NOW)
            self.assertTrue(token)
            mid = NOW + timedelta(seconds=90)
            first.record_event("heartbeat", {"ok": True}, clock=mid)
            self.assertFalse(second.acquire_lease("owner-b", clock=mid))
            still_later = mid + timedelta(seconds=90)
            self.assertFalse(second.acquire_lease("owner-b", clock=still_later))
            assert token is not None
            first.release_lease(token)
            self.assertTrue(second.acquire_lease("owner-b", clock=still_later))
            first.close()
            second.close()

    def test_lease_race_has_one_successful_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stores = [self._store(tmp), self._store(tmp)]
            barrier = threading.Barrier(2)
            results: list[str | None] = [None, None]
            errors: list[BaseException] = []

            def acquire(index: int) -> None:
                try:
                    barrier.wait()
                    results[index] = stores[index].acquire_lease(
                        f"owner-{index}", clock=NOW
                    )
                except BaseException as exc:  # pragma: no cover - diagnostic path
                    errors.append(exc)

            threads = [
                threading.Thread(target=acquire, args=(index,))
                for index in range(2)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            for store in stores:
                store.close()

            self.assertEqual(errors, [])
            self.assertEqual(sum(result is not None for result in results), 1)

    def test_call_occurrence_is_required_for_call_ledger_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            with self.assertRaisesRegex(
                ObservationScheduleStoreError, "CALL_OCCURRENCE_REQUIRED"
            ):
                store.start_call(
                    request_sha256="b" * 64,
                    attempt_id="ATT-1",
                    primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    payload={"url": "https://api.jup.ag/tokens/v2/search"},
                    clock=NOW,
                )
            store.close()

    def test_legacy_call_ledger_without_occurrence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ops.sqlite"
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    """
                    CREATE TABLE call_ledger(
                        request_sha256 TEXT PRIMARY KEY,
                        attempt_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        primitive_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "a" * 64,
                        "ATT-LEGACY",
                        "STARTED",
                        "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "{}",
                        "2026-09-01T00:00:00Z",
                        "2026-09-01T00:00:00Z",
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            with self.assertRaisesRegex(
                ObservationScheduleStoreError,
                "CALL_LEDGER_MIGRATION_OCCURRENCE_REQUIRED",
            ):
                ObservationScheduleStore(path)

    def test_started_call_is_not_restarted_for_same_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            first = store.start_call(
                request_sha256="b" * 64,
                call_occurrence_id="occurrence-search-slot",
                attempt_id="ATT-1",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": "https://api.jup.ag/tokens/v2/search"},
                clock=NOW,
            )
            self.assertEqual(first, "STARTED")
            second = store.start_call(
                request_sha256="b" * 64,
                call_occurrence_id="occurrence-search-slot",
                attempt_id="ATT-2",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": "https://api.jup.ag/tokens/v2/search"},
                clock=NOW,
            )
            self.assertEqual(second, "IN_FLIGHT_CALL_INDETERMINATE")
            store.complete_call(
                request_sha256="b" * 64,
                call_occurrence_id="occurrence-search-slot",
                attempt_id="ATT-1",
                payload={"ok": True},
                clock=NOW,
            )
            self.assertEqual(store.call_state("occurrence-search-slot"), "COMPLETED")
            self.assertIsNone(store.call_state("b" * 64))
            store.close()

    def test_same_transport_request_can_have_distinct_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            request_digest = "c" * 64
            first_occurrence = "occurrence-y900"
            second_occurrence = "occurrence-y3600"
            self.assertEqual(
                store.start_call(
                    request_sha256=request_digest,
                    call_occurrence_id=first_occurrence,
                    attempt_id="ATT-Y900",
                    primitive_id="PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    payload={"url": "same-url"},
                    clock=NOW,
                ),
                "STARTED",
            )
            store.complete_call(
                request_sha256=request_digest,
                call_occurrence_id=first_occurrence,
                attempt_id="ATT-Y900",
                payload={"outAmount": "1"},
                clock=NOW,
            )
            self.assertEqual(
                store.start_call(
                    request_sha256=request_digest,
                    call_occurrence_id=second_occurrence,
                    attempt_id="ATT-Y3600",
                    primitive_id="PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    payload={"url": "same-url"},
                    clock=NOW,
                ),
                "STARTED",
            )
            self.assertEqual(store.call_state(first_occurrence), "COMPLETED")
            self.assertEqual(store.call_state(second_occurrence), "STARTED")
            store.close()

    def test_same_attempt_id_is_scoped_to_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            self.addCleanup(store.close)
            request_digest = "d" * 64
            primitive_id = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
            self.assertEqual(
                store.start_call(
                    request_sha256=request_digest,
                    call_occurrence_id="occurrence-y900",
                    attempt_id="ATT-SAME",
                    primitive_id=primitive_id,
                    payload={"url": "same-url"},
                    clock=NOW,
                ),
                "STARTED",
            )
            self.assertEqual(
                store.start_call(
                    request_sha256=request_digest,
                    call_occurrence_id="occurrence-y3600",
                    attempt_id="ATT-SAME",
                    primitive_id=primitive_id,
                    payload={"url": "same-url"},
                    clock=NOW,
                ),
                "STARTED",
            )
            self.assertEqual(store.call_state("occurrence-y900"), "STARTED")
            self.assertEqual(store.call_state("occurrence-y3600"), "STARTED")
            store.close()

    def test_candidate_state_updates_without_duplicate_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            row = {
                "schedule_sha256": DIGEST,
                "activation_id": "ACT-OBS-001",
                "entity_id": "Mint222222222222222222222222222222222222222",
                "state": "CANDIDATE",
                "payload": {},
            }
            self.assertTrue(store.insert_candidate(row, clock=NOW))
            self.assertFalse(store.insert_candidate(row, clock=NOW))
            store.set_candidate_state({**row, "state": "NOT_SELECTED_CAPACITY"}, clock=NOW)
            stored = store._conn.execute(
                "SELECT state, COUNT(*) AS n FROM candidate_members GROUP BY state"
            ).fetchone()
            self.assertEqual(stored["state"], "NOT_SELECTED_CAPACITY")
            self.assertEqual(int(stored["n"]), 1)
            store.close()

    def test_equivalent_collection_plan_registers_second_key_as_alias(self) -> None:
        from solana_alpha_lab.factory.observation_schedule import schedule_sha256

        document = {
            "schema": "smial.observation-schedule",
            "schema_version": "1.0",
            "schedule_key": "PLAN-KEY-A",
            "activation": {
                "starts_at": "2026-09-01T00:00:00Z",
                "stops_admitting_at": "2026-09-02T00:00:00Z",
            },
            "source_poll": {"period_seconds": 60},
            "x_point": {"point_id": "X300", "due_offset_seconds": 300},
            "y_points": [{"point_id": "Y900", "due_offset_seconds": 900}],
        }
        digest = schedule_sha256(document)
        equivalent = {**document, "schedule_key": "PLAN-KEY-B"}
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            self.assertEqual(
                store.persist_registered_schedule(
                    schedule_sha256=digest,
                    schedule_key="PLAN-KEY-A",
                    document=document,
                    clock=NOW,
                ),
                "REGISTERED",
            )
            self.assertEqual(
                store.persist_registered_schedule(
                    schedule_sha256=digest,
                    schedule_key="PLAN-KEY-B",
                    document=equivalent,
                    clock=NOW,
                ),
                "ATTACHED_TO_EXISTING_PLAN",
            )
            registered = store.get_registered_schedule(digest)
            self.assertIsNotNone(registered)
            assert registered is not None
            self.assertEqual(len(registered["aliases"]), 2)
            self.assertEqual(
                store.get_registered_schedule_by_key("PLAN-KEY-B")["schedule_sha256"],
                digest,
            )
            store.close()

    def test_collection_mutation_can_reuse_key_with_new_plan_hash(self) -> None:
        from solana_alpha_lab.factory.observation_schedule import schedule_sha256

        document = {
            "schema": "smial.observation-schedule",
            "schema_version": "1.0",
            "schedule_key": "PLAN-KEY-SAME",
            "activation": {
                "starts_at": "2026-09-01T00:00:00Z",
                "stops_admitting_at": "2026-09-02T00:00:00Z",
            },
            "source_poll": {"period_seconds": 60},
            "x_point": {"point_id": "X300", "due_offset_seconds": 300},
            "y_points": [{"point_id": "Y900", "due_offset_seconds": 900}],
        }
        changed = {
            **document,
            "x_point": {**document["x_point"], "due_offset_seconds": 301},
        }
        first_digest = schedule_sha256(document)
        second_digest = schedule_sha256(changed)
        self.assertNotEqual(first_digest, second_digest)
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            self.assertEqual(
                store.persist_registered_schedule(
                    schedule_sha256=first_digest,
                    schedule_key=document["schedule_key"],
                    document=document,
                    clock=NOW,
                ),
                "REGISTERED",
            )
            self.assertEqual(
                store.persist_registered_schedule(
                    schedule_sha256=second_digest,
                    schedule_key=changed["schedule_key"],
                    document=changed,
                    clock=NOW,
                ),
                "REGISTERED",
            )
            self.assertIsNotNone(store.get_registered_schedule(first_digest))
            self.assertIsNotNone(store.get_registered_schedule(second_digest))
            store.close()

    def test_backup_and_restore_sets_unresolved_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.record_event("TICK", {"n": 1}, clock=NOW)
            backup = Path(tmp) / "backup.sqlite"
            store.backup_to(backup)
            store.restore_from(backup, recovery_epoch="RECOVERY-001")
            self.assertTrue(store.restore_marker_unresolved())
            store.resolve_restore_marker()
            self.assertFalse(store.restore_marker_unresolved())
            store.close()

    def test_terminal_due_state_cannot_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            row = {
                "schedule_sha256": DIGEST,
                "activation_id": "ACT-OBS-001",
                "entity_id": "Mint111111111111111111111111111111111111111",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "OBSERVED",
                "due_at": "2026-09-01T00:05:00Z",
                "deadline_at": "2026-09-01T00:10:00Z",
                "payload": {},
            }
            store.insert_due(row, clock=NOW)
            with self.assertRaisesRegex(
                ObservationScheduleStoreError, "DENY_RETROACTIVE_MUTATION"
            ):
                store.insert_due({**row, "state": "CENSORED"}, clock=NOW)
            store.close()

    def test_lifecycle_transition_rejects_invalid_state_edge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.upsert_activation(
                {
                    "schedule_sha256": DIGEST,
                    "activation_id": "ACT-OBS-STATE",
                    "schedule_key": "OBS-STATE-001",
                    "state": "COMPLETE",
                    "starts_at": "2026-09-01T00:00:00Z",
                    "stops_admitting_at": "2026-09-02T00:00:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            with self.assertRaisesRegex(
                ObservationScheduleStoreError, "INVALID_STATE_TRANSITION"
            ):
                store.transition_activation(
                    schedule_sha256=DIGEST,
                    activation_id="ACT-OBS-STATE",
                    new_state="PAUSED_OPERATOR",
                    clock=NOW,
                )
            store.close()

    def test_censor_remaining_points_can_exclude_only_current_primitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            common = {
                "schedule_sha256": DIGEST,
                "activation_id": "ACT-OBS-001",
                "entity_id": "Mint111111111111111111111111111111111111111",
                "deadline_at": "2026-09-01T00:20:00Z",
                "payload": {},
            }
            store.insert_due(
                {
                    **common,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "OBSERVED",
                    "due_at": "2026-09-01T00:05:00Z",
                },
                clock=NOW,
            )
            store.insert_due(
                {
                    **common,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:05:00Z",
                },
                clock=NOW,
            )
            censored = store.censor_remaining_points(
                schedule_sha256=DIGEST,
                activation_id="ACT-OBS-001",
                entity_id=common["entity_id"],
                reason="X_POPULATION_INELIGIBLE",
                exclude_primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                clock=NOW,
            )
            self.assertEqual(len(censored), 1)
            self.assertEqual(censored[0]["primitive_id"], "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001")
            self.assertEqual(
                store.get_due(
                    {
                        **common,
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    }
                )["state"],
                "OBSERVED",
            )
            store.close()

    def test_terminal_provisional_point_can_be_explicitly_censored_without_reanchoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            row = {
                "schedule_sha256": DIGEST,
                "activation_id": "ACT-OBS-001",
                "entity_id": "Mint111111111111111111111111111111111111111",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "OBSERVED",
                "due_at": "2026-09-01T00:05:00Z",
                "deadline_at": "2026-09-01T00:10:00Z",
                "payload": {"provisional_due": True},
            }
            store.insert_due(row, clock=NOW)
            changed = store.mark_point_censored_late(
                row,
                reason="AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                clock=NOW,
            )
            self.assertEqual(changed["state"], "CENSORED_LATE")
            stored = store.get_due(row)
            self.assertEqual(stored["state"], "CENSORED_LATE")
            self.assertEqual(stored["due_at"], row["due_at"])
            store.close()

    def test_sqlite_restore_does_not_rewrite_sibling_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.record_event("TICK", {"n": 1}, clock=NOW)
            backup = Path(tmp) / "backup.sqlite"
            store.backup_to(backup)
            sibling = Path(tmp) / "datasets" / "parquet" / "panel.parquet"
            sibling.parent.mkdir(parents=True)
            sibling.write_bytes(b"partition-bytes")
            store.restore_from(backup, recovery_epoch="RECOVERY-ISO")
            self.assertEqual(sibling.read_bytes(), b"partition-bytes")
            self.assertTrue(store.restore_marker_unresolved())
            store.close()


if __name__ == "__main__":
    unittest.main()
