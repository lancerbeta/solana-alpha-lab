#!/usr/bin/env python3
"""Read-only stable-ID resolver for the SMIAL Project Asset Catalog."""

from __future__ import annotations

import argparse
import json
from typing import Any

from validate_catalog import load_and_validate


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
) -> list[dict[str, Any]]:
    """Return deterministic, bounded metadata matches from the validated Catalog."""

    needle = text.strip().casefold()
    if not needle:
        raise ValueError("SEARCH_TEXT_REQUIRED")
    values: list[dict[str, Any]] = []
    for asset_id, record in assets.items():
        location = record.get("location", {})
        relation_ids = [item.get("target_asset_id", "") for item in record.get("relations", [])]
        evidence_ids = [item.get("evidence_id", "") for item in record.get("evidence", [])]
        searchable = " ".join(
            [
                asset_id,
                str(record.get("purpose", "")),
                str(location.get("logical_uri", "")),
                str(location.get("repository_path", "")),
                " ".join(str(item) for item in record.get("consumers", [])),
                " ".join(str(item) for item in relation_ids),
                " ".join(str(item) for item in evidence_ids),
                " ".join(str(item) for item in record.get("search_terms", [])),
            ]
        ).casefold()
        searchable = f"{searchable} {searchable.replace('-', ' ')}"
        if needle not in searchable:
            continue
        if asset_type is not None and record.get("asset_type") != asset_type:
            continue
        if consumer is not None and consumer not in record.get("consumers", []):
            continue
        if status is not None and record.get("status") != status:
            continue
        values.append(
            {
                "asset_id": asset_id,
                "asset_type": record.get("asset_type"),
                "status": record.get("status"),
                "purpose": record.get("purpose"),
                "location": location,
                "consumers": record.get("consumers", []),
                "relations": record.get("relations", []),
                "evidence": record.get("evidence", []),
                "search_terms": record.get("search_terms", []),
            }
        )
    return sorted(values, key=lambda item: item["asset_id"])


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

    search = sub.add_parser("search-assets")
    search.add_argument("--text", required=True)
    search.add_argument("--asset-type")
    search.add_argument("--consumer")
    search.add_argument("--status")
    search.add_argument("--json", action="store_true")

    args = parser.parse_args()
    snapshot = load_and_validate()

    if args.command == "list-assets":
        values = sorted(snapshot.assets)
        emit(values, args.json)
        return 0

    if args.command == "resolve-asset":
        record = snapshot.assets.get(args.asset_id)
        if record is None:
            print(f"ASSET_NOT_FOUND: {args.asset_id}")
            return 2
        emit(record, args.json)
        return 0

    if args.command == "search-assets":
        try:
            matches = search_assets(
                snapshot.assets,
                args.text,
                asset_type=args.asset_type,
                consumer=args.consumer,
                status=args.status,
            )
        except ValueError as exc:
            print(str(exc))
            return 2
        emit(matches, args.json)
        return 0

    record = snapshot.queries.get(args.recipe_id)
    if record is None:
        print(f"QUERY_NOT_FOUND: {args.recipe_id}")
        return 2
    emit(record, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
