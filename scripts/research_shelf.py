#!/usr/bin/env python3
"""Полка исследований: подготовка записи и проверка отдельного локального Git-хранилища.

Metadata operations stay separate from native execution. Git writes still use
local remotes only until production commissioning is accepted.
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
from solana_alpha_lab.factory.research_shelf_git import ShelfGit, ScopedShelfGit
from solana_alpha_lab.factory import research_shelf_context as context


def _input(path: Path | None) -> bytes:
    shelf.require(path is not None, "INPUT_REQUIRED")
    with path.open("rb") as stream:
        raw = stream.read(shelf.MAX_REVISION_BYTES + 1)
    shelf.require(len(raw) <= shelf.MAX_REVISION_BYTES, "REVISION_SIZE_LIMIT")
    return raw


def _store(path: Path | None):
    if path is None:
        return None
    from solana_alpha_lab.factory.research_store import ExistingResearchStoreReader
    return ExistingResearchStoreReader(path)


def _sources(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(_input(path))
    shelf.require(isinstance(payload, list), "SOURCE_BUNDLE_INVALID")
    return {shelf.canonical(row["source"]).decode("utf-8"): row for row in payload}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init-local", "init-scoped", "capture", "prepare", "validate", "apply", "refresh", "review", "show", "revise", "reconcile", "resolve", "find", "link", "adoption-key", "public-check"])
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--remote", type=Path, help="Существующий локальный bare remote; сеть пока не подключена")
    parser.add_argument("--remote-url", help="Только существующий GitHub transport SMIAL для принятого metadata scope")
    parser.add_argument("--metadata-scope", type=Path, help="Exact owner scope после принятого code/policy на main; не из shelf item")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, help="Новый файл подготовленной ревизии; существующий файл не перезаписывается")
    parser.add_argument("--commit", help="Точный 40-hex commit snapshot; read не выполняет fetch")
    parser.add_argument("--item")
    parser.add_argument("--revision", help="Точный hash исторической ревизии для show")
    parser.add_argument("--snapshot", type=Path, help="Pinned export с доказательством проверки data head; без fetch")
    parser.add_argument("--data-root", type=Path, help="Read-only native source, только для отдельной metadata operation")
    parser.add_argument("--source-bundle", type=Path, help="Exact saved Scout source bytes/ref, только из разрешённого контекста")
    parser.add_argument("--strategy", type=Path, help="Exact StrategyVersion для resolve; без поиска latest PROMOTE")
    parser.add_argument("--request-id", help="Stable pre-call identity; native ID в ключ не входит")
    parser.add_argument("--public", action="store_true", help="Проверить весь outgoing public payload перед apply/выводом dossier")
    parser.add_argument("--disclosure", type=Path, help="Owner-reviewed hash минимального public payload для private origin")
    parser.add_argument("--mutation-id")
    parser.add_argument("--now", default=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action in {"adoption-key", "public-check"}:
            if args.action == "adoption-key":
                from solana_alpha_lab.factory.research_shelf_native import adoption_key
                shelf.require(args.item and args.revision and args.request_id, "ADOPTION_IDENTITY_REQUIRED")
                result = dict(adoption_key=adoption_key(args.item, args.revision, owner="SMIAL", route="HFIC", request_id=args.request_id),
                              native_created=False)
            else:
                payload = json.loads(_input(args.input))
                context.public_payload_guard(payload, disclosure=json.loads(_input(args.disclosure)) if args.disclosure else None)
                result = dict(status="PUBLIC_PAYLOAD_REVIEW_BOUND", payload_sha256=shelf.sha256(shelf.canonical(payload)))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
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
            shelf.require(args.cache is not None or (args.snapshot is not None and args.action in {"review", "resolve", "find", "link"}), "CACHE_REQUIRED")
            if args.action == "init-local":
                shelf.require(args.remote is not None, "LOCAL_REMOTE_REQUIRED")
                ShelfGit.init_local(args.cache, args.remote)
                print(json.dumps(dict(status="LOCAL_CACHE_INITIALIZED", production_commissioned=False)))
                return 0
            if args.action == "init-scoped":
                shelf.require(args.metadata_scope and args.remote_url, "EXACT_METADATA_SCOPE_REQUIRED")
                ScopedShelfGit.init_scoped(args.cache, remote=args.remote_url, scope=json.loads(_input(args.metadata_scope)))
                print(json.dumps(dict(status="SCOPED_CACHE_INITIALIZED", data_branch_created=False)))
                return 0
            git = (ScopedShelfGit(args.cache, scope=json.loads(_input(args.metadata_scope))) if args.metadata_scope else ShelfGit(args.cache)) if args.cache else None
            if args.action == "apply":
                raw = _input(args.input)
                body = shelf.decode(raw)
                if args.public:
                    context.public_payload_guard(body, disclosure=json.loads(_input(args.disclosure)) if args.disclosure else None)
                approval = ({shelf.sha256(shelf.canonical(body)): json.loads(_input(args.disclosure))} if args.disclosure else {})
                options = dict(disclosures=approval) if isinstance(git, ScopedShelfGit) else {}
                result = git.publish({shelf.revision_path(body): raw}, expected_heads={body["item_id"]: body["parents"]}, **options)
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 0 if result["status"] in {"PUBLISHED", "ALREADY_PUBLISHED"} else 2
            if args.action == "refresh":
                result = git.refresh()
                if args.output:
                    from solana_alpha_lab.factory.research_shelf_native import read_events
                    events = read_events(result, now=args.now, store=_store(args.data_root), saved_sources=_sources(args.source_bundle))
                    context.write_snapshot(args.output, context.export_snapshot(result, event_states=events))
                print(json.dumps({k: v for k, v in result.items() if k not in {"files", "items"}}, sort_keys=True))
                return 0 if result["status"] == "READY" else 2
            if args.snapshot is not None:
                snapshot = context.load_snapshot(args.snapshot, now=args.now)
            else:
                shelf.require(args.commit is not None, "EXACT_COMMIT_REQUIRED")
                snapshot = git.read(args.commit)
            if args.action == "review":
                events = snapshot.get("event_states", {})
                if args.data_root or args.source_bundle:
                    from solana_alpha_lab.factory.research_shelf_native import read_events
                    events = read_events(snapshot, now=args.now, store=_store(args.data_root), saved_sources=_sources(args.source_bundle))
                print(json.dumps(shelf.attention(snapshot, now=args.now, limit=None if args.all else 5, source_states=events),
                                 ensure_ascii=False, sort_keys=True))
                return 0 if snapshot["complete"] else 2
            if args.action in {"resolve", "find", "link"}:
                from solana_alpha_lab.factory import research_shelf_native as native
                def git_read(ref):
                    shelf.require(git is not None, "ADOPTED_COMMIT_READBACK_REQUIRED")
                    return git.read(ref["commit"])["files"][ref["path"]]
                if args.action == "find":
                    result = native.find_native(snapshot, json.loads(_input(args.input)))
                elif args.action == "resolve":
                    if args.strategy:
                        import yaml
                        strategy = yaml.safe_load(args.strategy.read_bytes())
                        result = native.resolve_strategy(snapshot, strategy, store=_store(args.data_root), root=ROOT, git_read=git_read)
                    elif args.input:
                        result = native.native_dossier(_store(args.data_root), json.loads(_input(args.input)))
                    else:
                        shelf.require(args.item, "ITEM_REQUIRED")
                        result = native.resolve_item(snapshot, args.item, git_read=git_read)
                else:
                    shelf.require(args.item and args.revision and args.mutation_id and args.request_id, "LINK_IDENTITY_REQUIRED")
                    result = native.prepare_link(snapshot, args.item, args.revision, store=_store(args.data_root),
                        identity=json.loads(_input(args.input)), request_id=args.request_id, now=args.now, mutation_id=args.mutation_id)
                    if result["prepared"] is not None:
                        shelf.require(args.output is not None, "OUTPUT_REQUIRED")
                        with args.output.open("xb") as stream:
                            stream.write(result.pop("prepared"))
                    else:
                        result.pop("prepared")
                if args.public:
                    linked_ids = {row["item_id"] for row in result.get("matches", [])}
                    linked_ids.update(i for i in (args.item, (result.get("shelf") or {}).get("item_id")) if i)
                    for ref in result.get("candidate_record_refs", []):
                        linked_ids.update(row["item_id"] for row in native.find_native(snapshot, ref)["matches"])
                    context.public_payload_guard(result, disclosure=json.loads(_input(args.disclosure)) if args.disclosure else None,
                        known_private_origin=any(context.historically_private(snapshot, item) for item in linked_ids))
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 0 if result["status"] not in {"UNRESOLVED", "INCOMPLETE", "AMBIGUOUS_SOURCE_LINK", "LINK_PENDING", "UNAVAILABLE", "NOT_INITIALIZED"} else 2
            shelf.require(args.item is not None, "ITEM_REQUIRED")
            if args.action == "show":
                shelf.require(args.item in snapshot["items"], "ITEM_NOT_FOUND")
                item = snapshot["items"][args.item]
                if args.revision is not None:
                    shelf.require(args.revision in item["revisions"], "REVISION_NOT_FOUND")
                    print(json.dumps(dict(commit=snapshot["commit"], item_id=args.item,
                        source_freshness=snapshot["source_freshness"], complete=snapshot["complete"],
                        revision=item["revisions"][args.revision]), ensure_ascii=False, sort_keys=True))
                    return 0 if snapshot["complete"] else 2
                print(json.dumps(dict(commit=snapshot["commit"], item_id=args.item,
                    source_freshness=snapshot["source_freshness"], complete=snapshot["complete"],
                    competing_revisions={head: item["revisions"][head] for head in item["heads"]}
                        if item["status"] == "ITEM_CONFLICT" else {},
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
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        # Do not leak source bytes, machine paths or Git/provider exception text.
        print(json.dumps(dict(status="UNAVAILABLE", reason="INPUT_OR_STORAGE_UNAVAILABLE")))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
