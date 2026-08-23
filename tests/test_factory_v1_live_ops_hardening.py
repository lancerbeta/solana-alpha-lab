from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.live_ops_hardening import (
    LiveOpsHardeningError,
    build_acceptance,
    clear_diagnostic_inject,
    compose_health_clocks,
    prove_financial_boundary,
    prove_incident_lifecycle,
    prove_local_clean_rehost,
    prove_local_release_rollback,
    prove_phase0_local,
    run_fault_matrix,
    validate_host_proof,
    write_diagnostic_inject,
)
from solana_alpha_lab.factory.remote_ops import (
    load_config,
    package_backup,
    write_heartbeat,
)

SCHEMA = ROOT / "catalog/schemas/factory_v1_live_ops_hardening.schema.json"
HOST_SCHEMA = ROOT / "catalog/schemas/factory_v1_live_ops_hardening_host_proof.schema.json"
HOST_PROOF = ROOT / "docs/evidence/factory_v1_live_ops_hardening/a1_host_proof_v1.json"
COPY_RELATIVES = [
    "catalog/schemas/factory_remote_operations.schema.json",
    "configs/factory_remote_operations_v1.yaml",
    "configs/factory_v1_live_ops_hardening_v1.yaml",
    "configs/factory_v1_linux_runtime/factory-v1-workbench.service",
    "configs/factory_remote_ops/sshd_factory.conf",
    "configs/factory_remote_ops/nftables_factory.conf",
    "configs/factory_remote_ops/fail2ban_sshd.local",
    "configs/factory_remote_ops/factory-remote-health.service",
    "configs/factory_remote_ops/factory-remote-backup.service",
    "configs/factory_remote_ops/factory-remote-backup.timer",
    "configs/factory_remote_ops/factory-paper-heartbeat.service",
    "configs/factory_remote_ops/factory-paper-heartbeat.timer",
    "configs/factory_remote_ops/secrets.env.example",
    "src/solana_alpha_lab/factory/remote_ops.py",
    "src/solana_alpha_lab/factory/live_ops_hardening.py",
    "scripts/factory_remote_doctor.py",
    "scripts/run_factory_unattended_shadow_tick.py",
]


def _copy_tree(dst: Path) -> Path:
    for relative in COPY_RELATIVES:
        source = ROOT / relative
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return dst


def _seed_stores(root: Path) -> None:
    config = load_config(root)
    ops = root / config["stores"]["operational_relative"]
    paper = root / config["stores"]["paper_relative"]
    ops.parent.mkdir(parents=True, exist_ok=True)
    ops.write_bytes(b"ops-seed")
    if paper.is_file():
        paper.unlink()
    import sqlite3

    conn = sqlite3.connect(paper)
    conn.execute(
        "CREATE TABLE bot_instances (bot_instance_id TEXT PRIMARY KEY, strategy_id TEXT, strategy_version TEXT, mode TEXT, status TEXT, started_at TEXT, stopped_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE positions (position_id TEXT PRIMARY KEY, bot_instance_id TEXT, mint TEXT, state TEXT, signal_kind TEXT, entered_notional_usd REAL, exit_notional_usd REAL, opened_at TEXT, closed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO bot_instances VALUES ('BOT-1','STRAT','v1','PAPER','RUNNING','2026-08-22T00:00:00Z',NULL)"
    )
    conn.execute(
        "INSERT INTO positions VALUES ('POS-1','BOT-1','Mint11111111','RECONCILED', 'SIMULATED_FILL', 1.0, 1.0, '2026-08-22T00:00:00Z', NULL)"
    )
    conn.commit()
    conn.close()


class LiveOpsHardeningPhase0Tests(unittest.TestCase):
    def test_market_data_stale_distinct_from_worker_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            write_heartbeat(root)
            package_backup(root)
            stale_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
            write_diagnostic_inject(
                root,
                {
                    "market_data": {
                        "applicability": "REQUIRED",
                        "observed_at": stale_at,
                        "status": "STALE",
                    }
                },
            )
            health = compose_health_clocks(root=root, process_alive=True)
            self.assertEqual(health["clocks"]["worker"]["status"], "ALIVE")
            self.assertEqual(health["clocks"]["market_data"]["status"], "STALE")
            self.assertEqual(health["verdict"], "DEGRADED_STALE_DATA")
            clear_diagnostic_inject(root)

    def test_commissioning_provider_not_required_is_not_ok_lie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            write_heartbeat(root)
            package_backup(root)
            health = compose_health_clocks(root=root, process_alive=True)
            self.assertEqual(health["clocks"]["provider"]["status"], "NOT_REQUIRED")
            self.assertTrue(health["provider_health_visible"])
            with self.assertRaisesRegex(LiveOpsHardeningError, "PROVIDER_OK_WITHOUT_REQUIREMENT"):
                write_diagnostic_inject(
                    root,
                    {
                        "provider": {
                            "applicability": "NOT_REQUIRED_COMMISSIONING_ONLY",
                            "status": "OK",
                        }
                    },
                )
                compose_health_clocks(root=root, process_alive=True)

    def test_incident_lifecycle_redelivers_after_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            delivered: list[str] = []

            def transport(token: str, body: str) -> None:
                delivered.append(body)

            result = prove_incident_lifecycle(
                root=root,
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "t",
                    "FACTORY_TELEGRAM_CHAT_ID": "1",
                },
                transport=transport,
            )
            self.assertEqual(result["first_delivery"], "PASS")
            self.assertEqual(result["duplicate_dedup"], "PASS")
            self.assertEqual(result["recovery"], "PASS")
            self.assertEqual(result["recurrence_redelivery"], "PASS")
            self.assertEqual(len(delivered), 2)

    def test_financial_boundary_positive(self) -> None:
        proof = prove_financial_boundary(ROOT)
        self.assertTrue(proof["destructive_and_financial_actions_separately_gated"])
        self.assertEqual(proof["shadow_financial_authority"], "DENIED")
        self.assertFalse(proof["signer_material_present"])
        self.assertFalse(proof["transaction_submit_capability_present"])
        self.assertEqual(proof["financial_command_surface_hits"], [])

    def test_local_release_rollback_and_rehost(self) -> None:
        import subprocess

        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        parent = subprocess.check_output(
            ["git", "rev-parse", "HEAD~1"], cwd=ROOT, text=True
        ).strip()
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            subprocess.check_call(
                ["git", "worktree", "add", "--detach", str(work), head], cwd=ROOT
            )
            try:
                release = prove_local_release_rollback(
                    work_root=work, target_sha=head, previous_sha=parent
                )
                self.assertTrue(release["local_deploy_rollback"])
                self.assertTrue(release["local_forward_restore"])
                self.assertFalse(release["live_deploy_rollback"])
                self.assertFalse(release["live_forward_restore"])
                self.assertFalse(release["left_on_rollback_sha"])
            finally:
                subprocess.check_call(
                    ["git", "worktree", "remove", "--force", str(work)], cwd=ROOT
                )
            rehost_root = Path(tmp) / "rehost"
            rehost = prove_local_clean_rehost(
                src_root=ROOT,
                empty_root=rehost_root,
                relatives=[
                    "configs/factory_v1_live_ops_hardening_v1.yaml",
                    "configs/factory_remote_operations_v1.yaml",
                ],
            )
            self.assertTrue(rehost["local_clean_rehost"])
            self.assertFalse(rehost["live_clean_rehost"])
            self.assertFalse(rehost["copied_venv"])

    def test_archive_deploy_preserves_local(self) -> None:
        import importlib.util
        import subprocess

        spec = importlib.util.spec_from_file_location(
            "factory_live_release",
            ROOT / "scripts/factory_live_release.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory() as tmp:
            deploy = Path(tmp) / "deploy"
            deploy.mkdir()
            (deploy / "local").mkdir()
            (deploy / "local" / "keep.txt").write_text("preserve\n", encoding="utf-8")
            (deploy / "stale.txt").write_text("gone\n", encoding="utf-8")
            result = mod.deploy_exact_sha(
                repo=ROOT,
                deploy_root=deploy,
                sha=head,
                sync_env=False,
                restart=False,
            )
            self.assertEqual(result["sha"], head)
            self.assertEqual((deploy / ".factory_deploy_sha").read_text(encoding="utf-8").strip(), head)
            self.assertTrue((deploy / "local" / "keep.txt").is_file())
            self.assertFalse((deploy / "stale.txt").exists())
            self.assertTrue((deploy / "configs/factory_remote_operations_v1.yaml").is_file())

    def test_fault_matrix_marks_mock_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            env = {
                "FACTORY_TELEGRAM_BOT_TOKEN": "t",
                "FACTORY_TELEGRAM_CHAT_ID": "1",
            }
            delivered: list[str] = []

            def transport(token: str, body: str) -> None:
                delivered.append(body)

            faults = run_fault_matrix(root=root, environ=env, transport=transport)
            self.assertEqual(faults["checks"]["stale_data_alert"], "PASS")
            self.assertEqual(faults["checks"]["bot_stall_alert"], "PASS")
            self.assertTrue(faults["provider_failure_alert_tested"])
            self.assertTrue(faults["provider_health_visible"])
            self.assertEqual(faults["alert_transport"], "MOCK")
            self.assertFalse(
                (root / "local/factory_v1/diagnostic_health_inject.json").is_file()
            )

    def test_phase0_never_mints_live_pass_acceptance(self) -> None:
        phase0 = prove_phase0_local(ROOT)
        self.assertEqual(phase0["terminal"], "PHASE0_LOCAL_PASS")
        self.assertNotIn("acceptance_draft", phase0)
        self.assertFalse(phase0["local_runtime"]["live_deploy_rollback"])
        self.assertFalse(phase0["local_runtime"]["live_clean_rehost"])
        self.assertEqual(phase0["local_monitoring"]["alert_transport"], "MOCK")
        with self.assertRaisesRegex(LiveOpsHardeningError, "ACCEPTANCE_REQUIRES_LIVE_HOST_PROOF"):
            build_acceptance(
                runtime=phase0["local_runtime"],
                monitoring=phase0["local_monitoring"],
                incident_lifecycle=phase0["local_incident_lifecycle"],
                security=phase0["local_security"],
                live_bound=False,
            )

    def test_host_proof_builds_live_acceptance(self) -> None:
        host = json.loads(HOST_PROOF.read_text(encoding="utf-8"))
        jsonschema.validate(host, json.loads(HOST_SCHEMA.read_text(encoding="utf-8")))
        validate_host_proof(host)
        hp_sha = hashlib.sha256(HOST_PROOF.read_bytes()).hexdigest()
        acceptance = build_acceptance(
            runtime={
                **host["runtime"],
                "release_steps": host["release_steps"],
                "host": host["host"],
                "deploy_sha": host["deploy_sha"],
            },
            monitoring=host["monitoring"],
            incident_lifecycle=host["incident_lifecycle"],
            security=host["security"],
            side_effects=host["side_effects"],
            host=host["host"],
            deploy_sha=host["deploy_sha"],
            host_proof_sha256=hp_sha,
            live_bound=True,
        )
        jsonschema.validate(acceptance, json.loads(SCHEMA.read_text(encoding="utf-8")))
        self.assertEqual(acceptance["terminal"], "FACTORY_V1_LIVE_OPS_HARDENING_PASS")
        self.assertEqual(acceptance["host"], "factory-remote-ops")
        self.assertEqual(acceptance["monitoring"]["alert_transport"], "LIVE")
        self.assertEqual(acceptance["host_proof_sha256"], hp_sha)

    def test_host_proof_rejects_inconsistent_release_steps(self) -> None:
        host = json.loads(HOST_PROOF.read_text(encoding="utf-8"))
        host["runtime"]["previous_sha"] = "63429c0965e3d775edeaaadeb183b40f3352ec0c"
        with self.assertRaisesRegex(LiveOpsHardeningError, "HOST_PROOF_ROLLBACK_STEP_MISMATCH"):
            validate_host_proof(host)
        host = json.loads(HOST_PROOF.read_text(encoding="utf-8"))
        host["release_steps"][-1]["doctor_verdict"] = "DEGRADED_BACKUP_AGE"
        with self.assertRaisesRegex(LiveOpsHardeningError, "HOST_PROOF_FINAL_DOCTOR_NOT_PROVED"):
            validate_host_proof(host)


if __name__ == "__main__":
    unittest.main()
