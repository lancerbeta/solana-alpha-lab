"""Memory-bounded live source bundle: 150k stress, complexity, crash-safety."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    LiveCohortReleaseError,
    build_live_observation_source_from_rdp,
    classify_cohort_readiness,
    load_observation_rdp_source,
    seal_live_cohort,
    verify_live_cohort,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (  # noqa: E402
    SOURCE_BUILD_RSS_CEILING_BYTES,
    SOURCE_MANIFEST_NAME,
    SOURCE_MEMBERS_NAME,
    SOURCE_OBSERVATIONS_NAME,
    SOURCE_STAGING_PREFIX,
    extraction_counters,
    peak_rss_bytes,
    reset_extraction_counters,
    sha256_file_streaming,
    source_build_child_was_resource_killed,
)
from solana_alpha_lab.factory.members_snapshot_delta import (  # noqa: E402
    append_delta_publication,
    iter_member_row_batches_for_location,
    reconstruct_stats,
    reset_fingerprint_work,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.live_cohort_to_forge import (  # noqa: E402
    assert_closure_ready,
    assert_source_matches_receipt,
    build_closure_receipt,
    synthetic_closed_receipt,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    persist_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id  # noqa: E402

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

PRODUCER_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
PRODUCER_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
PRODUCER_C = "cccccccccccccccccccccccccccccccccccccccc"
ACTIVATION = "ACT-619AE64E885E995E"
COHORT1 = "REL-20260902T111900Z-20260909T111900Z"
AS_OF_C1 = datetime(2026, 9, 10, 16, 58, 0, tzinfo=UTC)
C1_ADMIT = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
C2_ADMIT = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)
STRESS_MEMBERS = 150_000
STRESS_RSS_CEILING = SOURCE_BUILD_RSS_CEILING_BYTES
INTERPRETER = [
    sys.executable,
    "-B",
]


def _schedule(root: Path) -> dict:
    schedule = load_observation_schedule(
        root, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    schedule = dict(schedule)
    schedule.pop("schedule_sha256", None)
    schedule["activation"] = {
        **dict(schedule.get("activation") or {}),
        "starts_at": "2026-09-02T11:19:00Z",
        "stops_admitting_at": "2026-09-23T11:19:00Z",
        "cadence_alignment": "UTC_EPOCH",
    }
    schedule["sampling"] = {
        "policy": "DETERMINISTIC_HASH_BERNOULLI",
        "seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
        "inclusion_probability": "0.0425",
        "max_candidates_per_utc_day": 2000,
        "max_members_per_utc_day": 85,
        "overflow_state": "NOT_SELECTED_CAPACITY",
    }
    validated = validate_observation_schedule(schedule, root=root)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


def _member_row(digest: str, entity: str, admission: datetime) -> dict:
    stamp = admission.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION,
        "entity_id": entity,
        "membership_state": "OBSERVED",
        "candidate_state": "ADMITTED",
        "authoritative_anchor": stamp,
        "inclusion_probability": "0.0425",
        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
        "discovery_available_at": stamp,
        "first_reliable_available_at": stamp,
        "request_sha256": "a" * 64,
        "response_sha256": "b" * 64,
    }


def _obs_row(digest: str, entity: str, admission: datetime, *, available: datetime | None = None) -> dict:
    stamp = admission.strftime("%Y-%m-%dT%H:%M:%SZ")
    available_stamp = (available or (admission + timedelta(seconds=1))).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION,
        "entity_id": entity,
        "point_id": "X300",
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
        "event_time": stamp,
        "first_reliable_available_at": available_stamp,
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
            }
        ],
    }


def _write_parquet_batches(path: Path, rows_iter, batch_size: int = 2048) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    batch: list[dict] = []
    for row in rows_iter:
        batch.append(row)
        if len(batch) >= batch_size:
            table = pa.Table.from_pylist(batch)
            if writer is None:
                writer = pq.ParquetWriter(path, table.schema, compression="zstd")
            writer.write_table(table)
            batch = []
    if batch:
        table = pa.Table.from_pylist(batch)
        if writer is None:
            writer = pq.ParquetWriter(path, table.schema, compression="zstd")
        writer.write_table(table)
    if writer is not None:
        writer.close()
    return sha256_file_streaming(path)


def _append_event(
    data_root: Path,
    *,
    record_id: str,
    kind: RecordKind,
    digest: str,
    payload: dict,
    now: datetime,
    producer: str,
    txn: str,
) -> None:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=digest,
        hypothesis_version_id=None,
        run_id=ACTIVATION,
        transaction_id=txn,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
        producer_git_sha=producer,
        created_at=now,
    )
    ResearchStore(data_root).append([event], transaction_id=txn)


def _publish_panel(
    observation_rdp: Path,
    *,
    digest: str,
    now: datetime,
    producer: str,
    member_path: Path,
    obs_path: Path,
    member_count: int,
    obs_count: int,
    coverage: str,
    tag: str,
) -> None:
    utc_day = now.strftime("%Y%m%d")
    dataset_id = f"observation-panel-{digest[:12]}"
    dataset_version = f"{utc_day}-1-{tag}"
    dataset_manifest_id = compute_dataset_manifest_id(dataset_id, dataset_version)
    member_rel = member_path.relative_to(observation_rdp).as_posix()
    obs_rel = obs_path.relative_to(observation_rdp).as_posix()
    created = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifests = observation_rdp / "datasets" / "manifests"
    partitions = manifests / "partitions"
    manifests.mkdir(parents=True, exist_ok=True)
    partitions.mkdir(parents=True, exist_ok=True)
    member_part = {
        "partition_manifest_id": f"partition-{tag}-members",
        "dataset_manifest_id": dataset_manifest_id,
        "partition_id": f"utc-day-{utc_day}-members",
        "logical_location": member_rel,
    }
    obs_part = {
        "partition_manifest_id": f"partition-{tag}-obs",
        "dataset_manifest_id": dataset_manifest_id,
        "partition_id": f"utc-day-{utc_day}",
        "logical_location": obs_rel,
    }
    (partitions / f"{member_part['partition_manifest_id']}.json").write_text(
        json.dumps(member_part, sort_keys=True), encoding="utf-8"
    )
    (partitions / f"{obs_part['partition_manifest_id']}.json").write_text(
        json.dumps(obs_part, sort_keys=True), encoding="utf-8"
    )
    manifest = {
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "created_at": created,
        "first_reliable_available_at": created,
        "partitions": [obs_part, member_part],
    }
    (manifests / f"{dataset_manifest_id}.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    (manifests / f"{dataset_manifest_id}.published").write_text(
        json.dumps(
            {
                "dataset_manifest_id": dataset_manifest_id,
                "dataset_fingerprint": tag,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _append_event(
        observation_rdp,
        record_id=f"OBS-MEMB-{tag}",
        kind=RecordKind.OBSERVATION_MEMBER_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "member_location": member_rel,
            "row_count": member_count,
            "discovery_coverage_class": coverage,
        },
        now=now,
        producer=producer,
        txn=f"RESEARCH-TXN-MEM-{tag.upper()[:12]}",
    )
    _append_event(
        observation_rdp,
        record_id=f"OBS-BATCH-{tag}",
        kind=RecordKind.OBSERVATION_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "observation_location": obs_rel,
            "row_count": obs_count,
            "discovery_coverage_class": coverage,
        },
        now=now,
        producer=producer,
        txn=f"RESEARCH-TXN-OBS-{tag.upper()[:12]}",
    )


def _c1_entities(n: int) -> list[str]:
    return [f"MintC1{index:06d}{'p' * 32}" for index in range(n)]


def _seed_ops_store(path: Path, *, digest: str, entities: list[str]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE candidate_members (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, activation_id, entity_id)
            );
            CREATE TABLE due_observations (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                point_id TEXT NOT NULL,
                primitive_id TEXT NOT NULL,
                state TEXT NOT NULL,
                due_at TEXT NOT NULL,
                deadline_at TEXT NOT NULL,
                request_sha256 TEXT,
                call_occurrence_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (
                    schedule_sha256, activation_id, entity_id, point_id, primitive_id
                )
            );
            """
        )
        stamp = C1_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ")
        due_at = "2026-09-03T00:00:00Z"
        members = []
        dues = []
        for entity in entities:
            payload = json.dumps({"discovery_available_at": stamp}, sort_keys=True)
            members.append(
                (digest, ACTIVATION, entity, "ADMITTED", payload, stamp, stamp)
            )
            dues.append(
                (
                    digest,
                    ACTIVATION,
                    entity,
                    "X300",
                    "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "OBSERVED",
                    due_at,
                    "2026-09-03T01:00:00Z",
                    "{}",
                    stamp,
                    stamp,
                )
            )
        c2 = "MintC2later" + ("q" * 32)
        c2_stamp = C2_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ")
        members.append(
            (
                digest,
                ACTIVATION,
                c2,
                "ADMITTED",
                json.dumps({"discovery_available_at": c2_stamp}, sort_keys=True),
                c2_stamp,
                c2_stamp,
            )
        )
        conn.executemany(
            """
            INSERT INTO candidate_members(
                schedule_sha256, activation_id, entity_id, state,
                payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            members,
        )
        conn.executemany(
            """
            INSERT INTO due_observations(
                schedule_sha256, activation_id, entity_id, point_id, primitive_id,
                state, due_at, deadline_at, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            dues,
        )
        conn.commit()
    finally:
        conn.close()


class LiveCohortMemoryBoundedPublicationTests(unittest.TestCase):
    def test_crash_safe_staging_has_no_committed_manifest(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION,
            )
            members = [_member_row(digest, f"Mint{i:04d}{'p' * 32}", C1_ADMIT) for i in range(8)]
            observations = [_obs_row(digest, members[i]["entity_id"], C1_ADMIT) for i in range(8)]
            member_path = observation_rdp / "datasets/parquet/p1/members.parquet"
            obs_path = observation_rdp / "datasets/parquet/p1/observations.parquet"
            _write_parquet_batches(member_path, members)
            _write_parquet_batches(obs_path, observations)
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT,
                producer=PRODUCER_A,
                member_path=member_path,
                obs_path=obs_path,
                member_count=8,
                obs_count=8,
                coverage="GAP_SUSPECTED",
                tag="c1a",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                members_total=8,
            )
            source_dir = observation_rdp / "live_observation_rebuild" / f"cohort={COHORT1}"
            staging = source_dir / f"{SOURCE_STAGING_PREFIX}deadbeef"
            staging.mkdir(parents=True)
            (staging / SOURCE_MEMBERS_NAME).write_bytes(b"partial")
            with self.assertRaises(LiveCohortReleaseError):
                load_observation_rdp_source(observation_rdp, cohort_id=COHORT1)
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(source["source_representation"], "SOURCE_BUNDLE_V1")
            self.assertEqual(source["member_count"], 8)
            self.assertFalse(any(source_dir.glob(f"{SOURCE_STAGING_PREFIX}*")))
            manifest = source_dir / SOURCE_MANIFEST_NAME
            self.assertTrue(manifest.is_file())
            again = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(again["source_sha256"], source["source_sha256"])

    def test_resource_kill_classifier_does_not_swallow_ordinary_fail(self) -> None:
        self.assertTrue(source_build_child_was_resource_killed(-9))
        self.assertTrue(source_build_child_was_resource_killed(-11))
        self.assertTrue(source_build_child_was_resource_killed(137))
        self.assertTrue(source_build_child_was_resource_killed(139))
        self.assertFalse(source_build_child_was_resource_killed(0))
        self.assertFalse(source_build_child_was_resource_killed(2))
        self.assertFalse(source_build_child_was_resource_killed(1))
        self.assertFalse(source_build_child_was_resource_killed(-2))

    def test_cli_resource_kill_emits_typed_limit(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "discovery_evidence_release_cli_memory",
            ROOT / "scripts" / "discovery_evidence_release.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fake = subprocess.CompletedProcess(args=[], returncode=137)
        buf = io.StringIO()
        with patch.dict(os.environ, {module.SOURCE_BUILD_WORKER_ENV: ""}):
            with patch.object(module.subprocess, "run", return_value=fake):
                with patch.object(module.sys, "stdout", buf):
                    code = module.main(
                        [
                            "build-live-source",
                            "--observation-rdp",
                            "observation_rdp",
                            "--ops-store",
                            "ops.sqlite",
                            "--schedule-sha256",
                            "a" * 64,
                            "--activation-id",
                            ACTIVATION,
                            "--cohort-id",
                            COHORT1,
                        ]
                    )
        self.assertEqual(code, 2)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["code"], "SOURCE_BUILD_RESOURCE_LIMIT")
        self.assertEqual(payload["next"], "STOP_RETRY_BOUNDED_SOURCE_BUILD")

    def test_dest_parquet_without_manifest_is_not_valid_source(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION,
            )
            members = [_member_row(digest, f"Mint{i:04d}{'p' * 32}", C1_ADMIT) for i in range(8)]
            observations = [_obs_row(digest, members[i]["entity_id"], C1_ADMIT) for i in range(8)]
            member_path = observation_rdp / "datasets/parquet/p1/members.parquet"
            obs_path = observation_rdp / "datasets/parquet/p1/observations.parquet"
            _write_parquet_batches(member_path, members)
            _write_parquet_batches(obs_path, observations)
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT,
                producer=PRODUCER_A,
                member_path=member_path,
                obs_path=obs_path,
                member_count=8,
                obs_count=8,
                coverage="GAP_SUSPECTED",
                tag="c1a",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                members_total=8,
            )
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            source_dir = observation_rdp / "live_observation_rebuild" / f"cohort={COHORT1}"
            manifest = source_dir / SOURCE_MANIFEST_NAME
            self.assertTrue(manifest.is_file())
            members_part = source_dir / SOURCE_MEMBERS_NAME
            obs_part = source_dir / SOURCE_OBSERVATIONS_NAME
            self.assertTrue(members_part.is_file())
            self.assertTrue(obs_part.is_file())
            manifest.unlink()
            with self.assertRaises(LiveCohortReleaseError) as raised:
                load_observation_rdp_source(observation_rdp, cohort_id=COHORT1)
            self.assertEqual(str(raised.exception), "RELEASE_INVALID_SOURCE_INTEGRITY")
            rebuilt = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertTrue((source_dir / SOURCE_MANIFEST_NAME).is_file())
            self.assertEqual(rebuilt["source_sha256"], source["source_sha256"])
            self.assertEqual(rebuilt["member_count"], 8)

    def test_same_identity_corrupt_partitions_are_replaced(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION,
            )
            members = [_member_row(digest, f"Mint{i:04d}{'p' * 32}", C1_ADMIT) for i in range(6)]
            observations = [_obs_row(digest, members[i]["entity_id"], C1_ADMIT) for i in range(6)]
            member_path = observation_rdp / "datasets/parquet/p1/members.parquet"
            obs_path = observation_rdp / "datasets/parquet/p1/observations.parquet"
            _write_parquet_batches(member_path, members)
            _write_parquet_batches(obs_path, observations)
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT,
                producer=PRODUCER_A,
                member_path=member_path,
                obs_path=obs_path,
                member_count=6,
                obs_count=6,
                coverage="GAP_SUSPECTED",
                tag="c1a",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                members_total=6,
            )
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            source_dir = observation_rdp / "live_observation_rebuild" / f"cohort={COHORT1}"
            (source_dir / SOURCE_MEMBERS_NAME).write_bytes(b"corrupt-not-parquet")
            repaired = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(repaired["source_sha256"], source["source_sha256"])
            self.assertNotEqual(
                (source_dir / SOURCE_MEMBERS_NAME).read_bytes(),
                b"corrupt-not-parquet",
            )

    def test_snapshot_plus_delta_removed_member_stays_in_c1(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION,
            )
            first = [
                _member_row(digest, f"MintD{i:04d}{'p' * 32}", C1_ADMIT) for i in range(5)
            ]
            later = first[1:] + [
                _member_row(digest, f"MintD{5:04d}{'p' * 32}", C1_ADMIT)
            ]
            unit = write_snapshot_unit(
                observation_rdp,
                utc_day="20260902",
                dataset_manifest_id="dataset-delta-000",
                rows=first,
            )
            unit = append_delta_publication(
                observation_rdp,
                utc_day="20260902",
                dataset_manifest_id="dataset-delta-001",
                rows=later,
            )
            snap_rel = str(unit["publications"][0]["rel"])
            delta_rel = str(unit["publications"][1]["rel"])
            obs_a = observation_rdp / "datasets/parquet/d0/observations.parquet"
            obs_b = observation_rdp / "datasets/parquet/d1/observations.parquet"
            _write_parquet_batches(
                obs_a, [_obs_row(digest, row["entity_id"], C1_ADMIT) for row in first]
            )
            _write_parquet_batches(
                obs_b, [_obs_row(digest, row["entity_id"], C1_ADMIT) for row in later]
            )
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT,
                producer=PRODUCER_A,
                member_path=observation_rdp / snap_rel,
                obs_path=obs_a,
                member_count=5,
                obs_count=5,
                coverage="GAP_SUSPECTED",
                tag="d0",
            )
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT + timedelta(minutes=1),
                producer=PRODUCER_B,
                member_path=observation_rdp / delta_rel,
                obs_path=obs_b,
                member_count=5,
                obs_count=5,
                coverage="GAP_SUSPECTED",
                tag="d1",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                members_total=6,
            )
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(source["member_count"], 6)
            self.assertEqual(source["source_representation"], "SOURCE_BUNDLE_V1")

    def test_cumulative_snapshot_count_does_not_multiply_full_row_work(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        n = 4096
        entities = [f"MintC{i:05d}{'p' * 32}" for i in range(n)]
        rows = [_member_row(digest, entity, C1_ADMIT) for entity in entities]

        def _build_with_snapshots(snapshot_count: int) -> dict[str, int]:
            with tempfile.TemporaryDirectory() as tmp:
                observation_rdp = Path(tmp) / "observation_rdp"
                observation_rdp.mkdir()
                persist_observation_schedule(
                    data_root=observation_rdp,
                    schedule=schedule,
                    now=C1_ADMIT,
                    producer_git_sha=PRODUCER_A,
                    activation_id=ACTIVATION,
                )
                unit = write_snapshot_unit(
                    observation_rdp,
                    utc_day="20260902",
                    dataset_manifest_id="dataset-delta-000",
                    rows=rows,
                )
                obs_path = observation_rdp / "datasets/parquet/obs/observations.parquet"
                _write_parquet_batches(
                    obs_path,
                    [_obs_row(digest, entity, C1_ADMIT) for entity in entities[:64]],
                )
                _publish_panel(
                    observation_rdp,
                    digest=digest,
                    now=C1_ADMIT,
                    producer=PRODUCER_A,
                    member_path=observation_rdp / str(unit["publications"][0]["rel"]),
                    obs_path=obs_path,
                    member_count=n,
                    obs_count=64,
                    coverage="GAP_SUSPECTED",
                    tag="d000",
                )
                for index in range(1, snapshot_count):
                    unit = append_delta_publication(
                        observation_rdp,
                        utc_day="20260902",
                        dataset_manifest_id=f"dataset-delta-{index:03d}",
                        rows=rows,
                    )
                    rel = str(unit["publications"][-1]["rel"])
                    _publish_panel(
                        observation_rdp,
                        digest=digest,
                        now=C1_ADMIT + timedelta(minutes=index),
                        producer=PRODUCER_B if index == snapshot_count - 1 else PRODUCER_A,
                        member_path=observation_rdp / rel,
                        obs_path=obs_path,
                        member_count=n,
                        obs_count=64,
                        coverage="GAP_SUSPECTED",
                        tag=f"d{index:03d}",
                    )
                receipt = synthetic_closed_receipt(
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT1,
                    as_of=AS_OF_C1,
                    members_total=n,
                )
                reset_extraction_counters()
                reset_fingerprint_work()
                source = build_live_observation_source_from_rdp(
                    observation_rdp_root=observation_rdp,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT1,
                    as_of=AS_OF_C1,
                    closure_receipt=receipt,
                    discovery_coverage_class="GAP_SUSPECTED",
                )
                self.assertEqual(source["member_count"], n)
                stats = reconstruct_stats()
                counters = extraction_counters()
                counters["reconstruct_calls"] = stats["reconstruct_calls"]
                return counters

        ten = _build_with_snapshots(10)
        hundred = _build_with_snapshots(100)
        self.assertEqual(ten["reconstruct_calls"], 1)
        self.assertEqual(hundred["reconstruct_calls"], 1)
        self.assertEqual(ten["member_snapshot_full_column_scans"], 1)
        self.assertEqual(hundred["member_snapshot_full_column_scans"], 1)
        self.assertLess(
            hundred["full_member_row_materializations"],
            ten["full_member_row_materializations"] * 2,
        )
        self.assertLess(
            hundred["full_member_row_materializations"]
            / max(ten["full_member_row_materializations"], 1),
            3,
        )

    def test_delta_reconstruct_peak_rows_do_not_scale_with_chain(self) -> None:
        n = 64
        rows = [_member_row("a" * 64, f"MintP{i:04d}{'p' * 32}", C1_ADMIT) for i in range(n)]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            unit = write_snapshot_unit(
                data_root, utc_day="20260902", dataset_manifest_id="dataset-000", rows=rows
            )
            current = list(rows)
            for index in range(1, 41):
                current = current + [
                    _member_row("a" * 64, f"MintN{index:04d}{'p' * 32}", C1_ADMIT)
                ]
                unit = append_delta_publication(
                    data_root,
                    utc_day="20260902",
                    dataset_manifest_id=f"dataset-{index:04d}",
                    rows=current,
                )
            last_rel = str(unit["publications"][-1]["rel"])
            reset_fingerprint_work()
            total = 0
            for batch in iter_member_row_batches_for_location(data_root, last_rel):
                total += len(batch)
            stats = reconstruct_stats()
            self.assertEqual(total, len(current))
            self.assertEqual(stats["peak_sqlite_rows"], len(current))
            self.assertEqual(stats["reconstruct_calls"], 1)


def _stress_worker(payload_path: str, result_path: str) -> None:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    observation_rdp = Path(payload["observation_rdp"])
    release_root = Path(payload["release_root"])
    ops_store = Path(payload["ops_store"])
    digest = payload["digest"]
    receipt = build_closure_receipt(
        ops_store=ops_store,
        observation_rdp=observation_rdp,
        schedule_sha256=digest,
        activation_id=ACTIVATION,
        cohort_id=COHORT1,
        as_of=AS_OF_C1,
    )
    assert_closure_ready(receipt)
    source = build_live_observation_source_from_rdp(
        observation_rdp_root=observation_rdp,
        schedule_sha256=digest,
        activation_id=ACTIVATION,
        cohort_id=COHORT1,
        as_of=AS_OF_C1,
        closure_receipt=receipt,
        discovery_coverage_class="GAP_SUSPECTED",
    )
    assert_source_matches_receipt(source, receipt)
    loaded = load_observation_rdp_source(observation_rdp, cohort_id=COHORT1)
    ready = classify_cohort_readiness(loaded, cohort_id=COHORT1, as_of=AS_OF_C1)
    sealed = seal_live_cohort(
        observation_rdp_root=observation_rdp,
        cohort_id=COHORT1,
        release_root=release_root,
        sealed_at=AS_OF_C1,
        as_of=AS_OF_C1,
    )
    verified = verify_live_cohort(release_root)
    Path(result_path).write_text(
        json.dumps(
            {
                "member_count": source["member_count"],
                "observation_count": source["observation_count"],
                "source_sha256": source["source_sha256"],
                "readiness": ready["state"],
                "release_id": sealed["release_id"],
                "verified_release_id": verified["release_id"],
                "max_rss_bytes": peak_rss_bytes(),
                "source_representation": source["source_representation"],
                "receipt_members_total": receipt["members_total"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


class LiveCohortProductionShapeStressTests(unittest.TestCase):
    def test_publication_path_stays_under_rss_ceiling(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        n = STRESS_MEMBERS
        entities = _c1_entities(n)
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            release_root = Path(tmp) / "release"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=ACTIVATION,
            )

            def obs_c1():
                for entity in entities:
                    yield _obs_row(digest, entity, C1_ADMIT)

            def obs_late():
                yield _obs_row(
                    digest,
                    entities[0],
                    C1_ADMIT,
                    available=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
                )

            c1_rows = [_member_row(digest, entity, C1_ADMIT) for entity in entities]
            mixed_rows = c1_rows + [
                _member_row(digest, "MintC2later" + ("q" * 32), C2_ADMIT)
            ]
            unit = write_snapshot_unit(
                observation_rdp,
                utc_day="20260902",
                dataset_manifest_id="dataset-stress-000",
                rows=c1_rows,
            )
            unit = append_delta_publication(
                observation_rdp,
                utc_day="20260902",
                dataset_manifest_id="dataset-stress-001",
                rows=c1_rows,
            )
            unit = append_delta_publication(
                observation_rdp,
                utc_day="20260902",
                dataset_manifest_id="dataset-stress-002",
                rows=mixed_rows,
            )
            p_a_m = observation_rdp / str(unit["publications"][0]["rel"])
            p_b_m = observation_rdp / str(unit["publications"][1]["rel"])
            p_c_m = observation_rdp / str(unit["publications"][2]["rel"])
            p_a_o = observation_rdp / "datasets/parquet/a/observations.parquet"
            p_b_o = observation_rdp / "datasets/parquet/b/observations.parquet"
            p_c_o = observation_rdp / "datasets/parquet/c/observations.parquet"
            _write_parquet_batches(p_a_o, obs_c1())
            p_b_o.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p_a_o, p_b_o)
            _write_parquet_batches(p_c_o, obs_late())
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT,
                producer=PRODUCER_A,
                member_path=p_a_m,
                obs_path=p_a_o,
                member_count=n,
                obs_count=n,
                coverage="GAP_SUSPECTED",
                tag="c1a",
            )
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT + timedelta(hours=1),
                producer=PRODUCER_B,
                member_path=p_b_m,
                obs_path=p_b_o,
                member_count=n,
                obs_count=n,
                coverage="GAP_SUSPECTED",
                tag="c1b",
            )
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=C1_ADMIT + timedelta(hours=2),
                producer=PRODUCER_C,
                member_path=p_c_m,
                obs_path=p_c_o,
                member_count=n + 1,
                obs_count=1,
                coverage="GAP_SUSPECTED",
                tag="mixed",
            )
            later = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
            p_d_m = observation_rdp / "datasets/parquet/d/members.parquet"
            p_d_o = observation_rdp / "datasets/parquet/d/observations.parquet"
            _write_parquet_batches(
                p_d_m,
                [_member_row(digest, "MintC2later" + ("q" * 32), C2_ADMIT)],
            )
            _write_parquet_batches(
                p_d_o,
                [_obs_row(digest, "MintC2later" + ("q" * 32), C2_ADMIT, available=later)],
            )
            _publish_panel(
                observation_rdp,
                digest=digest,
                now=later,
                producer="ddddaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                member_path=p_d_m,
                obs_path=p_d_o,
                member_count=1,
                obs_count=1,
                coverage="GAP_SUSPECTED",
                tag="laterc2",
            )
            ops_store = Path(tmp) / "observation_schedule_state.sqlite"
            _seed_ops_store(ops_store, digest=digest, entities=entities)
            payload_path = Path(tmp) / "payload.json"
            result_path = Path(tmp) / "result.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "observation_rdp": str(observation_rdp),
                        "release_root": str(release_root),
                        "ops_store": str(ops_store),
                        "digest": digest,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    *INTERPRETER,
                    str(Path(__file__).resolve()),
                    str(payload_path),
                    str(result_path),
                ],
                cwd=str(ROOT),
                env={**os.environ, "LIVE_COHORT_STRESS_WORKER": "1"},
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                self.fail(proc.stderr[-4000:] or proc.stdout[-4000:] or str(proc.returncode))
            result = json.loads(result_path.read_text(encoding="utf-8"))
            print(
                f"STRESS_MAX_RSS_BYTES={result['max_rss_bytes']} "
                f"observations={result['observation_count']}",
                file=sys.stderr,
                flush=True,
            )
            self.assertEqual(result["member_count"], n)
            self.assertEqual(result["receipt_members_total"], n)
            self.assertEqual(result["readiness"], "READY_VALID_WITH_COVERAGE_LIMITATION")
            self.assertEqual(result["release_id"], result["verified_release_id"])
            self.assertLessEqual(
                int(result["max_rss_bytes"]),
                STRESS_RSS_CEILING,
                msg=f"max_rss_bytes={result['max_rss_bytes']} observations={result['observation_count']}",
            )
            self.assertEqual(result["source_representation"], "SOURCE_BUNDLE_V1")


if os.environ.get("LIVE_COHORT_STRESS_WORKER") == "1":
    _stress_worker(sys.argv[1], sys.argv[2])
elif __name__ == "__main__":
    unittest.main()
