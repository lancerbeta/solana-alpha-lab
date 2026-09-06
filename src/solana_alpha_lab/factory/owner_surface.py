"""Reusable owner-surface HTML. Presentation only; owns no domain truth."""

from __future__ import annotations

import html
from typing import Any, Iterable, Mapping

from solana_alpha_lab.factory.owner_language import (
    command_label,
    shell_copy,
    status_gloss,
    surface_copy,
)


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def canon(value: Any) -> str:
    text = str(value if value is not None else "")
    if not text:
        return ""
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


def status_html(status: Any) -> str:
    canonical = str(status or "UNKNOWN")
    gloss = status_gloss(canonical)
    unknown = canonical in {"UNKNOWN", "MISSING", "EMPTY", "NOT_APPLICABLE", "NOT_PRESENT"}
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
        displayed = empty_as if value is None and empty_as is not None else _plain(value)
        rows.append(f"<tr><th>{esc(key)}</th><td>{esc(displayed)}</td></tr>")
    return "".join(rows)


def _plain(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        return value
    import json

    return json.dumps(value, ensure_ascii=False)
