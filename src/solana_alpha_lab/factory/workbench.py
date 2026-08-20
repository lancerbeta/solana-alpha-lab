"""Thin local owner Workbench. Projection plus bounded commands. Owns nothing."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec

COMMANDS = ("FREEZE", "START", "STOP", "PARK", "RECORD_DECISION")
NAV = (("/", "HOME"), ("/research", "RESEARCH"), ("/system", "SYSTEM"))
HIDDEN_NAV = ("MARKET", "OPERATIONS", "ECONOMICS")


def owner_copy_blocks(app: FactoryApplication) -> list[dict[str, str]]:
    spec = load_experiment_spec(app.root, app.spec_relative)
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), dict) else {}
    phrase = str(parameters.get("required_owner_phrase") or "")
    if not phrase:
        return []
    return [
        {
            "id": "exact-owner-phrase",
            "title": "Точная owner phrase — вставьте целиком в чат",
            "text": phrase,
        },
        {
            "id": "live-capture-cli",
            "title": "CLI после той же фразы в чате (не из Workbench START)",
            "text": (
                "uv run --locked --managed-python python -B "
                "scripts/run_factory_experiment.py --authority-phrase "
                + json.dumps(phrase, ensure_ascii=False)
            ),
        },
    ]


def _copy_sections(blocks: list[dict[str, str]]) -> str:
    if not blocks:
        return ""
    sections = []
    for block in blocks:
        sections.append(
            "<section class=\"copy-block\">"
            f"<div class=\"copy-head\"><h2>{html.escape(block['title'])}</h2>"
            f"<button type=\"button\" class=\"copy-btn\" data-copy-target=\"{html.escape(block['id'])}\">"
            "Копировать</button></div>"
            f"<pre id=\"{html.escape(block['id'])}\" class=\"copy-text\">{html.escape(block['text'])}</pre>"
            "</section>"
        )
    return (
        "<p class=\"copy-hint\">Наведите на блок — справа появится «Копировать». "
        "START на этой странице фразу не подставляет и Jupiter не вызывает.</p>"
        + "".join(sections)
    )


def _nav(active: str) -> str:
    links = []
    for href, name in NAV:
        current = " aria-current=\"page\"" if name == active else ""
        links.append(f'<a href="{href}"{current}>{html.escape(name)}</a>')
    return "<nav>" + " · ".join(links) + "</nav>"


def _rows(mapping: dict[str, Any]) -> str:
    return "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(_cell(value))}</td></tr>"
        for key, value in mapping.items()
    )


def _feature_rows(features: list[dict[str, Any]]) -> str:
    if not features:
        return "<tr><td>NONE</td></tr>"
    return "".join(
        "<tr><th>"
        + html.escape(str(item.get("feature_id") or ""))
        + "</th><td>"
        + html.escape(str(item.get("display") or item.get("availability_class") or ""))
        + "</td></tr>"
        for item in features
        if isinstance(item, dict)
    )


def _cell(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _attention(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Нет attention items.</p>"
    cards = []
    for item in items:
        cards.append(
            "<article class=\"attention\">"
            f"<h3>{html.escape(str(item.get('id') or ''))}</h3>"
            "<table>"
            f"<tr><th>WHY_NOW</th><td>{html.escape(_cell(item.get('WHY_NOW')))}</td></tr>"
            f"<tr><th>IMPACT</th><td>{html.escape(_cell(item.get('IMPACT')))}</td></tr>"
            f"<tr><th>EVIDENCE</th><td>{html.escape(_cell(item.get('EVIDENCE')))}</td></tr>"
            f"<tr><th>NEXT_SAFE_ACTION</th><td>{html.escape(_cell(item.get('NEXT_SAFE_ACTION')))}</td></tr>"
            "</table></article>"
        )
    return "".join(cards)


def _page(
    model: dict[str, Any],
    *,
    surface: str,
    copy_blocks: list[dict[str, str]] | None = None,
    error: str = "",
) -> bytes:
    cockpit = model.get("cockpit") if isinstance(model.get("cockpit"), dict) else {}
    packet = cockpit.get("packet") if isinstance(cockpit.get("packet"), dict) else {}
    runtime = model.get("runtime") if isinstance(model.get("runtime"), dict) else {}
    notice = f"<p class=\"error\">{html.escape(error)}</p>" if error else ""
    buttons = "".join(
        f'<button type="submit" name="command" value="{command}">{command}</button>'
        for command in COMMANDS
    )
    archaeology = "true" if cockpit.get("git_archaeology_required") else "false"
    sections = {
        "HOME": (
            "<h2>Attention / Today</h2>"
            + _attention(list(cockpit.get("attention") or []))
            + "<h2>Owner packet</h2><table>"
            + _rows(packet)
            + "</table><h2>Cycle state</h2><table>"
            + _rows(
                {
                    "status": model.get("status") or "",
                    "blocker": model.get("blocker") or "",
                    "hypothesis": model.get("hypothesis") or "",
                }
            )
            + "</table><h2>Required features</h2><table>"
            + _feature_rows(list(model.get("required_features") or []))
            + "</table><h2>System health</h2><table>"
            + _rows(
                {
                    "verdict": runtime.get("verdict") or "UNAVAILABLE",
                    "backup_status": runtime.get("backup_status") or cockpit.get("backup_status") or "EXPLICIT_UNKNOWN",
                    "deploy_version": runtime.get("deploy_version") or "",
                }
            )
            + "</table>"
        ),
        "RESEARCH": "<h2>Research packet</h2><table>" + _rows(packet) + "</table>",
        "SYSTEM": "<h2>Runtime</h2><table>" + _rows(runtime) + "</table>",
    }
    body = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Factory v1 Workbench</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; max-width: 960px; }}
th {{ text-align: left; padding-right: 1rem; vertical-align: top; }}
.error {{ color: #a40000; }}
nav a[aria-current="page"] {{ font-weight: bold; }}
form button {{ margin-right: 0.5rem; }}
.copy-hint {{ color: #444; }}
.copy-block {{ position: relative; margin: 1rem 0; padding: 0.75rem 1rem; border: 1px solid #ccc; background: #f7f7f7; }}
.copy-head {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
.copy-head h2 {{ font-size: 1rem; margin: 0; }}
.copy-btn {{ opacity: 0; pointer-events: none; }}
.copy-block:hover .copy-btn, .copy-block:focus-within .copy-btn {{ opacity: 1; pointer-events: auto; }}
.copy-text {{ white-space: pre-wrap; word-break: break-word; margin: 0.75rem 0 0; }}
.attention {{ border: 1px solid #ccc; padding: 0.75rem 1rem; margin: 0.75rem 0; }}
</style></head><body>
<h1>Factory v1 — локальный срез владельца</h1>
<p>Проекция. UI не владеет научной истиной. START без точной owner phrase не читает ключ и не вызывает Jupiter. git_archaeology_required={html.escape(archaeology)}. Operational-ready milestone is not claimed.</p>
{_nav(surface)}
{notice}
{_copy_sections(copy_blocks or []) if surface == "HOME" else ""}
{sections.get(surface) or ""}
{("<form method=\"post\" action=\"/\">" + buttons + "</form>") if surface == "HOME" else ""}
<script>
document.querySelectorAll(".copy-btn").forEach(function (button) {{
  button.addEventListener("click", function () {{
    var target = document.getElementById(button.getAttribute("data-copy-target"));
    if (!target) {{ return; }}
    var text = target.textContent || "";
    var done = function () {{
      button.textContent = "Скопировано";
      window.setTimeout(function () {{ button.textContent = "Копировать"; }}, 1500);
    }};
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text).then(done);
      return;
    }}
    var range = document.createRange();
    range.selectNodeContents(target);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand("copy");
    done();
  }});
}});
</script>
</body></html>
"""
    if any(f">{name}<" in body for name in HIDDEN_NAV):
        raise ApplicationError("EMPTY_ENTERPRISE_SCREENS")
    return body.encode("utf-8")


def make_handler(app: FactoryApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _render(self, surface: str, error: str = "") -> None:
            body = _page(
                app.read_model(),
                surface=surface,
                copy_blocks=owner_copy_blocks(app) if surface == "HOME" else [],
                error=error,
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            surfaces = {"/": "HOME", "/index.html": "HOME", "/research": "RESEARCH", "/system": "SYSTEM"}
            surface = surfaces.get(path)
            if surface is None:
                self.send_error(404)
                return
            self._render(surface)

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8")
            fields = parse_qs(raw)
            command = (fields.get("command") or [""])[0]
            error = ""
            try:
                if command == "FREEZE":
                    app.freeze_hypothesis()
                elif command == "START":
                    app.start()
                elif command == "STOP":
                    app.stop()
                elif command == "PARK":
                    app.park()
                elif command == "RECORD_DECISION":
                    app.record_decision("OWNER_RECORDED_FROM_WORKBENCH")
                else:
                    raise ApplicationError("COMMAND_NOT_ALLOWLISTED")
            except ApplicationError as exc:
                error = str(exc)
            self._render("HOME", error=error)

    return Handler


def serve(app: FactoryApplication, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ApplicationError("WORKBENCH_BIND_NOT_LOCALHOST")
    return ThreadingHTTPServer((host, port), make_handler(app))
