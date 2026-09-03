"""StrategyVersion version dispatch, schema validation, and normalization.

Scientific feature evaluation stays outside the generic PAPER/SHADOW engine.
Legacy v1.0 keeps declarative signal_rule; v1.1 consumes SignalDecision/ExitDecision.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml


class PaperPlaneError(ValueError):
    """Raised when a strategy version or paper-plane transition is invalid."""


SCHEMA_V1_0 = "catalog/schemas/strategy_version.schema.json"
SCHEMA_V1_1 = "catalog/schemas/strategy_version_v1_1.schema.json"
SCHEMA_SIGNAL_DECISION = "catalog/schemas/signal_decision_v1.schema.json"
SCHEMA_EXIT_DECISION = "catalog/schemas/exit_decision_v1.schema.json"


def canonical_spec_sha256(unsigned: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(unsigned), ensure_ascii=False, sort_keys=True) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json_schema(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _validate(instance: Mapping[str, Any], schema: Mapping[str, Any], code: str) -> None:
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        raise PaperPlaneError(code) from exc


def load_strategy_document(root: Path, relative: str) -> dict[str, Any]:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PaperPlaneError("STRATEGY_PATH_UNSAFE")
    path = root / candidate
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PaperPlaneError("STRATEGY_MISSING") from exc
    if not isinstance(loaded, dict):
        raise PaperPlaneError("STRATEGY_INVALID")
    return loaded


def validate_and_hash_strategy(root: Path, loaded: Mapping[str, Any]) -> dict[str, Any]:
    version = str(loaded.get("schema_version", ""))
    if version == "1.0":
        schema_rel = SCHEMA_V1_0
        invalid_code = "STRATEGY_SCHEMA_INVALID"
    elif version == "1.1":
        schema_rel = SCHEMA_V1_1
        invalid_code = "STRATEGY_V1_1_SCHEMA_INVALID"
    else:
        raise PaperPlaneError("STRATEGY_SCHEMA_VERSION_UNSUPPORTED")

    schema = _load_json_schema(root, schema_rel)
    _validate(loaded, schema, invalid_code)

    unsigned = dict(loaded)
    claimed = str(unsigned.pop("spec_sha256"))
    actual = canonical_spec_sha256(unsigned)
    if claimed != actual:
        raise PaperPlaneError("SPEC_SHA256_MISMATCH")
    return dict(loaded)


def load_strategy_version(root: Path, relative: str) -> dict[str, Any]:
    """Load StrategyVersion v1.0 or v1.1 with schema dispatch and self-hash check."""

    loaded = load_strategy_document(root, relative)
    return validate_and_hash_strategy(root, loaded)


def normalize_strategy(strategy: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a validated strategy into a runtime contract for paper_plane."""

    version = str(strategy["schema_version"])
    base = {
        "schema_version": version,
        "strategy_id": str(strategy["strategy_id"]),
        "strategy_version": str(strategy["strategy_version"]),
        "title": str(strategy["title"]),
        "notional_policy": dict(strategy["notional_policy"]),
        "risk_policy": dict(strategy["risk_policy"]),
        "mode_eligibility": dict(strategy["mode_eligibility"]),
        "spec_sha256": str(strategy["spec_sha256"]),
        "raw": dict(strategy),
    }
    if version == "1.0":
        base.update(
            {
                "runtime_path": "LEGACY_V1_0",
                "commissioning_only": True,
                "signal_rule": dict(strategy["signal_rule"]),
                "entry_rule": dict(strategy["entry_rule"]),
                "exit_rule": dict(strategy["exit_rule"]),
                "source_hypothesis_refs": list(strategy.get("hypothesis_ids", [])),
            }
        )
        return base
    if version == "1.1":
        base.update(
            {
                "runtime_path": "CANDIDATE_V1_1",
                "commissioning_only": False,
                "signal_input": dict(strategy["signal_input"]),
                "exit_input": dict(strategy["exit_input"]),
                "authority_class": str(strategy["authority_class"]),
                "source_hypothesis_refs": list(strategy["source_hypothesis_refs"]),
                "population_ref": str(strategy["population_ref"]),
                "source_decision_asset_id": str(strategy["source_decision_asset_id"]),
            }
        )
        return base
    raise PaperPlaneError("STRATEGY_SCHEMA_VERSION_UNSUPPORTED")


def validate_signal_decision(root: Path, decision: Mapping[str, Any]) -> dict[str, Any]:
    schema = _load_json_schema(root, SCHEMA_SIGNAL_DECISION)
    _validate(decision, schema, "SIGNAL_DECISION_SCHEMA_INVALID")
    return dict(decision)


def validate_exit_decision(root: Path, decision: Mapping[str, Any]) -> dict[str, Any]:
    schema = _load_json_schema(root, SCHEMA_EXIT_DECISION)
    _validate(decision, schema, "EXIT_DECISION_SCHEMA_INVALID")
    return dict(decision)


def position_id_for_signal_decision(signal_decision_id: str) -> str:
    return f"POS-SIG-{signal_decision_id}"
