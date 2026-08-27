"""Hash-verified offline importer for the 2026-08-24 valuation-window panel.

Explicit source only. No provider/API/RPC/WSS. Raw bodies stay outside Git.
X is R0-only. Dataset role is DISCOVERY_ONLY_SECOND_LOOK.
Publication is fail-closed: process-owned staging, then one commit-point.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.early_market_panel_field_semantics import (
    FEATURE_ID,
    FIELD_SEMANTICS_UNPROVEN,
    FieldSemanticsError,
    classify_r0_mix,
    prove_r0_taker_volume_mix_semantics,
)
from solana_alpha_lab.factory.data_root import DEFAULT_DATA_PLANE_RELATIVE
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes

DATASET_MANIFEST_ID = "DATASET-MANIFEST-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
DATASET_ID = "DATASET-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
PARTITION_ID = "PARTITION-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
PARTITION_MANIFEST_ID = "PARTITION-MANIFEST-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
SCHEMA_ID = "SCHEMA-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
CAPTURE_ATOM_ID = "EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1"
R0_OBSERVATION_ID = "DISCOVERY:SEARCH_R0"
REQUIRED_LABELS = {
    "evidence_role": "DISCOVERY_ONLY_SECOND_LOOK",
    "outcome_previously_consumed": True,
    "confirmatory_reuse_forbidden": True,
    "provider_calls_for_bind": 0,
}
FORBIDDEN_HYPOTHESIS_ID = "HYP-EARLY-TAKER-VOLUME-MIX-H900-V1"
CLOSED_FAMILY = "CLOSE_VALUATION_LIQUIDITY_DIVERGENCE_FAMILY"
GIT_RECEIPT_RELATIVE = (
    "docs/evidence/early_valuation_liquidity_divergence_confirmation/"
    "a1_runtime_receipt_v1.json"
)
GIT_RECEIPT_SHA256 = "a8c8df4a7c02a8e6cf4d2be2fe004f2cfbff170efcf5645064788ea20f12db63"
PANEL_CREATED_AT = datetime(2026, 8, 24, 0, 24, 22, tzinfo=UTC)
AVAILABILITY_WINDOW_START = datetime(2026, 8, 24, 0, 0, 0, tzinfo=UTC)
AVAILABILITY_WINDOW_END = datetime(2026, 8, 24, 23, 59, 59, tzinfo=UTC)
RECEIPT_OBSERVED_AT_RELATION = "EQUALS_ENVELOPE_OBSERVED_AT"
MIN_USABLE_YIELD_ELIGIBLE = 10
SAMPLE_VALID = "SAMPLE_VALID"
SAMPLE_INVALID = "SAMPLE_INVALID"
LOGICAL_LOCATION = (
    "datasets/partitions/date=2026-08-24/"
    f"{PARTITION_ID}.parquet"
)
LABELS_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.labels.json"
MANIFEST_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.json"
PARTITION_RELATIVE = f"datasets/manifests/partitions/{PARTITION_MANIFEST_ID}.json"
PUBLISHED_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.published"
CANONICAL_TARGET_RELATIVES = (
    MANIFEST_RELATIVE,
    LABELS_RELATIVE,
    PARTITION_RELATIVE,
    LOGICAL_LOCATION,
    PUBLISHED_RELATIVE,
)
COMMIT_POINT_KIND = "EARLY_MARKET_PANEL_PUBLICATION_V1"


class EarlyMarketPanelImportError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EarlyMarketPanelImportError(code)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _schema_sha256() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "columns": [
                    {"name": "mint", "type": "string"},
                    {"name": "observed_at", "type": "timestamp[us, tz=UTC]"},
                    {"name": "available_to_strategy_at", "type": "timestamp[us, tz=UTC]"},
                    {"name": "r0_taker_volume_mix", "type": "float64"},
                    {"name": "missingness_code", "type": "string"},
                    {"name": "buy_volume_present", "type": "bool"},
                    {"name": "sell_volume_present", "type": "bool"},
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def is_link_path(path: Path) -> bool:
    return _is_link(path)


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse)


def _is_filesystem_root(path: Path) -> bool:
    resolved = path.resolve()
    return resolved.parent == resolved


def _is_broad_unsafe_target(path: Path) -> bool:
    resolved = path.resolve()
    if _is_filesystem_root(resolved) or _is_filesystem_root(resolved.parent):
        return True
    try:
        home = Path.home().resolve()
    except OSError:
        home = None
    return home is not None and resolved == home


def _paths_overlap(left: Path, right: Path) -> bool:
    left_parts = left.resolve().parts
    right_parts = right.resolve().parts
    if left_parts == right_parts:
        return True
    shorter, longer = (
        (left_parts, right_parts)
        if len(left_parts) <= len(right_parts)
        else (right_parts, left_parts)
    )
    return longer[: len(shorter)] == shorter


def _git_root_of(path: Path) -> Path | None:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


GitRunner = Callable[[Path, list[str]], tuple[int, bytes]]


def _run_git(repo: Path, args: list[str]) -> tuple[int, bytes]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
    except OSError as exc:
        raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE") from exc
    return completed.returncode, completed.stdout


def _posix_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_canonical_data_plane(worktree: Path, data_root: Path) -> bool:
    canonical = (worktree / DEFAULT_DATA_PLANE_RELATIVE).resolve()
    resolved = data_root.resolve()
    return resolved == canonical or resolved.is_relative_to(canonical)


def _absolute_unresolved(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _git_root_lexical(path: Path) -> Path | None:
    current = _absolute_unresolved(path)
    for _ in range(64):
        marker = current / ".git"
        if marker.exists() or marker.is_symlink():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
    raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE")


def _any_lexical_link(path: Path, *, stop_at: Path) -> bool:
    cursor = _absolute_unresolved(path)
    stop = _absolute_unresolved(stop_at)
    for _ in range(64):
        if cursor.is_symlink() or _is_link(cursor):
            return True
        if cursor == stop:
            return stop.is_symlink() or _is_link(stop)
        parent = cursor.parent
        if parent == cursor:
            return False
        cursor = parent
    raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE")


def _git_is_ignored(repo: Path, relative: str, runner: GitRunner) -> bool:
    code, _payload = runner(repo, ["check-ignore", "-q", "--", relative])
    if code == 0:
        return True
    if code == 1:
        return False
    raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE")


def _git_has_tracked_or_staged(repo: Path, relative: str, runner: GitRunner) -> bool:
    code, tracked = runner(repo, ["ls-files", "-z", "--cached", "--", relative])
    if code != 0:
        raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE")
    if tracked.strip(b"\0"):
        return True
    code, staged = runner(repo, ["diff", "--cached", "--name-only", "-z", "--", relative])
    if code != 0:
        raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE")
    return bool(staged.strip(b"\0"))


def assert_publication_fences(
    *,
    source_root: Path,
    data_root: Path,
    source_receipt_path: Path,
    repo_root: Path | None = None,
    git_runner: GitRunner | None = None,
) -> None:
    runner = git_runner or _run_git
    _require(not _is_link(source_root), "SOURCE_SYMLINK")
    _require(not _is_link(source_receipt_path), "SOURCE_RECEIPT_SYMLINK")
    if data_root.exists() or data_root.is_symlink():
        _require(not _is_link(data_root), "DATA_ROOT_SYMLINK")
    _require(not _is_broad_unsafe_target(data_root), "DATA_ROOT_UNSAFE")
    if repo_root is not None:
        _require(
            not _any_lexical_link(
                repo_root / DEFAULT_DATA_PLANE_RELATIVE,
                stop_at=repo_root,
            ),
            "DATA_ROOT_SYMLINK",
        )
    worktree = _git_root_lexical(data_root) or _git_root_of(data_root)
    if worktree is not None:
        git_dir = (worktree / ".git").resolve()
        _require(not _paths_overlap(data_root.resolve(), git_dir), "DATA_ROOT_INSIDE_GIT")
        _require(data_root.resolve() != worktree.resolve(), "DATA_ROOT_INSIDE_GIT")
        if repo_root is not None:
            _require(worktree == repo_root.resolve(), "DATA_ROOT_INSIDE_GIT")
        _require(_is_canonical_data_plane(worktree, data_root), "DATA_ROOT_INSIDE_GIT")
        _require(_git_is_ignored(worktree, "local/", runner), "DATA_ROOT_INSIDE_GIT")
        relative = _posix_relative(worktree, data_root)
        _require(_git_is_ignored(worktree, relative, runner), "DATA_ROOT_INSIDE_GIT")
        _require(not _git_has_tracked_or_staged(worktree, relative, runner), "DATA_ROOT_INSIDE_GIT")
        _require(not _any_lexical_link(data_root, stop_at=worktree), "DATA_ROOT_SYMLINK")
    elif repo_root is not None and _paths_overlap(data_root, repo_root.resolve()):
        raise EarlyMarketPanelImportError("GIT_GUARD_UNAVAILABLE")
    _require(not _paths_overlap(source_root, data_root), "SOURCE_DATA_ROOT_OVERLAP")
    _require(
        not _paths_overlap(source_receipt_path, data_root),
        "SOURCE_RECEIPT_DATA_ROOT_OVERLAP",
    )


def inspect_canonical_targets(data_root: Path) -> dict[str, Any]:
    root = Path(data_root)
    paths = [root / relative for relative in CANONICAL_TARGET_RELATIVES]
    present = [path for path in paths if path.exists() or path.is_symlink()]
    if not present:
        return {"state": "ABSENT", "paths": []}
    if any(_is_link(path) for path in present):
        return {"state": "SYMLINK", "paths": [str(path.name) for path in present]}
    if len(present) != len(paths):
        return {"state": "PARTIAL", "paths": [path.name for path in present]}
    bound = _load_bound_panel_strict(root)
    if bound is None:
        return {"state": "CORRUPT", "paths": [path.name for path in present]}
    return {
        "state": "COMPLETE_VALID",
        "dataset_fingerprint": bound["dataset_fingerprint"],
        "bound": bound,
    }


def _load_json_bytes(path: Path) -> tuple[bytes, object]:
    _require(path.is_file() and not _is_link(path), "SOURCE_FILE_MISSING")
    payload = path.read_bytes()
    try:
        loaded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarlyMarketPanelImportError("SOURCE_JSON_INVALID") from exc
    return payload, loaded


def _index_receipt_manifests(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_retention = receipt.get("raw_retention")
    _require(isinstance(raw_retention, Mapping), "RAW_RETENTION_MISSING")
    manifests = raw_retention.get("manifests")
    _require(isinstance(manifests, list) and manifests, "RAW_MANIFESTS_MISSING")
    index: dict[str, dict[str, Any]] = {}
    for row in manifests:
        _require(isinstance(row, Mapping), "RAW_MANIFEST_INVALID")
        observation_id = row.get("observation_id")
        _require(isinstance(observation_id, str) and observation_id, "RAW_MANIFEST_INVALID")
        _require(observation_id not in index, "RAW_MANIFEST_DUPLICATE")
        index[observation_id] = dict(row)
    return index


def _resolve_r0_body(source_root: Path, binding: Mapping[str, Any]) -> Path:
    relative = binding.get("path")
    _require(isinstance(relative, str) and relative, "R0_PATH_MISSING")
    name = Path(relative.replace("\\", "/")).name
    _require(name == "DISCOVERY_SEARCH_R0.body", "R0_PATH_INVALID")
    root = source_root.resolve()
    candidate = (source_root / name).resolve()
    _require(candidate.is_relative_to(root), "R0_PATH_ESCAPE")
    _require(candidate.is_file() and not _is_link(candidate), "R0_BODY_MISSING")
    return candidate


def _parse_rows(payload: object) -> list[dict[str, Any]]:
    _require(isinstance(payload, list) and payload, "R0_BODY_NOT_LIST")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        _require(isinstance(item, Mapping), "R0_ROW_INVALID")
        mint = item.get("id")
        _require(isinstance(mint, str) and mint, "R0_MINT_INVALID")
        _require(mint not in seen, "R0_MINT_DUPLICATE")
        seen.add(mint)
        rows.append(dict(item))
    return rows


def _parse_required_timestamp(value: object, *, code: str) -> datetime:
    if value is None or value == "":
        raise EarlyMarketPanelImportError("OBSERVED_AT_MISSING")
    if not isinstance(value, str):
        raise EarlyMarketPanelImportError("OBSERVED_AT_INVALID")
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "T" not in text:
        raise EarlyMarketPanelImportError("OBSERVED_AT_INVALID")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EarlyMarketPanelImportError("OBSERVED_AT_INVALID") from exc
    if parsed.tzinfo is None:
        raise EarlyMarketPanelImportError("OBSERVED_AT_NAIVE")
    aware = parsed.astimezone(UTC)
    if aware < AVAILABILITY_WINDOW_START or aware > AVAILABILITY_WINDOW_END:
        raise EarlyMarketPanelImportError("OBSERVED_AT_OUT_OF_WINDOW")
    if code and code != "OBSERVED_AT":
        pass
    return aware


def _normalized_table(
    rows: list[dict[str, Any]],
    *,
    available_at: datetime,
) -> pa.Table:
    mints: list[str] = []
    observed: list[datetime] = []
    available: list[datetime] = []
    mixes: list[float | None] = []
    codes: list[str] = []
    buy_present: list[bool] = []
    sell_present: list[bool] = []
    for row in rows:
        mix, code = classify_r0_mix(row)
        stats = row.get("stats5m") if isinstance(row.get("stats5m"), Mapping) else {}
        mints.append(str(row["id"]))
        observed.append(available_at)
        available.append(available_at)
        mixes.append(mix)
        codes.append(code or "")
        buy_present.append(isinstance(stats, Mapping) and "buyVolume" in stats)
        sell_present.append(isinstance(stats, Mapping) and "sellVolume" in stats)
    return pa.table(
        {
            "mint": pa.array(mints, type=pa.string()),
            "observed_at": pa.array(observed, type=pa.timestamp("us", tz="UTC")),
            "available_to_strategy_at": pa.array(
                available, type=pa.timestamp("us", tz="UTC")
            ),
            "r0_taker_volume_mix": pa.array(mixes, type=pa.float64()),
            "missingness_code": pa.array(codes, type=pa.string()),
            "buy_volume_present": pa.array(buy_present, type=pa.bool_()),
            "sell_volume_present": pa.array(sell_present, type=pa.bool_()),
        }
    )


def _parquet_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(
        table,
        sink,
        compression="NONE",
        use_dictionary=False,
        write_statistics=True,
        version="2.6",
        data_page_version="1.0",
        row_group_size=65536,
        coerce_timestamps="us",
        allow_truncated_timestamps=False,
        store_schema=True,
    )
    return sink.getvalue().to_pybytes()


def dataset_labels() -> dict[str, Any]:
    return {
        **REQUIRED_LABELS,
        "feature_hint": FEATURE_ID,
        "accepted_hypothesis_id": None,
        "closed_family": CLOSED_FAMILY,
        "capture_atom_id": CAPTURE_ATOM_ID,
        "x_uses_r0_only": True,
        "forbidden_hypothesis_id": FORBIDDEN_HYPOTHESIS_ID,
        "min_usable_yield_eligible": MIN_USABLE_YIELD_ELIGIBLE,
        "receipt_observed_at_relation": RECEIPT_OBSERVED_AT_RELATION,
    }


def _load_bound_panel_strict(data_root: Path) -> dict[str, Any] | None:
    manifest_path = Path(data_root) / MANIFEST_RELATIVE
    labels_path = Path(data_root) / LABELS_RELATIVE
    partition_path = Path(data_root) / PARTITION_RELATIVE
    if (
        not manifest_path.is_file()
        or not labels_path.is_file()
        or not partition_path.is_file()
        or _is_link(manifest_path)
        or _is_link(labels_path)
        or _is_link(partition_path)
    ):
        return None
    try:
        DatasetManifest.model_validate_json(manifest_path.read_bytes())
        PartitionManifest.model_validate_json(partition_path.read_bytes())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        partition = json.loads(partition_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, Exception):
        return None
    if not isinstance(manifest, dict) or not isinstance(labels, dict) or not isinstance(partition, dict):
        return None
    for key, expected in REQUIRED_LABELS.items():
        if labels.get(key) != expected:
            return None
    if labels.get("accepted_hypothesis_id") is not None:
        return None
    fingerprint = manifest.get("dataset_fingerprint")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        return None
    parquet_rel = partition.get("logical_location")
    expected_file = partition.get("file_sha256")
    if not isinstance(parquet_rel, str) or not isinstance(expected_file, str):
        return None
    parquet_path = Path(data_root) / parquet_rel
    if not parquet_path.is_file() or _is_link(parquet_path):
        return None
    if sha256_bytes(parquet_path.read_bytes()) != expected_file:
        return None
    yield_eligible = int(labels.get("yield_eligible") or 0)
    feature_usable = yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE
    published_path = Path(data_root) / PUBLISHED_RELATIVE
    if not published_path.is_file() or _is_link(published_path):
        return None
    try:
        published = json.loads(published_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(published, dict)
        or published.get("commit_point") != COMMIT_POINT_KIND
        or published.get("dataset_fingerprint") != fingerprint
        or published.get("dataset_manifest_id") != DATASET_MANIFEST_ID
    ):
        return None
    return {
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
        "labels": labels,
        "row_count": int(labels.get("row_count") or 0),
        "yield_eligible": yield_eligible,
        "yield_missing": int(labels.get("yield_missing") or 0),
        "feature_hint": FEATURE_ID,
        "feature_usable": feature_usable,
        "dataset_terminal": labels.get("dataset_terminal")
        or (SAMPLE_VALID if feature_usable else SAMPLE_INVALID),
    }


def load_bound_panel(data_root: Path) -> dict[str, Any] | None:
    return _load_bound_panel_strict(Path(data_root))


def _cleanup_owned_staging(staging_root: Path) -> None:
    if staging_root.exists() or staging_root.is_symlink():
        if staging_root.is_symlink() or staging_root.is_file():
            staging_root.unlink()
            return
        shutil.rmtree(staging_root)


def publication_marker(fingerprint: str) -> dict[str, str]:
    return {
        "commit_point": COMMIT_POINT_KIND,
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
    }


def _write_targets(
    dest_root: Path,
    *,
    parquet_bytes: bytes,
    partition_bytes: bytes,
    manifest_bytes: bytes,
    labels_text: str,
    fingerprint: str,
) -> None:
    mapping = {
        LOGICAL_LOCATION: parquet_bytes,
        PARTITION_RELATIVE: partition_bytes,
        MANIFEST_RELATIVE: manifest_bytes,
        LABELS_RELATIVE: labels_text.encode("utf-8"),
        PUBLISHED_RELATIVE: (
            json.dumps(
                publication_marker(fingerprint),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8"),
    }
    for relative, payload in mapping.items():
        path = dest_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _require(not _is_link(path.parent), "TARGET_PARENT_SYMLINK")
        path.write_bytes(payload)


def _publish_commit_point(staging_root: Path, data_root: Path) -> None:
    payload_relatives = CANONICAL_TARGET_RELATIVES[:-1]
    marker_relative = CANONICAL_TARGET_RELATIVES[-1]
    for relative in payload_relatives:
        dest = data_root / relative
        _require(not dest.exists() and not dest.is_symlink(), "CANONICAL_TARGET_EXISTS")
        dest.parent.mkdir(parents=True, exist_ok=True)
        _require(not _is_link(dest.parent), "TARGET_PARENT_SYMLINK")
        os.replace(staging_root / relative, dest)
    marker_dest = data_root / marker_relative
    _require(
        not marker_dest.exists() and not marker_dest.is_symlink(),
        "CANONICAL_TARGET_EXISTS",
    )
    marker_dest.parent.mkdir(parents=True, exist_ok=True)
    _require(not _is_link(marker_dest.parent), "TARGET_PARENT_SYMLINK")
    os.replace(staging_root / marker_relative, marker_dest)


def import_early_market_panel(
    *,
    source_root: Path,
    data_root: Path,
    source_receipt_path: Path,
    expected_receipt_sha256: str | None = None,
    generation_task_id: str = "HFIC_NEXT_EVIDENCE_BIND_AND_CONTEXT_V1",
    generation_run_id: str = "RUN-EARLY-MARKET-PANEL-TEMP-001",
    repo_root: Path | None = None,
    publication_hook: Callable[[], None] | None = None,
    git_runner: GitRunner | None = None,
) -> dict[str, Any]:
    _require(source_root is not None, "SOURCE_REQUIRED")
    _require(source_root.is_dir() and not _is_link(source_root), "SOURCE_INVALID")
    assert_publication_fences(
        source_root=source_root,
        data_root=data_root,
        source_receipt_path=source_receipt_path,
        repo_root=repo_root,
        git_runner=git_runner,
    )
    existing_state = inspect_canonical_targets(data_root)
    receipt_bytes, receipt_obj = _load_json_bytes(source_receipt_path)
    _require(isinstance(receipt_obj, dict), "SOURCE_RECEIPT_INVALID")
    receipt: dict[str, Any] = receipt_obj
    observed_receipt_sha = sha256_bytes(receipt_bytes)
    if expected_receipt_sha256 is not None:
        _require(observed_receipt_sha == expected_receipt_sha256, "RECEIPT_HASH_MISMATCH")
    index = _index_receipt_manifests(receipt)
    r0_binding = index.get(R0_OBSERVATION_ID)
    _require(isinstance(r0_binding, Mapping), "R0_BINDING_MISSING")
    expected_body_sha = r0_binding.get("sha256")
    _require(isinstance(expected_body_sha, str) and len(expected_body_sha) == 64, "R0_HASH_MISSING")
    body_path = _resolve_r0_body(source_root, r0_binding)
    _require(body_path.is_file() and not _is_link(body_path), "R0_BODY_MISSING")
    body_bytes = body_path.read_bytes()
    _require(sha256_bytes(body_bytes) == expected_body_sha, "R0_BODY_HASH_MISMATCH")
    try:
        body_obj = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarlyMarketPanelImportError("R0_BODY_JSON_INVALID") from exc
    envelope_name = r0_binding.get("envelope_path")
    _require(isinstance(envelope_name, str) and envelope_name, "R0_ENVELOPE_PATH_MISSING")
    envelope_path = (source_root / Path(str(envelope_name).replace("\\", "/")).name).resolve()
    _require(envelope_path.is_relative_to(source_root.resolve()), "R0_PATH_ESCAPE")
    _require(envelope_path.is_file() and not _is_link(envelope_path), "R0_ENVELOPE_MISSING")
    envelope_bytes, envelope_obj = _load_json_bytes(envelope_path)
    expected_envelope = r0_binding.get("capture_envelope_sha256")
    _require(
        isinstance(expected_envelope, str) and len(expected_envelope) == 64,
        "R0_ENVELOPE_HASH_MISSING",
    )
    _require(sha256_bytes(envelope_bytes) == expected_envelope, "R0_ENVELOPE_HASH_MISMATCH")
    _require(isinstance(envelope_obj, Mapping), "R0_ENVELOPE_INVALID")
    available_at = _parse_required_timestamp(
        envelope_obj.get("observed_at"),
        code="OBSERVED_AT",
    )
    receipt_observed = r0_binding.get("observed_at")
    receipt_at = _parse_required_timestamp(receipt_observed, code="OBSERVED_AT")
    _require(receipt_at == available_at, "RECEIPT_OBSERVED_AT_MISMATCH")
    rows = _parse_rows(body_obj)
    try:
        semantics = prove_r0_taker_volume_mix_semantics(
            rows, x_source_observation=R0_OBSERVATION_ID
        )
    except FieldSemanticsError as exc:
        raise EarlyMarketPanelImportError(FIELD_SEMANTICS_UNPROVEN) from exc
    table = _normalized_table(rows, available_at=available_at)
    parquet_bytes = _parquet_bytes(table)
    file_sha256 = sha256_bytes(parquet_bytes)
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": DATASET_MANIFEST_ID,
            "r0_body_sha256": expected_body_sha,
            "parquet_sha256": file_sha256,
            "feature_id": FEATURE_ID,
            "evidence_role": REQUIRED_LABELS["evidence_role"],
            "confirmatory_reuse_forbidden": True,
            "outcome_previously_consumed": True,
        }
    )
    yield_eligible = int(semantics["yield_eligible"])
    sample_terminal = (
        SAMPLE_VALID if yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE else SAMPLE_INVALID
    )
    feature_usable = sample_terminal == SAMPLE_VALID
    labels = {
        **dataset_labels(),
        "row_count": table.num_rows,
        "yield_eligible": yield_eligible,
        "yield_missing": semantics["yield_missing"],
        "missingness_codes": semantics["missingness_codes"],
        "source_receipt_sha256": observed_receipt_sha,
        "r0_body_sha256": expected_body_sha,
        "dataset_fingerprint": fingerprint,
        "field_semantics_terminal": semantics["terminal"],
        "dataset_terminal": sample_terminal,
        "feature_usable": feature_usable,
        "provider_calls_actual": 0,
        "observed_at": available_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    state = existing_state["state"]
    if state == "COMPLETE_VALID":
        if existing_state["dataset_fingerprint"] == fingerprint:
            bound = existing_state["bound"]
            return {
                "status": "IDEMPOTENT_REUSE",
                "dataset_manifest_id": DATASET_MANIFEST_ID,
                "dataset_fingerprint": fingerprint,
                "row_count": bound["row_count"],
                "yield_eligible": bound["yield_eligible"],
                "yield_missing": bound["yield_missing"],
                "dataset_terminal": bound["dataset_terminal"],
                "feature_usable": bound["feature_usable"],
                "provider_calls_actual": 0,
                "field_semantics": semantics,
                "labels": bound["labels"],
                "epoch_material_changed": False,
            }
        raise EarlyMarketPanelImportError("DATASET_FINGERPRINT_CONFLICT")
    if state == "PARTIAL":
        raise EarlyMarketPanelImportError("EXISTING_TARGET_PARTIAL")
    if state == "CORRUPT":
        raise EarlyMarketPanelImportError("EXISTING_TARGET_CORRUPT")
    if state == "SYMLINK":
        raise EarlyMarketPanelImportError("EXISTING_TARGET_SYMLINK")
    if state != "ABSENT":
        raise EarlyMarketPanelImportError("EXISTING_TARGET_INVALID")

    partition_manifest = PartitionManifest(
        partition_manifest_id=PARTITION_MANIFEST_ID,
        dataset_manifest_id=DATASET_MANIFEST_ID,
        partition_id=PARTITION_ID,
        logical_location=LOGICAL_LOCATION,
        file_sha256=file_sha256,
        content_sha256=file_sha256,
        row_count=table.num_rows,
        min_event_time=available_at,
        max_event_time=available_at,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=available_at,
    )
    dataset_manifest = DatasetManifest(
        dataset_manifest_id=DATASET_MANIFEST_ID,
        dataset_id=DATASET_ID,
        dataset_version="1.0",
        schema_id=SCHEMA_ID,
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=fingerprint,
        generation_task_id=generation_task_id,
        generation_run_id=generation_run_id,
        validation_receipt_sha256=canonical_sha256(
            {
                "field_semantics_terminal": semantics["terminal"],
                "r0_body_sha256": expected_body_sha,
                "dataset_terminal": sample_terminal,
            }
        ),
        first_reliable_available_at=available_at,
        created_at=available_at,
        content_sha256=canonical_sha256(
            {
                "dataset_fingerprint": fingerprint,
                "partition_file_sha256": file_sha256,
                "labels": REQUIRED_LABELS,
            }
        ),
    )
    staging_root = (
        Path(data_root).resolve().parent
        / f".{Path(data_root).name}.panel-import-{os.getpid()}-{uuid.uuid4().hex}"
    )
    _require(not staging_root.exists() and not staging_root.is_symlink(), "STAGING_EXISTS")
    staging_owned = False
    published = False
    try:
        staging_root.mkdir(parents=False, exist_ok=False)
        staging_owned = True
        labels_text = json.dumps(labels, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        _write_targets(
            staging_root,
            parquet_bytes=parquet_bytes,
            partition_bytes=canonical_manifest_bytes(partition_manifest),
            manifest_bytes=canonical_manifest_bytes(dataset_manifest),
            labels_text=labels_text,
            fingerprint=fingerprint,
        )
        staged = _load_bound_panel_strict(staging_root)
        _require(staged is not None, "STAGING_VERIFY_FAILED")
        _require(staged["dataset_fingerprint"] == fingerprint, "STAGING_FINGERPRINT_MISMATCH")
        if publication_hook is not None:
            publication_hook()
        _publish_commit_point(staging_root, Path(data_root))
        published = True
        staging_owned = False
        _cleanup_owned_staging(staging_root)
    finally:
        if staging_owned and not published:
            _cleanup_owned_staging(staging_root)

    return {
        "status": "IMPORTED",
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
        "row_count": table.num_rows,
        "yield_eligible": yield_eligible,
        "yield_missing": semantics["yield_missing"],
        "dataset_terminal": sample_terminal,
        "feature_usable": feature_usable,
        "provider_calls_actual": 0,
        "field_semantics": semantics,
        "labels": labels,
        "epoch_material_changed": True,
    }


__all__ = [
    "CAPTURE_ATOM_ID",
    "CLOSED_FAMILY",
    "DATASET_MANIFEST_ID",
    "EarlyMarketPanelImportError",
    "FEATURE_ID",
    "FORBIDDEN_HYPOTHESIS_ID",
    "GIT_RECEIPT_RELATIVE",
    "GIT_RECEIPT_SHA256",
    "MIN_USABLE_YIELD_ELIGIBLE",
    "RECEIPT_OBSERVED_AT_RELATION",
    "REQUIRED_LABELS",
    "SAMPLE_INVALID",
    "SAMPLE_VALID",
    "DEFAULT_DATA_PLANE_RELATIVE",
    "GitRunner",
    "assert_publication_fences",
    "import_early_market_panel",
    "inspect_canonical_targets",
    "is_link_path",
    "load_bound_panel",
]
