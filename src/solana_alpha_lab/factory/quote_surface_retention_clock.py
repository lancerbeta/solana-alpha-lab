"""Clock admissibility for quote-surface retention. Must not see Y or quote amounts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

CLOCK_VALID = "CLOCK_VALID"
CLOCK_INVALID = "CLOCK_INVALID"
CLOCK_UNKNOWN = "UNKNOWN"
ALLOWED_CLOCK_KEYS = frozenset(
    {
        "identity_id",
        "kind",
        "terminal",
        "due_at",
        "observed_at",
        "horizon_seconds",
        "lateness_slack_seconds",
    }
)
FORBIDDEN_CLOCK_KEYS = frozenset(
    {
        "quote",
        "amount",
        "out_amount",
        "in_amount",
        "retention_delta",
        "forward_quoted_return_h900_h3600",
        "y_status",
        "decision",
        "rtf_t0",
        "rtf_h900",
    }
)
DEFAULT_SLACK_SECONDS = 120
QUOTE_OBSERVED = "QUOTE_OBSERVED"
NO_ROUTE = "NO_ROUTE"
CLOCKED_TERMINALS = frozenset({QUOTE_OBSERVED, NO_ROUTE})
PROVIDER_FAILURE_TERMINALS = frozenset(
    {
        "PROVIDER_TYPED_FAILURE",
        "RATE_LIMITED",
        "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
        "TOKEN_LIST_SHAPE_INVALID",
        "CANCELLED_AFTER_TERMINAL",
    }
)


class QuoteSurfaceRetentionClockError(ValueError):
    """Raised when clock metadata leaks market outcomes or is unusable."""


def clock_metadata_from_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in ALLOWED_CLOCK_KEYS if key in row}


def evaluate_observation_clock(
    h900: Mapping[str, Any],
    h3600: Mapping[str, Any],
) -> str:
    _reject_leak(h900)
    _reject_leak(h3600)
    h900_terminal = str(h900.get("terminal") or "")
    h3600_terminal = str(h3600.get("terminal") or "")
    if h900_terminal in PROVIDER_FAILURE_TERMINALS or h3600_terminal in PROVIDER_FAILURE_TERMINALS:
        return CLOCK_UNKNOWN
    if h900_terminal not in CLOCKED_TERMINALS or h3600_terminal not in CLOCKED_TERMINALS:
        return CLOCK_UNKNOWN
    h900_obs = _parse_utc(h900.get("observed_at"))
    h3600_obs = _parse_utc(h3600.get("observed_at"))
    h900_due = _parse_utc(h900.get("due_at"))
    h3600_due = _parse_utc(h3600.get("due_at"))
    if None in {h900_obs, h3600_obs, h900_due, h3600_due}:
        return CLOCK_UNKNOWN
    if not _inside_window(h900_obs, h900_due, h900.get("lateness_slack_seconds")):
        return CLOCK_INVALID
    if not _inside_window(h3600_obs, h3600_due, h3600.get("lateness_slack_seconds")):
        return CLOCK_INVALID
    if h3600_due <= h900_due or h3600_obs <= h900_obs:
        return CLOCK_INVALID
    return CLOCK_VALID


def evaluate_retention_cell_clock(
    buy_h900: Mapping[str, Any],
    reverse_h900: Mapping[str, Any],
    sell_h3600: Mapping[str, Any],
) -> str:
    pair = evaluate_observation_clock(reverse_h900, sell_h3600)
    if pair != CLOCK_VALID:
        return pair
    _reject_leak(buy_h900)
    buy_terminal = str(buy_h900.get("terminal") or "")
    if buy_terminal in PROVIDER_FAILURE_TERMINALS:
        return CLOCK_UNKNOWN
    if buy_terminal not in CLOCKED_TERMINALS:
        return CLOCK_UNKNOWN
    buy_obs = _parse_utc(buy_h900.get("observed_at"))
    buy_due = _parse_utc(buy_h900.get("due_at"))
    reverse_due = _parse_utc(reverse_h900.get("due_at"))
    sell_obs = _parse_utc(sell_h3600.get("observed_at"))
    if None in {buy_obs, buy_due, reverse_due, sell_obs}:
        return CLOCK_UNKNOWN
    if buy_due != reverse_due:
        return CLOCK_INVALID
    if not _inside_window(buy_obs, buy_due, buy_h900.get("lateness_slack_seconds")):
        return CLOCK_INVALID
    if sell_obs <= buy_obs:
        return CLOCK_INVALID
    return CLOCK_VALID


def qualify_clock_from_consumed_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    observations = receipt.get("observations")
    frozen = receipt.get("frozen_cells")
    strata = {
        str(cell.get("identity_id")): str(cell.get("stratum") or "")
        for cell in list(frozen or [])
        if isinstance(cell, Mapping) and cell.get("identity_id")
    }
    by_identity: dict[str, dict[str, Mapping[str, Any]]] = {}
    if isinstance(observations, list):
        for row in observations:
            if not isinstance(row, Mapping):
                continue
            identity_id = str(row.get("identity_id") or "")
            kind = str(row.get("kind") or "")
            if identity_id and kind in {"BUY_H900", "REVERSE_H900", "SELL_H3600"}:
                by_identity.setdefault(identity_id, {})[kind] = row
    recent_valid = 0
    traded_valid = 0
    unknown_n = 0
    invalid_n = 0
    cells: list[dict[str, Any]] = []
    for identity_id, kinds in by_identity.items():
        buy = kinds.get("BUY_H900")
        reverse = kinds.get("REVERSE_H900")
        sell = kinds.get("SELL_H3600")
        if (
            not isinstance(buy, Mapping)
            or not isinstance(reverse, Mapping)
            or not isinstance(sell, Mapping)
        ):
            status = CLOCK_UNKNOWN
        else:
            status = evaluate_retention_cell_clock(
                clock_metadata_from_observation(buy),
                clock_metadata_from_observation(reverse),
                clock_metadata_from_observation(sell),
            )
        stratum = strata.get(identity_id, "")
        if status == CLOCK_VALID and stratum == "RECENT":
            recent_valid += 1
        elif status == CLOCK_VALID and stratum == "TRADED":
            traded_valid += 1
        elif status == CLOCK_INVALID:
            invalid_n += 1
        else:
            unknown_n += 1
        cells.append(
            {
                "identity_id": identity_id,
                "stratum": stratum,
                "clock_status": status,
            }
        )
    return {
        "schema": "smial.measurement-qualification-receipt",
        "schema_version": "1.0",
        "evidence_class": "ENGINEERING_QUALIFICATION_ONLY",
        "selection_eligible": False,
        "confirmation_eligible": False,
        "promotion_eligible": False,
        "reusable_as_holdout": False,
        "scientific_reclassification": False,
        "provider_api_rpc_wss_calls": 0,
        "recent_clock_valid_n": recent_valid,
        "traded_clock_valid_n": traded_valid,
        "clock_invalid_n": invalid_n,
        "clock_unknown_n": unknown_n,
        "cells": cells,
    }


def _reject_leak(row: Mapping[str, Any]) -> None:
    leaked = FORBIDDEN_CLOCK_KEYS.intersection(row)
    extra = set(row) - ALLOWED_CLOCK_KEYS
    if leaked or extra:
        raise QuoteSurfaceRetentionClockError("CLOCK_METADATA_LEAK")


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _inside_window(observed: datetime, due: datetime, slack_raw: object) -> bool:
    try:
        slack = int(slack_raw) if slack_raw is not None else DEFAULT_SLACK_SECONDS
    except (TypeError, ValueError):
        slack = DEFAULT_SLACK_SECONDS
    if slack < 0:
        slack = DEFAULT_SLACK_SECONDS
    return due <= observed <= due + timedelta(seconds=slack)
