"""Paused-only bounded ARTIFACTS resume for oversized legacy open jobs."""

from __future__ import annotations

import importlib.util
import io
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hot90_activation import (  # noqa: E402
    STAGE_WRITE_ONLY_SHADOW,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (  # noqa: E402
    peak_rss_bytes,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    ObservationPanelPublisherError,
    PublicationFault,
    has_open_publication_jobs,
    inspect_legacy_fat_open_artifacts,
    publish_observation_batch,
    repair_open_publication_jobs,
    resume_legacy_fat_open_artifacts,
)
from solana_alpha_lab.factory.observation_publication_jobs import (  # noqa: E402
    COLLECTOR_NOT_PAUSED,
    FAT_ARTIFACTS_RESUME_ALREADY_COMPLETE,
    FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING,
    FAT_ARTIFACTS_RESUME_COMPLETED,
    FAT_ARTIFACTS_RESUME_CONFLICT,
    FAT_ARTIFACTS_RESUME_HASH_MISMATCH,
    FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT,
    FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE,
    FAT_ARTIFACTS_RESUME_READY,
    FAT_ARTIFACTS_RESUME_READY_RETRY,
    FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE,
    LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION,
    ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES,
    PublicationJobError,
    collector_pause_proven,
    completed_job_path,
    is_compact_receipt,
    load_open_job_for_routine_path,
    open_job_path,
    prove_legacy_fat_open_artifacts_source,
    stream_legacy_fat_open_job_for_artifacts_resume,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
FAT_EXTRA_BYTES = ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES + 8192
MEMORY_FAT_BYTES = 16 * 1024 * 1024
SOFT_RSS = 768 * 1024 * 1024
COMFORTABLE_RSS = 256 * 1024 * 1024
HOT90_DELTA = {
    "activation_stage": STAGE_WRITE_ONLY_SHADOW,
    "production_compaction_enabled": False,
    "production_eviction_enabled": False,
    "drive_writes_enabled": False,
    "members_layout": "SNAPSHOT_PLUS_DELTA",
    "new_write_zstd": True,
    "activation_source": "OVERRIDE",
}


def _cli():
    spec = importlib.util.spec_from_file_location(
        "observation_publication_jobs_cli_fat_resume",
        ROOT / "scripts" / "observation_publication_jobs.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schedule():
    return load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )


def _members(schedule: dict) -> list[dict]:
    return [{"schedule_sha256": schedule["schedule_sha256"], "entity_id": "MintA"}]


def _observations(schedule: dict) -> list[dict]:
    return [
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "entity_id": "MintA",
            "point_id": "X300",
            "state": "OBSERVED",
            "event_time": "2026-09-01T00:05:00Z",
            "first_reliable_available_at": "2026-09-01T00:10:00Z",
        }
    ]


def _paused(schedule: dict | None = None) -> list[dict]:
    schedule = schedule or _schedule()
    return [
        {
            "state": "PAUSED_OPERATOR",
            "activation_id": "ACT-OBS-001",
            "schedule_sha256": schedule["schedule_sha256"],
        }
    ]


def _publish(data_root: Path, schedule: dict, *, fault_after: str | None = None):
    return publish_observation_batch(
        data_root=data_root,
        root=ROOT,
        schedule=schedule,
        activation_id="ACT-OBS-001",
        now=NOW,
        producer_git_sha=GIT_SHA,
        members=_members(schedule),
        observations=_observations(schedule),
        fault_after=fault_after,
    )


def _inflate_open_job(path: Path, *, extra_bytes: int = FAT_EXTRA_BYTES) -> None:
    compact = json.loads(path.read_text(encoding="utf-8"))
    inner = json.dumps(compact, sort_keys=True)[1:-1].strip()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("{")
        if inner:
            handle.write(inner)
            handle.write(",")
        handle.write('"members":[')
        chunk = "0," * 4096
        written = 0
        while written < extra_bytes:
            handle.write(chunk)
            written += len(chunk)
        handle.write("0]}")


def _rdp_identity(data_root: Path) -> set[tuple[str, str, str]]:
    return {
        (str(item.record_id), str(item.record_kind), str(item.payload_sha256))
        for item in ResearchStore(data_root).iter_committed_records()
    }


def _guard_fat_materialization(fat_path: Path):
    fat = fat_path.resolve()
    orig_read_text = Path.read_text
    orig_read_bytes = Path.read_bytes
    orig_loads = json.loads
    orig_load = json.load

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if Path(self).resolve() == fat:
            raise AssertionError("read_text on fat open job")
        return orig_read_text(self, *args, **kwargs)

    def guarded_read_bytes(self: Path, *args: object, **kwargs: object) -> bytes:
        if Path(self).resolve() == fat:
            raise AssertionError("read_bytes on fat open job")
        return orig_read_bytes(self, *args, **kwargs)

    def guarded_loads(s: object, *args: object, **kwargs: object):
        if isinstance(s, (str, bytes, bytearray)) and len(s) > ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES:
            raise AssertionError("json.loads of oversized body")
        return orig_loads(s, *args, **kwargs)

    def guarded_load(fp: object, *args: object, **kwargs: object):
        name = getattr(fp, "name", None)
        if name and Path(str(name)).resolve() == fat:
            raise AssertionError("json.load of fat open job")
        return orig_load(fp, *args, **kwargs)

    return (
        patch.object(Path, "read_text", guarded_read_text),
        patch.object(Path, "read_bytes", guarded_read_bytes),
        patch.object(json, "loads", guarded_loads),
        patch.object(json, "load", guarded_load),
    )


def _register_paused_store(store_path: Path, schedule: dict) -> None:
    store = ObservationScheduleStore(store_path)
    store.acquire_lease("owner", clock=NOW)
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=NOW,
    )
    store.upsert_activation(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": "ACT-OBS-001",
            "schedule_key": schedule["schedule_key"],
            "state": "PAUSED_OPERATOR",
            "authority_receipt_sha256": "e" * 64,
            "starts_at": "2026-09-01T00:00:00Z",
            "stops_admitting_at": "2026-09-02T00:00:00Z",
            "payload": {},
        },
        clock=NOW,
    )
    store.close()


def _register_schedule_only(store_path: Path, schedule: dict) -> None:
    store = ObservationScheduleStore(store_path)
    store.acquire_lease("owner", clock=NOW)
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=NOW,
    )
    store.close()


class LegacyFatOpenBoundedArtifactsResumeTests(unittest.TestCase):
    def test_stream_skips_members_and_routine_path_still_fails(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next(open_job_path(data_root, "").parent.glob("*.json")).stem
            job_path = open_job_path(data_root, content)
            _inflate_open_job(job_path)
            self.assertGreater(job_path.stat().st_size, ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES)
            patches = _guard_fat_materialization(job_path)
            with patches[0], patches[1], patches[2], patches[3]:
                streamed = stream_legacy_fat_open_job_for_artifacts_resume(job_path)
                self.assertNotIn("members", streamed)
                self.assertTrue(streamed["has_members_array"])
                self.assertEqual(streamed["stage"], "ARTIFACTS")
                self.assertEqual(len(streamed["observations"]), 1)
                with self.assertRaises(PublicationJobError) as load_err:
                    load_open_job_for_routine_path(job_path)
                self.assertEqual(str(load_err.exception), LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
                with self.assertRaises(ObservationPanelPublisherError) as has_err:
                    has_open_publication_jobs(
                        data_root=data_root,
                        schedule_sha256=schedule["schedule_sha256"],
                        activation_id="ACT-OBS-001",
                    )
                self.assertEqual(str(has_err.exception), LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
                with self.assertRaises(ObservationPanelPublisherError) as repair_err:
                    repair_open_publication_jobs(
                        data_root=data_root,
                        root=ROOT,
                        schedule=schedule,
                        activation_id="ACT-OBS-001",
                        now=NOW,
                        producer_git_sha=GIT_SHA,
                    )
                self.assertEqual(
                    str(repair_err.exception), LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION
                )

    def test_normal_and_recovery_converge(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            modern_root = Path(tmp) / "modern"
            recover_root = Path(tmp) / "recover"
            modern_root.mkdir()
            recover_root.mkdir()
            modern = _publish(modern_root, schedule)
            with self.assertRaises(PublicationFault):
                _publish(recover_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((recover_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            job_path = open_job_path(recover_root, content)
            _inflate_open_job(job_path)
            patches = _guard_fat_materialization(job_path)
            with patches[0], patches[1], patches[2], patches[3]:
                with patch.object(socket, "create_connection", side_effect=AssertionError("provider")):
                    recovered = resume_legacy_fat_open_artifacts(
                        data_root=recover_root,
                        root=ROOT,
                        content_sha256=content,
                        activations=_paused(),
                        schedule=schedule,
                        producer_git_sha=GIT_SHA,
                        now=NOW,
                    )
            self.assertEqual(recovered["terminal"], FAT_ARTIFACTS_RESUME_COMPLETED)
            self.assertEqual(recovered["provider_calls"], 0)
            self.assertEqual(modern["dataset_manifest_id"], recovered["dataset_manifest_id"])
            self.assertEqual(modern["dataset_fingerprint"], recovered["dataset_fingerprint"])
            self.assertEqual(_rdp_identity(modern_root), _rdp_identity(recover_root))
            modern_marker = (
                modern_root / "datasets" / "manifests" / f"{modern['dataset_manifest_id']}.published"
            )
            recover_marker = (
                recover_root / "datasets" / "manifests" / f"{recovered['dataset_manifest_id']}.published"
            )
            self.assertEqual(modern_marker.read_bytes(), recover_marker.read_bytes())
            modern_manifest = (
                modern_root / "datasets" / "manifests" / f"{modern['dataset_manifest_id']}.json"
            )
            recover_manifest = (
                recover_root / "datasets" / "manifests" / f"{recovered['dataset_manifest_id']}.json"
            )
            self.assertEqual(modern_manifest.read_bytes(), recover_manifest.read_bytes())
            modern_receipt = json.loads(
                completed_job_path(modern_root, content).read_text(encoding="utf-8")
            )
            recover_receipt = json.loads(
                completed_job_path(recover_root, content).read_text(encoding="utf-8")
            )
            self.assertTrue(is_compact_receipt(modern_receipt))
            self.assertTrue(is_compact_receipt(recover_receipt))
            for key in (
                "content_sha256",
                "dataset_manifest_id",
                "dataset_fingerprint",
                "parquet_rel",
                "member_rel",
                "file_sha256",
                "member_sha256",
                "observation_count",
                "member_count",
            ):
                self.assertEqual(modern_receipt[key], recover_receipt[key])
            self.assertFalse(job_path.is_file())

    def test_snapshot_plus_delta_member_location(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with patch(
                "solana_alpha_lab.factory.observation_panel_publisher.load_hot90_activation",
                return_value=HOT90_DELTA,
            ):
                with self.assertRaises(PublicationFault):
                    _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
                content = next(
                    (data_root / "datasets" / "publication_jobs" / "open").glob("*.json")
                ).stem
                job_path = open_job_path(data_root, content)
                compact = json.loads(job_path.read_text(encoding="utf-8"))
                self.assertIn("members_snapshot_plus_delta", compact["member_rel"])
                _inflate_open_job(job_path)
                recovered = resume_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=_paused(),
                    schedule=schedule,
                    producer_git_sha=GIT_SHA,
                    now=NOW,
                )
            self.assertEqual(recovered["terminal"], FAT_ARTIFACTS_RESUME_COMPLETED)
            self.assertIn("members_snapshot_plus_delta", compact["member_rel"])

    def test_artifact_hash_mismatch_fails_closed(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            job_path = open_job_path(data_root, content)
            compact = json.loads(job_path.read_text(encoding="utf-8"))
            parquet = data_root / compact["parquet_rel"]
            parquet.write_bytes(parquet.read_bytes() + b"x")
            _inflate_open_job(job_path)
            before = job_path.stat().st_mtime_ns
            with self.assertRaises(PublicationJobError) as err:
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=_paused(),
                    schedule=schedule,
                )
            self.assertEqual(str(err.exception), FAT_ARTIFACTS_RESUME_HASH_MISMATCH)
            self.assertEqual(_rdp_identity(data_root), set())
            self.assertEqual(job_path.stat().st_mtime_ns, before)

    def test_wrong_stage_refuses_without_mutation(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            job_path = open_job_path(data_root, content)
            compact = json.loads(job_path.read_text(encoding="utf-8"))
            compact["stage"] = None
            job_path.write_text(json.dumps(compact, sort_keys=True), encoding="utf-8")
            _inflate_open_job(job_path)
            with self.assertRaises(PublicationJobError) as err:
                prove_legacy_fat_open_artifacts_source(data_root, content)
            self.assertEqual(str(err.exception), FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE)
            self.assertEqual(_rdp_identity(data_root), set())

    def test_compact_job_is_not_this_path(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            with self.assertRaises(PublicationJobError) as err:
                prove_legacy_fat_open_artifacts_source(data_root, content)
            self.assertEqual(str(err.exception), FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT)

    def test_collector_not_paused(self) -> None:
        schedule = _schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            job_path = open_job_path(data_root, content)
            _inflate_open_job(job_path)
            source = job_path.read_bytes()
            with self.assertRaises(PublicationJobError) as err:
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=[{"state": "ACTIVE"}],
                    schedule=schedule,
                )
            self.assertEqual(str(err.exception), COLLECTOR_NOT_PAUSED)
            with self.assertRaises(PublicationJobError):
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=[{"state": "DRAINING"}],
                    schedule=schedule,
                )
            self.assertEqual(job_path.read_bytes(), source)

    def test_empty_activations_and_bounds_fail_closed(self) -> None:
        schedule = _schedule()
        self.assertFalse(collector_pause_proven([]))
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            job_path = open_job_path(data_root, content)
            source = job_path.read_bytes()
            with self.assertRaises(PublicationJobError) as err:
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=[],
                    schedule=schedule,
                )
            self.assertEqual(str(err.exception), COLLECTOR_NOT_PAUSED)
            self.assertEqual(job_path.read_bytes(), source)
            compact = json.loads(job_path.read_text(encoding="utf-8"))
            compact["parquet_rel"] = "../escape.parquet"
            job_path.write_text(json.dumps(compact), encoding="utf-8")
            _inflate_open_job(job_path)
            with self.assertRaises(PublicationJobError) as path_err:
                prove_legacy_fat_open_artifacts_source(data_root, content)
            self.assertEqual(str(path_err.exception), FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING)
            job_path.write_bytes(source)
            compact = json.loads(job_path.read_text(encoding="utf-8"))
            compact["dataset_manifest_id"] = "tampered-manifest-id"
            job_path.write_text(json.dumps(compact), encoding="utf-8")
            _inflate_open_job(job_path)
            with self.assertRaises(PublicationJobError) as manifest_err:
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=_paused(),
                    schedule=schedule,
                )
            self.assertEqual(str(manifest_err.exception), FAT_ARTIFACTS_RESUME_CONFLICT)
            huge = Path(tmp) / "huge-string.json"
            padding = "0," * 200000
            huge.write_text(
                '{"stage":"ARTIFACTS","dataset_version":"' + ("v" * 300) + '","members":[' + padding + "0]}",
                encoding="utf-8",
            )
            with self.assertRaises(PublicationJobError) as huge_err:
                stream_legacy_fat_open_job_for_artifacts_resume(huge)
            self.assertEqual(str(huge_err.exception), FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE)
            job_path.write_bytes(source)
            compact = json.loads(job_path.read_text(encoding="utf-8"))
            job_path.write_text(json.dumps(compact), encoding="utf-8")
            _inflate_open_job(job_path)
            text = job_path.read_text(encoding="utf-8")
            job_path.write_text(text.replace(',"members":[', ',"no_members":['), encoding="utf-8")
            with self.assertRaises(PublicationJobError) as members_err:
                prove_legacy_fat_open_artifacts_source(data_root, content)
            self.assertEqual(str(members_err.exception), FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT)
            job_path.write_bytes(source)
            compact = json.loads(job_path.read_text(encoding="utf-8"))
            compact["activation_id"] = "ACT-OTHER-999"
            job_path.write_text(json.dumps(compact), encoding="utf-8")
            _inflate_open_job(job_path)
            with self.assertRaises(PublicationJobError) as act_err:
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=_paused(schedule),
                    schedule=schedule,
                )
            self.assertEqual(str(act_err.exception), COLLECTOR_NOT_PAUSED)
            job_path.write_bytes(source)
            _inflate_open_job(job_path)
            with self.assertRaises(PublicationJobError) as unknown_err:
                inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=[
                        {
                            "state": "COMPLETE",
                            "activation_id": "ACT-OBS-001",
                            "schedule_sha256": schedule["schedule_sha256"],
                        }
                    ],
                    schedule=schedule,
                )
            self.assertEqual(str(unknown_err.exception), COLLECTOR_NOT_PAUSED)

    def test_fault_retry_matrix_converges_once(self) -> None:
        schedule = _schedule()
        for stage in (
            "AFTER_ONE_RDP_EVENT",
            "AFTER_MANIFEST",
            "AFTER_MARKER",
            "AFTER_COMPLETE",
        ):
            with self.subTest(stage=stage):
                with tempfile.TemporaryDirectory() as tmp:
                    data_root = Path(tmp) / "rdp"
                    data_root.mkdir()
                    with self.assertRaises(PublicationFault):
                        _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
                    content = next(
                        (data_root / "datasets" / "publication_jobs" / "open").glob("*.json")
                    ).stem
                    job_path = open_job_path(data_root, content)
                    _inflate_open_job(job_path)
                    with self.assertRaises(PublicationFault):
                        resume_legacy_fat_open_artifacts(
                            data_root=data_root,
                            root=ROOT,
                            content_sha256=content,
                            activations=_paused(),
                            schedule=schedule,
                            producer_git_sha=GIT_SHA,
                            now=NOW,
                            fault_after=stage,
                        )
                    inspected = inspect_legacy_fat_open_artifacts(
                        data_root=data_root,
                        root=ROOT,
                        content_sha256=content,
                        activations=_paused(),
                        schedule=schedule,
                    )
                    expected = {FAT_ARTIFACTS_RESUME_ALREADY_COMPLETE} if stage == "AFTER_COMPLETE" else {
                        FAT_ARTIFACTS_RESUME_READY,
                        FAT_ARTIFACTS_RESUME_READY_RETRY,
                    }
                    self.assertIn(inspected["terminal"], expected)
                    finished = resume_legacy_fat_open_artifacts(
                        data_root=data_root,
                        root=ROOT,
                        content_sha256=content,
                        activations=_paused(),
                        schedule=schedule,
                        producer_git_sha=GIT_SHA,
                        now=NOW,
                    )
                    replay = resume_legacy_fat_open_artifacts(
                        data_root=data_root,
                        root=ROOT,
                        content_sha256=content,
                        activations=_paused(),
                        schedule=schedule,
                        producer_git_sha=GIT_SHA,
                        now=NOW,
                    )
                    self.assertEqual(finished["dataset_manifest_id"], replay["dataset_manifest_id"])
                    kinds = [
                        str(item.record_kind)
                        for item in ResearchStore(data_root).iter_committed_records()
                        if str(item.record_kind)
                        in {"OBSERVATION_BATCH", "OBSERVATION_MEMBER_BATCH"}
                    ]
                    self.assertEqual(kinds.count("OBSERVATION_BATCH"), 1)
                    self.assertEqual(kinds.count("OBSERVATION_MEMBER_BATCH"), 1)
                    self.assertTrue(replay.get("replay") or finished["terminal"] == FAT_ARTIFACTS_RESUME_COMPLETED)

    def test_cli_inspect_then_resume(self) -> None:
        schedule = _schedule()
        module = _cli()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store_path = Path(tmp) / "ops.sqlite"
            _register_paused_store(store_path, schedule)
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, fault_after="AFTER_ARTIFACTS")
            content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
            job_path = open_job_path(data_root, content)
            _inflate_open_job(job_path)
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "inspect-fat-open",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--content",
                        content,
                    ]
                )
            self.assertEqual(code, 0)
            inspected = json.loads(buf.getvalue())
            self.assertEqual(inspected["terminal"], FAT_ARTIFACTS_RESUME_READY)
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "resume-fat-artifacts",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--content",
                        content,
                        "--producer-git-sha",
                        GIT_SHA,
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(buf.getvalue())["terminal"],
                "FAT_ARTIFACTS_RESUME_REQUIRES_FLAG",
            )
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "resume-fat-artifacts",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--content",
                        content,
                        "--producer-git-sha",
                        GIT_SHA,
                        "--i-understand-resume",
                    ]
                )
            self.assertEqual(code, 0)
            resumed = json.loads(buf.getvalue())
            self.assertEqual(resumed["terminal"], FAT_ARTIFACTS_RESUME_COMPLETED)
            self.assertEqual(resumed["provider_calls"], 0)
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "inspect-fat-open",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--content",
                        content,
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(buf.getvalue())["terminal"],
                FAT_ARTIFACTS_RESUME_ALREADY_COMPLETE,
            )
            empty_store = Path(tmp) / "empty-ops.sqlite"
            _register_schedule_only(empty_store, schedule)
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "inspect-fat-open",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(empty_store),
                        "--content",
                        content,
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(buf.getvalue())["terminal"], COLLECTOR_NOT_PAUSED)
            from solana_alpha_lab.factory.observation_schedule_runtime import (
                ObservationRuntimeError,
            )

            buf = io.StringIO()
            with patch.object(
                module, "git_sha", side_effect=ObservationRuntimeError("PRODUCER_GIT_SHA_UNAVAILABLE")
            ), patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "resume-fat-artifacts",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--content",
                        content,
                        "--i-understand-resume",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(buf.getvalue())["terminal"],
                "FAT_ARTIFACTS_RESUME_PRODUCER_SHA_REQUIRED",
            )

    def test_memory_envelope_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload.json"
            result = Path(tmp) / "result.json"
            payload.write_text(
                json.dumps(
                    {
                        "tmp": tmp,
                        "schedule_rel": "tests/fixtures/observation_schedule/x300_y900.yaml",
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "--memory-child",
                    str(payload),
                    str(result),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            body = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(body["terminal"], FAT_ARTIFACTS_RESUME_COMPLETED)
            self.assertGreater(int(body["source_size"]), ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES)
            self.assertLessEqual(int(body["max_rss_bytes"]), SOFT_RSS)
            self.assertLessEqual(int(body["max_rss_bytes"]), COMFORTABLE_RSS)


def _memory_child(payload_path: str, result_path: str) -> None:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    schedule = load_observation_schedule(ROOT, payload["schedule_rel"])
    data_root = Path(payload["tmp"]) / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    try:
        publish_observation_batch(
            data_root=data_root,
            root=ROOT,
            schedule=schedule,
            activation_id="ACT-OBS-001",
            now=NOW,
            producer_git_sha=GIT_SHA,
            members=_members(schedule),
            observations=_observations(schedule),
            fault_after="AFTER_ARTIFACTS",
        )
    except PublicationFault:
        pass
    content = next((data_root / "datasets" / "publication_jobs" / "open").glob("*.json")).stem
    job_path = open_job_path(data_root, content)
    _inflate_open_job(job_path, extra_bytes=MEMORY_FAT_BYTES)
    source_size = int(job_path.stat().st_size)
    recovered = resume_legacy_fat_open_artifacts(
        data_root=data_root,
        root=ROOT,
        content_sha256=content,
        activations=_paused(),
        schedule=schedule,
        producer_git_sha=GIT_SHA,
        now=NOW,
    )
    Path(result_path).write_text(
        json.dumps(
            {
                "terminal": recovered["terminal"],
                "source_size": source_size,
                "max_rss_bytes": peak_rss_bytes(),
                "provider_calls": recovered.get("provider_calls", 0),
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--memory-child":
        _memory_child(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
