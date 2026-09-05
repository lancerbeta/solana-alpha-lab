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
        "--text-muted": text.get("muted"),
        "--accent-signal": accent.get("signal"),
        "--semantic-warning": semantic.get("warning"),
        "--semantic-danger": semantic.get("danger"),
        "--semantic-unknown": semantic.get("unknown"),
    }
    pairs = [f"{name}:{value}" for name, value in tokens.items() if isinstance(value, str)]
    return ":root{" + ";".join(pairs) + ";}"


def visual_os_consumed(root: Path) -> bool:
    contract = load_visual_os(root)
    if contract is None:
        return False
    return (
        contract.get("appearance") == "DARK_ONLY"
        and (contract.get("identity") or {}).get("base") == "STEEL_SIGNAL"
    )
