"""Thin local owner Workbench. Projection plus bounded commands. Owns nothing."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec

COMMANDS = ("FREEZE", "START", "STOP", "PARK", "RECORD_DECISION")
OPERATOR_COMMANDS = (
    "PAUSE_NEW_ENTRIES",
    "RESUME_NEW_ENTRIES",
    "REQUEST_CLOSE_POSITION",
    "REQUEST_CLOSE_ALL",
    "STOP_BOT",
)
NAV = (
    ("/", "HOME"),
    ("/research", "RESEARCH"),
    ("/operations", "OPERATIONS"),
    ("/economics", "ECONOMICS"),
    ("/system", "SYSTEM"),
)
HIDDEN_NAV = ("MARKET",)


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
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _pnl_cell(row: dict[str, Any]) -> str:
    if row.get("pnl_status") == "UNKNOWN" or row.get("net_pnl_usd") is None:
        return "UNKNOWN"
    return str(row.get("net_pnl_usd"))


def _attention(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Нет attention items.</p>"
    cards = []
    for item in items:
        cards.append(
            "<article class=\"attention\">"
            f"<h3>{html.escape(str(item.get('id') or item.get('code') or ''))}</h3>"
            "<table>"
            f"<tr><th>WHY_NOW</th><td>{html.escape(_cell(item.get('WHY_NOW')))}</td></tr>"
            f"<tr><th>IMPACT</th><td>{html.escape(_cell(item.get('IMPACT')))}</td></tr>"
            f"<tr><th>EVIDENCE</th><td>{html.escape(_cell(item.get('EVIDENCE')))}</td></tr>"
            f"<tr><th>NEXT_SAFE_ACTION</th><td>{html.escape(_cell(item.get('NEXT_SAFE_ACTION')))}</td></tr>"
            "</table></article>"
        )
    return "".join(cards)


def _recent_changes(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Нет недавних execution/command events.</p>"
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('created_at') or ''))}</td>"
            f"<td>{html.escape(str(item.get('event_type') or ''))}</td>"
            f"<td>{html.escape(str(item.get('position_id') or ''))}</td>"
            f"<td>{html.escape(_cell(item.get('payload')))}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>as_of</th><th>event</th><th>position</th><th>payload</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _position_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>Нет позиций.</p>"
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('position_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('strategy_id') or ''))}/{html.escape(str(row.get('strategy_version') or ''))}</td>"
            f"<td>{html.escape(str(row.get('activation_epoch_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('mint') or ''))}</td>"
            f"<td>{html.escape(str(row.get('state') or ''))}</td>"
            f"<td>{html.escape(str(row.get('opened_at') or ''))}</td>"
            f"<td>{html.escape(_cell(row.get('entered_notional_usd')))}</td>"
            f"<td>{html.escape(_pnl_cell(row))}</td>"
            f"<td>{html.escape(_cell(row.get('pnl_evidence_class')))}</td>"
            "</tr>"
        )
    return (
        "<table><tr>"
        "<th>position_id</th><th>strategy</th><th>activation_epoch</th><th>mint</th>"
        "<th>state</th><th>opened_at</th><th>entry_notional</th><th>pnl</th>"
        "<th>pnl_evidence_class</th></tr>"
        + "".join(body)
        + "</table>"
    )


def _operations_section(model: dict[str, Any]) -> str:
    ops = model.get("operations") if isinstance(model.get("operations"), dict) else {}
    bots = ops.get("bots") if isinstance(ops.get("bots"), list) else []
    bot_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(bot.get('bot_instance_id') or ''))}</td>"
        f"<td>{html.escape(str(bot.get('strategy_id') or ''))}</td>"
        f"<td>{html.escape(str(bot.get('mode') or ''))}</td>"
        f"<td>{html.escape(str(bot.get('status') or ''))}</td>"
        f"<td>{html.escape(str(bool(int(bot.get('entries_paused') or 0))))}</td>"
        f"<td>{html.escape(str(bot.get('activation_epoch_id') or ''))}</td>"
        "</tr>"
        for bot in bots
        if isinstance(bot, dict)
    ) or "<tr><td colspan=\"6\">NONE</td></tr>"
    snapshot = str(ops.get("open_position_set_sha256") or "")
    bot_id = str(ops.get("bot") or (bots[0].get("bot_instance_id") if bots else "") or "")
    return (
        "<h2>Bots</h2><table><tr><th>bot</th><th>strategy</th><th>mode</th>"
        "<th>status</th><th>entries_paused</th><th>activation_epoch</th></tr>"
        + bot_rows
        + "</table>"
        + "<h2>Counts</h2><table>"
        + _rows(
            {
                "open_positions": ops.get("open_positions"),
                "partial_positions": ops.get("partial_positions"),
                "unknown_positions": ops.get("unknown_positions"),
                "exit_required": ops.get("exit_required"),
                "unresolved_positions": ops.get("unresolved_positions"),
                "entries_paused": ops.get("entries_paused"),
                "open_position_set_sha256": snapshot,
            }
        )
        + "</table>"
        + "<h2>Positions</h2>"
        + _position_table(list(ops.get("position_rows") or []))
        + "<h2>Attention</h2>"
        + _attention(list(ops.get("attention") or []))
        + "<h2>Recent changes</h2>"
        + _recent_changes(list(model.get("recent_changes") or []))
        + "<h2>Operator commands</h2>"
        + "<form method=\"post\" action=\"/operations\" class=\"ops-form\">"
        + f"<input type=\"hidden\" name=\"bot_instance_id\" value=\"{html.escape(bot_id)}\">"
        + f"<input type=\"hidden\" name=\"expected_open_position_set_sha256\" value=\"{html.escape(snapshot)}\">"
        + "<p><label>position_id <input name=\"position_id\"></label></p>"
        + "<p><label>idempotency_key <input name=\"idempotency_key\" "
        + f"value=\"{html.escape('WB-' + uuid4().hex[:12].upper())}\"></label></p>"
        + "<p class=\"safe-actions\">"
        + "<button type=\"submit\" name=\"command\" value=\"PAUSE_NEW_ENTRIES\">PAUSE_NEW_ENTRIES</button>"
        + "<button type=\"submit\" name=\"command\" value=\"RESUME_NEW_ENTRIES\">RESUME_NEW_ENTRIES</button>"
        + "<button type=\"submit\" name=\"command\" value=\"REQUEST_CLOSE_POSITION\">REQUEST_CLOSE_POSITION</button>"
        + "</p>"
        + "<fieldset class=\"danger\">"
        + "<legend>Bulk / stop (local confirmation)</legend>"
        + "<p><label><input type=\"checkbox\" name=\"confirm_close_all\" value=\"1\"> "
        + "Confirm REQUEST_CLOSE_ALL against the rendered open-position snapshot</label></p>"
        + "<button type=\"submit\" name=\"command\" value=\"REQUEST_CLOSE_ALL\">REQUEST_CLOSE_ALL</button>"
        + "<button type=\"submit\" name=\"command\" value=\"STOP_BOT\">STOP_BOT</button>"
        + "</fieldset></form>"
    )


def _economics_section(model: dict[str, Any]) -> str:
    eco = model.get("economics") if isinstance(model.get("economics"), dict) else {}
    non_claims = eco.get("non_claims") if isinstance(eco.get("non_claims"), list) else []
    return (
        "<h2>PAPER/SHADOW model economics</h2>"
        + "<p class=\"non-claims\">"
        + " · ".join(html.escape(str(item)) for item in non_claims)
        + "</p><table>"
        + _rows(
            {
                "reconciled_net_pnl_usd": eco.get("reconciled_net_pnl_usd"),
                "reconciled_net_pnl_status": eco.get("reconciled_net_pnl_status"),
                "pnl_known_count": eco.get("pnl_known_count"),
                "pnl_unknown_count": eco.get("pnl_unknown_count"),
                "known_open_exposure_usd": eco.get("known_open_exposure_usd"),
                "known_open_exposure_status": eco.get("known_open_exposure_status"),
                "current_loss_streak_status": eco.get("current_loss_streak_status"),
                "current_loss_streak_count": eco.get("current_loss_streak_count"),
                "max_drawdown_usd": eco.get("max_drawdown_usd"),
                "max_drawdown_status": eco.get("max_drawdown_status"),
                "pnl_by_evidence_class": eco.get("pnl_by_evidence_class"),
            }
        )
        + "</table>"
        + "<p>Absent live metrics are not shown as $0.</p>"
    )


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
            + "<h2>Recent changes</h2>"
            + _recent_changes(list(model.get("recent_changes") or [])[:6])
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
                    "backup_status": runtime.get("backup_status")
                    or cockpit.get("backup_status")
                    or "EXPLICIT_UNKNOWN",
                    "deploy_version": runtime.get("deploy_version") or "",
                }
            )
            + "</table>"
        ),
        "RESEARCH": "<h2>Research packet</h2><table>" + _rows(packet) + "</table>",
        "OPERATIONS": _operations_section(model),
        "ECONOMICS": _economics_section(model),
        "SYSTEM": "<h2>Runtime</h2><table>" + _rows(runtime) + "</table>",
    }
    body = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Factory v1 Workbench</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; max-width: 1100px; }}
th {{ text-align: left; padding-right: 1rem; vertical-align: top; }}
.error {{ color: #a40000; }}
nav a[aria-current="page"] {{ font-weight: bold; }}
form button {{ margin-right: 0.5rem; margin-bottom: 0.5rem; }}
.copy-hint {{ color: #444; }}
.copy-block {{ position: relative; margin: 1rem 0; padding: 0.75rem 1rem; border: 1px solid #ccc; background: #f7f7f7; }}
.copy-head {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
.copy-head h2 {{ font-size: 1rem; margin: 0; }}
.copy-btn {{ opacity: 0; pointer-events: none; }}
.copy-block:hover .copy-btn, .copy-block:focus-within .copy-btn {{ opacity: 1; pointer-events: auto; }}
.copy-text {{ white-space: pre-wrap; word-break: break-word; margin: 0.75rem 0 0; }}
.attention {{ border: 1px solid #ccc; padding: 0.75rem 1rem; margin: 0.75rem 0; }}
.non-claims {{ font-weight: bold; }}
.danger {{ border: 2px solid #a40000; padding: 0.75rem; margin-top: 1rem; }}
.safe-actions {{ margin: 0.75rem 0; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
td, th {{ border-bottom: 1px solid #ddd; padding: 0.35rem 0.5rem; }}
</style></head><body>
<h1>Factory v1 — локальный срез владельца</h1>
<p>Проекция. UI не владеет научной истиной и не открывает SQLite. START без точной owner phrase не читает ключ и не вызывает Jupiter. git_archaeology_required={html.escape(archaeology)}. Operational-ready milestone is not claimed.</p>
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
            surfaces = {
                "/": "HOME",
                "/index.html": "HOME",
                "/research": "RESEARCH",
                "/operations": "OPERATIONS",
                "/economics": "ECONOMICS",
                "/system": "SYSTEM",
            }
            surface = surfaces.get(path)
            if surface is None:
                self.send_error(404)
                return
            self._render(surface)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8")
            fields = parse_qs(raw)
            command = (fields.get("command") or [""])[0]
            error = ""
            try:
                if path in {"/", "/index.html"}:
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
                    self._render("HOME", error=error)
                    return
                if path == "/operations":
                    if command not in OPERATOR_COMMANDS:
                        raise ApplicationError("COMMAND_NOT_ALLOWLISTED")
                    if command == "REQUEST_CLOSE_ALL" and (
                        fields.get("confirm_close_all") or [""]
                    )[0] != "1":
                        raise ApplicationError("CLOSE_ALL_CONFIRMATION_REQUIRED")
                    payload: dict[str, Any] = {
                        "command_type": command,
                        "idempotency_key": (fields.get("idempotency_key") or [""])[0]
                        or f"WB-{uuid4().hex[:12].upper()}",
                    }
                    bot_id = (fields.get("bot_instance_id") or [""])[0]
                    if bot_id:
                        payload["bot_instance_id"] = bot_id
                    if command == "REQUEST_CLOSE_POSITION":
                        payload["position_id"] = (fields.get("position_id") or [""])[0]
                    if command == "REQUEST_CLOSE_ALL":
                        payload["expected_open_position_set_sha256"] = (
                            fields.get("expected_open_position_set_sha256") or [""]
                        )[0]
                    result = app.apply_paper_operator_command(payload)
                    if result.get("status") == "STALE_OPERATOR_SNAPSHOT":
                        error = "STALE_OPERATOR_SNAPSHOT"
                    self._render("OPERATIONS", error=error)
                    return
                raise ApplicationError("COMMAND_PATH_INVALID")
            except ApplicationError as exc:
                error = str(exc)
                surface = "OPERATIONS" if path == "/operations" else "HOME"
                self._render(surface, error=error)

    return Handler


def serve(app: FactoryApplication, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ApplicationError("WORKBENCH_BIND_NOT_LOCALHOST")
    return ThreadingHTTPServer((host, port), make_handler(app))
