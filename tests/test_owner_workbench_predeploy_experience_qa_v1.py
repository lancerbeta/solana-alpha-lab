"""OWNER_WORKBENCH_PREDEPLOY_EXPERIENCE_QA_V1: scan-first presentation, unchanged commands."""

from __future__ import annotations

import re
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
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config
from solana_alpha_lab.factory.visual_os import visual_os_layout_css
from solana_alpha_lab.factory.owner_language import research_copy, surface_copy
from solana_alpha_lab.factory.owner_surface import command_button
from solana_alpha_lab.factory.workbench import (
    OPERATOR_COMMANDS,
    _attention,
    _count_and_status,
    _daily_attention,
    _eco_money_and_status,
    _research_rows,
    _system_section,
    serve,
)

VISUAL_OS = ROOT / "configs/smial_visual_operating_system_v1.yaml"
PATHS = ("/", "/research", "/market", "/operations", "/economics", "/system")


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
        conn = HTTPConnection(host, port, timeout=3)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200, body
        return body
    finally:
        server.shutdown()
        server.server_close()


class OwnerWorkbenchPredeployExperienceQaTests(unittest.TestCase):
    def test_attention_scan_first_keeps_canonical_tokens(self) -> None:
        html = _daily_attention(
            [
                {
                    "attention_code": "PNL_UNKNOWN_OR_STALE",
                    "priority": "P0",
                    "WHY_NOW": "Known inventory lacks a known mark",
                    "IMPACT": "Exposure/PnL cannot be treated as zero",
                    "EVIDENCE": "pnl_status:UNKNOWN",
                    "NEXT_SAFE_ACTION": "INSPECT_MARK",
                    "drilldown_target": "/operations",
                }
            ],
            empty="empty",
        )
        self.assertIn("details class=\"attention attention-p0 attention-scan\"", html)
        self.assertIn("<summary>", html)
        self.assertIn("PNL_UNKNOWN_OR_STALE", html)
        self.assertIn("WHY_NOW", html)
        self.assertIn("INSPECT_MARK", html)
        self.assertIn("Открыть источник", html)
        self.assertIn("/operations", html)
        self.assertNotIn("<article class=\"attention\">", html)

    def test_new_since_review_is_visible_on_closed_summary(self) -> None:
        html = _daily_attention(
            [
                {
                    "attention_code": "PNL_UNKNOWN_OR_STALE",
                    "priority": "P0",
                    "WHY_NOW": "Known inventory lacks a known mark",
                    "IMPACT": "Exposure/PnL cannot be treated as zero",
                    "EVIDENCE": "pnl_status:UNKNOWN",
                    "NEXT_SAFE_ACTION": "INSPECT_MARK",
                    "new_since_review": True,
                    "drilldown_target": "/operations",
                }
            ],
            empty="empty",
        )
        summary = html.split("</summary>", 1)[0]
        self.assertIn(surface_copy("HOME", "new_since_review"), summary)
        self.assertIn("PNL_UNKNOWN_OR_STALE", summary)

    def test_system_impact_p1_gets_scan_border(self) -> None:
        html = _system_section(
            {
                "state": "DEGRADED",
                "identity": {},
                "processes": {},
                "collection": {},
                "storage": {},
                "durability": {},
                "alerting": {},
                "coverage": {},
                "attention": [
                    {
                        "attention_code": "OFFHOST_BACKUP_FAILED",
                        "WHY_NOW": "Off-host backup failed.",
                        "IMPACT": "P1",
                        "EVIDENCE": "offhost failed",
                        "NEXT_SAFE_ACTION": "FOLLOW_DURABILITY_RUNBOOK",
                    }
                ],
                "next_safe_action": "FOLLOW_DURABILITY_RUNBOOK",
            }
        )
        self.assertIn("attention-p1", html)
        self.assertIn("FOLLOW_DURABILITY_RUNBOOK", html.split("</summary>", 1)[0])

    def test_operations_prose_impact_is_not_invented_priority(self) -> None:
        html = _attention(
            [
                {
                    "code": "PAUSE_NEW_ENTRIES",
                    "WHY_NOW": "Known inventory lacks a known mark",
                    "IMPACT": "Exposure/PnL cannot be treated as zero",
                    "EVIDENCE": "pnl_status:UNKNOWN",
                    "NEXT_SAFE_ACTION": "PAUSE_NEW_ENTRIES",
                }
            ],
            empty="empty",
        )
        self.assertNotIn("attention-p0", html)
        self.assertNotIn("attention-p1", html)
        self.assertIn("PAUSE_NEW_ENTRIES", html.split("</summary>", 1)[0])

    def test_unknown_money_is_not_doubled(self) -> None:
        self.assertNotIn("UNKNOWN UNKNOWN", _eco_money_and_status(None, "UNKNOWN"))
        self.assertIn("UNKNOWN", _eco_money_and_status(None, "UNKNOWN"))
        self.assertNotIn("UNKNOWN UNKNOWN", _count_and_status(None, "UNKNOWN"))

    def test_research_table_headers_are_russian_first(self) -> None:
        html = _research_rows(
            [
                {
                    "kind": "HYPOTHESIS",
                    "title": "example",
                    "native_state": "ACTIVE",
                    "truth_plane": "GIT",
                    "evidence_class": "MODEL",
                    "as_of": "UNKNOWN",
                    "locator": {
                        "entity_id": "H-EXAMPLE",
                        "truth_plane": "GIT",
                        "native_kind": "HYPOTHESIS",
                    },
                }
            ]
        )
        self.assertIn(research_copy("col_evidence_class"), html)
        self.assertIn(research_copy("col_as_of"), html)
        self.assertNotIn(">evidence_class</th>", html)
        self.assertNotIn(">as_of</th>", html)

    def test_six_routes_keep_question_and_hide_archaeology_from_note(self) -> None:
        css = visual_os_layout_css()
        self.assertIn("attention-p0", css)
        self.assertIn("color-scheme: dark", css)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                store_before = (root / "ops.sqlite").read_bytes()
                pages = {path: _get(app, path) for path in PATHS}
                for path, body in pages.items():
                    note = re.search(r'class="page-note">([^<]+)', body)
                    self.assertIsNotNone(note, path)
                    self.assertNotIn("git_archaeology_required", note.group(1), path)
                    self.assertIn("git_archaeology_required=", body, path)
                    self.assertIn("page-machine", body, path)
                    self.assertIn("page-question", body, path)
                    self.assertIn('name="viewport"', body, path)
                    self.assertNotIn('name="command" value="START"', body)
                hypotheses = _get(app, "/research?kind=hypotheses")
                experiments = _get(app, "/research?kind=experiments")
                for body in (hypotheses, experiments):
                    note = re.search(r'class="page-note">([^<]+)', body)
                    self.assertIsNotNone(note)
                    self.assertIn("page-question", body)
                    self.assertNotIn("git_archaeology_required", note.group(1))
                self.assertIn("гипотезы", hypotheses)
                self.assertIn("эксперименты", experiments)
                self.assertEqual(store_before, (root / "ops.sqlite").read_bytes())
                home = pages["/"]
                self.assertIn("WHY_NOW", home)
                self.assertIn("Требует внимания", home)
                self.assertNotIn(">source</th>", home)
                self.assertNotIn(">CURRENT_STATE</th>", home)
                research = pages["/research"]
                self.assertEqual(research.count(">Требует внимания<"), 2)
                self.assertNotIn(">evidence_class</th>", research)
                self.assertNotIn(">as_of</th>", research)
                self.assertNotIn(">ACTIVE NOW</h3>", research)
                market = pages["/market"]
                self.assertIn("LOW не выдуман", market)
                self.assertNotIn("<h3>Деталь 30м</h3>", market)
                self.assertNotIn("<h2>Матрица возраста</h2>", market)
                self.assertIn("NO_MARKET_WIDE_CLAIM", market)
                operations = pages["/operations"]
                self.assertIn("Позиции UNKNOWN", operations)
                self.assertIn("PnL неизвестен", operations)
                self.assertIn("Режим", operations)
                self.assertIn("Открыть источник", home)
                self.assertIn("RESEARCH", home)
                self.assertIn('name="command" value="MARK_REVIEWED"', home)
                for command in OPERATOR_COMMANDS:
                    self.assertIn(f'name="command" value="{command}"', command_button(command))
                economics = pages["/economics"]
                self.assertNotIn("UNKNOWN UNKNOWN", economics)
                self.assertIn("Сведённая экономика", economics)
                self.assertIn("NO LIVE PNL", economics)
                self.assertIn("reconciled_net_pnl_usd</th><td>UNKNOWN</td>", economics)
            finally:
                paper = getattr(app, "_paper_plane_store", None)
                if paper is not None:
                    paper.close()
                store.close()


if __name__ == "__main__":
    unittest.main()
