"""Bounded TASK-25 R2 outcome projection over tracked TASK-23 evidence.

The reader is intentionally exact-path and content-addressed.  It never scans raw
R2 roots and never discovers or opens R3 paths or values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


TASK_ID = "TASK-25"
ATOM_ID = "T25-A4_BOUNDED_R2_OUTCOME_PROJECTION_AND_READ_RECEIPT_V1"
ENGINE_VERSION = "task25-r2-outcome-projection-v1"
EVALUATION_CUTOFF_AT = "2026-08-01T13:11:54.057142Z"
PRE_READ_PATH = PurePosixPath(
    "docs/evidence/task25/a4_r2_outcome_pre_read_manifest_v1.json"
)
PRE_READ_SHA256 = "647d2c769762a6f08fd767436799604a8fdc53e70f181d895e1c82ecb6bae565"
PROJECTION_PATH = PurePosixPath(
    "docs/evidence/task25/a4_r2_outcome_projection_v1.json"
)
RECEIPT_PATH = PurePosixPath(
    "docs/evidence/task25/"
    "a4_bounded_r2_outcome_projection_and_read_receipt_v1.json"
)
MANAGED_WRITE_SET = (
    PRE_READ_PATH.as_posix(),
    "src/solana_alpha_lab/task25_r2_outcome_projection.py",
    "tests/test_task25_r2_outcome_projection.py",
    PROJECTION_PATH.as_posix(),
    RECEIPT_PATH.as_posix(),
)

EXPECTED_INPUTS = {
    "panel_inventory_v1.csv": {
        "path": PurePosixPath(
            "docs/evidence/task23/a3_projection_v1_attempt_02/"
            "panel_inventory_v1.csv"
        ),
        "sha256": "a623b70543a74c63df41bb45c83074541fa98ac105fdeb611b7e02723014b4ec",
        "bytes": 3638,
        "data_rows": 9,
    },
    "quote_pair_availability_v1.csv": {
        "path": PurePosixPath(
            "docs/evidence/task23/a3_projection_v1_attempt_02/"
            "quote_pair_availability_v1.csv"
        ),
        "sha256": "5b525a9602f32b6c654a9bf87c0a783212046cee8f292d13838e160ec9788273",
        "bytes": 9657,
        "data_rows": 36,
    },
    "panel_diagnostics_v1.csv": {
        "path": PurePosixPath(
            "docs/evidence/task23/a3_projection_v1_attempt_02/"
            "panel_diagnostics_v1.csv"
        ),
        "sha256": "20cefa9332f2074042f9168ef2c1448bcbe8db281f49a55123f84d8389994c4d",
        "bytes": 1657,
        "data_rows": 9,
    },
}

MEMBERS = (
    "T21-WATCH-29e2b75994975253bd74",
    "T21-WATCH-61ce24fc3fa04e3eaba7",
    "T21-WATCH-6f21dec76d05f5831216",
)
PANELS = ("P0", "P1", "P2")
NOTIONALS = (10, 25, 50, 100)
QUOTE_STATES = {
    "QUOTE_AVAILABLE",
    "NO_ROUTE",
    "PROVIDER_ERROR",
    "INVALID_RESPONSE",
    "TIMEOUT",
    "SELL_NOT_ATTEMPTED",
    "CAPTURE_STOPPED",
    "PANEL_MISSING",
}
FAILURE_STATES = {
    "PROVIDER_ERROR",
    "INVALID_RESPONSE",
    "TIMEOUT",
    "SELL_NOT_ATTEMPTED",
    "CAPTURE_STOPPED",
    "PANEL_MISSING",
}


class Task25R2ProjectionError(ValueError):
    """Raised when the bounded read or projection contract is violated."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task25R2ProjectionError(code)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _parse_time(value: str) -> datetime:
    _require(bool(value), "timestamp_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task25R2ProjectionError("timestamp_invalid") from exc
    _require(parsed.tzinfo is not None, "timestamp_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _decimal(value: str, code: str) -> Decimal:
    _require(value != "", code)
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise Task25R2ProjectionError(code) from exc
    _require(parsed.is_finite(), code)
    return parsed


def _decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), "f")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Task25R2ProjectionError(f"json_unreadable:{path.name}") from exc
    _require(isinstance(value, dict), f"json_root_invalid:{path.name}")
    return value


def _safe_repo_path(repo_root: Path, relative: PurePosixPath) -> Path:
    _require(not relative.is_absolute(), "absolute_input_path_forbidden")
    candidate = (repo_root / relative).resolve()
    root = repo_root.resolve()
    _require(candidate.is_relative_to(root), "input_outside_repository")
    return candidate


def validate_pre_read_manifest(repo_root: Path) -> dict[str, Any]:
    path = _safe_repo_path(repo_root, PRE_READ_PATH)
    _require(path.is_file(), "pre_read_manifest_missing")
    _require(sha256_file(path) == PRE_READ_SHA256, "pre_read_manifest_hash_drift")
    manifest = _load_json(path)
    _require(
        manifest.get("status") == "SEALED_BEFORE_R2_DERIVED_VALUE_READ",
        "pre_read_manifest_not_sealed",
    )
    authority = manifest.get("authority", {})
    _require(
        authority.get("access_surface")
        == "TRACKED_CONTENT_ADDRESSED_TASK23_R2_PROJECTION_ONLY",
        "read_surface_drift",
    )
    _require(authority.get("r2_derived_value_files_max") == 3, "r2_file_cap_drift")
    _require(authority.get("raw_r2_value_files_reopened_max") == 0, "raw_r2_cap_drift")
    _require(authority.get("r3_path_discovery") is False, "r3_path_authority_forbidden")
    _require(authority.get("r3_value_read") is False, "r3_value_authority_forbidden")
    for zero_field in (
        "provider_calls",
        "network_calls",
        "dependencies_added",
        "sources_changed",
        "entity_graph_values_read",
    ):
        _require(authority.get(zero_field) == 0, f"authority_broadened:{zero_field}")
    _require(authority.get("catalog_mutation") is False, "catalog_authority_broadened")
    assertions = manifest.get("seal_assertions", {})
    _require(assertions.get("receipt_written_before_value_open") is True, "pre_read_order_unsealed")
    _require(assertions.get("r2_derived_value_files_opened_before_seal") == 0, "pre_read_value_opened")
    _require(assertions.get("raw_r2_value_files_opened_before_seal") == 0, "pre_read_raw_opened")
    _require(assertions.get("r3_paths_or_values_opened_before_seal") == 0, "pre_read_r3_opened")
    _require(
        tuple(manifest.get("managed_write_set", [])) == MANAGED_WRITE_SET,
        "managed_write_set_drift",
    )

    prerequisites = manifest.get("prerequisite_bindings", [])
    _require(len(prerequisites) == 5, "prerequisite_binding_count_drift")
    for binding in prerequisites:
        relative = PurePosixPath(binding["path"])
        _require(
            relative.as_posix().startswith("docs/evidence/"),
            "prerequisite_path_outside_evidence",
        )
        prerequisite = _safe_repo_path(repo_root, relative)
        _require(prerequisite.is_file(), f"prerequisite_missing:{binding['role']}")
        _require(
            sha256_file(prerequisite) == binding["sha256"],
            f"prerequisite_hash_drift:{binding['role']}",
        )

    declared = manifest.get("permitted_value_inputs", [])
    _require(len(declared) == 3, "permitted_input_count_drift")
    by_name = {PurePosixPath(item["path"]).name: item for item in declared}
    _require(set(by_name) == set(EXPECTED_INPUTS), "permitted_input_set_drift")
    for name, expected in EXPECTED_INPUTS.items():
        item = by_name[name]
        _require(item["path"] == expected["path"].as_posix(), f"input_path_drift:{name}")
        for field in ("sha256", "bytes", "data_rows"):
            _require(item[field] == expected[field], f"input_{field}_drift:{name}")
        _require(bool(item.get("permitted_columns")), f"permitted_columns_missing:{name}")
    return manifest


def _read_exact_csv(
    repo_root: Path,
    manifest_item: Mapping[str, Any],
) -> list[dict[str, str]]:
    relative = PurePosixPath(str(manifest_item["path"]))
    _require(
        relative.as_posix().startswith(
            "docs/evidence/task23/a3_projection_v1_attempt_02/"
        ),
        "untracked_or_unbounded_value_path",
    )
    path = _safe_repo_path(repo_root, relative)
    _require(path.is_file(), f"value_input_missing:{path.name}")
    payload = path.read_bytes()
    _require(len(payload) == manifest_item["bytes"], f"value_input_size_drift:{path.name}")
    _require(
        sha256_bytes(payload) == manifest_item["sha256"],
        f"value_input_hash_drift:{path.name}",
    )
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise Task25R2ProjectionError(f"value_input_csv_invalid:{path.name}") from exc
    _require(
        reader.fieldnames == list(manifest_item["permitted_columns"]),
        f"value_input_columns_drift:{path.name}",
    )
    _require(len(rows) == manifest_item["data_rows"], f"value_input_rows_drift:{path.name}")
    return rows


def load_exact_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    manifest = validate_pre_read_manifest(repo_root)
    rows: dict[str, list[dict[str, str]]] = {}
    for item in manifest["permitted_value_inputs"]:
        name = PurePosixPath(item["path"]).name
        rows[name] = _read_exact_csv(repo_root, item)
    return manifest, rows


def _validate_rows(rows: Mapping[str, Sequence[Mapping[str, str]]]) -> None:
    panels = rows["panel_inventory_v1.csv"]
    pairs = rows["quote_pair_availability_v1.csv"]
    diagnostics = rows["panel_diagnostics_v1.csv"]
    cutoff = _parse_time(EVALUATION_CUTOFF_AT)

    expected_panel_keys = {(member, panel) for member in MEMBERS for panel in PANELS}
    panel_keys = {(row["member_id"], row["panel_id"]) for row in panels}
    diagnostic_keys = {(row["member_id"], row["panel_id"]) for row in diagnostics}
    _require(panel_keys == expected_panel_keys, "panel_population_drift")
    _require(len(panel_keys) == len(panels), "duplicate_panel_row")
    _require(diagnostic_keys == expected_panel_keys, "diagnostic_population_drift")
    _require(len(diagnostic_keys) == len(diagnostics), "duplicate_diagnostic_row")

    expected_pair_keys = {
        (member, panel, str(notional))
        for member in MEMBERS
        for panel in PANELS
        for notional in NOTIONALS
    }
    pair_keys = {
        (row["member_id"], row["panel_id"], row["tested_notional_usd"])
        for row in pairs
    }
    _require(pair_keys == expected_pair_keys, "quote_pair_population_drift")
    _require(len(pair_keys) == len(pairs), "duplicate_quote_pair_row")

    for row in panels:
        _require(row["panel_state"] == "OBSERVED", "panel_not_observed")
        first = _parse_time(row["first_reliable_available_at"])
        last = _parse_time(row["last_reliable_available_at"])
        _require(first <= last <= cutoff, "future_panel_row_for_cutoff")
        _require(row["raw_path"].startswith("local/task21_forward/final_cohort/r2/"), "r2_lineage_path_invalid")
        _require(len(row["raw_sha256"]) == 64, "r2_lineage_hash_invalid")
        _decimal(row["actual_elapsed_from_member_p0_seconds"], "elapsed_missing")

    for row in diagnostics:
        _require(row["inference_mode"] == "DESCRIPTIVE_ONLY", "inference_mode_broadened")
        _require(row["cluster_id"] == "T21-R2-SINGLE-NOMINATION-CLUSTER", "cluster_identity_drift")
        _require(int(row["planned_buy_legs"]) == 4, "planned_buy_leg_drift")

    for row in pairs:
        _require(row["buy_status"] in QUOTE_STATES, "buy_status_invalid")
        _require(row["sell_status"] in QUOTE_STATES, "sell_status_invalid")
        _require(row["buy_input_atomic"] == str(int(row["tested_notional_usd"]) * 1_000_000), "buy_atomic_notional_mismatch")
        buy_time = _parse_time(row["buy_first_reliable_available_at"])
        _require(buy_time <= cutoff, "future_buy_quote_for_cutoff")
        if row["sell_status"] == "QUOTE_AVAILABLE":
            sell_time = _parse_time(row["sell_first_reliable_available_at"])
            _require(buy_time <= sell_time <= cutoff, "future_or_reversed_sell_quote")
            _decimal(row["roundtrip_quote_retention_bps"], "pair_retention_missing")
        else:
            _require(row["roundtrip_quote_retention_bps"] == "", "failed_sell_retention_forbidden")


def _route_assessment(observed_state: str) -> str:
    _require(observed_state in QUOTE_STATES, "quote_state_invalid")
    if observed_state == "NO_ROUTE":
        return "REFUTED"
    if observed_state in FAILURE_STATES:
        return "UNKNOWN"
    # QUOTE_AVAILABLE alone is insufficient here: the tracked TASK-23 table did
    # not retain exact output mint/inventory atomic identity or the full frozen
    # freshness/latency block required by the A2 contract.
    return "UNKNOWN"


def _base_outcome(
    *,
    record_id: str,
    member_id: str,
    panel_id: str,
    label: str,
    assessment: str,
    evidence_basis: str,
    claim_scope: str,
    value_decimal: str | None,
    unit: str | None,
    available_at: str,
    source_sha256: str,
    quality_flags: Sequence[str],
    observed_measures: Mapping[str, Any],
    tested_notional_usd: int | None = None,
    route_state_observed: str = "NOT_APPLICABLE",
    path_state: str = "NOT_APPLICABLE",
) -> dict[str, Any]:
    if assessment == "UNKNOWN":
        _require(value_decimal is None and unit is None, "unknown_coerced_to_value")
    return {
        "record_id": record_id,
        "member_id": member_id,
        "panel_id": panel_id,
        "tested_notional_usd": tested_notional_usd,
        "label": label,
        "assessment": assessment,
        "evidence_basis": evidence_basis,
        "claim_scope": claim_scope,
        "value_decimal": value_decimal,
        "unit": unit,
        "route_state_observed": route_state_observed,
        "fill_state": "ACTUAL_FILLS_NOT_OBSERVED" if label in {"FILLABLE", "QUOTE_EXIT", "REALIZED_VWAP"} else "NOT_APPLICABLE",
        "cashflow_state": "CASHFLOW_NOT_OBSERVED" if label == "NET" else "NOT_APPLICABLE",
        "path_state": path_state,
        "first_reliable_available_at": available_at,
        "source_scope": "T21_R2_DEVELOPMENT",
        "source_content_sha256": source_sha256,
        "quality_flags": sorted(set(quality_flags)),
        "observed_measures": dict(observed_measures),
    }


def build_projection_from_rows(
    manifest: Mapping[str, Any],
    input_rows: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    rows = deepcopy(input_rows)
    _validate_rows(rows)
    panels = {
        (row["member_id"], row["panel_id"]): row
        for row in rows["panel_inventory_v1.csv"]
    }
    diagnostics = {
        (row["member_id"], row["panel_id"]): row
        for row in rows["panel_diagnostics_v1.csv"]
    }
    pairs = {
        (row["member_id"], row["panel_id"], int(row["tested_notional_usd"])): row
        for row in rows["quote_pair_availability_v1.csv"]
    }
    baselines = {
        (member, notional): _decimal(
            pairs[(member, "P0", notional)]["roundtrip_quote_retention_bps"],
            "p0_retention_missing",
        )
        for member in MEMBERS
        for notional in NOTIONALS
    }

    outcomes: list[dict[str, Any]] = []
    counter = 0

    def add(**values: Any) -> None:
        nonlocal counter
        counter += 1
        values["record_id"] = f"T25-R2-{counter:04d}"
        outcomes.append(_base_outcome(**values))

    for member in MEMBERS:
        for panel_id in PANELS:
            panel = panels[(member, panel_id)]
            diagnostic = diagnostics[(member, panel_id)]
            available_at = panel["last_reliable_available_at"]
            source_sha = panel["raw_sha256"]
            common_measures = {
                "actual_elapsed_from_member_p0_seconds": panel[
                    "actual_elapsed_from_member_p0_seconds"
                ],
                "panel_state": panel["panel_state"],
            }
            add(
                member_id=member,
                panel_id=panel_id,
                label="TOUCH",
                assessment="UNKNOWN",
                evidence_basis="DISCRETE_PANEL_GRID",
                claim_scope="TOUCH_WITHIN_HORIZON",
                value_decimal=None,
                unit=None,
                available_at=available_at,
                source_sha256=source_sha,
                path_state="SPARSE_DISCRETE",
                quality_flags=(
                    "NO_FROZEN_REFERENCE_THRESHOLD_IN_TRACKED_PROJECTION",
                    "NO_OBSERVED_THRESHOLD_CROSS_FIELD",
                    "SPARSE_PANEL",
                ),
                observed_measures=common_measures,
            )

            for notional in NOTIONALS:
                pair = pairs[(member, panel_id, notional)]
                buy_assessment = _route_assessment(pair["buy_status"])
                add(
                    member_id=member,
                    panel_id=panel_id,
                    tested_notional_usd=notional,
                    label="FILLABLE",
                    assessment=buy_assessment,
                    evidence_basis="CONTEMPORANEOUS_QUOTE",
                    claim_scope="POINT_IN_TIME_QUOTE",
                    value_decimal=None,
                    unit=None,
                    available_at=pair["buy_first_reliable_available_at"],
                    source_sha256=source_sha,
                    route_state_observed=pair["buy_status"],
                    quality_flags=(
                        "BUY_QUOTE_STATE_OBSERVED",
                        "EXACT_OUTPUT_MINT_AND_FRESHNESS_BLOCK_NOT_RETAINED",
                        "QUOTE_IS_NOT_FILL",
                    ),
                    observed_measures={
                        **common_measures,
                        "buy_input_atomic": pair["buy_input_atomic"],
                        "buy_price_impact_pct": pair["buy_price_impact_pct"],
                        "buy_route_count": pair["buy_route_count"],
                    },
                )
                sell_assessment = _route_assessment(pair["sell_status"])
                add(
                    member_id=member,
                    panel_id=panel_id,
                    tested_notional_usd=notional,
                    label="QUOTE_EXIT",
                    assessment=sell_assessment,
                    evidence_basis="CONTEMPORANEOUS_QUOTE",
                    claim_scope="POINT_IN_TIME_QUOTE",
                    value_decimal=None,
                    unit=None,
                    available_at=(
                        pair["sell_first_reliable_available_at"]
                        or pair["buy_first_reliable_available_at"]
                    ),
                    source_sha256=source_sha,
                    route_state_observed=pair["sell_status"],
                    path_state="UNOBSERVED",
                    quality_flags=(
                        "DEPENDENT_SELL_QUOTE_STATE_OBSERVED",
                        "EXACT_SELL_INVENTORY_ATOMIC_IDENTITY_NOT_RETAINED",
                        "EXACT_FRESHNESS_BLOCK_NOT_RETAINED",
                        "QUOTE_EXIT_IS_NOT_LIQUIDATION",
                    ),
                    observed_measures={
                        **common_measures,
                        "roundtrip_quote_retention_bps": (
                            pair["roundtrip_quote_retention_bps"] or None
                        ),
                        "sell_route_count": pair["sell_route_count"],
                    },
                )

            add(
                member_id=member,
                panel_id=panel_id,
                label="REALIZED_VWAP",
                assessment="UNKNOWN",
                evidence_basis="NONE",
                claim_scope="ACTUAL_FILL_SERIES",
                value_decimal=None,
                unit=None,
                available_at=available_at,
                source_sha256=source_sha,
                quality_flags=(
                    "ACTUAL_FILLS_NOT_OBSERVED",
                    "QUOTE_RETENTION_IS_NOT_REALIZED_VWAP",
                ),
                observed_measures=common_measures,
            )
            add(
                member_id=member,
                panel_id=panel_id,
                label="NET",
                assessment="UNKNOWN",
                evidence_basis="NONE",
                claim_scope="SETTLED_CASHFLOW",
                value_decimal=None,
                unit=None,
                available_at=available_at,
                source_sha256=source_sha,
                quality_flags=(
                    "SETTLED_CASHFLOW_NOT_OBSERVED",
                    "TASK26_FEE_AND_CASHFLOW_MODEL_NOT_AVAILABLE",
                ),
                observed_measures=common_measures,
            )

            current_retention = {
                notional: _decimal(
                    pairs[(member, panel_id, notional)][
                        "roundtrip_quote_retention_bps"
                    ],
                    "pair_retention_missing",
                )
                for notional in NOTIONALS
            }
            adverse = max(
                max(Decimal("0"), baselines[(member, notional)] - value)
                for notional, value in current_retention.items()
            ) / Decimal("10000")
            worst_return = min(current_retention.values()) / Decimal("10000") - Decimal("1")
            add(
                member_id=member,
                panel_id=panel_id,
                label="PATH_RISK",
                assessment="SUPPORTED",
                evidence_basis="DISCRETE_PANEL_GRID",
                claim_scope="DISCRETE_PATH_GRID",
                value_decimal=_decimal_text(adverse),
                unit="RETURN_DECIMAL",
                available_at=available_at,
                source_sha256=source_sha,
                path_state="SPARSE_DISCRETE",
                quality_flags=(
                    "ACTUAL_SPARSE_PANEL_TIMES",
                    "CONTINUOUS_MAE_MFE_FORBIDDEN",
                    "QUOTE_IMPLIED_NOT_REALIZED",
                    "WORST_NOTIONAL_DETERIORATION_FROM_MEMBER_P0",
                ),
                observed_measures={
                    **common_measures,
                    "notionals_usd": list(NOTIONALS),
                    "quote_notional_capacity_proxy_usd": diagnostic[
                        "quote_notional_capacity_proxy_usd"
                    ],
                    "worst_observed_roundtrip_quote_return_decimal": _decimal_text(
                        worst_return
                    ),
                },
            )

    _require(len(outcomes) == 108, "outcome_denominator_drift")
    labels = Counter(row["label"] for row in outcomes)
    assessments = Counter(row["assessment"] for row in outcomes)
    _require(labels == Counter({"FILLABLE": 36, "QUOTE_EXIT": 36, "TOUCH": 9, "REALIZED_VWAP": 9, "NET": 9, "PATH_RISK": 9}), "label_denominator_drift")
    _require(assessments == Counter({"UNKNOWN": 99, "SUPPORTED": 9}), "assessment_denominator_drift")

    inputs = [
        {
            "path": item["path"],
            "sha256": item["sha256"],
            "bytes": item["bytes"],
            "data_rows": item["data_rows"],
        }
        for item in manifest["permitted_value_inputs"]
    ]
    return {
        "schema": "smial.task25.r2-outcome-projection",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "engine_version": ENGINE_VERSION,
        "status": "PASS_BOUNDED_R2_DEVELOPMENT_WITH_LIMITATIONS",
        "evaluation_cutoff_at": EVALUATION_CUTOFF_AT,
        "dataset_identity": dict(manifest["dataset_identity"]),
        "input_bindings": {
            "pre_read_manifest": {
                "path": PRE_READ_PATH.as_posix(),
                "sha256": PRE_READ_SHA256,
            },
            "r2_derived_value_inputs": inputs,
        },
        "summary": {
            "members": 3,
            "panels": 9,
            "quote_pairs": 36,
            "outcomes_input": 108,
            "outcomes_output": 108,
            "outcomes_dropped": 0,
            "labels": dict(sorted(labels.items())),
            "assessments": dict(sorted(assessments.items())),
            "observed_buy_quote_available": sum(
                row["buy_status"] == "QUOTE_AVAILABLE"
                for row in rows["quote_pair_availability_v1.csv"]
            ),
            "observed_sell_quote_available": sum(
                row["sell_status"] == "QUOTE_AVAILABLE"
                for row in rows["quote_pair_availability_v1.csv"]
            ),
            "fillable_supported": 0,
            "quote_exit_supported": 0,
            "realized_vwap_supported": 0,
            "net_supported": 0,
            "path_risk_discrete_supported": 9,
            "unknown_values_coerced_to_zero": 0,
            "future_rows_consumed": 0,
            "raw_r2_value_files_reopened": 0,
            "r3_paths_or_values_read": 0,
            "entity_graph_values_read": 0,
        },
        "outcomes": outcomes,
        "claims": [
            "R2_TRACKED_PROJECTION_READ_IS_CONTENT_ADDRESSED_AND_PIT_BOUNDED",
            "DISCRETE_QUOTE_IMPLIED_PATH_RISK_AVAILABLE_FOR_NINE_MEMBER_PANELS",
            "OBSERVED_QUOTE_AVAILABLE_STATE_RETAINED_WITHOUT_FILLABILITY_UPGRADE",
        ],
        "prohibited_claims": [
            "CONTINUOUS_TOUCH",
            "EXACT_NOMINAL_HORIZON",
            "FILL_OR_SETTLEMENT",
            "REALIZED_VWAP",
            "NET_RETURN",
            "OWNER_CASHFLOW",
            "CONTINUOUS_MAE_MFE",
            "GENERALIZATION_OR_ALPHA",
            "R3_HOLDOUT_RESULT",
        ],
        "limitations": [
            "TRACKED_TASK23_PROJECTION_OMITS_EXACT_OUTPUT_MINT_AND_SELL_INVENTORY_ATOMIC_IDENTITY",
            "TRACKED_TASK23_PROJECTION_OMITS_FULL_FRESHNESS_LATENCY_AND_PIT_TIMESTAMP_BLOCK",
            "FILLABLE_AND_QUOTE_EXIT_REMAIN_UNKNOWN_DESPITE_OBSERVED_QUOTE_AVAILABLE_STATES",
            "TOUCH_REMAINS_UNKNOWN_WITHOUT_FROZEN_REFERENCE_THRESHOLD_OR_CROSS_FIELD",
            "REALIZED_VWAP_REQUIRES_ACTUAL_RECONCILED_FILLS",
            "NET_REQUIRES_TASK26_SETTLED_CASHFLOW_AND_COST_MODEL",
            "ONE_CAPTURE_CLUSTER_DESCRIPTIVE_ONLY",
        ],
        "next_boundary": {
            "atom": "T25-A5_ADVERSARIAL_ACCEPTANCE_AND_OWNER_DECISION_V1",
            "authorized_by_a4": False,
            "r3_access": "DENY",
        },
    }


def build_projection(repo_root: Path) -> dict[str, Any]:
    manifest, rows = load_exact_inputs(repo_root)
    return build_projection_from_rows(manifest, rows)


def build_receipt(repo_root: Path, projection: Mapping[str, Any]) -> dict[str, Any]:
    holdout_path = repo_root / "docs/evidence/task22/holdout_access_ledger_v2.json"
    _require(
        sha256_file(holdout_path)
        == "2282e5d1eac09a0ce940a5700f04b03ff4d75fc9cd4d65e08e5fe7deda88ca51",
        "holdout_ledger_hash_drift",
    )
    holdout = _load_json(holdout_path)
    _require(holdout.get("records") == [], "holdout_ledger_not_empty")
    summary = projection["summary"]
    checks = [
        ("PRE_READ_MANIFEST_SEALED_FIRST", True),
        ("EXACT_TRACKED_R2_INPUT_SET", len(projection["input_bindings"]["r2_derived_value_inputs"]) == 3),
        ("OUTCOME_DENOMINATOR_EXACT", summary["outcomes_output"] == 108 and summary["outcomes_dropped"] == 0),
        ("MISSING_NOT_COERCED_TO_ZERO", summary["unknown_values_coerced_to_zero"] == 0),
        ("QUOTE_NOT_UPGRADED_TO_FILL_OR_SETTLEMENT", summary["fillable_supported"] == 0 and summary["quote_exit_supported"] == 0),
        ("REALIZED_VWAP_AND_NET_UNKNOWN", summary["realized_vwap_supported"] == 0 and summary["net_supported"] == 0),
        ("PATH_RISK_DISCRETE_ONLY", summary["path_risk_discrete_supported"] == 9),
        ("FUTURE_ROWS_REJECTED", summary["future_rows_consumed"] == 0),
        ("RAW_R2_NOT_REOPENED", summary["raw_r2_value_files_reopened"] == 0),
        ("R3_UNTOUCHED", summary["r3_paths_or_values_read"] == 0 and holdout.get("records") == []),
    ]
    _require(all(passed for _, passed in checks), "acceptance_check_failed")
    return {
        "schema": "smial.task25.r2-outcome-projection-read-receipt",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS_WITH_EXPLICIT_PROJECTION_LIMITATIONS",
        "pre_read_manifest": {
            "path": PRE_READ_PATH.as_posix(),
            "sha256": PRE_READ_SHA256,
            "sealed_before_value_read": True,
        },
        "value_read_receipt": {
            "access_surface": "TRACKED_CONTENT_ADDRESSED_TASK23_R2_PROJECTION_ONLY",
            "distinct_r2_derived_value_files_opened": 3,
            "raw_r2_value_files_opened": 0,
            "r3_paths_discovered": 0,
            "r3_value_files_opened": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "inputs": projection["input_bindings"]["r2_derived_value_inputs"],
        },
        "projection": {
            "path": PROJECTION_PATH.as_posix(),
            "sha256": sha256_bytes(canonical_json_bytes(projection)),
            "summary": dict(summary),
        },
        "checks": [
            {"check_id": check_id, "status": "PASS"}
            for check_id, _ in checks
        ],
        "holdout_boundary": {
            "ledger_path": "docs/evidence/task22/holdout_access_ledger_v2.json",
            "ledger_sha256": "2282e5d1eac09a0ce940a5700f04b03ff4d75fc9cd4d65e08e5fe7deda88ca51",
            "records": 0,
            "state": "UNTOUCHED",
            "r3_paths_or_values_read": 0,
        },
        "implementation": {
            "module": {
                "path": "src/solana_alpha_lab/task25_r2_outcome_projection.py",
                "sha256": sha256_file(repo_root / "src/solana_alpha_lab/task25_r2_outcome_projection.py"),
            },
            "tests": {
                "path": "tests/test_task25_r2_outcome_projection.py",
                "sha256": sha256_file(repo_root / "tests/test_task25_r2_outcome_projection.py"),
            },
        },
        "side_effects": {
            "provider_api_rpc_wss_calls": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_or_credits_spent": 0,
            "dependencies_added": 0,
            "sources_changed": 0,
            "catalog_changed": 0,
            "commit_push_pr_merge_actions": 0,
        },
        "next_boundary": dict(projection["next_boundary"]),
    }


def build_outputs(repo_root: Path) -> tuple[bytes, bytes]:
    projection = build_projection(repo_root)
    receipt = build_receipt(repo_root, projection)
    return canonical_json_bytes(projection), canonical_json_bytes(receipt)


def check_stored_outputs(repo_root: Path) -> dict[str, str]:
    projection_bytes, receipt_bytes = build_outputs(repo_root)
    expected = {PROJECTION_PATH: projection_bytes, RECEIPT_PATH: receipt_bytes}
    hashes: dict[str, str] = {}
    for relative, payload in expected.items():
        path = _safe_repo_path(repo_root, relative)
        _require(path.is_file(), f"stored_output_missing:{relative.name}")
        _require(path.read_bytes() == payload, f"stored_output_drift:{relative.name}")
        hashes[relative.as_posix()] = sha256_bytes(payload)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        choices=("projection", "receipt", "hashes", "check", "write"),
        default="check",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    projection_bytes, receipt_bytes = build_outputs(repo_root)
    if args.artifact == "projection":
        print(projection_bytes.decode("utf-8"), end="")
    elif args.artifact == "receipt":
        print(receipt_bytes.decode("utf-8"), end="")
    elif args.artifact == "hashes":
        print(
            json.dumps(
                {
                    PROJECTION_PATH.as_posix(): sha256_bytes(projection_bytes),
                    RECEIPT_PATH.as_posix(): sha256_bytes(receipt_bytes),
                },
                sort_keys=True,
            )
        )
    elif args.artifact == "write":
        for relative, payload in (
            (PROJECTION_PATH, projection_bytes),
            (RECEIPT_PATH, receipt_bytes),
        ):
            path = _safe_repo_path(repo_root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        print("WROTE_A4_OUTPUTS")
    else:
        print(json.dumps(check_stored_outputs(repo_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
