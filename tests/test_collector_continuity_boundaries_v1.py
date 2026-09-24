"""Main-line parity for live continuity selection invariants."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_operational_packet import (  # noqa: E402
    build_collector_operational_packet,
)
from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    activation_selection_status,
    project_activation_as_of,
    select_current_activation,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    status_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    _persist_draining_pre_cutover_stop,
    _pre_cutover_operational_stop,
)
from solana_alpha_lab.factory.operability_watch import classify_incidents  # noqa: E402


NOW = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)


def _row(activation_id: str, state: str, family: str, updated: str) -> dict:
    return {
        "activation_id": activation_id,
        "state": state,
        "cohort_family_key": family,
        "updated_at": updated,
        "created_at": updated,
        "schedule_sha256": "a" * 64,
    }


class CollectorContinuityBoundaryTests(unittest.TestCase):
    def test_historical_other_family_stays_scoped(self) -> None:
        rows = [
            _row("ACT-LIVE", "ACTIVE", "FAMILY-A", "2026-09-01T00:05:00Z"),
            _row("ACT-OLD", "COMPLETE", "FAMILY-B", "2026-08-01T00:00:00Z"),
            _row("ACT-ABORT", "ABORTED_SAFETY", "FAMILY-C", "2026-08-02T00:00:00Z"),
        ]
        self.assertEqual(activation_selection_status(rows, now=NOW), "SCOPED")
        selected = select_current_activation(rows, now=NOW)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-LIVE")
        self.assertEqual(selected["state"], "ACTIVE")

    def test_same_family_active_beats_draining(self) -> None:
        rows = [
            _row("ACT-DRAIN", "DRAINING", "FAMILY-A", "2026-09-01T00:04:00Z"),
            _row("ACT-LIVE", "ACTIVE", "FAMILY-A", "2026-09-01T00:05:00Z"),
        ]
        self.assertEqual(activation_selection_status(rows, now=NOW), "SCOPED")
        selected = select_current_activation(rows, now=NOW)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-LIVE")

    def test_two_live_families_fail_closed(self) -> None:
        rows = [
            _row("ACT-A", "ACTIVE", "FAMILY-A", "2026-09-01T00:05:00Z"),
            _row("ACT-B", "DRAINING", "FAMILY-B", "2026-09-01T00:04:00Z"),
        ]
        self.assertEqual(activation_selection_status(rows, now=NOW), "AMBIGUOUS")
        self.assertIsNone(select_current_activation(rows, now=NOW))

    def test_live_row_without_family_is_ambiguous(self) -> None:
        rows = [
            {
                "activation_id": "ACT-BARE",
                "state": "ACTIVE",
                "cohort_family_key": "",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:05:00Z",
            }
        ]
        self.assertEqual(activation_selection_status(rows, now=NOW), "AMBIGUOUS")
        self.assertIsNone(select_current_activation(rows, now=NOW))

    def test_no_live_rows_are_not_ambiguous(self) -> None:
        rows = [
            _row("ACT-OLD", "COMPLETE", "FAMILY-B", "2026-08-01T00:00:00Z"),
            _row("ACT-ABORT", "ABORTED_SAFETY", "FAMILY-C", "2026-08-02T00:00:00Z"),
        ]
        self.assertEqual(activation_selection_status(rows, now=NOW), "NO_LIVE")
        selected = select_current_activation(rows, now=NOW)
        assert selected is not None
        self.assertEqual(selected["state"], "ABORTED_SAFETY")

    def test_future_other_family_does_not_hide_current_active(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            _row("ACT-LIVE", "ACTIVE", "FAMILY-A", "2026-09-01T00:00:00Z"),
            {
                **_row("ACT-NEXT", "ACTIVE", "FAMILY-B", "2026-09-01T00:00:00Z"),
                "payload": {
                    "prior_state": "UNREGISTERED",
                    "transition_effective_at": "2026-09-02T00:00:00Z",
                },
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "SCOPED")
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-LIVE")
        self.assertEqual(
            activation_selection_status(rows),
            "AMBIGUOUS",
        )

    def test_future_same_family_successor_does_not_outrank_predecessor(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            _row("ACT-NOW", "ACTIVE", "FAMILY-A", "2026-09-01T00:00:00Z"),
            {
                **_row("ACT-LATER", "ACTIVE", "FAMILY-A", "2026-09-01T00:30:00Z"),
                "payload": {
                    "prior_state": "ACTIVE",
                    "transition_effective_at": "2026-09-02T00:00:00Z",
                },
            },
        ]
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-NOW")

    def test_pending_predecessor_is_not_replaced_by_historical_row(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            _row("ACT-OLD", "ABORTED_SAFETY", "FAMILY-A", "2026-09-01T00:30:00Z"),
            {
                **_row("ACT-NOW", "ACTIVE", "FAMILY-A", "2026-09-01T00:00:00Z"),
                "payload": {
                    "prior_state": "ACTIVE",
                    "transition_effective_at": "2026-09-02T00:00:00Z",
                },
            },
        ]
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-NOW")
        self.assertEqual(selected["state"], "ACTIVE")

    def test_status_projects_predecessor_before_effective_time(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        row = {
            "schedule_sha256": "d" * 64,
            "activation_id": "ACT-FUTURE",
            "state": "ACTIVE",
            "last_transition_event_id": "OBS-TRANS-KEEP",
            "payload": {
                "prior_state": "DRAINING",
                "transition_effective_at": "2026-09-02T00:00:00Z",
            },
        }
        visible = project_activation_as_of(row, now)
        self.assertEqual(visible["state"], "DRAINING")
        self.assertTrue(visible["future_transition_pending"])
        self.assertEqual(row["state"], "ACTIVE")
        self.assertEqual(row["last_transition_event_id"], "OBS-TRANS-KEEP")
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            store.upsert_activation(
                {
                    "schedule_sha256": row["schedule_sha256"],
                    "activation_id": row["activation_id"],
                    "schedule_key": "OBS-ASOF",
                    "state": "ACTIVE",
                    "starts_at": "2026-09-01T00:00:00Z",
                    "stops_admitting_at": "2026-09-03T00:00:00Z",
                    "last_transition_event_id": "OBS-TRANS-KEEP",
                    "payload": row["payload"],
                },
                clock=now,
            )
            status = status_schedule(
                store,
                schedule_sha256=row["schedule_sha256"],
                activation_id=row["activation_id"],
                now=now,
            )
            reported = status["activations"][0]
            self.assertEqual(reported["state"], "DRAINING")
            self.assertTrue(reported["future_transition_pending"])
            self.assertEqual(reported["transition_event_id"], "OBS-TRANS-KEEP")
            store.close()

    def test_historical_publication_stall_does_not_stick_the_live_family(self) -> None:
        now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
        live = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        historical = json.loads(json.dumps(live))
        historical["sampling"] = dict(historical["sampling"])
        historical["sampling"]["seed"] = 99002
        historical["schedule_key"] = "OBS-HISTORICAL-PUBLICATION"
        historical.pop("schedule_sha256", None)
        historical["schedule_sha256"] = schedule_sha256(historical)
        aborted = json.loads(json.dumps(live))
        aborted["sampling"] = dict(aborted["sampling"])
        aborted["sampling"]["seed"] = 99003
        aborted["schedule_key"] = "OBS-ABORTED-FAMILY"
        aborted.pop("schedule_sha256", None)
        aborted["schedule_sha256"] = schedule_sha256(aborted)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ObservationScheduleStore(root / "ops.sqlite")
            self.addCleanup(store.close)
            for document, activation_id, state in (
                (live, "ACT-LIVE", "ACTIVE"),
                (historical, "ACT-OLD", "COMPLETE"),
                (aborted, "ACT-ABORT", "ABORTED_SAFETY"),
            ):
                store.persist_registered_schedule(
                    schedule_sha256=document["schedule_sha256"],
                    schedule_key=document["schedule_key"],
                    document=document,
                    clock=now,
                )
                store.upsert_activation(
                    {
                        "schedule_sha256": document["schedule_sha256"],
                        "activation_id": activation_id,
                        "schedule_key": document["schedule_key"],
                        "state": state,
                        "starts_at": document["activation"]["starts_at"],
                        "stops_admitting_at": document["activation"]["stops_admitting_at"],
                        "payload": {},
                    },
                    clock=now,
                )
            store.insert_due(
                {
                    "schedule_sha256": historical["schedule_sha256"],
                    "activation_id": "ACT-OLD",
                    "entity_id": "MintOldPub111111111111111111111111111111",
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:00:00Z",
                    "deadline_at": "2026-09-01T00:05:00Z",
                    "payload": {},
                },
                clock=now,
            )
            rdp = root / "observation_rdp"
            marker = rdp / "datasets" / "manifests"
            marker.mkdir(parents=True)
            published = marker / "historical.published"
            published.write_text("historical\n", encoding="utf-8")
            os.utime(published, (now.timestamp() - 8 * 3600, now.timestamp() - 8 * 3600))
            packet = build_collector_operational_packet(
                root=root,
                store=store,
                now=now,
                observation_rdp=rdp,
                remote_config={"backup": {}},
                environ={},
            )
            self.assertEqual(packet["activation_selection_status"], "SCOPED")
            self.assertEqual(packet["activation_id"], "ACT-LIVE")
            self.assertEqual(packet["activation_state"], "ACTIVE")
            self.assertEqual(packet["due_pressure"]["due_now_count"], 0)
            self.assertEqual(packet["due_pressure"]["actually_overdue_count"], 0)
            self.assertNotIn("RDP_PUBLICATION_STALE", set(packet["health_classes"]))
            self.assertNotIn("PUBLICATION_STUCK", classify_incidents(packet))
            store.close()

    def test_draining_pre_cutover_stop_keeps_lifecycle_proof(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        activation = {
            "schedule_sha256": "e" * 64,
            "activation_id": "ACT-DRAIN",
            "schedule_key": "OBS-DRAIN",
            "state": "DRAINING",
            "authority_receipt_sha256": "f" * 64,
            "starts_at": "2026-09-01T00:00:00Z",
            "stops_admitting_at": "2026-09-02T00:00:00Z",
            "last_transition_event_id": "OBS-TRANS-KEEP",
            "payload": {"reason": "ADMISSION_CLOSED"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            store.upsert_activation(activation, clock=now)
            _persist_draining_pre_cutover_stop(
                store, activation, "BLOCKED_BUDGET", clock=now
            )
            saved = store.get_activation("e" * 64, "ACT-DRAIN")
            assert saved is not None
            self.assertEqual(saved["state"], "DRAINING")
            self.assertEqual(saved["last_transition_event_id"], "OBS-TRANS-KEEP")
            self.assertEqual(
                _pre_cutover_operational_stop(saved),
                "BLOCKED_BUDGET",
            )
            store.close()


if __name__ == "__main__":
    unittest.main()
