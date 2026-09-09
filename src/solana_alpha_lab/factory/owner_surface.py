"""Reusable owner-surface HTML. Presentation only; owns no domain truth."""

from __future__ import annotations

import html
from typing import Any, Iterable, Mapping

from urllib.parse import urlencode

from solana_alpha_lab.factory.owner_language import (
    command_label,
    shell_copy,
    status_gloss,
    surface_copy,
    token_gloss,
)


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def machine_text(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    import json

    return json.dumps(value, ensure_ascii=False)


def cell_html(value: Any) -> str:
    return esc(machine_text(value))


def canon(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        if not value:
            return ""
        text = value
    else:
        text = machine_text(value)
    return f'<span class="canon">{esc(text)}</span>'


def dual(primary: str, machine: Any, *, unknown: bool = False) -> str:
    css = "semantic-unknown" if unknown else ""
    machine_html = canon(machine)
    if not machine_html:
        return f'<span class="{css}">{esc(primary)}</span>'
    return (
        f'<span class="dual"><span class="{css}">{esc(primary)}</span>'
        f"{machine_html}</span>"
    )


def token_dual(
    value: Any,
    gloss_map: Mapping[str, str],
    *,
    empty: str = "UNKNOWN",
) -> str:
    gloss, canonical, unknown = token_gloss(gloss_map, value, empty=empty)
    if gloss:
        return dual(gloss, canonical, unknown=unknown)
    if unknown:
        return dual(canonical, canonical, unknown=True)
    return canon(canonical)


def status_html(status: Any) -> str:
    canonical = str(status or "UNKNOWN")
    gloss = status_gloss(canonical)
    unknown = canonical in {
        "UNKNOWN",
        "MISSING",
        "EMPTY",
        "NOT_APPLICABLE",
        "NOT_PRESENT",
        "UNAVAILABLE",
        "NOT_CONFIGURED",
        "PARTIAL",
        "DEGRADED",
        "ACTION_REQUIRED",
    }
    if gloss:
        return dual(gloss, canonical, unknown=unknown)
    return canon(canonical)


def page_head(surface: str, *, note: str) -> str:
    return (
        '<header class="page-head">'
        f"<h1>{esc(surface_copy(surface, 'h1'))}</h1>"
        f'<p class="page-question">{esc(surface_copy(surface, "question"))}</p>'
        f'<p class="page-note">{esc(note)}</p>'
        "</header>"
    )


def fact(label: str, value_html: str) -> str:
    return (
        f'<article class="fact"><span class="label">{esc(label)}</span>'
        f'<div class="value">{value_html}</div></article>'
    )


def fact_strip(items: Iterable[tuple[str, str]]) -> str:
    cards = "".join(fact(label, value) for label, value in items)
    return f'<div class="fact-strip">{cards}</div>' if cards else ""


def technical(inner: str, *, title: str | None = None) -> str:
    heading = title or shell_copy("technical")
    return (
        '<details class="technical">'
        f"<summary>{esc(heading)}</summary>"
        f"{inner}</details>"
    )


def command_button(value: str, *, extra: str = "") -> str:
    return (
        f'<button type="submit" class="cmd-btn" name="command" value="{esc(value)}"{extra}>'
        f"{esc(command_label(value))}{canon(value)}</button>"
    )


def compact_title(text: str, *, limit: int = 88) -> tuple[str, bool]:
    raw = str(text or "")
    if len(raw) <= limit:
        return raw, False
    return raw[: limit - 1].rstrip() + "…", True


def mapping_rows(mapping: Mapping[str, Any], *, empty_as: str | None = None) -> str:
    rows = []
    for key, value in mapping.items():
        displayed = empty_as if value is None and empty_as is not None else machine_text(value)
        rows.append(f"<tr><th>{esc(key)}</th><td>{esc(displayed)}</td></tr>")
    return "".join(rows)


DEFAULT_PAGE_SIZE = 25
ACTIVE_POSITION_STATES = frozenset(
    {
        "WATCHED",
        "SIGNALLED",
        "INTENT_CREATED",
        "ATTEMPTING",
        "OPEN",
        "PARTIAL",
        "UNKNOWN",
        "EXIT_REQUIRED",
        "EXITING",
        "UNRESOLVED",
    }
)
HISTORY_POSITION_STATES = frozenset({"CLOSED", "RECONCILED"})


def parse_page(query: Mapping[str, list[str]] | None, name: str = "page") -> int:
    if not query:
        return 1
    raw = (query.get(name) or ["1"])[0]
    try:
        page = int(raw)
    except (TypeError, ValueError):
        return 1
    return page if page > 0 else 1


def paginate(
    rows: list[Any],
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    total = len(rows)
    page = max(1, int(page))
    start = (page - 1) * page_size
    if start >= total and total:
        page = max(1, (total - 1) // page_size + 1)
        start = (page - 1) * page_size
    sliced = rows[start : start + page_size]
    end = start + len(sliced)
    return {
        "rows": sliced,
        "total": total,
        "page": page,
        "page_size": page_size,
        "start_ordinal": start + 1 if sliced else 0,
        "end_ordinal": end,
        "has_prev": page > 1 and total > page_size,
        "has_next": end < total,
        "show_controls": total > page_size,
    }


def pager_html(
    info: Mapping[str, Any],
    *,
    base_path: str,
    params: Mapping[str, str] | None = None,
    page_param: str = "page",
) -> str:
    total = int(info.get("total") or 0)
    start = int(info.get("start_ordinal") or 0)
    end = int(info.get("end_ordinal") or 0)
    page = int(info.get("page") or 1)
    summary = f"Всего {total}"
    if info.get("show_controls"):
        summary += f" · {start}–{end} из {total}"
    if not info.get("show_controls"):
        return f'<p class="pager">{esc(summary)}</p>'
    query = dict(params or {})

    def _href(target: int) -> str:
        items = {**query, page_param: str(target)}
        encoded = urlencode({key: value for key, value in items.items() if value})
        href = f"{base_path}?{encoded}" if encoded else base_path
        return esc(href)

    prev = (
        f'<a href="{_href(page - 1)}">Назад</a>'
        if info.get("has_prev")
        else "<span>Назад</span>"
    )
    nxt = (
        f'<a href="{_href(page + 1)}">Вперёд</a>'
        if info.get("has_next")
        else "<span>Вперёд</span>"
    )
    return (
        f'<p class="pager">{esc(summary)} · {prev} · {esc(str(page))} · {nxt}</p>'
    )


def compact_id_html(value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return canon("UNKNOWN")
    return (
        f'<span class="entity-id"><span class="canon" title="{esc(text)}">{esc(text)}</span></span>'
    )


def zone(title: str, inner: str) -> str:
    return f'<section class="zone"><h2>{esc(title)}</h2>{inner}</section>'
