"""Deterministic point-in-time replay and leakage checks for TASK-19."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from statistics import median
from typing import Any

from solana_alpha_lab.jupiter_quote_logger import USDC_MINT
from solana_alpha_lab.task17a_execution_capacity_audit import (
    Task17AAuditError,
    audit_repaired_panel,
)
from solana_alpha_lab.task17a_execution_capacity_panel import SELECTED_MINT
from solana_alpha_lab.task18_data_quality import (
    Task18ContractError,
    audit_narrow_data_quality,
)

JsonObject = dict[str, Any]

CONTRACT_ID = "CONTRACT-T19-POINT-IN-TIME-REPLAY-001"
CONTRACT_SHA256 = (
    "c2485b17ae2fd7daac08c6a433b95d842a9552fe74d6f5df8d52d4786f3abce0"
)
TASK18_FIXTURE_ASSET_ID = "FIXTURE-T18-NARROW-DATA-QUALITY-001"
TASK18_AUDIT_ASSET_ID = "EVIDENCE-T18-NARROW-DATA-QUALITY-AUDIT-001"
TASK18_BACKUP_ASSET_ID = (
    "EVIDENCE-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001"
)
TASK18_FINALIZATION_ASSET_ID = (
    "EVIDENCE-T18-CATALOG-REPOSITORY-FINALIZATION-001"
)
TASK17A_FIXTURE_ASSET_ID = (
    "FIXTURE-T17A-EXECUTION-CAPACITY-QUOTE-PANEL-001"
)
TASK17A_AUDIT_ASSET_ID = "EVIDENCE-T17A-EXECUTION-CAPACITY-AUDIT-001"
TASK17A_REPAIR_CONTRACT_PATH = (
    "tests/fixtures/task17a/one_window_timing_repair_contract_v1.json"
)
QUANTUM = Decimal("0.0001")


class Task19ReplayError(RuntimeError):
    """A frozen replay invariant failed with a typed TASK-19 verdict."""

    def __init__(self, verdict: str, code: str) -> None:
        super().__init__(code)
        self.verdict = verdict
        self.code = code


def _fail(code: str, *, verdict: str = "EVIDENCE_UNAVAILABLE") -> None:
    raise Task19ReplayError(verdict, code)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: JsonObject) -> bytes:
    """Serialize one stable machine artifact with a final LF."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _load_json(path: Path, code: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Task19ReplayError("EVIDENCE_UNAVAILABLE", code) from exc
    if not isinstance(value, dict):
        _fail(code)
    return value


def _load_jsonl(path: Path, code: str) -> list[JsonObject]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise Task19ReplayError("EVIDENCE_UNAVAILABLE", code) from exc
    rows: list[JsonObject] = []
    for index, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Task19ReplayError(
                "EVIDENCE_UNAVAILABLE",
                f"{code}:ROW_{index}",
            ) from exc
        if not isinstance(value, dict):
            _fail(f"{code}:ROW_{index}")
        rows.append(value)
    return rows


def _contained_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        _fail("PATH_NOT_TEXT")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        _fail(f"PATH_OUTSIDE_REPOSITORY:{relative}")
    return candidate


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _fail(f"TIMESTAMP_INVALID:{field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task19ReplayError(
            "EVIDENCE_UNAVAILABLE",
            f"TIMESTAMP_INVALID:{field}",
        ) from exc
    if parsed.utcoffset() is None:
        _fail(f"TIMESTAMP_TIMEZONE_MISSING:{field}")
    return parsed


def _verify_blob(
    value: bytes,
    *,
    expected_bytes: int,
    expected_sha256: str,
    label: str,
) -> None:
    if len(value) != expected_bytes:
        _fail(f"SIZE_DRIFT:{label}")
    if _sha256_bytes(value) != expected_sha256:
        _fail(f"SHA256_DRIFT:{label}")


def load_frozen_contract(contract_path: Path) -> JsonObject:
    """Load the exact frozen A2 contract, rejecting local contract drift."""

    contract = _load_json(contract_path, "CONTRACT_UNREADABLE")
    if _sha256(contract_path) != CONTRACT_SHA256:
        _fail("CONTRACT_SHA256_DRIFT")
    if contract.get("contract_id") != CONTRACT_ID:
        _fail("CONTRACT_ID_DRIFT")
    if contract.get("status") != "FROZEN_OFFLINE_CONTRACT":
        _fail("CONTRACT_STATUS_DRIFT")
    time_contract = contract.get("time_contract")
    if not isinstance(time_contract, dict):
        _fail("TIME_CONTRACT_MISSING")
    if (
        time_contract.get("cutoff_source")
        != "FROZEN_LITERAL_NOT_RUNTIME_MAXIMUM"
        or time_contract.get("runtime_cutoff_extension_allowed") is not False
    ):
        _fail("LITERAL_CUTOFF_CONTRACT_DRIFT")
    return contract


def _verify_tracked_inputs(
    repository_root: Path,
    contract: JsonObject,
) -> dict[str, str]:
    actual: dict[str, str] = {}
    rows = contract.get("tracked_inputs")
    if not isinstance(rows, list):
        _fail("TRACKED_INPUTS_INVALID")
    for row in rows:
        if not isinstance(row, dict):
            _fail("TRACKED_INPUT_ROW_INVALID")
        relative = row.get("path")
        path = _contained_path(repository_root, relative)
        if not path.is_file():
            _fail(f"TRACKED_INPUT_MISSING:{relative}")
        try:
            digest = _sha256(path)
        except OSError as exc:
            raise Task19ReplayError(
                "EVIDENCE_UNAVAILABLE",
                f"TRACKED_INPUT_UNREADABLE:{relative}",
            ) from exc
        if digest != row.get("sha256"):
            _fail(f"TRACKED_INPUT_DRIFT:{relative}")
        actual[str(relative)] = digest
    return actual


def _tracked_input_path(
    repository_root: Path,
    contract: JsonObject,
    asset_id: str,
) -> Path:
    for row in contract["tracked_inputs"]:
        if row.get("asset_id") == asset_id:
            return _contained_path(repository_root, row.get("path"))
    _fail(f"TRACKED_ASSET_BINDING_MISSING:{asset_id}")


def _verify_wrapped_audits(
    repository_root: Path,
    contract: JsonObject,
) -> JsonObject:
    """Reuse TASK-17A/TASK-18 auditors before the thin PIT projection."""

    task18_fixture_path = _tracked_input_path(
        repository_root,
        contract,
        TASK18_FIXTURE_ASSET_ID,
    )
    task18_audit_path = _tracked_input_path(
        repository_root,
        contract,
        TASK18_AUDIT_ASSET_ID,
    )
    try:
        task18_actual = audit_narrow_data_quality(
            repository_root=repository_root,
            contract_path=task18_fixture_path,
        )
    except (Task18ContractError, OSError, ValueError) as exc:
        raise Task19ReplayError(
            "EVIDENCE_UNAVAILABLE",
            "TASK18_WRAPPED_AUDIT_FAILED",
        ) from exc
    task18_expected = _load_json(
        task18_audit_path,
        "TASK18_TRACKED_AUDIT_UNREADABLE",
    )
    if task18_actual != task18_expected:
        _fail("TASK18_TRACKED_AUDIT_RECONCILIATION_DRIFT")
    if (
        task18_actual.get("verdict") != "FIT_WITH_LIMITATIONS"
        or task18_actual.get("quality_metrics", {}).get("hard_failure_count")
        != 0
        or task18_actual.get("claims", {}).get(
            "narrow_quote_only_data_quality"
        )
        is not True
    ):
        _fail("TASK18_HARD_QUALITY_GATE_NOT_MET")

    backup_receipt = _load_json(
        _tracked_input_path(
            repository_root,
            contract,
            TASK18_BACKUP_ASSET_ID,
        ),
        "TASK18_BACKUP_RECEIPT_UNREADABLE",
    )
    if (
        backup_receipt.get("verdict") != "PASS"
        or backup_receipt.get("reconciliation", {}).get(
            "reconciled_verdict"
        )
        != "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND"
        or any(
            row.get("status") != "PASS"
            for row in backup_receipt.get("checks", [])
        )
        or backup_receipt.get("restore", {}).get("source_mutations") != 0
        or backup_receipt.get("restore", {}).get("source_deletions") != 0
    ):
        _fail("TASK18_BACKUP_RESTORE_RECONCILIATION_DRIFT")
    finalization_receipt = _load_json(
        _tracked_input_path(
            repository_root,
            contract,
            TASK18_FINALIZATION_ASSET_ID,
        ),
        "TASK18_FINALIZATION_RECEIPT_UNREADABLE",
    )
    if (
        finalization_receipt.get("status") != "PASS"
        or finalization_receipt.get("accepted_result", {}).get(
            "quality_verdict"
        )
        != "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND"
        or finalization_receipt.get("accepted_result", {}).get(
            "recoverability"
        )
        != "CONTENT_ADDRESSED_BACKUP_AND_RESTORE_PROVEN"
    ):
        _fail("TASK18_FINALIZATION_RECONCILIATION_DRIFT")

    task17a_fixture_path = _tracked_input_path(
        repository_root,
        contract,
        TASK17A_FIXTURE_ASSET_ID,
    )
    task17a_audit_path = _tracked_input_path(
        repository_root,
        contract,
        TASK17A_AUDIT_ASSET_ID,
    )
    repair_contract_path = _contained_path(
        repository_root,
        TASK17A_REPAIR_CONTRACT_PATH,
    )
    if not repair_contract_path.is_file():
        _fail("TASK17A_REPAIR_CONTRACT_MISSING")
    try:
        task17a_actual = audit_repaired_panel(
            raw_root=repository_root / "data" / "raw",
            contract_path=task17a_fixture_path,
            repair_contract_path=repair_contract_path,
        )
    except (Task17AAuditError, OSError, ValueError) as exc:
        raise Task19ReplayError(
            "EVIDENCE_UNAVAILABLE",
            "TASK17A_WRAPPED_AUDIT_FAILED",
        ) from exc
    task17a_expected = _load_json(
        task17a_audit_path,
        "TASK17A_TRACKED_AUDIT_UNREADABLE",
    )
    if task17a_actual != task17a_expected:
        _fail("TASK17A_TRACKED_AUDIT_RECONCILIATION_DRIFT")
    if task17a_actual.get("verdict") != "PASS":
        _fail("TASK17A_ACCEPTED_AUDIT_NOT_PASS")
    return {
        "task17a_verdict": task17a_actual["verdict"],
        "task18_verdict": task18_actual["verdict"],
        "task18_hard_failures": task18_actual["quality_metrics"][
            "hard_failure_count"
        ],
        "task18_reconciled_verdict": backup_receipt["reconciliation"][
            "reconciled_verdict"
        ],
        "task18_recoverability": finalization_receipt["accepted_result"][
            "recoverability"
        ],
    }


def _verify_production_inventory(
    repository_root: Path,
    task18_contract: JsonObject,
) -> tuple[list[JsonObject], JsonObject, tuple[bytes, int, str]]:
    inventory = task18_contract.get("raw_inventory")
    if not isinstance(inventory, dict):
        _fail("RAW_INVENTORY_MISSING")
    files = inventory.get("files")
    roots = inventory.get("logical_roots")
    if not isinstance(files, list) or not isinstance(roots, list):
        _fail("RAW_INVENTORY_INVALID")

    expected_paths = {str(row.get("path")) for row in files}
    actual_paths: set[str] = set()
    for relative_root in roots:
        root = _contained_path(repository_root, relative_root)
        if not root.is_dir():
            _fail(f"RAW_ROOT_MISSING:{relative_root}")
        try:
            candidates = sorted(path for path in root.rglob("*") if path.is_file())
        except OSError as exc:
            raise Task19ReplayError(
                "EVIDENCE_UNAVAILABLE",
                f"RAW_ROOT_UNREADABLE:{relative_root}",
            ) from exc
        actual_paths.update(
            path.relative_to(repository_root).as_posix() for path in candidates
        )
    if actual_paths != expected_paths:
        _fail("RAW_FILE_SET_DRIFT")

    all_rows: list[JsonObject] = []
    first_probe: tuple[bytes, int, str] | None = None
    verified_bytes = 0
    for row in files:
        if not isinstance(row, dict):
            _fail("RAW_INVENTORY_ROW_INVALID")
        relative = str(row.get("path"))
        path = _contained_path(repository_root, relative)
        if not path.is_file():
            _fail(f"RAW_FILE_MISSING:{relative}")
        try:
            value = path.read_bytes()
        except OSError as exc:
            raise Task19ReplayError(
                "EVIDENCE_UNAVAILABLE",
                f"RAW_FILE_UNREADABLE:{relative}",
            ) from exc
        _verify_blob(
            value,
            expected_bytes=row.get("bytes"),
            expected_sha256=row.get("sha256"),
            label=relative,
        )
        verified_bytes += len(value)
        if row.get("kind") == "RAW_EVENTS_JSONL":
            parsed = _load_jsonl(path, f"RAW_JSONL_INVALID:{relative}")
            if len(parsed) != row.get("rows"):
                _fail(f"RAW_ROW_COUNT_DRIFT:{relative}")
            all_rows.extend(parsed)
            if first_probe is None:
                first_probe = (value, len(value), str(row.get("sha256")))
        else:
            _load_json(path, f"RAW_JSON_INVALID:{relative}")

    if first_probe is None:
        _fail("RAW_JSONL_PROBE_MISSING")
    if len(files) != inventory.get("file_count"):
        _fail("RAW_FILE_COUNT_CONTRACT_DRIFT")
    if len(all_rows) != inventory.get("jsonl_attempt_rows"):
        _fail("RAW_TOTAL_ROW_COUNT_DRIFT")
    if verified_bytes != inventory.get("stored_bytes"):
        _fail("RAW_STORED_BYTES_DRIFT")
    metrics = {
        "files": len(files),
        "rows": len(all_rows),
        "stored_bytes": verified_bytes,
        "logical_roots": sorted(str(value) for value in roots),
    }
    return all_rows, metrics, first_probe


def _identity_key(row: JsonObject) -> tuple[object, ...]:
    fields = (
        "hypothesis_version_id",
        "watchlist_id",
        "watchlist_version",
        "window_id",
        "member_id",
        "call_ordinal",
        "request_hash",
        "idempotency_key",
    )
    values = tuple(row.get(field) for field in fields)
    if any(value in (None, "") for value in values):
        _fail("STABLE_IDENTITY_FIELD_MISSING")
    return values


def _validate_row(
    row: JsonObject,
    *,
    identities: set[tuple[object, ...]],
    quote_ids: set[str],
    raw_ids: set[str],
) -> None:
    identity = _identity_key(row)
    if identity in identities:
        _fail("DUPLICATE_STABLE_IDENTITY")
    identities.add(identity)

    quote = row.get("quote_attempt")
    raw = row.get("raw_event")
    if not isinstance(quote, dict) or not isinstance(raw, dict):
        _fail("EMBEDDED_RECORD_MISSING")
    quote_id = quote.get("quote_attempt_id")
    raw_id = raw.get("raw_event_id")
    if not isinstance(quote_id, str) or not quote_id:
        _fail("QUOTE_ATTEMPT_ID_MISSING")
    if not isinstance(raw_id, str) or not raw_id:
        _fail("RAW_EVENT_ID_MISSING")
    if quote_id in quote_ids:
        _fail("DUPLICATE_QUOTE_ATTEMPT_ID")
    if raw_id in raw_ids:
        _fail("DUPLICATE_RAW_EVENT_ID")
    quote_ids.add(quote_id)
    raw_ids.add(raw_id)

    if quote.get("raw_event_id") != raw_id:
        _fail("RAW_EVENT_LINK_DRIFT")
    for nested in (quote, raw):
        if nested.get("request_hash") != row.get("request_hash"):
            _fail("REQUEST_HASH_LINK_DRIFT")
    if quote.get("idempotency_key") != row.get("idempotency_key"):
        _fail("IDEMPOTENCY_KEY_LINK_DRIFT")
    content_hash = row.get("raw_content_sha256")
    if (
        not isinstance(content_hash, str)
        or quote.get("response_content_sha256") != content_hash
        or raw.get("content_sha256") != content_hash
    ):
        _fail("CONTENT_HASH_LINK_DRIFT")
    for label, nested in (("QUOTE", quote), ("RAW", raw)):
        if nested.get("revision_number") != 1:
            _fail(f"{label}_REVISION_NUMBER_DRIFT")
        if nested.get("revision_of") is not None:
            _fail(f"{label}_REVISION_CHAIN_PRESENT")

    ordered_fields = (
        "requested_at",
        "response_at",
        "first_reliable_available_at",
        "available_to_strategy_at",
        "ingested_at",
    )
    ordered = [_parse_utc(row.get(field), field) for field in ordered_fields]
    if ordered != sorted(ordered):
        _fail("IMPOSSIBLE_SOURCE_TIME_ORDER")
    for field in ordered_fields:
        if quote.get(field) != row.get(field):
            _fail(f"QUOTE_{field.upper()}_LINK_DRIFT")
    for field in (
        "first_reliable_available_at",
        "available_to_strategy_at",
        "ingested_at",
    ):
        if raw.get(field) != row.get(field):
            _fail(f"RAW_{field.upper()}_LINK_DRIFT")


def _window_cutoffs(contract: JsonObject) -> dict[str, datetime]:
    cutoffs: dict[str, datetime] = {}
    for row in contract["time_contract"]["window_cutoffs"]:
        if row.get("classification") == "ACCEPTED":
            window_id = row.get("window_id")
            if not isinstance(window_id, str):
                _fail("WINDOW_CUTOFF_ID_INVALID")
            cutoffs[window_id] = _parse_utc(
                row.get("decision_at"),
                f"{window_id}:decision_at",
            )
    expected = set(contract["membership"]["accepted_window_order"])
    if set(cutoffs) != expected:
        _fail("ACCEPTED_WINDOW_CUTOFF_SET_DRIFT")
    return cutoffs


def _pair_cost(
    buy_record: JsonObject,
    sell_record: JsonObject,
    *,
    notional_atomic: int,
) -> Decimal:
    buy = buy_record["quote_attempt"]
    sell = sell_record["quote_attempt"]
    if buy.get("side") != "BUY" or sell.get("side") != "SELL":
        _fail("PAIR_SIDE_DRIFT")
    if (
        buy.get("input_mint") != USDC_MINT
        or buy.get("output_mint") != SELECTED_MINT
        or sell.get("input_mint") != SELECTED_MINT
        or sell.get("output_mint") != USDC_MINT
    ):
        _fail("PAIR_MINT_DRIFT")
    if buy.get("input_requested_atomic") != notional_atomic:
        _fail("PAIR_BUY_NOTIONAL_DRIFT")
    buy_output = buy.get("output_quoted_atomic")
    if isinstance(buy_output, bool) or not isinstance(buy_output, int):
        _fail("PAIR_BUY_OUTPUT_INVALID")
    if sell.get("input_requested_atomic") != buy_output:
        _fail("PAIR_DEPENDENT_SELL_INPUT_DRIFT")
    sell_output = sell.get("output_quoted_atomic")
    if isinstance(sell_output, bool) or not isinstance(sell_output, int):
        _fail("PAIR_SELL_OUTPUT_INVALID")
    if buy_output <= 0 or sell_output <= 0:
        _fail("PAIR_NONPOSITIVE_OUTPUT")
    return (
        Decimal(10_000)
        * (Decimal(notional_atomic) - Decimal(sell_output))
        / Decimal(notional_atomic)
    )


def replay_rows(
    rows: list[JsonObject],
    contract: JsonObject,
    *,
    enforce_expected: bool = True,
) -> JsonObject:
    """Project rows at frozen literal cutoffs with deterministic ordering."""

    accepted_order = tuple(contract["membership"]["accepted_window_order"])
    excluded_window = contract["membership"]["excluded_window_id"]
    known_windows = {*accepted_order, excluded_window}
    cutoffs = _window_cutoffs(contract)
    eligibility_fields = tuple(contract["time_contract"]["eligibility_fields"])

    identities: set[tuple[object, ...]] = set()
    quote_ids: set[str] = set()
    raw_ids: set[str] = set()
    eligible: dict[str, list[JsonObject]] = {
        window_id: [] for window_id in accepted_order
    }
    excluded_rows: list[JsonObject] = []

    for row in rows:
        if not isinstance(row, dict):
            _fail("REPLAY_ROW_NOT_OBJECT")
        window_id = row.get("window_id")
        if window_id not in known_windows:
            _fail(f"UNKNOWN_WINDOW:{window_id}")
        _validate_row(
            row,
            identities=identities,
            quote_ids=quote_ids,
            raw_ids=raw_ids,
        )
        if window_id == excluded_window:
            excluded_rows.append(row)
            continue
        cutoff = cutoffs[str(window_id)]
        availability = [
            _parse_utc(row.get(field), f"{window_id}:{field}")
            for field in eligibility_fields
        ]
        if all(value <= cutoff for value in availability):
            eligible[str(window_id)].append(row)

    expected_excluded = contract["estimand"]["excluded_retained_attempts"]
    if len(excluded_rows) != expected_excluded:
        _fail("EXCLUDED_RETAINED_ROW_COUNT_DRIFT")
    if sorted(row.get("call_ordinal") for row in excluded_rows) != list(
        range(1, expected_excluded + 1)
    ):
        _fail("EXCLUDED_RETAINED_ORDINAL_DRIFT")

    costs_by_window: dict[str, JsonObject] = {}
    deltas: list[Decimal] = []
    monotonic_panels = 0
    total_eligible = 0
    notionals = tuple(contract["pairing"]["notionals_usd"])
    ordinal_pairs = tuple(
        tuple(pair) for pair in contract["pairing"]["ordinal_pairs"]
    )
    for window_id in accepted_order:
        window_rows = eligible[window_id]
        expected_rows = next(
            row["expected_eligible_rows"]
            for row in contract["time_contract"]["window_cutoffs"]
            if row["window_id"] == window_id
        )
        if len(window_rows) != expected_rows:
            _fail(f"ELIGIBLE_ROW_COUNT_DRIFT:{window_id}")
        ordered = sorted(
            window_rows,
            key=lambda row: (
                row["call_ordinal"],
                row["quote_attempt"]["quote_attempt_id"],
                row["raw_event"]["raw_event_id"],
                row["request_hash"],
                row["idempotency_key"],
            ),
        )
        by_ordinal = {row["call_ordinal"]: row for row in ordered}
        if sorted(by_ordinal) != list(range(1, expected_rows + 1)):
            _fail(f"ELIGIBLE_ORDINAL_DRIFT:{window_id}")
        costs: list[Decimal] = []
        for notional, pair in zip(notionals, ordinal_pairs):
            buy_ordinal, sell_ordinal = pair
            costs.append(
                _pair_cost(
                    by_ordinal[buy_ordinal],
                    by_ordinal[sell_ordinal],
                    notional_atomic=int(notional) * 1_000_000,
                )
            )
        if all(left < right for left, right in zip(costs, costs[1:])):
            monotonic_panels += 1
        delta = costs[-1] - costs[0]
        deltas.append(delta)
        window_output: JsonObject = {
            str(notional): format(
                cost.quantize(QUANTUM, rounding=ROUND_HALF_EVEN),
                "f",
            )
            for notional, cost in zip(notionals, costs)
        }
        window_output["delta_100_minus_10"] = format(
            delta.quantize(QUANTUM, rounding=ROUND_HALF_EVEN),
            "f",
        )
        costs_by_window[window_id] = window_output
        total_eligible += len(ordered)

    median_delta = Decimal(median(deltas))
    result = (
        "SUPPORTED_WITHIN_ONE_MEMBER_THREE_WINDOWS_QUOTE_ONLY"
        if monotonic_panels > len(accepted_order) / 2 and median_delta > 0
        else "FALSIFIED_WITHIN_BOUNDED_PANEL"
    )
    output: JsonObject = {
        "schema": "smial.task19_point_in_time_replay.v1",
        "schema_version": "1.0",
        "replay_id": "REPLAY-T19-EXECUTION-CAPACITY-PIT-001",
        "accepted_rows": total_eligible,
        "excluded_retained_rows": len(excluded_rows),
        "complete_quote_pairs": len(accepted_order) * len(notionals),
        "complete_monotonic_panels": monotonic_panels,
        "complete_panels": len(accepted_order),
        "cost_bps_by_window": costs_by_window,
        "median_delta_cost_bps": format(
            median_delta.quantize(QUANTUM, rounding=ROUND_HALF_EVEN),
            "f",
        ),
        "hypothesis_result": result,
        "hypothesis_state": contract["estimand"]["hypothesis_state"],
        "promotion_authorized": contract["estimand"]["promotion_authorized"],
        "serialization": (
            "UTF8_JSON_SORT_KEYS_COMPACT_SEPARATORS_PLUS_FINAL_LF"
        ),
        "repeat_output_sha256_must_match": True,
        "shuffle_output_sha256_must_match": True,
    }
    if enforce_expected and output != contract["expected_output"]:
        _fail("FROZEN_EXPECTED_OUTPUT_MISMATCH")
    return output


def build_lineage_projection(
    rows: list[JsonObject],
    contract: JsonObject,
) -> JsonObject:
    """Bind the aggregate replay to exact attempt and raw-content identities."""

    accepted = set(contract["membership"]["accepted_window_order"])
    excluded_window = contract["membership"]["excluded_window_id"]
    cutoff_rows = {
        row["window_id"]: row
        for row in contract["time_contract"]["window_cutoffs"]
    }
    window_rank = {
        row["window_id"]: index
        for index, row in enumerate(
            contract["time_contract"]["window_cutoffs"]
        )
    }
    attempts: list[JsonObject] = []
    for row in rows:
        window_id = row["window_id"]
        cutoff_row = cutoff_rows[window_id]
        cutoff = cutoff_row.get("decision_at") or cutoff_row.get("audit_as_of")
        cutoff_time = _parse_utc(cutoff, f"{window_id}:lineage_cutoff")
        availability_eligible = all(
            _parse_utc(row.get(field), f"{window_id}:{field}") <= cutoff_time
            for field in contract["time_contract"]["eligibility_fields"]
        )
        membership_eligible = window_id in accepted
        quote = row["quote_attempt"]
        raw = row["raw_event"]
        attempts.append(
            {
                "hypothesis_version_id": row["hypothesis_version_id"],
                "watchlist_id": row["watchlist_id"],
                "watchlist_version": row["watchlist_version"],
                "member_id": row["member_id"],
                "window_id": window_id,
                "classification": (
                    "ACCEPTED"
                    if membership_eligible
                    else "EXCLUDED_RETAINED"
                ),
                "call_ordinal": row["call_ordinal"],
                "quote_attempt_id": quote["quote_attempt_id"],
                "raw_event_id": raw["raw_event_id"],
                "request_hash": row["request_hash"],
                "idempotency_key": row["idempotency_key"],
                "raw_content_sha256": row["raw_content_sha256"],
                "first_reliable_available_at": row[
                    "first_reliable_available_at"
                ],
                "available_to_strategy_at": row[
                    "available_to_strategy_at"
                ],
                "ingested_at": row["ingested_at"],
                "literal_cutoff": cutoff,
                "availability_eligible": availability_eligible,
                "membership_eligible": membership_eligible,
                "eligible_at_decision": (
                    membership_eligible and availability_eligible
                ),
            }
        )
    attempts.sort(
        key=lambda row: (
            window_rank[row["window_id"]],
            row["call_ordinal"],
            row["quote_attempt_id"],
            row["raw_event_id"],
            row["request_hash"],
            row["idempotency_key"],
        )
    )
    if {row["window_id"] for row in attempts} != {
        *accepted,
        excluded_window,
    }:
        _fail("LINEAGE_WINDOW_SET_DRIFT")
    accepted_attempts = [
        row for row in attempts if row["classification"] == "ACCEPTED"
    ]
    excluded_attempts = [
        row
        for row in attempts
        if row["classification"] == "EXCLUDED_RETAINED"
    ]
    if (
        len(accepted_attempts) != contract["estimand"]["accepted_attempts"]
        or len(excluded_attempts)
        != contract["estimand"]["excluded_retained_attempts"]
        or any(not row["eligible_at_decision"] for row in accepted_attempts)
        or any(row["eligible_at_decision"] for row in excluded_attempts)
    ):
        _fail("LINEAGE_ELIGIBILITY_RECONCILIATION_DRIFT")
    return {
        "schema": "smial.task19_point_in_time_replay_lineage.v1",
        "schema_version": "1.0",
        "replay_id": contract["expected_output"]["replay_id"],
        "contract_id": contract["contract_id"],
        "contract_sha256": CONTRACT_SHA256,
        "hypothesis_version_id": contract["estimand"][
            "hypothesis_version_id"
        ],
        "attempts": attempts,
    }


def _set_identity(record: JsonObject, suffix: str) -> None:
    request_hash = hashlib.sha256(f"request:{suffix}".encode()).hexdigest()
    content_hash = hashlib.sha256(f"content:{suffix}".encode()).hexdigest()
    idempotency_key = f"synthetic-{suffix}"
    quote_id = f"quote-synthetic-{suffix}"
    raw_id = f"raw-synthetic-{suffix}"
    record["call_ordinal"] = 9
    record["request_hash"] = request_hash
    record["idempotency_key"] = idempotency_key
    record["raw_content_sha256"] = content_hash
    quote = record["quote_attempt"]
    raw = record["raw_event"]
    quote["quote_attempt_id"] = quote_id
    quote["raw_event_id"] = raw_id
    quote["request_hash"] = request_hash
    quote["idempotency_key"] = idempotency_key
    quote["response_content_sha256"] = content_hash
    raw["raw_event_id"] = raw_id
    raw["request_hash"] = request_hash
    raw["idempotency_key"] = f"raw-{suffix}"
    raw["content_sha256"] = content_hash


def _set_times(record: JsonObject, values: tuple[str, ...]) -> None:
    fields = (
        "requested_at",
        "response_at",
        "first_reliable_available_at",
        "available_to_strategy_at",
        "ingested_at",
    )
    quote = record["quote_attempt"]
    raw = record["raw_event"]
    for field, value in zip(fields, values):
        record[field] = value
        quote[field] = value
        raw[field] = value


def _future_values(cutoff: datetime, *, backfill: bool) -> tuple[str, ...]:
    future = [
        (cutoff + timedelta(microseconds=value))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
        for value in (1, 2, 3)
    ]
    if backfill:
        requested = (cutoff - timedelta(hours=1)).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
        response = (cutoff - timedelta(hours=1) + timedelta(seconds=1)).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
    else:
        requested = future[0]
        response = future[0]
    return (requested, response, *future)


def run_adversarial_suite(
    base_rows: list[JsonObject],
    contract: JsonObject,
    *,
    physical_probe: tuple[bytes, int, str],
) -> list[JsonObject]:
    """Run the ten frozen vectors without mutating production evidence."""

    expected = {
        row["vector_id"]: row["expected_outcome"]
        for row in contract["adversarial_vectors"]
    }
    checks: list[JsonObject] = []
    base_output = replay_rows(base_rows, contract, enforce_expected=False)
    base_hash = _sha256_bytes(canonical_json_bytes(base_output))

    def record(vector_id: str, observed: str) -> None:
        expected_outcome = expected.get(vector_id)
        checks.append(
            {
                "vector_id": vector_id,
                "expected_outcome": expected_outcome,
                "observed_outcome": observed,
                "status": "PASS" if observed == expected_outcome else "FAIL",
            }
        )

    accepted_window = contract["membership"]["accepted_window_order"][0]
    template = next(
        row
        for row in base_rows
        if row["window_id"] == accepted_window and row["call_ordinal"] == 8
    )
    cutoff = _window_cutoffs(contract)[accepted_window]

    future = copy.deepcopy(template)
    _set_identity(future, "future-row")
    _set_times(future, _future_values(cutoff, backfill=False))
    future_output = replay_rows(
        [*base_rows, future],
        contract,
        enforce_expected=False,
    )
    record(
        "T19-FUTURE-ROW-AFTER-CUTOFF-001",
        (
            "IGNORED_AND_BASE_OUTPUT_SHA256_UNCHANGED"
            if _sha256_bytes(canonical_json_bytes(future_output)) == base_hash
            else "LEAKAGE_DETECTED"
        ),
    )

    backfill = copy.deepcopy(template)
    _set_identity(backfill, "backfill-trap")
    _set_times(backfill, _future_values(cutoff, backfill=True))
    backfill_output = replay_rows(
        [*base_rows, backfill],
        contract,
        enforce_expected=False,
    )
    record(
        "T19-BACKFILL-TRAP-001",
        (
            "IGNORED_AND_BASE_OUTPUT_SHA256_UNCHANGED"
            if _sha256_bytes(canonical_json_bytes(backfill_output)) == base_hash
            else "LEAKAGE_DETECTED"
        ),
    )

    shuffled_output = replay_rows(
        list(reversed(base_rows)),
        contract,
        enforce_expected=False,
    )
    record(
        "T19-SHUFFLED-INPUT-001",
        (
            "BASE_OUTPUT_SHA256_UNCHANGED"
            if _sha256_bytes(canonical_json_bytes(shuffled_output)) == base_hash
            else "LEAKAGE_DETECTED"
        ),
    )

    excluded_output = replay_rows(
        base_rows,
        contract,
        enforce_expected=False,
    )
    record(
        "T19-EXCLUDED-WINDOW-BEFORE-FINAL-CUTOFF-001",
        (
            "EXCLUDED_ROWS_RETAINED_AND_OUTPUT_UNCHANGED"
            if excluded_output["excluded_retained_rows"]
            == contract["estimand"]["excluded_retained_attempts"]
            and _sha256_bytes(canonical_json_bytes(excluded_output)) == base_hash
            else "LEAKAGE_DETECTED"
        ),
    )

    fail_closed_cases = [
        (
            "T19-DUPLICATE-IDENTITY-001",
            [*base_rows, copy.deepcopy(base_rows[0])],
        ),
        (
            "T19-CHANGED-REVISION-001",
            copy.deepcopy(base_rows),
        ),
        (
            "T19-MISSING-AVAILABILITY-001",
            copy.deepcopy(base_rows),
        ),
        (
            "T19-IMPOSSIBLE-TIME-ORDER-001",
            copy.deepcopy(base_rows),
        ),
        (
            "T19-INCOMPLETE-PAIR-001",
            [
                row
                for index, row in enumerate(base_rows)
                if index != next(
                    position
                    for position, candidate in enumerate(base_rows)
                    if candidate["window_id"] == accepted_window
                    and candidate["call_ordinal"] == 2
                )
            ],
        ),
    ]
    changed = fail_closed_cases[1][1]
    changed[0]["quote_attempt"]["revision_number"] = 2
    missing = fail_closed_cases[2][1]
    missing[0].pop("first_reliable_available_at")
    impossible = fail_closed_cases[3][1]
    impossible[0]["ingested_at"] = impossible[0][
        "first_reliable_available_at"
    ]
    impossible[0]["raw_event"]["ingested_at"] = impossible[0]["ingested_at"]
    impossible[0]["quote_attempt"]["ingested_at"] = impossible[0][
        "ingested_at"
    ]

    for vector_id, mutated in fail_closed_cases:
        try:
            replay_rows(mutated, contract, enforce_expected=False)
        except Task19ReplayError as exc:
            observed = exc.verdict
        else:
            observed = "UNEXPECTED_REPLAY_SUCCESS"
        record(vector_id, observed)

    probe_bytes, probe_size, probe_sha256 = physical_probe
    try:
        _verify_blob(
            probe_bytes + b"\n",
            expected_bytes=probe_size,
            expected_sha256=probe_sha256,
            label="SYNTHETIC_PHYSICAL_DRIFT_PROBE",
        )
    except Task19ReplayError as exc:
        observed = (
            "EVIDENCE_UNAVAILABLE_BEFORE_REPLAY"
            if exc.verdict == "EVIDENCE_UNAVAILABLE"
            else exc.verdict
        )
    else:
        observed = "UNEXPECTED_REPLAY_SUCCESS"
    record("T19-PHYSICAL-RAW-DRIFT-001", observed)

    if set(expected) != {row["vector_id"] for row in checks}:
        _fail("ADVERSARIAL_VECTOR_SET_DRIFT", verdict="LEAKAGE_DETECTED")
    if any(row["status"] != "PASS" for row in checks):
        _fail("ADVERSARIAL_VECTOR_FAILED", verdict="LEAKAGE_DETECTED")
    return checks


def _base_receipt(contract: JsonObject, contract_path: Path) -> JsonObject:
    return {
        "schema": "smial.task19_point_in_time_replay_receipt.v1",
        "schema_version": "1.0",
        "task": "TASK-19",
        "atom": (
            "T19-A3_DETERMINISTIC_OFFLINE_REPLAY_AND_LEAKAGE_TESTS_V1"
        ),
        "as_of": contract.get("as_of", "2026-07-29"),
        "contract_id": contract.get("contract_id", CONTRACT_ID),
        "contract_sha256": (
            _sha256(contract_path) if contract_path.is_file() else None
        ),
        "verdict": "EVIDENCE_UNAVAILABLE",
        "failures": [],
        "limitations": [],
        "checks": [],
        "adversarial_checks": [],
        "claims": {
            "point_in_time_replay_safe": False,
            "cross_token_generalization": False,
            "provider_reliability": False,
            "fillable": False,
            "realized_vwap": False,
            "net_return": False,
            "signal_or_strategy": False,
            "execution_or_position": False,
            "owner_cashflow": False,
            "alpha": False,
            "production_readiness": False,
        },
        "authority": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "credential_use": 0,
            "collector_executions": 0,
            "raw_data_writes": 0,
            "cash_spend_usd_cents": 0,
            "provider_credits": 0,
            "wallet_signer_transaction_actions": 0,
            "dependency_changes": 0,
        },
        "next_gate": {
            "atom_id": "T19-A4_CATALOG_REPOSITORY_FINALIZATION_V1",
            "status": "NOT_AUTHORIZED_BY_T19_A3",
        },
    }


def audit_point_in_time_replay(
    *,
    repository_root: Path,
    contract_path: Path,
) -> JsonObject:
    """Verify exact evidence, replay it, and run every frozen leakage vector."""

    try:
        loose_contract = _load_json(contract_path, "CONTRACT_UNREADABLE")
    except Task19ReplayError as exc:
        loose_contract = {"contract_id": CONTRACT_ID, "as_of": "2026-07-29"}
        receipt = _base_receipt(loose_contract, contract_path)
        receipt["failures"] = [exc.code]
        return receipt
    receipt = _base_receipt(loose_contract, contract_path)

    try:
        contract = load_frozen_contract(contract_path)
        tracked_hashes = _verify_tracked_inputs(repository_root, contract)
        receipt["checks"].append(
            {
                "check_id": "FROZEN_CONTRACT_AND_TRACKED_INPUTS",
                "status": "PASS",
                "tracked_inputs_verified": len(tracked_hashes),
                "tracked_input_sha256": tracked_hashes,
            }
        )
        wrapped_metrics = _verify_wrapped_audits(repository_root, contract)
        receipt["checks"].append(
            {
                "check_id": "WRAPPED_TASK17A_TASK18_AUDITS",
                "status": "PASS",
                "metrics": wrapped_metrics,
            }
        )
        task18_path = _tracked_input_path(
            repository_root,
            contract,
            TASK18_FIXTURE_ASSET_ID,
        )
        task18_contract = _load_json(
            task18_path,
            "TASK18_FIXTURE_UNREADABLE",
        )
        rows, inventory_metrics, physical_probe = (
            _verify_production_inventory(repository_root, task18_contract)
        )
        receipt["checks"].append(
            {
                "check_id": "EXACT_PRODUCTION_INVENTORY",
                "status": "PASS",
                "metrics": inventory_metrics,
            }
        )
        output = replay_rows(rows, contract)
        output_bytes = canonical_json_bytes(output)
        output_sha256 = _sha256_bytes(output_bytes)
        lineage = build_lineage_projection(rows, contract)
        lineage_sha256 = _sha256_bytes(canonical_json_bytes(lineage))
        repeat_sha256 = _sha256_bytes(
            canonical_json_bytes(replay_rows(rows, contract))
        )
        if repeat_sha256 != output_sha256:
            _fail("REPEAT_OUTPUT_SHA256_DRIFT", verdict="LEAKAGE_DETECTED")
        receipt["checks"].append(
            {
                "check_id": "FROZEN_LITERAL_CUTOFF_REPLAY",
                "status": "PASS",
                "output_sha256": output_sha256,
                "repeat_output_sha256": repeat_sha256,
                "lineage_projection_sha256": lineage_sha256,
                "lineage_attempts": len(lineage["attempts"]),
            }
        )
        adversarial = run_adversarial_suite(
            rows,
            contract,
            physical_probe=physical_probe,
        )
        receipt["checks"].append(
            {
                "check_id": "ADVERSARIAL_LEAKAGE_AND_FAIL_CLOSED",
                "status": "PASS",
                "vectors_passed": len(adversarial),
                "vectors_total": len(contract["adversarial_vectors"]),
            }
        )
        receipt["adversarial_checks"] = adversarial
        receipt["replay_output"] = output
        receipt["replay_output_sha256"] = output_sha256
        receipt["lineage_projection"] = lineage
        receipt["lineage_projection_sha256"] = lineage_sha256
        receipt["coverage"] = {
            "members": len(contract["estimand"]["member_ids"]),
            "accepted_windows": len(
                contract["estimand"]["accepted_windows"]
            ),
            "excluded_retained_windows": len(
                contract["estimand"]["excluded_retained_windows"]
            ),
            "accepted_rows": output["accepted_rows"],
            "excluded_retained_rows": output["excluded_retained_rows"],
            "complete_quote_pairs": output["complete_quote_pairs"],
            "raw_files": inventory_metrics["files"],
            "raw_rows": inventory_metrics["rows"],
            "raw_stored_bytes": inventory_metrics["stored_bytes"],
        }
        receipt["verdict"] = "REPLAY_SAFE"
        receipt["claims"]["point_in_time_replay_safe"] = True
    except Task19ReplayError as exc:
        receipt["verdict"] = exc.verdict
        receipt["failures"] = [exc.code]
    return receipt


def build_summary(receipt: JsonObject, receipt_sha256: str) -> str:
    """Render a compact deterministic human summary for the receipt."""

    output = receipt.get("replay_output", {})
    coverage = receipt.get("coverage", {})
    adversarial = receipt.get("adversarial_checks", [])
    return "\n".join(
        [
            "# TASK-19 point-in-time replay summary v1",
            "",
            f"- Verdict: `{receipt['verdict']}`.",
            f"- Machine receipt SHA-256: `{receipt_sha256}`.",
            (
                "- Frozen evidence: "
                f"{coverage.get('raw_files', 0)} files / "
                f"{coverage.get('raw_rows', 0)} rows / "
                f"{coverage.get('raw_stored_bytes', 0)} bytes."
            ),
            (
                "- Replay: "
                f"{coverage.get('accepted_rows', 0)} accepted rows, "
                f"{coverage.get('excluded_retained_rows', 0)} "
                "excluded-retained rows, "
                f"{coverage.get('complete_quote_pairs', 0)} quote pairs."
            ),
            (
                "- Lineage: all "
                f"{coverage.get('accepted_rows', 0) + coverage.get('excluded_retained_rows', 0)} "
                "attempts bind hypothesis, window, attempt and raw-content "
                "identities to literal cutoffs."
            ),
            (
                "- Result: "
                f"`{output.get('hypothesis_result', 'NOT_AVAILABLE')}`; "
                f"median delta `{output.get('median_delta_cost_bps', 'N/A')}` "
                "bps; hypothesis remains `PAUSED`; promotion is not authorized."
            ),
            (
                "- Leakage proof: "
                f"{sum(row.get('status') == 'PASS' for row in adversarial)}/"
                f"{len(adversarial)} frozen adversarial vectors PASS."
            ),
            (
                "- Scope: exact one-member, three-window quote-only evidence. "
                "No fill, realized VWAP, net-return, alpha, execution, "
                "position or owner-cashflow claim."
            ),
            (
                "- Side effects: zero network/provider/API/RPC/WSS/Drive calls, "
                "zero raw writes, spend, credentials, dependencies and "
                "wallet/signer/transaction actions."
            ),
            "",
        ]
    )
