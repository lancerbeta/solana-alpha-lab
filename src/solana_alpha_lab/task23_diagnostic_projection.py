"""Deterministic, offline TASK-23 projection over the sealed R2 roots only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import stat
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import yaml

from solana_alpha_lab.contracts.schema_v1 import QuoteAttempt, RawApiEvent


TASK_ID = "TASK-23"
ATOM_ID = "T23-A3_DETERMINISTIC_R2_DIAGNOSTIC_PROJECTION_V1"
RECEIPT_SCHEMA = "smial.task23.r2-development-read-receipt"
PROJECTION_SCHEMA = "smial.task23.r2-diagnostic-projection"
SCHEMA_VERSION = "1.0.0"
EXPECTED_RAW_SCHEMA = "smial.task21.forward-quote-panel-raw"
TESTED_NOTIONALS = ((10, 10_000_000), (25, 25_000_000), (50, 50_000_000), (100, 100_000_000))
OUTPUT_FILENAMES = (
    "panel_inventory_v1.csv",
    "quote_pair_availability_v1.csv",
    "panel_diagnostics_v1.csv",
    "projection_manifest_v1.json",
)


class Task23ProjectionError(RuntimeError):
    """Raised when a frozen TASK-23 projection invariant is violated."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task23ProjectionError(f"yaml_root_not_mapping:{path.as_posix()}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task23ProjectionError(f"json_root_not_mapping:{path.as_posix()}")
    return value


def _as_utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Task23ProjectionError("timestamp_not_timezone_aware")
    return value.isoformat().replace("+00:00", "Z")


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f")


def _rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return format(Decimal(numerator) / Decimal(denominator), ".6f")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _enum_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    info = path.stat(follow_symlinks=False)
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _validate_safe_descendant(repo_root: Path, candidate: Path) -> Path:
    repo_resolved = repo_root.resolve(strict=True)
    candidate_resolved = candidate.resolve(strict=True)
    if not candidate_resolved.is_relative_to(repo_resolved):
        raise Task23ProjectionError("resolved_path_outside_repository")
    current = candidate
    while True:
        if _is_reparse_or_symlink(current):
            raise Task23ProjectionError(f"reparse_or_symlink_forbidden:{current.name}")
        if current.resolve(strict=True) == repo_resolved:
            break
        if current.parent == current:
            raise Task23ProjectionError("repository_ancestor_not_reached")
        current = current.parent
    return candidate_resolved


def validate_config(config: Mapping[str, Any]) -> None:
    if config.get("schema") != "smial.task23.bounded-diagnostics-contract":
        raise Task23ProjectionError("config_schema_mismatch")
    if config.get("task_id") != TASK_ID:
        raise Task23ProjectionError("config_task_mismatch")
    if config.get("status") != "FROZEN_PRE_READ":
        raise Task23ProjectionError("config_not_frozen_pre_read")
    if config["next_boundary"]["atom"] != ATOM_ID:
        raise Task23ProjectionError("config_next_atom_mismatch")
    primary = config["population"]["primary_development"]
    if primary["split"] != "R2" or primary["batch_id"] != "T21-R2":
        raise Task23ProjectionError("primary_population_not_exact_r2")
    if primary["member_count"] != 3 or len(primary["members"]) != 3:
        raise Task23ProjectionError("primary_population_member_count_mismatch")
    holdout = config["population"]["untouched_holdout"]
    if holdout["split"] != "R3" or holdout["access"] != "DENY":
        raise Task23ProjectionError("r3_not_default_deny")
    forbidden_holdout_flags = (
        "path_discovery",
        "value_read",
        "outcome_read",
        "statistics",
        "joins",
        "derived_inspection",
    )
    if any(holdout[key] for key in forbidden_holdout_flags):
        raise Task23ProjectionError("r3_authority_nonzero")
    boundary = config["r2_read_boundary"]
    roots = boundary["allowed_roots_after_a3_pre_read_receipt"]
    bindings = boundary["root_bindings"]
    if [item["panel_id"] for item in bindings] != ["P0", "P1", "P2"]:
        raise Task23ProjectionError("root_panel_binding_mismatch")
    if [item["root"] for item in bindings] != roots:
        raise Task23ProjectionError("root_binding_list_mismatch")
    for root in roots:
        pure = PurePosixPath(root)
        lowered = f"/{root.lower().strip('/')}/"
        if pure.is_absolute() or ".." in pure.parts:
            raise Task23ProjectionError("root_must_be_safe_relative_path")
        if "/r2/" not in lowered:
            raise Task23ProjectionError("root_not_r2")
        if "/r1/" in lowered or "/r3/" in lowered or "outcomes" in lowered:
            raise Task23ProjectionError("forbidden_root_fragment")
    if boundary["allowed_value_filename"] != "raw_events.jsonl":
        raise Task23ProjectionError("value_filename_mismatch")
    if config["time_semantics"]["window_ids_are_nominal_horizons"]:
        raise Task23ProjectionError("nominal_horizon_substitution_forbidden")
    if config["denominators"]["missing_is_zero"]:
        raise Task23ProjectionError("missing_cannot_equal_zero")
    if config["dependence"]["iid_assumption"]:
        raise Task23ProjectionError("iid_assumption_forbidden")


def validate_pre_read_receipt(
    *,
    repo_root: Path,
    config_path: Path,
    config: Mapping[str, Any],
    receipt_path: Path,
) -> dict[str, Any]:
    receipt = _load_json(receipt_path)
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("schema_version") != SCHEMA_VERSION:
        raise Task23ProjectionError("pre_read_receipt_schema_mismatch")
    if receipt.get("task_id") != TASK_ID or receipt.get("atom_id") != ATOM_ID:
        raise Task23ProjectionError("pre_read_receipt_atom_mismatch")
    if receipt.get("status") not in {
        "SEALED_BEFORE_FIRST_R2_VALUE_READ",
        "SEALED_BEFORE_R2_RETRY_READ",
    }:
        raise Task23ProjectionError("pre_read_receipt_not_sealed")
    created_at = datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00"))
    _as_utc_text(created_at)

    bindings = receipt["bindings"]
    contract_binding = bindings["contract"]
    config_binding = bindings["config"]
    code_binding = bindings["projection_code"]
    if config_binding["path"] != config_path.relative_to(repo_root).as_posix():
        raise Task23ProjectionError("receipt_config_path_mismatch")
    for binding, label in (
        (contract_binding, "contract"),
        (config_binding, "config"),
        (code_binding, "projection_code"),
    ):
        path = repo_root / PurePosixPath(binding["path"])
        if not path.is_file() or sha256_file(path) != binding["sha256"]:
            raise Task23ProjectionError(f"receipt_{label}_hash_mismatch")

    frozen_receipt = {
        item["path"]: item["sha256"] for item in bindings["frozen_inputs"]
    }
    frozen_config = {
        item["path"]: item["sha256"] for item in config["frozen_inputs"]
    }
    if frozen_receipt != frozen_config:
        raise Task23ProjectionError("receipt_frozen_inputs_mismatch")
    for item in config["frozen_inputs"]:
        path = repo_root / PurePosixPath(item["path"])
        if not path.is_file():
            raise Task23ProjectionError(f"frozen_input_missing:{item['path']}")
        if item.get("mutation_policy") == "APPEND_ONLY_AFTER_A2":
            if path.stat().st_size < item["bytes"]:
                raise Task23ProjectionError("append_only_ledger_truncated")
        elif sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise Task23ProjectionError(f"frozen_input_identity_mismatch:{item['path']}")

    if bindings["dataset_identity"] != config["dataset_identity"]:
        raise Task23ProjectionError("receipt_dataset_identity_mismatch")
    if bindings["member_set"] != config["population"]["primary_development"]["members"]:
        raise Task23ProjectionError("receipt_member_set_mismatch")
    boundary = config["r2_read_boundary"]
    if bindings["root_bindings"] != boundary["root_bindings"]:
        raise Task23ProjectionError("receipt_root_binding_mismatch")
    if bindings["allowed_value_filename"] != boundary["allowed_value_filename"]:
        raise Task23ProjectionError("receipt_value_filename_mismatch")
    holdout_binding = bindings["holdout_ledger"]
    holdout_path = repo_root / PurePosixPath(holdout_binding["path"])
    if sha256_file(holdout_path) != holdout_binding["sha256"]:
        raise Task23ProjectionError("holdout_ledger_changed_before_read")
    if receipt["r3_boundary"] != {
        "split": "R3",
        "state": "UNTOUCHED",
        "access": "DENY",
        "path_discovery": False,
        "value_read": False,
        "outcome_read": False,
    }:
        raise Task23ProjectionError("receipt_r3_boundary_mismatch")
    authority = receipt["authority"]
    if not authority["r2_value_read"] or authority["r2_value_files_max"] != 9:
        raise Task23ProjectionError("receipt_r2_read_cap_mismatch")
    for key in (
        "network",
        "provider_call",
        "credential_use",
        "drive_read",
        "external_api",
        "dependency_change",
        "r3_read",
        "outcome_path_read_outside_r2",
        "wallet_or_signer",
        "cash_or_credits",
    ):
        if authority[key]:
            raise Task23ProjectionError(f"receipt_forbidden_authority:{key}")
    if not receipt["ordering"]["receipt_written_before_value_open"]:
        raise Task23ProjectionError("receipt_ordering_not_sealed")
    return receipt


def _raw_response(quote: QuoteAttempt, raw: RawApiEvent) -> tuple[Decimal | None, int | None]:
    if sha256_bytes(raw.redacted_body) != raw.content_sha256:
        raise Task23ProjectionError("raw_body_hash_mismatch")
    if quote.response_content_sha256 != raw.content_sha256:
        raise Task23ProjectionError("quote_raw_hash_mismatch")
    if _enum_text(quote.status) != "QUOTE_AVAILABLE":
        return None, None
    try:
        response = json.loads(raw.redacted_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task23ProjectionError("quote_available_raw_response_invalid") from exc
    if not isinstance(response, dict):
        raise Task23ProjectionError("quote_available_raw_response_not_mapping")
    required = {
        "inputMint",
        "inAmount",
        "outputMint",
        "outAmount",
        "priceImpactPct",
        "routePlan",
    }
    if not required.issubset(response):
        raise Task23ProjectionError("quote_available_raw_response_missing_fields")
    if response["inputMint"] != quote.input_mint or response["outputMint"] != quote.output_mint:
        raise Task23ProjectionError("raw_normalized_mint_mismatch")
    if int(response["inAmount"]) != quote.input_requested_atomic:
        raise Task23ProjectionError("raw_normalized_input_amount_mismatch")
    if int(response["outAmount"]) != quote.output_quoted_atomic:
        raise Task23ProjectionError("raw_normalized_output_amount_mismatch")
    route_plan = response["routePlan"]
    if not isinstance(route_plan, list) or len(route_plan) != quote.route_count:
        raise Task23ProjectionError("raw_normalized_route_count_mismatch")
    try:
        price_impact = Decimal(str(response["priceImpactPct"]))
    except (InvalidOperation, ValueError) as exc:
        raise Task23ProjectionError("price_impact_decimal_invalid") from exc
    if not price_impact.is_finite():
        raise Task23ProjectionError("price_impact_not_finite")
    return price_impact, len(route_plan)


def _read_panel(path: Path, *, member_id: str, panel_id: str, allowed_envelope: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_bytes = path.read_bytes()
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_bytes.splitlines(), start=1):
        if not line:
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Task23ProjectionError(f"raw_json_invalid:{panel_id}:{member_id}:{line_number}") from exc
        if not isinstance(envelope, dict):
            raise Task23ProjectionError("raw_envelope_not_mapping")
        if not set(envelope).issubset(allowed_envelope | {"raw_event", "quote_attempt"}):
            raise Task23ProjectionError("raw_envelope_unallowlisted_field")
        if envelope.get("schema") != EXPECTED_RAW_SCHEMA:
            raise Task23ProjectionError("raw_envelope_schema_mismatch")
        if envelope.get("task_id") != "TASK-21" or envelope.get("batch_id") != "T21-R2":
            raise Task23ProjectionError("raw_envelope_population_mismatch")
        if envelope.get("member_id") != member_id or envelope.get("horizon_id") != panel_id:
            raise Task23ProjectionError("raw_envelope_path_identity_mismatch")
        raw = RawApiEvent.model_validate_json(
            json.dumps(envelope["raw_event"], separators=(",", ":"))
        )
        quote = QuoteAttempt.model_validate_json(
            json.dumps(envelope["quote_attempt"], separators=(",", ":"))
        )
        if raw.raw_event_id != quote.raw_event_id:
            raise Task23ProjectionError("raw_quote_event_id_mismatch")
        if envelope["request_hash"] != quote.request_hash or envelope["idempotency_key"] != quote.idempotency_key:
            raise Task23ProjectionError("raw_quote_request_identity_mismatch")
        if envelope["raw_content_sha256"] != raw.content_sha256:
            raise Task23ProjectionError("envelope_raw_hash_mismatch")
        if envelope["terminal_class"] != _enum_text(quote.status):
            raise Task23ProjectionError("envelope_terminal_mismatch")
        price_impact, raw_route_count = _raw_response(quote, raw)
        events.append(
            {
                "ordinal": envelope["call_ordinal"],
                "window_id": envelope["window_id"],
                "stop_reason": envelope.get("stop_reason"),
                "quote": quote,
                "price_impact": price_impact,
                "raw_route_count": raw_route_count,
            }
        )
    ordinals = [item["ordinal"] for item in events]
    if ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
        raise Task23ProjectionError("raw_call_ordinals_not_strictly_increasing")
    return events, {
        "path": path,
        "bytes": len(raw_bytes),
        "sha256": sha256_bytes(raw_bytes),
        "line_count": len(events),
    }


def _pair_events(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    pairs = {atomic: {"usd": usd, "buy": None, "sell": None} for usd, atomic in TESTED_NOTIONALS}
    for event in events:
        quote: QuoteAttempt = event["quote"]
        side = _enum_text(quote.side)
        if side == "BUY":
            pair = pairs.get(quote.input_requested_atomic)
            if pair is None or pair["buy"] is not None:
                raise Task23ProjectionError("buy_notional_unexpected_or_duplicate")
            pair["buy"] = event
        elif side == "SELL":
            candidates = []
            for pair in pairs.values():
                buy_event = pair["buy"]
                if buy_event is None or pair["sell"] is not None:
                    continue
                buy: QuoteAttempt = buy_event["quote"]
                if (
                    _enum_text(buy.status) == "QUOTE_AVAILABLE"
                    and buy.output_quoted_atomic == quote.input_requested_atomic
                    and buy.output_mint == quote.input_mint
                    and buy.input_mint == quote.output_mint
                ):
                    candidates.append(pair)
            if len(candidates) != 1:
                raise Task23ProjectionError("dependent_sell_pair_ambiguous_or_missing")
            candidates[0]["sell"] = event
        else:
            raise Task23ProjectionError("quote_side_not_buy_or_sell")
    return pairs


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Task23ProjectionError(f"output_already_exists:{path.name}") from exc


def build_projection(
    *, repo_root: Path, config_path: Path, receipt_path: Path, output_dir: Path
) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    config_path = config_path.resolve(strict=True)
    receipt_path = receipt_path.resolve(strict=True)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir = output_dir.resolve(strict=False)
    if not config_path.is_relative_to(repo_root) or not receipt_path.is_relative_to(repo_root):
        raise Task23ProjectionError("control_file_outside_repository")
    if not output_dir.is_relative_to(repo_root):
        raise Task23ProjectionError("output_directory_outside_repository")
    config = _load_yaml(config_path)
    validate_config(config)
    receipt = validate_pre_read_receipt(
        repo_root=repo_root,
        config_path=config_path,
        config=config,
        receipt_path=receipt_path,
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise Task23ProjectionError("output_directory_not_empty")

    members = config["population"]["primary_development"]["members"]
    allowed_envelope = set(config["allowed_fields"]["envelope"])
    panel_records: list[dict[str, Any]] = []
    raw_inputs: list[dict[str, Any]] = []

    for binding in config["r2_read_boundary"]["root_bindings"]:
        panel_id = binding["panel_id"]
        root = repo_root / PurePosixPath(binding["root"])
        root_resolved = _validate_safe_descendant(repo_root, root)
        for member_id in members:
            raw_path = root_resolved / f"member={member_id}" / f"horizon={panel_id}" / "raw_events.jsonl"
            if not raw_path.exists():
                panel_records.append(
                    {
                        "member_id": member_id,
                        "panel_id": panel_id,
                        "path": None,
                        "events": [],
                        "pairs": _pair_events([]),
                        "raw_input": None,
                        "state": "PANEL_MISSING",
                    }
                )
                continue
            raw_resolved = _validate_safe_descendant(repo_root, raw_path)
            relative = raw_resolved.relative_to(repo_root).as_posix()
            expected_prefix = f"{binding['root']}/member={member_id}/horizon={panel_id}/"
            if relative != expected_prefix + "raw_events.jsonl":
                raise Task23ProjectionError("raw_path_not_exact_allowlisted_shape")
            events, raw_input = _read_panel(
                raw_resolved,
                member_id=member_id,
                panel_id=panel_id,
                allowed_envelope=allowed_envelope,
            )
            raw_input["path"] = relative
            raw_inputs.append(raw_input)
            stop_reasons = sorted({item["stop_reason"] for item in events if item["stop_reason"]})
            panel_records.append(
                {
                    "member_id": member_id,
                    "panel_id": panel_id,
                    "path": relative,
                    "events": events,
                    "pairs": _pair_events(events),
                    "raw_input": raw_input,
                    "state": "CAPTURE_STOPPED" if stop_reasons else "OBSERVED",
                    "stop_reasons": stop_reasons,
                }
            )

    if len(raw_inputs) > receipt["authority"]["r2_value_files_max"]:
        raise Task23ProjectionError("r2_value_file_cap_exceeded")

    p0_baselines: dict[str, datetime] = {}
    for panel in panel_records:
        if panel["panel_id"] != "P0":
            continue
        moments = [item["quote"].first_reliable_available_at for item in panel["events"]]
        if moments:
            p0_baselines[panel["member_id"]] = min(moments)

    panel_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    for panel in panel_records:
        member_id = panel["member_id"]
        panel_id = panel["panel_id"]
        events = panel["events"]
        moments = [item["quote"].first_reliable_available_at for item in events]
        first_available = min(moments) if moments else None
        last_available = max(moments) if moments else None
        baseline = p0_baselines.get(member_id)
        elapsed = None
        if first_available is not None and baseline is not None:
            elapsed = Decimal(str((first_available - baseline).total_seconds()))
            if elapsed < 0:
                raise Task23ProjectionError("actual_elapsed_time_negative")
        terminal_counts = Counter(_enum_text(item["quote"].status) for item in events)
        buys = [item for item in events if _enum_text(item["quote"].side) == "BUY"]
        sells = [item for item in events if _enum_text(item["quote"].side) == "SELL"]
        panel_rows.append(
            {
                "member_id": member_id,
                "panel_id": panel_id,
                "window_id": events[0]["window_id"] if events else f"{member_id}-{panel_id}",
                "panel_state": panel["state"],
                "raw_path": panel["path"] or "",
                "raw_sha256": panel["raw_input"]["sha256"] if panel["raw_input"] else "",
                "observed_attempts": len(events),
                "observed_buy_legs": len(buys),
                "observed_sell_legs": len(sells),
                "quote_available": terminal_counts["QUOTE_AVAILABLE"],
                "no_route": terminal_counts["NO_ROUTE"],
                "provider_error": terminal_counts["PROVIDER_ERROR"],
                "invalid_response": terminal_counts["INVALID_RESPONSE"],
                "timeout": terminal_counts["TIMEOUT"],
                "first_reliable_available_at": _as_utc_text(first_available) if first_available else "",
                "last_reliable_available_at": _as_utc_text(last_available) if last_available else "",
                "actual_elapsed_from_member_p0_seconds": _decimal_text(elapsed),
                "stop_reasons": "|".join(panel.get("stop_reasons", [])),
            }
        )

        eligible_sells = 0
        observed_sells = 0
        complete_roundtrips: list[int] = []
        for atomic, pair in panel["pairs"].items():
            buy_event = pair["buy"]
            sell_event = pair["sell"]
            buy: QuoteAttempt | None = None if buy_event is None else buy_event["quote"]
            sell: QuoteAttempt | None = None if sell_event is None else sell_event["quote"]
            buy_status = panel["state"] if buy is None else _enum_text(buy.status)
            sell_eligible = buy is not None and _enum_text(buy.status) == "QUOTE_AVAILABLE"
            if sell_eligible:
                eligible_sells += 1
            if sell is not None:
                observed_sells += 1
            if sell is not None:
                sell_status = _enum_text(sell.status)
            elif not sell_eligible:
                sell_status = "SELL_NOT_ATTEMPTED"
            else:
                sell_status = "CAPTURE_STOPPED" if panel["state"] == "CAPTURE_STOPPED" else "PANEL_MISSING"
            retention = None
            if buy is not None and sell is not None and _enum_text(buy.status) == "QUOTE_AVAILABLE" and _enum_text(sell.status) == "QUOTE_AVAILABLE":
                if sell.output_decimals != buy.input_decimals or sell.output_mint != buy.input_mint:
                    raise Task23ProjectionError("roundtrip_output_unit_mismatch")
                retention = Decimal(sell.output_quoted_atomic) * Decimal(10_000) / Decimal(buy.input_requested_atomic)
                complete_roundtrips.append(pair["usd"])
            pair_rows.append(
                {
                    "member_id": member_id,
                    "panel_id": panel_id,
                    "window_id": events[0]["window_id"] if events else f"{member_id}-{panel_id}",
                    "tested_notional_usd": pair["usd"],
                    "buy_input_atomic": atomic,
                    "buy_status": buy_status,
                    "sell_eligible": _bool_text(sell_eligible),
                    "sell_status": sell_status,
                    "buy_route_count": "" if buy is None or buy.route_count is None else buy.route_count,
                    "sell_route_count": "" if sell is None or sell.route_count is None else sell.route_count,
                    "buy_price_impact_pct": "" if buy_event is None else _decimal_text(buy_event["price_impact"]),
                    "sell_price_impact_pct": "" if sell_event is None else _decimal_text(sell_event["price_impact"]),
                    "roundtrip_quote_retention_bps": _decimal_text(retention),
                    "buy_first_reliable_available_at": "" if buy is None else _as_utc_text(buy.first_reliable_available_at),
                    "sell_first_reliable_available_at": "" if sell is None else _as_utc_text(sell.first_reliable_available_at),
                    "actual_elapsed_from_member_p0_seconds": _decimal_text(elapsed),
                    "buy_error_class": "" if buy is None or buy.error_class is None else buy.error_class,
                    "sell_error_class": "" if sell is None or sell.error_class is None else sell.error_class,
                }
            )
        observed_buys = len(buys)
        available_buys = sum(_enum_text(item["quote"].status) == "QUOTE_AVAILABLE" for item in buys)
        available_sells = sum(_enum_text(item["quote"].status) == "QUOTE_AVAILABLE" for item in sells)
        diagnostic_rows.append(
            {
                "member_id": member_id,
                "panel_id": panel_id,
                "panel_state": panel["state"],
                "planned_buy_legs": 4,
                "observed_buy_legs": observed_buys,
                "available_buy_routes": available_buys,
                "buy_route_availability_rate_observed": _rate(available_buys, observed_buys),
                "eligible_dependent_sell_legs": eligible_sells,
                "observed_dependent_sell_legs": observed_sells,
                "available_dependent_sell_routes": available_sells,
                "sell_route_availability_rate_eligible": _rate(available_sells, eligible_sells),
                "quote_notional_capacity_proxy_usd": max(complete_roundtrips) if complete_roundtrips else "",
                "missing_buy_legs": 4 - observed_buys,
                "missing_eligible_sell_legs": eligible_sells - observed_sells,
                "actual_elapsed_from_member_p0_seconds": _decimal_text(elapsed),
                "cluster_id": "T21-R2-SINGLE-NOMINATION-CLUSTER",
                "inference_mode": "DESCRIPTIVE_ONLY",
            }
        )

    panel_rows.sort(key=lambda row: (row["member_id"], row["panel_id"]))
    pair_rows.sort(key=lambda row: (row["member_id"], row["panel_id"], int(row["tested_notional_usd"])))
    diagnostic_rows.sort(key=lambda row: (row["member_id"], row["panel_id"]))
    raw_inputs.sort(key=lambda row: row["path"])

    table_payloads = {
        "panel_inventory_v1.csv": _csv_bytes(panel_rows, list(panel_rows[0])),
        "quote_pair_availability_v1.csv": _csv_bytes(pair_rows, list(pair_rows[0])),
        "panel_diagnostics_v1.csv": _csv_bytes(diagnostic_rows, list(diagnostic_rows[0])),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in table_payloads.items():
        _write_new(output_dir / name, payload)

    output_inventory = [
        {
            "path": (output_dir / name).relative_to(repo_root).as_posix(),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "rows": len(panel_rows) if name == "panel_inventory_v1.csv" else len(pair_rows) if name == "quote_pair_availability_v1.csv" else len(diagnostic_rows),
        }
        for name, payload in sorted(table_payloads.items())
    ]
    summary = {
        "planned_panels": len(members) * 3,
        "observed_panels": sum(row["panel_state"] != "PANEL_MISSING" for row in panel_rows),
        "planned_buy_legs": len(members) * 3 * 4,
        "observed_buy_legs": sum(int(row["observed_buy_legs"]) for row in diagnostic_rows),
        "eligible_dependent_sell_legs": sum(int(row["eligible_dependent_sell_legs"]) for row in diagnostic_rows),
        "observed_dependent_sell_legs": sum(int(row["observed_dependent_sell_legs"]) for row in diagnostic_rows),
        "r2_value_files_opened": len(raw_inputs),
        "r3_paths_discovered": 0,
        "r3_value_files_opened": 0,
        "outcome_paths_outside_r2_opened": 0,
        "capture_clusters": 1,
        "members": len(members),
        "validation_population": "NONE",
        "inference_mode": "DESCRIPTIVE_ONLY",
    }
    manifest = {
        "schema": PROJECTION_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "MATERIALIZED_DETERMINISTIC_R2_ONLY",
        "created_at": receipt["created_at"],
        "bindings": {
            "contract": receipt["bindings"]["contract"],
            "config": receipt["bindings"]["config"],
            "projection_code": receipt["bindings"]["projection_code"],
            "pre_read_receipt": {
                "path": receipt_path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(receipt_path),
            },
            "dataset_identity": config["dataset_identity"],
            "member_set": members,
        },
        "raw_inputs": raw_inputs,
        "outputs": output_inventory,
        "summary": summary,
        "denominator_policy": config["denominators"],
        "nonclaims": [
            "NOT_POOL_LIQUIDITY",
            "NOT_MARKET_DEPTH",
            "NOT_FILLABLE_SIZE",
            "NOT_REALIZED_VWAP",
            "NOT_EXECUTION_CAPACITY",
            "NOT_NET_RETURN",
            "NOT_ALPHA",
            "NOT_POPULATION_GENERALIZATION",
        ],
        "next_boundary": {
            "atom_id": "T23-A4_BOUNDED_ANALYSIS_AND_ADVERSARIAL_ACCEPTANCE_V1",
            "authorized": False,
            "owner_decision": None,
            "r3_access": "DENY",
        },
    }
    manifest_payload = canonical_json_bytes(manifest)
    _write_new(output_dir / "projection_manifest_v1.json", manifest_payload)
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pre-read-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = build_projection(
        repo_root=args.repo_root,
        config_path=args.config,
        receipt_path=args.pre_read_receipt,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
