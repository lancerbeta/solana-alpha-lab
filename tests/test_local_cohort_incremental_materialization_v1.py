from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.live_cohort_discovery_release import (
    LiveCohortReleaseError,
    bound_schedule_from_rdp,
    _cohort_members_into_sqlite,
    build_live_observation_source_from_rdp,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    extraction_counters,
    reset_extraction_counters,
)
from solana_alpha_lab.factory.members_snapshot_delta import (
    MembersDeltaError,
    append_delta_publication,
    canonical_unit_files_binding,
    canonical_unit_noop_transitions,
    _fingerprint_sqlite,
    _invalidate_operational_latest,
    _operational_latest_paths,
    _refresh_canonical_files_binding,
    reconstruct_stats,
    reset_fingerprint_work,
    _try_extend_operational_latest,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.live_cohort_to_forge import synthetic_closed_receipt
from solana_alpha_lab.factory.observation_panel_publisher import (
    persist_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule import (
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
)


SCHEDULE_SHA256 = "a" * 64
ACTIVATION_ID = "ACT-LOCAL-COHORT-INCREMENTAL-V1"
WINDOW_START = datetime(2026, 9, 2, 11, 19, tzinfo=UTC)
WINDOW_END = WINDOW_START + timedelta(days=7)
PRODUCER_A = "a" * 40
PRODUCER_B = "b" * 40


def _member(entity_id: str, *, schedule_sha256: str = SCHEDULE_SHA256) -> dict[str, str]:
    stamp = "2026-09-03T00:00:00Z"
    return {
        "schedule_sha256": schedule_sha256,
        "activation_id": ACTIVATION_ID,
        "entity_id": entity_id,
        "mint": entity_id,
        "discovery_first_reliable_available_at": stamp,
        "first_reliable_available_at": stamp,
        "discovery_available_at": stamp,
        "authoritative_anchor": stamp,
        "membership_state": "OBSERVED",
        "candidate_state": "ADMITTED",
        "inclusion_probability": "0.0425",
        "sampling_seed": "LOCAL-TEST",
    }


def _lifecycle_row(
    location: str, effective_at: datetime, producer_git_sha: str
) -> dict[str, object]:
    return {
        "kind": "OBSERVATION_MEMBER_BATCH",
        "effective_at": effective_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer_git_sha": producer_git_sha,
        "payload": {"member_location": location},
    }


def _schedule() -> dict[str, object]:
    schedule = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    schedule = dict(schedule)
    schedule.pop("schedule_sha256", None)
    schedule["activation"] = {
        **dict(schedule.get("activation") or {}),
        "starts_at": "2026-09-02T11:19:00Z",
        "stops_admitting_at": "2026-09-23T11:19:00Z",
        "cadence_alignment": "UTC_EPOCH",
    }
    validated = validate_observation_schedule(schedule, root=ROOT)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


def _append_member_event(
    data_root: Path,
    *,
    digest: str,
    location: str,
    effective_at: datetime,
    producer_git_sha: str,
    record_id: str,
) -> None:
    payload = {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION_ID,
        "dataset_manifest_id": record_id,
        "member_location": location,
        "row_count": 2,
        "discovery_coverage_class": "GAP_SUSPECTED",
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    transaction_id = f"RESEARCH-TXN-{record_id}"
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.OBSERVATION_MEMBER_BATCH,
        entity_id=digest,
        hypothesis_version_id=None,
        run_id=ACTIVATION_ID,
        transaction_id=transaction_id,
        effective_at=effective_at,
        first_reliable_available_at=effective_at,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
        producer_git_sha=producer_git_sha,
        created_at=effective_at,
    )
    ResearchStore(data_root).append([event], transaction_id=transaction_id)


class LocalCohortIncrementalMaterializationTests(unittest.TestCase):
    def test_cold_materialization_replays_each_requested_pit_once(self) -> None:
        """Each requested PIT is exact and is not reconstructed twice per location."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()

            unit_a = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-a-anchor",
                rows=[_member("a-0")],
            )
            unit_a = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-a-tail",
                rows=[
                    _member("a-0"),
                    _member("a-1"),
                ],
            )
            unit_b = write_snapshot_unit(
                data_root,
                utc_day="20260903",
                dataset_manifest_id="unit-b-anchor",
                rows=[_member("b-0")],
            )
            unit_b = append_delta_publication(
                data_root,
                utc_day="20260903",
                dataset_manifest_id="unit-b-tail",
                rows=[
                    _member("b-0"),
                    _member("b-1"),
                ],
            )

            a_tail = str(unit_a["publications"][-1]["rel"])
            a_anchor = str(unit_a["publications"][0]["rel"])
            b_tail = str(unit_b["publications"][-1]["rel"])
            b_anchor = str(unit_b["publications"][0]["rel"])
            lifecycle_rows = [
                _lifecycle_row(a_tail, WINDOW_START + timedelta(minutes=4), PRODUCER_A),
                _lifecycle_row(b_tail, WINDOW_START + timedelta(minutes=3), PRODUCER_B),
                _lifecycle_row(a_anchor, WINDOW_START + timedelta(minutes=2), PRODUCER_A),
                _lifecycle_row(b_anchor, WINDOW_START + timedelta(minutes=1), PRODUCER_B),
            ]
            for utc_day in ("20260902", "20260903"):
                _invalidate_operational_latest(
                    data_root
                    / "datasets"
                    / "members_snapshot_plus_delta"
                    / utc_day
                )

            extract_path = data_root / "extract.sqlite"
            conn = sqlite3.connect(extract_path)
            try:
                reset_extraction_counters()
                reset_fingerprint_work()
                _producers, member_count = _cohort_members_into_sqlite(
                    data_root,
                    conn=conn,
                    lifecycle_rows=lifecycle_rows,
                    window_start=WINDOW_START,
                    window_end=WINDOW_END,
                    schedule_sha256=SCHEDULE_SHA256,
                    activation_id=ACTIVATION_ID,
                    sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                    sampling_seed="LOCAL-TEST",
                    inclusion_probability="0.0425",
                )
                self.assertEqual(member_count, 4)
            finally:
                conn.close()

            counters = extraction_counters()
            stats = reconstruct_stats()
            self.assertEqual(stats["reconstruct_calls"], 4)
            self.assertEqual(counters["member_snapshot_full_column_scans"], 4)
            self.assertEqual(counters["full_member_row_materializations"], 6)

    def test_warm_source_rebuild_reuses_exact_unit_tail_cache(self) -> None:
        """A second identical source build must not replay canonical member history."""

        schedule = _schedule()
        digest = str(schedule["schedule_sha256"])
        cohort_id = "REL-20260902T111900Z-20260909T111900Z"
        as_of = datetime(2026, 9, 10, 16, 58, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            persist_observation_schedule(
                data_root=data_root,
                schedule=schedule,
                now=WINDOW_START,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION_ID,
            )

            unit_a = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-a-anchor",
                rows=[_member("a-0", schedule_sha256=digest)],
            )
            unit_a = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-a-tail",
                rows=[
                    _member("a-0", schedule_sha256=digest),
                    _member("a-1", schedule_sha256=digest),
                ],
            )
            unit_b = write_snapshot_unit(
                data_root,
                utc_day="20260903",
                dataset_manifest_id="unit-b-anchor",
                rows=[_member("b-0", schedule_sha256=digest)],
            )
            unit_b = append_delta_publication(
                data_root,
                utc_day="20260903",
                dataset_manifest_id="unit-b-tail",
                rows=[
                    _member("b-0", schedule_sha256=digest),
                    _member("b-1", schedule_sha256=digest),
                ],
            )
            _append_member_event(
                data_root,
                digest=digest,
                location=str(unit_a["publications"][-1]["rel"]),
                effective_at=WINDOW_START + timedelta(minutes=4),
                producer_git_sha=PRODUCER_A,
                record_id="MEMBER-A-TAIL",
            )
            _append_member_event(
                data_root,
                digest=digest,
                location=str(unit_b["publications"][-1]["rel"]),
                effective_at=WINDOW_START + timedelta(minutes=3),
                producer_git_sha=PRODUCER_B,
                record_id="MEMBER-B-TAIL",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=cohort_id,
                as_of=as_of,
                members_total=4,
            )
            for utc_day in ("20260902", "20260903"):
                _invalidate_operational_latest(
                    data_root
                    / "datasets"
                    / "members_snapshot_plus_delta"
                    / utc_day
                )

            _bound_schedule, _schedule_producer, lifecycle = bound_schedule_from_rdp(
                data_root, schedule_sha256=digest, activation_id=ACTIVATION_ID
            )
            self.assertEqual(
                {
                    str(row["payload"]["member_location"])
                    for row in lifecycle
                    if row.get("kind") == "OBSERVATION_MEMBER_BATCH"
                },
                {
                    str(unit_a["publications"][-1]["rel"]),
                    str(unit_b["publications"][-1]["rel"]),
                },
            )
            reset_extraction_counters()
            reset_fingerprint_work()
            cold = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=cohort_id,
                as_of=as_of,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            cold_stats = reconstruct_stats()
            self.assertEqual(cold["member_count"], 4)
            self.assertEqual(cold_stats["reconstruct_calls"], 2)

            reset_extraction_counters()
            reset_fingerprint_work()
            warm = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=cohort_id,
                as_of=as_of,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            warm_counters = extraction_counters()
            warm_stats = reconstruct_stats()
            self.assertEqual(warm["source_sha256"], cold["source_sha256"])
            self.assertEqual(warm["member_count"], 4)
            self.assertEqual(warm_stats["reconstruct_calls"], 0)
            self.assertEqual(warm_counters["member_snapshot_full_column_scans"], 0)
            self.assertEqual(warm_counters["member_snapshot_admission_probes"], 0)

    def test_older_removed_member_pit_preserves_cold_warm_source_parity(self) -> None:
        """An older PIT is replayed exactly instead of consuming the newer tail."""

        schedule = _schedule()
        digest = str(schedule["schedule_sha256"])
        cohort_id = "REL-20260902T111900Z-20260909T111900Z"
        as_of = datetime(2026, 9, 10, 16, 58, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            persist_observation_schedule(
                data_root=data_root,
                schedule=schedule,
                now=WINDOW_START,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION_ID,
            )
            unit = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-anchor",
                rows=[
                    _member("removed-anchor", schedule_sha256=digest),
                    _member("retained", schedule_sha256=digest),
                ],
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-tail",
                rows=[
                    _member("retained", schedule_sha256=digest),
                    _member("new-tail", schedule_sha256=digest),
                ],
            )
            tail_location = str(unit["publications"][-1]["rel"])
            anchor_location = str(unit["publications"][0]["rel"])
            _append_member_event(
                data_root,
                digest=digest,
                location=tail_location,
                effective_at=WINDOW_START + timedelta(minutes=2),
                producer_git_sha=PRODUCER_A,
                record_id="MEMBER-TAIL",
            )
            _append_member_event(
                data_root,
                digest=digest,
                location=anchor_location,
                effective_at=WINDOW_START + timedelta(minutes=1),
                producer_git_sha=PRODUCER_A,
                record_id="MEMBER-ANCHOR",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=cohort_id,
                as_of=as_of,
                members_total=3,
            )
            _invalidate_operational_latest(
                data_root / "datasets/members_snapshot_plus_delta/20260902"
            )
            reset_extraction_counters()
            reset_fingerprint_work()
            cold = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=cohort_id,
                as_of=as_of,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(cold["member_count"], 3)
            cold_stats = reconstruct_stats()
            self.assertEqual(cold_stats["reconstruct_calls"], 2)
            self.assertEqual(cold_stats["anchor_loads"], 2)

            reset_extraction_counters()
            reset_fingerprint_work()
            warm = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=cohort_id,
                as_of=as_of,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            warm_stats = reconstruct_stats()
            warm_counters = extraction_counters()
            self.assertEqual(warm["source_sha256"], cold["source_sha256"])
            self.assertEqual(warm["member_count"], 3)
            self.assertEqual(warm_stats["reconstruct_calls"], 1)
            self.assertEqual(warm_stats["anchor_loads"], 1)
            self.assertEqual(warm_counters["member_checkpoint_hits"], 1)
            self.assertEqual(warm_counters["member_checkpoint_misses"], 1)

            meta_path = (
                data_root
                / "datasets/members_snapshot_plus_delta/20260902"
                / ".operational_latest_members.meta.json"
            )
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["schema_version"], "3.0")
            self.assertTrue(meta["canonical_unit_sha256"])
            self.assertTrue(meta["canonical_unit_files_sha256"])
            cache_conn = sqlite3.connect(meta_path.with_suffix("").with_suffix(".sqlite"))
            try:
                tables = {
                    str(row[0])
                    for row in cache_conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                cache_conn.close()
            self.assertNotIn("history_ops", tables)

    def test_non_monotonic_removal_history_falls_back_to_exact_pit_replay(self) -> None:
        """A remove/re-add/remove chain must not use removal-only recovery."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            unit = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-anchor",
                rows=[_member("recycled")],
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-removed",
                rows=[],
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-readded",
                rows=[_member("recycled")],
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-tail",
                rows=[],
            )
            tail_location = str(unit["publications"][-1]["rel"])
            removed_location = str(unit["publications"][1]["rel"])
            conn = sqlite3.connect(data_root / "pit.sqlite")
            try:
                reset_extraction_counters()
                reset_fingerprint_work()
                _producers, member_count = _cohort_members_into_sqlite(
                    data_root,
                    conn=conn,
                    lifecycle_rows=[
                        _lifecycle_row(
                            tail_location, WINDOW_START + timedelta(minutes=2), PRODUCER_A
                        ),
                        _lifecycle_row(
                            removed_location, WINDOW_START + timedelta(minutes=1), PRODUCER_A
                        ),
                    ],
                    window_start=WINDOW_START,
                    window_end=WINDOW_END,
                    schedule_sha256=SCHEDULE_SHA256,
                    activation_id=ACTIVATION_ID,
                    sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                    sampling_seed="LOCAL-TEST",
                    inclusion_probability="0.0425",
                )
                self.assertEqual(member_count, 0)
            finally:
                conn.close()

            self.assertEqual(reconstruct_stats()["reconstruct_calls"], 1)

    def test_older_pit_target_does_not_consume_newer_tail_cache(self) -> None:
        """A newer durable tail cache cannot satisfy an earlier PIT target."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            unit = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-anchor",
                rows=[_member("anchor-only")],
            )
            changed_tail_member = _member("anchor-only")
            changed_tail_member["inclusion_probability"] = "0.99"
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-tail",
                rows=[changed_tail_member, _member("tail-only")],
            )
            anchor_location = str(unit["publications"][0]["rel"])
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260902"
            tail_meta_path = unit_dir / ".operational_latest_members.meta.json"
            tail_meta = json.loads(tail_meta_path.read_text(encoding="utf-8"))
            self.assertEqual(tail_meta["dataset_manifest_id"], "unit-tail")

            conn = sqlite3.connect(data_root / "pit.sqlite")
            try:
                reset_extraction_counters()
                reset_fingerprint_work()
                _producers, member_count = _cohort_members_into_sqlite(
                    data_root,
                    conn=conn,
                    lifecycle_rows=[
                        _lifecycle_row(anchor_location, WINDOW_START, PRODUCER_A)
                    ],
                    window_start=WINDOW_START,
                    window_end=WINDOW_END,
                    schedule_sha256=SCHEDULE_SHA256,
                    activation_id=ACTIVATION_ID,
                    sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                    sampling_seed="LOCAL-TEST",
                    inclusion_probability="0.0425",
                )
                self.assertEqual(member_count, 1)
                self.assertEqual(
                    conn.execute("SELECT mint FROM members").fetchone()[0],
                    "anchor-only",
                )
                payload = json.loads(
                    conn.execute("SELECT payload_json FROM members").fetchone()[0]
                )
                self.assertEqual(payload["inclusion_probability"], "0.0425")
            finally:
                conn.close()

            self.assertEqual(reconstruct_stats()["reconstruct_calls"], 1)
            self.assertEqual(extraction_counters()["member_checkpoint_hits"], 0)
            self.assertEqual(extraction_counters()["member_checkpoint_misses"], 1)
            preserved_tail_meta = json.loads(
                tail_meta_path.read_text(encoding="utf-8")
            )
            self.assertEqual(preserved_tail_meta["dataset_manifest_id"], "unit-tail")

    def test_new_tail_extends_previous_latest_cache_without_full_replay(self) -> None:
        """A lagging latest cache advances by one verified canonical delta."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            unit = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-anchor",
                rows=[_member("kept")],
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-tail-1",
                rows=[_member("kept"), _member("first")],
            )
            unit_dir = data_root / "datasets/members_snapshot_plus_delta/20260902"
            db_path, meta_path = _operational_latest_paths(unit_dir)
            previous_cache = (db_path.read_bytes(), meta_path.read_bytes())
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-tail-2",
                rows=[_member("kept"), _member("first"), _member("second")],
            )
            # Recreate the realistic lagging-cache window after canonical append.
            db_path.write_bytes(previous_cache[0])
            meta_path.write_bytes(previous_cache[1])

            reset_fingerprint_work()
            extended = _try_extend_operational_latest(
                data_root,
                unit_dir,
                unit,
                unit["publications"][-1],
            )
            self.assertIsNotNone(extended)
            spill, conn = extended
            try:
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]),
                    3,
                )
                self.assertEqual(
                    _fingerprint_sqlite(conn),
                    unit["publications"][-1]["snapshot_fingerprint"],
                )
            finally:
                conn.close()
                spill.unlink(missing_ok=True)
            stats = reconstruct_stats()
            self.assertEqual(stats["reconstruct_calls"], 0)
            self.assertEqual(stats["incremental_extensions"], 1)
            self.assertEqual(stats["delta_files_applied"], 1)

    def test_canonical_file_binding_rejects_same_stat_byte_mutation(self) -> None:
        """A preserved size/mtime cannot make altered canonical bytes trusted."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            unit = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-anchor",
                rows=[_member("kept")],
            )
            path = data_root / unit["publications"][0]["rel"]
            original_stat = path.stat()
            payload = bytearray(path.read_bytes())
            payload[-1] ^= 1
            path.write_bytes(payload)
            os.utime(
                path,
                ns=(int(original_stat.st_atime_ns), int(original_stat.st_mtime_ns)),
            )
            with self.assertRaisesRegex(MembersDeltaError, "CANONICAL_FILE_HASH_MISMATCH"):
                canonical_unit_files_binding(data_root, unit)

    def test_noop_proof_rejects_false_zero_counts_with_real_delta_ops(self) -> None:
        """A delta with real ops cannot become a cache-reuse no-op by metadata."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            unit = write_snapshot_unit(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-anchor",
                rows=[_member("kept")],
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260902",
                dataset_manifest_id="unit-tail",
                rows=[_member("kept"), _member("added")],
            )
            anchor = unit["publications"][0]
            tail = unit["publications"][-1]
            tail["row_count"] = anchor["row_count"]
            tail["snapshot_fingerprint"] = anchor["snapshot_fingerprint"]
            tail["current_fingerprint"] = anchor["snapshot_fingerprint"]
            tail["delta_counts"] = {"added": 0, "changed": 0, "removed": 0}
            _refresh_canonical_files_binding(unit)

            transitions = canonical_unit_noop_transitions(data_root, unit)

            self.assertEqual(transitions, (True, False))

    def test_snapshot_plus_delta_unit_path_escape_fails_closed(self) -> None:
        """A sidecar cannot redirect canonical replay or cache outside the RDP root."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            sidecar = data_root / "unit" / "members.layout.json"
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text(
                json.dumps(
                    {
                        "kind": "SNAPSHOT_PLUS_DELTA",
                        "unit_rel": "../outside/unit.json",
                        "dataset_manifest_id": "unit-tail",
                    }
                ),
                encoding="utf-8",
            )
            conn = sqlite3.connect(data_root / "pit.sqlite")
            try:
                with self.assertRaises(LiveCohortReleaseError) as context:
                    _cohort_members_into_sqlite(
                        data_root,
                        conn=conn,
                        lifecycle_rows=[
                            _lifecycle_row(
                                "unit/members.parquet", WINDOW_START, PRODUCER_A
                            )
                        ],
                        window_start=WINDOW_START,
                        window_end=WINDOW_END,
                        schedule_sha256=SCHEDULE_SHA256,
                        activation_id=ACTIVATION_ID,
                        sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                        sampling_seed="LOCAL-TEST",
                        inclusion_probability="0.0425",
                    )
            finally:
                conn.close()
            self.assertEqual(
                str(context.exception), "LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE"
            )


if __name__ == "__main__":
    unittest.main()
