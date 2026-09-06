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
from solana_alpha_lab.factory.owner_language import (
    counter_label,
    decision_kind_label,
    field_label,
    nav_label,
    obligation_label,
    owner_error,
    research_copy,
    status_display,
)
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
        links.append(
            f'<a href="{href}"{current}>{html.escape(nav_label(name))}</a>'
        )
    return (
        "<aside class=\"signal-rail\" data-mode=\"STEEL_SIGNAL\">"
        "<p class=\"brand\">SMIAL</p>"
        "<nav>" + "".join(links) + "</nav></aside>"
    )


def _rows(
    mapping: dict[str, Any],
    *,
    translate_keys: bool = False,
    empty_as: str | None = None,
) -> str:
    rows = []
    for key, value in mapping.items():
        displayed = empty_as if value is None and empty_as is not None else _cell(value)
        rows.append(
            f"<tr><th>{html.escape(field_label(str(key)) if translate_keys else str(key))}</th>"
            f"<td>{html.escape(displayed)}</td></tr>"
        )
    return "".join(rows)


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
        return f"<p class=\"empty\">{html.escape(research_copy('none'))}</p>"
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
            marker.append(counter_label("ATTENTION"))
        if row.get("blocker"):
            marker.append(str(row.get("blocker")))
        if not has_locator and row.get("next_safe_action"):
            marker.append(str(row.get("next_safe_action")))
        native_state = str(row.get("native_state") or "UNKNOWN")
        body.append(
            "<tr class=\"research-row\">"
            + kind_cell
            + title_cell
            + f"<td>{html.escape(status_display(native_state))}</td>"
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
        f"<th>{html.escape(research_copy('col_kind'))}</th>"
        f"<th>{html.escape(research_copy('col_title'))}</th>"
        f"<th>{html.escape(research_copy('col_state'))}</th>"
        f"<th>{html.escape(research_copy('col_plane'))}</th>"
        f"<th>{html.escape(research_copy('col_evidence_class'))}</th>"
        f"<th>{html.escape(research_copy('col_as_of'))}</th>"
        f"<th>{html.escape(research_copy('col_source'))}</th>"
        f"<th>{html.escape(research_copy('col_marker'))}</th>"
        f"<th>{html.escape(research_copy('col_id'))}</th>"
        "</tr>" + "".join(body) + "</table>"
    )


def _counter_cell(label: str, value: Any) -> str:
    if value is None:
        return (
            f"<article class=\"counter\"><h3>{html.escape(label)}</h3>"
            f"<p class=\"semantic-unknown\">{html.escape(research_copy('not_available'))}</p></article>"
        )
    return (
        f"<article class=\"counter\"><h3>{html.escape(label)}</h3>"
        f"<p>{html.escape(str(value))}</p></article>"
    )


def _lineage_list(edges: list[dict[str, Any]], direction: str) -> str:
    if not edges:
        return f"<p class=\"empty\">{html.escape(direction)} {html.escape(research_copy('none'))}</p>"
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
        f"<h2>{html.escape(research_copy('title'))}</h2>"
        f"<p>{html.escape(research_copy('projection'))} "
        f"{html.escape(str(view.get('completeness') or 'PARTIAL'))}</p>"
        + degraded
        + "<table class=\"source-panel\">"
        + "<tr><th>"
        + html.escape(research_copy("source"))
        + "</th><th>"
        + html.escape(research_copy("status"))
        + "</th><th>"
        + html.escape(research_copy("plane"))
        + "</th><th>"
        + html.escape(research_copy("error"))
        + "</th><th>"
        + html.escape(research_copy("next"))
        + "</th></tr>"
        + sources
        + "</table>"
        + "<div class=\"counters\">"
        + "".join(
            _counter_cell(counter_label(label), counters.get(label))
            for label in (
                "ACTIVE NOW",
                "TRIALS",
                "DECISIONS",
                "NEGATIVES",
                "ATTENTION",
                "GAPS",
            )
        )
        + "</div>"
        + f"<h3>{html.escape(research_copy('needs_attention'))}</h3>"
        + _research_rows(list(view.get("needs_attention") or []))
        + f"<h3>{html.escape(research_copy('current_activity'))}</h3>"
        + (
            f"<p class=\"empty semantic-unknown\">{html.escape(research_copy('not_available'))}</p>"
            if counters.get("ACTIVE NOW") is None
            else _research_rows(list(view.get("current_activity") or []))
        )
        + f"<h3>{html.escape(research_copy('universe'))}</h3>"
        + "<p class=\"filters\">"
        + f"<a href=\"/research\">{html.escape(research_copy('all'))}</a> "
        + f"<a href=\"/research?kind=hypotheses\">{html.escape(research_copy('hypotheses'))}</a> "
        + f"<a href=\"/research?kind=experiments\">{html.escape(research_copy('experiments'))}</a> "
        + f"<a href=\"/research?kind=trials\">{html.escape(research_copy('trials'))}</a> "
        + f"<a href=\"/research?kind=decisions\">{html.escape(research_copy('decisions'))}</a> "
        + f"<a href=\"/research?kind=negative\">{html.escape(research_copy('negative'))}</a>"
        + "</p>"
        + "<form method=\"get\" action=\"/research\" class=\"search\">"
        + f"<input name=\"q\" value=\"{q}\" maxlength=\"80\" aria-label=\"{html.escape(research_copy('search_aria'))}\">"
        + f"<input type=\"hidden\" name=\"kind\" value=\"{kind}\">"
        + f"<button type=\"submit\">{html.escape(research_copy('search'))}</button></form>"
        + _research_rows(list(view.get("universe") or []))
        + "</section>"
    )


def _evidence_cards(cards: list[Any], empty_copy: str) -> str:
    if not cards:
        return f"<p class=\"semantic-unknown\">{html.escape(empty_copy)}</p>"
    items = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        summary = card.get("summary_fields") if isinstance(card.get("summary_fields"), dict) else {}
        items.append(
            "<li>"
            f"<span class=\"mono\">{html.escape(str(card.get('record_kind') or ''))}</span> "
            f"<span class=\"mono\">{html.escape(str(card.get('record_id') or card.get('entity_id') or ''))}</span>"
            + "".join(
                f" <span>{html.escape(str(key))}="
                f"<span class=\"mono\">{html.escape(str(value))}</span></span>"
                for key, value in summary.items()
            )
            + "</li>"
        )
    return "<ul>" + "".join(items) + "</ul>"


def _dossier_html(dossier: Mapping[str, Any]) -> str:
    tested = dossier.get("tested") if isinstance(dossier.get("tested"), dict) else {}
    planes = dossier.get("planes") if isinstance(dossier.get("planes"), dict) else {}
    obligations = "".join(
        "<tr class=\"obligation-"
        + html.escape(str(item.get("status") or "UNKNOWN"))
        + "\"><th>"
        + html.escape(obligation_label(str(item.get("code") or "")))
        + f" <span class=\"mono\">{html.escape(str(item.get('code') or ''))}</span>"
        + "</th><td>"
        + html.escape(status_display(str(item.get("status") or "UNKNOWN")))
        + "</td><td>"
        + html.escape(str(item.get("note") or item.get("source") or ""))
        + "</td></tr>"
        for item in dossier.get("obligations") or []
        if isinstance(item, dict)
    )
    history = "".join(
        "<li>"
        + html.escape(decision_kind_label(str(item.get("decision_kind") or "")))
        + f" <span class=\"mono\">{html.escape(str(item.get('decision_kind') or ''))}</span> "
        + f"<span class=\"mono\">{html.escape(str(item.get('record_id') or ''))}</span> "
        + f"<span class=\"mono\">{html.escape(str(item.get('relation') or 'DIRECT'))}</span> "
        + html.escape(str(item.get("rationale") or ""))
        + (
            " — " + html.escape(str(item.get("next_condition")))
            if item.get("next_condition")
            else ""
        )
        + "</li>"
        for item in dossier.get("decision_history") or []
        if isinstance(item, dict)
    ) or f"<p class=\"semantic-unknown\">{html.escape(research_copy('no_decisions'))}</p>"
    write = dossier.get("write_capability") if isinstance(dossier.get("write_capability"), dict) else {}
    writable = write.get("write") == "AVAILABLE"
    locator = dossier.get("locator") if isinstance(dossier.get("locator"), dict) else {}
    guard = dossier.get("science_guard") if isinstance(dossier.get("science_guard"), dict) else {}
    blocked = ", ".join(str(code) for code in guard.get("blocked_codes") or [])
    blocked_banner = (
        f"<p class=\"semantic-warning\">{html.escape(research_copy('promote_blocked'))} "
        f"<span class=\"mono\">{html.escape(blocked)}</span></p>"
        if not guard.get("allowed")
        else ""
    )
    write_status = (
        f"<p>{html.escape(research_copy('read_available' if write.get('read') == 'AVAILABLE' else 'not_available'))} "
        f"/ {html.escape(research_copy('write_available' if writable else 'write_off'))} "
        f"<span class=\"mono\">{html.escape(str(write.get('read') or 'UNKNOWN'))}/"
        f"{html.escape(str(write.get('write') or 'UNKNOWN'))}</span></p>"
    )
    buttons = []
    for kind in dossier.get("owner_decision_kinds") or []:
        disabled = " disabled" if kind == "PROMOTE" and not guard.get("allowed") else ""
        buttons.append(
            f'<button type="submit" name="decision_kind" value="{html.escape(kind)}"{disabled}>'
            f"{html.escape(decision_kind_label(kind))} "
            f"<span class=\"mono\">{html.escape(kind)}</span></button>"
        )
    controls = write_status + blocked_banner + (
        f"<p class=\"semantic-unknown\">{html.escape(research_copy('write_unavailable'))}</p>"
        if not writable
        else (
            "<form method=\"post\" action=\"/research\" class=\"control-zone\" data-mode=\"CONTROL_SURFACE\">"
            "<input type=\"hidden\" name=\"command\" value=\"RESEARCH_DECISION\">"
            f"<input type=\"hidden\" name=\"entity_id\" value=\"{html.escape(str(locator.get('entity_id') or ''))}\">"
            f"<input type=\"hidden\" name=\"truth_plane\" value=\"{html.escape(str(locator.get('truth_plane') or ''))}\">"
            f"<input type=\"hidden\" name=\"native_kind\" value=\"{html.escape(str(locator.get('native_kind') or ''))}\">"
            "<input type=\"hidden\" name=\"expected_evidence_snapshot_sha256\" value=\""
            + html.escape(str(dossier.get("evidence_snapshot_sha256") or ""))
            + "\">"
            "<p>"
            + html.escape(research_copy("snapshot"))
            + f" <span class=\"mono\">{html.escape(str(dossier.get('evidence_snapshot_sha256') or ''))}</span></p>"
            "<label>"
            + html.escape(research_copy("rationale"))
            + "<br><textarea name=\"rationale\" rows=\"3\" maxlength=\"2000\"></textarea></label>"
            "<label>"
            + html.escape(research_copy("next_condition"))
            + "<br><textarea name=\"next_condition\" rows=\"2\" maxlength=\"2000\"></textarea></label>"
            "<p class=\"promote-boundary\">"
            "<label><input type=\"checkbox\" name=\"promote_scientific_only\" value=\"1\"> "
            + html.escape(research_copy("promote_confirm"))
            + "</label></p>"
            + "".join(buttons)
            + "</form>"
        )
    )
    return (
        "<section class=\"experiment-dossier\">"
        + "<table class=\"planes\">"
        + _rows(
            {
                research_copy("execution"): planes.get("execution") or "NO_RUN",
                research_copy("evidence"): planes.get("evidence") or "UNKNOWN",
                research_copy("decision"): planes.get("decision") or "NO_DECISION",
            }
        )
        + "</table>"
        + f"<h3>{html.escape(research_copy('what_was_tested'))}</h3>"
        + f"<p class=\"legacy-note\">{html.escape(research_copy('original_source'))} "
        + f"<span class=\"mono\">{html.escape(research_copy('legacy_en'))}</span></p>"
        + "<table>"
        + _rows(
            {
                "QUESTION": tested.get("question"),
                "ESTIMAND": tested.get("estimand"),
                "POPULATION": tested.get("population"),
                "FALSIFIER": tested.get("falsifier"),
                "HOLDOUT POLICY": tested.get("holdout_policy"),
            },
            translate_keys=True,
        )
        + "</table>"
        + f"<h3>{html.escape(research_copy('evidence'))}</h3><table>"
        + obligations
        + "</table>"
        + f"<h3>{html.escape(research_copy('result'))}</h3><table>"
        + _rows(
            dossier.get("result") if isinstance(dossier.get("result"), dict) else {},
            translate_keys=True,
            empty_as="MISSING",
        )
        + "</table>"
        + f"<h3>{html.escape(research_copy('direct_evidence'))}</h3>"
        + "<div class=\"direct-evidence\">"
        + _evidence_cards(list(dossier.get("direct_evidence") or []), research_copy("no_direct"))
        + "</div>"
        + f"<h3>{html.escape(research_copy('related_prior_memory'))}</h3>"
        + "<div class=\"related-memory\">"
        + f"<p class=\"muted\">{html.escape(research_copy('related_not_direct'))}</p>"
        + _evidence_cards(
            list(dossier.get("related_prior_memory") or []),
            research_copy("no_related"),
        )
        + "</div>"
        + f"<h3>{html.escape(research_copy('decision_history'))}</h3>"
        + (f"<ul>{history}</ul>" if history.startswith("<li>") else history)
        + f"<h3>{html.escape(research_copy('owner_decision'))}</h3>"
        + controls
        + "</section>"
    )


def _research_detail_html(view: Mapping[str, Any]) -> str:
    header = view.get("header") if isinstance(view.get("header"), dict) else {}
    fields = view.get("fields") if isinstance(view.get("fields"), dict) else {}
    lineage = view.get("lineage") if isinstance(view.get("lineage"), dict) else {}
    dossier = view.get("dossier") if isinstance(view.get("dossier"), dict) else None
    gaps = "".join(
        "<li>"
        + html.escape(str(item.get("gap_code") or "UNKNOWN"))
        + " — "
        + html.escape(str(item.get("reason") or ""))
        + "</li>"
        for item in view.get("gaps") or []
        if isinstance(item, dict)
    ) or f"<li class=\"semantic-unknown\">{html.escape(research_copy('none'))}</li>"
    unknown = view.get("unknown") if isinstance(view.get("unknown"), list) else []
    unknown_html = (
        "<ul>" + "".join(f"<li class=\"semantic-unknown\">{html.escape(str(item))}</li>" for item in unknown) + "</ul>"
        if unknown
        else f"<p class=\"semantic-unknown\">{html.escape(research_copy('none'))}</p>"
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
    field_rows = _rows({str(key): value for key, value in fields.items()}, translate_keys=True)
    dossier_html = _dossier_html(dossier) if dossier else ""
    return (
        "<article class=\"evidence-editorial\" data-mode=\"EVIDENCE_EDITORIAL\">"
        f"<p><a href=\"/research\">{html.escape(research_copy('back'))}</a></p>"
        "<header class=\"evidence-header\">"
        f"<p>{html.escape(str(header.get('native_kind') or ''))} "
        f"<span class=\"mono\">{html.escape(str(header.get('entity_id') or ''))}</span></p>"
        f"<h2>{html.escape(str(header.get('title') or ''))}</h2>"
        "<table>"
        + _rows(
            {
                "STATE": header.get("state") or "UNKNOWN",
                "TRUTH PLANE": header.get("truth_plane"),
                **(
                    {}
                    if dossier and header.get("evidence_class") == "NOT_APPLICABLE"
                    else {"EVIDENCE CLASS": header.get("evidence_class")}
                ),
                "SOURCE": header.get("source"),
                "AS OF": header.get("as_of"),
                "OBSERVED AT": header.get("observed_at"),
                "FRESHNESS": header.get("freshness"),
                "NEXT SAFE ACTION": header.get("next_safe_action") or "UNKNOWN",
            },
            translate_keys=True,
        )
        + "</table></header>"
        + dossier_html
        + f"<h3>{html.escape(research_copy('detail'))}</h3><table>"
        + (field_rows or "<tr><td class=\"semantic-unknown\">UNKNOWN</td></tr>")
        + "</table>"
        + f"<h3>{html.escape(research_copy('lineage'))}</h3>"
        + "<div class=\"computational-field\" data-mode=\"COMPUTATIONAL_FIELD\">"
        + "<p class=\"trace-label\">TRACE</p>"
        + _lineage_list(list(lineage.get("inbound") or []), research_copy("inbound"))
        + f"<p class=\"current\">{html.escape(research_copy('current_object'))}</p>"
        + _lineage_list(list(lineage.get("outbound") or []), research_copy("outbound"))
        + "</div>"
        + f"<h3>{html.escape(research_copy('gaps_unknown'))}</h3><ul>"
        + gaps
        + "</ul>"
        + unknown_html
        + f"<h3>{html.escape(research_copy('source_provenance'))}</h3><table>"
        + _rows(provenance)
        + "</table>"
        + f"<h3>{html.escape(research_copy('timeline'))}</h3><ul>"
        + timeline
        + "</ul>"
        + f"<details class=\"technical\"><summary>{html.escape(research_copy('technical'))}</summary><table>"
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
        return (
            f"<p class=\"error\">{html.escape(owner_error(getattr(exc, 'code', str(exc))))}</p>"
            f"<p><a href=\"/research\">{html.escape(research_copy('back'))}</a></p>"
        )


def _page(
    model: dict[str, Any],
    *,
    surface: str,
    copy_blocks: list[dict[str, str]] | None = None,
    error: str = "",
    notice: str = "",
    research_html: str | None = None,
    visual_css: str = "",
    visual_consumed: bool = False,
) -> bytes:
    cockpit = model.get("cockpit") if isinstance(model.get("cockpit"), dict) else {}
    packet = cockpit.get("packet") if isinstance(cockpit.get("packet"), dict) else {}
    runtime = model.get("runtime") if isinstance(model.get("runtime"), dict) else {}
    notice_html = f"<p class=\"error\">{html.escape(error)}</p>" if error else ""
    if notice:
        notice_html += f"<p class=\"notice\">{html.escape(notice)}</p>"
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
        "RESEARCH": research_html
        or (
            f"<h2>{html.escape(research_copy('title'))}</h2>"
            "<p class=\"semantic-unknown\">UNKNOWN</p>"
        ),
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
.direct-evidence {{ border-left: 3px solid var(--accent-signal, #888); padding-left: 1rem; margin-bottom: 1rem; }}
.related-memory {{ border-left: 3px solid var(--text-muted, #999); padding-left: 1rem; margin-bottom: 1rem; }}
.related-memory .muted {{ color: var(--text-muted, #999); }}
.control-zone {{ border: 1px solid var(--border-hairline, #333); padding: 1rem; background: var(--surface-panel, #1c1c1c); margin: 1rem 0; }}
.control-zone textarea {{ width: 100%; background: var(--surface-base, #161616); color: var(--text-primary, #eee); border: 1px solid var(--border-hairline, #333); }}
.obligation-MISSING, .obligation-UNKNOWN {{ color: var(--semantic-warning, #b8860b); }}
.obligation-CONFLICT {{ color: var(--semantic-danger, #a40000); }}
.legacy-note {{ color: var(--text-muted, #999); font-size: 0.9rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
td, th {{ border-bottom: 1px solid var(--border-hairline, #333); padding: 0.35rem 0.5rem; }}
</style></head><body class="steel-signal" data-visual-os-consumed="{consumed}">
<div class="shell">
{_nav(surface)}
<main>
<h1>Factory v1 — локальный срез владельца</h1>
<p>Проекция. UI не владеет научной истиной и не открывает SQLite. START без точной owner phrase не читает ключ и не вызывает Jupiter. git_archaeology_required={html.escape(archaeology)}. Operational-ready milestone is not claimed.</p>
{notice_html}
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
            notice: str = "",
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
                notice=notice,
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
                if path == "/research":
                    if command != "RESEARCH_DECISION":
                        raise ApplicationError("COMMAND_NOT_ALLOWLISTED")
                    query = {
                        "entity_id": fields.get("entity_id") or [],
                        "truth_plane": fields.get("truth_plane") or [],
                        "native_kind": fields.get("native_kind") or [],
                    }
                    app.record_research_decision(
                        {
                            "entity_id": (fields.get("entity_id") or [""])[0],
                            "truth_plane": (fields.get("truth_plane") or [""])[0],
                            "native_kind": (fields.get("native_kind") or [""])[0],
                            "decision_kind": (fields.get("decision_kind") or [""])[0],
                            "expected_evidence_snapshot_sha256": (
                                fields.get("expected_evidence_snapshot_sha256") or [""]
                            )[0],
                            "rationale": (fields.get("rationale") or [""])[0],
                            "next_condition": (fields.get("next_condition") or [""])[0],
                            "promote_scientific_only": (
                                fields.get("promote_scientific_only") or [""]
                            )[0],
                        }
                    )
                    self._render(
                        "RESEARCH",
                        query=query,
                        notice=research_copy("decision_recorded"),
                    )
                    return
                raise ApplicationError("COMMAND_PATH_INVALID")
            except ApplicationError as exc:
                error = owner_error(getattr(exc, "code", str(exc)))
                if path == "/research":
                    self._render(
                        "RESEARCH",
                        error=error,
                        query={
                            "entity_id": fields.get("entity_id") or [],
                            "truth_plane": fields.get("truth_plane") or [],
                            "native_kind": fields.get("native_kind") or [],
                        },
                    )
                    return
                surface = "OPERATIONS" if path == "/operations" else "HOME"
                self._render(surface, error=error)

    return Handler


def serve(app: FactoryApplication, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ApplicationError("WORKBENCH_BIND_NOT_LOCALHOST")
    return ThreadingHTTPServer((host, port), make_handler(app))
