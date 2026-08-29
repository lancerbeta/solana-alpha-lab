from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    rebuild_observation_panel_from_rdp,
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore  # noqa: E402


GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


class ObservationScheduleRdpTests(unittest.TestCase):
    def test_rebuild_preserves_typed_values_and_terminal_states_without_sqlite(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
                members=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": "ACT-OBS-001",
                        "entity_id": "MintA",
                        "membership_state": "ADMITTED",
                    }
                ],
                observations=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": "ACT-OBS-001",
                        "entity_id": "MintA",
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "state": "OBSERVED",
                        "event_time": "2026-09-01T00:05:00Z",
                        "first_reliable_available_at": "2026-09-01T00:10:07Z",
                        "request_started_at": "2026-09-01T00:10:00Z",
                        "response_received_at": "2026-09-01T00:10:07Z",
                        "request_sha256": "a" * 64,
                        "call_occurrence_id": "b" * 64,
                        "field_values": [
                            {
                                "field_id": "FIELD-LIQUIDITY-USD-001",
                                "value_kind": "DECIMAL",
                                "typed_value_or_null": "1234.50",
                                "state": "OBSERVED",
                                "missing_reason": None,
                                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                                "point_id": "X300",
                                "event_time": "2026-09-01T00:05:00Z",
                                "first_reliable_available_at": "2026-09-01T00:10:07Z",
                                "request_sha256": "a" * 64,
                                "call_occurrence_id": "b" * 64,
                            }
                        ],
                    },
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": "ACT-OBS-001",
                        "entity_id": "MintA",
                        "point_id": "Y900",
                        "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                        "state": "CENSORED_LATE",
                        "event_time": None,
                        "first_reliable_available_at": "2026-09-01T00:10:07Z",
                        "request_sha256": "c" * 64,
                        "call_occurrence_id": "d" * 64,
                        "missing_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                        "field_values": [
                            {
                                "field_id": "FIELD-QUOTE-SELL-OUT-AMOUNT-001",
                                "value_kind": "DECIMAL",
                                "typed_value_or_null": None,
                                "state": "CENSORED_LATE",
                                "missing_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                                "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                                "point_id": "Y900",
                                "event_time": None,
                                "first_reliable_available_at": "2026-09-01T00:10:07Z",
                                "request_sha256": "c" * 64,
                                "call_occurrence_id": "d" * 64,
                            }
                        ],
                    },
                ],
            )
            for path in data_root.glob("**/*.sqlite"):
                path.unlink()
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            self.assertEqual(len(rebuilt["members"]), 1)
            observations = {
                row["point_id"]: row for row in rebuilt["observations"]
            }
            x_values = {
                value["field_id"]: value
                for value in observations["X300"]["field_values"]
            }
            self.assertEqual(
                x_values["FIELD-LIQUIDITY-USD-001"]["typed_value_or_null"],
                "1234.50",
            )
            self.assertEqual(observations["Y900"]["state"], "CENSORED_LATE")
            self.assertEqual(
                observations["Y900"]["field_values"][0]["missing_reason"],
                "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
            )

    def test_rebuild_deduplicates_repeated_member_snapshots(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        member = {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": "ACT-OBS-001",
            "entity_id": "MintA",
            "membership_state": "ADMITTED",
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
                members=[member],
                observations=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": "ACT-OBS-001",
                        "entity_id": "MintA",
                        "point_id": "X300",
                        "state": "MISSING_TYPED",
                        "event_time": None,
                        "first_reliable_available_at": "2026-09-01T00:10:00Z",
                        "missing_reason": "FIRST",
                    }
                ],
            )
            publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW + timedelta(seconds=1),
                producer_git_sha=GIT_SHA,
                members=[{**member, "membership_state": "OBSERVED"}],
                observations=[
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": "ACT-OBS-001",
                        "entity_id": "MintA",
                        "point_id": "Y900",
                        "state": "MISSING_TYPED",
                        "event_time": None,
                        "first_reliable_available_at": "2026-09-01T00:10:01Z",
                        "missing_reason": "SECOND",
                    }
                ],
            )
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            self.assertEqual(len(rebuilt["members"]), 1)
            self.assertEqual(rebuilt["members"][0]["membership_state"], "OBSERVED")
            self.assertEqual(
                {row["point_id"] for row in rebuilt["observations"]},
                {"X300", "Y900"},
            )

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
        from solana_alpha_lab.factory.observation_panel_publisher import (
            build_panel_snapshot,
            persist_observation_schedule,
            persist_panel_snapshot_binding,
        )
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
        snapshot = build_panel_snapshot(
            schedule_sha256=covering["schedule_sha256"],
            availability_cutoff=NOW,
            dataset_manifest_ids=["dataset-" + "b" * 64],
            dataset_fingerprints=["c" * 64],
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
            persist_observation_schedule(
                data_root=data_root,
                schedule=covering,
                now=NOW,
                producer_git_sha=GIT_SHA,
            )
            persist_panel_snapshot_binding(
                data_root=data_root,
                schedule=covering,
                snapshot=snapshot,
                now=NOW,
                producer_git_sha=GIT_SHA,
                evidence_role="EXPLORATORY_REUSE",
                hypothesis_version_id="HYP-VERSION-OBS-BIND-001",
                run_id="RUN-OBS-BIND-001",
            )
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
