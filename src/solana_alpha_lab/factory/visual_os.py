"""Read the canonical Visual OS contract and emit CSS custom properties."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

VISUAL_OS_RELATIVE = "configs/smial_visual_operating_system_v1.yaml"


def load_visual_os(root: Path) -> dict[str, Any] | None:
    path = root / VISUAL_OS_RELATIVE
    if not path.is_file():
        return None
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else None


def visual_os_css(root: Path) -> str:
    contract = load_visual_os(root)
    if contract is None:
        return (
            ":root{--surface-void:#111;--surface-base:#161616;--surface-panel:#1c1c1c;"
            "--border-hairline:#333;--text-primary:#eee;--text-muted:#999;"
            "--accent-signal:#888;--semantic-warning:#b8860b;--semantic-danger:#a40000;"
            "--semantic-unknown:#777;}"
        )
    palette = contract.get("palette") if isinstance(contract.get("palette"), dict) else {}
    surface = palette.get("surface") if isinstance(palette.get("surface"), dict) else {}
    border = palette.get("border") if isinstance(palette.get("border"), dict) else {}
    text = palette.get("text") if isinstance(palette.get("text"), dict) else {}
    accent = palette.get("accent") if isinstance(palette.get("accent"), dict) else {}
    semantic = palette.get("semantic") if isinstance(palette.get("semantic"), dict) else {}
    tokens = {
        "--surface-void": surface.get("void"),
        "--surface-base": surface.get("base"),
        "--surface-panel": surface.get("panel"),
        "--border-hairline": border.get("hairline"),
        "--text-primary": text.get("primary"),
        "--text-secondary": text.get("secondary"),
        "--text-muted": text.get("muted"),
        "--accent-signal": accent.get("signal"),
        "--semantic-warning": semantic.get("warning"),
        "--semantic-danger": semantic.get("danger"),
        "--semantic-unknown": semantic.get("unknown"),
    }
    pairs = [f"{name}:{value}" for name, value in tokens.items() if isinstance(value, str)]
    return ":root{" + ";".join(pairs) + ";}"


def visual_os_layout_css() -> str:
    """Reusable workstation layout. Tokens come from the Visual OS contract."""
    return """
html,body { background: var(--surface-void, #111); color: var(--text-primary, #eee); font-family: system-ui, sans-serif; margin: 0; }
.shell { display: grid; grid-template-columns: 12rem minmax(0, 1fr); min-height: 100vh; }
.signal-rail { background: var(--surface-base, #161616); border-right: 1px solid var(--border-hairline, #333); padding: 1.5rem 1rem; }
.signal-rail .brand { letter-spacing: 0.12em; margin: 0 0 1.5rem; color: var(--text-secondary, #bbb); }
.signal-rail nav { display: flex; flex-direction: column; gap: 0.75rem; }
.signal-rail a { color: var(--text-muted, #999); text-decoration: none; }
.signal-rail a[aria-current="page"] { color: var(--accent-signal, #888); font-weight: 600; }
main { background: var(--surface-base, #161616); padding: 1.5rem 2rem 3rem; max-width: 72rem; min-width: 0; }
.page-head h1 { font-size: 1.35rem; font-weight: 650; margin: 0 0 0.35rem; }
.page-question { color: var(--text-secondary, #bbb); margin: 0 0 0.75rem; font-size: 1rem; }
.page-note { color: var(--text-muted, #999); margin: 0 0 1.25rem; font-size: 0.9rem; }
.fact-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: 0.75rem; margin: 0 0 1.25rem; }
.fact { background: var(--surface-panel, #1c1c1c); border: 1px solid var(--border-hairline, #333); padding: 0.65rem 0.75rem; }
.fact .label { display: block; color: var(--text-muted, #999); font-size: 0.75rem; margin: 0 0 0.25rem; }
.fact .value { margin: 0; overflow-wrap: anywhere; word-break: break-word; }
.canon, .mono { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: 0.82em; color: var(--text-muted, #999); overflow-wrap: anywhere; }
.dual { display: flex; flex-direction: column; gap: 0.15rem; align-items: flex-start; }
section { margin: 1.25rem 0; }
h2 { font-size: 1.05rem; margin: 0 0 0.6rem; }
h3 { font-size: 0.9rem; margin: 0.9rem 0 0.4rem; color: var(--text-secondary, #bbb); }
.error, .danger { color: var(--semantic-danger, #a40000); }
.semantic-unknown { color: var(--semantic-unknown, #777); }
.semantic-warning { color: var(--semantic-warning, #b8860b); }
.degraded { border: 1px solid var(--border-hairline, #333); padding: 0.75rem 1rem; background: var(--surface-panel, #1c1c1c); }
form button { margin-right: 0.5rem; margin-bottom: 0.5rem; }
.copy-hint { color: var(--text-muted, #999); }
.copy-block { position: relative; margin: 1rem 0; padding: 0.75rem 1rem; border: 1px solid var(--border-hairline, #333); background: var(--surface-panel, #1c1c1c); }
.copy-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.copy-head h2 { font-size: 1rem; margin: 0; }
.copy-btn { opacity: 1; pointer-events: auto; }
.copy-block:hover .copy-btn, .copy-block:focus-within .copy-btn { opacity: 1; pointer-events: auto; }
.copy-text { white-space: pre-wrap; word-break: break-word; margin: 0.75rem 0 0; }
.attention { border: 1px solid var(--border-hairline, #333); padding: 0.75rem 1rem; margin: 0.75rem 0; background: var(--surface-panel, #1c1c1c); }
.attention h3 { margin: 0 0 0.4rem; color: var(--text-primary, #eee); }
.non-claims { font-weight: 600; color: var(--text-secondary, #bbb); }
.danger-zone { border: 2px solid var(--semantic-danger, #a40000); padding: 0.75rem; margin-top: 1rem; }
.safe-actions { margin: 0.75rem 0; }
.counters { display: grid; grid-template-columns: repeat(auto-fit, minmax(7rem, 1fr)); gap: 0.75rem; margin: 1rem 0; }
.counter { background: var(--surface-panel, #1c1c1c); border: 1px solid var(--border-hairline, #333); padding: 0.5rem 0.75rem; }
.counter h3 { font-size: 0.75rem; margin: 0 0 0.35rem; color: var(--text-muted, #999); }
.research-table { table-layout: fixed; width: 100%; }
.research-table th:nth-child(2), .research-table td:nth-child(2) { width: 28%; }
.title-scan { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-word; }
.research-table a { color: var(--text-primary, #eee); }
.trace-resolved { color: var(--text-primary, #eee); }
.trace-gap { color: var(--semantic-warning, #b8860b); }
.trace-conflict { color: var(--semantic-danger, #a40000); font-weight: bold; }
.evidence-editorial .evidence-header { border-bottom: 1px solid var(--border-hairline, #333); margin-bottom: 1rem; }
.direct-evidence { border-left: 3px solid var(--accent-signal, #888); padding-left: 1rem; margin-bottom: 1rem; }
.related-memory { border-left: 3px solid var(--text-muted, #999); padding-left: 1rem; margin-bottom: 1rem; }
.related-memory .muted { color: var(--text-muted, #999); }
.control-zone { border: 1px solid var(--border-hairline, #333); padding: 1rem; background: var(--surface-panel, #1c1c1c); margin: 1rem 0; }
.control-zone textarea { width: 100%; background: var(--surface-base, #161616); color: var(--text-primary, #eee); border: 1px solid var(--border-hairline, #333); }
.obligation-MISSING, .obligation-UNKNOWN { color: var(--semantic-warning, #b8860b); }
.obligation-CONFLICT { color: var(--semantic-danger, #a40000); }
.legacy-note { color: var(--text-muted, #999); font-size: 0.85rem; }
details.technical { margin: 1rem 0; color: var(--text-muted, #999); }
details.technical > summary { cursor: pointer; color: var(--text-secondary, #bbb); margin-bottom: 0.5rem; }
.cmd-btn .canon { display: block; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
th { text-align: left; padding-right: 1rem; vertical-align: top; color: var(--text-muted, #999); font-weight: 600; }
td, th { border-bottom: 1px solid var(--border-hairline, #333); padding: 0.35rem 0.5rem; word-break: break-word; }
"""


def visual_os_consumed(root: Path) -> bool:
    contract = load_visual_os(root)
    if contract is None:
        return False
    return (
        contract.get("appearance") == "DARK_ONLY"
        and (contract.get("identity") or {}).get("base") == "STEEL_SIGNAL"
    )
