"""FACTORY_OPERATIONAL_STORE_READONLY_SCHEMA_COMPATIBILITY_V1."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication, commissioning_spec_relative  # noqa: E402
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec  # noqa: E402
from solana_alpha_lab.factory.operational_store import (  # noqa: E402
    SCHEMA_INCOMPATIBLE,
    SCHEMA_LEGACY_UNINITIALIZED,
    SCHEMA_READY,
    SCHEMA_SOURCE_NOT_PRESENT,
    OperationalStore,
    OperationalStoreError,
)
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config  # noqa: E402
from solana_alpha_lab.factory.workbench import serve  # noqa: E402

GET_PATHS = ("/", "/system", "/operations", "/economics", "/research", "/market")
LEGACY_NOTE = "preserved-local-pre-jobs"


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _ops_path(root: Path) -> Path:
    return (root / "local/factory_v1/operational_state.sqlite").resolve()


def _write_legacy_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE legacy_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO legacy_meta(k, v) VALUES (?, ?)",
            ("note", LEGACY_NOTE),
        )
        conn.commit()
    finally:
        conn.close()


def _write_incompatible_jobs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE jobs (foo TEXT)")
        conn.execute("INSERT INTO jobs(foo) VALUES ('not-a-job')")
        conn.commit()
    finally:
        conn.close()


def _fingerprint(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        master = [
            (str(row[0]), str(row[1]), row[2])
            for row in conn.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY name, type"
            ).fetchall()
        ]
        rows: dict[str, list[tuple[object, ...]]] = {}
        for kind, name, _sql in master:
            if kind != "table" or name.startswith("sqlite_"):
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            rows[name] = [tuple(item) for item in conn.execute(f"SELECT * FROM {quoted}")]
    finally:
        conn.close()
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "master": master,
        "rows": rows,
        "wal": Path(str(path) + "-wal").exists(),
        "shm": Path(str(path) + "-shm").exists(),
    }


def _close_app(app: FactoryApplication) -> None:
    closer = getattr(app, "_close_operational_readonly", None)
    if callable(closer):
        closer()
    paper_closer = getattr(app, "_close_paper_plane_readonly", None)
    if callable(paper_closer):
        paper_closer()


def _get(app: FactoryApplication, path: str) -> tuple[int, str]:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=20)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        status = int(response.status)
        conn.close()
        return status, body
    finally:
        server.shutdown()
        server.server_close()


def _sample_job(*, experiment_id: str, spec_relative: str) -> dict[str, object]:
    return {
        "job_id": f"JOB-{experiment_id}",
        "experiment_id": experiment_id,
        "spec_relative": spec_relative,
        "spec_sha256": "0" * 64,
        "status": "COMPLETE",
        "blocker": "NONE",
        "terminal": "DIRECTIONAL_HINT_NOT_CONFIRMATION",
        "evidence": {"result": "FIXTURE"},
    }


def _commissioning_job(root: Path) -> dict[str, object]:
    spec_relative = commissioning_spec_relative(root)
    spec = load_experiment_spec(root, spec_relative)
    return _sample_job(experiment_id=str(spec["experiment_id"]), spec_relative=spec_relative)


class OperationalStoreReadonlySchemaCompatTests(unittest.TestCase):
    def test_legacy_no_jobs_get_surfaces_do_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp))
            path = _ops_path(root)
            _write_legacy_sqlite(path)
            before = _fingerprint(path)
            app = FactoryApplication(root=root)
            try:
                model = app.read_model()
                self.assertEqual(model["operational_source_status"], SCHEMA_LEGACY_UNINITIALIZED)
                self.assertNotEqual(model["status"], "UNAVAILABLE")
                probe = OperationalStore(path, readonly=True)
                try:
                    self.assertIsNone(probe.get_job("JOB-ABSENT"))
                    self.assertIsNone(probe.latest_job())
                    self.assertEqual(probe.runtime_events(), [])
                finally:
                    probe.close()
                for route in GET_PATHS:
                    status, body = _get(app, route)
                    self.assertEqual(status, 200, route)
                    self.assertNotIn("Traceback", body)
                    self.assertNotIn("no such table", body)
                after = _fingerprint(path)
                self.assertEqual(after["sha256"], before["sha256"])
                self.assertEqual(after["master"], before["master"])
                self.assertEqual(after["rows"], before["rows"])
                self.assertNotIn("jobs", after["rows"])
                self.assertFalse(Path(str(path) + "-wal").exists())
            finally:
                _close_app(app)

    def test_missing_file_get_does_not_create_db(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp))
            path = _ops_path(root)
            self.assertFalse(path.exists())
            app = FactoryApplication(root=root)
            try:
                model = app.read_model()
                self.assertEqual(model["operational_source_status"], SCHEMA_SOURCE_NOT_PRESENT)
                for route in GET_PATHS:
                    status, body = _get(app, route)
                    self.assertEqual(status, 200, route)
                    self.assertNotIn("Traceback", body)
                self.assertFalse(path.exists())
                self.assertFalse(Path(str(path) + "-wal").exists())
            finally:
                _close_app(app)

    def test_incompatible_jobs_fail_closed_without_http_crash(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp))
            path = _ops_path(root)
            _write_incompatible_jobs(path)
            before = _fingerprint(path)
            app = FactoryApplication(root=root)
            try:
                model = app.read_model()
                self.assertEqual(model["operational_source_status"], SCHEMA_INCOMPATIBLE)
                self.assertEqual(model["status"], "UNAVAILABLE")
                self.assertEqual(model["blocker"], "OPS_STORE_INCOMPATIBLE")
                self.assertNotEqual(model["status"], "NOT_STARTED")
                for route in GET_PATHS:
                    status, body = _get(app, route)
                    self.assertEqual(status, 200, route)
                    self.assertNotIn("Traceback", body)
                    self.assertNotIn("OperationalError", body)
                    if route == "/":
                        self.assertIn("UNAVAILABLE", body)
                        self.assertIn("OPS_STORE_INCOMPATIBLE", body)
                after = _fingerprint(path)
                self.assertEqual(after["sha256"], before["sha256"])
                self.assertEqual(after["master"], before["master"])
                self.assertEqual(after["rows"], before["rows"])
            finally:
                _close_app(app)

    def test_ready_schema_reads_existing_job_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp))
            path = _ops_path(root)
            writer = OperationalStore(path)
            job = _commissioning_job(root)
            writer.upsert_job(job)
            writer.close()
            before = _fingerprint(path)
            reader = OperationalStore(path, readonly=True)
            self.assertEqual(reader.schema_status, SCHEMA_READY)
            loaded = reader.get_job(str(job["job_id"]))
            assert loaded is not None
            self.assertEqual(loaded["job_id"], job["job_id"])
            self.assertEqual(loaded["status"], "COMPLETE")
            self.assertEqual(loaded["blocker"], "NONE")
            self.assertEqual(loaded["terminal"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
            self.assertEqual(loaded["evidence"], {"result": "FIXTURE"})
            reader.close()
            app = FactoryApplication(root=root)
            try:
                model = app.read_model()
                self.assertEqual(model["operational_source_status"], SCHEMA_READY)
                self.assertEqual(model["status"], "COMPLETE")
                for route in GET_PATHS:
                    status, body = _get(app, route)
                    self.assertEqual(status, 200, route)
                    self.assertNotIn("Traceback", body)
                after = _fingerprint(path)
                self.assertEqual(after["sha256"], before["sha256"])
                self.assertEqual(after["rows"]["jobs"], before["rows"]["jobs"])
            finally:
                _close_app(app)

    def test_upgrade_boundary_get_then_explicit_write_init(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp))
            path = _ops_path(root)
            _write_legacy_sqlite(path)
            before = _fingerprint(path)
            app = FactoryApplication(root=root)
            try:
                self.assertEqual(
                    app.read_model()["operational_source_status"], SCHEMA_LEGACY_UNINITIALIZED
                )
                status, body = _get(app, "/")
                self.assertEqual(status, 200)
                self.assertNotIn("Traceback", body)
                after_get = _fingerprint(path)
                self.assertEqual(after_get["sha256"], before["sha256"])
            finally:
                _close_app(app)
            writer = OperationalStore(path, readonly=False)
            writer.upsert_job(_commissioning_job(root))
            writer.close()
            reader = OperationalStore(path, readonly=True)
            loaded = reader.get_job(str(_commissioning_job(root)["job_id"]))
            assert loaded is not None
            self.assertEqual(loaded["terminal"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
            reader.close()
            conn = sqlite3.connect(path)
            try:
                note = conn.execute(
                    "SELECT v FROM legacy_meta WHERE k = ?", ("note",)
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(note[0], LEGACY_NOTE)

    def test_writable_init_preserves_unrelated_legacy_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = (Path(tmp) / "operational_state.sqlite").resolve()
            _write_legacy_sqlite(path)
            store = OperationalStore(path, readonly=False)
            self.assertEqual(store.schema_status, SCHEMA_READY)
            job = _sample_job(
                experiment_id="EXP-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-OFFLINE-001",
                spec_relative=(
                    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
                ),
            )
            store.upsert_job(job)
            store.close()
            conn = sqlite3.connect(path)
            try:
                note = conn.execute(
                    "SELECT v FROM legacy_meta WHERE k = ?", ("note",)
                ).fetchone()
                self.assertEqual(note[0], LEGACY_NOTE)
                tables = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            finally:
                conn.close()
            self.assertIn("legacy_meta", tables)
            self.assertIn("jobs", tables)
            reader = OperationalStore(path, readonly=True)
            loaded = reader.get_job(str(job["job_id"]))
            assert loaded is not None
            self.assertEqual(loaded["status"], "COMPLETE")
            reader.close()

    def test_incompatible_writable_fails_closed_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = (Path(tmp) / "operational_state.sqlite").resolve()
            _write_incompatible_jobs(path)
            before = _fingerprint(path)
            with self.assertRaisesRegex(OperationalStoreError, "OPS_STORE_INCOMPATIBLE"):
                OperationalStore(path, readonly=False)
            after = _fingerprint(path)
            self.assertEqual(after["sha256"], before["sha256"])
            self.assertEqual(after["master"], before["master"])
            self.assertEqual(after["rows"], before["rows"])


if __name__ == "__main__":
    unittest.main()
