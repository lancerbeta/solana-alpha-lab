#!/usr/bin/env python3
"""Read-only stable-ID resolver for the SMIAL Project Asset Catalog."""

from __future__ import annotations

import argparse
import json

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

    record = snapshot.queries.get(args.recipe_id)
    if record is None:
        print(f"QUERY_NOT_FOUND: {args.recipe_id}")
        return 2
    emit(record, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
