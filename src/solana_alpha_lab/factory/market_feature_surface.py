"""Factory-owned market feature surface. Not a feature store. Owns no scientific alpha."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml

from solana_alpha_lab.factory.pit_data_truth_canonicalization import (
    PIT_FEATURE_ID,
    PIT_AVAILABILITY_SCOPE,
    PIT_TERMINAL,
    PitCanonicalizationError,
    canonicalize_from_repository,
)

SURFACE_CONFIG_RELATIVE = "configs/factory_v1_common_market_feature_surface_v1.yaml"
SURFACE_SCHEMA_RELATIVE = (
    "catalog/schemas/factory_v1_common_market_feature_surface.schema.json"
)
CAP_OFFLINE_MARKET_FEATURE_RESOLVE = "CAP-OFFLINE-MARKET-FEATURE-RESOLVE-001"
PASS_TERMINAL = "FEATURE_SURFACE_COMPOSITION_PASS"
DISPLAY_MARK = {
    "COMPUTED": "✓",
    "PIT_READY": "✓",
    "UNKNOWN": "!",
    "NOT_AVAILABLE": "—",
    "MISSING_CAPABILITY": "—",
}


class FeatureSurfaceError(ValueError):
    """Raised when the feature surface cannot resolve fail-closed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unsafe(relative: str) -> bool:
    return Path(relative).is_absolute() or ".." in Path(relative).parts


def load_surface_config(root: Path, relative: str = SURFACE_CONFIG_RELATIVE) -> dict[str, Any]:
    if _unsafe(relative):
        raise FeatureSurfaceError("SURFACE_CONFIG_PATH_UNSAFE")
    path = root / relative
    schema_path = root / SURFACE_SCHEMA_RELATIVE
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FeatureSurfaceError("SURFACE_CONFIG_OR_SCHEMA_MISSING") from exc
    if not isinstance(loaded, dict) or not isinstance(schema, dict):
        raise FeatureSurfaceError("SURFACE_CONFIG_INVALID")
    try:
        jsonschema.validate(loaded, schema)
    except jsonschema.ValidationError as exc:
        raise FeatureSurfaceError("SURFACE_CONFIG_SCHEMA_INVALID") from exc
    return loaded


def _load_json(root: Path, relative: str, expected: str) -> dict[str, Any]:
    if _unsafe(relative):
        raise FeatureSurfaceError("FEATURE_FIXTURE_PATH_UNSAFE")
    path = root / relative
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise FeatureSurfaceError("FEATURE_FIXTURE_MISSING") from exc
    if _sha256(path) != expected:
        raise FeatureSurfaceError("FEATURE_FIXTURE_HASH_MISMATCH")
    loaded = json.loads(payload.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise FeatureSurfaceError("FEATURE_FIXTURE_INVALID")
    return loaded


def _int_path(payload: Mapping[str, Any], *keys: str) -> int | None:
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, Mapping) or key not in cursor:
            return None
        cursor = cursor[key]
    if isinstance(cursor, bool) or not isinstance(cursor, int):
        return None
    return cursor


def _quote_observed_share(runtime: Mapping[str, Any]) -> float | None:
    campaign = runtime.get("campaign")
    if not isinstance(campaign, Mapping):
        return None
    cells = campaign.get("cells")
    if not isinstance(cells, list) or not cells:
        return None
    observed = 0
    for cell in cells:
        if isinstance(cell, Mapping) and cell.get("buy_terminal") == "QUOTE_OBSERVED":
            observed += 1
    return observed / len(cells)


def _compute(
    compute: str,
    *,
    a24: Mapping[str, Any] | None,
    a1: Mapping[str, Any] | None,
    pit: Mapping[str, Any] | None,
) -> tuple[str, float | int | None]:
    if compute == "NONE":
        return "UNKNOWN", None
    if compute.startswith("A24_"):
        if a24 is None:
            raise FeatureSurfaceError("A24_RUNTIME_REQUIRED")
        if compute == "A24_TARGET_BUY_COUNT":
            value = _int_path(a24, "reconciliation", "target_buy_events")
            return ("COMPUTED", value) if value is not None else ("UNKNOWN", None)
        if compute == "A24_TARGET_SELL_COUNT":
            value = _int_path(a24, "reconciliation", "target_sell_events")
            return ("COMPUTED", value) if value is not None else ("UNKNOWN", None)
        if compute == "A24_TARGET_TRADE_COUNT":
            value = _int_path(a24, "reconciliation", "target_pool_trade_events")
            return ("COMPUTED", value) if value is not None else ("UNKNOWN", None)
        if compute == "A24_OBSERVED_TRADE_SLOTS":
            value = _int_path(a24, "decision", "observed_trade_slots")
            return ("COMPUTED", value) if value is not None else ("UNKNOWN", None)
        if compute == "A24_UNKNOWN_COVERAGE_COUNT":
            value = _int_path(a24, "slot_state_counts", "UNKNOWN_COVERAGE")
            return ("COMPUTED", value) if value is not None else ("UNKNOWN", None)
        if compute == "A24_BUY_SELL_COUNT_RATIO":
            buys = _int_path(a24, "reconciliation", "target_buy_events")
            sells = _int_path(a24, "reconciliation", "target_sell_events")
            if buys is None or sells is None or sells == 0:
                return "UNKNOWN", None
            return "COMPUTED", buys / sells
        raise FeatureSurfaceError("COMPUTE_NOT_ALLOWLISTED")
    if compute == "A1_QUOTE_OBSERVED_SHARE":
        if a1 is None:
            raise FeatureSurfaceError("A1_RUNTIME_REQUIRED")
        share = _quote_observed_share(a1)
        return ("COMPUTED", share) if share is not None else ("UNKNOWN", None)
    if compute == "A1_PIT_LIQUIDITY_TO_MCAP_RATIO":
        if pit is None:
            raise FeatureSurfaceError("A1_PIT_RUNTIME_REQUIRED")
        if pit.get("terminal") != PIT_TERMINAL:
            return "UNKNOWN", None
        # The generic surface exposes capability status. Per-mint numeric rows
        # remain owned by the bounded A4 projector, not an aggregate snapshot.
        return "PIT_READY", None
    raise FeatureSurfaceError("COMPUTE_NOT_ALLOWLISTED")


def _value_status_for(availability: str, computed_status: str) -> str:
    if availability == "MISSING_CAPABILITY":
        return "MISSING_CAPABILITY"
    if availability == "MISSING":
        return "NOT_AVAILABLE"
    if availability == "PIT_READY":
        return "PIT_READY" if computed_status == "PIT_READY" else "UNKNOWN"
    if computed_status == "COMPUTED":
        return "COMPUTED"
    return "UNKNOWN"


def feature_index(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in config["features"]:
        feature_id = str(item["feature_id"])
        if feature_id in index:
            raise FeatureSurfaceError("DUPLICATE_FEATURE_ID")
        index[feature_id] = dict(item)
    return index


def resolve_feature_snapshot(
    spec: Mapping[str, Any],
    *,
    root: Path,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    surface = config or load_surface_config(root)
    required = list(spec.get("required_feature_ids") or [])
    if not required:
        raise FeatureSurfaceError("REQUIRED_FEATURE_IDS_MISSING")
    index = feature_index(surface)
    needs_a24 = False
    needs_a1 = False
    needs_pit = False
    for feature_id in required:
        feature = index.get(feature_id)
        if feature is None:
            raise FeatureSurfaceError("FEATURE_NOT_IN_SURFACE")
        compute = str(feature["compute"])
        needs_a24 = needs_a24 or compute.startswith("A24_")
        needs_a1 = needs_a1 or compute == "A1_QUOTE_OBSERVED_SHARE"
    fixtures = surface["fixtures"]
    a24 = (
        _load_json(root, str(fixtures["a24_runtime"]["path"]), str(fixtures["a24_runtime"]["sha256"]))
        if needs_a24
        else None
    )
    a1 = (
        _load_json(root, str(fixtures["a1_runtime"]["path"]), str(fixtures["a1_runtime"]["sha256"]))
        if needs_a1
        else None
    )
    needs_pit = any(
        str(index[feature_id]["compute"]) == "A1_PIT_LIQUIDITY_TO_MCAP_RATIO"
        for feature_id in required
    )
    if needs_pit:
        pit_fixture = fixtures["a1_pit_runtime"]
        try:
            pit = canonicalize_from_repository(
                root,
                runtime_relative=str(pit_fixture["path"]),
                runtime_sha256=str(pit_fixture["sha256"]),
            )
        except PitCanonicalizationError as exc:
            raise FeatureSurfaceError(
                f"PIT_CANONICALIZATION_FAILED:{exc}"
            ) from exc
        pit_features = [
            index[feature_id]
            for feature_id in required
            if str(index[feature_id]["compute"]) == "A1_PIT_LIQUIDITY_TO_MCAP_RATIO"
        ]
        if len(pit_features) != 1:
            raise FeatureSurfaceError("PIT_FEATURE_BINDING_AMBIGUOUS")
        surface_feature = pit_features[0]
        acceptance_feature = pit["feature"]
        if (
            surface_feature["feature_id"] != PIT_FEATURE_ID
            or acceptance_feature["feature_id"] != PIT_FEATURE_ID
            or surface_feature["units"] != acceptance_feature["units"]
            or surface_feature["entity_scope"] != acceptance_feature["entity_scope"]
            or surface_feature["availability_class"]
            != acceptance_feature["availability_class"]
            or surface_feature.get("availability_scope") != PIT_AVAILABILITY_SCOPE
            or acceptance_feature.get("availability_scope")
            != PIT_AVAILABILITY_SCOPE
            or surface_feature.get("availability_scope")
            != acceptance_feature.get("availability_scope")
            or "liquidity USD divided by token market cap USD"
            not in str(surface_feature["description"])
            or acceptance_feature["formula"] != "liquidity / mcap"
            or surface_feature["compute"] != "A1_PIT_LIQUIDITY_TO_MCAP_RATIO"
        ):
            raise FeatureSurfaceError("PIT_FEATURE_BINDING_MISMATCH")
    else:
        pit = None
    rows: list[dict[str, Any]] = []
    for feature_id in required:
        feature = index[feature_id]
        availability = str(feature["availability_class"])
        computed_status, value = _compute(
            str(feature["compute"]),
            a24=a24,
            a1=a1,
            pit=pit,
        )
        if availability in {"MISSING", "MISSING_CAPABILITY"}:
            computed_status, value = (
                "NOT_AVAILABLE" if availability == "MISSING" else "MISSING_CAPABILITY",
                None,
            )
        value_status = _value_status_for(availability, computed_status)
        if value_status != "COMPUTED":
            value = None
        row = {
            "feature_id": feature_id,
            "availability_class": availability,
            "value_status": value_status,
            "value": value,
            "units": feature["units"],
            "coverage_domain": feature["coverage_domain"],
            "available_to_strategy_semantics": feature[
                "available_to_strategy_semantics"
            ],
            "display": f"{DISPLAY_MARK[value_status]} {feature_id} {availability}",
        }
        if value_status == "PIT_READY":
            if pit is None:
                raise FeatureSurfaceError("PIT_ACCEPTANCE_REQUIRED")
            row.update(
                {
                    "pit_acceptance_id": pit["acceptance_id"],
                    "pit_entity_scope": pit["feature"]["entity_scope"],
                    "pit_availability_scope": pit["feature"]["availability_scope"],
                    "pit_decision_snapshot_at": pit["projection"][
                        "decision_snapshot_at"
                    ],
                    "pit_candidate_count": pit["projection"]["candidate_count"],
                    "pit_eligible_count": pit["projection"]["eligible_count"],
                    "pit_missing_count": pit["projection"]["missing_count"],
                }
            )
        rows.append(row)
    return {
        "schema": "smial.factory-v1-market-feature-snapshot",
        "schema_version": "1.0",
        "capability": CAP_OFFLINE_MARKET_FEATURE_RESOLVE,
        "experiment_id": spec.get("experiment_id"),
        "required_feature_ids": required,
        "features": rows,
        "pit_ready_count": sum(
            1 for row in rows if row["value_status"] == "PIT_READY"
        ),
        "provider_api_rpc_wss_calls": 0,
        "terminal": PASS_TERMINAL,
    }
