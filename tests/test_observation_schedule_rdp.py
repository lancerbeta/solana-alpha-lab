from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore  # noqa: E402


GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


class ObservationScheduleRdpTests(unittest.TestCase):
    def test_batch_event_and_projection_views(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            published = publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
                members=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "entity_id": "MintA",
                        "event_time": "2026-09-01T00:05:00Z",
                    }
                ],
                observations=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "entity_id": "MintA",
                        "point_id": "X300",
                        "state": "OBSERVED",
                        "event_time": "2026-09-01T00:05:00Z",
                        "first_reliable_available_at": "2026-09-01T00:10:00Z",
                    }
                ],
            )
            store = ResearchStore(data_root)
            records = list(store.iter_committed_records())
            kinds = {item.record_kind for item in records}
            self.assertIn(RecordKind.OBSERVATION_BATCH.value, kinds)
            self.assertIn(RecordKind.OBSERVATION_SCHEDULE.value, kinds)
            receipt = store.rebuild_projection()
            self.assertGreaterEqual(receipt.record_count, 1)
            import duckdb

            connection = duckdb.connect(
                str(data_root / "projections" / "research_memory.duckdb"),
                read_only=True,
            )
            try:
                rows = connection.execute(
                    "SELECT dataset_manifest_id FROM observation_batches"
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual(rows[0][0], published["dataset_manifest_id"])

    def test_envelope_schema_includes_observation_kinds(self) -> None:
        schema = json.loads(
            (ROOT / "catalog/schemas/research_event_envelope.schema.json").read_text(
                encoding="utf-8"
            )
        )
        enum = schema["properties"]["record_kind"]["enum"]
        for kind in (
            "OBSERVATION_SCHEDULE",
            "OBSERVATION_SCHEDULE_AUTHORITY",
            "OBSERVATION_SCHEDULE_STATE",
            "OBSERVATION_MEMBER_BATCH",
            "OBSERVATION_BATCH",
            "OBSERVATION_PANEL_SNAPSHOT",
            "OBSERVATION_SCHEDULE_BINDING",
        ):
            self.assertIn(kind, enum)

    def test_snapshot_bind_writes_rdp_and_validates_passport(self) -> None:
        from solana_alpha_lab.factory.observation_panel_coverage import CoverageIndex
        from solana_alpha_lab.factory.observation_schedule_capability import (
            bind_observation_run_passport,
            compile_and_bind_observation_schedule,
        )

        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        requested = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        from solana_alpha_lab.factory.observation_panel_publisher import build_panel_snapshot

        snapshot = build_panel_snapshot(
            schedule_sha256=covering["schedule_sha256"],
            availability_cutoff=NOW,
            dataset_manifest_ids=["dataset-" + "b" * 64],
            dataset_fingerprints=["c" * 64],
        )
        index = CoverageIndex()
        index.add_snapshot(
            snapshot_sha256=snapshot["snapshot_sha256"],
            schedule=covering,
            availability_cutoff=NOW,
            first_y_available_at=datetime(2026, 8, 15, tzinfo=UTC),
            dataset_manifest_ids=list(snapshot["dataset_manifest_ids"]),
            dataset_fingerprints=list(snapshot["dataset_fingerprints"]),
        )
        payload = {
            "run_id": "RUN-OBS-BIND-001",
            "run_key_sha256": "d" * 64,
            "trial_id": "TRIAL-OBS-BIND-001",
            "hypothesis_version_id": "HYP-VERSION-OBS-BIND-001",
            "hypothesis_definition_sha256": "1" * 64,
            "experiment_spec_sha256": "2" * 64,
            "runner_capability_id": "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
            "runner_git_sha": "3" * 40,
            "capability_closure_sha256": "4" * 64,
            "uv_lock_sha256": "5" * 64,
            "dataset_manifest_ids": [],
            "dataset_fingerprints": [],
            "query_recipe_ids": [],
            "query_recipe_sha256s": [],
            "config_sha256": "6" * 64,
            "as_of": "2026-08-25T00:00:00Z",
            "availability_cutoff": "2026-08-25T00:00:00Z",
            "holdout_consumption_ids": [],
            "random_seed_or_null": None,
            "started_at": "2026-08-25T00:00:00Z",
            "completed_at": "2026-08-25T00:01:00Z",
            "first_reliable_available_at": "2026-08-25T00:01:00Z",
            "provider_calls_planned": 0,
            "provider_calls_actual": 0,
            "cash_spend_usd_cents": 0,
            "execution_status": "COMPLETE",
            "trial_outcome": "INCONCLUSIVE",
            "scientific_terminal": "INCONCLUSIVE",
            "result_digest_sha256": "7" * 64,
            "artifact_manifest_sha256": "8" * 64,
            "limitations": [],
            "non_claims": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            bound = compile_and_bind_observation_schedule(
                {
                    "observation_request": {
                        **requested,
                        "collection_mode": "REUSE_OR_SCHEDULE",
                        "requested_evidence_role": "EXPLORATORY_REUSE",
                    },
                    "availability_cutoff": "2026-09-01T12:00:00Z",
                    "as_of": "2026-09-01T12:00:00Z",
                },
                root=ROOT,
                coverage=index,
                data_root=data_root,
                producer_git_sha=GIT_SHA,
                hypothesis_version_id="HYP-VERSION-OBS-BIND-001",
                run_id="RUN-OBS-BIND-001",
                now=NOW,
            )
            self.assertEqual(bound["terminal"], "PANEL_REUSE_READY")
            store = ResearchStore(data_root)
            records = list(store.iter_committed_records())
            kinds = {item.record_kind for item in records}
            self.assertIn(RecordKind.OBSERVATION_SCHEDULE.value, kinds)
            self.assertIn(RecordKind.OBSERVATION_PANEL_SNAPSHOT.value, kinds)
            self.assertIn(RecordKind.OBSERVATION_SCHEDULE_BINDING.value, kinds)
            snapshot_payload = json.loads(
                next(
                    item.payload_json
                    for item in records
                    if item.record_kind == RecordKind.OBSERVATION_PANEL_SNAPSHOT.value
                )
            )
            self.assertEqual(snapshot_payload["snapshot_sha256"], snapshot["snapshot_sha256"])
            self.assertEqual(
                snapshot_payload["dataset_manifest_ids"],
                snapshot["dataset_manifest_ids"],
            )
            passport = bind_observation_run_passport(
                payload,
                observation_schedule_sha256=bound["passport_bindings"][
                    "observation_schedule_sha256"
                ],
                observation_panel_snapshot_sha256=bound["passport_bindings"][
                    "observation_panel_snapshot_sha256"
                ],
            )
            self.assertEqual(
                passport.observation_panel_snapshot_sha256,
                snapshot["snapshot_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
