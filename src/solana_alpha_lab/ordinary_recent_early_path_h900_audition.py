"""One fresh, quote-only early-path H900 audition wrapping the organic campaign."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    OrganicPressureError,
    SEASONING_SECONDS,
    _number,
    _parse_datetime,
    run_campaign,
    score_audition,
    validate_policy,
)


ATOM_ID = "ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1"
POLICY_SCHEMA = "smial.ordinary-recent-early-path-h900-audition"
RECEIPT_SCHEMA = "smial.ordinary-recent-early-path-h900-audition.runtime-receipt"
X_FORMULA = "(mcap_T5 / mcap_recent) - 1"
CLOSE_TERMINAL = "CLOSE_EARLY_PATH_CANDIDATE"
FIELD_PATHS = ["recent.mcap", "t5.mcap", "firstPool.createdAt", "t5.updatedAt"]
AUTHORITY_PHRASE = (
    "OK ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1: one bounded Jupiter "
    "Free-key read-only campaign using a local process-environment key only; "
    "Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus "
    "quote-only /swap/v2/order; x-api-key header only; no .env read, no key in "
    "URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, "
    "transaction, paid plan, second provider, retry or fallback; cash cap $0; "
    "call cap 60; global provider pace >=3s; 24 fresh project-eligible recent "
    "candidates excluding all prior consumed mints including "
    "ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1; wait until pool age "
    ">=5m before the single bulk T0 resnapshot; X = (mcap_T5 / mcap_recent) - 1 "
    "from /recent freeze row and that T0 snapshot only; quote-only BUY at T0 "
    "and quote-only SELL at H900; UNKNOWN is never zero; organic-pressure, "
    "flow-pressure, TX_IMBALANCE, H3600/H4, Strategy, Bot, Shadow, alpha and "
    "NetReturn forbidden."
)


def project_early_path(
    recent_row: Mapping[str, Any],
    t5_row: Mapping[str, Any] | None,
    snapshot_at: datetime,
    *,
    seasoning_seconds: int = SEASONING_SECONDS,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "MISSING",
        "value": None,
        "field_paths": list(FIELD_PATHS),
        "inputs": {},
    }
    if not isinstance(recent_row, Mapping) or not isinstance(t5_row, Mapping):
        result["reason"] = "SEARCH_MINT_NOT_RETURNED"
        return result
    if recent_row.get("launchpad") != "pump.fun" or t5_row.get("launchpad") != "pump.fun":
        result["reason"] = "PROJECT_PREDICATE_FALSE"
        return result
    if recent_row.get("id") != t5_row.get("id"):
        result["reason"] = "RECENT_T5_MINT_MISMATCH"
        return result
    pool = t5_row.get("firstPool")
    if not isinstance(pool, Mapping):
        result["reason"] = "REQUIRED_OBJECT_ABSENT"
        return result
    try:
        created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        updated_at = _parse_datetime(t5_row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        result["reason"] = str(exc)
        return result
    observed_at = snapshot_at.astimezone(UTC)
    age_seconds = (observed_at - created_at).total_seconds()
    result["age_seconds"] = age_seconds
    result["inputs"] = {
        "recent.mcap": recent_row.get("mcap"),
        "t5.mcap": t5_row.get("mcap"),
        "firstPool.createdAt": pool.get("createdAt"),
        "t5.updatedAt": t5_row.get("updatedAt"),
    }
    if created_at > observed_at:
        result["reason"] = "FIRST_POOL_TIMESTAMP_IN_FUTURE"
        return result
    if age_seconds < seasoning_seconds:
        result["status"] = "TOO_YOUNG"
        result["reason"] = "POOL_AGE_BELOW_SEASONING"
        return result
    if updated_at < created_at:
        result["reason"] = "UPDATED_TIMESTAMP_BEFORE_POOL_CREATION"
        return result
    if updated_at > observed_at:
        result["reason"] = "UPDATED_TIMESTAMP_IN_FUTURE"
        return result
    mcap_recent = recent_row.get("mcap")
    mcap_t5 = t5_row.get("mcap")
    if not (
        _number(mcap_recent)
        and float(mcap_recent) > 0
        and _number(mcap_t5)
        and float(mcap_t5) >= 0
    ):
        result["reason"] = "MCAP_FIELD_MISSING_OR_INVALID"
        return result
    value = float(mcap_t5) / float(mcap_recent) - 1.0
    if not math.isfinite(value):
        result["reason"] = "EARLY_PATH_NONFINITE"
        return result
    result["status"] = "ELIGIBLE"
    result["value"] = value
    return result


def validate_early_path_policy(policy: Mapping[str, Any], *, root: Any) -> None:
    validate_policy(
        policy,
        root=root,
        expected_atom_id=ATOM_ID,
        expected_authority_phrase=AUTHORITY_PHRASE,
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
    )


def run_early_path_campaign(policy: Mapping[str, Any], **kwargs: Any) -> dict[str, object]:
    return run_campaign(
        policy,
        atom_id=ATOM_ID,
        expected_authority_phrase=AUTHORITY_PHRASE,
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
        receipt_schema=RECEIPT_SCHEMA,
        close_terminal=CLOSE_TERMINAL,
        project_x=project_early_path,
        **kwargs,
    )


__all__ = [
    "ATOM_ID",
    "AUTHORITY_PHRASE",
    "CLOSE_TERMINAL",
    "X_FORMULA",
    "project_early_path",
    "run_early_path_campaign",
    "score_audition",
    "validate_early_path_policy",
]
