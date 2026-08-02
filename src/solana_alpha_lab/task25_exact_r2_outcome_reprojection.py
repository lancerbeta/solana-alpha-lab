"""Exact, bounded R2 reprojection for TASK-25 A5R1.

Raw values are opened only by ``raw-write``/``raw-check`` after validating the
sealed pre-read manifest.  The default ``check`` path is CI-portable and uses
only tracked, content-addressed outputs plus a synthetic transformation fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from . import task23_diagnostic_projection as task23
from .contracts.schema_v1 import QuoteAttempt, RawApiEvent


TASK_ID = "TASK-25"
ATOM_ID = "T25-A5R1_EXACT_R2_OUTCOME_SURFACE_REPROJECTION_V1"
ENGINE_VERSION = "task25-exact-r2-outcome-reprojection-v1"
PRE_READ_PATH = PurePosixPath(
    "docs/evidence/task25/a5r1_exact_r2_pre_read_manifest_v1.json"
)
PRE_READ_SHA256 = "ba6a2b8b8af550ce613860a250fc5e1be57109d89bb76dbb21644da1b96f3fc2"
SURFACE_PATH = PurePosixPath(
    "docs/evidence/task25/a5r1_exact_r2_outcome_surface_v1.json"
)
ACCEPTANCE_PATH = PurePosixPath(
    "docs/evidence/task25/a5r1_exact_r2_outcome_reprojection_acceptance_v1.json"
)
SYNTHETIC_FIXTURE_PATH = PurePosixPath(
    "tests/fixtures/task25/a5r1_exact_r2_quote_fixture_v1.json"
)
TEST_PATH = PurePosixPath("tests/test_task25_exact_r2_outcome_reprojection.py")
MODULE_PATH = PurePosixPath(
    "src/solana_alpha_lab/task25_exact_r2_outcome_reprojection.py"
)

MEMBERS = (
    "T21-WATCH-29e2b75994975253bd74",
    "T21-WATCH-61ce24fc3fa04e3eaba7",
    "T21-WATCH-6f21dec76d05f5831216",
)
PANELS = ("P0", "P1", "P2")
NOTIONALS = ((10, 10_000_000), (25, 25_000_000), (50, 50_000_000), (100, 100_000_000))
EXPECTED_LABELS = Counter(
    {
        "FILLABLE": 36,
        "QUOTE_EXIT": 36,
        "TOUCH": 9,
        "REALIZED_VWAP": 9,
        "NET": 9,
        "PATH_RISK": 9,
    }
)
FAILURE_STATES = {"PROVIDER_ERROR", "INVALID_RESPONSE", "TIMEOUT"}


class Task25ExactR2ReprojectionError(ValueError):
    """Raised when exact R2 scope, lineage, PIT, or label truth drifts."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task25ExactR2ReprojectionError(code)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _safe_path(repo_root: Path, relative: str | PurePosixPath) -> Path:
    rel = PurePosixPath(str(relative))
    _require(not rel.is_absolute(), "absolute_path_forbidden")
    root = repo_root.resolve()
    candidate = (root / rel).resolve()
    _require(candidate.is_relative_to(root), "path_outside_repository")
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Task25ExactR2ReprojectionError(f"json_unreadable:{path.name}") from exc
    _require(isinstance(value, dict), f"json_root_invalid:{path.name}")
    return value


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _as_utc_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    _require(value.tzinfo is not None and value.utcoffset() is not None, "timestamp_timezone_missing")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task25ExactR2ReprojectionError("timestamp_invalid") from exc
    _require(parsed.tzinfo is not None, "timestamp_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _decimal(value: Any, code: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise Task25ExactR2ReprojectionError(code) from exc
    _require(parsed.is_finite(), code)
    return parsed


def _decimal_text(value: Decimal, places: str = "0.000000000000") -> str:
    return format(value.quantize(Decimal(places), rounding=ROUND_HALF_UP), "f")


def _regular_file_metadata(path: Path) -> tuple[int, bool]:
    info = path.stat()
    return info.st_size, stat.S_ISREG(info.st_mode) and not path.is_symlink()


def validate_pre_read_manifest(
    repo_root: Path, *, require_raw_metadata: bool = False
) -> dict[str, Any]:
    path = _safe_path(repo_root, PRE_READ_PATH)
    _require(path.is_file(), "pre_read_manifest_missing")
    _require(sha256_file(path) == PRE_READ_SHA256, "pre_read_manifest_hash_drift")
    manifest = _load_json(path)
    _require(manifest.get("status") == "SEALED_BEFORE_EXACT_R2_VALUE_REOPEN", "pre_read_manifest_not_sealed")
    authority = manifest.get("authority", {})
    _require(authority.get("raw_r2_value_files_max") == 9, "raw_file_cap_drift")
    _require(authority.get("raw_r2_total_bytes_max") == 392234, "raw_byte_cap_drift")
    _require(authority.get("raw_r2_total_lines_expected") == 72, "raw_line_cap_drift")
    _require(authority.get("r3_path_discovery") is False, "r3_path_authority_forbidden")
    _require(authority.get("r3_value_read") is False, "r3_value_authority_forbidden")
    for key in (
        "provider_calls",
        "network_calls",
        "dependencies_added",
        "sources_changed",
        "entity_graph_values_read",
    ):
        _require(authority.get(key) == 0, f"authority_broadened:{key}")
    _require(authority.get("new_collection") is False, "new_collection_forbidden")
    _require(authority.get("catalog_mutation") is False, "catalog_authority_forbidden")

    policy = manifest.get("classification_policy", {})
    _require(policy.get("latency_budget_ms") == 1000, "latency_budget_drift")
    _require(policy.get("freshness_max_age_ms") == 5000, "freshness_limit_drift")
    _require(policy.get("scope") == "R2_DEVELOPMENT_ONLY_NOT_LIVE_SLA_OR_STRATEGY_AUTHORITY", "classification_scope_drift")

    managed = manifest.get("managed_write_set", [])
    _require(
        managed
        == [
            PRE_READ_PATH.as_posix(),
            MODULE_PATH.as_posix(),
            SYNTHETIC_FIXTURE_PATH.as_posix(),
            TEST_PATH.as_posix(),
            SURFACE_PATH.as_posix(),
            ACCEPTANCE_PATH.as_posix(),
        ],
        "managed_write_set_drift",
    )
    delivery = manifest.get("delivery_contract", {})
    _require(delivery.get("ci_tests_must_not_require_local_or_ignored_raw") is True, "ci_portability_contract_missing")
    _require(delivery.get("decision_critical_missing_raw_skip_allowed") is False, "raw_skip_authorized")

    prerequisites = manifest.get("prerequisite_bindings", [])
    _require(len(prerequisites) == 9, "prerequisite_count_drift")
    for item in prerequisites:
        prerequisite = _safe_path(repo_root, item["path"])
        _require(prerequisite.is_file(), f"prerequisite_missing:{item['role']}")
        _require(sha256_file(prerequisite) == item["sha256"], f"prerequisite_hash_drift:{item['role']}")

    raw_inputs = manifest.get("raw_inputs", [])
    _require(len(raw_inputs) == 9, "raw_input_count_drift")
    _require(sum(int(item["bytes"]) for item in raw_inputs) == 392234, "raw_input_bytes_drift")
    _require(sum(int(item["line_count"]) for item in raw_inputs) == 72, "raw_input_lines_drift")
    for item in raw_inputs:
        relative = PurePosixPath(item["path"])
        _require(relative.name == "raw_events.jsonl", "raw_filename_not_allowed")
        _require(relative.as_posix().startswith("local/task21_forward/final_cohort/r2/"), "raw_path_outside_r2")
        if require_raw_metadata:
            raw_path = _safe_path(repo_root, relative)
            _require(raw_path.exists(), f"raw_input_missing:{item['sha256']}")
            size, regular = _regular_file_metadata(raw_path)
            _require(regular, "raw_input_not_regular_file")
            _require(
                size == item["bytes"],
                f"raw_input_metadata_size_drift:{item['sha256']}",
            )

    assertions = manifest.get("seal_assertions", {})
    _require(assertions.get("receipt_written_before_raw_value_reopen") is True, "pre_read_order_not_sealed")
    _require(assertions.get("raw_files_opened_before_this_seal") == 0, "pre_seal_raw_opened")
    _require(assertions.get("r3_paths_or_values_opened_before_this_seal") == 0, "pre_seal_r3_opened")
    return manifest


def classify_quote(
    *,
    status: str,
    quote_age_ms: int | None,
    provider_latency_ms: int | None,
    exact_identity: bool,
    pit_valid: bool,
    latency_budget_ms: int = 1000,
    freshness_max_age_ms: int = 5000,
) -> tuple[str, str]:
    if status == "NO_ROUTE":
        return "REFUTED", "EXPLICIT_NO_ROUTE"
    if status in FAILURE_STATES:
        return "UNKNOWN", "PROVIDER_FAILURE_NOT_NO_ROUTE"
    _require(status == "QUOTE_AVAILABLE", "quote_status_invalid")
    if not exact_identity:
        return "UNKNOWN", "EXACT_QUOTE_IDENTITY_MISSING"
    if not pit_valid:
        return "UNKNOWN", "PIT_ORDER_OR_CUTOFF_INVALID"
    if quote_age_ms is None:
        return "UNKNOWN", "QUOTE_AGE_UNOBSERVED"
    if provider_latency_ms is None:
        return "UNKNOWN", "PROVIDER_LATENCY_UNOBSERVED"
    if quote_age_ms > freshness_max_age_ms:
        return "UNKNOWN", "QUOTE_FRESHNESS_LIMIT_EXCEEDED"
    if provider_latency_ms > latency_budget_ms:
        return "UNKNOWN", "PROVIDER_LATENCY_LIMIT_EXCEEDED"
    return "SUPPORTED", "EXACT_QUOTE_WITHIN_FROZEN_LIMITS"


def exact_dependent_sell_identity(
    *,
    buy_input_mint: str,
    buy_output_mint: str,
    buy_output_atomic: int,
    buy_output_decimals: int,
    sell_input_mint: str,
    sell_input_atomic: int,
    sell_input_decimals: int,
    sell_output_mint: str,
) -> bool:
    return (
        buy_output_mint == sell_input_mint
        and buy_output_atomic == sell_input_atomic
        and buy_output_decimals == sell_input_decimals
        and buy_input_mint == sell_output_mint
    )


def validate_synthetic_fixture(repo_root: Path) -> dict[str, int]:
    fixture = _load_json(_safe_path(repo_root, SYNTHETIC_FIXTURE_PATH))
    _require(fixture.get("schema") == "smial.task25.exact-r2-quote-synthetic-fixture", "synthetic_fixture_schema_drift")
    policy = fixture.get("classification_policy", {})
    _require(policy == {"latency_budget_ms": 1000, "freshness_max_age_ms": 5000}, "synthetic_policy_drift")
    cases = fixture.get("classification_cases", [])
    _require(len(cases) == 12, "synthetic_classification_case_count_drift")
    for case in cases:
        observed = classify_quote(
            status=case["status"],
            quote_age_ms=case["quote_age_ms"],
            provider_latency_ms=case["provider_latency_ms"],
            exact_identity=case["exact_identity"],
            pit_valid=case["pit_valid"],
        )
        _require(
            observed == (case["expected_assessment"], case["expected_reason"]),
            f"synthetic_classification_mismatch:{case['case_id']}",
        )
    pair_cases = fixture.get("pair_identity_cases", [])
    _require(len(pair_cases) == 2, "synthetic_pair_case_count_drift")
    for case in pair_cases:
        observed = exact_dependent_sell_identity(
            buy_input_mint=case["buy_input_mint"],
            buy_output_mint=case["buy_output_mint"],
            buy_output_atomic=int(case["buy_output_atomic"]),
            buy_output_decimals=int(case["buy_output_decimals"]),
            sell_input_mint=case["sell_input_mint"],
            sell_input_atomic=int(case["sell_input_atomic"]),
            sell_input_decimals=int(case["sell_input_decimals"]),
            sell_output_mint=case["sell_output_mint"],
        )
        _require(observed is case["expected_exact"], f"synthetic_pair_identity_mismatch:{case['case_id']}")
    return {"classification_cases": len(cases), "pair_identity_cases": len(pair_cases)}


def _path_identity(relative: str) -> tuple[str, str]:
    parts = PurePosixPath(relative).parts
    member_parts = [part for part in parts if part.startswith("member=")]
    panel_parts = [part for part in parts if part.startswith("horizon=")]
    _require(len(member_parts) == 1 and len(panel_parts) == 1, "raw_path_identity_missing")
    return member_parts[0].split("=", 1)[1], panel_parts[0].split("=", 1)[1]


def _pit_valid(raw: RawApiEvent, quote: QuoteAttempt, cutoff: datetime) -> bool:
    timestamps = (
        raw.observed_at,
        raw.first_reliable_available_at,
        raw.available_to_strategy_at,
        raw.ingested_at,
    )
    if not (timestamps[0] <= timestamps[1] <= timestamps[2] <= timestamps[3]):
        return False
    if raw.event_time is not None and raw.event_time > raw.observed_at:
        return False
    if raw.available_to_strategy_at > cutoff:
        return False
    if quote.response_at is not None and quote.response_at < quote.requested_at:
        return False
    return (
        raw.first_reliable_available_at == quote.first_reliable_available_at
        and raw.available_to_strategy_at == quote.available_to_strategy_at
        and raw.ingested_at == quote.ingested_at
    )


def _read_raw_input(
    repo_root: Path,
    item: Mapping[str, Any],
    allowed_envelope: set[str],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    path = _safe_path(repo_root, item["path"])
    payload = path.read_bytes()
    _require(len(payload) == item["bytes"], f"raw_size_drift:{item['sha256']}")
    _require(sha256_bytes(payload) == item["sha256"], f"raw_hash_drift:{item['sha256']}")
    lines = [line for line in payload.splitlines() if line]
    _require(len(lines) == item["line_count"], f"raw_line_count_drift:{item['sha256']}")
    expected_member, expected_panel = _path_identity(item["path"])
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Task25ExactR2ReprojectionError(
                f"raw_json_invalid:{item['sha256']}:{line_number}"
            ) from exc
        _require(isinstance(envelope, dict), "raw_envelope_not_mapping")
        _require(set(envelope).issubset(allowed_envelope | {"raw_event", "quote_attempt"}), "raw_envelope_unallowlisted_field")
        _require(envelope.get("schema") == "smial.task21.forward-quote-panel-raw", "raw_schema_drift")
        _require(envelope.get("task_id") == "TASK-21" and envelope.get("batch_id") == "T21-R2", "raw_population_drift")
        _require(envelope.get("member_id") == expected_member and envelope.get("horizon_id") == expected_panel, "raw_path_envelope_identity_mismatch")
        raw = RawApiEvent.model_validate_json(json.dumps(envelope["raw_event"], separators=(",", ":")))
        quote = QuoteAttempt.model_validate_json(json.dumps(envelope["quote_attempt"], separators=(",", ":")))
        _require(raw.raw_event_id == quote.raw_event_id, "raw_quote_event_id_mismatch")
        _require(envelope["request_hash"] == quote.request_hash, "envelope_request_hash_mismatch")
        _require(envelope["idempotency_key"] == quote.idempotency_key, "envelope_idempotency_mismatch")
        _require(envelope["raw_content_sha256"] == raw.content_sha256, "envelope_raw_hash_mismatch")
        _require(envelope["terminal_class"] == _enum_text(quote.status), "envelope_terminal_mismatch")
        price_impact, route_count = task23._raw_response(quote, raw)
        _require(_pit_valid(raw, quote, cutoff), "raw_quote_pit_invalid")
        events.append(
            {
                "member_id": expected_member,
                "panel_id": expected_panel,
                "window_id": envelope["window_id"],
                "call_ordinal": int(envelope["call_ordinal"]),
                "raw_path": item["path"],
                "raw_file_sha256": item["sha256"],
                "raw": raw,
                "quote": quote,
                "price_impact_pct": price_impact,
                "validated_route_count": route_count,
            }
        )
    ordinals = [event["call_ordinal"] for event in events]
    _require(ordinals == sorted(ordinals) and len(ordinals) == len(set(ordinals)), "raw_ordinals_invalid")
    return events


def _pair_id(member_id: str, panel_id: str, atomic: int) -> str:
    digest = sha256_bytes(f"{member_id}|{panel_id}|{atomic}".encode("utf-8"))[:24]
    return f"T25-R2-PAIR-{digest}"


def _attempt_row(event: Mapping[str, Any], pair_id: str, pair_role: str) -> dict[str, Any]:
    quote: QuoteAttempt = event["quote"]
    raw: RawApiEvent = event["raw"]
    return {
        "quote_attempt_id": quote.quote_attempt_id,
        "raw_event_id": quote.raw_event_id,
        "pair_id": pair_id,
        "pair_role": pair_role,
        "member_id": event["member_id"],
        "panel_id": event["panel_id"],
        "window_id": event["window_id"],
        "call_ordinal": event["call_ordinal"],
        "provider": quote.provider,
        "provider_version": quote.provider_version,
        "side": _enum_text(quote.side),
        "input_mint": quote.input_mint,
        "input_requested_atomic": str(quote.input_requested_atomic),
        "input_decimals": quote.input_decimals,
        "output_mint": quote.output_mint,
        "output_quoted_atomic": None if quote.output_quoted_atomic is None else str(quote.output_quoted_atomic),
        "output_decimals": quote.output_decimals,
        "route_id": quote.route_id,
        "route_count": quote.route_count,
        "context_slot": quote.context_slot,
        "requested_at": _as_utc_text(quote.requested_at),
        "response_at": _as_utc_text(quote.response_at),
        "raw_event_at": _as_utc_text(raw.event_time),
        "raw_observed_at": _as_utc_text(raw.observed_at),
        "first_reliable_available_at": _as_utc_text(quote.first_reliable_available_at),
        "available_to_strategy_at": _as_utc_text(quote.available_to_strategy_at),
        "ingested_at": _as_utc_text(quote.ingested_at),
        "quote_age_ms": quote.quote_age_ms,
        "provider_latency_ms": quote.provider_latency_ms,
        "provider_fee_atomic": None if quote.provider_fee_atomic is None else str(quote.provider_fee_atomic),
        "platform_fee_atomic": None if quote.platform_fee_atomic is None else str(quote.platform_fee_atomic),
        "fee_mint": quote.fee_mint,
        "included_in_output_amount": quote.included_in_output_amount,
        "status": _enum_text(quote.status),
        "error_class": quote.error_class,
        "request_hash": quote.request_hash,
        "response_content_sha256": quote.response_content_sha256,
        "raw_content_sha256": raw.content_sha256,
        "raw_file_sha256": event["raw_file_sha256"],
        "raw_path": event["raw_path"],
        "price_impact_pct": None if event["price_impact_pct"] is None else str(event["price_impact_pct"]),
        "schema_version": quote.schema_version,
        "revision_number": quote.revision_number,
        "revision_of": quote.revision_of,
        "quality_flags": quote.quality_flags,
    }


def _na_inventory() -> dict[str, Any]:
    return {
        "state": "NOT_APPLICABLE",
        "remaining_inventory_atomic": "0",
        "remaining_inventory_mint": None,
        "remaining_inventory_decimals": None,
    }


def _open_inventory(buy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "state": "OPEN",
        "remaining_inventory_atomic": buy["output_quoted_atomic"],
        "remaining_inventory_mint": buy["output_mint"],
        "remaining_inventory_decimals": buy["output_decimals"],
    }


def _timestamps(attempt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_at": attempt["raw_event_at"],
        "observed_at": attempt["raw_observed_at"],
        "first_reliable_available_at": attempt["first_reliable_available_at"],
        "available_to_strategy_at": attempt["available_to_strategy_at"],
        "ingested_at": attempt["ingested_at"],
        "measured_as_of": attempt["requested_at"],
    }


def _notional(attempt: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_amount_atomic": attempt["input_requested_atomic"],
        "input_mint": attempt["input_mint"],
        "input_decimals": attempt["input_decimals"],
        "quote_mint": attempt["output_mint"],
        "quote_decimals": attempt["output_decimals"],
        "latency_budget_ms": policy["latency_budget_ms"],
        "freshness_max_age_ms": policy["freshness_max_age_ms"],
        "observed_age_ms": attempt["quote_age_ms"],
        "observed_provider_latency_ms": attempt["provider_latency_ms"],
    }


def _lineage(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "source_asset_ids": sorted({attempt["raw_path"] for attempt in attempts}),
        "quote_attempt_ids": [attempt["quote_attempt_id"] for attempt in attempts],
        "execution_attempt_ids": [],
        "cashflow_reference_ids": [],
        "raw_file_sha256": sorted({attempt["raw_file_sha256"] for attempt in attempts}),
        "response_content_sha256": [attempt["response_content_sha256"] for attempt in attempts],
    }


def _outcome(
    *,
    record_id: str,
    member_id: str,
    panel_id: str,
    tested_notional_usd: int | None,
    label: str,
    assessment: str,
    assessment_reason: str,
    evidence_basis: str,
    claim_scope: str,
    value_decimal: str | None,
    unit: str | None,
    route_state_observed: str,
    notional: Mapping[str, Any] | None,
    inventory: Mapping[str, Any],
    timestamps: Mapping[str, Any],
    lineage: Mapping[str, Any],
    quality_flags: Sequence[str],
    path_state: str = "NOT_APPLICABLE",
) -> dict[str, Any]:
    if assessment != "SUPPORTED":
        _require(value_decimal is None and unit is None, "unsupported_value_must_be_null")
    return {
        "record_id": record_id,
        "member_id": member_id,
        "panel_id": panel_id,
        "tested_notional_usd": tested_notional_usd,
        "label": label,
        "assessment": assessment,
        "assessment_reason": assessment_reason,
        "evidence_basis": evidence_basis,
        "claim_scope": claim_scope,
        "value_decimal": value_decimal,
        "unit": unit,
        "route_state_observed": route_state_observed,
        "fill_state": "ACTUAL_FILLS_NOT_OBSERVED" if label in {"FILLABLE", "QUOTE_EXIT", "REALIZED_VWAP"} else "NOT_APPLICABLE",
        "cashflow_state": "CASHFLOW_NOT_OBSERVED" if label == "NET" else "NOT_APPLICABLE",
        "path_state": path_state,
        "notional": None if notional is None else dict(notional),
        "inventory": dict(inventory),
        "timestamps": dict(timestamps),
        "lineage": dict(lineage),
        "quality_flags": sorted(set(quality_flags)),
    }


def build_surface_from_raw(repo_root: Path) -> dict[str, Any]:
    manifest = validate_pre_read_manifest(repo_root, require_raw_metadata=True)
    config_path = _safe_path(repo_root, "configs/task23_bounded_diagnostics_v1.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    _require(isinstance(config, dict), "task23_config_invalid")
    allowed_envelope = set(config["allowed_fields"]["envelope"])
    cutoff = _parse_time(manifest["dataset_identity"]["evaluation_cutoff_at"])
    events: list[dict[str, Any]] = []
    for item in manifest["raw_inputs"]:
        events.extend(_read_raw_input(repo_root, item, allowed_envelope, cutoff))
    _require(len(events) == 72, "exact_quote_attempt_count_drift")
    _require({event["member_id"] for event in events} == set(MEMBERS), "member_set_drift")
    _require({event["panel_id"] for event in events} == set(PANELS), "panel_set_drift")

    by_panel: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in events:
        by_panel.setdefault((event["member_id"], event["panel_id"]), []).append(event)
    _require(set(by_panel) == {(member, panel) for member in MEMBERS for panel in PANELS}, "panel_population_drift")

    attempts: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    pair_attempts: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for member in MEMBERS:
        for panel_id in PANELS:
            panel_events = sorted(by_panel[(member, panel_id)], key=lambda event: event["call_ordinal"])
            paired = task23._pair_events(panel_events)
            for usd, atomic in NOTIONALS:
                pair = paired[atomic]
                buy_event = pair["buy"]
                sell_event = pair["sell"]
                _require(buy_event is not None and sell_event is not None, "exact_pair_leg_missing")
                buy_quote: QuoteAttempt = buy_event["quote"]
                sell_quote: QuoteAttempt = sell_event["quote"]
                _require(_enum_text(buy_quote.status) == "QUOTE_AVAILABLE", "current_r2_buy_not_available")
                _require(_enum_text(sell_quote.status) == "QUOTE_AVAILABLE", "current_r2_sell_not_available")
                _require(
                    exact_dependent_sell_identity(
                        buy_input_mint=buy_quote.input_mint,
                        buy_output_mint=buy_quote.output_mint,
                        buy_output_atomic=int(buy_quote.output_quoted_atomic),
                        buy_output_decimals=buy_quote.output_decimals,
                        sell_input_mint=sell_quote.input_mint,
                        sell_input_atomic=sell_quote.input_requested_atomic,
                        sell_input_decimals=sell_quote.input_decimals,
                        sell_output_mint=sell_quote.output_mint,
                    ),
                    "dependent_sell_identity_mismatch",
                )
                pair_id = _pair_id(member, panel_id, atomic)
                buy = _attempt_row(buy_event, pair_id, "BUY")
                sell = _attempt_row(sell_event, pair_id, "DEPENDENT_SELL")
                attempts.extend((buy, sell))
                pair_attempts[pair_id] = (buy, sell)
                retention = Decimal(sell["output_quoted_atomic"]) * Decimal(10_000) / Decimal(buy["input_requested_atomic"])
                pairs.append(
                    {
                        "pair_id": pair_id,
                        "member_id": member,
                        "panel_id": panel_id,
                        "window_id": buy["window_id"],
                        "tested_notional_usd": usd,
                        "buy_quote_attempt_id": buy["quote_attempt_id"],
                        "sell_quote_attempt_id": sell["quote_attempt_id"],
                        "buy_input_mint": buy["input_mint"],
                        "buy_input_atomic": buy["input_requested_atomic"],
                        "buy_input_decimals": buy["input_decimals"],
                        "buy_output_mint": buy["output_mint"],
                        "buy_output_atomic": buy["output_quoted_atomic"],
                        "buy_output_decimals": buy["output_decimals"],
                        "sell_input_mint": sell["input_mint"],
                        "sell_input_atomic": sell["input_requested_atomic"],
                        "sell_input_decimals": sell["input_decimals"],
                        "sell_output_mint": sell["output_mint"],
                        "sell_output_atomic": sell["output_quoted_atomic"],
                        "sell_output_decimals": sell["output_decimals"],
                        "buy_status": buy["status"],
                        "sell_status": sell["status"],
                        "buy_quote_age_ms": buy["quote_age_ms"],
                        "sell_quote_age_ms": sell["quote_age_ms"],
                        "buy_provider_latency_ms": buy["provider_latency_ms"],
                        "sell_provider_latency_ms": sell["provider_latency_ms"],
                        "roundtrip_quote_retention_bps": _decimal_text(retention, "0.0001"),
                        "exact_dependent_sell_identity": True,
                    }
                )

    attempts.sort(key=lambda row: (row["member_id"], row["panel_id"], row["call_ordinal"]))
    pairs.sort(key=lambda row: (row["member_id"], row["panel_id"], row["tested_notional_usd"]))
    _require(len(attempts) == 72 and len({row["quote_attempt_id"] for row in attempts}) == 72, "attempt_identity_drift")
    _require(len(pairs) == 36 and len({row["pair_id"] for row in pairs}) == 36, "pair_identity_drift")

    panel_attempts = {
        (member, panel): [row for row in attempts if row["member_id"] == member and row["panel_id"] == panel]
        for member in MEMBERS
        for panel in PANELS
    }
    p0_first = {
        member: min(_parse_time(row["first_reliable_available_at"]) for row in panel_attempts[(member, "P0")])
        for member in MEMBERS
    }
    panel_elapsed: dict[tuple[str, str], str] = {}
    for member in MEMBERS:
        for panel_id in PANELS:
            first = min(_parse_time(row["first_reliable_available_at"]) for row in panel_attempts[(member, panel_id)])
            elapsed = Decimal(str((first - p0_first[member]).total_seconds()))
            _require(elapsed >= 0, "actual_elapsed_negative")
            panel_elapsed[(member, panel_id)] = str(elapsed)
    for row in attempts:
        row["actual_elapsed_from_member_p0_seconds"] = panel_elapsed[(row["member_id"], row["panel_id"])]
    for row in pairs:
        row["actual_elapsed_from_member_p0_seconds"] = panel_elapsed[(row["member_id"], row["panel_id"])]

    policy = manifest["classification_policy"]
    baseline_retention = {
        (row["member_id"], row["tested_notional_usd"]): Decimal(row["roundtrip_quote_retention_bps"])
        for row in pairs
        if row["panel_id"] == "P0"
    }
    outcomes: list[dict[str, Any]] = []
    record_counter = 0

    def add(**kwargs: Any) -> None:
        nonlocal record_counter
        record_counter += 1
        kwargs["record_id"] = f"T25-R2-EXACT-{record_counter:04d}"
        outcomes.append(_outcome(**kwargs))

    pairs_by_key = {
        (row["member_id"], row["panel_id"], row["tested_notional_usd"]): row
        for row in pairs
    }
    for member in MEMBERS:
        for panel_id in PANELS:
            panel_rows = panel_attempts[(member, panel_id)]
            panel_last = max(panel_rows, key=lambda row: _parse_time(row["available_to_strategy_at"]))
            panel_lineage = _lineage(panel_rows)
            common_timestamps = _timestamps(panel_last)
            add(
                member_id=member,
                panel_id=panel_id,
                tested_notional_usd=None,
                label="TOUCH",
                assessment="UNKNOWN",
                assessment_reason="NO_FROZEN_REFERENCE_THRESHOLD_OR_CROSS_FIELD",
                evidence_basis="DISCRETE_PANEL_GRID",
                claim_scope="TOUCH_WITHIN_HORIZON",
                value_decimal=None,
                unit=None,
                route_state_observed="NOT_APPLICABLE",
                notional=None,
                inventory=_na_inventory(),
                timestamps=common_timestamps,
                lineage=panel_lineage,
                quality_flags=("SPARSE_PANEL", "CONTINUOUS_TOUCH_NOT_ESTABLISHED"),
                path_state="SPARSE_DISCRETE",
            )
            for usd, _ in NOTIONALS:
                pair = pairs_by_key[(member, panel_id, usd)]
                buy, sell = pair_attempts[pair["pair_id"]]
                buy_assessment, buy_reason = classify_quote(
                    status=buy["status"],
                    quote_age_ms=buy["quote_age_ms"],
                    provider_latency_ms=buy["provider_latency_ms"],
                    exact_identity=True,
                    pit_valid=True,
                    latency_budget_ms=policy["latency_budget_ms"],
                    freshness_max_age_ms=policy["freshness_max_age_ms"],
                )
                buy_value = None
                buy_unit = None
                if buy_assessment == "SUPPORTED":
                    buy_value = _decimal_text(-_decimal(buy["price_impact_pct"], "buy_price_impact_invalid") / Decimal(100))
                    buy_unit = "RETURN_DECIMAL"
                add(
                    member_id=member,
                    panel_id=panel_id,
                    tested_notional_usd=usd,
                    label="FILLABLE",
                    assessment=buy_assessment,
                    assessment_reason=buy_reason,
                    evidence_basis="CONTEMPORANEOUS_QUOTE",
                    claim_scope="POINT_IN_TIME_QUOTE",
                    value_decimal=buy_value,
                    unit=buy_unit,
                    route_state_observed=buy["status"],
                    notional=_notional(buy, policy),
                    inventory=_na_inventory(),
                    timestamps=_timestamps(buy),
                    lineage=_lineage((buy,)),
                    quality_flags=("EXACT_ATOMIC_NOTIONAL", "QUOTE_IS_NOT_FILL", "DEVELOPMENT_LIMITS_ONLY"),
                )
                sell_assessment, sell_reason = classify_quote(
                    status=sell["status"],
                    quote_age_ms=sell["quote_age_ms"],
                    provider_latency_ms=sell["provider_latency_ms"],
                    exact_identity=pair["exact_dependent_sell_identity"],
                    pit_valid=True,
                    latency_budget_ms=policy["latency_budget_ms"],
                    freshness_max_age_ms=policy["freshness_max_age_ms"],
                )
                sell_value = None
                sell_unit = None
                if sell_assessment == "SUPPORTED":
                    sell_value = _decimal_text(Decimal(pair["roundtrip_quote_retention_bps"]) / Decimal(10_000) - Decimal(1))
                    sell_unit = "RETURN_DECIMAL"
                add(
                    member_id=member,
                    panel_id=panel_id,
                    tested_notional_usd=usd,
                    label="QUOTE_EXIT",
                    assessment=sell_assessment,
                    assessment_reason=sell_reason,
                    evidence_basis="CONTEMPORANEOUS_QUOTE",
                    claim_scope="POINT_IN_TIME_QUOTE",
                    value_decimal=sell_value,
                    unit=sell_unit,
                    route_state_observed=sell["status"],
                    notional=_notional(sell, policy),
                    inventory=_open_inventory(buy),
                    timestamps=_timestamps(sell),
                    lineage=_lineage((buy, sell)),
                    quality_flags=("EXACT_DEPENDENT_SELL_INVENTORY", "QUOTE_EXIT_IS_NOT_LIQUIDATION", "DEVELOPMENT_LIMITS_ONLY"),
                    path_state="UNOBSERVED",
                )
            add(
                member_id=member,
                panel_id=panel_id,
                tested_notional_usd=None,
                label="REALIZED_VWAP",
                assessment="UNKNOWN",
                assessment_reason="ACTUAL_RECONCILED_FILLS_NOT_OBSERVED",
                evidence_basis="NONE",
                claim_scope="ACTUAL_FILL_SERIES",
                value_decimal=None,
                unit=None,
                route_state_observed="NOT_APPLICABLE",
                notional=None,
                inventory=_na_inventory(),
                timestamps=common_timestamps,
                lineage=panel_lineage,
                quality_flags=("QUOTE_RETENTION_IS_NOT_REALIZED_VWAP",),
            )
            add(
                member_id=member,
                panel_id=panel_id,
                tested_notional_usd=None,
                label="NET",
                assessment="UNKNOWN",
                assessment_reason="SETTLED_CASHFLOW_AND_TASK26_COST_MODEL_NOT_AVAILABLE",
                evidence_basis="NONE",
                claim_scope="SETTLED_CASHFLOW",
                value_decimal=None,
                unit=None,
                route_state_observed="NOT_APPLICABLE",
                notional=None,
                inventory=_na_inventory(),
                timestamps=common_timestamps,
                lineage=panel_lineage,
                quality_flags=("NET_RETURN_NOT_ESTABLISHED",),
            )
            current = {
                usd: Decimal(pairs_by_key[(member, panel_id, usd)]["roundtrip_quote_retention_bps"])
                for usd, _ in NOTIONALS
            }
            adverse = max(
                max(Decimal(0), baseline_retention[(member, usd)] - value)
                for usd, value in current.items()
            ) / Decimal(10_000)
            add(
                member_id=member,
                panel_id=panel_id,
                tested_notional_usd=None,
                label="PATH_RISK",
                assessment="SUPPORTED",
                assessment_reason="EXACT_QUOTE_RETENTION_ON_ACTUAL_SPARSE_GRID",
                evidence_basis="DISCRETE_PANEL_GRID",
                claim_scope="DISCRETE_PATH_GRID",
                value_decimal=_decimal_text(adverse),
                unit="RETURN_DECIMAL",
                route_state_observed="NOT_APPLICABLE",
                notional=None,
                inventory=_na_inventory(),
                timestamps=common_timestamps,
                lineage=panel_lineage,
                quality_flags=("ACTUAL_SPARSE_PANEL_TIMES", "CONTINUOUS_MAE_MFE_FORBIDDEN", "QUOTE_IMPLIED_NOT_REALIZED"),
                path_state="SPARSE_DISCRETE",
            )

    labels = Counter(row["label"] for row in outcomes)
    assessments = Counter(row["assessment"] for row in outcomes)
    reasons = Counter(row["assessment_reason"] for row in outcomes)
    _require(len(outcomes) == 108 and labels == EXPECTED_LABELS, "exact_outcome_denominator_drift")
    raw_inputs = [
        {key: item[key] for key in ("path", "sha256", "bytes", "line_count")}
        for item in manifest["raw_inputs"]
    ]
    surface = {
        "schema": "smial.task25.exact-r2-outcome-surface",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "engine_version": ENGINE_VERSION,
        "status": "MATERIALIZED_EXACT_R2_DEVELOPMENT_SURFACE",
        "evaluation_cutoff_at": manifest["dataset_identity"]["evaluation_cutoff_at"],
        "dataset_identity": manifest["dataset_identity"],
        "classification_policy": policy,
        "input_bindings": {
            "pre_read_manifest": {"path": PRE_READ_PATH.as_posix(), "sha256": PRE_READ_SHA256},
            "raw_inputs": raw_inputs,
        },
        "summary": {
            "raw_r2_value_files_opened": 9,
            "raw_r2_bytes_read": 392234,
            "raw_r2_lines_read": 72,
            "quote_attempts": len(attempts),
            "quote_pairs": len(pairs),
            "members": 3,
            "panels": 9,
            "outcomes_input": len(outcomes),
            "outcomes_output": len(outcomes),
            "outcomes_dropped": 0,
            "labels": dict(sorted(labels.items())),
            "assessments": dict(sorted(assessments.items())),
            "assessment_reasons": dict(sorted(reasons.items())),
            "fillable_supported": sum(row["label"] == "FILLABLE" and row["assessment"] == "SUPPORTED" for row in outcomes),
            "quote_exit_supported": sum(row["label"] == "QUOTE_EXIT" and row["assessment"] == "SUPPORTED" for row in outcomes),
            "realized_vwap_supported": 0,
            "net_supported": 0,
            "latency_limit_exceeded_attempts": sum(row["provider_latency_ms"] is not None and row["provider_latency_ms"] > policy["latency_budget_ms"] for row in attempts),
            "freshness_limit_exceeded_attempts": sum(row["quote_age_ms"] is not None and row["quote_age_ms"] > policy["freshness_max_age_ms"] for row in attempts),
            "unknown_values_coerced_to_zero": 0,
            "future_rows_consumed": 0,
            "r3_paths_or_values_read": 0,
        },
        "quote_attempts": attempts,
        "quote_pairs": pairs,
        "outcomes": outcomes,
        "claims": [
            "EXACT_R2_QUOTE_IDENTITY_AND_PIT_SURFACE_RETAINED",
            "FILLABLE_AND_QUOTE_EXIT_ARE_DEVELOPMENT_QUOTE_LABELS_ONLY",
            "DISCRETE_QUOTE_PATH_RISK_RETAINED",
        ],
        "prohibited_claims": [
            "ORDER_OR_FILL",
            "SETTLEMENT_OR_FLAT_INVENTORY",
            "REALIZED_VWAP",
            "NET_RETURN_OR_OWNER_CASHFLOW",
            "CONTINUOUS_TOUCH_OR_MAE_MFE",
            "EXACT_NOMINAL_HORIZON",
            "GENERALIZATION_OR_ALPHA",
            "LIVE_SLA_OR_STRATEGY_AUTHORITY",
            "R3_HOLDOUT_RESULT",
        ],
        "limitations": [
            "ONE_CAPTURE_CLUSTER_DESCRIPTIVE_ONLY",
            "DEVELOPMENT_LIMITS_REUSE_A2_GOLDEN_NUMERIC_PARAMETERS",
            "ONE_BUY_QUOTE_EXCEEDS_1000_MS_LATENCY_AND_REMAINS_UNKNOWN",
            "NO_ACTUAL_FILLS_OR_SETTLED_CASHFLOW",
            "TOUCH_THRESHOLD_NOT_FROZEN",
        ],
        "next_boundary": {
            "candidate_atom": "T25-A6_REGISTER_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1",
            "authorized_by_a5r1": False,
            "r3_access": "DENY",
        },
    }
    validate_surface(surface)
    return surface


def validate_surface(surface: Mapping[str, Any]) -> None:
    _require(surface.get("schema") == "smial.task25.exact-r2-outcome-surface", "surface_schema_drift")
    _require(surface.get("task_id") == TASK_ID and surface.get("atom_id") == ATOM_ID, "surface_identity_drift")
    _require(surface.get("input_bindings", {}).get("pre_read_manifest") == {"path": PRE_READ_PATH.as_posix(), "sha256": PRE_READ_SHA256}, "surface_pre_read_binding_drift")
    summary = surface.get("summary", {})
    _require(summary.get("raw_r2_value_files_opened") == 9, "surface_raw_file_count_drift")
    _require(summary.get("raw_r2_bytes_read") == 392234 and summary.get("raw_r2_lines_read") == 72, "surface_raw_volume_drift")
    _require(summary.get("r3_paths_or_values_read") == 0, "surface_r3_access_forbidden")
    _require(summary.get("future_rows_consumed") == 0, "surface_future_rows_consumed")
    _require(summary.get("unknown_values_coerced_to_zero") == 0, "surface_unknown_zero_coercion")
    attempts = surface.get("quote_attempts")
    pairs = surface.get("quote_pairs")
    outcomes = surface.get("outcomes")
    _require(isinstance(attempts, list) and len(attempts) == 72, "stored_attempt_count_drift")
    _require(isinstance(pairs, list) and len(pairs) == 36, "stored_pair_count_drift")
    _require(isinstance(outcomes, list) and len(outcomes) == 108, "stored_outcome_count_drift")
    _require(len({row["quote_attempt_id"] for row in attempts}) == 72, "stored_attempt_id_duplicate")
    _require(len({row["pair_id"] for row in pairs}) == 36, "stored_pair_id_duplicate")
    _require(all("redacted_body" not in row and "raw_body" not in row for row in attempts), "raw_body_leaked_to_surface")

    cutoff = _parse_time(surface["evaluation_cutoff_at"])
    attempts_by_id = {row["quote_attempt_id"]: row for row in attempts}
    for row in attempts:
        observed = _parse_time(row["raw_observed_at"])
        first = _parse_time(row["first_reliable_available_at"])
        available = _parse_time(row["available_to_strategy_at"])
        ingested = _parse_time(row["ingested_at"])
        _require(observed <= first <= available <= ingested and available <= cutoff, "stored_attempt_pit_invalid")
        _require(row["status"] == "QUOTE_AVAILABLE", "stored_current_r2_status_drift")
        _require(row["output_quoted_atomic"] is not None, "stored_available_output_missing")
    for pair in pairs:
        buy = attempts_by_id[pair["buy_quote_attempt_id"]]
        sell = attempts_by_id[pair["sell_quote_attempt_id"]]
        _require(pair["exact_dependent_sell_identity"] is True, "stored_pair_exact_flag_missing")
        _require(
            exact_dependent_sell_identity(
                buy_input_mint=buy["input_mint"],
                buy_output_mint=buy["output_mint"],
                buy_output_atomic=int(buy["output_quoted_atomic"]),
                buy_output_decimals=int(buy["output_decimals"]),
                sell_input_mint=sell["input_mint"],
                sell_input_atomic=int(sell["input_requested_atomic"]),
                sell_input_decimals=int(sell["input_decimals"]),
                sell_output_mint=sell["output_mint"],
            ),
            "stored_pair_identity_invalid",
        )
    labels = Counter(row["label"] for row in outcomes)
    assessments = Counter(row["assessment"] for row in outcomes)
    _require(labels == EXPECTED_LABELS, "stored_outcome_label_drift")
    _require(assessments == Counter({"SUPPORTED": 80, "UNKNOWN": 28}), "stored_outcome_assessment_drift")
    _require(summary.get("fillable_supported") == 35, "stored_fillable_support_drift")
    _require(summary.get("quote_exit_supported") == 36, "stored_quote_exit_support_drift")
    _require(summary.get("latency_limit_exceeded_attempts") == 1, "stored_latency_exception_drift")
    _require(summary.get("freshness_limit_exceeded_attempts") == 0, "stored_freshness_exception_drift")
    for row in outcomes:
        if row["assessment"] != "SUPPORTED":
            _require(row["value_decimal"] is None and row["unit"] is None, "stored_unknown_value_not_null")
        if row["label"] in {"FILLABLE", "QUOTE_EXIT"} and row["assessment"] == "SUPPORTED":
            notional = row["notional"]
            _require(isinstance(notional, dict), "stored_supported_quote_notional_missing")
            _require(notional["observed_age_ms"] <= 5000, "stored_supported_quote_stale")
            _require(notional["observed_provider_latency_ms"] <= 1000, "stored_supported_quote_slow")
            _require(row["fill_state"] == "ACTUAL_FILLS_NOT_OBSERVED", "stored_quote_promoted_to_fill")
        if row["label"] == "QUOTE_EXIT" and row["assessment"] == "SUPPORTED":
            _require(row["inventory"]["state"] == "OPEN", "stored_quote_exit_flattened_inventory")
        if row["label"] in {"REALIZED_VWAP", "NET", "TOUCH"}:
            _require(row["assessment"] == "UNKNOWN", f"stored_unsupported_label_promoted:{row['label']}")
        if row["label"] == "PATH_RISK":
            _require(row["claim_scope"] == "DISCRETE_PATH_GRID" and row["path_state"] == "SPARSE_DISCRETE", "stored_path_scope_broadened")


def build_acceptance(repo_root: Path, surface: Mapping[str, Any]) -> dict[str, Any]:
    validate_pre_read_manifest(repo_root)
    validate_surface(surface)
    synthetic = validate_synthetic_fixture(repo_root)
    holdout_path = _safe_path(repo_root, "docs/evidence/task22/holdout_access_ledger_v2.json")
    holdout = _load_json(holdout_path)
    _require(holdout.get("records") == [], "holdout_ledger_not_empty")
    return {
        "schema": "smial.task25.exact-r2-outcome-reprojection-acceptance",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS_EXACT_R2_OUTCOME_SURFACE_WITH_BOUNDED_DEVELOPMENT_LABELS",
        "input_bindings": {
            "pre_read_manifest": {"path": PRE_READ_PATH.as_posix(), "sha256": PRE_READ_SHA256},
            "raw_inputs": surface["input_bindings"]["raw_inputs"],
        },
        "surface": {
            "path": SURFACE_PATH.as_posix(),
            "sha256": sha256_bytes(canonical_json_bytes(surface)),
            "summary": surface["summary"],
        },
        "acceptance_checks": [
            {"check_id": "PRE_READ_SEALED_BEFORE_RAW_REOPEN", "status": "PASS"},
            {"check_id": "NINE_RAW_HASHES_AND_72_LINES_EXACT", "status": "PASS"},
            {"check_id": "EXACT_MINT_ATOMIC_AND_PAIR_IDENTITY_RETAINED", "status": "PASS"},
            {"check_id": "PIT_ORDER_AND_EVALUATION_CUTOFF_VALID", "status": "PASS"},
            {"check_id": "FILLABLE_35_SUPPORTED_ONE_LATENCY_UNKNOWN", "status": "PASS"},
            {"check_id": "QUOTE_EXIT_36_SUPPORTED_INVENTORY_REMAINS_OPEN", "status": "PASS"},
            {"check_id": "TOUCH_REALIZED_VWAP_NET_REMAIN_UNKNOWN", "status": "PASS"},
            {"check_id": "PATH_RISK_DISCRETE_ONLY", "status": "PASS"},
            {"check_id": "R3_UNTOUCHED", "status": "PASS"},
            {"check_id": "CI_PORTABLE_SYNTHETIC_TRANSFORM_COVERAGE", "status": "PASS"},
        ],
        "synthetic_delivery_fixture": {
            "path": SYNTHETIC_FIXTURE_PATH.as_posix(),
            "sha256": sha256_file(_safe_path(repo_root, SYNTHETIC_FIXTURE_PATH)),
            **synthetic,
            "raw_local_dependency_required_by_ci": False,
            "decision_critical_skip_count": 0,
        },
        "implementation": {
            "module": {"path": MODULE_PATH.as_posix(), "sha256": sha256_file(_safe_path(repo_root, MODULE_PATH))},
            "tests": {"path": TEST_PATH.as_posix(), "sha256": sha256_file(_safe_path(repo_root, TEST_PATH))},
            "upstream_parser": {
                "path": "src/solana_alpha_lab/task23_diagnostic_projection.py",
                "sha256": "728fa77fc82a3e27245a908cfecc2a50e7df82c5813e6b90d4ad8ff0870e57f9",
            },
        },
        "side_effects": {
            "raw_r2_value_files_opened_for_generation": 9,
            "raw_r2_bytes_read_for_generation": 392234,
            "new_collection": 0,
            "r3_paths_or_values_read": 0,
            "provider_api_rpc_wss_calls": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_or_credits_spent": 0,
            "dependencies_added": 0,
            "sources_changed": 0,
            "catalog_changed": 0,
            "commit_push_pr_merge_actions": 0,
        },
        "limitations": surface["limitations"],
        "next_boundary": surface["next_boundary"],
    }


def _load_stored_surface(repo_root: Path) -> dict[str, Any]:
    surface = _load_json(_safe_path(repo_root, SURFACE_PATH))
    validate_surface(surface)
    return surface


def build_acceptance_bytes(repo_root: Path, surface: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(build_acceptance(repo_root, surface))


def write_raw_outputs(repo_root: Path) -> tuple[str, str]:
    surface = build_surface_from_raw(repo_root)
    surface_bytes = canonical_json_bytes(surface)
    acceptance_bytes = build_acceptance_bytes(repo_root, surface)
    _safe_path(repo_root, SURFACE_PATH).write_bytes(surface_bytes)
    _safe_path(repo_root, ACCEPTANCE_PATH).write_bytes(acceptance_bytes)
    return sha256_bytes(surface_bytes), sha256_bytes(acceptance_bytes)


def check_stored_outputs(repo_root: Path, *, raw_recompute: bool = False) -> dict[str, str]:
    stored_surface = _load_stored_surface(repo_root)
    surface_bytes = canonical_json_bytes(stored_surface)
    if raw_recompute:
        recomputed = build_surface_from_raw(repo_root)
        _require(canonical_json_bytes(recomputed) == surface_bytes, "raw_recomputed_surface_drift")
    acceptance_bytes = build_acceptance_bytes(repo_root, stored_surface)
    stored_acceptance_path = _safe_path(repo_root, ACCEPTANCE_PATH)
    _require(stored_acceptance_path.is_file(), "stored_acceptance_missing")
    _require(stored_acceptance_path.read_bytes() == acceptance_bytes, "stored_acceptance_drift")
    return {
        SURFACE_PATH.as_posix(): sha256_bytes(surface_bytes),
        ACCEPTANCE_PATH.as_posix(): sha256_bytes(acceptance_bytes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        choices=("raw-write", "raw-surface", "raw-check", "check", "hashes"),
        default="check",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    if args.artifact == "raw-write":
        surface_hash, acceptance_hash = write_raw_outputs(repo_root)
        print(json.dumps({"surface": surface_hash, "acceptance": acceptance_hash}, sort_keys=True))
    elif args.artifact == "raw-surface":
        print(canonical_json_bytes(build_surface_from_raw(repo_root)).decode("utf-8"), end="")
    else:
        hashes = check_stored_outputs(repo_root, raw_recompute=args.artifact == "raw-check")
        print(json.dumps(hashes, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
