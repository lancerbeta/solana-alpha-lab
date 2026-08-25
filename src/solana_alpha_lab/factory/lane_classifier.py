"""Deterministic lane classification for governed ExperimentSpec v1.1 submissions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SPEC_SCHEMA_RELATIVE = "catalog/schemas/experiment_spec_v1_1.schema.json"
DESCRIPTOR_SCHEMA_RELATIVE = (
    "catalog/schemas/experiment_capability_descriptor.schema.json"
)
CAPABILITY_REGISTRY_RELATIVE = "configs/experiment_capability_registry_v1.yaml"


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
    descriptor: Mapping[str, Any],
) -> str:
    payload = {
        "experiment_spec": dict(spec),
        "capability_descriptor": dict(descriptor),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
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

    run_key_sha256 = _run_key(spec, descriptor)
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
