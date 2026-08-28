from __future__ import annotations

import sys
import tempfile
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
            store = self._store(tmp)
            self.assertTrue(store.acquire_lease("owner-a", clock=NOW))
            self.assertFalse(store.acquire_lease("owner-b", clock=NOW))
            store.release_lease("owner-a")
            self.assertTrue(store.acquire_lease("owner-b", clock=NOW))
            later = NOW + timedelta(seconds=56)
            self.assertTrue(store.acquire_lease("owner-c", clock=later))
            store.close()

    def test_started_call_is_not_restarted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            first = store.start_call(
                request_sha256="b" * 64,
                attempt_id="ATT-1",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": "https://api.jup.ag/tokens/v2/search"},
                clock=NOW,
            )
            self.assertEqual(first, "STARTED")
            second = store.start_call(
                request_sha256="b" * 64,
                attempt_id="ATT-2",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": "https://api.jup.ag/tokens/v2/search"},
                clock=NOW,
            )
            self.assertEqual(second, "IN_FLIGHT_CALL_INDETERMINATE")
            store.complete_call(
                request_sha256="b" * 64,
                attempt_id="ATT-1",
                payload={"ok": True},
                clock=NOW,
            )
            self.assertEqual(store.call_state("b" * 64), "COMPLETED")
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
