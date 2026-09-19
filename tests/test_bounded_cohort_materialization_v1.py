"""Bounded cohort materialization: prefix walk, predecessor bound, lock, wall."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.bounded_cohort_materialization import (
    BOUNDED_WORK_CLASS,
    BUILD_ALREADY_RUNNING,
    BoundedMaterializationError,
    CohortBuildLock,
    UNBOUNDED_PLAN,
    WALL_BUDGET_EXCEEDED,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    LiveCohortReleaseError,
    _cohort_members_into_sqlite,
    build_live_observation_source_from_rdp,
    cohort_source_dir,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    SOURCE_MANIFEST_NAME,
    SOURCE_STAGING_PREFIX,
    extraction_counters,
    reset_extraction_counters,
)
from solana_alpha_lab.factory.live_cohort_to_forge import synthetic_closed_receipt
from solana_alpha_lab.factory.members_snapshot_delta import (
    LEGACY_KIND,
    append_delta_publication,
    reconstruct_stats,
    reset_fingerprint_work,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.observation_panel_publisher import persist_observation_schedule
from solana_alpha_lab.factory.observation_schedule import (
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore
from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id

ACTIVATION_ID = "ACT-BOUNDED-COHORT-V1"
WINDOW_START = datetime(2026, 9, 9, 11, 19, tzinfo=UTC)
WINDOW_END = WINDOW_START + timedelta(days=7)
PRODUCER = "a" * 40
COHORT_ID = "REL-20260909T111900Z-20260916T111900Z"
AS_OF = datetime(2026, 9, 17, 11, 19, tzinfo=UTC)


def _member(entity_id: str, *, admit: datetime, digest: str, state: str = "OBSERVED") -> dict[str, str]:
    stamp = admit.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION_ID,
        "entity_id": entity_id,
        "mint": entity_id,
        "discovery_first_reliable_available_at": stamp,
        "first_reliable_available_at": stamp,
        "discovery_available_at": stamp,
        "authoritative_anchor": stamp,
        "membership_state": state,
        "candidate_state": "ADMITTED",
        "inclusion_probability": "0.0425",
        "sampling_seed": "BOUNDED-TEST",
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


def _append_event(
    data_root: Path,
    *,
    record_id: str,
    kind: RecordKind,
    digest: str,
    payload: dict,
    now: datetime,
    txn: str,
) -> None:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=digest,
        hypothesis_version_id=None,
        run_id=ACTIVATION_ID,
        transaction_id=txn,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
        producer_git_sha=PRODUCER,
        created_at=now,
    )
    ResearchStore(data_root).append([event], transaction_id=txn)


def _lifecycle_member(location: str, effective_at: datetime, index: int) -> dict[str, object]:
    return {
        "kind": "OBSERVATION_MEMBER_BATCH",
        "effective_at": effective_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer_git_sha": PRODUCER,
        "payload": {"member_location": location},
        "_source_index": index,
    }


def _write_legacy(data_root: Path, rel: str, rows: list[dict[str, str]]) -> None:
    path = data_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="zstd")
    sidecar = path.with_name("members.layout.json")
    sidecar.write_text(
        json.dumps({"kind": LEGACY_KIND, "dataset_manifest_id": "legacy"}, indent=2),
        encoding="utf-8",
    )


def _publish_obs(
    data_root: Path,
    *,
    digest: str,
    now: datetime,
    tag: str,
    rows: list[dict[str, object]],
    member_rel: str,
) -> str:
    obs_rel = f"datasets/parquet/{tag}/observations.parquet"
    obs_path = data_root / obs_rel
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), obs_path, compression="zstd")
    dataset_id = f"observation-panel-{digest[:12]}"
    dataset_version = f"{now.strftime('%Y%m%d')}-1-{tag}"
    dataset_manifest_id = compute_dataset_manifest_id(dataset_id, dataset_version)
    manifests = data_root / "datasets" / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    obs_part = {
        "partition_manifest_id": f"partition-{tag}-obs",
        "dataset_manifest_id": dataset_manifest_id,
        "partition_id": f"utc-day-{now.strftime('%Y%m%d')}",
        "logical_location": obs_rel,
    }
    manifest = {
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_reliable_available_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "partitions": [obs_part],
    }
    (manifests / f"{dataset_manifest_id}.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    _append_event(
        data_root,
        record_id=f"OBS-BATCH-{tag}",
        kind=RecordKind.OBSERVATION_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "row_count": len(rows),
        },
        now=now,
        txn=f"RESEARCH-TXN-OBS-{tag.upper()[:12]}",
    )
    _append_event(
        data_root,
        record_id=f"OBS-MEMB-{tag}",
        kind=RecordKind.OBSERVATION_MEMBER_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "member_location": member_rel,
            "row_count": 1,
        },
        now=now,
        txn=f"RESEARCH-TXN-MEM-{tag.upper()[:12]}",
    )
    return dataset_manifest_id


class BoundedCohortMaterializationTests(unittest.TestCase):
    def test_a_prefix_walk_applies_each_delta_at_most_once(self) -> None:
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = write_snapshot_unit(
                root,
                utc_day="20260909",
                dataset_manifest_id="m-000",
                rows=[_member("keep", admit=WINDOW_START + timedelta(hours=1), digest=digest)],
            )
            for index in range(1, 201):
                unit = append_delta_publication(
                    root,
                    utc_day="20260909",
                    dataset_manifest_id=f"m-{index:03d}",
                    rows=[
                        _member("keep", admit=WINDOW_START + timedelta(hours=1), digest=digest),
                        _member(
                            f"add{index}",
                            admit=WINDOW_START + timedelta(hours=1),
                            digest=digest,
                        ),
                    ],
                )
            lifecycle = [
                _lifecycle_member(str(pub["rel"]), WINDOW_START + timedelta(minutes=i), i)
                for i, pub in enumerate(unit["publications"])
            ]
            conn = sqlite3.connect(":memory:")
            reset_extraction_counters()
            reset_fingerprint_work()
            _producers, count = _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=lifecycle,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            conn.close()
            stats = reconstruct_stats()
            self.assertEqual(stats["prefix_walks"], 1)
            self.assertEqual(stats["delta_files_applied"], 200)
            self.assertEqual(stats["historical_independent_reconstruct_calls"], 0)
            self.assertEqual(stats["unique_target_seq_consumed"], 201)
            self.assertEqual(count, 201)

    def test_b_later_seq_cannot_satisfy_earlier_pit(self) -> None:
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = write_snapshot_unit(
                root,
                utc_day="20260909",
                dataset_manifest_id="early",
                rows=[_member("only-early", admit=WINDOW_START + timedelta(hours=1), digest=digest)],
            )
            unit = append_delta_publication(
                root,
                utc_day="20260909",
                dataset_manifest_id="late",
                rows=[
                    _member("only-early", admit=WINDOW_START + timedelta(hours=1), digest=digest),
                    _member("only-late", admit=WINDOW_START + timedelta(hours=1), digest=digest),
                ],
            )
            early_only = [
                _lifecycle_member(str(unit["publications"][0]["rel"]), WINDOW_START, 0)
            ]
            conn = sqlite3.connect(":memory:")
            reset_fingerprint_work()
            _producers, count = _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=early_only,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            mints = {row[0] for row in conn.execute("SELECT mint FROM members")}
            conn.close()
            self.assertEqual(mints, {"only-early"})
            self.assertEqual(count, 1)
            self.assertEqual(reconstruct_stats()["delta_files_applied"], 0)

    def test_c_predecessor_preserves_boundary_admission(self) -> None:
        digest = "a" * 64
        admit = WINDOW_START + timedelta(seconds=30)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pred = write_snapshot_unit(
                root,
                utc_day="20260908",
                dataset_manifest_id="pred",
                rows=[_member("straddle", admit=admit, digest=digest)],
            )
            inside = write_snapshot_unit(
                root,
                utc_day="20260910",
                dataset_manifest_id="inside",
                rows=[
                    _member("straddle", admit=admit, digest=digest),
                    _member("later", admit=WINDOW_START + timedelta(days=1), digest=digest),
                ],
            )
            older = write_snapshot_unit(
                root,
                utc_day="20260905",
                dataset_manifest_id="older",
                rows=[_member("too-old-only", admit=admit, digest=digest)],
            )
            lifecycle = [
                _lifecycle_member(str(older["publications"][0]["rel"]), WINDOW_START - timedelta(days=4), 0),
                _lifecycle_member(str(pred["publications"][0]["rel"]), WINDOW_START - timedelta(minutes=5), 1),
                _lifecycle_member(str(inside["publications"][0]["rel"]), WINDOW_START + timedelta(hours=2), 2),
            ]
            conn = sqlite3.connect(":memory:")
            _producers, count = _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=lifecycle,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            mints = {row[0] for row in conn.execute("SELECT mint FROM members")}
            conn.close()
            self.assertIn("straddle", mints)
            self.assertIn("later", mints)
            self.assertNotIn("too-old-only", mints)
            self.assertEqual(count, 2)

    def test_e_first_publication_inside_cohort_needs_no_predecessor(self) -> None:
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = write_snapshot_unit(
                root,
                utc_day="20260910",
                dataset_manifest_id="first",
                rows=[_member("new", admit=WINDOW_START + timedelta(hours=2), digest=digest)],
            )
            lifecycle = [
                _lifecycle_member(str(unit["publications"][0]["rel"]), WINDOW_START + timedelta(hours=1), 0)
            ]
            conn = sqlite3.connect(":memory:")
            _producers, count = _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=lifecycle,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            conn.close()
            self.assertEqual(count, 1)

    def test_f_g_state_evolution_and_remove_parity(self) -> None:
        digest = "a" * 64
        admit = WINDOW_START + timedelta(hours=1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = write_snapshot_unit(
                root,
                utc_day="20260909",
                dataset_manifest_id="s0",
                rows=[
                    _member("keep", admit=admit, digest=digest, state="OBSERVED"),
                    _member("gone", admit=admit, digest=digest, state="OBSERVED"),
                ],
            )
            unit = append_delta_publication(
                root,
                utc_day="20260909",
                dataset_manifest_id="s1",
                rows=[_member("keep", admit=admit, digest=digest, state="SAMPLED_MEMBER")],
            )
            lifecycle = [
                _lifecycle_member(str(unit["publications"][0]["rel"]), WINDOW_START, 0),
                _lifecycle_member(str(unit["publications"][1]["rel"]), WINDOW_START + timedelta(minutes=1), 1),
            ]
            conn = sqlite3.connect(":memory:")
            _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=lifecycle,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            rows = {
                mint: json.loads(payload)
                for mint, payload in conn.execute("SELECT mint, payload_json FROM members")
            }
            conn.close()
            self.assertEqual(rows["keep"]["membership_state"], "SAMPLED_MEMBER")
            self.assertIn("gone", rows)

    def test_h_cross_unit_newest_wins_order_independent(self) -> None:
        digest = "a" * 64
        admit = WINDOW_START + timedelta(hours=1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = write_snapshot_unit(
                root,
                utc_day="20260909",
                dataset_manifest_id="older-unit",
                rows=[_member("shared", admit=admit, digest=digest, state="OBSERVED")],
            )
            newer = write_snapshot_unit(
                root,
                utc_day="20260910",
                dataset_manifest_id="newer-unit",
                rows=[_member("shared", admit=admit, digest=digest, state="SAMPLED_MEMBER")],
            )
            orders = [
                [
                    _lifecycle_member(str(older["publications"][0]["rel"]), WINDOW_START, 0),
                    _lifecycle_member(str(newer["publications"][0]["rel"]), WINDOW_START + timedelta(hours=1), 1),
                ],
                [
                    _lifecycle_member(str(newer["publications"][0]["rel"]), WINDOW_START + timedelta(hours=1), 1),
                    _lifecycle_member(str(older["publications"][0]["rel"]), WINDOW_START, 0),
                ],
            ]
            payloads = []
            for lifecycle in orders:
                conn = sqlite3.connect(":memory:")
                _cohort_members_into_sqlite(
                    root,
                    conn=conn,
                    lifecycle_rows=lifecycle,
                    window_start=WINDOW_START,
                    window_end=WINDOW_END,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION_ID,
                    sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                    sampling_seed="BOUNDED-TEST",
                    inclusion_probability="0.0425",
                )
                payloads.append(
                    json.loads(conn.execute("SELECT payload_json FROM members").fetchone()[0])
                )
                conn.close()
            self.assertEqual(payloads[0]["membership_state"], "SAMPLED_MEMBER")
            self.assertEqual(payloads[0], payloads[1])

    def test_i_legacy_location_read_once(self) -> None:
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = "datasets/parquet/legacy/members.parquet"
            _write_legacy(
                root,
                rel,
                [_member("legacy", admit=WINDOW_START + timedelta(hours=1), digest=digest)],
            )
            lifecycle = [
                _lifecycle_member(rel, WINDOW_START + timedelta(minutes=1), 0),
                _lifecycle_member(rel, WINDOW_START + timedelta(minutes=2), 1),
            ]
            conn = sqlite3.connect(":memory:")
            reset_extraction_counters()
            _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=lifecycle,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            conn.close()
            self.assertEqual(extraction_counters()["legacy_member_locations_read"], 1)

    def test_j_old_legacy_outside_bound_is_zero(self) -> None:
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_rel = "datasets/parquet/20260902/members.parquet"
            _write_legacy(
                root,
                old_rel,
                [_member("sep02", admit=WINDOW_START + timedelta(hours=1), digest=digest)],
            )
            pred = write_snapshot_unit(
                root,
                utc_day="20260908",
                dataset_manifest_id="pred",
                rows=[_member("pred", admit=WINDOW_START + timedelta(hours=1), digest=digest)],
            )
            current = write_snapshot_unit(
                root,
                utc_day="20260910",
                dataset_manifest_id="cur",
                rows=[_member("cur", admit=WINDOW_START + timedelta(hours=2), digest=digest)],
            )
            lifecycle = [
                _lifecycle_member(old_rel, datetime(2026, 9, 2, 12, tzinfo=UTC), 0),
                _lifecycle_member(
                    str(pred["publications"][0]["rel"]),
                    WINDOW_START - timedelta(minutes=10),
                    1,
                ),
                _lifecycle_member(
                    str(current["publications"][0]["rel"]),
                    WINDOW_START + timedelta(hours=1),
                    2,
                ),
            ]
            conn = sqlite3.connect(":memory:")
            reset_extraction_counters()
            _producers, count = _cohort_members_into_sqlite(
                root,
                conn=conn,
                lifecycle_rows=lifecycle,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
                sampling_seed="BOUNDED-TEST",
                inclusion_probability="0.0425",
            )
            mints = {row[0] for row in conn.execute("SELECT mint FROM members")}
            conn.close()
            self.assertEqual(mints, {"pred", "cur"})
            self.assertEqual(extraction_counters()["legacy_member_locations_read"], 0)
            self.assertEqual(count, 2)

    def test_n_duplicate_build_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = CohortBuildLock(root, COHORT_ID, run_id="one", command_identity="build")
            first.acquire()
            second = CohortBuildLock(root, COHORT_ID, run_id="two", command_identity="build")
            started = time.monotonic()
            with self.assertRaises(BoundedMaterializationError) as ctx:
                second.acquire()
            elapsed = time.monotonic() - started
            first.release()
            self.assertEqual(str(ctx.exception), BUILD_ALREADY_RUNNING)
            self.assertLess(elapsed, 1.0)

    def test_n_two_threads_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            winner: list[int] = []
            loser: list[str] = []

            def _attempt(idx: int) -> None:
                lock = CohortBuildLock(root, COHORT_ID, run_id=str(idx), command_identity="build")
                try:
                    lock.acquire()
                except BoundedMaterializationError as exc:
                    loser.append(str(exc))
                    return
                winner.append(idx)
                time.sleep(0.2)
                lock.release()

            threads = [threading.Thread(target=_attempt, args=(i,)) for i in (1, 2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(winner), 1)
            self.assertEqual(loser, [BUILD_ALREADY_RUNNING])

    def test_k_l_o_p_observation_routing_crash_and_cleanup(self) -> None:
        schedule = _schedule()
        digest = str(schedule["schedule_sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "rdp"
            root.mkdir()
            persist_observation_schedule(
                data_root=root,
                schedule=schedule,
                now=WINDOW_START,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION_ID,
            )
            unit = write_snapshot_unit(
                root,
                utc_day="20260910",
                dataset_manifest_id="cur",
                rows=[_member("mint1", admit=WINDOW_START + timedelta(hours=2), digest=digest)],
            )
            member_rel = str(unit["publications"][0]["rel"])
            stamp = (WINDOW_START + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            _publish_obs(
                root,
                digest=digest,
                now=WINDOW_START + timedelta(hours=2),
                tag="obs1",
                member_rel=member_rel,
                rows=[
                    {
                        "schedule_sha256": digest,
                        "activation_id": ACTIVATION_ID,
                        "entity_id": "mint1",
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "event_time": stamp,
                        "first_reliable_available_at": stamp,
                        "request_sha256": "c" * 64,
                        "response_sha256": "d" * 64,
                        "call_occurrence_id": "e" * 64,
                        "http_status": 200,
                        "http_class": "HTTP_OK",
                        "field_values": [
                            {
                                "field_id": "FIELD-LIQUIDITY-USD-001",
                                "value_kind": "DECIMAL",
                                "typed_value": "1.25",
                                "state": "OBSERVED",
                            },
                            {
                                "field_id": "FIELD-MISSING-001",
                                "value_kind": "DECIMAL",
                                "state": "MISSING",
                                "missing_reason": "PROVIDER_EMPTY",
                            },
                        ],
                    }
                ],
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                as_of=AS_OF,
                members_total=1,
            )
            reset_extraction_counters()
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=root,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                as_of=AS_OF,
                closure_receipt=receipt,
            )
            self.assertEqual(source["member_count"], 1)
            self.assertGreaterEqual(source["observation_count"], 1)
            counters = extraction_counters()
            self.assertEqual(counters["global_manifest_markers_scanned"], 0)
            self.assertEqual(counters["historical_independent_reconstruct_calls"], 0)
            self.assertGreaterEqual(counters["unique_observation_locations_read"], 1)
            materialization = source["materialization"]
            self.assertEqual(materialization["historical_independent_reconstruct_calls"], 0)
            self.assertEqual(materialization["global_manifest_markers_scanned"], 0)
            self.assertTrue(materialization["owned_scratch_removed"])
            self.assertGreater(int(materialization["progress"]["scratch_peak_bytes"]), 0)
            source_dir = cohort_source_dir(root, COHORT_ID)
            leftover = [
                item
                for item in source_dir.iterdir()
                if item.is_dir() and item.name.startswith(SOURCE_STAGING_PREFIX)
            ]
            self.assertEqual(leftover, [])

            with patch(
                "solana_alpha_lab.factory.live_cohort_discovery_release.commit_source_bundle",
                side_effect=OSError("boom"),
            ):
                with self.assertRaises(OSError):
                    build_live_observation_source_from_rdp(
                        observation_rdp_root=root,
                        schedule_sha256=digest,
                        activation_id=ACTIVATION_ID,
                        cohort_id=COHORT_ID,
                        as_of=AS_OF,
                        closure_receipt=receipt,
                    )
            # Canonical bundle from the successful run must remain; crash must not
            # publish a replacement partial tree.
            self.assertTrue((source_dir / SOURCE_MANIFEST_NAME).is_file())

    def test_wall_budget_stops_without_partial_canonical(self) -> None:
        schedule = _schedule()
        digest = str(schedule["schedule_sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "rdp"
            root.mkdir()
            persist_observation_schedule(
                data_root=root,
                schedule=schedule,
                now=WINDOW_START,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION_ID,
            )
            unit = write_snapshot_unit(
                root,
                utc_day="20260910",
                dataset_manifest_id="cur",
                rows=[_member("mint1", admit=WINDOW_START + timedelta(hours=2), digest=digest)],
            )
            _append_event(
                root,
                record_id="MEM-CUR",
                kind=RecordKind.OBSERVATION_MEMBER_BATCH,
                digest=digest,
                payload={
                    "schedule_sha256": digest,
                    "dataset_manifest_id": "cur",
                    "member_location": str(unit["publications"][0]["rel"]),
                    "row_count": 1,
                },
                now=WINDOW_START + timedelta(hours=2),
                txn="RESEARCH-TXN-MEM-CURWALL01",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                as_of=AS_OF,
                members_total=1,
            )
            with self.assertRaises(LiveCohortReleaseError) as ctx:
                build_live_observation_source_from_rdp(
                    observation_rdp_root=root,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION_ID,
                    cohort_id=COHORT_ID,
                    as_of=AS_OF,
                    closure_receipt=receipt,
                    wall_budget_s=0.0,
                )
            self.assertEqual(str(ctx.exception), WALL_BUDGET_EXCEEDED)
            source_dir = cohort_source_dir(root, COHORT_ID)
            self.assertFalse((source_dir / SOURCE_MANIFEST_NAME).exists())

    def test_m_plan_and_scale_payload_does_not_grow_with_history(self) -> None:
        def _shape(history: int) -> dict[str, int]:
            schedule = _schedule()
            digest = str(schedule["schedule_sha256"])
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "rdp"
                root.mkdir()
                persist_observation_schedule(
                    data_root=root,
                    schedule=schedule,
                    now=datetime(2026, 9, 2, 11, 19, tzinfo=UTC),
                    producer_git_sha=PRODUCER,
                    activation_id=ACTIVATION_ID,
                )
                for index in range(history):
                    when = WINDOW_START - timedelta(days=history - index, hours=1)
                    _append_event(
                        root,
                        record_id=f"HIST-{index:04d}",
                        kind=RecordKind.OBSERVATION_MEMBER_BATCH,
                        digest=digest,
                        payload={
                            "schedule_sha256": digest,
                            "dataset_manifest_id": f"hist-{index}",
                            "member_location": f"datasets/parquet/hist-{index}/members.parquet",
                            "row_count": 1,
                        },
                        now=when,
                        txn=f"RESEARCH-TXN-MEM-H{index:04d}XXXX",
                    )
                unit = write_snapshot_unit(
                    root,
                    utc_day="20260910",
                    dataset_manifest_id="cur",
                    rows=[_member("mint1", admit=WINDOW_START + timedelta(hours=2), digest=digest)],
                )
                _append_event(
                    root,
                    record_id="MEM-CUR",
                    kind=RecordKind.OBSERVATION_MEMBER_BATCH,
                    digest=digest,
                    payload={
                        "schedule_sha256": digest,
                        "dataset_manifest_id": "cur",
                        "member_location": str(unit["publications"][0]["rel"]),
                        "row_count": 1,
                    },
                    now=WINDOW_START + timedelta(hours=2),
                    txn="RESEARCH-TXN-MEM-CURSHAPE01",
                )
                receipt = synthetic_closed_receipt(
                    schedule_sha256=digest,
                    activation_id=ACTIVATION_ID,
                    cohort_id=COHORT_ID,
                    as_of=AS_OF,
                    members_total=1,
                )
                plan = build_live_observation_source_from_rdp(
                    observation_rdp_root=root,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION_ID,
                    cohort_id=COHORT_ID,
                    as_of=AS_OF,
                    closure_receipt=receipt,
                    plan_only=True,
                )
                self.assertEqual(plan["work_class"], BOUNDED_WORK_CLASS)
                self.assertFalse(plan["slow_fallback_required"])
                self.assertEqual(plan["historical_independent_reconstruct_calls"], 0)
                self.assertEqual(plan["global_manifest_markers_scanned"], 0)
                return {
                    "headers": int(plan["research_manifest_headers_scanned"]),
                    "opened": int(plan["research_event_partitions_planned"]),
                    "decoded": int(plan["research_event_records_decoded"]),
                    "payload": int(plan["research_event_payload_bytes_read"]),
                    "members": int(plan["member_batches_selected"]),
                }

        c3 = _shape(3)
        c20 = _shape(20)
        c50 = _shape(50)
        c100 = _shape(100)
        self.assertLessEqual(c100["payload"] / max(c3["payload"], 1), 1.5)
        self.assertLessEqual(c100["members"] / max(c3["members"], 1), 1.5)
        self.assertGreaterEqual(c100["headers"], c3["headers"])
        self.assertEqual(c100["members"], c3["members"])


if __name__ == "__main__":
    unittest.main()
