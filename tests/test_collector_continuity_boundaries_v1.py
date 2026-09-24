"""Regression tests for continuity selection and lightweight monitor imports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    activation_selection_status,
    build_collector_read_model,
    classify_doctor_current_activation,
    select_current_activation,
)


class CollectorContinuityBoundaryTests(unittest.TestCase):
    def test_active_selection_prefers_freshest_peer(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-OLD",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-NEW",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertEqual(
            select_current_activation(rows, now=now)["activation_id"],
            "ACT-NEW",
        )

    def test_draining_selection_prefers_freshest_peer(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-DRAIN-OLD",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-DRAIN-NEW",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertEqual(
            select_current_activation(rows, now=now)["activation_id"],
            "ACT-DRAIN-NEW",
        )

    def test_current_selection_does_not_cross_family_without_scope(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-FAMILY-A-DRAINING",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-FAMILY-B-ACTIVE",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-B",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertIsNone(select_current_activation(rows, now=now))
        self.assertEqual(
            select_current_activation(rows, now=now, family_key="FAMILY-A")[
                "activation_id"
            ],
            "ACT-FAMILY-A-DRAINING",
        )

    def test_future_updated_activation_fails_selection_closed(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-CURRENT",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-FUTURE-PROJECTION",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]

        self.assertIsNone(select_current_activation(rows, now=now))
        report = classify_doctor_current_activation(rows, now=now)
        self.assertEqual(report["current_activation_state"], "UNKNOWN")
        self.assertEqual(report["terminal"], "DOCTOR_ACTIVATION_SELECTION_UNKNOWN")
        self.assertEqual(
            report["next_action"], "RECONCILE_FUTURE_ACTIVATION_TRANSITION"
        )

    def test_future_transition_without_prior_state_does_not_hide_current_peer(
        self,
    ) -> None:
        now = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-CURRENT",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-FUTURE-UNKNOWN",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:10:00Z",
                "created_at": "2026-09-01T00:01:00Z",
                "payload": {"transition_effective_at": "2026-09-01T00:20:00Z"},
            },
        ]

        current = select_current_activation(rows, now=now)
        assert current is not None
        self.assertEqual(current["activation_id"], "ACT-CURRENT")
        report = classify_doctor_current_activation(rows, now=now)
        self.assertEqual(report["current_activation_state"], "ACTIVE")
        self.assertEqual(report["terminal"], "DOCTOR_CURRENT_OK")
        self.assertEqual(report["current_activation_id"], "ACT-CURRENT")

    def test_current_selection_fails_closed_without_family_identity(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-UNSCOPED",
                "state": "ACTIVE",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            }
        ]
        self.assertIsNone(select_current_activation(rows, now=now))
        report = classify_doctor_current_activation(rows, now=now)
        self.assertEqual(report["terminal"], "DOCTOR_ACTIVATION_SCOPE_AMBIGUOUS")
        self.assertEqual(report["next_action"], "RECONCILE_ACTIVATION_FAMILY_SCOPE")

    def test_exact_scope_resolves_selection_before_ambiguity_gate(self) -> None:
        rows = [
            {
                "activation_id": "ACT-FAMILY-A",
                "schedule_sha256": "a" * 64,
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
            },
            {
                "activation_id": "ACT-FAMILY-B",
                "schedule_sha256": "b" * 64,
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-B",
            },
        ]
        report = classify_doctor_current_activation(
            [rows[0]],
            explicit_scope=True,
        )
        self.assertEqual(report["terminal"], "DOCTOR_CURRENT_OK")
        self.assertEqual(report["current_activation_id"], "ACT-FAMILY-A")

    def test_live_active_ignores_historical_families(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-LIVE",
                "schedule_sha256": "a" * 64,
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-LIVE",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
            {
                "activation_id": "ACT-OLD-COMPLETE",
                "schedule_sha256": "b" * 64,
                "state": "COMPLETE",
                "cohort_family_key": "FAMILY-OLD",
                "updated_at": "2026-08-01T00:00:00Z",
                "created_at": "2026-07-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-OLD-ABORTED",
                "schedule_sha256": "c" * 64,
                "state": "ABORTED_SAFETY",
                "cohort_family_key": "FAMILY-OTHER",
                "updated_at": "2026-08-02T00:00:00Z",
                "created_at": "2026-07-02T00:00:00Z",
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "SCOPED")
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-LIVE")
        self.assertEqual(selected["state"], "ACTIVE")

    def test_same_family_active_beats_draining(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-DRAIN",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
            {
                "activation_id": "ACT-LIVE",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:02:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "SCOPED")
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-LIVE")

    def test_two_live_families_fail_closed(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-A",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:01:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-B",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-B",
                "updated_at": "2026-09-01T00:02:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "AMBIGUOUS")
        self.assertIsNone(select_current_activation(rows, now=now))

    def test_historical_families_without_live_row_are_not_ambiguous(self) -> None:
        now = datetime(2026, 9, 1, 0, 6, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-OLDER",
                "state": "COMPLETE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-08-01T00:00:00Z",
                "created_at": "2026-07-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-NEWER",
                "state": "ABORTED_SAFETY",
                "cohort_family_key": "FAMILY-B",
                "updated_at": "2026-08-15T00:00:00Z",
                "created_at": "2026-08-01T00:00:00Z",
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "NO_LIVE")
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-NEWER")
        report = classify_doctor_current_activation(rows, now=now)
        self.assertFalse(report["live_activation"])
        self.assertEqual(report["terminal"], "DOCTOR_ABORTED_SAFETY")
        self.assertEqual(report["current_activation_id"], "ACT-NEWER")

    def test_future_unknown_successor_does_not_hide_current_active(self) -> None:
        now = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-CURRENT",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-FUTURE",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:09:00Z",
                "created_at": "2026-09-01T00:09:00Z",
                "payload": {
                    "prior_state": "UNREGISTERED",
                    "transition_effective_at": "2026-09-01T00:20:00Z",
                },
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "SCOPED")
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-CURRENT")
        self.assertEqual(selected["state"], "ACTIVE")

    def test_future_other_family_is_not_a_second_live_family(self) -> None:
        now = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-CURRENT",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-FUTURE-OTHER",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-B",
                "updated_at": "2026-09-01T00:09:00Z",
                "created_at": "2026-09-01T00:09:00Z",
                "payload": {
                    "prior_state": "UNREGISTERED",
                    "transition_effective_at": "2026-09-01T00:20:00Z",
                },
            },
        ]
        self.assertEqual(activation_selection_status(rows, now=now), "SCOPED")
        self.assertEqual(activation_selection_status(rows), "AMBIGUOUS")
        selected = select_current_activation(rows, now=now)
        assert selected is not None
        self.assertEqual(selected["activation_id"], "ACT-CURRENT")

    def test_due_pressure_ignores_historical_backlog_when_one_active_is_current(self) -> None:
        from solana_alpha_lab.factory.observation_schedule import (
            load_observation_schedule,
            schedule_sha256,
        )
        from solana_alpha_lab.factory.observation_schedule_store import (
            ObservationScheduleStore,
        )

        now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
        live = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        historical = json.loads(json.dumps(live))
        historical["sampling"] = dict(historical["sampling"])
        historical["sampling"]["seed"] = 99001
        historical["schedule_key"] = "OBS-HISTORICAL-FAMILY"
        historical.pop("schedule_sha256", None)
        historical["schedule_sha256"] = schedule_sha256(historical)
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            for document, activation_id, state in (
                (live, "ACT-LIVE", "ACTIVE"),
                (historical, "ACT-OLD", "COMPLETE"),
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
                    "entity_id": "MintOld111111111111111111111111111111111",
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:00:00Z",
                    "deadline_at": "2026-09-01T00:05:00Z",
                    "payload": {},
                },
                clock=now,
            )
            model = build_collector_read_model(store, now=now)
            self.assertEqual(model["activation_selection_status"], "SCOPED")
            self.assertEqual(model["activation_id"], "ACT-LIVE")
            self.assertEqual(model["activation_state"], "ACTIVE")
            self.assertEqual(model["due_pressure"]["due_now_count"], 0)
            self.assertEqual(model["due_pressure"]["actually_overdue_count"], 0)
            self.assertNotIn("BACKLOG_RISK", model["health_flags"])
            store.close()

    def test_operational_packet_does_not_inherit_historical_publication_stall(self) -> None:
        from solana_alpha_lab.factory.collector_operational_packet import (
            build_collector_operational_packet,
        )
        from solana_alpha_lab.factory.observation_schedule import (
            load_observation_schedule,
            schedule_sha256,
        )
        from solana_alpha_lab.factory.observation_schedule_store import (
            ObservationScheduleStore,
        )
        from solana_alpha_lab.factory.operability_watch import classify_incidents

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
            self.assertEqual(packet["publication_jobs_open_count"], 0)
            classes = set(packet["health_classes"])
            self.assertNotIn("RDP_PUBLICATION_STALE", classes)
            self.assertNotIn("PUBLICATION_STUCK", classify_incidents(packet))
            store.close()

    def test_operability_watch_import_does_not_eagerly_load_research_dependencies(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        code = (
            "import sys; "
            "import solana_alpha_lab.factory.operability_watch; "
            "print('lifecycle=' + str('solana_alpha_lab.factory.observation_schedule_lifecycle' in sys.modules)); "
            "print('research=' + str('solana_alpha_lab.factory.research_store' in sys.modules)); "
            "print('duckdb=' + str('duckdb' in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            result.stdout.splitlines(),
            ["lifecycle=False", "research=False", "duckdb=False"],
        )


if __name__ == "__main__":
    unittest.main()
