"""OWNER_WORKBENCH_VERTICAL_UX_FOUNDATION_V1: Russian-first shell, unchanged machine truth."""

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
from solana_alpha_lab.factory.owner_language import command_label, research_copy, surface_copy
from solana_alpha_lab.factory.owner_surface import (
    command_button,
    compact_title,
    esc,
    page_head,
)
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config
from solana_alpha_lab.factory.visual_os import visual_os_layout_css
from solana_alpha_lab.factory.workbench import (
    OPERATOR_COMMANDS,
    _home_section,
    _operations_section,
    _system_section,
    serve,
)

OWNER_LANGUAGE = ROOT / "src/solana_alpha_lab/factory/owner_language.py"
HUMAN = ROOT / "docs/contracts/smial_visual_operating_system_v1.md"
WORKBENCH = ROOT / "src/solana_alpha_lab/factory/workbench.py"
OWNER_SURFACE = ROOT / "src/solana_alpha_lab/factory/owner_surface.py"
VISUAL_OS = ROOT / "configs/smial_visual_operating_system_v1.yaml"

HEADINGS = {
    "/": ("Главная", "Что сейчас действительно требует моего внимания?"),
    "/research": ("Исследования", "Что мы проверяем / что знаем / что мне решать?"),
    "/operations": (
        "Операции",
        "Что исполняется, где остановился путь и что безопасно сделать?",
    ),
    "/economics": (
        "Экономика",
        "Есть ли уже экономический результат и насколько ему можно доверять?",
    ),
    "/system": ("Система", "Система сейчас в каком состоянии и что не доказано?"),
}

GENERIC_H1 = "Factory v1 — локальный срез владельца"


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


class OwnerWorkbenchVerticalUxFoundationTests(unittest.TestCase):
    def test_surface_helpers_escape_and_preserve_commands(self) -> None:
        self.assertIn("&lt;script&gt;", esc("<script>"))
        self.assertIn('value="PAUSE_NEW_ENTRIES"', command_button("PAUSE_NEW_ENTRIES"))
        self.assertIn(command_label("PAUSE_NEW_ENTRIES"), command_button("PAUSE_NEW_ENTRIES"))
        short, truncated = compact_title("short")
        self.assertEqual(short, "short")
        self.assertFalse(truncated)
        long_title, was_cut = compact_title("x" * 120, limit=88)
        self.assertTrue(was_cut)
        self.assertLessEqual(len(long_title), 88)
        head = page_head("HOME", note="note")
        self.assertIn("<h1>Главная</h1>", head)
        self.assertIn(surface_copy("HOME", "question"), head)
        css = visual_os_layout_css()
        self.assertIn(".page-head", css)
        self.assertIn("details.technical", css)
        self.assertIn("copy-btn { opacity: 1;", css)
        self.assertIn("Owner-surface invariants", HUMAN.read_text(encoding="utf-8"))

    def test_five_routes_are_russian_first_with_page_questions(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                pages = {path: _get(app, path) for path in HEADINGS}
                for path, (h1, question) in HEADINGS.items():
                    body = pages[path]
                    self.assertIn(f"<h1>{h1}</h1>", body, path)
                    self.assertIn(question, body, path)
                    self.assertIn("data-visual-os-consumed=\"true\"", body, path)
                    self.assertIn("--surface-void", body, path)
                    self.assertIn("page-question", body, path)
                    self.assertNotIn(f"<h1>{GENERIC_H1}</h1>", body, path)
                    self.assertNotIn("i18next", body)
                    self.assertNotIn("gettext", body)
                for path in HEADINGS:
                    self.assertIn("details class=\"technical\"", pages[path], path)
                home = pages["/"]
                self.assertIn("WHY_NOW", home)
                self.assertIn("NEXT_SAFE_ACTION", home)
                self.assertIn("COMMISSIONING_PACKET_SCIENTIFIC_HINT_NOT_ALPHA", home)
                self.assertIn("git_archaeology_required=", home)
                self.assertIn("Factory v1", home)
                self.assertIn("Почему сейчас", home)
                research = pages["/research"]
                self.assertIn("research-overview", research)
                self.assertIn("Активно сейчас", research)
                self.assertIn(research_copy("source"), research)
                self.assertIn(research_copy("universe"), research)
                self.assertEqual(research.count("<h1>Исследования</h1>"), 1)
                self.assertNotIn("<h2>Исследования</h2>", research)
                operations = pages["/operations"]
                self.assertIn("Допустимые действия", operations)
                self.assertIn("NOT_PRESENT", operations)
                self.assertIn("SOURCE_NOT_PRESENT", operations)
                self.assertNotIn(">Bots<", operations)
                self.assertLess(
                    operations.find("<h2>Требует внимания</h2>"),
                    operations.find("<h2>Позиции</h2>"),
                )
                self.assertLess(
                    operations.find("<h2>Позиции</h2>"),
                    operations.find("<h2>Допустимые действия</h2>"),
                )
                for command in OPERATOR_COMMANDS:
                    self.assertNotRegex(
                        operations,
                        rf'name="command" value="{command}"',
                    )
                economics = pages["/economics"]
                self.assertIn("NO_REALIZED_LIVE_PNL", economics)
                self.assertIn("UNKNOWN", economics)
                self.assertIn("неизвестно", economics)
                self.assertIn("не показываются как $0", economics)
                self.assertIn(
                    "reconciled_net_pnl_usd</th><td>UNKNOWN</td>",
                    economics,
                )
                self.assertNotIn(
                    "reconciled_net_pnl_usd</th><td>$0</td>",
                    economics,
                )
                system = pages["/system"]
                self.assertIn("Runtime", system)
                self.assertIn("DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN", system)
                self.assertIn("process_alive", system)
                self.assertIn("не означает, что система исправна", system)
                self.assertNotIn("<h1>Система исправна</h1>", system)
                self.assertIn("Required features", home)
                home_note = re.search(r"git_archaeology_required=(true|false|UNKNOWN)", home)
                research_note = re.search(
                    r"git_archaeology_required=(true|false|UNKNOWN)", research
                )
                self.assertIsNotNone(home_note)
                self.assertIsNotNone(research_note)
                self.assertEqual(research_note.group(1), "UNKNOWN")
            finally:
                paper = getattr(app, "_paper_plane_store", None)
                if paper is not None:
                    paper.close()
                store.close()

    def test_modes_and_ids_remain_canonical(self) -> None:
        text = (
            WORKBENCH.read_text(encoding="utf-8")
            + OWNER_SURFACE.read_text(encoding="utf-8")
            + OWNER_LANGUAGE.read_text(encoding="utf-8")
        )
        for token in (
            "PAUSE_NEW_ENTRIES",
            "RESUME_NEW_ENTRIES",
            "REQUEST_CLOSE_POSITION",
            "REQUEST_CLOSE_ALL",
            "STOP_BOT",
            "PAPER",
            "SHADOW",
            "LIVE",
            "UNKNOWN",
            "MISSING",
            "CONFLICT",
            "expected_open_position_set_sha256",
        ):
            self.assertIn(token, text)
        self.assertIn("command_button", WORKBENCH.read_text(encoding="utf-8"))
        self.assertIn("visual_os_layout_css", WORKBENCH.read_text(encoding="utf-8"))
        self.assertIn('value="{esc(value)}"', OWNER_SURFACE.read_text(encoding="utf-8"))
        self.assertFalse(re.search(r"react|tailwind|i18next", text, re.I))

    def test_visual_os_consumed_without_second_system(self) -> None:
        human = HUMAN.read_text(encoding="utf-8")
        self.assertIn("They do not create a second", human)
        self.assertIn("visual system", human)
        self.assertIn("SEM-VISUAL-OPERATING-SYSTEM", human)
        self.assertNotIn("SEM-OWNER-WORKBENCH-VERTICAL-UX", human)

    def test_exact_tokens_are_not_rewritten_as_missing_or_degraded(self) -> None:
        proved = {
            "process_alive": True,
            "backup_status": "EXPLICIT_UNKNOWN",
            "local_rollback_snapshot": "PRESENT",
            "verdict": "RUNTIME_PROVED_BACKUP_UNKNOWN",
            "next_safe_action": "INSPECT_SYSTEM",
            "deploy_version": "test-deploy",
        }
        system_html = _system_section(proved)
        home_html = _home_section(
            {
                "runtime": proved,
                "cockpit": {},
                "hypothesis": "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1",
                "status": "COMPLETE",
                "blocker": None,
                "next_safe_action": "DO_NOT_PROMOTE",
                "required_features": [],
            },
            copy_blocks=[],
        )
        self.assertIn("есть", system_html)
        self.assertIn("PRESENT", system_html)
        self.assertNotIn("отсутствует", system_html)
        proved_gloss = "процесс доказан, бэкап неизвестен"
        self.assertIn(proved_gloss, system_html)
        self.assertIn(proved_gloss, home_html)
        self.assertNotIn("деградирован", system_html)
        self.assertNotIn("деградирован", home_html)
        self.assertEqual(system_html.count(proved_gloss), home_html.count(proved_gloss))
        self.assertIn("HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1", home_html)
        self.assertIn("DO_NOT_PROMOTE", home_html)
        self.assertIn("Required features", home_html)
        self.assertIn("Не продвигать в стратегию", home_html)
        missing_ops = _operations_section({"operations": {}})
        missing_ops = _operations_section({"operations": {}})
        self.assertIn("UNKNOWN", missing_ops)
        self.assertNotIn("не приостановлены", missing_ops)
        paused = _operations_section({"operations": {"entries_paused": False}})
        self.assertIn("не приостановлены", paused)
        missing_process = _system_section({"verdict": "UNHEALTHY_NOT_RUNNING"})
        self.assertIn("неизвестно", missing_process)
        self.assertIn("UNKNOWN", missing_process)


if __name__ == "__main__":
    unittest.main()
