from __future__ import annotations

import json
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.runtime import (
    FactoryRuntime,
    copy_rehost_allowlist,
    load_runtime_config,
)
from solana_alpha_lab.factory.workbench import serve


RUNTIME_SCHEMA = ROOT / "catalog/schemas/factory_v1_production_lite_runtime.schema.json"
UNIT_RELATIVE = "configs/factory_v1_linux_runtime/factory-v1-workbench.service"


def isolated_runtime_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


class FactoryV1ProductionLiteRuntimeTests(unittest.TestCase):
    def test_config_and_unit_are_vps_shaped_without_purchase(self) -> None:
        config = load_runtime_config(ROOT)
        jsonschema.validate(config, json.loads(RUNTIME_SCHEMA.read_text(encoding="utf-8")))
        self.assertEqual(config["implementation"], "LOCAL_LINUX_SHAPED_PROOF")
        self.assertEqual(config["target"]["purchase"], "LATER_EXTERNAL_AUTHORITY")
        self.assertTrue(config["health"]["process_alive_alone_is_not_healthy"])
        self.assertTrue(config["health"]["healthy_verdict_forbidden"])
        self.assertFalse(config["authority"]["deployment"])
        self.assertFalse(config["authority"]["provider_calls"])
        self.assertFalse(config["authority"]["cash_spend"])
        unit = (ROOT / UNIT_RELATIVE).read_text(encoding="utf-8")
        exec_start = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
        self.assertEqual(len(exec_start), 1)
        self.assertIn("--host 127.0.0.1", exec_start[0])
        self.assertIn("Restart=on-failure", unit)
        self.assertNotIn("0.0.0.0", exec_start[0])
        self.assertNotIn("EnvironmentFile", unit)
        self.assertNotIn(".env", unit)
        dumped = yaml.safe_dump(config)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", dumped)
        self.assertNotIn("Kubernetes", dumped)

    def test_process_alive_alone_is_not_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime_receipt = (
                root
                / "docs/evidence/factory_v1_commissioning"
                / "a2_factory_v1_commissioning_runtime_receipt_v1.json"
            )
            runtime_receipt.unlink()
            store = OperationalStore((root / "ops.sqlite").resolve())
            runtime = FactoryRuntime(root=root, store=store, process_alive=True)
            try:
                health = runtime.health()
                self.assertTrue(health["process_alive"])
                self.assertNotEqual(health["verdict"], "HEALTHY")
                self.assertEqual(health["verdict"], "UNHEALTHY_EVIDENCE_MISSING")
                self.assertEqual(health["backup_status"], "EXPLICIT_UNKNOWN")
            finally:
                runtime.close()

    def test_restart_recovers_complete_without_recapture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root)
            try:
                started = runtime.app.start()
                self.assertEqual(started["status"], "COMPLETE")
                first_job = runtime.store.latest_job()
                assert first_job is not None
                historical_calls = first_job["evidence"].get("provider_api_rpc_wss_calls")
                self.assertEqual(historical_calls, 50)
                runtime.start_process()
                recovered = runtime.restart()
                self.assertEqual(recovered["experiment_status"], "COMPLETE")
                self.assertEqual(recovered["proofs"]["restart_recovery"], True)
                self.assertNotEqual(recovered["verdict"], "HEALTHY")
                second = runtime.app.start()
                self.assertEqual(second["status"], "COMPLETE")
                job = runtime.store.latest_job()
                assert job is not None
                self.assertEqual(job["evidence"].get("provider_api_rpc_wss_calls"), historical_calls)
            finally:
                runtime.close()

    def test_hash_bound_without_proofs_is_degraded_not_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root, process_alive=True)
            try:
                health = runtime.health()
                self.assertEqual(health["git_evidence"], "HASH_BOUND")
                self.assertEqual(health["verdict"], "DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN")
                self.assertNotEqual(health["verdict"], "HEALTHY")
            finally:
                runtime.close()

    def test_stop_process_is_unhealthy_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root)
            try:
                runtime.start_process()
                stopped = runtime.stop_process()
                self.assertFalse(stopped["process_alive"])
                self.assertEqual(stopped["verdict"], "UNHEALTHY_NOT_RUNNING")
            finally:
                runtime.close()

    def test_rollback_restores_snapshot_after_operational_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root)
            try:
                runtime.app.start()
                runtime.start_process()
                runtime.snapshot()
                job = runtime.store.latest_job()
                assert job is not None
                clobbered = dict(job)
                clobbered["status"] = "FAILED"
                clobbered["blocker"] = "TEST_CLOBBER"
                clobbered["terminal"] = "FAILED"
                runtime.store.upsert_job(clobbered)
                self.assertEqual(runtime.app.read_model()["status"], "FAILED")
                rolled = runtime.rollback()
                self.assertEqual(rolled["deploy_version"], "factory-v1-runtime-v0.9")
                self.assertEqual(rolled["experiment_status"], "COMPLETE")
                self.assertEqual(runtime.app.read_model()["status"], "COMPLETE")
                self.assertEqual(rolled["proofs"]["rollback"], True)
            finally:
                runtime.close()

    def test_rollback_restores_after_wiped_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root)
            try:
                runtime.app.start()
                runtime.start_process()
                runtime.snapshot()
                path = runtime.store.path
                runtime.store.close()
                path.unlink()
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(str(path) + suffix)
                    if sidecar.exists():
                        sidecar.unlink()
                runtime.store = OperationalStore(path)
                runtime.app = runtime.app.__class__(root=root, store=runtime.store)
                self.assertIsNone(runtime.store.latest_job())
                rolled = runtime.rollback()
                self.assertEqual(rolled["experiment_status"], "COMPLETE")
                self.assertEqual(runtime.app.read_model()["status"], "COMPLETE")
            finally:
                runtime.close()

    def test_rollback_without_snapshot_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root, process_alive=True)
            try:
                with self.assertRaisesRegex(Exception, "ROLLBACK_SNAPSHOT_MISSING"):
                    runtime.rollback()
            finally:
                runtime.close()

    def test_rehost_projects_git_complete_without_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = isolated_runtime_root(Path(tmp) / "source")
            dest = Path(tmp) / "dest"
            runtime = FactoryRuntime(root=source, process_alive=True)
            hosted = None
            try:
                hosted = runtime.rehost(dest)
                health = hosted.health()
                self.assertEqual(health["git_evidence"], "HASH_BOUND")
                self.assertEqual(health["proofs"]["rehost"], True)
                model = hosted.app.read_model()
                self.assertEqual(model["status"], "COMPLETE")
                self.assertNotEqual(health["verdict"], "HEALTHY")
                job = hosted.store.latest_job()
                assert job is not None
                self.assertEqual(job["evidence"].get("provider_api_rpc_wss_calls"), 50)
                self.assertEqual(job["evidence"].get("credential_reads"), 1)
                self.assertTrue((dest / "src/solana_alpha_lab/factory/runtime.py").is_file())
            finally:
                if hosted is not None:
                    hosted.close()
                runtime.close()

    def test_full_proof_packet_never_claims_operational_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = isolated_runtime_root(Path(tmp) / "source")
            runtime = FactoryRuntime(root=source)
            try:
                proved = runtime.prove()
                self.assertEqual(proved["backup_status"], "EXPLICIT_UNKNOWN")
                self.assertEqual(proved["verdict"], "RUNTIME_PROVED_BACKUP_UNKNOWN")
                self.assertEqual(proved["terminal"], "PRODUCTION_LITE_LINUX_RUNTIME_PROOF_PASS")
                self.assertEqual(proved["purchase"], "LATER_EXTERNAL_AUTHORITY")
                self.assertTrue(proved["proofs"]["rehost"])
                self.assertNotEqual(proved["verdict"], "HEALTHY")
                self.assertIn("runtime", runtime.app.read_model())
            finally:
                runtime.close()

    def test_workbench_shows_runtime_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_runtime_root(Path(tmp) / "src")
            runtime = FactoryRuntime(root=root, process_alive=True)
            server = None
            try:
                server = serve(runtime.app, host="127.0.0.1", port=0)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address[:2]
                conn = HTTPConnection(host, port, timeout=2)
                conn.request("GET", "/")
                response = conn.getresponse()
                body = response.read().decode("utf-8")
                conn.close()
                self.assertEqual(response.status, 200)
                self.assertIn("DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN", body)
                self.assertIn("EXPLICIT_UNKNOWN", body)
                self.assertIn("factory-v1-runtime-v1.0", body)
            finally:
                if server is not None:
                    server.shutdown()
                    server.server_close()
                runtime.close()

    def test_kernel_and_commissioning_authority_unchanged(self) -> None:
        kernel = yaml.safe_load(
            (ROOT / "configs/factory_v1_product_kernel_v1.yaml").read_text(encoding="utf-8")
        )
        commissioning = yaml.safe_load(
            (ROOT / "configs/factory_v1_commissioning_v1.yaml").read_text(encoding="utf-8")
        )
        readiness = yaml.safe_load(
            (ROOT / "configs/factory_v1_operational_readiness_v1.yaml").read_text(encoding="utf-8")
        )
        self.assertFalse(kernel["authority"]["provider_calls"])
        self.assertFalse(kernel["authority"]["deployment"])
        self.assertEqual(commissioning["authority"]["deployment"], False)
        self.assertEqual(readiness["implementation"], "OPERATIONAL_READY")
        self.assertEqual(readiness["milestone"]["status"], "PASS")
        self.assertEqual(
            readiness["runtime_objectives"]["actual_vps_provider_purchase"],
            "LATER_EXTERNAL_AUTHORITY",
        )


if __name__ == "__main__":
    unittest.main()
