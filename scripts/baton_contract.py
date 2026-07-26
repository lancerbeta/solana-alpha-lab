#!/usr/bin/env python3
"""Atom Contract marker extraction, hashing, and semantic validation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
ATOM_SCHEMA_PATH = ROOT / "docs/contracts/atom_contract.schema.json"
BEGIN_MARKER = "<!-- SMIAL-BATON-CONTRACT-BEGIN -->"
END_MARKER = "<!-- SMIAL-BATON-CONTRACT-END -->"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
# Structural path checks prefer segment rules over ASCII-only charset so
# Unicode filenames are allowed while '.', '..', globs and absolutes stay denied.
CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f]")
# Drive / UNC / home paths may appear embedded inside larger strings.
ABS_WIN = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]")
UNC_BACKSLASH = re.compile(r"\\\\[^\s\"']+")
UNC_FORWARD = re.compile(r"//[^\s\"']+")
# URI scheme immediately before // (https://, repo://, git://, …) is not UNC.
URI_SCHEME_COLON_BEFORE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:$")
ABS_POSIX = re.compile(r"^/")
ABS_POSIX_HOME_EMBEDDED = re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|root)/")
EXPECTED_REPO = "lancerbeta/solana-alpha-lab"
FORBIDDEN_NAME_PREFIXES = (
    ".git",
    ".env",
    "wallet",
    "secrets",
    "private",
    "data/raw",
    "data/canonical",
)
CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(password|passphrase|token|api[_-]?key|access[_-]?token|"
        r"secret[_-]?key)\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)\b(sk|pk|ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
)


class BatonContractError(ValueError):
    """Fail-closed Atom Contract error with a deterministic code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = f"{code}:{detail}" if detail else code
        super().__init__(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_contract_payload_bytes(issue_body: str | bytes) -> bytes:
    # Preserve exact offline bytes. Do not decode/re-encode (CRLF stays CRLF).
    if isinstance(issue_body, bytes):
        raw = issue_body
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BatonContractError("issue_body_not_utf8") from exc
    else:
        raw = issue_body.encode("utf-8")
    begin = BEGIN_MARKER.encode("utf-8")
    end = END_MARKER.encode("utf-8")
    if raw.count(begin) != 1:
        raise BatonContractError("begin_marker_count_invalid")
    if raw.count(end) != 1:
        raise BatonContractError("end_marker_count_invalid")
    start = raw.find(begin)
    stop = raw.find(end)
    if start < 0 or stop < 0 or start >= stop:
        raise BatonContractError("marker_order_invalid")
    payload_start = start + len(begin)
    if payload_start >= len(raw) or raw[payload_start : payload_start + 1] != b"\n":
        raise BatonContractError("missing_begin_boundary_newline")
    payload_start += 1
    if stop == 0 or raw[stop - 1 : stop] != b"\n":
        raise BatonContractError("missing_end_boundary_newline")
    payload = raw[payload_start : stop - 1]
    if b"\r" in payload:
        raise BatonContractError("payload_contains_cr")
    if begin in payload or end in payload:
        raise BatonContractError("nested_markers_forbidden")
    return payload


def _reject_json_constant(token: str) -> Any:
    raise BatonContractError(
        "payload_json_nonfinite_forbidden",
        token,
    )


def _object_pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise BatonContractError("payload_json_duplicate_keys", key)
        out[key] = value
    return out


def parse_contract_json(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BatonContractError("payload_not_utf8") from exc
    try:
        data = json.loads(
            text,
            strict=True,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_pairs_no_duplicates,
        )
    except BatonContractError:
        raise
    except json.JSONDecodeError as exc:
        raise BatonContractError("payload_json_invalid", str(exc)) from exc
    if not isinstance(data, dict):
        raise BatonContractError("payload_not_object")
    return data


def load_atom_schema() -> dict[str, Any]:
    return json.loads(ATOM_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_expected_hash(value: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise BatonContractError("expected_contract_sha256_invalid")
    return value


def validate_expected_revision(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise BatonContractError("expected_revision_invalid", repr(value))
    return value


def validate_issue_number(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise BatonContractError("issue_number_invalid", repr(value))
    return value


def verify_out_of_band_hash(payload: bytes, expected_contract_sha256: str) -> str:
    expected = validate_expected_hash(expected_contract_sha256)
    observed = sha256_bytes(payload)
    if observed != expected:
        raise BatonContractError(
            "contract_hash_mismatch",
            f"{observed}:{expected}",
        )
    return observed


def verify_out_of_band_revision(contract: dict[str, Any], expected_revision: int) -> None:
    expected = validate_expected_revision(expected_revision)
    observed = contract.get("contract_revision")
    if not isinstance(observed, int) or isinstance(observed, bool) or observed != expected:
        raise BatonContractError(
            "contract_revision_mismatch",
            f"{observed}:{expected}",
        )


def _has_control_or_nul(value: str) -> bool:
    return CONTROL_CHAR.search(value) is not None


def _forward_unc_is_uri_scheme(value: str, start: int) -> bool:
    """True when ``//`` at ``start`` is the authority slash pair of a URI scheme."""
    return URI_SCHEME_COLON_BEFORE.search(value[:start]) is not None


def _has_unc_path(value: str) -> bool:
    """Detect real UNC forms without treating ``scheme://`` URIs as UNC."""
    if UNC_BACKSLASH.search(value):
        return True
    for match in UNC_FORWARD.finditer(value):
        if _forward_unc_is_uri_scheme(value, match.start()):
            continue
        return True
    return False


def _is_absolute_or_unc(path: str) -> bool:
    return bool(
        ABS_WIN.search(path)
        or ABS_POSIX.match(path)
        or path.startswith("\\\\")
        or path.startswith("//")
        or _has_unc_path(path)
    )


def _normalized_segments_ok(path: str) -> bool:
    if path != path.strip():
        return False
    if "//" in path or path.startswith("/") or path.endswith("/"):
        return False
    if "\\" in path:
        return False
    parts = path.split("/")
    if not parts or any(part == "" for part in parts):
        return False
    if any(part in {".", ".."} for part in parts):
        return False
    return True


def path_is_forbidden_target(path: str) -> bool:
    """Case-insensitive forbidden security targets."""
    if not isinstance(path, str) or not path:
        return True
    if _has_control_or_nul(path) or _is_absolute_or_unc(path):
        return True
    lowered = path.replace("\\", "/").lower()
    if lowered == ".env" or lowered.startswith(".env."):
        return True
    for prefix in FORBIDDEN_NAME_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + "/"):
            return True
        # also catch `.GIT/**` style and `Wallet/**`
        if prefix.startswith(".") and (
            lowered == prefix or lowered.startswith(prefix + "/")
        ):
            return True
    return False


def validate_repository_relative_path(
    path: str,
    *,
    allow_terminal_dir_glob: bool = False,
) -> None:
    if not isinstance(path, str) or path == "":
        raise BatonContractError("path_empty")
    if _has_control_or_nul(path):
        raise BatonContractError("path_control_chars", path)
    if _is_absolute_or_unc(path):
        raise BatonContractError("path_absolute", path)
    if "\\" in path:
        raise BatonContractError("path_backslash", path)
    if allow_terminal_dir_glob and path.endswith("/**"):
        body = path[:-3]
        if "*" in body or "?" in body or "[" in body:
            raise BatonContractError("managed_write_unsafe_glob", path)
        if not _normalized_segments_ok(body):
            raise BatonContractError("managed_write_glob_invalid", path)
        if path_is_forbidden_target(body) or path_is_forbidden_target(path):
            raise BatonContractError("managed_write_forbidden", path)
        return
    if "*" in path or "?" in path or "[" in path:
        raise BatonContractError("managed_write_unsafe_glob", path)
    if not _normalized_segments_ok(path):
        raise BatonContractError("managed_write_path_invalid", path)
    if path_is_forbidden_target(path):
        raise BatonContractError("managed_write_forbidden", path)


def validate_managed_write_entry(entry: str) -> None:
    if not isinstance(entry, str) or entry == "":
        raise BatonContractError("managed_write_empty")
    validate_repository_relative_path(entry, allow_terminal_dir_glob=True)


def normalize_managed_write_entry(entry: str) -> str:
    """Canonical comparison form after validation."""
    validate_managed_write_entry(entry)
    return entry


def path_in_managed_write_set(path: str, managed_write_set: list[str]) -> bool:
    """Match path against fully validated managed-write entries.

    Terminal ``dir/**`` matches only ``dir`` subtree paths ``dir/...``,
    never prefix siblings such as ``dir_evil.txt``.
    """
    try:
        validate_repository_relative_path(path, allow_terminal_dir_glob=False)
    except BatonContractError:
        return False
    if path_is_forbidden_target(path):
        return False
    for entry in managed_write_set:
        validate_managed_write_entry(entry)
        if entry.endswith("/**"):
            prefix = entry[:-3]
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif path == entry:
            return True
    return False


def scan_string_for_secrets(value: str) -> None:
    for pattern in CREDENTIAL_VALUE_PATTERNS:
        if pattern.search(value):
            raise BatonContractError("credential_value_in_contract_string")


def scan_string_for_absolute_user_path(value: str) -> None:
    if (
        ABS_WIN.search(value)
        or _has_unc_path(value)
        or ABS_POSIX_HOME_EMBEDDED.search(value)
    ):
        raise BatonContractError("absolute_user_path_in_contract_string", value)


def walk_strings(node: Any, visitor) -> None:  # type: ignore[no-untyped-def]
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                visitor(key)
            walk_strings(value, visitor)
    elif isinstance(node, list):
        for item in node:
            walk_strings(item, visitor)
    elif isinstance(node, str):
        visitor(node)


def schema_validate_contract(contract: dict[str, Any]) -> None:
    Draft202012Validator(load_atom_schema()).validate(contract)


def semantic_validate_contract(contract: dict[str, Any]) -> None:
    if "contract_sha256" in contract:
        raise BatonContractError("self_referential_contract_sha256_forbidden")
    if contract.get("repository", {}).get("full_name") != EXPECTED_REPO:
        raise BatonContractError("wrong_repository")
    repo = contract["repository"]
    for key in ("base_head", "base_tree"):
        if not HEX40.fullmatch(str(repo.get(key, ""))):
            raise BatonContractError(f"invalid_{key}")
    authority = contract["execution"]["authority_class"]
    network = contract["execution"]["network"]
    if network.get("allowed") is False and list(network.get("allowed_targets") or []):
        raise BatonContractError("network_denied_nonempty_targets")
    if network.get("allowed") is True and not list(network.get("allowed_targets") or []):
        raise BatonContractError("network_allowed_empty_targets")
    credentials = contract["execution"]["credentials"]
    if credentials.get("references_only") is not True:
        raise BatonContractError("credentials_references_only_required")
    writes = contract.get("managed_write_set") or []
    if not isinstance(writes, list):
        raise BatonContractError("managed_write_set_not_list")
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in writes:
        validate_managed_write_entry(entry)
        key = normalize_managed_write_entry(entry)
        if key in seen:
            raise BatonContractError("managed_write_duplicate", entry)
        seen.add(key)
        normalized.append(entry)
    if authority == "READ_ONLY" and writes:
        raise BatonContractError("read_only_nonempty_write_set")
    if authority == "LOCAL_WRITE" and not writes:
        raise BatonContractError("local_write_empty_write_set")
    if contract["execution"].get("dependency_changes_allowed") and authority in {
        "READ_ONLY",
        "LOCAL_WRITE",
    }:
        if authority not in {"COMMIT", "PUSH_REMOTE_SETTINGS"}:
            raise BatonContractError("dependency_changes_authority_insufficient")
    if contract["execution"]["cash_cap_usd"] < 0:
        raise BatonContractError("cash_cap_negative")
    if contract["rollback"].get("destructive_actions_allowed") is not False:
        raise BatonContractError("destructive_actions_must_be_false")
    stop_conditions = contract.get("stop_conditions") or []
    if not isinstance(stop_conditions, list) or not stop_conditions:
        raise BatonContractError("stop_conditions_empty")
    semantic_invariants = contract.get("acceptance", {}).get("semantic_invariants") or []
    if not isinstance(semantic_invariants, list) or not semantic_invariants:
        raise BatonContractError("semantic_invariants_empty")
    for path in contract.get("inputs", {}).get("repository_paths") or []:
        try:
            validate_repository_relative_path(str(path), allow_terminal_dir_glob=False)
        except BatonContractError as exc:
            raise BatonContractError("input_path_forbidden", str(path)) from exc
        if path_is_forbidden_target(str(path)):
            raise BatonContractError("input_path_forbidden", str(path))
    walk_strings(contract, scan_string_for_secrets)
    walk_strings(contract, scan_string_for_absolute_user_path)


def validate_payload(
    payload: bytes,
    *,
    expected_contract_sha256: str,
    expected_revision: int,
) -> dict[str, Any]:
    verify_out_of_band_hash(payload, expected_contract_sha256)
    contract = parse_contract_json(payload)
    verify_out_of_band_revision(contract, expected_revision)
    schema_validate_contract(contract)
    semantic_validate_contract(contract)
    return contract


def resolve_repo_relative_file(
    relative_path: str,
    *,
    root: Path | None = None,
) -> Path:
    """Resolve an explicitly supplied repository-relative regular file.

    Rejects absolute paths, parent traversal, missing files, non-files, and
    symlink escapes outside the repository root.
    """
    repo_root = (root or ROOT).resolve()
    validate_repository_relative_path(relative_path, allow_terminal_dir_glob=False)
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise BatonContractError("issue_body_path_absolute", relative_path)
    joined = (repo_root / candidate).resolve()
    if repo_root not in joined.parents and joined != repo_root:
        raise BatonContractError("issue_body_path_escape", relative_path)
    if not joined.exists():
        raise BatonContractError("issue_body_path_missing", relative_path)
    if joined.is_symlink():
        # After resolve containment already checked; still reject symlink files
        # that are not regular files after resolution.
        pass
    if not joined.is_file():
        raise BatonContractError("issue_body_path_not_regular_file", relative_path)
    # Symlink escape: ensure no symlink component leaves the repo before resolve.
    current = repo_root
    for part in Path(relative_path).parts:
        current = current / part
        if current.is_symlink():
            target = current.resolve()
            if repo_root not in target.parents and target != repo_root:
                raise BatonContractError("issue_body_symlink_escape", relative_path)
    return joined
