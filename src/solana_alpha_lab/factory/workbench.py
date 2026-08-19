"""Thin local owner Workbench. Projection plus bounded commands. Owns nothing."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication

COMMANDS = ("FREEZE", "START", "STOP", "PARK", "RECORD_DECISION")


def _page(model: dict[str, Any], error: str = "") -> bytes:
    rows = "".join(
        f"<tr><th>{html.escape(key)}</th><td>{html.escape(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)}</td></tr>"
        for key, value in model.items()
    )
    buttons = "".join(
        f'<button type="submit" name="command" value="{command}">{command}</button>'
        for command in COMMANDS
    )
    notice = f"<p class=\"error\">{html.escape(error)}</p>" if error else ""
    body = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Factory v1 Workbench</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; max-width: 960px; }}
th {{ text-align: left; padding-right: 1rem; vertical-align: top; }}
.error {{ color: #a40000; }}
button {{ margin-right: 0.5rem; }}
</style></head><body>
<h1>Factory v1 — локальный срез владельца</h1>
<p>Проекция. UI не является владельцем научной истины и не вызывает provider.</p>
{notice}
<table>{rows}</table>
<form method="post">
{buttons}
</form>
</body></html>
"""
    return body.encode("utf-8")


def make_handler(app: FactoryApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/", "/index.html"}:
                self.send_error(404)
                return
            body = _page(app.read_model())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
            body = _page(app.read_model(), error=error)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(app: FactoryApplication, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ApplicationError("WORKBENCH_BIND_NOT_LOCALHOST")
    return ThreadingHTTPServer((host, port), make_handler(app))
