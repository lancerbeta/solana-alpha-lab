"""Zero-network canonicalization of the accepted Atom 1 PIT observations."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PIT_FEATURE_ID = "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO"
PIT_TERMINAL = "FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_PASS"
SOURCE_RUNTIME_RELATIVE = (
    "docs/evidence/early_structural_backing_pit_commissioning/"
    "a1_window_a_runtime_receipt_v1.json"
)
SOURCE_RUNTIME_SHA256 = (
    "8a6647de6e22de81a2be59474bc6e2021ceae740b778113b820b99b158c948be"
)
SOURCE_ACCEPTANCE_RELATIVE = (
    "docs/evidence/early_structural_backing_pit_commissioning/a1_acceptance_v1.json"
)
SOURCE_ACCEPTANCE_SHA256 = (
    "16197a90a7555d4dc77dee9868a7bd82c4191079e9bc1a8711cc7ec913d25d73"
)
SOURCE_TASK_RELATIVE = "docs/tasks/EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1.md"
SOURCE_TASK_SHA256 = (
    "09204fc043bb6df5f01ee44c257ef7b8a62c0885a5a4563b5d3d29e057cb77d9"
)
FACTORY_RUNNER_RELATIVE = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = (
    "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
)
ATOM_1_ID = "EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1"
ATOM_1_TERMINAL = "CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY"
SEARCH_OBSERVATION_ID = "DISCOVERY:SEARCH_T5"
LIQUIDITY_MIN_USD = 1000.0
RATIO_TOLERANCE = 1e-12
REQUIRED_FIELD_PATHS = {
    "liquidity",
    "mcap",
    "firstPool.createdAt",
    "updatedAt",
    "launchpad",
}
FDV_FIELD_NAMES = {"fdv", "fullydilutedvaluation"}
PIT_AVAILABILITY_SCOPE = (
    "Tokens V2 decision snapshot on ICP-EARLY-PUMPFUN-V1; explicit "
    "decision_snapshot_at; liquidity and mcap field availability checks; "
    "updatedAt at or before decision time; source route and acquisition "
    "timing pinned to the accepted Atom 1 receipt"
)


class PitCanonicalizationError(ValueError):
    """Raised when the frozen PIT evidence cannot be promoted fail-closed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(root: Path, relative: str, expected_sha256: str) -> dict[str, Any]:
    path = root / relative
    try:
        actual_sha256 = _sha256(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PitCanonicalizationError("SOURCE_EVIDENCE_UNREADABLE") from exc
    if actual_sha256 != expected_sha256:
        raise PitCanonicalizationError("SOURCE_LINEAGE_HASH_MISMATCH")
    if not isinstance(payload, dict):
        raise PitCanonicalizationError("SOURCE_EVIDENCE_INVALID")
    return payload


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PitCanonicalizationError(code)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise PitCanonicalizationError(code) from exc
    if parsed.tzinfo is None:
        raise PitCanonicalizationError(code)
    return parsed.astimezone(UTC)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        raise PitCanonicalizationError("HISTORICAL_SIDE_EFFECT_COUNT_INVALID")


def _validate_entity_identity(
    row: Mapping[str, Any], source: Mapping[str, Any]
) -> str:
    mint = row.get("mint")
    if not isinstance(mint, str) or not mint:
        raise PitCanonicalizationError("ROW_MINT_INVALID")
    if source.get("row_mint") != mint:
        raise PitCanonicalizationError("ROW_MINT_LINEAGE_MISMATCH")
    return mint


def _validate_unique_entity_keys(rows: list[Mapping[str, Any]]) -> None:
    keys = {
        (row.get("mint"), row.get("decision_snapshot_at"))
        for row in rows
    }
    if len(keys) != len(rows):
        raise PitCanonicalizationError("DUPLICATE_MINT_DECISION_SNAPSHOT")


def _missing_result(
    row: Mapping[str, Any],
    *,
    reason: str,
    decision_snapshot_at: str,
) -> dict[str, Any]:
    source = row.get("x_source")
    if not isinstance(source, Mapping):
        raise PitCanonicalizationError("ROW_SOURCE_LINEAGE_MISSING")
    mint = _validate_entity_identity(row, source)
    if row.get("x") is not None:
        raise PitCanonicalizationError("MISSING_ROW_HAS_NUMERIC_VALUE")
    if row.get("x_status") != "MISSING":
        raise PitCanonicalizationError("ROW_STATUS_NOT_EXPLICIT_MISSING")
    if row.get("x_reason") != reason:
        raise PitCanonicalizationError("MISSING_REASON_MISMATCH")
    return {
        "mint": mint,
        "source_row_mint": source.get("row_mint"),
        "status": "MISSING",
        "value": None,
        "reason": reason,
        "decision_snapshot_at": decision_snapshot_at,
        "source_row_sha256": source.get("row_sha256"),
        "source_response_sha256": source.get("response_sha256"),
    }


def project_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute one candidate's PIT status without using provider code."""

    if not isinstance(row, Mapping):
        raise PitCanonicalizationError("CANDIDATE_ROW_INVALID")
    inputs = row.get("x_inputs")
    source = row.get("x_source")
    if not isinstance(inputs, Mapping) or not isinstance(source, Mapping):
        raise PitCanonicalizationError("ROW_INPUTS_OR_SOURCE_INVALID")
    mint = _validate_entity_identity(row, source)
    if source.get("observation_id") != SEARCH_OBSERVATION_ID:
        raise PitCanonicalizationError("ROW_OBSERVATION_ID_INVALID")
    field_paths = source.get("field_paths")
    if not isinstance(field_paths, list) or not all(
        isinstance(path, str) for path in field_paths
    ):
        raise PitCanonicalizationError("ROW_FIELD_LINEAGE_INVALID")
    if not REQUIRED_FIELD_PATHS.issubset(set(field_paths)):
        raise PitCanonicalizationError("ROW_FIELD_LINEAGE_INCOMPLETE")
    if any(
        path.rsplit(".", 1)[-1].casefold() in FDV_FIELD_NAMES
        for path in field_paths
    ) or any(
        isinstance(key, str) and key.casefold() in FDV_FIELD_NAMES
        for key in inputs
    ):
        raise PitCanonicalizationError("FDV_FIELD_NOT_ADMISSIBLE")
    response_sha256 = source.get("response_sha256")
    row_sha256 = source.get("row_sha256")
    if not isinstance(response_sha256, str) or not isinstance(row_sha256, str):
        raise PitCanonicalizationError("ROW_SOURCE_HASH_MISSING")

    decision_snapshot_at = row.get("decision_snapshot_at")
    decision_at = _parse_utc(decision_snapshot_at, "DECISION_TIMESTAMP_INVALID")
    updated_at_value = inputs.get("updatedAt")
    updated_at = _parse_utc(updated_at_value, "UPDATED_TIMESTAMP_INVALID")

    if updated_at > decision_at:
        return _missing_result(
            row,
            reason="UPDATED_TIMESTAMP_IN_FUTURE",
            decision_snapshot_at=str(decision_snapshot_at),
        )

    existing_reason = row.get("x_reason")
    if existing_reason == "FDV_OR_SUBSTITUTE_REJECTED":
        if inputs.get("mcap") is not None or inputs.get("liquidity") is not None:
            raise PitCanonicalizationError("FDV_REJECTION_WITH_NUMERIC_INPUT")
        return _missing_result(
            row,
            reason="FDV_OR_SUBSTITUTE_REJECTED",
            decision_snapshot_at=str(decision_snapshot_at),
        )

    liquidity = _number(inputs.get("liquidity"))
    mcap = _number(inputs.get("mcap"))
    if liquidity is None or mcap is None:
        return _missing_result(
            row,
            reason="MCAP_OR_LIQUIDITY_MISSING",
            decision_snapshot_at=str(decision_snapshot_at),
        )
    if liquidity <= 0 or mcap <= 0:
        return _missing_result(
            row,
            reason="INVALID_INPUT",
            decision_snapshot_at=str(decision_snapshot_at),
        )
    if liquidity < LIQUIDITY_MIN_USD:
        return _missing_result(
            row,
            reason="LIQUIDITY_BELOW_ICP_MIN",
            decision_snapshot_at=str(decision_snapshot_at),
        )
    if inputs.get("launchpad") != "pump.fun":
        return _missing_result(
            row,
            reason="PROJECT_PREDICATE_FALSE",
            decision_snapshot_at=str(decision_snapshot_at),
        )

    value = liquidity / mcap
    recorded_value = _number(row.get("x"))
    if row.get("x_status") != "ELIGIBLE" or existing_reason is not None:
        raise PitCanonicalizationError("ELIGIBLE_ROW_STATUS_NOT_RECONCILABLE")
    if recorded_value is None or not math.isclose(
        value, recorded_value, rel_tol=RATIO_TOLERANCE, abs_tol=RATIO_TOLERANCE
    ):
        raise PitCanonicalizationError("RECORDED_RATIO_MISMATCH")
    return {
        "mint": mint,
        "source_row_mint": source.get("row_mint"),
        "status": "ELIGIBLE",
        "value": value,
        "reason": None,
        "decision_snapshot_at": str(decision_snapshot_at),
        "source_row_sha256": row_sha256,
        "source_response_sha256": response_sha256,
    }


def _validate_first_byte_basis(root: Path) -> dict[str, Any]:
    task_path = root / SOURCE_TASK_RELATIVE
    try:
        task_text = task_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PitCanonicalizationError("FIRST_BYTE_BASIS_UNREADABLE") from exc
    if _sha256(task_path) != SOURCE_TASK_SHA256:
        raise PitCanonicalizationError("FIRST_BYTE_BASIS_HASH_MISMATCH")
    required_markers = (
        "DEFER_FRESH_PIT_CAPTURE",
        "not a prep-only PR",
        "prospective PIT commissioning",
    )
    if any(marker not in task_text for marker in required_markers):
        raise PitCanonicalizationError("FIRST_BYTE_CHAIN_NOT_PROVEN")
    return {
        "predecessor_decision": "DEFER_FRESH_PIT_CAPTURE",
        "capture_atom": ATOM_1_ID,
        "preparatory_only_atoms_between": 0,
        "basis_task_path": SOURCE_TASK_RELATIVE,
        "basis_task_sha256": SOURCE_TASK_SHA256,
    }


def canonicalize_from_repository(
    root: Path,
    *,
    runtime_relative: str = SOURCE_RUNTIME_RELATIVE,
    runtime_sha256: str = SOURCE_RUNTIME_SHA256,
) -> dict[str, Any]:
    """Build the current A4 acceptance from hash-pinned Git evidence."""

    root = root.resolve()
    if (
        runtime_relative != SOURCE_RUNTIME_RELATIVE
        or runtime_sha256 != SOURCE_RUNTIME_SHA256
    ):
        raise PitCanonicalizationError("PIT_RUNTIME_BINDING_MISMATCH")
    runtime = _read_json(root, runtime_relative, runtime_sha256)
    source_acceptance = _read_json(
        root, SOURCE_ACCEPTANCE_RELATIVE, SOURCE_ACCEPTANCE_SHA256
    )
    runner_path = root / FACTORY_RUNNER_RELATIVE
    if _sha256(runner_path) != FACTORY_RUNNER_SHA256:
        raise PitCanonicalizationError("FACTORY_RUNNER_HASH_CHANGED")

    if runtime.get("atom_id") != ATOM_1_ID:
        raise PitCanonicalizationError("SOURCE_ATOM_ID_INVALID")
    if runtime.get("window") != "A":
        raise PitCanonicalizationError("SOURCE_WINDOW_INVALID")
    if runtime.get("terminal_outcome") != ATOM_1_TERMINAL:
        raise PitCanonicalizationError("SOURCE_TERMINAL_INVALID")
    if source_acceptance.get("task_id") != ATOM_1_ID:
        raise PitCanonicalizationError("SOURCE_ACCEPTANCE_TASK_INVALID")
    if source_acceptance.get("verdict") != ATOM_1_TERMINAL:
        raise PitCanonicalizationError("SOURCE_ACCEPTANCE_TERMINAL_INVALID")
    if source_acceptance.get("promotable") is not False:
        raise PitCanonicalizationError("SCIENTIFIC_FAMILY_NOT_CLOSED")

    candidates = runtime.get("candidate_observations")
    if not isinstance(candidates, list) or not candidates:
        raise PitCanonicalizationError("CANDIDATE_OBSERVATIONS_MISSING")

    search_hash = runtime.get("snapshot_response_sha256")
    manifests = (runtime.get("raw_retention") or {}).get("manifests")
    if not isinstance(search_hash, str) or not isinstance(manifests, list):
        raise PitCanonicalizationError("SEARCH_SOURCE_LINEAGE_MISSING")
    search_manifest = next(
        (
            item
            for item in manifests
            if isinstance(item, Mapping)
            and item.get("observation_id") == SEARCH_OBSERVATION_ID
        ),
        None,
    )
    if not isinstance(search_manifest, Mapping):
        raise PitCanonicalizationError("SEARCH_SOURCE_MANIFEST_MISSING")
    if search_manifest.get("sha256") != search_hash:
        raise PitCanonicalizationError("SEARCH_SOURCE_HASH_MISMATCH")
    if search_manifest.get("retention") != "A4_OUTSIDE_GIT":
        raise PitCanonicalizationError("RAW_BYTES_IMPORTED_AS_GIT_TRUTH")
    search_observed_at = _parse_utc(
        search_manifest.get("observed_at"),
        "SEARCH_OBSERVED_TIMESTAMP_INVALID",
    )

    projected = [project_candidate(row) for row in candidates]
    _validate_unique_entity_keys(projected)
    if any(row["source_response_sha256"] != search_hash for row in projected):
        raise PitCanonicalizationError("ROW_SOURCE_HASH_MISMATCH")
    eligible = [row for row in projected if row["status"] == "ELIGIBLE"]
    missing = [row for row in projected if row["status"] == "MISSING"]
    if len(projected) != 24 or len(eligible) != 19 or len(missing) != 5:
        raise PitCanonicalizationError("SOURCE_PROJECTION_COUNTS_CHANGED")

    first_byte_basis = _validate_first_byte_basis(root)
    decision_times = {row["decision_snapshot_at"] for row in projected}
    if len(decision_times) != 1:
        raise PitCanonicalizationError("DECISION_SNAPSHOT_NOT_SINGLETON")
    decision_snapshot_at = next(iter(decision_times))
    if _parse_utc(decision_snapshot_at, "DECISION_TIMESTAMP_INVALID") != search_observed_at:
        raise PitCanonicalizationError("DECISION_TIMESTAMP_NOT_BOUND_TO_SEARCH")

    row_status_counts = dict(Counter(row["status"] for row in projected))
    missing_reason_counts = dict(Counter(row["reason"] for row in missing))
    return {
        "schema": "smial.factory-v1-pit-data-truth-canonicalization.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "FACTORY-V1-PIT-DATA-TRUTH-CANONICALIZATION-001",
        "task_id": "FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_V1",
        "terminal": PIT_TERMINAL,
        "readiness": {
            "pit_lineage_ready": True,
            "explicit_missingness_preserved": True,
            "first_market_byte_within_one_preparatory_step": True,
        },
        "feature": {
            "feature_id": PIT_FEATURE_ID,
            "availability_class": "PIT_READY",
            "availability_scope": PIT_AVAILABILITY_SCOPE,
            "concept": "token liquidity USD / token market cap USD",
            "entity_scope": "MINT_DECISION_SNAPSHOT",
            "units": "ratio",
            "formula": "liquidity / mcap",
            "fdv_substitution": "forbidden",
        },
        "projection": {
            "candidate_count": len(projected),
            "eligible_count": len(eligible),
            "missing_count": len(missing),
            "row_status_counts": row_status_counts,
            "missing_reason_counts": missing_reason_counts,
            "decision_snapshot_at": decision_snapshot_at,
            "search_observed_at": str(search_manifest["observed_at"]),
            "source_observation_id": SEARCH_OBSERVATION_ID,
            "source_response_sha256": search_hash,
            "rows": projected,
        },
        "source_lineage": {
            "runtime_path": SOURCE_RUNTIME_RELATIVE,
            "runtime_sha256": SOURCE_RUNTIME_SHA256,
            "acceptance_path": SOURCE_ACCEPTANCE_RELATIVE,
            "acceptance_sha256": SOURCE_ACCEPTANCE_SHA256,
            "raw_retention": "A4_OUTSIDE_GIT",
            "historical_provider_calls": _count(runtime.get("provider_requests")),
            "historical_credential_reads": _count(runtime.get("credential_reads")),
        },
        "first_market_byte_basis": first_byte_basis,
        "scientific_family": {
            "family": "EARLY_STRUCTURAL_BACKING",
            "terminal": "CLOSED",
            "reopened": False,
            "source_terminal": ATOM_1_TERMINAL,
        },
        "factory_runner_changed": False,
        "factory_runner": {
            "path": FACTORY_RUNNER_RELATIVE,
            "sha256": FACTORY_RUNNER_SHA256,
        },
        "side_effects": {
            "provider_calls": 0,
            "credential_reads": 0,
            "network_calls": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": [
            "NO_NEW_MARKET_CAPTURE",
            "NO_SCIENTIFIC_HYPOTHESIS_PROMOTION",
            "NO_A5_LIVE_OPERATIONAL_HARDENING",
            "NO_A6_POLICY_CERTIFICATION",
            "NO_RAW_BODY_RECOVERY_FROM_GIT",
            "NO_FACTORY_V1_OPERATIONAL_READY",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_SCIENTIFIC_SHADOW",
            "NO_MICRO_LIVE",
        ],
    }


__all__ = [
    "ATOM_1_ID",
    "ATOM_1_TERMINAL",
    "FACTORY_RUNNER_SHA256",
    "PIT_AVAILABILITY_SCOPE",
    "PIT_FEATURE_ID",
    "PIT_TERMINAL",
    "PitCanonicalizationError",
    "canonicalize_from_repository",
    "project_candidate",
]
