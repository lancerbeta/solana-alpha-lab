"""Deterministic lane classification for governed ExperimentSpec v1.1 submissions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import jsonschema
import yaml

SPEC_SCHEMA_RELATIVE = "catalog/schemas/experiment_spec_v1_1.schema.json"
DESCRIPTOR_SCHEMA_RELATIVE = (
    "catalog/schemas/experiment_capability_descriptor.schema.json"
)
CAPABILITY_REGISTRY_RELATIVE = "configs/experiment_capability_registry_v1.yaml"
_TASK_1_RUN_KEY_DEFAULTS: Mapping[str, Any] = {
    "hypothesis_definition_sha256": "0" * 64,
    "capability_closure_sha256": "1" * 64,
    "runner_git_sha": "2" * 40,
    "uv_lock_sha256": "3" * 64,
    "ordered_input_dataset_manifest_ids": (),
    "ordered_input_dataset_fingerprints": (),
    "ordered_query_recipe_sha256s": (),
    "config_sha256": "4" * 64,
    "holdout_consumption_ids": (),
    "random_seed_or_null": None,
}
_SHA256_FIELDS = (
    "hypothesis_definition_sha256",
    "capability_closure_sha256",
    "uv_lock_sha256",
    "config_sha256",
)
_STABLE_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class Lane(StrEnum):
    FAST_LANE = "FAST_LANE"
    CHANGE_LANE = "CHANGE_LANE"
    PROMOTION_LANE = "PROMOTION_LANE"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class LaneDecision:
    lane: Lane
    terminal: str
    reason_codes: tuple[str, ...]
    run_key_sha256: str | None
    prior_run_id: str | None
    next_action: str


def _decision(
    lane: Lane,
    terminal: str,
    *,
    reason_codes: tuple[str, ...],
    run_key_sha256: str | None = None,
    prior_run_id: str | None = None,
    next_action: str,
) -> LaneDecision:
    return LaneDecision(
        lane=lane,
        terminal=terminal,
        reason_codes=reason_codes,
        run_key_sha256=run_key_sha256,
        prior_run_id=prior_run_id,
        next_action=next_action,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"EXPECTED_JSON_OBJECT:{path.name}")
    return loaded


def _load_capabilities(root: Path) -> dict[str, Mapping[str, Any]]:
    registry_path = root / CAPABILITY_REGISTRY_RELATIVE
    loaded = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping) or not isinstance(
        loaded.get("capabilities"), list
    ):
        raise ValueError("EXPERIMENT_CAPABILITY_REGISTRY_INVALID")
    descriptor_schema = _load_json_object(root / DESCRIPTOR_SCHEMA_RELATIVE)
    descriptors: dict[str, Mapping[str, Any]] = {}
    for item in loaded["capabilities"]:
        if not isinstance(item, Mapping):
            raise ValueError("EXPERIMENT_CAPABILITY_DESCRIPTOR_INVALID")
        jsonschema.validate(dict(item), descriptor_schema)
        capability_id = str(item["capability_id"])
        if capability_id in descriptors:
            raise ValueError("EXPERIMENT_CAPABILITY_ID_DUPLICATE")
        descriptors[capability_id] = item
    return descriptors


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("TIMESTAMP_INVALID")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(UTC)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _validated_string_sequence(
    value: object,
    *,
    pattern: re.Pattern[str],
) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("RUN_KEY_INPUTS_INVALID")
    normalized = list(value)
    if any(
        not isinstance(item, str) or pattern.fullmatch(item) is None
        for item in normalized
    ):
        raise ValueError("RUN_KEY_INPUTS_INVALID")
    return normalized


def _validate_spec(
    submission: Mapping[str, Any],
    *,
    root: Path,
    as_of: datetime,
) -> Mapping[str, Any] | None:
    spec = submission.get("experiment_spec")
    if not isinstance(spec, Mapping):
        return None
    try:
        jsonschema.validate(dict(spec), _load_json_object(root / SPEC_SCHEMA_RELATIVE))
        capabilities = spec["capabilities"]
        if (
            not isinstance(capabilities, list)
            or len(capabilities) != 1
            or capabilities[0] != spec["capability_id"]
        ):
            return None
        for requirement in spec["data_requirements"]:
            requirement_path = str(requirement["path"])
            posix_path = PurePosixPath(requirement_path)
            windows_path = PureWindowsPath(requirement_path)
            if (
                posix_path.is_absolute()
                or windows_path.is_absolute()
                or bool(windows_path.drive)
                or bool(windows_path.root)
                or ".." in posix_path.parts
                or ".." in windows_path.parts
            ):
                return None
        if as_of.tzinfo is None:
            return None
        spec_as_of = _parse_timestamp(spec["as_of"])
        availability_cutoff = _parse_timestamp(spec["availability_cutoff"])
        if availability_cutoff > spec_as_of or spec_as_of > as_of.astimezone(UTC):
            return None
    except (jsonschema.ValidationError, KeyError, TypeError, ValueError):
        return None
    return spec


def _run_key(
    spec: Mapping[str, Any],
    submission: Mapping[str, Any],
) -> str:
    injected_value = submission.get("run_key_inputs", {})
    if not isinstance(injected_value, Mapping):
        raise ValueError("RUN_KEY_INPUTS_INVALID")
    spec_for_hash = dict(spec)
    spec_for_hash.pop("what_changed", None)
    spec_for_hash["as_of"] = (
        _parse_timestamp(spec_for_hash["as_of"]).isoformat().replace("+00:00", "Z")
    )
    spec_for_hash["availability_cutoff"] = (
        _parse_timestamp(spec_for_hash["availability_cutoff"])
        .isoformat()
        .replace("+00:00", "Z")
    )
    for field in ("capabilities", "required_feature_ids", "terminal_outcomes"):
        if field in spec_for_hash:
            spec_for_hash[field] = sorted(spec_for_hash[field])
    experiment_spec_sha256 = hashlib.sha256(
        _canonical_json_bytes(spec_for_hash)
    ).hexdigest()
    payload = {
        key: injected_value.get(key, default)
        for key, default in _TASK_1_RUN_KEY_DEFAULTS.items()
    }
    payload.update(
        {
            "experiment_spec_sha256": experiment_spec_sha256,
            "capability_id": spec["capability_id"],
            "ordered_query_recipe_ids": list(spec["query_recipe_ids"]),
            "as_of": _parse_timestamp(spec["as_of"])
            .isoformat()
            .replace("+00:00", "Z"),
            "availability_cutoff": _parse_timestamp(spec["availability_cutoff"])
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )
    for field in _SHA256_FIELDS:
        value = payload[field]
        if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("RUN_KEY_INPUTS_INVALID")
    runner_git_sha = payload["runner_git_sha"]
    if (
        not isinstance(runner_git_sha, str)
        or _GIT_SHA_PATTERN.fullmatch(runner_git_sha) is None
    ):
        raise ValueError("RUN_KEY_INPUTS_INVALID")
    payload["ordered_input_dataset_manifest_ids"] = _validated_string_sequence(
        payload["ordered_input_dataset_manifest_ids"],
        pattern=_STABLE_ID_PATTERN,
    )
    payload["ordered_input_dataset_fingerprints"] = _validated_string_sequence(
        payload["ordered_input_dataset_fingerprints"],
        pattern=_SHA256_PATTERN,
    )
    payload["ordered_query_recipe_sha256s"] = _validated_string_sequence(
        payload["ordered_query_recipe_sha256s"],
        pattern=_SHA256_PATTERN,
    )
    payload["holdout_consumption_ids"] = sorted(
        _validated_string_sequence(
            payload["holdout_consumption_ids"],
            pattern=_STABLE_ID_PATTERN,
        )
    )
    random_seed = payload["random_seed_or_null"]
    if random_seed is not None and (
        not isinstance(random_seed, int) or isinstance(random_seed, bool)
    ):
        raise ValueError("RUN_KEY_INPUTS_INVALID")
    canonical = _canonical_json_bytes(payload)
    return hashlib.sha256(canonical).hexdigest()


def _change_lane(reason_code: str) -> LaneDecision:
    return _decision(
        Lane.CHANGE_LANE,
        "CHANGE_LANE_CAPABILITY_GAP",
        reason_codes=(reason_code,),
        next_action="OPEN_BOUNDED_CAPABILITY_CHANGE",
    )


def classify_lane(
    submission: Mapping[str, Any],
    *,
    root: Path,
    data_root: Path,
    as_of: datetime,
) -> LaneDecision:
    """Return one deterministic lane decision without executing a capability."""

    del data_root  # Physical resolution is introduced by the Task 4 resolver.
    spec = _validate_spec(submission, root=root, as_of=as_of)
    if spec is None:
        return _decision(
            Lane.DENY,
            "DENY_INVALID_SPEC",
            reason_codes=("EXPERIMENT_SPEC_INVALID",),
            next_action="CORRECT_EXPERIMENT_SPEC",
        )

    if submission.get("promotion_requested") is True:
        return _decision(
            Lane.PROMOTION_LANE,
            "PROMOTION_LANE_REQUIRED",
            reason_codes=("PROMOTION_REQUESTED",),
            next_action="PREPARE_PROMOTION_PACKET",
        )

    capability_id = str(spec["capability_id"])
    descriptor = _load_capabilities(root).get(capability_id)
    if descriptor is None:
        return _change_lane("CAPABILITY_NOT_REGISTERED")
    if descriptor["status"] != "ACCEPTED":
        return _change_lane("CAPABILITY_NOT_ACCEPTED")
    if descriptor["parameter_schema_asset_id"] != spec["parameter_schema_asset_id"]:
        return _change_lane("PARAMETER_OUTSIDE_ACCEPTED_SCHEMA")
    if descriptor["query_recipe_required"] and not spec["query_recipe_ids"]:
        return _change_lane("QUERY_IMPLEMENTATION_MISSING")
    if not descriptor["supports_pit"]:
        return _change_lane("PIT_LOGIC_CHANGE_REQUIRED")
    if descriptor["output_zone"] != "DATA_ROOT_ONLY":
        return _change_lane("OUTPUT_SINK_NOT_DATA_PLANE")
    requested_calls = int(spec["evidence_budget"]["provider_api_rpc_wss_calls"])
    if (
        descriptor["effect_class"] != "PROVIDER_READ_ONLY_BOUNDED"
        and requested_calls > 0
    ):
        return _change_lane("GUARDRAIL_CHANGE_REQUIRED")
    if requested_calls > int(descriptor["max_provider_calls"]):
        return _change_lane("GUARDRAIL_CHANGE_REQUIRED")

    available_value = submission.get("available_data_binding_ids", ())
    available = (
        {str(value) for value in available_value}
        if isinstance(available_value, (list, tuple, set, frozenset))
        else set()
    )
    required = {
        str(binding["binding_id"])
        for binding in spec["data_bindings"]
        if isinstance(binding, Mapping)
    }
    if not required.issubset(available):
        return _decision(
            Lane.FAST_LANE,
            "BLOCKED_DATA",
            reason_codes=("DATA_BINDING_UNAVAILABLE",),
            next_action="RESOLVE_IMMUTABLE_DATA_BINDINGS",
        )

    try:
        run_key_sha256 = _run_key(spec, submission)
    except (TypeError, ValueError):
        return _decision(
            Lane.DENY,
            "DENY_INVALID_SPEC",
            reason_codes=("RUN_KEY_INPUTS_INVALID",),
            next_action="CORRECT_EXPERIMENT_SPEC",
        )
    completed_runs = submission.get("completed_runs", {})
    prior_run_id = (
        completed_runs.get(run_key_sha256)
        if isinstance(completed_runs, Mapping)
        else None
    )
    if isinstance(prior_run_id, str) and prior_run_id:
        return _decision(
            Lane.FAST_LANE,
            "REPLAY_AVAILABLE",
            reason_codes=("EXACT_DUPLICATE_COMPLETED",),
            run_key_sha256=run_key_sha256,
            prior_run_id=prior_run_id,
            next_action="REPLAY_PRIOR_RUN",
        )

    if descriptor["effect_class"] == "PROVIDER_READ_ONLY_BOUNDED":
        return _decision(
            Lane.FAST_LANE,
            "FAST_LANE_OWNER_GATE_REQUIRED",
            reason_codes=("OWNER_AUTHORITY_REQUIRED",),
            run_key_sha256=run_key_sha256,
            next_action="PROVIDE_EXACT_OWNER_AUTHORITY",
        )

    return _decision(
        Lane.FAST_LANE,
        "FAST_LANE_READY",
        reason_codes=(),
        run_key_sha256=run_key_sha256,
        next_action="EXECUTE_ACCEPTED_CAPABILITY",
    )


__all__ = ["Lane", "LaneDecision", "classify_lane"]
