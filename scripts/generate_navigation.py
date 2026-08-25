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
    """Render Git-native Catalog discovery first; Project Sources stay historical."""
    context = evaluate_context(root)
    manifest = snapshot.manifest if isinstance(getattr(snapshot, "manifest", None), dict) else {}
    bindings = manifest.get("canonical_bindings") or {}
    binding_lines = []
    for binding_id in sorted(bindings):
        spec = bindings[binding_id]
        binding_lines.append(
            f"- `{binding_id}` → `{spec['target_asset_id']}` (`{spec.get('semantics', '')}`)"
        )
    if not binding_lines:
        binding_lines.append("- Canonical bindings are unavailable in this synthetic snapshot.")
    lines = [
        "# Operator navigation",
        "",
        "Generated from the validated Catalog, canonical bindings and Delivery Harness. Do not edit manually.",
        "This is a short route map, not a second truth owner or a documentation portal.",
        "",
        "## Active Git discovery",
        "",
        "Project Sources release and owner-smoke receipts are not the active discovery path.",
        "",
        "1. Exact known Catalog ID:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-asset <ASSET_ID> --json",
        "```",
        "",
        "2. Current semantic root (`resolve-binding`):",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-binding ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY --json",
        "```",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-binding ACTIVE-FACTORY-MARKET-FEATURE-SURFACE --json",
        "```",
        "",
        "Canonical bindings at this commit:",
        "",
        *binding_lines,
        "",
        "3. Concept search:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py search-assets --text <QUERY> --match all --limit 20 --explain --json",
        "```",
        "",
        "4. Declared Catalog relations (`related-assets`, depth at most 2, `authority_inferred: false`):",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py related-assets <ASSET_ID> --depth 2 --direction both --json",
        "```",
        "",
        "5. Prior work is `PARTIAL_COVERAGE` in this atom. Use recipe `QUERY-T16-PRIOR-WORK-001` only after substituting its documented parameters. The `prior-work-references` command is not implemented.",
        "",
        "6. Task execution context:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/delivery_harness.py check",
        "```",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/delivery_harness.py context --route DIRECT_CURSOR_DELIVERY --task-id <TASK_ID> --contract <CONTRACT_PATH> --json",
        "```",
        "",
        "7. Exhaustive browsing: generated [`PROJECT_MAP.md`](PROJECT_MAP.md).",
        "",
        "## Historical / optional Project Sources",
        "",
        "The following is optional owner-managed export diagnostics. It is not the Git discovery path.",
        "",
        f"- Historical Project Sources release: `{context['active_release_id']}`",
        f"- Owner-smoke receipt: `{context['activation_receipt']}`",
        f"- Historical task in that release: `{context['active_task_id']}`",
        f"- Bound source roles: `{context['source_role_count']}`",
        "- A local Project Sources mirror is optional diagnostic input; it is never canonical.",
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
        "- `MIRROR_MATCHES_ACTIVE_RELEASE`: the optional bytes agree with the historical release.",
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
        "- `CATALOG-ROOT-001`",
        "- `GENERATOR-CATALOG-NAVIGATION-001`",
        "- `CTRL-AGENTS-001`",
        "- `QUERY-CATALOG-SEARCH-ASSETS-001`",
        "- `QUERY-T16-PRIOR-WORK-001`",
        "",
        "No provider, credential, wallet, transaction, cash, deployment, or Project Sources UI action is performed by these commands.",
        "",
    ]
    rendered = "\n".join(lines)
    if "provider_route_capability_registry_v3.yaml" in rendered:
        raise RuntimeError("operator_navigation_hardcoded_v3_path")
    return rendered.encode("utf-8")



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
