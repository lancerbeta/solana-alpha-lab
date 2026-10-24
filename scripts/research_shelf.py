#!/usr/bin/env python3
"""Полка исследований: подготовка записи и проверка отдельного локального Git-хранилища.

Stage 1: local remotes only. Production/cloud commissioning, native adapters and
Forge entry integration are not enabled by this CLI.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import research_shelf as shelf
from solana_alpha_lab.factory.research_shelf_git import ShelfGit


def _input(path: Path | None) -> bytes:
    shelf.require(path is not None, "INPUT_REQUIRED")
    with path.open("rb") as stream:
        raw = stream.read(shelf.MAX_REVISION_BYTES + 1)
    shelf.require(len(raw) <= shelf.MAX_REVISION_BYTES, "REVISION_SIZE_LIMIT")
    return raw


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init-local", "capture", "prepare", "validate", "apply", "refresh", "review", "show", "revise", "reconcile"])
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--remote", type=Path, help="Существующий локальный bare remote; сеть пока не подключена")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, help="Новый файл подготовленной ревизии; существующий файл не перезаписывается")
    parser.add_argument("--commit", help="Точный 40-hex commit snapshot; read не выполняет fetch")
    parser.add_argument("--item")
    parser.add_argument("--mutation-id")
    parser.add_argument("--now", default=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action in {"capture", "prepare"}:
            request = json.loads(_input(args.input))
            if args.action == "capture":
                shelf.require(isinstance(request, dict) and set(request) <= {"title", "statement", "product", "origin_key"}
                              and {"title", "statement"} <= set(request), "CAPTURE_FIELDS_INVALID")
                raw = shelf.capture(product=request.get("product", "SMIAL"), title=request["title"],
                    statement=request["statement"], origin_key=request.get("origin_key"), now=args.now)
            else:
                shelf.require(isinstance(request, dict), "WIRE_JSON_INVALID")
                raw = shelf.prepare(request)
        elif args.action == "validate":
            body = shelf.decode(_input(args.input))
            print(json.dumps(dict(status="VALID", item_id=body["item_id"], revision_sha256=body["revision_sha256"])))
            return 0
        else:
            shelf.require(args.cache is not None, "CACHE_REQUIRED")
            if args.action == "init-local":
                shelf.require(args.remote is not None, "LOCAL_REMOTE_REQUIRED")
                ShelfGit.init_local(args.cache, args.remote)
                print(json.dumps(dict(status="LOCAL_CACHE_INITIALIZED", production_commissioned=False)))
                return 0
            git = ShelfGit(args.cache)
            if args.action == "apply":
                raw = _input(args.input)
                body = shelf.decode(raw)
                result = git.publish({shelf.revision_path(body): raw}, expected_heads={body["item_id"]: body["parents"]})
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 0 if result["status"] in {"PUBLISHED", "ALREADY_PUBLISHED"} else 2
            if args.action == "refresh":
                result = git.refresh()
                print(json.dumps({k: v for k, v in result.items() if k not in {"files", "items"}}, sort_keys=True))
                return 0 if result["status"] == "READY" else 2
            shelf.require(args.commit is not None, "EXACT_COMMIT_REQUIRED")
            snapshot = git.read(args.commit)
            if args.action == "review":
                print(json.dumps(shelf.attention(snapshot, now=args.now, limit=None if args.all else 5),
                                 ensure_ascii=False, sort_keys=True))
                return 0 if snapshot["complete"] else 2
            shelf.require(args.item is not None, "ITEM_REQUIRED")
            if args.action == "show":
                shelf.require(args.item in snapshot["items"], "ITEM_NOT_FOUND")
                item = snapshot["items"][args.item]
                print(json.dumps(dict(commit=snapshot["commit"], item_id=args.item,
                    **{k: v for k, v in item.items() if k != "revisions"}), ensure_ascii=False, sort_keys=True))
                return 0 if snapshot["complete"] and item["status"] == "READY" else 2
            shelf.require(args.mutation_id is not None, "MUTATION_ID_REQUIRED")
            changes = json.loads(_input(args.input))
            shelf.require(isinstance(changes, dict), "CHANGES_OBJECT_REQUIRED")
            raw = shelf.revise(snapshot, args.item, changes, now=args.now, mutation_id=args.mutation_id,
                               reconcile=args.action == "reconcile")
        shelf.require(args.output is not None, "OUTPUT_REQUIRED")
        with args.output.open("xb") as stream:
            stream.write(raw)
        body = shelf.decode(raw)
        print(json.dumps(dict(status="PREPARED_LOCAL_ONLY", item_id=body["item_id"],
                              revision_sha256=body["revision_sha256"], saved_in_git=False), sort_keys=True))
        return 0
    except shelf.ShelfError as error:
        print(json.dumps(dict(status="REFUSED", reason=error.code, field=error.field), ensure_ascii=False))
    except FileExistsError:
        print(json.dumps(dict(status="REFUSED", reason="DRAFT_ALREADY_EXISTS")))
    except (OSError, ValueError, TypeError):
        # Do not leak source bytes, machine paths or Git/provider exception text.
        print(json.dumps(dict(status="UNAVAILABLE", reason="INPUT_OR_STORAGE_UNAVAILABLE")))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
