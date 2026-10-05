"""Optional derived, hash-authenticated identity lookup for ResearchStore.

Canonical manifests and Parquet remain the sole research truth. Preparation is
explicit; no cold-start rebuild. A small pending receipt fences visibility.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

RELATIVE = "research/write_lookup_v1"
MAX_LEAF = 16
MAX_NODE_BYTES = 65536
HASH = re.compile(r"^[0-9a-f]{64}$")


class WriteLookupError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class WriteLookup:
    def __init__(self, root: Path, safe_path: Callable[..., Path]) -> None:
        self.root, self.safe_path = root, safe_path
        self.state: dict[str, Any] | None = None
        self.nodes: dict[str, dict] = {}  # only this operation; not cold-start authority

    def path(self, name: str, *, create: bool = False) -> Path:
        return self.safe_path(self.root, f"{RELATIVE}/{name}", create_parents=create)

    def exists(self) -> bool:
        return (self.root / RELATIVE).exists()

    def stamp(self) -> list[int] | None:
        directory = self.root / "research/manifests/partitions"
        if not directory.exists():
            return None
        if directory.is_symlink() or not directory.is_dir():
            raise WriteLookupError("WRITE_LOOKUP_SOURCE_UNSAFE")
        value = directory.stat()
        return [value.st_dev, value.st_ino, value.st_mtime_ns, value.st_ctime_ns]

    def _read(self, name: str) -> dict:
        try:
            path = self.path(name)
            if path.stat().st_size > MAX_NODE_BYTES:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            raw = path.read_bytes()
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (OSError, ValueError) as exc:
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT") from exc

    def _atomic(self, name: str, value: dict) -> None:
        path = self.path(name, create=True)
        temporary = self.path(name + ".tmp", create=True)
        raw = canonical(value)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            fd = os.open(temporary, flags, 0o644)
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            # Files and directory entries durable before manifest publication.
            if os.name != "nt":
                fd_dir = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd_dir)
                finally:
                    os.close(fd_dir)
        except OSError as exc:
            raise WriteLookupError("WRITE_LOOKUP_WRITE_FAILED") from exc

    def _signed(self, value: dict) -> dict:
        return {**value, "sha256": digest(canonical(value))}

    def _verify_signed(self, value: dict) -> dict:
        body = {key: item for key, item in value.items() if key != "sha256"}
        try:
            expected = digest(canonical(body))
        except (TypeError, ValueError) as exc:
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT") from exc
        if value.get("sha256") != expected:
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        return body

    def _node(self, sha: str | None) -> dict:
        if sha is None:
            return {"leaf": {}}
        if not isinstance(sha, str) or not HASH.fullmatch(sha):
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        if sha not in self.nodes:
            value = self._read(f"nodes/{sha[:2]}/{sha}.json")
            try:
                valid_hash = digest(canonical(value)) == sha
            except (TypeError, ValueError) as exc:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT") from exc
            if not valid_hash or set(value) not in ({"leaf"}, {"children"}):
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            mapping = value.get("leaf", value.get("children"))
            if not isinstance(mapping, dict):
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            if "children" in value and any(
                not isinstance(key, str) or len(key) != 1 or key not in "0123456789abcdef"
                or not isinstance(child, str) or not HASH.fullmatch(child)
                for key, child in mapping.items()):
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            if "leaf" in value and (len(mapping) > MAX_LEAF
                    or any(not isinstance(item, dict) for item in mapping.values())):
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            if "leaf" in value:
                for item in mapping.values():
                    if set(item) == {"root"}:
                        self._hash_or_none(item["root"])
                    elif set(item) == {"manifest_id", "transaction_id"}:
                        if any(not isinstance(part, str) or not part or "/" in part
                               or "\\" in part or part in {".", ".."} for part in item.values()):
                            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
                    else:
                        raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            self.nodes[sha] = value
        return self.nodes[sha]

    def _save_node(self, node: dict) -> str:
        raw = canonical(node)
        if len(raw) > MAX_NODE_BYTES:
            raise WriteLookupError("WRITE_LOOKUP_NODE_LIMIT")
        sha = digest(raw)
        path = self.path(f"nodes/{sha[:2]}/{sha}.json", create=True)
        if path.exists():
            if path.read_bytes() != raw:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        else:
            self._atomic(f"nodes/{sha[:2]}/{sha}.json", node)
        self.nodes[sha] = node
        return sha

    def get(self, tree: str, key: str) -> dict | None:
        assert self.state is not None
        sha, hashed, depth = self.state[tree], digest(key.encode()), 0
        while True:
            node = self._node(sha)
            if "leaf" in node:
                value = node["leaf"].get(key)
                if value is not None:
                    expected = {"root"} if tree == "states" else {"manifest_id", "transaction_id"}
                    if set(value) != expected:
                        raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
                return value
            if depth >= 64:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            sha = node["children"].get(hashed[depth])
            depth += 1

    def _insert(self, sha: str | None, key: str, value: dict, depth: int = 0, *, replace: bool = False) -> str:
        node = self._node(sha)
        if "leaf" in node:
            leaf = dict(node["leaf"])
            if key in leaf and leaf[key] != value and not replace:
                raise WriteLookupError("WRITE_LOOKUP_IDENTITY_CONFLICT")
            leaf[key] = value
            if len(leaf) <= MAX_LEAF:
                return self._save_node({"leaf": leaf})
            if depth >= 64:
                raise WriteLookupError("WRITE_LOOKUP_HASH_COLLISION")
            groups: dict[str, dict] = {}
            for item, payload in leaf.items():
                groups.setdefault(digest(item.encode())[depth], {})[item] = payload
            children = {}
            for slot, entries in groups.items():
                child = None
                for item, payload in sorted(entries.items()):
                    child = self._insert(child, item, payload, depth + 1)
                children[slot] = child
            return self._save_node({"children": children})
        if depth >= 64:
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        children = dict(node["children"])
        slot = digest(key.encode())[depth]
        children[slot] = self._insert(children.get(slot), key, value, depth + 1, replace=replace)
        return self._save_node({"children": children})

    def initialize(self) -> None:
        self.state = {"schema": "smial.research-write-lookup", "version": "1.0",
                      "transactions": None, "records": None, "states": None,
                      "source_stamp": self.stamp()}

    def build_tree(self, entries: dict[str, dict], depth: int = 0) -> str | None:
        """Explicit preparation writes only final nodes, not N obsolete versions."""
        if not entries:
            return None
        if len(entries) <= MAX_LEAF:
            return self._save_node({"leaf": entries})
        if depth >= 64:
            raise WriteLookupError("WRITE_LOOKUP_HASH_COLLISION")
        groups: dict[str, dict] = {}
        for key, pointer in entries.items():
            groups.setdefault(digest(key.encode())[depth], {})[key] = pointer
        return self._save_node({"children": {
            slot: self.build_tree(group, depth + 1) for slot, group in sorted(groups.items())}})

    def add(self, manifest: Any, records: Any) -> None:
        assert self.state is not None
        pointer = {"manifest_id": manifest.partition_manifest_id,
                   "transaction_id": manifest.partition_id}
        self.state["transactions"] = self._insert(
            self.state["transactions"], manifest.partition_id, pointer)
        for record in records:
            if self.get("records", record.record_id) is not None:
                raise WriteLookupError("DUPLICATE_RECORD_ID")
            self.state["records"] = self._insert(self.state["records"], record.record_id, pointer)
            if str(record.record_kind) == "OBSERVATION_SCHEDULE_STATE":
                group = self.get("states", record.entity_id) or {"root": None}
                group = {"root": self._insert(group["root"], record.record_id, pointer)}
                self.state["states"] = self._insert(
                    self.state["states"], record.entity_id, group, replace=True)

    def state_pointers(self, entity_id: str) -> list[dict]:
        group = self.get("states", entity_id)
        if group is None:
            return []
        result = []
        def visit(sha, depth=0):
            if depth > 64:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            node = self._node(sha)
            if "leaf" in node:
                if any(set(pointer) != {"manifest_id", "transaction_id"} for pointer in node["leaf"].values()):
                    raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
                result.extend(node["leaf"].values())
            else:
                for child in node["children"].values():
                    visit(child, depth + 1)
        visit(group["root"])
        return result

    def save(self) -> None:
        assert self.state is not None
        self.state["source_stamp"] = self.stamp()
        self._atomic("state.json", self._signed(self.state))

    def begin(self, manifest: Any, records: Any) -> None:
        assert self.state is not None
        previous = dict(self.state)
        self.add(manifest, records)
        manifest_rel = f"research/manifests/partitions/{manifest.partition_manifest_id}.json"
        # A pending journal precedes canonical visibility, and names one exact
        # transaction. Losing any indexed node cannot turn into false absence.
        self._atomic("pending.json", self._signed({
            "previous": previous, "next": self.state, "manifest_rel": manifest_rel,
            "manifest_id": manifest.partition_manifest_id,
            "transaction_id": manifest.partition_id,
        }))

    def finish(self) -> None:
        self._validate_state(self.state)
        self.save()
        try:
            self.path("pending.json").unlink(missing_ok=True)
        except OSError as exc:
            raise WriteLookupError("WRITE_LOOKUP_WRITE_FAILED") from exc

    @staticmethod
    def _hash_or_none(value: Any) -> None:
        if value is not None and (not isinstance(value, str) or not HASH.fullmatch(value)):
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")

    def _validate_state(self, value: Any) -> None:
        if (not isinstance(value, dict)
                or set(value) != {"schema", "version", "transactions", "records", "states", "source_stamp"}
                or value["schema"] != "smial.research-write-lookup" or value["version"] != "1.0"):
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        stamp = value["source_stamp"]
        if stamp is not None and (not isinstance(stamp, list) or len(stamp) != 4
                                 or any(type(part) is not int for part in stamp)):
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        for tree in ("transactions", "records", "states"):
            self._hash_or_none(value[tree])
            self._node(value[tree])

    def _validate_pending(self, value: dict) -> None:
        required = {"previous", "next", "manifest_rel", "manifest_id", "transaction_id"}
        if not required <= set(value) or set(value) - required - {"published_stamp"}:
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        for field in ("manifest_id", "transaction_id"):
            part = value[field]
            if not isinstance(part, str) or not part or "/" in part or "\\" in part or part in {".", ".."}:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        if value["manifest_rel"] != f"research/manifests/partitions/{value['manifest_id']}.json":
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
        self._validate_state(value["previous"])
        self._validate_state(value["next"])
        if "published_stamp" in value and (not isinstance(value["published_stamp"], list)
                or len(value["published_stamp"]) != 4
                or any(type(part) is not int for part in value["published_stamp"])):
            raise WriteLookupError("WRITE_LOOKUP_CORRUPT")

    def published(self) -> None:
        pending = self._verify_signed(self._read("pending.json"))
        pending["published_stamp"] = self.stamp()
        self._atomic("pending.json", self._signed(pending))

    def load(self, *, recover: Callable[[dict], str] | None = None) -> None:
        pending_path = self.root / RELATIVE / "pending.json"
        if pending_path.exists():
            if recover is None:
                raise WriteLookupError("WRITE_LOOKUP_PENDING")
            pending = self._verify_signed(self._read("pending.json"))
            self._validate_pending(pending)
            recovered = recover(pending)
            if recovered not in {"previous", "next"}:
                raise WriteLookupError("WRITE_LOOKUP_CORRUPT")
            self.state = pending[recovered]
            self.finish()
        else:
            self.state = self._verify_signed(self._read("state.json"))
        self._validate_state(self.state)
        if self.state.get("source_stamp") != self.stamp():
            raise WriteLookupError("WRITE_LOOKUP_STALE_PREPARATION_REQUIRED")
