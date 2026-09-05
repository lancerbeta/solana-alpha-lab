"""Shared Research Data Plane root resolution for Fast Lane and HFIC."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATA_PLANE_RELATIVE = Path("local/factory_v1/data_plane")


class DataRootError(ValueError):
    """Fail-closed data-root resolution error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ResolvedDataRoot:
    root: Path
    selection_reason: str
    duplicate_receipt: bool
    instance_fingerprint: str
    store_inventory_digest: str | None

    def redacted_receipt(self) -> dict[str, object]:
        return {
            "selection_reason": self.selection_reason,
            "duplicate_receipt": self.duplicate_receipt,
            "data_root_instance_fingerprint": self.instance_fingerprint,
            "store_inventory_digest": self.store_inventory_digest,
        }


def instance_fingerprint(path: Path) -> str:
    encoded = str(path.resolve()).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_data_root(candidate: Path) -> Path:
    if candidate.is_symlink():
        raise DataRootError("DATA_ROOT_INVALID")
    if not candidate.is_absolute():
        try:
            candidate = candidate.resolve()
        except OSError as exc:
            raise DataRootError("DATA_ROOT_UNAVAILABLE") from exc
    if candidate.is_symlink():
        raise DataRootError("DATA_ROOT_INVALID")
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise DataRootError("DATA_ROOT_UNAVAILABLE") from exc
    if resolved.is_symlink() or not resolved.is_dir():
        raise DataRootError("DATA_ROOT_INVALID")
    encoded = str(resolved).replace("\\", "/").casefold()
    if "google drive" in encoded or "/googledrive/" in encoded:
        raise DataRootError("DATA_ROOT_INVALID")
    return resolved


def _env_mapping(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def inspect_existing_directory(candidate: Path) -> Path | None:
    """Return a resolved existing directory, or None. Never mkdir."""

    try:
        path = Path(candidate)
        if not path.is_absolute():
            path = path.resolve()
        if path.is_symlink() or not path.is_dir():
            return None
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if resolved.is_symlink() or not resolved.is_dir():
        return None
    return resolved


@dataclass(frozen=True, slots=True)
class ExistingDataRootResolution:
    status: str
    root: Path | None
    selection_reason: str
    error: str | None

    def redacted_receipt(self) -> dict[str, object]:
        return {
            "status": self.status,
            "selection_reason": self.selection_reason,
            "error": self.error,
            "present": self.root is not None,
        }


def resolve_existing_data_root(
    repo_root: Path,
    *,
    explicit_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ExistingDataRootResolution:
    """Non-creating discovery: explicit → SMIAL_DATA_ROOT → existing default.

    Missing stays missing. Split-brain is UNAVAILABLE, not an arbitrary pick.
    """

    mapping = _env_mapping(env)
    if explicit_data_root is not None:
        existing = inspect_existing_directory(Path(explicit_data_root))
        if existing is None:
            return ExistingDataRootResolution(
                "NOT_PRESENT", None, "EXPLICIT_MISSING", "RESEARCH_STORE_NOT_PRESENT"
            )
        return ExistingDataRootResolution("PRESENT", existing, "EXPLICIT", None)

    env_raw = mapping.get("SMIAL_DATA_ROOT")
    default_existing = inspect_existing_directory(
        Path(repo_root) / DEFAULT_DATA_PLANE_RELATIVE
    )
    if env_raw:
        env_existing = inspect_existing_directory(Path(env_raw))
        if env_existing is None:
            return ExistingDataRootResolution(
                "NOT_PRESENT",
                None,
                "ENV_MISSING",
                "RESEARCH_STORE_NOT_PRESENT",
            )
        if (
            default_existing is not None
            and env_existing != default_existing
        ):
            return ExistingDataRootResolution(
                "UNAVAILABLE",
                None,
                "SPLIT_BRAIN",
                "DATA_ROOT_SPLIT_BRAIN",
            )
        return ExistingDataRootResolution("PRESENT", env_existing, "ENV", None)

    if default_existing is not None:
        return ExistingDataRootResolution(
            "PRESENT", default_existing, "DEFAULT_EXISTING", None
        )
    return ExistingDataRootResolution(
        "NOT_PRESENT", None, "DEFAULT_MISSING", "RESEARCH_STORE_NOT_PRESENT"
    )


def resolve_data_root(
    repo_root: Path,
    *,
    explicit_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Fast Lane compatible: explicit, else env, else canonical default."""

    mapping = _env_mapping(env)
    if explicit_data_root is not None:
        return validate_data_root(Path(explicit_data_root))
    raw = mapping.get("SMIAL_DATA_ROOT")
    candidate = Path(raw) if raw else Path(repo_root) / DEFAULT_DATA_PLANE_RELATIVE
    return validate_data_root(candidate)


def resolve_active_data_root(
    repo_root: Path,
    *,
    explicit_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    is_commissioned: Callable[[Path], bool] | None = None,
    inventory_digest: Callable[[Path], str | None] | None = None,
) -> ResolvedDataRoot:
    mapping = _env_mapping(env)
    if explicit_data_root is not None:
        explicit_root = validate_data_root(Path(explicit_data_root))
        return _resolved(
            explicit_root,
            "EXPLICIT",
            False,
            inventory_digest or (lambda _path: None),
        )

    default_root = validate_data_root(Path(repo_root) / DEFAULT_DATA_PLANE_RELATIVE)
    env_raw = mapping.get("SMIAL_DATA_ROOT")
    env_root: Path | None = None
    if env_raw:
        env_root = validate_data_root(Path(env_raw))

    ordered: list[Path] = []
    for item in (env_root, default_root):
        if item is None:
            continue
        if item not in ordered:
            ordered.append(item)

    commissioned_fn = is_commissioned or (lambda _path: False)
    digest_fn = inventory_digest or (lambda _path: None)
    commissioned = [path for path in ordered if commissioned_fn(path)]

    if len(commissioned) == 1:
        chosen = commissioned[0]
        return _resolved(chosen, "SINGLE_COMMISSIONED", False, digest_fn)
    if len(commissioned) >= 2:
        digests = {digest_fn(path) for path in commissioned}
        if len(digests) == 1 and next(iter(digests)):
            chosen = env_root or default_root
            return _resolved(chosen, "IDENTICAL_COMMISSIONED", True, digest_fn)
        raise DataRootError("DATA_ROOT_SPLIT_BRAIN")

    if env_root is not None:
        return _resolved(env_root, "ENV_UNCOMMISSIONED", False, digest_fn)
    return _resolved(default_root, "DEFAULT_UNCOMMISSIONED", False, digest_fn)


def _resolved(
    root: Path,
    reason: str,
    duplicate_receipt: bool,
    digest_fn: Callable[[Path], str | None],
) -> ResolvedDataRoot:
    return ResolvedDataRoot(
        root=root,
        selection_reason=reason,
        duplicate_receipt=duplicate_receipt,
        instance_fingerprint=instance_fingerprint(root),
        store_inventory_digest=digest_fn(root),
    )
