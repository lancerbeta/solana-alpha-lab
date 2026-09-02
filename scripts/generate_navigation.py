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
FACTORY_SEMANTIC_MAP_PATH = "docs/FACTORY_SEMANTIC_MAP.md"


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


def _prior_work_recipe_lines(snapshot: Any) -> list[str]:
    preferred = [
        "QUERY-HFIC-EXACT-RELATED-PRIOR-001",
        "QUERY-HYPOTHESIS-FAST-LANE-SEARCH-PRIOR-WORK-001",
        "QUERY-HFIC-SESSION-BY-SEARCH-KEY-001",
        "QUERY-HFIC-PENDING-SESSION-001",
        "QUERY-T16-PRIOR-WORK-001",
    ]
    queries = getattr(snapshot, "queries", {}) or {}
    lines: list[str] = []
    for recipe_id in preferred:
        if recipe_id in queries:
            purpose = str((queries[recipe_id] or {}).get("purpose") or recipe_id)
            lines.append(f"- `{recipe_id}` — {purpose}")
    if not lines:
        lines.append("- Prior-work query recipes are unavailable in this snapshot.")
    return lines


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
    prior_lines = _prior_work_recipe_lines(snapshot)
    lines = [
        "# Operator navigation",
        "",
        "Generated from the validated Catalog, semantic operability projection, canonical bindings and Delivery Harness. Do not edit manually.",
        "This is a short route map, not a second truth owner or a documentation portal.",
        "",
        "## Active Git discovery",
        "",
        "Project Sources release and owner-smoke receipts are not the active discovery path.",
        "",
        "1. Product or capability question → semantic routes (`docs/FACTORY_SEMANTIC_MAP.md`):",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py search-routes --text \"<NEED>\" --limit 5 --explain --json",
        "```",
        "",
        "2. Known semantic route → resolve route:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-route <SEMANTIC_ROUTE_ID> --json",
        "```",
        "",
        "3. Exact known Catalog ID:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-asset <ASSET_ID> --json",
        "```",
        "",
        "4. Current root (`resolve-binding`):",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-binding <BINDING_ID> --json",
        "```",
        "",
        "Canonical bindings at this commit:",
        "",
        *binding_lines,
        "",
        "5. Concept search:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py search-assets --text <QUERY> --match all --limit 20 --explain --json",
        "```",
        "",
        "6. Declared Catalog relations (`related-assets`, depth at most 2, `authority_inferred: false`):",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py related-assets <ASSET_ID> --depth 2 --direction both --json",
        "```",
        "",
        "7. Prior work — current registered query recipes (historical T16 remains valid):",
        "",
        *prior_lines,
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-query <RECIPE_ID> --json",
        "```",
        "",
        "8. Exact task execution context:",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/delivery_harness.py check",
        "```",
        "",
        "```powershell",
        "uv run --locked --managed-python python -B scripts/delivery_harness.py context --route DIRECT_CURSOR_DELIVERY --task-id <TASK_ID> --contract <CONTRACT_PATH> --json",
        "```",
        "",
        "9. Exhaustive browsing fallback only: generated [`PROJECT_MAP.md`](PROJECT_MAP.md).",
        "",
        "10. Historical / optional Project Sources diagnostics (not the discovery path).",
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
        "- `CONFIG-FACTORY-SEMANTIC-OPERABILITY-001`",
        "- `QUERY-CATALOG-SEARCH-ASSETS-001`",
        "- `QUERY-HFIC-EXACT-RELATED-PRIOR-001`",
        "- `QUERY-T16-PRIOR-WORK-001`",
        "",
        "No provider, credential, wallet, transaction, cash, deployment, or Project Sources UI action is performed by these commands.",
        "Semantic routing never grants authority (`authority_granted = false`).",
        "",
    ]
    rendered = "\n".join(lines)
    if "provider_route_capability_registry_v3.yaml" in rendered:
        raise RuntimeError("operator_navigation_hardcoded_v3_path")
    if "PARTIAL_COVERAGE" in rendered:
        raise RuntimeError("operator_navigation_stale_partial_coverage")
    return rendered.encode("utf-8")


def render_factory_semantic_map(root: Path, snapshot: Any) -> bytes:
    if "CONFIG-FACTORY-SEMANTIC-OPERABILITY-001" not in getattr(snapshot, "assets", {}):
        return (
            "# Factory semantic map\n\n"
            "Synthetic Catalog snapshot without semantic projection roots.\n"
        ).encode("utf-8")
    from solana_alpha_lab.factory_semantic_operability import (  # noqa: PLC0415
        PROJECTION_RELATIVE,
        load_semantic_projection,
        validate_semantic_projection,
    )

    projection = load_semantic_projection(root)
    manifest = snapshot.manifest if isinstance(getattr(snapshot, "manifest", None), dict) else {}
    bindings = manifest.get("canonical_bindings") or {}
    violations = validate_semantic_projection(
        projection,
        assets=snapshot.assets,
        bindings=bindings,
        queries=getattr(snapshot, "queries", {}) or {},
    )
    if violations:
        raise RuntimeError("factory_semantic_map_invalid:" + ",".join(violations))
    lines = [
        "# Factory semantic map",
        "",
        "Generated from validated Catalog + `configs/factory_semantic_operability_v1.yaml`. Do not edit manually.",
        "Reference-only navigation. `authority_granted = false` for every route. Runtime values require machine readback.",
        "",
        f"Projection: `{projection.get('projection_id')}` (`{PROJECTION_RELATIVE}`).",
        "Validation: `PASS`.",
        "",
        "| Owner/agent need | Semantic route | Current root | Truth plane | Inspection surface | Authority |",
        "| ---------------- | -------------- | ------------ | ----------- | ------------------ | --------- |",
    ]
    for route in sorted(
        projection.get("routes") or [],
        key=lambda item: str(item.get("semantic_route_id") or ""),
    ):
        need = (route.get("owner_questions") or ["(unspecified)"])[0]
        roots: list[str] = []
        for binding_id in route.get("root_binding_ids") or []:
            target = (bindings.get(binding_id) or {}).get("target_asset_id")
            roots.append(f"{binding_id}→{target or 'UNRESOLVED'}")
        for asset_id in route.get("root_asset_ids") or []:
            roots.append(str(asset_id))
        root_text = "; ".join(roots) if roots else "(query recipes only)"
        runtime = route.get("runtime_resolution") or {}
        mode = runtime.get("mode") or "NONE"
        if mode == "NONE":
            inspection = "resolve-route / Catalog dereference"
        else:
            ops = ", ".join(runtime.get("operator_asset_ids") or []) or "operator root"
            inspection = f"{mode} via {ops}"
        recipes = route.get("query_recipe_ids") or []
        if recipes:
            inspection = inspection + "; recipes " + ", ".join(recipes)
        values = (
            need,
            route.get("semantic_route_id"),
            root_text,
            route.get("status_plane"),
            inspection,
            "false",
        )
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "Planes: `CAPABILITY` = what Git currently knows how to do; `RUNTIME` = machine readback;",
            "`SCIENTIFIC` = evidence/results; `AUTHORITY` = gate/task resolver only; `MIXED` = explicit multi-plane.",
            "",
            "Not a roadmap. Not task selection. Not runtime status. Not authority.",
        ]
    )
    rendered = ("\n".join(lines) + "\n").encode("utf-8")
    if len(rendered) > 24 * 1024:
        raise RuntimeError("factory_semantic_map_too_large")
    return rendered


def expected_outputs(snapshot: Any) -> dict[str, bytes]:
    return {
        PROJECT_MAP_PATH: render_project_map(snapshot),
        EDGE_PROJECTION_PATH: render_edge_projection(snapshot),
        OPERATOR_NAVIGATION_PATH: render_operator_navigation(ROOT, snapshot),
        FACTORY_SEMANTIC_MAP_PATH: render_factory_semantic_map(ROOT, snapshot),
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
