"""Vertical proof for publication-job journal lifecycle.

Routine repair cost is O(open jobs), not O(historical completed bytes).
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
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

from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    PublicationFault,
    has_open_publication_jobs,
    publish_observation_batch,
    rebuild_observation_panel_from_rdp,
    repair_open_publication_jobs,
)
from solana_alpha_lab.factory.observation_publication_jobs import (  # noqa: E402
    AMBIGUOUS_BLOCKS_APPLY,
    COLLECTOR_NOT_PAUSED,
    COMPACT_RECEIPT_UNCONSTRUCTABLE,
    COMPLETED_RECEIPT_CONFLICT,
    HOT_PATH_FORBIDDEN,
    LEGACY_FULL_BYTE_MISMATCH,
    PublicationJobError,
    UNAVAILABLE_FILESYSTEM_TRUTH,
    UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET,
    apply_migration,
    collector_blocks_apply,
    compact_receipt_from_job,
    completed_job_path,
    dry_run_migration,
    is_compact_receipt,
    journal_stats,
    jobs_root,
    legacy_full_path,
    load_job_by_content,
    open_dir,
    open_job_path,
    project_7d_disk_used,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_sha256,
    load_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


def _cli():
    spec = importlib.util.spec_from_file_location(
        "observation_publication_jobs_cli",
        ROOT / "scripts" / "observation_publication_jobs.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _members(schedule: dict, entity: str) -> list[dict]:
    return [{"schedule_sha256": schedule["schedule_sha256"], "entity_id": entity}]


def _observations(schedule: dict, entity: str) -> list[dict]:
    return [
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "entity_id": entity,
            "point_id": "X300",
            "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            "state": "OBSERVED",
            "event_time": "2026-09-01T00:05:00Z",
            "first_reliable_available_at": "2026-09-01T00:10:00Z",
        }
    ]


def _content(members: list[dict], observations: list[dict]) -> str:
    return canonical_sha256({"members": members, "observations": observations})


def _publish(data_root: Path, schedule: dict, entity: str, **kwargs):
    return publish_observation_batch(
        data_root=data_root,
        root=ROOT,
        schedule=schedule,
        activation_id="ACT-OBS-001",
        now=NOW,
        producer_git_sha=GIT_SHA,
        members=_members(schedule, entity),
        observations=_observations(schedule, entity),
        **kwargs,
    )


def _early_open_source(data_root: Path, schedule: dict) -> Path:
    content = "0" * 64
    payload = {
        "content_sha256": content,
        "schedule_sha256": schedule["schedule_sha256"],
        "activation_id": "ACT-OBS-001",
        "stage": "OPEN",
        "members": [{"schedule_sha256": schedule["schedule_sha256"], "entity_id": "Early"}],
    }
    path = jobs_root(data_root) / f"{content}.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _flatten_jobs(data_root: Path) -> None:
    root = jobs_root(data_root)
    for path in list(open_dir(data_root).glob("*.json")):
        os.replace(path, root / path.name)


def _alien_receipt(content: str) -> dict:
    return {
        "content_sha256": content,
        "schedule_sha256": "e" * 64,
        "activation_id": "ACT-ALIEN",
        "stage": "COMPLETE",
        "utc_day": "2020-01-01",
        "dataset_version": "v-alien",
        "dataset_manifest_id": "dataset-alien",
        "created_at": "2020-01-01T00:00:00Z",
        "completed_at": "2020-01-01T00:00:00Z",
        "parquet_rel": "datasets/parquet/alien.parquet",
        "member_rel": "datasets/members/alien.json",
        "file_sha256": "a" * 64,
        "member_sha256": "b" * 64,
        "observation_count": 0,
        "member_count": 0,
        "dataset_fingerprint": content,
    }


def _forbid_historical_job_reads():
    orig_text = Path.read_text
    orig_bytes = Path.read_bytes

    def _check(path: Path) -> None:
        parts = Path(path).parts
        if "completed" in parts or "legacy_full" in parts:
            raise AssertionError(HOT_PATH_FORBIDDEN)

    def read_text(self, *args, **kwargs):
        _check(self)
        return orig_text(self, *args, **kwargs)

    def read_bytes(self, *args, **kwargs):
        _check(self)
        return orig_bytes(self, *args, **kwargs)

    return patch.multiple(Path, read_text=read_text, read_bytes=read_bytes)


class ObservationPublicationJobLifecycleTests(unittest.TestCase):
    def test_routine_repair_is_open_only_and_ignores_completed_sentinel(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            _publish(data_root, schedule, "MintDone")
            completed = completed_job_path(data_root, "a" * 64).parent
            completed.mkdir(parents=True, exist_ok=True)
            for index in range(250):
                digest = hashlib.sha256(f"completed-{index}".encode()).hexdigest()
                (completed / f"{digest}.json").write_text(
                    json.dumps({"stage": "COMPLETE", "n": index}, sort_keys=True),
                    encoding="utf-8",
                )
            sentinel = completed / ("b" * 64 + ".json")
            sentinel.write_bytes(b"SENTINEL" * 32768)
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintOpen", fault_after="AFTER_ARTIFACTS")
            open_files = list(open_dir(data_root).glob("*.json"))
            self.assertEqual(len(open_files), 1)
            with _forbid_historical_job_reads():
                repaired = repair_open_publication_jobs(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                )
                self.assertEqual(len(repaired), 1)
                self.assertFalse(
                    has_open_publication_jobs(
                        data_root=data_root,
                        schedule_sha256=schedule["schedule_sha256"],
                        activation_id="ACT-OBS-001",
                    )
                )
            self.assertTrue(sentinel.is_file())
            self.assertGreaterEqual(
                journal_stats(data_root)["publication_jobs_completed_count"], 251
            )
            self.assertEqual(journal_stats(data_root)["publication_jobs_open_count"], 0)

    def test_marker_crash_repair_is_idempotent_and_compact(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        members = _members(schedule, "MintA")
        observations = _observations(schedule, "MintA")
        content = _content(members, observations)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintA", fault_after="AFTER_MARKER")
            self.assertEqual(journal_stats(data_root)["publication_jobs_open_count"], 1)
            repaired = repair_open_publication_jobs(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
            )
            self.assertEqual(len(repaired), 1)
            receipt = load_job_by_content(data_root, content)
            self.assertTrue(is_compact_receipt(receipt or {}))
            self.assertNotIn("observations", receipt or {})
            self.assertNotIn("members", receipt or {})
            again = repair_open_publication_jobs(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
            )
            self.assertEqual(again, [])
            records = list(ResearchStore(data_root).iter_committed_records())
            self.assertEqual(
                sum(1 for item in records if str(item.record_kind) == "OBSERVATION_BATCH"),
                1,
            )

    def test_cross_day_replay_keeps_dataset_identity_without_full_payload(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        members = _members(schedule, "MintA")
        observations = _observations(schedule, "MintA")
        content = _content(members, observations)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = _publish(data_root, schedule, "MintA")
            later = datetime(2026, 9, 2, 0, 10, tzinfo=UTC)
            replay = publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=later,
                producer_git_sha=GIT_SHA,
                members=members,
                observations=observations,
            )
            self.assertTrue(replay["replay"])
            self.assertEqual(replay["dataset_manifest_id"], first["dataset_manifest_id"])
            receipt = load_job_by_content(data_root, content)
            self.assertEqual(
                str((receipt or {}).get("dataset_manifest_id")),
                first["dataset_manifest_id"],
            )
            self.assertTrue(is_compact_receipt(receipt or {}))

    def test_forge_rdp_consumer_does_not_need_job_payload(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            published = _publish(data_root, schedule, "MintA")
            before = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            content = _content(_members(schedule, "MintA"), _observations(schedule, "MintA"))
            receipt_path = completed_job_path(data_root, content)
            self.assertTrue(receipt_path.is_file())
            receipt_path.unlink()
            after = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            self.assertEqual(before["dataset_manifest_ids"], after["dataset_manifest_ids"])
            self.assertEqual(len(before["members"]), 1)
            self.assertEqual(after["members"], before["members"])
            self.assertEqual(after["observations"], before["observations"])
            self.assertEqual(published["dataset_manifest_id"], before["dataset_manifest_ids"][0])

    def test_migration_dry_run_apply_idempotent_preserves_legacy_bytes(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintOpen", fault_after="AFTER_ARTIFACTS")
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintDone", fault_after="AFTER_MARKER")
            root_jobs = jobs_root(data_root)
            for path in list(open_dir(data_root).glob("*.json")):
                os.replace(path, root_jobs / path.name)
            ambiguous = root_jobs / ("d" * 64 + ".json")
            ambiguous.write_text("{", encoding="utf-8")
            dry = dry_run_migration(data_root)
            self.assertEqual(dry["classified_open"], 1)
            self.assertEqual(dry["classified_proven_completed"], 1)
            self.assertEqual(dry["classified_ambiguous"], 1)
            self.assertEqual(dry["provider_calls"], 0)
            self.assertEqual(dry["scientific_writes"], 0)
            with self.assertRaises(PublicationJobError) as raised:
                apply_migration(data_root)
            self.assertEqual(str(raised.exception), AMBIGUOUS_BLOCKS_APPLY)
            ambiguous.unlink()
            open_raw = None
            proven_raw = None
            for path in sorted(root_jobs.glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("stage") == "MARKER":
                    proven_raw = path.read_bytes()
                else:
                    open_raw = path.read_bytes()
            first = apply_migration(data_root)
            self.assertEqual(first["moved_open"], 1)
            self.assertEqual(first["moved_completed"], 1)
            self.assertFalse(first["legacy_full_deleted"])
            self.assertEqual(dry_run_migration(data_root)["old_unmigrated_count"], 0)
            second = apply_migration(data_root)
            self.assertEqual(second["moved_open"], 0)
            self.assertEqual(second["moved_completed"], 0)
            stats = journal_stats(data_root)
            self.assertEqual(stats["publication_jobs_legacy_full_count"], 1)
            self.assertEqual(stats["publication_jobs_open_count"], 1)
            self.assertEqual(stats["publication_jobs_completed_count"], 1)
            legacy = next((jobs_root(data_root) / "legacy_full").glob("*.json"))
            self.assertEqual(legacy.read_bytes(), proven_raw)
            self.assertEqual(open_raw, next(open_dir(data_root).glob("*.json")).read_bytes())
            self.assertIsNotNone(
                load_job_by_content(
                    data_root,
                    json.loads((open_dir(data_root) / next(open_dir(data_root).glob("*.json")).name).read_text(encoding="utf-8"))[
                        "content_sha256"
                    ],
                )
            )

    def test_cli_status_dry_run_apply_and_pause_gate(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        module = _cli()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintOpen", fault_after="AFTER_ARTIFACTS")
            for path in list(open_dir(data_root).glob("*.json")):
                os.replace(path, jobs_root(data_root) / path.name)
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(["dry-run", "--data-root", str(data_root)])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["classified_open"], 1)
            self.assertEqual(payload["provider_calls"], 0)
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(["apply", "--data-root", str(data_root)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(buf.getvalue())["terminal"], "APPLY_REQUIRES_FLAG")
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "apply",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(Path(tmp) / "missing.sqlite"),
                        "--i-understand-apply",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(buf.getvalue())["terminal"], "COLLECTOR_STORE_MISSING"
            )
            store_path = Path(tmp) / "ops.sqlite"
            store = ObservationScheduleStore(store_path)
            store.upsert_activation(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": "ACT-OBS-001",
                    "schedule_key": schedule["schedule_key"],
                    "state": "ACTIVE",
                    "authority_receipt_sha256": "e" * 64,
                    "starts_at": "2026-09-01T00:00:00Z",
                    "stops_admitting_at": "2026-09-02T00:00:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            store.close()
            self.assertTrue(collector_blocks_apply([{"state": "ACTIVE"}]))
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "apply",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--i-understand-apply",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(buf.getvalue())["terminal"], COLLECTOR_NOT_PAUSED)
            store = ObservationScheduleStore(store_path)
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
            buf = io.StringIO()
            with patch.object(sys, "stdout", buf):
                code = module.main(
                    [
                        "apply",
                        "--data-root",
                        str(data_root),
                        "--ops-store",
                        str(store_path),
                        "--i-understand-apply",
                    ]
                )
            self.assertEqual(code, 0)
            applied = json.loads(buf.getvalue())
            self.assertEqual(applied["terminal"], "PUBLICATION_JOB_MIGRATION_APPLIED")
            self.assertEqual(applied["moved_open"], 1)
            self.assertFalse(applied["legacy_full_deleted"])

    def test_preflight_malformed_proven_moves_nothing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintOpen", fault_after="AFTER_ARTIFACTS")
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintDone", fault_after="AFTER_MARKER")
            _flatten_jobs(data_root)
            early = _early_open_source(data_root, schedule)
            early_bytes = early.read_bytes()
            root = jobs_root(data_root)
            for path in root.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("stage") == "MARKER":
                    payload.pop("utc_day", None)
                    payload.pop("file_sha256", None)
                    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            before = {path.name: path.read_bytes() for path in root.glob("*.json")}
            names = sorted(before)
            self.assertEqual(names[0], early.name)
            self.assertGreater(len(names), 1)
            with self.assertRaises(PublicationJobError) as raised:
                apply_migration(data_root)
            self.assertEqual(str(raised.exception), COMPACT_RECEIPT_UNCONSTRUCTABLE)
            after = {path.name: path.read_bytes() for path in root.glob("*.json")}
            self.assertEqual(set(after), set(before))
            self.assertEqual(after[early.name], early_bytes)
            self.assertEqual(list(open_dir(data_root).glob("*.json")), [])
            self.assertEqual(journal_stats(data_root)["publication_jobs_legacy_full_count"], 0)

    def test_preflight_incompatible_completed_moves_nothing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintDone", fault_after="AFTER_MARKER")
            _flatten_jobs(data_root)
            early = _early_open_source(data_root, schedule)
            early_bytes = early.read_bytes()
            source = next(
                path
                for path in jobs_root(data_root).glob("*.json")
                if path.name != early.name
            )
            payload = json.loads(source.read_text(encoding="utf-8"))
            content = payload["content_sha256"]
            dest = completed_job_path(data_root, content)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(_alien_receipt(content), sort_keys=True), encoding="utf-8")
            source_bytes = source.read_bytes()
            self.assertLess(early.name, source.name)
            with self.assertRaises(PublicationJobError) as raised:
                apply_migration(data_root)
            self.assertEqual(str(raised.exception), COMPLETED_RECEIPT_CONFLICT)
            self.assertTrue(early.is_file())
            self.assertEqual(early.read_bytes(), early_bytes)
            self.assertTrue(source.is_file())
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(
                json.loads(dest.read_text(encoding="utf-8"))["dataset_manifest_id"],
                "dataset-alien",
            )

    def test_preflight_incompatible_legacy_full_moves_nothing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintDone", fault_after="AFTER_MARKER")
            _flatten_jobs(data_root)
            early = _early_open_source(data_root, schedule)
            early_bytes = early.read_bytes()
            source = next(
                path
                for path in jobs_root(data_root).glob("*.json")
                if path.name != early.name
            )
            payload = json.loads(source.read_text(encoding="utf-8"))
            content = payload["content_sha256"]
            source_bytes = source.read_bytes()
            legacy = legacy_full_path(data_root, content)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_bytes(b"NOT-THE-SOURCE")
            self.assertLess(early.name, source.name)
            with self.assertRaises(PublicationJobError) as raised:
                apply_migration(data_root)
            self.assertEqual(str(raised.exception), LEGACY_FULL_BYTE_MISMATCH)
            self.assertTrue(early.is_file())
            self.assertEqual(early.read_bytes(), early_bytes)
            self.assertTrue(source.is_file())
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(legacy.read_bytes(), b"NOT-THE-SOURCE")

    def test_identical_preexisting_destinations_are_idempotent(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintOpen", fault_after="AFTER_ARTIFACTS")
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintDone", fault_after="AFTER_MARKER")
            _flatten_jobs(data_root)
            root = jobs_root(data_root)
            open_path = None
            proven_path = None
            for path in root.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("stage") == "MARKER":
                    proven_path = path
                else:
                    open_path = path
            assert open_path is not None and proven_path is not None
            open_raw = open_path.read_bytes()
            proven_raw = proven_path.read_bytes()
            open_payload = json.loads(open_raw.decode("utf-8"))
            proven_payload = json.loads(proven_raw.decode("utf-8"))
            dest_open = open_job_path(data_root, open_payload["content_sha256"])
            dest_open.parent.mkdir(parents=True, exist_ok=True)
            dest_open.write_bytes(open_raw)
            receipt = compact_receipt_from_job(
                proven_payload,
                completed_at=NOW,
                dataset_fingerprint=proven_payload["content_sha256"],
            )
            dest_completed = completed_job_path(data_root, proven_payload["content_sha256"])
            dest_completed.parent.mkdir(parents=True, exist_ok=True)
            dest_completed.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            dest_legacy = legacy_full_path(data_root, proven_payload["content_sha256"])
            dest_legacy.parent.mkdir(parents=True, exist_ok=True)
            dest_legacy.write_bytes(proven_raw)
            first = apply_migration(data_root)
            self.assertEqual(first["moved_open"], 1)
            self.assertEqual(first["moved_completed"], 1)
            self.assertFalse(open_path.is_file())
            self.assertFalse(proven_path.is_file())
            self.assertEqual(dest_open.read_bytes(), open_raw)
            self.assertEqual(dest_legacy.read_bytes(), proven_raw)
            self.assertTrue(is_compact_receipt(json.loads(dest_completed.read_text(encoding="utf-8"))))
            second = apply_migration(data_root)
            self.assertEqual(second["moved_open"], 0)
            self.assertEqual(second["moved_completed"], 0)

    def test_prefix_applied_state_converges_on_rerun(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintOpen", fault_after="AFTER_ARTIFACTS")
            with self.assertRaises(PublicationFault):
                _publish(data_root, schedule, "MintDone", fault_after="AFTER_MARKER")
            _flatten_jobs(data_root)
            root = jobs_root(data_root)
            open_path = None
            proven_path = None
            for path in root.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("stage") == "MARKER":
                    proven_path = path
                else:
                    open_path = path
            assert open_path is not None and proven_path is not None
            open_payload = json.loads(open_path.read_text(encoding="utf-8"))
            os.replace(open_path, open_job_path(data_root, open_payload["content_sha256"]))
            self.assertTrue(proven_path.is_file())
            report = apply_migration(data_root)
            self.assertEqual(report["moved_open"], 0)
            self.assertEqual(report["moved_completed"], 1)
            self.assertFalse(proven_path.is_file())
            self.assertEqual(journal_stats(data_root)["publication_jobs_open_count"], 1)
            self.assertEqual(journal_stats(data_root)["publication_jobs_completed_count"], 1)
            self.assertEqual(journal_stats(data_root)["publication_jobs_legacy_full_count"], 1)
            again = apply_migration(data_root)
            self.assertEqual(again["moved_open"], 0)
            self.assertEqual(again["moved_completed"], 0)

    def test_compact_missing_keys_are_typed_not_keyerror(self) -> None:
        with self.assertRaises(PublicationJobError) as raised:
            compact_receipt_from_job({}, completed_at=NOW)
        self.assertEqual(str(raised.exception), COMPACT_RECEIPT_UNCONSTRUCTABLE)

    def test_week_survival_uses_declared_budget_not_unknown_pass(self) -> None:
        passing = project_7d_disk_used(
            disk_total_bytes=1_000_000,
            disk_used_bytes=100_000,
            sqlite_bytes=1_000,
            rdp_science_bytes=2_000,
            job_open_bytes=0,
            job_completed_bytes=100,
            job_legacy_bytes=50_000,
            elapsed_campaign_days=0.5,
            declared_raw_bytes_per_day=1_000,
            history_data_growth_24h_bytes=None,
        )
        self.assertEqual(passing["projection_basis"], "DECLARED_RAW_BYTES_PER_DAY")
        self.assertTrue(passing["projected_7d_disk_used_pass_70"])
        failing = project_7d_disk_used(
            disk_total_bytes=1_000,
            disk_used_bytes=600,
            sqlite_bytes=1,
            rdp_science_bytes=1,
            job_open_bytes=0,
            job_completed_bytes=1,
            job_legacy_bytes=100,
            elapsed_campaign_days=1.0,
            declared_raw_bytes_per_day=50,
            history_data_growth_24h_bytes=None,
        )
        self.assertFalse(failing["projected_7d_disk_used_pass_70"])
        self.assertIsInstance(failing["projected_7d_disk_used_pass_70"], bool)
        missing_fs = project_7d_disk_used(
            disk_total_bytes=None,
            disk_used_bytes=None,
            sqlite_bytes=None,
            rdp_science_bytes=None,
            job_open_bytes=0,
            job_completed_bytes=0,
            job_legacy_bytes=0,
            elapsed_campaign_days=3.0,
            declared_raw_bytes_per_day=1_000,
            history_data_growth_24h_bytes=None,
        )
        self.assertEqual(missing_fs["projection_basis"], UNAVAILABLE_FILESYSTEM_TRUTH)
        self.assertIsNone(missing_fs["projected_7d_disk_used_pct"])
        self.assertFalse(missing_fs["projected_7d_disk_used_pass_70"])
        missing_budget = project_7d_disk_used(
            disk_total_bytes=1_000_000,
            disk_used_bytes=100_000,
            sqlite_bytes=None,
            rdp_science_bytes=None,
            job_open_bytes=0,
            job_completed_bytes=0,
            job_legacy_bytes=0,
            elapsed_campaign_days=0.5,
            declared_raw_bytes_per_day=None,
            history_data_growth_24h_bytes=None,
        )
        self.assertEqual(
            missing_budget["projection_basis"], UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET
        )
        self.assertIsNone(missing_budget["projected_7d_disk_used_pct"])
        self.assertFalse(missing_budget["projected_7d_disk_used_pass_70"])
        coerced_zero = project_7d_disk_used(
            disk_total_bytes=1_000_000,
            disk_used_bytes=0,
            sqlite_bytes=0,
            rdp_science_bytes=0,
            job_open_bytes=0,
            job_completed_bytes=0,
            job_legacy_bytes=0,
            elapsed_campaign_days=10.0,
            declared_raw_bytes_per_day=None,
            history_data_growth_24h_bytes=None,
        )
        self.assertFalse(coerced_zero["projected_7d_disk_used_pass_70"])
        self.assertEqual(
            coerced_zero["projection_basis"], UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET
        )


if __name__ == "__main__":
    unittest.main()
