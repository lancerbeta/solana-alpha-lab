"""OWNER_TRADING_OPERABILITY_FOUNDATION_V1 owner Workbench presentation."""

from __future__ import annotations

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

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.owner_surface import compact_id_html, paginate
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config
from solana_alpha_lab.factory.trading_runtime_policy import apply_policy, compose_runtime_envelope
from solana_alpha_lab.factory.visual_os import visual_os_layout_css
from solana_alpha_lab.factory.workbench import _operations_section, serve

VISUAL_OS = ROOT / "configs/smial_visual_operating_system_v1.yaml"


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    dest = tmp / "configs" / VISUAL_OS.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(VISUAL_OS.read_bytes())
    return tmp


def _get(app: FactoryApplication, path: str) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=8)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200, body
        return body
    finally:
        server.shutdown()
        server.server_close()


def _reconciled(n: int) -> list[dict[str, str]]:
    return [
        {
            "position_id": f"POS-{index:03d}",
            "bot_instance_id": "BOT-A",
            "strategy_id": "STRAT-A",
            "strategy_version": "V1",
            "mint": "mintA",
            "state": "RECONCILED",
            "opened_at": f"2026-09-01T00:{index:02d}:00Z",
            "closed_at": f"2026-09-02T00:{index:02d}:00Z",
            "entered_notional_usd": "10",
            "pnl_evidence_class": "PAPER_RECONCILED_MODEL",
        }
        for index in range(n)
    ]


class OwnerTradingOperabilityWorkbenchTests(unittest.TestCase):
    def test_wide_layout_uses_workspace_without_dropping_prose_width(self) -> None:
        css = visual_os_layout_css()
        self.assertIn("max-width: none", css)
        self.assertIn("width: 100%", css)
        self.assertIn(".prose, .page-question, .page-note, .copy-text, .help { max-width: 42rem; }", css)
        self.assertIn("section.zone", css)
        self.assertIn("--surface-raised", css)
        self.assertIn("--accent-cobalt", css)

    def test_paginate_page_two_is_26_to_50(self) -> None:
        info = paginate(list(range(50)), page=2, page_size=25)
        self.assertEqual(info["start_ordinal"], 26)
        self.assertEqual(info["end_ordinal"], 50)
        self.assertEqual(info["rows"][0], 25)
        self.assertTrue(info["show_controls"])
        small = paginate(list(range(8)), page=1, page_size=25)
        self.assertFalse(small["show_controls"])
        self.assertEqual(small["total"], 8)

    def test_reconciled_history_is_not_active_inventory(self) -> None:
        html = _operations_section(
            {
                "operations": {
                    "source_status": "PRESENT",
                    "position_rows": _reconciled(8),
                    "bots": [],
                },
                "trading_operations": {
                    "source_status": "PRESENT",
                    "runtime_envelope": {"modes": {}, "by_strategy": []},
                    "contexts": [],
                    "traces": [],
                    "attention": [],
                },
            }
        )
        self.assertIn("ACTIVE POSITIONS = 0", html)
        self.assertIn("Торговые ограничения", html)
        self.assertIn("<h2>Активные позиции</h2>", html)
        self.assertIn("<h2>История</h2>", html)
        self.assertIn("POS-000", html)
        self.assertIn("entity-id", html)
        self.assertNotIn("Баланс", html)
        self.assertNotIn("Доступные деньги", html)

    def test_operations_shows_requested_runtime_effective(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                apply_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    candidate_raw={
                        "new_entries_enabled": True,
                        "global_entry_notional_cap_usd": "10",
                    },
                    expected_current_sha256="0" * 64,
                    idempotency_key="IDEM-UI-1",
                    owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                    reason="UI",
                )
                envelope = compose_runtime_envelope(
                    store,
                    [
                        {
                            "strategy_id": "STRAT-UI",
                            "strategy_version": "V1",
                            "notional_usd": "100",
                            "max_open_positions": 5,
                        }
                    ],
                )
            finally:
                store.close()
        html = _operations_section(
            {
                "operations": {"source_status": "PRESENT", "position_rows": [], "bots": []},
                "trading_operations": {
                    "source_status": "PRESENT",
                    "runtime_envelope": envelope,
                    "contexts": [],
                    "traces": [],
                    "attention": [],
                },
            }
        )
        self.assertIn("Запрос стратегии", html)
        self.assertIn("Runtime cap", html)
        self.assertIn("Эффективно", html)
        self.assertIn("100", html)
        self.assertIn("10", html)
        self.assertIn("Runtime cap (global)", html)
        self.assertNotIn("Эффективный следующий вход", html)
        self.assertIn("NOT_SET", html)
        self.assertIn("StrategyVersion max (на бот)", html)
        paper_rows = [
            row
            for row in envelope["by_strategy"]
            if row["mode"] == "PAPER" and row["strategy_id"] == "STRAT-UI"
        ]
        self.assertEqual(len(paper_rows), 1)
        self.assertEqual(paper_rows[0]["declared_max_open_positions"], 5)
        self.assertIsNone(paper_rows[0]["runtime_max_open_positions"])
        self.assertIsNone(paper_rows[0]["effective_max_open_positions"])
        self.assertIn("entity-id-copy", compact_id_html("POS-UI"))

    def test_operations_http_get_present_store_shows_runtime_envelope(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            strat_dir = root / "configs" / "strategies"
            strat_dir.mkdir(parents=True, exist_ok=True)
            (strat_dir / "STRAT-HTTP-UI.yaml").write_text(
                "\n".join(
                    [
                        "strategy_id: STRAT-HTTP-UI",
                        "strategy_version: V1",
                        "notional_policy:",
                        "  notional_usd: 111",
                        "risk_policy:",
                        "  max_open_positions: 5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            paper_path = root / "local" / "factory_v1" / "paper_plane_state.sqlite"
            paper_path.parent.mkdir(parents=True, exist_ok=True)
            paper = PaperPlaneStore(paper_path)
            try:
                apply_policy(
                    ROOT,
                    paper,
                    mode="PAPER",
                    candidate_raw={
                        "new_entries_enabled": True,
                        "global_entry_notional_cap_usd": "12.5",
                    },
                    expected_current_sha256="0" * 64,
                    idempotency_key="IDEM-HTTP-1",
                    owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                    reason="UI",
                )
            finally:
                paper.close()
            mtime_before = paper_path.stat().st_mtime_ns
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            html = _get(app, "/operations")
            self.assertIn("STRAT-HTTP-UI", html)
            self.assertIn("Запрос стратегии", html)
            self.assertIn("Runtime cap", html)
            self.assertIn("Эффективно", html)
            self.assertIn("111", html)
            self.assertIn("12.5", html)
            self.assertNotIn("PaperPlane отсутствует", html)
            self.assertEqual(paper_path.stat().st_mtime_ns, mtime_before)

    def test_six_surfaces_render_and_get_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                sqlite_before = {
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*.sqlite")
                }
                pages = {
                    path: _get(app, path)
                    for path in (
                        "/",
                        "/research",
                        "/market",
                        "/operations",
                        "/economics",
                        "/system",
                    )
                }
                sqlite_after = {
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*.sqlite")
                }
                self.assertEqual(sqlite_before, sqlite_after)
                self.assertFalse(any("paper_plane" in name for name in sqlite_after))
                self.assertIn("section.zone", pages["/operations"])
                self.assertIn("Торговые ограничения", pages["/operations"])
                research = pages["/research"]
                self.assertIn("research-overview", research)
                self.assertIn("Всего", research)
                self.assertIn("td.num", visual_os_layout_css())
                self.assertIn("runtime-конверт", pages["/economics"])
                self.assertIn("NO OWNER FCF", pages["/economics"])
                home = pages["/"]
                self.assertNotIn("<h2>Точные команды владельца</h2>", home)
            finally:
                paper = getattr(app, "_paper_plane_store", None)
                if paper is not None:
                    paper.close()
                store.close()
