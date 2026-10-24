"""Isolated append-only Git plumbing, initially commissioned for local remotes only.

Algorithm reused from Scout lab_publish at d6e50ee1b0ad0dd2cd1063c999f4609b8744fa8f:
pinned parent, private index, immutable paths, non-force push. Shelf additionally
checks item heads/origin identity on every retry and reads back lost replies.
No code checkout, native state or data-branch executable is opened.
"""
from __future__ import annotations

import os
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from . import research_shelf as wire

BRANCH = "refs/heads/research-log"
CACHE_REF = "refs/shelf/snapshot"
HEX40 = re.compile(r"[0-9a-f]{40}")
MAX_SNAPSHOT_BYTES = 16_777_216
PUBLIC_REPOSITORY = "lancerbeta/solana-alpha-lab"
PUBLIC_ENDPOINTS = ("git@github.com:lancerbeta/solana-alpha-lab.git", "https://github.com/lancerbeta/solana-alpha-lab.git")


def _drive_type(anchor: str) -> int:
    import ctypes
    return ctypes.windll.kernel32.GetDriveTypeW(anchor)


def _local_form(path: Path) -> None:
    """Lexical and drive checks precede resolve/is_dir/Git, including UNC aliases."""
    raw = str(path).replace("\\", "/")
    wire.require(not raw.startswith("//"), "NETWORK_PATH_REFUSED")
    wire.require(not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", raw), "NETWORK_TRANSPORT_NOT_COMMISSIONED")
    if os.name == "nt":
        wire.require(_drive_type(path.absolute().anchor) in {2, 3, 5, 6}, "NETWORK_PATH_REFUSED")


def _local_path(path: Path) -> Path:
    _local_form(path)
    absolute = path.absolute()
    # Never query a child until every ancestor is known not to redirect I/O.
    for component in reversed((absolute, *absolute.parents)):
        wire.require(not component.is_symlink() and not component.is_junction(), "INDIRECT_PATH_REFUSED")
    resolved = path.resolve()
    _local_form(resolved)
    return resolved


class ShelfGit:
    """A bare metadata cache. Network publication needs the later accepted policy.

    Local-only scope is enforced for fetch AND push, including existing caches.
    This is a first-stage boundary, not an assertion of production commissioning.
    """

    def __init__(self, cache: Path):
        self.cache = _local_path(cache)
        wire.require(self.cache.is_dir(), "CACHE_NOT_INITIALIZED")
        wire.require(self._git("rev-parse", "--is-bare-repository").stdout.strip() == b"true", "BARE_CACHE_REQUIRED")

    @classmethod
    def init_local(cls, cache: Path, remote: Path) -> ShelfGit:
        # Validate BOTH forms before any filesystem call on either argument.
        _local_form(cache)
        _local_form(remote)
        cache, remote = _local_path(cache), _local_path(remote)
        wire.require(not cache.exists(), "CACHE_ALREADY_EXISTS")
        wire.require(remote.is_dir(), "LOCAL_REMOTE_REQUIRED")
        wire.require(not (cache == remote or remote in cache.parents or cache in remote.parents), "CACHE_REMOTE_OVERLAP")
        cls._run(None, "init", "--bare", "--quiet", str(cache))
        result = cls(cache)
        result._git("remote", "add", "origin", str(remote))
        result._local_remote()
        return result

    @staticmethod
    def _run(cache: Path | None, *args: str, data: bytes | None = None,
             env: Mapping[str, str] | None = None, check: bool = True):
        overrides = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")
        wire.require(not any(k in os.environ for k in overrides), "GIT_ENV_OVERRIDE_REFUSED")
        command = ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false",
                   "-c", "user.name=Research Shelf", "-c", "user.email=research-shelf@example.invalid"]
        if cache:
            command += ["-C", str(cache)]
        try:
            result = subprocess.run(command + list(args), input=data, capture_output=True,
                                    env=env, timeout=30)
        except subprocess.TimeoutExpired:
            raise wire.ShelfError("GIT_TIMEOUT", args[0]) from None
        except OSError:
            raise wire.ShelfError("GIT_UNAVAILABLE") from None
        wire.require(not check or result.returncode == 0, "GIT_OPERATION_FAILED", args[0])
        return result

    def _git(self, *args: str, **kwargs):
        return self._run(self.cache, *args, **kwargs)

    def _local_remote(self) -> Path:
        raw = self._git("remote", "get-url", "origin").stdout.decode("utf-8").strip()
        remote = Path(raw)
        _local_form(remote)
        remote = _local_path(remote)
        wire.require(remote.is_absolute() and remote.is_dir(), "NETWORK_TRANSPORT_NOT_COMMISSIONED")
        wire.require(remote != self.cache and remote not in self.cache.parents and self.cache not in remote.parents,
                     "CACHE_REMOTE_OVERLAP")
        wire.require(self._run(remote, "rev-parse", "--is-bare-repository").stdout.strip() == b"true", "BARE_REMOTE_REQUIRED")
        # Deny hidden push redirection even when the fetch URL is local.
        push = self._git("remote", "get-url", "--push", "--all", "origin").stdout.decode("utf-8").splitlines()
        wire.require(len(push) == 1 and _local_path(Path(push[0])) == remote, "PUSH_DESTINATION_MISMATCH")
        return remote

    def remote_head(self) -> str | None:
        remote = self._local_remote()
        result = self._git("ls-remote", "--heads", str(remote), BRANCH)
        rows = result.stdout.decode("ascii").splitlines()
        if not rows:
            return None
        wire.require(len(rows) == 1, "REMOTE_HEAD_INVALID")
        head, ref = rows[0].split("\t")
        wire.require(HEX40.fullmatch(head) and ref == BRANCH, "REMOTE_HEAD_INVALID")
        # Fetch only this ref into this separate bare repository. No code refs/index.
        self._git("fetch", "--quiet", "--no-tags", "--no-write-fetch-head", str(remote), BRANCH)
        # ls-remote/fetch can race; pin the advertised H, never a moving FETCH_HEAD.
        if self._git("cat-file", "-t", head, check=False).stdout.strip() != b"commit":
            raise wire.ShelfError("REMOTE_CHANGED_DURING_REFRESH")
        self._git("update-ref", CACHE_REF, head)
        return head

    def read(self, commit: str, *, max_bytes: int = MAX_SNAPSHOT_BYTES) -> dict[str, Any]:
        wire.require(isinstance(commit, str) and HEX40.fullmatch(commit), "EXACT_COMMIT_REQUIRED")
        wire.require(max_bytes > 0, "SNAPSHOT_LIMIT_INVALID")
        wire.require(self._git("cat-file", "-t", commit).stdout.strip() == b"commit", "EXACT_COMMIT_REQUIRED")
        listed = self._git("ls-tree", "-r", "-z", commit, "--", wire.PREFIX + "/")
        files, complete, used = {}, True, 0
        for entry in listed.stdout.split(b"\0"):
            if not entry:
                continue
            header, name = entry.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split()
            try:
                path = name.decode("utf-8")
            except UnicodeError:
                complete = False
                continue
            size = int(self._git("cat-file", "-s", oid).stdout)
            if used + size > max_bytes:
                complete = False
                continue
            used += size
            if mode != "100644" or kind != "blob" or size > wire.MAX_REVISION_BYTES:
                files[path] = b""  # Item is invalid; never follow a symlink/oversized blob.
            else:
                files[path] = self._git("cat-file", "blob", oid).stdout
        result = wire.fold(files, complete=complete)
        return dict(result, commit=commit, files=files, source_freshness="UNVERIFIED_PINNED", source_checked_at=None)

    def refresh(self) -> dict[str, Any]:
        """Fetch explicitly. Pure read(commit) never refreshes implicitly."""
        try:
            head = self.remote_head()
            if head is None:
                return dict(status="NOT_INITIALIZED", complete=False, items={}, commit=None)
            return dict(self.read(head), source_freshness="REMOTE_VERIFIED",
                        source_checked_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        except wire.ShelfError as error:
            cached = self._git("rev-parse", "--verify", CACHE_REF, check=False)
            if cached.returncode == 0:
                result = self.read(cached.stdout.decode().strip())
                return dict(result, status="STALE_AS_OF", source_freshness="STALE_AS_OF", complete=False, reason=error.code)
            return dict(status="UNAVAILABLE", complete=False, items={}, commit=None, reason=error.code)

    def _commit(self, parent: str | None, files: Mapping[str, bytes]) -> str:
        with tempfile.TemporaryDirectory(prefix="shelf-index-", dir=self.cache) as temporary:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
            if parent:
                self._git("read-tree", parent, env=env)
            else:
                self._git("read-tree", "--empty", env=env)
            for path, raw in sorted(files.items()):
                blob = self._git("hash-object", "-w", "--stdin", data=raw).stdout.decode().strip()
                self._git("update-index", "--add", "--cacheinfo", "100644", blob, path, env=env)
            tree = self._git("write-tree", env=env).stdout.decode().strip()
            args = ("commit-tree", tree, "-p", parent) if parent else ("commit-tree", tree)
            commit = self._git(*args, data=b"research: append shelf metadata\n").stdout.decode().strip()
        args = ("diff-tree", "--no-commit-id", "--name-only", "-r", parent, commit) if parent else (
            "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit)
        changed = self._git(*args).stdout.decode().splitlines()
        wire.require(set(changed) == set(files), "PUBLICATION_DIFF_SCOPE")
        return commit

    def _push(self, commit: str):
        remote = self._local_remote()
        return self._git("push", "--no-verify", str(remote), commit + ":" + BRANCH, check=False)

    def publish(self, files: Mapping[str, bytes], *, expected_heads: Mapping[str, list[str]],
                _check_snapshot: Callable[[dict], None] | None = None) -> dict[str, Any]:
        """Retry the same prepared batch at most three times; no last-writer-wins."""
        wire.require(bool(files) and sum(map(len, files.values())) <= wire.MAX_BATCH_BYTES, "BATCH_SIZE_LIMIT")
        prepared = {}
        for path, raw in files.items():
            body = wire.decode(raw)
            wire.require(path == wire.revision_path(body), "REVISION_PATH_MISMATCH")
            wire.require(body["item_id"] not in prepared, "ONE_REVISION_PER_ITEM_PER_BATCH")
            prepared[body["item_id"]] = body
        wire.require(set(expected_heads) == set(prepared), "EXPECTED_ITEM_HEADS_REQUIRED")
        for item, body in prepared.items():
            wire.require(expected_heads[item] == body["parents"], "EXPECTED_HEADS_PARENT_MISMATCH")
        for attempt in range(3):
            head = self.remote_head()
            snapshot = self.read(head) if head else dict(files={}, items={}, complete=True)
            existing = snapshot["files"]
            if all(existing.get(path) == raw for path, raw in files.items()):
                return dict(status="ALREADY_PUBLISHED", commit=head, retries=attempt)
            wire.require(snapshot["complete"], "INCOMPLETE")
            for item_id, body in prepared.items():
                if existing.get(wire.revision_path(body)) == files[wire.revision_path(body)]:
                    continue  # Historical exact retry remains valid after descendants.
                item = snapshot["items"].get(item_id)
                wire.require((item["heads"] if item else []) == expected_heads[item_id], "STALE_ITEM_REVISION")
                wire.require(item is None or (item["status"] == "READY" or
                    (item["status"] == "ITEM_CONFLICT" and not item["reasons"] and len(body["parents"]) > 1)), "ITEM_NOT_WRITABLE")
                for other_id, other in snapshot["items"].items():
                    if other_id != item_id and any(row["origin_key"] == body["origin_key"] and
                        row["product"] == body["product"] and body["origin_key"] is not None
                        for row in other["revisions"].values()):
                        raise wire.ShelfError("ORIGIN_ALREADY_EXISTS", other_id)
            prospective = wire.fold(existing | dict(files))
            wire.require(prospective["identity_scope_complete"], "IDENTITY_HISTORY_UNRESOLVED")
            wire.require(all(prospective["items"][i]["status"] == "READY" for i in prepared), "BATCH_LINEAGE_INVALID")
            if _check_snapshot is not None:
                _check_snapshot(snapshot)  # Exact fetched parent, on every retry, before writing objects.
            pending = {path: raw for path, raw in files.items() if path not in existing}
            wire.require(all(path not in existing or existing[path] == raw for path, raw in files.items()), "IMMUTABLE_CAPSULE_CONFLICT")
            commit = self._commit(head, pending)
            try:
                pushed = self._push(commit)
            except wire.ShelfError as error:
                if error.code != "GIT_TIMEOUT":
                    raise
                pushed = None
            try:
                actual = self.remote_head()
                landed = self.read(actual) if actual else dict(files={})
            except wire.ShelfError:
                return dict(status="PENDING_PUBLICATION", commit=None, retries=attempt,
                            prepared_revision_sha256=sorted(b["revision_sha256"] for b in prepared.values()))
            if all(landed["files"].get(path) == raw for path, raw in files.items()):
                return dict(status="PUBLISHED" if pushed is not None and pushed.returncode == 0 else "ALREADY_PUBLISHED",
                            commit=actual, retries=attempt)
            if actual == head:
                if pushed is None:
                    return dict(status="PENDING_PUBLICATION", commit=None, retries=attempt)
                raise wire.ShelfError("PUBLICATION_FAILED")
        return dict(status="PENDING_PUBLICATION", commit=None, retries=3)


class ScopedShelfGit(ShelfGit):
    """Same append algorithm for the accepted namespace, under explicit scope.

    A scope file is caller-supplied authorization evidence, never generated by
    a shelf item. Both namespace and policy bytes must exist on accepted main.
    This does not authorize a caller who lacks the owner's actual permission.
    """
    def __init__(self, cache: Path, *, scope: Mapping[str, Any]):
        self.scope = dict(scope)
        self._accepted_policy("READ")
        super().__init__(cache)
        wire.require(not self.cache.is_relative_to(wire.ROOT), "CACHE_MUST_BE_OUTSIDE_EXECUTION_CHECKOUT")

    @staticmethod
    def _scope_shape(scope: Mapping[str, Any], action: str) -> None:
        wire.require(isinstance(scope, dict) and scope.get("schema") == "smial.research-shelf-metadata-scope"
            and scope.get("schema_version") == "1.0", "EXACT_METADATA_SCOPE_REQUIRED")
        wire.require((scope.get("repository"), scope.get("branch"), scope.get("prefix")) ==
            (PUBLIC_REPOSITORY, "research-log", wire.PREFIX), "METADATA_SCOPE_NAMESPACE_MISMATCH")
        actions = scope.get("allowed_actions")
        wire.require(isinstance(actions, list) and set(actions) <= {"READ", "APPEND"} and action in actions,
                     "METADATA_SCOPE_ACTION_REFUSED")
        wire.require(isinstance(scope.get("owner_scope_ref"), str) and bool(scope["owner_scope_ref"]) and
            isinstance(scope.get("accepted_code_commit"), str) and HEX40.fullmatch(scope["accepted_code_commit"]) and
            isinstance(scope.get("accepted_policy_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", scope["accepted_policy_sha256"]),
            "METADATA_SCOPE_BINDING_REQUIRED")

    def _accepted_policy(self, action: str) -> None:
        self._scope_shape(self.scope, action)
        code = self.scope["accepted_code_commit"]
        # Read-only source checkout checks; no fetch, index/ref/config movement.
        accepted = self._run(wire.ROOT, "merge-base", "--is-ancestor", code, "refs/remotes/origin/main", check=False)
        wire.require(accepted.returncode == 0, "METADATA_CAPABILITY_NOT_ACCEPTED_ON_MAIN")
        raw = self._run(wire.ROOT, "show", code + ":configs/research_shelf_v1.json", check=False)
        wire.require(raw.returncode == 0 and wire.sha256(raw.stdout) == self.scope["accepted_policy_sha256"], "ACCEPTED_METADATA_POLICY_UNAVAILABLE")
        policy = json.loads(raw.stdout)
        wire.require((policy["repository"], policy["branch"], policy["prefix"], policy["metadata_scope_required"],
            policy["production_publication_enabled_by_default"]) == (PUBLIC_REPOSITORY, "research-log", wire.PREFIX, True, False),
            "ACCEPTED_METADATA_POLICY_MISMATCH")

    @classmethod
    def init_scoped(cls, cache: Path, *, remote: str, scope: Mapping[str, Any]) -> ScopedShelfGit:
        wire.require(remote in PUBLIC_ENDPOINTS, "PUBLIC_METADATA_ENDPOINT_REFUSED")
        probe = object.__new__(cls)
        probe.scope = dict(scope)
        probe._accepted_policy("READ")
        cache = _local_path(cache)
        wire.require(not cache.exists() and not cache.is_relative_to(wire.ROOT), "SEPARATE_NEW_CACHE_REQUIRED")
        cls._run(None, "init", "--bare", "--quiet", str(cache))
        cls._run(cache, "remote", "add", "origin", remote)
        return cls(cache, scope=scope)

    def _local_remote(self) -> str:
        # Override only the destination seam. The original local-only class and
        # immutable append/CAS/recovery algorithm are preserved unchanged.
        self._accepted_policy("READ")
        remote = self._git("remote", "get-url", "origin").stdout.decode("utf-8").strip()
        pushes = self._git("remote", "get-url", "--push", "--all", "origin").stdout.decode("utf-8").splitlines()
        wire.require(remote in PUBLIC_ENDPOINTS and pushes == [remote], "PUBLIC_METADATA_ENDPOINT_REFUSED")
        return remote

    def publish(self, files: Mapping[str, bytes], *, expected_heads: Mapping[str, list[str]],
                disclosures: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._accepted_policy("APPEND")
        from .research_shelf_context import historically_private, public_payload_guard
        disclosures = disclosures or {}
        bodies = []
        for raw in files.values():
            body = wire.decode(raw)
            wire.require(body["product"] == "SMIAL", "PUBLIC_PRODUCT_NAMESPACE_MISMATCH")
            digest = wire.sha256(wire.canonical(body))
            public_payload_guard(body, disclosure=disclosures.get(digest))
            bodies.append((body, digest))
        def check(snapshot):
            for body, digest in bodies:
                public_payload_guard(body, disclosure=disclosures.get(digest),
                    known_private_origin=historically_private(snapshot, body["item_id"]))
        return super().publish(files, expected_heads=expected_heads, _check_snapshot=check)
