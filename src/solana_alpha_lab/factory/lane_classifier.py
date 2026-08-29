"""Deterministic lane classification for governed ExperimentSpec v1.1 submissions."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import jsonschema
import yaml

from solana_alpha_lab.factory.data_resolver import (
    EvidenceResolutionError,
    ResolvedEvidence,
    resolve_catalog_asset,
    resolve_evidence_bindings,
    resolve_query_recipe_hashes,
    verify_implementation_assets,
)
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
from solana_alpha_lab.factory.run_passport import (
    RunPassportError,
    canonical_sha256,
    compute_run_key_sha256,
    experiment_spec_sha256,
)

SPEC_SCHEMA_RELATIVE = "catalog/schemas/experiment_spec_v1_1.schema.json"
SPEC_SCHEMA_V1_2_RELATIVE = "catalog/schemas/experiment_spec_v1_2.schema.json"
DESCRIPTOR_SCHEMA_RELATIVE = (
    "catalog/schemas/experiment_capability_descriptor.schema.json"
)
CAPABILITY_REGISTRY_RELATIVE = "configs/experiment_capability_registry_v1.yaml"
CAPABILITY_REGISTRY_V2_RELATIVE = "configs/experiment_capability_registry_v2.yaml"
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


def _load_capabilities(
    root: Path,
    *,
    registry_relative: str = CAPABILITY_REGISTRY_RELATIVE,
) -> dict[str, Mapping[str, Any]]:
    registry_path = root / registry_relative
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
    version = spec.get("schema_version")
    schema_relative = SPEC_SCHEMA_RELATIVE
    if version == "1.2":
        schema_relative = SPEC_SCHEMA_V1_2_RELATIVE
    elif version not in {None, "1.1"}:
        return None
    try:
        jsonschema.validate(dict(spec), _load_json_object(root / schema_relative))
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


def _git_head_sha(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    value = completed.stdout.decode("ascii", errors="ignore").strip()
    return value if _GIT_SHA_PATTERN.fullmatch(value) is not None else None


def _git_show_bytes(root: Path, git_sha: str, relative: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "show", f"{git_sha}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def _runner_git_sha(submission: Mapping[str, Any], *, root: Path) -> str:
    supplied = submission.get("runner_git_sha")
    if supplied is None:
        supplied = _git_head_sha(root)
    if (
        not isinstance(supplied, str)
        or _GIT_SHA_PATTERN.fullmatch(supplied) is None
    ):
        raise ValueError("RUNNER_GIT_SHA_INVALID")
    return supplied


def _hypothesis_definition_sha256(submission: Mapping[str, Any]) -> str:
    value = submission.get("hypothesis_definition_sha256")
    if value is None and isinstance(submission.get("hypothesis_version"), Mapping):
        value = submission["hypothesis_version"].get("definition_sha256")
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("HYPOTHESIS_DEFINITION_SHA256_INVALID")
    return value


def _uv_lock_sha256(root: Path) -> str:
    path = root / "uv.lock"
    if path.is_symlink() or not path.is_file():
        raise ValueError("UV_LOCK_UNAVAILABLE")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_key(
    spec: Mapping[str, Any],
    submission: Mapping[str, Any],
    *,
    runner_git_sha: str,
    implementation_assets: tuple[tuple[str, str], ...],
    evidence: tuple[ResolvedEvidence, ...],
    query_recipes: tuple[tuple[str, str], ...],
    root: Path,
) -> str:
    parameters = spec.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("PARAMETERS_INVALID")
    random_seed = parameters.get(
        "random_seed_or_null",
        parameters.get("random_seed"),
    )
    if random_seed is None:
        normalized_seed: int | None = None
    elif isinstance(random_seed, int) and not isinstance(random_seed, bool):
        normalized_seed = random_seed
    else:
        raise ValueError("RANDOM_SEED_INVALID")
    holdouts = submission.get("holdout_consumption_ids", ())
    datasets = tuple(
        item for item in evidence if item.source_kind == "DATASET_MANIFEST"
    )
    values = {
        "hypothesis_definition_sha256": _hypothesis_definition_sha256(submission),
        "experiment_spec_sha256": experiment_spec_sha256(spec),
        "capability_id": spec["capability_id"],
        "capability_closure_sha256": canonical_sha256(
            {
                "capability_id": spec["capability_id"],
                "implementation_assets": [
                    {"asset_id": asset_id, "sha256": content_sha256}
                    for asset_id, content_sha256 in implementation_assets
                ],
            }
        ),
        "runner_git_sha": runner_git_sha,
        "uv_lock_sha256": _uv_lock_sha256(root),
        "ordered_input_dataset_manifest_ids": [
            item.stable_id for item in datasets
        ],
        "ordered_input_dataset_fingerprints": [
            item.dataset_fingerprint for item in datasets
        ],
        "ordered_query_recipe_ids": [recipe_id for recipe_id, _ in query_recipes],
        "ordered_query_recipe_sha256s": [
            content_sha256 for _, content_sha256 in query_recipes
        ],
        "config_sha256": canonical_sha256(parameters),
        "as_of": spec["as_of"],
        "availability_cutoff": spec["availability_cutoff"],
        "holdout_consumption_ids": holdouts,
        "random_seed_or_null": normalized_seed,
    }
    return compute_run_key_sha256(values)


def _change_lane(reason_code: str) -> LaneDecision:
    return _decision(
        Lane.CHANGE_LANE,
        "CHANGE_LANE_CAPABILITY_GAP",
        reason_codes=(reason_code,),
        next_action="OPEN_BOUNDED_CAPABILITY_CHANGE",
    )


def _blocked_data(reason_code: str) -> LaneDecision:
    return _decision(
        Lane.FAST_LANE,
        "BLOCKED_DATA",
        reason_codes=(reason_code,),
        next_action="RESOLVE_IMMUTABLE_DATA_BINDINGS",
    )


def _deny_integrity(reason_code: str) -> LaneDecision:
    return _decision(
        Lane.DENY,
        "DENY_INTEGRITY_MISMATCH",
        reason_codes=(reason_code,),
        next_action="CORRECT_IMMUTABLE_EVIDENCE_BINDING",
    )


def classify_lane(
    submission: Mapping[str, Any],
    *,
    root: Path,
    data_root: Path,
    as_of: datetime,
) -> LaneDecision:
    """Return one deterministic lane decision without executing a capability."""

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
    registry_relative = (
        CAPABILITY_REGISTRY_V2_RELATIVE
        if spec.get("schema_version") == "1.2"
        else CAPABILITY_REGISTRY_RELATIVE
    )
    try:
        descriptor = _load_capabilities(root, registry_relative=registry_relative).get(capability_id)
    except (OSError, ValueError, yaml.YAMLError, jsonschema.ValidationError):
        return _decision(
            Lane.DENY,
            "DENY_INVALID_SPEC",
            reason_codes=("EXPERIMENT_SPEC_INVALID",),
            next_action="CORRECT_EXPERIMENT_SPEC",
        )
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

    if spec.get("schema_version") == "1.2":
        from solana_alpha_lab.factory.observation_schedule_compiler import (
            compile_observation_request,
        )

        definition_sha = None
        try:
            definition_sha = _hypothesis_definition_sha256(submission)
        except ValueError:
            definition_sha = None
        compiled = compile_observation_request(
            spec,
            root=root,
            data_root=data_root,
            now=as_of,
            hypothesis_version_id=str(spec.get("hypothesis_version") or "") or None,
            hypothesis_definition_sha256=definition_sha,
        )
        if compiled.terminal in {
            "CHANGE_LANE_PRIMITIVE_GAP",
            "CHANGE_LANE_ESTIMATOR_GAP",
            "CHANGE_LANE_SAFETY_CONTRACT_GAP",
        }:
            return _decision(
                Lane.CHANGE_LANE,
                compiled.terminal,
                reason_codes=compiled.reason_codes,
                next_action="OPEN_BOUNDED_CAPABILITY_CHANGE",
            )
        if compiled.terminal in {
            "DENY_OUTCOME_LEAKAGE",
            "DENY_RETROACTIVE_MUTATION",
            "DENY_UNSAFE_RUNTIME_CODE",
            "DENY_INVALID_SPEC",
        }:
            return _decision(
                Lane.DENY,
                compiled.terminal,
                reason_codes=compiled.reason_codes,
                next_action="CORRECT_EXPERIMENT_SPEC",
            )
        if compiled.terminal in {"BLOCKED_BUDGET", "BLOCKED_AUTHORITY"}:
            return _decision(
                Lane.DENY,
                compiled.terminal,
                reason_codes=compiled.reason_codes,
                next_action="NARROW_RUNTIME_REQUEST",
            )
        observation_terminal = compiled.terminal
        observation_next = compiled.next_action
    else:
        observation_terminal = None
        observation_next = None

    try:
        resolve_catalog_asset(
            root,
            str(descriptor["parameter_schema_asset_id"]),
        )
    except EvidenceResolutionError as exc:
        if exc.code == "CATALOG_ASSET_UNAVAILABLE":
            return _change_lane("PARAMETER_SCHEMA_MISSING")
        return _deny_integrity(exc.code)

    try:
        runner_git_sha = _runner_git_sha(submission, root=root)
        implementation_assets = verify_implementation_assets(
            descriptor,
            root=root,
            runner_git_sha=runner_git_sha,
            git_show_bytes=_git_show_bytes,
        )
    except (EvidenceResolutionError, OSError, ValueError):
        return _change_lane("IMPLEMENTATION_HASH_MISMATCH")

    try:
        query_recipes = resolve_query_recipe_hashes(
            spec["query_recipe_ids"],
            root=root,
        )
    except EvidenceResolutionError as exc:
        if exc.code in {
            "ARBITRARY_CODE_OR_SQL_REQUESTED",
            "QUERY_IMPLEMENTATION_MISSING",
        }:
            return _change_lane(exc.code)
        return _decision(
            Lane.DENY,
            "DENY_INVALID_SPEC",
            reason_codes=(exc.code,),
            next_action="CORRECT_EXPERIMENT_SPEC",
        )

    try:
        evidence = resolve_evidence_bindings(
            spec,
            root=root,
            data_root=data_root,
        )
    except EvidenceResolutionError as exc:
        if exc.code in {
            "DATA_BINDING_UNAVAILABLE",
            "EVIDENCE_UNAVAILABLE_AT_CUTOFF",
        }:
            return _blocked_data(exc.code)
        if exc.code in {
            "CATALOG_ASSET_INTEGRITY_MISMATCH",
            "EVIDENCE_HASH_MISMATCH",
            "DATASET_MANIFEST_INVALID",
            "RESEARCH_ARTIFACT_INVALID",
        }:
            return _deny_integrity(exc.code)
        return _decision(
            Lane.DENY,
            "DENY_INVALID_SPEC",
            reason_codes=(exc.code,),
            next_action="CORRECT_EXPERIMENT_SPEC",
        )

    try:
        run_key_sha256 = _run_key(
            spec,
            submission,
            runner_git_sha=runner_git_sha,
            implementation_assets=implementation_assets,
            evidence=evidence,
            query_recipes=query_recipes,
            root=root,
        )
    except (RunPassportError, TypeError, ValueError):
        return _decision(
            Lane.DENY,
            "DENY_INVALID_SPEC",
            reason_codes=("RUN_KEY_INPUTS_INVALID",),
            next_action="CORRECT_EXPERIMENT_SPEC",
        )

    try:
        prior_run = ResearchStore(data_root).find_completed_run(run_key_sha256)
    except ResearchStoreError:
        return _deny_integrity("RUN_COMPLETED_PASSPORT_INVALID")
    if prior_run is not None:
        return _decision(
            Lane.FAST_LANE,
            "REPLAY_AVAILABLE",
            reason_codes=("EXACT_DUPLICATE_COMPLETED",),
            run_key_sha256=run_key_sha256,
            prior_run_id=prior_run.run_id,
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

    if observation_terminal is not None:
        return _decision(
            Lane.FAST_LANE,
            observation_terminal,
            reason_codes=(),
            run_key_sha256=run_key_sha256,
            next_action=observation_next or "EXECUTE_ACCEPTED_CAPABILITY",
        )

    return _decision(
        Lane.FAST_LANE,
        "FAST_LANE_READY",
        reason_codes=(),
        run_key_sha256=run_key_sha256,
        next_action="EXECUTE_ACCEPTED_CAPABILITY",
    )


__all__ = ["Lane", "LaneDecision", "classify_lane"]
