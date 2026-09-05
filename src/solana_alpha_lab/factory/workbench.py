"""Thin local owner Workbench. Projection plus bounded commands. Owns nothing."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.research_workbench import (
    ResearchWorkbenchError,
    parse_locator,
)
from solana_alpha_lab.factory.visual_os import visual_os_css, visual_os_consumed

COMMANDS = ("FREEZE", "START", "STOP", "PARK", "RECORD_DECISION")
OPERATOR_COMMANDS = (
    "PAUSE_NEW_ENTRIES",
    "RESUME_NEW_ENTRIES",
    "REQUEST_CLOSE_POSITION",
    "REQUEST_CLOSE_ALL",
    "STOP_BOT",
)
BOT_SCOPED_COMMANDS = frozenset(
    {"PAUSE_NEW_ENTRIES", "RESUME_NEW_ENTRIES", "REQUEST_CLOSE_ALL", "STOP_BOT"}
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
    return (
        "<aside class=\"signal-rail\" data-mode=\"STEEL_SIGNAL\">"
        "<p class=\"brand\">SMIAL</p>"
        "<nav>" + "".join(links) + "</nav></aside>"
    )


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
    bot_id = str(ops.get("bot") or "")
    bot_warning = ""
    if len(bots) != 1:
        bot_id = ""
        bot_warning = (
            "<p class=\"error\">Operator commands require exactly one bot instance.</p>"
        )
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
        + bot_warning
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


def _href_detail(locator: Mapping[str, Any]) -> str:
    return (
        "/research?entity_id="
        + html.escape(str(locator.get("entity_id") or ""), quote=True)
        + "&amp;truth_plane="
        + html.escape(str(locator.get("truth_plane") or ""), quote=True)
        + "&amp;native_kind="
        + html.escape(str(locator.get("native_kind") or ""), quote=True)
    )


def _research_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"empty\">NONE</p>"
    body = []
    for row in rows:
        locator = row.get("locator") if isinstance(row.get("locator"), dict) else {}
        has_locator = bool(
            locator.get("entity_id")
            and locator.get("truth_plane")
            and locator.get("native_kind")
        )
        href = _href_detail(locator) if has_locator else ""
        kind_text = html.escape(str(row.get("kind") or ""))
        title_text = html.escape(str(row.get("title") or ""))
        kind_cell = f"<td><a href=\"{href}\">{kind_text}</a></td>" if href else f"<td>{kind_text}</td>"
        title_cell = f"<td><a href=\"{href}\">{title_text}</a></td>" if href else f"<td>{title_text}</td>"
        marker = []
        if row.get("attention"):
            marker.append("ATTENTION")
        if row.get("blocker"):
            marker.append(str(row.get("blocker")))
        if not has_locator and row.get("next_safe_action"):
            marker.append(str(row.get("next_safe_action")))
        body.append(
            "<tr class=\"research-row\">"
            + kind_cell
            + title_cell
            + f"<td>{html.escape(str(row.get('native_state') or 'UNKNOWN'))}</td>"
            f"<td>{html.escape(str(row.get('truth_plane') or ''))}</td>"
            f"<td>{html.escape(str(row.get('evidence_class') or ''))}</td>"
            f"<td class=\"mono\">{html.escape(str(row.get('as_of') or ''))}</td>"
            f"<td>{html.escape(str(row.get('source') or ''))}</td>"
            f"<td>{html.escape(' · '.join(marker) if marker else '')}</td>"
            f"<td class=\"mono\">{html.escape(str(locator.get('entity_id') or ''))}</td>"
            "</tr>"
        )
    return (
        "<table class=\"research-table\"><tr>"
        "<th>kind</th><th>title</th><th>state</th><th>plane</th>"
        "<th>evidence</th><th>as_of</th><th>source</th><th>marker</th><th>id</th>"
        "</tr>" + "".join(body) + "</table>"
    )


def _counter_cell(label: str, value: Any) -> str:
    if value is None:
        return (
            f"<article class=\"counter\"><h3>{html.escape(label)}</h3>"
            "<p class=\"semantic-unknown\">NOT AVAILABLE</p></article>"
        )
    return (
        f"<article class=\"counter\"><h3>{html.escape(label)}</h3>"
        f"<p>{html.escape(str(value))}</p></article>"
    )


def _lineage_list(edges: list[dict[str, Any]], direction: str) -> str:
    if not edges:
        return f"<p class=\"empty\">{html.escape(direction)} NONE</p>"
    items = []
    for edge in edges:
        resolution = str(edge.get("resolution") or "")
        css = "trace-resolved"
        if resolution in {"TARGET_GAP", "SOURCE_GAP"}:
            css = "trace-gap"
        elif resolution == "CONFLICT":
            css = "trace-conflict"
        items.append(
            f"<li class=\"{css}\">"
            f"<span>{html.escape(str(edge.get('relation_type') or ''))}</span> "
            f"<span class=\"mono\">{html.escape(str(edge.get('from_entity_id') or ''))}</span>"
            " → "
            f"<span class=\"mono\">{html.escape(str(edge.get('to_entity_id') or ''))}</span> "
            f"<span>{html.escape(resolution)}</span> "
            f"<span>{html.escape(str(edge.get('derivation_method') or ''))}</span>"
            "</li>"
        )
    return f"<ul class=\"trace {html.escape(direction.casefold())}\">" + "".join(items) + "</ul>"


def _research_overview_html(view: Mapping[str, Any]) -> str:
    sources = "".join(
        "<tr>"
        f"<th>{html.escape(str(item.get('label') or ''))}</th>"
        f"<td>{html.escape(str(item.get('status') or 'UNKNOWN'))}</td>"
        f"<td>{html.escape(str(item.get('truth_plane') or ''))}</td>"
        f"<td>{html.escape(str(item.get('error') or ''))}</td>"
        f"<td>{html.escape(str(item.get('next_safe_action') or 'UNKNOWN'))}</td>"
        "</tr>"
        for item in view.get("sources") or []
        if isinstance(item, dict)
    ) or "<tr><td>UNKNOWN</td></tr>"
    counters = view.get("counters") if isinstance(view.get("counters"), dict) else {}
    degraded = ""
    if view.get("degraded"):
        degraded = (
            "<p class=\"degraded semantic-unknown\">"
            + html.escape(str(view.get("degraded_copy") or "PARTIAL"))
            + "</p>"
        )
    filters = view.get("filters") if isinstance(view.get("filters"), dict) else {}
    q = html.escape(str(filters.get("q") or ""))
    kind = html.escape(str(filters.get("kind") or "all"))
    return (
        "<section class=\"research-overview\">"
        "<h2>RESEARCH</h2>"
        f"<p>projection {html.escape(str(view.get('completeness') or 'PARTIAL'))}</p>"
        + degraded
        + "<table class=\"source-panel\">"
        + "<tr><th>source</th><th>status</th><th>plane</th><th>error</th><th>next</th></tr>"
        + sources
        + "</table>"
        + "<div class=\"counters\">"
        + "".join(_counter_cell(label, counters.get(label)) for label in (
            "ACTIVE NOW", "TRIALS", "DECISIONS", "NEGATIVES", "ATTENTION", "GAPS"
        ))
        + "</div>"
        + "<h3>Needs attention</h3>"
        + _research_rows(list(view.get("needs_attention") or []))
        + "<h3>Current activity</h3>"
        + (
            "<p class=\"empty semantic-unknown\">NOT AVAILABLE</p>"
            if counters.get("ACTIVE NOW") is None
            else _research_rows(list(view.get("current_activity") or []))
        )
        + "<h3>Research universe</h3>"
        + "<p class=\"filters\">"
        + "<a href=\"/research\">all</a> "
        + "<a href=\"/research?kind=hypotheses\">hypotheses</a> "
        + "<a href=\"/research?kind=experiments\">experiments</a> "
        + "<a href=\"/research?kind=trials\">trials</a> "
        + "<a href=\"/research?kind=decisions\">decisions</a> "
        + "<a href=\"/research?kind=negative\">negative</a>"
        + "</p>"
        + "<form method=\"get\" action=\"/research\" class=\"search\">"
        + f"<input name=\"q\" value=\"{q}\" maxlength=\"80\" aria-label=\"search\">"
        + f"<input type=\"hidden\" name=\"kind\" value=\"{kind}\">"
        + "<button type=\"submit\">search</button></form>"
        + _research_rows(list(view.get("universe") or []))
        + "</section>"
    )


def _research_detail_html(view: Mapping[str, Any]) -> str:
    header = view.get("header") if isinstance(view.get("header"), dict) else {}
    fields = view.get("fields") if isinstance(view.get("fields"), dict) else {}
    lineage = view.get("lineage") if isinstance(view.get("lineage"), dict) else {}
    gaps = "".join(
        "<li>"
        + html.escape(str(item.get("gap_code") or "UNKNOWN"))
        + " — "
        + html.escape(str(item.get("reason") or ""))
        + "</li>"
        for item in view.get("gaps") or []
        if isinstance(item, dict)
    ) or "<li class=\"semantic-unknown\">NONE</li>"
    unknown = view.get("unknown") if isinstance(view.get("unknown"), list) else []
    unknown_html = (
        "<ul>" + "".join(f"<li class=\"semantic-unknown\">{html.escape(str(item))}</li>" for item in unknown) + "</ul>"
        if unknown
        else "<p class=\"semantic-unknown\">NONE</p>"
    )
    timeline = "".join(
        "<li>"
        + html.escape(str(item.get("clock") or ""))
        + " "
        + f"<span class=\"mono\">{html.escape(str(item.get('value') or ''))}</span>"
        + "</li>"
        for item in view.get("timeline") or []
        if isinstance(item, dict)
    )
    technical = view.get("technical") if isinstance(view.get("technical"), dict) else {}
    provenance = view.get("provenance") if isinstance(view.get("provenance"), dict) else {}
    field_rows = _rows({str(key): value for key, value in fields.items()})
    return (
        "<article class=\"evidence-editorial\" data-mode=\"EVIDENCE_EDITORIAL\">"
        "<p><a href=\"/research\">← RESEARCH</a></p>"
        "<header class=\"evidence-header\">"
        f"<p>{html.escape(str(header.get('native_kind') or ''))} "
        f"<span class=\"mono\">{html.escape(str(header.get('entity_id') or ''))}</span></p>"
        f"<h2>{html.escape(str(header.get('title') or ''))}</h2>"
        "<table>"
        + _rows(
            {
                "STATE": header.get("state") or "UNKNOWN",
                "TRUTH PLANE": header.get("truth_plane"),
                "EVIDENCE CLASS": header.get("evidence_class"),
                "SOURCE": header.get("source"),
                "AS OF": header.get("as_of"),
                "OBSERVED AT": header.get("observed_at"),
                "FRESHNESS": header.get("freshness"),
                "NEXT SAFE ACTION": header.get("next_safe_action") or "UNKNOWN",
            }
        )
        + "</table></header>"
        + "<h3>DETAIL</h3><table>"
        + (field_rows or "<tr><td class=\"semantic-unknown\">UNKNOWN</td></tr>")
        + "</table>"
        + "<h3>LINEAGE</h3>"
        + "<div class=\"computational-field\" data-mode=\"COMPUTATIONAL_FIELD\">"
        + "<p class=\"trace-label\">TRACE</p>"
        + _lineage_list(list(lineage.get("inbound") or []), "INBOUND")
        + "<p class=\"current\">CURRENT OBJECT</p>"
        + _lineage_list(list(lineage.get("outbound") or []), "OUTBOUND")
        + "</div>"
        + "<h3>GAPS / UNKNOWN</h3><ul>"
        + gaps
        + "</ul>"
        + unknown_html
        + "<h3>SOURCE / PROVENANCE</h3><table>"
        + _rows(provenance)
        + "</table>"
        + "<h3>TIMELINE</h3><ul>"
        + timeline
        + "</ul>"
        + "<details class=\"technical\"><summary>TECHNICAL DETAILS</summary><table>"
        + _rows(technical)
        + "</table></details></article>"
    )


def _research_section(app: FactoryApplication, query: dict[str, list[str]]) -> str:
    def first(name: str) -> str | None:
        values = query.get(name) or []
        return values[0] if values else None

    try:
        locator = parse_locator(
            first("entity_id"),
            first("truth_plane"),
            first("native_kind"),
        )
        if locator is not None:
            return _research_detail_html(app.research_detail(locator))
        limit_raw = first("limit") or "80"
        limit = int(limit_raw)
        return _research_overview_html(
            app.research_overview(
                q=first("q"),
                kind=first("kind"),
                truth_plane=first("truth_plane") if not first("entity_id") else None,
                state=first("state"),
                evidence_class=first("evidence_class"),
                limit=limit,
            )
        )
    except (ResearchWorkbenchError, ApplicationError, ValueError) as exc:
        return f"<p class=\"error\">{html.escape(str(exc))}</p><p><a href=\"/research\">← RESEARCH</a></p>"


def _page(
    model: dict[str, Any],
    *,
    surface: str,
    copy_blocks: list[dict[str, str]] | None = None,
    error: str = "",
    research_html: str | None = None,
    visual_css: str = "",
    visual_consumed: bool = False,
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
        "RESEARCH": research_html or "<h2>RESEARCH</h2><p class=\"semantic-unknown\">UNKNOWN</p>",
        "OPERATIONS": _operations_section(model),
        "ECONOMICS": _economics_section(model),
        "SYSTEM": "<h2>Runtime</h2><table>" + _rows(runtime) + "</table>",
    }
    consumed = "true" if visual_consumed else "false"
    body = f"""<!doctype html>
<html lang="ru" data-appearance="DARK_ONLY" data-identity="STEEL_SIGNAL"><head><meta charset="utf-8"><title>Factory v1 Workbench</title>
<style>
{visual_css}
html,body {{ background: var(--surface-void, #111); color: var(--text-primary, #eee); font-family: sans-serif; margin: 0; }}
.shell {{ display: grid; grid-template-columns: 12rem 1fr; min-height: 100vh; }}
.signal-rail {{ background: var(--surface-base, #161616); border-right: 1px solid var(--border-hairline, #333); padding: 1.5rem 1rem; }}
.signal-rail .brand {{ letter-spacing: 0.12em; margin: 0 0 1.5rem; }}
.signal-rail nav {{ display: flex; flex-direction: column; gap: 0.75rem; }}
.signal-rail a {{ color: var(--text-muted, #999); text-decoration: none; }}
.signal-rail a[aria-current="page"] {{ color: var(--accent-signal, #888); font-weight: bold; }}
main {{ background: var(--surface-base, #161616); padding: 2rem; max-width: 1100px; }}
th {{ text-align: left; padding-right: 1rem; vertical-align: top; }}
.error, .danger {{ color: var(--semantic-danger, #a40000); }}
.semantic-unknown {{ color: var(--semantic-unknown, #777); }}
.semantic-warning {{ color: var(--semantic-warning, #b8860b); }}
.degraded {{ border: 1px solid var(--border-hairline, #333); padding: 0.75rem 1rem; background: var(--surface-panel, #1c1c1c); }}
form button {{ margin-right: 0.5rem; margin-bottom: 0.5rem; }}
.copy-hint {{ color: var(--text-muted, #999); }}
.copy-block {{ position: relative; margin: 1rem 0; padding: 0.75rem 1rem; border: 1px solid var(--border-hairline, #333); background: var(--surface-panel, #1c1c1c); }}
.copy-head {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
.copy-head h2 {{ font-size: 1rem; margin: 0; }}
.copy-btn {{ opacity: 0; pointer-events: none; }}
.copy-block:hover .copy-btn, .copy-block:focus-within .copy-btn {{ opacity: 1; pointer-events: auto; }}
.copy-text {{ white-space: pre-wrap; word-break: break-word; margin: 0.75rem 0 0; }}
.attention {{ border: 1px solid var(--border-hairline, #333); padding: 0.75rem 1rem; margin: 0.75rem 0; }}
.non-claims {{ font-weight: bold; }}
.danger {{ border: 2px solid var(--semantic-danger, #a40000); padding: 0.75rem; margin-top: 1rem; }}
.safe-actions {{ margin: 0.75rem 0; }}
.mono {{ font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: 0.85em; }}
.counters {{ display: grid; grid-template-columns: repeat(6, minmax(6rem, 1fr)); gap: 0.75rem; margin: 1rem 0; }}
.counter {{ background: var(--surface-panel, #1c1c1c); border: 1px solid var(--border-hairline, #333); padding: 0.5rem 0.75rem; }}
.counter h3 {{ font-size: 0.75rem; margin: 0 0 0.35rem; color: var(--text-muted, #999); }}
.research-table a {{ color: var(--text-primary, #eee); }}
.trace-resolved {{ color: var(--text-primary, #eee); }}
.trace-gap {{ color: var(--semantic-warning, #b8860b); }}
.trace-conflict {{ color: var(--semantic-danger, #a40000); font-weight: bold; }}
.evidence-editorial .evidence-header {{ border-bottom: 1px solid var(--border-hairline, #333); margin-bottom: 1rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
td, th {{ border-bottom: 1px solid var(--border-hairline, #333); padding: 0.35rem 0.5rem; }}
</style></head><body class="steel-signal" data-visual-os-consumed="{consumed}">
<div class="shell">
{_nav(surface)}
<main>
<h1>Factory v1 — локальный срез владельца</h1>
<p>Проекция. UI не владеет научной истиной и не открывает SQLite. START без точной owner phrase не читает ключ и не вызывает Jupiter. git_archaeology_required={html.escape(archaeology)}. Operational-ready milestone is not claimed.</p>
{notice}
{_copy_sections(copy_blocks or []) if surface == "HOME" else ""}
{sections.get(surface) or ""}
{("<form method=\"post\" action=\"/\">" + buttons + "</form>") if surface == "HOME" else ""}
</main></div>
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

        def _render(
            self,
            surface: str,
            error: str = "",
            query: dict[str, list[str]] | None = None,
        ) -> None:
            if surface == "RESEARCH":
                model: dict[str, Any] = {"cockpit": {}, "runtime": {}}
                research_html = _research_section(app, query or {})
            else:
                model = app.read_model(surface=surface)
                research_html = None
            body = _page(
                model,
                surface=surface,
                copy_blocks=owner_copy_blocks(app) if surface == "HOME" else [],
                error=error,
                research_html=research_html,
                visual_css=visual_os_css(app.root),
                visual_consumed=visual_os_consumed(app.root),
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
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
            self._render(surface, query=parse_qs(parsed.query))

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
                    if command in BOT_SCOPED_COMMANDS and not bot_id:
                        raise ApplicationError("BOT_INSTANCE_ID_REQUIRED")
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
