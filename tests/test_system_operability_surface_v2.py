"""SYSTEM_OPERABILITY_SURFACE_V2 vertical acceptance."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
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

from solana_alpha_lab.factory.application import FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.owner_daily_attention import compose_owner_attention  # noqa: E402
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config  # noqa: E402
from solana_alpha_lab.factory.system_operability import (  # noqa: E402
    HTTP_SERVING,
    SYSTEMD_UNAVAILABLE,
    compose_system_operability,
    observation_sqlite_path,
)
from solana_alpha_lab.factory.workbench import _system_section, serve  # noqa: E402
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    search_semantic_routes,
)


NOW = __import__("datetime").datetime(2026, 9, 7, 12, 0, tzinfo=__import__("datetime").UTC)
DIGEST = "a" * 64
UNITS_OK = {
    "factory-observation-schedule.timer": "active",
    "factory-remote-backup.timer": "active",
    "factory-collector-owner-pulse.timer": "active",
    "factory-hot90-closed-day-archive.timer": "active",
    "factory-operability-watch.timer": "active",
    "factory-v1-workbench.service": "active",
}


def _init_git_head(root: Path) -> str:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=lab@example",
            "-c",
            "user.name=lab",
            "commit",
            "--allow-empty",
            "-m",
            "t",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _walk(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _get(app: FactoryApplication, path: str) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200, body
        return body
    finally:
        server.shutdown()
        server.server_close()


def _packet(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "collector_verdict": "OK",
        "health_classes": ["PROCESS_OK"],
        "activation_state": "ACTIVE",
        "filesystem_disk_used_pct": 10,
        "projected_97d_status": "OK",
        "backup_age_seconds": 60,
        "offhost_backup_state": "CURRENT",
        "immutable_archive_latest_verified_day": "20260906",
    }
    base.update(overrides)
    return base


class SystemOperabilitySurfaceV2Tests(unittest.TestCase):
    def test_a1_fake_process_proof(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                model = app.read_model(surface="SYSTEM")
                runtime = model.get("runtime") or {}
                self.assertNotEqual(runtime.get("process_alive"), True)
                self.assertNotIn("process_alive", runtime)
                self.assertNotEqual(model["system_operability"]["state"], "HEALTHY")
                dumped = json.dumps(model["system_operability"])
                self.assertNotIn('"process_alive": true', dumped)
            finally:
                store.close()

    def test_a2_http_vs_systemd(self) -> None:
        units = dict(UNITS_OK)
        units["factory-v1-workbench.service"] = "inactive"
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            http_self=HTTP_SERVING,
            unit_status=units,
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(projection["coverage"]["HTTP_SELF"]["status"], "SERVING")
        self.assertEqual(projection["processes"]["http_self"], HTTP_SERVING)
        self.assertEqual(projection["processes"]["managed_workbench_unit"], "inactive")
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("WORKBENCH_SERVICE_DOWN", codes)
        self.assertNotEqual(projection["state"], "OK_OBSERVED")

    def test_a3_systemd_unavailable_is_not_all_down(self) -> None:
        units = {name: SYSTEMD_UNAVAILABLE for name in UNITS_OK}
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            http_self="NOT_APPLICABLE",
            unit_status=units,
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(projection["coverage"]["SYSTEMD"]["status"], "UNAVAILABLE")
        self.assertEqual(projection["coverage"]["SYSTEMD"]["detail"], SYSTEMD_UNAVAILABLE)
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertNotIn("REQUIRED_TIMER_FAILED", codes)
        self.assertNotIn("WORKBENCH_SERVICE_DOWN", codes)

    def test_a4_absent_observation_store_does_not_create(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            before = _walk(root)
            projection = compose_system_operability(
                root=root,
                now=NOW,
                unit_status=UNITS_OK,
                environ={},
            )
            after = _walk(root)
            self.assertEqual(before, after)
            self.assertEqual(projection["collection"]["source_status"], "NOT_PRESENT")
            self.assertFalse(observation_sqlite_path(root).exists())
            self.assertNotEqual(projection["state"], "OK_OBSERVED")
            self.assertNotEqual(projection["state"], "HEALTHY")

    def test_a5_present_observation_store_is_readonly(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / "obs"
            root.mkdir()
            path = observation_sqlite_path(root)
            writable = ObservationScheduleStore(path)
            writable.record_event("TICK", {"n": 1}, clock=NOW)
            writable.close()
            before = path.read_bytes()
            inventory = _walk(root)
            projection = compose_system_operability(
                root=root,
                now=NOW,
                unit_status=UNITS_OK,
                environ={},
            )
            self.assertEqual(projection["collection"]["source_status"], "PRESENT")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(_walk(root), inventory)

    def test_a6_deploy_identity_match(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / "match"
            root.mkdir()
            marker = _init_git_head(root)
            (root / ".factory_deploy_sha").write_text(marker + "\n", encoding="ascii")
            projection = compose_system_operability(
                root=root,
                now=NOW,
                unit_status=UNITS_OK,
                collector_packet=_packet(),
                environ={},
            )
            self.assertEqual(projection["identity"]["deploy_relation"], "MATCH")
            self.assertEqual(projection["identity"]["deployed_sha"], marker)
            self.assertNotIn(
                "DEPLOY_IDENTITY_MISMATCH",
                {item["attention_code"] for item in projection["attention"]},
            )
            self.assertEqual(projection["coverage"]["STORAGE"]["status"], "AVAILABLE")
            self.assertEqual(projection["state"], "OK_OBSERVED")

    def test_a7_deploy_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / "mismatch"
            root.mkdir()
            _init_git_head(root)
            marker = "c" * 40
            (root / ".factory_deploy_sha").write_text(marker + "\n", encoding="ascii")
            projection = compose_system_operability(
                root=root,
                now=NOW,
                unit_status=UNITS_OK,
                collector_packet=_packet(),
                environ={},
            )
            self.assertEqual(projection["identity"]["deploy_relation"], "MISMATCH")
            self.assertEqual(projection["identity"]["deployed_sha"], marker)
            codes = {item["attention_code"] for item in projection["attention"]}
            self.assertIn("DEPLOY_IDENTITY_MISMATCH", codes)

    def test_b1_stale_collection(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(
                collector_verdict="DEGRADED",
                health_classes=["DATA_STALE"],
            ),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("SOURCE_DATA_STALE", codes)
        self.assertEqual(projection["state"], "DEGRADED")

    def test_b2_required_timer_failure(self) -> None:
        units = dict(UNITS_OK)
        units["factory-observation-schedule.timer"] = "inactive"
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            http_self=HTTP_SERVING,
            unit_status=units,
            collector_packet=_packet(),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("REQUIRED_TIMER_FAILED", codes)
        card = next(item for item in projection["attention"] if item["attention_code"] == "REQUIRED_TIMER_FAILED")
        self.assertTrue(card["AUTHORITY_REQUIRED"])
        self.assertIn("FACTORY_UNATTENDED_OPERABILITY.md", card["RECOVERY_ROUTE"])

    def test_b3_backup_stale(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(health_classes=["BACKUP_DEGRADED"]),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("MUTABLE_BACKUP_STALE", codes)

    def test_b4_offhost_failure(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(health_classes=["OFFHOST_BACKUP_FAILED"]),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("OFFHOST_BACKUP_FAILED", codes)

    def test_b5_archive_hash_mismatch(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(
                collector_verdict="ACTION_REQUIRED",
                health_classes=["IMMUTABLE_ARCHIVE_HASH_MISMATCH"],
            ),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("IMMUTABLE_ARCHIVE_HASH_MISMATCH", codes)
        self.assertEqual(projection["state"], "ACTION_REQUIRED")

    def test_b6_storage_pressure(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(health_classes=["DISK_RUNWAY_TARGET40"]),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("DISK_RUNWAY_TARGET40", codes)

    def test_b7_provider_errors_are_observations(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(health_classes=["PROVIDER_FAILED"]),
            environ={},
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertIn("SUSTAINED_PROVIDER_FAILURE", codes)
        dumped = json.dumps(projection)
        self.assertNotIn("currently unreachable", dumped)

    def test_b8_partial_observability(self) -> None:
        units = dict(UNITS_OK)
        units["factory-remote-backup.timer"] = SYSTEMD_UNAVAILABLE
        partial = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=units,
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(partial["coverage"]["SYSTEMD"]["status"], "PARTIAL")
        self.assertNotEqual(partial["state"], "OK_OBSERVED")

    def test_b9_trading_duplication(self) -> None:
        system = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(),
            environ={},
        )
        codes = {item["attention_code"] for item in system["attention"]}
        self.assertNotIn("UNRESOLVED_POSITION", codes)
        daily = compose_owner_attention(
            trading={
                "source_status": "PRESENT",
                "attention": [
                    {
                        "code": "UNRESOLVED_POSITION",
                        "source_native_identity": "POS-1",
                        "WHY_NOW": "open",
                        "IMPACT": "P0",
                        "EVIDENCE": "POS-1",
                        "NEXT_SAFE_ACTION": "OPEN_OPERATIONS",
                    }
                ],
            },
            system=system,
        )
        ops = [
            item
            for item in daily["current_attention"]
            if item.get("attention_code") == "UNRESOLVED_POSITION"
        ]
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["source_domain"], "OPERATIONS")
        self.assertFalse(
            any(
                item.get("source_domain") == "SYSTEM"
                and item.get("attention_code") == "UNRESOLVED_POSITION"
                for item in daily["current_attention"]
            )
        )
        unknown = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status={name: SYSTEMD_UNAVAILABLE for name in UNITS_OK},
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(unknown["state"], "UNKNOWN")
        home = compose_owner_attention(system=unknown)
        system_cov = next(item for item in home["coverage"] if item["source_domain"] == "SYSTEM")
        self.assertNotEqual(system_cov["CURRENT_STATE"], "AVAILABLE")

    def test_c1_timer_card_has_recovery_fields(self) -> None:
        units = dict(UNITS_OK)
        units["factory-operability-watch.timer"] = "failed"
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=units,
            collector_packet=_packet(),
            environ={},
        )
        card = next(
            item
            for item in projection["attention"]
            if item["attention_code"] == "REQUIRED_TIMER_FAILED"
        )
        for key in (
            "WHAT",
            "EVIDENCE",
            "CURRENT_SAFE_STATE",
            "NEXT_SAFE_ACTION",
            "RECOVERY_ROUTE",
            "AUTHORITY_REQUIRED",
        ):
            self.assertTrue(card.get(key) not in {None, ""}, key)

    def test_c4_recovery_readback(self) -> None:
        before = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status={**UNITS_OK, "factory-observation-schedule.timer": "inactive"},
            collector_packet=_packet(),
            environ={},
        )
        self.assertIn(
            "REQUIRED_TIMER_FAILED",
            {item["attention_code"] for item in before["attention"]},
        )
        after = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(),
            environ={},
        )
        self.assertNotIn(
            "REQUIRED_TIMER_FAILED",
            {item["attention_code"] for item in after["attention"]},
        )

    def test_c5_total_host_death_coverage(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(
            projection["coverage"]["OUT_OF_BAND_HOST_REACHABILITY"]["status"],
            "NOT_CONFIGURED",
        )
        codes = {item["attention_code"] for item in projection["attention"]}
        self.assertNotIn("OUT_OF_BAND_HOST_REACHABILITY", codes)

    def test_d1_get_system_does_not_create_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            before = _walk(root)
            app = FactoryApplication(root=root)
            body = _get(app, "/system")
            after = _walk(root)
            self.assertEqual(before, after)
            self.assertIn("SYSTEM_OPERABILITY", body)
            self.assertIn("технически", body)
            self.assertNotIn("HEALTHY", body.split("non_claims")[0] if "non_claims" in body else body)
            self.assertNotIn('name="command" value="START"', body)
            self.assertNotIn("HEALTHY", json.dumps(app.read_model(surface="SYSTEM")["system_operability"]["state"]))

    def test_get_system_shows_visible_diagnosis(self) -> None:
        units = dict(UNITS_OK)
        units["factory-v1-workbench.service"] = "inactive"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            before = _walk(root)
            app = FactoryApplication(
                root=root,
                unit_status=units,
                collector_packet=_packet(),
            )
            body = _get(app, "/system")
            self.assertEqual(before, _walk(root))
            self.assertIn("технически", body)
            self.assertIn("WORKBENCH_SERVICE_DOWN", body)
            self.assertIn("Почему сейчас", body)
            self.assertIn("FACTORY_UNATTENDED_OPERABILITY.md", body)
            self.assertIn("не SSH", body)
            self.assertIn("Workbench unit не active", body)
            self.assertNotIn("HEALTHY", body.split("non_claims")[0] if "non_claims" in body else body)
            self.assertNotIn('name="command" value="START"', body)

    def test_deploy_strip_ignores_git_capability(self) -> None:
        html = _system_section(
            {
                "state": "UNKNOWN",
                "identity": {
                    "deployed_sha": None,
                    "capability_deploy_version": "git-only-capability",
                },
                "processes": {},
                "collection": {},
                "storage": {},
                "durability": {},
                "alerting": {},
                "coverage": {},
                "attention": [],
            }
        )
        visible = html.split("technical")[0]
        self.assertNotIn("git-only-capability", visible)
        self.assertIn("UNKNOWN", visible)

    def test_offhost_absence_is_not_available(self) -> None:
        packet = _packet()
        packet.pop("offhost_backup_state")
        packet["health_classes"] = ["PROCESS_OK"]
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=packet,
            environ={},
        )
        self.assertEqual(projection["coverage"]["OFFHOST_BACKUP"]["status"], "UNKNOWN")

    def test_unknown_sentinels_are_not_available(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(
                health_classes=["PROCESS_OK"],
                filesystem_disk_used_pct="UNKNOWN",
                projected_97d_status="UNKNOWN",
                backup_age_seconds="UNKNOWN",
                offhost_backup_state="UNKNOWN",
                immutable_archive_latest_verified_day="UNKNOWN",
                collector_verdict="UNKNOWN",
            ),
            environ={},
        )
        coverage = projection["coverage"]
        self.assertEqual(coverage["STORAGE"]["status"], "UNKNOWN")
        self.assertEqual(coverage["MUTABLE_BACKUP"]["status"], "UNKNOWN")
        self.assertEqual(coverage["OFFHOST_BACKUP"]["status"], "UNKNOWN")
        self.assertEqual(coverage["IMMUTABLE_ARCHIVE"]["status"], "UNKNOWN")
        self.assertEqual(coverage["DATA_FRESHNESS"]["status"], "UNKNOWN")
        self.assertNotEqual(projection["state"], "OK_OBSERVED")

    def test_offhost_unknown_blocks_ok_observed(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(offhost_backup_state="UNKNOWN"),
            environ={},
        )
        self.assertEqual(projection["coverage"]["OFFHOST_BACKUP"]["status"], "UNKNOWN")
        self.assertNotEqual(projection["state"], "OK_OBSERVED")

    def test_mixed_storage_sentinel_is_not_available(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / "mixed"
            root.mkdir()
            marker = _init_git_head(root)
            (root / ".factory_deploy_sha").write_text(marker + "\n", encoding="ascii")
            disk_only = compose_system_operability(
                root=root,
                now=NOW,
                unit_status=UNITS_OK,
                collector_packet=_packet(projected_97d_status="UNKNOWN"),
                environ={},
            )
            self.assertEqual(disk_only["coverage"]["STORAGE"]["status"], "UNKNOWN")
            self.assertNotEqual(disk_only["state"], "OK_OBSERVED")
            runway_only = compose_system_operability(
                root=root,
                now=NOW,
                unit_status=UNITS_OK,
                collector_packet=_packet(filesystem_disk_used_pct="UNKNOWN"),
                environ={},
            )
            self.assertEqual(runway_only["coverage"]["STORAGE"]["status"], "UNKNOWN")
            self.assertNotEqual(runway_only["state"], "OK_OBSERVED")

    def test_empty_unit_status_is_not_all_active(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status={},
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(projection["coverage"]["SYSTEMD"]["status"], "UNAVAILABLE")
        self.assertNotEqual(projection["state"], "OK_OBSERVED")

    def test_d2_existing_observation_db_unmodified(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            path = observation_sqlite_path(root)
            writable = ObservationScheduleStore(path)
            writable.record_event("TICK", {"n": 1}, clock=NOW)
            writable.close()
            before = path.read_bytes()
            inventory = _walk(root)
            app = FactoryApplication(root=root)
            _get(app, "/system")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(_walk(root), inventory)

    def test_d3_incident_state_not_written(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            incident = root / "local/factory_v1/operability_incident_state.json"
            incident.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"active": {"SOURCE_DATA_STALE": {"notified": True}}}, sort_keys=True)
            incident.write_text(payload, encoding="utf-8")
            digest = hashlib.sha256(incident.read_bytes()).hexdigest()
            app = FactoryApplication(root=root)
            _get(app, "/system")
            self.assertEqual(hashlib.sha256(incident.read_bytes()).hexdigest(), digest)

    def test_d4_telegram_configured_without_secrets(self) -> None:
        token = "secret-token-value-not-for-output"
        chat = "123456789"
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(),
            environ={
                "FACTORY_TELEGRAM_BOT_TOKEN": token,
                "FACTORY_TELEGRAM_CHAT_ID": chat,
            },
        )
        self.assertEqual(projection["alerting"]["status"], "CONFIGURED")
        dumped = json.dumps(projection)
        self.assertNotIn(token, dumped)
        self.assertNotIn(chat, dumped)

    def test_d5_does_not_shell_remote_doctor(self) -> None:
        text = (SRC / "solana_alpha_lab/factory/system_operability.py").read_text(encoding="utf-8")
        self.assertNotIn("factory_remote_doctor", text)
        self.assertNotIn("doctor_packet", text)

    def test_d6_heartbeat_absent_is_not_configured(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(),
            environ={},
        )
        self.assertEqual(
            projection["out_of_band_host_reachability"]["status"],
            "NOT_CONFIGURED",
        )

    def test_cli_uses_same_composer(self) -> None:
        cli = (ROOT / "scripts/show_system_operability.py").read_text(encoding="utf-8")
        self.assertIn("compose_system_operability", cli)
        self.assertIn("--json", cli)
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        raw = subprocess.check_output(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/show_system_operability.py"),
                "--json",
            ],
            cwd=str(ROOT),
            env=env,
        )
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(payload["schema"], "smial.system-operability-projection")
        dumped = json.dumps(payload)
        self.assertNotIn("HEALTHY", dumped)

    def test_gold_queries_land_on_remote_ops(self) -> None:
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        projection = load_semantic_projection(ROOT)
        hits = search_semantic_routes(
            projection,
            "Is Factory system okay right now?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(hits[0]["semantic_route_id"], "SEM-REMOTE-OPS-RECOVERY")
        restart = search_semantic_routes(
            projection,
            "May I restart or deploy?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(restart[0]["semantic_route_id"], "SEM-AUTHORITY-BOUNDARIES")

    def test_no_healthy_token(self) -> None:
        projection = compose_system_operability(
            root=ROOT,
            now=NOW,
            unit_status=UNITS_OK,
            collector_packet=_packet(),
            environ={},
        )
        self.assertNotEqual(projection["state"], "HEALTHY")
        self.assertIn(projection["state"], {"ACTION_REQUIRED", "DEGRADED", "OK_OBSERVED", "UNKNOWN"})

    def test_readonly_missing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nope.sqlite"
            with self.assertRaisesRegex(ObservationScheduleStoreError, "SOURCE_NOT_PRESENT"):
                ObservationScheduleStore(path, readonly=True)


if __name__ == "__main__":
    unittest.main()
