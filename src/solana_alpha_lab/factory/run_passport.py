"""Canonical Fast Lane run keys and validated durable run passports."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Annotated, Any, Literal

import jsonschema
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


RUN_PASSPORT_SCHEMA_RELATIVE = "catalog/schemas/run_passport.schema.json"
_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_RUN_KEY_FIELDS = (
    "hypothesis_definition_sha256",
    "experiment_spec_sha256",
    "capability_id",
    "capability_closure_sha256",
    "runner_git_sha",
    "uv_lock_sha256",
    "ordered_input_dataset_manifest_ids",
    "ordered_input_dataset_fingerprints",
    "ordered_query_recipe_ids",
    "ordered_query_recipe_sha256s",
    "config_sha256",
    "as_of",
    "availability_cutoff",
    "holdout_consumption_ids",
    "random_seed_or_null",
)
_SET_ARRAY_FIELDS = frozenset(
    {
        "capabilities",
        "holdout_consumption_ids",
        "non_claims",
        "required_feature_ids",
        "terminal_outcomes",
        "what_changed",
    }
)
_PHYSICAL_PATH_KEYS = frozenset(
    {
        "data_root",
        "physical_path",
        "smial_data_root",
    }
)

Hash64 = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]
GitSha = Annotated[
    str,
    Field(min_length=40, max_length=40, pattern=r"^[0-9a-f]{40}$"),
]
StableId = Annotated[
    str,
    Field(
        min_length=3,
        max_length=256,
        pattern=r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$",
    ),
]


class RunPassportError(ValueError):
    """Raised when a run passport cannot become durable evidence."""


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise RunPassportError("NON_FINITE_NUMBER")
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _timestamp_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RunPassportError("TIMESTAMP_NOT_AWARE")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def normalize_timestamp(value: object) -> str:
    """Normalize an aware timestamp or RFC3339 value to UTC with ``Z``."""

    if isinstance(value, datetime):
        return _timestamp_text(value)
    if not isinstance(value, str):
        raise RunPassportError("TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00") if value.endswith("Z") else datetime.fromisoformat(value)
    except ValueError as exc:
        raise RunPassportError("TIMESTAMP_INVALID") from exc
    return _timestamp_text(parsed)


def _reject_physical_paths(value: object, *, key: str | None = None) -> None:
    if key is not None and key.casefold() in _PHYSICAL_PATH_KEYS:
        raise RunPassportError("PHYSICAL_PATH_FORBIDDEN")
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise RunPassportError("PAYLOAD_KEY_INVALID")
            _reject_physical_paths(child_value, key=child_key)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _reject_physical_paths(item)
        return
    if isinstance(value, Path):
        raise RunPassportError("PHYSICAL_PATH_FORBIDDEN")
    if not isinstance(value, str):
        return
    if value.startswith(("repo://", "smial-data://")):
        return
    normalized = value.replace("\\", "/")
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (
        value.startswith(("/", "\\"))
        or _WINDOWS_DRIVE_RE.match(value) is not None
        or windows_path.is_absolute()
        or posix_path.is_absolute()
        or value.casefold().startswith("file:")
        or ".." in normalized.split("/")
    ):
        raise RunPassportError("PHYSICAL_PATH_FORBIDDEN")


def _canonicalize(value: object) -> object:
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, datetime):
        return _timestamp_text(value)
    if isinstance(value, Path):
        raise RunPassportError("PHYSICAL_PATH_FORBIDDEN")
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RunPassportError("CANONICAL_OBJECT_KEY_INVALID")
            result[key] = _canonicalize(item)
        return result
    if isinstance(value, (set, frozenset)):
        normalized = [_canonicalize(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise RunPassportError("NON_FINITE_NUMBER")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise RunPassportError("CANONICAL_VALUE_INVALID")


def canonical_json_bytes(value: object) -> bytes:
    """Return stable UTF-8 JSON for a public, finite value."""

    try:
        return json.dumps(
            _canonicalize(value),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RunPassportError("CANONICALIZATION_FAILED") from exc


def canonical_sha256(value: object) -> str:
    """Hash canonical JSON with SHA-256."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_experiment_value(value: object, *, key: str | None = None) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise RunPassportError("EXPERIMENT_SPEC_INVALID")
            result[child_key] = _canonical_experiment_value(
                child_value,
                key=child_key,
            )
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        normalized = [_canonical_experiment_value(item) for item in value]
        if key in _SET_ARRAY_FIELDS or isinstance(value, (set, frozenset)):
            return sorted(
                normalized,
                key=lambda item: canonical_json_bytes(item),
            )
        return normalized
    return _canonicalize(value)


def experiment_spec_sha256(spec: Mapping[str, Any]) -> str:
    """Hash an ExperimentSpec while deliberately excluding prose-only change notes."""

    if not isinstance(spec, Mapping):
        raise RunPassportError("EXPERIMENT_SPEC_INVALID")
    without_prose = {
        key: value
        for key, value in spec.items()
        if isinstance(key, str) and key != "what_changed"
    }
    if len(without_prose) != len(spec) - (1 if "what_changed" in spec else 0):
        raise RunPassportError("EXPERIMENT_SPEC_INVALID")
    _reject_physical_paths(without_prose)
    return canonical_sha256(_canonical_experiment_value(without_prose))


def _hash64(name: str, value: object) -> str:
    if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
        raise RunPassportError(f"{name.upper()}_INVALID")
    return value


def _git_sha(name: str, value: object) -> str:
    if not isinstance(value, str) or _GIT_SHA_RE.fullmatch(value) is None:
        raise RunPassportError(f"{name.upper()}_INVALID")
    return value


def _stable_id(name: str, value: object) -> str:
    if not isinstance(value, str) or _STABLE_ID_RE.fullmatch(value) is None:
        raise RunPassportError(f"{name.upper()}_INVALID")
    return value


def _ordered_identifiers(
    name: str,
    value: object,
    *,
    validator: callable,
) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise RunPassportError(f"{name.upper()}_INVALID")
    return [validator(name, item) for item in value]


def _set_identifiers(
    name: str,
    value: object,
    *,
    validator: callable,
) -> list[str]:
    ordered = _ordered_identifiers(name, value, validator=validator)
    return sorted(set(ordered))


def _normalized_run_key_inputs(values: Mapping[str, Any]) -> dict[str, object]:
    if not isinstance(values, Mapping):
        raise RunPassportError("RUN_KEY_INPUTS_INVALID")
    unexpected = set(values).difference(_RUN_KEY_FIELDS)
    missing = set(_RUN_KEY_FIELDS).difference(values)
    if unexpected or missing or any(not isinstance(key, str) for key in values):
        raise RunPassportError("RUN_KEY_INPUTS_INVALID")
    _reject_physical_paths(values)
    random_seed = values["random_seed_or_null"]
    if random_seed is not None and (
        not isinstance(random_seed, int) or isinstance(random_seed, bool)
    ):
        raise RunPassportError("RANDOM_SEED_OR_NULL_INVALID")
    return {
        "hypothesis_definition_sha256": _hash64(
            "hypothesis_definition_sha256",
            values["hypothesis_definition_sha256"],
        ),
        "experiment_spec_sha256": _hash64(
            "experiment_spec_sha256",
            values["experiment_spec_sha256"],
        ),
        "capability_id": _stable_id("capability_id", values["capability_id"]),
        "capability_closure_sha256": _hash64(
            "capability_closure_sha256",
            values["capability_closure_sha256"],
        ),
        "runner_git_sha": _git_sha("runner_git_sha", values["runner_git_sha"]),
        "uv_lock_sha256": _hash64("uv_lock_sha256", values["uv_lock_sha256"]),
        "ordered_input_dataset_manifest_ids": _ordered_identifiers(
            "ordered_input_dataset_manifest_ids",
            values["ordered_input_dataset_manifest_ids"],
            validator=_stable_id,
        ),
        "ordered_input_dataset_fingerprints": _ordered_identifiers(
            "ordered_input_dataset_fingerprints",
            values["ordered_input_dataset_fingerprints"],
            validator=_hash64,
        ),
        "ordered_query_recipe_ids": _ordered_identifiers(
            "ordered_query_recipe_ids",
            values["ordered_query_recipe_ids"],
            validator=_stable_id,
        ),
        "ordered_query_recipe_sha256s": _ordered_identifiers(
            "ordered_query_recipe_sha256s",
            values["ordered_query_recipe_sha256s"],
            validator=_hash64,
        ),
        "config_sha256": _hash64("config_sha256", values["config_sha256"]),
        "as_of": normalize_timestamp(values["as_of"]),
        "availability_cutoff": normalize_timestamp(
            values["availability_cutoff"]
        ),
        "holdout_consumption_ids": _set_identifiers(
            "holdout_consumption_ids",
            values["holdout_consumption_ids"],
            validator=_stable_id,
        ),
        "random_seed_or_null": random_seed,
    }


def compute_run_key_sha256(values: Mapping[str, Any]) -> str:
    """Compute PRD §8.1's canonical, content-addressed run identity."""

    return canonical_sha256(_normalized_run_key_inputs(values))


class RunPassport(BaseModel):
    """Validated payload required for every durable terminal run event."""

    model_config = ConfigDict(extra="allow", frozen=True)

    run_id: StableId
    run_key_sha256: Hash64
    trial_id: StableId
    hypothesis_version_id: StableId
    hypothesis_definition_sha256: Hash64
    experiment_spec_sha256: Hash64
    runner_capability_id: StableId
    runner_git_sha: GitSha
    capability_closure_sha256: Hash64
    uv_lock_sha256: Hash64
    dataset_manifest_ids: tuple[StableId, ...]
    dataset_fingerprints: tuple[Hash64, ...]
    query_recipe_ids: tuple[StableId, ...]
    query_recipe_sha256s: tuple[Hash64, ...]
    config_sha256: Hash64
    as_of: AwareDatetime
    availability_cutoff: AwareDatetime
    holdout_consumption_ids: tuple[StableId, ...]
    random_seed_or_null: int | None
    started_at: AwareDatetime
    completed_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    provider_calls_planned: Annotated[int, Field(ge=0)]
    provider_calls_actual: Annotated[int, Field(ge=0)]
    cash_spend_usd_cents: Annotated[int, Field(ge=0)]
    execution_status: Literal[
        "COMPLETE",
        "FAILED_INFRA",
        "BLOCKED_DATA",
        "BLOCKED_AUTHORITY",
        "ABORTED",
        "INVALID_EVIDENCE",
    ]
    trial_outcome: Literal["POSITIVE", "NEGATIVE", "INCONCLUSIVE", "INVALID"]
    scientific_terminal: Literal[
        "REJECTED",
        "RETAINED",
        "INCONCLUSIVE",
        "PROMOTION_CANDIDATE",
        "INVALID",
    ]
    result_digest_sha256: Hash64
    artifact_manifest_sha256: Hash64
    limitations: tuple[str, ...]
    non_claims: tuple[str, ...]
    observation_schedule_sha256: Hash64 | None = None
    observation_schedule_authority_sha256: Hash64 | None = None
    observation_panel_snapshot_sha256: Hash64 | None = None

    @model_validator(mode="after")
    def validate_passport(self) -> RunPassport:
        if self.provider_calls_actual > self.provider_calls_planned:
            raise ValueError("PROVIDER_CALLS_EXCEED_PLAN")
        if self.availability_cutoff > self.as_of:
            raise ValueError("AVAILABILITY_CUTOFF_AFTER_AS_OF")
        if self.completed_at < self.started_at:
            raise ValueError("COMPLETED_BEFORE_STARTED")
        if self.first_reliable_available_at < self.completed_at:
            raise ValueError("RUN_RELIABLE_BEFORE_COMPLETION")
        _reject_physical_paths(self.model_dump(mode="python"))
        return self

    @property
    def payload(self) -> Mapping[str, Any]:
        """A path-free, immutable JSON-ready view retained for callers."""

        return MappingProxyType(self.model_dump(mode="json"))


def _load_run_passport_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / RUN_PASSPORT_SCHEMA_RELATIVE
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunPassportError("RUN_PASSPORT_SCHEMA_UNAVAILABLE") from exc
    if not isinstance(loaded, dict):
        raise RunPassportError("RUN_PASSPORT_SCHEMA_INVALID")
    return loaded


def validate_run_passport(payload: Mapping[str, Any]) -> RunPassport:
    """Validate a public payload through both Pydantic and JSON Schema."""

    try:
        passport = RunPassport.model_validate(payload)
        jsonschema.validate(passport.model_dump(mode="json"), _load_run_passport_schema())
    except (
        RunPassportError,
        ValidationError,
        jsonschema.ValidationError,
        TypeError,
        ValueError,
    ) as exc:
        if isinstance(exc, RunPassportError):
            raise
        raise RunPassportError("RUN_PASSPORT_INVALID") from exc
    return passport


__all__ = [
    "RUN_PASSPORT_SCHEMA_RELATIVE",
    "RunPassport",
    "RunPassportError",
    "canonical_json_bytes",
    "canonical_sha256",
    "compute_run_key_sha256",
    "experiment_spec_sha256",
    "normalize_timestamp",
    "validate_run_passport",
]
