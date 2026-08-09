"""Fail-closed interpretation of the retained Task30 A0 OHLCV response."""

from __future__ import annotations

import re
from typing import Any, Mapping


RAW_SHA256 = "cce29d4e175bc81a474c699e3bb465daf8cb864f3cb195a9812bd0d3c0ca4163"
EXPECTED_MODELS = ("START_LABELED", "END_LABELED")
EXPECTED_DECISION = "UNRESOLVED_INTERVAL_LABEL_SEMANTICS"
REQUIRED_NEXT_EVIDENCE = "INDEPENDENT_EXACT_TIMESTAMP_SEMANTICS_PROOF"


class BoundarySemanticsError(ValueError):
    """Raised when a boundary observation is promoted beyond its evidence."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BoundarySemanticsError(code)


def _window(value: object) -> tuple[int, int]:
    _require(isinstance(value, Mapping), "WINDOW_REQUIRED")
    start = value.get("start")
    end_exclusive = value.get("end_exclusive")
    _require(
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end_exclusive, int)
        and not isinstance(end_exclusive, bool)
        and start < end_exclusive,
        "WINDOW_INVALID",
    )
    return start, end_exclusive


def evaluate_boundary_semantics(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the only permitted result for the A0 timestamp-boundary shape.

    A response that ends at ``before_timestamp`` is compatible with both
    start-labelled and end-labelled candle models. This evaluator makes that
    ambiguity explicit and rejects every attempted promotion to a continuous
    panel, PIT evidence, no-trade fact, or new external authority.
    """
    raw_binding = config.get("raw_binding")
    _require(isinstance(raw_binding, Mapping), "RAW_BINDING_REQUIRED")
    raw_sha256 = raw_binding.get("raw_sha256")
    _require(
        isinstance(raw_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", raw_sha256),
        "RAW_SHA256_INVALID",
    )
    _require(raw_sha256 == RAW_SHA256, "RAW_BINDING_DRIFT")
    _require(raw_binding.get("git_tracking") == "OUTSIDE_GIT", "RAW_TRACKING_INVALID")

    authority = config.get("authority")
    _require(isinstance(authority, Mapping), "AUTHORITY_REQUIRED")
    _require(
        authority.get("provider_api_rpc_wss_calls") == 0
        and not isinstance(authority.get("provider_api_rpc_wss_calls"), bool),
        "EXTERNAL_AUTHORITY_FORBIDDEN",
    )
    for field in (
        "credential_use",
        "r2_r3_access",
        "dependency_changes",
        "wallet_signer_transaction_actions",
        "cash_spend",
        "task30_trial_or_acceptance",
        "project_sources_changes",
    ):
        _require(authority.get(field) is False, "EXTERNAL_AUTHORITY_FORBIDDEN")

    observed = config.get("observed_response")
    _require(isinstance(observed, Mapping), "OBSERVED_RESPONSE_REQUIRED")
    _require(observed.get("interval_seconds") == 900, "INTERVAL_DRIFT")
    _require(observed.get("record_count") == 96, "RECORD_COUNT_DRIFT")
    target_start, target_end = _window(observed.get("requested_window"))
    returned_grid = observed.get("returned_grid")
    _require(isinstance(returned_grid, Mapping), "RETURNED_GRID_REQUIRED")
    first_timestamp = returned_grid.get("first_timestamp")
    last_timestamp = returned_grid.get("last_timestamp")
    _require(
        first_timestamp == target_start + 900 and last_timestamp == target_end,
        "OBSERVED_GRID_DRIFT",
    )
    _require(
        observed.get("zero_volume_semantics")
        == "OBSERVED_ZERO_VOLUME_NOT_PROVEN_NO_TRADE",
        "ZERO_VOLUME_PROMOTION_FORBIDDEN",
    )

    models = config.get("candidate_models")
    _require(isinstance(models, list), "CANDIDATE_MODELS_REQUIRED")
    model_ids = [model.get("model_id") for model in models if isinstance(model, Mapping)]
    _require(tuple(model_ids) == EXPECTED_MODELS, "CANDIDATE_MODELS_DRIFT")
    implied_windows = []
    for model in models:
        assert isinstance(model, Mapping)
        implied_windows.append(_window(model.get("implied_window")))
    _require(implied_windows[0] == (target_start + 900, target_end + 900), "START_MODEL_DRIFT")
    _require(implied_windows[1] == (target_start, target_end), "END_MODEL_DRIFT")
    _require(implied_windows[0] != implied_windows[1], "MODELS_NOT_DISCRIMINATED")

    _require(config.get("selected_model") is None, "SELECTED_MODEL_FORBIDDEN")
    _require(config.get("decision") == EXPECTED_DECISION, "DECISION_PROMOTION_FORBIDDEN")
    _require(config.get("continuous_panel_claim") is False, "CONTINUOUS_PANEL_CLAIM_FORBIDDEN")
    _require(config.get("pit_admissible_claim") is False, "PIT_ADMISSIBLE_CLAIM_FORBIDDEN")
    _require(
        config.get("required_next_evidence") == REQUIRED_NEXT_EVIDENCE,
        "REQUIRED_NEXT_EVIDENCE_DRIFT",
    )
    _require(config.get("project_sources_disposition") == "NO_CHANGE", "SOURCE_DISPOSITION_DRIFT")

    return {
        "decision": EXPECTED_DECISION,
        "candidate_models": list(EXPECTED_MODELS),
        "required_next_evidence": REQUIRED_NEXT_EVIDENCE,
    }
