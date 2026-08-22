"""Zero-network tests for FACTORY_UNATTENDED_SHADOW_VERTICAL_SLICE_V1."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_state_hypothesis import (  # noqa: E402
    build_cohort,
    load_config as load_early_state_config,
)
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore, run_shadow_tick  # noqa: E402
from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    package_backup,
    restore_backup_isolated,
    write_heartbeat,
)
from solana_alpha_lab.factory.unattended_shadow import (  # noqa: E402
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    assert_factory_runner_pin,
    load_shadow_config,
    run_unattended_shadow_tick,
)


class FactoryUnattendedShadowTests(unittest.TestCase):
    def test_factory_runner_pin(self) -> None:
        config = load_shadow_config(ROOT)
        assert_factory_runner_pin(ROOT, config)
        digest = hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)

    def test_shadow_tick_rejects_real_fill_and_uses_shadow_mode(self) -> None:
        early = load_early_state_config(ROOT)
        cohort, _ = build_cohort(ROOT, early)
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "paper.sqlite"
            result = run_shadow_tick(
                ROOT,
                strategy_relative="configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml",
                store_path=store_path,
                cohort=cohort[:5],
            )
            self.assertEqual(result["mode"], "SHADOW")
            self.assertTrue(result["commissioning_only"])
            self.assertFalse(result["factory_core_python_changed"])
            bots = result["bot_instances"]
            self.assertEqual(bots[0]["mode"], "SHADOW")
            for pos in result["positions"]:
                self.assertNotEqual(pos["signal_kind"], "REAL_FILL")
                self.assertEqual(pos["signal_kind"], "SHADOW_EXECUTABLE")
                self.assertEqual(pos["state"], "RECONCILED")

    def test_heartbeat_progress_uses_supplied_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = {
                "monitoring": {"heartbeat_relative": "local/factory_v1/paper_heartbeat.json"},
                "deploy": {"version": "test"},
            }
            (root / "local/factory_v1").mkdir(parents=True)
            path = write_heartbeat(
                root,
                config=cfg,
                kind="SHADOW_HEARTBEAT",
                progress_at="2026-08-22T00:00:00Z",
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("SHADOW_HEARTBEAT", text)
            self.assertIn('"progress_at": "2026-08-22T00:00:00Z"', text)

    def test_restart_preserves_reconciled_positions(self) -> None:
        early = load_early_state_config(ROOT)
        cohort, _ = build_cohort(ROOT, early)
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "paper.sqlite"
            first = run_shadow_tick(
                ROOT,
                strategy_relative="configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml",
                store_path=store_path,
                cohort=cohort[:3],
            )
            second = run_shadow_tick(
                ROOT,
                strategy_relative="configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml",
                store_path=store_path,
                cohort=cohort[:3],
            )
            self.assertEqual(first["shadow_observations"], second["shadow_observations"])
            self.assertEqual(len(first["positions"]), len(second["positions"]))
            store = PaperPlaneStore(store_path)
            try:
                self.assertEqual(store.bots()[0]["status"], "RUNNING")
            finally:
                store.close()

    def test_isolated_backup_restore_of_paper_sqlite(self) -> None:
        early = load_early_state_config(ROOT)
        cohort, _ = build_cohort(ROOT, early)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_rel = "local/factory_v1/paper_plane_state.sqlite"
            ops_rel = "local/factory_v1/operational_state.sqlite"
            (root / "local/factory_v1").mkdir(parents=True)
            (root / ops_rel).write_bytes(b"")
            run_shadow_tick(
                ROOT,
                strategy_relative="configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml",
                store_path=root / store_rel,
                cohort=cohort[:2],
            )
            before = hashlib.sha256((root / store_rel).read_bytes()).hexdigest()
            remote_cfg = {
                "backup": {
                    "same_parent_forbidden": True,
                    "source_relative_paths": [ops_rel, store_rel],
                    "sink_relative": "local/factory_v1_backup_sink",
                },
                "deploy": {"version": "test"},
                "monitoring": {"heartbeat_relative": "local/factory_v1/paper_heartbeat.json"},
            }
            sink = root / "backup_sink_independent"
            packed = package_backup(root, config=remote_cfg, sink_override=sink)
            bundle = sink / packed["bundle"]
            dest = root / "restore_isolated"
            restore_backup_isolated(bundle=bundle, dest_root=dest)
            restored = dest / store_rel
            self.assertTrue(restored.is_file())
            after = hashlib.sha256(restored.read_bytes()).hexdigest()
            self.assertEqual(before, after)

    def test_end_to_end_tick_writes_receipt_fields(self) -> None:
        early = load_early_state_config(ROOT)
        try:
            build_cohort(ROOT, early)
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"pinned cohort unavailable: {exc}")
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "shadow.sqlite"
            result = run_unattended_shadow_tick(ROOT, store_path=store_path)
            self.assertTrue(result["commissioning_only"])
            self.assertFalse(result["scientific_shadow_pass"])
            self.assertEqual(result["operations_view"]["mode"], "SHADOW")
            self.assertIn("bot", result["operations_view"])


if __name__ == "__main__":
    unittest.main()
