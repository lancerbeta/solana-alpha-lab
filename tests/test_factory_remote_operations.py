from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.remote_ops import (
    RemoteOpsError,
    doctor_packet,
    emit_alert,
    emit_health_alert,
    format_alert,
    load_config,
    package_backup,
    project_health,
    prove_git_side,
    require_secret,
    restore_backup_isolated,
    verify_security_templates,
    write_heartbeat,
)


SCHEMA = ROOT / "catalog/schemas/factory_remote_operations.schema.json"
COPY_RELATIVES = [
    "catalog/schemas/factory_remote_operations.schema.json",
    "configs/factory_remote_operations_v1.yaml",
    "configs/factory_v1_linux_runtime/factory-v1-workbench.service",
    "configs/factory_remote_ops/sshd_factory.conf",
    "configs/factory_remote_ops/nftables_factory.conf",
    "configs/factory_remote_ops/fail2ban_sshd.local",
    "configs/factory_remote_ops/factory-remote-health.service",
    "configs/factory_remote_ops/factory-remote-backup.service",
    "configs/factory_remote_ops/factory-remote-backup.timer",
    "configs/factory_remote_ops/factory-remote-backup-gdrive.service",
    "configs/factory_remote_ops/factory-paper-heartbeat.service",
    "configs/factory_remote_ops/factory-paper-heartbeat.timer",
    "configs/factory_remote_ops/secrets.env.example",
]


def _copy_tree(dst: Path) -> Path:
    for relative in COPY_RELATIVES:
        source = ROOT / relative
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return dst


def _seed_stores(root: Path, *, open_position: bool = False) -> None:
    config = load_config(root)
    ops = root / config["stores"]["operational_relative"]
    paper = root / config["stores"]["paper_relative"]
    ops.parent.mkdir(parents=True, exist_ok=True)
    ops.write_bytes(b"ops-seed")
    if paper.is_file():
        paper.unlink()
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
    state = "OPEN" if open_position else "RECONCILED"
    conn.execute(
        "INSERT INTO positions VALUES ('POS-1','BOT-1','Mint11111111',?, 'SIMULATED_FILL', 1.0, 1.0, '2026-08-22T00:00:00Z', NULL)",
        (state,),
    )
    conn.commit()
    conn.close()


class FactoryRemoteOperationsTests(unittest.TestCase):
    def test_config_freezes_cherry_vps4_not_bomzh(self) -> None:
        config = load_config(ROOT)
        jsonschema.validate(config, json.loads(SCHEMA.read_text(encoding="utf-8")))
        self.assertEqual(config["target"]["provider"], "CHERRY_SERVERS")
        self.assertEqual(config["target"]["sku"], "CLOUD_VPS_4_GEN2")
        self.assertEqual(config["target"]["rejected_sku"], "CLOUD_VPS_1_GEN2")
        self.assertEqual(config["target"]["purchase"], "OWNER_EXTERNAL_GATE")
        self.assertEqual(config["workbench"]["bind"], "127.0.0.1")
        self.assertEqual(config["workbench"]["access"], "SSH_TUNNEL_ONLY")
        self.assertTrue(config["health"]["process_alive_alone_is_not_healthy"])
        self.assertEqual(config["backup"]["google_drive_role"], "OPTIONAL_COLD_COPY_NOT_DOD")
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1

        v1_1 = load_config_v1_1(ROOT)
        self.assertEqual(v1_1["backup"]["google_drive_role"], "PROVEN_OFFHOST_DURABILITY")
        dumped = yaml.safe_dump(config)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", dumped)
        self.assertNotIn("CLOUD_VPS_1_GEN2", dumped.split("rejected_sku:")[0])

    def test_security_templates_reject_password_root_and_public_admin(self) -> None:
        security = verify_security_templates(ROOT)
        self.assertFalse(security["password_ssh"])
        self.assertFalse(security["permit_root_login"])
        self.assertFalse(security["public_admin"])
        self.assertTrue(security["fail2ban"])
        sshd = (ROOT / "configs/factory_remote_ops/sshd_factory.conf").read_text(encoding="utf-8")
        self.assertIn("AllowUsers factory", sshd)
        self.assertIn("PermitRootLogin no", sshd)
        unit = (ROOT / "configs/factory_v1_linux_runtime/factory-v1-workbench.service").read_text(
            encoding="utf-8"
        )
        self.assertIn("--host 127.0.0.1", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_public_bind_is_security_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            unit = root / "configs/factory_v1_linux_runtime/factory-v1-workbench.service"
            unit.write_text(unit.read_text(encoding="utf-8").replace("127.0.0.1", "0.0.0.0"), encoding="utf-8")
            with self.assertRaisesRegex(RemoteOpsError, "UNHEALTHY_SECURITY_BASELINE"):
                verify_security_templates(root)

    def test_secret_has_no_default(self) -> None:
        with self.assertRaisesRegex(RemoteOpsError, "SECRET_MISSING:FACTORY_TELEGRAM_BOT_TOKEN"):
            require_secret("FACTORY_TELEGRAM_BOT_TOKEN", {})
        source = (ROOT / "src/solana_alpha_lab/factory/remote_ops.py").read_text(encoding="utf-8")
        self.assertNotIn("os.environ.get('JWT", source)
        self.assertNotIn('os.environ.get("JWT', source)
        self.assertNotIn("default=", source)

    def test_process_alive_alone_is_not_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            health = project_health(root=root, process_alive=True)
            self.assertTrue(health["process_alive"])
            self.assertNotEqual(health["verdict"], "HEALTHY")
            self.assertEqual(health["dimensions"]["process"], "ALIVE")
            self.assertIn(health["verdict"], {"DEGRADED_BACKUP_AGE", "DEGRADED_STALE_DATA", "DEGRADED_BOT_STALL"})

    def test_down_process_is_unhealthy_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            health = project_health(root=root, process_alive=False)
            self.assertEqual(health["verdict"], "UNHEALTHY_NOT_RUNNING")
            self.assertNotEqual(health["verdict"], "HEALTHY")

    def test_independent_backup_restore_and_same_parent_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            packed = package_backup(root)
            restored_root = Path(tmp) / "restore"
            restored = restore_backup_isolated(
                bundle=root / "local/factory_v1_backup_sink" / packed["bundle"],
                dest_root=restored_root,
            )
            self.assertEqual(restored["count"], 2)
            for item in restored["restored"]:
                self.assertEqual(
                    (restored_root / item["path"]).read_bytes(),
                    (root / item["path"]).read_bytes(),
                )
            with self.assertRaisesRegex(RemoteOpsError, "BACKUP_SINK_NOT_INDEPENDENT"):
                package_backup(root, sink_override=(root / "local/factory_v1"))

    def test_stale_heartbeat_and_unresolved_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root, open_position=True)
            write_heartbeat(root)
            health = project_health(root=root, process_alive=True)
            self.assertEqual(health["verdict"], "UNHEALTHY_UNRESOLVED_POSITION")
            old = datetime.now(UTC) - timedelta(hours=4)
            path = root / load_config(root)["monitoring"]["heartbeat_relative"]
            path.write_text(
                json.dumps({"kind": "PAPER_HEARTBEAT", "observed_at": old.isoformat().replace("+00:00", "Z")}),
                encoding="utf-8",
            )
            _seed_stores(root, open_position=False)
            packed = package_backup(root)
            self.assertTrue(packed["sha256"])
            health = project_health(
                root=root,
                process_alive=True,
                now=datetime.now(UTC),
            )
            self.assertEqual(health["dimensions"]["data_freshness"], "STALE")
            self.assertNotEqual(health["verdict"], "HEALTHY")

    def test_alert_dedup_and_missing_token(self) -> None:
        config = load_config(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "alerts.json"
            sent: list[str] = []

            def transport(token: str, body: str) -> None:
                self.assertEqual(token, "placeholder-token")
                sent.append(body)

            first = emit_alert(
                config=config,
                incident_key="kill-worker",
                what="paper worker down",
                why_it_matters="unattended paper bot is not progressing",
                current_safe_state="NO_NEW_ENTRIES",
                required_action="START_REMOTE_PROCESSES",
                store=store,
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "placeholder-token",
                    "FACTORY_TELEGRAM_CHAT_ID": "1",
                },
                transport=transport,
            )
            second = emit_alert(
                config=config,
                incident_key="kill-worker",
                what="paper worker down",
                why_it_matters="unattended paper bot is not progressing",
                current_safe_state="NO_NEW_ENTRIES",
                required_action="START_REMOTE_PROCESSES",
                store=store,
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "placeholder-token",
                    "FACTORY_TELEGRAM_CHAT_ID": "1",
                },
                transport=transport,
            )
            self.assertTrue(first["delivered"])
            self.assertFalse(second["delivered"])
            self.assertTrue(second["deduped"])
            self.assertEqual(len(sent), 1)
            self.assertIn("🛠️", sent[0])
            self.assertIn("🔵", sent[0])
            self.assertIn("📈", sent[0])
            self.assertIn("<b>FACTORY</b>", sent[0])
            self.assertIn("<code>OPS</code>", sent[0])
            self.assertIn("<b>ЧТО</b>", sent[0])
            self.assertIn("<b>ПОЧЕМУ ЭТО ВАЖНО</b>", sent[0])
            self.assertIn("<b>СЕЙЧАС БЕЗОПАСНО</b>", sent[0])
            self.assertIn("<b>ЧТО СДЕЛАТЬ</b>", sent[0])
            self.assertIn("<b>ТОРГОВЛЯ</b>", sent[0])
            self.assertIn("<b>ХОСТ</b>", sent[0])
            self.assertIn("Напишите агенту: процесс Factory упал", sent[0])
            self.assertIn("SSH tunnel", sent[0])
            self.assertIn("<code>127.0.0.1:8765</code>", sent[0])
            self.assertNotIn("WHAT:", sent[0])
            trade = format_alert(
                what="x",
                why_it_matters="y",
                current_safe_state="z",
                required_action="a",
                kind="TRADE",
            )
            security = format_alert(
                what="x",
                why_it_matters="y",
                current_safe_state="z",
                required_action="a",
                kind="SECURITY",
            )
            self.assertIn("🟢", trade)
            self.assertIn("📈", trade)
            self.assertIn("<code>TRADE</code>", trade)
            self.assertIn("ожидание контура", trade)
            mocked = format_alert(
                what="Paper-бот закрыл смоделированную позицию",
                why_it_matters="Так будет выглядеть рутина гипотезы, пока нет live",
                current_safe_state="NO_NEW_ENTRIES",
                required_action="Ничего, это эмуляция",
                kind="TRADE",
                trade={
                    "emulation": True,
                    "action": "позиция закрыта",
                    "bot": "paper-h900-01",
                    "hypothesis": "H900-MOCK",
                    "ticker": "$PEPEMOCK",
                    "mint_short": "Paper1111…mock",
                    "side": "long",
                    "notional_usd": "$18.50",
                    "pnl_usd": "+$0.74",
                    "horizon": "H900",
                    "state": "RECONCILED",
                },
            )
            self.assertIn("ЭМУЛЯЦИЯ", mocked)
            self.assertIn("$PEPEMOCK", mocked)
            self.assertIn("paper-h900-01", mocked)
            self.assertIn("не деньги", mocked)
            with self.assertRaisesRegex(RemoteOpsError, "TRADE_BLOCK_REQUIRES_EMULATION"):
                format_alert(
                    what="x",
                    why_it_matters="y",
                    current_safe_state="z",
                    required_action="a",
                    kind="TRADE",
                    trade={"emulation": False, "ticker": "$X"},
                )
            self.assertIn("🔴", security)
            self.assertIn("🛡️", security)
            self.assertIn("<code>SEC</code>", security)
            with self.assertRaisesRegex(RemoteOpsError, "ALERT_KIND_INVALID"):
                format_alert(
                    what="x",
                    why_it_matters="y",
                    current_safe_state="z",
                    required_action="a",
                    kind="NEWS",
                )
            with self.assertRaisesRegex(RemoteOpsError, "SECRET_MISSING"):
                emit_alert(
                    config=config,
                    incident_key="other",
                    what="x",
                    why_it_matters="y",
                    current_safe_state="z",
                    required_action="a",
                    store=store,
                    environ={},
                    transport=transport,
                )

    def test_git_side_prove_and_doctor_omit_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            write_heartbeat(root)
            package_backup(root)
            packet = doctor_packet(root, process_alive=True, git_sha="abc123")
            dumped = json.dumps(packet)
            self.assertNotIn("placeholder-token", dumped)
            self.assertNotEqual(packet["verdict"], "HEALTHY")
            self.assertEqual(packet["sku"], "CLOUD_VPS_4_GEN2")
            proved = prove_git_side(root, isolated_sink=Path(tmp) / "sink")
            self.assertEqual(proved["terminal"], "FACTORY_REMOTE_OPERATIONS_GIT_READY")
            self.assertEqual(proved["purchase"], "OWNER_EXTERNAL_GATE")

    def test_bot_stall_when_progress_stale_heartbeat_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            write_heartbeat(root)
            package_backup(root)
            path = root / load_config(root)["monitoring"]["heartbeat_relative"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["progress_at"] = (datetime.now(UTC) - timedelta(hours=2)).isoformat().replace(
                "+00:00", "Z"
            )
            path.write_text(json.dumps(payload), encoding="utf-8")
            health = project_health(root=root, process_alive=True)
            self.assertEqual(health["dimensions"]["data_freshness"], "OK")
            self.assertEqual(health["verdict"], "DEGRADED_BOT_STALL")

    def test_unreadable_paper_store_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            write_heartbeat(root)
            paper = root / load_config(root)["stores"]["paper_relative"]
            paper.write_bytes(b"not-a-sqlite-database")
            health = project_health(root=root, process_alive=True)
            self.assertEqual(health["paper"]["store"], "UNREADABLE")
            self.assertEqual(health["verdict"], "UNHEALTHY_UNRESOLVED_POSITION")

    def test_backup_sink_env_absolute_and_rejects_store_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            sink = Path(tmp) / "volume-sink"
            packed = package_backup(
                root,
                environ={"FACTORY_BACKUP_SINK": str(sink)},
            )
            self.assertTrue((sink / packed["bundle"]).is_file())
            health = project_health(
                root=root,
                process_alive=True,
                environ={"FACTORY_BACKUP_SINK": str(sink)},
            )
            self.assertEqual(health["backup_domain"], "ABSOLUTE_SINK_SAME_VOLUME")
            with self.assertRaisesRegex(RemoteOpsError, "BACKUP_SINK_NOT_INDEPENDENT"):
                package_backup(
                    root,
                    environ={"FACTORY_BACKUP_SINK": str(root / "local/factory_v1")},
                )
            with self.assertRaisesRegex(RemoteOpsError, "BACKUP_SINK_ENV_NOT_ABSOLUTE"):
                package_backup(root, environ={"FACTORY_BACKUP_SINK": "relative/sink"})

    def test_health_alert_emits_once_from_packet(self) -> None:
        config = load_config(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_tree(Path(tmp) / "src")
            _seed_stores(root)
            store = Path(tmp) / "alerts.json"
            sent: list[str] = []

            def transport(token: str, body: str) -> None:
                sent.append(body)

            packet = {
                "verdict": "UNHEALTHY_NOT_RUNNING",
                "alert_configured": True,
                "next_safe_action": "START_REMOTE_PROCESSES",
            }
            env = {
                "FACTORY_TELEGRAM_BOT_TOKEN": "placeholder-token",
                "FACTORY_TELEGRAM_CHAT_ID": "1",
            }
            first = emit_health_alert(
                root=root,
                packet=packet,
                config=config,
                store=store,
                environ=env,
                transport=transport,
            )
            second = emit_health_alert(
                root=root,
                packet=packet,
                config=config,
                store=store,
                environ=env,
                transport=transport,
            )
            self.assertTrue(first["delivered"])
            self.assertTrue(second["deduped"])
            self.assertEqual(len(sent), 1)
            self.assertNotIn("text", first)
            skip = emit_health_alert(
                root=root,
                packet={"verdict": "RUNTIME_PROVED_BACKUP_INDEPENDENT", "alert_configured": True},
                config=config,
                store=store,
                environ=env,
                transport=transport,
            )
            self.assertEqual(skip["skipped"], "NO_INCIDENT")

    def test_doctor_cli_does_not_force_process_alive(self) -> None:
        source = (ROOT / "scripts/factory_remote_doctor.py").read_text(encoding="utf-8")
        self.assertNotIn("default=True", source)
        self.assertIn("observe_workbench_alive", source)
        self.assertIn("emit_health_alert", source)

    def test_install_apply_refuses_without_owner_packet(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/factory_remote_install.py"), "--apply"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("APPLY_REQUIRES_OWNER_PACKET", completed.stdout)


if __name__ == "__main__":
    unittest.main()
