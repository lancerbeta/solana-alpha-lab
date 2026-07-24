"""Fail-closed storage-budget snapshots for immutable dataset pieces."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

STORAGE_BUDGET_PROFILE = "smial-storage-budget-v1"

_HASH64_RE = re.compile(r"[0-9a-f]{64}")
_LOGICAL_LOCATION_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._=/+-]{0,1023}"
)
_WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:")


class StorageBudgetError(RuntimeError):
    """Base error for storage-budget policy and inventory checks."""


class StorageBudgetContractError(StorageBudgetError):
    """A budget policy or evaluation input is invalid."""


class StorageInventoryError(StorageBudgetError):
    """The on-disk inventory cannot support a trustworthy budget claim."""


class StorageBudgetExceededError(StorageBudgetError):
    """A write would violate an explicit dataset or filesystem limit."""


class StorageBudgetStatus(StrEnum):
    OK = "OK"
    WARNING = "WARNING"


class StorageBudgetAlert(StrEnum):
    DATASET_UTILIZATION_WARNING = "DATASET_UTILIZATION_WARNING"
    FORECAST_DATASET_BUDGET_EXCEEDED = (
        "FORECAST_DATASET_BUDGET_EXCEEDED"
    )
    FORECAST_FILESYSTEM_RESERVE_EXCEEDED = (
        "FORECAST_FILESYSTEM_RESERVE_EXCEEDED"
    )


def _positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StorageBudgetContractError(f"{name}_must_be_positive_int")
    return value


def _non_negative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StorageBudgetContractError(
            f"{name}_must_be_non_negative_int"
        )
    return value


@dataclass(frozen=True, slots=True)
class StorageBudgetPolicy:
    """Explicit owner-selected limits; no implicit production cap exists."""

    max_partition_bytes: int
    max_dataset_bytes: int
    min_free_bytes: int
    warning_threshold_bps: int = 8000
    forecast_partition_count: int = 10

    def __post_init__(self) -> None:
        partition_limit = _positive_int(
            "max_partition_bytes",
            self.max_partition_bytes,
        )
        dataset_limit = _positive_int(
            "max_dataset_bytes",
            self.max_dataset_bytes,
        )
        _non_negative_int("min_free_bytes", self.min_free_bytes)
        warning_threshold = _positive_int(
            "warning_threshold_bps",
            self.warning_threshold_bps,
        )
        _positive_int(
            "forecast_partition_count",
            self.forecast_partition_count,
        )
        if partition_limit > dataset_limit:
            raise StorageBudgetContractError(
                "max_partition_bytes_exceeds_dataset_budget"
            )
        if warning_threshold >= 10_000:
            raise StorageBudgetContractError(
                "warning_threshold_bps_must_be_below_10000"
            )


@dataclass(frozen=True, slots=True)
class StorageBudgetSnapshot:
    """Sanitized measurement returned by the budget gate."""

    profile: str
    status: StorageBudgetStatus
    alerts: tuple[StorageBudgetAlert, ...]
    dataset_logical_root: str
    existing_partition_count: int
    existing_dataset_bytes: int
    incoming_partition_bytes: int
    incremental_write_bytes: int
    projected_dataset_bytes: int
    remaining_dataset_bytes: int
    dataset_utilization_bps: int
    forecast_partition_count: int
    forecast_dataset_bytes: int
    filesystem_free_bytes: int
    filesystem_free_bytes_after_write: int
    remaining_filesystem_bytes_above_reserve: int


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _validated_root(root: Path) -> Path:
    if not isinstance(root, Path):
        raise StorageBudgetContractError("root_must_be_path")
    if not root.is_absolute():
        raise StorageBudgetContractError("root_must_be_absolute")
    if root.is_symlink():
        raise StorageInventoryError("root_symlink_forbidden")
    if not root.exists():
        raise StorageBudgetContractError("root_must_exist")
    if not root.is_dir():
        raise StorageBudgetContractError("root_must_be_directory")
    try:
        return root.resolve(strict=True)
    except OSError as exc:
        raise StorageInventoryError("root_unresolvable") from exc


def _logical_parts(logical_location: str) -> tuple[str, ...]:
    if (
        not isinstance(logical_location, str)
        or _LOGICAL_LOCATION_RE.fullmatch(logical_location) is None
        or logical_location.startswith("/")
        or "\\" in logical_location
        or "://" in logical_location
        or "?" in logical_location
        or "#" in logical_location
        or _WINDOWS_DRIVE_RE.match(logical_location) is not None
    ):
        raise StorageBudgetContractError("logical_location_invalid")
    segments = logical_location.split("/")
    logical = PurePosixPath(logical_location)
    if (
        logical.is_absolute()
        or len(segments) < 2
        or any(segment in {"", ".", ".."} for segment in segments)
        or not logical_location.endswith(".parquet")
    ):
        raise StorageBudgetContractError("logical_location_invalid")
    return tuple(segments)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise StorageInventoryError("inventory_file_unreadable") from exc
    return digest.hexdigest()


def _dataset_inventory(
    *,
    root: Path,
    logical_parts: tuple[str, ...],
) -> tuple[int, int, int | None, str | None]:
    dataset_root = root / logical_parts[0]
    target = root.joinpath(*logical_parts)
    if dataset_root.is_symlink():
        raise StorageInventoryError("dataset_root_symlink_forbidden")
    if not dataset_root.exists():
        return 0, 0, None, None
    if not dataset_root.is_dir():
        raise StorageInventoryError("dataset_root_must_be_directory")
    try:
        resolved_dataset_root = dataset_root.resolve(strict=True)
    except OSError as exc:
        raise StorageInventoryError(
            "dataset_root_unresolvable"
        ) from exc
    if not _is_within(resolved_dataset_root, root):
        raise StorageInventoryError("dataset_root_escapes_root")

    total_bytes = 0
    partition_count = 0
    target_size: int | None = None
    target_sha256: str | None = None
    pending = [resolved_dataset_root]
    while pending:
        current = pending.pop()
        try:
            entries = sorted(
                os.scandir(current),
                key=lambda entry: entry.name,
            )
        except OSError as exc:
            raise StorageInventoryError(
                "inventory_directory_unreadable"
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    raise StorageInventoryError(
                        "inventory_symlink_forbidden"
                    )
                if entry.is_dir(follow_symlinks=False):
                    resolved = path.resolve(strict=True)
                    if not _is_within(resolved, root):
                        raise StorageInventoryError(
                            "inventory_directory_escapes_root"
                        )
                    pending.append(resolved)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    raise StorageInventoryError(
                        "inventory_non_regular_entry"
                    )
                if path.suffix != ".parquet":
                    raise StorageInventoryError(
                        "inventory_unexpected_file"
                    )
                stat_result = entry.stat(follow_symlinks=False)
            except StorageInventoryError:
                raise
            except OSError as exc:
                raise StorageInventoryError(
                    "inventory_entry_unreadable"
                ) from exc
            total_bytes += stat_result.st_size
            partition_count += 1
            if path == target:
                target_size = stat_result.st_size
                target_sha256 = _file_sha256(path)
    return total_bytes, partition_count, target_size, target_sha256


def evaluate_storage_budget(
    *,
    root: Path,
    logical_location: str,
    incoming_file_sha256: str,
    incoming_partition_bytes: int,
    policy: StorageBudgetPolicy,
) -> StorageBudgetSnapshot:
    """Measure one immutable write against explicit logical/physical caps."""

    if not isinstance(policy, StorageBudgetPolicy):
        raise StorageBudgetContractError(
            "policy_must_be_storage_budget_policy"
        )
    incoming_bytes = _positive_int(
        "incoming_partition_bytes",
        incoming_partition_bytes,
    )
    if (
        not isinstance(incoming_file_sha256, str)
        or _HASH64_RE.fullmatch(incoming_file_sha256) is None
    ):
        raise StorageBudgetContractError(
            "incoming_file_sha256_must_be_lowercase_sha256"
        )
    if incoming_bytes > policy.max_partition_bytes:
        raise StorageBudgetExceededError(
            "partition_byte_budget_exceeded"
        )

    resolved_root = _validated_root(root)
    logical_parts = _logical_parts(logical_location)
    (
        existing_bytes,
        partition_count,
        target_size,
        target_sha256,
    ) = _dataset_inventory(
        root=resolved_root,
        logical_parts=logical_parts,
    )
    if target_size is None:
        incremental_bytes = incoming_bytes
    elif (
        target_size == incoming_bytes
        and target_sha256 == incoming_file_sha256
    ):
        incremental_bytes = 0
    else:
        raise StorageInventoryError("immutable_target_conflict")

    projected_bytes = existing_bytes + incremental_bytes
    if projected_bytes > policy.max_dataset_bytes:
        raise StorageBudgetExceededError("dataset_byte_budget_exceeded")

    try:
        free_bytes = shutil.disk_usage(resolved_root).free
    except OSError as exc:
        raise StorageInventoryError("filesystem_usage_unavailable") from exc
    free_after_write = free_bytes - incremental_bytes
    if free_after_write < policy.min_free_bytes:
        raise StorageBudgetExceededError(
            "filesystem_free_space_reserve_exceeded"
        )

    utilization_bps = (
        projected_bytes * 10_000 // policy.max_dataset_bytes
    )
    forecast_growth = (
        incoming_bytes * policy.forecast_partition_count
    )
    forecast_dataset_bytes = projected_bytes + forecast_growth
    alerts: list[StorageBudgetAlert] = []
    if utilization_bps >= policy.warning_threshold_bps:
        alerts.append(
            StorageBudgetAlert.DATASET_UTILIZATION_WARNING
        )
    if forecast_dataset_bytes > policy.max_dataset_bytes:
        alerts.append(
            StorageBudgetAlert.FORECAST_DATASET_BUDGET_EXCEEDED
        )
    if free_after_write - forecast_growth < policy.min_free_bytes:
        alerts.append(
            StorageBudgetAlert.FORECAST_FILESYSTEM_RESERVE_EXCEEDED
        )

    return StorageBudgetSnapshot(
        profile=STORAGE_BUDGET_PROFILE,
        status=(
            StorageBudgetStatus.WARNING
            if alerts
            else StorageBudgetStatus.OK
        ),
        alerts=tuple(alerts),
        dataset_logical_root=logical_parts[0],
        existing_partition_count=partition_count,
        existing_dataset_bytes=existing_bytes,
        incoming_partition_bytes=incoming_bytes,
        incremental_write_bytes=incremental_bytes,
        projected_dataset_bytes=projected_bytes,
        remaining_dataset_bytes=(
            policy.max_dataset_bytes - projected_bytes
        ),
        dataset_utilization_bps=utilization_bps,
        forecast_partition_count=policy.forecast_partition_count,
        forecast_dataset_bytes=forecast_dataset_bytes,
        filesystem_free_bytes=free_bytes,
        filesystem_free_bytes_after_write=free_after_write,
        remaining_filesystem_bytes_above_reserve=(
            free_after_write - policy.min_free_bytes
        ),
    )
