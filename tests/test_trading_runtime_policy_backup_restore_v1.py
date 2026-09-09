"""Isolated backup/restore roundtrip for TradingRuntimePolicy revisions."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hot90_mutable_backup import DEFAULT_MUTABLE_SOURCES
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore
from solana_alpha_lab.factory.trading_runtime_policy import apply_policy, show_policy

PHRASE = "AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY"


class TradingRuntimePolicyBackupRestoreTests(unittest.TestCase):
    def test_paper_plane_sqlite_is_a_mutable_backup_source(self) -> None:
        self.assertIn("local/factory_v1/paper_plane_state.sqlite", DEFAULT_MUTABLE_SOURCES)

    def test_policy_revision_survives_file_copy_restore(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = Path(tmp) / "paper_plane_state.sqlite"
            store = PaperPlaneStore(src)
            try:
                applied = apply_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    candidate_raw={
                        "new_entries_enabled": True,
                        "global_entry_notional_cap_usd": "10",
                        "max_total_open_positions": 10,
                    },
                    expected_current_sha256="0" * 64,
                    idempotency_key="IDEM-BACKUP-1",
                    owner_authorization_phrase=PHRASE,
                    reason="BACKUP_PROOF",
                )
                sha = applied["readback"]["policy_sha256"]
                revision = applied["readback"]["revision"]
            finally:
                store.close()
            restored = Path(tmp) / "restore" / "paper_plane_state.sqlite"
            restored.parent.mkdir()
            shutil.copy2(src, restored)
            reader = PaperPlaneStore(restored, readonly=True)
            try:
                shown = show_policy(reader, "PAPER")
                self.assertEqual(shown["status"], "VALID")
                self.assertEqual(shown["revision"], revision)
                self.assertEqual(shown["policy_sha256"], sha)
                self.assertEqual(shown["policy"]["global_entry_notional_cap_usd"], "10")
            finally:
                reader.close()
