#!/usr/bin/env python3
"""Generate deterministic navigation views from the validated Catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_catalog import ROOT, load_and_validate

PROJECT_MAP_PATH = "docs/PROJECT_MAP.md"
EDGE_PROJECTION_PATH = "catalog/generated/asset_edges.json"


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


def expected_outputs(snapshot: Any) -> dict[str, bytes]:
    return {
        PROJECT_MAP_PATH: render_project_map(snapshot),
        EDGE_PROJECTION_PATH: render_edge_projection(snapshot),
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
