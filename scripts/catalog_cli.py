#!/usr/bin/env python3
"""Read-only stable-ID resolver for the SMIAL Project Asset Catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_catalog import ROOT, CatalogValidationError, load_and_validate

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.catalog_discovery import (
    CatalogDiscoveryError,
    related_catalog_assets,
    resolve_canonical_binding,
    search_catalog_assets,
)


def emit(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        if isinstance(value, dict):
            for key, item in value.items():
                print(f"{key}: {item}")
        else:
            print(value)


def search_assets(
    assets: dict[str, dict[str, Any]],
    text: str,
    *,
    asset_type: str | None = None,
    consumer: str | None = None,
    status: str | None = None,
    relation: str | None = None,
    match: str = "all",
    limit: int = 20,
    explain: bool = False,
    bindings: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return deterministic, bounded metadata matches from the validated Catalog."""

    try:
        return search_catalog_assets(
            assets,
            text,
            bindings=bindings,
            asset_type=asset_type,
            consumer=consumer,
            status=status,
            relation=relation,
            match=match,
            limit=limit,
            explain=explain,
        )
    except CatalogDiscoveryError as exc:
        raise ValueError(str(exc)) from exc


ERROR_NEXT = {
    "BINDING_NOT_FOUND": "Inspect catalog/catalog_manifest.yaml canonical_bindings or search-assets for the binding id.",
    "BINDING_RELEVANT_BYTES_DIRTY": "Commit or restore catalog/catalog_manifest.yaml, Catalog asset shards, and the bound target path.",
    "LIMIT_OUT_OF_RANGE": "Pass --limit as an integer from 1 to 50.",
    "DEPTH_OUT_OF_RANGE": "Pass --depth as 1 or 2.",
}


def _emit_error(code: str, as_json: bool, **fields: Any) -> int:
    payload = {"error": code, **fields}
    if code in ERROR_NEXT and "next" not in payload:
        payload["next"] = ERROR_NEXT[code]
    if as_json:
        emit(payload, True)
    else:
        extras = " ".join(
            f"{key}={value}" for key, value in payload.items() if key != "error" and value is not None
        )
        print(f"{code}" + (f": {extras}" if extras else ""))
    return 2


def _parse_bounded_int(value: str, *, minimum: int, maximum: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    list_assets = sub.add_parser("list-assets")
    list_assets.add_argument("--json", action="store_true")

    resolve_asset = sub.add_parser("resolve-asset")
    resolve_asset.add_argument("asset_id")
    resolve_asset.add_argument("--json", action="store_true")

    resolve_query = sub.add_parser("resolve-query")
    resolve_query.add_argument("recipe_id")
    resolve_query.add_argument("--json", action="store_true")

    resolve_binding = sub.add_parser("resolve-binding")
    resolve_binding.add_argument("binding_id")
    resolve_binding.add_argument("--json", action="store_true")

    search = sub.add_parser("search-assets")
    search.add_argument("--text", required=True)
    search.add_argument("--asset-type")
    search.add_argument("--consumer")
    search.add_argument("--status")
    search.add_argument("--relation")
    search.add_argument("--match", choices=("all", "any"), default="all")
    search.add_argument("--limit", default="20")
    search.add_argument("--explain", action="store_true")
    search.add_argument("--json", action="store_true")

    related = sub.add_parser("related-assets")
    related.add_argument("asset_id")
    related.add_argument("--depth", default="1")
    related.add_argument("--direction", choices=("out", "in", "both"), default="both")
    related.add_argument("--relation", action="append", dest="relations")
    related.add_argument("--limit", default="20")
    related.add_argument("--json", action="store_true")

    args = parser.parse_args()
    as_json = bool(getattr(args, "json", False))
    try:
        snapshot = load_and_validate()
    except CatalogValidationError as exc:
        return _emit_error("BINDING_CATALOG_INVALID" if args.command == "resolve-binding" else "CATALOG_INVALID", as_json, detail=str(exc))
    except Exception as exc:
        return _emit_error("CATALOG_INVALID", as_json, detail=str(exc))

    if args.command == "list-assets":
        values = sorted(snapshot.assets)
        emit(values, as_json)
        return 0

    if args.command == "resolve-asset":
        record = snapshot.assets.get(args.asset_id)
        if record is None:
            return _emit_error("ASSET_NOT_FOUND", as_json, asset_id=args.asset_id)
        emit(record, as_json)
        return 0

    if args.command == "resolve-query":
        record = snapshot.queries.get(args.recipe_id)
        if record is None:
            return _emit_error("QUERY_NOT_FOUND", as_json, recipe_id=args.recipe_id)
        emit(record, as_json)
        return 0

    if args.command == "resolve-binding":
        try:
            payload = resolve_canonical_binding(
                snapshot,
                args.binding_id,
                root=ROOT,
                shard_paths=list(snapshot.manifest["root_resolver"]["asset_registries"]),
            )
        except CatalogDiscoveryError as exc:
            return _emit_error(str(exc), as_json, binding_id=args.binding_id)
        emit(payload, as_json)
        return 0

    if args.command == "search-assets":
        limit = _parse_bounded_int(args.limit, minimum=1, maximum=50)
        if limit is None:
            return _emit_error("LIMIT_OUT_OF_RANGE", as_json)
        try:
            matches = search_assets(
                snapshot.assets,
                args.text,
                asset_type=args.asset_type,
                consumer=args.consumer,
                status=args.status,
                relation=args.relation,
                match=args.match,
                limit=limit,
                explain=args.explain,
                bindings=snapshot.manifest.get("canonical_bindings") or {},
            )
        except ValueError as exc:
            return _emit_error(str(exc), as_json)
        emit(matches, as_json)
        return 0

    if args.command == "related-assets":
        depth = _parse_bounded_int(args.depth, minimum=1, maximum=2)
        if depth is None:
            return _emit_error("DEPTH_OUT_OF_RANGE", as_json, asset_id=args.asset_id)
        limit = _parse_bounded_int(args.limit, minimum=1, maximum=50)
        if limit is None:
            return _emit_error("LIMIT_OUT_OF_RANGE", as_json, asset_id=args.asset_id)
        try:
            payload = related_catalog_assets(
                snapshot.assets,
                args.asset_id,
                depth=depth,
                direction=args.direction,
                relations=args.relations,
                limit=limit,
            )
        except CatalogDiscoveryError as exc:
            return _emit_error(str(exc), as_json, asset_id=args.asset_id)
        emit(payload, as_json)
        return 0

    return _emit_error("COMMAND_NOT_IMPLEMENTED", as_json, command=args.command)


if __name__ == "__main__":
    raise SystemExit(main())
