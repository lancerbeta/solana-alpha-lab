"""Versioned ExperimentSpec load and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml

SCHEMA_RELATIVE = "catalog/schemas/experiment_spec.schema.json"


class ExperimentSpecError(ValueError):
    """Raised when an ExperimentSpec is missing, unsafe, or invalid."""


def _load_schema(root: Path) -> dict[str, Any]:
    path = root / SCHEMA_RELATIVE
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ExperimentSpecError("EXPERIMENT_SPEC_SCHEMA_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ExperimentSpecError("EXPERIMENT_SPEC_SCHEMA_INVALID")
    return loaded


def load_experiment_spec(root: Path, relative: str) -> dict[str, Any]:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ExperimentSpecError("EXPERIMENT_SPEC_PATH_UNSAFE")
    path = root / relative
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ExperimentSpecError("EXPERIMENT_SPEC_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ExperimentSpecError("EXPERIMENT_SPEC_INVALID")
    try:
        jsonschema.validate(loaded, _load_schema(root))
    except jsonschema.ValidationError as exc:
        raise ExperimentSpecError("EXPERIMENT_SPEC_SCHEMA_INVALID") from exc
    return loaded


def spec_sha256(root: Path, relative: str) -> str:
    import hashlib

    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ExperimentSpecError("EXPERIMENT_SPEC_PATH_UNSAFE")
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


def requirement_map(spec: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["requirement_id"]): item
        for item in spec["data_requirements"]
        if isinstance(item, Mapping)
    }
