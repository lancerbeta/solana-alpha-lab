#!/usr/bin/env python3
"""Generate deterministic navigation views from the validated Catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_catalog import ROOT, load_and_validate

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task34a_documentation_foundation import evaluate_context

PROJECT_MAP_PATH = "docs/PROJECT_MAP.md"
EDGE_PROJECTION_PATH = "catalog/generated/asset_edges.json"
OPERATOR_NAVIGATION_PATH = "docs/OPERATOR_NAVIGATION.md"


def markdown_cell(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def relation_text(asset: dict[str, Any]) -> str:
    relations = sorted(
        (
            relation["relation_type"],
            relation["target_asset_id"],
        )
        for relation in asset["relations"]
    )
    return "; ".join(f"{kind} -> {target}" for kind, target in relations) or "NONE"


def render_project_map(snapshot: Any) -> bytes:
    lines = [
        "# Project map",
        "",
        "Generated from `SMIAL-PROJECT-ASSET-CATALOG`. Do not edit manually.",
        "Integrity hashes, receipts, fingerprints, and evidence payloads are intentionally excluded.",
        "",
        "| Stable ID | Type | Status | Purpose | Logical location | Relations |",
        "|---|---|---|---|---|---|",
    ]
    for asset_id in sorted(snapshot.assets):
        asset = snapshot.assets[asset_id]
        values = (
            asset_id,
            asset["asset_type"],
            asset["status"],
            asset["purpose"],
            asset["location"]["logical_uri"],
            relation_text(asset),
        )
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_edge_projection(snapshot: Any) -> bytes:
    edges = [
        {
            "source_asset_id": source_id,
            "relation": relation["relation_type"],
            "target_asset_id": relation["target_asset_id"],
        }
        for source_id, asset in snapshot.assets.items()
        for relation in asset["relations"]
    ]
    edges.sort(
        key=lambda edge: (
            edge["source_asset_id"],
            edge["relation"],
            edge["target_asset_id"],
        )
    )
    payload = {
        "schema_version": "1.0",
        "catalog_id": snapshot.manifest["catalog_id"],
        "edges": edges,
    }
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def render_operator_navigation(root: Path, snapshot: Any) -> bytes:
    """Render stable, repository-native entry points without local runtime paths."""
    context = evaluate_context(root)
    catalog_ids = (
        "CATALOG-ROOT-001",
        "GENERATOR-CATALOG-NAVIGATION-001",
        "CTRL-AGENTS-001",
    )
    missing_ids = [asset_id for asset_id in catalog_ids if asset_id not in snapshot.assets]
    if missing_ids:
        raise ValueError("OPERATOR_NAVIGATION_CATALOG_IDS_MISSING:" + ",".join(missing_ids))
    lines = [
        "# Operator navigation",
        "",
        "Generated from the active Project Sources release and validated Catalog. Do not edit manually.",
        "This is a short route map, not a second truth owner or a documentation portal.",
        "",
        "## Current binding",
        "",
        f"- Active Project Sources release: `{context['active_release_id']}`",
        f"- Owner-smoke receipt: `{context['activation_receipt']}`",
        f"- Active task in that release: `{context['active_task_id']}`",
        f"- Bound source roles: `{context['source_role_count']}`",
        "- A local Project Sources mirror is optional diagnostic input; it is never canonical.",
        "",
        "## Safe first command",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/show_task34a_context.py --format text",
        "```",
        "",
        "To inspect an optional local mirror without printing its path:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/show_task34a_context.py --format json --sources-dir <local-sources-directory>",
        "```",
        "",
        "## Read the result",
        "",
        "- `MIRROR_MATCHES_ACTIVE_RELEASE`: the optional bytes agree with the active release.",
        "- `STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED` or `MIRROR_UNAVAILABLE`: use the activated registry/receipt; no automatic repair is needed.",
        "- `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW`: stop selection and resolve the conflicting Source state before proceeding.",
        "- A `TASK34A_CONTEXT: FAIL` is a release-binding failure, not permission to choose a replacement truth owner.",
        "",
        "## Runbooks",
        "",
        "- [Start or resume a task](runbooks/task_entry_and_resume.md)",
        "- [Handle Source mirror drift](runbooks/source_mirror_drift.md)",
        "- [Stop at external authority](runbooks/external_authority_stop.md)",
        "",
        "## Catalog anchors",
        "",
    ]
    lines.extend(f"- `{asset_id}`" for asset_id in catalog_ids)
    lines.extend(
        [
            "",
            "No provider, credential, wallet, transaction, cash, deployment, or Project Sources UI action is performed by these commands.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def expected_outputs(snapshot: Any) -> dict[str, bytes]:
    return {
        PROJECT_MAP_PATH: render_project_map(snapshot),
        EDGE_PROJECTION_PATH: render_edge_projection(snapshot),
        OPERATOR_NAVIGATION_PATH: render_operator_navigation(ROOT, snapshot),
    }


def write_outputs(root: Path, outputs: dict[str, bytes]) -> bool:
    changed = False
    for relative, expected in outputs.items():
        path = root / relative
        observed = path.read_bytes() if path.is_file() else None
        if observed != expected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
            changed = True
    return changed


def check_outputs(root: Path, outputs: dict[str, bytes]) -> list[str]:
    stale = []
    for relative, expected in outputs.items():
        path = root / relative
        if not path.is_file() or path.read_bytes() != expected:
            stale.append(relative)
    return stale


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_and_validate(allow_generated_drift=args.write)
    outputs = expected_outputs(snapshot)
    if args.write:
        changed = write_outputs(ROOT, outputs)
        print(f"GENERATOR_WRITE: {'UPDATED' if changed else 'UNCHANGED'}")
        return 0
    stale = check_outputs(ROOT, outputs)
    if stale:
        print("GENERATOR_CHECK: FAIL")
        print("STALE_OUTPUTS: " + ",".join(stale))
        return 1
    print("GENERATOR_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
