"""Closed UTC-day ZIP_STORED archive + isolated hydration. No live Drive."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.members_snapshot_delta import (
    load_member_rows_for_location,
)
from solana_alpha_lab.factory.observation_schedule import canonical_sha256

ARCHIVE_KIND = "FACTORY_HOT90_CLOSED_DAY_ARCHIVE"


class Hot90ArchiveError(ValueError):
    """Typed closed-day archive failure."""


def confined_relative_file(
    root: Path, relative: str, *, error: type[Exception], code: str
) -> Path:
    text = str(relative).replace("\\", "/")
    if text.startswith("/") or text.startswith("\\") or "://" in text:
        raise error(code)
    segments = text.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise error(code)
    if any(token in text for token in ("*", "?", "[", "]")):
        raise error(code)
    if len(segments[0]) == 2 and segments[0][1] == ":":
        raise error(code)
    resolved_root = root.resolve()
    candidate = (root / text).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise error(code) from exc
    return candidate


def list_closed_day_relative_paths(source_root: Path, utc_day: str) -> list[str]:
    """Deterministic scientific inventory for one UTC day. Never uses mtime."""

    if len(utc_day) != 8 or utc_day.isdigit() is False:
        raise Hot90ArchiveError("UTC_DAY_INVALID")
    relatives: set[str] = set()
    members_root = source_root / "datasets" / "members_snapshot_plus_delta" / utc_day
    if members_root.is_dir():
        for path in members_root.rglob("*"):
            if path.is_file() and path.is_symlink() is False:
                relatives.add(path.relative_to(source_root).as_posix())
    unit_path = members_root / "unit.json"
    if unit_path.is_file():
        unit = json.loads(unit_path.read_text(encoding="utf-8"))
        for pub in unit.get("publications") or []:
            mid = str(pub.get("dataset_manifest_id") or "")
            rel = str(pub.get("rel") or "").replace("\\", "/")
            for extra in (
                rel,
                str(Path(rel).with_name("members.layout.json").as_posix()) if rel else "",
                f"datasets/parquet/{mid}/observations.parquet" if mid else "",
                f"datasets/parquet/{mid}/members.parquet" if mid else "",
                f"datasets/manifests/{mid}.json" if mid else "",
                f"datasets/manifests/{mid}.published" if mid else "",
            ):
                if extra:
                    candidate = source_root / extra
                    if candidate.is_file() and candidate.is_symlink() is False:
                        relatives.add(extra)
    iso = f"{utc_day[:4]}-{utc_day[4:6]}-{utc_day[6:]}"
    manifests_dir = source_root / "datasets" / "manifests"
    if manifests_dir.is_dir():
        for man in manifests_dir.glob("*.json"):
            try:
                payload = json.loads(man.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            pid = str(payload.get("partition_id") or "")
            if pid not in {f"utc-day-{utc_day}", f"utc-day-{iso}"}:
                continue
            rel = f"datasets/manifests/{man.name}"
            if (source_root / rel).is_file():
                relatives.add(rel)
            published = f"datasets/manifests/{man.stem}.published"
            if (source_root / published).is_file():
                relatives.add(published)
            loc = payload.get("logical_location")
            if isinstance(loc, str) and loc and (source_root / loc).is_file():
                relatives.add(loc.replace("\\", "/"))
    raw_root = source_root / "datasets" / "raw_evidence" / utc_day
    if raw_root.is_dir():
        for path in raw_root.rglob("*"):
            if path.is_file() and path.is_symlink() is False:
                relatives.add(path.relative_to(source_root).as_posix())
    if not relatives:
        raise Hot90ArchiveError("ARCHIVE_INVENTORY_EMPTY")
    return sorted(relatives)


def package_closed_day_archive(
    source_root: Path,
    *,
    utc_day: str,
    relative_paths: Sequence[str],
    dest_dir: Path,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f".archive-{os.getpid()}.zip"
    with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for relative in relative_paths:
            confined_relative_file(
                source_root, relative, error=Hot90ArchiveError, code="ARCHIVE_PATH_UNSAFE"
            )
            path = source_root / relative
            if path.is_file() is False:
                raise Hot90ArchiveError(f"ARCHIVE_SOURCE_MISSING:{relative}")
            payload = path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            info = zipfile.ZipInfo(filename=relative.replace("\\", "/"), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, payload)
            entries.append({"path": relative.replace("\\", "/"), "sha256": digest, "bytes": len(payload)})
        inventory_sha256 = canonical_sha256(entries)
        manifest = {
            "kind": ARCHIVE_KIND,
            "utc_day": utc_day,
            "inventory_sha256": inventory_sha256,
            "entries": entries,
        }
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        info = zipfile.ZipInfo(filename="ARCHIVE_MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, encoded)
    bundle_sha256 = hashlib.sha256(tmp.read_bytes()).hexdigest()
    dest = dest_dir / f"ARCHIVE_{bundle_sha256}.zip"
    if dest.is_file():
        tmp.unlink(missing_ok=True)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != bundle_sha256:
            raise Hot90ArchiveError("ARCHIVE_IDENTITY_CONFLICT")
    else:
        tmp.replace(dest)
    return {
        "path": dest,
        "filename": dest.name,
        "sha256": bundle_sha256,
        "utc_day": utc_day,
        "inventory_sha256": inventory_sha256,
        "entries": entries,
    }


def hydrate_closed_day_archive(
    archive_path: Path,
    *,
    isolated_data_root: Path,
    live_data_root: Path | None = None,
) -> dict[str, Any]:
    if isolated_data_root.resolve() == (live_data_root.resolve() if live_data_root else None):
        raise Hot90ArchiveError("HYDRATE_INTO_LIVE_FORBIDDEN")
    if live_data_root is not None and _is_relative_to(isolated_data_root, live_data_root):
        raise Hot90ArchiveError("HYDRATE_INTO_LIVE_FORBIDDEN")
    isolated_data_root.mkdir(parents=True, exist_ok=True)
    live_before = _tree_fingerprint(live_data_root) if live_data_root is not None else None
    with zipfile.ZipFile(archive_path) as archive:
        try:
            manifest = json.loads(archive.read("ARCHIVE_MANIFEST.json").decode("utf-8"))
        except KeyError as exc:
            raise Hot90ArchiveError("ARCHIVE_MANIFEST_MISSING") from exc
        if manifest.get("kind") != ARCHIVE_KIND:
            raise Hot90ArchiveError("ARCHIVE_KIND_INVALID")
        observed_entries = []
        for item in manifest.get("entries") or []:
            rel = str(item["path"])
            confined_relative_file(
                isolated_data_root, rel, error=Hot90ArchiveError, code="HYDRATE_PATH_ESCAPE"
            )
            payload = archive.read(rel)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != str(item.get("sha256") or "") or len(payload) != int(item.get("bytes") or -1):
                raise Hot90ArchiveError("ARCHIVE_ENTRY_HASH_MISMATCH")
            target = isolated_data_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            observed_entries.append({"path": rel, "sha256": digest, "bytes": len(payload)})
        if canonical_sha256(observed_entries) != str(manifest.get("inventory_sha256") or ""):
            raise Hot90ArchiveError("ARCHIVE_INVENTORY_MISMATCH")
    if live_before is not None and _tree_fingerprint(live_data_root) != live_before:
        raise Hot90ArchiveError("LIVE_FACTORY_TREE_MUTATED")
    return {
        "isolated_data_root": isolated_data_root,
        "inventory_sha256": manifest["inventory_sha256"],
        "entries": observed_entries,
        "live_unchanged": live_before is not None,
    }


def reconstruct_members_from_hydrated(
    isolated_data_root: Path,
    logical_location: str,
) -> list[dict[str, Any]]:
    return load_member_rows_for_location(isolated_data_root, logical_location)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _tree_fingerprint(root: Path | None) -> str:
    if root is None or root.exists() is False:
        return "ABSENT"
    items = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            items.append({"path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return canonical_sha256(items)
